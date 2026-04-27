#!/usr/bin/env python3
"""
信号检测器测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.signal_detector import SignalDetector, SignalType, detect_signals
from src.chanlun_structure_v2 import (
    process_inclusion,
    detect_all_fractals,
    build_bi_from_fractals,
    detect_all_zhongshu
)


class TestSignalDetector:
    """信号检测器测试类"""
    
    @pytest.fixture
    def sample_data(self):
        """生成测试数据"""
        np.random.seed(42)
        n = 500
        dates = pd.date_range(end=datetime.now(), periods=n, freq='5min')
        
        close = np.zeros(n)
        close[0] = 65000.0
        
        # 下跌趋势
        for i in range(1, n):
            if i < 150:
                close[i] = close[i-1] * (1 + np.random.randn() * 0.003 - 0.002)  # 下跌
            elif i < 300:
                close[i] = close[i-1] * (1 + np.random.randn() * 0.002)  # 盘整
            else:
                close[i] = close[i-1] * (1 + np.random.randn() * 0.003 + 0.001)  # 上涨
        
        close = np.clip(close, 50000, 80000)
        
        df = pd.DataFrame({
            'date': dates,
            'open': close * (1 + np.random.randn(n) * 0.001),
            'high': close * (1 + np.abs(np.random.randn(n)) * 0.003),
            'low': close * (1 - np.abs(np.random.randn(n)) * 0.003),
            'close': close,
            'volume': np.random.randint(100, 500, n)
        })
        df['high'] = df[['high', 'open', 'close']].max(axis=1)
        df['low'] = df[['low', 'open', 'close']].min(axis=1)
        
        return df
    
    @pytest.fixture
    def detector(self):
        """创建检测器"""
        return SignalDetector()
    
    def test_detector_initialization(self, detector):
        """测试检测器初始化"""
        assert detector.divergence_threshold_trend == 0.9
        assert detector.divergence_threshold_consolidation == 0.95
        assert detector.macd_threshold == 0.8
    
    def test_detect_signals_basic(self, sample_data, detector):
        """测试基本信号检测"""
        df = sample_data
        
        # 缠论分析
        df_proc = process_inclusion(df)
        fractals = detect_all_fractals(df_proc)
        bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
        zs_list = detect_all_zhongshu(bi_list, min_bi=3)
        
        # 检测信号
        signals = detector.detect_all_signals(df, bi_list, zs_list)
        
        # 验证返回的是列表
        assert isinstance(signals, list)
        
        # 验证信号结构
        for sig in signals:
            assert hasattr(sig, 'signal_type')
            assert hasattr(sig, 'price')
            assert hasattr(sig, 'index')
            assert hasattr(sig, 'confidence')
            assert hasattr(sig, 'reason')
    
    def test_buy1_signal_detection(self, sample_data):
        """测试第一类买点检测"""
        df = sample_data
        
        df_proc = process_inclusion(df)
        fractals = detect_all_fractals(df_proc)
        bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
        zs_list = detect_all_zhongshu(bi_list, min_bi=3)
        
        detector = SignalDetector()
        signals = detector.detect_all_signals(df, bi_list, zs_list)
        
        # 检查是否有第一类买点
        buy1_signals = [s for s in signals if s.signal_type == SignalType.BUY_1]
        
        # 如果有，验证结构
        for sig in buy1_signals:
            assert sig.signal_type == SignalType.BUY_1
            assert sig.price > 0
            assert sig.confidence > 0
            assert '第一类买点' in sig.reason
    
    def test_sell1_signal_detection(self, sample_data):
        """测试第一类卖点检测"""
        df = sample_data
        
        df_proc = process_inclusion(df)
        fractals = detect_all_fractals(df_proc)
        bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
        zs_list = detect_all_zhongshu(bi_list, min_bi=3)
        
        detector = SignalDetector()
        signals = detector.detect_all_signals(df, bi_list, zs_list)
        
        sell1_signals = [s for s in signals if s.signal_type == SignalType.SELL_1]
        
        for sig in sell1_signals:
            assert sig.signal_type == SignalType.SELL_1
            assert sig.price > 0
            assert '第一类卖点' in sig.reason
    
    def test_buy3_signal_detection(self, sample_data):
        """测试第三类买点检测"""
        df = sample_data
        
        df_proc = process_inclusion(df)
        fractals = detect_all_fractals(df_proc)
        bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
        zs_list = detect_all_zhongshu(bi_list, min_bi=3)
        
        detector = SignalDetector()
        signals = detector.detect_all_signals(df, bi_list, zs_list)
        
        buy3_signals = [s for s in signals if s.signal_type == SignalType.BUY_3]
        
        for sig in buy3_signals:
            assert sig.signal_type == SignalType.BUY_3
            assert '第三类买点' in sig.reason
    
    def test_signal_ordering(self, sample_data):
        """测试信号排序"""
        df = sample_data
        
        df_proc = process_inclusion(df)
        fractals = detect_all_fractals(df_proc)
        bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
        zs_list = detect_all_zhongshu(bi_list, min_bi=3)
        
        detector = SignalDetector()
        signals = detector.detect_all_signals(df, bi_list, zs_list)
        
        # 验证信号按时间排序
        if len(signals) > 1:
            for i in range(len(signals) - 1):
                assert signals[i].index <= signals[i+1].index
    
    def test_signal_to_dict(self, sample_data):
        """测试信号转换为字典"""
        df = sample_data
        
        df_proc = process_inclusion(df)
        fractals = detect_all_fractals(df_proc)
        bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
        zs_list = detect_all_zhongshu(bi_list, min_bi=3)
        
        detector = SignalDetector()
        signals = detector.detect_all_signals(df, bi_list, zs_list)
        
        if signals:
            sig_dict = signals[0].to_dict()
            assert 'signal_type' in sig_dict
            assert 'price' in sig_dict
            assert 'confidence' in sig_dict
    
    def test_convenience_function(self, sample_data):
        """测试便捷函数"""
        df = sample_data
        
        df_proc = process_inclusion(df)
        fractals = detect_all_fractals(df_proc)
        bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
        zs_list = detect_all_zhongshu(bi_list, min_bi=3)
        
        signals = detect_signals(df, bi_list, zs_list)
        
        assert isinstance(signals, list)


class TestDivergenceDetection:
    """背驰检测测试"""
    
    def test_strength_calculation(self):
        """测试力度计算"""
        detector = SignalDetector()
        
        # 创建模拟笔对象
        class MockBi:
            def __init__(self):
                self.high = 70000
                self.low = 65000
                self.start_index = 0
                self.end_index = 10
        
        bi = MockBi()
        df = pd.DataFrame({'close': np.random.randn(100) * 1000 + 67500})
        
        strength = detector._calculate_strength(df, bi)
        
        # 力度应该为正数
        assert strength > 0
    
    def test_trend_judgment(self):
        """测试趋势判断"""
        detector = SignalDetector()
        
        # 创建模拟数据
        class MockBi:
            def __init__(self, high, low):
                self.high = high
                self.low = low
        
        # 上涨趋势
        uptrend_bis = [
            MockBi(70000, 68000),
            MockBi(71000, 69000),
            MockBi(72000, 70000)
        ]
        df = pd.DataFrame({'close': range(70000, 72000)})
        
        from src.signal_detector import TrendType
        trend = detector._judge_trend(df, uptrend_bis)
        # 应该识别为上涨趋势或盘整
        assert trend in (TrendType.UPTREND, TrendType.CONSOLIDATION)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
