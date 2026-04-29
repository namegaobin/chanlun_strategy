#!/usr/bin/env python3
"""
测试 FU-003: 策略执行器

测试策略的入场和出场逻辑，管理订单生命周期，处理止损止盈触发
"""

import pytest
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


class TestStrategyExecutor:
    """测试策略执行器"""
    
    # -------------------------------------------------------------------------
    # AC-003-001: 入场执行
    # -------------------------------------------------------------------------
    
    def test_execute_entry_success(self):
        """AC-003-001: 成功执行入场
        
        Given: 策略选择器返回 STRATEGY_TYPE_1，且市场条件满足入场条件
        When: 调用 execute_entry(strategy, market_data) 方法
        Then: 创建入场订单并返回订单ID，更新持仓状态为 OPEN
        """
        from src.strategy_executor import (
            StrategyExecutor,
            StrategyConfig,
            MarketData
        )
        
        # 创建策略配置
        config = StrategyConfig(
            strategy_id='STRATEGY_TYPE_1',
            confidence_threshold=0.75,
            stop_loss_ratio=0.02,
            take_profit_ratio=0.05,
            position_size=0.1,
            max_holding_hours=24
        )
        
        executor = StrategyExecutor(config)
        
        # 创建市场数据
        market_data = MarketData(
            symbol='BTCUSDT',
            price=100.0,
            volume=1000.0,
            timestamp=datetime.now()
        )
        
        # 执行入场
        result = executor.execute_entry(config, market_data)
        
        # 验证结果
        assert result is not None, "入场结果不应为 None"
        assert hasattr(result, 'order_id'), "结果应包含 order_id"
        assert result.order_id is not None, "order_id 不应为 None"
        
        # 验证持仓状态
        position = executor.get_position()
        assert position is not None, "应有持仓记录"
        assert position.status == 'OPEN', f"持仓状态应为 OPEN，实际: {position.status}"
    
    # -------------------------------------------------------------------------
    # AC-003-002: 止盈触发
    # -------------------------------------------------------------------------
    
    def test_take_profit_trigger(self):
        """AC-003-002: 止盈触发
        
        Given: 持仓处于盈利状态，盈利比例达到 take_profit_ratio
        When: 调用 execute_exit(position, exit_reason='take_profit') 方法
        Then: 平仓并记录盈利，更新持仓状态为 CLOSED
        """
        from src.strategy_executor import (
            StrategyExecutor,
            StrategyConfig,
            Position
        )
        
        config = StrategyConfig(
            strategy_id='STRATEGY_TYPE_1',
            confidence_threshold=0.75,
            stop_loss_ratio=0.02,
            take_profit_ratio=0.05,
            position_size=0.1,
            max_holding_hours=24
        )
        
        executor = StrategyExecutor(config)
        
        # 创建持仓（模拟入场价格 100，当前价格 105，盈利 5%）
        position = Position(
            position_id='POS-001',
            strategy_id='STRATEGY_TYPE_1',
            symbol='BTCUSDT',
            entry_price=100.0,
            current_price=105.0,  # 5% 盈利
            size=0.1,
            status='OPEN',
            entry_time=datetime.now() - timedelta(hours=1)
        )
        
        # 执行出场
        result = executor.execute_exit(position, exit_reason='take_profit')
        
        # 验证结果
        assert result is not None, "出场结果不应为 None"
        assert result.status == 'CLOSED', f"持仓状态应为 CLOSED，实际: {result.status}"
        assert result.exit_reason == 'take_profit', \
            f"出场原因应为 take_profit，实际: {result.exit_reason}"
        
        # 验证盈利记录
        assert result.profit_pct > 0, "应有盈利记录"
    
    # -------------------------------------------------------------------------
    # AC-003-003: 止损触发
    # -------------------------------------------------------------------------
    
    def test_stop_loss_trigger(self):
        """AC-003-003: 止损触发
        
        Given: 持仓处于亏损状态，亏损比例达到 stop_loss_ratio
        When: 调用 execute_exit(position, exit_reason='stop_loss') 方法
        Then: 平仓并记录亏损，更新持仓状态为 CLOSED
        """
        from src.strategy_executor import (
            StrategyExecutor,
            StrategyConfig,
            Position
        )
        
        config = StrategyConfig(
            strategy_id='STRATEGY_TYPE_1',
            confidence_threshold=0.75,
            stop_loss_ratio=0.02,
            take_profit_ratio=0.05,
            position_size=0.1,
            max_holding_hours=24
        )
        
        executor = StrategyExecutor(config)
        
        # 创建持仓（入场价格 100，当前价格 98，亏损 2%）
        position = Position(
            position_id='POS-002',
            strategy_id='STRATEGY_TYPE_1',
            symbol='BTCUSDT',
            entry_price=100.0,
            current_price=98.0,  # 2% 亏损
            size=0.1,
            status='OPEN',
            entry_time=datetime.now() - timedelta(hours=1)
        )
        
        result = executor.execute_exit(position, exit_reason='stop_loss')
        
        assert result is not None, "出场结果不应为 None"
        assert result.status == 'CLOSED', f"持仓状态应为 CLOSED，实际: {result.status}"
        assert result.exit_reason == 'stop_loss', \
            f"出场原因应为 stop_loss，实际: {result.exit_reason}"
        assert result.profit_pct < 0, "应有亏损记录"
    
    # -------------------------------------------------------------------------
    # AC-003-004: 最大持仓时间
    # -------------------------------------------------------------------------
    
    def test_max_holding_time_exceeded(self):
        """AC-003-004: 最大持仓时间超时
        
        Given: 持仓时间超过 max_holding_hours
        When: 检查持仓时间
        Then: 触发强制平仓逻辑
        """
        from src.strategy_executor import (
            StrategyExecutor,
            StrategyConfig,
            Position
        )
        
        config = StrategyConfig(
            strategy_id='STRATEGY_TYPE_1',
            confidence_threshold=0.75,
            stop_loss_ratio=0.02,
            take_profit_ratio=0.05,
            position_size=0.1,
            max_holding_hours=24
        )
        
        executor = StrategyExecutor(config)
        
        # 创建持仓（超过 24 小时）
        position = Position(
            position_id='POS-003',
            strategy_id='STRATEGY_TYPE_1',
            symbol='BTCUSDT',
            entry_price=100.0,
            current_price=102.0,
            size=0.1,
            status='OPEN',
            entry_time=datetime.now() - timedelta(hours=25)  # 超过 24 小时
        )
        
        # 检查出场条件
        exit_reason = executor.check_exit_conditions(position)
        
        assert exit_reason == 'max_holding_time', \
            f"应触发最大持仓时间平仓，实际: {exit_reason}"
        
        # 执行强制平仓
        result = executor.execute_exit(position, exit_reason='max_holding_time')
        
        assert result.status == 'CLOSED', "应平仓"
        assert result.exit_reason == 'max_holding_time', \
            f"出场原因应为 max_holding_time，实际: {result.exit_reason}"
