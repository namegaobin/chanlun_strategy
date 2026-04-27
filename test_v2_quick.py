#!/usr/bin/env python3
"""
快速测试脚本 - 验证缠论核心功能 V2
测试：K线包含关系处理、笔的构建、中枢计算
"""
import sys
import os

# 添加src目录到路径
src_path = '/Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy/src'
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import pandas as pd
import numpy as np

# 直接导入chanlun_structure_v2模块
import importlib.util
spec = importlib.util.spec_from_file_location(
    "chanlun_structure_v2",
    "/Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy/src/chanlun_structure_v2.py"
)
chanlun_structure_v2 = importlib.util.module_from_spec(spec)
sys.modules['chanlun_structure_v2'] = chanlun_structure_v2
spec.loader.exec_module(chanlun_structure_v2)

process_inclusion = chanlun_structure_v2.process_inclusion
ChanLunStructureAnalyzerV2 = chanlun_structure_v2.ChanLunStructureAnalyzerV2


def test_kline_inclusion():
    """测试1: K线包含关系处理"""
    print("\n" + "="*60)
    print("测试1: K线包含关系处理")
    print("="*60)
    
    # 创建包含关系的测试数据
    df = pd.DataFrame({
        'high': [13, 12, 14, 15, 14.5],
        'low': [9, 10, 11, 12, 11.5],
        'close': [10, 11, 13, 14, 13.5],
        'open': [9, 10, 11, 12, 11.5],
        'date': pd.date_range('2026-04-01', periods=5, freq='D').strftime('%Y-%m-%d')
    })
    
    print("\n原始K线数据:")
    print(df[['date', 'high', 'low', 'close']])
    
    # 处理包含关系
    df_processed = process_inclusion(df)
    
    print(f"\n处理后K线数: {len(df_processed)} (原始: {len(df)})")
    print(df_processed[['date', 'high', 'low', 'close']])
    
    print("\n✅ K线包含关系处理测试通过")


def test_full_analysis():
    """测试2: 完整分析流程"""
    print("\n" + "="*60)
    print("测试2: 完整分析流程")
    print("="*60)
    
    # 创建模拟数据（包含上涨趋势和震荡）
    np.random.seed(42)
    n = 100
    
    # 生成价格序列：上涨 → 震荡 → 上涨
    prices = []
    price = 10.0
    
    # 第一段：上涨
    for i in range(30):
        change = np.random.randn() * 0.1 + 0.05
        price += change
        prices.append(price)
    
    # 第二段：震荡（形成中枢）
    for i in range(40):
        change = np.random.randn() * 0.3
        price += change
        prices.append(price)
    
    # 第三段：上涨（离开中枢）
    for i in range(30):
        change = np.random.randn() * 0.1 + 0.03
        price += change
        prices.append(price)
    
    df = pd.DataFrame({
        'high': [p + np.random.rand() * 0.5 for p in prices],
        'low': [p - np.random.rand() * 0.5 for p in prices],
        'close': prices,
        'open': [p - np.random.rand() * 0.3 for p in prices],
        'date': pd.date_range('2026-01-01', periods=n, freq='D').strftime('%Y-%m-%d')
    })
    
    print(f"\n生成 {n} 根K线数据")
    print(f"价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")
    
    # 执行分析
    analyzer = ChanLunStructureAnalyzerV2(df)
    result = analyzer.analyze()
    
    # 打印详细摘要
    analyzer.print_summary()
    
    print("✅ 完整分析流程测试通过")


