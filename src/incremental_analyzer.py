#!/usr/bin/env python3
"""
增量式缠论结构计算器 - GREEN Phase 实现

逐K线处理，返回当前状态。
支持增量式包含关系处理、分型确认延迟、笔确认延迟、中枢确认延迟。

核心约束：每个决策点只能使用≤当前时间的数据
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import copy


@dataclass
class KLine:
    """K线数据"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Fractal:
    """分型"""
    timestamp: datetime
    type: str  # 'top' or 'bottom'
    high: float
    low: float
    confirmed: bool = False
    confirm_time: Optional[datetime] = None


@dataclass
class Bi:
    """笔"""
    start_time: datetime
    end_time: datetime
    direction: str  # 'up' or 'down'
    high: float
    low: float
    confirmed: bool = False
    confirm_time: Optional[datetime] = None


@dataclass
class Zhongshu:
    """中枢"""
    start_time: datetime
    end_time: datetime
    zg: float  # 中枢高点
    zd: float  # 中枢低点
    confirmed: bool = False
    confirm_time: Optional[datetime] = None


class IncrementalChanLunAnalyzer:
    """增量式缠论结构计算器"""
    
    def __init__(self):
        self.klines: List[KLine] = []
        self.merged_klines: List[KLine] = []
        self.pending_fractals: List[Fractal] = []
        self.confirmed_fractals: List[Fractal] = []
        self.confirmed_bi_list: List[Bi] = []
        self.confirmed_zhongshu_list: List[Zhongshu] = []
        self.processed_klines_count = 0
        self.pending_klines_count = 0
    
    def on_bar(self, kline: KLine) -> dict:
        """
        逐K线处理，返回当前状态
        
        核心约束：只能使用≤当前时间的数据
        """
        self.klines.append(kline)
        self.processed_klines_count += 1
        
        # 包含关系处理（增量式）
        merged_klines = self._process_inclusion(kline)
        self.merged_klines = merged_klines
        
        # 分型检测（需要3根K线，需要延迟确认）
        pending_fractals, confirmed_fractals = self._detect_fractals(kline)
        self.pending_fractals = pending_fractals
        self.confirmed_fractals = confirmed_fractals
        
        # 笔检测（需要两个分型+独立K线，延迟确认）
        confirmed_bi_list = self._detect_bi(kline)
        self.confirmed_bi_list = confirmed_bi_list
        
        # 中枢检测（需要至少3笔，延迟确认）
        confirmed_zhongshu_list = self._detect_zhongshu(kline)
        self.confirmed_zhongshu_list = confirmed_zhongshu_list
        
        # 计算pending_klines_count（第1根K线需要等下一根确认）
        if len(self.merged_klines) == 1:
            self.pending_klines_count = 1
        else:
            self.pending_klines_count = 0
        
        return {
            'current_time': kline.timestamp,
            'processed_klines_count': self.processed_klines_count,
            'pending_klines_count': self.pending_klines_count,
            'merged_klines': self.merged_klines,
            'pending_fractals': self.pending_fractals,
            'confirmed_fractals': self.confirmed_fractals,
            'confirmed_bi_list': self.confirmed_bi_list,
            'confirmed_zhongshu_list': self.confirmed_zhongshu_list,
        }
    
    def _process_inclusion(self, kline: KLine) -> List[KLine]:
        """增量式包含关系处理"""
        if len(self.merged_klines) == 0:
            return [kline]
        
        last_k = self.merged_klines[-1]
        
        # 检查包含关系
        if (last_k.high >= kline.high and last_k.low <= kline.low) or \
           (last_k.high <= kline.high and last_k.low >= kline.low):
            # 合并：向上趋势取max，向下趋势取min
            if len(self.merged_klines) >= 2:
                prev_k = self.merged_klines[-2]
                if prev_k.high < last_k.high:
                    # 上升趋势
                    new_high = max(last_k.high, kline.high)
                    new_low = max(last_k.low, kline.low)
                else:
                    # 下降趋势
                    new_high = min(last_k.high, kline.high)
                    new_low = min(last_k.low, kline.low)
            else:
                # 只有2根K线，无法判断趋势，保守处理
                new_high = max(last_k.high, kline.high)
                new_low = min(last_k.low, kline.low)
            
            merged = KLine(
                timestamp=kline.timestamp,
                open=last_k.open,
                close=kline.close,
                high=new_high,
                low=new_low,
                volume=last_k.volume + kline.volume
            )
            self.merged_klines[-1] = merged
            return self.merged_klines
        else:
            self.merged_klines.append(kline)
            return self.merged_klines
    
    def _detect_fractals(self, kline: KLine) -> tuple:
        """分型检测 - 需要3根K线才能确认，分型确认延迟"""
        pending = list(self.pending_fractals)
        confirmed = list(self.confirmed_fractals)
        
        merged = self.merged_klines
        if len(merged) < 3:
            return pending, confirmed
        
        # 检查顶分型和底分型
        k1, k2, k3 = merged[-3], merged[-2], merged[-1]
        
        # 顶分型：中间K线高点最高、低点也最高
        is_top = (k2.high >= k1.high and k2.high >= k3.high and
                  k2.low >= k1.low and k2.low >= k3.low)
        
        # 底分型：中间K线低点最低、高点也最低
        is_bottom = (k2.low <= k1.low and k2.low <= k3.low and
                     k2.high <= k1.high and k2.high <= k3.high)
        
        # 只添加一个分型（优先顶分型）
        if is_top and not is_bottom:
            fractal = Fractal(
                timestamp=k2.timestamp,
                type='top',
                high=k2.high,
                low=k2.low,
                confirmed=False
            )
            pending.append(fractal)
        elif is_bottom and not is_top:
            fractal = Fractal(
                timestamp=k2.timestamp,
                type='bottom',
                high=k2.high,
                low=k2.low,
                confirmed=False
            )
            pending.append(fractal)
        elif is_top and is_bottom:
            # 既是顶分型又是底分型（异常），跳过
            pass
        
        # 确认逻辑：需要下一根K线来确认分型
        # 只有当有pending分型，并且当前输入了新的K线后，才能确认
        if len(merged) >= 4:
            # 确认前一个分型
            if pending:
                confirmed_fx = pending.pop(0)
                confirmed_fx.confirmed = True
                confirmed_fx.confirm_time = kline.timestamp
                confirmed.append(confirmed_fx)
        
        return pending, confirmed
    
    def _detect_bi(self, kline: KLine) -> List[Bi]:
        """笔检测 - 需要两分型之间至少1根独立K线"""
        confirmed = list(self.confirmed_bi_list)
        
        if len(self.confirmed_fractals) < 2:
            return confirmed
        
        # 获取最近的两个分型
        fxs = self.confirmed_fractals
        
        # 检查是否有连续的两个反向分型
        for i in range(len(fxs) - 1):
            f1, f2 = fxs[i], fxs[i + 1]
            
            # 需要方向相反
            if f1.type == f2.type:
                continue
            
            # 向上笔：底分型 -> 顶分型
            # 向下笔：顶分型 -> 底分型
            if f1.type == 'bottom' and f2.type == 'top':
                direction = 'up'
            elif f1.type == 'top' and f2.type == 'bottom':
                direction = 'down'
            else:
                continue
            
            # 检查独立K线数量
            f1_idx = next((j for j, k in enumerate(self.merged_klines) 
                          if k.timestamp == f1.timestamp), -1)
            f2_idx = next((j for j, k in enumerate(self.merged_klines) 
                          if k.timestamp == f2.timestamp), -1)
            
            if f1_idx >= 0 and f2_idx >= 0 and (f2_idx - f1_idx) >= 4:
                # 满足独立K线条件
                bi = Bi(
                    start_time=f1.timestamp,
                    end_time=f2.timestamp,
                    direction=direction,
                    high=max(f1.high, f2.high),
                    low=min(f1.low, f2.low),
                    confirmed=True,
                    confirm_time=kline.timestamp
                )
                # 避免重复添加
                if not any(b.start_time == bi.start_time and b.end_time == bi.end_time 
                          for b in confirmed):
                    confirmed.append(bi)
        
        return confirmed
    
    def _detect_zhongshu(self, kline: KLine) -> List[Zhongshu]:
        """中枢检测 - 需要至少3笔才能确认"""
        confirmed = list(self.confirmed_zhongshu_list)
        
        bi_list = self.confirmed_bi_list
        if len(bi_list) < 3:
            return confirmed
        
        # 检查最近3笔是否构成中枢
        for i in range(len(bi_list) - 2):
            b1, b2, b3 = bi_list[i], bi_list[i+1], bi_list[i+2]
            
            # 方向交替：上-下-上 或 下-上-下
            if b1.direction == b2.direction or b2.direction == b3.direction:
                continue
            
            # 计算重叠区间
            highs = [b1.high, b2.high, b3.high]
            lows = [b1.low, b2.low, b3.low]
            
            zd = max(lows)  # 中枢低点
            zg = min(highs)  # 中枢高点
            
            if zg > zd:  # 有重叠区间
                zs = Zhongshu(
                    start_time=b1.start_time,
                    end_time=b3.end_time,
                    zg=zg,
                    zd=zd,
                    confirmed=True,
                    confirm_time=kline.timestamp
                )
                # 避免重复添加
                if not any(z.start_time == zs.start_time and z.zg == zs.zg 
                          for z in confirmed):
                    confirmed.append(zs)
        
        return confirmed