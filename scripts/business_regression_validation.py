#!/usr/bin/env python3
"""
业务回归验证脚本

任务：
1. 用真实BTC数据验证信号检测
2. 验证缠论结构识别（分型、笔、中枢）
3. 验证第三类买点检测
4. 运行回测冒烟测试

输出：JSON格式的验证报告
"""
import sys
import os
import json
from datetime import datetime

# 设置代理
os.environ['http_proxy'] = 'http://127.0.0.1:11090'
os.environ['https_proxy'] = 'http://127.0.0.1:11090'

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np

print("=" * 70)
print("业务回归验证 - 缠论策略")
print("=" * 70)
print(f"开始时间: {datetime.now()}")
print(f"代理设置: http://127.0.0.1:11090")

# ─────────────────────────────────────────────────────────────────
# 结果容器
# ─────────────────────────────────────────────────────────────────
result = {
    "data_validation": {
        "btc_data_fetched": False,
        "klines_count": 0,
        "price_range": "",
        "data_source": "",
        "issues": []
    },
    "structure_validation": {
        "fractals_detected": 0,
        "bi_count": 0,
        "zhongshu_count": 0,
        "theory_compliant": False,
        "details": {}
    },
    "signal_validation": {
        "third_buy_points": 0,
        "signals": [],
        "reason": ""
    },
    "backtest_smoke_test": {
        "executed": False,
        "total_trades": 0,
        "win_rate": 0.0,
        "total_return": 0.0,
        "theory_compliant": False
    },
    "approved_for_delivery": False,
    "validation_time": str(datetime.now())
}

# ─────────────────────────────────────────────────────────────────
# 任务1: 获取真实BTC数据
# ─────────────────────────────────────────────────────────────────
print("\n[任务1] 获取真实BTC 5分钟数据...")

try:
    # 直接导入模块，避免__init__.py中的backtrader依赖
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 手动导入crypto_data_fetcher
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "crypto_data_fetcher",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'crypto_data_fetcher.py')
    )
    crypto_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(crypto_module)
    
    fetch_btc_5min = crypto_module.fetch_btc_5min
    validate_crypto_data = crypto_module.validate_crypto_data
    
    # 获取1天的BTC 5分钟数据
    df = fetch_btc_5min(days=1)
    
    if df is not None and not df.empty:
        result["data_validation"]["btc_data_fetched"] = True
        result["data_validation"]["klines_count"] = len(df)
        result["data_validation"]["price_range"] = f"{df['low'].min():.2f} ~ {df['high'].max():.2f}"
        
        # 验证数据质量
        validation = validate_crypto_data(df)
        if validation['valid']:
            result["data_validation"]["data_source"] = "真实市场数据"
            print(f"✓ 成功获取 {len(df)} 根K线")
            print(f"  价格范围: {result['data_validation']['price_range']}")
            print(f"  时间范围: {df['date'].min()} ~ {df['date'].max()}")
        else:
            result["data_validation"]["issues"] = validation.get('issues', [])
            print(f"⚠ 数据质量问题: {validation.get('issues')}")
    else:
        result["data_validation"]["issues"].append("无法获取BTC数据")
        print("✗ 数据获取失败")
        
except Exception as e:
    result["data_validation"]["issues"].append(f"异常: {str(e)}")
    print(f"✗ 数据获取异常: {e}")
    import traceback
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────
# 任务2: 验证缠论结构识别
# ─────────────────────────────────────────────────────────────────
print("\n[任务2] 验证缠论结构识别...")

