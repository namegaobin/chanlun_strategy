#!/usr/bin/env python3
"""AI API 测试"""
import os
import sys
import json

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

print("="*60)
print("AI API 连接测试")
print("="*60)

# 检查环境变量
api_key = os.getenv("AI_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL")

print(f"\n[配置信息]")
print(f"  API Key: {api_key[:15]}...")
print(f"  Base URL: {base_url}")
print(f"  Model: {os.getenv('AI_MODEL', 'deepseek-chat')}")

# 测试 AI 调用
print(f"\n[测试] 发送请求到 AI API...")
sys.path.insert(0, 'src')

try:
    from ai_evaluator import AIEvaluator
    
    evaluator = AIEvaluator(
        api_key=api_key,
        provider="deepseek"
    )
    
    # 快速测试
    result = evaluator.quick_evaluate(
        stock_code='sh.600000',
        signal_type='third_buy',
        price=10.8,
        zhongshu={'zg': 11.0, 'zd': 10.0}
    )
    
    print(f"\n[结果]")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n✅ AI API 连接成功！")
    
except Exception as e:
    print(f"\n✗ AI API 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)