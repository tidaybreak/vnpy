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
from vnpy.trader.utility import extract_vt_symbol
from vnpy.trader.database import get_database

from vnpy_ctastrategy.base import (
    StopOrderStatus,
    INTERVAL_DELTA_MAP
)
from vnpy_ctastrategy.template import CtaTemplate
from time import sleep

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

    def load_bar2(
            self,
            vt_symbol: str,
            days: int,
            interval: Interval,
            callback: Callable[[BarData], None],
            use_database: bool
    ):
        """"""
        bars = super().load_bar(vt_symbol, days, interval, callback, use_database)

        # symbol, exchange = extract_vt_symbol(vt_symbol)
        # #end: datetime = datetime.now(LOCAL_TZ)
        # end = datetime.now(get_localzone())
        # start = end - timedelta(days)
        # # ti 0点触发
        # start = start.replace(hour=8, minute=0, second=0, microsecond=0)
        # bars = []
        #
        # # Pass gateway and RQData if use_database set to True
        # if not use_database:
        #     # Query bars from gateway if available
        #     contract = self.main_engine.get_contract(vt_symbol)
        #
        #     if contract and contract.history_data:
        #         req = HistoryRequest(
        #             symbol=symbol,
        #             exchange=exchange,
        #             interval=interval,
        #             start=start,  # ti 8点开始，binance 1分钟合成日数据和直接获取的日数据对应的上
        #             end=end
        #         )
        #         bars = self.main_engine.query_history(req, contract.gateway_name)
        #
        #     # Try to query bars from RQData, if not found, load from database.
        #     else:
        #         bars = self.query_bar_from_rq(symbol, exchange, interval, start, end)
        #
        # if not bars:
        #     bars = get_database().load_bar_data(
        #         symbol=symbol,
        #         exchange=exchange,
        #         interval=interval,
        #         start=start,
        #         end=end,
        #     )

        # ti 缺失bar处理，保持时间连续
        tmp_bar = None
        interval_delta = INTERVAL_DELTA_MAP[interval]
        for bar in bars:
            if tmp_bar and tmp_bar.datetime + interval_delta != bar.datetime:
                self.write_log(f"bar missing start:{tmp_bar} ",)
                tmp_bar.volume = 0
                while True:
                    if tmp_bar.datetime == bar.datetime:
                        break
                    tmp_bar.datetime += interval_delta
                    #callback(tmp_bar)
            tmp_bar = bar
            # if bar.datetime.day == 11 and bar.datetime.hour == 7 and bar.datetime.minute == 59:
            #     tmp_bar = bar
            #callback(bar)
        return bars

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
