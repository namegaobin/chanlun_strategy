"""
市场环境识别模块测试 V2
测试基于中枢位置判断趋势/震荡

FU-010: 市场环境识别（基于中枢位置判断趋势/震荡）
BB-OPT-001: 重写 market_filter.py 使用中枢判断

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
def trending_market_data():
    """
    生成趋势市场数据
    
    特征：两个中枢不重叠
    - 第一个中枢：位置较低（95-100）
    - 第二个中枢：位置较高（110-115）
    - 符合趋势市定义：后续中枢不与前面中枢重叠
    """
    dates = pd.date_range('2026-01-01', periods=200, freq='D')
    
    # 第一阶段：震荡形成第一个中枢（95-100）
    phase1 = 97.5 + np.sin(np.linspace(0, 6*np.pi, 50)) * 2.5
    
    # 第二阶段：上涨突破
    phase2 = np.linspace(100, 112, 30)
    
    # 第三阶段：震荡形成第二个中枢（110-115）
    phase3 = 112.5 + np.sin(np.linspace(0, 6*np.pi, 60)) * 2.5
    
    # 第四阶段：继续上涨
    phase4 = np.linspace(115, 120, 60)
    
    prices = np.concatenate([phase1, phase2, phase3, phase4])
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': prices + np.abs(np.random.randn(200)) * 1.5,
        'low': prices - np.abs(np.random.randn(200)) * 1.5,
        'close': prices + np.random.randn(200) * 0.3,
        'volume': np.random.randint(1000000, 5000000, 200)
    })
    
    return df


@pytest.fixture
def sideways_market_data():
    """
    生成震荡市场数据
    
    特征：两个中枢重叠
    - 第一个中枢：位置在（100-105）
    - 第二个中枢：位置在（103-108）
    - 重叠区间：103-105
    - 符合震荡市定义：后续中枢与前面中枢有重叠
    """
    dates = pd.date_range('2026-01-01', periods=200, freq='D')
    
    # 第一阶段：震荡形成第一个中枢（100-105）
    phase1 = 102.5 + np.sin(np.linspace(0, 8*np.pi, 60)) * 2.5
    
    # 第二阶段：小幅上涨
    phase2 = np.linspace(105, 107, 20)
    
    # 第三阶段：震荡形成第二个中枢（103-108）
    phase3 = 105.5 + np.sin(np.linspace(0, 8*np.pi, 70)) * 2.5
    
    # 第四阶段：回落
    phase4 = np.linspace(105, 102, 50)
    
    prices = np.concatenate([phase1, phase2, phase3, phase4])
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': prices + np.abs(np.random.randn(200)) * 1.5,
        'low': prices - np.abs(np.random.randn(200)) * 1.5,
        'close': prices + np.random.randn(200) * 0.3,
        'volume': np.random.randint(1000000, 5000000, 200)
    })
    
    return df


# ============================================================================
# FU-010: 市场环境识别测试
# ============================================================================

class TestMarketEnvironmentDetectionV2:
    """
    FU-010: 市场环境识别（基于中枢位置判断趋势/震荡）
    
    测试策略：
    1. 使用中枢位置判断趋势市/震荡市
    2. 趋势市 = 两个中枢不重叠（同向）
    3. 震荡市 = 两个中枢重叠
    
    缠论定义：
    - 趋势：在任何级别的任何走势中，某完成的走势类型至少包含两个以上依次同向的中枢
    - 盘整：在任何级别的任何走势中，某完成的走势类型只包含一个中枢
    """
    
    # ========================================================================
    # P0: 趋势市识别（两个中枢不重叠）
    # ========================================================================
    
    def test_trending_market_two_non_overlapping_zhongshus(self, trending_market_data):
        """
        TC-FU010-001 - P0: 趋势市识别（两个中枢不重叠）
        
        Given:
        - K线数据包含两个中枢
        - 第一个中枢区间：[95, 100]
        - 第二个中枢区间：[110, 115]
        - 两个中枢无重叠（100 < 110）
        
        When:
        - 调用 detect_market_environment_v2(kline_data, zhongshu_list)
        
        Then:
        - 返回 MarketEnvironment.TRENDING
        - trend_direction = 'up'（第二个中枢在第一个中枢之上）
        - confidence >= 0.8
        """
        # Given: 准备中枢数据
        from chanlun_strategy.chanlun_structure_v2 import Zhongshu, Bi, Direction
        
        # 创建第一个中枢（95-100）
        zs1 = Zhongshu(
            zg=100.0,
            zd=95.0,
            start_index=10,
            end_index=50,
            level=1,
            bi_list=[]
        )
        
        # 创建第二个中枢（110-115）
        zs2 = Zhongshu(
            zg=115.0,
            zd=110.0,
            start_index=80,
            end_index=140,
            level=1,
            bi_list=[]
        )
        
        zhongshu_list = [zs1, zs2]
        
        # When: 调用市场环境检测
        from chanlun_strategy.market_filter_v2 import detect_market_environment_v2
        
        result = detect_market_environment_v2(
            df=trending_market_data,
            zhongshu_list=zhongshu_list
        )
        
        # Then: 验证结果
        assert result['environment'] == 'trending', \
            f"预期趋势市，实际得到：{result['environment']}"
        
        assert result['trend_direction'] == 'up', \
            f"预期上涨趋势，实际得到：{result['trend_direction']}"
        
        assert result['confidence'] >= 0.8, \
            f"预期置信度 >= 0.8，实际得到：{result['confidence']}"
        
        # 验证中枢重叠信息
        assert result['zhongshu_overlap'] is False, \
            "趋势市中中枢不应重叠"
    
    def test_trending_downtrend_two_non_overlapping_zhongshus(self, sample_kline_data):
        """
        TC-FU010-002 - P0: 下跌趋势市识别（两个中枢不重叠）
        
        Given:
        - 两个中枢位置递减
        - 第一个中枢：[110, 115]
        - 第二个中枢：[95, 100]
        - 两个中枢无重叠（110 > 100）
        
        When:
        - 调用市场环境检测
        
        Then:
        - 返回 MarketEnvironment.TRENDING
        - trend_direction = 'down'
        """
        # Given
        from chanlun_strategy.chanlun_structure_v2 import Zhongshu
        
        zs1 = Zhongshu(zg=115.0, zd=110.0, start_index=10, end_index=50, level=1, bi_list=[])
        zs2 = Zhongshu(zg=100.0, zd=95.0, start_index=80, end_index=140, level=1, bi_list=[])
        
        zhongshu_list = [zs1, zs2]
        
        # When
        from chanlun_strategy.market_filter_v2 import detect_market_environment_v2
        
        result = detect_market_environment_v2(
            df=sample_kline_data,
            zhongshu_list=zhongshu_list
        )
        
        # Then
        assert result['environment'] == 'trending'
        assert result['trend_direction'] == 'down'
        assert result['zhongshu_overlap'] is False
    
    # ========================================================================
    # P0: 震荡市识别（中枢重叠）
    # ========================================================================
    
    def test_sideways_market_overlapping_zhongshus(self, sideways_market_data):
        """
        TC-FU010-003 - P0: 震荡市识别（两个中枢重叠）
        
        Given:
        - K线数据包含两个中枢
        - 第一个中枢区间：[100, 105]
        - 第二个中枢区间：[103, 108]
        - 重叠区间：[103, 105]
        - 重叠比例：(105-103) / min(105-100, 108-103) = 2/5 = 40%
        
        When:
        - 调用 detect_market_environment_v2
        
        Then:
        - 返回 MarketEnvironment.SIDEWAYS
        - trend_direction = 'none'（无明确趋势）
        - overlapping_range 存在
        - overlapping_ratio >= 0.3（30%重叠阈值）
        """
        # Given
        from chanlun_strategy.chanlun_structure_v2 import Zhongshu
        
        # 第一个中枢（100-105）
        zs1 = Zhongshu(
            zg=105.0,
            zd=100.0,
            start_index=10,
            end_index=60,
            level=1,
            bi_list=[]
        )
        
        # 第二个中枢（103-108）
        zs2 = Zhongshu(
            zg=108.0,
            zd=103.0,
            start_index=80,
            end_index=150,
            level=1,
            bi_list=[]
        )
        
        zhongshu_list = [zs1, zs2]
        
        # When
        from chanlun_strategy.market_filter_v2 import detect_market_environment_v2
        
        result = detect_market_environment_v2(
            df=sideways_market_data,
            zhongshu_list=zhongshu_list
        )
        
        # Then
        assert result['environment'] == 'sideways', \
            f"预期震荡市，实际得到：{result['environment']}"
        
        assert result['trend_direction'] == 'none', \
            f"震荡市应无明确趋势，实际得到：{result['trend_direction']}"
        
        assert result['zhongshu_overlap'] is True, \
            "震荡市中枢应重叠"
        
        # 验证重叠区间
        overlap_range = result.get('overlap_range')
        assert overlap_range is not None, "应计算重叠区间"
        assert overlap_range['low'] == 103.0
        assert overlap_range['high'] == 105.0
        
        # 验证重叠比例
        overlap_ratio = result.get('overlap_ratio', 0)
        assert overlap_ratio >= 0.3, \
            f"预期重叠比例 >= 30%，实际得到：{overlap_ratio * 100:.1f}%"
    
    def test_sideways_market_three_overlapping_zhongshus(self, sample_kline_data):
        """
        TC-FU010-004 - P0: 多个中枢重叠识别为震荡市
        
        Given:
        - 三个中枢位置相近
        - 中枢1：[100, 105]
        - 中枢2：[103, 108]
        - 中枢3：[102, 107]
        - 所有中枢都有重叠
        
        When:
        - 调用市场环境检测
        
        Then:
        - 返回 MarketEnvironment.SIDEWAYS
        - all_zhongshus_overlapping = True
        """
        # Given
        from chanlun_strategy.chanlun_structure_v2 import Zhongshu
        
        zs1 = Zhongshu(zg=105.0, zd=100.0, start_index=10, end_index=50, level=1, bi_list=[])
        zs2 = Zhongshu(zg=108.0, zd=103.0, start_index=60, end_index=100, level=1, bi_list=[])
        zs3 = Zhongshu(zg=107.0, zd=102.0, start_index=110, end_index=150, level=1, bi_list=[])
        
        zhongshu_list = [zs1, zs2, zs3]
        
        # When
        from chanlun_strategy.market_filter_v2 import detect_market_environment_v2
        
        result = detect_market_environment_v2(
            df=sample_kline_data,
            zhongshu_list=zhongshu_list
        )
        
        # Then
        assert result['environment'] == 'sideways'
        assert result.get('all_zhongshus_overlapping', False) is True
    
    # ========================================================================
    # P1: 边界条件测试
    # ========================================================================
    
    def test_single_zhongshu_identified_as_consolidation(self, sample_kline_data):
        """
        TC-FU010-005 - P1: 单中枢识别为盘整
        
        Given:
        - 只有一个中枢
        
        When:
        - 调用市场环境检测
        
        Then:
        - 返回 MarketEnvironment.CONSOLIDATION
        - 无法判断趋势方向
        """
        # Given
        from chanlun_strategy.chanlun_structure_v2 import Zhongshu
        
        zs1 = Zhongshu(zg=105.0, zd=100.0, start_index=10, end_index=100, level=1, bi_list=[])
        zhongshu_list = [zs1]
        
        # When
        from chanlun_strategy.market_filter_v2 import detect_market_environment_v2
        
        result = detect_market_environment_v2(
            df=sample_kline_data,
            zhongshu_list=zhongshu_list
        )
        
        # Then
        assert result['environment'] == 'consolidation', \
            f"单中枢应识别为盘整，实际得到：{result['environment']}"
    
    def test_no_zhongshu_identified_as_neutral(self, sample_kline_data):
        """
        TC-FU010-006 - P1: 无中枢识别为中性
        
        Given:
        - 没有中枢
        
        When:
        - 调用市场环境检测
        
        Then:
        - 返回 MarketEnvironment.NEUTRAL
        - 需要更多数据才能判断
        """
        # Given
        zhongshu_list = []
        
        # When
        from chanlun_strategy.market_filter_v2 import detect_market_environment_v2
        
        result = detect_market_environment_v2(
            df=sample_kline_data,
            zhongshu_list=zhongshu_list
        )
        
        # Then
        assert result['environment'] == 'neutral', \
            f"无中枢应返回中性，实际得到：{result['environment']}"
    
    def test_zhongshu_overlap_threshold_detection(self, sample_kline_data):
        """
        TC-FU010-007 - P1: 中枢重叠阈值检测
        
        Given:
        - 两个中枢
        - 中枢1：[100, 105]
        - 中枢2：[104.5, 109.5]
        - 重叠区间：[104.5, 105] = 0.5
        - 重叠比例：0.5 / 5 = 10%（低于30%阈值）
        
        When:
        - 调用市场环境检测
        
        Then:
        - 返回 MarketEnvironment.TRENDING（重叠不足）
        - zhongshu_overlap_ratio < 0.3
        """
        # Given
        from chanlun_strategy.chanlun_structure_v2 import Zhongshu
        
        zs1 = Zhongshu(zg=105.0, zd=100.0, start_index=10, end_index=50, level=1, bi_list=[])
        zs2 = Zhongshu(zg=109.5, zd=104.5, start_index=80, end_index=140, level=1, bi_list=[])
        
        zhongshu_list = [zs1, zs2]
        
        # When
        from chanlun_strategy.market_filter_v2 import detect_market_environment_v2
        
        result = detect_market_environment_v2(
            df=sample_kline_data,
            zhongshu_list=zhongshu_list
        )
        
        # Then
        assert result['environment'] == 'trending', \
            f"重叠不足应识别为趋势市，实际得到：{result['environment']}"
        
        overlap_ratio = result.get('overlap_ratio', 0)
        assert overlap_ratio < 0.3, \
            f"预期重叠比例 < 30%，实际得到：{overlap_ratio * 100:.1f}%"


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
