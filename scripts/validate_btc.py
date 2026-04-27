#!/usr/bin/env python3
"""
BTC 缠论策略验证脚本

使用 BTC 5分钟数据验证缠论策略：
1. 获取 BTC 5分钟 K 线数据
2. 处理包含关系
3. 检测分型、笔、中枢
4. 识别第三类买点
5. 运行回测
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    from src.crypto_data_fetcher import fetch_btc_5min, validate_crypto_data
    from src.chanlun_structure_v2 import (
        process_inclusion,
        detect_all_fractals,
        build_bi_from_fractals,
        calculate_zhongshu_from_bi,
        detect_all_zhongshu
    )
    from src.replay_engine import ReplayEngine, BacktestConfig
    
    print("=" * 60)
    print("BTC 缠论策略验证")
    print("=" * 60)
    
    # ─────────────────────────────────────────────────────────────
    # 第一步：获取 BTC 5分钟数据
    # ─────────────────────────────────────────────────────────────
    print("\n[Step 1] 获取 BTC 5分钟数据...")
    
    # 使用1天数据（5分钟数据量大）
    df = fetch_btc_5min(days=1)
    
    if df is None or df.empty:
        print("❌ 数据获取失败")
        return
    
    # 验证数据
    validation = validate_crypto_data(df)
    print(f"✓ 数据验证: {validation}")
    print(f"  - 总行数: {len(df)}")
    print(f"  - 时间范围: {df['date'].min()} ~ {df['date'].max()}")
    
    # ─────────────────────────────────────────────────────────────
    # 第二步：缠论结构分析
    # ─────────────────────────────────────────────────────────────
    print("\n[Step 2] 缠论结构分析...")
    
    # 2.1 处理K线包含关系
    df_processed = process_inclusion(df)
    print(f"✓ 包含关系处理: {len(df)} → {len(df_processed)} 根K线")
    
    # 2.2 检测分型
    fractals = detect_all_fractals(df_processed)
    print(f"✓ 检测分型: {len(fractals)} 个")
    
    if len(fractals) > 0:
        # 统计顶底分型
        top_fractals = [f for f in fractals if f.type.value == 'top']
        bottom_fractals = [f for f in fractals if f.type.value == 'bottom']
        print(f"  - 顶分型: {len(top_fractals)} 个")
        print(f"  - 底分型: {len(bottom_fractals)} 个")
    
    # 2.3 构建笔
    bi_list = build_bi_from_fractals(fractals, df_processed, min_klines=5)
    print(f"✓ 构建笔: {len(bi_list)} 笔")
    
    if len(bi_list) > 0:
        up_bi = [b for b in bi_list if b.direction.value == 'up']
        down_bi = [b for b in bi_list if b.direction.value == 'down']
        print(f"  - 向上笔: {len(up_bi)} 笔")
        print(f"  - 向下笔: {len(down_bi)} 笔")
        
        # 显示最近的笔
        if len(bi_list) >= 3:
            print(f"\n  最近3笔:")
            for i, bi in enumerate(bi_list[-3:]):
                print(f"    笔{i+1}: {bi.direction.value} {bi.start_price:.2f} → {bi.end_price:.2f} ({bi.kline_count}根K线)")
    
    # 2.4 检测中枢
    zhongshu_list = detect_all_zhongshu(bi_list, min_bi=3)
    print(f"\n✓ 检测中枢: {len(zhongshu_list)} 个")
    
    if len(zhongshu_list) > 0:
        print(f"\n  中枢详情:")
        for i, zs in enumerate(zhongshu_list[-3:]):  # 显示最近3个
            print(f"    中枢{i+1}: ZG={zs.zg:.2f}, ZD={zs.zd:.2f}, 高度={zs.height:.2f}")
    
    # ─────────────────────────────────────────────────────────────
    # 第三步：第三类买点识别
    # ─────────────────────────────────────────────────────────────
    print("\n[Step 3] 第三类买点识别...")
    
    buy_signals = []
    
    for i, zs in enumerate(zhongshu_list):
        # 检查是否有离开段
        if zs.exit_bi is not None:
            # 离开段向上突破
            if zs.exit_bi.direction.value == 'up' and zs.exit_bi.high > zs.zg:
                # 检查后续是否有回抽
                exit_idx = bi_list.index(zs.exit_bi)
                if exit_idx + 1 < len(bi_list):
                    next_bi = bi_list[exit_idx + 1]
                    # 回抽不破 ZG
                    if next_bi.direction.value == 'down' and next_bi.low > zs.zg:
                        buy_signals.append({
                            'zhongshu_idx': i,
                            'zg': zs.zg,
                            'zd': zs.zd,
                            'pullback_low': next_bi.low,
                            'signal_time': df_processed.iloc[next_bi.end_index]['date']
                        })
    
    print(f"✓ 识别到 {len(buy_signals)} 个第三类买点信号")
    
    if buy_signals:
        print("\n  信号详情:")
        for i, sig in enumerate(buy_signals):
            print(f"    信号{i+1}: 时间={sig['signal_time']}, ZG={sig['zg']:.2f}, 回抽低点={sig['pullback_low']:.2f}")
    
    # ─────────────────────────────────────────────────────────────
    # 第四步：回测验证
    # ─────────────────────────────────────────────────────────────
    print("\n[Step 4] 回测验证...")
    
    config = BacktestConfig(
        initial_capital=100000,  # 10万初始资金
        stop_loss_pct=0.03,      # 3%止损
        take_profit_pct=0.05,    # 5%止盈
        max_holding_days=12,     # 5分钟K线，12根 = 1小时
        commission_rate=0.001    # 0.1%手续费
    )
    
    engine = ReplayEngine(df, config=config)
    result = engine.run()
    
    metrics = result['metrics']
    trades = result['trades']
    
    print(f"\n✓ 回测完成:")
    print(f"  - 总交易次数: {metrics['total_trades']}")
    print(f"  - 胜率: {metrics['win_rate']:.2f}%")
    print(f"  - 总收益率: {metrics['total_return']:.2f}%")
    print(f"  - 平均收益率: {metrics['avg_trade_return']:.2f}%")
    print(f"  - 最终资金: ${metrics['final_capital']:.2f}")
    
    if trades:
        print(f"\n  交易记录:")
        for i, trade in enumerate(trades[-5:]):  # 显示最近5笔
            pnl_str = f"+{trade.pnl:.2f}" if trade.pnl >= 0 else f"{trade.pnl:.2f}"
            print(f"    {i+1}. {trade.entry_date} → {trade.exit_date} | PnL: {pnl_str} ({trade.exit_reason})")
    
    # ─────────────────────────────────────────────────────────────
    # 第五步：总结
    # ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    
    print(f"""
