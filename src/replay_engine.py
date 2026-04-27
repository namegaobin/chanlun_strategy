"""
历史数据回放引擎
用于逐 bar 回放历史数据，验证交易策略

核心功能：
1. 逐 bar 推进，确保不泄露未来数据
2. 基于缠论结构的信号生成（分型、笔、中枢、第三类买点）
3. 风控检查（止损/止盈/超时）
4. 回测指标计算
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class Trade:
    """单笔交易记录"""
    stock_code: str = ""
    direction: str = "LONG"
    entry_date: str = ""
    entry_price: float = 0.0
    exit_date: str = ""
    exit_price: float = 0.0
    shares: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""
    commission: float = 0.0


@dataclass
class BacktestMetrics:
    """回测指标"""
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    avg_trade_return: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 1000000.0
    commission_rate: float = 0.0003
    slippage: float = 0.0
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10
    max_holding_days: int = 20
    risk_per_trade: float = 0.02
    max_positions: int = 5
    max_consecutive_losses: int = 3
    cooldown_days: int = 5


# ============================================================================
# 缠论信号生成器
# ============================================================================

class ChanLunSignalGenerator:
    """基于缠论结构的信号生成器"""
    
    def __init__(self):
        self.last_zhongshu = None
        self.last_signal = None
    
    def generate(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        生成缠论买卖信号
        
        流程：
        1. 处理K线包含关系
        2. 检测分型
        3. 构建笔
        4. 检测中枢
        5. 识别第三类买点
        
        Args:
            df: K线数据
            
        Returns:
            信号字典或 None
        """
        from src.chanlun_structure_v2 import (
            process_inclusion,
            detect_all_fractals,
            build_bi_from_fractals,
            detect_all_zhongshu
        )
        
        if df is None or len(df) < 20:
            return None
        
        # 1. 处理K线包含关系
        df_processed = process_inclusion(df)
        if df_processed is None or len(df_processed) < 10:
            return None
        
        # 2. 检测分型
        fractals = detect_all_fractals(df_processed)
        if len(fractals) < 4:
            return None
        
        # 3. 构建笔
        bi_list = build_bi_from_fractals(fractals, df_processed, min_klines=5)
        if len(bi_list) < 5:
            return None
        
        # 4. 检测所有中枢（而不是只检测最后一个）
        zhongshu_list = detect_all_zhongshu(bi_list, min_bi=3)
        if not zhongshu_list:
            return None
        
        # 更新最后的中枢
        self.last_zhongshu = zhongshu_list[-1] if zhongshu_list else None
        
        # 5. 遍历所有中枢，寻找第三类买点
        for zhongshu in zhongshu_list:
            signal = self._detect_third_buy_point(bi_list, zhongshu, df_processed)
            if signal and signal['action'] == 'BUY':
                return signal
        
        return None
    
    def _detect_third_buy_point(
        self,
        bi_list: List,
        zhongshu,
        df: pd.DataFrame
    ) -> Optional[Dict]:
        """
        识别第三类买点
        
        第三类买点定义：
        1. 价格向上离开中枢（突破 ZG）
        2. 回抽不破 ZG（回抽低点 > ZG）
        3. 重新向上时买入
        
        Args:
            bi_list: 笔列表
            zhongshu: 中枢对象
            df: K线数据
            
        Returns:
            信号字典或 None
        """
        if len(bi_list) < 5 or zhongshu.exit_bi is None:
            return None
        
        # 离开段
        exit_bi = zhongshu.exit_bi
        
        # 获取离开段在笔列表中的索引
        try:
            exit_idx = bi_list.index(exit_bi)
        except ValueError:
            return None
        
        # 检查离开段是否向上突破
        if exit_bi.direction.value != 'up':
            return None
        
        if exit_bi.high <= zhongshu.zg:
            return None
        
        # 检查是否有回抽笔
        if exit_idx + 1 >= len(bi_list):
            return None
        
        pullback_bi = bi_list[exit_idx + 1]
        
        # 回抽必须是向下笔
        if pullback_bi.direction.value != 'down':
            return None
        
        # 关键：回抽低点必须高于 ZG（不破中枢）
        if pullback_bi.low <= zhongshu.zg:
            return None
        
        # ✅ 第三类买点成立！
        current_price = df.iloc[-1]['close']
        
        return {
            'action': 'BUY',
            'price': current_price,
            'reason': 'third_buy_point_pullback_above_zg',
            'zhongshu_zg': zhongshu.zg,
            'zhongshu_zd': zhongshu.zd,
            'pullback_low': pullback_bi.low,
            'confidence': self._calculate_confidence(zhongshu, pullback_bi)
        }
    
    def _calculate_confidence(self, zhongshu, pullback_bi) -> float:
        """
        计算信号置信度
        
        基于因素：
        1. 中枢高度（越窄越强）
        2. 回抽幅度（回抽越浅越强）
        3. 离开段力度
        
        Returns:
            0.0 - 1.0
        """
        # 中枢强度
        zhongshu_height = zhongshu.zg - zhongshu.zd
        zhongshu_middle = (zhongshu.zg + zhongshu.zd) / 2
        zhongshu_strength = max(0.1, 1 - zhongshu_height / zhongshu_middle)
        
        # 回抽强度（回抽低点距离 ZG 的距离）
        pullback_margin = pullback_bi.low - zhongshu.zg
        pullback_strength = min(1.0, pullback_margin / zhongshu_middle * 10)
        
        # 综合置信度
        confidence = (zhongshu_strength * 0.5 + pullback_strength * 0.5)
        
        return round(confidence, 2)


