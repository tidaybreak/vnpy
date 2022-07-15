from vnpy.event import EventEngine

from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp

from vnpy.gateway.binance import BinanceGateway  #现货
from vnpy.gateway.binances import BinancesGateway  # 合约

from vnpy.app.cta_strategy import CtaStrategyApp  # CTA策略
from vnpy.app.data_manager import DataManagerApp  # 数据管理, csv_data
from vnpy.app.data_recorder import DataRecorderApp  # 录行情数据
from vnpy.app.algo_trading import AlgoTradingApp  # 算法交易
from vnpy.app.cta_backtester import CtaBacktesterApp  # 回测研究
from vnpy.app.risk_manager import RiskManagerApp  # 风控管理
from vnpy.app.spread_trading import SpreadTradingApp  # 价差交易

from vnpy.trader.utility import load_json


def main():
    """"""
    # man = ArrayManagerEx(7)
    # a = [12400.63, 11903.13, 10854.1, 10624.93, 10842.85, 11940, 11145.67]
    # man.close_array = a
    # man.rsi2(6)

    qapp = create_qapp()

    event_engine = EventEngine()

    main_engine = MainEngine(event_engine)

    gateway = main_engine.add_gateway(BinanceGateway)
    main_engine.add_gateway(BinancesGateway)
    main_engine.add_app(CtaStrategyApp)
    main_engine.add_app(CtaBacktesterApp)
    main_engine.add_app(DataManagerApp)
    main_engine.add_app(AlgoTradingApp)
    main_engine.add_app(DataRecorderApp)
    main_engine.add_app(RiskManagerApp)
    main_engine.add_app(SpreadTradingApp)

    #backTest = CtaBacktesterApp
    #backTest.add_strategy(SpotGridStrategy, {})

    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()

    filename: str = f"connect_{gateway.gateway_name.lower()}.json"
    loaded_setting = load_json(filename)
    main_engine.connect(loaded_setting, gateway.gateway_name)

    qapp.exec()


if __name__ == "__main__":
    """
     vnpy main window demo
     vnpy 的图形化界面

     we have binance gate way, which is for spot, while the binances gateway is for contract or futures.
     the difference between the spot and future is their symbol is just different. Spot uses the lower case for symbol, 
     while the futures use the upper cases.

     币安的接口有现货和合约接口之分。 他们之间的区别是通过交易对来区分的。现货用小写，合约用大写。 btcusdt.BINANCE 是现货的symbol,
     BTCUSDT.BINANCE合约的交易对。 BTCUSD.BINANCE是合约的币本位保证金的交易对.
     
     BTCUSDT, BTCUSDT
    """

    main()