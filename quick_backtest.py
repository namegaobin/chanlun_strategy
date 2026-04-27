#!/usr/bin/env python3
"""快速回测 - 简化版"""
import sys
import os
sys.path.insert(0, 'src')

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import numpy as np

print("="*60)
print("缠论策略快速回测")
print("="*60)

# 测试股票
stock_code = sys.argv[1] if len(sys.argv) > 1 else "sh.600000"
print(f"\n股票代码: {stock_code}")

# 1. 数据获取
print("\n[1] 获取数据...")
from data_fetcher import DataFetcher

with DataFetcher() as fetcher:
    df = fetcher.fetch_daily_kline(stock_code, "2026-02-01", "2026-04-14")

if df is None or df.empty:
    print("⚠ 未获取到数据（可能非交易时间）")
    # 使用模拟数据
    print("使用模拟数据进行演示...")
    dates = pd.date_range('2026-02-01', periods=50)
    prices = 10 + np.cumsum(np.random.randn(50) * 0.03)
    df = pd.DataFrame({
        'date': dates,
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': [1000000] * 50
    })

print(f"✓ 数据量: {len(df)} 条")
print(f"✓ 价格区间: {df['close'].min():.2f} - {df['close'].max():.2f}")
print(f"✓ 最新价格: {df['close'].iloc[-1]:.2f}")

# 2. 缠论分析
print("\n[2] 缠论结构分析...")
from chanlun_structure import ChanLunStructureAnalyzer

analyzer = ChanLunStructureAnalyzer(df)
result = analyzer.analyze()

print(f"✓ 分型: {len(result['fractals'])} 个")
print(f"✓ 笔: {len(result['bi_list'])} 个")
print(f"✓ 线段: {len(result['xianduan_list'])} 个")

if result['zhongshu']:
    zs = result['zhongshu']
    print(f"✓ 中枢: ZG={zs.zg:.2f}, ZD={zs.zd:.2f}, 高度={zs.zg-zs.zd:.2f}")
else:
    print("⚠ 未检测到有效中枢")

# 3. 简化信号识别
print("\n[3] 信号识别...")
signals = []

if result['zhongshu']:
    zs = result['zhongshu']
    current_price = df['close'].iloc[-1]
    
    # 价格相对中枢位置
    if current_price > zs.zg:
        print(f"✓ 信号: 价格在中枢上方 ({current_price:.2f} > {zs.zg:.2f})")
        signals.append('突破中枢')
    elif current_price < zs.zd:
        print(f"✓ 信号: 价格在中枢下方 ({current_price:.2f} < {zs.zd:.2f})")
        signals.append('中枢下方')
    else:
        print(f"✓ 信号: 价格在中枢内 ({zs.zd:.2f} - {zs.zg:.2f})")
        signals.append('中枢震荡')
        
    # 第三类买点判断
    recent_low = df['low'].tail(10).min()
    if recent_low > zs.zd and current_price < zs.zg:
        print(f"✓ 潜在信号: 第三类买点候选（回抽不破ZD）")
        signals.append('第三类买点候选')

if not signals:
    print("⚠ 未发现明确信号")

# 4. AI 评估
api_key = os.getenv("AI_API_KEY")
if api_key and signals:
    print("\n[4] AI 评估...")
    try:
        from ai_evaluator import AIEvaluator
        evaluator = AIEvaluator(api_key=api_key)
        
        current_price = float(df['close'].iloc[-1])
        zhongshu = {
            'zg': float(result['zhongshu'].zg) if result['zhongshu'] else 0,
            'zd': float(result['zhongshu'].zd) if result['zhongshu'] else 0
        }
        
        ai_result = evaluator.quick_evaluate(
            stock_code=stock_code,
            signal_type=signals[0] if signals else 'unknown',
            price=current_price,
            zhongshu=zhongshu
        )
        
        print(f"✓ AI 评估完成")
        if isinstance(ai_result, dict):
            action = ai_result.get('action', ai_result.get('raw_text', 'N/A'))
            print(f"  建议: {action[:100] if isinstance(action, str) else action}")
    except Exception as e:
        print(f"✗ AI 评估失败: {e}")

# 5. 简要建议
print("\n" + "="*60)
print("简要评估")
print("="*60)
current_price = float(df['close'].iloc[-1])
print(f"当前价格: {current_price:.2f}")
print(f"近期走势: {((current_price / df['close'].iloc[0] - 1) * 100):.2f}%")
print(f"波动率: {(df['close'].std() / df['close'].mean() * 100):.2f}%")

if result['zhongshu']:
    zs = result['zhongshu']
    print(f"\n中枢区间: {zs.zd:.2f} - {zs.zg:.2f}")
    print(f"建议止损: {current_price * 0.95:.2f} (5%)")
    print(f"建议止盈: {current_price * 1.15:.2f} (15%)")

print("\n" + "="*60)
