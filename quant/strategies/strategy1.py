from quant.units import bool_color
from quant.strategies.base_strategy import BaseStrategy


class Strategy1(BaseStrategy):

    def on_real_bar(self, bar):
        # print("on_day_bar:", bar.datetime, " bar:", bar)
        self.am.update_bar(bar)

        if bar.datetime.year == 2022 and bar.datetime.month == 7 and bar.datetime.day == 28 and bar.datetime.hour == 5:
           print("on_day_bar:", bar.datetime, " bar:", bar)

        # SAR
        self.sar_value = self.am.sar(self.sar_acceleration, self.sar_maximum)
        if self.sar_value < bar.close_price:
            if self.sar_high_step == 0:
                self.sar_switch_amount += 1
            self.sar_high_step += 1
            self.sar_low_step = 0
            if self.sar_high_step == 1:
                self.sar_first_price = self.sar_value
        else:
            if self.sar_low_step == 0:
                self.sar_switch_amount += 1
            self.sar_low_step += 1
            self.sar_high_step = 0

        # RSI
        rsi_value = self.am.rsi(self.rsi_length)
        # EMA
        open_ema = self.am.ema(self.open_gt_ema) if self.open_gt_ema > 1 else 0
        close_ema = self.am.ema(self.stop_lt_ema) if self.stop_lt_ema > 1 else 0

        # 不需要等ArrayManagerEx初始化
        # if not self.am.inited:
        #    return
        # 回测时self.days天内数据过滤（在run_backtesting内） 实盘时初始化后
        # if not self.inited:
        #     return

        self.cancel_all()

        self.my_log(f"{bar.datetime} [cash:{self.my_available_cash()} pos:{self.my_pos()}] "
                    f"[open:{bar.open_price} close:{bar.close_price} high:{bar.high_price} low:{bar.low_price} volume:{bar.volume}] "
                    f"[sar_value:{self.sar_value} sar_high_step:{self.sar_high_step} sar_low_step:{self.sar_low_step}]"
                    f"[rsi_value:{rsi_value} ]  "
                    f"[open_ema:{open_ema} ]  "
                    f"[close_price_max:{self.close_price_max} open_buy_price:{self.open_buy_price}]  ")

        b_open_sar = self.open_eq_sar_step == 0 or self.sar_high_step == self.open_eq_sar_step
        b_open_rsi = self.open_lt_rsi == 0 or rsi_value <= self.open_lt_rsi
        # 这里防止实盘时如果交易没成功重复下单
        b_open_ema = self.open_gt_ema <= 1 or (bar.close_price > open_ema > self.am.close_array[-2])

        # 开仓信号
        open_signal = False
        if (b_open_sar and
                b_open_rsi and
                b_open_ema):
            open_signal = True
            self.trade_info['open_sar'] = self.sar_high_step #[self.sar_high_step, bool_color(b_open_sar)]
            self.trade_info['open_rsi'] = [round(rsi_value, 2), bool_color(b_open_rsi)]
            self.trade_info['open_em'] = [round(open_ema, 2), bool_color(b_open_ema)]
            self.report_signal_data(bar, 'open')

        #
        #
        # 买入后最高收盘价
        self.close_price_max = max(self.close_price_max, bar.close_price)

        stop_gt_move_price = self.close_price_max * (1 - self.stop_gt_move)
        stop_win_price = self.open_buy_price * (1 + self.stop_win_per)
        stop_loss_price = self.open_buy_price * (1 - self.stop_loss_per)

        # 卖出条件：sar向下拐点 或 到达移动止损
        b_close_sar = self.stop_eq_sar_step > 0 and (self.stop_eq_sar_step == self.sar_low_step)
        b_close_move = self.stop_gt_move > 0.0 and bar.close_price < stop_gt_move_price
        b_close_rsi = 0.0 < self.stop_gt_rsi <= rsi_value
        # 这里防止实盘时如果交易没成功重复下单
        b_close_ema = self.stop_lt_ema > 0 and (bar.close_price < close_ema < self.am.close_array[-2])
        b_close_win_per = self.stop_win_per > 0.0 and bar.close_price >= stop_win_price
        b_close_loss_per = self.stop_loss_per > 0.0 and bar.close_price <= stop_loss_price
        close_signal = False
        if b_close_sar or \
                b_close_move or \
                b_close_ema or \
                b_close_rsi or \
                b_close_win_per or \
                b_close_loss_per:
            close_signal = True

        # 当前无仓位，发送开仓委托
        if self.my_pos(bar) == 0:
            if open_signal:
                if self.position_ratio <= 1:
                    use_cash = self.my_available_cash() * self.position_ratio
                else:
                    use_cash = self.position_ratio
                fixed_size = use_cash / bar.close_price
                if self.inited:
                    self.buy(bar.close_price, fixed_size)
                self.open_buy_price = bar.close_price
                self.close_price_max = bar.close_price
        elif self.my_pos(bar) > 0.0:
            # if self.open_buy_price <= 0.0 or self.close_price_max <= 0.0:
            #     self.my_log("当前有仓位，需要初始化买入价相关信息！")
            # else:
            if close_signal and self.inited:
                self.sell(bar.close_price, abs(self.pos))

            self.trade_info['close_sar'] = [self.sar_low_step, bool_color(b_close_sar)]
            self.trade_info['close_move'] = [round(stop_gt_move_price, 2), bool_color(b_close_move)]
            self.trade_info['close_rsi'] = [round(rsi_value, 2), bool_color(b_close_rsi)]
            self.trade_info['close_ema'] = [round(close_ema, 2), bool_color(b_close_ema)]
            self.trade_info['stop_win_per'] = [round(stop_win_price, 2), bool_color(b_close_win_per)]
            self.trade_info['stop_loss_per'] = [round(stop_loss_price, 2), bool_color(b_close_loss_per)]
        self.sync_data()
        self.put_event()
