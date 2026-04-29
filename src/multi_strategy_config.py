#!/usr/bin/env python3
"""多策略配置系统 - FU-001

管理三类买卖点策略的独立配置。

本模块提供策略配置的数据结构和验证机制:
    - StrategyConfig: 策略配置数据类
    - StrategyConfigManager: 策略配置管理器
    - ConfigurationValidationError: 配置验证异常

Example:
    >>> from src.multi_strategy_config import StrategyConfigManager
    >>> manager = StrategyConfigManager()
    >>> config = manager.get_config('TYPE_1')
    >>> print(config.strategy_id)
    STRATEGY_TYPE_1
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


class ConfigurationValidationError(Exception):
    """配置验证错误"""
    pass


@dataclass
class StrategyConfig:
    """策略配置数据类
    
    封装单个策略的完整配置信息，包括入场条件、出场条件和风控参数。
    
    Attributes:
        strategy_id: 策略唯一标识符
        confidence_threshold: 置信度阈值 (0.0-1.0)
        stop_loss_ratio: 止损比例
        take_profit_ratio: 止盈比例
        position_size: 仓位比例 (0.0-1.0]
        max_holding_hours: 最大持仓时间(小时)
        entry_conditions: 入场条件字典，可选
        exit_conditions: 出场条件字典，可选
        divergence_threshold: 背驰阈值，可选
        market_environment: 适用市场环境列表
    
    Example:
        >>> config = StrategyConfig(
        ...     strategy_id='STRATEGY_TYPE_1',
        ...     confidence_threshold=0.75,
        ...     stop_loss_ratio=0.015,
        ...     take_profit_ratio=0.03,
        ...     position_size=0.05,
        ...     max_holding_hours=24
        ... )
    """
    strategy_id: str
    confidence_threshold: float
    stop_loss_ratio: float
    take_profit_ratio: float
    position_size: float
    max_holding_hours: int
    
    # 入场和出场条件
    entry_conditions: Optional[Dict[str, Any]] = None
    exit_conditions: Optional[Dict[str, Any]] = None
    
    # 其他字段
    divergence_threshold: Optional[float] = None
    market_environment: List[str] = field(default_factory=list)


# 默认配置常量
DEFAULT_CONFIGS = {
    'TYPE_1': StrategyConfig(
        strategy_id='STRATEGY_TYPE_1',
        confidence_threshold=0.75,
        divergence_threshold=0.85,
        stop_loss_ratio=0.015,
        take_profit_ratio=0.03,
        position_size=0.05,
        max_holding_hours=24,
        market_environment=['bull', 'bear'],
        entry_conditions={'type': 'type1_buy', 'min_structure': 'bi'},
        exit_conditions={'stop_loss': True, 'take_profit': True, 'timeout': True}
    ),
    'TYPE_2': StrategyConfig(
        strategy_id='STRATEGY_TYPE_2',
        confidence_threshold=0.50,
        stop_loss_ratio=0.02,
        take_profit_ratio=0.05,
        position_size=0.10,
        max_holding_hours=36,
        market_environment=['bull', 'bear'],
        entry_conditions={'type': 'type2_buy', 'min_structure': 'segment'},
        exit_conditions={'stop_loss': True, 'take_profit': True, 'timeout': True}
    ),
    'TYPE_3': StrategyConfig(
        strategy_id='STRATEGY_TYPE_3',
        confidence_threshold=0.60,
        stop_loss_ratio=0.025,
        take_profit_ratio=0.08,
        position_size=0.25,  # 增加仓位
        max_holding_hours=60,
        market_environment=['bull'],
        entry_conditions={'type': 'type3_buy', 'min_structure': 'zhongshu'},
        exit_conditions={'stop_loss': True, 'take_profit': True, 'timeout': True}
    )
}


class StrategyConfigManager:
    """策略配置管理器
    
    管理三类买卖点策略的配置，提供配置查询和验证功能。
    
    Attributes:
        _configs: 策略配置字典，键为策略类型，值为 StrategyConfig 对象
    """
    
    # 验证所需的字段列表
    _REQUIRED_FIELDS = ['confidence_threshold', 'stop_loss_ratio', 
                        'take_profit_ratio', 'position_size']
    
    def __init__(self) -> None:
        """初始化策略配置管理器，加载默认配置"""
        self._configs: Dict[str, StrategyConfig] = DEFAULT_CONFIGS.copy()
    
    def get_config(self, strategy_type: str) -> Optional[StrategyConfig]:
        """获取指定策略类型的配置
        
        Args:
            strategy_type: 策略类型 ('TYPE_1', 'TYPE_2', 'TYPE_3')
            
        Returns:
            策略配置对象，如果不存在返回 None
            
        Example:
            >>> manager = StrategyConfigManager()
            >>> config = manager.get_config('TYPE_1')
            >>> print(config.confidence_threshold)
        """
        return self._configs.get(strategy_type)
    
    def get_all_configs(self) -> Dict[str, StrategyConfig]:
        """获取所有策略配置
        
        Returns:
            包含所有策略配置的字典副本，键为策略类型
            
        Note:
            返回的是配置的副本，修改不会影响内部配置
        """
        return self._configs.copy()
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置有效性
        
        Args:
            config: 配置字典
            
        Returns:
            验证通过返回 True
            
        Raises:
            ConfigurationValidationError: 配置无效时抛出
            
        Validations:
            - 必需字段存在
            - 数值非负
            - 数值非零
            - 止损比例小于止盈比例
        """
        self._validate_required_fields(config)
        self._validate_non_negative(config)
        self._validate_non_zero(config)
        self._validate_stop_loss_vs_take_profit(config)
        return True
    
    def _validate_required_fields(self, config: Dict[str, Any]) -> None:
        """验证必需字段存在
        
        Args:
            config: 配置字典
            
        Raises:
            ConfigurationValidationError: 缺少必需字段时抛出
        """
        for field_name in self._REQUIRED_FIELDS:
            if field_name not in config:
                raise ConfigurationValidationError(f"缺少必需字段: {field_name}")
    
    def _validate_non_negative(self, config: Dict[str, Any]) -> None:
        """验证数值字段非负
        
        Args:
            config: 配置字典
            
        Raises:
            ConfigurationValidationError: 存在负值时抛出
        """
        for field_name in self._REQUIRED_FIELDS:
            value = config.get(field_name)
            if value is not None and value < 0:
                raise ConfigurationValidationError(
                    f"{field_name} 不能为负值: {value}"
                )
    
    def _validate_non_zero(self, config: Dict[str, Any]) -> None:
        """验证数值字段非零
        
        Args:
            config: 配置字典
            
        Raises:
            ConfigurationValidationError: 存在零值时抛出
        """
        for field_name in self._REQUIRED_FIELDS:
            value = config.get(field_name)
            if value is not None and value == 0:
                raise ConfigurationValidationError(f"{field_name} 不能为零")
    
    def _validate_stop_loss_vs_take_profit(self, config: Dict[str, Any]) -> None:
        """验证止损比例小于止盈比例
        
        Args:
            config: 配置字典
            
        Raises:
            ConfigurationValidationError: 止损 >= 止盈时抛出
        """
        stop_loss = config.get('stop_loss_ratio', 0)
        take_profit = config.get('take_profit_ratio', 0)
        if stop_loss >= take_profit:
            raise ConfigurationValidationError(
                f"止损比例({stop_loss}) 应小于止盈比例({take_profit})"
            )
