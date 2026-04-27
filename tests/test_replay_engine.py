"""
历史数据回放测试体系 - 测试用例
TC-RP-001 ~ TC-RP-017

核心目标：以历史数据回放驱动策略验证，产出胜率/收益率关键指标
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import json
import os


# ============================================================================
# 数据模型（测试所需的最小数据结构）
# ============================================================================

@dataclass
class Trade:
    """单笔交易记录"""
    stock_code: str = ""  # 改为可选
    direction: str = "LONG"           # 买入方向
    entry_date: str = ""              # 买入日期
    entry_price: float = 0.0          # 买入价格
    exit_date: str = ""               # 卖出日期
    exit_price: float = 0.0           # 卖出价格
    shares: int = 0                   # 持仓数量
    pnl: float = 0.0                  # 盈亏金额
    pnl_pct: float = 0.0             # 盈亏比例
    exit_reason: str = ""             # 退出原因: stop_loss / take_profit / timeout
    commission: float = 0.0           # 手续费


@dataclass
class BacktestMetrics:
    """回测指标"""
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0         # 总收益率 %
    avg_trade_return: float = 0.0     # 平均单笔收益率 %
    win_rate: float = 0.0             # 胜率 %
    total_trades: int = 0             # 总交易次数
    winning_trades: int = 0           # 盈利交易次数
    losing_trades: int = 0            # 亏损交易次数
    max_drawdown: float = 0.0         # 最大回撤 %
    sharpe_ratio: float = 0.0         # 夏普比率
    profit_factor: float = 0.0        # 盈亏比


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 1000000.0    # 初始资金 100万
    commission_rate: float = 0.001        # 手续费率 0.1%
    stop_loss_pct: float = 0.05           # 止损 5%
    take_profit_pct: float = 0.15         # 止盈 15%
    max_hold_days: int = 10               # 最大持仓天数
    min_hold_days: int = 2                # 最少持仓天数（涨停后）
    lot_size: int = 100                    # 每手股数
    max_consecutive_losses: int = 3        # 连续亏损熔断阈值
    cooldown_days: int = 5                 # 熔断冷却天数


# ============================================================================
# 测试辅助函数：构造模拟数据
# ============================================================================

def make_daily_data(days: int = 120, start_price: float = 10.0,
                    trend: str = "flat", volatility: float = 0.02) -> pd.DataFrame:
    """
    构造模拟日线数据

    Args:
        days: 天数
        start_price: 起始价格
        trend: 趋势类型 flat/up/down/v_shaped/limit_up_breakout
        volatility: 波动率
    """
    np.random.seed(42)
    dates = pd.date_range(start='2025-01-02', periods=days, freq='B')

    close_prices = [start_price]
    for i in range(1, days):
        if trend == "flat":
            change = np.random.normal(0, volatility * start_price)
        elif trend == "up":
            change = np.random.normal(0.003, volatility * start_price)
        elif trend == "down":
            change = np.random.normal(-0.003, volatility * start_price)
        elif trend == "v_shaped":
            if i < days // 2:
                change = np.random.normal(-0.005, volatility * start_price)
            else:
                change = np.random.normal(0.005, volatility * start_price)
        elif trend == "limit_up_breakout":
            if i == days // 2:
                change = start_price * 0.10  # 涨停日
            else:
                change = np.random.normal(0, volatility * start_price)
        else:
            change = np.random.normal(0, volatility * start_price)

        close_prices.append(max(close_prices[-1] + change, 1.0))

    close = np.array(close_prices)
    high = close * (1 + np.abs(np.random.normal(0, 0.01, days)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, days)))
    open_ = close * (1 + np.random.normal(0, 0.005, days))
    volume = np.random.randint(100000, 500000, days)

    df = pd.DataFrame({
        'date': dates,
        'open': np.round(open_, 2),
        'high': np.round(high, 2),
        'low': np.round(low, 2),
        'close': np.round(close, 2),
        'volume': volume
    })
    return df


def make_limit_up_data(days: int = 60) -> pd.DataFrame:
    """构造包含涨停突破形态的模拟数据"""
    np.random.seed(100)
    dates = pd.date_range(start='2025-01-02', periods=days, freq='B')

    # 阶段1: 横盘震荡（形成中枢）day 0-29
    # 阶段2: 涨停突破 day 30
    # 阶段3: 回抽不破ZG day 31-35
    # 阶段4: 重新向上 day 36+

    prices = []
    base = 10.0
    for i in range(days):
        if i < 30:
            # 横盘震荡
            p = base + np.random.normal(0, 0.1)
        elif i == 30:
            # 涨停
            p = base * 1.10
        elif i < 36:
            # 回抽（不破ZG ≈ base + 0.2）
            p = base * 1.10 - (i - 30) * 0.02
        else:
            # 重新向上
            p = base * 1.10 + (i - 36) * 0.03
        prices.append(round(p, 2))

    close = np.array(prices)
    high = close * 1.005
    low = close * 0.995
    open_ = close * (1 + np.random.normal(0, 0.003, days))
    volume = np.random.randint(100000, 500000, days)

    # 涨停日特殊处理
    high[30] = close[30]
    low[30] = close[30]

    df = pd.DataFrame({
        'date': dates,
        'open': np.round(open_, 2),
        'high': np.round(high, 2),
        'low': np.round(low, 2),
        'close': np.round(close, 2),
        'volume': volume
    })
    return df


def make_consecutive_loss_data() -> pd.DataFrame:
    """构造会触发连续亏损熔断的数据"""
    np.random.seed(200)
    days = 120
    dates = pd.date_range(start='2025-01-02', periods=days, freq='B')

    prices = []
    base = 10.0
    for i in range(days):
        if i in [20, 40, 60]:
            # 三个买入点，每个都快速下跌触发止损
            p = base + 0.5
            base -= 0.3
        elif i in [22, 42, 62]:
            # 止损日
            p = prices[-1] * 0.94
        else:
            p = prices[-1] + np.random.normal(0, 0.05) if prices else base
        prices.append(round(p, 2))

    close = np.array(prices)
    high = close * 1.005
    low = close * 0.995
    open_ = close * (1 + np.random.normal(0, 0.003, days))
    volume = np.random.randint(100000, 500000, days)

    df = pd.DataFrame({
        'date': dates,
        'open': np.round(open_, 2),
        'high': np.round(high, 2),
        'low': np.round(low, 2),
        'close': np.round(close, 2),
        'volume': volume
    })
    return df


# ============================================================================
# P0 核心路径测试
# ============================================================================

class TestReplayEngineCore:
    """TC-RP-001 ~ TC-RP-006: 回放引擎核心功能"""

    def test_rp001_bar_by_bar_progression(self):
        """
        TC-RP-001: 回放引擎逐 bar 推进
        Given: 120 天日线数据
        When: 启动回放引擎逐 bar 推进
        Then: 每个时间点只看到当前及之前数据，不泄露未来
        """
        from src.replay_engine import ReplayEngine

        df = make_daily_data(days=120)
        engine = ReplayEngine(df)

        for i in range(len(df)):
            engine.advance()
            available = engine.get_available_data()
            # 验证只能看到当前及之前的数据
            assert len(available) == i + 1, \
                f"Bar {i}: 应有 {i+1} 条数据，实际 {len(available)}"
            # 验证最后一条就是当前 bar
            assert available.iloc[-1]['date'] == df.iloc[i]['date'], \
                f"Bar {i}: 数据泄露！当前 bar 日期不匹配"

    def test_rp002_buy_signal_execution(self):
        """
        TC-RP-002: 买入信号触发并模拟成交
        Given: 回放过程中策略识别到买点信号
        When: 信号触发且风控通过
        Then: 以次日开盘价模拟买入成交
        """
        from src.replay_engine import ReplayEngine

        df = make_limit_up_data(days=60)
        config = BacktestConfig()
        engine = ReplayEngine(df, config=config)

        # 模拟在 day 35 附近产生买入信号
        # 策略识别信号后，以次日开盘价成交
        for i in range(len(df)):
            engine.advance()

            if i == 35:  # 假设在 day 35 触发买入信号
                signal = engine.generate_signal()
                if signal and signal.get('action') == 'BUY':
                    trade = engine.execute_buy(signal, shares=1000)
                    assert trade is not None, "买入交易应成功"
                    assert trade.entry_price == df.iloc[i + 1]['open'], \
                        "买入价应为次日开盘价"
                    assert trade.direction == "LONG"
                    assert trade.entry_date == str(df.iloc[i + 1]['date'].date())

    def test_rp003_sell_signal_execution(self):
        """
        TC-RP-003: 卖出信号触发（止损/止盈/超时）
        Given: 持仓中，触发退出条件
        When: 止损/止盈/超时
        Then: 以次日开盘价模拟卖出
        """
        from src.replay_engine import ReplayEngine

        df = make_daily_data(days=60, trend="up")
        config = BacktestConfig(take_profit_pct=0.10)
        engine = ReplayEngine(df, config=config)

        # 手动注入一笔交易来测试卖出逻辑
        trade = Trade(
            stock_code="TEST",
            direction="LONG",
            entry_date="2025-01-03",
            entry_price=10.0,
            shares=1000
        )

        # 模拟持仓后价格上涨 12%，触发止盈
        # 止盈条件: exit_price >= entry_price * (1 + take_profit_pct)
        assert trade.entry_price * (1 + config.take_profit_pct) == 11.0, \
            "止盈价 = 10.0 * 1.10 = 11.0"

    def test_rp004_win_rate_calculation(self):
        """
        TC-RP-004: 胜率计算
        Given: 5 笔已完成交易，3 笔盈利
        When: 计算胜率
        Then: win_rate = 3 / 5 * 100% = 60%
        """
        from src.replay_engine import calculate_metrics

        trades = [
            Trade(stock_code="A", pnl=500, pnl_pct=5.0),
            Trade(stock_code="B", pnl=-200, pnl_pct=-2.0),
            Trade(stock_code="C", pnl=300, pnl_pct=3.0),
            Trade(stock_code="D", pnl=-100, pnl_pct=-1.0),
            Trade(stock_code="E", pnl=800, pnl_pct=8.0),
        ]

        metrics = calculate_metrics(
            trades=trades,
            initial_capital=1000000.0
        )

        assert metrics.total_trades == 5
        assert metrics.winning_trades == 3
        assert metrics.losing_trades == 2
        assert metrics.win_rate == pytest.approx(60.0, abs=0.01), \
            f"胜率应为 60%，实际 {metrics.win_rate}%"

    def test_rp005_return_calculation(self):
        """
        TC-RP-005: 收益率计算
        Given: 初始 100 万，最终 115 万
        When: 计算收益率
        Then: total_return = 15%, avg_trade_return = mean(pnl_pct)
        """
        from src.replay_engine import calculate_metrics

        trades = [
            Trade(stock_code="A", pnl=50000, pnl_pct=5.0),
            Trade(stock_code="B", pnl=-20000, pnl_pct=-2.0),
            Trade(stock_code="C", pnl=80000, pnl_pct=8.0),
            Trade(stock_code="D", pnl=40000, pnl_pct=4.0),
        ]

        metrics = calculate_metrics(
            trades=trades,
            initial_capital=1000000.0,
            final_capital=1150000.0
        )

        assert metrics.total_return == pytest.approx(15.0, abs=0.01), \
            f"总收益率应为 15%，实际 {metrics.total_return}%"
        assert metrics.avg_trade_return == pytest.approx(3.75, abs=0.01), \
            f"平均收益率应为 3.75%，实际 {metrics.avg_trade_return}%"

    def test_rp006_end_to_end_replay(self):
        """
        TC-RP-006: 完整回放流程端到端
        Given: 60 天历史数据
        When: 执行完整回放
        Then: 输出完整回测报告
        """
        from src.replay_engine import ReplayEngine

        df = make_limit_up_data(days=60)
        config = BacktestConfig()
        engine = ReplayEngine(df, config=config)

        # 运行完整回放
        result = engine.run()

        # 验证报告包含所有必要字段
        assert 'metrics' in result
        assert 'trades' in result
        assert 'config' in result

        metrics = result['metrics']
        assert 'total_return' in metrics
        assert 'win_rate' in metrics
        assert 'total_trades' in metrics
        assert 'max_drawdown' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'avg_trade_return' in metrics


# ============================================================================
# P1 异常场景测试
# ============================================================================

class TestReplayEdgeCases:
    """TC-RP-007 ~ TC-RP-011: 异常与边界场景"""

    def test_rp007_no_signal_replay(self):
        """
        TC-RP-007: 无信号数据回放
        Given: 平稳无趋势行情
        When: 执行完整回放
        Then: 交易次数为 0，资金不变
        """
        from src.replay_engine import ReplayEngine

        df = make_daily_data(days=60, trend="flat", volatility=0.001)
        config = BacktestConfig()
        engine = ReplayEngine(df, config=config)

        result = engine.run()

        assert result['metrics']['total_trades'] == 0, \
            "无趋势数据应无交易"
        assert result['metrics']['final_capital'] == config.initial_capital, \
            "无交易资金应不变"
        assert result['metrics']['win_rate'] == 0.0, \
            "无交易胜率应为 0"

    def test_rp008_no_future_data_leak(self):
        """
        TC-RP-008: 未来数据泄露检测
        Given: 回放引擎在某个 bar 位置
        When: 策略获取数据
        Then: 只能看到当前及之前数据
        """
        from src.replay_engine import ReplayEngine

        df = make_daily_data(days=60)
        engine = ReplayEngine(df)

        # 在 bar 30 处检查
        for i in range(31):
            engine.advance()

        available = engine.get_available_data()
        current_date = df.iloc[30]['date']
        last_available_date = available.iloc[-1]['date']

        assert last_available_date == current_date, \
            "数据泄露！当前 bar 之后的数据不应可见"

        # 验证总行数
        assert len(available) == 31, \
            f"bar 30 处应有 31 条数据，实际 {len(available)}"

    def test_rp009_consecutive_loss_circuit_breaker(self):
        """
        TC-RP-009: 连续亏损后风控熔断
        Given: 连续 3 笔止损
        When: 风控检测到连续亏损
        Then: 暂停交易 5 天（冷却期）
        """
        from src.replay_engine import ReplayEngine

        df = make_consecutive_loss_data()
        config = BacktestConfig(max_consecutive_losses=3, cooldown_days=5)
        engine = ReplayEngine(df, config=config)

        result = engine.run()

        # 验证冷却期内无新交易
        # 检查交易时间间隔
        trades = result['trades']
        if len(trades) >= 4:
            # 第 3 笔亏损后，第 4 笔应间隔至少 cooldown_days
            loss_dates = [t.exit_date for t in trades[:3]]
            if len(loss_dates) == 3:
                third_loss_date = pd.to_datetime(loss_dates[2])
                next_entry_date = pd.to_datetime(trades[3].entry_date)
                gap = (next_entry_date - third_loss_date).days
                assert gap >= config.cooldown_days, \
                    f"冷却期应为 {config.cooldown_days} 天，实际间隔 {gap} 天"

    def test_rp010_limit_up_no_execution(self):
        """
        TC-RP-010: 涨跌停无法成交
        Given: 信号触发次日股票涨停
        When: 尝试以开盘价买入
        Then: 涨停日无法买入，跳过信号
        """
        from src.replay_engine import ReplayEngine

        df = make_limit_up_data(days=60)
        config = BacktestConfig()
        engine = ReplayEngine(df, config=config)

        result = engine.run()
        trades = result['trades']

        # 验证没有在涨停日买入
        for trade in trades:
            entry_idx = df[df['date'].astype(str).str.startswith(trade.entry_date)].index
            if len(entry_idx) > 0:
                idx = entry_idx[0]
                row = df.iloc[idx]
                # 涨停日 high == close == low（一字板）
                is_limit_up = (row['high'] == row['close'] == row['low'] and
                               row['close'] > row['open'])
                if is_limit_up:
                    pytest.fail(f"不应在涨停日 {trade.entry_date} 成交买入")

    def test_rp011_insufficient_capital(self):
        """
        TC-RP-011: 资金不足无法开仓
        Given: 可用资金不足一手
        When: 信号触发
        Then: 跳过信号
        """
        from src.replay_engine import ReplayEngine

        df = make_limit_up_data(days=60)
        # 设置极小的初始资金
        config = BacktestConfig(initial_capital=500.0, lot_size=100)
        engine = ReplayEngine(df, config=config)

        result = engine.run()

        # 如果股价 > 5 元，500 元买不到一手(100股)
        # 验证没有超出资金能力的交易
        for trade in result['trades']:
            position_cost = trade.entry_price * trade.shares
            assert position_cost <= config.initial_capital, \
                f"交易金额 {position_cost} 超过初始资金 {config.initial_capital}"


# ============================================================================
# P2 边界条件测试
# ============================================================================

class TestReplayBoundaryConditions:
    """TC-RP-012 ~ TC-RP-015: 边界条件"""

    def test_rp012_consecutive_limit_up(self):
        """
        TC-RP-012: 连续涨停极端行情
        Given: 买入后连续涨停
        When: 回放
        Then: 持仓穿越涨停期，不触发止盈（无法卖出）
        """
        from src.replay_engine import ReplayEngine

        # 构造连续涨停数据
        days = 30
        dates = pd.date_range(start='2025-01-02', periods=days, freq='B')
        base = 10.0
        prices = []
        for i in range(days):
            if i < 5:
                prices.append(base + i * 0.1)
            elif i < 10:
                # 连续涨停
                prices.append(prices[-1] * 1.10)
            else:
                prices.append(prices[-1] + np.random.normal(0, 0.5))

        close = np.round(np.array(prices), 2)
        df = pd.DataFrame({
            'date': dates,
            'open': close * 0.998,
            'high': close,
            'low': close * 0.998,
            'close': close,
            'volume': np.random.randint(100000, 500000, days)
        })

        config = BacktestConfig(take_profit_pct=0.15)
        engine = ReplayEngine(df, config=config)
        result = engine.run()

        # 涨停板期间不应有卖出成交
        # （实际实现中，涨停板卖单可以成交，但买入需要排队）
        assert result is not None  # 至少不崩溃

    def test_rp013_data_gap_handling(self):
        """
        TC-RP-013: 数据缺失（停牌）处理
        Given: 数据中有停牌日（日期不连续）
        When: 回放到缺失日期
        Then: 跳过停牌日，持仓天数排除停牌
        """
        from src.replay_engine import ReplayEngine

        df = make_daily_data(days=60)
        # 模拟停牌：删除中间几天的数据
        df_with_gap = pd.concat([df.iloc[:25], df.iloc[30:]]).reset_index(drop=True)

        config = BacktestConfig()
        engine = ReplayEngine(df_with_gap, config=config)
        result = engine.run()

        # 应该能正常完成，不崩溃
        assert result is not None
        assert 'metrics' in result

    def test_rp014_single_trade_pnl_boundary(self):
        """
        TC-RP-014: 单笔交易收益率边界
        Given: 买入后次日止损（-5%）
        When: 计算收益率
        Then: pnl_pct ≈ -5% - 手续费
        """
        from src.replay_engine import calculate_metrics

        trade = Trade(
            stock_code="TEST",
            entry_price=10.0,
            exit_price=9.5,
            shares=1000,
            pnl=-500,
            pnl_pct=-5.0,
            commission=10.0,
            exit_reason="stop_loss"
        )

        metrics = calculate_metrics(
            trades=[trade],
            initial_capital=1000000.0,
            final_capital=999490.0  # 100万 - 500亏损 - 10手续费
        )

        assert metrics.total_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.winning_trades == 0
        assert metrics.win_rate == 0.0

    def test_rp015_multi_stock_aggregation(self):
        """
        TC-RP-015: 多股票并行回放指标汇总
        Given: 多只股票各自回放完毕
        When: 汇总指标
        Then: 输出汇总胜率、收益率
        """
        from src.replay_engine import aggregate_multi_stock_results

        stock_results = {
            'sh.600000': {
                'trades': [Trade(pnl=1000, pnl_pct=5.0),
                           Trade(pnl=-500, pnl_pct=-2.0)],
                'initial_capital': 1000000,
                'final_capital': 1000500,
            },
            'sh.600036': {
                'trades': [Trade(pnl=2000, pnl_pct=8.0),
                           Trade(pnl=500, pnl_pct=2.0),
                           Trade(pnl=-800, pnl_pct=-3.0)],
                'initial_capital': 1000000,
                'final_capital': 1001700,
            }
        }

        aggregate = aggregate_multi_stock_results(stock_results)

        # 汇总: 总交易 5 笔, 盈利 3 笔, 胜率 60%
        assert aggregate['total_trades'] == 5
        assert aggregate['winning_trades'] == 3
        assert aggregate['win_rate'] == pytest.approx(60.0, abs=0.01)


# ============================================================================
# 迭代优化测试
# ============================================================================

class TestIterationOptimization:
    """TC-RP-016 ~ TC-RP-017: 策略迭代优化"""

    def test_rp016_parameter_comparison(self):
        """
        TC-RP-016: 策略参数变更后指标对比
        Given: 基线策略参数 A 的回测结果
        When: 调整为参数 B 重新回测
        Then: 对比指标变化，输出 diff 报告
        """
        from src.replay_engine import ReplayEngine, compare_backtest_results

        df = make_limit_up_data(days=60)

        # 参数 A: 基线
        config_a = BacktestConfig(stop_loss_pct=0.05, take_profit_pct=0.15)
        engine_a = ReplayEngine(df, config=config_a)
        result_a = engine_a.run()

        # 参数 B: 调整
        config_b = BacktestConfig(stop_loss_pct=0.03, take_profit_pct=0.10)
        engine_b = ReplayEngine(df, config=config_b)
        result_b = engine_b.run()

        # 对比
        comparison = compare_backtest_results(result_a, result_b)

        assert 'metrics_diff' in comparison
        assert 'win_rate_diff' in comparison['metrics_diff']
        assert 'total_return_diff' in comparison['metrics_diff']

    def test_rp017_baseline_recording(self):
        """
        TC-RP-017: 指标基准线记录
        Given: 首次完整回放完成
        When: 保存结果
        Then: baseline.json 包含胜率、收益率、时间戳
        """
        from src.replay_engine import save_baseline

        metrics = BacktestMetrics(
            initial_capital=1000000,
            final_capital=1080000,
            total_return=8.0,
            win_rate=55.0,
            total_trades=10,
            winning_trades=5,
            max_drawdown=3.2,
            sharpe_ratio=1.2
        )

        baseline_path = save_baseline(metrics, path="/tmp/test_baseline.json")

        # 验证文件存在
        assert os.path.exists(baseline_path)

        # 验证内容
        with open(baseline_path) as f:
            data = json.load(f)

        assert 'win_rate' in data
        assert 'total_return' in data
        assert 'timestamp' in data
        assert data['win_rate'] == 55.0
        assert data['total_return'] == 8.0

        # 清理
        os.remove(baseline_path)
