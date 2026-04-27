"""
缠论形态识别模块 V2 - 重构辅助函数
用于 Phase 3: REFACTOR

提取穿越中轴检查逻辑为独立函数，提高代码可读性和复用性
"""
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    """方向"""
    UP = "up"
    DOWN = "down"


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
    kline_count: int


def validate_cross_middle_line(
    bi_list: list,
    direction: Direction,
    end_price: float,
    tolerance: float = 0.1
) -> bool:
    """
    验证笔是否穿越前一笔的中轴
    
    Args:
        bi_list: 已生成的笔列表
        direction: 当前笔方向
        end_price: 当前笔终点价格
        tolerance: 允许的误差比例（默认10%）
        
    Returns:
        True 如果通过中轴检查或无需检查，False 如果未通过
        
    Business Rule:
        - 前3笔不要求穿越中轴（尚未形成中枢）
        - 第4笔开始，必须穿越前一笔中轴
        - 向上笔：终点应 > 前笔中轴 * (1 - tolerance)
        - 向下笔：终点应 < 前笔中轴 * (1 + tolerance)
    """
    # 前3笔不检查穿越中轴
    if not bi_list or len(bi_list) < 3:
        return True
    
    prev_bi = bi_list[-1]
    mid_line = (prev_bi.high + prev_bi.low) / 2
    
    if direction == Direction.UP:
        # 向上笔：终点应高于中轴（允许误差）
        return end_price >= mid_line * (1 - tolerance)
    else:
        # 向下笔：终点应低于中轴（允许误差）
        return end_price <= mid_line * (1 + tolerance)


def validate_bi_direction(
    direction: Direction,
    start_price: float,
    end_price: float
) -> bool:
    """
    验证笔的方向一致性
    
    Args:
        direction: 笔的方向
        start_price: 起点价格
        end_price: 终点价格
        
    Returns:
        True 如果方向一致，False 否则
        
    Business Rule:
        - 向上笔：终点价格 > 起点价格
        - 向下笔：终点价格 < 起点价格
    """
    if direction == Direction.UP:
        return end_price > start_price
    else:
        return end_price < start_price


def validate_bi_alternation(bi_list: list, direction: Direction) -> bool:
    """
    验证笔的顶底交替规则
    
    Args:
        bi_list: 已生成的笔列表
        direction: 当前笔方向
        
    Returns:
        True 如果满足顶底交替，False 如果违反
        
    Business Rule:
        相邻两笔方向必须相反
    """
    if not bi_list:
        return True
    
    return bi_list[-1].direction != direction
