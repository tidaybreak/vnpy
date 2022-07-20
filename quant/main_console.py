import multiprocessing
import sys, getopt
from time import sleep
from datetime import time
from logging import INFO

from vnpy.event import EventEngine
from vnpy.trader.setting import SETTINGS
from quant.vnpy.trader.engineEx import MainEngineEx

from vnpy_binance import (
    BinanceSpotGateway,
    BinanceUsdtGateway,
    BinanceInverseGateway
)

from vnpy_ctastrategy import CtaStrategyApp
from quant.vnpy.gateway.binance.binance_gateway_ex import BinanceSpotGatewayEx  # 现货
#from vnpy.gateway.binances import BinancesGateway  # 合约

from quant.vnpy.app.cta_strategy import CtaStrategyAppEx

from vnpy_ctastrategy.base import EVENT_CTA_LOG

from vnpy.trader.utility import load_json

SETTINGS["log.active"] = True
SETTINGS["log.level"] = INFO
SETTINGS["log.console"] = True

ctp_setting = {
    "用户名": "",
    "密码": "",
    "经纪商代码": "",
    "交易服务器": "",
    "行情服务器": "",
    "产品名称": "",
    "授权编码": "",
    "产品信息": ""
}

# Chinese futures market trading period (day/night)
DAY_START = time(8, 45)
DAY_END = time(15, 0)

NIGHT_START = time(20, 45)
NIGHT_END = time(2, 45)


def check_trading_period():
    """"""
    return True
    #
    # current_time = datetime.now().time()
    #
    # trading = False
    # if (
    #     (current_time >= DAY_START and current_time <= DAY_END)
    #     or (current_time >= NIGHT_START)
    #     or (current_time <= NIGHT_END)
    # ):
    #     trading = True
    #
    # return trading


def run_child(currency):
    """
    Running in the child process.
    """
    SETTINGS["log.file"] = True
    gateway_name = 'binance'

    event_engine = EventEngine()

    main_engine = MainEngineEx(event_engine)

    main_engine.add_gateway(BinanceSpotGateway, gateway_name=gateway_name)
    # gateway = main_engine.add_gateway(BinanceUsdtGateway)
    # gateway = main_engine.add_gateway(BinanceInverseGateway)

    cta_engine = main_engine.add_app(CtaStrategyAppEx)
    # main_engine.add_app(CtaStrategyAppEx)

    log_engine = main_engine.get_engine("log")
    event_engine.register(EVENT_CTA_LOG, log_engine.process_log_event)
    main_engine.write_log("注册日志事件监听")

    filename: str = f"connect_{gateway_name}.json"
    loaded_setting = load_json(filename)
    main_engine.connect(loaded_setting, gateway_name)

    # main_engine.write_log("sleep10等待connect连接")
    # sleep(10)
    vt_symbol = currency
    cta_engine.setting_filename = f"cta_strategy_setting_{vt_symbol}.json"
    cta_engine.data_filename = f"cta_strategy_data_{vt_symbol}.json"
    cta_engine.init_engine()
    main_engine.write_log("CTA策略初始化完成")

    cta_engine.init_all_strategies()    # 异步 SarStrategy.on_init -> load_bar
    main_engine.write_log("CTA策略全部初始化")

    cta_engine.start_all_strategies()
    main_engine.write_log("CTA策略全部启动")

    while True:
        sleep(10)

        trading = check_trading_period()
        if not trading:
            print("关闭子进程")
            main_engine.close()
            sys.exit(0)


def run_parent(currency):
    """
    Running in the parent process.
    """
    print("启动CTA策略守护父进程")

    child_process = None

    while True:
        trading = check_trading_period()

        # Start child process in trading period
        if trading and child_process is None:
            print("启动子进程")
            child_process = multiprocessing.Process(target=run_child(currency))
            child_process.start()
            print("子进程启动成功")

        # 非记录时间则退出子进程
        if not trading and child_process is not None:
            if not child_process.is_alive():
                child_process = None
                print("子进程关闭成功")

        sleep(5)


if __name__ == "__main__":
    tip = 'main_console.py -c <currency>'
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hc:", ["currency="])
    except getopt.GetoptError:
        print(tip)
        sys.exit(2)
    currency = None
    for opt, arg in opts:
        if opt == '-h':
            print(tip)
            sys.exit()
        elif opt in ("-c", "--currency"):
            currency = arg
    if not currency:
        print(tip)
        sys.exit()
    run_parent(currency)
