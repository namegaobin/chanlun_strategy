#!/usr/bin/env python3
"""
测试脚本 - 使用更大的数据集测试笔的构建
"""
import importlib.util
import pandas as pd
import numpy as np

# 加载模块
spec = importlib.util.spec_from_file_location(
    "chanlun_structure_v2",
    "/Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy/src/chanlun_structure_v2.py"
)
chanlun = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chanlun)

print("="*60)
print("测试：更大的数据集（200根K线）")
print("="*60)

# 创建更大的数据集（模拟真实走势）
np.random.seed(42)
n = 200
prices = []

# 生成更真实的走势
price = 10.0
trend = 1  # 1=上涨, -1=下跌
trend_duration = 0

for i in range(n):
    # 随机改变趋势
    if np.random.rand() < 0.1:  # 10%概率改变趋势
        trend = -trend
    
    # 添加趋势性变化 + 随机波动
    change = trend * 0.05 + np.random.randn() * 0.15
    price += change
    prices.append(price)
    
    # 每隔一段时间改变趋势
    trend_duration += 1
    if trend_duration > np.random.randint(10, 30):
        trend = -trend
        trend_duration = 0

# 创建DataFrame
df = pd.DataFrame({
    'high': [p + np.random.rand() * 0.5 for p in prices],
    'low': [p - np.random.rand() * 0.5 for p in prices],
    'close': prices,
    'open': [p + np.random.randn() * 0.2 for p in prices],
    'date': pd.date_range('2026-01-01', periods=n, freq='D').strftime('%Y-%m-%d')
})

print(f"\n生成 {n} 根K线数据")
print(f"价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")

# 执行分析
analyzer = chanlun.ChanLunStructureAnalyzerV2(df)
result = analyzer.analyze()

print(f"\n【分析结果】")
print(f"处理后K线数: {len(result['df_processed'])}")
print(f"分型数量: {len(result['fractals'])}")
print(f"笔数量: {len(result['bi_list'])}")
print(f"中枢数量: {len(result['zhongshu_list'])}")

if result['bi_list']:
    print(f"\n【笔的详情】（前10笔）")
    for i, bi in enumerate(result['bi_list'][:10]):
        print(f"  笔{i+1}: {bi.direction.value:4s}, 价格 {bi.start_price:6.2f} → {bi.end_price:6.2f}, K线数: {bi.kline_count}")

if result['zhongshu_list']:
    print(f"\n【中枢详情】")
    for i, zs in enumerate(result['zhongshu_list']):
        print(f"  中枢{i+1}: ZG={zs.zg:.2f}, ZD={zs.zd:.2f}, 高度={zs.height:.2f}")
        print(f"    进入段: {'有' if zs.enter_bi else '无'}")
        print(f"    离开段: {'有' if zs.exit_bi else '无'}")

# 测试不同的min_klines参数
print("\n" + "="*60)
print("测试：不同min_klines参数的影响")
print("="*60)

for min_k in [3, 4, 5, 6]:
    fractals = result['fractals']
    bi_list = chanlun.build_bi_from_fractals(fractals, result['df_processed'], min_klines=min_k)
    print(f"min_klines={min_k}: 生成 {len(bi_list)} 笔")
