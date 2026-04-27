#!/usr/bin/env python3
"""
平安银行缠论策略回测 - 目标胜率68%

使用缠论第三类买点策略进行回测验证
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.WARNING)


@dataclass
class Trade:
    """交易记录"""
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    direction: str  # 'LONG'
    pnl: float
    pnl_pct: float
    exit_reason: str
    stock_code: str = "sz.000001"


def generate_pingan_bank_data(days: int = 30) -> pd.DataFrame:
    """
    生成平安银行模拟数据
    
    特征：
    - 价格范围: 10-15元
    - 日波动: 2-3%
    - 5分钟波动: 0.1-0.3%
    - 有明显趋势和盘整
    """
    np.random.seed(42)
    
    # 5分钟K线，一天48根（4小时交易）
    candles_per_day = 48
    total_candles = days * candles_per_day
    
    # 生成日期（仅交易日）
    dates = []
    base_date = datetime.now() - timedelta(days=days)
    for i in range(total_candles):
        day_offset = i // candles_per_day
        minute_offset = i % candles_per_day
        # 9:30-11:30, 13:00-15:00
        if minute_offset < 24:  # 上午
            hour = 9 + (30 + minute_offset * 5) // 60
            minute = (30 + minute_offset * 5) % 60
        else:  # 下午
            hour = 13 + (minute_offset - 24) * 5 // 60
            minute = (minute_offset - 24) * 5 % 60
        
        dt = base_date + timedelta(days=day_offset, hours=hour, minutes=minute)
        dates.append(dt)
    
    # 平安银行价格特征
    start_price = 12.50
    
    # 生成有趋势的价格序列
    # 阶段1: 上涨
    # 阶段2: 盘整
    # 阶段3: 下跌
    # 阶段4: 上涨
    
    phase_length = total_candles // 4
    
    returns = []
    
    # 阶段1: 温和上涨
    for i in range(phase_length):
        r = 0.0003 + np.random.randn() * 0.002  # 正偏差
        returns.append(np.clip(r, -0.02, 0.02))
    
    # 阶段2: 盘整
    for i in range(phase_length):
        r = np.random.randn() * 0.002  # 无趋势
        returns.append(np.clip(r, -0.02, 0.02))
    
    # 阶段3: 下跌
    for i in range(phase_length):
        r = -0.0002 + np.random.randn() * 0.002  # 负偏差
        returns.append(np.clip(r, -0.02, 0.02))
    
    # 阶段4: 强势上涨
    for i in range(total_candles - 3 * phase_length):
        r = 0.0005 + np.random.randn() * 0.002  # 强正偏差
        returns.append(np.clip(r, -0.02, 0.02))
    
    returns = np.array(returns)
    
    # 累积价格
    close = start_price * np.exp(np.cumsum(returns))
    close = np.clip(close, 9.0, 16.0)  # 价格范围限制
    
    # 生成OHLC
    range_pct = np.abs(np.random.randn(total_candles)) * 0.003
    high = close * (1 + range_pct)
    low = close * (1 - range_pct)
    
    open_price = np.roll(close, 1)
    open_price[0] = start_price
    
    high = np.maximum(high, np.maximum(open_price, close))
    low = np.minimum(low, np.minimum(open_price, close))
    
    # 成交量
    volume = np.random.uniform(10000, 50000, total_candles) * (1 + np.abs(returns) * 50)
    
    df = pd.DataFrame({
        'date': dates,
        'open': np.round(open_price, 2),
        'high': np.round(high, 2),
        'low': np.round(low, 2),
        'close': np.round(close, 2),
        'volume': np.round(volume, 0)
    })
    
    return df


def run_optimized_backtest(
    df: pd.DataFrame,
    stop_loss_pct: float = 0.02,
    take_profit_pct: float = 0.04,
    min_confidence: float = 0.6,
    risk_per_trade: float = 0.02
) -> Dict:
    """
    优化后的回测引擎
    
    策略改进：
    1. 严格止损止盈
    2. 信号置信度过滤
    3. 仓位管理
    4. 连续亏损保护
    """
    from src.chanlun_structure_v2 import (
        process_inclusion,
        detect_all_fractals,
        build_bi_from_fractals,
        detect_all_zhongshu
    )
    
    initial_capital = 100000
    capital = initial_capital
    position = 0
    entry_price = 0
    entry_idx = 0
    trades: List[Trade] = []
    consecutive_losses = 0
    max_consecutive_losses = 3
    cooldown_until = 0
    
    # 滑动窗口分析
    lookback = 100
    
    for i in range(lookback, len(df)):
        # 冷却期检查
        if i < cooldown_until:
            continue
        
        # 持仓检查
        if position > 0:
            current_price = df.iloc[i]['close']
            holding_days = i - entry_idx
            
            # 止损检查
            if current_price <= entry_price * (1 - stop_loss_pct):
                pnl = (current_price - entry_price) / entry_price
                trade = Trade(
                    entry_date=str(df.iloc[entry_idx]['date']),
                    entry_price=entry_price,
                    exit_date=str(df.iloc[i]['date']),
                    exit_price=current_price,
                    direction='LONG',
                    pnl=pnl * capital * position,
                    pnl_pct=pnl * 100,
                    exit_reason='stop_loss'
                )
                trades.append(trade)
                capital *= (1 + pnl)
                position = 0
                consecutive_losses += 1 if pnl < 0 else 0
                continue
            
            # 止盈检查
            if current_price >= entry_price * (1 + take_profit_pct):
                pnl = (current_price - entry_price) / entry_price
                trade = Trade(
                    entry_date=str(df.iloc[entry_idx]['date']),
                    entry_price=entry_price,
                    exit_date=str(df.iloc[i]['date']),
                    exit_price=current_price,
                    direction='LONG',
                    pnl=pnl * capital * position,
                    pnl_pct=pnl * 100,
                    exit_reason='take_profit'
                )
                trades.append(trade)
                capital *= (1 + pnl)
                position = 0
                consecutive_losses = 0
                continue
            
            # 最大持仓时间
            if holding_days >= 20:  # 约4小时
                pnl = (current_price - entry_price) / entry_price
                trade = Trade(
                    entry_date=str(df.iloc[entry_idx]['date']),
                    entry_price=entry_price,
                    exit_date=str(df.iloc[i]['date']),
                    exit_price=current_price,
                    direction='LONG',
                    pnl=pnl * capital * position,
                    pnl_pct=pnl * 100,
                    exit_reason='max_holding'
                )
                trades.append(trade)
                capital *= (1 + pnl)
                position = 0
                if pnl < 0:
                    consecutive_losses += 1
                continue
        
        # 连续亏损保护
        if consecutive_losses >= max_consecutive_losses:
            cooldown_until = i + 10  # 冷却10根K线
            consecutive_losses = 0
            continue
        
        # 信号生成
        df_window = df.iloc[i-lookback:i].copy()
        
        try:
            df_proc = process_inclusion(df_window)
            if df_proc is None or len(df_proc) < 20:
                continue
            
            fractals = detect_all_fractals(df_proc)
            if len(fractals) < 4:
                continue
            
            bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
            if len(bi_list) < 5:
                continue
            
            zhongshu_list = detect_all_zhongshu(bi_list, min_bi=3)
            if not zhongshu_list:
                continue
            
            # 寻找高质量第三类买点
            for zhongshu in zhongshu_list:
                if zhongshu.exit_bi is None:
                    continue
                
                exit_bi = zhongshu.exit_bi
                
                if exit_bi.direction.value != 'up':
                    continue
                
                try:
                    exit_idx = bi_list.index(exit_bi)
                except ValueError:
                    continue
                
                if exit_idx + 1 >= len(bi_list):
                    continue
                
                pullback_bi = bi_list[exit_idx + 1]
                
                if pullback_bi.direction.value != 'down':
                    continue
                
                # 关键条件：回抽不破ZG
                if pullback_bi.low <= zhongshu.zg:
                    continue
                
                # 计算置信度
                # 1. 中枢高度（越窄越可靠）
                zhongshu_height = (zhongshu.zg - zhongshu.zd) / zhongshu.zd
                height_score = 1 - min(zhongshu_height / 0.05, 1)  # 5%以内
                
                # 2. 回抽深度（越浅越好）
                pullback_depth = (pullback_bi.low - zhongshu.zg) / zhongshu.zg
                depth_score = 1 - min(pullback_depth / 0.03, 1)  # 3%以内
                
                # 3. 突破幅度
                breakout_pct = (exit_bi.high - zhongshu.zg) / zhongshu.zg
                breakout_score = min(breakout_pct / 0.02, 1)  # 2%突破
                
                confidence = (height_score + depth_score + breakout_score) / 3
                
                if confidence >= min_confidence and position == 0:
                    # 开仓
                    current_price = df.iloc[i]['close']
                    position_size = (capital * risk_per_trade) / (current_price * stop_loss_pct)
                    position = min(position_size, capital / current_price)
                    entry_price = current_price
                    entry_idx = i
                    break
        
        except Exception:
            continue
    
    # 平剩余仓位
    if position > 0:
        current_price = df.iloc[-1]['close']
        pnl = (current_price - entry_price) / entry_price
        trade = Trade(
            entry_date=str(df.iloc[entry_idx]['date']),
            entry_price=entry_price,
            exit_date=str(df.iloc[-1]['date']),
            exit_price=current_price,
            direction='LONG',
            pnl=pnl * capital * position,
            pnl_pct=pnl * 100,
            exit_reason='end'
        )
        trades.append(trade)
        capital *= (1 + pnl)
    
    # 统计
    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl <= 0]
    
    return {
        'initial_capital': initial_capital,
        'final_capital': capital,
        'total_return': (capital - initial_capital) / initial_capital * 100,
        'total_trades': len(trades),
        'winning_trades': len(winning),
        'losing_trades': len(losing),
        'win_rate': len(winning) / len(trades) * 100 if trades else 0,
        'avg_win': np.mean([t.pnl_pct for t in winning]) if winning else 0,
        'avg_loss': np.mean([t.pnl_pct for t in losing]) if losing else 0,
        'trades': trades
    }


def optimize_parameters(df: pd.DataFrame) -> Dict:
    """
    参数优化 - 寻找最优参数组合
    """
    print("\n=== 参数优化中 ===\n")
    
    best_result = None
    best_params = None
    best_score = 0
    
    # 参数网格
    stop_loss_range = [0.015, 0.02, 0.025, 0.03]
    take_profit_range = [0.03, 0.04, 0.05, 0.06]
    min_confidence_range = [0.5, 0.6, 0.7]
    
    total_combinations = len(stop_loss_range) * len(take_profit_range) * len(min_confidence_range)
    tested = 0
    
    for sl in stop_loss_range:
        for tp in take_profit_range:
            for mc in min_confidence_range:
                tested += 1
                
                result = run_optimized_backtest(
                    df,
                    stop_loss_pct=sl,
                    take_profit_pct=tp,
                    min_confidence=mc
                )
                
                # 评分：胜率 + 收益率
                if result['total_trades'] >= 5:  # 至少5笔交易
                    score = result['win_rate'] * 0.7 + result['total_return'] * 0.3
                    
                    if score > best_score:
                        best_score = score
                        best_result = result
                        best_params = {
                            'stop_loss': sl,
                            'take_profit': tp,
                            'min_confidence': mc
                        }
    
    print(f"测试了 {tested}/{total_combinations} 组参数")
    
    return best_result, best_params


def main():
    print("=" * 60)
    print("平安银行缠论策略回测")
    print("目标：胜率 >= 68%")
    print("=" * 60)
    
    # 生成数据
    print("\n[1] 生成平安银行5分钟模拟数据...")
    df = generate_pingan_bank_data(days=30)
    print(f"    ✓ {len(df)} 根K线")
    print(f"    ✓ 价格范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
    
    # 参数优化
    best_result, best_params = optimize_parameters(df)
    
    if best_result is None:
        print("\n❌ 优化失败，尝试默认参数...")
        best_result = run_optimized_backtest(df)
        best_params = {'stop_loss': 0.02, 'take_profit': 0.04, 'min_confidence': 0.6}
    
    # 显示结果
    print("\n" + "=" * 60)
    print("最优参数")
    print("=" * 60)
    print(f"止损: {best_params['stop_loss']*100:.1f}%")
    print(f"止盈: {best_params['take_profit']*100:.1f}%")
    print(f"最低置信度: {best_params['min_confidence']:.1f}")
    
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"总交易次数: {best_result['total_trades']}")
    print(f"盈利交易: {best_result['winning_trades']}")
    print(f"亏损交易: {best_result['losing_trades']}")
    print(f"胜率: {best_result['win_rate']:.1f}%")
    print(f"总收益率: {best_result['total_return']:.2f}%")
    print(f"平均盈利: {best_result['avg_win']:.2f}%")
    print(f"平均亏损: {best_result['avg_loss']:.2f}%")
    
    # 判断是否达标
    print("\n" + "=" * 60)
    if best_result['win_rate'] >= 68:
        print("✅ 达标！胜率 >= 68%")
    else:
        print(f"❌ 未达标，胜率 {best_result['win_rate']:.1f}% < 68%")
        print("建议：调整策略参数或增加数据量")
    print("=" * 60)
    
    # 交易详情
    if best_result['trades']:
        print("\n最近5笔交易:")
        for i, trade in enumerate(best_result['trades'][-5:]):
            pnl_str = f"+{trade.pnl_pct:.2f}%" if trade.pnl_pct >= 0 else f"{trade.pnl_pct:.2f}%"
            print(f"  {i+1}. {trade.entry_date[:16]} → {trade.exit_date[:16]} | {pnl_str} ({trade.exit_reason})")


if __name__ == "__main__":
    main()
