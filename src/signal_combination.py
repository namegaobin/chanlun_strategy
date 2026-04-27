"""
多信号组合策略模块

FU-011: 多信号组合策略（根据市场状态选择信号类型）
BB-OPT-004: 新建 signal_combination.py 实现多信号组合
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.signal_detector import Signal, SignalType


# 信号选择相关常量
MIN_CONFIDENCE_FOR_DOWNTREND_BUY1 = 70  # 下跌趋势中 BUY1 最低置信度
MAX_SIDEWAYS_SIGNALS = 3  # 震荡市最大信号数量

# 仓位管理相关常量
DEFAULT_MAX_TOTAL_POSITION = 0.8  # 默认最大总仓位
MAX_SINGLE_SIGNAL_POSITION = 0.3  # 单信号最大仓位


def select_signals_by_market_environment(
    signals: List[Signal],
    market_env: Dict[str, Any]
) -> List[Signal]:
    """
    根据市场环境选择信号
    
    Args:
        signals: 信号列表
        market_env: 市场环境信息
        
    Returns:
        选择后的信号列表
    """
    if not signals:
        return []
    
    environment = market_env.get('environment', 'neutral')
    trend_direction = market_env.get('trend_direction', 'none')
    
    # 根据环境类型选择信号
    if environment == 'trending':
        if trend_direction == 'up':
            # 上涨趋势 → 选择第二、第三类买点
            return _select_for_uptrend(signals)
        else:
            # 下跌趋势 → 选择第一类买点
            return _select_for_downtrend(signals)
    elif environment == 'sideways':
        # 震荡市 → 选择第一类买点
        return _select_for_sideways(signals)
    else:
        # 中性市场 → 接受所有买入信号
        return _select_for_neutral(signals)


def _select_for_uptrend(signals: List[Signal]) -> List[Signal]:
    """上涨趋势选择信号"""
    selected = []
    
    for signal in signals:
        sig_type = signal.signal_type
        
        # 只选择买入信号
        if sig_type in [SignalType.BUY_2, SignalType.BUY_3]:
            # 添加过滤原因
            signal.metadata['filter_reasons'] = {
                'BUY_1': 'trending_uptrend_no_bottom_fishing'
            }
            selected.append(signal)
    
    # 按优先级排序：BUY_3 > BUY_2，然后按置信度降序
    type_priority = {SignalType.BUY_3: 0, SignalType.BUY_2: 1}
    selected.sort(key=lambda s: (type_priority.get(s.signal_type, 99), -s.confidence))
    return selected


def _select_for_downtrend(signals: List[Signal]) -> List[Signal]:
    """下跌趋势选择信号"""
    selected = []
    
    for signal in signals:
        sig_type = signal.signal_type
        
        # 只选择高置信度的第一类买点
        if sig_type == SignalType.BUY_1 and signal.confidence >= MIN_CONFIDENCE_FOR_DOWNTREND_BUY1:
            signal.metadata['filter_reasons'] = {
                'BUY_2': 'downtrend_no_chasing',
                'BUY_3': 'downtrend_no_chasing'
            }
            selected.append(signal)
    
    # 按置信度降序
    selected.sort(key=lambda s: -s.confidence)
    return selected


def _select_for_sideways(signals: List[Signal]) -> List[Signal]:
    """震荡市选择信号"""
    selected = []
    
    for signal in signals:
        sig_type = signal.signal_type
        
        # 只选择第一类买点
        if sig_type == SignalType.BUY_1:
            selected.append(signal)
    
    # 按置信度降序，最多指定数量
    selected.sort(key=lambda s: -s.confidence)
    return selected[:MAX_SIDEWAYS_SIGNALS]


def _select_for_neutral(signals: List[Signal]) -> List[Signal]:
    """中性市场选择信号"""
    selected = []
    
    for signal in signals:
        sig_type = signal.signal_type
        
        # 接受所有买入信号
        if sig_type in [SignalType.BUY_1, SignalType.BUY_2, SignalType.BUY_3]:
            selected.append(signal)
    
    return selected


def select_signals_with_position(
    signals: List[Signal],
    market_env: Dict[str, Any],
    max_total_position: float = DEFAULT_MAX_TOTAL_POSITION
) -> List[Signal]:
    """
    带仓位管理的信号选择
    
    Args:
        signals: 信号列表
        market_env: 市场环境
        max_total_position: 最大总仓位
        
    Returns:
        选择后的信号列表（带仓位信息）
    """
    # 先选择信号
    selected = select_signals_by_market_environment(signals, market_env)
    
    if not selected:
        return []
    
    # 计算每个信号的仓位
    total_position = 0.0
    result = []
    
    for signal in selected:
        # 单个信号仓位 = 剩余仓位 / 信号数量，但不超过最大值
        remaining = max_total_position - total_position
        position_size = min(
            MAX_SINGLE_SIGNAL_POSITION,
            remaining / max(len(selected) - len(result), 1)
        )
        
        if total_position + position_size <= max_total_position:
            signal.metadata['position_size'] = position_size
            result.append(signal)
            total_position += position_size
    
    return result


def calculate_zhongshu_overlap_ratio(zs1: Any, zs2: Any) -> float:
    """
    计算中枢重叠比例
    
    Args:
        zs1: 中枢1
        zs2: 中枢2
        
    Returns:
        重叠比例
    """
    # 重叠区间
    overlap_low = max(zs1.zd, zs2.zd)
    overlap_high = min(zs1.zg, zs2.zg)
    
    if overlap_high <= overlap_low:
        return 0.0
    
    # 重叠长度
    overlap_range = overlap_high - overlap_low
    
    # 最小中枢高度
    min_height = min(zs1.zg - zs1.zd, zs2.zg - zs2.zd)
    
    if min_height <= 0:
        return 0.0
    
    return overlap_range / min_height


def filter_signals_by_type(
    signals: List[Signal],
    signal_types: List[SignalType]
) -> List[Signal]:
    """
    按类型过滤信号
    
    Args:
        signals: 信号列表
        signal_types: 允许的信号类型列表
        
    Returns:
        过滤后的信号列表
    """
    return [s for s in signals if s.signal_type in signal_types]
