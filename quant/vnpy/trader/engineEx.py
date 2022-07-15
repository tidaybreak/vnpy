"""
General utility functions.
"""

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine, OmsEngine, LogEngine, EmailEngine
from quant.vnpy.trader.objectEx import (
    QueryRequest
)
from vnpy.trader.event import (
    EVENT_TIMER
)
from vnpy.trader.setting import SETTINGS
from datetime import datetime


class MainEngineEx(MainEngine):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self, event_engine: EventEngine = None):
        super().__init__(event_engine)

    def init_engines(self) -> None:
        """
        Init all engines.
        """
        self.add_engine(LogEngine)
        self.add_engine(OmsEngineEx)
        self.add_engine(EmailEngine)

    def query_order(self, req: QueryRequest, gateway_name: str) -> None:
        """
        Send query order request to a specific gateway.
        """
        gateway = self.get_gateway(gateway_name)
        if gateway and hasattr(gateway, 'query_order'):
            gateway.query_order(req)

    def query_position(self):
        """
        query the position
        """
        for gateway in self.gateways.values():
            gateway.query_position()

    def query_account(self):
        """
        query the account
        """
        for gateway in self.gateways.values():
            gateway.rest_api.query_account()


class OmsEngineEx(OmsEngine):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        super().__init__(main_engine, event_engine)

        self.order_update_interval = 0  # for counting the timer.
        self.position_update_interval = 0
        self.account_update_interval = SETTINGS.get('account_update_interval', 120)

    def register_event(self) -> None:
        super().register_event()
        self.event_engine.register(EVENT_TIMER, self.process_timer)

    def process_timer(self, event: Event) -> None:
        """
        update the orders, positions by timer, for we may be disconnected from server update push.
        """

        self.order_update_interval += 1
        self.position_update_interval += 1
        self.account_update_interval += 1

        if self.order_update_interval >= SETTINGS.get('order_update_interval', 120):
            self.order_update_interval = 0
            orders = self.get_all_active_orders()
            for order in orders:
                if order.datetime and (datetime.now(order.datetime.tzinfo) - order.datetime).seconds > SETTINGS.get('order_update_timer', 120):
                    #req = order.create_query_request()
                    req = QueryRequest(
                        orderid=order.orderid, symbol=order.symbol, exchange=order.exchange
                    )
                    self.main_engine.query_order(req, order.gateway_name)

        if self.position_update_interval >= SETTINGS.get('position_update_interval', 120):
            self.main_engine.query_position()
            self.position_update_interval = 0

        if self.account_update_interval >= SETTINGS.get('account_update_interval', 120):
            self.account_update_interval = 0
            self.main_engine.query_account()