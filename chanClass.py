# 导入函数库
import math
from copy import copy
import pandas as pd
import numpy as np
import talib as tl
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, Optional
from typing import Optional, List, Dict, Any



class Interval(Enum):
    MINUTE = "1m"
    MINUTE5 = "5m"
    MINUTE15 = "15m"
    MINUTE30 = "30m"
    HOUR = "1h"
    HOUR4 = "4h"
    DAILY = "1d"

FREQS = ['日线', '240分钟', '60分钟', '30分钟', '15分钟', '5分钟', '1分钟']

FREQS_WINDOW = {
    '日线': [240, Interval.MINUTE, Interval.DAILY],
    '240分钟': [240, Interval.MINUTE, Interval.HOUR4],
    '60分钟': [60, Interval.MINUTE, Interval.HOUR],
    '30分钟': [30, Interval.MINUTE, Interval.MINUTE30],
    '15分钟': [15, Interval.MINUTE, Interval.MINUTE15],
    '5分钟': [5, Interval.MINUTE, Interval.MINUTE5],
    '1分钟': [1, Interval.MINUTE, Interval.MINUTE],
}

INTERVAL_FREQ = {
    '1d': '日线',
    '4h': '240分钟',
    '1h': '60分钟',
    '30m': '30分钟',
    '15m': '15分钟',
    '5m': '5分钟',
    '1m': '1分钟'
}



class Exchange(Enum):
    XSHE = "XSHE"
    XSHG = "XSHG"


# 日志类（模拟原项目中的 ChanLog，需根据实际需求调整）
import logging
chan_logger = logging.getLogger(__name__)

class ChanLog:
    @staticmethod
    def log(freq, symbol, message):
        # 关闭日志输出（调试完成后）
        print(f"[{freq}][{symbol}] {message}")
        return None

        
class TickData:
    symbol: str
    exchange: Exchange
    datetime: datetime

    name: str = ""
    volume: float = 0
    open_interest: float = 0
    last_price: float = 0
    last_volume: float = 0
    limit_up: float = 0
    limit_down: float = 0

    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    pre_close: float = 0

    bid_price_1: float = 0
    bid_price_2: float = 0
    bid_price_3: float = 0
    bid_price_4: float = 0
    bid_price_5: float = 0

    ask_price_1: float = 0
    ask_price_2: float = 0
    ask_price_3: float = 0
    ask_price_4: float = 0
    ask_price_5: float = 0

    bid_volume_1: float = 0
    bid_volume_2: float = 0
    bid_volume_3: float = 0
    bid_volume_4: float = 0
    bid_volume_5: float = 0

    ask_volume_1: float = 0
    ask_volume_2: float = 0
    ask_volume_3: float = 0
    ask_volume_4: float = 0
    ask_volume_5: float = 0

    def __post_init__(self):
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

class BarData:
    datetime: datetime
    symbol: str
    exchange: Exchange = None
    interval: Interval = None
    volume: float = 0
    open_interest: float = 0
    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    close_price: float = 0

    def __init__(self, datetime, symbol, exchange, freq, open_price, high_price, low_price, close_price, volume):
        self.datetime = datetime
        self.symbol = symbol
        self.exchange =  exchange
        self.interval = Interval(freq)
        self.open_interest = 0
        self.open_price = open_price
        self.high_price = high_price
        self.low_price = low_price
        self.close_price = close_price
        self.volume = volume
        self.vt_symbol = symbol
        # self.vt_symbol = f"{self.symbol}.{self.exchange.value}"    

class BarGenerator:
    """
    Target:
    1. generating 1 minute bar data from tick data
    2. generateing x minute bar/x hour bar data from 1 minute data

    Notice:
    1. for x minute bar, x must be able to divide 60: 2, 3, 5, 6, 10, 15, 20, 30
    2. for x hour bar, x can be any number
    """

    def __init__(
            self,
            on_bar: Callable,
            window: int = 0,
            on_window_bar: Callable = None,
            interval: Interval = Interval.MINUTE,
            target: Interval = Interval.MINUTE
    ):
        self.bar: BarData = None
        self.on_bar: Callable = on_bar

        self.interval: Interval = interval
        self.interval_count: int = 0

        self.window: int = window
        self.window_bar: BarData = None
        self.on_window_bar: Callable = on_window_bar

        self.last_tick: TickData = None
        self.last_bar: BarData = None

        self.target = target

    def update_tick(self, tick: TickData) -> None:
        """
        Update new tick data into generator.
        """
        new_minute = False

        # Filter tick data with 0 last price
        if not tick.last_price:
            return

        # Filter tick data with less intraday trading volume (i.e. older timestamp)
        # if self.last_tick and tick.volume and tick.volume < self.last_tick.volume:
        #     return
        # 过滤掉收到的过去的tick
        if self.last_tick and tick.datetime < self.last_tick.datetime:
            return

        if not self.bar:
            new_minute = True
        elif self.bar.datetime.minute != tick.datetime.minute:
            self.bar.datetime = self.bar.datetime.replace(
                second=0, microsecond=0
            )
            self.on_bar(self.bar)

            new_minute = True

        if new_minute:
            self.bar = BarData(symbol=tick.symbol,
                exchange=tick.exchange,
                interval=Interval.MINUTE,
                datetime=tick.datetime,
                open_price=tick.last_price,
                high_price=tick.last_price,
                low_price=tick.last_price,
                close_price=tick.last_price,
                open_interest=tick.open_interest
            )
        else:
            self.bar.high_price = max(self.bar.high_price, tick.last_price)
            self.bar.low_price = min(self.bar.low_price, tick.last_price)
            self.bar.close_price = tick.last_price
            self.bar.open_interest = tick.open_interest
            self.bar.datetime = tick.datetime

        if self.last_tick:
            volume_change = tick.volume - self.last_tick.volume
            self.bar.volume += max(volume_change, 0)

        self.last_tick = tick

    def update_bar(self, bar: BarData) -> None:
        """
        Update 1 minute bar into generator
        """
        # If not inited, creaate window bar object
        if not self.window_bar:
            # Generate timestamp for bar data
            if self.interval == Interval.MINUTE:
                dt = bar.datetime.replace(second=0, microsecond=0)
            else:
                dt = bar.datetime.replace(minute=0, second=0, microsecond=0)

            self.window_bar = BarData(
                datetime=dt,
                symbol=bar.symbol,
                freq=bar.interval,
                exchange=bar.exchange,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price,
                close_price=bar.close_price,
                volume=bar.volume,
            )

        # Otherwise, update high/low price into window bar
        else:
            dt = bar.datetime.replace(second=0, microsecond=0)
            if not self.interval == Interval.MINUTE:
                dt = bar.datetime.replace(minute=0, second=0, microsecond=0)
            self.window_bar.datetime = dt
            self.window_bar.high_price = max(
                self.window_bar.high_price, bar.high_price)
            self.window_bar.low_price = min(
                self.window_bar.low_price, bar.low_price)

        # Update close price/volume into window bar
        self.window_bar.close_price = bar.close_price
        self.window_bar.volume += int(bar.volume)
        self.window_bar.open_interest = bar.open_interest
        self.window_bar.interval = self.target
        # Check if window bar completed
        finished = False

        if self.interval == Interval.MINUTE:
            # x-minute bar
            self.interval_count += 1

            if not self.interval_count % self.window:
                finished = True
                self.interval_count = 0
        elif self.interval == Interval.HOUR:
            if self.last_bar and bar.datetime.hour != self.last_bar.datetime.hour:
                # 1-hour bar
                if self.window == 1:
                    finished = True
                # x-hour bar
                else:
                    self.interval_count += 1

                    if not self.interval_count % self.window:
                        finished = True
                        self.interval_count = 0

        if finished:
            #print(self.window_bar)
            self.on_window_bar(self.window_bar)
            self.window_bar = None

        # Cache last bar object
        self.last_bar = bar

    def generate(self) -> Optional[BarData]:
        """
        Generate the bar data and call callback immediately.
        """
        bar = self.bar

        if self.bar:
            bar.datetime = bar.datetime.replace(second=0, microsecond=0)
            self.on_bar(bar)

        self.bar = None
        return bar

