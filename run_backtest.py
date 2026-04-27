#!/usr/bin/env python3
"""
最终回测脚本 - 完整流程
"""
import sys
sys.path.insert(0, 'src')

import pymysql
import pandas as pd
import os
from datetime import datetime

print("="*60)
print("缠论策略 - 数据库回测")
print("="*60)

# 数据库连接
conn = pymysql.connect(
    host='127.0.0.1',
    port=33306,  # SSH隧道映射端口
    user='chanClaw',
    password='chanClaw@2026',
    database='chanClaw'
)

# 股票代码
stock_code = sys.argv[1] if len(sys.argv) > 1 else 'sh.600000'
print(f"\n[1] 获取股票数据: {stock_code}")

# 查询数据
query = f"""
SELECT 
    trade_date as date,
    open, high, low, close, volume, amount
FROM stock_daily 
WHERE ts_code = '{stock_code}'
ORDER BY trade_date DESC
LIMIT 120
"""

df = pd.read_sql(query, conn)
df = df.sort_values('date')

print(f"✓ 数据量: {len(df)} 条")
print(f"✓ 日期范围: {df['date'].min()} ~ {df['date'].max()}")
print(f"✓ 价格区间: {df['close'].min():.2f} ~ {df['close'].max():.2f}")

# 缠论分析
print("\n[2] 缠论结构分析...")
from chanlun_structure import ChanLunStructureAnalyzer

analyzer = ChanLunStructureAnalyzer(df)
result = analyzer.analyze()

print(f"✓ 分型: {len(result['fractals'])} 个")
print(f"✓ 笔: {len(result['bi_list'])} 个")
print(f"✓ 线段: {len(result['xianduan_list'])} 个")

zs = result['zhongshu']
if zs:
    print(f"✓ 中枢: ZG={zs.zg:.2f}, ZD={zs.zd:.2f}, 高度={zs.zg-zs.zd:.2f}")
else:
    print("⚠ 未检测到有效中枢")

# 信号识别
print("\n[3] 信号识别...")
current_price = float(df['close'].iloc[-1])
signals = []

if zs:
    if current_price > zs.zg:
        signals.append(f"✓ 突破中枢 ({current_price:.2f} > ZG {zs.zg:.2f})")
    elif current_price < zs.zd:
        signals.append(f"✓ 跌破中枢 ({current_price:.2f} < ZD {zs.zd:.2f})")
    else:
        signals.append(f"✓ 中枢震荡 (价格在 {zs.zd:.2f} - {zs.zg:.2f})")
    
    # 第三买点候选
    recent_low = float(df['low'].tail(20).min())
    if recent_low > zs.zd and current_price < zs.zg:
        signals.append(f"✓ 第三买点候选 (回抽{recent_low:.2f}不破ZD {zs.zd:.2f})")
    
    # 近期走势
    recent_change = (current_price / float(df['close'].iloc[-20]) - 1) * 100
    if abs(recent_change) > 5:
        signals.append(f"✓ 近期涨跌: {recent_change:+.2f}%")

for sig in signals:
    print(f"  {sig}")

# AI评估
api_key = os.getenv("AI_API_KEY")
if api_key and signals:
    print("\n[4] AI 评估...")
    try:
        from ai_evaluator import AIEvaluator
        evaluator = AIEvaluator(api_key=api_key)
        
        zhongshu_data = {'zg': float(zs.zg) if zs else 0, 'zd': float(zs.zd) if zs else 0}
        
        ai_result = evaluator.quick_evaluate(
            stock_code=stock_code,
            signal_type=signals[0] if signals else 'unknown',
            price=current_price,
            zhongshu=zhongshu_data
        )
        
        print("✓ AI 评估完成")
        if isinstance(ai_result, dict):
            action = ai_result.get('action', '')
            if action:
                print(f"  操作建议: {action}")
            raw = ai_result.get('raw_text', '')
            if raw and len(raw) > 50:
                print(f"  AI分析: {raw[:250]}...")
    except Exception as e:
        print(f"✗ AI评估失败: {e}")

# 生成报告
print("\n" + "="*60)
print("📊 评估报告")
print("="*60)
print(f"股票代码: {stock_code}")
print(f"当前价格: {current_price:.2f}")
print(f"数据日期: {df['date'].iloc[-1]}")

recent_change = (current_price / float(df['close'].iloc[0]) - 1) * 100
print(f"区间涨跌: {recent_change:+.2f}%")
print(f"波动率: {(df['close'].std() / df['close'].mean() * 100):.2f}%")

if zs:
    print(f"\n缠论结构:")
    print(f"  中枢区间: {zs.zd:.2f} - {zs.zg:.2f}")
    print(f"  中枢高度: {zs.zg-zs.zd:.2f}")
    
    if current_price > zs.zg:
        position = "中枢上方 ↑"
    elif current_price < zs.zd:
        position = "中枢下方 ↓"
    else:
        position = "中枢内 →"
    print(f"  价格位置: {position}")
    
    print(f"\n风控建议:")
    print(f"  建议仓位: 20%")
    print(f"  止损价格: {current_price * 0.95:.2f} (-5%)")
    print(f"  止盈价格: {current_price * 1.15:.2f} (+15%)")

print("\n信号列表:")
for i, sig in enumerate(signals, 1):
    print(f"  {i}. {sig}")

print("\n" + "="*60)

conn.close()
