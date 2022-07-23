from quant.units import bool_color
from quant.strategies.base_strategy import BaseStrategy


class Strategy1(BaseStrategy):

    def on_real_bar(self, bar):
        # print("on_day_bar:", bar.datetime, " bar:", bar)
        self.am.update_bar(bar)

        if bar.datetime.year == 2020 and bar.datetime.month == 9 and bar.datetime.day == 3:
            print("on_day_bar:", bar.datetime, " bar:", bar)

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

        #if not self.am.inited:
        #    return

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
