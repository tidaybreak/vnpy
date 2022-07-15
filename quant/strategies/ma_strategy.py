from vnpy.app.cta_strategy import (
    CtaTemplate,
    BarGenerator,
    TradeData
)

from quant.vnpy.trader.utilityEx import ArrayManagerEx
from vnpy.trader.constant import Direction
from vnpy.app.cta_strategy.backtesting import BacktestingEngine
from vnpy.trader.constant import Interval

TIMER_WAITING_INTERVAL = 30


class MaStrategy(CtaTemplate):
    """基于sar and Keltner 交易策略"""
    className = 'SARKELStrategy'
    author = u'BillyZhang'

    # 策略参数
    sarAcceleration = 0.02  # 加速线
    sarMaximum = 0.2  #
    cciWindow = 20  # CCI窗口数
    keltnerWindow = 25  # keltner窗口数
    keltnerlMultiplier = 6.0  # 乘数
    initDays = 10  # 初始化数据所用的天数
    fixedSize = 1  # 每次交易的数量
    barMins = 15
    barMinsClose = 10
    # 策略变量
    sarValue = 0  # sar指标数值
    cciValue = 0  # CCI指标数值
    keltnerup = 0
    keltnerdown = 0
    longStop = 0  # 多头止损
    shortStop = 0  # 空头止损

    segSize = 90

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol',
                 'sarAcceleration',
                 'sarMaximum',
                 'cciWindow',
                 'keltnerWindow',
                 'keltnerlMultiplier',
                 'initDays',
                 'fixedSize',
                 'barMinsClose',
                 'barMins']

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'sarValue',
               'cciValue',
               'atrValue',
               'intraBarHigh',
               'intraBarLow',
               'longStop',
               'shortStop']

    # 同步列表，保存了需要保存到数据库的变量名称
    syncList = ['pos',
                'intraTradeHigh',
                'intraTradeLow']

    # ----------------------------------------------------------------------
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.buyPrice = 0.0
        self.sar_point = 0
        self.interval = None
        if isinstance(self.cta_engine, BacktestingEngine):
            self.interval = self.cta_engine.interval
            self.available_cash = self.cta_engine.capital
        else:
            self.interval = Interval.HOUR
            self.available_cash = self.cta_engine.main_engine.engines["oms"].get_account("BINANCE.USDT").available
            if self.interval == Interval.MINUTE:
                self.bg = BarGenerator(self.on_bar, 1, self.on_real_bar, Interval.MINUTE)
            elif self.interval == Interval.HOUR:
                self.bg = BarGenerator(self.on_bar, 1, self.on_real_bar, Interval.HOUR)
            elif self.interval == Interval.DAILY:
                self.bg = BarGenerator(self.on_bar, 24, self.on_real_bar, Interval.HOUR)

        self.amClose = ArrayManagerEx(self.segSize)

    def on_init(self):
        """初始化策略（必须由用户继承实现）"""
        self.write_log(u'策略初始化')

        # # 载入历史数据，并采用回放计算的方式初始化策略数值
        # if self.interval == Interval.MINUTE:
        #     self.load_bar(math.ceil(self.segSize / 24 / 60))
        # elif self.interval == Interval.HOUR:
        #     self.load_bar(math.ceil(self.segSize / 24))
        # elif self.interval == Interval.DAILY:
        #     self.load_bar(self.segSize)
        # else:
        #     self.load_bar(self.segSize)

        # self.putEvent()

    # ----------------------------------------------------------------------
    def on_start(self):
        """启动策略（必须由用户继承实现）"""
        self.write_log(u'策略启动')
        self.put_event()

    # ----------------------------------------------------------------------
    def on_stop(self):
        """停止策略（必须由用户继承实现）"""
        self.write_log(u'策略停止')
        self.put_event()

    # ----------------------------------------------------------------------
    def on_tick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        self.bg.update_tick(tick)

    # ----------------------------------------------------------------------
    def on_bar(self, bar):
        # print("bar:", bar.datetime)
        if isinstance(self.cta_engine, BacktestingEngine):
            self.on_real_bar(bar)
        else:
            self.bg.update_bar(bar)

        # self.on_day_bar(bar)

    def on_real_bar(self, bar):
        print("on_day_bar:", bar.datetime)
        self.amClose.update_bar(bar)
        if not self.amClose.inited:
            return

        self.cancel_all()

        # 计算指标数值
        # self.cciValue = self.am.cci(self.cciWindow)
        # self.keltnerup, self.keltnerdown = self.am.keltner(self.keltnerWindow, self.keltnerlMultiplier)

        # 计算指标数值
        self.sarValue = self.amClose.sar(self.sarAcceleration, self.sarMaximum)

        # print("bar:", bar.datetime, " ", bar.close_price, " ", self.sarValue)
        # 当前无仓位，发送开仓委托
        if self.pos == 0:
            if self.sarValue < bar.close_price:
                self.sar_point += 1
                if self.sar_point > 1:
                    ema20 = self.amClose.ema(20)
                    ema60 = self.amClose.ema(60)
                    ema90 = self.amClose.ema(90)
                    # print(bar.datetime, "  close_price:", bar.close_price, " ema20:", ema20, " ema60:", ema60, " ema90:", ema90)
                    if bar.close_price > ema20:
                        # fixed_size = (self.available_cash / (bar.close_price + 5)) / 2
                        fixed_size = (self.available_cash / (bar.close_price + 5))
                        self.buy(bar.close_price + 5, fixed_size)
                        self.sar_point = 0
        elif self.pos > 0:
            if self.sarValue > bar.close_price:
                # loss = (self.sarValue - self.buyPrice) / self.buyPrice
                # if loss > -0.2:
                self.sell(bar.close_price - 5, abs(self.pos))

        self.put_event()

    def on_order(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        pass

    # ----------------------------------------------------------------------
    def on_trade(self, trade: TradeData):
        # 发出状态更新事件
        if trade.direction == Direction.LONG:
            self.available_cash -= (trade.price * trade.volume) * (1.0 + self.cta_engine.rate)
            self.buyPrice = trade.price
        elif trade.direction == Direction.SHORT:
            self.available_cash += (trade.price * trade.volume) * (1.0 - self.cta_engine.rate)
        # print("available_cash:", self.available_cash, " trade:", trade)
        self.put_event()

    # ----------------------------------------------------------------------
    def on_stop_order(self, so):
        """停止单推送"""
        pass

    # ----------------------------------------------------------------------
    def onminBarClose(self, bar):
        """分钟作为清仓周期"""
        # 如果没有仓位,那么不用care,直接skip

        # 保存K线数据
        amClose = self.amClose

        amClose.update_bar(bar)

        if not amClose.inited:
            return

        # 计算指标数值
        self.sarValue = amClose.sar(self.sarAcceleration, self.sarMaximum)

        # 判断是否要进行交易
        if self.pos == 0:
            return

        # 当前无仓位，发送开仓委托
        # 持有多头仓位
        elif self.pos > 0:
            self.cancel_all()
            self.sell(self.sarValue, abs(self.pos), True)

        # # 持有空头仓位
        # elif self.pos < 0:
        #     self.cancel_all()
        #     self.cover(self.sarValue, abs(self.pos), True)

        # 同步数据到数据库
        self.sync_data()

        # 发出状态更新事件
        self.put_event()

        # ----------------------------------------------------------------------

    # ----------------------------------------------------------------------
    def onXminBar(self, bar):
        """收到X分钟K线"""
        # 全撤之前发出的委托
        self.cancel_all()

        # 保存K线数据
        am = self.am

        am.update_bar(bar)

        if not am.inited:
            return

        # 计算指标数值
        self.cciValue = am.cci(self.cciWindow)
        self.keltnerup, self.keltnerdown = am.keltner(self.keltnerWindow, self.keltnerlMultiplier)

        # 判断是否要进行交易

        # 当前无仓位，发送开仓委托
        if self.pos == 0:

            if self.cciValue > 0:
                # ru
                self.buy(self.keltnerup, self.fixedSize, True)

            # elif self.cciValue < 0:
            #     self.short(self.keltnerdown, self.fixedSize, True)

        # 同步数据到数据库
        self.sync_data()

        # 发出状态更新事件
        self.put_event()