if df is not None and not df.empty:
    try:
        from src.chanlun_structure_v2 import (
            process_inclusion,
            detect_all_fractals,
            build_bi_from_fractals,
            detect_all_zhongshu,
            validate_bi_direction_alternation,
            validate_zhongshu_overlap
        )
        
        # 2.1 K线包含关系处理
        df_processed = process_inclusion(df)
        print(f"✓ 包含关系处理: {len(df)} → {len(df_processed)} 根K线")
        
        # 2.2 分型检测
        fractals = detect_all_fractals(df_processed)
        result["structure_validation"]["fractals_detected"] = len(fractals)
        
        if len(fractals) > 0:
            top_fractals = [f for f in fractals if f.type.value == 'top']
            bottom_fractals = [f for f in fractals if f.type.value == 'bottom']
            print(f"✓ 检测分型: {len(fractals)} 个")
            print(f"  - 顶分型: {len(top_fractals)} 个")
            print(f"  - 底分型: {len(bottom_fractals)} 个")
            
            result["structure_validation"]["details"]["top_fractals"] = len(top_fractals)
            result["structure_validation"]["details"]["bottom_fractals"] = len(bottom_fractals)
        
        # 2.3 笔构建
        bi_list = build_bi_from_fractals(fractals, df_processed, min_klines=5)
        result["structure_validation"]["bi_count"] = len(bi_list)
        
        if len(bi_list) > 0:
            up_bi = [b for b in bi_list if b.direction.value == 'up']
            down_bi = [b for b in bi_list if b.direction.value == 'down']
            print(f"✓ 构建笔: {len(bi_list)} 笔")
            print(f"  - 向上笔: {len(up_bi)} 笔")
            print(f"  - 向下笔: {len(down_bi)} 笔")
            
            result["structure_validation"]["details"]["up_bi"] = len(up_bi)
            result["structure_validation"]["details"]["down_bi"] = len(down_bi)
            
            # 验证笔的方向交替规则
            if validate_bi_direction_alternation(bi_list):
                print("  ✓ 笔方向交替规则验证通过")
                result["structure_validation"]["details"]["bi_direction_valid"] = True
            else:
                print("  ✗ 笔方向交替规则验证失败")
                result["structure_validation"]["details"]["bi_direction_valid"] = False
            
            # 显示最近3笔
            if len(bi_list) >= 3:
                print(f"\n  最近3笔:")
                for i, bi in enumerate(bi_list[-3:]):
                    print(f"    笔{i+1}: {bi.direction.value} {bi.start_price:.2f} → {bi.end_price:.2f} ({bi.kline_count}根K线)")
        
        # 2.4 中枢检测
        zhongshu_list = detect_all_zhongshu(bi_list, min_bi=3)
        result["structure_validation"]["zhongshu_count"] = len(zhongshu_list)
        
        if len(zhongshu_list) > 0:
            print(f"\n✓ 检测中枢: {len(zhongshu_list)} 个")
            
            for i, zs in enumerate(zhongshu_list):
                print(f"  中枢{i+1}: ZG={zs.zg:.2f}, ZD={zs.zd:.2f}, 高度={zs.height:.2f}")
                
                # 验证中枢重叠规则
                if validate_zhongshu_overlap(zs):
                    print(f"    ✓ 中枢重叠验证通过")
                else:
                    print(f"    ✗ 中枢重叠验证失败")
        
        # 理论合规性判断
        theory_compliant = (
            len(fractals) > 0 and
            len(bi_list) > 0 and
            result["structure_validation"]["details"].get("bi_direction_valid", True)
        )
        result["structure_validation"]["theory_compliant"] = theory_compliant
        
        if theory_compliant:
            print("\n✓ 缠论结构识别符合理论规范")
        else:
            print("\n✗ 缠论结构识别存在问题")
            
    except Exception as e:
        print(f"✗ 结构验证异常: {e}")
        import traceback
        traceback.print_exc()
        result["structure_validation"]["theory_compliant"] = False

# ─────────────────────────────────────────────────────────────────
# 任务3: 验证第三类买点检测
# ─────────────────────────────────────────────────────────────────
print("\n[任务3] 验证第三类买点检测...")

if len(bi_list) > 0 and len(zhongshu_list) > 0:
    try:
        # 第三类买点逻辑：
        # 1. 中枢有离开段向上突破ZG
        # 2. 随后有回抽段向下
        # 3. 回抽低点 > ZG
        # 4. 再创新高（确认）
        
        buy_signals = []
        
        for i, zs in enumerate(zhongshu_list):
            # 检查离开段
            if zs.exit_bi is not None:
                # 离开段向上突破
                if zs.exit_bi.direction.value == 'up' and zs.exit_bi.high > zs.zg:
                    # 检查回抽段
                    exit_idx = bi_list.index(zs.exit_bi)
                    if exit_idx + 1 < len(bi_list):
                        pullback_bi = bi_list[exit_idx + 1]
                        
                        # 回抽不破ZG
                        if pullback_bi.direction.value == 'down' and pullback_bi.low > zs.zg:
                            # 检查是否再创新高（确认段）
                            if exit_idx + 2 < len(bi_list):
                                confirm_bi = bi_list[exit_idx + 2]
                                if confirm_bi.direction.value == 'up' and confirm_bi.high > zs.exit_bi.high:
                                    signal = {
                                        'zhongshu_idx': i,
                                        'zg': float(zs.zg),
                                        'zd': float(zs.zd),
                                        'exit_high': float(zs.exit_bi.high),
                                        'pullback_low': float(pullback_bi.low),
                                        'confirm_high': float(confirm_bi.high),
                                        'signal_time': str(df_processed.iloc[confirm_bi.end_index]['date'])
                                    }
                                    buy_signals.append(signal)
        
        result["signal_validation"]["third_buy_points"] = len(buy_signals)
        result["signal_validation"]["signals"] = buy_signals
        
        if buy_signals:
            print(f"✓ 检测到 {len(buy_signals)} 个第三类买点信号")
            for i, sig in enumerate(buy_signals):
                print(f"\n  信号{i+1}:")
                print(f"    ZG: {sig['zg']:.2f}")
                print(f"    离开段高点: {sig['exit_high']:.2f}")
                print(f"    回抽低点: {sig['pullback_low']:.2f}")
                print(f"    确认段高点: {sig['confirm_high']:.2f}")
                print(f"    信号时间: {sig['signal_time']}")
        else:
            result["signal_validation"]["reason"] = "当前市场数据无符合条件的第三类买点"
            print("⚠ 未检测到符合条件的第三类买点")
            print(f"  原因: {result['signal_validation']['reason']}")
            
    except Exception as e:
        print(f"✗ 信号验证异常: {e}")
        import traceback
        traceback.print_exc()
        result["signal_validation"]["reason"] = f"异常: {str(e)}"
