#!/usr/bin/env python3
"""
真实数据库回测 - 针对大盘股进行缠论分析
"""
import sys
sys.path.insert(0, 'src')

import pymysql
import pandas as pd
import os
from datetime import datetime

print("="*70)
print("📊 真实数据库回测 - 20只大盘股分析")
print("="*70)

# 使用新端口连接
conn = pymysql.connect(
    host='127.0.0.1',
    port=33306,
    user='chanClaw',
    password='chanClaw@2026',
    database='chanClaw'
)

cursor = conn.cursor()

# 获取大盘股（数据量最多的股票）
print("\n[1] 获取大盘股列表...")
cursor.execute("""
    SELECT ts_code, COUNT(*) as cnt
    FROM stock_daily
    GROUP BY ts_code
    ORDER BY cnt DESC
    LIMIT 20
""")
top_stocks = cursor.fetchall()

print(f"✓ 选取数据量最多的20只股票\n")

# AI评估器
api_key = os.getenv("AI_API_KEY")
if api_key:
    from ai_evaluator import AIEvaluator
    ai_evaluator = AIEvaluator(api_key=api_key)
    print("✓ AI评估已启用\n")

results = []

# 回测每只股票
for i, (code, data_count) in enumerate(top_stocks, 1):
    print(f"[{i}/20] {code} ({data_count}条数据)", end=" ")
    
    try:
        # 获取最近120天数据
        df = pd.read_sql(f"""
            SELECT 
                trade_date as date,
                open, high, low, close, volume, amount
            FROM stock_daily 
            WHERE ts_code = '{code}'
            ORDER BY trade_date DESC
            LIMIT 120
        """, conn)
        df = df.sort_values('date')
        
        current_price = float(df['close'].iloc[-1])
        recent_20d = (current_price / float(df['close'].iloc[-20]) - 1) * 100
        
        # 缠论分析
        from chanlun_structure import ChanLunStructureAnalyzer
        analyzer = ChanLunStructureAnalyzer(df)
        result = analyzer.analyze()
        
        zs = result['zhongshu']
        signal = "无信号"
        
        if zs:
            if current_price > zs.zg:
                signal = "突破中枢⭐"
            elif current_price < zs.zd:
                signal = "跌破中枢"
            else:
                signal = "中枢震荡"
        
        print(f"价格={current_price:.2f}, 涨跌={recent_20d:+.2f}%, {signal}")
        
        results.append({
            'code': code,
            'price': current_price,
            'change': recent_20d,
            'signal': signal,
            'zs_zg': float(zs.zg) if zs else None,
            'zs_zd': float(zs.zd) if zs else None,
            'data_count': data_count
        })
        
    except Exception as e:
        print(f"错误: {e}")

conn.close()

# 汇总报告
print("\n" + "="*70)
print("📊 回测汇总")
print("="*70)

df_results = pd.DataFrame(results)

# 信号统计
print("\n【信号统计】")
signal_counts = df_results['signal'].value_counts()
for sig, count in signal_counts.items():
    print(f"  {sig}: {count}只")

# 突破中枢
print("\n【突破中枢 - 强势股】")
breakout = df_results[df_results['signal'].str.contains('突破')]
if not breakout.empty:
    for _, row in breakout.iterrows():
        print(f"  ✓ {row['code']}: {row['price']:.2f} ({row['change']:+.2f}%)")

# 整体表现
print("\n【整体表现】")
print(f"  平均20日涨跌: {df_results['change'].mean():+.2f}%")
print(f"  上涨股票: {(df_results['change'] > 0).sum()}/20只")

print("\n" + "="*70)
