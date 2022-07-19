from quant.vnpy.app.cta_strategy.backtestingEx import BacktestingEngineEx
from vnpy.trader.object import Interval
from strategies.sar_strategy import SarStrategy
from quant.units import report_excel_xlsx
from vnpy.trader.database import get_database
from vnpy_ctastrategy.base import (
    BacktestingMode,
    INTERVAL_DELTA_MAP
)
from datetime import datetime
from pytz import timezone
import os


def run(currency, setting, rate, capital):
    engine = BacktestingEngineEx()
    symbol = currency + "usdt"
    interval = Interval.DAILY
    overview = get_database().get_bar_overview()
    data = None
    for item in overview:
        if item.symbol == symbol.lower() and item.interval == interval:
            data = item
            break
    interval_delta = INTERVAL_DELTA_MAP[interval]

    start = data.start
    end = data.end
    # 日要从8点开始
    # start = datetime(2018, 9, 6, 8) - interval_delta * 30
    # end = datetime(2019, 9, 6, 8)
    engine.set_parameters(
        vt_symbol=symbol.lower() + ".BINANCE",
        # vt_symbol="xmrusdt.BINANCE",  # 现货的数据
        interval=interval,
        start=start,
        end=end,
        rate=rate,  # 币安手续费千分之1， BNB 万7.5  7.5/10000
        slippage=0,
        size=1,  # 币本位合约 100
        pricetick=0.01,  # 价格精度.
        capital=capital)
    engine.load_data()

    engine.add_strategy(SarStrategy, setting)
    engine.run_backtesting()

    #engine.statistics_batch()
    engine.calculate_result()  # 计算回测的结果
    # statistics_op = {}
    # for ent in engine.daily_dfs:
    #     engine.daily_df = engine.daily_dfs[ent]
    #     statistics_op[ent] = engine.calculate_statistics(output=False)
    engine.calculate_statistics()  # 计算一些统计指标
    engine.show_chart(safe_path="/home/data/docker-volume/nginx-php/html/www.tiham.com/cache/")  # 绘制图表 https://tiham.com/cache/fig.png

    # 区间推进统计
    def_stat, result_def_stat, result_end_time_stat, result_move_time_stat = engine.calculate_statistics_all(start, end)

    # 参数
    str_parameter = []
    parameters = [[['参数', 'FFA500', 20], '值']]
    for attr in engine.strategy.parameters:
        val = getattr(engine.strategy, attr)
        parameters += [[attr, val]]
        str_parameter.append(str(val))
    str_parameter = " ".join(map(str, str_parameter))

    report = [["交易信息", engine.strategy.report_trade],
              ["信号", engine.strategy.report_signal],
              ["结束时间推进统计", result_end_time_stat],
              ["区间时间推进统计", result_move_time_stat],
              ["默认统计", result_def_stat],
              ["参数", parameters]]

    #title_statistics = f"[{def_stat['总收益率']}_{def_stat['总成交次数']}_{def_stat['百分比最大回撤']}_{def_stat['胜率']}_{def_stat['盈亏比']}]"
    title_statistics = ""
    file_name = f"交易记录-{symbol}-{interval}-{title_statistics}-[{str_parameter}].xlsx"

    save_file = "result/" + file_name
    if os.path.exists(save_file):
        os.remove(save_file)
    report_excel_xlsx(save_file, report)

    print(file_name)
    print("overview:", data.symbol, data.interval, start, end)


if __name__ == '__main__':
    currency = ['btc']
    rate = 1.0 / 1000
    capital = 100

    setting = dict()
    setting["btc"] = {
        "class_name": "SarStrategy",
        "interval": "d",
        "seg_size": 30,
        "sar_acceleration": 0.02,
        "sar_maximum": 0.2,
        "rsi_length": 14,
        "position_ratio": 100,
        "slippage": 0.001,
        "open_eq_sar_step": 1,
        "open_lt_rsi": 0,  # [20, 1, 90] 0
        "open_gt_ema": 0,  # [0, 1, 30] 2
        "stop_eq_sar_step": 1,  # [1, 1, 10] 0
        "stop_gt_rsi": 0,
        "stop_lt_ema": 0,
        "stop_gt_move": 0.189,  # [0.01, 0.01, 0.3] 0.22
        "stop_win_per": 0.0,
        "stop_loss_per": 0.0
    }
    for ent in currency:
        run(ent, setting[ent], rate, capital)
