"""
General utility functions.
"""
import pandas as pd
import multiprocessing
import traceback
import numpy as np
import copy
from collections import defaultdict
from pandas import DataFrame
from pytz import timezone
from vnpy_ctastrategy.backtesting import BacktestingEngine, load_bar_data, load_tick_data, OptimizationSetting
from vnpy_ctastrategy.base import (
    BacktestingMode,
    INTERVAL_DELTA_MAP
)
from datetime import date, datetime, timedelta
from vnpy.trader.constant import (Direction, Offset, Interval)
from vnpy_ctastrategy.template import CtaTemplate
from threading import Lock
from multiprocessing import Pool,Lock,Manager
from quant.units import bool_color

pd.set_option('mode.chained_assignment', None)

history_data = None


class BacktestingEngineEx(BacktestingEngine):
    """
    For:
    1. time series container of bar data
    2. calculating technical indicator value
    """

    def __init__(self):
        super().__init__()
        self.out_log = True
        self.daily_dfs = None
        self.cpu_count = multiprocessing.cpu_count()

    def output(self, msg):
        """
        Output message of backtesting engine.
        """
        if self.out_log:
            print(f"{datetime.now()}\t{msg}")

    def load_data(self):
        """"""
        global history_data
        self.output("开始加载历史数据")

        if not self.end:
            self.end = datetime.now()

        if self.start >= self.end:
            self.output("起始日期必须小于结束日期")
            return

        self.history_data.clear()  # Clear previously loaded history data

        if history_data:
            self.history_data = copy.deepcopy(history_data)
            return

        # Load 30 days of data each time and allow for progress update
        total_days = (self.end - self.start).days
        progress_days = max(int(total_days / 10), 1)
        progress_delta = timedelta(days=progress_days)
        interval_delta = INTERVAL_DELTA_MAP[self.interval]

        start = self.start
        end = self.start + progress_delta
        progress = 0

        while start < self.end:
            progress_bar = "#" * int(progress * 10 + 1)
            self.output(f"加载进度：{progress_bar} [{progress:.0%}] range:{start}-{end} data:{len(self.history_data)}")

            end = min(end, self.end)  # Make sure end time stays within set range

            if self.mode == BacktestingMode.BAR:
                data = load_bar_data(
                    self.symbol,
                    self.exchange,
                    self.interval,
                    start,
                    end
                )
            else:
                data = load_tick_data(
                    self.symbol,
                    self.exchange,
                    start,
                    end
                )

            if not data:
                self.output(f"无数据，确认已下载：range:{start}-{end} data:{len(self.history_data)}")

            self.history_data.extend(data)

            progress += progress_days / total_days
            progress = min(progress, 1)
            start = end + interval_delta
            end += progress_delta

        history_data = copy.deepcopy(self.history_data)
        self.output(f"历史数据加载完成，数据量：{len(self.history_data)}")

    def run_backtesting(self):
        """"""
        if self.mode == BacktestingMode.BAR:
            func = self.new_bar
        else:
            func = self.new_tick

        self.strategy.on_init()

        # Use the first [days] of history data for initializing strategy
        day_count = 1
        ix = 0

        for ix, data in enumerate(self.history_data):
            if self.datetime and data.datetime.day != self.datetime.day:
                day_count += 1
                if day_count >= self.days:
                    break

            self.datetime = data.datetime

            try:
                self.callback(data)
            except Exception:
                self.output("触发异常，回测终止")
                self.output(traceback.format_exc())
                return

        self.strategy.inited = True
        self.output("策略初始化完成")

        self.strategy.on_start()
        self.strategy.trading = True
        self.output("开始回放历史数据")

        # Use the rest of history data for running backtesting
        # ti ix: + 1
        backtesting_data = self.history_data[ix:]
        if not backtesting_data:
            self.output("历史数据不足，回测终止")
            return

        total_size = len(backtesting_data)
        batch_size = max(int(total_size / 10), 1)

        for ix, i in enumerate(range(0, total_size, batch_size)):
            batch_data = backtesting_data[i: i + batch_size]
            for data in batch_data:
                try:
                    func(data)
                except Exception:
                    self.output("触发异常，回测终止")
                    self.output(traceback.format_exc())
                    return

            progress = min(ix / 10, 1)
            progress_bar = "=" * (ix + 1)
            self.output(f"回放进度：{progress_bar} [{progress:.0%}]")

        self.strategy.on_stop()
        self.output("历史数据回放结束")

    def run_optimization(self, optimization_setting: OptimizationSetting, output=True):
        """"""
        self.load_data()

        # Get optimization setting and target
        settings = optimization_setting.generate_setting()
        target_name = optimization_setting.target_name

        if not settings:
            self.output("优化参数组合为空，请检查")
            return

        if not target_name:
            self.output("优化目标未设置，请检查")
            return

        # Use multiprocessing pool for running backtesting with different setting
        # Force to use spawn method to create new process (instead of fork on Linux)
        ctx = multiprocessing.get_context("spawn")
        #cpu_count = multiprocessing.cpu_count()
        pool = ctx.Pool(self.cpu_count)

        start = datetime.now()
        op_idx = 0
        results = []
        op_total = len(settings)
        progress_delta = int(op_total / 10)

        print(f"{start} settings:{op_total}, delta:{progress_delta}")

        for setting in settings:
            op_idx += 1
            idx = 0
            if progress_delta > 0 and int(op_idx % progress_delta) == 0:
                idx = op_idx
            # print(op_idx % progress_delta)
            result = (pool.apply_async(optimizeEx, (
                target_name,
                self.strategy_class,
                setting,
                self.vt_symbol,
                self.interval,
                self.start,
                self.rate,
                self.slippage,
                self.size,
                self.pricetick,
                self.capital,
                self.end,
                self.mode,
                self.inverse,
                idx,
                self.history_data
            )))
            results.append(result)

        pool.close()
        pool.join()

        new_results = {
            "result_move_time_stat": {},
            "result_end_time_stat": {}
        }

        for result in results:
            one = result.get()
            for stat in one[0]:
                move_time = stat[0]
                setting = stat[1]
                target_value = stat[2]
                statistics = stat[3]
                if move_time not in new_results["result_move_time_stat"]:
                    new_results["result_move_time_stat"][move_time] = []
                new_results["result_move_time_stat"][move_time].append((setting, target_value, statistics))

            for stat in one[1]:
                move_time = stat[0]
                setting = stat[1]
                target_value = stat[2]
                statistics = stat[3]
                if move_time not in new_results["result_end_time_stat"]:
                    new_results["result_end_time_stat"][move_time] = []
                new_results["result_end_time_stat"][move_time].append((setting, target_value, statistics))

        # result_move_time_stat = []
        for ent in new_results["result_move_time_stat"]:
            new_results["result_move_time_stat"][ent].sort(reverse=True, key=lambda result: result[1])
            # result_move_time_stat.append(new_results["result_move_time_stat"][ent][0])
        for ent in new_results["result_end_time_stat"]:
            new_results["result_end_time_stat"][ent].sort(reverse=True, key=lambda result: result[1])

        return new_results

        # Sort results and output
        result_values = [result.get() for result in results]
        result_values.sort(reverse=True, key=lambda result: result[1])

        end = datetime.now()
        print(start, end, end - start)
        if output:
            for value in result_values:
                msg = f"参数：{value[0]}, 目标：{value[1]}"
                self.output(msg)

        return result_values

    def calculate_statistics_new(self, start=None, end=None):
        # 区间推进
        interval_delta = INTERVAL_DELTA_MAP[self.interval]
        def_stat = self.calculate_result_new()
        result_def_stat = [[['指标', 'FFA500', 20], '值'],
                           ["时间段", f"{start.strftime('%Y-%m-%d')} - {end.strftime('%Y-%m-%d')}"]]
        for key in def_stat:
            result_def_stat += [[key, def_stat[key]]]
        title = ["开始时间", "结束时间"]
        for name in def_stat:
            title += [name]
        result_end_time_stat = [title]
        result_move_time_stat = [title]
        stat_end = start

        def calculate_result(stats, values):
            for k, v in stats.items():
                if k == '总收益率':
                    if float(v.replace('%', '')) < 0:
                        v = [v, "DC143C"]
                    else:
                        v = [v, ""]
                values += [v]
            return values
        while True:
            if stat_end >= end:
                break
            stat_end += interval_delta * 10
            if stat_end >= end:
                stat_end = end

            values = [start, stat_end]
            stats = self.calculate_result_new(start, stat_end)
            result_end_time_stat += [calculate_result(stats, values)]

            if stat_end - start > interval_delta * 365:
                values = [stat_end - interval_delta * 365, stat_end]
                stats = self.calculate_result_new(stat_end - interval_delta * 365, stat_end)
                result_move_time_stat += [calculate_result(stats, values)]
        return def_stat, result_def_stat, result_end_time_stat, result_move_time_stat

    def calculate_result_new(self, start=None, end=None):
        """
        Calculate trade result from increment
        """
        capital = 0
        end_balance = 0
        total_return = 0
        max_drawdown = 0
        max_ddpercent = 0
        return_drawdown_ratio = 0

        trade_count = 0
        win_count = 0
        loss_count = 0
        winning_rate = 0
        win_loss_pnl_ratio = 0

        pnl_medio = 0
        duration_medio = 0
        commission_medio = 0
        slipping_medio = 0

        win_amount = 0
        win_pnl_medio = 0
        win_duration_medio = 0

        loss_amount = 0
        loss_pnl_medio = 0
        loss_duration_medio = 0

        if len(self.trades) > 0:
            if start and end:
                start = start.replace(tzinfo=timezone('Asia/Shanghai'))
                end = end.replace(tzinfo=timezone('Asia/Shanghai'))
            dt, direction, offset, price, volume = [], [], [], [], []
            trade_last = None
            for i in self.trades.values():
                # 区间交易记录
                if (start and end) and (i.datetime < start or i.datetime > end):
                    continue
                # 第一笔交易不能是卖
                if len(dt) == 0 and i.direction == Direction.SHORT:
                    continue
                if len(dt) == 0:
                    capital = i.price * i.volume
                dt.append(i.datetime)
                direction.append(i.direction.value)
                offset.append(i.offset.value)
                price.append(i.price)
                volume.append(i.volume)
                trade_last = i

            if len(dt) > 0:
                # 如果最后一单是买单，要补上卖单
                if trade_last and trade_last.direction == Direction.LONG:
                    daily_last = None
                    for daily_result in self.daily_results.values():
                        if end and daily_result.date > end.date():
                            continue
                        daily_last = daily_result
                    if daily_last:
                        dt.append(datetime.fromordinal(daily_last.date.toordinal()).replace(tzinfo=timezone('Asia/Shanghai')))
                        direction.append(Direction.SHORT)
                        offset.append(Offset.CLOSE)
                        price.append(daily_last.close_price)
                        volume.append(trade_last.volume)

                # Generate DataFrame with datetime, direction, offset, price, volume
                base_df = pd.DataFrame()

                base_df["direction"] = direction
                base_df["offset"] = offset
                base_df["price"] = price
                base_df["volume"] = volume

                base_df["current_time"] = dt
                base_df["last_time"] = base_df["current_time"].shift(1)

                # Calculate trade amount
                base_df["amount"] = base_df["price"] * base_df["volume"]
                base_df["acum_amount"] = base_df["amount"].cumsum()

                # Calculate pos, net pos(with direction), acumluation pos(with direction)
                def calculate_pos(df):
                    if df["direction"] == "多":
                        result = df["volume"]
                    else:
                        result = - df["volume"]

                    return result

                base_df["pos"] = base_df.apply(calculate_pos, axis=1)

                base_df["net_pos"] = base_df["pos"].cumsum()
                base_df["acum_pos"] = base_df["volume"].cumsum()

                # Calculate trade result, acumulation result
                # ej: trade result(buy->sell) means (new price - old price) * volume
                base_df["result"] = -1 * base_df["pos"] * base_df["price"]
                base_df["acum_result"] = base_df["result"].cumsum()

                # Filter column data when net pos comes to zero
                def get_acum_trade_result(df):
                    if df["net_pos"] == 0:
                        return df["acum_result"]

                base_df["acum_trade_result"] = base_df.apply(get_acum_trade_result, axis=1)

                def get_acum_trade_volume(df):
                    if df["net_pos"] == 0:
                        return df["acum_pos"]

                base_df["acum_trade_volume"] = base_df.apply(get_acum_trade_volume, axis=1)

                def get_acum_trade_duration(df):
                    if df["net_pos"] == 0:
                        return df["current_time"] - df["last_time"]

                base_df["acum_trade_duration"] = base_df.apply(get_acum_trade_duration, axis=1)

                def get_acum_trade_amount(df):
                    if df["net_pos"] == 0:
                        return df["acum_amount"]

                base_df["acum_trade_amount"] = base_df.apply(get_acum_trade_amount, axis=1)

                # Select row data with net pos equil to zero
                base_df = base_df.dropna()

                trade_df = pd.DataFrame()
                trade_df["close_direction"] = base_df["direction"]
                trade_df["close_time"] = base_df["current_time"]
                trade_df["close_price"] = base_df["price"]
                trade_df["pnl"] = base_df["acum_trade_result"] - \
                                  base_df["acum_trade_result"].shift(1).fillna(0)

                trade_df["volume"] = base_df["acum_trade_volume"] - \
                                     base_df["acum_trade_volume"].shift(1).fillna(0)
                trade_df["duration"] = base_df["current_time"] - \
                                       base_df["last_time"]
                trade_df["turnover"] = base_df["acum_trade_amount"] - \
                                       base_df["acum_trade_amount"].shift(1).fillna(0)

                trade_df["commission"] = trade_df["turnover"] * self.rate
                trade_df["slipping"] = trade_df["volume"] * self.size * self.slippage
                trade_df["net_pnl"] = trade_df["pnl"] - \
                                      trade_df["commission"] - trade_df["slipping"]

                # result = calculate_base_net_pnl(trade_df, capital)
                df = trade_df
                df["acum_pnl"] = df["net_pnl"].cumsum()
                df["balance"] = df["acum_pnl"] + capital

                df["return"] = np.log(
                    df["balance"] / df["balance"].shift(1)
                ).fillna(0)
                df["highlevel"] = 0
                if len(df["balance"]) > 0:
                    df["highlevel"] = (
                        df["balance"].rolling(
                            min_periods=1, window=len(df), center=False).max()
                    )
                df["drawdown"] = df["balance"] - df["highlevel"]
                df["ddpercent"] = df["drawdown"] / df["highlevel"] * 100

                df.reset_index(drop=True, inplace=True)

                # result
                end_balancev = 0
                if len(df["balance"]) > 0:
                    end_balance = df["balance"].iloc[-1]

                max_drawdown = df["drawdown"].min()
                max_ddpercent = df["ddpercent"].min()

                pnl_medio = df["net_pnl"].mean()
                trade_count = len(df)
                duration_medio = df["duration"].mean().total_seconds() / 3600
                commission_medio = df["commission"].mean()
                slipping_medio = df["slipping"].mean()

                win = df[df["net_pnl"] > 0]
                win_amount = win["net_pnl"].sum()
                win_pnl_medio = win["net_pnl"].mean()
                win_duration_medio = win["duration"].mean().total_seconds() / 3600
                win_count = len(win)

                loss = df[df["net_pnl"] < 0]
                loss_amount = loss["net_pnl"].sum()
                loss_pnl_medio = loss["net_pnl"].mean()
                loss_duration_medio = loss["duration"].mean().total_seconds() / 3600
                loss_count = len(loss)

                winning_rate = win_count / trade_count
                win_loss_pnl_ratio = - win_pnl_medio / loss_pnl_medio

                total_return = (end_balance / capital - 1) * 100
                return_drawdown_ratio = 0
                if max_ddpercent > 0:
                    return_drawdown_ratio = -total_return / max_ddpercent

        statistics = dict()
        statistics["起始资金"] = f"{capital:,.2f}"
        statistics["结束资金"] = f"{end_balance:,.2f}"
        statistics["总收益率"] = f"{total_return:.2f}"
        statistics["最大回撤(百分比最大回撤时"] = f"{max_drawdown:,.2f}"
        statistics["百分比最大回撤"] = f"{max_ddpercent:,.2f}%"
        statistics["收益回撤比"] = f"{return_drawdown_ratio:,.2f}"

        statistics["总成交次数"] = f"{trade_count}"
        statistics["盈利成交次数"] = f"{win_count}"
        statistics["亏损成交次数"] = f"{loss_count}"
        statistics["胜率"] = f"{winning_rate:,.2f}"
        statistics["盈亏比"] = f"{win_loss_pnl_ratio:,.2f}"

        statistics["平均每笔盈亏"] = f"{pnl_medio:,.2f}"
        statistics["平均持仓小时"] = f"{duration_medio:,.2f}"
        statistics["平均每笔手续费"] = f"{commission_medio:,.2f}"
        statistics["平均每笔滑点"] = f"{slipping_medio:,.2f}"

        statistics["总盈利金额"] = f"{win_amount:,.2f}"
        statistics["盈利交易均值"] = f"{win_pnl_medio:,.2f}"
        statistics["盈利持仓小时"] = f"{win_duration_medio:,.2f}"

        statistics["总亏损金额"] = f"{loss_amount:,.2f}"
        statistics["亏损交易均值"] = f"{loss_pnl_medio:,.2f}"
        statistics["亏损持仓小时"] = f"{loss_duration_medio:,.2f}"

        return statistics

    def calculate_result(self):
        """"""
        self.output("开始计算逐日盯市盈亏")

        if not self.trades:
            self.output("成交记录为空，无法计算")
            return

        # Add trade data into daily reuslt.
        for trade in self.trades.values():
            d = trade.datetime.date()
            daily_result = self.daily_results[d]
            daily_result.add_trade(trade)

        # Calculate daily result by iteration.
        pre_close = 0
        start_pos = 0

        for daily_result in self.daily_results.values():
            daily_result.calculate_pnl(
                pre_close,
                start_pos,
                self.size,
                self.rate,
                self.slippage
               # self.inverse
            )

            pre_close = daily_result.close_price
            start_pos = daily_result.end_pos

        # Generate dataframe
        results = defaultdict(list)

        for daily_result in self.daily_results.values():
            if self.daily_dfs and daily_result.date in self.daily_dfs:
                self.daily_dfs[daily_result.date] = DataFrame.from_dict(results).set_index("date")
            for key, value in daily_result.__dict__.items():
                results[key].append(value)

        self.daily_df = DataFrame.from_dict(results).set_index("date")

        self.output("逐日盯市盈亏计算完成")
        return self.daily_df

    def statistics_batch(self):
        interval_delta = INTERVAL_DELTA_MAP[self.interval]
        self.daily_dfs = {}
        s = self.start
        while True:
            if s >= self.end:
                break
            s += interval_delta * 365
            if s >= self.end:
                s = self.end
            self.daily_dfs[s.date()] = []


