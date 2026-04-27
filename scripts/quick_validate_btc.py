#!/usr/bin/env python3
"""
BTC 缠论策略快速验证
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime


def main():
    print("=" * 60)
    print("BTC 缠论策略验证")
    print("=" * 60)
    print()
    
    from src.crypto_data_fetcher import generate_simulated_btc_data, validate_crypto_data
    from src.chanlun_structure_v2 import (
        process_inclusion,
        detect_all_fractals,
        build_bi_from_fractals,
        detect_all_zhongshu
    )
    from src.replay_engine import ReplayEngine, BacktestConfig
    
    # ─────────────────────────────────────────────────────────────
    # Step 1: 数据
    # ─────────────────────────────────────────────────────────────
    print("[1] 生成 BTC 5分钟模拟数据...")
    df = generate_simulated_btc_data(days=3)  # 3天数据，更多笔和中枢
    print(f"    ✓ {len(df)} 根K线")
    print(f"    ✓ 价格: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
    
    # ─────────────────────────────────────────────────────────────
    # Step 2: 缠论结构
    # ─────────────────────────────────────────────────────────────
    print("\n[2] 缠论结构分析...")
    
    df_proc = process_inclusion(df)
    print(f"    ✓ 包含关系处理: {len(df)} → {len(df_proc)}")
    
    fractals = detect_all_fractals(df_proc)
    print(f"    ✓ 分型: {len(fractals)} 个")
    
    bi_list = build_bi_from_fractals(fractals, df_proc, min_klines=5)
    print(f"    ✓ 笔: {len(bi_list)} 笔")
    
    if bi_list:
        up = sum(1 for b in bi_list if b.direction.value == 'up')
        down = len(bi_list) - up
        print(f"      - 向上: {up}, 向下: {down}")
    
    zhongshu_list = detect_all_zhongshu(bi_list, min_bi=3) if bi_list else []
    print(f"    ✓ 中枢: {len(zhongshu_list)} 个")
    
    # ─────────────────────────────────────────────────────────────
    # Step 3: 回测
    # ─────────────────────────────────────────────────────────────
    print("\n[3] 回测验证...")
    
    config = BacktestConfig(
        initial_capital=100000,
        stop_loss_pct=0.03,
        take_profit_pct=0.05,
        max_holding_days=12
    )
    
    engine = ReplayEngine(df, config=config)
    result = engine.run()
    
    metrics = result['metrics']
    print(f"    ✓ 总交易: {metrics['total_trades']}")
    print(f"    ✓ 胜率: {metrics['win_rate']:.1f}%")
    print(f"    ✓ 收益率: {metrics['total_return']:.2f}%")
    
    # ─────────────────────────────────────────────────────────────
    # Step 4: 总结
    # ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)
    print(f"""
数据: {len(df)} 根5分钟K线
结构:
  - 分型: {len(fractals)}
  - 笔: {len(bi_list)}
  - 中枢: {len(zhongshu_list)}

回测:
  - 交易次数: {metrics['total_trades']}
  - 胜率: {metrics['win_rate']:.1f}%
  - 收益率: {metrics['total_return']:.2f}%
""")


if __name__ == "__main__":
    main()
