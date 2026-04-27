#!/usr/bin/env python3
"""
调试脚本 - 诊断笔构建问题
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

# 创建简单的测试数据
print("创建测试数据...")
prices = [10, 10.5, 11, 10.8, 10.3, 10.5, 11, 11.5, 11.2, 10.8, 11, 11.5, 12, 11.8, 11.5]
df = pd.DataFrame({
    'high': [p + 0.3 for p in prices],
    'low': [p - 0.3 for p in prices],
    'close': prices,
    'open': [p for p in prices],
    'date': pd.date_range('2026-04-01', periods=len(prices), freq='D').strftime('%Y-%m-%d')
})

print("原始K线:")
print(df[['date', 'high', 'low', 'close']])

# 处理包含关系
df_processed = chanlun.process_inclusion(df)
print(f"\n处理后K线数: {len(df_processed)}")

# 检测分型
fractals = chanlun.detect_all_fractals(df_processed)
print(f"\n检测到 {len(fractals)} 个分型:")
for i, f in enumerate(fractals):
    print(f"  分型{i+1}: {f.type.value}, 索引{f.index}, 价格{f.price:.2f}")

# 过滤分型
fractals_filtered = chanlun.filter_fractals(fractals)
print(f"\n过滤后 {len(fractals_filtered)} 个分型:")
for i, f in enumerate(fractals_filtered):
    print(f"  分型{i+1}: {f.type.value}, 索引{f.index}, 价格{f.price:.2f}")

# 构建笔 - 手动模拟
print("\n=== 笔构建过程 ===")
bi_list = []
for i in range(len(fractals_filtered) - 1):
    f1 = fractals_filtered[i]
    f2 = fractals_filtered[i + 1]
    
    print(f"\n检查分型对 {i+1}:")
    print(f"  f1: {f1.type.value} @ {f1.price:.2f} (索引{f1.index})")
    print(f"  f2: {f2.type.value} @ {f2.price:.2f} (索引{f2.index})")
    
    # 必须是顶底交替
    if f1.type == f2.type:
        print("  ❌ 同类型，跳过")
        continue
    
    # 确定方向
    if f1.type == chanlun.FractalType.BOTTOM and f2.type == chanlun.FractalType.TOP:
        direction = chanlun.Direction.UP
        start_price = f1.price
        end_price = f2.price
        print(f"  方向: 向上笔")
    else:
        direction = chanlun.Direction.DOWN
        start_price = f1.price
        end_price = f2.price
        print(f"  方向: 向下笔")
    
    # 检查K线数量
    kline_count = f2.index - f1.index + 1
    print(f"  K线数量: {kline_count} (要求 >= 4)")
    if kline_count < 4:
        print("  ❌ K线数量不足，跳过")
        continue
    
    # 检查方向一致性
    if direction == chanlun.Direction.UP and end_price <= start_price:
        print(f"  ❌ 向上笔但终点({end_price:.2f}) <= 起点({start_price:.2f})")
        continue
    if direction == chanlun.Direction.DOWN and end_price >= start_price:
        print(f"  ❌ 向下笔但终点({end_price:.2f}) >= 起点({start_price:.2f})")
        continue
    
    print(f"  ✅ 有效笔: {direction.value}, {start_price:.2f} → {end_price:.2f}")
    
    bi_data = df_processed.iloc[f1.index:f2.index + 1]
    high = bi_data['high'].max()
    low = bi_data['low'].min()
    
    bi = chanlun.Bi(
        direction=direction,
        start_index=f1.index,
        end_index=f2.index,
        start_price=start_price,
        end_price=end_price,
        high=high,
        low=low,
        kline_count=kline_count
    )
    bi_list.append(bi)

print(f"\n最终生成 {len(bi_list)} 笔")
for i, bi in enumerate(bi_list):
    print(f"  笔{i+1}: {bi.direction.value}, {bi.start_price:.2f} → {bi.end_price:.2f}, K线数{bi.kline_count}")
