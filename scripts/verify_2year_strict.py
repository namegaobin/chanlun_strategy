#!/usr/bin/env python3
"""
BTC 2年历史数据回测验证

验证要求：
1. 真实BTC数据
2. 最近2年时间
3. 任意一个月周期
4. 胜率 > 68%
5. 年化收益率 > 30%
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


def fetch_2year_data(proxy='http://127.0.0.1:11090'):
    """获取2年BTC历史数据"""
    print('[1] 获取 BTC 2年历史数据...')
    
    fetcher = CryptoDataFetcher(exchange='binance', proxy=proxy)
    
    # Binance API限制，需要分批获取
    all_data = []
    end_time = datetime.now()
    
    # 每次获取1000根K线，5分钟K线约3.5天
    # 2年约需要 365*2*24*12 = 175,200 根K线
    # 分批获取，每次1000根
    
    total_days = 365 * 2  # 2年
    
    try:
        df = fetcher.fetch_historical_klines('BTCUSDT', '5m', days=total_days)
        print(f'    ✓ 获取成功: {len(df)} 根K线')
        print(f'    ✓ 时间范围: {df["date"].min()} ~ {df["date"].max()}')
        return df
    except Exception as e:
        print(f'    ✗ 获取失败: {e}')
        return None


def split_by_month(df):
    """按月份分割数据"""
    df['year_month'] = df['date'].dt.to_period('M')
    months = df.groupby('year_month')
    
    result = []
    for period, group in months:
        result.append({
            'period': str(period),
            'start': group['date'].min(),
            'end': group['date'].max(),
            'count': len(group),
            'data': group
        })
    
    return result


def backtest_month(df_month, stop_pct=0.02, take_pct=0.03, max_hold=40, 
                   min_confidence=75, signal_types=None):
    """单月回测"""
    if signal_types is None:
        signal_types = [SignalType.BUY_1, SignalType.BUY_2, SignalType.BUY_3]
    
    df = df_month.reset_index(drop=True)
    
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


def optimize_parameters(df_month):
    """优化参数"""
    best_result = None
    best_params = None
    best_score = 0
    
    # 参数范围
    stop_range = [0.015, 0.02, 0.025, 0.03]
    take_range = [0.02, 0.03, 0.04, 0.05]
    hold_range = [30, 40, 50, 60]
    conf_range = [70, 75, 80, 85]
    
    for stop_pct in stop_range:
        for take_pct in take_range:
            for max_hold in hold_range:
                for min_conf in conf_range:
                    result = backtest_month(
                        df_month,
                        stop_pct=stop_pct,
                        take_pct=take_pct,
                        max_hold=max_hold,
                        min_confidence=min_conf
                    )
                    
                    if result and result['trades'] >= 3:
                        # 评分：胜率权重 + 收益权重
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
    
    return best_result, best_params


def main():
    print('=' * 70)
    print('BTC 2年历史数据回测验证')
    print('目标：任意一个月 胜率>68% 年化收益>30%')
    print('=' * 70)
    print()
    
    # 获取数据
    df = fetch_2year_data()
    if df is None:
        print('获取数据失败，退出')
        return
    
    print()
    
    # 按月分割
    print('[2] 按月份分割数据...')
    months = split_by_month(df)
    print(f'    ✓ 共 {len(months)} 个月')
    print()
    
    # 回测每个月
    print('[3] 开始回测（固定参数）...')
    print()
    
    # 固定参数
    stop_pct = 0.02
    take_pct = 0.03
    max_hold = 40
    min_confidence = 80
    
    results = []
    for month in months:
        if month['count'] < 1000:  # 数据太少跳过
            continue
        
        result = backtest_month(
            month['data'],
            stop_pct=stop_pct,
            take_pct=take_pct,
            max_hold=max_hold,
            min_confidence=min_confidence
        )
        
        if result:
            result['period'] = month['period']
            result['klines'] = month['count']
            results.append(result)
            
            status = '✅' if result['win_rate'] >= 68 else '❌'
            print(f'  {status} {month["period"]}: {result["trades"]}笔, '
                  f'胜率{result["win_rate"]:.1f}%, 收益{result["total_return"]:.2f}%')
    
    print()
    print('=' * 70)
    print('[4] 回测结果汇总')
    print('=' * 70)
    print()
    
    if results:
        # 统计
        pass_count = sum(1 for r in results if r['win_rate'] >= 68)
        total_return = sum(r['total_return'] for r in results)
        avg_win_rate = np.mean([r['win_rate'] for r in results])
        
        # 年化收益率估算
        total_days = sum(r['klines'] for r in results) * 5 / (24 * 60)  # K线数转天数
        annual_return = total_return / total_days * 365 if total_days > 0 else 0
        
        print(f'  总月份数: {len(results)}')
        print(f'  达标月份: {pass_count} ({pass_count/len(results)*100:.1f}%)')
        print(f'  平均胜率: {avg_win_rate:.1f}%')
        print(f'  总收益: {total_return:.2f}%')
        print(f'  年化收益: {annual_return:.2f}%')
        print()
        
        if pass_count == len(results) and annual_return >= 30:
            print('✅ 验证通过！所有月份达标')
        else:
            print('❌ 验证未通过')
            if pass_count < len(results):
                print(f'   - {len(results) - pass_count} 个月未达标')
            if annual_return < 30:
                print(f'   - 年化收益 {annual_return:.1f}% < 30%')
    
    print()
    print('=' * 70)
    print('[5] 参数优化测试（最近3个月）')
    print('=' * 70)
    print()
    
    # 优化最近3个月
    for month in months[-3:]:
        if month['count'] < 1000:
            continue
        
        print(f'  优化 {month["period"]}...')
        best_result, best_params = optimize_parameters(month['data'])
        
        if best_result and best_params:
            status = '✅' if best_result['win_rate'] >= 68 else '❌'
            print(f'    {status} 最优参数:')
            print(f'       止损={best_params["stop_pct"]*100:.1f}%, '
                  f'止盈={best_params["take_pct"]*100:.1f}%, '
                  f'持仓={best_params["max_hold"]}根')
            print(f'       结果: {best_result["trades"]}笔, '
                  f'胜率{best_result["win_rate"]:.1f}%, '
                  f'收益{best_result["total_return"]:.2f}%')
        print()
    
    print('=' * 70)
    print('验证完成')
    print('=' * 70)


if __name__ == '__main__':
    main()
