#!/usr/bin/env python3
"""
完整信号回测脚本

测试所有信号类型的回测效果
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from src.crypto_data_fetcher import CryptoDataFetcher
from src.chanlun_structure_v2 import (
    process_inclusion,
    detect_all_fractals,
    build_bi_from_fractals,
    detect_all_zhongshu
)
from src.signal_detector import SignalDetector, SignalType

def run_backtest_with_signals(df, signals, stop_pct=0.025, take_pct=0.05, max_hold=60):
    """运行回测"""
    trades = []
    
    for sig in signals:
        entry_idx = sig.index
        if entry_idx >= len(df) - max_hold:
            continue
        
        # 根据信号类型确定方向
        is_buy = 'buy' in sig.signal_type.value
        
        entry_price = sig.price
        
        if is_buy:
            # 买入信号
            stop_loss = entry_price * (1 - stop_pct)
            take_profit = entry_price * (1 + take_pct)
            
            for j in range(entry_idx, min(entry_idx + max_hold, len(df))):
                if df.iloc[j]['low'] <= stop_loss:
                    trades.append({
                        'type': sig.signal_type.value,
                        'entry': entry_price,
                        'exit': df.iloc[j]['close'],
                        'pnl_pct': -stop_pct * 100,
                        'reason': 'stop_loss'
                    })
                    break
                elif df.iloc[j]['high'] >= take_profit:
                    trades.append({
                        'type': sig.signal_type.value,
                        'entry': entry_price,
                        'exit': df.iloc[j]['close'],
                        'pnl_pct': take_pct * 100,
                        'reason': 'take_profit'
                    })
                    break
            else:
                final = df.iloc[min(entry_idx + max_hold, len(df)-1)]['close']
                pnl = (final - entry_price) / entry_price * 100
                trades.append({
                    'type': sig.signal_type.value,
                    'entry': entry_price,
                    'exit': final,
                    'pnl_pct': pnl,
                    'reason': 'time_exit'
                })
        else:
            # 卖出信号（做空）
            stop_loss = entry_price * (1 + stop_pct)
            take_profit = entry_price * (1 - take_pct)
            
            for j in range(entry_idx, min(entry_idx + max_hold, len(df))):
                if df.iloc[j]['high'] >= stop_loss:
                    trades.append({
                        'type': sig.signal_type.value,
                        'entry': entry_price,
                        'exit': df.iloc[j]['close'],
                        'pnl_pct': -stop_pct * 100,
                        'reason': 'stop_loss'
                    })
                    break
                elif df.iloc[j]['low'] <= take_profit:
                    trades.append({
                        'type': sig.signal_type.value,
                        'entry': entry_price,
                        'exit': df.iloc[j]['close'],
                        'pnl_pct': take_pct * 100,
                        'reason': 'take_profit'
                    })
                    break
            else:
                final = df.iloc[min(entry_idx + max_hold, len(df)-1)]['close']
                pnl = (entry_price - final) / entry_price * 100  # 做空方向
                trades.append({
                    'type': sig.signal_type.value,
                    'entry': entry_price,
                    'exit': final,
                    'pnl_pct': pnl,
                    'reason': 'time_exit'
                })
    
    return trades


def main():
    print('=' * 70)
    print('BTC 完整信号回测（14天数据）')
    print('=' * 70)
    print()
    
    # 获取数据
    print('[1] 获取 BTC 5分钟历史数据...')
    fetcher = CryptoDataFetcher(exchange='binance', proxy='http://127.0.0.1:11090')
    df = fetcher.fetch_historical_klines('BTCUSDT', '5m', days=14)
    
    print(f'    ✓ 获取成功: {len(df)} 根K线')
    print()
    
    # 缠论分析
    print('[2] 缠论结构分析...')
    df_proc = process_inclusion(df)
    fractals = detect_all_fractals(df_proc)
    bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
    zs_list = detect_all_zhongshu(bi_list, min_bi=3)
    
    print(f'    ✓ 笔: {len(bi_list)}, 中枢: {len(zs_list)}')
    print()
    
    # 信号检测
    print('[3] 检测所有信号类型...')
    detector = SignalDetector()
    signals = detector.detect_all_signals(df, bi_list, zs_list)
    
    print(f'    ✓ 总信号数: {len(signals)}')
    print()
    
    # 分信号类型回测
    print('=' * 70)
    print('[4] 分信号类型回测')
    print('=' * 70)
    print()
    
    stop_pct = 0.025
    take_pct = 0.05
    
    results = {}
    
    for sig_type in SignalType:
        sig_list = [s for s in signals if s.signal_type == sig_type]
        if not sig_list:
            continue
        
        trades = run_backtest_with_signals(df, sig_list, stop_pct, take_pct)
        
        if trades:
            wins = [t for t in trades if t['pnl_pct'] > 0]
            win_rate = len(wins) / len(trades) * 100
            total_return = sum(t['pnl_pct'] for t in trades)
            avg_pnl = np.mean([t['pnl_pct'] for t in trades])
            
            results[sig_type.value] = {
                'count': len(trades),
                'win_rate': win_rate,
                'total_return': total_return,
                'avg_pnl': avg_pnl
            }
            
            print(f'  {sig_type.value}:')
            print(f'    交易次数: {len(trades)}')
            print(f'    胜率: {win_rate:.1f}%')
            print(f'    总收益: {total_return:.2f}%')
            print(f'    平均收益: {avg_pnl:.2f}%')
            print()
    
    # 综合回测
    print('=' * 70)
    print('[5] 综合回测（所有信号）')
    print('=' * 70)
    print()
    
    all_trades = run_backtest_with_signals(df, signals, stop_pct, take_pct)
    
    if all_trades:
        wins = [t for t in all_trades if t['pnl_pct'] > 0]
        win_rate = len(wins) / len(all_trades) * 100
        total_return = sum(t['pnl_pct'] for t in all_trades)
        avg_pnl = np.mean([t['pnl_pct'] for t in all_trades])
        
        print(f'  总交易次数: {len(all_trades)}')
        print(f'  总胜率: {win_rate:.1f}%')
        print(f'  总收益: {total_return:.2f}%')
        print(f'  平均收益: {avg_pnl:.2f}%')
        print()
        
        # 按买卖方向统计
        buy_trades = [t for t in all_trades if 'buy' in t['type']]
        sell_trades = [t for t in all_trades if 'sell' in t['type']]
        
        print(f'  买入信号: {len(buy_trades)} 笔, 胜率 {len([t for t in buy_trades if t["pnl_pct"] > 0]) / len(buy_trades) * 100 if buy_trades else 0:.1f}%')
        print(f'  卖出信号: {len(sell_trades)} 笔, 胜率 {len([t for t in sell_trades if t["pnl_pct"] > 0]) / len(sell_trades) * 100 if sell_trades else 0:.1f}%')
    
    print()
    print('=' * 70)
    print('回测完成')
    print('=' * 70)


if __name__ == '__main__':
    main()
