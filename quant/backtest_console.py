from quant.vnpy.app.cta_strategy.backtestingEx import BacktestingEngineEx
from vnpy.trader.object import Interval
from quant.units import report_excel_xlsx
from vnpy.trader.database import get_database
from strategies.strategy1 import Strategy1
from datetime import datetime
import os
import pytz
import sys
import json


def run():
    symbol = "btcusdt"
    eng_conf = {
        "vt_symbol": "btcusdt.BINANCE",
        "interval": "d",
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
        "class_name": "Strategy1",
        "sar_acceleration": 0.02,
        "sar_maximum": 0.2,
        "rsi_length": 14,
        "position_ratio": 100,
        "open_eq_sar_step": 0,
        "open_lt_rsi": 0,
        "open_gt_ema": 75,
        "stop_eq_sar_step": 0,
        "stop_gt_rsi": 0,
        "stop_lt_ema": 130,
        "stop_gt_move": 0,
        "stop_win_per": 0,
        "stop_loss_per": 0
    }
    setting_conf2 = {
        "class_name": "Strategy1",
        "sar_acceleration": 0.02,
        "sar_maximum": 0.2,
        "rsi_length": 14,
        "position_ratio": 100,
        "open_eq_sar_step": 0,
        "open_lt_rsi": 0,
        "open_gt_ema": 180,
        "stop_eq_sar_step": 0,
        "stop_gt_rsi": 0,
        "stop_lt_ema": 180,
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
    # chart_path = "./result/"
    chart_path = os.environ.get('CHART_PATH', "./result/")
    def_stat, result_def_stat = engine.calculate_statistics_all(start,
                                                                end,
                                                                chart_path=chart_path)

    report = [["交易信息", engine.strategy.report_trade],
              ["信号", engine.strategy.report_signal],
              # ["结束时间推进统计", result_end_time_stat],
              # ["区间时间推进统计", result_move_time_stat],
              ["默认统计", result_def_stat],
              ["eng_conf", eng_conf, False],
              ["setting_conf", setting_conf, False]]

    # title_statistics = f"[{def_stat['总收益率']}_{def_stat['总成交次数']}_{def_stat['百分比最大回撤']}_{def_stat['胜率']}_{def_stat[
    # '盈亏比']}]"
    title_statistics = ""
    start = start.strftime("%Y%m%d_%H%M%S")
    end = end.strftime("%Y%m%d_%H%M%S")
    file_name = f"backtest-{symbol}-{interval}-{start}-{end}.xlsx"

    save_file = "result/" + file_name
    if os.path.exists(save_file):
        os.remove(save_file)
    report_excel_xlsx(save_file, report)

    print(json.dumps(setting_conf, indent=2))
    for ent in result_def_stat:
        print(f"{ent[0]}：\t{ent[1]}")
    print(os.environ.get('CHART_PATH', "./result/"))
    print(save_file)


if __name__ == '__main__':
    run()
