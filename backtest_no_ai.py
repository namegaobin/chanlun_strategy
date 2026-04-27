#!/usr/bin/env python3
"""
纯缠论回测 - 不使用 AI 评估
针对真实数据库进行大规模缠论分析
"""
import sys
sys.path.insert(0, 'src')

import pymysql
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*70)
print("📊 纯缠论回测 - 无 AI 评估")
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
    HAVING cnt >= 100
    ORDER BY ts_code
    LIMIT 100
""")
stocks = cursor.fetchall()

print(f"✓ 选取 {len(stocks)} 只股票（数据量≥100）\n")

results = []

# 回测每只股票
print("[2] 开始缠论分析...")
print("-"*70)

for i, (code, data_count) in enumerate(stocks, 1):
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
        
        if len(df) < 60:
            continue
            
        current_price = float(df['close'].iloc[-1])
        recent_5d = (current_price / float(df['close'].iloc[-5]) - 1) * 100
        recent_20d = (current_price / float(df['close'].iloc[-20]) - 1) * 100
        
        # 缠论分析
        from chanlun_structure import ChanLunStructureAnalyzer
        analyzer = ChanLunStructureAnalyzer(df)
        result = analyzer.analyze()
        
        fractal_count = len(result['fractals'])
        bi_count = len(result['bi_list'])
        xd_count = len(result['xianduan_list'])
        zs = result['zhongshu']
        
        # 信号识别
        signal = "无信号"
        zs_info = ""
        
        if zs:
            if current_price > zs.zg:
                signal = "突破中枢⭐"
            elif current_price < zs.zd:
                signal = "跌破中枢"
            else:
                signal = "中枢震荡"
            
            zs_info = f"ZG={zs.zg:.2f}, ZD={zs.zd:.2f}"
            
            # 第三买点候选
            recent_low = float(df['low'].tail(20).min())
            if recent_low > zs.zd and current_price < zs.zg:
                signal += "+第三买点"
        
        # 输出结果
        status = "✓" if "突破" in signal or "第三买点" in signal else "•"
        print(f"{status} [{i}/{len(stocks)}] {code}: {current_price:>7.2f} | {recent_5d:>+6.2f}% | {signal:<20} | {bi_count}笔")
        
        results.append({
            'code': code,
            'price': current_price,
            'recent_5d': recent_5d,
            'recent_20d': recent_20d,
            'signal': signal,
            'fractal_count': fractal_count,
            'bi_count': bi_count,
            'zs_zg': float(zs.zg) if zs else None,
            'zs_zd': float(zs.zd) if zs else None
        })
        
    except Exception as e:
        print(f"✗ [{i}/{len(stocks)}] {code}: 错误 - {e}")

conn.close()

# ============================================
# 汇总分析
# ============================================
print("\n" + "="*70)
print("📊 回测汇总报告")
print("="*70)

df_results = pd.DataFrame(results)

# 1. 信号统计
print("\n【1. 信号分布】")
signal_counts = df_results['signal'].value_counts()
for sig, count in signal_counts.items():
    pct = count / len(df_results) * 100
    print(f"  {sig:<25} {count:>5}只 ({pct:>5.1f}%)")

# 2. 突破中枢的股票
print("\n【2. 突破中枢 - 强势股】")
breakout = df_results[df_results['signal'].str.contains('突破中枢')]
if not breakout.empty:
    print(f"  共 {len(breakout)} 只")
    print(f"  {'代码':<12} {'价格':>8} {'5日%':>8} {'20日%':>8} {'ZG':>8}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for _, row in breakout.head(10).iterrows():
        print(f"  {row['code']:<12} {row['price']:>8.2f} {row['recent_5d']:>+8.2f}% {row['recent_20d']:>+8.2f}% {row['zs_zg']:>8.2f}")

# 3. 第三买点候选
print("\n【3. 第三买点候选】")
third_buy = df_results[df_results['signal'].str.contains('第三买点')]
if not third_buy.empty:
    print(f"  共 {len(third_buy)} 只")
    for _, row in third_buy.head(10).iterrows():
        print(f"  • {row['code']}: {row['price']:.2f} ({row['recent_5d']:+.2f}%)")

# 4. 整体市场表现
print("\n【4. 整体市场表现】")
print(f"  分析股票: {len(df_results)} 只")
print(f"  平均5日涨跌: {df_results['recent_5d'].mean():+.2f}%")
print(f"  平均20日涨跌: {df_results['recent_20d'].mean():+.2f}%")
print(f"  5日上涨股票: {(df_results['recent_5d'] > 0).sum()}/{len(df_results)}只 ({(df_results['recent_5d'] > 0).sum()/len(df_results)*100:.1f}%)")
print(f"  20日上涨股票: {(df_results['recent_20d'] > 0).sum()}/{len(df_results)}只 ({(df_results['recent_20d'] > 0).sum()/len(df_results)*100:.1f}%)")

# 5. 保存报告
report_path = 'output/chanlun_backtest_report.md'
import os
os.makedirs('output', exist_ok=True)

with open(report_path, 'w', encoding='utf-8') as f:
    f.write(f"# 📊 纯缠论回测报告\n\n")
    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"## 统计概览\n\n")
    f.write(f"- 分析股票: {len(df_results)} 只\n")
    f.write(f"- 平均5日涨跌: {df_results['recent_5d'].mean():+.2f}%\n")
    f.write(f"- 平均20日涨跌: {df_results['recent_20d'].mean():+.2f}%\n\n")
    
    f.write(f"## 信号分布\n\n")
    for sig, count in signal_counts.items():
        f.write(f"- {sig}: {count}只\n")
    
    f.write(f"\n## 详细结果\n\n")
    f.write(f"| 代码 | 价格 | 5日% | 20日% | 信号 |\n")
    f.write(f"|------|------|------|-------|------|\n")
    
    for _, row in df_results.iterrows():
        f.write(f"| {row['code']} | {row['price']:.2f} | {row['recent_5d']:+.2f}% | {row['recent_20d']:+.2f}% | {row['signal']} |\n")

print(f"\n✅ 详细报告已保存: {report_path}")
print("="*70)
