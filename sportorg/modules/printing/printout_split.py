import platform
from typing import Optional, List
from abc import ABC, abstractmethod

from sportorg.language import translate
from sportorg.models.memory import Group, Result, ResultStatus, race
from sportorg.models.result.result_calculation import ResultCalculation

if platform.system() == "Windows":
    import win32con
    import win32print
    import win32ui


class SplitPrinterStrategy(ABC):
    """Абстрактный класс стратегии печати сплитов"""

    @abstractmethod
    def print_splits(self, printer: 'SportorgPrinter', result: Result, course, group):
        pass

    @abstractmethod
    def format_split_line(self, split) -> str:
        pass


class NormalSplitPrinter(SplitPrinterStrategy):
    """Стратегия печати для обычного режима"""

    def print_splits(self, printer: 'SportorgPrinter', result: Result, course, group):
        """Печать сплитов в обычном режиме"""
        splits = result.splits.copy()
        is_penalty_used = race().get_setting("marked_route_mode", "off") != "off"
        is_relay = group.is_relay()

        index = 1
        for split in splits:
            line = self.format_split_line(split, index, course, is_penalty_used, is_relay)
            if line:
                printer.print_line(line, 'main')
                if split.is_correct:
                    index += 1

    def format_split_line(self, split, index: int, course, is_penalty_used: bool, is_relay: bool) -> str:
        """Форматирование строки сплита"""
        if not course:
            return self._format_split_without_course(split, index)
        elif split.is_correct:
            return self._format_correct_split(split, index, course, is_penalty_used, is_relay)
        else:
            return self._format_incorrect_split(split)

    def _format_split_without_course(self, split, index: int) -> str:
        """Форматирование сплита без информации о курсе"""
        return (
            f"{index:>3} "
            f"{split.code:>3} "
            f"{split.time.to_str()[-7:]}"
        )

    def _format_correct_split(self, split, index: int, course, is_penalty_used: bool, is_relay: bool) -> str:
        """Форматирование корректного сплита"""
        line_parts = [
            f"{split.course_index + 1:>3}",
            f"{split.code:>3}",
            f"{split.relative_time.to_str()[-7:]}",
            f"{split.leg_time.to_str()[-5:]}",
            f"{split.speed}",
        ]

        if not is_relay:
            line_parts.append(f"{split.leg_place:>3}")

        line = " ".join(line_parts)

        # Добавление маркера для отмеченных контрольных пунктов
        if is_penalty_used and course:
            for course_cp in course.controls:
                if str(course_cp).startswith(split.code):
                    line += " +"
                    break

        return line

    def _format_incorrect_split(self, split) -> str:
        """Форматирование некорректного сплита"""
        return (
                " " * 4 +
                f"{split.code:>3} "
                f"{split.relative_time.to_str()[-7:]}"
        )


class TrailOSplitPrinter(SplitPrinterStrategy):
    """Стратегия печати для режима Trail-O"""

    def print_splits(self, printer: 'SportorgPrinter', result: Result, course, group):
        """Печать сплитов в режиме Trail-O"""
        splits = result.splits.copy()
        splits.sort(key=lambda s: (int(s.code[:-1]), s.time))

        for split in splits:
            line = self.format_split_line(split)
            printer.print_line(line, 'main')

    def format_split_line(self, split) -> str:
        """Форматирование строки сплита для Trail-O"""
        if split.is_correct:
            return (
                f"{split.code[:-1]:>3} "
                f"{split.code[-1]:>3} "
                f"{split.relative_time.to_str()[-7:]}"
            )
        else:
            return (
                    " " * 4 +
                    f"{split.code[-1]:>3} "
                    f"{split.relative_time.to_str()[-7:]}"
            )


class SplitPrinterFactory:
    """Фабрика для создания стратегий печати сплитов"""

    @staticmethod
    def create_printer() -> SplitPrinterStrategy:
        """Создание стратегии печати в зависимости от режима"""
        if race().get_setting("result_processing_mode", "time") == "trailo":
            return TrailOSplitPrinter()
        else:
            return NormalSplitPrinter()


