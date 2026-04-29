#!/usr/bin/env python3
"""回测结果可视化"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import warnings
warnings.filterwarnings('ignore')

PROXY = 'http://127.0.0.1:11090'
os.environ['https_proxy'] = PROXY

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'STHeiti']
plt.rcParams['axes.unicode_minus'] = False

from src.chanlun_structure_v2 import process_inclusion, detect_all_fractals, build_bi_from_fractals, detect_all_zhongshu
from src.strategy_selector import SignalType, Signal
from src.multi_strategy_config import StrategyConfigManager
from src.chanlun_structure_v2 import Direction


class SimpleSignalDetector:
    def detect_all_signals(self, df, bi_list, zs_list):
        signals = []
        if not bi_list or not zs_list:
            return signals
        
        DIR_UP, DIR_DOWN = Direction.UP, Direction.DOWN
        
        for i, bi in enumerate(bi_list):
            if bi.direction == DIR_DOWN:
                for zs in zs_list:
                    if bi.low > zs.zg and bi.end_index > zs.end_index:
                        signals.append(Signal(SignalType.BUY_3, 80.0, bi.low, df.iloc[bi.end_index]['date'], {'bi_idx': i, 'zs_idx': zs_list.index(zs)}, bi.end_index))
                        break
            
            if bi.direction == DIR_UP:
                for zs in zs_list:
                    if bi.high < zs.zd and bi.end_index > zs.end_index:
                        signals.append(Signal(SignalType.SELL_3, 80.0, bi.high, df.iloc[bi.end_index]['date'], {'bi_idx': i, 'zs_idx': zs_list.index(zs)}, bi.end_index))
                        break
            
            if bi.direction == DIR_DOWN:
                for zs in zs_list:
                    if bi.end_index > zs.end_index:
                        signals.append(Signal(SignalType.BUY_1, 75.0, bi.low, df.iloc[bi.end_index]['date'], {'bi_idx': i, 'zs_idx': zs_list.index(zs)}, bi.end_index))
                        break
            
            if bi.direction == DIR_UP:
                for zs in zs_list:
                    if bi.end_index > zs.end_index:
                        signals.append(Signal(SignalType.SELL_1, 75.0, bi.high, df.iloc[bi.end_index]['date'], {'bi_idx': i, 'zs_idx': zs_list.index(zs)}, bi.end_index))
                        break
        
        buy1_signals = [s for s in signals if s.signal_type == SignalType.BUY_1]
        for sig in buy1_signals:
            for bi in bi_list:
                if bi.direction == DIR_UP and bi.start_index > sig.index:
                    signals.append(Signal(SignalType.BUY_2, 70.0, bi.low, df.iloc[bi.start_index]['date'], {'related_buy1': sig.index}, bi.start_index))
                    break
        
        signals.sort(key=lambda s: s.index)
        return signals


def fetch_btc_data(days=90):
    print(f"\n[1] 获取BTC最近 {days} 天数据...")
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
            print(f"   已获取 {len(all_data)} 条K线...", end='\r')
        except Exception as e:
            print(f"   获取数据错误: {e}")
            break
    
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = df[c].astype(float)
    df = df[df['timestamp'] >= start_time]
    print(f"\n   ✓ 获取成功: {len(df)} 根K线")
    return df[['date', 'open', 'high', 'low', 'close', 'volume']]


def backtest_with_curve(df, signals, strategy_type, config):
    """回测并生成资金曲线"""
    signal_map = {'TYPE_1': [SignalType.BUY_1, SignalType.SELL_1], 'TYPE_2': [SignalType.BUY_2], 'TYPE_3': [SignalType.BUY_3, SignalType.SELL_3]}
    filtered = [s for s in signals if s.signal_type in signal_map.get(strategy_type, []) and s.confidence >= config.get('confidence_threshold', 0.6) * 100]
    
    trades = []
    equity_curve = [100]  # 初始资金100
    equity_dates = [df.iloc[0]['date']]
    current_equity = 100
    
    for sig in filtered:
        if sig.index >= len(df) - 1: continue
        is_buy = sig.signal_type in [SignalType.BUY_1, SignalType.BUY_2, SignalType.BUY_3]
        stop_pct, take_pct = config.get('stop_loss_ratio', 0.02) * 100, config.get('take_profit_ratio', 0.05) * 100
        max_hold = int(config.get('max_holding_hours', 24) * 12)
        pos = config.get('position_size', 0.1)
        
        sl = sig.price * (1 - stop_pct/100) if is_buy else sig.price * (1 + stop_pct/100)
        tp = sig.price * (1 + take_pct/100) if is_buy else sig.price * (1 - take_pct/100)
        
        exit_price, exit_idx = None, None
        for i in range(sig.index + 1, min(sig.index + max_hold + 1, len(df))):
            if is_buy:
                if df.iloc[i]['low'] <= sl: exit_price, exit_idx = sl, i; break
                if df.iloc[i]['high'] >= tp: exit_price, exit_idx = tp, i; break
            else:
                if df.iloc[i]['high'] >= sl: exit_price, exit_idx = sl, i; break
                if df.iloc[i]['low'] <= tp: exit_price, exit_idx = tp, i; break
        
        if not exit_price:
            exit_idx = min(sig.index + max_hold, len(df) - 1)
            exit_price = df.iloc[exit_idx]['close']
        
        pnl = (exit_price - sig.price) / sig.price * 100 if is_buy else (sig.price - exit_price) / sig.price * 100
        current_equity *= (1 + pnl * pos / 100)
        
        # 更新资金曲线
        for i in range(len(equity_dates), sig.index):
            if i < len(df):
                equity_curve.append(equity_curve[-1])
                equity_dates.append(df.iloc[i]['date'])
        
        equity_curve.append(current_equity)
        equity_dates.append(df.iloc[exit_idx]['date'])
        
        trades.append({'pnl': pnl, 'pos': pos})
    
    if not trades:
        return None, None, {'strategy': strategy_type, 'trades': 0, 'win_rate': 0, 'return': 0}
    
    wins = [t for t in trades if t['pnl'] > 0]
    return equity_curve, equity_dates, {
        'strategy': strategy_type,
        'trades': len(trades),
        'win_rate': len(wins) / len(trades) * 100,
        'return': (current_equity - 100),
        'max_drawdown': min(equity_curve) / max(equity_curve) * 100 - 100 if equity_curve else 0
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=90, help='回测天数')
    args = parser.parse_args()
    
    # 获取数据
    df = fetch_btc_data(days=args.days)
    
    print("\n[2] 缠论结构分析...")
    df_proc = process_inclusion(df)
    fractals = detect_all_fractals(df_proc)
    bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
    zs_list = detect_all_zhongshu(bi_list, min_bi=3)
    print(f"   ✓ 笔: {len(bi_list)}, 中枢: {len(zs_list)}")
    
    print("\n[3] 检测信号...")
    detector = SimpleSignalDetector()
    signals = detector.detect_all_signals(df, bi_list, zs_list)
    print(f"   ✓ 总信号数: {len(signals)}")
    
    print("\n[4] 回测三套策略...")
    config_mgr = StrategyConfigManager()
    
    all_curves = {}
    all_stats = {}
    
    for st in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
        cfg = config_mgr.get_config(st)
        if cfg is None: continue
        cfg_dict = {'confidence_threshold': cfg.confidence_threshold, 'stop_loss_ratio': cfg.stop_loss_ratio,
                    'take_profit_ratio': cfg.take_profit_ratio, 'position_size': cfg.position_size,
                    'max_holding_hours': cfg.max_holding_hours}
        
        curve, dates, stats = backtest_with_curve(df, signals, st, cfg_dict)
        if curve:
            all_curves[st] = (curve, dates)
            all_stats[st] = stats
            print(f"   ✓ {st}: {stats['trades']} 笔, 胜率 {stats['win_rate']:.1f}%, 收益 {stats['return']:+.2f}%")
    
    # 创建可视化
    print("\n[5] 生成可视化图表...")
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. 资金曲线对比
    ax1 = axes[0, 0]
    colors = {'TYPE_1': '#2E86AB', 'TYPE_2': '#A23B72', 'TYPE_3': '#F18F01'}
    for st, (curve, dates) in all_curves.items():
        ax1.plot(dates, curve, label=f"{st} ({all_stats[st]['return']:+.1f}%)", linewidth=2, color=colors[st])
    ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.5)
    ax1.set_title('Strategy Equity Curves', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Equity (Base=100)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # 2. 胜率对比
    ax2 = axes[0, 1]
    strategies = list(all_stats.keys())
    win_rates = [all_stats[s]['win_rate'] for s in strategies]
    bars = ax2.bar(strategies, win_rates, color=[colors[s] for s in strategies], alpha=0.8)
    ax2.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='50% baseline')
    ax2.set_title('Win Rate Comparison', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Win Rate (%)')
    ax2.set_ylim(0, 70)
    ax2.legend()
    for bar, rate in zip(bars, win_rates):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f'{rate:.1f}%', ha='center', fontsize=11)
    
    # 3. 总收益对比
    ax3 = axes[1, 0]
    returns = [all_stats[s]['return'] for s in strategies]
    colors_bar = ['green' if r > 0 else 'red' for r in returns]
    bars = ax3.bar(strategies, returns, color=[colors[s] for s in strategies], alpha=0.8)
    ax3.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
    ax3.set_title('Total Return Comparison', fontsize=14, fontweight='bold')
    ax3.set_ylabel('Return (%)')
    for bar, ret in zip(bars, returns):
        y_pos = bar.get_height() + 2 if ret > 0 else bar.get_height() - 5
        ax3.text(bar.get_x() + bar.get_width()/2, y_pos, f'{ret:+.1f}%', ha='center', fontsize=11)
    
    # 4. 策略配置表格
    ax4 = axes[1, 1]
    ax4.axis('off')
    table_data = [
        ['Strategy', 'Trades', 'Win Rate', 'Return', 'Config'],
        ['TYPE_1\n(Trend Reversal)', str(all_stats.get('TYPE_1', {}).get('trades', 0)), 
         f"{all_stats.get('TYPE_1', {}).get('win_rate', 0):.1f}%", f"{all_stats.get('TYPE_1', {}).get('return', 0):+.2f}%",
         'SL:1.5% TP:3% Pos:5%'],
        ['TYPE_2\n(Trend Confirm)', str(all_stats.get('TYPE_2', {}).get('trades', 0)),
         f"{all_stats.get('TYPE_2', {}).get('win_rate', 0):.1f}%", f"{all_stats.get('TYPE_2', {}).get('return', 0):+.2f}%",
         'SL:2% TP:5% Pos:10%'],
        ['TYPE_3\n(Trend Continue)', str(all_stats.get('TYPE_3', {}).get('trades', 0)),
         f"{all_stats.get('TYPE_3', {}).get('win_rate', 0):.1f}%", f"{all_stats.get('TYPE_3', {}).get('return', 0):+.2f}%",
         'SL:2.5% TP:8% Pos:15%']
    ]
    table = ax4.table(cellText=table_data[1:], colLabels=table_data[0], loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.8)
    for i in range(5):
        table[(0, i)].set_facecolor('#4472C4')
        table[(0, i)].set_text_props(color='white', fontweight='bold')
    ax4.set_title('Strategy Summary', fontsize=14, fontweight='bold', pad=20)
    
    plt.suptitle(f'BTC Multi-Strategy Backtest Results\n({args.days} days, 5min data)', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    # 保存图片
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'{output_dir}/backtest_visualization_{args.days}d_{timestamp}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n✓ 可视化图表已保存: {output_file}")
    
    plt.close()
    
    # 额外生成：按月收益统计
    print("\n[6] 生成月度收益统计...")
    fig2, ax = plt.subplots(figsize=(14, 6))
    
    # 计算各策略月度收益
    for st, (curve, dates) in all_curves.items():
        df_equity = pd.DataFrame({'date': dates, 'equity': curve})
        df_equity['month'] = pd.to_datetime(df_equity['date']).dt.to_period('M')
        monthly = df_equity.groupby('month')['equity'].last().pct_change() * 100
        monthly = monthly.dropna()
        
        x = range(len(monthly))
        ax.bar([i + list(all_curves.keys()).index(st)*0.25 for i in x], monthly.values, 
               width=0.25, label=st, color=colors[st], alpha=0.8)
    
    ax.set_title('Monthly Returns by Strategy', fontsize=14, fontweight='bold')
    ax.set_xlabel('Month')
    ax.set_ylabel('Return (%)')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
    
    output_file2 = f'{output_dir}/backtest_monthly_{args.days}d_{timestamp}.png'
    plt.savefig(output_file2, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"✓ 月度收益图表已保存: {output_file2}")
    
    plt.close()
    print("\n✅ 可视化完成！")


if __name__ == "__main__":
    main()
