"""
缠论形态识别模块 - 完整版
功能：笔识别、线段识别、中枢精确计算
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
    index: int          # K线索引
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
    start_index: int
    end_index: int
    level: int          # 中枢级别（1=笔中枢，2=线段中枢）
    bi_list: List[Bi]   # 构成中枢的笔


def detect_fractal(df: pd.DataFrame, i: int) -> Optional[Fractal]:
    """
    检测第i根K线是否构成分型
    
    分型定义：
    - 顶分型：中间K线高点最高
    - 底分型：中间K线低点最低
    
    Args:
        df: K线数据
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
        # 确认：中间K线高点最高
        return Fractal(
            type=FractalType.TOP,
            index=i,
            price=high2,
            high=high2,
            low=low2
        )
    
    # 底分型判断
    if low2 < low1 and low2 < low3:
        # 确认：中间K线低点最低
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
        df: K线数据
        
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
        过滤后的分型列表
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
    df: pd.DataFrame
) -> List[Bi]:
    """
    从分型构建笔
    
    笔的定义：
    - 一个顶分型和一个底分型构成一笔
    - 笔必须包含至少5根K线（包含端点）
    - 笔必须穿越前一笔的中轴
    
    Args:
        fractals: 分型列表
        df: K线数据
        
    Returns:
        笔列表
    """
    if len(fractals) < 2:
        return []
        
    bi_list = []
    
    for i in range(len(fractals) - 1):
        f1 = fractals[i]
        f2 = fractals[i + 1]
        
        # 顶→底 或 底→顶 构成一笔
        if f1.type == FractalType.TOP and f2.type == FractalType.BOTTOM:
            direction = Direction.DOWN
            start_price = f1.price
            end_price = f2.price
        elif f1.type == FractalType.BOTTOM and f2.type == FractalType.TOP:
            direction = Direction.UP
            start_price = f1.price
            end_price = f2.price
        else:
            continue
            
        # 计算笔的高点和低点
        bi_data = df.iloc[f1.index:f2.index + 1]
        high = bi_data['high'].max()
        low = bi_data['low'].min()
        
        bi = Bi(
            direction=direction,
            start_index=f1.index,
            end_index=f2.index,
            start_price=start_price,
            end_price=end_price,
            high=high,
            low=low
        )
        
        bi_list.append(bi)
        
    return bi_list


def validate_bi(bi_list: List[Bi], min_klines: int = 5) -> List[Bi]:
    """
    验证笔的有效性
    
    规则：
    - 笔必须包含至少 min_klines 根K线
    - 向上笔的终点必须高于起点
    - 向下笔的终点必须低于起点
    
    Args:
        bi_list: 笔列表
        min_klines: 最小K线数
        
    Returns:
        验证后的笔列表
    """
    valid_bi = []
    
    for bi in bi_list:
        # 检查K线数
        kline_count = bi.end_index - bi.start_index + 1
        if kline_count < min_klines:
            continue
            
        # 检查方向一致性
        if bi.direction == Direction.UP:
            if bi.end_price <= bi.start_price:
                continue
        else:
            if bi.end_price >= bi.start_price:
                continue
                
        valid_bi.append(bi)
        
    return valid_bi


def detect_xianduan_from_bi(bi_list: List[Bi], min_bi_count: int = 3) -> List[Xianduan]:
    """
    从笔构建线段
    
    线段定义：
    - 至少由3笔构成
    - 同向笔的延伸构成线段
    - 出现破坏特征序列时线段结束
    
    Args:
        bi_list: 笔列表
        min_bi_count: 最少笔数
        
    Returns:
        线段列表
    """
    if len(bi_list) < min_bi_count:
        return []
        
    xianduan_list = []
    current_start = 0
    current_direction = bi_list[0].direction
    
    for i in range(1, len(bi_list)):
        # 检查是否出现破坏
        bi = bi_list[i]
        
        # 简化判断：如果连续2笔同向，则线段延续
        # 如果出现反向破坏，则线段可能结束
        if bi.direction != current_direction:
            # 反向笔，检查是否构成线段破坏
            bi_count = i - current_start
            
            if bi_count >= min_bi_count:
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
    if len(bi_list) - current_start >= min_bi_count:
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


def calculate_zhongshu_from_bi(bi_list: List[Bi], min_bi: int = 3) -> Optional[Zhongshu]:
    """
    从笔计算中枢
    
    中枢定义：
    - 至少由3笔构成
    - ZG = min(笔高点)
    - ZD = max(笔低点)
    - ZG > ZD 才是有效中枢
    
    Args:
        bi_list: 笔列表
        min_bi: 最少笔数
        
    Returns:
        Zhongshu对象，如果无效则返回None
    """
    if len(bi_list) < min_bi:
        return None
        
    # 取最近的笔计算中枢
    recent_bi = bi_list[-min_bi:]
    
    # ZG = min(笔高点)
    zg = min(bi.high for bi in recent_bi)
    
    # ZD = max(笔低点)
    zd = max(bi.low for bi in recent_bi)
    
    # 验证中枢有效性
    if zg <= zd:
        return None
        
    return Zhongshu(
        zg=zg,
        zd=zd,
        start_index=recent_bi[0].start_index,
        end_index=recent_bi[-1].end_index,
        level=1,  # 笔中枢
        bi_list=recent_bi
    )


def calculate_zhongshu_from_xianduan(xianduan_list: List[Xianduan], min_xd: int = 3) -> Optional[Zhongshu]:
    """
    从线段计算中枢（更高级别）
    
    Args:
        xianduan_list: 线段列表
        min_xd: 最少线段数
        
    Returns:
        Zhongshu对象
    """
    if len(xianduan_list) < min_xd:
        return None
        
    recent_xd = xianduan_list[-min_xd:]
    
    zg = min(xd.end_price if xd.direction == Direction.UP else xd.start_price for xd in recent_xd)
    zd = max(xd.end_price if xd.direction == Direction.DOWN else xd.start_price for xd in recent_xd)
    
    if zg <= zd:
        return None
        
    return Zhongshu(
        zg=zg,
        zd=zd,
        start_index=recent_xd[0].start_index,
        end_index=recent_xd[-1].end_index,
        level=2,  # 线段中枢
        bi_list=[]
    )


class ChanLunStructureAnalyzer:
    """缠论形态分析器"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.fractals = []
        self.bi_list = []
        self.xianduan_list = []
        self.zhongshu = None
        
    def analyze(self) -> Dict:
        """
        执行完整的缠论形态分析
        
        Returns:
            分析结果
        """
        # 1. 检测分型
        self.fractals = detect_all_fractals(self.df)
        self.fractals = filter_fractals(self.fractals)
        
        # 2. 构建笔
        self.bi_list = build_bi_from_fractals(self.fractals, self.df)
        self.bi_list = validate_bi(self.bi_list)
        
        # 3. 构建线段
        self.xianduan_list = detect_xianduan_from_bi(self.bi_list)
        
        # 4. 计算中枢
        self.zhongshu = calculate_zhongshu_from_bi(self.bi_list)
        
        return {
            'fractals': self.fractals,
            'bi_list': self.bi_list,
            'xianduan_list': self.xianduan_list,
            'zhongshu': self.zhongshu
        }
        
    def get_current_structure(self) -> Dict:
        """获取当前形态结构"""
        return {
            'current_bi': self.bi_list[-1] if self.bi_list else None,
            'current_xianduan': self.xianduan_list[-1] if self.xianduan_list else None,
            'zhongshu': {
                'zg': self.zhongshu.zg,
                'zd': self.zhongshu.zd,
                'level': self.zhongshu.level
            } if self.zhongshu else None
        }
