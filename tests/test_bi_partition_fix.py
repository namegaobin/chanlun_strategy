"""
Phase 1: RED - 笔划分逻辑测试用例

测试目标：
1. 验证笔必须顶底交替（不能连续同向笔）
2. 验证笔至少包含5根K线（缠论原文标准）
3. 验证笔的方向一致性（向上笔终点>起点，向下笔终点<起点）
4. 验证穿越中轴逻辑
5. 验证分型重新匹配机制

测试数据：使用 debug_bi.py 中的测试数据
"""
import pytest
import pandas as pd
import sys
sys.path.insert(0, '/Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy/src')

from chanlun_structure_v2 import (
    process_inclusion, detect_all_fractals, filter_fractals,
    build_bi_from_fractals, FractalType, Direction
)


class TestBiPartitionFix:
    """笔划分逻辑修复测试套件"""

    @pytest.fixture
    def sample_data(self):
        """创建测试数据：15根K线，产生5个分型（顶底顶底顶）"""
        prices = [10, 10.5, 11, 10.8, 10.3, 10.5, 11, 11.5, 11.2, 10.8, 11, 11.5, 12, 11.8, 11.5]
        df = pd.DataFrame({
            'high': [p + 0.3 for p in prices],
            'low': [p - 0.3 for p in prices],
            'close': prices,
            'open': [p for p in prices],
            'date': pd.date_range('2026-04-01', periods=len(prices), freq='D').strftime('%Y-%m-%d')
        })
        return df

    # ─────────────────────────────────────────────────────────────
    # AC-001: 笔必须顶底交替，不允许连续同向笔
    # ─────────────────────────────────────────────────────────────
    
    def test_bi_alternation_rule(self, sample_data):
        """
        AC-001: 验证笔序列顶底交替
        
        Given: 5个分型（顶底顶底顶）
        When: 执行笔划分
        Then: 生成的笔必须顶底交替，不允许连续同向笔
        """
        df_processed = process_inclusion(sample_data)
        fractals = detect_all_fractals(df_processed)
        fractals = filter_fractals(fractals)
        bi_list = build_bi_from_fractals(fractals, df_processed)
        
        # 断言：相邻两笔方向必须相反
        for i in range(len(bi_list) - 1):
            current_bi = bi_list[i]
            next_bi = bi_list[i + 1]
            assert current_bi.direction != next_bi.direction, \
                f"笔{i+1}和笔{i+2}方向相同（都是{current_bi.direction.value}），违反顶底交替规则"

    # ─────────────────────────────────────────────────────────────
    # AC-002: K线数量不足时的处理
    # ─────────────────────────────────────────────────────────────
    
    def test_bi_minimum_klines(self, sample_data):
        """
        AC-002: 验证笔至少包含5根K线
        
        Given: 两个分型之间只有3根K线
        When: 验证笔的成立条件
        Then: 该笔无效，但必须处理后续分型以确保序列正确
        """
        df_processed = process_inclusion(sample_data)
        fractals = detect_all_fractals(df_processed)
        fractals = filter_fractals(fractals)
        bi_list = build_bi_from_fractals(fractals, df_processed)
        
        # 断言：所有有效笔的K线数量 >= 5
        for bi in bi_list:
            assert bi.kline_count >= 5, \
                f"笔的K线数量{bi.kline_count}小于5，违反缠论原文规则"

    # ─────────────────────────────────────────────────────────────
    # AC-003: 笔的方向一致性
    # ─────────────────────────────────────────────────────────────
    
    def test_bi_direction_consistency(self, sample_data):
        """
        AC-003: 验证向上笔终点>起点，向下笔终点<起点
        
        Given: 生成的笔序列
        When: 检查方向一致性
        Then: 向上笔终点价格 > 起点价格；向下笔终点价格 < 起点价格
        """
        df_processed = process_inclusion(sample_data)
        fractals = detect_all_fractals(df_processed)
        fractals = filter_fractals(fractals)
        bi_list = build_bi_from_fractals(fractals, df_processed)
        
        for i, bi in enumerate(bi_list):
            if bi.direction == Direction.UP:
                assert bi.end_price > bi.start_price, \
                    f"笔{i+1}是向上笔但终点({bi.end_price}) <= 起点({bi.start_price})"
            else:
                assert bi.end_price < bi.start_price, \
                    f"笔{i+1}是向下笔但终点({bi.end_price}) >= 起点({bi.start_price})"

    # ─────────────────────────────────────────────────────────────
    # AC-004: 分型重新匹配机制
    # ─────────────────────────────────────────────────────────────
    
    def test_fractal_rematch_mechanism(self, sample_data):
        """
        AC-004: 验证笔无效时能够重新匹配分型对
        
        Given: 分型序列：顶A → 底B → 顶C → 底D → 顶E
        When: 顶C到底D的K线数量不足
        Then: 应尝试：顶A→底D，或底B→顶E，确保序列不断裂
        """
        df_processed = process_inclusion(sample_data)
        fractals = detect_all_fractals(df_processed)
        fractals = filter_fractals(fractals)
        bi_list = build_bi_from_fractals(fractals, df_processed)
        
        # 断言：即使中间有笔无效，最终生成的笔序列也应该有效
        # 检查：如果有5个分型，应该至少生成2笔（因为可能有些分型对不符合条件）
        # 但这2笔必须是顶底交替的
        
        if len(fractals) >= 4:
            # 至少应该生成一些笔
            assert len(bi_list) >= 1, \
                f"有{len(fractals)}个分型但没有生成任何笔"
            
            # 检查序列有效性
            for i in range(len(bi_list) - 1):
                assert bi_list[i].direction != bi_list[i+1].direction, \
                    "笔序列断裂，出现连续同向笔"

    # ─────────────────────────────────────────────────────────────
    # AC-005: 笔序列完整性
    # ─────────────────────────────────────────────────────────────
    
    def test_bi_sequence_integrity(self, sample_data):
        """
        AC-005: 验证笔序列完整性
        
        Given: 生成的笔序列
        When: 检查序列有效性
        Then: 相邻两笔方向必须相反
        """
        df_processed = process_inclusion(sample_data)
        fractals = detect_all_fractals(df_processed)
        fractals = filter_fractals(fractals)
        bi_list = build_bi_from_fractals(fractals, df_processed)
        
        if len(bi_list) >= 2:
            for i in range(len(bi_list) - 1):
                assert bi_list[i].direction != bi_list[i+1].direction, \
                    f"笔序列不完整：笔{i+1}和笔{i+2}方向相同"

    # ─────────────────────────────────────────────────────────────
    # AC-006: 穿越中轴逻辑（可选，P1）
    # ─────────────────────────────────────────────────────────────
    
    def test_cross_middle_line(self, sample_data):
        """
        AC-006: 验证笔穿越前笔中轴（形成中枢后）
        
        Given: 已有3笔，形成中枢
        When: 第4笔向上笔生成
        Then: 终点价格应 > 前一笔中轴价格
        """
        df_processed = process_inclusion(sample_data)
        fractals = detect_all_fractals(df_processed)
        fractals = filter_fractals(fractals)
        bi_list = build_bi_from_fractals(fractals, df_processed)
        
        # 只有4笔以上才检查穿越中轴
        if len(bi_list) >= 4:
            for i in range(3, len(bi_list)):
                prev_bi = bi_list[i - 1]
                current_bi = bi_list[i]
                mid_line = (prev_bi.high + prev_bi.low) / 2
                
                if current_bi.direction == Direction.UP:
                    # 向上笔：终点应高于中轴（允许10%误差）
                    assert current_bi.end_price >= mid_line * 0.9, \
                        f"笔{i+1}向上笔未穿越前笔中轴：终点{current_bi.end_price:.2f} < 中轴{mid_line:.2f}"
                else:
                    # 向下笔：终点应低于中轴（允许10%误差）
                    assert current_bi.end_price <= mid_line * 1.1, \
                        f"笔{i+1}向下笔未穿越前笔中轴：终点{current_bi.end_price:.2f} > 中轴{mid_line:.2f}"


