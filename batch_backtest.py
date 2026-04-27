#!/usr/bin/env python3
"""
完整批量回测 - 对所有股票进行缠论分析 + AI评估
"""
import sys
sys.path.insert(0, 'src')

import pymysql
import pandas as pd
import os
import json
from datetime import datetime

print("="*70)
print("缠论策略 - 完整批量回测")
print("="*70)

# 数据库连接
conn = pymysql.connect(
    host='127.0.0.1',
    port=33306,  # SSH隧道映射端口
    user='chanClaw',
    password='chanClaw@2026',
    database='chanClaw'
)

# AI API配置
api_key = os.getenv("AI_API_KEY")
if api_key:
    print("✓ AI 评估已启用")
    from ai_evaluator import AIEvaluator
    ai_evaluator = AIEvaluator(api_key=api_key)
else:
    print("⚠ AI 评估未启用（未配置 API_KEY）")
    ai_evaluator = None

# 获取所有股票
cursor = conn.cursor()
cursor.execute("""
    SELECT DISTINCT ts_code, COUNT(*) as cnt
    FROM stock_daily 
    GROUP BY ts_code
    HAVING cnt >= 60
    ORDER BY ts_code
""")
stocks = cursor.fetchall()

print(f"\n共 {len(stocks)} 只股票待回测")
print("="*70)

# 回测结果
all_results = []

# 开始回测
for i, (code, data_count) in enumerate(stocks, 1):
    print(f"\n[{i}/{len(stocks)}] {code} ({data_count}天数据)")
    print("-"*70)
    
    try:
        # 1. 获取数据
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
        print(f"  当前价格: {current_price:.2f}")
        
        # 2. 缠论分析
        from chanlun_structure import ChanLunStructureAnalyzer
        
        analyzer = ChanLunStructureAnalyzer(df)
        result = analyzer.analyze()
        
        fractal_count = len(result['fractals'])
        bi_count = len(result['bi_list'])
        xd_count = len(result['xianduan_list'])
        zs = result['zhongshu']
        
        print(f"  缠论结构: {fractal_count}分型, {bi_count}笔, {xd_count}线段")
        
        if zs:
            print(f"  中枢区间: {zs.zd:.2f} - {zs.zg:.2f}")
        else:
            print(f"  中枢: 未检测到")
        
        # 3. 信号识别
        signals = []
        signal_type = "无明确信号"
        
        if zs:
            if current_price > zs.zg:
                signal_type = "突破中枢"
                signals.append(f"价格{current_price:.2f}突破ZG{zs.zg:.2f}")
            elif current_price < zs.zd:
                signal_type = "跌破中枢"
                signals.append(f"价格{current_price:.2f}跌破ZD{zs.zd:.2f}")
            else:
                signal_type = "中枢震荡"
                signals.append(f"价格在中枢内{zs.zd:.2f}-{zs.zg:.2f}")
            
            # 第三买点候选
            recent_low = float(df['low'].tail(20).min())
            recent_high = float(df['high'].tail(20).max())
            
            if recent_low > zs.zd and current_price < zs.zg:
                signals.append(f"第三买点候选(回抽{recent_low:.2f}不破ZD)")
            
            # 背驰检查
            if bi_count >= 3:
                last_3_bi = result['bi_list'][-3:]
                # 简化判断：最近3笔力度对比
                signals.append("多笔结构形成")
        
        print(f"  信号类型: {signal_type}")
        for sig in signals:
            print(f"    • {sig}")
        
        # 4. AI评估
        ai_evaluation = None
        if ai_evaluator and zs:
            print(f"  AI评估中...", end=" ")
            try:
                zhongshu_data = {
                    'zg': float(zs.zg),
                    'zd': float(zs.zd)
                }
                
                ai_result = ai_evaluator.quick_evaluate(
                    stock_code=code,
                    signal_type=signal_type,
                    price=current_price,
                    zhongshu=zhongshu_data
                )
                
                if isinstance(ai_result, dict):
                    action = ai_result.get('action', '')
                    raw = ai_result.get('raw_text', '')
                    
                    if action:
                        print(f"建议: {action}")
                        ai_evaluation = action
                    elif raw:
                        # 提取关键信息
                        if '买' in raw or 'buy' in raw.lower():
                            ai_evaluation = "buy"
                            print(f"建议: 买入")
                        elif '卖' in raw or 'sell' in raw.lower():
                            ai_evaluation = "sell"
                            print(f"建议: 卖出")
                        else:
                            ai_evaluation = "wait"
                            print(f"建议: 观望")
                    
            except Exception as e:
                print(f"失败: {e}")
        
        # 5. 计算绩效指标
        recent_5d = (current_price / float(df['close'].iloc[-5]) - 1) * 100
        recent_20d = (current_price / float(df['close'].iloc[-20]) - 1) * 100
        volatility = (df['close'].std() / df['close'].mean() * 100)
        
        print(f"  近期表现: 5日{recent_5d:+.2f}%, 20日{recent_20d:+.2f}%")
        print(f"  波动率: {volatility:.2f}%")
        
        # 6. 风控建议
        stop_loss = current_price * 0.95
        take_profit = current_price * 1.15
        
        print(f"  风控: 止损{stop_loss:.2f}, 止盈{take_profit:.2f}")
        
        # 记录结果
        all_results.append({
            'code': code,
            'price': current_price,
            'signal_type': signal_type,
            'signals': signals,
            'fractal_count': fractal_count,
            'bi_count': bi_count,
            'zs_zg': float(zs.zg) if zs else None,
            'zs_zd': float(zs.zd) if zs else None,
            'recent_5d': recent_5d,
            'recent_20d': recent_20d,
            'volatility': volatility,
            'ai_evaluation': ai_evaluation,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'data_count': data_count
        })
        
    except Exception as e:
        print(f"  ✗ 回测失败: {e}")
        import traceback
        traceback.print_exc()

