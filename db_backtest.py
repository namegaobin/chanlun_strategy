#!/usr/bin/env python3
"""
完整回测 - 从数据库读取数据进行缠论分析
"""
import sys
import os
sys.path.insert(0, 'src')

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import pymysql
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*60)
print("缠论策略 - 数据库回测")
print("="*60)

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 33306,  # SSH隧道映射端口
    'user': 'chanClaw',
    'password': 'chanClaw@2026',
    'database': 'chanClaw',
    'charset': 'utf8mb4'
}

# ============================================
# 1. 连接数据库
# ============================================
print("\n[1] 连接数据库...")
conn = pymysql.connect(**DB_CONFIG)
print("✅ 连接成功")

# ============================================
# 2. 查询股票列表
# ============================================
print("\n[2] 查询可用股票...")
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT DISTINCT ts_code, MAX(trade_date) as latest_date, COUNT(*) as days
        FROM stock_daily 
        GROUP BY ts_code 
        ORDER BY latest_date DESC 
        LIMIT 20
    """)
    stocks = cursor.fetchall()
    
    print(f"✓ 发现 {len(stocks)} 只股票:")
    for i, (code, date, days) in enumerate(stocks[:10]):
        print(f"  {i+1}. {code} - 最新日期: {date}, {days}天数据")

# ============================================
# 3. 选择股票并获取数据
# ============================================
target_code = sys.argv[1] if len(sys.argv) > 1 else (stocks[0][0] if stocks else None)

if not target_code:
    print("\n❌ 未找到股票数据")
    conn.close()
    sys.exit(1)

print(f"\n[3] 获取股票数据: {target_code}")

# 查询K线数据
query = f"""
SELECT 
    trade_date as date,
    open,
    high,
    low,
    close,
    volume,
    amount
