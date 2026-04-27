#!/usr/bin/env python3
"""
BTC 历史数据回测验证（优化版）

分批获取数据，逐步验证
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.crypto_data_fetcher import CryptoDataFetcher
from src.chanlun_structure_v2 import (
    process_inclusion,
    detect_all_fractals,
    build_bi_from_fractals,
    detect_all_zhongshu
)
from src.signal_detector import SignalDetector, SignalType


def backtest_period(df, stop_pct=0.02, take_pct=0.03, max_hold=40, 
                   min_confidence=80, signal_types=None):
    """时间段回测"""
    if signal_types is None:
        signal_types = [SignalType.BUY_1, SignalType.BUY_2, SignalType.BUY_3]
    
    df = df.reset_index(drop=True)
    
    # 缠论分析
    try:
        df_proc = process_inclusion(df)
        fractals = detect_all_fractals(df_proc)
        bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
        zs_list = detect_all_zhongshu(bi_list, min_bi=3)
        
        if not bi_list or not zs_list:
            return None
    except Exception as e:
        return None
    
    # 信号检测
    detector = SignalDetector()
    signals = detector.detect_all_signals(df, bi_list, zs_list)
    
    # 过滤信号类型和置信度
    filtered_signals = [
        s for s in signals 
        if s.signal_type in signal_types and s.confidence >= min_confidence
    ]
    
    if not filtered_signals:
        return None
    
    # 回测
    trades = []
    for sig in filtered_signals:
        entry_idx = sig.index
        if entry_idx >= len(df) - max_hold:
            continue
        
        is_buy = 'buy' in sig.signal_type.value
        entry_price = sig.price
        
        if is_buy:
            stop_loss = entry_price * (1 - stop_pct)
            take_profit = entry_price * (1 + take_pct)
            
            for j in range(entry_idx, min(entry_idx + max_hold, len(df))):
                if df.iloc[j]['low'] <= stop_loss:
                    trades.append({'pnl_pct': -stop_pct * 100, 'type': sig.signal_type.value})
                    break
                elif df.iloc[j]['high'] >= take_profit:
                    trades.append({'pnl_pct': take_pct * 100, 'type': sig.signal_type.value})
                    break
            else:
                final = df.iloc[min(entry_idx + max_hold, len(df)-1)]['close']
                pnl = (final - entry_price) / entry_price * 100
                trades.append({'pnl_pct': pnl, 'type': sig.signal_type.value})
    
    if not trades:
        return None
    
    wins = [t for t in trades if t['pnl_pct'] > 0]
    win_rate = len(wins) / len(trades) * 100
    total_return = sum(t['pnl_pct'] for t in trades)
    
    return {
        'trades': len(trades),
        'win_rate': win_rate,
        'total_return': total_return,
        'avg_pnl': np.mean([t['pnl_pct'] for t in trades])
    }


def main():
    print('=' * 70)
    print('BTC 历史数据回测验证')
    print('目标：任意一个月 胜率>68%')
    print('=' * 70)
    print()
    
    # 获取数据
    print('[1] 获取 BTC 历史数据（分批获取）...')
    fetcher = CryptoDataFetcher(exchange='binance', proxy='http://127.0.0.1:11090')
    
    all_results = []
    
    # 分批获取不同时间段的数据
    periods = [
        {'days': 30, 'label': '最近1个月'},
        {'days': 60, 'label': '最近2个月'},
        {'days': 90, 'label': '最近3个月'},
        {'days': 180, 'label': '最近6个月'},
        {'days': 365, 'label': '最近1年'},
    ]
    
    for period in periods:
        print(f'\n正在获取 {period["label"]} 数据...')
        
        try:
            df = fetcher.fetch_historical_klines('BTCUSDT', '5m', days=period['days'])
            
            if df is None or len(df) < 1000:
                print(f'  ✗ 数据不足')
                continue
            
            print(f'  ✓ 获取成功: {len(df)} 根K线')
            print(f'  ✓ 价格范围: ${df["close"].min():,.0f} ~ ${df["close"].max():,.0f}')
            
            # 回测
            result = backtest_period(
                df,
                stop_pct=0.02,
                take_pct=0.03,
                max_hold=40,
                min_confidence=80
            )
            
            if result:
                result['period'] = period['label']
                result['klines'] = len(df)
                all_results.append(result)
                
                status = '✅' if result['win_rate'] >= 68 else '❌'
                print(f'  {status} {result["trades"]}笔交易, '
                      f'胜率{result["win_rate"]:.1f}%, '
                      f'收益{result["total_return"]:.2f}%')
            else:
                print(f'  ⚠️  无有效信号')
                
        except Exception as e:
            print(f'  ✗ 获取失败: {e}')
    
    print()
    print('=' * 70)
    print('[2] 回测结果汇总')
    print('=' * 70)
    print()
    
    if all_results:
        pass_count = sum(1 for r in all_results if r['win_rate'] >= 68)
        avg_win_rate = np.mean([r['win_rate'] for r in all_results])
        total_return = sum(r['total_return'] for r in all_results)
        
        print(f'  测试周期数: {len(all_results)}')
        print(f'  达标周期数: {pass_count}')
        print(f'  平均胜率: {avg_win_rate:.1f}%')
        print(f'  总收益: {total_return:.2f}%')
        print()
        
        if pass_count == len(all_results):
            print('✅ 所有周期达标！')
        else:
            print(f'❌ {len(all_results) - pass_count} 个周期未达标')
    
    print()
    print('=' * 70)
    print('[3] 参数优化测试')
    print('=' * 70)
    print()
    
    # 获取最近3个月数据进行参数优化
    print('获取最近3个月数据...')
    try:
        df = fetcher.fetch_historical_klines('BTCUSDT', '5m', days=90)
        print(f'✓ 获取成功: {len(df)} 根K线')
        print()
        
        # 参数网格搜索
        best_result = None
        best_params = None
        best_score = 0
        
        print('参数优化中...')
        count = 0
        total = 4 * 4 * 3 * 3  # 总组合数
        
        for stop_pct in [0.015, 0.02, 0.025, 0.03]:
            for take_pct in [0.02, 0.03, 0.04, 0.05]:
                for max_hold in [30, 40, 50]:
                    for min_conf in [75, 80, 85]:
                        count += 1
                        if count % 20 == 0:
                            print(f'  进度: {count}/{total}')
                        
                        result = backtest_period(
                            df,
                            stop_pct=stop_pct,
                            take_pct=take_pct,
                            max_hold=max_hold,
                            min_confidence=min_conf
                        )
                        
                        if result and result['trades'] >= 5:
                            score = result['win_rate'] * 0.7 + min(result['total_return'], 10) * 3
                            
                            if score > best_score:
                                best_score = score
                                best_result = result
                                best_params = {
                                    'stop_pct': stop_pct,
                                    'take_pct': take_pct,
                                    'max_hold': max_hold,
                                    'min_confidence': min_conf
                                }
        
        print()
        if best_result and best_params:
            print('【最优参数】')
            print(f'  止损: {best_params["stop_pct"]*100:.1f}%')
            print(f'  止盈: {best_params["take_pct"]*100:.1f}%')
            print(f'  最大持仓: {best_params["max_hold"]} 根K线')
            print(f'  最低置信度: {best_params["min_confidence"]}%')
            print()
            print('【最优结果】')
            print(f'  交易次数: {best_result["trades"]}')
            print(f'  胜率: {best_result["win_rate"]:.1f}%')
            print(f'  总收益: {best_result["total_return"]:.2f}%')
            print()
            
            if best_result['win_rate'] >= 68:
                print('✅ 达到68%胜率目标！')
            else:
                print(f'❌ 未达标，差距 {68 - best_result["win_rate"]:.1f}%')
        else:
            print('未找到有效参数组合')
            
    except Exception as e:
        print(f'✗ 优化失败: {e}')
    
    print()
    print('=' * 70)
    print('验证完成')
    print('=' * 70)


if __name__ == '__main__':
    main()
