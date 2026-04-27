"""
涨停识别模块
功能：识别涨停板、判断中枢突破、时间窗口过滤
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple


# 涨停阈值
LIMIT_UP_THRESHOLD = 9.9  # 涨幅阈值（%）


def detect_limit_up(df: pd.DataFrame) -> Optional[Dict]:
    """
    检测涨停板
    
    Args:
        df: 日K线数据，需包含 close, pct_change 列
        
    Returns:
        dict: {
            'is_limit_up': bool,
            'pct_change': float,
            'limit_up_date': str,
            'limit_up_price': float
        }
    """
    if df is None or df.empty:
        return None
        
    # 确保数据按日期排序
    if 'date' in df.columns:
        df = df.sort_values('date')
        
    # 获取最后一行数据
    last_row = df.iloc[-1]
    
    # 涨停判断
    pct_change = last_row.get('pct_change', 0)
    if pd.isna(pct_change):
        # 如果没有 pct_change 列，手动计算
        if len(df) >= 2:
            prev_close = df.iloc[-2]['close']
            curr_close = last_row['close']
            pct_change = ((curr_close - prev_close) / prev_close) * 100
        else:
            pct_change = 0
    
    is_limit_up = pct_change >= LIMIT_UP_THRESHOLD
    
    return {
        'is_limit_up': is_limit_up,
        'pct_change': round(pct_change, 2),
        'limit_up_date': last_row.get('date', ''),
        'limit_up_price': last_row['close']
    }


def is_limit_up(pct_change: float) -> bool:
    """
    判断单日是否涨停
    
    Args:
        pct_change: 涨幅百分比
        
    Returns:
        是否涨停
    """
    return pct_change >= LIMIT_UP_THRESHOLD


def check_zg_breakout(price: float, zg: float) -> Dict:
    """
    判断是否突破中枢高点（ZG）
    
    Args:
        price: 当前价格
        zg: 中枢高点（Zhongshu Gong）
        
    Returns:
        dict: {
            'breaks_zg': bool,
            'breakout_pct': float  # 突破幅度（%）
        }
    """
    if zg <= 0:
        return {'breaks_zg': False, 'breakout_pct': 0}
        
    breaks_zg = price > zg
    breakout_pct = ((price - zg) / zg) * 100 if breaks_zg else 0
    
    return {
        'breaks_zg': breaks_zg,
        'breakout_pct': round(breakout_pct, 2)
    }


def filter_by_time_window(
    limit_up_date: str,
    current_date: str,
    min_days: int = 3,
    max_days: int = 5
) -> bool:
    """
    时间窗口过滤
    
    判断涨停日期是否在当前日期的前 min_days 到 max_days 天内
    
    Args:
        limit_up_date: 涨停日期，格式 "2026-04-12"
        current_date: 当前日期，格式 "2026-04-14"
        min_days: 最小天数
        max_days: 最大天数
        
    Returns:
        是否在时间窗口内
    """
    try:
        limit_dt = datetime.strptime(limit_up_date, "%Y-%m-%d")
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        
        days_diff = (current_dt - limit_dt).days
        
        return min_days <= days_diff <= max_days
        
    except Exception:
        return False


def find_recent_limit_ups(
    df: pd.DataFrame,
    current_date: str,
    window_days: int = 5
) -> pd.DataFrame:
    """
    查找最近N天内的所有涨停
    
    Args:
        df: 日K线数据
        current_date: 当前日期
        window_days: 时间窗口（天）
        
    Returns:
        包含涨停信息的DataFrame
    """
    if df is None or df.empty:
        return pd.DataFrame()
        
    # 确保有 pct_change 列
    if 'pct_change' not in df.columns and len(df) >= 2:
        df = df.copy()
        df['pct_change'] = df['close'].pct_change() * 100
        
    # 筛选涨停
    limit_ups = df[df['pct_change'] >= LIMIT_UP_THRESHOLD].copy()
    
    if limit_ups.empty:
        return pd.DataFrame()
        
    # 时间窗口过滤
    try:
        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        limit_ups['date_dt'] = pd.to_datetime(limit_ups['date'])
        limit_ups = limit_ups[
            (current_dt - limit_ups['date_dt']).dt.days <= window_days
        ]
        limit_ups = limit_ups.drop(columns=['date_dt'])
    except Exception:
        pass
        
    return limit_ups


def validate_limit_up_with_zg_breakout(
    df: pd.DataFrame,
    zg: float,
    current_date: str
) -> Optional[Dict]:
    """
    验证涨停是否伴随中枢突破
    
    Args:
        df: 日K线数据
        zg: 中枢高点
        current_date: 当前日期
        
    Returns:
        验证结果，包含涨停信息和突破状态
    """
    # 查找涨停
    limit_up_info = detect_limit_up(df)
    if not limit_up_info or not limit_up_info['is_limit_up']:
        return None
        
    # 检查时间窗口
    if not filter_by_time_window(limit_up_info['limit_up_date'], current_date):
        return None
        
    # 检查中枢突破
    breakout_info = check_zg_breakout(limit_up_info['limit_up_price'], zg)
    if not breakout_info['breaks_zg']:
        return None
        
    return {
        **limit_up_info,
        **breakout_info,
        'valid': True
    }
