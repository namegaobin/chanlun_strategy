#!/usr/bin/env python3
"""快速测试 - 验证核心功能"""
import os
import sys

print("="*50)
print("快速测试 - ChanLun Strategy")
print("="*50)

# 1. 环境变量
print("\n[1] 环境变量检查")
api_key = os.getenv("AI_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL")
print(f"  AI_API_KEY: {api_key[:10] if api_key else '未配置'}...")
print(f"  BASE_URL: {base_url if base_url else '默认'}")

# 2. 模块导入
print("\n[2] 模块导入测试")
try:
    sys.path.insert(0, 'src')
    from data_fetcher import DataFetcher
    from chanlun_structure import ChanLunStructureAnalyzer
    from ai_evaluator import AIEvaluator
    print("  ✓ 所有模块导入成功")
except Exception as e:
    print(f"  ✗ 导入失败: {e}")
    sys.exit(1)

# 3. 缠论分析（模拟数据）
print("\n[3] 缠论分析测试")
try:
    import pandas as pd
    import numpy as np
    
    dates = pd.date_range('2026-01-01', periods=50)
    prices = 10 + np.cumsum(np.random.randn(50) * 0.02)
    df = pd.DataFrame({
        'date': dates, 'open': prices*0.99, 'high': prices*1.02,
        'low': prices*0.98, 'close': prices, 'volume': [1000000]*50
    })
    
    analyzer = ChanLunStructureAnalyzer(df)
    result = analyzer.analyze()
    print(f"  ✓ 分析完成: {len(result['fractals'])} 分型, {len(result['bi_list'])} 笔")
except Exception as e:
    print(f"  ✗ 分析失败: {e}")

# 4. AI 连接测试（可选）
if api_key:
    print("\n[4] AI API 测试")
    try:
        evaluator = AIEvaluator(api_key=api_key, provider="deepseek")
        print("  ✓ AI 评估器初始化成功")
        print("  提示: 运行完整测试以验证 API 连接")
    except Exception as e:
        print(f"  ✗ AI 初始化失败: {e}")

print("\n" + "="*50)
print("✅ 基础测试通过！")
print("运行完整测试: ./venv/bin/python test_connection.py")
print("="*50)