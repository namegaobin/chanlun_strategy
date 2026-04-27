#!/usr/bin/env python3
"""
快速测试脚本 - 验证 AI API 连接和数据获取
"""
import os
import sys

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

print("="*60)
print("缠论策略系统 - 连接测试")
print("="*60)

# 1. 测试环境变量
print("\n【测试 1】环境变量检查...")
api_key = os.getenv("AI_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL")
model = os.getenv("AI_MODEL")

if api_key:
    print(f"✓ AI_API_KEY: {api_key[:10]}...")
else:
    print("✗ AI_API_KEY 未配置")

if base_url:
    print(f"✓ DEEPSEEK_BASE_URL: {base_url}")
else:
    print("✗ DEEPSEEK_BASE_URL 未配置")

print(f"✓ AI_MODEL: {model}")

# 2. 测试 AI API 连接
print("\n【测试 2】AI API 连接...")
try:
    sys.path.insert(0, 'src')
    from ai_evaluator import AIEvaluator, call_ai
    
    evaluator = AIEvaluator()
    
    # 发送测试请求
    print("  发送测试请求...")
    result = evaluator.quick_evaluate(
        stock_code='sh.600000',
        signal_type='test',
        price=10.0,
        zhongshu={'zg': 11.0, 'zd': 10.0}
    )
    
    print(f"  ✓ AI 响应成功")
    print(f"  结果: {result}")
    
except Exception as e:
    print(f"  ✗ AI API 连接失败: {e}")
    import traceback
    traceback.print_exc()

# 3. 测试数据获取
print("\n【测试 3】数据获取...")
try:
    from data_fetcher import DataFetcher
    
    print("  连接 baostock...")
    with DataFetcher() as fetcher:
        print("  ✓ baostock 连接成功")
        
        # 获取少量数据测试
        print("  获取测试数据...")
        df = fetcher.fetch_daily_kline(
            "sh.600000",
            "2026-04-01",
            "2026-04-14"
        )
        
        if df is not None and not df.empty:
            print(f"  ✓ 数据获取成功: {len(df)} 条")
            print(f"  最新价格: {df['close'].iloc[-1]:.2f}")
        else:
            print("  ⚠ 未获取到数据（可能是非交易时间）")
            
except Exception as e:
    print(f"  ✗ 数据获取失败: {e}")

# 4. 测试缠论分析
print("\n【测试 4】缠论分析...")
try:
    import pandas as pd
    import numpy as np
    from chanlun_structure import ChanLunStructureAnalyzer
    
    # 创建测试数据
    dates = pd.date_range('2026-01-01', periods=100)
    prices = 10 + np.cumsum(np.random.randn(100) * 0.02)
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, 100)
    })
    
    analyzer = ChanLunStructureAnalyzer(df)
    result = analyzer.analyze()
    
    print("  ✓ 缠论分析成功")
    print(f"    分型: {len(result['fractals'])} 个")
    print(f"    笔: {len(result['bi_list'])} 个")
    
except Exception as e:
    print(f"  ✗ 缠论分析失败: {e}")

print("\n" + "="*60)
print("测试完成！")
print("="*60)
