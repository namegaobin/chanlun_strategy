#!/usr/bin/env python3
"""
Phase 5 业务回归验证：使用新策略验证最近半年表现
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime
from src.crypto_data_fetcher import CryptoDataFetcher
from src.chanlun_structure_v2 import (
    process_inclusion,
    detect_all_fractals,
    build_bi_from_fractals,
    detect_all_zhongshu,
    Zhongshu
)
from src.signal_detector import SignalDetector, SignalType
from src.market_filter_v2 import detect_market_environment_v2
from src.signal_combination import select_signals_by_market_environment


def backtest_with_new_strategy(df, bi_list, zs_list):
    """使用新策略回测"""
    # 市场环境识别
    market_info = detect_market_environment_v2(df, zs_list)
    
    # 信号检测
    detector_signal = SignalDetector()
    signals = detector_signal.detect_all_signals(df, bi_list, zs_list)
    
    # 信号组合
    selected_signals = select_signals_by_market_environment(signals, market_info)
    
    return selected_signals, market_info['environment']


def main():
    print('=' * 70)
    print('Phase 5 业务回归验证：新策略最近半年测试')
    print('=' * 70)
    print()
    
    # 获取数据
    print('[1] 获取BTC最近半年数据...')
    fetcher = CryptoDataFetcher(exchange='binance', proxy='http://127.0.0.1:11090')
    
    try:
        df = fetcher.fetch_historical_klines('BTCUSDT', '5m', days=180)
        print(f'✓ 获取成功: {len(df)} 根K线')
        print(f'✓ 时间范围: {df["date"].min()} ~ {df["date"].max()}')
    except Exception as e:
        print(f'✗ 获取失败: {e}')
        return
    
    print()
    
    # 按月分割
    print('[2] 按月份分割数据...')
    df['year_month'] = df['date'].dt.to_period('M')
    months = list(df.groupby('year_month'))
    print(f'✓ 共 {len(months)} 个月')
    print()
    
    # 回测每个月
    print('[3] 使用新策略回测...')
    print()
    
    results = []
    for period, group in months:
        if len(group) < 2000:
            continue
        
        print(f'[{period}]')
        
        # 缠论分析
        try:
            df_proc = process_inclusion(group)
            fractals = detect_all_fractals(df_proc)
            bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
            zs_list = detect_all_zhongshu(bi_list, min_bi=3)
            
            if not zs_list:
                print('  中枢不足，跳过')
                continue
            
            # 使用新策略
            signals, market_env = backtest_with_new_strategy(group, bi_list, zs_list)
            
            # 打印市场环境
            market_info = detect_market_environment_v2(group, zs_list)
            print(f'  市场环境: {market_info}')
            
            # 调试：打印原始信号数
            detector_debug = SignalDetector()
            all_signals = detector_debug.detect_all_signals(group, bi_list, zs_list)
            print(f'  原始信号: {len(all_signals)} 个')
            
            # 打印信号类型分布
            from collections import Counter
            sig_types = Counter([s.signal_type.value for s in all_signals])
            buy_signals = {k: v for k, v in sig_types.items() if 'buy' in k}
            print(f'  买入信号: {buy_signals}')
            
            print(f'  筛选后: {len(signals)} 个')
            
            if not signals:
                print('  信号不足，跳过')
                continue
            
            print(f'  市场环境: {market_env}')
            print(f'  选中信号: {len(signals)} 个')
            
            # 简单回测
            trades = []
            for sig in signals:
                entry_idx = sig.index
                if entry_idx >= len(group) - 15:
                    continue
                
                entry_price = sig.price
                stop_loss = entry_price * 0.992
                take_profit = entry_price * 1.015
                
                for j in range(entry_idx, min(entry_idx + 15, len(group))):
                    if group.iloc[j]['low'] <= stop_loss:
                        trades.append(-0.8)
                        break
                    elif group.iloc[j]['high'] >= take_profit:
                        trades.append(1.5)
                        break
                else:
                    final = group.iloc[min(entry_idx + 15, len(group)-1)]['close']
                    trades.append((final - entry_price) / entry_price * 100)
            
            if len(trades) >= 3:
                wins = sum(1 for t in trades if t > 0)
                win_rate = wins / len(trades) * 100
                total_return = sum(trades)
                
                status = '✅' if win_rate >= 68 else '❌'
                print(f'  {status} {len(trades)}笔, 胜率{win_rate:.1f}%, 收益{total_return:.2f}%')
                
                results.append({
                    'period': str(period),
                    'env': market_env,
                    'trades': len(trades),
                    'win_rate': win_rate,
                    'return': total_return
                })
            else:
                print(f'  交易不足({len(trades)}笔)')
            
        except Exception as e:
            print(f'  错误: {e}')
        
        print()
    
    # 汇总
    print('=' * 70)
    print('[4] 结果汇总')
    print('=' * 70)
    print()
    
    if results:
        pass_count = sum(1 for r in results if r['win_rate'] >= 68)
        avg_win_rate = np.mean([r['win_rate'] for r in results])
        total_return = sum(r['return'] for r in results)
        annual_return = total_return / len(results) * 12
        
        print(f'测试月份: {len(results)}')
        print(f'达标月份: {pass_count}')
        print(f'平均胜率: {avg_win_rate:.1f}%')
        print(f'年化收益: {annual_return:.1f}%')
        print()
        
        if pass_count == len(results) and annual_return >= 30:
            print('✅ Gate 5 通过！')
        else:
            print(f'❌ Gate 5 未通过')


if __name__ == '__main__':
    main()
