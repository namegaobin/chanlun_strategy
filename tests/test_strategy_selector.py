#!/usr/bin/env python3
"""
测试 FU-002: 策略选择器

测试根据买卖点信号类型自动选择对应的策略配置
"""

import pytest
from typing import List, Optional
from datetime import datetime


class TestStrategySelector:
    """测试策略选择器"""
    
    # -------------------------------------------------------------------------
    # AC-002-001: 信号类型映射
    # -------------------------------------------------------------------------
    
    def test_select_type1_for_buy1_signal(self):
        """AC-002-001: 第一类买点信号选择第一类策略
        
        Given: 检测到第一类买点信号（趋势反转）
        When: 调用 select_strategy(signal) 方法
        Then: 返回 STRATEGY_TYPE_1 策略配置
        """
        from src.strategy_selector import StrategySelector, Signal, SignalType
        
        selector = StrategySelector()
        
        # 创建第一类买点信号
        signal = Signal(
            signal_type=SignalType.BUY_1,
            confidence=0.85,
            price=100.0,
            timestamp=datetime.now(),
            metadata={'strength_ratio': 0.35}  # 背驰力度
        )
        
        # 选择策略
        selected = selector.select_strategy(signal)
        
        assert selected is not None, "策略选择结果不应为 None"
        assert selected.strategy_id == 'STRATEGY_TYPE_1', \
            f"第一类买点应选择 TYPE_1 策略，实际: {selected.strategy_id}"
    
    def test_select_type2_for_buy2_signal(self):
        """AC-002-001: 第二类买点信号选择第二类策略
        
        Given: 检测到第二类买点信号
        When: 调用 select_strategy(signal) 方法
        Then: 返回 STRATEGY_TYPE_2 策略配置
        """
        from src.strategy_selector import StrategySelector, Signal, SignalType
        
        selector = StrategySelector()
        
        # 创建第二类买点信号
        signal = Signal(
            signal_type=SignalType.BUY_2,
            confidence=0.75,
            price=100.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        selected = selector.select_strategy(signal)
        
        assert selected is not None, "策略选择结果不应为 None"
        assert selected.strategy_id == 'STRATEGY_TYPE_2', \
            f"第二类买点应选择 TYPE_2 策略，实际: {selected.strategy_id}"
    
    def test_select_type3_for_buy3_signal(self):
        """AC-002-001: 第三类买点信号选择第三类策略
        
        Given: 检测到第三类买点信号
        When: 调用 select_strategy(signal) 方法
        Then: 返回 STRATEGY_TYPE_3 策略配置
        """
        from src.strategy_selector import StrategySelector, Signal, SignalType
        
        selector = StrategySelector()
        
        # 创建第三类买点信号
        signal = Signal(
            signal_type=SignalType.BUY_3,
            confidence=0.70,
            price=100.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        selected = selector.select_strategy(signal)
        
        assert selected is not None, "策略选择结果不应为 None"
        assert selected.strategy_id == 'STRATEGY_TYPE_3', \
            f"第三类买点应选择 TYPE_3 策略，实际: {selected.strategy_id}"
    
    # -------------------------------------------------------------------------
    # AC-002-002: 冲突处理 - 优先级
    # -------------------------------------------------------------------------
    
    def test_priority_type2_over_type1(self):
        """AC-002-002: 第二类买点优先级高于第一类
        
        Given: 同时检测到第一类和第二类买点信号
        When: 调用 select_strategy(signals) 方法
        Then: 返回第二类买点策略（优先级：二类 > 一类）
        """
        from src.strategy_selector import StrategySelector, Signal, SignalType
        
        selector = StrategySelector()
        
        # 创建两个信号
        signal1 = Signal(
            signal_type=SignalType.BUY_1,
            confidence=0.85,
            price=100.0,
            timestamp=datetime.now(),
            metadata={'strength_ratio': 0.35}
        )
        
        signal2 = Signal(
            signal_type=SignalType.BUY_2,
            confidence=0.75,
            price=100.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # 选择策略（传入多个信号）
        selected = selector.select_strategy([signal1, signal2])
        
        assert selected is not None, "策略选择结果不应为 None"
        assert selected.strategy_id == 'STRATEGY_TYPE_2', \
            f"二类买点优先级应高于一类，实际选择了: {selected.strategy_id}"
    
    def test_priority_type3_over_type1(self):
        """AC-002-002: 第三类买点优先级高于第一类
        
        Given: 同时检测到第一类和第三类买点信号
        When: 调用 select_strategy(signals) 方法
        Then: 返回第三类买点策略（优先级：三类 > 一类）
        """
        from src.strategy_selector import StrategySelector, Signal, SignalType
        
        selector = StrategySelector()
        
        signal1 = Signal(
            signal_type=SignalType.BUY_1,
            confidence=0.85,
            price=100.0,
            timestamp=datetime.now(),
            metadata={'strength_ratio': 0.35}
        )
        
        signal3 = Signal(
            signal_type=SignalType.BUY_3,
            confidence=0.70,
            price=100.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        selected = selector.select_strategy([signal1, signal3])
        
        assert selected is not None, "策略选择结果不应为 None"
        assert selected.strategy_id == 'STRATEGY_TYPE_3', \
            f"三类买点优先级应高于一类，实际选择了: {selected.strategy_id}"
    
    def test_priority_all_three_conflict(self):
        """AC-002-002: 三类买点同时出现时的优先级
        
        Given: 同时检测到三类买点信号
        When: 调用 select_strategy(signals) 方法
        Then: 返回优先级最高的策略（三类 > 二类 > 一类）
        """
        from src.strategy_selector import StrategySelector, Signal, SignalType
        
        selector = StrategySelector()
        
        signal1 = Signal(
            signal_type=SignalType.BUY_1,
            confidence=0.85,
            price=100.0,
            timestamp=datetime.now(),
            metadata={'strength_ratio': 0.35}
        )
        
        signal2 = Signal(
            signal_type=SignalType.BUY_2,
            confidence=0.75,
            price=100.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        signal3 = Signal(
            signal_type=SignalType.BUY_3,
            confidence=0.70,
            price=100.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        selected = selector.select_strategy([signal1, signal2, signal3])
        
        assert selected is not None, "策略选择结果不应为 None"
        # 验证选择了优先级最高的策略
        assert selected.strategy_id in ['STRATEGY_TYPE_3', 'STRATEGY_TYPE_2'], \
            f"应选择优先级最高的策略，实际选择了: {selected.strategy_id}"
    
    # -------------------------------------------------------------------------
    # AC-002-003: 无效信号处理
    # -------------------------------------------------------------------------
    
    def test_invalid_signal_type_raises_error(self):
        """AC-002-003: 无效信号类型应抛出异常
        
        Given: 买卖点信号类型未知或无效
        When: 调用 select_strategy(signal) 方法
        Then: 抛出 InvalidSignalTypeError 异常
        """
        from src.strategy_selector import (
            StrategySelector, 
            Signal,
            InvalidSignalTypeError
        )
        
        selector = StrategySelector()
        
        # 创建无效信号
        signal = Signal(
            signal_type='INVALID_TYPE',  # 无效类型
            confidence=0.70,
            price=100.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        with pytest.raises(InvalidSignalTypeError):
            selector.select_strategy(signal)
    
    def test_null_signal_raises_error(self):
        """AC-002-003: 空信号应抛出异常
        
        Given: 信号为 None
        When: 调用 select_strategy(signal) 方法
        Then: 抛出 InvalidSignalTypeError 异常
        """
        from src.strategy_selector import StrategySelector, InvalidSignalTypeError
        
        selector = StrategySelector()
        
        with pytest.raises(InvalidSignalTypeError):
            selector.select_strategy(None)
    
    def test_empty_signal_list_raises_error(self):
        """AC-002-003: 空信号列表应抛出异常
        
        Given: 信号列表为空
        When: 调用 select_strategy(signals) 方法
        Then: 抛出 InvalidSignalTypeError 异常
        """
        from src.strategy_selector import StrategySelector, InvalidSignalTypeError
        
        selector = StrategySelector()
        
        with pytest.raises(InvalidSignalTypeError):
            selector.select_strategy([])
    
    # -------------------------------------------------------------------------
    # INV-002-001: 唯一映射
    # -------------------------------------------------------------------------
    
    def test_signal_uniquely_maps_to_strategy(self):
        """INV-002-001: 每个买卖点信号必须唯一映射到一个策略"""
        from src.strategy_selector import StrategySelector, Signal, SignalType
        
        selector = StrategySelector()
        
        # 测试每种信号类型
        test_cases = [
            (SignalType.BUY_1, 'STRATEGY_TYPE_1'),
            (SignalType.BUY_2, 'STRATEGY_TYPE_2'),
            (SignalType.BUY_3, 'STRATEGY_TYPE_3'),
            (SignalType.SELL_1, 'STRATEGY_TYPE_1'),
            (SignalType.SELL_2, 'STRATEGY_TYPE_2'),
            (SignalType.SELL_3, 'STRATEGY_TYPE_3'),
        ]
        
        for signal_type, expected_strategy in test_cases:
            signal = Signal(
                signal_type=signal_type,
                confidence=0.80,
                price=100.0,
                timestamp=datetime.now(),
                metadata={'strength_ratio': 0.35} if '1' in signal_type.value else {}
            )
            
            selected = selector.select_strategy(signal)
            
            assert selected is not None, \
                f"{signal_type} 应选择一个策略"
            assert selected.strategy_id == expected_strategy, \
                f"{signal_type} 应映射到 {expected_strategy}，实际: {selected.strategy_id}"
    
    # -------------------------------------------------------------------------
    # INV-002-003: 选择性能
    # -------------------------------------------------------------------------
    
    def test_selection_performance(self):
        """INV-002-003: 策略选择必须在 10ms 内完成"""
        import time
        from src.strategy_selector import StrategySelector, Signal, SignalType
        
        selector = StrategySelector()
        
        signal = Signal(
            signal_type=SignalType.BUY_2,
            confidence=0.75,
            price=100.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        # 测试多次取平均
        times = []
        for _ in range(100):
            start = time.perf_counter()
            selector.select_strategy(signal)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        
        assert avg_time < 10.0, \
            f"策略选择平均耗时 {avg_time:.2f}ms 应 < 10ms"
    
    # -------------------------------------------------------------------------
    # INV-002-004: 可追溯性
    # -------------------------------------------------------------------------
    
    def test_selection_result_is_traceable(self):
        """INV-002-004: 选择结果必须可追溯（包含选择原因和时间戳）"""
        from src.strategy_selector import StrategySelector, Signal, SignalType
        
        selector = StrategySelector()
        
        signal = Signal(
            signal_type=SignalType.BUY_2,
            confidence=0.75,
            price=100.0,
            timestamp=datetime.now(),
            metadata={}
        )
        
        selected = selector.select_strategy(signal)
        
        # 验证选择结果包含追溯信息
        assert hasattr(selected, 'selection_reason'), \
            "选择结果应包含 selection_reason"
        assert hasattr(selected, 'selection_timestamp'), \
            "选择结果应包含 selection_timestamp"
        
        assert selected.selection_reason is not None, \
            "selection_reason 不应为 None"
        assert selected.selection_timestamp is not None, \
            "selection_timestamp 不应为 None"
