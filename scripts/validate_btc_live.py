#!/usr/bin/env python3
"""
BTC 实盘验证脚本

支持：
1. 手动指定代理
2. 自动检测本地代理
3. 降级到模拟数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from src.crypto_data_fetcher import (
    CryptoDataFetcher, 
    validate_crypto_data,
    generate_simulated_btc_data
)
from src.replay_engine import ReplayEngine, BacktestConfig


def test_with_real_data(proxy: str = None):
    """测试真实数据"""
    print("=== 尝试获取真实 BTC 数据 ===")
    print(f"代理: {proxy or '无'}")
    print()
    
    fetcher = CryptoDataFetcher(exchange='binance', proxy=proxy)
    
    try:
        df = fetcher.fetch_klines('BTCUSDT', '5m', limit=200)
        
        if df is not None and not df.empty:
            print(f"✓ 成功获取 {len(df)} 根K线")
            print(f"  最新价: {df['close'].iloc[-1]:.2f} USDT")
            print(f"  时间范围: {df['date'].min()} ~ {df['date'].max()}")
            return df
    except Exception as e:
        print(f"✗ 获取失败: {e}")
    
    return None


def test_with_simulated_data():
    """使用模拟数据"""
    print("=== 使用模拟数据 ===")
    print()
    
    df = generate_simulated_btc_data(days=3)
    print(f"✓ 生成 {len(df)} 根K线")
    print(f"  价格范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
    return df


def run_backtest(df):
    """运行回测"""
    print("\n=== 回测验证 ===")
    
    config = BacktestConfig(
        initial_capital=100000,
        stop_loss_pct=0.03,
        take_profit_pct=0.05
    )
    
    engine = ReplayEngine(df, config=config)
    result = engine.run()
    
    metrics = result['metrics']
    print(f"  交易次数: {metrics['total_trades']}")
    print(f"  胜率: {metrics['win_rate']:.1f}%")
    print(f"  收益率: {metrics['total_return']:.2f}%")


def main():
    parser = argparse.ArgumentParser(description='BTC 缠论策略验证')
    parser.add_argument('--proxy', '-p', help='代理地址，如 http://127.0.0.1:7890')
    parser.add_argument('--simulated', '-s', action='store_true', help='强制使用模拟数据')
    args = parser.parse_args()
    
    print("=" * 60)
    print("BTC 缠论策略验证")
    print("=" * 60)
    print()
    
    # 获取数据
    df = None
    
    if not args.simulated:
        # 尝试真实数据
        df = test_with_real_data(args.proxy)
    
    if df is None:
        # 降级到模拟数据
        df = test_with_simulated_data()
    
    # 运行回测
    run_backtest(df)
    
    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