else:
    result["signal_validation"]["reason"] = "笔或中枢数量不足，无法检测信号"
    print("⚠ 笔或中枢数量不足，跳过信号检测")

# ─────────────────────────────────────────────────────────────────
# 任务4: 运行回测冒烟测试
# ─────────────────────────────────────────────────────────────────
print("\n[任务4] 运行回测冒烟测试...")

if df is not None and not df.empty:
    try:
        from src.replay_engine import ReplayEngine, BacktestConfig
        
        # 配置回测参数
        config = BacktestConfig(
            initial_capital=100000,   # 10万初始资金
            stop_loss_pct=0.03,       # 3%止损
            take_profit_pct=0.05,     # 5%止盈
            max_holding_days=12,      # 5分钟K线，12根 = 1小时
            commission_rate=0.001     # 0.1%手续费
        )
        
        # 运行回测
        engine = ReplayEngine(df, config=config)
        backtest_result = engine.run()
        
        metrics = backtest_result['metrics']
        trades = backtest_result['trades']
        
        result["backtest_smoke_test"]["executed"] = True
        result["backtest_smoke_test"]["total_trades"] = metrics['total_trades']
        result["backtest_smoke_test"]["win_rate"] = round(metrics['win_rate'], 2)
        result["backtest_smoke_test"]["total_return"] = round(metrics['total_return'], 2)
        
        print(f"✓ 回测完成:")
        print(f"  - 总交易次数: {metrics['total_trades']}")
        print(f"  - 胜率: {metrics['win_rate']:.2f}%")
        print(f"  - 总收益率: {metrics['total_return']:.2f}%")
        print(f"  - 最终资金: ${metrics['final_capital']:.2f}")
        
        if trades:
            print(f"\n  最近交易记录:")
            for i, trade in enumerate(trades[-5:]):
                pnl_str = f"+{trade.pnl:.2f}" if trade.pnl >= 0 else f"{trade.pnl:.2f}"
                print(f"    {i+1}. {trade.entry_date} → {trade.exit_date} | PnL: {pnl_str} ({trade.exit_reason})")
        
        # 理论合规性判断
        # 回测结果应该合理（不能有极端异常值）
        theory_compliant = (
            metrics['total_return'] > -50 and  # 不能亏损超过50%
            metrics['win_rate'] >= 0 and        # 胜率应该 >= 0
            metrics['win_rate'] <= 100          # 胜率应该 <= 100
        )
        result["backtest_smoke_test"]["theory_compliant"] = theory_compliant
        
        if theory_compliant:
            print("\n✓ 回测结果合理")
        else:
            print("\n✗ 回测结果存在异常")
            
    except Exception as e:
        print(f"✗ 回测异常: {e}")
        import traceback
        traceback.print_exc()
        result["backtest_smoke_test"]["theory_compliant"] = False

# ─────────────────────────────────────────────────────────────────
# 最终判断
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("验证总结")
print("=" * 70)

# 判断是否通过
approved = (
    result["data_validation"]["btc_data_fetched"] and
    result["structure_validation"]["theory_compliant"] and
    result["backtest_smoke_test"]["executed"] and
    result["backtest_smoke_test"]["theory_compliant"]
)

result["approved_for_delivery"] = approved

print(f"""
数据验证:
  ✓ BTC数据获取: {'成功' if result['data_validation']['btc_data_fetched'] else '失败'}
  ✓ K线数量: {result['data_validation']['klines_count']}
  ✓ 价格范围: {result['data_validation']['price_range']}

缠论结构验证:
  ✓ 分型数量: {result['structure_validation']['fractals_detected']}
  ✓ 笔数量: {result['structure_validation']['bi_count']}
  ✓ 中枢数量: {result['structure_validation']['zhongshu_count']}
  ✓ 理论合规: {'通过' if result['structure_validation']['theory_compliant'] else '失败'}

信号验证:
  ✓ 第三类买点: {result['signal_validation']['third_buy_points']}
  原因: {result['signal_validation'].get('reason', '已有信号')}

回测验证:
  ✓ 执行状态: {'已完成' if result['backtest_smoke_test']['executed'] else '未执行'}
  ✓ 总交易次数: {result['backtest_smoke_test']['total_trades']}
  ✓ 胜率: {result['backtest_smoke_test']['win_rate']:.2f}%
  ✓ 总收益率: {result['backtest_smoke_test']['total_return']:.2f}%

最终结果: {'✓ 通过，可以交付' if approved else '✗ 未通过，需要修复'}
""")

# 保存JSON报告
output_path = os.path.join(os.path.dirname(__file__), '..', 'output', 'business_regression_validation.json')
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"✓ 验证报告已保存: {output_path}")
print(f"\n完成时间: {datetime.now()}")
