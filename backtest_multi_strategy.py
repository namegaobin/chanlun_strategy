#!/usr/bin/env python3
"""
BTC 多策略回测脚本

使用最近3个月真实BTC数据，回测三套独立策略
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import warnings
warnings.filterwarnings('ignore')

# 配置代理
PROXY = 'http://127.0.0.1:11090'
os.environ['https_proxy'] = PROXY

# 导入模块
from src.chanlun_structure_v2 import ChanLunStructureAnalyzerV2
from src.signal_detector import SignalDetector, SignalType
from src.multi_strategy_config import StrategyConfigManager


def fetch_btc_data(days: int = 180, interval: str = '5m') -> pd.DataFrame:
    """获取BTC历史数据"""
    print(f"\n[1] 获取BTC最近 {days} 天数据...")
    
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    all_data = []
    current_end = end_time
    
    while current_end > start_time:
        url = f'https://api.binance.com/api/v3/klines'
        params = {
            'symbol': 'BTCUSDT',
            'interval': interval,
            'limit': 1000,
            'endTime': current_end
        }
        
        try:
            resp = requests.get(url, params=params, timeout=30, proxies={'https': PROXY})
            data = resp.json()
            
            if not data:
                break
            
            all_data = data + all_data
            current_end = data[0][0] - 1
            
            print(f"   已获取 {len(all_data)} 条K线...", end='\r')
            
        except Exception as e:
            print(f"   获取数据错误: {e}")
            break
    
    # 转换为DataFrame
    df = pd.DataFrame(all_data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    
    # 过滤时间范围
    df = df[df['timestamp'] >= start_time]
    
    print(f"\n   ✓ 获取成功: {len(df)} 根K线")
    print(f"   ✓ 时间范围: {df['date'].min()} ~ {df['date'].max()}")
    
    return df[['date', 'open', 'high', 'low', 'close', 'volume']]


def analyze_chanlun(df: pd.DataFrame) -> dict:
    """缠论结构分析"""
    print(f"\n[2] 缠论结构分析...")
    
    analyzer = ChanLunStructureAnalyzerV2(df)
    result = analyzer.analyze()
    
    print(f"   ✓ 处理后K线: {len(result['df_processed'])} 根")
    print(f"   ✓ 识别笔: {len(result['bi_list'])} 条")
    print(f"   ✓ 识别中枢: {len(result['zhongshu_list'])} 个")
    
    return result


def detect_signals(df: pd.DataFrame, bi_list: list, zs_list: list) -> list:
    """检测买卖点信号"""
    print(f"\n[3] 检测买卖点信号...")
    
    detector = SignalDetector()
    signals = detector.detect_all_signals(df, bi_list, zs_list)
    
    # 按类型分组统计
    signal_counts = {}
    for sig in signals:
        sig_type = sig.signal_type.value
        signal_counts[sig_type] = signal_counts.get(sig_type, 0) + 1
    
    print(f"   ✓ 检测到 {len(signals)} 个信号")
    for sig_type, count in sorted(signal_counts.items()):
        print(f"     - {sig_type}: {count} 个")
    
    return signals


def backtest_strategy(df: pd.DataFrame, signals: list, strategy_type: str, config: dict) -> dict:
    """回测单个策略"""
    trades = []
    max_profit_trade = 0
    max_loss_trade = 0
    
    # 筛选该策略对应的信号
    signal_type_map = {
        'TYPE_1': ['buy_1', 'sell_1'],
        'TYPE_2': ['buy_2', 'sell_2'],
        'TYPE_3': ['buy_3', 'sell_3']
    }
    
    allowed_signals = signal_type_map.get(strategy_type, [])
    filtered_signals = [s for s in signals if s.signal_type.value in allowed_signals]
    
    # 进一步筛选置信度
    min_conf = config.get('confidence_threshold', 0.6) * 100
    filtered_signals = [s for s in filtered_signals if s.confidence >= min_conf]
    
    for signal in filtered_signals:
        # 入场
        entry_idx = signal.index
        entry_price = signal.price
        signal_type = signal.signal_type.value
        
        if entry_idx >= len(df) - 1:
            continue
        
        # 止损止盈参数
        stop_loss_pct = config.get('stop_loss_ratio', 0.02) * 100
        take_profit_pct = config.get('take_profit_ratio', 0.05) * 100
        max_hold_bars = int(config.get('max_holding_hours', 24) * 12)  # 5分钟K线，每小时12根
        position_size = config.get('position_size', 0.1)
        
        # 买卖方向
        is_buy = signal_type.startswith('buy')
        
        if is_buy:
            stop_loss = entry_price * (1 - stop_loss_pct / 100)
            take_profit = entry_price * (1 + take_profit_pct / 100)
        else:
            stop_loss = entry_price * (1 + stop_loss_pct / 100)
            take_profit = entry_price * (1 - take_profit_pct / 100)
        
        # 模拟持仓
        exit_price = None
        exit_reason = None
        hold_bars = 0
        
        for i in range(entry_idx + 1, min(entry_idx + max_hold_bars + 1, len(df))):
            hold_bars = i - entry_idx
            high = df.iloc[i]['high']
            low = df.iloc[i]['low']
            
            if is_buy:
                if low <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = 'stop_loss'
                    break
                if high >= take_profit:
                    exit_price = take_profit
                    exit_reason = 'take_profit'
                    break
            else:
                if high >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = 'stop_loss'
                    break
                if low <= take_profit:
                    exit_price = take_profit
                    exit_reason = 'take_profit'
                    break
        
        # 超时平仓
        if exit_price is None:
            exit_price = df.iloc[min(entry_idx + max_hold_bars, len(df) - 1)]['close']
            exit_reason = 'timeout'
        
        # 计算收益
        if is_buy:
            profit_pct = (exit_price - entry_price) / entry_price * 100
        else:
            profit_pct = (entry_price - exit_price) / entry_price * 100
        
        # 记录最大浮盈浮亏
        if profit_pct > max_profit_trade:
            max_profit_trade = profit_pct
        if profit_pct < max_loss_trade:
            max_loss_trade = profit_pct
        
        trades.append({
            'signal_type': signal_type,
            'entry_time': df.iloc[entry_idx]['date'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'hold_bars': hold_bars,
            'hold_hours': hold_bars / 12,
            'profit_pct': profit_pct,
            'position_size': position_size
        })
    
    # 计算统计指标
    if not trades:
        return {
            'strategy_type': strategy_type,
            'total_trades': 0,
            'win_rate': 0,
            'total_return': 0,
            'actual_return': 0,
            'annual_return': 0,
            'max_drawdown': 0,
            'max_profit': 0,
            'max_loss': 0,
            'avg_hold_hours': 0,
            'profit_loss_ratio': 0,
            'sharpe': 0
        }
    
    wins = [t for t in trades if t['profit_pct'] > 0]
    losses = [t for t in trades if t['profit_pct'] <= 0]
    
    # 实际收益率（考虑仓位）
    actual_return = sum(t['profit_pct'] * t['position_size'] for t in trades)
    
    # 年化收益率
    days = (df['date'].max() - df['date'].min()).days
    annual_return = actual_return * (365 / days) if days > 0 else 0
    
    total_return = actual_return  # 别名
    
    # 计算最大回撤
    cumulative = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cumulative += t['profit_pct'] * t['position_size']
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    
    avg_win = np.mean([t['profit_pct'] for t in wins]) if wins else 0
    avg_loss = abs(np.mean([t['profit_pct'] for t in losses])) if losses else 0
    pl_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    # Sharpe比率
    returns = [t['profit_pct'] for t in trades]
    if len(returns) > 1:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 / (days / len(trades))) if np.std(returns) > 0 else 0
    else:
        sharpe = 0
    
    return {
        'strategy_type': strategy_type,
        'total_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(trades) * 100 if trades else 0,
        'total_return': total_return,
        'actual_return': actual_return,
        'annual_return': annual_return,
        'max_drawdown': max_dd,
        'max_profit': max_profit_trade,
        'max_loss': max_loss_trade,
        'avg_hold_hours': np.mean([t['hold_hours'] for t in trades]),
        'profit_loss_ratio': pl_ratio,
        'sharpe': sharpe,
        'trades': trades
    }


def generate_report(df: pd.DataFrame, signals: list, results: list):
    """生成回测报告"""
    
    days = (df['date'].max() - df['date'].min()).days
    
    print("\n" + "=" * 100)
    print("BTC 多策略优化回测报告")
    print("=" * 100)
    
    # 数据概览
    print(f"\n【数据概览】")
    print(f"  时间范围: {df['date'].min().strftime('%Y-%m-%d %H:%M')} ~ {df['date'].max().strftime('%Y-%m-%d %H:%M')}")
    print(f"  数据天数: {days} 天")
    print(f"  K线数量: {len(df)} 根")
    print(f"  信号总数: {len(signals)} 个")
    
    # 策略对比
    print(f"\n【策略对比汇总】")
    print(f"{'策略':<10} {'交易次数':<8} {'胜率':<8} {'实际收益':<10} {'年化收益':<10} {'最大回撤':<8} {'最大浮盈':<8} {'最大浮亏':<8} {'盈亏比':<6}")
    print("-" * 100)
    
    for r in results:
        if r['total_trades'] > 0:
            print(f"{r['strategy_type']:<10} {r['total_trades']:<8} {r['win_rate']:.1f}%{'':<3} "
                  f"{r['actual_return']:+.2f}%{'':<4} {r['annual_return']:+.2f}%{'':<4} "
                  f"{r['max_drawdown']:.2f}%{'':<3} +{r['max_profit']:.2f}%{'':<3} {r['max_loss']:.2f}%{'':<3} {r['profit_loss_ratio']:.2f}")
    
    # 详细分析
    print(f"\n【详细分析】")
    for r in results:
        print(f"\n{'='*70}")
        print(f"  {r['strategy_type']}")
        print(f"{'='*70}")
        print(f"  交易次数: {r['total_trades']}")
        print(f"  盈利次数: {r.get('wins', 0)}")
        print(f"  亏损次数: {r.get('losses', 0)}")
        print(f"  胜率: {r['win_rate']:.1f}%")
        print(f"  实际收益率: {r['actual_return']:+.2f}%")
        print(f"  年化收益率: {r['annual_return']:+.2f}%")
        print(f"  最大回撤: {r['max_drawdown']:.2f}%")
        print(f"  最大浮盈: +{r['max_profit']:.2f}%")
        print(f"  最大浮亏: {r['max_loss']:.2f}%")
        print(f"  平均持仓: {r['avg_hold_hours']:.1f} 小时")
        print(f"  盈亏比: {r['profit_loss_ratio']:.2f}")
        print(f"  Sharpe比率: {r.get('sharpe', 0):.2f}")
        
        # 出场原因分布
        if r.get('trades'):
            exit_reasons = {}
            for t in r['trades']:
                reason = t['exit_reason']
                exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
            print(f"  出场原因: {exit_reasons}")
    
    # 结论
    print(f"\n{'='*100}")
    print(f"【结论与建议】")
    print(f"{'='*100}")
    
    valid_results = [r for r in results if r['total_trades'] > 0]
    
    if valid_results:
        best_by_return = max(valid_results, key=lambda x: x['annual_return'])
        best_by_winrate = max(valid_results, key=lambda x: x['win_rate'])
        best_by_sharpe = max(valid_results, key=lambda x: x.get('sharpe', 0))
        
        print(f"\n  📊 年化收益最高: {best_by_return['strategy_type']} ({best_by_return['annual_return']:+.2f}%)")
        print(f"  📊 胜率最高: {best_by_winrate['strategy_type']} ({best_by_winrate['win_rate']:.1f}%)")
        print(f"  📊 Sharpe最高: {best_by_sharpe['strategy_type']} ({best_by_sharpe.get('sharpe', 0):.2f})")
        
        print(f"\n  ⚠️ 风险提示:")
        print(f"     - 回测结果不代表未来表现")
        print(f"     - 建议用更多数据验证策略稳定性")
        print(f"     - 实盘前请进行模拟交易")
    
    print("\n" + "=" * 100)


def main():
    """主函数"""
    # 1. 获取数据
    df = fetch_btc_data(days=90, interval='5m')
    
    # 2. 缠论分析
    result = analyze_chanlun(df)
    
    # 3. 检测信号
    signals = detect_signals(df, result['bi_list'], result['zhongshu_list'])
    
    # 4. 三套策略回测
    print(f"\n[4] 三套策略回测...")
    config_manager = StrategyConfigManager()
    
    results = []
    for strategy_type in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
        config = config_manager.get_config(strategy_type)
        if config is None:
            print(f"   ⚠️ {strategy_type} 配置不存在，跳过")
            continue
        
        # 转换配置格式
        config_dict = {
            'confidence_threshold': config.confidence_threshold,
            'stop_loss_ratio': config.stop_loss_ratio,
            'take_profit_ratio': config.take_profit_ratio,
            'position_size': config.position_size,
            'max_holding_hours': config.max_holding_hours
        }
        
        r = backtest_strategy(df, signals, strategy_type, config_dict)
        results.append(r)
        print(f"   ✓ {strategy_type}: {r['total_trades']} 笔交易, 胜率 {r['win_rate']:.1f}%")
    
    # 5. 生成报告
    generate_report(df, signals, results)
    
    return results


if __name__ == "__main__":
    main()