class SportorgPrinter:
    """Класс для печати результатов соревнований"""

    # Константы для стилей печати
    FONT_STYLES = {
        'small': {'name': 'Lucida Console', 'size': 2.5, 'weight': 400},
        'main': {'name': 'Lucida Console', 'size': 3, 'weight': 400},
        'large': {'name': 'Lucida Console', 'size': 4, 'weight': 400},
        'bold_large': {'name': 'Lucida Console', 'size': 4, 'weight': 700},
        'bib': {'name': 'Arial Black', 'size': 50, 'weight': 400},
        'penalty': {'name': 'Arial Black', 'size': 50, 'weight': 400},
        'penalty_small': {'name': 'Arial', 'size': 15, 'weight': 400},
    }

    def __init__(self, printer_name: Optional[str] = None, scale_factor: int = 60,
                 x_offset: int = 5, y_offset: int = 5):
        if platform.system() != "Windows":
            raise NotImplementedError("Printing is only supported on Windows")

        self.printer_name = printer_name or win32print.GetDefaultPrinter()
        self.scale_factor = scale_factor
        self.x_offset = x_offset
        self.y_offset = y_offset

        self._split_printer = SplitPrinterFactory.create_printer()
        self._init_printer()

    def _init_printer(self):
        self.dc = win32ui.CreateDC()
        self.dc.CreatePrinterDC(self.printer_name)
        self.dc.SetMapMode(win32con.MM_TWIPS)  # 1440 units per inch

        self.x = self.x_offset * self.scale_factor
        self.y = -self.y_offset * self.scale_factor

    def start_page(self):
        """Начало новой страницы"""
        self.dc.StartDoc(translate("SportOrg printing"))
        self.dc.StartPage()

    def end_page(self):
        """Завершение текущей страницы"""
        self.dc.EndPage()
        self.y = -self.y_offset * self.scale_factor  # Сброс позиции Y

    def end_doc(self):
        """Завершение документа"""
        self.dc.EndDoc()
        self.dc.DeleteDC()

    def move_cursor(self, offset: float):
        """Перемещение курсора по вертикали"""
        self.y -= int(self.scale_factor * offset)

    def print_line(self, text: str, font_style: str = 'main'):
        """Печать строки с указанным стилем шрифта"""
        style = self.FONT_STYLES[font_style]
        font = win32ui.CreateFont({
            "name": style['name'],
            "height": int(self.scale_factor * style['size']),
            "weight": style['weight'],
        })

        self.dc.SelectObject(font)
        self.dc.TextOut(self.x, self.y, str(text))
        self.move_cursor(style['size'] * 1.3)

    def print_split(self, result: Result):
        """Печать результата в зависимости от режима"""
        if self._is_penalty_laps_mode():
            self._print_penalty_laps_split(result)
        else:
            self._print_normal_split(result)

    def _is_penalty_laps_mode(self) -> bool:
        """Проверка режима кругов штрафа"""
        return (race().get_setting("marked_route_if_counting_lap", False) and
                race().get_setting("marked_route_mode", "laps") == "laps")

    def _print_penalty_laps_split(self, result: Result):
        """Печать номера и штрафных кругов"""
        if not result.person:
            return

        self._print_vertical_space(20)
        self._print_bib_line(result)
        self._print_vertical_space(7)
        self._print_penalty_line(result)

    def _print_vertical_space(self, lines: int):
        """Печать вертикального пробела"""
        for _ in range(lines):
            self.print_line(".", 'main')

    def _print_bib_line(self, result: Result):
        """Печать номера участника"""
        text = str(result.person.bib) if result.person else ""
        self.print_line(text, 'bib')

    def _print_penalty_line(self, result: Result):
        """Печать информации о штрафных кругах"""
        laps = result.penalty_laps
        if not result.is_status_ok():
            laps = max(2, laps)  # Минимум 2 круга для дисквалифицированных

        text = str(laps).rjust(2)
        self.print_line(text, 'penalty')

        # Добавление подписи "laps"
        text_small = " " + translate("laps")
        self._print_suffix_text(text, text_small, 'penalty_small')

        self.end_page()

    def _print_suffix_text(self, main_text: str, suffix_text: str, font_style: str):
        """Печать дополнительного текста после основного"""
        dx1, dy1 = self.dc.GetTextExtent(main_text)
        style = self.FONT_STYLES[font_style]

        font = win32ui.CreateFont({
            "name": style['name'],
            "height": int(self.scale_factor * style['size']),
            "weight": style['weight'],
        })

        self.dc.SelectObject(font)
        _, dy2 = self.dc.GetTextExtent(suffix_text)
        dy = int(0.8 * (dy1 - dy2))  # Выравнивание по базовой линии

        self.dc.TextOut(self.x + dx1, self.y - dy, suffix_text)

    def _print_normal_split(self, result: Result):
        """Печать обычного результата с детальной информацией"""
        if not result.person or result.status in [
            ResultStatus.DID_NOT_START,
            ResultStatus.DID_NOT_FINISH,
        ]:
            return

        race_obj = race()
        person = result.person
        group = person.group or Group(name="-")
        course = race_obj.find_course(result)

        # Печать заголовка и информации о событии
        self._print_event_info(race_obj)

        # Печать информации об участнике
        self._print_athlete_info(person, group, result)

        # Печать сплитов с использованием стратегии
        self._print_splits_with_strategy(result, course, group)

        # Печать финишной информации
        self._print_finish_info(result, group)

        # Печать дополнительной информации
        self._print_additional_info(result, group, race_obj)

        self.end_page()

    def _print_event_info(self, race_obj):
        """Печать информации о событии"""
        self.print_line(race_obj.data.title, 'main')
        event_info = f"{str(race_obj.data.start_datetime)[:10]}, {race_obj.data.location}"
        self.print_line(event_info, 'main')

    def _print_athlete_info(self, person, group, result):
        """Печать информации об участнике"""
        self.print_line(person.full_name, 'bold_large')
        self.print_line(f"{translate('Group')}: {group.name}", 'main')

        if person.organization:
            self.print_line(f"{translate('Team')}: {person.organization.name}", 'main')

        bib_card_info = (
            f"{translate('Bib')}: {person.bib}     "
            f"{translate('Card')}: {person.card_number}"
        )
        self.print_line(bib_card_info, 'main')
        self.print_line(f"{translate('Start')}: {result.get_start_time().to_str()}", 'main')

    def _print_splits_with_strategy(self, result: Result, course, group):
        """Печать сплитов с использованием выбранной стратегии"""
        self._split_printer.print_splits(self, result, course, group)

    def _print_finish_info(self, result: Result, group):
        """Печать информации о финише и результате"""
        splits = result.splits
        finish_split = ""
        if splits:
            finish_split = (result.get_finish_time() - splits[-1].time).to_str()

        self.print_line(
            f"{translate('Finish')}: {result.get_finish_time().to_str()}     {finish_split}",
            'main'
        )

        # Результат
        result_text = f"{translate('Result')}: {result.get_result()}"
        if result.is_status_ok():
            result_text += f"     {result.speed}"
        self.print_line(result_text, 'main')

    def _print_additional_info(self, result: Result, group, race_obj):
        """Печать дополнительной информации"""
        self._print_penalty_info(result)
        self._print_credit_time_info(result)
        self._print_rogaine_info(result)
        self._print_place_info(result, group)
        self._print_competition_info(result, group, race_obj)
        self._print_status_info(result, group)
        self._print_draft_results(group)
        self._print_footer(race_obj)

    def _print_penalty_info(self, result: Result):
        """Печать информации о штрафах"""
        penalty_mode = race().get_setting("marked_route_mode")
        if penalty_mode == "time":
            self.print_line(
                f"{translate('Penalty')}: {result.get_penalty_time().to_str()}",
                'main'
            )
        elif penalty_mode == "laps":
            self.print_line(
                f"{translate('Penalty')}: {result.penalty_laps}",
                'main'
            )

    def _print_credit_time_info(self, result: Result):
        """Печать информации о кредитном времени"""
        if race().get_setting("credit_time_enabled", False):
            self.print_line(
                f"{translate('Credit')}: {result.get_credit_time().to_str()}",
                'main'
            )

    def _print_rogaine_info(self, result: Result):
        """Печать информации для рогейна"""
        if (race().get_setting("result_processing_mode", "time") == "scores" and
                result.rogaine_penalty > 0):
            penalty = result.rogaine_penalty
            total_score = result.rogaine_score + penalty

            self.print_line(
                f"{translate('Points gained')}: {total_score}",
                'main'
            )
            self.print_line(
                f"{translate('Penalty for finishing late')}: {penalty}",
                'main'
            )

    def _print_place_info(self, result: Result, group):
        """Печать информации о месте"""
        if result.place > 0 and group.name != "-":
            place_text = f"{translate('Place')}: {result.place}"
            if not group.is_relay():
                place_text += (
                    f" {translate('from')} {group.count_finished} "
                    f"({translate('total')} {group.count_person})"
                )
            self.print_line(place_text, 'main')
        elif result.person.is_out_of_competition:
            self.print_line(f"{translate('Place')}: {translate('o/c').upper()}", 'main')

    def _print_competition_info(self, result: Result, group, race_obj):
        """Печать информации о конкуренции"""
        if (result.is_status_ok() and not group.is_relay() and
                race_obj.get_setting("result_processing_mode", "time") != "scores" and
                group.name != "-"):

            if race_obj.get_setting("system_start_source", "protocol") == "protocol":
                if hasattr(result, "can_win_count"):
                    if result.can_win_count > 0:
                        self.print_line(
                            f"{translate('Who can win you')}: {result.can_win_count}",
                            'main'
                        )
                        self.print_line(
                            f"{translate('Final result will be known')}: "
                            f"{result.final_result_time.to_str()}",
                            'main'
                        )
                    else:
                        self.print_line(translate("Result is final"), 'main')

    def _print_status_info(self, result: Result, group):
        """Печать информации о статусе"""
        if group.name == "-":
            return

        status_text = translate("Status: OK") if result.is_status_ok() else translate("Status: DSQ")
        self.print_line(status_text, 'bold_large')

        if not result.is_status_ok():
            self._print_course_controls(result)

    def _print_course_controls(self, result: Result):
        """Печать контрольных пунктов курса"""
        course = race().find_course(result)
        if not course or not course.controls:
            return

        cp_list = ""
        line_limit = 35

        for cp in course.controls:
            cp_code = cp.code.split("(")[0]
            if len(cp_list) + len(cp_code) + 1 > line_limit:
                self.print_line(cp_list, 'main')
                cp_list = ""
            cp_list += cp_code + " "

        if cp_list:
            self.print_line(cp_list, 'main')

    def _print_draft_results(self, group):
        """Печать предварительных результатов"""
        if group.is_relay() or group.name == "-":
            return

        race_obj = race()
        is_rogaine = race_obj.get_setting("result_processing_mode", "time") == "scores"
        results = ResultCalculation(race_obj).get_group_finishes(group)

        self.print_line(translate("Draft results"), 'main')

        font_style = 'small' if is_rogaine else 'main'
        for cur_res in results[:10]:
            result_line = (
                f"{cur_res.get_place():>3} "
                f"{cur_res.person.full_name:<22} "
                f"{cur_res.get_result()}"
            )
            self.print_line(result_line, font_style)

    def _print_footer(self, race_obj):
        """Печать футера"""
        self.print_line(race_obj.data.url, 'main')