# ============================================================================
# 回放引擎
# ============================================================================

class ReplayEngine:
    """
    历史数据回放引擎
    
    核心功能：
    - 逐 bar 推进历史数据
    - 基于缠论结构生成信号
    - 风控检查
    """
    
    def __init__(self, df: pd.DataFrame, config: BacktestConfig = None):
        self.df = df.copy()
        self.config = config or BacktestConfig()
        self.current_index = -1
        self.position = None
        self.trades: List[Trade] = []
        self.capital = self.config.initial_capital
        self.signal_generator = ChanLunSignalGenerator()
    
    def advance(self) -> bool:
        """推进到下一根 bar"""
        if self.current_index >= len(self.df) - 1:
            return False
        
        self.current_index += 1
        
        if self.position:
            self._check_exit_conditions()
        
        return True
    
    def get_available_data(self) -> pd.DataFrame:
        """获取当前可用的数据（不泄露未来）"""
        if self.current_index < 0:
            return pd.DataFrame()
        return self.df.iloc[:self.current_index + 1].copy()
    
    def generate_signal(self) -> Optional[Dict]:
        """生成缠论信号"""
        df_available = self.get_available_data()
        return self.signal_generator.generate(df_available)
    
    def execute_buy(self, signal: Dict, shares: int = None) -> Optional[Trade]:
        """执行买入"""
        if self.position is not None:
            return None
        
        if self.current_index >= len(self.df) - 1:
            return None
        
        next_bar = self.df.iloc[self.current_index + 1]
        entry_price = float(next_bar['open'])
        entry_date = str(next_bar['date'].date()) if hasattr(next_bar['date'], 'date') else str(next_bar['date'])
        
        if shares is None:
            risk_per_trade = getattr(self.config, 'risk_per_trade', 0.02)
            risk_amount = self.capital * risk_per_trade
            shares = int(risk_amount / (entry_price * self.config.stop_loss_pct))
            shares = (shares // 100) * 100
        
        required_capital = entry_price * shares * (1 + self.config.commission_rate)
        if required_capital > self.capital:
            shares = int(self.capital * 0.95 / entry_price / (1 + self.config.commission_rate))
            shares = (shares // 100) * 100
            if shares < 100:
                return None
        
        trade = Trade(
            stock_code=signal.get('stock_code', 'TEST'),
            direction="LONG",
            entry_date=entry_date,
            entry_price=entry_price,
            shares=shares,
            commission=entry_price * shares * self.config.commission_rate
        )
        
        self.position = trade
        self.capital -= trade.commission
        
        return trade
    
    def execute_sell(self, reason: str = "signal") -> Optional[Trade]:
        """执行卖出"""
        if self.position is None:
            return None
        
        if self.current_index >= len(self.df) - 1:
            return None
        
        next_bar = self.df.iloc[self.current_index + 1]
        exit_price = float(next_bar['open'])
        exit_date = str(next_bar['date'].date()) if hasattr(next_bar['date'], 'date') else str(next_bar['date'])
        
        trade = self.position
        trade.exit_date = exit_date
        trade.exit_price = exit_price
        trade.exit_reason = reason
        trade.pnl = (exit_price - trade.entry_price) * trade.shares - trade.commission
        trade.pnl_pct = (exit_price - trade.entry_price) / trade.entry_price * 100
        
        self.capital += exit_price * trade.shares - trade.commission
        self.trades.append(trade)
        self.position = None
        
        return trade
    
    def _check_exit_conditions(self):
        """检查持仓退出条件"""
        if self.position is None:
            return
        
        current = self.df.iloc[self.current_index]
        
        # 止损
        if current['close'] <= self.position.entry_price * (1 - self.config.stop_loss_pct):
            self.execute_sell(reason="stop_loss")
            return
        
        # 止盈
        if current['close'] >= self.position.entry_price * (1 + self.config.take_profit_pct):
            self.execute_sell(reason="take_profit")
            return
        
        # 超时
        max_holding_days = getattr(self.config, 'max_holding_days', 20)
        entry_idx = self._find_entry_index(self.position.entry_date)
        if entry_idx is not None:
            holding_days = self.current_index - entry_idx
            if holding_days >= max_holding_days:
                self.execute_sell(reason="timeout")
    
    def _find_entry_index(self, entry_date: str) -> Optional[int]:
        """找到买入日期对应的索引"""
        for i, row in self.df.iterrows():
            date_str = str(row['date'].date()) if hasattr(row['date'], 'date') else str(row['date'])
            if date_str == entry_date:
                return i
        return None
    
    def run(self) -> Dict:
        """运行完整回放流程"""
        consecutive_losses = 0
        cooldown_counter = 0
        
        self.current_index = -1
        self.position = None
        self.trades = []
        self.capital = self.config.initial_capital
        
        while self.advance():
            if cooldown_counter > 0:
                cooldown_counter -= 1
                continue
            
            signal = self.generate_signal()
            
            if signal and signal['action'] == 'BUY':
                if self.position is None:
                    self.execute_buy(signal)
            
            if self.trades:
                last_trade = self.trades[-1]
                if last_trade.pnl < 0:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0
                
                max_consecutive_losses = getattr(self.config, 'max_consecutive_losses', 3)
                cooldown_days = getattr(self.config, 'cooldown_days', 5)
                if consecutive_losses >= max_consecutive_losses:
                    cooldown_counter = cooldown_days
                    consecutive_losses = 0
        
        if self.position:
            self.execute_sell(reason="end_of_backtest")
        
        metrics = self.get_metrics()
        
        return {
            'metrics': {
                'total_return': metrics.total_return,
                'win_rate': metrics.win_rate,
                'total_trades': metrics.total_trades,
                'avg_trade_return': metrics.avg_trade_return,
                'max_drawdown': metrics.max_drawdown,
                'sharpe_ratio': metrics.sharpe_ratio,
                'final_capital': metrics.final_capital
            },
            'trades': self.trades,
            'config': self.config.__dict__
        }
    
    def get_metrics(self) -> BacktestMetrics:
        """获取回测指标"""
        return calculate_metrics(
            trades=self.trades,
            initial_capital=self.config.initial_capital,
            final_capital=self.capital
        )


# ============================================================================
# 指标计算函数
# ============================================================================

def calculate_metrics(
    trades: List[Trade],
    initial_capital: float,
    final_capital: float = None
) -> BacktestMetrics:
    """计算回测指标"""
    metrics = BacktestMetrics()
    metrics.initial_capital = initial_capital
    metrics.total_trades = len(trades)
    
    if len(trades) == 0:
        metrics.final_capital = initial_capital
        return metrics
    
    winning_trades = [t for t in trades if t.pnl > 0]
    losing_trades = [t for t in trades if t.pnl <= 0]
    
    metrics.winning_trades = len(winning_trades)
    metrics.losing_trades = len(losing_trades)
    metrics.win_rate = (metrics.winning_trades / metrics.total_trades * 100) if metrics.total_trades > 0 else 0
    
    if trades:
        metrics.avg_trade_return = sum(t.pnl_pct for t in trades) / len(trades)
    
    if final_capital:
        metrics.final_capital = final_capital
        metrics.total_return = (final_capital - initial_capital) / initial_capital * 100
    else:
        total_pnl = sum(t.pnl for t in trades)
        metrics.final_capital = initial_capital + total_pnl
        metrics.total_return = total_pnl / initial_capital * 100
    
    total_profit = sum(t.pnl for t in winning_trades)
    total_loss = abs(sum(t.pnl for t in losing_trades))
    metrics.profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    return metrics


def aggregate_multi_stock_results(results, weights: List[float] = None) -> Dict:
    """聚合多股票回测结果"""
    if not results:
        return {'total_trades': 0, 'winning_trades': 0, 'win_rate': 0.0}
    
    if isinstance(results, dict):
        results_list = list(results.values())
    else:
        results_list = results
    
    if weights is None:
        weights = [1.0 / len(results_list)] * len(results_list)
    
    all_trades = []
    for r in results_list:
        if isinstance(r, dict) and 'trades' in r:
            trades = r['trades']
            for t in trades:
                if hasattr(t, 'pnl'):
                    all_trades.append(t)
    
    total_trades = len(all_trades)
    winning_trades = sum(1 for t in all_trades if getattr(t, 'pnl', 0) > 0)
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    avg_return = sum(getattr(t, 'pnl_pct', 0) for t in all_trades) / len(all_trades) if all_trades else 0
    
    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'avg_trade_return': avg_return,
        'trades': all_trades
    }


def compare_backtest_results(baseline: Dict, candidate: Dict) -> Dict:
    """对比两个回测结果"""
    return {
        'metrics_diff': {
            'total_return_diff': candidate['metrics']['total_return'] - baseline['metrics']['total_return'],
            'win_rate_diff': candidate['metrics']['win_rate'] - baseline['metrics']['win_rate'],
            'total_trades_diff': candidate['metrics']['total_trades'] - baseline['metrics']['total_trades']
        },
        'better': candidate['metrics']['total_return'] > baseline['metrics']['total_return']
    }


def save_baseline(metrics, filepath: str = None, path: str = None) -> str:
    """保存基线结果"""
    import json
    import os
    
    if path is not None:
        filepath = path
    
    if filepath is None:
        filepath = '/tmp/baseline.json'
    
    if hasattr(metrics, '__dict__'):
        data = metrics.__dict__
    else:
        data = metrics
    
    baseline = {
        'win_rate': data.get('win_rate', 0),
        'total_return': data.get('total_return', 0),
        'total_trades': data.get('total_trades', 0),
        'max_drawdown': data.get('max_drawdown', 0),
        'sharpe_ratio': data.get('sharpe_ratio', 0),
        'timestamp': datetime.now().isoformat()
    }
    
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    return filepath