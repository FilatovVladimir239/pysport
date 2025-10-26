import datetime
import logging
import time
from queue import Empty, Queue
from threading import Event
from typing import Optional, Callable

from PySide6.QtCore import QThread, Signal

from sportorg.common.singleton import singleton
from sportorg.language import translate
from sportorg.libs.sfr import sfrreader
from sportorg.libs.sfr.sfrreader import SFRReaderCardChanged, SFRReaderException
from sportorg.models import memory
from sportorg.models.memory import TrailOAns, ResultSFR, Split
from sportorg.modules.sportident import backup
from sportorg.utils.time import time_to_otime


class SFRReaderCommand:
    def __init__(self, command: str, data=None):
        self.command = command
        self.data = data


class CardDataProcessor:

    def __init__(self):
        self.is_trailo = memory.race().get_setting("result_processing_mode", "time") == "trailo"

    def process_card_data(self, card_data: dict) -> ResultSFR:
        card_number = card_data["bib"]

        if self.is_trailo:
            return self._process_trailo_card(card_data, card_number)
        else:
            return self._process_standard_card(card_data, card_number)

    def _process_trailo_card(self, card_data: dict, card_number: int) -> ResultSFR:
        trailo_ans = card_number % 10
        card_number = card_number // 10

        result = self._create_result(card_number)
        self._add_splits(result, card_data["punches"], trailo_ans)
        self._add_times(result, card_data)

        return result

    def _process_standard_card(self, card_data: dict, card_number: int) -> ResultSFR:
        result = self._create_result(card_number)
        self._add_splits(result, card_data["punches"])
        self._add_times(result, card_data)

        return result

    def _create_result(self, card_number: int) -> ResultSFR:
        result = memory.race().new_result(ResultSFR)
        result.card_number = card_number
        return result

    def _add_splits(self, result: ResultSFR, punches: list, trailo_ans: Optional[int] = None):
        for punch_code, punch_time in punches:
            if not punch_time:
                continue

            code = str(punch_code)
            if code == "0":
                continue

            if trailo_ans is not None:
                code = code + TrailOAns(trailo_ans).name

            split = self._create_split(code, punch_time)
            if split.code not in ("0", ""):
                result.splits.append(split)

    def _create_split(self, code: str, punch_time) -> Split:
        split = Split()
        split.code = code
        split.time = time_to_otime(punch_time)
        split.days = memory.race().get_days(punch_time)
        return split

    def _add_times(self, result: ResultSFR, card_data: dict):
        """Добавление времени старта и финиша"""
        if card_data["start"]:
            result.start_time = time_to_otime(card_data["start"])
        if card_data["finish"]:
            result.finish_time = time_to_otime(card_data["finish"])


class SFRReaderThread(QThread):
    POLL_TIMEOUT = 0.2

    def __init__(self, queue: Queue, stop_event: Event, logger: logging.Logger):
        super().__init__()
        self.setObjectName(self.__class__.__name__)
        self._queue = queue
        self._stop_event = stop_event
        self._logger = logger

    def run(self):
        try:
            sfr = sfrreader.SFRReaderReadout(logger=logging.root)
        except Exception as e:
            self._logger.error(f"Failed to initialize SFR reader: {e}")
            return

        self._poll_cards(sfr)
        sfr.disconnect()

    def _poll_cards(self, sfr):
        """Опрос карт в цикле"""
        while not self._stop_event.is_set():
            try:
                if sfr.poll_card():
                    self._process_card(sfr)
                else:
                    time.sleep(self.POLL_TIMEOUT)
            except (SFRReaderException, SFRReaderCardChanged) as e:
                self._logger.error(str(e))
            except Exception as e:
                self._logger.error(f"Unexpected error: {e}")

    def _process_card(self, sfr):
        card_data = sfr.read_card()
        if sfr.is_card_connected():
            self._queue.put(SFRReaderCommand("card_data", card_data), timeout=1)
            sfr.ack_card()


class ResultProcessorThread(QThread):
    data_sender = Signal(object)

    def __init__(self, queue: Queue, stop_event: Event, logger: logging.Logger):
        super().__init__()
        self.setObjectName(self.__class__.__name__)
        self._queue = queue
        self._stop_event = stop_event
        self._logger = logger
        self._card_processor = CardDataProcessor()

    def run(self):
        time.sleep(3)  # Задержка для инициализации

        while not self._stop_event.is_set():
            try:
                self._process_queue()
            except Exception as e:
                self._logger.error(f"Error in result processor: {e}")

        self._logger.debug("Result processor stopped")

    def _process_queue(self):
        try:
            cmd = self._queue.get(timeout=5)
            if cmd.command == "card_data":
                self._process_card_data(cmd.data)
        except Empty:
            pass  # Таймаут - нормальная ситуация

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
        self._processor_thread: Optional[ResultProcessorThread] = None
        self._logger = logging.root
        self._callback: Optional[Callable] = None

    def set_call(self, callback: Callable) -> 'SFRReaderClient':
        self._callback = callback
        return self

    def start(self):
        self._stop_event.clear()
        self._start_reader_thread()
        self._start_processor_thread()

    def stop(self):
        self._stop_event.set()
        self._logger.info(translate("Closing connection"))

    def toggle(self):
        if self.is_alive():
            self.stop()
        else:
            self.start()

    def is_alive(self) -> bool:
        return (self._reader_thread and not self._reader_thread.isFinished() and
                self._processor_thread and not self._processor_thread.isFinished())

    def _start_reader_thread(self):
        if self._reader_thread is None or self._reader_thread.isFinished():
            self._reader_thread = SFRReaderThread(
                self._queue, self._stop_event, self._logger
            )
            self._reader_thread.start()

    def _start_processor_thread(self):
        if self._processor_thread is None or self._processor_thread.isFinished():
            self._processor_thread = ResultProcessorThread(
                self._queue, self._stop_event, self._logger
            )

            if self._callback:
                self._processor_thread.data_sender.connect(self._callback)

            self._processor_thread.start()

    @staticmethod
    def get_start_time() -> datetime.datetime:
        start_time = memory.race().get_setting("system_zero_time", (8, 0, 0))
        return datetime.datetime.today().replace(
            hour=start_time[0],
            minute=start_time[1],
            second=start_time[2],
            microsecond=0,
        )
