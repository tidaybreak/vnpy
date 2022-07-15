
import json
import os
from vnpy.trader.object import Interval
from strategies.sar_strategy import SarStrategy
from quant.vnpy.trader.engineEx import MainEngineEx

from quant.units import get_symbol_overview, report_excel_xlsx
from quant.vnpy.app.cta_strategy.backtestingEx import BacktestingEngineEx
from datetime import date, datetime

from vnpy.app.cta_strategy.backtesting import (
    OptimizationSetting
)
from vnpy.app.cta_strategy.base import (
    BacktestingMode
)


def generate_setting(rate, parameters):
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


def format_json_str(s):
    return s.replace('\'', '"').replace(": True", ": true").replace(": False", ": false")


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        else:
            return str(obj)
            #return json.JSONEncoder.default(self, obj)


if __name__ == '__main__':
    engine = BacktestingEngineEx()
    currency = "btc"
    symbol = currency + "usdt"
    interval = Interval.DAILY
    data = get_symbol_overview(symbol, interval)

    class_name = "SarStrategy"
    rate = 1.0 / 1000
    capital = 1000
    slippage = 0.0
    size = 1.0
    pricetick = 0.1

    training_parameters = dict()
    training_parameters["btc"] = {
        "seg_size": 30,
        "sar_acceleration": 0.02,
        "sar_maximum": 0.2,
        "rsi_length": 14,
        "position_ratio": 1 - rate,
        "slippage": 0.001,
        "open_eq_sar_step": [1, 1, 10],
        "open_lt_rsi": 0,  # [20, 1, 90]
        "open_gt_ema": [0, 1, 20],  # [0, 1, 30]
        "stop_eq_sar_step": 0,  # [1, 1, 10]
        "stop_gt_rsi": 0,
        "stop_lt_ema": [0, 1, 20],
        "stop_gt_move": [0.05, 0.02, 0.2],  # [0.01, 0.01, 0.3]
        "stop_win_per": 0.0,
        "stop_loss_per": 0.0
    }
    training_parameters["fil"] = {
        "seg_size": 30,
        "sar_acceleration": 0.02,
        "sar_maximum": 0.2,
        "rsi_length": 14,
        "position_ratio": 1 - rate,
        "slippage": 0.001,
        "open_eq_sar_step": 2,
        "open_lt_rsi": [20, 1, 90],  # [20, 1, 90]
        "open_gt_ema": [0, 1, 30],  # [0, 1, 30]
        "stop_eq_sar_step": 0,  # [1, 1, 10]
        "stop_gt_rsi": 0,
        "stop_gt_move": 0.1199,  # [0.01, 0.01, 0.3]
        "stop_win_per": 0.0,
        "stop_loss_per": 0.0
    }

    optimization_setting, use_ga = generate_setting(rate, training_parameters[currency])

    if use_ga:
        print("开始遗传算法参数优化")
    else:
        print("开始多进程参数优化")

    result_values = None

    engine.clear_data()

    if interval == Interval.TICK:
        mode = BacktestingMode.TICK
    else:
        mode = BacktestingMode.BAR

    engine.set_parameters(
        vt_symbol=symbol.lower() + ".BINANCE",
        interval=interval,
        start=data.start,
        end=data.end,
        rate=rate,
        slippage=slippage,
        size=size,
        pricetick=pricetick,
        capital=capital,
        inverse=False,
        mode=mode
    )

    engine.add_strategy(SarStrategy, {})
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

    print(json.dumps(training_parameters[currency], cls=ComplexEncoder, sort_keys=False, indent=4, separators=(',', ':')))

    def calculate_result(result):
        report = [['时间', '收益']]
        setting_head = []
        for move_time, values in result.items():
            setting = []
            for k, v in values[0][0].items():
                setting.append(v)
                if len(setting_head) != len(values[0][0]):
                    setting_head.append(k)
            target_value = values[0][1]
            statistics = values[0][2]
            report.append([move_time, target_value] + setting + statistics)

        statistics_head = []
        statistics_dict = engine.calculate_result_new()
        for k, v in statistics_dict.items():
            statistics_head.append([k, "00FFFF"])
        report[0] += setting_head + statistics_head
        return report

    report1 = calculate_result(result_values["result_move_time_stat"])
    report2 = calculate_result(result_values["result_end_time_stat"])

    file_name = f"参数优化-{symbol}-{interval}.xlsx"
    save_file = "result/" + file_name
    if os.path.exists(save_file):
        os.remove(save_file)
    report_excel_xlsx(save_file, [["区间时间推进统计", report1], ["结束时间推进统计", report2]])
