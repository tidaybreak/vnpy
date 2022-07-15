from pathlib import Path

from vnpy.trader.app import BaseApp

from vnpy_ctastrategy.base import (
    APP_NAME,
    StopOrder
)

from quant.vnpy.app.cta_strategy.engineEx import CtaEngineEx


class CtaStrategyAppEx(BaseApp):
    """"""

    app_name = APP_NAME
    app_module = __module__
    app_path = Path(__file__).parent
    display_name = "CTA策略"
    engine_class = CtaEngineEx
    widget_name = "CtaManager"
    icon_name = "cta.ico"
