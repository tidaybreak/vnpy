"""
Gateway for Binance Crypto Exchange.
"""


from vnpy.gateway.binance.binance_gateway import BinanceGateway, BinanceRestApi
from vnpy.trader.object import (
    AccountData
)


class BinanceGatewayEx(BinanceGateway):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self, event_engine):
        super().__init__(event_engine)
        self.rest_api = BinanceRestApiEx(self)


class BinanceRestApiEx(BinanceRestApi):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self, gateway: BinanceGateway):
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