"""
Gateway for Binance Crypto Exchange.
"""


#from vnpy_ctastrategy.binance.binance_gateway import BinanceGateway, BinanceRestApi
from vnpy_binance.binance_spot_gateway import BinanceSpotRestAPi
from vnpy_binance import (
    BinanceSpotGateway
)
from vnpy.event import Event, EventEngine
from vnpy.trader.object import (
    AccountData
)


class BinanceSpotGatewayEx(BinanceSpotGateway):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self, event_engine: EventEngine, gateway_name: str = "BINANCE_SPOT") -> None:
        super().__init__(event_engine, gateway_name)
        self.rest_api = BinanceSpotRestAPiEx(self)


class BinanceSpotRestAPiEx(BinanceSpotRestAPi):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self, gateway: BinanceSpotGateway):
        super().__init__(gateway)

    def on_query_account(self, data, request):
        """"""
        for account_data in data["balances"]:
            account = AccountData(
                accountid=account_data["asset"],
                balance=float(account_data["free"]) + float(account_data["locked"]),
                frozen=float(account_data["locked"]),
                gateway_name=self.gateway_name
            )

            if account.balance:
                self.gateway.on_account(account)

        # self.gateway.write_log("账户资金查询成功")