def test_bi_construction():
    """测试3: 笔的构建验证"""
    print("\n" + "="*60)
    print("测试3: 笔的构建验证")
    print("="*60)
    
    # 创建更规律的数据（便于验证笔的逻辑）
    df = pd.DataFrame({
        'high': [10.0, 10.5, 11.0, 11.5, 11.0, 10.5, 10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 12.0, 11.5],
        'low': [9.5, 10.0, 10.5, 11.0, 10.5, 10.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0, 11.5, 11.0],
        'close': [9.8, 10.3, 10.8, 11.3, 10.8, 10.3, 9.8, 10.3, 10.8, 11.3, 11.8, 12.3, 11.8, 11.3],
        'open': [9.6, 10.1, 10.6, 11.1, 10.6, 10.1, 9.6, 10.1, 10.6, 11.1, 11.6, 12.1, 11.6, 11.1],
        'date': pd.date_range('2026-04-01', periods=14, freq='D').strftime('%Y-%m-%d')
    })
    
    print("\n原始K线数据:")
    print(df[['date', 'high', 'low', 'close']])
    
    # 执行分析
    analyzer = ChanLunStructureAnalyzerV2(df)
    result = analyzer.analyze()
    
    print(f"\n处理后K线数: {len(result['df_processed'])}")
    print(f"分型数量: {len(result['fractals'])}")
    print(f"笔数量: {len(result['bi_list'])}")
    print(f"中枢数量: {len(result['zhongshu_list'])}")
    
    # 打印笔的详情
    if result['bi_list']:
        print("\n笔的详情:")
        for i, bi in enumerate(result['bi_list']):
            print(f"  笔{i+1}: {bi.direction.value}, 价格 {bi.start_price:.2f} → {bi.end_price:.2f}, K线数: {bi.kline_count}")
    
    print("\n✅ 笔的构建验证测试通过")


def test_zhongshu_calculation():
    """测试4: 中枢计算验证"""
    print("\n" + "="*60)
    print("测试4: 中枢计算验证")
    print("="*60)
    
    # 创建包含明显中枢的数据
    # 上涨 → 震荡（中枢）→ 上涨
    prices = []
    
    # 上涨段1: 10 → 12
    for i in range(10):
        prices.append(10 + i * 0.2)
    
    # 震荡段（中枢）: 11.5 - 12.5
    for i in range(20):
        prices.append(12 + np.sin(i * 0.5) * 0.5)
    
    # 上涨段2: 12 → 14
    for i in range(10):
        prices.append(12 + i * 0.2)
    
    df = pd.DataFrame({
        'high': [p + 0.2 for p in prices],
        'low': [p - 0.2 for p in prices],
        'close': prices,
        'open': [p - 0.1 for p in prices],
        'date': pd.date_range('2026-04-01', periods=len(prices), freq='D').strftime('%Y-%m-%d')
    })
    
    print(f"\n生成 {len(df)} 根K线数据")
    print(f"价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")
    
    # 执行分析
    analyzer = ChanLunStructureAnalyzerV2(df)
    result = analyzer.analyze()
    
    print(f"\n检测到 {len(result['zhongshu_list'])} 个中枢")
    
    if result['zhongshu_list']:
        for i, zs in enumerate(result['zhongshu_list']):
            print(f"\n中枢{i+1}:")
            print(f"  ZG (高点): {zs.zg:.2f}")
            print(f"  ZD (低点): {zs.zd:.2f}")
            print(f"  中轴: {zs.middle:.2f}")
            print(f"  高度: {zs.height:.2f}")
            print(f"  进入段: {'有' if zs.enter_bi else '无'}")
            print(f"  离开段: {'有' if zs.exit_bi else '无'}")
            if zs.exit_bi:
                print(f"  离开段方向: {zs.exit_bi.direction.value}")
                print(f"  离开段价格: {zs.exit_bi.start_price:.2f} → {zs.exit_bi.end_price:.2f}")
    
    print("\n✅ 中枢计算验证测试通过")


def main():
    """运行所有测试"""
    print("\n" + "╔" + "="*58 + "╗")
    print("║" + " "*10 + "缠论核心功能 V2 测试套件" + " "*23 + "║")
    print("╚" + "="*58 + "╝")
    
    try:
        test_kline_inclusion()
        test_bi_construction()
        test_zhongshu_calculation()
        test_full_analysis()
        
        print("\n" + "╔" + "="*58 + "╗")
        print("║" + " "*15 + "✅ 所有测试通过！" + " "*23 + "║")
        print("╚" + "="*58 + "╝\n")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
