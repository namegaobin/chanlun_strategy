#!/usr/bin/env python3
"""
BTC 多策略优化与回测脚本

对三套策略进行参数网格搜索，找出最优参数组合
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import warnings
import json
from itertools import product
from typing import Dict, List, Any, Tuple
warnings.filterwarnings('ignore')

# 配置代理
PROXY = 'http://127.0.0.1:11090'
os.environ['https_proxy'] = PROXY

# 导入模块
from src.chanlun_structure_v2 import ChanLunStructureAnalyzerV2
from src.signal_detector import SignalDetector, SignalType
from src.multi_strategy_config import StrategyConfigManager


# ============================================================================
# 数据获取
# ============================================================================

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


# ============================================================================
# 缠论分析
# ============================================================================

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


# ============================================================================
# 回测引擎
# ============================================================================

def backtest_strategy(df: pd.DataFrame, signals: list, strategy_type: str, 
                      config: dict, require_divergence: bool = False) -> dict:
    """回测单个策略"""
    trades = []
    
    # 筛选该策略对应的信号
    signal_type_map = {
        'TYPE_1': ['buy_1', 'sell_1'],
        'TYPE_2': ['buy_2', 'sell_2'],
        'TYPE_3': ['buy_3', 'sell_3']
    }
    
    allowed_signals = signal_type_map.get(strategy_type, [])
    filtered_signals = [s for s in signals if s.signal_type.value in allowed_signals]
    
    # 筛选置信度
    min_conf = config.get('confidence_threshold', 0.6) * 100
    filtered_signals = [s for s in filtered_signals if s.confidence >= min_conf]
    
    # TYPE_1 背驰确认
    if require_divergence and strategy_type == 'TYPE_1':
        filtered_signals = [s for s in filtered_signals 
                          if s.metadata and s.metadata.get('macd_ratio', 1.0) < 0.8]
    
    for signal in filtered_signals:
        entry_idx = signal.index
        entry_price = signal.price
        signal_type = signal.signal_type.value
        
        if entry_idx >= len(df) - 1:
            continue
        
        stop_loss_pct = config.get('stop_loss_ratio', 0.02) * 100
        take_profit_pct = config.get('take_profit_ratio', 0.05) * 100
        max_hold_bars = int(config.get('max_holding_hours', 24) * 12)
        position_size = config.get('position_size', 0.1)
        
        is_buy = signal_type.startswith('buy')
        
        if is_buy:
            stop_loss = entry_price * (1 - stop_loss_pct / 100)
            take_profit = entry_price * (1 + take_profit_pct / 100)
        else:
            stop_loss = entry_price * (1 + stop_loss_pct / 100)
            take_profit = entry_price * (1 - take_profit_pct / 100)
        
        exit_price = None
        exit_reason = None
        hold_bars = 0
        max_profit = 0
        max_loss = 0
        
        for i in range(entry_idx + 1, min(entry_idx + max_hold_bars + 1, len(df))):
            hold_bars = i - entry_idx
            high = df.iloc[i]['high']
            low = df.iloc[i]['low']
            
            if is_buy:
                current_profit = (high - entry_price) / entry_price * 100
                current_loss = (entry_price - low) / entry_price * 100
                max_profit = max(max_profit, current_profit)
                max_loss = max(max_loss, current_loss)
                
                if low <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = 'stop_loss'
                    break
                if high >= take_profit:
                    exit_price = take_profit
                    exit_reason = 'take_profit'
                    break
            else:
                current_profit = (entry_price - low) / entry_price * 100
                current_loss = (high - entry_price) / entry_price * 100
                max_profit = max(max_profit, current_profit)
                max_loss = max(max_loss, current_loss)
                
                if high >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = 'stop_loss'
                    break
                if low <= take_profit:
                    exit_price = take_profit
                    exit_reason = 'take_profit'
                    break
        
        if exit_price is None:
            exit_price = df.iloc[min(entry_idx + max_hold_bars, len(df) - 1)]['close']
            exit_reason = 'timeout'
        
        if is_buy:
            profit_pct = (exit_price - entry_price) / entry_price * 100
        else:
            profit_pct = (entry_price - exit_price) / entry_price * 100
        
        trades.append({
            'signal_type': signal_type,
            'entry_time': df.iloc[entry_idx]['date'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'hold_bars': hold_bars,
            'hold_hours': hold_bars / 12,
            'profit_pct': profit_pct,
            'position_size': position_size,
            'max_profit': max_profit,
            'max_loss': max_loss
        })
    
    return calculate_metrics(trades, strategy_type, config)


def calculate_metrics(trades: list, strategy_type: str, config: dict) -> dict:
    """计算完整回测指标"""
    if not trades:
        return {
            'strategy_type': strategy_type,
            'config': config,
            'total_trades': 0,
            'win_rate': 0,
            'total_return': 0,
            'annualized_return': 0,
            'max_drawdown': 0,
            'max_profit': 0,
            'max_loss': 0,
            'avg_hold_hours': 0,
            'profit_loss_ratio': 0,
            'sharpe_ratio': 0
        }
    
    wins = [t for t in trades if t['profit_pct'] > 0]
    losses = [t for t in trades if t['profit_pct'] <= 0]
    
    total_return = sum(t['profit_pct'] * t['position_size'] for t in trades)
    days = 180
    annualized_return = total_return * (365 / days)
    
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
    
    max_profit = max([t['max_profit'] for t in trades]) if trades else 0
    max_loss = max([t['max_loss'] for t in trades]) if trades else 0
    
    avg_win = np.mean([t['profit_pct'] for t in wins]) if wins else 0
    avg_loss = abs(np.mean([t['profit_pct'] for t in losses])) if losses else 0
    pl_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    
    if len(trades) > 1:
        returns = [t['profit_pct'] * t['position_size'] for t in trades]
        std = np.std(returns)
        sharpe = (total_return - 0.02) / std if std > 0 else 0
    else:
        sharpe = 0
    
    return {
        'strategy_type': strategy_type,
        'config': config,
        'total_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(trades) * 100 if trades else 0,
        'total_return': total_return,
        'annualized_return': annualized_return,
        'max_drawdown': max_dd,
        'max_profit': max_profit,
        'max_loss': max_loss,
        'avg_hold_hours': np.mean([t['hold_hours'] for t in trades]),
        'profit_loss_ratio': pl_ratio,
        'sharpe_ratio': sharpe,
        'trades': trades
    }


# ============================================================================
# 参数优化
# ============================================================================

def optimize_type1(df: pd.DataFrame, signals: list) -> dict:
    """TYPE_1 策略参数优化"""
    print("\n[4] TYPE_1 策略优化...")
    
    confidence_thresholds = [0.75, 0.80, 0.85]
    stop_loss_ratios = [0.015, 0.01, 0.02]
    take_profit_ratios = [0.03, 0.02, 0.04]
    require_divergence_options = [True, False]
    
    best_result = None
    best_score = -float('inf')
    all_results = []
    
    total = len(confidence_thresholds) * len(stop_loss_ratios) * len(take_profit_ratios) * len(require_divergence_options)
    
    count = 0
    for conf, sl, tp, div in product(confidence_thresholds, stop_loss_ratios, take_profit_ratios, require_divergence_options):
        count += 1
        config = {
            'confidence_threshold': conf,
            'stop_loss_ratio': sl,
            'take_profit_ratio': tp,
            'position_size': 0.05,
            'max_holding_hours': 24
        }
        
        result = backtest_strategy(df, signals, 'TYPE_1', config, require_divergence=div)
        result['require_divergence'] = div
        all_results.append(result)
        
        if result['total_trades'] >= 5:
            score = result['total_return'] * (1 - result['max_drawdown']/100) * result['win_rate']/50
        else:
            score = -1000
        
        if score > best_score:
            best_score = score
            best_result = result
        
        print(f"   [{count}/{total}] conf={conf}, sl={sl*100:.1f}%, tp={tp*100:.1f}%, div={div} -> "
              f"trades={result['total_trades']}, win={result['win_rate']:.1f}%, ret={result['total_return']:+.2f}%", end='\r')
    
    print(f"\n   ✓ TYPE_1 优化完成，最优得分: {best_score:.2f}")
    return {'best_result': best_result, 'all_results': all_results}


def optimize_type2(df: pd.DataFrame, signals: list) -> dict:
    """TYPE_2 策略参数优化"""
    print("\n[5] TYPE_2 策略优化...")
    
    confidence_thresholds = [0.60, 0.65, 0.70]
    stop_loss_ratios = [0.015, 0.02]
    take_profit_ratios = [0.04, 0.05, 0.06]
    
    best_result = None
    best_score = -float('inf')
    all_results = []
    
    total = len(confidence_thresholds) * len(stop_loss_ratios) * len(take_profit_ratios)
    
    count = 0
    for conf, sl, tp in product(confidence_thresholds, stop_loss_ratios, take_profit_ratios):
        count += 1
        config = {
            'confidence_threshold': conf,
            'stop_loss_ratio': sl,
            'take_profit_ratio': tp,
            'position_size': 0.10,
            'max_holding_hours': 36
        }
        
        result = backtest_strategy(df, signals, 'TYPE_2', config)
        all_results.append(result)
        
        if result['total_trades'] >= 3:
            score = result['total_return'] * (1 - result['max_drawdown']/100) * result['win_rate']/50
        else:
            score = -1000
        
        if score > best_score:
            best_score = score
            best_result = result
        
        print(f"   [{count}/{total}] conf={conf}, sl={sl*100:.1f}%, tp={tp*100:.1f}% -> "
              f"trades={result['total_trades']}, win={result['win_rate']:.1f}%, ret={result['total_return']:+.2f}%", end='\r')
    
    print(f"\n   ✓ TYPE_2 优化完成，最优得分: {best_score:.2f}")
    return {'best_result': best_result, 'all_results': all_results}


def optimize_type3(df: pd.DataFrame, signals: list) -> dict:
    """TYPE_3 策略参数优化"""
    print("\n[6] TYPE_3 策略优化...")
    
    position_sizes = [0.10, 0.15, 0.20]
    stop_loss_ratios = [0.02, 0.025, 0.03]
    take_profit_ratios = [0.06, 0.08, 0.10]
    
    best_result = None
    best_score = -float('inf')
    all_results = []
    
    total = len(position_sizes) * len(stop_loss_ratios) * len(take_profit_ratios)
    
    count = 0
    for pos, sl, tp in product(position_sizes, stop_loss_ratios, take_profit_ratios):
        count += 1
        config = {
            'confidence_threshold': 0.60,
            'stop_loss_ratio': sl,
            'take_profit_ratio': tp,
            'position_size': pos,
            'max_holding_hours': 60
        }
        
        result = backtest_strategy(df, signals, 'TYPE_3', config)
        all_results.append(result)
        
        if result['total_trades'] >= 5:
            score = result['total_return'] * (1 - result['max_drawdown']/100) * result['win_rate']/50
        else:
            score = -1000
        
        if score > best_score:
            best_score = score
            best_result = result
        
        print(f"   [{count}/{total}] pos={pos*100:.0f}%, sl={sl*100:.1f}%, tp={tp*100:.1f}% -> "
              f"trades={result['total_trades']}, win={result['win_rate']:.1f}%, ret={result['total_return']:+.2f}%", end='\r')
    
    print(f"\n   ✓ TYPE_3 优化完成，最优得分: {best_score:.2f}")
    return {'best_result': best_result, 'all_results': all_results}


# ============================================================================
# 报告生成
# ============================================================================

def generate_optimization_report(df: pd.DataFrame, signals: list, 
                                 opt_results: dict, baseline_results: list) -> str:
    """生成优化报告"""
    report = []
    report.append("=" * 80)
    report.append("BTC 多策略优化与回测报告")
    report.append("=" * 80)
    
    # 数据概览
    report.append("\n【数据概览】")
    report.append(f"  时间范围: {df['date'].min().strftime('%Y-%m-%d %H:%M')} ~ {df['date'].max().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"  K线数量: {len(df)} 根")
    report.append(f"  信号总数: {len(signals)} 个")
    
    # 信号分布
    signal_counts = {}
    for sig in signals:
        sig_type = sig.signal_type.value
        signal_counts[sig_type] = signal_counts.get(sig_type, 0) + 1
    report.append("  信号分布:")
    for sig_type, count in sorted(signal_counts.items()):
        report.append(f"    - {sig_type}: {count} 个")
    
    # 基线对比
    report.append("\n【基线参数回测结果（优化前）】")
    for r in baseline_results:
        report.append(f"  {r['strategy_type']}: 交易{r['total_trades']}笔, 胜率{r['win_rate']:.1f}%, 收益{r['total_return']:+.2f}%")
    
    # 各策略优化结果
    for strategy_type in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
        key = f"{strategy_type.lower()}" if strategy_type != 'TYPE_1' else 'type1'
        if strategy_type == 'TYPE_1':
            key = 'type1'
        elif strategy_type == 'TYPE_2':
            key = 'type2'
        else:
            key = 'type3'
        
        opt = opt_results.get(key, {})
        best = opt.get('best_result')
        
        if not best:
            continue
        
        report.append(f"\n【{strategy_type} 优化结果】")
        
        # 最优参数
        config = best.get('config', {})
        report.append("  最优参数组合:")
        report.append(f"    置信度阈值: {config.get('confidence_threshold', 0) * 100:.0f}%")
        report.append(f"    止损比例: {config.get('stop_loss_ratio', 0) * 100:.2f}%")
        report.append(f"    止盈比例: {config.get('take_profit_ratio', 0) * 100:.2f}%")
        report.append(f"    仓位比例: {config.get('position_size', 0) * 100:.0f}%")
        if strategy_type == 'TYPE_1' and best.get('require_divergence') is not None:
            report.append(f"    背驰确认: {best.get('require_divergence')}")
        
        # 完整指标表
        report.append("\n  完整指标表:")
        report.append(f"    | 指标 | 数值 |")
        report.append(f"    |------|------|")
        report.append(f"    | 交易次数 | {best['total_trades']} |")
        report.append(f"    | 胜率 | {best['win_rate']:.1f}% |")
        report.append(f"    | 最大回撤 | {best['max_drawdown']:.2f}% |")
        report.append(f"    | 最大浮盈 | {best['max_profit']:.2f}% |")
        report.append(f"    | 最大浮亏 | {best['max_loss']:.2f}% |")
        report.append(f"    | 实际收益率 | {best['total_return']:+.2f}% |")
        report.append(f"    | 年化收益率 | {best['annualized_return']:+.2f}% |")
        report.append(f"    | 盈亏比 | {best['profit_loss_ratio']:.2f} |")
        report.append(f"    | Sharpe比率 | {best['sharpe_ratio']:.2f} |")
        
        # 优化前后对比
        baseline = next((b for b in baseline_results if b['strategy_type'] == strategy_type), None)
        if baseline and baseline['total_trades'] > 0:
            report.append("\n  优化前后对比:")
            report.append(f"    交易次数: {baseline['total_trades']} -> {best['total_trades']}")
            report.append(f"    胜率: {baseline['win_rate']:.1f}% -> {best['win_rate']:.1f}%")
            report.append(f"    收益率: {baseline['total_return']:+.2f}% -> {best['total_return']:+.2f}%")
    
    # 策略对比汇总表
    report.append("\n【策略对比汇总表】")
    report.append("  | 策略 | 最优参数 | 胜率 | 收益率 | 年化 | 最大回撤 | 盈亏比 |")
    report.append("  |------|----------|------|--------|------|----------|--------|")
    
    for strategy_type in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
        if strategy_type == 'TYPE_1':
            key = 'type1'
        elif strategy_type == 'TYPE_2':
            key = 'type2'
        else:
            key = 'type3'
        
        opt = opt_results.get(key, {})
        best = opt.get('best_result')
        
        if best and best['total_trades'] > 0:
            config = best.get('config', {})
            params = f"conf={config.get('confidence_threshold', 0)*100:.0f}%, sl={config.get('stop_loss_ratio', 0)*100:.1f}%, tp={config.get('take_profit_ratio', 0)*100:.1f}%"
            report.append(f"  | {strategy_type} | {params} | {best['win_rate']:.1f}% | {best['total_return']:+.2f}% | {best['annualized_return']:+.2f}% | {best['max_drawdown']:.2f}% | {best['profit_loss_ratio']:.2f} |")
        else:
            report.append(f"  | {strategy_type} | - | - | - | - | - | - |")
    
    # 结论与建议
    report.append("\n【结论与建议】")
    
    # 找出最佳策略
    best_strategy = None
    best_return = -float('inf')
    for key, opt in opt_results.items():
        best = opt.get('best_result')
        if best and best['total_trades'] > 0 and best['total_return'] > best_return:
            best_return = best['total_return']
            best_strategy = key.upper()
    
    if best_strategy:
        report.append(f"  1. 最佳策略: {best_strategy}，收益率 {best_return:+.2f}%")
    
    report.append("\n  策略适用场景:")
    report.append("    - TYPE_1（第一类买卖点）: 适合趋势明显的市场，背驰信号可靠性高")
    report.append("    - TYPE_2（第二类买卖点）: 适合震荡转趋势的市场，确认反转后入场")
    report.append("    - TYPE_3（第三类买卖点）: 适合中枢突破行情，顺势交易")
    
    report.append("\n  风险提示:")
    report.append("    - 回测结果仅供参考，实盘交易存在滑点、手续费等成本")
    report.append("    - 历史表现不代表未来收益")
    report.append("    - 建议结合市场环境选择策略，分散风险")
    
    report.append("\n" + "=" * 80)
    
    return "\n".join(report)


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("BTC 多策略优化与回测")
    print("=" * 80)
    
    # 1. 获取数据
    df = fetch_btc_data(days=180, interval='5m')
    
    # 2. 缠论分析
    result = analyze_chanlun(df)
    
    # 3. 检测信号
    signals = detect_signals(df, result['bi_list'], result['zhongshu_list'])
    
    # 4. 基线回测（默认参数）
    print("\n[基线回测] 使用默认参数...")
    config_manager = StrategyConfigManager()
    baseline_results = []
    
    for strategy_type in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
        config = config_manager.get_config(strategy_type)
        if config is None:
            continue
        
        config_dict = {
            'confidence_threshold': config.confidence_threshold,
            'stop_loss_ratio': config.stop_loss_ratio,
            'take_profit_ratio': config.take_profit_ratio,
            'position_size': config.position_size,
            'max_holding_hours': config.max_holding_hours
        }
        
        r = backtest_strategy(df, signals, strategy_type, config_dict)
        baseline_results.append(r)
        print(f"   {strategy_type}: {r['total_trades']}笔, 胜率{r['win_rate']:.1f}%, 收益{r['total_return']:+.2f}%")
    
    # 5. 参数优化
    opt_results = {}
    
    opt_results['type1'] = optimize_type1(df, signals)
    opt_results['type2'] = optimize_type2(df, signals)
    opt_results['type3'] = optimize_type3(df, signals)
    
    # 6. 生成报告
    report = generate_optimization_report(df, signals, opt_results, baseline_results)
    print(report)
    
    # 保存报告
    output_file = os.path.join(os.path.dirname(__file__), 'output', 'optimization_report.md')
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n报告已保存至: {output_file}")
    
    return opt_results


if __name__ == "__main__":
    main()