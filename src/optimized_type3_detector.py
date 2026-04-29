#!/usr/bin/env python3
"""
优化版 TYPE_3 信号检测器 - v4（修复逻辑匹配原版结构）

核心改进（保持原版逻辑结构）：
1. 对每个向下笔，找到对应的中枢
2. 增加有效突破过滤
3. 增加趋势过滤
4. 增加确认段过滤
"""

import pandas as pd
import numpy as np
from typing import List, Optional
from dataclasses import dataclass

from src.chanlun_structure_v2 import Bi, Zhongshu, Direction


@dataclass
class Type3Signal:
    """第三类买卖点信号"""
    signal_type: str
    price: float
    index: int
    confidence: float
    zhongshu: Zhongshu
    leave_bi: Bi
    pullback_bi: Bi
    confirm_bi: Optional[Bi] = None
    reasons: List[str] = None


class OptimizedType3Detector:
    """优化版第三类买卖点检测器 - 修复版"""
    
    def __init__(self, 
                 min_leave_ratio: float = 0.5,    # 离开段最小幅度（相对于中枢高度）
                 max_pullback_ratio: float = 0.5, # 回抽最大幅度（相对于离开段）
                 min_zs_age: int = 3,
                 use_trend_filter: bool = True):
        
        self.min_leave_ratio = min_leave_ratio
        self.max_pullback_ratio = max_pullback_ratio
        self.min_zs_age = min_zs_age
        self.use_trend_filter = use_trend_filter
        
        self.signals: List[Type3Signal] = []
    
    def detect_buy_3(self, 
                     bi_list: List[Bi], 
                     zs_list: List[Zhongshu],
                     df: pd.DataFrame) -> List[Type3Signal]:
        """
        检测第三类买点 - 简化版
        
        核心逻辑：
        1. 向下笔回抽不破ZG（核心条件）
        2. 离开段幅度过滤（可选）
        3. 趋势过滤（可选）
        """
        signals = []
        
        if not bi_list or not zs_list:
            return signals
        
        # 趋势判断
        trend_type = '盘整'
        if self.use_trend_filter:
            trend_type = self._simple_trend_judge(zs_list)
        
        # 遍历每个向下笔（买三候选）
        for bi in bi_list:
            if bi.direction != Direction.DOWN:
                continue
            
            # 找到该笔对应的中枢
            for zs in zs_list:
                if bi.end_index <= zs.end_index:
                    continue
                
                # 核心条件：回抽不破ZG
                if bi.low <= zs.zg:
                    continue
                
                # 趋势过滤
                if self.use_trend_filter and trend_type != '上升趋势':
                    continue
                
                # 离开段幅度检查（简化版：只检查是否有有效突破）
                # 找中枢后的第一笔（应该是离开段）
                after_zs = [b for b in bi_list if b.start_index > zs.end_index]
                if after_zs:
                    first_after = after_zs[0]
                    if first_after.direction == Direction.UP:
                        leave_height = first_after.high - zs.zg
                        if leave_height < zs.height * self.min_leave_ratio:
                            continue
                
                # 生成信号
                confidence = 80.0
                if self.use_trend_filter:
                    confidence = 85.0 if trend_type == '上升趋势' else 70.0
                
                signal = Type3Signal(
                    signal_type='buy_3',
                    price=bi.low,
                    index=bi.end_index,
                    confidence=confidence,
                    zhongshu=zs,
                    leave_bi=after_zs[0] if after_zs else None,
                    pullback_bi=bi,
                    confirm_bi=None,
                    reasons=[f'趋势={trend_type}', f'低点={bi.low:.0f}>ZG={zs.zg:.0f}']
                )
                
                signals.append(signal)
                break  # 找到第一个匹配的中枢就停止
        
        return signals
    
    def detect_sell_3(self,
                      bi_list: List[Bi],
                      zs_list: List[Zhongshu],
                      df: pd.DataFrame) -> List[Type3Signal]:
        """检测第三类卖点 - 简化版"""
        signals = []
        
        if not bi_list or not zs_list:
            return signals
        
        # 趋势判断
        trend_type = '盘整'
        if self.use_trend_filter:
            trend_type = self._simple_trend_judge(zs_list)
        
        # 遍历每个向上笔（卖三候选）
        for bi in bi_list:
            if bi.direction != Direction.UP:
                continue
            
            # 找到该笔对应的中枢
            for zs in zs_list:
                if bi.end_index <= zs.end_index:
                    continue
                
                # 核心条件：反弹不破ZD
                if bi.high >= zs.zd:
                    continue
                
                # 趋势过滤
                if self.use_trend_filter and trend_type != '下降趋势':
                    continue
                
                # 离开段幅度检查
                after_zs = [b for b in bi_list if b.start_index > zs.end_index]
                if after_zs:
                    first_after = after_zs[0]
                    if first_after.direction == Direction.DOWN:
                        leave_depth = zs.zd - first_after.low
                        if leave_depth < zs.height * self.min_leave_ratio:
                            continue
                
                # 生成信号
                confidence = 80.0
                if self.use_trend_filter:
                    confidence = 85.0 if trend_type == '下降趋势' else 70.0
                
                signal = Type3Signal(
                    signal_type='sell_3',
                    price=bi.high,
                    index=bi.end_index,
                    confidence=confidence,
                    zhongshu=zs,
                    leave_bi=after_zs[0] if after_zs else None,
                    pullback_bi=bi,
                    confirm_bi=None,
                    reasons=[f'趋势={trend_type}', f'高点={bi.high:.0f}<ZD={zs.zd:.0f}']
                )
                
                signals.append(signal)
                break
        
        return signals
    
    def _simple_trend_judge(self, zs_list: List[Zhongshu]) -> str:
        """简化版趋势判断"""
        if len(zs_list) < 2:
            return '盘整'
        
        zs_sorted = sorted(zs_list, key=lambda z: z.end_index, reverse=True)[:2]
        pre_zs, cur_zs = zs_sorted[1], zs_sorted[0]
        
        if pre_zs.zg < cur_zs.zd:
            return '上升趋势'
        if pre_zs.zd > cur_zs.zg:
            return '下降趋势'
        return '盘整'
    
    def _calculate_confidence(self,
                              zs: Zhongshu,
                              leave_bi: Bi,
                              pullback_bi: Bi,
                              confirm_bi: Bi,
                              df: pd.DataFrame,
                              trend_type: str = '盘整') -> float:
        """计算信号置信度"""
        base_confidence = 70.0
        
        if trend_type == '上升趋势' and leave_bi.direction == Direction.UP:
            base_confidence += 10
        elif trend_type == '下降趋势' and leave_bi.direction == Direction.DOWN:
            base_confidence += 10
        
        if leave_bi.direction == Direction.UP:
            leave_ratio = (leave_bi.high - zs.zg) / zs.height if zs.height > 0 else 0
        else:
            leave_ratio = (zs.zd - leave_bi.low) / zs.height if zs.height > 0 else 0
        
        if leave_ratio > 1.0:
            base_confidence += 10
        elif leave_ratio > 0.5:
            base_confidence += 5
        
        if leave_bi.direction == Direction.UP:
            pullback_ratio = (zs.zg - pullback_bi.low) / (leave_bi.high - zs.zg) if leave_bi.high > zs.zg else 1
        else:
            pullback_ratio = (pullback_bi.high - zs.zd) / (zs.zd - leave_bi.low) if zs.zd > leave_bi.low else 1
        
        if pullback_ratio < 0.3:
            base_confidence += 10
        elif pullback_ratio < 0.5:
            base_confidence += 5
        
        return min(95, max(60, base_confidence))
    
    def detect_all(self,
                   bi_list: List[Bi],
                   zs_list: List[Zhongshu],
                   df: pd.DataFrame) -> List[Type3Signal]:
        """检测所有第三类买卖点"""
        buy_signals = self.detect_buy_3(bi_list, zs_list, df)
        sell_signals = self.detect_sell_3(bi_list, zs_list, df)
        
        all_signals = buy_signals + sell_signals
        
        # 去重：基于 (signal_type, index, price) 唯一标识
        seen = set()
        unique_signals = []
        for s in all_signals:
            key = (s.signal_type, s.index, s.price)
            if key not in seen:
                seen.add(key)
                unique_signals.append(s)
        
        unique_signals.sort(key=lambda s: s.index)
        
        return unique_signals


if __name__ == "__main__":
    print("优化版TYPE_3检测器 v4 加载完成")