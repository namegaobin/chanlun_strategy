#!/usr/bin/env python3
"""
测试 FU-001: 多策略配置系统

测试三类买卖点策略的独立配置管理
"""

import pytest
from dataclasses import FrozenInstanceError
from typing import Dict, Any, List

# 测试目标：验证配置系统的基础功能


class TestMultiStrategyConfig:
    """测试多策略配置系统"""
    
    # -------------------------------------------------------------------------
    # AC-001-001: 加载策略配置
    # -------------------------------------------------------------------------
    
    def test_load_strategy_type1_config(self):
        """AC-001-001: 加载第一类买点策略配置
        
        Given: 系统初始化时
        When: 加载第一类买点策略配置
        Then: 策略配置包含 confidence_threshold, divergence_threshold, 
              market_environment, take_profit_ratio, stop_loss_ratio, 
              position_size, max_holding_hours 等参数
        """
        from src.multi_strategy_config import StrategyConfigManager
        
        manager = StrategyConfigManager()
        config = manager.get_config('TYPE_1')
        
        # 验证必需字段存在
        assert hasattr(config, 'confidence_threshold'), \
            "配置缺少 confidence_threshold 字段"
        assert hasattr(config, 'divergence_threshold'), \
            "配置缺少 divergence_threshold 字段"
        assert hasattr(config, 'market_environment'), \
            "配置缺少 market_environment 字段"
        assert hasattr(config, 'take_profit_ratio'), \
            "配置缺少 take_profit_ratio 字段"
        assert hasattr(config, 'stop_loss_ratio'), \
            "配置缺少 stop_loss_ratio 字段"
        assert hasattr(config, 'position_size'), \
            "配置缺少 position_size 字段"
        assert hasattr(config, 'max_holding_hours'), \
            "配置缺少 max_holding_hours 字段"
        
        # 验证第一类买点策略的具体值
        assert config.confidence_threshold >= 0.70, \
            f"第一类买点置信度阈值应 >= 70%，实际: {config.confidence_threshold}"
        assert config.divergence_threshold is not None, \
            "第一类买点需要背驰阈值"
    
    def test_load_strategy_type2_config(self):
        """AC-001-001: 加载第二类买点策略配置
        
        Given: 系统初始化时
        When: 加载第二类买点策略配置
        Then: 返回第二类买点的独立配置
        """
        from src.multi_strategy_config import StrategyConfigManager
        
        manager = StrategyConfigManager()
        config = manager.get_config('TYPE_2')
        
        assert config is not None, "第二类买点配置不应为 None"
        assert hasattr(config, 'confidence_threshold'), \
            "配置缺少 confidence_threshold 字段"
        assert hasattr(config, 'stop_loss_ratio'), \
            "配置缺少 stop_loss_ratio 字段"
        assert hasattr(config, 'take_profit_ratio'), \
            "配置缺少 take_profit_ratio 字段"
    
    def test_load_strategy_type3_config(self):
        """AC-001-001: 加载第三类买点策略配置
        
        Given: 系统初始化时
        When: 加载第三类买点策略配置
        Then: 返回第三类买点的独立配置
        """
        from src.multi_strategy_config import StrategyConfigManager
        
        manager = StrategyConfigManager()
        config = manager.get_config('TYPE_3')
        
        assert config is not None, "第三类买点配置不应为 None"
        assert hasattr(config, 'confidence_threshold'), \
            "配置缺少 confidence_threshold 字段"
        assert hasattr(config, 'stop_loss_ratio'), \
            "配置缺少 stop_loss_ratio 字段"
        assert hasattr(config, 'take_profit_ratio'), \
            "配置缺少 take_profit_ratio 字段"
    
    # -------------------------------------------------------------------------
    # AC-001-003: 配置验证
    # -------------------------------------------------------------------------
    
    def test_invalid_config_raises_error(self):
        """AC-001-003: 无效配置应抛出异常
        
        Given: 策略配置包含 stop_loss_ratio = 0.05, take_profit_ratio = 0.03
        When: 验证配置有效性
        Then: 抛出 ConfigurationValidationError，因为止损比例不应大于止盈比例
        """
        from src.multi_strategy_config import (
            StrategyConfigManager, 
            ConfigurationValidationError
        )
        
        manager = StrategyConfigManager()
        
        # 创建无效配置：止损 > 止盈
        invalid_config = {
            'strategy_type': 'TYPE_1',
            'confidence_threshold': 75.0,
            'stop_loss_ratio': 0.05,  # 5%
            'take_profit_ratio': 0.03,  # 3% - 比止损小
            'position_size': 0.1,
            'max_holding_hours': 24
        }
        
        # 应该抛出 ConfigurationValidationError
        with pytest.raises(ConfigurationValidationError) as exc_info:
            manager.validate_config(invalid_config)
        
        # 验证错误信息包含原因
        assert 'stop_loss' in str(exc_info.value).lower() or \
               '止损' in str(exc_info.value), \
            "错误信息应提及止损问题"
    
    def test_negative_values_raises_error(self):
        """AC-001-003: 负值配置应抛出异常
        
        Given: 策略配置包含负值
        When: 验证配置有效性
        Then: 抛出 ConfigurationValidationError
        """
        from src.multi_strategy_config import (
            StrategyConfigManager,
            ConfigurationValidationError
        )
        
        manager = StrategyConfigManager()
        
        invalid_config = {
            'strategy_type': 'TYPE_1',
            'confidence_threshold': -10.0,  # 负值
            'stop_loss_ratio': 0.02,
            'take_profit_ratio': 0.05,
            'position_size': 0.1,
            'max_holding_hours': 24
        }
        
        with pytest.raises(ConfigurationValidationError):
            manager.validate_config(invalid_config)
    
    def test_zero_values_raises_error(self):
        """AC-001-003: 零值配置应抛出异常
        
        Given: 策略配置包含零值
        When: 验证配置有效性
        Then: 抛出 ConfigurationValidationError
        """
        from src.multi_strategy_config import (
            StrategyConfigManager,
            ConfigurationValidationError
        )
        
        manager = StrategyConfigManager()
        
        invalid_config = {
            'strategy_type': 'TYPE_1',
            'confidence_threshold': 75.0,
            'stop_loss_ratio': 0.0,  # 零值
            'take_profit_ratio': 0.05,
            'position_size': 0.0,  # 零值
            'max_holding_hours': 24
        }
        
        with pytest.raises(ConfigurationValidationError):
            manager.validate_config(invalid_config)
    
    # -------------------------------------------------------------------------
    # AC-001-002: 查询所有策略配置
    # -------------------------------------------------------------------------
    
    def test_get_all_configs(self):
        """AC-001-002: 查询所有策略配置
        
        Given: 三套策略配置已存在
        When: 查询所有策略配置
        Then: 返回三个独立的策略配置对象，每个对象有唯一标识符
        """
        from src.multi_strategy_config import StrategyConfigManager
        
        manager = StrategyConfigManager()
        all_configs = manager.get_all_configs()
        
        # 验证返回三个配置
        assert len(all_configs) == 3, \
            f"应有 3 套策略配置，实际: {len(all_configs)}"
        
        # 验证每个配置有唯一标识符
        strategy_ids = [config.strategy_id for config in all_configs.values()]
        assert 'STRATEGY_TYPE_1' in strategy_ids, "缺少 STRATEGY_TYPE_1"
        assert 'STRATEGY_TYPE_2' in strategy_ids, "缺少 STRATEGY_TYPE_2"
        assert 'STRATEGY_TYPE_3' in strategy_ids, "缺少 STRATEGY_TYPE_3"
        
        # 验证标识符唯一
        assert len(set(strategy_ids)) == 3, "策略标识符应该唯一"
    
    # -------------------------------------------------------------------------
    # INV-001: 配置完整性
    # -------------------------------------------------------------------------
    
    def test_config_has_required_fields(self):
        """INV-001: 每个策略配置必须包含完整的入场条件和出场条件"""
        from src.multi_strategy_config import StrategyConfigManager
        
        manager = StrategyConfigManager()
        
        for strategy_type in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
            config = manager.get_config(strategy_type)
            
            # 入场条件
            assert hasattr(config, 'entry_conditions'), \
                f"{strategy_type} 缺少入场条件"
            assert config.entry_conditions is not None, \
                f"{strategy_type} 入场条件不应为 None"
            
            # 出场条件
            assert hasattr(config, 'exit_conditions'), \
                f"{strategy_type} 缺少出场条件"
            assert config.exit_conditions is not None, \
                f"{strategy_type} 出场条件不应为 None"
    
    # -------------------------------------------------------------------------
    # INV-002: 止损 < 止盈
    # -------------------------------------------------------------------------
    
    def test_stop_loss_less_than_take_profit(self):
        """INV-002: 止损比例必须小于止盈比例"""
        from src.multi_strategy_config import StrategyConfigManager
        
        manager = StrategyConfigManager()
        
        for strategy_type in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
            config = manager.get_config(strategy_type)
            
            assert config.stop_loss_ratio < config.take_profit_ratio, \
                f"{strategy_type} 止损比例({config.stop_loss_ratio}) " \
                f"应小于止盈比例({config.take_profit_ratio})"
    
    # -------------------------------------------------------------------------
    # INV-004: 置信度阈值范围
    # -------------------------------------------------------------------------
    
    def test_confidence_threshold_in_valid_range(self):
        """INV-004: 置信度阈值必须在 [0.0, 1.0] 区间内"""
        from src.multi_strategy_config import StrategyConfigManager
        
        manager = StrategyConfigManager()
        
        for strategy_type in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
            config = manager.get_config(strategy_type)
            
            assert 0.0 <= config.confidence_threshold <= 1.0, \
                f"{strategy_type} 置信度阈值({config.confidence_threshold}) " \
                f"应在 [0.0, 1.0] 范围内"
    
    # -------------------------------------------------------------------------
    # INV-005: 仓位比例范围
    # -------------------------------------------------------------------------
    
    def test_position_size_in_valid_range(self):
        """INV-005: 仓位比例必须满足 0 < position_size <= 1.0"""
        from src.multi_strategy_config import StrategyConfigManager
        
        manager = StrategyConfigManager()
        
        for strategy_type in ['TYPE_1', 'TYPE_2', 'TYPE_3']:
            config = manager.get_config(strategy_type)
            
            assert 0 < config.position_size <= 1.0, \
                f"{strategy_type} 仓位比例({config.position_size}) " \
                f"应在 (0, 1.0] 范围内"
