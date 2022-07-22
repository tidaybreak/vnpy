"""
General utility functions.
"""
import json
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, Tuple, Union, Optional
from decimal import Decimal
from math import floor, ceil
import numpy as np
import talib

import openpyxl
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from vnpy.trader.database import get_database

from vnpy.trader.object import Interval

from vnpy.trader.utility import ArrayManager, BarGenerator
from vnpy.trader.object import BarData, TickData


class ArrayManagerEx(ArrayManager):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self, size: int = 100):
        super().__init__(size)

    def sar(self, acceleration=0.02, maximum=0.2, array=False):
        """sar"""
        # real = talib.SAR(self.close, self.open, acceleration=acceleration, maximum=maximum)
        real = talib.SAR(self.high, self.low, acceleration=acceleration, maximum=maximum)
        if array:
            return real
        return real[-1]

    def rsi2(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Relative Strenght Index (RSI).
        """
        c0 = self.close[:-1]
        c1 = self.close[1:]
        c = np.array(c1) - np.array(c0)
        v = [0.0 if i < 0 else i for i in c]
        xx = np.array(v)
        up = talib.SMA(np.array([0.0 if i < 0 else i for i in c]), n)[-1]
        down = talib.SMA(np.array([0.0 if i > 0 else -i for i in c]), n)[-1]

        rsi = None
        if down == 0:
            rsi = 100
        elif up == 0:
            rsi = 0
        else:
            rsi = (up / (up + down)) * 100

        result = talib.RSI(self.close, n)
        if array:
            return result
        return result[-1]


# class BarGeneratorEx(BarGenerator):
#     def __init__(
#             self,
#             on_bar: Callable,
#             window: int = 0,
#             on_window_bar: Callable = None,
#             interval: Interval = Interval.MINUTE
#     ) -> None:
#         super().__init__(on_bar, window, on_window_bar, interval)
#
#     def update_bar(self, bar: BarData) -> None:
#         """
#         Update 1 minute bar into generator
#         """
#         if self.interval == Interval.MINUTE:
#             self.update_bar_minute_window(bar)
#         elif self.interval == Interval.HOUR:
#             self.update_bar_hour_window(bar)
#         else:
#             self.update_bar_day_window(bar)
