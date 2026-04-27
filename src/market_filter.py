"""
大盘环境过滤模块
功能：牛市/熊市/震荡市识别、策略参数自适应调整
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from enum import Enum


class MarketStatus(Enum):
    """市场状态"""
    BULL = "bull"           # 牛市
    BEAR = "bear"           # 熊市
    SIDEWAYS = "sideways"   # 震荡市
    NEUTRAL = "neutral"     # 中性（数据不足）


class TrendStatus(Enum):
    """趋势状态"""
    UP = "up"       # 上涨
    DOWN = "down"   # 下跌
    FLAT = "flat"   # 横盘


# 市场环境策略参数映射
MARKET_STRATEGY_PARAMS = {
    MarketStatus.BULL: {
        'take_profit': 0.20,      # 止盈20%
        'stop_loss': 0.08,        # 止损8%
        'max_position': 0.80,     # 最大仓位80%
        'max_stocks': 10,         # 最多10只股票
        'signal_filter': 'loose'  # 信号过滤宽松
    },
    MarketStatus.BEAR: {
        'take_profit': 0.10,
        'stop_loss': 0.03,
        'max_position': 0.30,
        'max_stocks': 5,
        'signal_filter': 'strict'  # 信号过滤严格
    },
    MarketStatus.SIDEWAYS: {
        'take_profit': 0.15,
        'stop_loss': 0.05,
        'max_position': 0.50,
        'max_stocks': 7,
        'signal_filter': 'normal'
    },
    MarketStatus.NEUTRAL: {
        'take_profit': 0.15,
        'stop_loss': 0.05,
        'max_position': 0.50,
        'max_stocks': 7,
        'signal_filter': 'normal'
    }
}


def calculate_ma_status(df: pd.DataFrame, price_col: str = 'close') -> Dict:
    """
    计算均线状态
    
    Args:
        df: K线数据
        price_col: 价格列名
        
    Returns:
        dict: {
            'ma5', 'ma10', 'ma20', 'ma60',
            'ma_bull': bool,  # 均线多头排列
            'ma_bear': bool   # 均线空头排列
        }
    """
    if len(df) < 60:
        return {
            'ma5': None, 'ma10': None, 'ma20': None, 'ma60': None,
            'ma_bull': False, 'ma_bear': False
        }
        
    prices = df[price_col]
    
    ma5 = prices.rolling(5).mean().iloc[-1]
    ma10 = prices.rolling(10).mean().iloc[-1]
    ma20 = prices.rolling(20).mean().iloc[-1]
    ma60 = prices.rolling(60).mean().iloc[-1]
    
    current_price = prices.iloc[-1]
    
    # 多头排列：MA5 > MA10 > MA20 > MA60，且价格在所有均线之上
    ma_bull = (ma5 > ma10 > ma20 > ma60) and (current_price > ma5)
    
    # 空头排列：MA5 < MA10 < MA20 < MA60，且价格在所有均线之下
    ma_bear = (ma5 < ma10 < ma20 < ma60) and (current_price < ma5)
    
    return {
        'ma5': round(ma5, 2),
        'ma10': round(ma10, 2),
        'ma20': round(ma20, 2),
        'ma60': round(ma60, 2),
        'ma_bull': ma_bull,
        'ma_bear': ma_bear
    }


def calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
    """
    计算ADX（平均趋向指数）
    
    ADX > 25 表示有明确趋势
    ADX < 20 表示无明确趋势
    
    Args:
        df: K线数据
        period: 计算周期
        
    Returns:
        ADX值
    """
    if len(df) < period + 1:
        return 0
        
    high = df['high']
    low = df['low']
    close = df['close']
    
    # 计算+DM和-DM
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    # 计算TR
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 平滑
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    
    # 计算DX和ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean().iloc[-1]
    
    return adx if not pd.isna(adx) else 0


def detect_market_trend(df: pd.DataFrame, period: int = 20) -> TrendStatus:
    """
    检测市场趋势
    
    Args:
        df: K线数据
        period: 判断周期
        
    Returns:
        TrendStatus
    """
    if len(df) < period:
        return TrendStatus.FLAT
        
    prices = df['close']
    
    # 计算趋势斜率
    y = prices.tail(period).values
    x = np.arange(len(y))
    
    slope = np.polyfit(x, y, 1)[0]
    
    # 标准化斜率
    avg_price = np.mean(y)
    normalized_slope = slope / avg_price * 100  # 百分比
    
    # 判断趋势
    if normalized_slope > 0.5:  # 斜率 > 0.5%
        return TrendStatus.UP
    elif normalized_slope < -0.5:
        return TrendStatus.DOWN
    else:
        return TrendStatus.FLAT


def detect_market_environment(
    df: pd.DataFrame,
    use_adx: bool = True
) -> Dict:
    """
    检测市场环境
    
    综合判断：
    1. 均线排列状态
    2. ADX趋势强度
    3. 价格趋势斜率
    
    Args:
        df: 大盘指数数据（沪深300或上证指数）
        use_adx: 是否使用ADX
        
    Returns:
        dict: {
            'status': MarketStatus,
            'trend': TrendStatus,
            'ma_status': dict,
            'adx': float,
            'confidence': float  # 判断置信度
        }
    """
    if len(df) < 60:
        return {
            'status': MarketStatus.NEUTRAL,
            'trend': TrendStatus.FLAT,
            'ma_status': {},
            'adx': 0,
            'confidence': 0
        }
        
    # 1. 均线状态
    ma_status = calculate_ma_status(df)
    
    # 2. 趋势
    trend = detect_market_trend(df)
    
    # 3. ADX
    adx = calculate_adx(df) if use_adx else 25
    
    # 综合判断
    status = MarketStatus.NEUTRAL
    confidence = 0
    
    if ma_status['ma_bull']:
        status = MarketStatus.BULL
        confidence = 0.8
    elif ma_status['ma_bear']:
        status = MarketStatus.BEAR
        confidence = 0.8
    elif adx < 20:
        # ADX低，无明确趋势
        status = MarketStatus.SIDEWAYS
        confidence = 0.6
    elif trend == TrendStatus.UP and adx > 25:
        status = MarketStatus.BULL
        confidence = 0.6
    elif trend == TrendStatus.DOWN and adx > 25:
        status = MarketStatus.BEAR
        confidence = 0.6
    else:
        status = MarketStatus.SIDEWAYS
        confidence = 0.5
        
    return {
        'status': status,
        'trend': trend,
        'ma_status': ma_status,
        'adx': round(adx, 2),
        'confidence': confidence
    }


def get_strategy_params(market_status: MarketStatus) -> Dict:
    """
    根据市场环境获取策略参数
    
    Args:
        market_status: 市场状态
        
    Returns:
        策略参数字典
    """
    return MARKET_STRATEGY_PARAMS.get(market_status, MARKET_STRATEGY_PARAMS[MarketStatus.NEUTRAL])


def should_filter_signal(
    signal: Dict,
    market_env: Dict
) -> Tuple[bool, str]:
    """
    判断信号是否应该被过滤
    
    Args:
        signal: 买点信号
        market_env: 市场环境
        
    Returns:
        (是否过滤, 原因)
    """
    status = market_env.get('status', MarketStatus.NEUTRAL)
    params = get_strategy_params(status)
    
    filter_level = params.get('signal_filter', 'normal')
    
    # 熊市严格过滤
    if filter_level == 'strict':
        # 只接受最强信号
        if not signal.get('strong_signal', False):
            return True, f"Signal filtered in {status.value} market (strict filter)"
            
    # 牛市宽松过滤
    if filter_level == 'loose':
        # 接受所有信号
        return False, "Signal accepted in bull market"
        
    # 震荡市正常过滤
    return False, "Signal accepted"


class MarketFilter:
    """市场环境过滤器"""
    
    def __init__(self, index_code: str = "sh.000300"):
        """
        Args:
            index_code: 大盘指数代码，默认沪深300
        """
        self.index_code = index_code
        self.market_env = None
        self.strategy_params = None
        
    def update(self, df: pd.DataFrame):
        """更新市场环境"""
        self.market_env = detect_market_environment(df)
        self.strategy_params = get_strategy_params(self.market_env['status'])
        
    def get_status(self) -> MarketStatus:
        """获取当前市场状态"""
        return self.market_env.get('status', MarketStatus.NEUTRAL) if self.market_env else MarketStatus.NEUTRAL
        
    def get_params(self) -> Dict:
        """获取策略参数"""
        return self.strategy_params or get_strategy_params(MarketStatus.NEUTRAL)
        
    def filter_signal(self, signal: Dict) -> Tuple[bool, str]:
        """过滤信号"""
        if not self.market_env:
            return False, "No market environment data"
        return should_filter_signal(signal, self.market_env)