class TestBiPartitionEdgeCases:
    """笔划分边界情况测试"""

    def test_exactly_5_klines(self):
        """
        边界情况：K线数量刚好等于5
        Expected: 有效笔
        """
        # 创建刚好5根K线的测试数据
        df = pd.DataFrame({
            'high': [11, 12, 13, 12, 11],
            'low': [10, 11, 12, 11, 10],
            'close': [10.5, 11.5, 12.5, 11.5, 10.5],
            'open': [10, 11, 12, 11, 10],
            'date': pd.date_range('2026-04-01', periods=5, freq='D').strftime('%Y-%m-%d')
        })
        
        df_processed = process_inclusion(df)
        fractals = detect_all_fractals(df_processed)
        fractals = filter_fractals(fractals)
        bi_list = build_bi_from_fractals(fractals, df_processed)
        
        # 如果有笔生成，K线数量应该 >= 5
        for bi in bi_list:
            assert bi.kline_count >= 5

    def test_4_klines_relaxed_rule(self):
        """
        边界情况：K线数量为4（放宽规则）
        Expected: 可接受，但需明确标注（当前代码允许）
        """
        df = pd.DataFrame({
            'high': [11, 12, 12.5, 11],
            'low': [10, 11, 11.5, 10],
            'close': [10.5, 11.8, 12, 10.5],
            'open': [10, 11, 12, 11],
            'date': pd.date_range('2026-04-01', periods=4, freq='D').strftime('%Y-%m-%d')
        })
        
        df_processed = process_inclusion(df)
        fractals = detect_all_fractals(df_processed)
        fractals = filter_fractals(fractals)
        bi_list = build_bi_from_fractals(fractals, df_processed, min_klines=4)
        
        # 当前代码 min_klines=4，所以4根K线的笔应该有效
        # 但按照缠论原文标准，这是不合规的
        # TODO: Phase 2 实现时需要处理这个边界情况

    def test_3_klines_invalid(self):
        """
        边界情况：K线数量为3
        Expected: 无效笔，需要处理分型匹配
        """
        df = pd.DataFrame({
            'high': [11, 12, 11],
            'low': [10, 11, 10],
            'close': [10.5, 11.5, 10.5],
            'open': [10, 11, 11],
            'date': pd.date_range('2026-04-01', periods=3, freq='D').strftime('%Y-%m-%d')
        })
        
        df_processed = process_inclusion(df)
        fractals = detect_all_fractals(df_processed)
        fractals = filter_fractals(fractals)
        bi_list = build_bi_from_fractals(fractals, df_processed)
        
        # K线数量 < 5，不应该生成笔
        # 但如果代码允许 min_klines=4，则3根K线仍然无效
        for bi in bi_list:
            assert bi.kline_count >= 4, \
                f"K线数量为{bi.kline_count}的笔不应该生成"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
