#!/usr/bin/env python3
"""BTC 多策略回测脚本（修复版）"""
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

from src.chanlun_structure_v2 import process_inclusion, detect_all_fractals, build_bi_from_fractals, detect_all_zhongshu, Direction
from src.strategy_selector import SignalType, Signal
from src.multi_strategy_config import StrategyConfigManager
from src.optimized_type3_detector import OptimizedType3Detector


class SimpleSignalDetector:
    def _get_trend(self, df, index, lookback=10):
        """判断当前趋势：通过最近N根K线的收盘价判断"""
        if index < lookback:
            lookback = index
        if lookback < 3:
            return 'down'  # 数据不足，默认下跌
        
        recent_closes = df.iloc[index-lookback:index]['close'].values
        # 简单判断：收盘价总体上涨=上涨趋势，下跌=下跌趋势
        first_half = np.mean(recent_closes[:lookback//2])
        second_half = np.mean(recent_closes[lookback//2:])
        
        if second_half > first_half:
            return 'up'
        else:
            return 'down'
    
    def _has_divergence(self, zs, bi_list):
        """背驰判断：离开段力度 < 进入段力度 * 0.4"""
        if zs.enter_bi is None or zs.exit_bi is None:
            return False
        
        # 计算进入段和离开段的力度（用幅度 * 成交量 或 简单幅度）
        # 这里用笔的幅度来衡量力度
        enter_power = abs(zs.enter_bi.end_price - zs.enter_bi.start_price)
        exit_power = abs(zs.exit_bi.end_price - zs.exit_bi.start_price)
        
        # 背驰条件：离开段力度 < 进入段力度 * 0.4
        return exit_power < enter_power * 0.4
    
    def _confirm_signal(self, df, index, signal_type, confirm_bars=3):
        """信号确认：要求连续N根K线验证"""
        if index + confirm_bars >= len(df):
            return False
        
        current_price = df.iloc[index]['close']
        
        if signal_type == 'buy_1':
            # 买入信号：要求后续N根K线收盘价逐步走高或至少不创新低
            for i in range(1, confirm_bars + 1):
                if df.iloc[index + i]['close'] < current_price:
                    return False
                current_price = df.iloc[index + i]['close']
            return True
        else:  # sell_1
            # 卖出信号：要求后续N根K线收盘价逐步走低或至少不创新高
            for i in range(1, confirm_bars + 1):
                if df.iloc[index + i]['close'] > current_price:
                    return False
                current_price = df.iloc[index + i]['close']
            return True

    def detect_all_signals(self, df, bi_list, zs_list):
        signals = []
        if not bi_list or not zs_list:
            return signals
        
        # 获取枚举值
        from src.chanlun_structure_v2 import Direction
        DIR_UP = Direction.UP
        DIR_DOWN = Direction.DOWN
        
        # 使用优化版TYPE_3检测器
        type3_detector = OptimizedType3Detector(min_leave_ratio=0.5, max_pullback_ratio=0.5, min_zs_age=3, use_trend_filter=True)
        type3_signals = type3_detector.detect_all(bi_list, zs_list, df)
        for s in type3_signals:
            if s.signal_type == 'buy_3':
                signals.append(Signal(SignalType.BUY_3, s.confidence, s.price, df.iloc[s.index]['date'], {}, s.index))
            elif s.signal_type == 'sell_3':
                signals.append(Signal(SignalType.SELL_3, s.confidence, s.price, df.iloc[s.index]['date'], {}, s.index))
        
        # TYPE_1 改进版：添加趋势过滤 + 背驰判断 + 信号确认
        for i, bi in enumerate(bi_list):
            # 获取当前趋势
            current_trend = self._get_trend(df, bi.end_index, lookback=10)
            
            # 第一类买点：向下笔在中枢之后（趋势背驰）
            # 条件1: 下跌趋势中
            # 条件2: 向下笔突破中枢
            # 条件3: 背驰判断（离开段力度 < 进入段力度 * 0.4）
            # 条件4: 信号确认（连续3根K线验证）
            if bi.direction == DIR_DOWN and current_trend == 'down':
                for zs in zs_list:
                    if bi.end_index > zs.end_index:
                        # 背驰判断
                        if self._has_divergence(zs, bi_list):
                            # 信号确认
                            if self._confirm_signal(df, bi.end_index, 'buy_1', confirm_bars=3):
                                signals.append(Signal(SignalType.BUY_1, 85.0, bi.low, df.iloc[bi.end_index]['date'], {'bi_idx': i, 'zs_idx': zs_list.index(zs), 'divergence': True}, bi.end_index))
                                break
            
            # 第一类卖点：向上笔在中枢之后
            # 条件1: 上涨趋势中
            # 条件2: 向上笔突破中枢
            # 条件3: 背驰判断
            # 条件4: 信号确认
            if bi.direction == DIR_UP and current_trend == 'up':
                for zs in zs_list:
                    if bi.end_index > zs.end_index:
                        if self._has_divergence(zs, bi_list):
                            if self._confirm_signal(df, bi.end_index, 'sell_1', confirm_bars=3):
                                signals.append(Signal(SignalType.SELL_1, 85.0, bi.high, df.iloc[bi.end_index]['date'], {'bi_idx': i, 'zs_idx': zs_list.index(zs), 'divergence': True}, bi.end_index))
                                break
        
        # 第二类买点：一买后第一个向上笔，需满足以下条件：
        # 1. 二买价格 > 对应一买价格（一买有效性验证）
        # 2. 一买后价格确实上涨（验证一买不是假的一买）
        buy1_signals = [s for s in signals if s.signal_type == SignalType.BUY_1]
        for sig in buy1_signals:
            # 找一买后所有向上笔
            up_bis = [bi for bi in bi_list if bi.direction == DIR_UP and bi.start_index > sig.index]
            
            if not up_bis:
                continue
            
            first_up_bi = up_bis[0]
            
            # 放宽条件1：二买价格略高于一买价格（允许2%误差）
            if first_up_bi.low < sig.price * 0.98:
                continue
            
            # 放宽条件2：验证一买后价格上涨（允许5%误差）
            if first_up_bi.high < sig.price * 1.02:
                continue
            
            # 二买价格就是向上笔的低点
            buy2_price = first_up_bi.low
            
            signals.append(Signal(SignalType.BUY_2, 60.0, buy2_price, df.iloc[first_up_bi.start_index]['date'], 
                                  {'related_buy1': sig.index, 'buy1_price': sig.price, 'up_bi_high': first_up_bi.high}, 
                                  first_up_bi.start_index))
        
        # 第二类买点独立检测：基于中枢的回抽
        # 条件：价格回调到中枢附近（ZG或ZD附近），形成支撑
        for zs in zs_list:
            # 向上中枢：回调到ZD附近获得支撑
            if zs.zg > zs.zd:  # 向上中枢
                # 找价格在ZD~ZG之间的笔（回抽笔）
                for bi in bi_list:
                    if bi.direction == DIR_DOWN and bi.low > zs.zd and bi.low < zs.zg:
                        # 回抽笔后上涨
                        next_up_bis = [b for b in bi_list if b.direction == DIR_UP and b.start_index > bi.end_index]
                        if next_up_bis and next_up_bis[0].high > bi.high:
                            # 产生二买信号
                            signals.append(Signal(SignalType.BUY_2, 55.0, next_up_bis[0].low, 
                                                  df.iloc[next_up_bis[0].start_index]['date'],
                                                  {'zs_idx': zs_list.index(zs), 'pullback_bi': bi.end_index},
                                                  next_up_bis[0].start_index))
        
        signals.sort(key=lambda s: s.index)
        
        signals.sort(key=lambda s: s.index)
        return signals

    def detect_only_type1_type2(self, df, bi_list, zs_list):
        """只检测TYPE_1和TYPE_2（用于对比）"""
        signals = []
        if not bi_list or not zs_list:
            return signals
        
        DIR_UP = Direction.UP
        DIR_DOWN = Direction.DOWN
        
        for i, bi in enumerate(bi_list):
            # 第一类买点：向下笔在中枢之后
            if bi.direction == DIR_DOWN:
                for zs in zs_list:
                    if bi.end_index > zs.end_index:
                        signals.append(Signal(SignalType.BUY_1, 75.0, bi.low, df.iloc[bi.end_index]['date'], {'bi_idx': i}, bi.end_index))
                        break
            
            # 第一类卖点：向上笔在中枢之后
            if bi.direction == DIR_UP:
                for zs in zs_list:
                    if bi.end_index > zs.end_index:
                        signals.append(Signal(SignalType.SELL_1, 75.0, bi.high, df.iloc[bi.end_index]['date'], {'bi_idx': i}, bi.end_index))
                        break
        
        # 第二类买点：一买后的向上笔
        buy1_signals = [s for s in signals if s.signal_type == SignalType.BUY_1]
        for sig in buy1_signals:
            for bi in bi_list:
                if bi.direction == DIR_UP and bi.start_index > sig.index:
                    signals.append(Signal(SignalType.BUY_2, 70.0, bi.low, df.iloc[bi.start_index]['date'], {}, bi.start_index))
                    break
        
        signals.sort(key=lambda s: s.index)
        return signals


def fetch_btc_data(days=90, start_date=None, end_date=None):
    print(f"\n[1] 获取BTC数据...")
    
    # 支持日期范围
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        start_time = int(start_dt.timestamp() * 1000)
        end_time = int(end_dt.timestamp() * 1000) + 86400000  # 加一天
        days = (end_dt - start_dt).days
    else:
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
    print(f"\n   ✓ 获取成功: {len(df)} 根K线, 时间范围: {df['date'].min()} ~ {df['date'].max()}")
    return df[['date', 'open', 'high', 'low', 'close', 'volume']]


def backtest_strategy(df, signals, strategy_type, config):
    signal_map = {'TYPE_1': [SignalType.BUY_1, SignalType.SELL_1], 'TYPE_2': [SignalType.BUY_2], 'TYPE_3': [SignalType.BUY_3, SignalType.SELL_3]}
    filtered = [s for s in signals if s.signal_type in signal_map.get(strategy_type, []) and s.confidence >= config.get('confidence_threshold', 0.6) * 100]
    
    trades = []
    for sig in filtered:
        if sig.index >= len(df) - 1: continue
        is_buy = sig.signal_type in [SignalType.BUY_1, SignalType.BUY_2, SignalType.BUY_3]
        stop_pct, take_pct = config.get('stop_loss_ratio', 0.02) * 100, config.get('take_profit_ratio', 0.05) * 100
        max_hold = int(config.get('max_holding_hours', 24) * 12)
        pos = config.get('position_size', 0.1)
        
        sl = sig.price * (1 - stop_pct/100) if is_buy else sig.price * (1 + stop_pct/100)
        tp = sig.price * (1 + take_pct/100) if is_buy else sig.price * (1 - take_pct/100)
        
        exit_price, reason, exit_idx = None, None, None
        for i in range(sig.index + 1, min(sig.index + max_hold + 1, len(df))):
            if is_buy:
                if df.iloc[i]['low'] <= sl: exit_price, reason, exit_idx = sl, 'stop_loss', i; break
                if df.iloc[i]['high'] >= tp: exit_price, reason, exit_idx = tp, 'take_profit', i; break
            else:
                if df.iloc[i]['high'] >= sl: exit_price, reason, exit_idx = sl, 'stop_loss', i; break
                if df.iloc[i]['low'] <= tp: exit_price, reason, exit_idx = tp, 'take_profit', i; break
        
        if not exit_price:
            exit_idx = min(sig.index + max_hold, len(df) - 1)
            exit_price = df.iloc[exit_idx]['close']
            reason = 'timeout'
        
        pnl = (exit_price - sig.price) / sig.price * 100 if is_buy else (sig.price - exit_price) / sig.price * 100
        hold_bars = exit_idx - sig.index
        
        trades.append({
            'signal_type': sig.signal_type.value,
            'entry_time': str(df.iloc[sig.index]['date']),
            'entry_price': sig.price,
            'exit_time': str(df.iloc[exit_idx]['date']),
            'exit_price': exit_price,
            'exit_reason': reason,
            'hold_bars': hold_bars,
            'hold_hours': hold_bars / 12,
            'pnl_pct': pnl,
            'position_size': pos,
            'pnl_actual': pnl * pos
        })
    
    if not trades:
        return {'strategy': strategy_type, 'trades': 0, 'win_rate': 0, 'return': 0, 'annual': 0, 'trade_details': []}
    
    wins = [t for t in trades if t['pnl_pct'] > 0]
    total_ret = sum(t['pnl_actual'] for t in trades)
    days = (df['date'].max() - df['date'].min()).days
    return {
        'strategy': strategy_type,
        'trades': len(trades),
        'wins': len(wins),
        'win_rate': len(wins) / len(trades) * 100,
        'return': total_ret,
        'annual': total_ret * (365 / days) if days > 0 else 0,
        'max_profit': max(t['pnl_pct'] for t in trades),
        'max_loss': min(t['pnl_pct'] for t in trades),
        'trade_details': trades
    }


def main():
    import json
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default='2026-01-01')
    parser.add_argument('--end', default='2026-04-29')
    args, _ = parser.parse_known_args()
    
    from datetime import datetime
    start_dt = datetime.strptime(args.start, '%Y-%m-%d')
    end_dt = datetime.strptime(args.end, '%Y-%m-%d')
    days = (end_dt - start_dt).days + 10
    
    df = fetch_btc_data(start_date=args.start, end_date=args.end)
    
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
    
    print("\n[4] 三套策略回测...")
    config_mgr = StrategyConfigManager()
    results = []
    
    for st in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
        cfg = config_mgr.get_config(st)
        if cfg is None:
            print(f"   ⚠️ {st} 配置不存在")
            continue
        cfg_dict = {'confidence_threshold': cfg.confidence_threshold, 'stop_loss_ratio': cfg.stop_loss_ratio,
                    'take_profit_ratio': cfg.take_profit_ratio, 'position_size': cfg.position_size,
                    'max_holding_hours': cfg.max_holding_hours}
        r = backtest_strategy(df, signals, st, cfg_dict)
        results.append(r)
        print(f"   ✓ {st}: {r['trades']} 笔, 胜率 {r['win_rate']:.1f}%, 收益 {r['return']:+.2f}%")
    
    # 输出汇总报告
    print("\n" + "=" * 80)
    print("BTC 多策略回测报告")
    print("=" * 80)
    print(f"\n{'策略':<10} {'交易':<6} {'胜率':<8} {'收益':<10} {'年化':<10} {'最大盈利':<10} {'最大亏损':<10}")
    print("-" * 80)
    for r in results:
        if r['trades'] > 0:
            print(f"{r['strategy']:<10} {r['trades']:<6} {r['win_rate']:.1f}%{'':<3} {r['return']:+.2f}%{'':<4} {r['annual']:+.2f}%{'':<4} +{r['max_profit']:.2f}%{'':<5} {r['max_loss']:.2f}%")
    print("=" * 80)
    
    # 保存交易明细到文件
    output_dir = 'output'
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    detail_file = f'{output_dir}/backtest_trades_{timestamp}.csv'
    summary_file = f'{output_dir}/backtest_summary_{timestamp}.json'
    
    # 保存交易明细CSV
    all_trades = []
    for r in results:
        for t in r.get('trade_details', []):
            t['strategy'] = r['strategy']
            all_trades.append(t)
    
    if all_trades:
        import csv
        with open(detail_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['strategy', 'signal_type', 'entry_time', 'entry_price', 
                                                      'exit_time', 'exit_price', 'exit_reason', 
                                                      'hold_bars', 'hold_hours', 'pnl_pct', 'position_size', 'pnl_actual'])
            writer.writeheader()
            writer.writerows(all_trades)
        print(f"\n✓ 交易明细已保存: {detail_file}")
    
    # 保存汇总报告JSON
    summary = {
        'timestamp': timestamp,
        'data_range': f"{df['date'].min()} ~ {df['date'].max()}",
        'klines': len(df),
        'bi_count': len(bi_list),
        'zs_count': len(zs_list),
        'signal_count': len(signals),
        'strategies': {r['strategy']: {
            'trades': r['trades'],
            'wins': r['wins'],
            'win_rate': round(r['win_rate'], 2),
            'total_return': round(r['return'], 4),
            'annual_return': round(r['annual'], 4),
            'max_profit': round(r['max_profit'], 2) if r['trades'] > 0 else 0,
            'max_loss': round(r['max_loss'], 2) if r['trades'] > 0 else 0
        } for r in results}
    }
    
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"✓ 汇总报告已保存: {summary_file}")
    
    # 打印前10笔交易明细
    print("\n" + "=" * 100)
    print("前10笔交易明细")
    print("=" * 100)
    print(f"{'策略':<8} {'信号类型':<10} {'入场时间':<20} {'入场价':<12} {'出场价':<12} {'收益%':<8} {'持仓h':<8} {'原因':<10}")
    print("-" * 100)
    for t in all_trades[:10]:
        print(f"{t['strategy']:<8} {t['signal_type']:<10} {t['entry_time'][:19]:<20} {t['entry_price']:<12.2f} {t['exit_price']:<12.2f} {t['pnl_pct']:+.2f}%{'':<3} {t['hold_hours']:<8.1f} {t['exit_reason']:<10}")
    print("...")
    print(f"共 {len(all_trades)} 笔交易")


if __name__ == "__main__":
    main()
