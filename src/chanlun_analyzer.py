"""
缠论分析模块
功能：中枢计算、第三类买点识别、盘整背驰判断
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple


def calculate_zhongshu(df: pd.DataFrame, min_periods: int = 3) -> Optional[Dict]:
    """
    计算中枢
    
    中枢定义：至少连续3笔（或线段）的价格重叠区间
    ZG (Zhongshu Gong) = 中枢高点 = min(高点序列)
    ZD (Zhongshu Di) = 中枢低点 = max(低点序列)
    
    Args:
        df: K线数据，需包含 high, low 列
        min_periods: 最少笔数，默认3笔
        
    Returns:
        dict: {
            'zg': float,  # 中枢高点
            'zd': float,  # 中枢低点
            'middle': float,  # 中枢中轴
            'height': float  # 中枢高度
        }
    """
    if df is None or len(df) < min_periods:
        return None
        
    # 使用最近N根K线计算中枢
    recent_df = df.tail(min_periods * 2)  # 取更多数据确保准确性
    
    if recent_df.empty:
        return None
        
    # 中枢计算
    # ZG = 连续笔的重叠区间高点 = min(各笔高点)
    # ZD = 连续笔的重叠区间低点 = max(各笔低点)
    
    highs = recent_df['high'].values
    lows = recent_df['low'].values
    
    # 简化算法：使用滑动窗口寻找重叠区间
    zg = np.min(highs[-min_periods:])
    zd = np.max(lows[-min_periods:])
    
    # 确保中枢有效（ZG > ZD）
    if zg <= zd:
        # 调整计算方式
        zg = np.percentile(highs[-min_periods*2:], 70)
        zd = np.percentile(lows[-min_periods*2:], 30)
        
    if zg <= zd:
        return None
        
    middle = (zg + zd) / 2
    height = zg - zd
    
    return {
        'zg': round(zg, 2),
        'zd': round(zd, 2),
        'middle': round(middle, 2),
        'height': round(height, 2)
    }


def detect_third_buy_point(
    prices: Dict[str, float],
    zg: float
) -> Dict:
    """
    检测第三类买点
    
    第三类买点定义：
    1. 价格向上离开中枢（突破ZG）
    2. 回抽不破ZG（回抽低点 > ZD，且收盘价 > ZG）
    3. 重新向上时买入
    
    Args:
        prices: {
            'breakout_price': 突破价格,
            'pullback_price': 回抽价格,
            'turnaround_price': 反转价格
        }
        zg: 中枢高点
        
    Returns:
        dict: {
            'is_third_buy': bool,
            'pullback_valid': bool,
            'reason': str
        }
    """
    if not prices or zg <= 0:
        return {
            'is_third_buy': False,
            'pullback_valid': False,
            'reason': 'Invalid parameters'
        }
        
    breakout_price = prices.get('breakout_price', 0)
    pullback_price = prices.get('pullback_price', 0)
    turnaround_price = prices.get('turnaround_price', 0)
    
    # 检查1：是否突破ZG
    if breakout_price <= zg:
        return {
            'is_third_buy': False,
            'pullback_valid': False,
            'reason': 'Price did not break ZG'
        }
        
    # 检查2：回抽是否不破ZG
    pullback_valid = pullback_price > zg
    if not pullback_valid:
        return {
            'is_third_buy': False,
            'pullback_valid': False,
            'reason': f'Pullback {pullback_price} broke ZG {zg}'
        }
        
    # 检查3：是否重新向上
    if turnaround_price <= pullback_price:
        return {
            'is_third_buy': False,
            'pullback_valid': True,
            'reason': 'Not turning upward yet'
        }
        
    return {
        'is_third_buy': True,
        'pullback_valid': True,
        'reason': 'Valid third buy point'
    }


def check_divergence(
    macd_areas: Dict[str, float],
    price_new_high: bool = False
) -> Dict:
    """
    判断盘整背驰
    
    盘整背驰定义：
    在盘整中，如果离开段力度 > 回来段力度，且回来段未创新高/新低，
    则可能形成背驰。
    
    使用MACD面积判断力度：
    - 离开段MACD面积大，回来段MACD面积小，且价格未创新高 → 背驰
    
    Args:
        macd_areas: {
            'departure': 离开段MACD面积,
            'pullback': 回抽段MACD面积,
            'return': 重新向上段MACD面积
        }
        price_new_high: 价格是否创新高
        
    Returns:
        dict: {
            'has_divergence': bool,
            'signal_filtered': bool,
            'reason': str
        }
    """
    if not macd_areas:
        return {
            'has_divergence': False,
            'signal_filtered': False,
            'reason': 'No MACD data'
        }
        
    departure = macd_areas.get('departure', 0)
    pullback = macd_areas.get('pullback', 0)
    return_area = macd_areas.get('return', 0)
    
    # 判断力度是否减弱
    # 如果重新向上的力度 < 离开段的力度，且价格未创新高 → 背驰
    if return_area > 0 and departure > 0:
        strength_ratio = return_area / departure
        
        # 力度减弱（< 0.8 认为是明显减弱）
        if strength_ratio < 0.8 and not price_new_high:
            return {
                'has_divergence': True,
                'signal_filtered': True,
                'reason': f'Divergence detected: return/departure = {strength_ratio:.2f}'
            }
            
    return {
        'has_divergence': False,
        'signal_filtered': False,
        'reason': 'No divergence'
    }


def confirm_5min_signal(df_5min: pd.DataFrame) -> Dict:
    """
    5分钟K线买点确认
    
    在5分钟K线上确认买点形态：
    1. 价格从低点开始向上
    2. 形成底分型（底分型：中间K线低点最低）
    3. 成交量放大
    
    Args:
        df_5min: 5分钟K线数据
        
    Returns:
        dict: {
            'confirmed': bool,
            'signal_time': str,
            'signal_price': float
        }
    """
    if df_5min is None or len(df_5min) < 3:
        return {
            'confirmed': False,
            'signal_time': '',
            'signal_price': 0
        }
        
    # 检查最后几根K线是否形成底分型
    last_3 = df_5min.tail(3)
    
    # 底分型判断：中间K线的低点最低
    low1 = last_3.iloc[0]['low']
    low2 = last_3.iloc[1]['low']
    low3 = last_3.iloc[2]['low']
    
    is_bottom_fractal = (low2 < low1) and (low2 < low3)
    
    if not is_bottom_fractal:
        return {
            'confirmed': False,
            'signal_time': '',
            'signal_price': 0
        }
        
    # 检查是否向上突破
    close1 = last_3.iloc[0]['close']
    close3 = last_3.iloc[2]['close']
    is_upward = close3 > close1
    
    if not is_upward:
        return {
            'confirmed': False,
            'signal_time': '',
            'signal_price': 0
        }
        
    return {
        'confirmed': True,
        'signal_time': last_3.iloc[2].get('time', last_3.iloc[2].get('date', '')),
        'signal_price': last_3.iloc[2]['close']
    }


class ChanLunAnalyzer:
    """缠论分析器"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.zhongshu = None
        
    def analyze(self) -> Dict:
        """执行完整分析"""
        # 计算中枢
        self.zhongshu = calculate_zhongshu(self.df)
        
        if not self.zhongshu:
            return {
                'status': 'failed',
                'reason': 'Cannot calculate zhongshu'
            }
            
        return {
            'status': 'success',
            'zhongshu': self.zhongshu
        }
        
    def find_third_buy_points(self) -> List[Dict]:
        """
        寻找第三类买点
        
        Returns:
            买点信号列表
        """
        if self.df is None or len(self.df) < 10:
            return []
            
        signals = []
        
        # 计算中枢
        self.zhongshu = calculate_zhongshu(self.df)
        if not self.zhongshu:
            return []
            
        zg = self.zhongshu['zg']
        
        # 遍历寻找突破-回抽-反转形态
        for i in range(5, len(self.df) - 2):
            window = self.df.iloc[i-5:i+3]
            
            # 寻找突破点
            breakout_idx = None
            for j in range(len(window)):
                if window.iloc[j]['high'] > zg:
                    breakout_idx = j
                    break
                    
            if breakout_idx is None:
                continue
                
            # 寻找回抽点
            after_breakout = window.iloc[breakout_idx:]
            pullback_idx = after_breakout['low'].idxmin()
            pullback_price = after_breakout.loc[pullback_idx, 'low']
            
            # 检查回抽是否不破ZG
            if pullback_price <= zg:
                continue
                
            # 检查是否重新向上
            last_price = window.iloc[-1]['close']
            if last_price <= pullback_price:
                continue
                
            # 确认买点
            prices = {
                'breakout_price': window.iloc[breakout_idx]['high'],
                'pullback_price': pullback_price,
                'turnaround_price': last_price
            }
            
            buy_point = detect_third_buy_point(prices, zg)
            if buy_point['is_third_buy']:
                signals.append({
                    'date': window.iloc[-1].get('date', ''),
                    'price': last_price,
                    'zhongshu': self.zhongshu,
                    'buy_point_info': buy_point
                })
                
        return signals
