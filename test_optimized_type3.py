#!/usr/bin/env python3
"""
TYPE_3 优化前后对比测试

对比原版TYPE_3和优化版TYPE_3的回测效果
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['https_proxy'] = 'http://127.0.0.1:11090'

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests

from src.chanlun_structure_v2 import process_inclusion, detect_all_fractals, build_bi_from_fractals, detect_all_zhongshu, Direction
from src.strategy_selector import SignalType, Signal
from src.multi_strategy_config import StrategyConfigManager
from src.optimized_type3_detector import OptimizedType3Detector


PROXY = 'http://127.0.0.1:11090'


def fetch_btc_data(days=60):
    print(f'[1] 获取BTC最近 {days} 天数据...')
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    all_data, current_end = [], end_time
    
    while current_end > start_time:
        try:
            resp = requests.get('https://api.binance.com/api/v3/klines',
                params={'symbol': 'BTCUSDT', 'interval': '5m', 'limit': 1000, 'endTime': current_end},
                timeout=30, proxies={'https': PROXY})
            data = resp.json()
            if not data: break
            all_data = data + all_data
            current_end = data[0][0] - 1
            print(f'   已获取 {len(all_data)} 条K线...', end='\r')
        except: break
    
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = df[c].astype(float)
    df = df[df['timestamp'] >= start_time]
    print(f'\n   ✓ 获取成功: {len(df)} 根K线')
    return df[['date', 'open', 'high', 'low', 'close', 'volume']]


def backtest_signals(df, signals, config):
    """回测信号"""
    trades = []
    
    for sig in signals:
        entry_idx = sig.index if hasattr(sig, 'index') else sig.get('index')
        entry_price = sig.price if hasattr(sig, 'price') else sig.get('price')
        signal_type = sig.signal_type if hasattr(sig, 'signal_type') else sig.get('signal_type')
        
        if entry_idx >= len(df) - 1: continue
        
        is_buy = 'buy' in str(signal_type).lower()
        stop_pct = config.get('stop_loss_pct', 2.5)
        take_pct = config.get('take_profit_pct', 8.0)
        max_hold = int(config.get('max_hold_hours', 24) * 12)
        pos = config.get('position_size', 0.15)
        
        sl = entry_price * (1 - stop_pct/100) if is_buy else entry_price * (1 + stop_pct/100)
        tp = entry_price * (1 + take_pct/100) if is_buy else entry_price * (1 - take_pct/100)
        
        exit_price, exit_reason = None, None
        for i in range(entry_idx + 1, min(entry_idx + max_hold + 1, len(df))):
            if is_buy:
                if df.iloc[i]['low'] <= sl: exit_price, exit_reason = sl, 'stop_loss'; break
                if df.iloc[i]['high'] >= tp: exit_price, exit_reason = tp, 'take_profit'; break
            else:
                if df.iloc[i]['high'] >= sl: exit_price, exit_reason = sl, 'stop_loss'; break
                if df.iloc[i]['low'] <= tp: exit_price, exit_reason = tp, 'take_profit'; break
        
        if not exit_price:
            exit_price = df.iloc[min(entry_idx + max_hold, len(df) - 1)]['close']
            exit_reason = 'timeout'
        
        pnl = (exit_price - entry_price) / entry_price * 100 if is_buy else (entry_price - exit_price) / entry_price * 100
        
        trades.append({
            'signal_type': str(signal_type),
            'entry_time': str(df.iloc[entry_idx]['date']),
            'entry_price': entry_price,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'hold_hours': (min(entry_idx + max_hold, len(df) - 1) - entry_idx) / 12,
            'pnl_pct': pnl,
            'pnl_actual': pnl * pos
        })
    
    return trades


def main():
    # 获取数据
    df = fetch_btc_data(days=60)
    
    print('\n[2] 缠论结构分析...')
    df_proc = process_inclusion(df)
    fractals = detect_all_fractals(df_proc)
    bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
    zs_list = detect_all_zhongshu(bi_list, min_bi=3)
    print(f'   ✓ 笔: {len(bi_list)}, 中枢: {len(zs_list)}')
    
    # 原版TYPE_3信号检测
    print('\n[3] 检测原版TYPE_3信号...')
    original_signals = []
    DIR_UP, DIR_DOWN = Direction.UP, Direction.DOWN
    
    for i, bi in enumerate(bi_list):
        if bi.direction == DIR_DOWN:
            for zs in zs_list:
                if bi.low > zs.zg and bi.end_index > zs.end_index:
                    original_signals.append({
                        'signal_type': 'buy_3_original',
                        'price': bi.low,
                        'index': bi.end_index,
                        'confidence': 80.0
                    })
                    break
        if bi.direction == DIR_UP:
            for zs in zs_list:
                if bi.high < zs.zd and bi.end_index > zs.end_index:
                    original_signals.append({
                        'signal_type': 'sell_3_original',
                        'price': bi.high,
                        'index': bi.end_index,
                        'confidence': 80.0
                    })
                    break
    
    print(f'   ✓ 原版TYPE_3信号: {len(original_signals)} 个')
    
    # 优化版TYPE_3信号检测（专家反馈修正版 - 简化版）
    print('\n[4] 检测优化版TYPE_3信号...')
    detector = OptimizedType3Detector(
        min_leave_ratio=0.5,    # 离开段需要有足够幅度
        max_pullback_ratio=0.5,
        min_zs_age=3,
        use_trend_filter=True   # 趋势过滤
    )
    optimized_signals = detector.detect_all(bi_list, zs_list, df)
    print(f'   ✓ 优化版TYPE_3信号: {len(optimized_signals)} 个')
    
    # 转换为统一格式
    optimized_signals_dict = [
        {
            'signal_type': f'{s.signal_type}_optimized',
            'price': s.price,
            'index': s.index,
            'confidence': s.confidence
        }
        for s in optimized_signals
    ]
    
    # 回测配置
    config = {
        'stop_loss_pct': 2.5,
        'take_profit_pct': 8.0,
        'max_hold_hours': 24,
        'position_size': 0.15
    }
    
    # 回测
    print('\n[5] 回测对比...')
    original_trades = backtest_signals(df, original_signals, config)
    optimized_trades = backtest_signals(df, optimized_signals_dict, config)
    
    # 统计结果
    def calc_stats(trades, name):
        if not trades:
            return {'name': name, 'trades': 0, 'win_rate': 0, 'return': 0}
        wins = [t for t in trades if t['pnl_pct'] > 0]
        return {
            'name': name,
            'trades': len(trades),
            'wins': len(wins),
            'win_rate': len(wins) / len(trades) * 100,
            'return': sum(t['pnl_actual'] for t in trades),
            'avg_pnl': np.mean([t['pnl_pct'] for t in trades]),
            'max_profit': max(t['pnl_pct'] for t in trades),
            'max_loss': min(t['pnl_pct'] for t in trades)
        }
    
    original_stats = calc_stats(original_trades, '原版TYPE_3')
    optimized_stats = calc_stats(optimized_trades, '优化版TYPE_3')
    
    # 输出对比报告
    print('\n' + '='*80)
    print('TYPE_3 优化前后对比报告')
    print('='*80)
    
    print(f'\n{"版本":<15} {"交易数":<8} {"盈利数":<8} {"胜率":<10} {"收益率":<12} {"平均盈亏":<10} {"最大盈利":<10} {"最大亏损":<10}')
    print('-'*80)
    
    for stats in [original_stats, optimized_stats]:
        if stats['trades'] > 0:
            print(f"{stats['name']:<15} {stats['trades']:<8} {stats['wins']:<8} {stats['win_rate']:.1f}%{'':<5} {stats['return']:+.2f}%{'':<6} {stats['avg_pnl']:+.2f}%{'':<4} +{stats['max_profit']:.2f}%{'':<5} {stats['max_loss']:.2f}%")
    
    print('\n' + '='*80)
    print('改进效果分析')
    print('='*80)
    
    if original_stats['trades'] > 0 and optimized_stats['trades'] > 0:
        trade_reduction = (1 - optimized_stats['trades'] / original_stats['trades']) * 100
        win_rate_improve = optimized_stats['win_rate'] - original_stats['win_rate']
        return_improve = optimized_stats['return'] - original_stats['return']
        
        print(f'\n信号数量: {original_stats["trades"]} → {optimized_stats["trades"]} (减少 {trade_reduction:.1f}%)')
        print(f'胜率: {original_stats["win_rate"]:.1f}% → {optimized_stats["win_rate"]:.1f}% (提升 {win_rate_improve:+.1f}%)')
        print(f'收益率: {original_stats["return"]:+.2f}% → {optimized_stats["return"]:+.2f}% (提升 {return_improve:+.2f}%)')
        
        if win_rate_improve > 10:
            print('\n✅ 优化效果显著！胜率提升超过10个百分点')
        elif win_rate_improve > 5:
            print('\n⚠️ 优化有一定效果，胜率提升5-10个百分点')
        else:
            print('\n❌ 优化效果不明显，需要进一步调整参数')
    else:
        print('\n⚠️ 数据不足，无法对比')
    
    # 保存详细交易记录
    os.makedirs('output', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    import csv
    for trades, name in [(original_trades, 'original'), (optimized_trades, 'optimized')]:
        if trades:
            filename = f'output/type3_{name}_{timestamp}.csv'
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['signal_type', 'entry_time', 'entry_price', 'exit_price', 'exit_reason', 'hold_hours', 'pnl_pct', 'pnl_actual'])
                writer.writeheader()
                writer.writerows(trades)
            print(f'\n✓ 交易明细已保存: {filename}')
    
    print('\n' + '='*80)


if __name__ == "__main__":
    main()
