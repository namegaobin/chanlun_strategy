"""
缠论形态识别模块 V2 - 完整实现
功能：K线包含关系处理、笔识别、线段识别、中枢精确计算

V2 改进：
1. 实现K线包含关系处理（P0）
2. 完善笔的构建逻辑（添加穿越中轴判断）
3. 正确的中枢计算（基于笔而非K线）
4. 添加进入段、确认段、离开段识别
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class FractalType(Enum):
    """分型类型"""
    TOP = "top"       # 顶分型
    BOTTOM = "bottom" # 底分型
    NONE = "none"     # 无分型


class Direction(Enum):
    """方向"""
    UP = "up"
    DOWN = "down"


@dataclass
class Fractal:
    """分型"""
    type: FractalType
    index: int          # K线索引（在处理后的DataFrame中）
    price: float        # 分型价格
    high: float         # K线高点
    low: float          # K线低点


@dataclass
class Bi:
    """笔"""
    direction: Direction
    start_index: int
    end_index: int
    start_price: float
    end_price: float
    high: float
    low: float
    kline_count: int    # 包含的K线数量


@dataclass
class Xianduan:
    """线段"""
    direction: Direction
    start_index: int
    end_index: int
    start_price: float
    end_price: float
    bi_list: List[Bi]


@dataclass
class Zhongshu:
    """中枢"""
    zg: float           # 中枢高点
    zd: float           # 中枢低点
    start_index: int    # 起始索引
    end_index: int      # 结束索引
    level: int          # 中枢级别（1=笔中枢，2=线段中枢）
    bi_list: List[Bi]   # 构成中枢的笔（确认三笔）
    enter_bi: Optional[Bi] = None   # 进入段
    exit_bi: Optional[Bi] = None    # 离开段
    
    @property
    def middle(self) -> float:
        """中枢中轴"""
        return (self.zg + self.zd) / 2
    
    @property
    def height(self) -> float:
        """中枢高度"""
        return self.zg - self.zd


# ────────────────────────────────────────────────────────────────
# Phase 1.1: K线包含关系处理（核心基础）
# ────────────────────────────────────────────────────────────────

def is_included(k1: pd.Series, k2: pd.Series) -> bool:
    """
    判断两根K线是否存在包含关系
    
    包含关系定义：
    - K1完全包含K2：k1.high >= k2.high 且 k1.low <= k2.low
    - K2完全包含K1：k2.high >= k1.high 且 k2.low <= k1.low
    
    Args:
        k1: K线1（需包含 high, low 字段）
        k2: K线2（需包含 high, low 字段）
        
    Returns:
        是否存在包含关系
    """
    # K1包含K2
    if k1['high'] >= k2['high'] and k1['low'] <= k2['low']:
        return True
    # K2包含K1
    if k2['high'] >= k1['high'] and k2['low'] <= k1['low']:
        return True
    return False


def determine_trend(df: pd.DataFrame, i: int) -> str:
    """
    判断当前趋势方向
    
    规则：
    - 如果当前K线的收盘价 > 前一根K线的收盘价，则为上升趋势
    - 如果当前K线的收盘价 < 前一根K线的收盘价，则为下降趋势
    - 如果相等，继续向前找
    
    Args:
        df: K线数据
        i: 当前K线索引
        
    Returns:
        'up' 或 'down'
    """
    if i < 1:
        # 无法判断趋势，默认下降趋势（保守处理）
        return 'down'
    
    current_close = df.iloc[i]['close']
    prev_close = df.iloc[i - 1]['close']
    
    if current_close > prev_close:
        return 'up'
    elif current_close < prev_close:
        return 'down'
    else:
        # 收盘价相等，继续向前判断
        return determine_trend(df, i - 1)


def merge_klines(k1: pd.Series, k2: pd.Series, trend: str) -> pd.Series:
    """
    合并两根存在包含关系的K线
    
    合并规则：
    - 上升趋势：高点取高的，低点取高的
    - 下降趋势：高点取低的，低点取低的
    
    时间属性：取后一根K线的时间
    
    Args:
        k1: 前一根K线
        k2: 后一根K线
        trend: 趋势方向 ('up' 或 'down')
        
    Returns:
        合并后的K线
    """
    if trend == 'up':
        # 上升趋势：取高高点、高低点
        high = max(k1['high'], k2['high'])
        low = max(k1['low'], k2['low'])
    else:
        # 下降趋势：取低高点、低低点
        high = min(k1['high'], k2['high'])
        low = min(k1['low'], k2['low'])
    
    # 创建合并后的K线
    merged = pd.Series({
        'high': high,
        'low': low,
        'open': k1['open'],
        'close': k2['close'],
        'date': k2['date'],
        'volume': k1.get('volume', 0) + k2.get('volume', 0)  # 成交量相加
    })
    
    return merged


def process_inclusion(df: pd.DataFrame) -> pd.DataFrame:
    """
    处理K线包含关系（主入口函数）
    
    处理流程：
    1. 遍历K线序列
    2. 检测相邻K线是否存在包含关系
    3. 如果存在，根据趋势方向合并K线
    4. 返回处理后的K线序列（包含关系已消除）
    
    Args:
        df: 原始K线数据（需包含 high, low, open, close, date 列）
        
    Returns:
        处理后的K线数据（包含关系已合并）
        
    示例：
        >>> df = pd.DataFrame({
        ...     'high': [12, 13, 11],
        ...     'low': [10, 11, 9],
        ...     'close': [11, 12, 10],
        ...     'open': [10, 11, 9],
        ...     'date': ['2026-04-01', '2026-04-02', '2026-04-03']
        ... })
        >>> result = process_inclusion(df)
    """
    if df is None or len(df) < 2:
        return df
    
    # 确保数据按日期排序
    df = df.copy()
    if 'date' in df.columns:
        df = df.sort_values('date').reset_index(drop=True)
    
    processed = []
    i = 0
    
    while i < len(df):
        # 最后一次循环，直接添加
        if i == len(df) - 1:
            processed.append(df.iloc[i])
            break
        
        k1 = df.iloc[i]
        k2 = df.iloc[i + 1]
        
        # 检查是否存在包含关系
        if is_included(k1, k2):
            # 判断趋势方向
            trend = determine_trend(df, i)
            
            # 合并K线
            merged_k = merge_klines(k1, k2, trend)
            processed.append(merged_k)
            
            # 跳过已处理的K线（i += 2）
            i += 2
        else:
            # 无包含关系，直接添加
            processed.append(k1)
            i += 1
    
    # 转换为DataFrame
    result = pd.DataFrame(processed)
    
    # 重置索引
    result = result.reset_index(drop=True)
    
    return result


# ────────────────────────────────────────────────────────────────
# Phase 1.2: 分型识别与笔的构建（改进版）
# ────────────────────────────────────────────────────────────────

def detect_fractal(df: pd.DataFrame, i: int) -> Optional[Fractal]:
    """
    检测第i根K线是否构成分型
    
    分型定义：
    - 顶分型：中间K线高点最高（high2 > high1 且 high2 > high3）
    - 底分型：中间K线低点最低（low2 < low1 且 low2 < low3）
    
    Args:
        df: K线数据（已处理包含关系）
        i: K线索引（需要 i >= 1 and i < len(df) - 1）
        
    Returns:
        Fractal对象，如果无分型则返回None
    """
    if i < 1 or i >= len(df) - 1:
        return None
        
    # 获取三根K线
    k1 = df.iloc[i - 1]
    k2 = df.iloc[i]
    k3 = df.iloc[i + 1]
    
    high1, high2, high3 = k1['high'], k2['high'], k3['high']
    low1, low2, low3 = k1['low'], k2['low'], k3['low']
    
    # 顶分型判断
    if high2 > high1 and high2 > high3:
        return Fractal(
            type=FractalType.TOP,
            index=i,
            price=high2,
            high=high2,
            low=low2
        )
    
    # 底分型判断
    if low2 < low1 and low2 < low3:
        return Fractal(
            type=FractalType.BOTTOM,
            index=i,
            price=low2,
            high=high2,
            low=low2
        )
    
    return None


def detect_all_fractals(df: pd.DataFrame) -> List[Fractal]:
    """
    检测所有分型
    
    Args:
        df: K线数据（已处理包含关系）
        
    Returns:
        分型列表（按时间排序）
    """
    fractals = []
    
    for i in range(1, len(df) - 1):
        fractal = detect_fractal(df, i)
        if fractal:
            fractals.append(fractal)
            
    return fractals


def filter_fractals(fractals: List[Fractal]) -> List[Fractal]:
    """
    过滤分型（合并相邻同类型分型）
    
    规则：
    - 相邻两个顶分型，取更高的那个
    - 相邻两个底分型，取更低的那个
    
    Args:
        fractals: 原始分型列表
        
    Returns:
        过滤后的分型列表（顶底交替）
    """
    if len(fractals) < 2:
        return fractals
        
    filtered = [fractals[0]]
    
    for f in fractals[1:]:
        last = filtered[-1]
        
        if f.type == last.type:
            # 同类型分型，保留更极端的
            if f.type == FractalType.TOP:
                if f.price > last.price:
                    filtered[-1] = f
            else:  # BOTTOM
                if f.price < last.price:
                    filtered[-1] = f
        else:
            # 不同类型，直接添加
            filtered.append(f)
            
    return filtered


def build_bi_from_fractals(
    fractals: List[Fractal],
    df: pd.DataFrame,
    min_klines: int = 5,  # 缠论原文标准：至少5根K线
    debug: bool = False
) -> List[Bi]:
    """
    从分型构建笔（改进版 V3）

    笔的成立条件：
    1. 顶分型 → 底分型 或 底分型 → 顶分型（必须交替）
    2. 笔至少包含 min_klines 根K线（包含处理后的K线）
    3. 向上笔：终点 > 起点；向下笔：终点 < 起点
    4. 相邻两笔方向必须相反（顶底交替）
    5. 第4笔开始必须穿越前一笔的中轴

    分型重新匹配机制：
    - 当笔无效时，尝试下一个分型对，而不是简单跳过
    - 确保笔序列不断裂

    Args:
        fractals: 分型列表（已过滤相邻同类型）
        df: K线数据（已处理包含关系）
        min_klines: 最少K线数（默认5，缠论原文标准）

    Returns:
        有效的笔列表（顶底交替）
    """
    if len(fractals) < 2:
        return []

    bi_list = []
    i = 0  # 当前分型索引

    while i < len(fractals) - 1:
        found_valid_bi = False
        best_bi = None
        best_j = i + 1

        # 从当前分型开始，寻找第一个有效的终点分型
        for j in range(i + 1, len(fractals)):
            f1 = fractals[i]
            f2 = fractals[j]

            # 必须是顶底交替（类型不同）
            if f1.type == f2.type:
                continue

            # 确定方向
            if f1.type == FractalType.BOTTOM and f2.type == FractalType.TOP:
                direction = Direction.UP
                start_price = f1.price
                end_price = f2.price
            elif f1.type == FractalType.TOP and f2.type == FractalType.BOTTOM:
                direction = Direction.DOWN
                start_price = f1.price
                end_price = f2.price
            else:
                continue

            # 检查与上一笔的方向是否相反（顶底交替规则）
            if bi_list and bi_list[-1].direction == direction:
                continue

            # 检查K线数量（至少 min_klines 根）
            kline_count = f2.index - f1.index + 1
            if kline_count < min_klines:
                continue

            # 检查方向一致性
            if direction == Direction.UP and end_price <= start_price:
                continue
            if direction == Direction.DOWN and end_price >= start_price:
                continue

            # 计算笔的高低点
            bi_data = df.iloc[f1.index:f2.index + 1]
            high = bi_data['high'].max()
            low = bi_data['low'].min()

            # 检查穿越前一笔的中轴（前3笔后启用）
            if bi_list and len(bi_list) >= 3:
                prev_bi = bi_list[-1]
                mid_line = (prev_bi.high + prev_bi.low) / 2

                if direction == Direction.UP:
                    # 向上笔：终点应高于中轴（允许10%误差）
                    if end_price < mid_line * 0.9:
                        continue
                else:
                    # 向下笔：终点应低于中轴（允许10%误差）
                    if end_price > mid_line * 1.1:
                        continue

            # 找到有效的笔
            bi = Bi(
                direction=direction,
                start_index=f1.index,
                end_index=f2.index,
                start_price=start_price,
                end_price=end_price,
                high=high,
                low=low,
                kline_count=kline_count
            )

            # 记录找到的有效笔
            best_bi = bi
            best_j = j
            found_valid_bi = True
            break  # 找到第一个有效笔，跳出内循环

        if found_valid_bi and best_bi:
            bi_list.append(best_bi)
            # 关键：下一笔的起点必须是相反类型的分型
            # 如果当前笔终点是顶分型，下一笔起点必须是顶分型（向下笔）
            # 如果当前笔终点是底分型，下一笔起点必须是底分型（向上笔）
            # 所以我们需要找到下一个与终点分型同类型的分型作为新起点
            end_fractal_type = fractals[best_j].type
            next_i = best_j
            for k in range(best_j + 1, len(fractals)):
                if fractals[k].type == end_fractal_type:
                    next_i = k
                    break
            else:
                # 没找到同类型的，就从终点分型的下一个开始
                next_i = best_j + 1
            i = next_i
        else:
            # 没有找到有效的笔，尝试下一个起点分型
            i += 1

    return bi_list


# ────────────────────────────────────────────────────────────────
# Phase 1.3: 中枢计算（基于笔的正确实现）
# ────────────────────────────────────────────────────────────────

def calculate_zhongshu_from_bi(
    bi_list: List[Bi],
    min_bi: int = 3
) -> Optional[Zhongshu]:
    """
    从笔计算中枢（正确实现 V2）
    
    中枢定义：
    - 至少由3笔构成
    - ZG (中枢高点) = min(笔高点)
    - ZD (中枢低点) = max(笔低点)
    - ZG > ZD 才是有效中枢
    
    中枢构成：
    - 进入段：中枢前的最后一笔
    - 确认段：构成中枢的3笔（笔2、笔3、笔4）
    - 离开段：中枢后的第一笔（如果有）
    
    Args:
        bi_list: 笔列表
        min_bi: 构成中枢的最少笔数（默认3）
        
    Returns:
        Zhongshu对象，无效时返回None
    """
    if len(bi_list) < min_bi:
        return None
    
    # 取最近的笔进行计算（确认三笔）
    confirm_bi = bi_list[-min_bi:]
    
    # ZG = min(笔高点)
    zg = min(bi.high for bi in confirm_bi)
    
    # ZD = max(笔低点)
    zd = max(bi.low for bi in confirm_bi)
    
    # 验证中枢有效性
    if zg <= zd:
        return None
    
    # 识别进入段和离开段
    enter_bi = None
    exit_bi = None
    
    if len(bi_list) > min_bi:
        # 进入段：中枢前的最后一笔
        enter_bi = bi_list[-(min_bi + 1)]
        
        # 离开段：中枢确认后的下一笔（如果有）
        if len(bi_list) > min_bi + 1:
            # 注意：离开段是确认三笔之后的第一笔
            exit_bi = bi_list[-1]
    
    return Zhongshu(
        zg=zg,
        zd=zd,
        start_index=confirm_bi[0].start_index,
        end_index=confirm_bi[-1].end_index,
        level=1,  # 笔中枢
        bi_list=confirm_bi,
        enter_bi=enter_bi,
        exit_bi=exit_bi
    )


def detect_all_zhongshu(bi_list: List[Bi], min_bi: int = 3) -> List[Zhongshu]:
    """
    检测所有中枢
    
    Args:
        bi_list: 笔列表
        min_bi: 最少笔数
        
    Returns:
        中枢列表
    """
    if len(bi_list) < min_bi:
        return []
    
    zhongshu_list = []
    
    # 滑动窗口检测中枢
    for i in range(len(bi_list) - min_bi + 1):
        window_bi = bi_list[i:i + min_bi]
        
        # 计算中枢
        zg = min(bi.high for bi in window_bi)
        zd = max(bi.low for bi in window_bi)
        
        if zg > zd:
            # 有效中枢
            enter_bi = bi_list[i - 1] if i > 0 else None
            exit_bi = bi_list[i + min_bi] if i + min_bi < len(bi_list) else None
            
            zhongshu = Zhongshu(
                zg=zg,
                zd=zd,
                start_index=window_bi[0].start_index,
                end_index=window_bi[-1].end_index,
                level=1,
                bi_list=window_bi,
                enter_bi=enter_bi,
                exit_bi=exit_bi
            )
            
            zhongshu_list.append(zhongshu)
    
    # 过滤重叠的中枢（只保留最大的）
    # TODO: 实现中枢延伸和扩展判断
    
    return zhongshu_list


# ────────────────────────────────────────────────────────────────
# 线段识别
# ────────────────────────────────────────────────────────────────

def detect_xianduan_from_bi(bi_list: List[Bi], min_bi: int = 3) -> List[Xianduan]:
    """
    从笔构建线段
    
    线段定义：
    - 至少由3笔构成
    - 同向笔的延伸构成线段
    - 出现破坏特征序列时线段结束
    
    Args:
        bi_list: 笔列表
        min_bi: 最少笔数
        
    Returns:
        线段列表
    """
    if len(bi_list) < min_bi:
        return []
        
    xianduan_list = []
    current_start = 0
    current_direction = bi_list[0].direction
    
    for i in range(1, len(bi_list)):
        bi = bi_list[i]
        
        # 检查是否出现破坏
        if bi.direction != current_direction:
            # 反向笔出现，检查是否构成线段
            bi_count = i - current_start
            
            if bi_count >= min_bi:
                # 构成线段
                segment_bi = bi_list[current_start:i]
                
                xd = Xianduan(
                    direction=current_direction,
                    start_index=segment_bi[0].start_index,
                    end_index=segment_bi[-1].end_index,
                    start_price=segment_bi[0].start_price,
                    end_price=segment_bi[-1].end_price,
                    bi_list=segment_bi
                )
                xianduan_list.append(xd)
                
                # 开始新线段
                current_start = i
                current_direction = bi.direction
                
    # 处理最后一个线段
    if len(bi_list) - current_start >= min_bi:
        segment_bi = bi_list[current_start:]
        xd = Xianduan(
            direction=current_direction,
            start_index=segment_bi[0].start_index,
            end_index=segment_bi[-1].end_index,
            start_price=segment_bi[0].start_price,
            end_price=segment_bi[-1].end_price,
            bi_list=segment_bi
        )
        xianduan_list.append(xd)
        
    return xianduan_list


# ────────────────────────────────────────────────────────────────
# 主分析器
# ────────────────────────────────────────────────────────────────

class ChanLunStructureAnalyzerV2:
    """缠论形态分析器 V2"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化分析器
        
        Args:
            df: 原始K线数据（未处理包含关系）
        """
        self.df_raw = df.copy()
        self.df_processed = None  # 处理包含关系后的数据
        self.fractals = []
        self.bi_list = []
        self.xianduan_list = []
        self.zhongshu_list = []
        
    def analyze(self) -> Dict:
        """
        执行完整的缠论形态分析
        
        Returns:
            分析结果
        """
        # 1. 处理K线包含关系
        self.df_processed = process_inclusion(self.df_raw)
        
        # 2. 检测分型
        self.fractals = detect_all_fractals(self.df_processed)
        self.fractals = filter_fractals(self.fractals)
        
        # 3. 构建笔
        self.bi_list = build_bi_from_fractals(self.fractals, self.df_processed)
        
        # 4. 构建线段
        self.xianduan_list = detect_xianduan_from_bi(self.bi_list)
        
        # 5. 检测所有中枢
        self.zhongshu_list = detect_all_zhongshu(self.bi_list)
        
        return {
            'df_processed': self.df_processed,
            'fractals': self.fractals,
            'bi_list': self.bi_list,
            'xianduan_list': self.xianduan_list,
            'zhongshu_list': self.zhongshu_list
        }
        
    def get_current_structure(self) -> Dict:
        """获取当前形态结构"""
        current_zhongshu = self.zhongshu_list[-1] if self.zhongshu_list else None
        
        return {
            'current_bi': self.bi_list[-1] if self.bi_list else None,
            'current_xianduan': self.xianduan_list[-1] if self.xianduan_list else None,
            'current_zhongshu': {
                'zg': current_zhongshu.zg,
                'zd': current_zhongshu.zd,
                'middle': current_zhongshu.middle,
                'level': current_zhongshu.level,
                'has_enter': current_zhongshu.enter_bi is not None,
                'has_exit': current_zhongshu.exit_bi is not None
            } if current_zhongshu else None,
            'bi_count': len(self.bi_list),
            'zhongshu_count': len(self.zhongshu_list)
        }
    
    def print_summary(self):
        """打印分析摘要"""
        print(f"\n{'='*60}")
        print(f"缠论形态分析摘要")
        print(f"{'='*60}")
        
        # K线信息
        print(f"\n【K线信息】")
        print(f"原始K线数: {len(self.df_raw)}")
        print(f"处理后K线数: {len(self.df_processed)}")
        print(f"合并K线数: {len(self.df_raw) - len(self.df_processed)}")
        
        # 分型信息
        print(f"\n【分型信息】")
        print(f"总分型数: {len(self.fractals)}")
        top_count = sum(1 for f in self.fractals if f.type == FractalType.TOP)
        bottom_count = sum(1 for f in self.fractals if f.type == FractalType.BOTTOM)
        print(f"顶分型: {top_count}, 底分型: {bottom_count}")
        
        # 笔信息
        print(f"\n【笔信息】")
        print(f"总笔数: {len(self.bi_list)}")
        if self.bi_list:
            up_count = sum(1 for bi in self.bi_list if bi.direction == Direction.UP)
            down_count = sum(1 for bi in self.bi_list if bi.direction == Direction.DOWN)
            print(f"向上笔: {up_count}, 向下笔: {down_count}")
            
            last_bi = self.bi_list[-1]
            print(f"当前笔: {last_bi.direction.value}笔")
            print(f"  起点价格: {last_bi.start_price:.2f}")
            print(f"  终点价格: {last_bi.end_price:.2f}")
            print(f"  包含K线: {last_bi.kline_count}根")
        
        # 中枢信息
        print(f"\n【中枢信息】")
        print(f"总中枢数: {len(self.zhongshu_list)}")
        if self.zhongshu_list:
            last_zs = self.zhongshu_list[-1]
            print(f"当前中枢:")
            print(f"  ZG (高点): {last_zs.zg:.2f}")
            print(f"  ZD (低点): {last_zs.zd:.2f}")
            print(f"  中轴: {last_zs.middle:.2f}")
            print(f"  高度: {last_zs.height:.2f}")
            print(f"  进入段: {'有' if last_zs.enter_bi else '无'}")
            print(f"  离开段: {'有' if last_zs.exit_bi else '无'}")
        
        print(f"\n{'='*60}\n")