class Chan_Class:

    def __init__(self, freq, symbol, sell, buy, include=True, include_feature=False, build_line_pivot=False, qjt=True,
                 gz=False, buy1=100, buy2=200, buy3=200, sell1=100, sell2=200, sell3=200):

        self.freq = freq
        self.symbol = symbol
        self.prev = None
        self.next = None
        self.k_list = []
        self.chan_k_list = []
        self.fx_list = []
        self.stroke_list = []
        self.stroke_index_in_k = {}
        # P0: 笔级别数据存储 - 增强版笔数据结构
        self.pens = []  # 完整笔数据: [{'index': int, 'start_fx': fx, 'end_fx': fx, 'direction': str,
                   #                    'open_price': float, 'high_price': float, 'low_price': float,
                   #                    'close_price': float, 'volume': float, 'start_k_index': int, 'end_k_index': int}]
        self.pen_macd = {}  # 笔级别MACD: {pen_index: {'dif': float, 'dea': float, 'macd': float, 'area': float}}
        self.line_list = []
        self.line_index = {}
        self.line_index_in_k = {}
        self.line_feature = []
        self.s_feature = []
        self.x_feature = []

        self.pivot_list = []
        self.trend_list = []
        self.buy_list = []
        self.sell_list = []
        self.macd = {}
        self.buy = buy
        self.sell = sell
        self.buy1 = buy1
        self.buy2 = buy2
        self.buy3 = buy3
        self.sell1 = sell1
        self.sell2 = sell2
        self.sell3 = sell3
        # 动力减弱最小指标
        self.dynamic_reduce = 0
        
        # 笔生成方法，new, old
        # K线是否进行包含处理
        self.include = include
        # 中枢生成方法，stroke, line
        # 使用笔还是线段作为中枢的构成, true使用线段
        self.build_line_pivot = build_line_pivot
        # 线段生成方法
        # 是否进行K线包含处理
        self.include_feature = include_feature
        # 是否使用区间套
        self.qjt = qjt
        # 是否使用共振
        # 采用买卖点共振组合方法，1分钟一类买卖点+5分钟二类买卖点或三类买卖点，都属于共振
        self.gz = gz
        # 计数
        self.gz_delay_k_num = 0
        # 最大
        self.gz_delay_k_max = 12
        # 潜在bs
        self.gz_tmp_bs = None
        # 高级别bs
        self.gz_prev_last_bs = None
        # 已执行的信号
        self.executed_signals = set()
        
        # 背驰判断参数
        self.divergence_ratio_threshold = 0.4  # MACD面积比例阈值（离开段/进入段 < 0.4 算背驰，即缩小60%）

    def set_prev(self, chan):
        self.prev = chan

    def set_next(self, chan):
        self.next = chan

    def on_bar(self, bar: BarData):
        self.k_list.append(bar)
        if self.gz and self.gz_tmp_bs:
            self.gz_delay_k_num += 1
            self.on_gz()
        if self.include:
            self.on_process_k_include(bar)
        else:
            self.on_process_k_no_include(bar)

    def on_process_k_include(self, bar: BarData):
        """K线包含处理（缠论第62课原文）

        缠论原文定义：
        - 包含关系：一根K线高低点完全在另一根范围内
        - 合并规则：**向前看趋势方向**
          - 上升趋势：取高点max、低点max
          - 下降趋势：取高点min、低点min
        - 趋势方向判断：用**前两根K线**（pre_bar vs last_bar）的high关系
          - pre_bar.high < last_bar.high → 上升趋势
          - pre_bar.high > last_bar.high → 下降趋势
        - 只处理 high/low，不处理 open/close
        - 合并后K线的 open 取第一根K线的open，close 取最后一根K线的close
        """
        if len(self.chan_k_list) < 2:
            self.chan_k_list.append(bar)
        else:
            pre_bar = self.chan_k_list[-2]
            last_bar = self.chan_k_list[-1]
            if (last_bar.high_price >= bar.high_price and last_bar.low_price <= bar.low_price) or (
                    last_bar.high_price <= bar.high_price and last_bar.low_price >= bar.low_price):
                # 缠论原文：趋势方向由**前两根K线**的高低关系决定
                if pre_bar.high_price < last_bar.high_price:
                    # 上升趋势：取高点max、低点max
                    new_bar = copy(bar)
                    new_bar.high_price = max(last_bar.high_price, new_bar.high_price)
                    new_bar.low_price = max(last_bar.low_price, new_bar.low_price)
                else:
                    # 下降趋势：取高点min、低点min
                    new_bar = copy(bar)
                    new_bar.high_price = min(last_bar.high_price, new_bar.high_price)
                    new_bar.low_price = min(last_bar.low_price, new_bar.low_price)

                # 缠论原文：只处理high/low，open/close保持原始值
                new_bar.open_price = last_bar.open_price
                new_bar.close_price = bar.close_price

                self.chan_k_list[-1] = new_bar
                ChanLog.log(self.freq, self.symbol, "combine k line: " + str(new_bar.datetime))
            else:
                self.chan_k_list.append(bar)
            self.on_process_fx(self.chan_k_list)

    def on_process_k_no_include(self, bar: BarData):
        """不用合并k线"""
        self.chan_k_list.append(bar)
        self.on_process_fx(self.chan_k_list)

    def on_process_fx(self, data):
        """分型判断（缠论第62课原文定义）

        缠论原文定义：
        - 顶分型：中间K线高点三者最高，低点也是三者最高
        - 底分型：中间K线低点三者最低，高点也是三者最低

        注：缠师原文明确要求"高低点都要满足"，这是区分真假分型的关键

        v2修复：添加去重检查，避免同一K线被重复识别为分型
        """
        if len(data) > 2:
            flag = False
            fx_datetime = data[-2].datetime
            fx_k_index = len(data) - 2

            # 去重检查：检查最后两个分型是否与当前检测位置相同
            # 避免K线合并后重复触发
            if len(self.fx_list) >= 2:
                last_two_fx = self.fx_list[-2:]
                for fx in last_two_fx:
                    if fx[2] == fx_datetime and fx[4] == fx_k_index:
                        # 已经识别过这个位置的分型，跳过
                        return

            # 顶分型：中间K线高点最高、低点也最高（缠论原文定义）
            if (data[-2].high_price >= data[-1].high_price and
                data[-2].high_price >= data[-3].high_price and
                data[-2].low_price >= data[-1].low_price and
                data[-2].low_price >= data[-3].low_price):
                self.fx_list.append([data[-2].high_price, data[-2].low_price, data[-2].datetime, 'up', fx_k_index])
                flag = True

            # 底分型：中间K线低点最低、高点也最低（缠论原文定义）
            if (data[-2].low_price <= data[-1].low_price and
                data[-2].low_price <= data[-3].low_price and
                data[-2].high_price <= data[-1].high_price and
                data[-2].high_price <= data[-3].high_price):
                self.fx_list.append([data[-2].high_price, data[-2].low_price, data[-2].datetime, 'down', fx_k_index])
                flag = True

            if flag:
                self.on_stroke(self.fx_list[-1])
                ChanLog.log(self.freq, self.symbol, "fx_list: ")
                ChanLog.log(self.freq, self.symbol, self.fx_list[-1])

    def build_pen_data(self, start_fx, end_fx, start_index, end_index):
        """
        P0: 构建完整的笔数据
        Args:
            start_fx: 起始分型 [high, low, datetime, direction, k_index]
            end_fx: 结束分型 [high, low, datetime, direction, k_index]
            start_index: 笔在stroke_list中的索引
            end_index: 笔在stroke_list中的索引（用于笔延伸时更新）
        Returns:
            笔数据字典
        """
        # 确定起止K线索引
        k_start = min(start_fx[4], end_fx[4])
        k_end = max(start_fx[4], end_fx[4])

        # 提取笔涵盖的K线数据
        k_data = self.k_list[k_start:k_end+1]

        if not k_data:
            return None

        # 计算笔的OHLCV
        open_price = start_fx[1] if start_fx[3] == 'down' else start_fx[0]  # 底分型low或顶分型high
        close_price = end_fx[1] if end_fx[3] == 'down' else end_fx[0]
        high_price = max(bar.high_price for bar in k_data)
        low_price = min(bar.low_price for bar in k_data)
        volume = sum(bar.volume for bar in k_data)

        # 确定笔的方向
        # 从底分型到顶分型 = 向上笔
        # 从顶分型到底分型 = 向下笔
        if start_fx[3] == 'down' and end_fx[3] == 'up':
            direction = 'up'
        elif start_fx[3] == 'up' and end_fx[3] == 'down':
            direction = 'down'
        else:
            # 异常情况，根据价格变化判断
            if end_fx[1] > start_fx[1]:  # 更高
                direction = 'up'
            else:
                direction = 'down'

        return {
            'index': end_index,
            'start_fx': start_fx,
            'end_fx': end_fx,
            'direction': direction,
            'open_price': open_price,
            'high_price': high_price,
            'low_price': low_price,
            'close_price': close_price,
            'volume': volume,
            'start_k_index': k_start,
            'end_k_index': k_end
        }

    def _count_independent_klines(self, start_idx, end_idx):
        """计算两分型之间的独立K线数（缠论第62课原文）

        缠论原文定义：
        - 笔要求顶分型和底分型之间至少有1根独立K线
        - 独立K线 = 不属于任一分型定义范围的K线

        关键理解：
        - 分型由3根K线形成：左边(k_idx-1)、中间(k_idx)、右边(k_idx+1)
        - 分型的定义范围 = 这3根K线全部
        - 两分型的独立K线 = 两分型定义范围之外的中间K线

        计算公式：
        - 分型A右边最后一根位置 = start_idx + 1
        - 分型B左边第一根位置 = end_idx - 1
        - 独立K线必须 > (start_idx + 1) 且 < (end_idx - 1)
        - 即独立K线位置从 (start_idx + 2) 到 (end_idx - 2)
        - 独立K线数 = (end_idx - 2) - (start_idx + 2) + 1 = end_idx - start_idx - 3

        Args:
            start_idx: 起始分型的中间K线索引
            end_idx: 结束分型的中间K线索引

        Returns:
            int: 独立K线数量
            - >=1: 可以形成笔
            - 0: 分型共用K线或距离太近，不能形成笔
        """
        if start_idx >= end_idx:
            return 0

        # 两分型定义范围是否有重叠？
        # 分型A右边 = start_idx + 1
        # 分型B左边 = end_idx - 1
        # 如果 start_idx + 1 >= end_idx - 1，说明有重叠或共用
        # 即 end_idx - start_idx <= 2，无独立K线

        if end_idx - start_idx <= 2:
            return 0

        # 独立K线数 = end_idx - start_idx - 3
        independent_count = end_idx - start_idx - 3
        return max(independent_count, 0)

    def on_stroke(self, data):
        """生成笔（缠论第62课原文完整版）

        缠论原文定义：
        1. 向上笔：底分型→顶分型，中间至少1根独立K线
           - 原文条件：顶分型高点 > 底分型低点
        2. 向下笔：顶分型→底分型，中间至少1根独立K线
           - 原文条件：底分型低点 < 顶分型高点
        3. 笔延伸：同向分型出现时，顶比前顶高、底比前底低
           - 延伸后需验证：延伸后的笔仍满足条件
        4. 笔修正：实时检查前一笔端点是否需要修正
        """
        if len(self.stroke_list) < 1:
            # 第一个分型，作为潜在笔起点（不立即记录为完整笔）
            self.stroke_list.append(data)
            ChanLog.log(self.freq, self.symbol, f'初始分型: {data[3]}')
        else:
            last_fx = self.stroke_list[-1]
            cur_fx = data
            pivot_flag = False

            # 计算两分型之间的独立K线数
            k_distance = self._count_independent_klines(last_fx[4], cur_fx[4])

            # 同向分型：笔延伸
            if last_fx[3] == cur_fx[3]:
                # 延伸条件：新分型比原分型更极端
                if (last_fx[3] == 'down' and cur_fx[1] < last_fx[1]) or (
                        last_fx[3] == 'up' and cur_fx[0] > last_fx[0]):
                    # 笔延伸后验证：整笔仍需满足条件
                    if len(self.stroke_list) >= 2:
                        # 获取笔的起始分型
                        start_fx = self.stroke_list[-2]
                        # 计算起始分型到延伸后分型的独立K线数
                        # 缠论原文：验证的是整笔（起始→延伸后终点）
                        extended_k_distance = self._count_independent_klines(start_fx[4], cur_fx[4])
                        # 验证延伸后的完整笔
                        if self._validate_extended_pen(start_fx, cur_fx, extended_k_distance):
                            self.stroke_list[-1] = cur_fx
                            if len(self.pens) > 0:
                                pen_index = len(self.stroke_list) - 1
                                pen_data = self.build_pen_data(start_fx, cur_fx, pen_index, pen_index)
                                if pen_data:
                                    self.pens[-1] = pen_data
                            pivot_flag = True
                    else:
                        # 只有1个分型时，直接更新
                        self.stroke_list[-1] = cur_fx

            # 反向分型：新笔生成
            else:
                if k_distance >= 1:
                    pen_valid = False
                    if cur_fx[3] == 'up':  # 形成向上笔（底→顶）
                        if cur_fx[0] > last_fx[1]:
                            pen_valid = True
                    elif cur_fx[3] == 'down':  # 形成向下笔（顶→底）
                        if cur_fx[1] < last_fx[0]:
                            pen_valid = True

                    if pen_valid:
                        self.stroke_list.append(cur_fx)
                        # 只有形成完整笔才记录到pens
                        if len(self.stroke_list) >= 2:
                            pen_data = self.build_pen_data(self.stroke_list[-2], cur_fx, len(self.stroke_list)-1, len(self.stroke_list)-1)
                            if pen_data:
                                self.pens.append(pen_data)
                        ChanLog.log(self.freq, self.symbol, f'新笔确认: {last_fx[3]}→{cur_fx[3]}')
                        pivot_flag = True

            # 笔修正
            if pivot_flag and len(self.stroke_list) > 2:
                self._adjust_stroke_endpoint_realtime()

            # MACD计算
            if not self.build_line_pivot:
                if len(self.stroke_list) > 1:
                    cur_fx = self.stroke_list[-1]
                    last_fx = self.stroke_list[-2]
                    self.macd[cur_fx[2]] = self.cal_macd(last_fx[4], cur_fx[4])

            # 线段生成
            self.on_line(self.stroke_list)

            # 笔级别中枢
            if not self.build_line_pivot and pivot_flag:
                self.on_pivot(self.stroke_list, None)

    def _validate_extended_pen(self, start_fx, end_fx, k_distance):
        """验证笔延伸后的完整笔是否满足条件（缠论第62课）

        延伸后需要验证：
        1. 独立K线条件：两分型之间至少1根独立K线
        2. 价格关系：向上笔顶>底，向下笔底<顶

        Args:
            start_fx: 笔的起始分型
            end_fx: 延伸后的结束分型
            k_distance: 独立K线数

        Returns:
            bool: 是否有效
        """
        if k_distance < 1:
            return False

        # 价格关系验证
        if start_fx[3] == 'down' and end_fx[3] == 'up':
            # 向上笔：顶分型high > 底分型low
            return end_fx[0] > start_fx[1]
        elif start_fx[3] == 'up' and end_fx[3] == 'down':
            # 向下笔：底分型low < 顶分型high
            return end_fx[1] < start_fx[0]

        return False

    def _adjust_stroke_endpoint_realtime(self):
        """实时笔端点修正（缠论原文第62课）

        缠论原文要求：新笔确认后，检查前一笔（倒数第二笔）的端点
        是否存在更极端的分型可以替代。

        修正规则：
        - 向下笔后检查：倒数第二笔（向上笔）是否有更高的顶分型可以替代
        - 向上笔后检查：倒数第二笔（向下笔）是否有更低的底分型可以替代
        - 修正后必须满足：修正点与新笔端点之间至少有1根独立K线
        - 如果修正导致笔失效（修正后价格关系不满足），回溯处理
        """
        if len(self.stroke_list) < 3:
            return

        cur_fx = self.stroke_list[-1]
        target_fx = self.stroke_list[-2]
        stroke_change = None

        # 在fx_list中搜索更极端的分型
        target_dt = target_fx[2]
        target_type = target_fx[3]

        for i in range(len(self.fx_list) - 1, -1, -1):
            fx = self.fx_list[i]
            # 找到target_fx在fx_list中的位置
            if fx[2] == target_dt and fx[3] == target_type:
                # 从该位置之后正向搜索
                for j in range(i + 1, len(self.fx_list)):
                    candidate = self.fx_list[j]
                    k_dist = self._count_independent_klines(candidate[4], cur_fx[4])

                    if cur_fx[3] == 'down':
                        # 当前向下笔：检查向上笔是否有更高的顶分型
                        if candidate[3] == 'up' and candidate[0] > target_fx[0]:
                            if k_dist >= 1:  # 修正后至少1根独立K线
                                stroke_change = candidate
                    else:
                        # 当前向上笔：检查向下笔是否有更低的底分型
                        if candidate[3] == 'down' and candidate[1] < target_fx[1]:
                            if k_dist >= 1:
                                stroke_change = candidate
                break

        if stroke_change and stroke_change != target_fx:
            # 修正后验证：修正点与新笔端点的价格关系
            if cur_fx[3] == 'down':
                # 修正后的向上笔：底分型→修正后的顶分型
                prev_fx = self.stroke_list[-3]
                if prev_fx[3] == 'down' and stroke_change[0] > prev_fx[1]:
                    self.stroke_list[-2] = stroke_change
                    ChanLog.log(self.freq, self.symbol, f'笔修正: {target_fx} -> {stroke_change}')
                    # 更新笔数据
                    if len(self.pens) >= 2:
                        pen_data = self.build_pen_data(self.stroke_list[-3], stroke_change, len(self.stroke_list)-2, len(self.stroke_list)-2)
                        if pen_data:
                            self.pens[-2] = pen_data
            else:
                # 修正后的向下笔：顶分型→修正后的底分型
                prev_fx = self.stroke_list[-3]
                if prev_fx[3] == 'up' and stroke_change[1] < prev_fx[0]:
                    self.stroke_list[-2] = stroke_change
                    ChanLog.log(self.freq, self.symbol, f'笔修正: {target_fx} -> {stroke_change}')
                    if len(self.pens) >= 2:
                        pen_data = self.build_pen_data(self.stroke_list[-3], stroke_change, len(self.stroke_list)-2, len(self.stroke_list)-2)
                        if pen_data:
                            self.pens[-2] = pen_data

    def on_line(self, data):
        """线段生成（缠论第65-67课原文完整版）

        缠论原文定义：
        1. 特征序列 = 笔的端点序列
           - 元素值 = 笔的终点价格（向上笔取high，向下笔取low）
        2. 特征序列包含处理：与K线包含处理原理相同
        3. **两种破坏的区分（第67课核心）**：
           - 判断两种破坏要用**原始特征序列**
           - **第一种破坏**：原始第1、2元素有包含关系
             → 合并第1、2元素，与第3元素组成新三元组
             → 判断合并后元素是否成为分型顶点
             → 若是 → 线段在原第2元素位置终结
             → 若否 → 线段可能延伸
           - **第二种破坏**：原始第1、2元素无包含关系
             → 对原始序列做包含处理
             → 判断是否出现分型
             → 出现分型 → 线段终结确认

        Args:
            data: 笔的端点列表
        """
        if len(data) < 3:
            return

        # 构建原始特征序列
        feature_seq = self._build_feature_sequence(data)
        if len(feature_seq) < 3:
            return

        pivot_flag = False

        # ================================================================
        # 缠论第67课：先用原始特征序列判断两种破坏
        # ================================================================
        raw_elem1 = feature_seq[-3]  # 原始第1元素
        raw_elem2 = feature_seq[-2]  # 原始第2元素
        raw_elem3 = feature_seq[-1]  # 原始第3元素

        # 检查原始第1、2元素是否有包含关系
        has_include_12_raw = self._has_include_relation(raw_elem1, raw_elem2)

        if has_include_12_raw:
            # ============================================================
            # 第一种破坏（缠论第67课原文）
            # 合并第1、2元素，与第3元素组成新三元组判断分型
            # ============================================================
            merged_12 = self._merge_feature_elements(raw_elem1, raw_elem2)
            # 新三元组：[合并后的元素, 第3元素] - 需要判断合并后元素相对于第3元素的位置
            # 如果合并后元素是"高点"，则是顶分型；如果是"低点"，则是底分型
            # 缠论原文：判断合并后元素是否成为分型顶点
            fx_result = self._check_first_damage_fractal(merged_12, raw_elem3)

            if fx_result == 'top':
                # 合并后出现顶分型特征，线段在原第2元素位置终结
                if not self.line_list or self.line_list[-1][3] == 'down':
                    self.line_list.append(raw_elem2)
                    self.line_index[str(raw_elem2[2])] = len(data) - 2
                    pivot_flag = True
                    ChanLog.log(self.freq, self.symbol, f'第一种破坏-顶分型, 线段终结')
            elif fx_result == 'bottom':
                if not self.line_list or self.line_list[-1][3] == 'up':
                    self.line_list.append(raw_elem2)
                    self.line_index[str(raw_elem2[2])] = len(data) - 2
                    pivot_flag = True
                    ChanLog.log(self.freq, self.symbol, f'第一种破坏-底分型, 线段终结')
            else:
                # 无分型，线段可能延伸
                pass

        else:
            # ============================================================
            # 第二种破坏（缠论第67课原文）
            # 无包含关系，做包含处理后直接判断分型
            # ============================================================
            # 先对原始序列做包含处理
            processed_seq = self._process_feature_sequence_include_v2(feature_seq)
            if len(processed_seq) < 3:
                return

            elem1 = processed_seq[-3]
            elem2 = processed_seq[-2]
            elem3 = processed_seq[-1]

            # 判断分型
            fx_result = self._check_fractal_type(elem1, elem2, elem3)

            if fx_result == 'top':
                if not self.line_list or self.line_list[-1][3] == 'down':
                    self.line_list.append(elem2)
                    self.line_index[str(elem2[2])] = len(data) - 2
                    pivot_flag = True
                elif elem2[0] > self.line_list[-1][0]:
                    # 线段延伸（更高的顶）
                    self.line_list[-1] = elem2
                    self.line_index[str(elem2[2])] = len(data) - 2
                    pivot_flag = True
            elif fx_result == 'bottom':
                if not self.line_list or self.line_list[-1][3] == 'up':
                    self.line_list.append(elem2)
                    self.line_index[str(elem2[2])] = len(data) - 2
                    pivot_flag = True
                elif elem2[1] < self.line_list[-1][1]:
                    # 线段延伸（更低的底）
                    self.line_list[-1] = elem2
                    self.line_index[str(elem2[2])] = len(data) - 2
                    pivot_flag = True

        # 线段修正
        if pivot_flag and len(self.line_list) > 1:
            self._adjust_line_endpoint_v2(data, feature_seq)

        # MACD计算和中枢生成
        if self.line_list and self.build_line_pivot:
            if len(self.line_list) > 1:
                cur_fx = self.line_list[-1]
                last_fx = self.line_list[-2]
                self.macd[cur_fx[2]] = self.cal_macd(last_fx[4], cur_fx[4])
            ChanLog.log(self.freq, self.symbol, f'line_list: {self.line_list[-1][:3]}')
            self.on_pivot(self.line_list, None)

    def _check_first_damage_fractal(self, merged_elem, elem3):
        """第一种破坏的分型判断（缠论第67课原文）

        第一种破坏时，合并第1、2元素后，判断合并后的元素是否成为分型顶点。
        由于只有两个元素，无法形成完整分型，需要用特殊逻辑：

        缠论原文精神：判断合并后元素相对于第3元素的位置关系
        - 如果合并后元素是"高点"（比第3元素高），具有顶分型特征
        - 如果合并后元素是"低点"（比第3元素低），具有底分型特征

        Args:
            merged_elem: 合并后的第1、2元素
            elem3: 第3元素

        Returns:
            str: 'top', 'bottom', None
        """
        if not merged_elem or not elem3:
            return None

        # 用值（笔的终点价格）判断
        if merged_elem[0] > elem3[0]:
            # 合并后元素的值更高，具有顶分型特征
            return 'top'
        elif merged_elem[0] < elem3[0]:
            # 合并后元素的值更低，具有底分型特征
            return 'bottom'

        return None

    def _check_fractal_type(self, elem1, elem2, elem3=None):
        """检查特征序列分型类型（缠论第65课原文）

        特征序列分型定义（与K线分型相同）：
        - 顶分型：中间元素高点最高、低点也最高
        - 底分型：中间元素低点最低、高点也最低

        Args:
            elem1: 第一个元素 [值, high, low, ...] 或合并后的元素
            elem2: 第二个元素（中间元素）
            elem3: 第三个元素（可选，第一种破坏时为None）

        Returns:
            str: 'top'(顶分型), 'bottom'(底分型), None(无分型)
        """
        if elem3 is None:
            # 第一种破坏：只有两个元素（合并后的elem1和elem3）
            # 此时不判断分型（需要更多元素）
            return None

        # 顶分型：中间元素高点最高、低点也最高
        if (elem2[1] >= elem1[1] and elem2[1] >= elem3[1] and
            elem2[2] >= elem1[2] and elem2[2] >= elem3[2]):
            return 'top'

        # 底分型：中间元素低点最低、高点也最低
        if (elem2[2] <= elem1[2] and elem2[2] <= elem3[2] and
            elem2[1] <= elem1[1] and elem2[1] <= elem3[1]):
            return 'bottom'

        return None

    def _merge_feature_elements(self, elem1, elem2):
        """合并特征序列元素（缠论第65课原文）

        合并规则（与K线包含处理相同）：
        - 向上趋势：取高点max、低点max
        - 向下趋势：取高点min、低点min

        Args:
            elem1: [值, high, low, datetime, direction, index]
            elem2: 同上

        Returns:
            list: 合并后的元素
        """
        if elem1[0] > elem2[0]:  # 向上趋势
            return [
                max(elem1[0], elem2[0]),  # 值取max
                max(elem1[1], elem2[1]),  # high取max
                max(elem1[2], elem2[2]),  # low取max
                elem2[3],  # 时间取后面
                elem2[4],  # 方向
                elem2[5]   # 索引
            ]
        else:  # 向下趋势
            return [
                min(elem1[0], elem2[0]),
                min(elem1[1], elem2[1]),
                min(elem1[2], elem2[2]),
                elem2[3],
                elem2[4],
                elem2[5]
            ]

    def _build_feature_sequence(self, data):
        """构建特征序列（缠论第65课原文）

        缠论原文：特征序列元素值 = 笔的终点价格
        - 向上笔（底分型→顶分型）：元素值 = 顶分型的high（笔的终点是顶）
        - 向下笔（顶分型→底分型）：元素值 = 底分型的low（笔的终点是底）

        Args:
            data: 笔的端点列表（分型列表）

        Returns:
            list: 特征序列 [[值, high, low, datetime, direction, stroke_index], ...]
        """
        feature_seq = []

        for i in range(len(data) - 1):
            start_fx = data[i]
            end_fx = data[i + 1]

            # 判断笔的方向
            if start_fx[3] == 'down' and end_fx[3] == 'up':
                # 向上笔：元素值 = 顶分型的high
                value = end_fx[0]  # 顶分型的high
                direction = 'up'
            elif start_fx[3] == 'up' and end_fx[3] == 'down':
                # 向下笔：元素值 = 底分型的low
                value = end_fx[1]  # 底分型的low
                direction = 'down'
            else:
                # 异常情况（同向分型）
                value = (end_fx[0] + end_fx[1]) / 2
                direction = end_fx[3]

            # 特征序列元素：[值, high, low, datetime, direction, stroke_index]
            feature_seq.append([
                value,
                max(start_fx[0], end_fx[0]),  # 笔的最高点
                min(start_fx[1], end_fx[1]),  # 笔的最低点
                end_fx[2],  # 时间
                direction,
                i  # 笔的索引
            ])

        return feature_seq

    def _process_feature_sequence_include_v2(self, feature_seq):
        """特征序列包含处理（缠论第65课原文完整版）

        处理规则（与K线包含处理相同）：
        1. 判断包含关系：元素2的高低点完全在元素1范围内
        2. 合并规则：向前看趋势方向
           - 上升方向：取高点max、低点max
           - 下降方向：取高点min、低点min
        3. 合并后的元素值取合并前的值（维持趋势方向）

        Args:
            feature_seq: 特征序列

        Returns:
            list: 处理包含关系后的特征序列
        """
        if len(feature_seq) < 2:
            return feature_seq

        processed = [feature_seq[0]]

        for i in range(1, len(feature_seq)):
            cur = feature_seq[i]

            if len(processed) < 2:
                processed.append(cur)
                continue

            prev1 = processed[-1]
            prev2 = processed[-2]

            # 判断包含关系
            if self._has_include_relation(prev1, cur):
                # 缠论原文：特征序列合并时，方向应该继承原有方向（因为方向由笔的方向决定）
                # 方向继承 prev1 的方向（prev1是已存在的元素，cur被合并进去）
                original_direction = prev1[4]

                # 判断趋势方向决定合并取值规则
                if prev1[0] > prev2[0]:  # 上升趋势（prev1值更高）
                    new_elem = [
                        max(prev1[0], cur[0]),  # 值取max（维持上升）
                        max(prev1[1], cur[1]),  # high取max
                        max(prev1[2], cur[2]),  # low取max
                        cur[3],  # 时间取后面
                        original_direction,  # 方向继承prev1
                        cur[5]   # 索引
                    ]
                else:  # 下降趋势
                    new_elem = [
                        min(prev1[0], cur[0]),  # 值取min（维持下降）
                        min(prev1[1], cur[1]),  # high取min
                        min(prev1[2], cur[2]),  # low取min
                        cur[3],
                        original_direction,  # 方向继承prev1
                        cur[5]
                    ]
                processed[-1] = new_elem
                ChanLog.log(self.freq, self.symbol, f'特征序列包含: {prev1[:4]} + {cur[:4]} -> {new_elem[:4]}')
            else:
                processed.append(cur)

        return processed

    def _has_include_relation(self, elem1, elem2):
        """判断两个特征序列元素是否存在包含关系

        包含关系：一个元素的高低点完全在另一个元素的范围内

        Args:
            elem1: [值, high, low, ...]
            elem2: [值, high, low, ...]

        Returns:
            bool: 是否存在包含关系
        """
        if not elem1 or not elem2:
            return False

        # elem1包含elem2：elem1.high >= elem2.high 且 elem1.low <= elem2.low
        case1 = elem1[1] >= elem2[1] and elem1[2] <= elem2[2]
        # elem2包含elem1：elem2.high >= elem1.high 且 elem2.low <= elem1.low
        case2 = elem2[1] >= elem1[1] and elem2[2] <= elem1[2]

        return case1 or case2

    def _adjust_line_endpoint_v2(self, data, processed_seq):
        """线段端点修正（缠论第67课）

        当出现新的线段端点后，检查倒数第二个端点是否需要修正

        Args:
            data: 原始笔数据
            processed_seq: 处理后的特征序列
        """
        if len(self.line_list) < 2:
            return

        cur_fx = self.line_list[-1]
        last_fx = self.line_list[-2]

        # 在处理后的特征序列中搜索更极端的分型
        cur_index = self.line_index.get(str(cur_fx[2]), 0)
        last_index = self.line_index.get(str(last_fx[2]), 0)

        if cur_index - last_index <= 1:
            return

        line_change = None
        for i in range(last_index + 1, min(cur_index, len(processed_seq) - 1)):
            elem = processed_seq[i]

            # 向下线段：找更高的顶分型
            if cur_fx[3] == 'down':
                if elem[4] == 'up' and elem[0] > last_fx[0]:
                    line_change = [elem[0], elem[2], elem[3], 'up', elem[5]]

            # 向上线段：找更低的底分型
            else:
                if elem[4] == 'down' and elem[0] < last_fx[0]:
                    line_change = [elem[0], elem[2], elem[3], 'down', elem[5]]

        if line_change and line_change != last_fx:
            self.line_list[-2] = line_change
            self.line_index[str(line_change[2])] = last_index
            ChanLog.log(self.freq, self.symbol, f'线段修正: {last_fx[:3]} -> {line_change[:3]}')




    def _get_pen_direction(self, start_fx, end_fx):
        """获取笔的方向（缠论第17课原文）

        笔的方向由起始分型和结束分型的方向决定：
        - 底分型→顶分型 = 向上笔 (up)
        - 顶分型→底分型 = 向下笔 (down)

        Args:
            start_fx: 起始分型
            end_fx: 结束分型

        Returns:
            str: 'up' 或 'down'
        """
        if not start_fx or not end_fx:
            return 'up'

        if start_fx[3] == 'down' and end_fx[3] == 'up':
            return 'up'
        elif start_fx[3] == 'up' and end_fx[3] == 'down':
            return 'down'
        # 异常情况：根据价格判断
        if end_fx[0] > start_fx[0]:
            return 'up'
        return 'down'

    def _get_stroke_endpoint(self, start_fx, end_fx):
        """获取笔的正确端点价格（缠论第17课原文）

        缠论原文定义：
        - 向上笔（底分型→顶分型）：笔高=顶分型high，笔低=底分型low
        - 向下笔（顶分型→底分型）：笔高=顶分型high，笔低=底分型low

        分型数据结构：[high, low, datetime, direction, k_index]
        - direction='up'：顶分型
        - direction='down'：底分型

        Args:
            start_fx: 起始分型 [high, low, datetime, direction, k_index]
            end_fx: 结束分型 [high, low, datetime, direction, k_index]

        Returns:
            tuple: (笔高点价格, 笔低点价格)
        """
        if not start_fx or not end_fx:
            return 0, 0

        # 向上笔：底分型→顶分型
        if start_fx[3] == 'down' and end_fx[3] == 'up':
            stroke_high = end_fx[0]  # 顶分型的high
            stroke_low = start_fx[1]  # 底分型的low
        # 向下笔：顶分型→底分型
        elif start_fx[3] == 'up' and end_fx[3] == 'down':
            stroke_high = start_fx[0]  # 顶分型的high
            stroke_low = end_fx[1]  # 底分型的low
        # 异常情况（同向分型），用极值
        else:
            stroke_high = max(start_fx[0], end_fx[0])
            stroke_low = min(start_fx[1], end_fx[1])

        return stroke_high, stroke_low

    def on_pivot(self, data, type):
        """中枢计算（缠论第17课原文完整版）

        缠论原文定义：
        - 中枢 = 连续三笔（或线段）的重叠区间 [ZD, ZG]
        - ZD = 前三笔低点的最大值
        - ZG = 前三笔高点的最小值
        - GG/DD = 中枢范围内的最高/最低点
        - **方向交替**：前三笔必须是上-下-上 或 下-上-下（原文要求）
        - **中枢方向**：由进入段的方向决定（向上笔进入=向上中枢）

        注：笔的正确计算方式：
        - 向上笔（底→顶）：笔高=顶分型high，笔低=底分型low
        - 向下笔（顶→底）：笔高=顶分型high，笔低=底分型low
        """
        # 中枢列表[[日期1，日期2，中枢低点，中枢高点, 中枢类型，中枢进入段，中枢离开段, 形成时间, GG, DD,BS,BS,TS]]]
        if len(data) > 5:
            cur_fx = data[-1]
            last_fx = data[-2]
            new_pivot = None
            flag = False

            # 构成新的中枢
            if not self.pivot_list or (len(self.pivot_list) > 0 and len(data) - self.pivot_list[-1][6] > 4):
                # 缠论原文：前三笔必须是方向交替（上-下-上 或 下-上-下）
                # data[-5], data[-4], data[-3], data[-2] 构成前三笔
                # 笔1: data[-5]→data[-4], 笔2: data[-4]→data[-3], 笔3: data[-3]→data[-2]
                direction1 = self._get_pen_direction(data[-5], data[-4])  # 第1笔方向
                direction2 = self._get_pen_direction(data[-4], data[-3])  # 第2笔方向
                direction3 = self._get_pen_direction(data[-3], data[-2])  # 第3笔方向

                # 验证方向交替：必须上-下-上 或 下-上-下
                directions_alternate = (direction1 == 'up' and direction2 == 'down' and direction3 == 'up') or \
                                       (direction1 == 'down' and direction2 == 'up' and direction3 == 'down')

                if not directions_alternate:
                    ChanLog.log(self.freq, self.symbol, f'中枢不形成: 方向不交替 {direction1}-{direction2}-{direction3}')
                    return  # 方向不交替，不能形成中枢

                # 正确计算笔的端点
                stroke1_high, stroke1_low = self._get_stroke_endpoint(data[-5], data[-4])
                stroke2_high, stroke2_low = self._get_stroke_endpoint(data[-4], data[-3])
                stroke3_high, stroke3_low = self._get_stroke_endpoint(data[-3], data[-2])

                ZD = max(stroke1_low, stroke2_low, stroke3_low)
                ZG = min(stroke1_high, stroke2_high, stroke3_high)

                # 区间必须有重叠（ZG > ZD）
                if ZG <= ZD:
                    ChanLog.log(self.freq, self.symbol, f'中枢不形成: 无重叠 ZG={ZG:.2f} <= ZD={ZD:.2f}')
                    return

                # GG/DD 用所有笔的端点极值
                all_stroke_highs = []
                all_stroke_lows = []
                for i in range(-5, 0):
                    if i + 1 < len(data):
                        h, l = self._get_stroke_endpoint(data[i-1] if i > -5 else data[-5], data[i])
                        all_stroke_highs.append(h)
                        all_stroke_lows.append(l)
                DD = min(all_stroke_lows) if all_stroke_lows else ZD
                GG = max(all_stroke_highs) if all_stroke_highs else ZG

                # 中枢方向由进入段（第1笔）的方向决定（缠论原文）
                pivot_direction = direction1  # 第1笔方向 = 中枢方向

                cur_pivot = [data[-5][2], last_fx[2]]
                cur_pivot.append(ZD)
                cur_pivot.append(ZG)
                cur_pivot.append(pivot_direction)  # 用第1笔方向，不是cur_fx方向
                cur_pivot.append(len(data) - 5)
                cur_pivot.append(len(data) - 2)
                cur_pivot.append(cur_fx[2])
                cur_pivot.append(GG)
                cur_pivot.append(DD)
                cur_pivot.append([[], [], []])
                cur_pivot.append([[], [], []])
                cur_pivot.append([])
                new_pivot = cur_pivot

                ChanLog.log(self.freq, self.symbol, f'中枢形成: 方向={pivot_direction}, ZD={ZD:.2f}, ZG={ZG:.2f}')

                if not self.pivot_list:
                    if new_pivot:
                        flag = True
                else:
                    last_pivot = self.pivot_list[-1]
                    if new_pivot and ((new_pivot[2] > last_pivot[3] and pivot_direction == 'up') or (
                            new_pivot[3] < last_pivot[2] and pivot_direction == 'down')):
                        flag = True
                    if type and new_pivot and type == new_pivot[4]:
                        flag = True

            if len(self.pivot_list) > 0 and not flag:
                last_pivot = self.pivot_list[-1]
                ts = last_pivot[12]
                # 由于stroke/line_change，不断change中枢
                start = last_pivot[5]
                # 防止异常
                if len(data) <= start:
                    self.pivot_list.pop()
                    if not self.pivot_list:
                        return
                    last_pivot = self.pivot_list[-1]
                    start = last_pivot[5]
                buy = last_pivot[10]
                sell = last_pivot[11]
                enter = data[start][2]
                exit = cur_fx[2]
                ee_data = [[data[start - 1], data[start]],
                           [data[len(data) - 2], data[len(data) - 1]]]

                if last_pivot[4] == 'up':
                    # 中枢扩展：只更新GG/DD，ZD/ZG固定不变（缠论第17课原文）
                    # 缠论原文：ZD/ZG由前三笔确定后固定，后续笔触及只扩展中枢生命周期
                    if len(data) > start + 3:
                        # 只更新GG/DD（中枢范围内最高/最低点）
                        all_h, all_l = [], []
                        for i in range(start, len(data) - 1):
                            h, l = self._get_stroke_endpoint(data[i], data[i+1])
                            all_h.append(h)
                            all_l.append(l)
                        last_pivot[8] = max(all_h) if all_h else last_pivot[3]  # GG
                        last_pivot[9] = min(all_l) if all_l else last_pivot[2]  # DD
                        # ZD/ZG保持不变（前三笔确定后固定）
                    if cur_fx[3] == 'up':
                        if sell[0]:
                            # 一卖后的顶分型判断一卖是否有效，无效则将上一个一卖置为无效
                            if sell[0][1] < cur_fx[0] and len(data) - last_pivot[6] < 3:
                                # 置一卖无效
                                sell[0][5] = 0
                                sell[0][6] = self.k_list[-1].datetime
                                sell[0] = []
                                # 置二卖无效
                                if sell[1]:
                                    sell[1][5] = 0
                                    sell[1][6] = self.k_list[-1].datetime
                                    sell[1] = []
                        # P0：笔级别背驰判断
                        pen_diverged = False
                        if self.on_turn(enter, exit, ee_data, last_pivot[4]):
                            pen_diverged = True
                            ChanLog.log(self.freq, self.symbol, f'中枢级别背驰确认(卖): 进入段={enter}, 离开段={exit}')

                        # P2：成交量背驰确认（辅助条件）
                        vol_diverged = False
                        if len(ee_data) >= 2 and len(ee_data[0]) >= 2 and len(ee_data[1]) >= 2:
                            enter_start_idx = ee_data[0][0][4] if len(ee_data[0][0]) > 4 else -1
                            enter_end_idx = ee_data[0][1][4] if len(ee_data[0][1]) > 4 else -1
                            exit_start_idx = ee_data[1][0][4] if len(ee_data[1][0]) > 4 else -1
                            exit_end_idx = ee_data[1][1][4] if len(ee_data[1][1]) > 4 else -1
                            # 索引必须有效（>=0）
                            if enter_start_idx >= 0 and exit_start_idx >= 0:
                                vol_diverged = self._check_volume_divergence(
                                    enter_start_idx, enter_end_idx, exit_start_idx, exit_end_idx
                                )

                        # P6-2: 区分趋势背驰和盘整背驰
                        if pen_diverged:
                            bs_type = self.cal_bs_type()
                            # 一卖需要上升趋势背驰（价格上升趋势中的背驰）
                            is_trend_bc = (bs_type == '上升趋势')

                            # 调试日志：分析一卖为什么没生成
                            pivot_GG = last_pivot[8] if len(last_pivot) > 8 else last_pivot[3]
                            pivot_ZG = last_pivot[3]
                            ChanLog.log(self.freq, self.symbol,
                                       f'背驰触发: 类型={bs_type}, cur_fx_high={cur_fx[0]:.2f}, ZG={pivot_ZG:.2f}, GG={pivot_GG:.2f}')

                            # ============================================================
                            # 缠论原文价格条件（第24课、第29课）- 放宽条件
                            # ============================================================
                            # 趋势背驰一卖：价格突破GG或回到中枢范围内
                            # 盘整背驰一卖：价格回到中枢范围内即可（置信度较低）
                            sell_valid = False
                            if is_trend_bc:
                                # 趋势背驰：突破GG或触及ZG都算
                                if cur_fx[0] >= pivot_GG or cur_fx[0] >= pivot_ZG:
                                    sell_valid = True
                            else:
                                # 盘整背驰：价格回到中枢范围内即可
                                if cur_fx[0] >= last_pivot[2]:  # 不低于ZD
                                    sell_valid = True

                            if sell_valid:
                                ts.append([last_fx[2], cur_fx[2]])
                                if not sell[0]:
                                    # 区间套验证：改为加分项，不作为否决条件
                                    qjt_confirmed, qjt_pivot_list = self.qjt_turn(last_fx[2], cur_fx[2], 'up')
                                    qjt_depth = 0 if qjt_confirmed else -1

                                    # 计算置信度（与一买对称）
                                    confidence = 60  # 基础分
                                    if is_trend_bc:
                                        confidence += 15  # 趋势背驰加分
                                    if qjt_confirmed:
                                        confidence += 15  # 区间套确认加分
                                    if vol_diverged:
                                        confidence += 10  # 成交量背驰加分

                                    ChanLog.log(self.freq, self.symbol,
                                               f'一卖确认: {bs_type}, 区间套={qjt_confirmed}, 成交量={vol_diverged}, 置信度={confidence}')

                                    sell[0] = [cur_fx[2], cur_fx[0], 'S1', self.k_list[-1].datetime, len(data) - 1, 1,
                                               None, bs_type, confidence, qjt_pivot_list, qjt_depth]
                                    self.on_buy_sell(sell[0])
                        if sell[0] and not sell[1]:
                            pos_sell1 = sell[0][4]
                            if len(data) > pos_sell1 + 2:
                                pos_fx = data[pos_sell1 + 2]
                                if pos_fx[3] == 'up':
                                    if pos_fx[1] < sell[0][1]:
                                        # 形成二卖
                                        ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'up')
                                        if ans:
                                            sell[1] = [pos_fx[2], pos_fx[0], 'S2', self.k_list[-1].datetime,
                                                       pos_sell1 + 2, 1, None, self.cal_bs_type(), None, qjt_pivot_list]
                                        self.on_buy_sell(sell[1])
                                    else:
                                        # 一卖无效
                                        sell[0][5] = 0
                                        sell[0][6] = self.k_list[-1].datetime
                                        sell[0] = []

                        if cur_fx[0] < last_pivot[2] and not sell[2] and not buy[0]:
                            # 形成三卖：反弹笔最高点严格低于ZD（不允许触及）
                            # 缠论原文第20课：三卖是"反弹不破ZD"，触及则不是三卖
                            ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'up')
                            if ans:
                                condition = len(data) > 2 and data[-3][0] < last_pivot[2] and data[-3][2] > last_pivot[
                                    1]
                                if not condition:
                                    sell[2] = [cur_fx[2], cur_fx[0], 'S3', self.k_list[-1].datetime, len(data) - 1, 1,
                                               None, self.cal_bs_type(), None, qjt_pivot_list]
                                    self.on_buy_sell(sell[2])

                        # if (not last_fx[1] > last_pivot[3]) and (not cur_fx[0] < last_pivot[2]):
                        #     last_pivot[1] = cur_fx[2]
                        #     last_pivot[6] = len(data) - 1

                    else:
                        # 判断是否延申
                        if (not cur_fx[1] > last_pivot[3]) and (not last_fx[0] < last_pivot[2]):
                            last_pivot[1] = cur_fx[2]
                            last_pivot[6] = len(data) - 1
                        else:
                            # 判断形成第三类买点
                            if cur_fx[1] > last_pivot[2] and not buy[2] and not sell[0]:
                                ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'down')
                                if ans:
                                    condition = len(data) > 2 and data[-3][1] > last_pivot[3] and data[-3][2] > \
                                                last_pivot[1]
                                    if not condition:
                                        sth_pivot = last_pivot
                                        # if len(self.pivot_list) > 1:
                                        #     sth_pivot = self.pivot_list[-2]
                                        buy[2] = [cur_fx[2], cur_fx[1], 'B3', self.k_list[-1].datetime, len(data) - 1,
                                                  1, None, self.cal_bs_type(),
                                                  self.cal_b3_strength(cur_fx[1], sth_pivot), qjt_pivot_list]
                                        ChanLog.log(self.freq, self.symbol, 'B3-pivot')
                                        ChanLog.log(self.freq, self.symbol, sth_pivot)
                                        ChanLog.log(self.freq, self.symbol, buy[2])
                                        self.on_buy_sell(buy[2])


                else:
                    # 中枢扩展：只更新GG/DD，ZD/ZG固定不变（缠论第17课原文）
                    # down方向中枢扩展
                    if len(data) > start + 3:
                        # 只更新GG/DD（中枢范围内最高/最低点）
                        all_h, all_l = [], []
                        for i in range(start, len(data) - 1):
                            h, l = self._get_stroke_endpoint(data[i], data[i+1])
                            all_h.append(h)
                            all_l.append(l)
                        last_pivot[8] = max(all_h) if all_h else last_pivot[3]  # GG
                        last_pivot[9] = min(all_l) if all_l else last_pivot[2]  # DD
                        # ZD/ZG保持不变（前三笔确定后固定）
                    if cur_fx[3] == 'down':
                        if buy[0]:
                            # 一买后的底分型判断一买是否有效，无效则将上一个一买置为无效
                            if buy[0][1] > cur_fx[1] and len(data) - last_pivot[6] < 3:
                                # 置一买无效
                                buy[0][5] = 0
                                buy[0][6] = self.k_list[-1].datetime
                                buy[0] = []
                                # 置二买无效
                                if buy[1]:
                                    buy[1][5] = 0
                                    buy[1][6] = self.k_list[-1].datetime
                                    buy[1] = []

                        # P0：笔级别背驰判断
                        # 使用中枢进入段和离开段的MACD面积对比（通过on_turn方法）
                        pen_diverged = False
                        if self.on_turn(enter, exit, ee_data, last_pivot[4]):
                            pen_diverged = True
                            ChanLog.log(self.freq, self.symbol, f'中枢级别背驰确认: 进入段={enter}, 离开段={exit}')

                        # P2：成交量背驰确认（辅助条件）
                        vol_diverged = False
                        if len(ee_data) >= 2 and len(ee_data[0]) >= 2 and len(ee_data[1]) >= 2:
                            enter_start_idx = ee_data[0][0][4] if len(ee_data[0][0]) > 4 else -1
                            enter_end_idx = ee_data[0][1][4] if len(ee_data[0][1]) > 4 else -1
                            exit_start_idx = ee_data[1][0][4] if len(ee_data[1][0]) > 4 else -1
                            exit_end_idx = ee_data[1][1][4] if len(ee_data[1][1]) > 4 else -1
                            # 索引必须有效（>=0）
                            if enter_start_idx >= 0 and exit_start_idx >= 0:
                                vol_diverged = self._check_volume_divergence(
                                    enter_start_idx, enter_end_idx, exit_start_idx, exit_end_idx
                                )

                        # P6-2: 区分趋势背驰和盘整背驰
                        if pen_diverged:
                            bs_type = self.cal_bs_type()
                            # 一买需要下降趋势背驰（价格下降趋势中的背驰）
                            is_trend_bc = (bs_type == '下降趋势')

                            # 调试日志：分析一买为什么没生成
                            pivot_DD = last_pivot[9] if len(last_pivot) > 9 else last_pivot[2]
                            pivot_ZD = last_pivot[2]
                            ChanLog.log(self.freq, self.symbol,
                                       f'背驰触发: 类型={bs_type}, cur_fx_low={cur_fx[1]:.2f}, ZD={pivot_ZD:.2f}, DD={pivot_DD:.2f}')

                            # ============================================================
                            # 缠论原文价格条件（第24课、第29课）- 放宽条件
                            # ============================================================
                            # 趋势背驰一买：价格跌破DD或回到中枢范围内
                            # 盘整背驰一买：价格回到中枢范围内即可（置信度较低）
                            buy_valid = False
                            if is_trend_bc:
                                # 趋势背驰：跌破DD或触及ZD都算
                                if cur_fx[1] <= pivot_DD or cur_fx[1] <= pivot_ZD:
                                    buy_valid = True
                            else:
                                # 盘整背驰：价格回到中枢范围内即可
                                if cur_fx[1] <= last_pivot[3]:  # 不超过ZG
                                    buy_valid = True

                            if buy_valid:
                                ts.append([last_fx[2], cur_fx[2]])
                                if not buy[0]:
                                    # 区间套验证：改为加分项，不作为否决条件
                                    qjt_confirmed, qjt_pivot_list = self.qjt_turn(last_fx[2], cur_fx[2], 'down')
                                    qjt_depth = 0 if qjt_confirmed else -1

                                    # 计算置信度（区间套确认时加分）
                                    confidence = 60  # 基础分
                                    if is_trend_bc:
                                        confidence += 15  # 趋势背驰加分
                                    if qjt_confirmed:
                                        confidence += 15  # 区间套确认加分
                                    if vol_diverged:
                                        confidence += 10  # 成交量背驰加分

                                    ChanLog.log(self.freq, self.symbol,
                                               f'一买确认: {bs_type}, 区间套={qjt_confirmed}, 成交量={vol_diverged}, 置信度={confidence}')

                                    buy[0] = [cur_fx[2], cur_fx[1], 'B1', self.k_list[-1].datetime, len(data) - 1, 1,
                                              None, bs_type, confidence, qjt_pivot_list, qjt_depth]
                                    if self.gz:
                                        self.gz_prev_last_bs = self.get_prev_last_bs()
                                        self.gz_tmp_bs = buy
                                        buy[0][5] = 0
                                    else:
                                        self.on_buy_sell(buy[0])

                        # 二买生成逻辑（缠论第18课）
                        # 方式1：一买成功后，后续底分型高于一买价格
                        # 方式2：即使没有一买，但底分型高于中枢ZD（独立二买）
                        if not buy[1]:
                            if buy[0] and buy[0][5] == 1:
                                # 方式1：一买成功后的二买
                                pos_buy1 = buy[0][4]
                                if len(data) > pos_buy1 + 2:
                                    pos_fx = data[pos_buy1 + 2]
                                    if pos_fx[3] == 'down':
                                        if pos_fx[1] > buy[0][1]:
                                            # 形成二买
                                            ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'down')
                                            if ans:
                                                sth_pivot = last_pivot
                                                buy[1] = [pos_fx[2], pos_fx[1], 'B2', self.k_list[-1].datetime,
                                                          pos_buy1 + 2, 1, None, self.cal_bs_type(),
                                                          self.cal_b2_strength(pos_fx[1], last_fx, sth_pivot),
                                                          qjt_pivot_list]
                                                self.on_buy_sell(buy[1])
                                        else:
                                            # 一买无效
                                            buy[0][5] = 0
                                            buy[0][6] = self.k_list[-1].datetime
                                            buy[0] = []
                            elif not buy[0] and cur_fx[1] > last_pivot[2]:
                                # 方式2：独立二买（缠论第18课补充）
                                # 当底分型高于中枢下沿ZD时，即使没有一买也可形成二买
                                ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'down')
                                if ans:
                                    sth_pivot = last_pivot
                                    buy[1] = [cur_fx[2], cur_fx[1], 'B2', self.k_list[-1].datetime,
                                              len(data) - 1, 1, None, self.cal_bs_type(),
                                              self.cal_b2_strength(cur_fx[1], last_fx, sth_pivot),
                                              qjt_pivot_list]
                                    ChanLog.log(self.freq, self.symbol, f'独立二买确认: cur_fx[1]={cur_fx[1]:.2f} > ZD={last_pivot[2]:.2f}')
                                    self.on_buy_sell(buy[1])

                        if cur_fx[1] > last_pivot[3] and not buy[2] and not sell[0]:
                            # 形成三买：回调笔最低点严格高于ZG（不允许触及）
                            # 缠论原文第20课：三买是"回调不破ZG"，触及则不是三买
                            ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'down')
                            if ans:
                                condition = len(data) > 2 and data[-3][1] > last_pivot[3] and data[-3][2] > \
                                            last_pivot[1]
                                if not condition:
                                    sth_pivot = last_pivot
                                    # if len(self.pivot_list) > 1:
                                    #     sth_pivot = self.pivot_list[-2]

                                    buy[2] = [cur_fx[2], cur_fx[1], 'B3', self.k_list[-1].datetime, len(data) - 1, 1,
                                              None, self.cal_bs_type(),
                                              self.cal_b3_strength(cur_fx[1], sth_pivot),
                                              qjt_pivot_list]
                                    ChanLog.log(self.freq, self.symbol, 'B3-pivot')
                                    ChanLog.log(self.freq, self.symbol, sth_pivot)
                                    ChanLog.log(self.freq, self.symbol, buy[2])
                                    self.on_buy_sell(buy[2])

                        # if (not cur_fx[1] > last_pivot[3]) and (not last_fx[0] < last_pivot[2]):
                        #     last_pivot[1] = cur_fx[2]
                        #     last_pivot[6] = len(data) - 1
                    else:
                        # 判断是否延申
                        if (not last_fx[1] > last_pivot[3]) and (not cur_fx[0] < last_pivot[2]):
                            last_pivot[1] = cur_fx[2]
                            last_pivot[6] = len(data) - 1
                        else:
                            # 判断形成第三类卖点
                            if cur_fx[1] < last_pivot[3] and not sell[2] and not buy[0]:
                                ans, qjt_pivot_list = self.qjt_trend(last_fx[2], cur_fx[2], 'up')
                                if ans:
                                    condition = len(data) > 2 and data[-3][0] < last_pivot[2] and data[-3][2] > \
                                                last_pivot[1]
                                    if not condition:
                                        sell[2] = [cur_fx[2], cur_fx[0], 'S3', self.k_list[-1].datetime, len(data) - 1,
                                                   1, None, self.cal_bs_type(), None, qjt_pivot_list]
                                        self.on_buy_sell(sell[2])

                # 判断一二类买卖点失效
                if len(self.pivot_list) > 1:
                    pre = self.pivot_list[-2]
                    pre_buy = pre[10]
                    pre_sell = pre[11]
                    if pre_sell[0] and not pre_sell[1]:
                        pos_sell1 = pre_sell[0][4]
                        if len(data) > pos_sell1 + 2:
                            pos_fx = data[pos_sell1 + 2]
                            if pos_fx[3] == 'up':
                                if pos_fx[0] < pre_sell[0][1]:
                                    # 形成二卖
                                    pre_sell[1] = [pos_fx[2], pos_fx[0], 'S2', self.k_list[-1].datetime, pos_sell1 + 2,
                                                   1, None, pre_sell[0][7], None]
                                    self.on_buy_sell(pre_sell[1])
                                else:
                                    # 一卖无效
                                    pre_sell[0][5] = 0
                                    pre_sell[0][6] = self.k_list[-1].datetime
                                    pre_sell[0] = []

                    if pre_buy[0] and pre_buy[0][5] == 1 and not pre_buy[1]:
                        pos_buy1 = pre_buy[0][4]
                        if len(data) > pos_buy1 + 2:
                            pos_fx = data[pos_buy1 + 2]
                            if pos_fx[3] == 'down':
                                if pos_fx[1] > pre_buy[0][1]:
                                    sth_pivot = None
                                    # if len(self.pivot_list) > 2:
                                    #     sth_pivot = self.pivot_list[-3]
                                    if len(self.pivot_list) > 1:
                                        sth_pivot = self.pivot_list[-2]

                                    # 形成二买
                                    pre_buy[1] = [pos_fx[2], pos_fx[1], 'B2', self.k_list[-1].datetime, pos_buy1 + 2, 1,
                                                  None, pre_buy[0][7],
                                                  self.cal_b2_strength(pos_fx[1], data[pos_buy1 + 1], sth_pivot)]
                                    self.on_buy_sell(pre_buy[1])
                                else:
                                    # 一买无效
                                    pre_buy[0][5] = 0
                                    pre_buy[0][6] = self.k_list[-1].datetime
                                    pre_buy[0] = []

                    # B2失效的判断标准：以B2为起点的笔的顶不大于反转笔的顶。
                    # 判断条件有问题
                    if pre_buy[1] and len(data) > pre_buy[1][4] + 2:
                        start = pre_buy[1][4] + 1
                        if data[start] < data[start - 2]:
                            if pre_buy[0]:
                                # 一买无效
                                pre_buy[0][5] = 0
                                pre_buy[0][6] = self.k_list[-1].datetime
                                pre_buy[0] = []
                                pre_buy[1][5] = 0
                                pre_buy[1][6] = self.k_list[-1].datetime
                                pre_buy[1] = []

                    sth_pivot = None
                    # if len(self.pivot_list) > 2:
                    #     sth_pivot = self.pivot_list[-3]
                    if len(self.pivot_list) > 1:
                        sth_pivot = self.pivot_list[-2]
                    self.x_bs_pos(data, pre_buy, pre_sell, pre, sth_pivot)

                if len(self.pivot_list) > 2:
                    pre2 = self.pivot_list[-3]
                    pre_buy = pre2[10]
                    pre_sell = pre2[11]
                    pre1 = self.pivot_list[-2]
                    if pre1[3] < last_pivot[2] and pre2[3] < pre1[2]:
                        # 上升趋势
                        if pre_sell[0]:
                            # 置一卖无效
                            pre_sell[0][5] = 0
                            pre_sell[0][6] = self.k_list[-1].datetime
                            pre_sell[0] = []

                        if pre_sell[1]:
                            # 置二卖无效
                            pre_sell[1][5] = 0
                            pre_sell[1][6] = self.k_list[-1].datetime
                            pre_sell[1] = []
                    # if pre1[2] > last_pivot[3]:
                    #     # 下降趋势
                    #     if pre_buy[0]:
                    #         # 置一买无效
                    #         pre_buy[0][5] = 0
                    #         pre_buy[0][6] = self.k_list[-1].datetime
                    #         pre_buy[0] = []
                    #
                    #     if pre_buy[1]:
                    #         # 置二买无效
                    #         pre_buy[1][5] = 0
                    #         pre_buy[1][6] = self.k_list[-1].datetime
                    #         pre_buy[1] = []
                # 判断三类买卖点失效
                if sell[2] and sell[2][0] < last_pivot[1]:
                    sell[2][5] = 0
                    sell[2][6] = self.k_list[-1].datetime
                    sell[2] = []

                if buy[2] and buy[2][0] < last_pivot[1]:
                    buy[2][5] = 0
                    buy[2][6] = self.k_list[-1].datetime
                    buy[2] = []
                sth_pivot = last_pivot
                # if len(self.pivot_list) > 1:
                #     sth_pivot = self.pivot_list[-2]
                self.x_bs_pos(data, buy, sell, last_pivot, sth_pivot)

            if flag:
                if new_pivot:
                    self.pivot_list.append(new_pivot)
                    # 中枢形成，判断背驰
                    ts = new_pivot[12]
                    buy = new_pivot[10]
                    sell = new_pivot[11]
                    enter = data[new_pivot[5]][2]
                    exit = data[new_pivot[6]][2]
                    ee_data = [[data[new_pivot[5] - 1], data[new_pivot[5]]],
                               [data[new_pivot[6] - 1], data[new_pivot[6]]]]
                    if new_pivot[4] == 'up':
                        if self.on_turn(enter, exit, ee_data, new_pivot[4]) and cur_fx[0] > new_pivot[8]:
                            ts.append([last_fx[2], cur_fx[2]])
                            if not sell[0]:
                                # 形成一卖
                                ans, qjt_pivot_list = self.qjt_turn(last_fx[2], cur_fx[2], 'up')
                                if ans:
                                    sell[0] = [cur_fx[2], cur_fx[0], 'S1', self.k_list[-1].datetime, len(data) - 1, 1,
                                               None, self.cal_bs_type(), None, qjt_pivot_list]
                                    self.on_buy_sell(sell[0])

                    if new_pivot[4] == 'down':
                        # P0：笔级别背驰判断
                        # 使用中枢进入段和离开段的MACD面积对比（通过on_turn方法）
                        pen_diverged = False
                        if self.on_turn(enter, exit, ee_data, new_pivot[4]):
                            pen_diverged = True
                            ChanLog.log(self.freq, self.symbol, f'新中枢-中枢级别背驰确认: 进入段={enter}, 离开段={exit}')

                        if pen_diverged and cur_fx[1] < new_pivot[9]:
                            ts.append([last_fx[2], cur_fx[2]])
                            if not buy[0]:
                                # 形成一买
                                ans, qjt_pivot_list = self.qjt_turn(last_fx[2], cur_fx[2], 'down')
                                if ans:
                                    buy[0] = [cur_fx[2], cur_fx[1], 'B1', self.k_list[-1].datetime, len(data) - 1, 1,
                                              None, self.cal_bs_type(), self.cal_b1_strength(cur_fx[1], cur_fx, new_pivot), qjt_pivot_list]
                                    if self.gz:
                                        self.gz_prev_last_bs = self.get_prev_last_bs()
                                        self.gz_tmp_bs = buy
                                        buy[0][5] = 0
                                    else:
                                        self.on_buy_sell(buy[0])

                    ChanLog.log(self.freq, self.symbol, "pivot_list:")
                    ChanLog.log(self.freq, self.symbol, new_pivot)
                    self.on_trend(new_pivot, data)

    def x_bs_pos(self, data, buy, sell, last_pivot, sth_pivot):
        """买卖点位置确认与等级修正

        当新K线到达或超过买卖点预判位置(pos_fx)时，确认并修正买卖点。
        核心逻辑：用实际到达的分型(low/high)替换预判值，并根据价格关系
        判断买卖点等级（B1/B2/B3 或 S1/S2/S3），或标记前置买卖点失效。

        处理流程（买方，卖方对称）：
        1. B1确认：笔端点价格<DD(中枢下沿) → 确认一类买点
        2. B2确认：笔端点价格>一买低点 → 确认二类买点；否则一买失效
        3. B3确认：笔端点价格>中枢上沿(ZG) → 确认三类买点

        Args:
            data: 分型列表(fx_list)
            buy: 买点列表 [buy1, buy2, buy3]，每个元素为买卖点数组或空列表
            sell: 卖点列表 [sell1, sell2, sell3]，每个元素为买卖点数组或空列表
            last_pivot: 最新中枢 [起始index, ZG, ZD, 结束index, ...]
            sth_pivot: 前一个中枢（用于B3/S3强度计算）
        """
        if not self.gz:
            if buy[0] and len(data) > buy[0][4] and data[buy[0][4]][2] != buy[0][0]:
                pos_fx = data[buy[0][4]]
                buy[0][5] = 0
                buy[0][6] = self.k_list[-1].datetime
                # B1<DD
                buy[0] = [pos_fx[2], pos_fx[1], 'B1', self.k_list[-1].datetime, buy[0][4], 1, None, buy[0][7],
                          self.cal_b1_strength(pos_fx[1], pos_fx, last_pivot)]
                self.on_buy_sell(buy[0])

        if sell[0] and len(data) > sell[0][4] and data[sell[0][4]][2] != sell[0][0]:
            pos_fx = data[sell[0][4]]
            sell[0][5] = 0
            sell[0][6] = self.k_list[-1].datetime
            # S1>GG
            sell[0] = [pos_fx[2], pos_fx[0], 'S1', self.k_list[-1].datetime, sell[0][4], 1, None, sell[0][7], None]
            self.on_buy_sell(sell[0])

        if buy[1] and len(data) > buy[1][4] and data[buy[1][4]][2] != buy[1][0]:
            pos_fx = data[buy[1][4]]
            buy[1][5] = 0
            buy[1][6] = self.k_list[-1].datetime
            if buy[0]:
                if pos_fx[1] > buy[0][1]:
                    # todo 笔延申重新判断为强弱
                    buy[1] = [pos_fx[2], pos_fx[1], 'B2', self.k_list[-1].datetime, buy[1][4], 1, None, buy[1][7],
                              self.cal_b2_strength(pos_fx[1], data[buy[1][4]], sth_pivot)]
                    self.on_buy_sell(buy[1])
                else:
                    # 一买无效
                    buy[0][5] = 0
                    buy[0][6] = self.k_list[-1].datetime

        if sell[1] and len(data) > sell[1][4] and data[sell[1][4]][2] != sell[1][0]:
            pos_fx = data[sell[1][4]]
            sell[1][5] = 0
            sell[1][6] = self.k_list[-1].datetime

            if pos_fx[0] < sell[0][1]:
                sell[1] = [pos_fx[2], pos_fx[0], 'S2', self.k_list[-1].datetime, sell[1][4], 1, None, sell[1][7], None]
                self.on_buy_sell(sell[1])
            else:
                # 一卖无效
                sell[0][5] = 0
                sell[0][6] = self.k_list[-1].datetime

        if buy[2] and len(data) > buy[2][4] and data[buy[2][4]][2] != buy[2][0] and buy[2][0] > last_pivot[1]:
            pos_fx = data[buy[2][4]]
            buy[2][5] = 0
            buy[2][6] = self.k_list[-1].datetime
            if pos_fx[1] > last_pivot[3]:
                buy[2] = [pos_fx[2], pos_fx[1], 'B3', self.k_list[-1].datetime, buy[2][4], 1, None, buy[2][7],
                          self.cal_b3_strength(pos_fx[1], sth_pivot)]
                ChanLog.log(self.freq, self.symbol, 'B3-pivot')
                ChanLog.log(self.freq, self.symbol, sth_pivot)
                ChanLog.log(self.freq, self.symbol, buy[2])
                self.on_buy_sell(buy[2])
        if sell[2] and len(data) > sell[2][4] and data[sell[2][4]][2] != sell[2][0] and sell[2][0] > last_pivot[1]:
            pos_fx = data[sell[2][4]]
            sell[2][5] = 0
            sell[2][6] = self.k_list[-1].datetime
            if pos_fx[0] < last_pivot[2]:
                sell[2] = [pos_fx[2], pos_fx[0], 'S3', self.k_list[-1].datetime, sell[2][4], 1, None, sell[2][7], None]
                self.on_buy_sell(sell[2])

    def cal_macd(self, start, end):
        """
        计算MACD面积（区分红绿柱）

        Args:
            start: 起始K线索引
            end: 结束K线索引

        Returns:
            dict: {
                'total': 总面积（绝对值之和）,
                'positive': 红柱面积（零轴上方）,
                'negative': 绿柱面积（零轴下方，取绝对值）
            }
        """
        result = {'total': 0, 'positive': 0, 'negative': 0}
        if start >= end:
            return result
        if self.include:
            close_list = np.array([x.close_price for x in self.chan_k_list], dtype=np.double)
        else:
            close_list = np.array([x.close_price for x in self.k_list], dtype=np.double)
        dif, dea, macd = tl.MACD(close_list, fastperiod=12,
                                 slowperiod=26, signalperiod=9)
        for i, v in enumerate(macd.tolist()):
            if start <= i <= end:
                v_rounded = round(v, 4)
                if v_rounded >= 0:
                    result['positive'] += v_rounded  # 红柱（零轴上方）
                else:
                    result['negative'] += abs(v_rounded)  # 绿柱（零轴下方，取绝对值）
                result['total'] += abs(v_rounded)
        result['total'] = round(result['total'], 4)
        result['positive'] = round(result['positive'], 4)
        result['negative'] = round(result['negative'], 4)
        return result

    def on_trend(self, new_pivot, data):
        # 走势列表[[日期1，日期2，走势类型，[背驰点], [中枢]]]
        if not self.trend_list:
            type = 'pzup'
            if new_pivot[4] == 'down':
                type = 'pzdown'
            self.trend_list.append([new_pivot[0], new_pivot[1], type, [], [len(self.pivot_list) - 1]])
        else:
            last_trend = self.trend_list[-1]
            if last_trend[2] == 'up':
                if new_pivot[4] == 'up':
                    last_trend[1] = new_pivot[1]
                    last_trend[4].append(len(self.pivot_list) - 1)
                else:
                    self.trend_list.append([new_pivot[0], new_pivot[1], 'pzdown', [], [len(self.pivot_list) - 1]])
            if last_trend[2] == 'down':
                if new_pivot[4] == 'down':
                    last_trend[1] = new_pivot[1]
                    last_trend[4].append(len(self.pivot_list) - 1)
                else:
                    self.trend_list.append([new_pivot[0], new_pivot[1], 'pzup', [], [len(self.pivot_list) - 1]])
            if last_trend[2] == 'pzup':
                if new_pivot[4] == 'up':
                    last_trend[1] = new_pivot[1]
                    last_trend[4].append(len(self.pivot_list) - 1)
                    last_trend[2] = 'up'
                else:
                    self.trend_list.append([new_pivot[0], new_pivot[1], 'pzdown', [], [len(self.pivot_list) - 1]])
            if last_trend[2] == 'pzdown':
                if new_pivot[4] == 'down':
                    last_trend[1] = new_pivot[1]
                    last_trend[4].append(len(self.pivot_list) - 1)
                    last_trend[2] = 'down'
                else:
                    self.trend_list.append([new_pivot[0], new_pivot[1], 'pzup', [], [len(self.pivot_list) - 1]])

    def on_turn(self, start, end, ee_data, type):
        """背驰判断（缠论原文多维度力度比较）

        缠论原文核心定义（第5课、第15课、第24课、第25课）：
        1. 力度 = 价格幅度 × 0.6 + 斜率 × 0.4（第5课原文定义）
        2. 背驰 = 离开段力度 < 进入段力度（第15课）
        3. MACD是辅助工具，不是判断依据（第25课）

        Args:
            start: 进入段时间
            end: 离开段时间
            ee_data: [[进入段起始分型, 进入段结束分型], [离开段起始分型, 离开段结束分型]]
            type: 'up' 或 'down'（中枢方向）

        Returns:
            bool: 是否背驰
        """
        # ============================================================
        # 第一步：力度计算（核心维度）
        # ============================================================
        enter_strength = 0.0
        exit_strength = 0.0

        if len(ee_data) >= 2 and len(ee_data[0]) >= 2 and len(ee_data[1]) >= 2:
            enter_start = ee_data[0][0]
            enter_end = ee_data[0][1]
            exit_start = ee_data[1][0]
            exit_end = ee_data[1][1]

            enter_strength = self._calculate_movement_strength(enter_start, enter_end)
            exit_strength = self._calculate_movement_strength(exit_start, exit_end)

        # 力度比
        if enter_strength > 0:
            strength_ratio = exit_strength / enter_strength
        else:
            strength_ratio = 1.0

        # ============================================================
        # 第二步：判断走势类型
        # ============================================================
        bs_type = self.cal_bs_type()
        is_trend = bs_type in ('上升趋势', '下降趋势')

        # ============================================================
        # 第三步：结构背驰判定（缠论原文阈值）
        # ============================================================
        # 缠论原文：趋势背驰要求力度衰减，盘整背驰条件更宽松
        if is_trend:
            structure_bc = strength_ratio < 0.9  # 趋势：力度衰减10%即算背驰
        else:
            structure_bc = strength_ratio < 0.95  # 盘整：力度衰减5%即算背驰

        # ============================================================
        # 第四步：MACD辅助确认（非主要判断）
        # ============================================================
        start_macd = self.macd.get(start, {'total': 0, 'positive': 0, 'negative': 0})
        end_macd = self.macd.get(end, {'total': 0, 'positive': 0, 'negative': 0})

        # 兼容旧格式
        if isinstance(start_macd, (int, float)):
            start_macd = {'total': start_macd, 'positive': start_macd, 'negative': start_macd}
        if isinstance(end_macd, (int, float)):
            end_macd = {'total': end_macd, 'positive': end_macd, 'negative': end_macd}

        # 根据方向选择对应颜色的MACD面积
        if type == 'down':
            enter_macd = start_macd.get('negative', start_macd.get('total', 0))
            exit_macd = end_macd.get('negative', end_macd.get('total', 0))
        else:
            enter_macd = start_macd.get('positive', start_macd.get('total', 0))
            exit_macd = end_macd.get('positive', end_macd.get('total', 0))

        macd_confirm = False
        if enter_macd > 0:
            macd_ratio = exit_macd / enter_macd
            macd_confirm = macd_ratio < 0.8  # MACD面积衰减20%作为辅助确认

        # ============================================================
        # 第五步：综合判定
        # ============================================================
        # 缠论原则：结构优先，MACD辅助
        if structure_bc:
            ChanLog.log(self.freq, self.symbol,
                       f'背驰确认: {bs_type}, 力度比={strength_ratio:.2%}, MACD确认={macd_confirm}')
            return True
        elif macd_confirm and strength_ratio < 0.95:
            # 结构未达标但MACD确认，且力度有明显衰减，也算弱背驰
            ChanLog.log(self.freq, self.symbol,
                       f'弱背驰: {bs_type}, 力度比={strength_ratio:.2%}, MACD确认')
            return True

        return False

    def on_buy_sell(self, data, valid=True):
        """仅记录买卖信号，不执行交易（交易执行逻辑已移至market_open层）

        数据结构扩展:
        - 原有: [日期，值，类型, evaluation_time, 位置索引, valid, invalid_time, 类型, 强弱, qjt_pivot_list, qjt_depth]
        - 新增: [..., stop_loss, take_profit]
        """
        if not data:
            return

        signal_key = f"{data[3]}_{data[2]}_{data[1]}"

        # 买点列表[[日期，值，类型, evaluation_time, 买点位置=index of stroke/line, valid, invalid_time, 类型, 强弱, qjt_pivot_list, qjt_depth, stop_loss, take_profit]]
        # 卖点列表[[日期，值，类型, evaluation_time, 买点位置=index of stroke/line, valid, invalid_time, 类型, 强弱, qjt_pivot_list, qjt_depth, stop_loss, take_profit]]
        if valid and (signal_key not in self.executed_signals):
            # 计算止盈止损
            stop_loss = 0.0
            take_profit = 0.0
            if len(data) < 13:
                last_pivot = self.pivot_list[-1] if self.pivot_list else None
                cur_fx = None
                if len(data) > 4 and data[4] < len(self.stroke_list):
                    cur_fx = self.stroke_list[data[4]]
                bs_name = data[2]
                stop_loss, take_profit = self.calculate_stop_loss_target(bs_name, last_pivot, cur_fx)
                # 扩展数据结构
                if len(data) == 11:
                    data.extend([stop_loss, take_profit])
                elif len(data) == 12:
                    data.append(take_profit)
            else:
                # 已有止盈止损字段
                if len(data) >= 13:
                    stop_loss = data[11]
                    take_profit = data[12]

            # 统一记录所有买卖信号，不区分级别（交易执行逻辑在market_open层处理）
            if data[2].startswith('B'):
                ChanLog.log(self.freq, self.symbol, f'buy signal: {data[2]} SL={stop_loss:.2f} TP={take_profit:.2f}')
                self.buy_list.append(data)
                self.executed_signals.add(signal_key)
            elif data[2].startswith('S'):
                ChanLog.log(self.freq, self.symbol, f'sell signal: {data[2]} SL={stop_loss:.2f} TP={take_profit:.2f}')
                self.sell_list.append(data)
                self.executed_signals.add(signal_key)

    def on_gz(self):
        """共振处理：只关联上一个级别"""
        # 暂时 只处理买点B1
        chan = self.prev
        if not chan:
            return
        last_bs = None
        if len(chan.buy_list) > 0:
            last_bs = chan.buy_list[-1]
        # B1不成立
        if self.gz_delay_k_num >= self.gz_delay_k_max or (len(self.gz_tmp_bs) > 4 and self.gz_tmp_bs[0][5] == 0) or not \
                self.gz_tmp_bs[0]:
            self.gz_delay_k_num = 0
            self.gz_prev_last_bs = None
            self.gz_tmp_bs[0] = []
            self.gz_tmp_bs = None
        else:
            if last_bs and last_bs != self.gz_prev_last_bs and (
                    last_bs[1] == 'B2' or last_bs[2] == 'B3' or last_bs[2] == 'B1'):
                ChanLog.log(self.freq, self.symbol, 'gz:' + str(self.gz_delay_k_num) + ':')
                ChanLog.log(self.freq, self.symbol, last_bs)
                ChanLog.log(self.freq, self.symbol, self.gz_prev_last_bs)
                ChanLog.log(self.freq, self.symbol, self.gz_tmp_bs[0])
                if self.gz_tmp_bs[0]:
                    self.gz_tmp_bs[0][3] = self.k_list[-1].datetime
                    self.gz_tmp_bs[0][5] = 1
                    self.on_buy_sell(self.gz_tmp_bs[0])
                self.gz_delay_k_num = 0
                self.gz_prev_last_bs = None
                self.gz_tmp_bs = None

    def qjt_trend(self, start, end, type):
        # 区间套判断有无走势：重新形成中枢
        qjt_pivot_list = []
        if not self.qjt:
            return True, qjt_pivot_list
        chan = self.next
        if not chan:
            return True, qjt_pivot_list
        ans = False
        ChanLog.log(self.freq, self.symbol, '区间套判断背驰：')
        ChanLog.log(self.freq, self.symbol, self.freq)

        while chan:
            tmp = False
            data = []
            if chan.build_line_pivot:
                for i in range(-1, -len(chan.line_list), -1):
                    d = chan.line_list[i]
                    if d[2] >= start:
                        if d[2] <= end:
                            data.append(d)
                    else:
                        if type == 'up' and d[3] == 'down':
                            data.append(d)
                        if type == 'down' and d[3] == 'up':
                            data.append(d)
                        break
            else:
                for i in range(-1, -len(chan.stroke_list), -1):
                    d = chan.stroke_list[i]
                    if d[2] >= start:
                        if d[2] <= end:
                            data.append(d)
                    else:
                        if type == 'up' and d[3] == 'down':
                            data.append(d)
                        if type == 'down' and d[3] == 'up':
                            data.append(d)
                        break
            data.reverse()
            chan_pivot_list = chan.qjt_pivot(data, type)
            ChanLog.log(self.freq, self.symbol, str(self.pivot_list[-1]) + ':' + str(start))
            ChanLog.log(self.freq, self.symbol, chan_pivot_list)
            qjt_pivot_list.append(chan_pivot_list)
            if not len(chan_pivot_list) > 0:
                chan = chan.next
            else:
                tmp = True
            ans = tmp or ans
            if ans:
                break

        return ans, qjt_pivot_list

    def qjt_pivot(self, data, type):
        chan_pivot = Chan_Class(freq=self.freq, symbol=self.symbol, sell=None, buy=None, include=self.include,
                                include_feature=self.include_feature, build_line_pivot=self.build_line_pivot, qjt=False)
        chan_pivot.macd = self.macd
        chan_pivot.k_list = self.chan_k_list
        new_data = []
        for d in data:
            new_data.append(d)
            chan_pivot.on_pivot(new_data, type)
        return chan_pivot.pivot_list

    def qjt_turn(self, start, end, type):
        """区间套验证（缠论第27课原文）

        缠论原文核心：区间套是"精确定位"机制，不是"否决"机制
        - 大级别背驰定方向
        - 中级别找买卖点结构
        - 小级别精确定位入场时机

        区间套未确认不代表买卖点无效，只是精度不够。

        Args:
            start: 背驰段开始时间
            end: 背驰段结束时间
            type: 'up' 或 'down'（中枢方向）

        Returns:
            tuple: (是否确认, 低级别中枢列表)
        """
        qjt_pivot_list = []
        chan = self.next
        if not chan:
            return True, qjt_pivot_list  # 无低级别数据，不阻挡

        ans = True
        ChanLog.log(self.freq, self.symbol, f'区间套验证: type={type}')

        while chan:
            tmp = False
            data = []
            if chan.build_line_pivot:
                for i in range(-1, -len(chan.line_list), -1):
                    d = chan.line_list[i]
                    if d[2] >= start:
                        if d[2] <= end:
                            data.append(d)
                    else:
                        if type == 'up' and d[3] == 'down':
                            data.append(d)
                        if type == 'down' and d[3] == 'up':
                            data.append(d)
                        break
            else:
                for i in range(-1, -len(chan.stroke_list), -1):
                    d = chan.stroke_list[i]
                    if d[2] >= start:
                        if d[2] <= end:
                            data.append(d)
                    else:
                        if type == 'up' and d[3] == 'down':
                            data.append(d)
                        if type == 'down' and d[3] == 'up':
                            data.append(d)
                        break
            data.reverse()
            chan_pivot_list = chan.qjt_pivot(data, type)
            qjt_pivot_list.append(chan_pivot_list)

            # ============================================================
            # 关键修正：区间套是确认机制，不是否决机制（缠论第27课原文）
            # ============================================================
            if chan_pivot_list and len(chan_pivot_list[-1][12]) > 0:
                # 有背驰段，精确确认
                ts_item = chan_pivot_list[-1][12][-1]
                start = ts_item[0]
                end = ts_item[1]
                tmp = True
                ChanLog.log(self.freq, self.symbol, f'区间套确认(背驰段): ts=[{start}, {end}]')
            else:
                # 无背驰段，标记为"未精确定位"但不否决
                # 缠论原文：区间套未确认不代表买卖点无效，只是精度不够
                ChanLog.log(self.freq, self.symbol, '区间套未精确定位: 无背驰段(买卖点仍有效)')
                tmp = True  # ← 关键修正：返回True，不否决

            ans = tmp and ans
            chan = chan.next

        return ans, qjt_pivot_list

    def cal_bs_type(self, pivot=None):
        """判断走势类型（缠论第17课、第20课、第33课原文）

        缠论原文定义：
        1. 趋势：至少两个同级别中枢，且中枢区间不重叠（第17课）
           - 上升趋势：前中枢ZG < 当前中枢ZD（完全不重叠，位置抬高）
           - 下降趋势：前中枢ZD > 当前中枢ZG（完全不重叠，位置降低）
        2. 中枢扩张/延伸 = 盘整（第20课）
           - 中枢区间有重叠 = 不是趋势，是盘整
        3. 缠论第33课补充：趋势至少需要9笔（3个中枢以上）
           - 如果只有2个中枢，即使不重叠，也只是"可能形成趋势"
        """
        if len(self.pivot_list) < 2:
            return '盘整'

        if pivot is None:
            pre = self.pivot_list[-2]
            cur = self.pivot_list[-1]
        else:
            idx = self.pivot_list.index(pivot)
            if idx < 1:
                return '盘整'
            pre = self.pivot_list[idx - 1]
            cur = pivot

        pre_ZD = pre[2]
        pre_ZG = pre[3]
        cur_ZD = cur[2]
        cur_ZG = cur[3]

        # 缠论原文：上升趋势 = 前中枢ZG < 当前中枢ZD（中枢完全不重叠，位置抬高）
        if pre_ZG < cur_ZD:
            return '上升趋势'

        # 缠论原文：下降趋势 = 前中枢ZD > 当前中枢ZG（中枢完全不重叠，位置降低）
        if pre_ZD > cur_ZG:
            return '下降趋势'

        # 中枢区间有重叠 = 中枢扩张 = 盘整（缠论第20课）
        # 缠论原文不允许"部分重叠也算趋势"的放宽判断
        return '盘整'

    def cal_b1_strength(self, price, cur_fx, last_pivot):
        """
        计算B1买点的强度
        B1买点：在中枢下方，向下离开中枢时的第一类买点

        强度判断逻辑：
        - 超强：大幅跌破中枢低点DD（price < last_pivot[9]）
        - 强：跌破中枢下沿ZD（price < last_pivot[2]）
        - 中：接近中枢下沿ZD（price < last_pivot[3]）
        - 弱：在中枢内部或边缘

        Args:
            price: B1买点价格
            cur_fx: 当前底分型 [high, low, datetime, direction, index]
            last_pivot: 上一个中枢

        Returns:
            强度：'超强'/'强'/'中'/'弱'
        """
        if last_pivot:
            # price = cur_fx[1]（底分型的低点）
            DD = last_pivot[9]  # 中枢低点
            ZD = last_pivot[2]  # 中枢下沿
            ZG = last_pivot[3]  # 中枢上沿

            # 计算中枢高度，用于判断"大幅跌破"
            pivot_height = ZG - ZD
            threshold = DD - pivot_height * 0.5  # 跌破DD超过中枢高度的50%

            if price < threshold:
                return '超强'
            elif price < DD:
                return '强'
            elif price < ZD:
                return '中'
        return '弱'

    def cal_b2_strength(self, price, fx, last_pivot):
        if last_pivot:
            if price > last_pivot[3]:
                return '超强'
            if fx[0] > last_pivot[3]:
                return '强'
            if fx[0] > last_pivot[2]:
                return '中'
        return '弱'

    def cal_b3_strength(self, price, last_pivot):
        if last_pivot:
            if price > last_pivot[8]:
                return '强'
        return '弱'

    def calculate_stop_loss_target(self, bs_name, pivot, cur_fx):
        """计算买卖点的止损价和目标价

        缠论原文（第100-102课 防狼术）：
        - 做多止损：一买/二买用底分型最低点，三买用中枢ZD
        - 做空止损：一卖/二卖用顶分型最高点，三卖用中枢ZG
        - 目标价：根据中枢高度计算

        Args:
            bs_name: 'B1'/'B2'/'B3'/'S1'/'S2'/'S3'
            pivot: 中枢数据 [date1, date2, ZD, ZG, type, ...]
            cur_fx: 当前分型 [high, low, datetime, direction, k_index]

        Returns:
            tuple: (stop_loss, take_profit)
        """
        stop_loss = 0.0
        take_profit = 0.0

        if pivot is None:
            return stop_loss, take_profit

        ZD = pivot[2]   # 中枢下沿
        ZG = pivot[3]   # 中枢上沿
        GG = pivot[8] if len(pivot) > 8 else pivot[3]  # 中枢最高点
        DD = pivot[9] if len(pivot) > 9 else pivot[2]  # 中枢最低点
        zs_height = ZG - ZD  # 中枢高度

        if bs_name in ('B1', 'B2', 'B3'):
            # 做多止损和目标
            if bs_name == 'B3':
                stop_loss = ZD
                take_profit = GG + zs_height
            elif bs_name == 'B2':
                stop_loss = cur_fx[1] if cur_fx else DD
                take_profit = GG
            else:
                stop_loss = cur_fx[1] if cur_fx else DD
                take_profit = ZG

        elif bs_name in ('S1', 'S2', 'S3'):
            # 做空止损和目标
            if bs_name == 'S3':
                stop_loss = ZG
                take_profit = DD - zs_height
            elif bs_name == 'S2':
                stop_loss = cur_fx[0] if cur_fx else GG
                take_profit = DD
            else:
                stop_loss = cur_fx[0] if cur_fx else GG
                take_profit = ZD

        return stop_loss, take_profit

    def _check_volume_divergence(self, enter_start_idx, enter_end_idx, exit_start_idx, exit_end_idx):
        """检查成交量背驰（缠论第12课：量能衰减确认背驰）

        核心逻辑：离开段成交量应小于进入段，表示动能衰竭

        Args:
            enter_start_idx: 进入段起始K线索引
            enter_end_idx: 进入段结束K线索引
            exit_start_idx: 离开段起始K线索引
            exit_end_idx: 离开段结束K线索引

        Returns:
            bool: 是否成交量背驰
        """
        if not self.k_list or len(self.k_list) < max(enter_end_idx, exit_end_idx) + 1:
            return False

        # 计算进入段总成交量
        enter_vol = 0.0
        for i in range(enter_start_idx, min(enter_end_idx + 1, len(self.k_list))):
            enter_vol += self.k_list[i].volume

        # 计算离开段总成交量
        exit_vol = 0.0
        for i in range(exit_start_idx, min(exit_end_idx + 1, len(self.k_list))):
            exit_vol += self.k_list[i].volume

        if enter_vol <= 0:
            return False

        vol_ratio = exit_vol / enter_vol

        # 成交量衰减超过30%才算背驰
        is_vol_divergence = vol_ratio < 0.7

        ChanLog.log(self.freq, self.symbol,
                   f'成交量背驰检查: 进入段={enter_vol:.2f}, 离开段={exit_vol:.2f}, '
                   f'比例={vol_ratio:.2%}, 结果={"背驰" if is_vol_divergence else "非背驰"}')

        return is_vol_divergence

    def _get_prev_pivot_leaving_strength(self, cur_pivot, type):
        """获取前一个中枢的离开段力度（用于趋势背驰比较）

        缠论原文（第24课、第25课）：
        趋势背驰比较的是：前一个中枢的离开段 vs 当前中枢的离开段

        Args:
            cur_pivot: 当前中枢
            type: 'up' 或 'down'（中枢方向）

        Returns:
            (strength, macd_area, ee_data): 力度、MACD面积、分型数据
        """
        if len(self.pivot_list) < 2:
            return 0.0, 0.0, None

        # 获取前一个中枢
        idx = self.pivot_list.index(cur_pivot) if cur_pivot in self.pivot_list else len(self.pivot_list) - 1
        if idx < 1:
            return 0.0, 0.0, None

        prev_pivot = self.pivot_list[idx - 1]
        data = self.stroke_list

        # 前中枢离开段 = 前中枢结束位置到前中枢后第一个反向分型
        prev_exit_time = prev_pivot[1]  # 前中枢结束时间

        # 查找前中枢离开段的分型
        leaving_start_fx = None
        leaving_end_fx = None
        for i, fx in enumerate(data):
            if fx[2] >= prev_exit_time:
                if leaving_start_fx is None:
                    leaving_start_fx = fx
                elif fx[3] != leaving_start_fx[3]:  # 方向相反
                    leaving_end_fx = fx
                    break

        if leaving_start_fx is None or leaving_end_fx is None:
            return 0.0, 0.0, None

        # 计算力度
        strength = self._calculate_movement_strength(leaving_start_fx, leaving_end_fx)

        # 计算MACD
        start_idx = leaving_start_fx[4] if len(leaving_start_fx) > 4 else 0
        end_idx = leaving_end_fx[4] if len(leaving_end_fx) > 4 else 0
        macd_info = self.cal_macd(start_idx, end_idx)

        if type == 'down':
            macd_area = macd_info.get('negative', 0)
        else:
            macd_area = macd_info.get('positive', 0)

        ee_data = [[leaving_start_fx, leaving_end_fx]]
        return strength, macd_area, ee_data

    def _check_leaving_strength_monotonic_decrease(self, cur_pivot, type):
        """校验趋势背驰的力度单调递减（缠论第33课）

        缠论原文（第33课）：
        趋势背驰的必要条件：所有离开中枢的笔，其力度必须严格递减。
        如果中间有任何一笔力度回升（非递减），则背驰不成立。

        Args:
            cur_pivot: 当前中枢
            type: 'up' 或 'down'

        Returns:
            bool: 是否满足力度单调递减
        """
        if len(self.pivot_list) < 3:
            return True  # 中枢数不足，不做校验

        # 收集所有中枢的离开段力度
        leaving_strengths = []
        data = self.stroke_list

        for pivot in self.pivot_list:
            exit_time = pivot[1]  # 中枢结束时间
            leaving_start_fx = None
            leaving_end_fx = None

            for fx in data:
                if fx[2] >= exit_time:
                    if leaving_start_fx is None:
                        leaving_start_fx = fx
                    elif fx[3] != leaving_start_fx[3]:
                        leaving_end_fx = fx
                        break

            if leaving_start_fx and leaving_end_fx:
                s = self._calculate_movement_strength(leaving_start_fx, leaving_end_fx)
                leaving_strengths.append(s)

        if len(leaving_strengths) < 3:
            return True  # 离开段不足3段，不做校验

        # 校验力度是否严格递减
        for i in range(1, len(leaving_strengths)):
            if leaving_strengths[i] >= leaving_strengths[i - 1]:
                ChanLog.log(self.freq, self.symbol,
                           f'力度单调递减校验失败: 第{i}段力度={leaving_strengths[i]:.4f} >= 第{i-1}段力度={leaving_strengths[i-1]:.4f}')
                return False

        return True

    def _calculate_movement_strength(self, start_fx, end_fx):
        """计算走势力度（缠论第5课原文定义）

        力度 = 价格幅度 × 0.6 + 斜率 × 0.4

        参考 engine_new.py _calculate_movement_strength (行2959-2987)

        Args:
            start_fx: 起始分型 [high, low, datetime, direction, k_index]
            end_fx: 结束分型 [high, low, datetime, direction, k_index]

        Returns:
            力度值
        """
        if start_fx is None or end_fx is None:
            return 0.0

        # 价格幅度
        if start_fx[3] == 'down':  # 底分型起始，向上笔
            price_amplitude = abs(end_fx[0] - start_fx[1])
        else:  # 顶分型起始，向下笔
            price_amplitude = abs(end_fx[1] - start_fx[0])

        # 时间效率（斜率）
        kline_count = max(abs(end_fx[4] - start_fx[4]), 1)
        slope = price_amplitude / kline_count

        # 综合力度 = 价格幅度 × 0.6 + 斜率 × 0.4
        strength = price_amplitude * 0.6 + slope * 0.4
        return max(strength, 1e-10)

    def cal_pen_macd(self, pen_index=None):
        """
        P0: 计算笔级别MACD
        Args:
            pen_index: 如果指定，只计算某笔的MACD；否则计算所有笔
        Returns:
            None（结果存入 self.pen_macd）
        """
        if len(self.pens) < 2:
            return

        # 构建笔的收盘价序列
        pen_close_prices = np.array([pen['close_price'] for pen in self.pens], dtype=np.double)

        # 计算笔级别MACD
        try:
            dif, dea, macd = tl.MACD(pen_close_prices, fastperiod=12, slowperiod=26, signalperiod=9)
        except:
            # 笔数据不足，无法计算
            return

        # 计算每笔的MACD面积（即该笔对应MACD值的绝对值）
        # 注意：这里pen_index是指笔在self.pens中的索引
        for i, pen in enumerate(self.pens):
            if i < len(macd):
                macd_value = macd[i]
                if math.isnan(macd_value):
                    macd_value = 0
                self.pen_macd[i] = {
                    'dif': float(dif[i]) if not math.isnan(dif[i]) else 0,
                    'dea': float(dea[i]) if not math.isnan(dea[i]) else 0,
                    'macd': float(macd_value),
                    'area': abs(float(macd_value))  # MACD柱子的面积（绝对值）
                }

    def check_pen_divergence(self, pen_index):
        """
        P0: 判断某笔是否与前一笔形成背驰
        Args:
            pen_index: 当前笔在self.pens中的索引
        Returns:
            True表示背驰，False表示未背驰
        """
        if pen_index < 1 or pen_index >= len(self.pens):
            return False

        current_pen = self.pens[pen_index]
        prev_pen = self.pens[pen_index - 1]

        # 需要两笔方向相反
        if current_pen['direction'] == prev_pen['direction']:
            return False

        # 确保已计算MACD
        if pen_index not in self.pen_macd or (pen_index - 1) not in self.pen_macd:
            self.cal_pen_macd()

        if pen_index not in self.pen_macd or (pen_index - 1) not in self.pen_macd:
            return False

        # 判断底背驰（向下笔）
        if current_pen['direction'] == 'down':
            # 价格创新低，但MACD面积缩小
            price_lower = current_pen['low_price'] < prev_pen['low_price']
            macd_shrink = self.pen_macd[pen_index]['area'] < self.pen_macd[pen_index - 1]['area']
            return price_lower and macd_shrink

        # 判断顶背驰（向上笔）
        elif current_pen['direction'] == 'up':
            # 价格创新高，但MACD面积缩小
            price_higher = current_pen['high_price'] > prev_pen['high_price']
            macd_shrink = self.pen_macd[pen_index]['area'] < self.pen_macd[pen_index - 1]['area']
            return price_higher and macd_shrink

        return False

    def qjt_turn0(self, start, end, type):
        # 区间套判断背驰：判断有无中枢和qjt_trend相同
        qjt_pivot_list = []
        if not self.qjt:
            return True, qjt_pivot_list
        chan = self.next
        if not chan:
            return True, qjt_pivot_list
        ans = False
        ChanLog.log(self.freq, self.symbol, '区间套判断背驰：')
        ChanLog.log(self.freq, self.symbol, self.freq)
        ChanLog.log(self.freq, self.symbol, str(self.pivot_list[-1]) + ':' + str(start))
        while chan:
            last_pivot = chan.pivot_list[-1]
            tmp = False
            if last_pivot[1] > start:
                if last_pivot[11][0]:
                    tmp = True
                    start = chan.stroke_list[last_pivot[11][0][4] - 1][2]
                    if chan.build_line_pivot:
                        start = chan.stroke_list[last_pivot[11][0][4] - 1][2]
                if last_pivot[10][0]:
                    tmp = True
                    start = chan.stroke_list[last_pivot[10][0][4] - 1][2]
                    if chan.build_line_pivot:
                        start = chan.stroke_list[last_pivot[10][0][4] - 1][2]
            ChanLog.log(self.freq, self.symbol, chan.freq + ':' + str(tmp))
            ChanLog.log(self.freq, self.symbol, str(last_pivot) + ':' + str(start))
            ans = ans or tmp
            chan = chan.next
        return ans, qjt_pivot_list

    def qjt_turn1(self, start, end, type):
        # 区间套判断背驰: 利用低级别的买卖点
        qjt_pivot_list = []
        if not self.qjt:
            return True, qjt_pivot_list
        chan = self.next
        if not chan:
            return True, qjt_pivot_list
        ans = False
        ChanLog.log(self.freq, self.symbol, '区间套判断背驰：')
        ChanLog.log(self.freq, self.symbol, self.freq)
        ChanLog.log(self.freq, self.symbol, str(self.pivot_list[-1]) + ':' + str(start))
        while chan:
            tmp = False
            for i in range(-1, -len(chan.buy_list), -1):
                buy_dt = chan.buy_list[i]
                if buy_dt >= end and buy_dt < start:
                    tmp = True
                    break
            tmp = False
            for i in range(-1, -len(chan.sell_list), -1):
                sell_dt = chan.sell_list[i]
                if sell_dt >= end and sell_dt < start:
                    tmp = True
                    break
            ans = ans or tmp
            chan = chan.next
        return ans, qjt_pivot_list

    def qjt_trend0(self, start, end, type):
        # 区间套判断有无走势：判断有无中枢
        qjt_pivot_list = []
        if not self.qjt:
            return True, qjt_pivot_list
        ChanLog.log(self.freq, self.symbol, '区间套判断有无走势：')
        ChanLog.log(self.freq, self.symbol, str(start) + '--' + str(end))
        ChanLog.log(self.freq, self.symbol, str(self.pivot_list[-1]))
        chan = self.next
        if not chan:
            return True, qjt_pivot_list
        ans = False
        while chan:
            tmp = False
            for i in range(-1, -len(chan.pivot_list), -1):
                last_pivot = chan.pivot_list[i]
                if last_pivot[1] <= end and last_pivot[0] >= start:
                    tmp = True
                    break
            ans = ans or tmp
            ChanLog.log(self.freq, self.symbol, chan.freq + ':' + str(tmp))
            chan = chan.next
        return ans, qjt_pivot_list

    def get_prev_last_bs(self):
        chan = self.prev
        if not chan or len(chan.buy_list) < 1:
            return None
        return chan.buy_list[-1]

    def check_next_level_bs(self, start_time, end_time):
        """
        P1: 检查下一级别在指定时间范围内是否有买卖点
        Args:
            start_time: 开始时间（datetime）
            end_time: 结束时间（datetime）
        Returns:
            True表示有买卖点确认，False表示无
        """
        if not self.next:
            return False

        next_chan = self.next
        # 检查下一级别的买入信号
        for buy_signal in next_chan.buy_list:
            signal_time = buy_signal[0]
            if start_time <= signal_time <= end_time:
                return True

        # 检查下一级别的卖出信号
        for sell_signal in next_chan.sell_list:
            signal_time = sell_signal[0]
            if start_time <= signal_time <= end_time:
                return True

        return False

    def check_next_level_divergence(self, start_time, end_time):
        """
        P1: 检查下一级别在指定时间范围内是否有背驰
        Args:
            start_time: 开始时间（datetime）
            end_time: 结束时间（datetime）
        Returns:
            True表示有背驰，False表示无
        """
        if not self.next:
            return False

        next_chan = self.next

        # 检查下一级别的背驰笔
        # 通过检查笔的结束时间来判断
        for i, pen in enumerate(next_chan.pens):
            pen_end_time = pen['end_fx'][2]  # 分型的datetime
            if start_time <= pen_end_time <= end_time:
                # 检查这笔是否背驰
                if next_chan.check_pen_divergence(i):
                    return True

        return False

    def check_multi_level_confirmation(self, signal_time, start_ref_time=None, end_ref_time=None):
        """
        P1: 多级别验证（增强版买卖点确认）
        Args:
            signal_time: 当前级别信号时间（datetime）
            start_ref_time: 参考开始时间（datetime），可选
            end_ref_time: 参考结束时间（datetime），可选
        Returns:
            '强': 多级别确认（30分+5分都有）
            '中': 下一级别确认
            '弱': 无确认
        """
        if not start_ref_time or not end_ref_time:
            # 默认时间范围：往前推20根笔的时间
            if len(self.pens) >= 20:
                start_ref_time = self.pens[-20]['end_fx'][2]
            elif len(self.pens) > 0:
                start_ref_time = self.pens[0]['end_fx'][2]
            else:
                start_ref_time = signal_time - timedelta(days=30)
            end_ref_time = signal_time

        if not self.next:
            return '弱'

        # 检查30分钟级别
        min30_has_bs = self.check_next_level_bs(start_ref_time, end_ref_time)
        min30_has_div = self.check_next_level_divergence(start_ref_time, end_ref_time)

        if not (min30_has_bs or min30_has_div):
            return '弱'

        # 检查5分钟级别
        if self.next and self.next.next:
            min5_has_bs = self.next.check_next_level_bs(start_ref_time, end_ref_time)
            min5_has_div = self.next.check_next_level_divergence(start_ref_time, end_ref_time)

            if min5_has_bs or min5_has_div:
                return '强'

        return '中'