conn.close()

# ============================================
# 生成汇总报告
# ============================================
print("\n" + "="*70)
print("📊 批量回测汇总报告")
print("="*70)

if not all_results:
    print("无回测结果")
    sys.exit(0)

# 转换为DataFrame便于分析
df_results = pd.DataFrame(all_results)

# 1. 按信号类型分组
print("\n【信号统计】")
signal_counts = df_results['signal_type'].value_counts()
for sig_type, count in signal_counts.items():
    pct = count / len(df_results) * 100
    print(f"  {sig_type}: {count}只 ({pct:.1f}%)")

# 2. 突破中枢的股票
print("\n【突破中枢 - 强势股】")
breakout = df_results[df_results['signal_type'] == '突破中枢']
if not breakout.empty:
    for _, row in breakout.iterrows():
        ai_rec = f" | AI建议: {row['ai_evaluation']}" if row['ai_evaluation'] else ""
        print(f"  ✓ {row['code']}: {row['price']:.2f} (ZG={row['zs_zg']:.2f}){ai_rec}")
        print(f"      近期: {row['recent_5d']:+.2f}%/{row['recent_20d']:+.2f}%")
else:
    print("  无")

# 3. 中枢震荡
print("\n【中枢震荡 - 观察股】")
oscillation = df_results[df_results['signal_type'] == '中枢震荡']
if not oscillation.empty:
    for _, row in oscillation.head(5).iterrows():
        ai_rec = f" | AI: {row['ai_evaluation']}" if row['ai_evaluation'] else ""
        print(f"  • {row['code']}: {row['price']:.2f} ({row['zs_zd']:.2f}-{row['zs_zg']:.2f}){ai_rec}")

# 4. 跌破中枢
print("\n【跌破中枢 - 弱势股】")
breakdown = df_results[df_results['signal_type'] == '跌破中枢']
if not breakdown.empty:
    for _, row in breakdown.iterrows():
        print(f"  ✗ {row['code']}: {row['price']:.2f} < ZD={row['zs_zd']:.2f}")
        print(f"      近期: {row['recent_5d']:+.2f}%/{row['recent_20d']:+.2f}%")

# 5. AI推荐汇总
if df_results['ai_evaluation'].notna().any():
    print("\n【AI 操作建议汇总】")
    ai_buy = df_results[df_results['ai_evaluation'] == 'buy']
    ai_sell = df_results[df_results['ai_evaluation'] == 'sell']
    ai_wait = df_results[df_results['ai_evaluation'] == 'wait']
    
    if not ai_buy.empty:
        print(f"  买入建议: {len(ai_buy)}只")
        for _, row in ai_buy.iterrows():
            print(f"    • {row['code']}: {row['price']:.2f}")
    
    if not ai_wait.empty:
        print(f"  观望建议: {len(ai_wait)}只")
    
    if not ai_sell.empty:
        print(f"  卖出建议: {len(ai_sell)}只")

# 6. 整体统计
print("\n【整体统计】")
print(f"  回测股票: {len(df_results)}只")
print(f"  平均波动率: {df_results['volatility'].mean():.2f}%")
print(f"  平均5日涨跌: {df_results['recent_5d'].mean():+.2f}%")
print(f"  平均20日涨跌: {df_results['recent_20d'].mean():+.2f}%")

# 上涨股票数量
up_5d = (df_results['recent_5d'] > 0).sum()
up_20d = (df_results['recent_20d'] > 0).sum()
print(f"  5日上涨股票: {up_5d}/{len(df_results)}只")
print(f"  20日上涨股票: {up_20d}/{len(df_results)}只")

# 保存详细报告
report_path = 'output/batch_backtest_report.md'
os.makedirs('output', exist_ok=True)

with open(report_path, 'w', encoding='utf-8') as f:
    f.write(f"# 📊 批量回测报告\n\n")
    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"## 概览\n\n")
    f.write(f"- 回测股票: {len(df_results)}只\n")
    f.write(f"- 数据周期: 近120个交易日\n")
    f.write(f"- AI评估: {'已启用' if api_key else '未启用'}\n\n")
    
    f.write(f"## 信号分布\n\n")
    for sig_type, count in signal_counts.items():
        f.write(f"- {sig_type}: {count}只\n")
    
    f.write(f"\n## 详细结果\n\n")
    f.write(f"| 代码 | 价格 | 信号 | 5日% | 20日% | AI建议 |\n")
    f.write(f"|------|------|------|------|-------|--------|\n")
    
    for _, row in df_results.iterrows():
        ai = row['ai_evaluation'] or '-'
        f.write(f"| {row['code']} | {row['price']:.2f} | {row['signal_type']} | {row['recent_5d']:+.2f}% | {row['recent_20d']:+.2f}% | {ai} |\n")

print(f"\n✅ 详细报告已保存: {report_path}")
print("="*70)
