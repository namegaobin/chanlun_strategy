"""
市场环境识别模块 V2
基于中枢位置判断趋势/震荡

FU-010: 市场环境识别（基于中枢位置判断趋势/震荡）
BB-OPT-001: 重写 market_filter.py 使用中枢判断
"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import pandas as pd

if TYPE_CHECKING:
    from chanlun_strategy.chanlun_structure_v2 import Zhongshu


# 重叠阈值：重叠比例 >= 此值判定为震荡市
OVERLAP_THRESHOLD = 0.3

# 置信度常量
CONFIDENCE_NEUTRAL = 0.0
CONFIDENCE_SINGLE_ZHONGSHU = 0.5
CONFIDENCE_SIDEWAYS = 0.75
CONFIDENCE_TRENDING = 0.85
CONFIDENCE_TRENDING_SLIGHT_OVERLAP = 0.8


def detect_market_environment_v2(
    df: pd.DataFrame,
    zhongshu_list: List['Zhongshu']
) -> Dict[str, Any]:
    """
    检测市场环境（基于中枢位置）
    
    Args:
        df: K线数据
        zhongshu_list: 中枢列表
        
    Returns:
        市场环境信息字典
    """
    # 无中枢 → 中性
    if not zhongshu_list or len(zhongshu_list) == 0:
        return {
            'environment': 'neutral',
            'trend_direction': 'none',
            'zhongshu_overlap': False,
            'confidence': CONFIDENCE_NEUTRAL
        }
    
    # 单中枢 → 盘整
    if len(zhongshu_list) == 1:
        return {
            'environment': 'consolidation',
            'trend_direction': 'none',
            'zhongshu_overlap': False,
            'confidence': CONFIDENCE_SINGLE_ZHONGSHU
        }
    
    # 多个中枢，检查重叠
    # 只检查相邻的两个中枢
    zs1 = zhongshu_list[0]
    zs2 = zhongshu_list[1]
    
    # 计算重叠
    overlap_low = max(zs1.zd, zs2.zd)
    overlap_high = min(zs1.zg, zs2.zg)
    
    # 重叠区间存在
    if overlap_high > overlap_low:
        # 计算重叠比例
        min_height = min(zs1.zg - zs1.zd, zs2.zg - zs2.zd)
        overlap_range = overlap_high - overlap_low
        overlap_ratio = overlap_range / min_height if min_height > 0 else 0
        
        # 重叠比例 >= 30% → 震荡市
        if overlap_ratio >= OVERLAP_THRESHOLD:
            return {
                'environment': 'sideways',
                'trend_direction': 'none',
                'zhongshu_overlap': True,
                'overlap_range': {
                    'low': overlap_low,
                    'high': overlap_high
                },
                'overlap_ratio': overlap_ratio,
                'confidence': CONFIDENCE_SIDEWAYS,
                'all_zhongshus_overlapping': len(zhongshu_list) > 2
            }
    
    # 不重叠或重叠不足 → 趋势市
    # 判断趋势方向
    if zs2.zd > zs1.zg:
        # 第二个中枢在第一个中枢之上 → 上涨趋势
        trend_direction = 'up'
        confidence = CONFIDENCE_TRENDING
    elif zs2.zg < zs1.zd:
        # 第二个中枢在第一个中枢之下 → 下跌趋势
        trend_direction = 'down'
        confidence = CONFIDENCE_TRENDING
    else:
        # 有轻微重叠但不足30%
        trend_direction = 'up' if zs2.zd > zs1.zd else 'down'
        confidence = CONFIDENCE_TRENDING_SLIGHT_OVERLAP
    
    return {
        'environment': 'trending',
        'trend_direction': trend_direction,
        'zhongshu_overlap': False,
        'overlap_ratio': 0.0,
        'confidence': confidence
    }
