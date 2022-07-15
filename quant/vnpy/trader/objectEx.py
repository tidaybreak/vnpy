"""
General utility functions.
"""

from vnpy.trader.constant import Exchange


class QueryRequest:
    """
    Request sending to specific gateway for query an existing order.
    Author: 51bitquant
    """
    orderid: str
    symbol: str
    exchange: Exchange

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