数据质量: {'✓ 通过' if validation['valid'] else '✗ 有问题'}
缠论结构:
  - K线（处理后）: {len(df_processed)}
  - 分型: {len(fractals)}
  - 笔: {len(bi_list)}
  - 中枢: {len(zhongshu_list)}

交易信号:
  - 第三类买点: {len(buy_signals)}

回测结果:
  - 总收益率: {metrics['total_return']:.2f}%
  - 胜率: {metrics['win_rate']:.2f}%
  - 交易次数: {metrics['total_trades']}
""")
    
    # 保存结果
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    report_path = os.path.join(output_dir, 'btc_validation_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"BTC 缠论策略验证报告\n")
        f.write(f"生成时间: {datetime.now()}\n")
        f.write(f"{'=' * 60}\n\n")
        f.write(f"数据范围: {df['date'].min()} ~ {df['date'].max()}\n")
        f.write(f"K线数量: {len(df)}\n")
        f.write(f"分型: {len(fractals)}\n")
        f.write(f"笔: {len(bi_list)}\n")
        f.write(f"中枢: {len(zhongshu_list)}\n")
        f.write(f"第三类买点: {len(buy_signals)}\n\n")
        f.write(f"回测结果:\n")
        f.write(f"  总收益率: {metrics['total_return']:.2f}%\n")
        f.write(f"  胜率: {metrics['win_rate']:.2f}%\n")
        f.write(f"  交易次数: {metrics['total_trades']}\n")
    
    print(f"✓ 报告已保存: {report_path}")


if __name__ == "__main__":
    main()
