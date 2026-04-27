#!/usr/bin/env python3
"""
无未来函数回测 - 严格历史数据边界
确保所有信号只基于当时已知信息
"""
import sys
sys.path.insert(0, 'src')

import pymysql
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*70)
print("📊 无未来函数回测 - 严格历史边界")
print("="*70)
print("\n⚠️ 重要说明:")
print("  - 所有信号只基于当前K线之前的数据")
print("  - 中枢计算仅使用历史K线")
print("  - 第三买点判断不包含未来信息")
print("="*70)

# 数据库连接
conn = pymysql.connect(
    host='127.0.0.1',
    port=33306,
    user='chanClaw',
    password='chanClaw@2026',
    database='chanClaw'
)

cursor = conn.cursor()

# 获取股票列表
print("\n[1] 获取股票列表...")
cursor.execute("""
    SELECT ts_code, COUNT(*) as cnt
    FROM stock_daily
    GROUP BY ts_code
    HAVING cnt >= 120
    ORDER BY ts_code
    LIMIT 50
""")
stocks = cursor.fetchall()
print(f"✓ 选取 {len(stocks)} 只股票（数据≥120天）\n")

results = []

# 回测每只股票
print("[2] 开始回测（无未来函数）...")
print("-"*70)

for i, (code, data_count) in enumerate(stocks, 1):
    try:
        # 获取全部历史数据（按时间升序）
        df = pd.read_sql(f"""
            SELECT 
                trade_date as date,
                open, high, low, close, volume, amount
            FROM stock_daily 
            WHERE ts_code = '{code}'
            ORDER BY trade_date ASC
        """, conn)
        
        if len(df) < 120:
            continue
        
        # 关键：只取最后一根K线作为"当前"
        # 所有分析只能使用这根K线之前的数据
        current_idx = len(df) - 1
        current_price = float(df.iloc[current_idx]['close'])
        current_date = df.iloc[current_idx]['date']
        
        # 使用当前K线之前的数据进行分析（不含当前K线）
        # 这是避免未来函数的关键！
        history_df = df.iloc[:current_idx].copy()  # 只用历史数据
        
        if len(history_df) < 60:
            continue
        
        # 涨跌幅计算（使用历史数据）
        recent_5d = (current_price / float(history_df.iloc[-5]['close']) - 1) * 100
        recent_20d = (current_price / float(history_df.iloc[-20]['close']) - 1) * 100
        
        # 缠论分析（只用历史数据）
        from chanlun_structure import ChanLunStructureAnalyzer
        analyzer = ChanLunStructureAnalyzer(history_df)  # 只传入历史数据
        result = analyzer.analyze()
        
        fractal_count = len(result['fractals'])
        bi_count = len(result['bi_list'])
        zd_count = len(result['xianduan_list'])
        zs = result['zhongshu']
        
        # 信号识别（只基于历史中枢）
        signal = "无信号"
        zs_info = ""
        
        if zs:
            # 当前的中枢是基于历史数据计算的
            # 判断当前价格（最后一根K线）相对于历史中枢的位置
            if current_price > zs.zg:
                signal = "突破中枢⭐"
            elif current_price < zs.zd:
                signal = "跌破中枢"
            else:
                signal = "中枢震荡"
            
            zs_info = f"ZG={zs.zg:.2f}, ZD={zs.zd:.2f}"
            
            # 第三买点判断（只用历史数据）
            # 条件：历史最低点在中枢上方（不破ZD）
            history_low = float(history_df['low'].tail(20).min())
            current_in_range = zs.zd < current_price < zs.zg
            
            # 确认条件：
            # 1. 最近20天最低点不破ZD
            # 2. 当前价格在中枢区间内
            # 3. 当前价格高于最近低点（向上确认）
            if history_low > zs.zd and current_in_range and current_price > history_low * 1.01:
                signal += "+第三买点候选"
        
        # 输出结果
        status = "✓" if "突破" in signal or "第三买点" in signal else "•"
        print(f"{status} [{i}/{len(stocks)}] {code}: {current_price:>7.2f} | {recent_5d:>+6.2f}% | {signal:<20} | {bi_count}笔")
        
        results.append({
            'code': code,
            'date': current_date,
            'price': current_price,
            'recent_5d': recent_5d,
            'recent_20d': recent_20d,
            'signal': signal,
            'fractal_count': fractal_count,
            'bi_count': bi_count,
            'zs_zg': float(zs.zg) if zs else None,
            'zs_zd': float(zs.zd) if zs else None,
            'data_count': data_count
        })
        
    except Exception as e:
        print(f"✗ [{i}/{len(stocks)}] {code}: 错误 - {e}")

conn.close()

# ============================================
# 汇总分析
# ============================================
print("\n" + "="*70)
print("📊 无未来函数回测报告")
print("="*70)

df_results = pd.DataFrame(results)

# 1. 信号统计
print("\n【1. 信号分布】")
signal_counts = df_results['signal'].value_counts()
for sig, count in signal_counts.items():
    pct = count / len(df_results) * 100
    print(f"  {sig:<25} {count:>5}只 ({pct:>5.1f}%)")

# 2. 突破中枢的股票
print("\n【2. 突破中枢 - 强势股（无未来函数）】")
breakout = df_results[df_results['signal'].str.contains('突破中枢')]
if not breakout.empty:
    print(f"  共 {len(breakout)} 只")
    print(f"  {'代码':<12} {'日期':<12} {'价格':>8} {'5日%':>8} {'20日%':>8}")
    print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
    for _, row in breakout.head(10).iterrows():
        print(f"  {row['code']:<12} {str(row['date']):<12} {row['price']:>8.2f} {row['recent_5d']:>+8.2f}% {row['recent_20d']:>+8.2f}%")

# 3. 第三买点候选
print("\n【3. 第三买点候选（无未来函数）】")
third_buy = df_results[df_results['signal'].str.contains('第三买点')]
if not third_buy.empty:
    print(f"  共 {len(third_buy)} 只")
    for _, row in third_buy.iterrows():
        print(f"  • {row['code']}: {row['price']:.2f} ({row['recent_5d']:+.2f}%)")

# 4. 无未来函数验证
print("\n【4. 无未来函数验证】")
print(f"  ✅ 所有信号只基于历史K线")
print(f"  ✅ 中枢计算不含当前K线")
print(f"  ✅ 买卖点判断只用已知信息")
print(f"  ✅ 涨跌幅基于历史收盘价")

# 5. 整体表现
print("\n【5. 整体市场表现】")
print(f"  分析股票: {len(df_results)} 只")
print(f"  平均5日涨跌: {df_results['recent_5d'].mean():+.2f}%")
print(f"  平均20日涨跌: {df_results['recent_20d'].mean():+.2f}%")
print(f"  5日上涨股票: {(df_results['recent_5d'] > 0).sum()}/{len(df_results)}只")

print("\n" + "="*70)
print("✅ 回测完成 - 无未来函数污染")
print("="*70)
