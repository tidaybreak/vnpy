from vnpy_ctastrategy import (
    CtaTemplate,
    BarGenerator,
    TradeData
)

import math
from datetime import datetime
from quant.vnpy.trader.utilityEx import ArrayManagerEx
from quant.units import bool_color
from vnpy.trader.constant import Direction
from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy.trader.constant import Interval
from tzlocal import get_localzone

LOCAL_TZ = get_localzone()
TIMER_WAITING_INTERVAL = 30


class SarStrategy(CtaTemplate):
    """基于sar 交易策略"""
    className = 'SarStrategy'
    author = u'ti'

    symbol1 = "USDT"
    symbol2 = ""
    # interval = Interval.DAILY

    # 参数-指标
    seg_size = 100  # 初始化数据所用的天数
    sar_acceleration = 0.02  # 加速线
    sar_maximum = 0.2  #
    rsi_length = 14
    # 参数-开平仓
    position_ratio = 1  # 下单仓位，利用凯利公式？ 大于1表示绝对值
    open_eq_sar_step = 2  # 开仓-等于指定sar步数  [关闭=0]     思想：开仓主指标
    open_lt_rsi = 58  # 开仓-小于指定rsi时  [关闭=0]       思想：超买时不开仓
    open_gt_ema = 14  # 开仓-大于指定ema天数  [关闭=0]     思想：突破平均线时考虑开仓
    stop_eq_sar_step = 7  # 平仓-止损-sar步数  [关闭=0]    假突破
    stop_gt_rsi = 0  # 平仓-大于指定rsi时  [关闭=100]
    stop_lt_ema = 0     # 平仓-小于定ema时  [关闭=0]
    stop_gt_move = 0.1099  # 平仓-止损-移动止损  [关闭=0.0]
    stop_win_per = 0.0  # 平仓-百分比止赢         [关闭=0.0]
    stop_loss_per = 0.0  # 平仓-百分比止损         [关闭=0.0]

    # 内部变量
    sar_value = 0  # sar指标数值
    sar_switch_amount = 0   # sar变换次数
    sar_high_step = 0  # sar 上行时步数
    sar_low_step = 0  # sar 下行时步数
    sar_first_price = 0
    sar_total_price = 0
    rsi_value = 0  # rsi指标数值
    available_cash = 0  # 可用现金
    no_log = False
    open_tmp_bar = None
    # 内部变量 - 需要恢复
    close_price_max = 0.0  # 买入后历史最高价
    open_buy_price = 0.0  # 买入价

    # 参数列表，保存了参数的名称
    parameters = ['seg_size',
                  'sar_acceleration',
                  'sar_maximum',
                  'rsi_length',
                  'position_ratio',
                  'open_eq_sar_step',
                  'open_lt_rsi',
                  'open_gt_ema',
                  'stop_eq_sar_step',
                  'stop_gt_move',
                  'stop_gt_rsi',
                  'stop_lt_ema',
                  'stop_win_per',
                  'stop_loss_per']

    # 变量列表，保存了变量的名称
    variables = ['close_price_max',
                 'open_buy_price']

    # 交易详情
    report_trade = []
    report_signal = []
    trade_info = {}

    # ----------------------------------------------------------------------
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        for k in self.parameters:
            if k in setting:
                setattr(self, k, setting[k])

        if "symbol1" in setting:
            self.symbol1 = setting["symbol1"]
        self.no_log = setting.get('no_log', False)

        self.symbol2 = vt_symbol.split('.')[0].upper().replace(self.symbol1, "")
        if isinstance(self.cta_engine, BacktestingEngine):
            self.am = ArrayManagerEx(self.seg_size)
            self.available_cash = self.cta_engine.capital
        else:
            if self.cta_engine.interval == Interval.MINUTE:
                self.am = ArrayManagerEx(math.ceil(self.seg_size / 24 / 60) * 1440)
            elif self.cta_engine.interval == Interval.HOUR:
                self.am = ArrayManagerEx(math.ceil(self.seg_size / 24) * 24)
            else:
                self.am = ArrayManagerEx(self.seg_size * 24)

            account_symbol1 = self.cta_engine.main_engine.engines["oms"].get_account("binance." + self.symbol1)
            # account_symbol1 = self.cta_engine.main_engine.query_account()
            # if account_symbol1:
            self.available_cash = account_symbol1.available
            if self.cta_engine.interval == Interval.MINUTE:
                self.bg = BarGenerator(self.on_bar, 1, self.on_real_bar, Interval.MINUTE)
            elif self.cta_engine.interval == Interval.HOUR:
                self.bg = BarGenerator(self.on_bar, 1, self.on_real_bar, Interval.HOUR)
            elif self.cta_engine.interval == Interval.DAILY:
                self.bg = BarGenerator(self.on_bar, 24, self.on_real_bar, Interval.HOUR)
                # 设置0点触发，不处理会以当前小时为触发点
                hour = datetime.now(LOCAL_TZ).hour
                self.bg.interval_count = 24 - (24 - hour + 8 - 1)

    def on_init(self):
        """初始化策略（必须由用户继承实现）"""
        self.my_log(u'策略初始化')

        # 实盘模式时才会真正加载 载入历史数据，并采用回放计算的方式初始化策略数值
        if self.cta_engine.interval == Interval.MINUTE:
            # todo 当前分钟会触发2次 1次来自load_bar 一次来自on_tick
            self.load_bar(math.ceil(self.seg_size / 24 / 60), Interval.MINUTE, use_database=False)
        elif self.cta_engine.interval == Interval.HOUR:
            self.load_bar(math.ceil(self.seg_size / 24), Interval.HOUR, use_database=False)
        elif self.cta_engine.interval == Interval.DAILY:
            # 加载小时是因为BarGenerator已经指定为小时24个窗口
            self.load_bar(self.seg_size, Interval.HOUR, use_database=False)
        else:
            self.load_bar(self.seg_size, self.cta_engine.interval, use_database=False)

        # self.putEvent()

    def my_log(self, msg: str):
        if isinstance(self.cta_engine, BacktestingEngine):
            if not self.no_log:
                print(f"{datetime.now()}\t{msg}")
        else:
            self.write_log(msg)

    def my_pos(self, bar=None):
        if isinstance(self.cta_engine, BacktestingEngine):
            return self.pos
        else:
            account_symbol2 = self.cta_engine.main_engine.engines["oms"].get_account("binance." + self.symbol2)
            # 币安每余额返回None
            if account_symbol2:
                if not bar or bar.close_price * account_symbol2.available > 20:
                    return account_symbol2.available
                else:
                    return 0
            else:
                return 0

    def my_available_cash(self):
        if isinstance(self.cta_engine, BacktestingEngine):
            return self.available_cash
        else:
            account_symbol1 = self.cta_engine.main_engine.engines["oms"].get_account("binance." + self.symbol1)
            # 币安每余额返回None
            if account_symbol1:
                return account_symbol1.available
            else:
                return 0

    # ----------------------------------------------------------------------
    def on_start(self):
        """启动策略（必须由用户继承实现）"""
        self.my_log(u'策略启动，参数如下')
        for k in self.parameters + self.variables:
            self.my_log(f"{k}:{getattr(self, k)}")

        if not isinstance(self.cta_engine, BacktestingEngine):
            symbol1_account = self.cta_engine.main_engine.engines["oms"].get_account("binance." + self.symbol1)
            symbol2_account = self.cta_engine.main_engine.engines["oms"].get_account("binance." + self.symbol2)
            self.my_log(f"{symbol1_account}")
            self.my_log(f"{symbol2_account}")
        self.put_event()

    # ----------------------------------------------------------------------
    def on_stop(self):
        """停止策略（必须由用户继承实现）"""
        # if len(self.cta_engine.trades) % 2 == 1:
        #    self.cta_engine.trades.popitem()
        self.my_log(u'策略停止')
        self.put_event()
        if self.open_buy_price > 0.0:
            self.report_trade_data(None)

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
            # self.sell(999, abs(1))
            self.bg.update_bar(bar)

    def on_real_bar(self, bar):
        # print("on_day_bar:", bar.datetime, " bar:", bar)
        self.am.update_bar(bar)

        # if bar.datetime.year == 2022 and bar.datetime.month == 7 and bar.datetime.day == 20 and bar.datetime.hour == 9:
        #    print("on_day_bar:", bar.datetime, " bar:", bar)

        # 计算指标数值 - 过程指标，要在inited前执行
        self.sar_value = self.am.sar(self.sar_acceleration, self.sar_maximum)
        if self.sar_value < bar.close_price:
            if self.sar_high_step == 0:
                self.sar_switch_amount += 1
            self.sar_high_step += 1
            self.sar_low_step = 0
            if self.sar_high_step == 1:
                self.sar_first_price = self.sar_value
            #elif self.sar_high_step == 5:
            #    self.sar_angle = self.sar_value - self.sar_first_price
        else:
            if self.sar_low_step == 0:
                self.sar_switch_amount += 1
            self.sar_low_step += 1
            self.sar_high_step = 0

        if not self.am.inited:
            return

        # 回测时self.days天内数据过滤 在run_backtesting内
        if not self.inited:
            return

        self.cancel_all()

        # 计算指标数值
        # self.cciValue = self.am.cci(self.cciWindow)
        # self.keltnerup, self.keltnerdown = self.am.keltner(self.keltnerWindow, self.keltnerlMultiplier)

        # 计算指标数值
        self.rsi_value = self.am.rsi(self.rsi_length)

        # self.my_log(f"{bar.datetime} [cash:{self.my_available_cash()} pos:{self.my_pos()}] "
        #             f"[open:{bar.open_price} close:{bar.close_price} high:{bar.high_price} low:{bar.low_price} volume:{bar.volume}] "
        #             f"[sar_value:{self.sar_value} sar_high_step:{self.sar_high_step} sar_low_step:{self.sar_low_step}]"
        #             f"[rsi_value:{self.rsi_value} {self.sar_angle}]  "
        #             f"[close_price_max:{self.close_price_max} open_buy_price:{self.open_buy_price}]  ")

        # 开仓信号
        open_signal = False
        open_ema = 0
        if self.open_gt_ema > 1:
            open_ema = self.am.ema(self.open_gt_ema)
        b_open_sar = self.open_eq_sar_step == 0 or self.sar_high_step == self.open_eq_sar_step
        b_open_rsi = self.open_lt_rsi == 0 or self.rsi_value <= self.open_lt_rsi
        b_open_ema = self.open_gt_ema <= 1 or bar.close_price > open_ema
        if (b_open_sar and
                b_open_rsi and
                b_open_ema):
            open_signal = True
            self.trade_info['open_sar'] = self.sar_high_step #[self.sar_high_step, bool_color(b_open_sar)]
            self.trade_info['open_rsi'] = [round(self.rsi_value, 2), bool_color(b_open_rsi)]
            self.trade_info['open_em'] = [round(open_ema, 2), bool_color(b_open_ema)]
            self.report_signal_data(bar, 'open')

        # 当前无仓位，发送开仓委托
        if self.my_pos(bar) == 0:
            if open_signal:
                if self.position_ratio <= 1:
                    use_cash = self.my_available_cash() * self.position_ratio
                else:
                    use_cash = self.position_ratio
                fixed_size = use_cash / bar.close_price
                self.buy(bar.close_price, fixed_size)
                self.open_tmp_bar = bar
        elif self.my_pos(bar) > 0.0:
            if self.open_buy_price <= 0.0 or self.close_price_max <= 0.0:
                self.my_log("当前有仓位，需要初始化买入价相关信息！")
            else:
                close_ema = 0
                if self.stop_lt_ema > 1:
                    close_ema = self.am.ema(self.stop_lt_ema)

                self.close_price_max = max(self.close_price_max, bar.close_price)
                stop_gt_move_price = self.close_price_max * (1 - self.stop_gt_move)
                stop_win_price = self.open_buy_price * (1 + self.stop_win_per)
                stop_loss_price = self.open_buy_price * (1 + self.stop_loss_per)

                # 卖出条件：sar向下拐点 或 到达移动止损
                b_close_sar = False
                if self.stop_eq_sar_step > 0:
                    if self.stop_eq_sar_step == self.sar_low_step:
                        b_close_sar = True

                b_close_move = self.stop_gt_move > 0.0 and bar.close_price < stop_gt_move_price
                b_close_rsi = 0.0 < self.stop_gt_rsi <= self.rsi_value
                b_close_ema = self.stop_lt_ema > 0 and bar.close_price < close_ema
                b_close_win_per = self.stop_win_per > 0.0 and bar.close_price >= stop_win_price
                b_close_loss_per = self.stop_loss_per > 0.0 and bar.close_price <= stop_loss_price
                if b_close_sar or \
                        b_close_move or \
                        b_close_ema or \
                        b_close_rsi or \
                        b_close_win_per or \
                        b_close_loss_per:
                    self.sell(bar.close_price, abs(self.pos))
                    self.trade_info['close_sar'] = [self.sar_low_step, bool_color(b_close_sar)]
                    self.trade_info['close_move'] = [round(stop_gt_move_price, 2), bool_color(b_close_move)]
                    self.trade_info['close_rsi'] = [round(self.rsi_value, 2), bool_color(b_close_rsi)]
                    self.trade_info['close_ema'] = [round(close_ema, 2), bool_color(b_close_ema)]
                    self.trade_info['stop_win_per'] = [round(stop_win_price, 2), bool_color(b_close_win_per)]
                    self.trade_info['stop_loss_per'] = [round(stop_loss_price, 2), bool_color(b_close_loss_per)]
        self.sync_data()
        self.put_event()

    def on_order(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        pass

    # ----------------------------------------------------------------------
    def on_trade(self, trade: TradeData):
        # 发出状态更新事件
        if trade.direction == Direction.LONG:
            self.available_cash -= (trade.price * trade.volume) * (1.0 + self.cta_engine.rate)
            self.open_buy_price = trade.price
            if self.open_tmp_bar:
                self.close_price_max = self.open_tmp_bar.high_price
                self.open_tmp_bar = None
            self.trade_info['open_trade_time'] = trade.datetime
            # print(f"on_trade long datetime:{trade.datetime} price:{trade.price} ")
            # self.my_log(f"on_trade long datetime:{trade.datetime} price:{trade.price} ")
        elif trade.direction == Direction.SHORT:
            self.available_cash += (trade.price * trade.volume) * (1.0 - self.cta_engine.rate)
            self.trade_info['available_cash_max'] = max(self.available_cash, self.trade_info.get('available_cash_max', 0))
            self.report_trade_data(trade)
            self.close_price_max = 0
            self.open_buy_price = 0
            # self.my_log(f"on_trade short datetime:{trade.datetime} price:{trade.price} ")
        self.sync_data()
        self.put_event()

    # ----------------------------------------------------------------------
    def on_stop_order(self, so):
        """停止单推送"""
        pass

    def report_trade_data(self, trade):
        # if trade.datetime.year == 2018 and trade.datetime.month == 5 and trade.datetime.day == 18 and trade.datetime.hour == 1:
        #     print("on_day_bar:", trade.datetime, " bar:", trade)

        if len(self.report_trade) == 0:
            self.report_trade.append([['序号', 'FFA500', 5], ['开仓时间', 'FFA500', 25], '开仓价格', ['平仓时间', 'FFA500', 25], '平仓价格',
                                      '盈亏率', ['交易数量', 'FFA500', 20], 'Balance', '回撤率', 'INFO',
                                      'open_sar', 'open_rsi', 'open_em',
                                      'close_sar', 'close_move', 'close_rsi', 'close_ema', 'stop_win_per', 'stop_loss_per'])

        if trade:
            # 盈亏率
            real_sell_price = trade.price * (1.0 - self.cta_engine.rate)
            real_buy_price = self.open_buy_price * (1.0 + self.cta_engine.rate)
            spread = (real_sell_price - real_buy_price) / real_buy_price
            profit_loss_spread = [format(spread, '.4f'), "008000"]
            if spread < 0.0:
                profit_loss_spread = [format(abs(spread), '.4f'), "DC143C"]

            # 回撤率
            dd_percent = 0
            available_cash_max = self.trade_info.get('available_cash_max')
            if available_cash_max > 0:
                dd_percent = round((self.available_cash - available_cash_max) / available_cash_max, 2)

            data = [len(self.report_trade), self.trade_info.get('open_trade_time'), self.open_buy_price, trade.datetime,
                    trade.price, profit_loss_spread, trade.volume, self.my_available_cash(), dd_percent,
                    self.sar_switch_amount,
                    self.trade_info.get('open_sar'), self.trade_info.get('open_rsi'), self.trade_info.get('open_em'),
                    self.trade_info.get('close_sar'), self.trade_info.get('close_move'), self.trade_info.get('close_rsi'), self.trade_info.get('close_ema'),
                    self.trade_info.get('stop_win_per'), self.trade_info.get('stop_loss_per')]
        else:
            data = [len(self.report_trade), self.trade_info.get('open_trade_time'), self.open_buy_price, "", '',
                    '', '', '', '',
                    self.trade_info.get('open_sar'), self.trade_info.get('open_rsi'), self.trade_info.get('open_em'),
                    '', '', '']
        self.report_trade.append(data)

    def report_signal_data(self, bar, action):
        if len(self.report_signal) == 0:
            self.report_signal.append(['序号', '时间', '开/平仓', '价格',
                                       'open_sar', 'open_rsi', 'open_em',
                                       'close_sar', 'close_move', 'close_rsi'])
        if action == 'open':
            data = [len(self.report_signal), bar.datetime, action, bar.close_price,
                    self.trade_info['open_sar'], self.trade_info['open_rsi'], self.trade_info['open_em'],
                    '', '', '']
        else:
            data = [len(self.report_signal), bar.datetime, action, bar.close_price,
                    '', '', '',
                    self.trade_info['close_sar'], self.trade_info['close_move'], self.trade_info['close_rsi']]
        self.report_signal.append(data)
