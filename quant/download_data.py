"""
    我们使用币安原生的api进行数据爬取.

"""

import pandas as pd
import time
# import datetime
from datetime import datetime, timedelta
import requests
import pytz
from vnpy.trader.database import get_database
from datetime import date, timedelta

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


def get_binance_data(symbol: str, interval: Interval, exchanges: str, start_time: str, end_time: str):
    """
    爬取币安交易所的数据
    :param symbol: BTCUSDT.
    :param exchanges: 现货、USDT合约, 或者币币合约.
    :param start_time: 格式如下:2020-1-1 或者2020-01-01
    :param end_time: 格式如下:2020-1-1 或者2020-01-01
    :return:
    """
    database_manager = get_database()

    if interval == Interval.DAILY:
        API_INTERVAL = "1d"
    elif interval == Interval.HOUR:
        API_INTERVAL = "1h"
    elif interval == Interval.MINUTE:
        API_INTERVAL = "1m"

    api_url = ''
    save_symbol = symbol
    gate_way = 'BINANCES'

    if exchanges == 'spot':
        # print("spot")
        limit = BINANCE_SPOT_LIMIT
        save_symbol = symbol.lower()
        gate_way = 'BINANCE'
        api_url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={API_INTERVAL}&limit={limit}'

    elif exchanges == 'future':
        print('future')
        limit = BINANCE_FUTURE_LIMIT
        api_url = f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={API_INTERVAL}&limit={limit}'

    elif exchanges == 'coin_future':
        print("coin_future")
        limit = BINANCE_FUTURE_LIMIT
        f'https://dapi.binance.com/dapi/v1/klines?symbol={symbol}&interval={API_INTERVAL}&limit={limit}'

    else:
        raise Exception('交易所名称请输入以下其中一个：spot, future, coin_future')

    start_time = int(datetime.strptime(start_time, '%Y-%m-%d').timestamp() * 1000)
    end_time = int(datetime.strptime(end_time, '%Y-%m-%d').timestamp() * 1000)

    while True:
        try:

            st = time.strftime("%Y-%m-%d", time.localtime(start_time / 1000))
            url = f'{api_url}&startTime={start_time}'
            print(f'{st} {url}')
            data = requests.get(url=url, timeout=10, proxies=proxies).json()

            """
            [
                [
                    1591258320000,      // 开盘时间
                    "9640.7",           // 开盘价
                    "9642.4",           // 最高价
                    "9640.6",           // 最低价
                    "9642.0",           // 收盘价(当前K线未结束的即为最新价)
                    "206",              // 成交量
                    1591258379999,      // 收盘时间
                    "2.13660389",       // 成交额(标的数量)
                    48,                 // 成交笔数
                    "119",              // 主动买入成交量
                    "1.23424865",      // 主动买入成交额(标的数量)
                    "0"                 // 请忽略该参数
                ]

            """

            buf = []

            for l in data:
                # t = l[0] / 1000
                # print(t, ',', datetime.fromtimestamp(t), ',', float(l[1]), ',', float(l[1]))
                bar = BarData(
                    symbol=save_symbol,
                    exchange=Exchange.BINANCE,
                    datetime=generate_datetime(l[0]),
                    # interval=Interval.DAILY,
                    interval=interval,
                    volume=float(l[5]),
                    open_price=float(l[1]),
                    high_price=float(l[2]),
                    low_price=float(l[3]),
                    close_price=float(l[4]),
                    gateway_name=gate_way
                )
                buf.append(bar)

            database_manager.save_bar_data(buf)

            # 到结束时间就退出, 后者收盘价大于当前的时间.
            if (data[-1][0] > end_time) or data[-1][6] >= (int(time.time() * 1000) - 60 * 1000):
                break

            start_time = data[-1][0]

        except Exception as error:
            print(error)
            time.sleep(10)


def download_spot(symbol, interval):
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

    start_time = int(datetime.strptime("2017-1-1", '%Y-%m-%d').timestamp())
    end_time = int(time.time()) - (int(time.time()) - time.timezone) % 86400
    if bar_overview:
        print("overview:", bar_overview.symbol, bar_overview.interval, bar_overview.start, bar_overview.end)
        start_time = int(time.mktime(bar_overview.end.timetuple()))
    while start_time < end_time:
        d = datetime.fromtimestamp(start_time)
        d = d + timedelta(days=365)

        stime = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d")
        etime = d.strftime("%Y-%m-%d")
        print(stime, etime)
        get_binance_data(symbol, interval, 'spot', stime, etime)

        start_time = int(time.mktime(d.timetuple()))

    # t0 = Thread(target=get_binance_data, args=(symbol, interval, 'spot', "2017-1-1", "2018-1-1"))
    #
    # t1 = Thread(target=get_binance_data, args=(symbol, interval, 'spot', "2018-1-1", "2019-1-1"))
    #
    # t2 = Thread(target=get_binance_data, args=(symbol, interval, 'spot', "2019-1-1", "2020-1-1"))
    #
    # t3 = Thread(target=get_binance_data, args=(symbol, interval, 'spot', "2020-1-1", "2021-1-1"))
    #
    # t4 = Thread(target=get_binance_data,
    #             args=(symbol, interval, 'spot', "2021-1-1", time.strftime("%Y-%m-%d", time.localtime())))
    #
    # t0.start()
    # t1.start()
    # t2.start()
    # t3.start()
    # t4.start()
    #
    # t0.join()
    # t1.join()
    # t2.join()
    # t3.join()
    # t4.join()


def download_future(symbol):
    """
    下载合约数据的方法。
    :return:
    """
    t1 = Thread(target=get_binance_data, args=(symbol, 'future', "2019-9-10", "2020-3-1"))
    t2 = Thread(target=get_binance_data, args=(symbol, 'future', "2019-3-1", "2020-11-16"))

    t1.start()
    t2.start()

    t1.join()
    t2.join()


if __name__ == '__main__':

    # 如果你有代理你就设置，如果没有你就设置为 None 或者空的字符串 "",
    # 但是你要确保你的电脑网络能访问币安交易所，你可以通过 ping api.binance.com 看看过能否ping得通
    proxy_host = ""  # 如果没有就设置为"", 如果有就设置为你的代理主机如：127.0.0.1
    proxy_port = 1090  # 设置你的代理端口号如: 1087, 没有你修改为0,但是要保证你能访问api.binance.com这个主机。

    proxies = None
    if proxy_host and proxy_port:
        proxy = f'http://:@{proxy_host}:{proxy_port}'
        proxies = {'http': proxy, 'https': proxy}

    # get_binance_data("BTCUSDT", Interval.MINUTE, 'spot', "2021-4-8", "2021-4-9")

    data = [["BTCUSDT", Interval.HOUR], ["BTCUSDT", Interval.DAILY],
            ["XMRUSDT", Interval.HOUR], ["XMRUSDT", Interval.DAILY],
            ["ETHUSDT", Interval.HOUR], ["ETHUSDT", Interval.DAILY],
            ["FILUSDT", Interval.HOUR], ["FILUSDT", Interval.DAILY]]

    data = [["BTCUSDT", Interval.HOUR], ["BTCUSDT", Interval.DAILY]]
    for item in data:
        download_spot(item[0], item[1])  # 下载现货的数据.

    # download_future(symbol)  # 下载合约的数据
