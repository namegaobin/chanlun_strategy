#!/usr/bin/env python3
"""
全市场评估 - 无未来函数
评估所有股票，找出潜在机会
"""
import sys
sys.path.insert(0, 'src')

import pymysql
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*70)
print("📊 全市场评估 - 无未来函数")
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

# 获取所有股票列表
print("\n[1] 获取全市场股票列表...")
cursor.execute("""
    SELECT ts_code, COUNT(*) as cnt
    FROM stock_daily
    GROUP BY ts_code
    HAVING cnt >= 120
    ORDER BY ts_code
""")
stocks = cursor.fetchall()
print(f"✓ 共 {len(stocks)} 只股票（数据≥120天）\n")

results = []
breakout_stocks = []
third_buy_stocks = []

# 回测每只股票
print("[2] 开始全市场评估...")
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
        
        # 只取最后一根K线作为"当前"
        current_idx = len(df) - 1
        current_price = float(df.iloc[current_idx]['close'])
        current_date = df.iloc[current_idx]['date']
        
        # 使用当前K线之前的数据进行分析
        history_df = df.iloc[:current_idx].copy()
        
        if len(history_df) < 60:
            continue
        
        # 涨跌幅计算
        recent_5d = (current_price / float(history_df.iloc[-5]['close']) - 1) * 100
        recent_20d = (current_price / float(history_df.iloc[-20]['close']) - 1) * 100
        
        # 缠论分析（只用历史数据）
        from chanlun_structure import ChanLunStructureAnalyzer
        analyzer = ChanLunStructureAnalyzer(history_df)
        result = analyzer.analyze()
        
        fractal_count = len(result['fractals'])
        bi_count = len(result['bi_list'])
        zs = result['zhongshu']
        
        # 信号识别
        signal = "无信号"
        
        if zs:
            if current_price > zs.zg:
                signal = "突破中枢⭐"
                breakout_stocks.append({
                    'code': code,
                    'date': current_date,
                    'price': current_price,
                    'recent_5d': recent_5d,
                    'recent_20d': recent_20d,
                    'zs_zg': float(zs.zg),
                    'zs_zd': float(zs.zd),
                    'bi_count': bi_count
                })
            elif current_price < zs.zd:
                signal = "跌破中枢"
            else:
                signal = "中枢震荡"
            
            # 第三买点判断
            history_low = float(history_df['low'].tail(20).min())
            current_in_range = zs.zd < current_price < zs.zg
            
            if history_low > zs.zd and current_in_range and current_price > history_low * 1.01:
                signal += "+第三买点候选"
                third_buy_stocks.append({
                    'code': code,
                    'date': current_date,
                    'price': current_price,
                    'recent_5d': recent_5d,
                    'recent_20d': recent_20d,
                    'zs_zg': float(zs.zg),
                    'zs_zd': float(zs.zd)
                })
        
        results.append({
            'code': code,
            'date': current_date,
            'price': current_price,
            'recent_5d': recent_5d,
            'recent_20d': recent_20d,
            'signal': signal,
            'bi_count': bi_count
        })
        
        # 进度显示（每100只显示一次）
        if i % 100 == 0:
            print(f"  已处理: {i}/{len(stocks)} 只股票...")
        
    except Exception as e:
        pass

conn.close()

# ============================================
# 汇总分析
# ============================================
print("\n" + "="*70)
print("📊 全市场评估报告")
print("="*70)

df_results = pd.DataFrame(results)

# 1. 信号统计
print("\n【1. 信号分布】")
signal_counts = df_results['signal'].value_counts()
for sig, count in signal_counts.items():
    pct = count / len(df_results) * 100
    print(f"  {sig:<30} {count:>6}只 ({pct:>5.1f}%)")

# 2. 突破中枢股票
print("\n【2. 突破中枢股票 - 按涨跌幅排序】")
if breakout_stocks:
    df_breakout = pd.DataFrame(breakout_stocks)
    df_breakout = df_breakout.sort_values('recent_5d', ascending=False)
    
    print(f"  共 {len(df_breakout)} 只")
    print(f"  {'代码':<12} {'价格':>8} {'5日%':>8} {'20日%':>8} {'ZG':>8}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    
    for _, row in df_breakout.head(20).iterrows():
        print(f"  {row['code']:<12} {row['price']:>8.2f} {row['recent_5d']:>+8.2f}% {row['recent_20d']:>+8.2f}% {row['zs_zg']:>8.2f}")

# 3. 第三买点候选
print("\n【3. 第三买点候选】")
if third_buy_stocks:
    df_third = pd.DataFrame(third_buy_stocks)
    df_third = df_third.sort_values('recent_5d', ascending=False)
    
    print(f"  共 {len(df_third)} 只")
    print(f"  {'代码':<12} {'价格':>8} {'5日%':>8} {'20日%':>8}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
    
    for _, row in df_third.head(15).iterrows():
        print(f"  {row['code']:<12} {row['price']:>8.2f} {row['recent_5d']:>+8.2f}% {row['recent_20d']:>+8.2f}%")

# 4. 市场整体表现
print("\n【4. 市场整体表现】")
print(f"  评估股票: {len(df_results)} 只")
print(f"  平均5日涨跌: {df_results['recent_5d'].mean():+.2f}%")
print(f"  平均20日涨跌: {df_results['recent_20d'].mean():+.2f}%")
print(f"  5日上涨股票: {(df_results['recent_5d'] > 0).sum()}/{len(df_results)}只 ({(df_results['recent_5d'] > 0).sum()/len(df_results)*100:.1f}%)")
print(f"  20日上涨股票: {(df_results['recent_20d'] > 0).sum()}/{len(df_results)}只 ({(df_results['recent_20d'] > 0).sum()/len(df_results)*100:.1f}%)")

# 5. 保存详细报告
import os
os.makedirs('output', exist_ok=True)

report_path = 'output/full_market_evaluation.md'
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(f"# 📊 全市场评估报告（无未来函数）\n\n")
    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    f.write(f"## 市场概况\n\n")
    f.write(f"- 评估股票: {len(df_results)} 只\n")
    f.write(f"- 平均5日涨跌: {df_results['recent_5d'].mean():+.2f}%\n")
    f.write(f"- 平均20日涨跌: {df_results['recent_20d'].mean():+.2f}%\n\n")
    
    f.write(f"## 信号分布\n\n")
    for sig, count in signal_counts.items():
        f.write(f"- {sig}: {count}只 ({count/len(df_results)*100:.1f}%)\n")
    
    if breakout_stocks:
        f.write(f"\n## 突破中枢股票（{len(breakout_stocks)}只）\n\n")
        f.write(f"| 代码 | 价格 | 5日% | 20日% | ZG |\n")
        f.write(f"|------|------|------|-------|-----|\n")
        for _, row in df_breakout.head(30).iterrows():
            f.write(f"| {row['code']} | {row['price']:.2f} | {row['recent_5d']:+.2f}% | {row['recent_20d']:+.2f}% | {row['zs_zg']:.2f} |\n")
    
    if third_buy_stocks:
        f.write(f"\n## 第三买点候选（{len(third_buy_stocks)}只）\n\n")
        f.write(f"| 代码 | 价格 | 5日% | 20日% |\n")
        f.write(f"|------|------|------|-------|\n")
        for _, row in df_third.iterrows():
            f.write(f"| {row['code']} | {row['price']:.2f} | {row['recent_5d']:+.2f}% | {row['recent_20d']:+.2f}% |\n")

print(f"\n✅ 详细报告已保存: {report_path}")
print("="*70)
