"""
多信号组合策略测试

FU-011: 多信号组合策略（根据市场状态选择信号类型）
BB-OPT-004: 新建 signal_combination.py 实现多信号组合

RED阶段 - 所有测试预期失败
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_kline_data():
    """生成示例K线数据"""
    dates = pd.date_range('2026-01-01', periods=200, freq='D')
    
    # 模拟价格数据
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(200) * 0.5)
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': prices + np.abs(np.random.randn(200)) * 2,
        'low': prices - np.abs(np.random.randn(200)) * 2,
        'close': prices + np.random.randn(200) * 0.5,
        'volume': np.random.randint(1000000, 5000000, 200)
    })
    
    return df


@pytest.fixture
def uptrend_market_env():
    """
    上涨趋势市场环境
    
    特征：
    - 两个中枢不重叠，位置递增
    - 趋势向上
    """
    from chanlun_strategy.chanlun_structure_v2 import Zhongshu
    
    zs1 = Zhongshu(zg=100.0, zd=95.0, start_index=10, end_index=50, level=1, bi_list=[])
    zs2 = Zhongshu(zg=115.0, zd=110.0, start_index=80, end_index=140, level=1, bi_list=[])
    
    return {
        'environment': 'trending',
        'trend_direction': 'up',
        'zhongshu_list': [zs1, zs2],
        'zhongshu_overlap': False,
        'confidence': 0.85
    }


@pytest.fixture
def downtrend_market_env():
    """
    下跌趋势市场环境
    
    特征：
    - 两个中枢不重叠，位置递减
    - 趋势向下
    """
    from chanlun_strategy.chanlun_structure_v2 import Zhongshu
    
    zs1 = Zhongshu(zg=115.0, zd=110.0, start_index=10, end_index=50, level=1, bi_list=[])
    zs2 = Zhongshu(zg=100.0, zd=95.0, start_index=80, end_index=140, level=1, bi_list=[])
    
    return {
        'environment': 'trending',
        'trend_direction': 'down',
        'zhongshu_list': [zs1, zs2],
        'zhongshu_overlap': False,
        'confidence': 0.85
    }


@pytest.fixture
def sideways_market_env():
    """
    震荡市场环境
    
    特征：
    - 两个中枢重叠
    - 无明确趋势
    """
    from chanlun_strategy.chanlun_structure_v2 import Zhongshu
    
    zs1 = Zhongshu(zg=105.0, zd=100.0, start_index=10, end_index=50, level=1, bi_list=[])
    zs2 = Zhongshu(zg=108.0, zd=103.0, start_index=80, end_index=140, level=1, bi_list=[])
    
    return {
        'environment': 'sideways',
        'trend_direction': 'none',
        'zhongshu_list': [zs1, zs2],
        'zhongshu_overlap': True,
        'overlap_ratio': 0.4,
        'confidence': 0.75
    }


@pytest.fixture
def mixed_signals():
    """
    混合信号列表
    
    包含：
    - 第一类买点
    - 第二类买点
    - 第三类买点
    - 各类卖点
    """
    from chanlun_strategy.signal_detector import Signal, SignalType
    from datetime import datetime
    
    signals = [
        # 第一类买点
        Signal(
            signal_type=SignalType.BUY_1,
            price=95.0,
            index=30,
            datetime=datetime(2026, 1, 31),
            confidence=85,
            reason='第一类买点：下跌趋势背驰'
        ),
        # 第二类买点
        Signal(
            signal_type=SignalType.BUY_2,
            price=98.0,
            index=60,
            datetime=datetime(2026, 3, 2),
            confidence=75,
            reason='第二类买点：回抽不破前低'
        ),
        # 第三类买点
        Signal(
            signal_type=SignalType.BUY_3,
            price=102.0,
            index=100,
            datetime=datetime(2026, 4, 11),
            confidence=70,
            reason='第三类买点：突破中枢后回抽不破ZG'
        ),
        # 第一类卖点
        Signal(
            signal_type=SignalType.SELL_1,
            price=110.0,
            index=40,
            datetime=datetime(2026, 2, 10),
            confidence=85,
            reason='第一类卖点：上涨趋势背驰'
        ),
        # 第二类卖点
        Signal(
            signal_type=SignalType.SELL_2,
            price=108.0,
            index=70,
            datetime=datetime(2026, 3, 12),
            confidence=75,
            reason='第二类卖点：反弹不破前高'
        ),
        # 第三类卖点
        Signal(
            signal_type=SignalType.SELL_3,
            price=105.0,
            index=110,
            datetime=datetime(2026, 4, 21),
            confidence=70,
            reason='第三类卖点：跌破中枢后反弹不过ZD'
        )
    ]
    
    return signals


# ============================================================================
# FU-011: 多信号组合策略测试
# ============================================================================

class TestSignalCombination:
    """
    FU-011: 多信号组合策略（根据市场状态选择信号类型）
    
    测试策略：
    1. 趋势上涨市 → 选择第二、第三类买点（顺势操作）
    2. 趋势下跌市 → 选择第一类买点（抄底）
    3. 震荡市 → 选择第一类买点（区间操作）
    
    缠论原理：
    - 趋势中操作要顺势而为（二、三类买卖点）
    - 趋势反转时用一类买卖点
    - 盘整中只操作一类买卖点
    """
    
    # ========================================================================
    # P0: 趋势上涨市 - 选择二三买
    # ========================================================================
    
    def test_trending_uptrend_select_buy2_buy3(self, uptrend_market_env, mixed_signals):
        """
        TC-FU011-001 - P0: 趋势上涨市选择二三买
        
        Given:
        - 市场环境：上涨趋势
        - 信号列表：包含一二三类买点
        
        When:
        - 调用 select_signals_by_market_environment(signals, market_env)
        
        Then:
        - 返回第二类买点和第三类买点
        - 排除第一类买点（趋势中不抄底）
        - 排除所有卖点（上涨趋势不做空）
        - selected_signals 只包含 BUY_2 和 BUY_3
        """
        # Given
        from chanlun_strategy.signal_combination import select_signals_by_market_environment
        
        # When
        selected = select_signals_by_market_environment(
            signals=mixed_signals,
            market_env=uptrend_market_env
        )
        
        # Then
        from chanlun_strategy.signal_detector import SignalType
        
        # 验证选中的信号类型
        selected_types = [s.signal_type for s in selected]
        
        # 应该只包含第二、第三类买点
        assert SignalType.BUY_2 in selected_types, \
            "上涨趋势应选择第二类买点"
        assert SignalType.BUY_3 in selected_types, \
            "上涨趋势应选择第三类买点"
        
        # 不应包含第一类买点
        assert SignalType.BUY_1 not in selected_types, \
            "上涨趋势不应选择第一类买点（趋势中不抄底）"
        
        # 不应包含任何卖点
        sell_types = [SignalType.SELL_1, SignalType.SELL_2, SignalType.SELL_3]
        for sell_type in sell_types:
            assert sell_type not in selected_types, \
                f"上涨趋势不应选择{sell_type.value}"
        
        # 验证过滤原因
        filter_reasons = selected[0].metadata.get('filter_reasons', {}) if selected else {}
        assert filter_reasons.get('BUY_1') == 'trending_uptrend_no_bottom_fishing', \
            "第一类买点应被标记为上涨趋势不抄底"
    
    def test_trending_uptrend_signal_priority(self, uptrend_market_env, mixed_signals):
        """
        TC-FU011-002 - P0: 趋势上涨市信号优先级
        
        Given:
        - 市场环境：上涨趋势
        - 同时存在第二、第三类买点
        
        When:
        - 选择信号
        
        Then:
        - 第三类买点优先级最高（顺势突破）
        - 第二类买点次之
        - 按 confidence 降序排列
        """
        # Given
        from chanlun_strategy.signal_combination import select_signals_by_market_environment
        
        # When
        selected = select_signals_by_market_environment(
            signals=mixed_signals,
            market_env=uptrend_market_env
        )
        
        # Then
        from chanlun_strategy.signal_detector import SignalType
        
        # 验证排序
        buy3_signals = [s for s in selected if s.signal_type == SignalType.BUY_3]
        buy2_signals = [s for s in selected if s.signal_type == SignalType.BUY_2]
        
        if buy3_signals and buy2_signals:
            # 第三类买点应排在前面
            first_buy3_idx = selected.index(buy3_signals[0])
            first_buy2_idx = selected.index(buy2_signals[0])
            
            assert first_buy3_idx < first_buy2_idx, \
                "第三类买点应优先于第二类买点"
        
        # 验证同一类型内按置信度排序
        for signal_type in [SignalType.BUY_3, SignalType.BUY_2]:
            type_signals = [s for s in selected if s.signal_type == signal_type]
            if len(type_signals) > 1:
                for i in range(len(type_signals) - 1):
                    assert type_signals[i].confidence >= type_signals[i+1].confidence, \
                        f"{signal_type.value}应按置信度降序排列"
    
    # ========================================================================
    # P0: 趋势下跌市 - 选择一买
    # ========================================================================
    
    def test_trending_downtrend_select_buy1(self, downtrend_market_env, mixed_signals):
        """
        TC-FU011-003 - P0: 趋势下跌市选择一买
        
        Given:
        - 市场环境：下跌趋势
        - 信号列表：包含一二三类买点
        
        When:
        - 调用 select_signals_by_market_environment
        
        Then:
        - 返回第一类买点
        - 排除第二、第三类买点（下跌趋势中不追涨）
        - 排除所有卖点（没有持仓不做空）
        """
        # Given
        from chanlun_strategy.signal_combination import select_signals_by_market_environment
        
        # When
        selected = select_signals_by_market_environment(
            signals=mixed_signals,
            market_env=downtrend_market_env
        )
        
        # Then
        from chanlun_strategy.signal_detector import SignalType
        
        selected_types = [s.signal_type for s in selected]
        
        # 应该只包含第一类买点
        assert SignalType.BUY_1 in selected_types, \
            "下跌趋势应选择第一类买点"
        
        # 不应包含第二、第三类买点
        assert SignalType.BUY_2 not in selected_types, \
            "下跌趋势不应选择第二类买点（不追涨）"
        assert SignalType.BUY_3 not in selected_types, \
            "下跌趋势不应选择第三类买点（不追涨）"
        
        # 不应包含任何卖点
        sell_types = [SignalType.SELL_1, SignalType.SELL_2, SignalType.SELL_3]
        for sell_type in sell_types:
            assert sell_type not in selected_types, \
                f"下跌趋势不应选择{sell_type.value}"
        
        # 验证过滤原因
        if selected:
            filter_reasons = selected[0].metadata.get('filter_reasons', {})
            assert filter_reasons.get('BUY_2') == 'downtrend_no_chasing', \
                "第二类买点应被标记为下跌趋势不追涨"
            assert filter_reasons.get('BUY_3') == 'downtrend_no_chasing', \
                "第三类买点应被标记为下跌趋势不追涨"
    
    def test_trending_downtrend_first_buy_confidence_threshold(self, downtrend_market_env):
        """
        TC-FU011-004 - P0: 下跌趋势第一类买点置信度阈值
        
        Given:
        - 市场环境：下跌趋势
        - 第一类买点置信度低于70%
        
        When:
        - 选择信号
        
        Then:
        - 低置信度的第一类买点被过滤
        - 只选择高置信度的第一类买点
        """
        # Given
        from chanlun_strategy.signal_combination import select_signals_by_market_environment
        from chanlun_strategy.signal_detector import Signal, SignalType
        
        low_confidence_buy1 = Signal(
            signal_type=SignalType.BUY_1,
            price=95.0,
            index=30,
            datetime=datetime(2026, 1, 31),
            confidence=65,  # 低于阈值
            reason='第一类买点：下跌趋势背驰（弱）'
        )
        
        high_confidence_buy1 = Signal(
            signal_type=SignalType.BUY_1,
            price=90.0,
            index=50,
            datetime=datetime(2026, 2, 20),
            confidence=85,  # 高于阈值
            reason='第一类买点：下跌趋势背驰（强）'
        )
        
        signals = [low_confidence_buy1, high_confidence_buy1]
        
        # When
        selected = select_signals_by_market_environment(
            signals=signals,
            market_env=downtrend_market_env
        )
        
        # Then
        assert len(selected) == 1, \
            f"预期只选择1个信号，实际选择{len(selected)}个"
        
        assert selected[0].confidence == 85, \
            "应选择高置信度的第一类买点"
    
    # ========================================================================
    # P0: 震荡市 - 选择一买
    # ========================================================================
    
    def test_sideways_market_select_buy1(self, sideways_market_env, mixed_signals):
        """
        TC-FU011-005 - P0: 震荡市选择一买
        
        Given:
        - 市场环境：震荡市
        - 信号列表：包含一二三类买点
        
        When:
        - 调用 select_signals_by_market_environment
        
        Then:
        - 返回第一类买点
        - 排除第二、第三类买点（震荡市中趋势不明确，不追涨）
        - 排除所有卖点
        """
        # Given
        from chanlun_strategy.signal_combination import select_signals_by_market_environment
        
        # When
        selected = select_signals_by_market_environment(
            signals=mixed_signals,
            market_env=sideways_market_env
        )
        
        # Then
        from chanlun_strategy.signal_detector import SignalType
        
        selected_types = [s.signal_type for s in selected]
        
        # 应该只包含第一类买点
        assert SignalType.BUY_1 in selected_types, \
            "震荡市应选择第一类买点"
        
        # 不应包含第二、第三类买点
        assert SignalType.BUY_2 not in selected_types, \
            "震荡市不应选择第二类买点（趋势不明确）"
        assert SignalType.BUY_3 not in selected_types, \
            "震荡市不应选择第三类买点（趋势不明确）"
        
        # 不应包含任何卖点
        sell_types = [SignalType.SELL_1, SignalType.SELL_2, SignalType.SELL_3]
        for sell_type in sell_types:
            assert sell_type not in selected_types, \
                f"震荡市不应选择{sell_type.value}"
    
    def test_sideways_market_signal_count_limit(self, sideways_market_env):
        """
        TC-FU011-006 - P0: 震荡市信号数量限制
        
        Given:
        - 市场环境：震荡市
        - 多个第一类买点信号
        
        When:
        - 选择信号
        
        Then:
        - 最多选择3个信号（震荡市操作保守）
        - 选择置信度最高的信号
        """
        # Given
        from chanlun_strategy.signal_combination import select_signals_by_market_environment
        from chanlun_strategy.signal_detector import Signal, SignalType
        
        signals = [
            Signal(
                signal_type=SignalType.BUY_1,
                price=100.0 - i,
                index=30 + i*20,
                datetime=datetime(2026, 1, 31) + pd.Timedelta(days=i*20),
                confidence=80 - i*5,
                reason=f'第一类买点{i+1}'
            )
            for i in range(5)
        ]
        
        # When
        selected = select_signals_by_market_environment(
            signals=signals,
            market_env=sideways_market_env
        )
        
        # Then
        assert len(selected) <= 3, \
            f"震荡市最多选择3个信号，实际选择{len(selected)}个"
        
        # 验证选择的是置信度最高的
        if len(selected) > 1:
            confidences = [s.confidence for s in selected]
            assert confidences == sorted(confidences, reverse=True), \
                "应按置信度降序选择信号"
    
    # ========================================================================
    # P1: 边界条件测试
    # ========================================================================
    
    def test_no_signals_return_empty_list(self, uptrend_market_env):
        """
        TC-FU011-007 - P1: 无信号返回空列表
        
        Given:
        - 市场环境：上涨趋势
        - 信号列表为空
        
        When:
        - 选择信号
        
        Then:
        - 返回空列表
        """
        # Given
        from chanlun_strategy.signal_combination import select_signals_by_market_environment
        
        # When
        selected = select_signals_by_market_environment(
            signals=[],
            market_env=uptrend_market_env
        )
        
        # Then
        assert selected == [], \
            "无信号时应返回空列表"
    
    def test_neutral_market_all_signals_accepted(self, mixed_signals):
        """
        TC-FU011-008 - P1: 中性市场接受所有信号
        
        Given:
        - 市场环境：中性（无法判断）
        
        When:
        - 选择信号
        
        Then:
        - 返回所有买入信号
        - 保守策略：不包含卖出信号
        """
        # Given
        from chanlun_strategy.signal_combination import select_signals_by_market_environment
        
        neutral_env = {
            'environment': 'neutral',
            'trend_direction': 'none',
            'zhongshu_list': [],
            'confidence': 0
        }
        
        # When
        selected = select_signals_by_market_environment(
            signals=mixed_signals,
            market_env=neutral_env
        )
        
        # Then
        from chanlun_strategy.signal_detector import SignalType
        
        # 应接受所有买入信号
        buy_types = [SignalType.BUY_1, SignalType.BUY_2, SignalType.BUY_3]
        for buy_type in buy_types:
            assert buy_type in [s.signal_type for s in selected], \
                f"中性市场应接受{buy_type.value}"
        
        # 不应包含卖出信号
        sell_types = [SignalType.SELL_1, SignalType.SELL_2, SignalType.SELL_3]
        for sell_type in sell_types:
            assert sell_type not in [s.signal_type for s in selected], \
                f"中性市场不应选择{sell_type.value}"
    
    def test_signal_combination_with_risk_management(self, uptrend_market_env, mixed_signals):
        """
        TC-FU011-009 - P1: 信号组合与风险管理
        
        Given:
        - 市场环境：上涨趋势
        - 信号列表包含多个高置信度信号
        
        When:
        - 选择信号并计算仓位
        
        Then:
        - 总仓位不超过限制
        - 单个信号仓位合理分配
        """
        # Given
        from chanlun_strategy.signal_combination import select_signals_with_position
        
        max_total_position = 0.8  # 最大总仓位
        
        # When
        selected = select_signals_with_position(
            signals=mixed_signals,
            market_env=uptrend_market_env,
            max_total_position=max_total_position
        )
        
        # Then
        # 验证总仓位
        total_position = sum(s.metadata.get('position_size', 0) for s in selected)
        assert total_position <= max_total_position, \
            f"总仓位{total_position}超过限制{max_total_position}"
        
        # 验证单个信号仓位
        for signal in selected:
            position = signal.metadata.get('position_size', 0)
            assert 0 < position <= 0.3, \
                f"单个信号仓位{position}不合理"


# ============================================================================
# 辅助函数测试
# ============================================================================

class TestSignalCombinationHelpers:
    """
    辅助函数测试
    """
    
    def test_calculate_overlap_ratio(self):
        """
        测试中枢重叠比例计算
        """
        # Given
        from chanlun_strategy.signal_combination import calculate_zhongshu_overlap_ratio
        from chanlun_strategy.chanlun_structure_v2 import Zhongshu
        
        zs1 = Zhongshu(zg=105.0, zd=100.0, start_index=10, end_index=50, level=1, bi_list=[])
        zs2 = Zhongshu(zg=108.0, zd=103.0, start_index=80, end_index=140, level=1, bi_list=[])
        
        # When
        overlap_ratio = calculate_zhongshu_overlap_ratio(zs1, zs2)
        
        # Then
        # 重叠区间: [103, 105] = 2
        # 最小中枢高度: 5
        # 重叠比例: 2/5 = 0.4
        assert abs(overlap_ratio - 0.4) < 0.01, \
            f"预期重叠比例0.4，实际得到{overlap_ratio}"
    
    def test_filter_signals_by_type(self):
        """
        测试按类型过滤信号
        """
        # Given
        from chanlun_strategy.signal_combination import filter_signals_by_type
        from chanlun_strategy.signal_detector import Signal, SignalType
        
        signals = [
            Signal(SignalType.BUY_1, 100.0, 10, datetime(2026, 1, 10), 80, 'BUY_1'),
            Signal(SignalType.BUY_2, 102.0, 20, datetime(2026, 1, 20), 75, 'BUY_2'),
            Signal(SignalType.SELL_1, 105.0, 30, datetime(2026, 1, 30), 85, 'SELL_1')
        ]
        
        # When
        buy_signals = filter_signals_by_type(signals, [SignalType.BUY_1, SignalType.BUY_2])
        
        # Then
        assert len(buy_signals) == 2
        assert all(s.signal_type in [SignalType.BUY_1, SignalType.BUY_2] for s in buy_signals)


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
