import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv()

print("测试开始...")

# 最小化测试
import pandas as pd
import numpy as np

# 模拟数据
dates = pd.date_range('2026-02-01', periods=50)
prices = 10 + np.cumsum(np.random.randn(50) * 0.03)
df = pd.DataFrame({
    'date': dates, 'open': prices*0.99, 'high': prices*1.02,
    'low': prices*0.98, 'close': prices, 'volume': [1000000]*50
})

print(f"✓ 数据: {len(df)} 条")

# 缠论分析
from chanlun_structure import ChanLunStructureAnalyzer
analyzer = ChanLunStructureAnalyzer(df)
result = analyzer.analyze()

print(f"✓ 分型: {len(result['fractals'])} 个")
print(f"✓ 笔: {len(result['bi_list'])} 个")

if result['zhongshu']:
    print(f"✓ 中枢: ZG={result['zhongshu'].zg:.2f}, ZD={result['zhongshu'].zd:.2f}")
    
# AI 测试
import os
api_key = os.getenv("AI_API_KEY")
if api_key:
    from ai_evaluator import AIEvaluator
    evaluator = AIEvaluator(api_key=api_key)
    print("✓ AI 评估器就绪")
    
print("\n✅ 测试完成！")