FROM stock_daily 
WHERE ts_code = '{target_code}'
ORDER BY trade_date DESC
LIMIT 200
"""

df = pd.read_sql(query, conn)
df = df.sort_values('date')  # 按日期升序

print(f"✓ 获取 {len(df)} 条数据")
print(f"✓ 日期范围: {df['date'].min()} ~ {df['date'].max()}")
print(f"✓ 价格区间: {df['close'].min():.2f} ~ {df['close'].max():.2f}")

# ============================================
# 4. 缠论分析
# ============================================
print("\n[4] 缠论结构分析...")
from chanlun_structure import ChanLunStructureAnalyzer

analyzer = ChanLunStructureAnalyzer(df)
result = analyzer.analyze()

print(f"✓ 分型: {len(result['fractals'])} 个")
print(f"✓ 笔: {len(result['bi_list'])} 个")
print(f"✓ 线段: {len(result['xianduan_list'])} 个")

if result['zhongshu']:
    zs = result['zhongshu']
    print(f"✓ 中枢: ZG={zs.zg:.2f}, ZD={zs.zd:.2f}")
else:
    print("⚠ 未检测到有效中枢")
    zs = None

# ============================================
# 5. 信号识别
# ============================================
print("\n[5] 信号识别...")
current_price = float(df['close'].iloc[-1])
signals = []

# 信号1: 价格位置判断
if zs:
    if current_price > zs.zg:
        signals.append(f"突破中枢 (价格{current_price:.2f} > ZG {zs.zg:.2f})")
    elif current_price < zs.zd:
        signals.append(f"跌破中枢 (价格{current_price:.2f} < ZD {zs.zd:.2f})")
    else:
        signals.append(f"中枢震荡 (价格在 {zs.zd:.2f} - {zs.zg:.2f})")

# 信号2: 近期涨跌
recent_change = (current_price / df['close'].iloc[-20] - 1) * 100 if len(df) >= 20 else 0
if recent_change > 5:
    signals.append(f"近期强势 (+{recent_change:.1f}%)")
elif recent_change < -5:
    signals.append(f"近期弱势 ({recent_change:.1f}%)")

# 信号3: 第三类买点判断
if zs and len(df) >= 20:
    recent_low = df['low'].tail(20).min()
    if recent_low > zs.zd and current_price < zs.zg:
        signals.append("第三类买点候选 (回抽不破ZD)")

for sig in signals:
    print(f"  ✓ {sig}")

# ============================================
# 6. AI 评估
# ============================================
api_key = os.getenv("AI_API_KEY")
if api_key and signals:
    print("\n[6] AI 评估...")
    try:
        from ai_evaluator import AIEvaluator
        
        evaluator = AIEvaluator(api_key=api_key)
        
        zhongshu_data = {
            'zg': float(zs.zg) if zs else 0,
            'zd': float(zs.zd) if zs else 0
        }
        
        ai_result = evaluator.quick_evaluate(
            stock_code=target_code,
            signal_type=signals[0] if signals else 'unknown',
            price=current_price,
            zhongshu=zhongshu_data
        )
        
        print("✓ AI 评估完成")
        if isinstance(ai_result, dict):
            action = ai_result.get('action', '')
            if action:
                print(f"  操作建议: {action}")
            
            reason = ai_result.get('reason', '')
            if reason:
                print(f"  理由: {reason[:100]}")
            
            # 如果返回的是 raw_text（DeepSeek思考过程）
            raw = ai_result.get('raw_text', '')
            if raw and len(raw) > 50:
                print(f"  AI 分析: {raw[:200]}...")
                
    except Exception as e:
        print(f"✗ AI 评估失败: {e}")

# ============================================
# 7. 生成简要报告
# ============================================
print("\n" + "="*60)
print("📊 评估报告")
print("="*60)

print(f"\n股票代码: {target_code}")
print(f"当前价格: {current_price:.2f}")
print(f"数据日期: {df['date'].iloc[-1]}")
print(f"涨跌幅: {recent_change:+.2f}%")

if zs:
    print(f"\n缠论结构:")
    print(f"  中枢: ZG={zs.zg:.2f}, ZD={zs.zd:.2f}")
    print(f"  高度: {zs.zg-zs.zd:.2f}")
    print(f"  价格位置: ", end="")
    if current_price > zs.zg:
        print("中枢上方 ↑")
    elif current_price < zs.zd:
        print("中枢下方 ↓")
    else:
        print("中枢内 →")

print(f"\n信号列表:")
for i, sig in enumerate(signals, 1):
    print(f"  {i}. {sig}")

# 风控建议
print(f"\n风控建议:")
print(f"  建议仓位: 20% (单股上限)")
print(f"  止损价格: {current_price * 0.95:.2f} (-5%)")
print(f"  止盈价格: {current_price * 1.15:.2f} (+15%)")

# 保存报告
report_path = f"output/{target_code.replace('.', '_')}_report.md"
os.makedirs('output', exist_ok=True)

with open(report_path, 'w', encoding='utf-8') as f:
    f.write(f"""# 📊 {target_code} 缠论评估报告

## 基本信息
- **股票代码**: {target_code}
- **当前价格**: {current_price:.2f}
- **评估时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- **数据日期**: {df['date'].iloc[-1]}

## 价格统计
- 最高价: {df['high'].max():.2f}
- 最低价: {df['low'].min():.2f}
- 平均价: {df['close'].mean():.2f}
- 近期涨跌: {recent_change:+.2f}%

## 缠论结构
- 分型数量: {len(result['fractals'])}
- 笔数量: {len(result['bi_list'])}
- 线段数量: {len(result['xianduan_list'])}
""")

    if zs:
        f.write(f"""
### 中枢状态
- ZG (中枢高点): {zs.zg:.2f}
- ZD (中枢低点): {zs.zd:.2f}
- 中枢高度: {zs.zg-zs.zd:.2f}

### 价格位置
""")
        if current_price > zs.zg:
            f.write("价格在中枢上方，突破状态\n")
        elif current_price < zs.zd:
            f.write("价格在中枢下方，弱势状态\n")
        else:
            f.write("价格在中枢内，震荡状态\n")

    f.write(f"""
## 信号分析
""")
    for i, sig in enumerate(signals, 1):
        f.write(f"{i}. {sig}\n")

    f.write(f"""
## 风控建议
- 建议仓位: 20%
- 止损价格: {current_price * 0.95:.2f}
- 止盈价格: {current_price * 1.15:.2f}

---
*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
""")

print(f"\n✅ 报告已保存: {report_path}")

# 关闭连接
conn.close()
print("\n" + "="*60)
