"""
    我们使用币安原生的api进行数据爬取.

"""

import pandas as pd
import time
import os
# import datetime
from datetime import datetime, timedelta
import requests
import pytz
from vnpy.trader.database import get_database
from datetime import timedelta
from vnpy.trader.datafeed import get_datafeed
from vnpy.trader.object import HistoryRequest

pd.set_option('expand_frame_repr', False)  #
from vnpy.trader.object import BarData, Interval, Exchange

BINANCE_SPOT_LIMIT = 1000
BINANCE_FUTURE_LIMIT = 1500

CHINA_TZ = pytz.timezone("Asia/Shanghai")
from threading import Thread


def generate_datetime(timestamp: float) -> datetime:
    """
    :param timestamp:
    :return:
    """
    dt = datetime.fromtimestamp(timestamp / 1000)
    dt = CHINA_TZ.localize(dt)
    return dt


def get_data(exchange: str, symbol: str, interval: Interval, exchanges: str, start_time: str, end_time: str):
    """
    爬取币安交易所的数据
    :param symbol: BTCUSDT.
    :param exchanges: 现货、USDT合约, 或者币币合约.
    :param start_time: 格式如下:2020-1-1 或者2020-01-01
    :param end_time: 格式如下:2020-1-1 或者2020-01-01
    :return:
    """
    database_manager = get_database()
    datafeed = get_datafeed()

    start_time = datetime.strptime(start_time, '%Y-%m-%d')
    end_time = datetime.strptime(end_time, '%Y-%m-%d')


    try:
        #### 获取k线级别的历史数据
        req = HistoryRequest(
            # 合约代码（示例cu888为米筐连续合约代码，仅用于示范，具体合约代码请根据需求查询数据服务提供商）
            symbol=symbol,
            # 合约所在交易所
            exchange=exchange,
            # 历史数据开始时间
            start=start_time,
            # 历史数据结束时间
            end=end_time,
            # 数据时间粒度，默认可选分钟级、小时级和日级，具体选择需要结合该数据服务的权限和需求自行选择
            interval=interval
        )

        # 获取k线历史数据
        bars = datafeed.query_bar_history(req)

        if bars is None:
            print("none bars, symbol:%s, interval:%s, start_time:%s, end_time:%s" % (symbol, interval, start_time, end_time))
            return False
        if len(bars) == 0:
            print("not bars:%d, symbol:%s, interval:%s, start_time:%s, end_time:%s" % (len(bars), symbol, interval, start_time, end_time))
            return True

        print("get bars:%d, symbol:%s, interval:%s, start_time:%s, end_time:%s" % (len(bars), symbol, interval, start_time, end_time))

        database_manager.save_bar_data(bars)

        # 到结束时间就退出, 后者收盘价大于当前的时间.
        # if (bars[-1].datetime > end_time) or bars[-1].datetime >= (int(time.time() * 1000) - 60 * 1000):
        #     break
    except Exception as error:
        # start time错误 太早
        print("get exception:", error)
        return False
    return True


def download_spot(exchange, symbol, first_date, interval):
    """
    下载现货数据的方法.
    :return:
    """
    database_manager = get_database()
    overview = database_manager.get_bar_overview()
    bar_overview = None
    for ent in overview:
        if ent.symbol == symbol.lower() and ent.interval == interval:
            bar_overview = ent
            break

    start_time = int(datetime.strptime(first_date, '%Y-%m-%d').timestamp())  # 开盘时间
    if bar_overview:
        print("overview:", bar_overview.symbol, bar_overview.interval, bar_overview.start, bar_overview.end)
        start_time = int(time.mktime(bar_overview.end.timetuple()))
        # if start_time < bar_start_time:
        #     start_time = bar_start_time

    end_time = int(time.time()) - (int(time.time()) - time.timezone) % 86400

    if start_time > end_time:
        return

    while start_time < end_time:
        d = datetime.fromtimestamp(start_time)
        d = d + timedelta(days=365)

        stime = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d")
        etime = d.strftime("%Y-%m-%d")
        if not get_data(exchange, symbol, interval, 'spot', stime, etime):
            break

        start_time = int(time.mktime(d.timetuple()))


if __name__ == '__main__':

    # 如果你有代理你就设置，如果没有你就设置为 None 或者空的字符串 "",
    # 但是你要确保你的电脑网络能访问币安交易所，你可以通过 ping api.binance.com 看看过能否ping得通 PROXY=http://user%40:pass@11.11.11.11:1090
    proxies = os.environ.get('PROXY', None)

    # get_binance_data("BTCUSDT", Interval.MINUTE, 'spot', "2021-4-8", "2021-4-9")

    #data = [["300738", Interval.HOUR], ["300738", Interval.DAILY]]
    data = [[Exchange.SZSE, "300738", "2018-1-1", Interval.DAILY], [Exchange.SZSE, "300738", "2018-1-1", Interval.HOUR]]    # 奥飞
    data = [[Exchange.SSE, "000001", "2018-1-1", Interval.DAILY], [Exchange.SSE, "000001", "2018-1-1", Interval.HOUR]]   # 上证
    data = [[Exchange.SSE, "510100", "2020-1-1", Interval.DAILY], [Exchange.SSE, "510100", "2020-1-1", Interval.HOUR], [Exchange.SSE, "510100", "2020-1-1", Interval.MINUTE]]   # SZ50ETF
    for item in data:
        download_spot(item[0], item[1], item[2], item[3])  # 下载现货的数据.

    # download_future(symbol)  # 下载合约的数据
