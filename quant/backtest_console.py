from quant.vnpy.app.cta_strategy.backtestingEx import BacktestingEngineEx
from vnpy.trader.object import Interval
from quant.units import report_excel_xlsx
from vnpy.trader.database import get_database
from strategies.sar_strategy import SarStrategy
from datetime import datetime
import os
import pytz
import sys


def run(currency):
    symbol = "btcusdt"
    eng_conf = {
        "vt_symbol": "btcusdt.BINANCE",
        "interval": "1h",
        "start": "",
        "end": "",
        "rate": 0.001,
        "slippage": 0.0,
        "size": 1,
        "pricetick": 0.01,
        "capital": 200,
        "mode": 1
    }
    setting_conf = {
        "class_name": "SarStrategy",
        "seg_size": 200,
        "sar_acceleration": 0.02,
        "sar_maximum": 0.2,
        "rsi_length": 14,
        "position_ratio": 100,
        "open_eq_sar_step": 0,
        "open_lt_rsi": 0,
        "open_gt_ema": 105,
        "stop_eq_sar_step": 0,
        "stop_gt_rsi": 0,
        "stop_lt_ema": 95,
        "stop_gt_move": 0,
        "stop_win_per": 0,
        "stop_loss_per": 0
    }

    interval = Interval(eng_conf["interval"])
    engine = BacktestingEngineEx()
    overview = get_database().get_bar_overview()
    data = None
    for item in overview:
        if item.symbol == symbol.lower() and item.interval == interval:
            data = item
            break

    start = data.start
    if eng_conf["start"] != "":
        start2 = datetime.strptime(eng_conf["start"], '%Y-%m-%d %H:%M:%S')
        cn_zone = pytz.timezone('Asia/Shanghai')
        start = cn_zone.localize(dt=start2)

    end = data.end
    if eng_conf["end"] != "":
        end2 = datetime.strptime(eng_conf["end"], '%Y-%m-%d %H:%M:%S')
        cn_zone = pytz.timezone('Asia/Shanghai')
        end = cn_zone.localize(dt=end2)

    engine.set_parameters(
        vt_symbol=eng_conf["vt_symbol"],
        interval=Interval(eng_conf["interval"]),
        start=start,
        end=end,
        rate=eng_conf["rate"],
        slippage=eng_conf["slippage"],
        size=eng_conf["size"],
        pricetick=eng_conf["pricetick"],
        capital=eng_conf["capital"])
    engine.load_data()

    engine.add_strategy(getattr(sys.modules[__name__], setting_conf["class_name"]), setting_conf)
    engine.run_backtesting()

    # engine.statistics_batch()
    engine.calculate_result()  # 计算回测的结果
    # statistics_op = {}
    # for ent in engine.daily_dfs:
    #     engine.daily_df = engine.daily_dfs[ent]
    #     statistics_op[ent] = engine.calculate_statistics(output=False)
    # engine.calculate_statistics()  # 计算一些统计指标

    # 区间推进统计
    chart_path = "/usr/local/nginx/html/"
    def_stat, result_def_stat = engine.calculate_statistics_all(start,
                                                                end,
                                                                chart_path=chart_path)

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
             # ["结束时间推进统计", result_end_time_stat],
             # ["区间时间推进统计", result_move_time_stat],
              ["默认统计", result_def_stat],
              ["参数", parameters]]

    # title_statistics = f"[{def_stat['总收益率']}_{def_stat['总成交次数']}_{def_stat['百分比最大回撤']}_{def_stat['胜率']}_{def_stat['盈亏比']}]"
    title_statistics = ""
    file_name = f"交易记录-{symbol}-{interval}-[{str_parameter}].xlsx"

    save_file = "result/" + file_name
    if os.path.exists(save_file):
        os.remove(save_file)
    report_excel_xlsx(save_file, report)

    for ent in result_def_stat:
        print(f"{ent[0]}：\t{ent[1]}")

    print(file_name)
    print("overview:", data.symbol, data.interval, start, end)


if __name__ == '__main__':
    currency = ['btc']
    for ent in currency:
        run(ent)
