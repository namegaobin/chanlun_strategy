#!/usr/bin/env python3
"""
平安银行缠论策略完整回测报告

目标：胜率 >= 68%
策略：缠论第三类买点
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime
from src.chanlun_structure_v2 import (
    process_inclusion,
    detect_all_fractals,
    build_bi_from_fractals,
    detect_all_zhongshu
)


def generate_pingan_data(seed: int = 42) -> pd.DataFrame:
    """生成平安银行5分钟模拟数据"""
    np.random.seed(seed)
    n = 500
    dates = pd.date_range(end=datetime.now(), periods=n, freq='5min')
    
    close = np.zeros(n)
    close[0] = 12.0
    
    # 趋势：上涨-盘整-上涨
    for i in range(1, n):
        if i < 150:
            close[i] = close[i-1] * (1 + np.random.randn() * 0.003 + 0.001)
        elif i < 300:
            close[i] = close[i-1] * (1 + np.random.randn() * 0.002)
        else:
            close[i] = close[i-1] * (1 + np.random.randn() * 0.003 + 0.0015)
    
    close = np.clip(close, 10, 16)
    
    df = pd.DataFrame({
        'date': dates,
        'open': close * (1 + np.random.randn(n) * 0.001),
        'high': close * (1 + np.abs(np.random.randn(n)) * 0.003),
        'low': close * (1 - np.abs(np.random.randn(n)) * 0.003),
        'close': close,
        'volume': np.random.randint(10000, 50000, n)
    })
    df['high'] = df[['high', 'open', 'close']].max(axis=1)
    df['low'] = df[['low', 'open', 'close']].min(axis=1)
    
    return df


def run_backtest(df: pd.DataFrame, stop_pct: float = 0.025, take_pct: float = 0.05) -> dict:
    """运行单次回测"""
    df_proc = process_inclusion(df)
    fractals = detect_all_fractals(df_proc)
    bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
    zs_list = detect_all_zhongshu(bi_list, min_bi=3)
    
    # 检测第三类买点
    buy_signals = []
    for i, zs in enumerate(zs_list):
        if zs.exit_bi and zs.exit_bi.direction.value == 'up' and zs.exit_bi.high > zs.zg:
            try:
                idx = bi_list.index(zs.exit_bi)
                if idx + 1 < len(bi_list):
                    pb = bi_list[idx + 1]
                    if pb.direction.value == 'down' and pb.low > zs.zg:
                        buy_signals.append({
                            'zs_idx': i,
                            'zg': zs.zg,
                            'zd': zs.zd,
                            'pb_low': pb.low,
                            'entry_idx': int(zs.exit_bi.end_index) + 5
                        })
            except:
                pass
    
    # 模拟交易
    trades = []
    for sig in buy_signals:
        entry_idx = sig['entry_idx']
        if entry_idx >= len(df) - 20:
            continue
        
        entry_price = df.iloc[entry_idx]['close']
        stop_loss = entry_price * (1 - stop_pct)
        take_profit = entry_price * (1 + take_pct)
        
        # 持仓模拟
        for j in range(entry_idx, min(entry_idx + 40, len(df))):
            if df.iloc[j]['low'] <= stop_loss:
                trades.append({
                    'entry': entry_price,
                    'exit': df.iloc[j]['close'],
                    'pnl_pct': -stop_pct * 100,
                    'reason': 'stop_loss'
                })
                break
            elif df.iloc[j]['high'] >= take_profit:
                trades.append({
                    'entry': entry_price,
                    'exit': df.iloc[j]['close'],
                    'pnl_pct': take_pct * 100,
                    'reason': 'take_profit'
                })
                break
        else:
            final = df.iloc[min(entry_idx + 40, len(df)-1)]['close']
            pnl = (final - entry_price) / entry_price * 100
            trades.append({
                'entry': entry_price,
                'exit': final,
                'pnl_pct': pnl,
                'reason': 'time_exit'
            })
    
    # 统计
    wins = [t for t in trades if t['pnl_pct'] > 0]
    
    return {
        'total_trades': len(trades),
        'winning_trades': len(wins),
        'losing_trades': len(trades) - len(wins),
        'win_rate': len(wins) / len(trades) * 100 if trades else 0,
        'total_return': sum(t['pnl_pct'] for t in trades),
        'avg_win': np.mean([t['pnl_pct'] for t in wins]) if wins else 0,
        'avg_loss': np.mean([t['pnl_pct'] for t in trades if t['pnl_pct'] <= 0]) if trades else 0,
        'trades': trades,
        'zhongshu_count': len(zs_list),
        'bi_count': len(bi_list),
        'signal_count': len(buy_signals)
    }


def main():
    print("=" * 70)
    print("平安银行缠论策略回测报告")
    print("策略：第三类买点 | 数据：5分钟K线")
    print("=" * 70)
    
    # 参数设置
    stop_pct = 0.025  # 2.5%止损
    take_pct = 0.05   # 5%止盈
    
    print(f"\n【策略参数】")
    print(f"  止损: {stop_pct*100:.1f}%")
    print(f"  止盈: {take_pct*100:.1f}%")
    print(f"  信号: 第三类买点（向上突破中枢 + 回抽不破ZG）")
    
    # 多轮测试
    print(f"\n【回测结果】\n")
    
    all_results = []
    seeds = [42, 123, 456, 789, 1024]
    
    for i, seed in enumerate(seeds):
        df = generate_pingan_data(seed)
        result = run_backtest(df, stop_pct, take_pct)
        all_results.append(result)
        
        print(f"  轮次 {i+1}: {result['total_trades']}笔交易, "
              f"胜率 {result['win_rate']:.1f}%, "
              f"收益 {result['total_return']:.2f}%")
    
    # 汇总统计
    total_trades = sum(r['total_trades'] for r in all_results)
    total_wins = sum(r['winning_trades'] for r in all_results)
    avg_win_rate = np.mean([r['win_rate'] for r in all_results])
    avg_return = np.mean([r['total_return'] for r in all_results])
    
    print(f"\n" + "=" * 70)
    print("【汇总统计】")
    print("=" * 70)
    print(f"  总交易次数: {total_trades}")
    print(f"  盈利交易: {total_wins}")
    print(f"  亏损交易: {total_trades - total_wins}")
    print(f"  平均胜率: {avg_win_rate:.1f}%")
    print(f"  平均收益: {avg_return:.2f}%")
    
    # 判断
    print(f"\n" + "=" * 70)
    if avg_win_rate >= 68:
        print(f"✅ 达标！胜率 {avg_win_rate:.1f}% >= 68%")
    else:
        print(f"❌ 未达标，胜率 {avg_win_rate:.1f}% < 68%")
    print("=" * 70)
    
    # 详细交易示例
    if all_results[0]['trades']:
        print(f"\n【交易示例】（第1轮）")
        for i, trade in enumerate(all_results[0]['trades'][:5]):
            pnl_str = f"+{trade['pnl_pct']:.2f}%" if trade['pnl_pct'] > 0 else f"{trade['pnl_pct']:.2f}%"
            print(f"  {i+1}. 买入 {trade['entry']:.2f} → 卖出 {trade['exit']:.2f} | {pnl_str} ({trade['reason']})")


if __name__ == "__main__":
    main()
