#!/usr/bin/env python3
"""
AI 评估示例 - 完整流程演示

展示如何使用 AI 评估模块增强交易决策
"""
import os
import sys
from datetime import datetime

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from data_fetcher import fetch_daily_kline, DataFetcher
from chanlun_structure import ChanLunStructureAnalyzer
from chanlun_analyzer import ChanLunAnalyzer
from market_filter import MarketFilter, detect_market_environment
from risk_manager import RiskManager
from ai_evaluator import AIEvaluator, evaluate_third_buy_point
from limit_up_detector import find_recent_limit_ups


def demo_ai_evaluation():
    """AI 评估完整流程演示"""
    
    print("=" * 60)
    print("缠论 AI 评估系统 - 完整流程演示")
    print("=" * 60)
    
    # ============================================
    # 1. 数据获取
    # ============================================
    print("\n【步骤 1】获取股票数据...")
    
    stock_code = "sh.600000"  # 浦发银行
    start_date = "2026-01-01"
    end_date = "2026-04-14"
    
    # 注意：实际运行需要 baostock 登录
    # df = fetch_daily_kline(stock_code, start_date, end_date)
    
    # 模拟数据（演示用）
    import pandas as pd
    import numpy as np
    
    dates = pd.date_range(start_date, end_date, freq='D')
    prices = 10 + np.cumsum(np.random.randn(len(dates)) * 0.02)
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, len(dates))
    })
    
    print(f"✓ 获取数据: {len(df)} 条记录")
    print(f"  价格区间: {df['close'].min():.2f} - {df['close'].max():.2f}")
    
    # ============================================
    # 2. 缠论结构分析
    # ============================================
    print("\n【步骤 2】缠论结构分析...")
    
    # 使用完整版分析器
    analyzer = ChanLunStructureAnalyzer(df)
    result = analyzer.analyze()
    
    print(f"✓ 分型数量: {len(result['fractals'])}")
    print(f"✓ 笔数量: {len(result['bi_list'])}")
    print(f"✓ 线段数量: {len(result['xianduan_list'])}")
    
    if result['zhongshu']:
        zs = result['zhongshu']
        print(f"✓ 中枢: ZG={zs.zg:.2f}, ZD={zs.zd:.2f}")
    else:
        print("⚠ 未检测到有效中枢")
        # 创建模拟中枢（演示用）
        from chanlun_structure import Zhongshu
        zs = Zhongshu(
            zg=df['high'].tail(20).max(),
            zd=df['low'].tail(20).max(),
            start_index=0,
            end_index=len(df)-1,
            level=1,
            bi_list=[]
        )
    
    # ============================================
    # 3. 大盘环境判断
    # ============================================
    print("\n【步骤 3】大盘环境判断...")
    
    # 模拟大盘数据
    index_prices = 4000 + np.cumsum(np.random.randn(len(dates)) * 10)
    index_df = pd.DataFrame({
        'date': dates,
        'close': index_prices
    })
    
    market_env = detect_market_environment(index_df)
    print(f"✓ 市场状态: {market_env['status'].value}")
    print(f"✓ 趋势方向: {market_env['trend'].value}")
    print(f"✓ 判断置信度: {market_env['confidence']:.0%}")
    
    # ============================================
    # 4. AI 评估信号
    # ============================================
    print("\n【步骤 4】AI 评估交易信号...")
    
    # 检查环境变量
    api_key = os.getenv("AI_API_KEY", "")
    
    if not api_key:
        print("⚠ AI_API_KEY 未配置，跳过 AI 评估")
        print("  设置方法: export AI_API_KEY='your_api_key'")
        
        # 演示输出格式
        print("\n【AI 评估输出示例】")
        example_output = """
{
  "structure_analysis": {
    "current_trend": "up",
    "zhongshu": {"zg": 10.50, "zd": 10.20},
    "latest_bi": {"direction": "up", "is_done": true, "strength": "strong"}
  },
  "signal_evaluation": {
    "signal_type": "third_buy",
    "confidence": 85,
    "quality_score": 82,
    "risk_reward_ratio": 2.5,
    "entry_price_zone": [10.30, 10.40],
    "stop_loss": 10.15,
    "take_profit": 10.80
  },
  "action_recommendation": {
    "action": "buy",
    "position_size": "normal",
    "reasoning": "第三类买点确认，回抽不破ZG，趋势向上",
    "warnings": ["注意大盘环境", "控制仓位在20%以内"]
  }
}
"""
        print(example_output)
    else:
        # 实际调用 AI
        evaluator = AIEvaluator(api_key=api_key)
        
        current_price = df['close'].iloc[-1]
        
        # 准备评估数据
        structure_data = {
            'zhongshu': {
                'zg': zs.zg,
                'zd': zs.zd,
                'middle': (zs.zg + zs.zd) / 2
            },
            'bi_direction': result['bi_list'][-1].direction.value if result['bi_list'] else 'unknown',
            'bi_done': result['bi_list'][-1].is_done() if result['bi_list'] else False,
            'bi_strength': 'medium'
        }
        
        signal_data = {
            'signal_type': 'third_buy',
            'strength': '待评估',
            'trigger_condition': '涨停后回抽不破ZG'
        }
        
        # 执行评估
        eval_result = evaluator.evaluate_signal(
            stock_code=stock_code,
            price=current_price,
            structure_data=structure_data,
            signal_data=signal_data,
            market_status=market_env['status'].value
        )
        
        if eval_result['success']:
            print("✓ AI 评估完成")
            print(f"\n{json.dumps(eval_result['evaluation'], indent=2, ensure_ascii=False)}")
        else:
            print(f"✗ AI 评估失败: {eval_result['error']}")
    
    # ============================================
    # 5. 风控计算
    # ============================================
    print("\n【步骤 5】风控计算...")
    
    risk = RiskManager(total_capital=1000000)
    risk.adjust_for_market(market_env['status'].value)
    
    current_price = df['close'].iloc[-1]
    shares = risk.calculate_position_size(stock_code, current_price)
    
    print(f"✓ 总资金: {risk.total_capital:,.0f} 元")
    print(f"✓ 可用现金: {risk.cash:,.0f} 元")
    print(f"✓ 建议仓位: {shares} 股 ({shares * current_price:,.0f} 元)")
    print(f"✓ 单股上限: {risk.config.max_single_position:.0%}")
    print(f"✓ 总仓上限: {risk.config.max_total_position:.0%}")
    
    # ============================================
    # 6. 综合决策
    # ============================================
    print("\n【步骤 6】综合决策建议")
    print("-" * 60)
    
    print(f"股票代码: {stock_code}")
    print(f"当前价格: {current_price:.2f}")
    print(f"市场环境: {market_env['status'].value} (置信度 {market_env['confidence']:.0%})")
    print(f"缠论结构: 中枢 ZG={zs.zg:.2f}, ZD={zs.zd:.2f}")
    
    if market_env['status'].value == 'bear':
        print("\n⚠ 熊市环境，建议谨慎操作或空仓观望")
    elif market_env['status'].value == 'sideways':
        print("\n→ 震荡市环境，可小仓位试探")
    else:
        print("\n✓ 牛市环境，可正常操作")
    
    print(f"\n建议仓位: {shares} 股")
    print(f"止损价格: {current_price * (1 - risk.config.base_stop_loss):.2f}")
    print(f"止盈价格: {current_price * (1 + risk.config.base_take_profit):.2f}")
    
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


def demo_quick_evaluation():
    """快速评估演示"""
    
    print("\n" + "=" * 60)
    print("快速 AI 评估演示")
    print("=" * 60)
    
    api_key = os.getenv("AI_API_KEY", "")
    
    if not api_key:
        print("\n⚠ 需要配置 AI_API_KEY")
        print("示例: export AI_API_KEY='sk-xxx'")
        return
    
    evaluator = AIEvaluator(api_key=api_key)
    
    # 快速评估
    result = evaluator.quick_evaluate(
        stock_code='sh.600000',
        signal_type='third_buy',
        price=10.8,
        zhongshu={'zg': 11.0, 'zd': 10.0}
    )
    
    print(f"\n快速评估结果:")
    print(f"  操作建议: {result.get('action', 'N/A')}")
    print(f"  置信度: {result.get('confidence', 0)}")
    print(f"  理由: {result.get('reason', 'N/A')}")


if __name__ == '__main__':
    import json
    
    # 运行完整演示
    demo_ai_evaluation()
    
    # 可选：快速评估
    # demo_quick_evaluation()
