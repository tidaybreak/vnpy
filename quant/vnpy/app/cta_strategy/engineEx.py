"""
General utility functions.
"""

from vnpy_ctastrategy.engine import CtaEngine
from typing import Callable
from datetime import datetime, timedelta
from tzlocal import get_localzone
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import (
    HistoryRequest,
    BarData
)
from vnpy.trader.constant import (
    Interval,
    Status
)
import copy
from vnpy.trader.utility import extract_vt_symbol
from vnpy.trader.database import get_database

from vnpy_ctastrategy.base import (
    StopOrderStatus,
    INTERVAL_DELTA_MAP
)
from vnpy_ctastrategy.template import CtaTemplate
from time import sleep
from vnpy.trader.utility import load_json, save_json, extract_vt_symbol, round_to

STOP_STATUS_MAP = {
    Status.SUBMITTING: StopOrderStatus.WAITING,
    Status.NOTTRADED: StopOrderStatus.WAITING,
    Status.PARTTRADED: StopOrderStatus.TRIGGERED,
    Status.ALLTRADED: StopOrderStatus.TRIGGERED,
    Status.CANCELLED: StopOrderStatus.CANCELLED,
    Status.REJECTED: StopOrderStatus.CANCELLED
}


class CtaEngineEx(CtaEngine):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        super().__init__(main_engine, event_engine)
        self.interval: Interval = None
        self.rate: float = 0

    def update_strategy_setting(self, strategy_name: str, setting: dict) -> None:
        """
        Update setting file.
        """
        strategy: CtaTemplate = self.strategies[strategy_name]

        self.strategy_setting[strategy_name] = {
            "class_name": strategy.__class__.__name__,
            "vt_symbol": strategy.vt_symbol,
            "interval": self.strategy_setting[strategy_name]["interval"],
            "setting": setting,
        }
        save_json(self.setting_filename, self.strategy_setting)

    def load_bar(
            self,
            vt_symbol: str,
            days: int,
            interval: Interval,
            callback: Callable[[BarData], None],
            use_database: bool
    ):
        """"""
        # 实盘数据
        """"""
        # interval 限制为 Interval.HOUR or Interval.MINUTE
        bars = super().load_bar(vt_symbol, days, interval, callback, use_database)

        # todo 24小时交易才处理

        new_bars = []
        # ti 缺失bar处理，保持时间连续
        tmp_bar = None
        miss_count = 0
        interval_delta = INTERVAL_DELTA_MAP[interval]
        for bar in bars:
            # 如果是日交易，从第一个0点开始
            if self.interval == Interval.DAILY and len(new_bars) == 0 and bar.datetime.hour != 0:
                continue
            if tmp_bar and tmp_bar.datetime + interval_delta != bar.datetime:
                tmp_bar.volume = 0
                while True:
                    tmp_bar.datetime += interval_delta
                    if tmp_bar.datetime == bar.datetime:
                        break
                    new_bars.append(copy.deepcopy(tmp_bar))
                    miss_count += 1
                    # self.write_log(f"bar missing start:{tmp_bar} ")
            tmp_bar = bar
            new_bars.append(bar)

            # callback(bar)
        bar_total = len(bars)
        self.write_log(f"加载周期{interval} 加载天数{days} 获取总数:{bar_total} 丢失数量:{miss_count} ")
        # for bar in new_bars:
        #     if bar.datetime.year == 2019 and bar.datetime.month == 11:
        #         print(bar)
        return new_bars

    def start_all_strategies(self) -> None:
        """
        """
        for strategy_name in self.strategies.keys():
            # 等待load_bar完成
            while True:
                strategy: CtaTemplate = self.strategies[strategy_name]
                if not strategy.inited:
                    sleep(1)
                else:
                    break
            self.start_strategy(strategy_name)
