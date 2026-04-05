import datetime
import logging
import time
from queue import Empty, Queue
from threading import Event, main_thread
from typing import Callable, Optional

try:
    from PySide6.QtCore import QThread, Signal
except ModuleNotFoundError:
    from PySide2.QtCore import QThread, Signal

from sportorg.common.singleton import singleton
from sportorg.language import translate
from sportorg.libs.sfr import sfrreader
from sportorg.libs.sfr.sfrreader import SFRReaderCardChanged, SFRReaderException
from sportorg.models import memory
from sportorg.models.memory import ResultSFR, Split
from sportorg.modules.trailo.sfr_card import TrailoSfrCardProcessor
from sportorg.modules.sportident import backup
from sportorg.utils.time import time_to_otime


class SFRReaderCommand:
    def __init__(self, command: str, data=None):
        self.command = command
        self.data = data


class CardDataProcessor:
    def __init__(self):
        self.is_trailo = (
            memory.race().get_setting("result_processing_mode", "time") == "trailo"
        )

    def process_card_data(self, card_data: dict) -> ResultSFR:
        card_number = card_data["bib"]

        if self.is_trailo:
            return self._process_trailo_card(card_data, card_number)
        return self._process_standard_card(card_data, card_number)

    def _process_trailo_card(self, card_data: dict, bib) -> ResultSFR:
        card_number, trailo_ans = TrailoSfrCardProcessor.decode_bib(bib)
        result = self._create_result(card_number)
        TrailoSfrCardProcessor.append_splits(result, card_data["punches"], trailo_ans)
        self._add_times(result, card_data)
        return result

    def _process_standard_card(self, card_data: dict, card_number) -> ResultSFR:
        result = self._create_result(card_number)
        self._add_splits_standard(result, card_data["punches"])
        self._add_times(result, card_data)
        return result

    def _create_result(self, card_number) -> ResultSFR:
        result = memory.race().new_result(ResultSFR)
        result.card_number = card_number
        return result

    def _add_splits_standard(self, result: ResultSFR, punches: list) -> None:
        for punch_code, punch_time in punches:
            if not punch_time:
                continue

            code = str(punch_code)
            if code == "0":
                continue

            split = self._create_split(code, punch_time)
            if split.code not in ("0", ""):
                result.splits.append(split)

    def _create_split(self, code: str, punch_time) -> Split:
        split = Split()
        split.code = code
        split.time = time_to_otime(punch_time)
        split.days = memory.race().get_days(punch_time)
        return split

    def _add_times(self, result: ResultSFR, card_data: dict) -> None:
        if card_data["start"]:
            result.start_time = time_to_otime(card_data["start"])
        if card_data["finish"]:
            result.finish_time = time_to_otime(card_data["finish"])


class SFRReaderThread(QThread):
    POLL_TIMEOUT = 0.2

    def __init__(self, queue: Queue, stop_event: Event, logger: logging.Logger, debug=False):
        super().__init__()
        self.setObjectName(self.__class__.__name__)
        self._queue = queue
        self._stop_event = stop_event
        self._logger = logger
        self._debug = debug

    def run(self):
        try:
            sfr = sfrreader.SFRReaderReadout(logger=logging.root)
        except Exception as e:
            self._logger.error(str(e))
            return
        while True:
            try:
                while not sfr.poll_card():
                    time.sleep(self.POLL_TIMEOUT)
                    if not main_thread().is_alive() or self._stop_event.is_set():
                        sfr.disconnect()
                        self._logger.debug("Stop sfrreader")
                        return
                self._process_card(sfr)
            except SFRReaderException as e:
                self._logger.error(str(e))
            except SFRReaderCardChanged as e:
                self._logger.error(str(e))
            except Exception as e:
                self._logger.error(str(e))

    def _process_card(self, sfr):
        card_data = sfr.read_card()
        if sfr.is_card_connected():
            self._queue.put(SFRReaderCommand("card_data", card_data), timeout=1)
            sfr.ack_card()


class ResultThread(QThread):
    data_sender = Signal(object)

    def __init__(self, queue: Queue, stop_event: Event, logger: logging.Logger, start_time=None):
        super().__init__()
        self.setObjectName(self.__class__.__name__)
        self._queue = queue
        self._stop_event = stop_event
        self._logger = logger
        self.start_time = start_time
        self._card_processor = CardDataProcessor()

    def run(self):
        time.sleep(3)
        while True:
            try:
                cmd = self._queue.get(timeout=5)
                if cmd.command == "card_data":
                    self._process_card_data(cmd.data)
            except Empty:
                if not main_thread().is_alive() or self._stop_event.is_set():
                    break
            except Exception as e:
                self._logger.error(str(e))
        self._logger.debug("Stop adder result")

    def _process_card_data(self, card_data: dict):
        result = self._card_processor.process_card_data(card_data)
        self.data_sender.emit(result)
        backup.backup_data(card_data)


@singleton
class SFRReaderClient:
    def __init__(self):
        self._queue = Queue()
        self._stop_event = Event()
        self._reader_thread: Optional[SFRReaderThread] = None
        self._result_thread: Optional[ResultThread] = None
        self._logger = logging.root
        self._callback: Optional[Callable] = None

    def set_call(self, value):
        if self._callback is None:
            self._callback = value
        return self

    def _start_reader_thread(self):
        if self._reader_thread is None:
            self._reader_thread = SFRReaderThread(
                self._queue, self._stop_event, self._logger, debug=True
            )
            self._reader_thread.start()
        elif self._reader_thread.isFinished():
            self._reader_thread = None
            self._start_reader_thread()

    def _start_result_thread(self):
        if self._result_thread is None:
            self._result_thread = ResultThread(
                self._queue, self._stop_event, self._logger, self.get_start_time()
            )
            if self._callback:
                self._result_thread.data_sender.connect(self._callback)
            self._result_thread.start()
        elif self._result_thread.isFinished():
            self._result_thread = None
            self._start_result_thread()

    def is_alive(self):
        if self._reader_thread and self._result_thread:
            return (
                not self._reader_thread.isFinished()
                and not self._result_thread.isFinished()
            )
        return False

    def start(self):
        self._stop_event.clear()
        self._start_reader_thread()
        self._start_result_thread()

    def stop(self):
        self._stop_event.set()
        self._logger.info(translate("Closing connection"))

    def toggle(self):
        if self.is_alive():
            self.stop()
            return
        self.start()

    @staticmethod
    def get_start_time():
        start_time = memory.race().get_setting("system_zero_time", (8, 0, 0))
        return datetime.datetime.today().replace(
            hour=start_time[0],
            minute=start_time[1],
            second=start_time[2],
            microsecond=0,
        )
