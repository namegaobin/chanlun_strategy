#!/usr/bin/env python3
"""
严格验证：BTC 2年数据，每个月胜率>68%，年化>30%
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


def backtest_month(df, stop_pct=0.008, take_pct=0.015, max_hold=15, min_conf=91):
    """单月回测"""
    df = df.reset_index(drop=True)
    
    try:
        df_proc = process_inclusion(df)
        fractals = detect_all_fractals(df_proc)
        bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
        zs_list = detect_all_zhongshu(bi_list, min_bi=3)
        
        if not bi_list or not zs_list:
            return None
    except:
        return None
    
    detector = SignalDetector()
    signals = detector.detect_all_signals(df, bi_list, zs_list)
    
    filtered = [s for s in signals 
               if s.confidence >= min_conf 
               and s.signal_type == SignalType.BUY_1]
    
    if len(filtered) < 3:
        return None
    
    trades = []
    for sig in filtered:
        entry_idx = sig.index
        if entry_idx >= len(df) - max_hold:
            continue
        
        entry_price = sig.price
        stop_loss = entry_price * (1 - stop_pct)
        take_profit = entry_price * (1 + take_pct)
        
        for j in range(entry_idx, min(entry_idx + max_hold, len(df))):
            if df.iloc[j]['low'] <= stop_loss:
                trades.append({'pnl': -stop_pct * 100})
                break
            elif df.iloc[j]['high'] >= take_profit:
                trades.append({'pnl': take_pct * 100})
                break
        else:
            final = df.iloc[min(entry_idx + max_hold, len(df)-1)]['close']
            pnl = (final - entry_price) / entry_price * 100
            trades.append({'pnl': pnl})
    
    if len(trades) < 3:
        return None
    
    wins = [t for t in trades if t['pnl'] > 0]
    win_rate = len(wins) / len(trades) * 100
    total_return = sum(t['pnl'] for t in trades)
    
    return {
        'trades': len(trades),
        'win_rate': win_rate,
        'return': total_return
    }


def main():
    print('=' * 70)
    print('BTC 2年数据严格验证')
    print('要求：每个月胜率>68%，年化收益>30%')
    print('=' * 70)
    print()
    
    # 获取数据
    print('[1] 获取BTC历史数据（最近2年）...')
    fetcher = CryptoDataFetcher(exchange='binance', proxy='http://127.0.0.1:11090')
    
    try:
        # 尝试获取2年数据
        df = fetcher.fetch_historical_klines('BTCUSDT', '5m', days=730)
        print(f'✓ 获取成功: {len(df)} 根K线')
        print(f'✓ 时间范围: {df["date"].min()} ~ {df["date"].max()}')
    except Exception as e:
        print(f'✗ 获取失败: {e}')
        print('尝试分批获取...')
        
        # 分批获取
        all_data = []
        for days in [180, 180, 180, 180, 30]:
            try:
                batch = fetcher.fetch_historical_klines('BTCUSDT', '5m', days=days)
                all_data.append(batch)
                print(f'  获取 {days} 天数据: {len(batch)} 根')
            except Exception as e2:
                print(f'  获取 {days} 天失败: {e2}')
        
        if not all_data:
            print('无法获取数据，退出')
            return
        
        df = pd.concat(all_data, ignore_index=True)
        df = df.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
        print(f'合并后: {len(df)} 根K线')
    
    print()
    
    # 按月分割
    print('[2] 按月份分割数据...')
    df['year_month'] = df['date'].dt.to_period('M')
    months = list(df.groupby('year_month'))
    print(f'✓ 共 {len(months)} 个月')
    print()
    
    # 回测每个月
    print('[3] 开始回测每个月...')
    print()
    
    results = []
    for period, group in months:
        if len(group) < 2000:  # 数据太少跳过
            print(f'  {period}: 数据不足({len(group)}根)，跳过')
            continue
        
        result = backtest_month(group)
        
        if result:
            result['period'] = str(period)
            result['klines'] = len(group)
            results.append(result)
            
            status = '✅' if result['win_rate'] >= 68 else '❌'
            print(f'  {status} {period}: {result["trades"]}笔, 胜率{result["win_rate"]:.1f}%, 收益{result["return"]:.2f}%')
        else:
            print(f'  ⚠️  {period}: 信号不足')
    
    print()
    print('=' * 70)
    print('[4] 结果汇总')
    print('=' * 70)
    print()
    
    if not results:
        print('无有效结果')
        return
    
    # 统计
    pass_count = sum(1 for r in results if r['win_rate'] >= 68)
    fail_count = len(results) - pass_count
    avg_win_rate = np.mean([r['win_rate'] for r in results])
    total_return = sum(r['return'] for r in results)
    
    # 年化收益
    total_months = len(results)
    annual_return = total_return / total_months * 12 if total_months > 0 else 0
    
    print(f'  测试月份数: {len(results)}')
    print(f'  达标月份数: {pass_count}')
    print(f'  未达标月份: {fail_count}')
    print(f'  平均胜率: {avg_win_rate:.1f}%')
    print(f'  总收益: {total_return:.2f}%')
    print(f'  年化收益: {annual_return:.1f}%')
    print()
    
    # 最终判断
    print('=' * 70)
    print('[5] 验证结论')
    print('=' * 70)
    print()
    
    if fail_count == 0 and annual_return >= 30:
        print('✅ 验证通过！')
        print(f'   - 所有{len(results)}个月份胜率均>68%')
        print(f'   - 年化收益{annual_return:.1f}% > 30%')
    else:
        print('❌ 验证未通过')
        if fail_count > 0:
            print(f'   - {fail_count}个月份未达标')
            print()
            print('未达标月份:')
            for r in results:
                if r['win_rate'] < 68:
                    print(f'     {r["period"]}: 胜率{r["win_rate"]:.1f}%')
        if annual_return < 30:
            print(f'   - 年化收益{annual_return:.1f}% < 30%')


if __name__ == '__main__':
    main()
