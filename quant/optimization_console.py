import json
import os
import sys
import pytz
import json
from strategies import *
from vnpy.trader.object import Interval
from strategies.sar_strategy import SarStrategy
#from quant.vnpy.trader.engineEx import MainEngineEx
from quant.units import get_symbol_overview, report_excel_xlsx
from quant.vnpy.app.cta_strategy.backtestingEx import BacktestingEngineEx
from datetime import date, datetime

from vnpy_ctastrategy.backtesting import (
    OptimizationSetting
)
from vnpy_ctastrategy.base import (
    BacktestingMode
)
from vnpy.trader.utility import load_json


def generate_setting(parameters):
    """"""
    optimization_setting = OptimizationSetting()
    optimization_setting.set_target('total_return')

    for name, d in parameters.items():
        start_value = d
        step_value = 1
        end_value = d
        if isinstance(d, list) and len(d) == 3:
            start_value = d[0]
            step_value = d[1]
            end_value = d[2]

        if start_value == end_value:
            optimization_setting.add_parameter(name, start_value)
        else:
            optimization_setting.add_parameter(
                name,
                start_value,
                end_value,
                step_value
            )
    optimization_setting.add_parameter("no_log", True)
    return optimization_setting, False


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        else:
            return str(obj)
            # return json.JSONEncoder.default(self, obj)


if __name__ == '__main__':
    config = dict()
    if len(sys.argv) > 1:
        title = sys.argv[1]
        filename: str = f"optimization/{title}.json"
        if not os.path.exists(f".vntrader/optimization/{title}.json"):
            print("配置文件不存在：" + filename)
            sys.exit(0)
        print("使用配置文件:", filename)
        config = load_json(filename)
        symbol = config["symbol"]
        eng_conf = config["engine"]
        setting_conf = config["setting"]
    else:
        print("使用默认配置")
        title = ""
        symbol = "btcusdt"
        eng_conf = {
            "vt_symbol": "btcusdt.BINANCE",
            "interval": "1h",
            "start": "2019-9-10 00:00:00",
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
            "open_lt_rsi": 0,  # [20, 1, 90]
            "open_gt_ema": [100, 1, 103],  # [0, 1, 30]
            "stop_eq_sar_step": 0,  # [1, 1, 10]
            "stop_gt_rsi": 0,
            "stop_lt_ema": 100,
            "stop_gt_move": 0,  # [0.01, 0.01, 0.3]
            "stop_win_per": 0,
            "stop_loss_per": 0
        }

    engine = BacktestingEngineEx()
    interval = Interval(eng_conf["interval"])
    data = get_symbol_overview(symbol, interval)

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

    optimization_setting, use_ga = generate_setting(setting_conf)

    if use_ga:
        print("开始遗传算法参数优化")
    else:
        print("开始多进程参数优化")

    result_values = None
    engine.clear_data()

    # if interval == Interval.TICK:
    #    mode = BacktestingMode.TICK
    # else:
    # mode = BacktestingMode.BAR

    engine.set_parameters(
        vt_symbol=eng_conf["vt_symbol"],
        interval=Interval(eng_conf["interval"]),
        start=start,
        end=end,
        rate=eng_conf["rate"],
        slippage=eng_conf["slippage"],
        size=eng_conf["size"],
        pricetick=eng_conf["pricetick"],
        capital=eng_conf["capital"],
        mode=BacktestingMode(eng_conf["mode"])
    )

    engine.add_strategy(getattr(sys.modules[__name__], setting_conf["class_name"]), {})
    # engine.cpu_count = 2
    if use_ga:
        result_values = engine.run_ga_optimization(
            optimization_setting,
            output=False
        )
    else:
        result_values = engine.run_optimization(
            optimization_setting,
            output=False
        )

    print(json.dumps(setting_conf, cls=ComplexEncoder, sort_keys=False, indent=4, separators=(',', ':')))

    report = [['优化值']]
    setting_head = []
    for k, v in result_values[0][0].items():
        setting_head.append(k)

    for ent in result_values:
        settings = []
        for k, v in ent[0].items():
            settings.append(v)

        statistics = ent[1]
        print(format(ent[2], '.2f'), settings, statistics[-8:])
        report.append([ent[2]] + settings + statistics)

    statistics_head = []
    statistics_dict = engine.calculate_statistics_plus()
    for k, v in statistics_dict.items():
        statistics_head.append([k, "00FFFF"])
    report[0] += setting_head + statistics_head

    # report2 = calculate_result(result_values["result_end_time_stat"])

    start = start.strftime("%Y%m%d_%H%M%S")
    end = end.strftime("%Y%m%d_%H%M%S")

    file_name = f"optimization-{title}-{symbol}-{interval}-{result_values[0][2]}-{start}-{end}.xlsx"
    save_file = "result/" + file_name
    if os.path.exists(save_file):
        os.remove(save_file)
    report_excel_xlsx(save_file, [["result", report], ["eng_conf", eng_conf, False], ["setting_conf", setting_conf, False]])
    print(save_file)
    # report_excel_xlsx(save_file, [["区间时间推进统计", report1], ["结束时间推进统计", report2]])
