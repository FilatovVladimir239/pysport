"""Разбор данных SFR-карты в режиме TrailO (коды КП, ответ на карте)."""

from typing import Optional, Tuple, Union

from sportorg.models import memory
from sportorg.models.memory import TrailOAns, ResultSFR, Split
from sportorg.utils.time import time_to_otime


class TrailoSfrCardProcessor:

    @staticmethod
    def decode_bib(bib: Union[int, str]) -> Tuple[int, int]:
        n = int(bib)
        return n // 10, n % 10

    @staticmethod
    def append_splits(
        result: ResultSFR, punches: list, trailo_ans: int
    ) -> None:
        for punch_code, punch_time in punches:
            if not punch_time:
                continue

            code = str(punch_code)
            if code == "0":
                continue

            if int(code) < 100:
                code = code + TrailOAns(trailo_ans).name
            elif int(code) < 240:
                n = int(code)
                tc_idx = (n // 10) - 10
                task = n % 10
                if task == 0:
                    code = f"{tc_idx}TT"
                else:
                    otime = time_to_otime(punch_time)
                    ans = TrailOAns(otime.hour).name
                    code = f"{tc_idx}T{task}{ans}"
                    punch_time = None

            split = TrailoSfrCardProcessor._create_split(code, punch_time)
            if split.code not in ("0", ""):
                result.splits.append(split)

    @staticmethod
    def _create_split(code: str, punch_time: Optional[object]) -> Split:
        split = Split()
        split.code = code
        split.time = time_to_otime(punch_time)
        split.days = memory.race().get_days(punch_time)
        return split
