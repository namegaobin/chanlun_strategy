#!/usr/bin/env python3
"""
缠论信号检测模块

实现第一类、第二类、第三类买卖点识别
基于缠论原文定义（第13-20课）

作者: TDD流水线
版本: 1.0.0
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False


class SignalType(Enum):
    """信号类型"""
    BUY_1 = "buy_1"      # 第一类买点
    BUY_2 = "buy_2"      # 第二类买点
    BUY_3 = "buy_3"      # 第三类买点
    SELL_1 = "sell_1"    # 第一类卖点
    SELL_2 = "sell_2"    # 第二类卖点
    SELL_3 = "sell_3"    # 第三类卖点


class TrendType(Enum):
    """趋势类型"""
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    CONSOLIDATION = "consolidation"


@dataclass
class Signal:
    """信号数据结构"""
    signal_type: SignalType
    price: float
    index: int
    datetime: Any
    confidence: float  # 置信度 0-100
    reason: str
    related_zhongshu: Optional[Any] = None  # 关联的中枢
    strength_ratio: Optional[float] = None  # 力度比（背驰信号）
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'signal_type': self.signal_type.value,
            'price': self.price,
            'index': self.index,
            'datetime': str(self.datetime),
            'confidence': self.confidence,
            'reason': self.reason,
            'strength_ratio': self.strength_ratio
        }


class SignalDetector:
    """缠论信号检测器
    
    实现完整的买卖点信号识别：
    - 第一类买点：下跌趋势背驰
    - 第二类买点：趋势反转确认
    - 第三类买点：突破中枢后回抽确认
    - 对应的三类卖点
    """
    
    def __init__(self,
                 divergence_threshold_trend: float = 0.9,
                 divergence_threshold_consolidation: float = 0.95,
                 macd_threshold: float = 0.8,
                 min_pullback_margin: float = 0.002):
        """
        Args:
            divergence_threshold_trend: 趋势背驰力度比阈值（默认0.9）
            divergence_threshold_consolidation: 盘整背驰力度比阈值（默认0.95）
            macd_threshold: MACD面积比阈值（默认0.8）
            min_pullback_margin: 回抽安全边际（默认0.2%）
        """
        self.divergence_threshold_trend = divergence_threshold_trend
        self.divergence_threshold_consolidation = divergence_threshold_consolidation
        self.macd_threshold = macd_threshold
        self.min_pullback_margin = min_pullback_margin
        
        # 缓存
        self._last_buy1_signal: Optional[Signal] = None
        self._last_sell1_signal: Optional[Signal] = None
    
    def detect_all_signals(self,
                          df: pd.DataFrame,
                          bi_list: List[Any],
                          zs_list: List[Any]) -> List[Signal]:
        """检测所有信号
        
        Args:
            df: K线数据
            bi_list: 笔列表
            zs_list: 中枢列表
            
        Returns:
            信号列表（按时间排序）
        """
        signals = []
        
        # 1. 检测第一类买卖点（背驰信号）
        signals.extend(self._detect_buy1_signals(df, bi_list, zs_list))
        signals.extend(self._detect_sell1_signals(df, bi_list, zs_list))
        
        # 2. 检测第二类买卖点（趋势确认）
        signals.extend(self._detect_buy2_signals(df, bi_list))
        signals.extend(self._detect_sell2_signals(df, bi_list))
        
        # 3. 检测第三类买卖点（中枢突破）
        signals.extend(self._detect_buy3_signals(df, bi_list, zs_list))
        signals.extend(self._detect_sell3_signals(df, bi_list, zs_list))
        
        # 按时间排序
        signals.sort(key=lambda s: s.index)
        
        return signals
    
    # =========================================================================
    # 第一类买点检测
    # =========================================================================
    
    def _detect_buy1_signals(self,
                            df: pd.DataFrame,
                            bi_list: List[Any],
                            zs_list: List[Any]) -> List[Signal]:
        """检测第一类买点
        
        条件：
        1. 处于下跌趋势
        2. 最后一个中枢的离开段发生背驰
        3. 离开段终点形成底分型
        
        Args:
            df: K线数据
            bi_list: 笔列表
            zs_list: 中枢列表
            
        Returns:
            第一类买点信号列表
        """
        signals = []
        
        if not zs_list or len(zs_list) < 1:
            return signals
        
        # 判断趋势类型
        trend = self._judge_trend(df, bi_list)
        if trend != TrendType.DOWNTREND:
            return signals
        
        # 检查每个中枢的背驰情况
        for i, zs in enumerate(zs_list):
            # 需要有离开段
            if not zs.exit_bi:
                continue
            
            # 离开段必须是向下笔
            if zs.exit_bi.direction.value != 'down':
                continue
            
            # 计算背驰
            is_diverged, strength_ratio, macd_ratio = self._check_divergence(
                df, bi_list, zs, direction='down'
            )
            
            if not is_diverged:
                continue
            
            # 确认底分型
            exit_idx = zs.exit_bi.end_index
            if exit_idx >= len(df) - 1:
                continue
            
            # 生成信号
            signal = Signal(
                signal_type=SignalType.BUY_1,
                price=df.iloc[exit_idx]['low'],
                index=exit_idx,
                datetime=df.iloc[exit_idx]['date'],
                confidence=self._calculate_confidence(
                    trend=trend,
                    strength_ratio=strength_ratio,
                    macd_ratio=macd_ratio
                ),
                reason='第一类买点：下跌趋势背驰',
                related_zhongshu=zs,
                strength_ratio=strength_ratio,
                metadata={
                    'macd_ratio': macd_ratio,
                    'zs_index': i
                }
            )
            
            signals.append(signal)
            self._last_buy1_signal = signal
        
        return signals
    
    # =========================================================================
    # 第一类卖点检测
    # =========================================================================
    
    def _detect_sell1_signals(self,
                             df: pd.DataFrame,
                             bi_list: List[Any],
                             zs_list: List[Any]) -> List[Signal]:
        """检测第一类卖点
        
        条件：
        1. 处于上涨趋势
        2. 最后一个中枢的离开段发生背驰
        3. 离开段终点形成顶分型
        
        Args:
            df: K线数据
            bi_list: 笔列表
            zs_list: 中枢列表
            
        Returns:
            第一类卖点信号列表
        """
        signals = []
        
        if not zs_list:
            return signals
        
        # 判断趋势类型
        trend = self._judge_trend(df, bi_list)
        if trend != TrendType.UPTREND:
            return signals
        
        # 检查每个中枢的背驰情况
        for i, zs in enumerate(zs_list):
            if not zs.exit_bi:
                continue
            
            if zs.exit_bi.direction.value != 'up':
                continue
            
            is_diverged, strength_ratio, macd_ratio = self._check_divergence(
                df, bi_list, zs, direction='up'
            )
            
            if not is_diverged:
                continue
            
            exit_idx = zs.exit_bi.end_index
            if exit_idx >= len(df) - 1:
                continue
            
            signal = Signal(
                signal_type=SignalType.SELL_1,
                price=df.iloc[exit_idx]['high'],
                index=exit_idx,
                datetime=df.iloc[exit_idx]['date'],
                confidence=self._calculate_confidence(
                    trend=trend,
                    strength_ratio=strength_ratio,
                    macd_ratio=macd_ratio
                ),
                reason='第一类卖点：上涨趋势背驰',
                related_zhongshu=zs,
                strength_ratio=strength_ratio,
                metadata={
                    'macd_ratio': macd_ratio,
                    'zs_index': i
                }
            )
            
            signals.append(signal)
            self._last_sell1_signal = signal
        
        return signals
    
    # =========================================================================
    # 第二类买点检测
    # =========================================================================
    
    def _detect_buy2_signals(self,
                            df: pd.DataFrame,
                            bi_list: List[Any]) -> List[Signal]:
        """检测第二类买点
        
        条件：
        1. 第一类买点已存在
        2. 回抽不破第一类买点价格
        3. 重新向上确认反转
        
        Args:
            df: K线数据
            bi_list: 笔列表
            
        Returns:
            第二类买点信号列表
        """
        signals = []
        
        if not self._last_buy1_signal:
            return signals
        
        buy1_price = self._last_buy1_signal.price
        buy1_idx = self._last_buy1_signal.index
        
        # 在第一类买点之后的笔中寻找
        for i, bi in enumerate(bi_list):
            if bi.start_index <= buy1_idx:
                continue
            
            # 找到向下笔回抽
            if bi.direction.value != 'down':
                continue
            
            # 回抽低点不能破第一类买点
            pullback_low = bi.low
            if pullback_low < buy1_price * (1 - self.min_pullback_margin):
                continue  # 破位，不形成第二类买点
            
            # 检查后续是否有向上笔确认
            if i + 1 >= len(bi_list):
                continue
            
            next_bi = bi_list[i + 1]
            if next_bi.direction.value != 'up':
                continue
            
            # 生成信号
            signal = Signal(
                signal_type=SignalType.BUY_2,
                price=pullback_low,
                index=bi.end_index,
                datetime=df.iloc[bi.end_index]['date'],
                confidence=75,  # 第二类买点相对安全
                reason=f'第二类买点：回抽不破前低（支撑={buy1_price:.2f}）',
                metadata={
                    'buy1_price': buy1_price,
                    'pullback_margin': (pullback_low - buy1_price) / buy1_price * 100
                }
            )
            
            signals.append(signal)
            break  # 只取第一个第二类买点
        
        return signals
    
    # =========================================================================
    # 第二类卖点检测
    # =========================================================================
    
    def _detect_sell2_signals(self,
                             df: pd.DataFrame,
                             bi_list: List[Any]) -> List[Signal]:
        """检测第二类卖点
        
        条件：
        1. 第一类卖点已存在
        2. 反弹不破第一类卖点价格
        3. 重新向下确认反转
        
        Args:
            df: K线数据
            bi_list: 笔列表
            
        Returns:
            第二类卖点信号列表
        """
        signals = []
        
        if not self._last_sell1_signal:
            return signals
        
        sell1_price = self._last_sell1_signal.price
        sell1_idx = self._last_sell1_signal.index
        
        for i, bi in enumerate(bi_list):
            if bi.start_index <= sell1_idx:
                continue
            
            if bi.direction.value != 'up':
                continue
            
            pullback_high = bi.high
            if pullback_high > sell1_price * (1 + self.min_pullback_margin):
                continue
            
            if i + 1 >= len(bi_list):
                continue
            
            next_bi = bi_list[i + 1]
            if next_bi.direction.value != 'down':
                continue
            
            signal = Signal(
                signal_type=SignalType.SELL_2,
                price=pullback_high,
                index=bi.end_index,
                datetime=df.iloc[bi.end_index]['date'],
                confidence=75,
                reason=f'第二类卖点：反弹不破前高（压力={sell1_price:.2f}）',
                metadata={
                    'sell1_price': sell1_price,
                    'pullback_margin': (sell1_price - pullback_high) / sell1_price * 100
                }
            )
            
            signals.append(signal)
            break
        
        return signals
    
    # =========================================================================
    # 第三类买点检测（已存在于 chanlun_structure_v2.py）
    # =========================================================================
    
    def _detect_buy3_signals(self,
                            df: pd.DataFrame,
                            bi_list: List[Any],
                            zs_list: List[Any]) -> List[Signal]:
        """检测第三类买点
        
        条件：
        1. 向上突破中枢ZG
        2. 回抽不破ZG
        
        Args:
            df: K线数据
            bi_list: 笔列表
            zs_list: 中枢列表
            
        Returns:
            第三类买点信号列表
        """
        signals = []
        
        for i, zs in enumerate(zs_list):
            if not zs.exit_bi:
                continue
            
            # 向上突破中枢
            if zs.exit_bi.direction.value != 'up':
                continue
            
            if zs.exit_bi.high <= zs.zg:
                continue
            
            # 找到回抽笔
            try:
                exit_idx = bi_list.index(zs.exit_bi)
                if exit_idx + 1 >= len(bi_list):
                    continue
                
                pullback_bi = bi_list[exit_idx + 1]
                if pullback_bi.direction.value != 'down':
                    continue
                
                # 回抽不破ZG
                if pullback_bi.low <= zs.zg:
                    continue
                
                signal = Signal(
                    signal_type=SignalType.BUY_3,
                    price=pullback_bi.low,
                    index=pullback_bi.end_index,
                    datetime=df.iloc[pullback_bi.end_index]['date'],
                    confidence=70,
                    reason=f'第三类买点：突破中枢后回抽不破ZG（ZG={zs.zg:.2f}）',
                    related_zhongshu=zs,
                    metadata={
                        'zs_index': i,
                        'zg': zs.zg,
                        'margin': (pullback_bi.low - zs.zg) / zs.zg * 100
                    }
                )
                
                signals.append(signal)
            except ValueError:
                continue
        
        return signals
    
    # =========================================================================
    # 第三类卖点检测
    # =========================================================================
    
    def _detect_sell3_signals(self,
                             df: pd.DataFrame,
                             bi_list: List[Any],
                             zs_list: List[Any]) -> List[Signal]:
        """检测第三类卖点
        
        条件：
        1. 向下突破中枢ZD
        2. 反弹不过ZD
        
        Args:
            df: K线数据
            bi_list: 笔列表
            zs_list: 中枢列表
            
        Returns:
            第三类卖点信号列表
        """
        signals = []
        
        for i, zs in enumerate(zs_list):
            if not zs.exit_bi:
                continue
            
            # 向下突破中枢
            if zs.exit_bi.direction.value != 'down':
                continue
            
            if zs.exit_bi.low >= zs.zd:
                continue
            
            # 找到反弹笔
            try:
                exit_idx = bi_list.index(zs.exit_bi)
                if exit_idx + 1 >= len(bi_list):
                    continue
                
                rebound_bi = bi_list[exit_idx + 1]
                if rebound_bi.direction.value != 'up':
                    continue
                
                # 反弹不过ZD
                if rebound_bi.high >= zs.zd:
                    continue
                
                signal = Signal(
                    signal_type=SignalType.SELL_3,
                    price=rebound_bi.high,
                    index=rebound_bi.end_index,
                    datetime=df.iloc[rebound_bi.end_index]['date'],
                    confidence=70,
                    reason=f'第三类卖点：跌破中枢后反弹不过ZD（ZD={zs.zd:.2f}）',
                    related_zhongshu=zs,
                    metadata={
                        'zs_index': i,
                        'zd': zs.zd,
                        'margin': (zs.zd - rebound_bi.high) / zs.zd * 100
                    }
                )
                
                signals.append(signal)
            except ValueError:
                continue
        
        return signals
    
    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    def _judge_trend(self, df: pd.DataFrame, bi_list: List[Any]) -> TrendType:
        """判断当前趋势类型
        
        Args:
            df: K线数据
            bi_list: 笔列表
            
        Returns:
            趋势类型
        """
        if len(bi_list) < 3:
            return TrendType.CONSOLIDATION
        
        # 比较最近几笔的高低点
        recent_bis = bi_list[-5:] if len(bi_list) >= 5 else bi_list
        
        # 计算高低点趋势
        highs = [bi.high for bi in recent_bis]
        lows = [bi.low for bi in recent_bis]
        
        # 简单趋势判断
        high_trend = np.mean(np.diff(highs))
        low_trend = np.mean(np.diff(lows))
        
        if high_trend > 0 and low_trend > 0:
            return TrendType.UPTREND
        elif high_trend < 0 and low_trend < 0:
            return TrendType.DOWNTREND
        else:
            return TrendType.CONSOLIDATION
    
    def _check_divergence(self,
                         df: pd.DataFrame,
                         bi_list: List[Any],
                         zs: Any,
                         direction: str) -> Tuple[bool, float, float]:
        """检查背驰
        
        缠论原文定义（第5课、第15课）：
        1. 力度 = 价格幅度 × 0.6 + 斜率 × 0.4
        2. 背驰 = 离开段力度 < 进入段力度
        
        Args:
            df: K线数据
            bi_list: 笔列表
            zs: 中枢
            direction: 方向 ('up' 或 'down')
            
        Returns:
            (是否背驰, 力度比, MACD面积比)
        """
        if not zs.enter_bi or not zs.exit_bi:
            return False, 1.0, 1.0
        
        # 计算力度（缠论原文定义）
        enter_strength = self._calculate_strength(df, zs.enter_bi)
        exit_strength = self._calculate_strength(df, zs.exit_bi)
        
        if enter_strength <= 0:
            return False, 1.0, 1.0
        
        strength_ratio = exit_strength / enter_strength
        
        # 计算MACD面积比（辅助）
        macd_ratio = self._calculate_macd_ratio(df, zs, direction)
        
        # 判断趋势类型
        trend = self._judge_trend(df, bi_list)
        
        # 背驰判定（缠论原文阈值）
        if trend == TrendType.UPTREND or trend == TrendType.DOWNTREND:
            threshold = self.divergence_threshold_trend  # 0.9
        else:
            threshold = self.divergence_threshold_consolidation  # 0.95
        
        is_diverged = strength_ratio < threshold
        
        # MACD辅助确认（不作为主要判断）
        macd_confirm = macd_ratio < self.macd_threshold
        
        # 综合判定
        if is_diverged:
            return True, strength_ratio, macd_ratio
        else:
            return False, strength_ratio, macd_ratio
    
    def _calculate_strength(self, df: pd.DataFrame, bi: Any) -> float:
        """计算笔的力度
        
        缠论原文定义（第5课）：
        力度 = 价格幅度 × 0.6 + 斜率 × 0.4
        
        Args:
            df: K线数据
            bi: 笔对象
            
        Returns:
            力度值
        """
        # 价格幅度
        price_range = abs(bi.high - bi.low) / bi.low * 100  # 百分比
        
        # 斜率（K线数量）
        bar_count = abs(bi.end_index - bi.start_index) + 1
        slope = price_range / bar_count if bar_count > 0 else 0
        
        # 力度 = 价格幅度 × 0.6 + 斜率 × 0.4
        strength = price_range * 0.6 + slope * 0.4
        
        return strength
    
    def _calculate_macd_ratio(self,
                             df: pd.DataFrame,
                             zs: Any,
                             direction: str) -> float:
        """计算MACD面积比
        
        Args:
            df: K线数据
            zs: 中枢
            direction: 方向
            
        Returns:
            MACD面积比
        """
        if not TALIB_AVAILABLE:
            # 降级使用简单计算
            return self._calculate_simple_macd_ratio(df, zs, direction)
        
        try:
            # 计算MACD
            close = df['close'].values
            macd, signal, hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            
            # 进入段MACD面积
            enter_start = max(0, zs.enter_bi.start_index)
            enter_end = min(len(df), zs.enter_bi.end_index + 1)
            
            # 离开段MACD面积
            exit_start = max(0, zs.exit_bi.start_index)
            exit_end = min(len(df), zs.exit_bi.end_index + 1)
            
            # 根据方向选择柱子
            if direction == 'down':
                # 下跌用负柱子
                enter_area = abs(np.sum(hist[enter_start:enter_end][hist[enter_start:enter_end] < 0]))
                exit_area = abs(np.sum(hist[exit_start:exit_end][hist[exit_start:exit_end] < 0]))
            else:
                # 上涨用正柱子
                enter_area = np.sum(hist[enter_start:enter_end][hist[enter_start:enter_end] > 0])
                exit_area = np.sum(hist[exit_start:exit_end][hist[exit_start:exit_end] > 0])
            
            if enter_area > 0:
                return exit_area / enter_area
            else:
                return 1.0
        except Exception:
            return 1.0
    
    def _calculate_simple_macd_ratio(self,
                                    df: pd.DataFrame,
                                    zs: Any,
                                    direction: str) -> float:
        """简单MACD面积比计算（无TA-Lib时使用）
        
        使用EMA近似MACD
        """
        try:
            close = df['close'].values
            
            # 计算EMA
            ema12 = pd.Series(close).ewm(span=12, adjust=False).mean()
            ema26 = pd.Series(close).ewm(span=26, adjust=False).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9, adjust=False).mean()
            hist = (dif - dea) * 2  # MACD柱
            
            # 进入段MACD面积
            enter_start = max(0, zs.enter_bi.start_index)
            enter_end = min(len(df), zs.enter_bi.end_index + 1)
            
            # 离开段MACD面积
            exit_start = max(0, zs.exit_bi.start_index)
            exit_end = min(len(df), zs.exit_bi.end_index + 1)
            
            # 根据方向选择柱子
            if direction == 'down':
                enter_area = abs(np.sum(hist[enter_start:enter_end][hist[enter_start:enter_end] < 0]))
                exit_area = abs(np.sum(hist[exit_start:exit_end][hist[exit_start:exit_end] < 0]))
            else:
                enter_area = np.sum(hist[enter_start:enter_end][hist[enter_start:enter_end] > 0])
                exit_area = np.sum(hist[exit_start:exit_end][hist[exit_start:exit_end] > 0])
            
            if enter_area > 0:
                return float(exit_area / enter_area)
            else:
                return 1.0
        except Exception:
            return 1.0
    
    def _calculate_confidence(self,
                            trend: TrendType,
                            strength_ratio: float,
                            macd_ratio: float) -> float:
        """计算信号置信度
        
        Args:
            trend: 趋势类型
            strength_ratio: 力度比
            macd_ratio: MACD面积比
            
        Returns:
            置信度（0-100）
        """
        confidence = 60  # 基础分
        
        # 趋势背驰加分
        if trend in (TrendType.UPTREND, TrendType.DOWNTREND):
            confidence += 15
        
        # 力度衰减加分
        if strength_ratio < 0.7:
            confidence += 15
        elif strength_ratio < 0.8:
            confidence += 10
        
        # MACD辅助确认加分
        if macd_ratio < 0.6:
            confidence += 10
        
        return min(100, confidence)


def detect_signals(df: pd.DataFrame,
                   bi_list: List[Any],
                   zs_list: List[Any],
                   **kwargs) -> List[Signal]:
    """便捷函数：检测所有信号
    
    Args:
        df: K线数据
        bi_list: 笔列表
        zs_list: 中枢列表
        **kwargs: SignalDetector参数
        
    Returns:
        信号列表
    """
    detector = SignalDetector(**kwargs)
    return detector.detect_all_signals(df, bi_list, zs_list)
