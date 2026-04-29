#!/usr/bin/env python3
"""
多策略系统 - 按买卖点类型分拆独立策略

设计思路：
- 第一类买卖点（一买/一卖）：趋势反转信号，风险最高，需要最严格的确认
- 第二类买卖点（二买/二卖）：趋势确认后的回踩入场，风险中等
- 第三类买卖点（三买/三卖）：趋势延续信号，顺势而为，风险相对较低

每套策略独立配置：
1. 入场条件（置信度、背驰阈值、市场环境）
2. 出场条件（止盈、止损、持仓时间）
3. 仓位管理
4. 风险控制
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import pandas as pd
import numpy as np


class StrategyType(Enum):
    """策略类型"""
    TYPE_1 = "type_1"  # 第一类买卖点策略
    TYPE_2 = "type_2"  # 第二类买卖点策略
    TYPE_3 = "type_3"  # 第三类买卖点策略


@dataclass
class StrategyConfig:
    """策略配置"""
    # 基本信息
    name: str
    description: str
    signal_types: List[str]  # 对应的信号类型
    
    # 入场条件
    min_confidence: float = 70.0  # 最低置信度
    require_divergence: bool = False  # 是否需要背驰确认
    min_divergence_ratio: float = 0.9  # 最小背驰力度比
    
    # 市场环境过滤
    allowed_environments: List[str] = field(default_factory=lambda: ['neutral'])
    preferred_trend: Optional[str] = None  # 偏好的趋势方向
    
    # 出场条件
    stop_loss_pct: float = 2.0  # 止损百分比
    take_profit_pct: float = 5.0  # 止盈百分比
    max_hold_bars: int = 30  # 最大持仓K线数
    
    # 仓位管理
    position_size_pct: float = 10.0  # 单次仓位百分比
    max_total_position: float = 30.0  # 最大总仓位
    
    # 风险控制
    max_daily_trades: int = 3  # 每日最大交易次数
    max_consecutive_losses: int = 3  # 最大连续亏损次数
    cooldown_after_loss: int = 5  # 亏损后冷却期（K线数）


# =============================================================================
# 三套独立策略配置
# =============================================================================

STRATEGY_CONFIGS = {
    # -------------------------------------------------------------------------
    # 第一类买卖点策略：趋势反转（抄底摸顶）
    # -------------------------------------------------------------------------
    StrategyType.TYPE_1: StrategyConfig(
        name="第一类买卖点策略",
        description="趋势反转信号，背驰确认，高置信度要求",
        signal_types=['buy_1', 'sell_1'],
        
        # 入场条件 - 最严格
        min_confidence=75.0,  # 需要高置信度
        require_divergence=True,  # 必须有背驰确认
        min_divergence_ratio=0.85,  # 力度比 < 0.85
        
        # 市场环境 - 趋势市才能抄底摸顶
        allowed_environments=['trending'],
        preferred_trend=None,  # 不限方向
        
        # 出场条件 - 快速止盈止损
        stop_loss_pct=1.5,  # 较小止损（趋势反转风险大）
        take_profit_pct=3.0,  # 较小止盈（快进快出）
        max_hold_bars=20,  # 较短持仓
        
        # 仓位管理 - 轻仓
        position_size_pct=5.0,  # 单次5%仓位
        max_total_position=15.0,  # 总仓位不超过15%
        
        # 风险控制 - 严格
        max_daily_trades=2,  # 每日最多2次
        max_consecutive_losses=2,  # 连亏2次暂停
        cooldown_after_loss=10  # 冷却期较长
    ),
    
    # -------------------------------------------------------------------------
    # 第二类买卖点策略：趋势确认后的回踩
    # -------------------------------------------------------------------------
    StrategyType.TYPE_2: StrategyConfig(
        name="第二类买卖点策略",
        description="趋势确认后的回踩入场，安全性较高",
        signal_types=['buy_2', 'sell_2'],
        
        # 入场条件 - 中等
        min_confidence=65.0,
        require_divergence=False,  # 不需要背驰
        min_divergence_ratio=0.9,
        
        # 市场环境 - 趋势确认后
        allowed_environments=['trending', 'consolidation'],
        preferred_trend='up',  # 偏好上涨趋势
        
        # 出场条件 - 中等
        stop_loss_pct=2.0,
        take_profit_pct=5.0,
        max_hold_bars=30,
        
        # 仓位管理 - 中等
        position_size_pct=10.0,
        max_total_position=30.0,
        
        # 风险控制 - 中等
        max_daily_trades=3,
        max_consecutive_losses=3,
        cooldown_after_loss=5
    ),
    
    # -------------------------------------------------------------------------
    # 第三类买卖点策略：趋势延续（顺势而为）
    # -------------------------------------------------------------------------
    StrategyType.TYPE_3: StrategyConfig(
        name="第三类买卖点策略",
        description="趋势延续信号，顺势而为，风险相对较低",
        signal_types=['buy_3', 'sell_3'],
        
        # 入场条件 - 相对宽松
        min_confidence=60.0,  # 较低置信度要求
        require_divergence=False,
        min_divergence_ratio=0.9,
        
        # 市场环境 - 顺势
        allowed_environments=['trending'],
        preferred_trend='up',  # 顺势
        
        # 出场条件 - 较大空间
        stop_loss_pct=2.5,  # 较大止损
        take_profit_pct=8.0,  # 较大止盈
        max_hold_bars=50,  # 较长持仓
        
        # 仓位管理 - 可重仓
        position_size_pct=15.0,
        max_total_position=50.0,
        
        # 风险控制 - 相对宽松
        max_daily_trades=5,
        max_consecutive_losses=4,
        cooldown_after_loss=3
    )
}


# =============================================================================
# 策略执行器
# =============================================================================

class MultiStrategyExecutor:
    """多策略执行器
    
    管理三套独立策略的执行、风控和统计
    """
    
    def __init__(self, configs: Dict[StrategyType, StrategyConfig] = None):
        """初始化
        
        Args:
            configs: 策略配置字典，默认使用 STRATEGY_CONFIGS
        """
        self.configs = configs or STRATEGY_CONFIGS
        
        # 策略状态
        self.strategy_states = {
            st: {
                'trades_today': 0,
                'consecutive_losses': 0,
                'last_trade_time': None,
                'in_cooldown': False,
                'cooldown_end_bar': 0
            }
            for st in StrategyType
        }
        
        # 统计数据
        self.stats = {
            st: {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'total_profit': 0.0,
                'win_rate': 0.0
            }
            for st in StrategyType
        }
    
    def filter_signal_by_strategy(
        self,
        signal: Any,
        market_env: Dict[str, Any],
        current_bar: int
    ) -> Optional[StrategyType]:
        """根据策略过滤信号
        
        Args:
            signal: 信号对象
            market_env: 市场环境
            current_bar: 当前K线索引
            
        Returns:
            匹配的策略类型，None表示不符合任何策略
        """
        signal_type_str = signal.signal_type.value
        
        # 遍历三套策略
        for strategy_type, config in self.configs.items():
            # 1. 检查信号类型是否匹配
            if signal_type_str not in config.signal_types:
                continue
            
            # 2. 检查置信度
            if signal.confidence < config.min_confidence:
                continue
            
            # 3. 检查背驰（如果需要）
            if config.require_divergence:
                strength_ratio = signal.metadata.get('strength_ratio', 1.0)
                if strength_ratio >= config.min_divergence_ratio:
                    continue
            
            # 4. 检查市场环境
            if market_env.get('environment') not in config.allowed_environments:
                continue
            
            # 5. 检查趋势偏好
            if config.preferred_trend:
                trend = market_env.get('trend_direction')
                if trend != config.preferred_trend:
                    continue
            
            # 6. 检查策略状态
            state = self.strategy_states[strategy_type]
            if state['in_cooldown'] and current_bar < state['cooldown_end_bar']:
                continue
            
            if state['trades_today'] >= config.max_daily_trades:
                continue
            
            if state['consecutive_losses'] >= config.max_consecutive_losses:
                continue
            
            # 符合该策略
            return strategy_type
        
        return None
    
    def execute_signal(
        self,
        signal: Any,
        strategy_type: StrategyType,
        market_env: Dict[str, Any],
        current_bar: int,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """执行信号
        
        Args:
            signal: 信号对象
            strategy_type: 策略类型
            market_env: 市场环境
            current_bar: 当前K线索引
            df: K线数据
            
        Returns:
            交易结果
        """
        config = self.configs[strategy_type]
        state = self.strategy_states[strategy_type]
        
        # 模拟交易
        entry_price = signal.price
        entry_bar = signal.index
        
        # 计算止损止盈价位
        if signal.signal_type.value.startswith('buy'):
            stop_loss = entry_price * (1 - config.stop_loss_pct / 100)
            take_profit = entry_price * (1 + config.take_profit_pct / 100)
        else:
            stop_loss = entry_price * (1 + config.stop_loss_pct / 100)
            take_profit = entry_price * (1 - config.take_profit_pct / 100)
        
        # 模拟持仓
        exit_price = None
        exit_reason = None
        hold_bars = 0
        
        for i in range(entry_bar + 1, min(entry_bar + config.max_hold_bars + 1, len(df))):
            hold_bars = i - entry_bar
            
            high = df.iloc[i]['high']
            low = df.iloc[i]['low']
            
            # 检查止损
            if signal.signal_type.value.startswith('buy'):
                if low <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = 'stop_loss'
                    break
                # 检查止盈
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
            exit_price = df.iloc[min(entry_bar + config.max_hold_bars, len(df) - 1)]['close']
            exit_reason = 'timeout'
        
        # 计算盈亏
        if signal.signal_type.value.startswith('buy'):
            profit_pct = (exit_price - entry_price) / entry_price * 100
        else:
            profit_pct = (entry_price - exit_price) / entry_price * 100
        
        # 更新统计
        state['trades_today'] += 1
        state['last_trade_time'] = current_bar
        
        if profit_pct > 0:
            state['consecutive_losses'] = 0
            self.stats[strategy_type]['wins'] += 1
        else:
            state['consecutive_losses'] += 1
            if state['consecutive_losses'] >= config.max_consecutive_losses:
                state['in_cooldown'] = True
                state['cooldown_end_bar'] = current_bar + config.cooldown_after_loss
        
        self.stats[strategy_type]['total_trades'] += 1
        self.stats[strategy_type]['total_profit'] += profit_pct
        
        # 更新胜率
        total = self.stats[strategy_type]['total_trades']
        wins = self.stats[strategy_type]['wins']
        self.stats[strategy_type]['win_rate'] = wins / total * 100 if total > 0 else 0
        
        return {
            'strategy_type': strategy_type.value,
            'signal_type': signal.signal_type.value,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'entry_bar': entry_bar,
            'exit_reason': exit_reason,
            'hold_bars': hold_bars,
            'profit_pct': profit_pct,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
    
    def reset_daily(self):
        """重置每日统计"""
        for strategy_type in StrategyType:
            self.strategy_states[strategy_type]['trades_today'] = 0
    
    def get_stats_report(self) -> str:
        """生成统计报告"""
        lines = []
        lines.append("=" * 80)
        lines.append("多策略系统统计报告")
        lines.append("=" * 80)
        
        for strategy_type in StrategyType:
            config = self.configs[strategy_type]
            stats = self.stats[strategy_type]
            
            lines.append(f"\n【{config.name}】")
            lines.append(f"  描述: {config.description}")
            lines.append(f"  总交易次数: {stats['total_trades']}")
            lines.append(f"  胜率: {stats['win_rate']:.1f}%")
            lines.append(f"  总收益: {stats['total_profit']:.2f}%")
            
            if stats['total_trades'] > 0:
                avg_profit = stats['total_profit'] / stats['total_trades']
                lines.append(f"  平均单笔收益: {avg_profit:.2f}%")
        
        return "\n".join(lines)


# =============================================================================
# 策略优化器
# =============================================================================

class StrategyOptimizer:
    """策略参数优化器
    
    对每套策略独立优化参数
    """
    
    def __init__(self, strategy_type: StrategyType):
        """初始化
        
        Args:
            strategy_type: 要优化的策略类型
        """
        self.strategy_type = strategy_type
        self.base_config = STRATEGY_CONFIGS[strategy_type]
    
    def optimize(
        self,
        df: pd.DataFrame,
        signals: List[Any],
        market_envs: List[Dict],
        param_grid: Dict[str, List]
    ) -> Dict[str, Any]:
        """网格搜索优化
        
        Args:
            df: K线数据
            signals: 信号列表
            market_envs: 市场环境列表
            param_grid: 参数网格
            
        Returns:
            最优参数和结果
        """
        best_params = None
        best_score = -float('inf')
        best_stats = None
        
        # 生成参数组合
        from itertools import product
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        for combo in product(*param_values):
            params = dict(zip(param_names, combo))
            
            # 创建测试配置
            test_config = StrategyConfig(
                name=self.base_config.name,
                description=self.base_config.description,
                signal_types=self.base_config.signal_types,
                **params
            )
            
            # 创建测试执行器
            test_configs = {self.strategy_type: test_config}
            executor = MultiStrategyExecutor(test_configs)
            
            # 执行回测
            for i, (signal, market_env) in enumerate(zip(signals, market_envs)):
                matched_strategy = executor.filter_signal_by_strategy(
                    signal, market_env, signal.index
                )
                
                if matched_strategy == self.strategy_type:
                    executor.execute_signal(
                        signal, self.strategy_type, market_env, signal.index, df
                    )
            
            # 计算得分
            stats = executor.stats[self.strategy_type]
            if stats['total_trades'] > 0:
                # 综合得分 = 胜率 * 0.4 + 收益 * 0.6
                score = stats['win_rate'] * 0.4 + stats['total_profit'] * 0.6
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_stats = stats
        
        return {
            'strategy_type': self.strategy_type.value,
            'best_params':