def optimizeEx(
        target_name: str,
        strategy_class: CtaTemplate,
        setting: dict,
        vt_symbol: str,
        interval: Interval,
        start: datetime,
        rate: float,
        slippage: float,
        size: float,
        pricetick: float,
        capital: int,
        end: datetime,
        mode: BacktestingMode,
        inverse: bool,
        idx,
        history_data
):
    """
    Function for running in multiprocessing.pool
    """

    engine = BacktestingEngineEx()
    engine.out_log = False

    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        rate=rate,
        slippage=slippage,
        size=size,
        pricetick=pricetick,
        capital=capital,
        end=end,
        mode=mode,
        inverse=inverse
    )

    engine.add_strategy(strategy_class, setting)
    engine.history_data = history_data
    #engine.load_data()
    engine.run_backtesting()
    engine.calculate_result()

    # statistics_op = {}
    # for ent in engine.daily_dfs:
    #     engine.daily_df = engine.daily_dfs[ent]
    #     statistics_op[ent] = engine.calculate_statistics(output=False)

    # statistics = engine.calculate_statistics(output=False)

    statistics, result_def_stat, result_end_time_stat, result_move_time_stat = engine.calculate_statistics_new(start, end)

    # target_value = statistics[target_name]

    if idx > 0:
        print(f"{datetime.now()}-{idx}\t")

    def calculate_result(stats):
        items = []
        for item in stats[1:]:
            key = f"{item[0]}-{item[1]}"
            target_value = 0
            if len(item) > 4:
                target_value = float(item[4][0])
            items.append((key, setting, target_value, item[2:]))
        return items

    result_move_time = calculate_result(result_move_time_stat)
    result_end_time = calculate_result(result_end_time_stat)

    # for stat in result_move_time_stat:
    #     key = f"{stat[0]}-{stat[1]}"
    #     target_value = 0
    #     if len(stat) > 4:
    #         target_value = float(stat[4][0])
    #     result_move_time.append((key, str(setting), target_value, stat))
    #
    # result_end_time = []
    # for stat in result_end_time_stat:
    #     key = f"{stat[0]}-{stat[1]}"
    #     target_value = 0
    #     if len(stat) > 4:
    #         target_value = float(stat[4][0])
    #     result_end_time.append((key, str(setting), target_value, stat))

    return (result_move_time, result_end_time)
    # return (str(setting), target_value, statistics)
