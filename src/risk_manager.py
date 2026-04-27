"""
风控模块
功能：单股仓位控制、总仓控制、动态止损止盈
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class PositionAction(Enum):
    """仓位操作"""
    OPEN = "open"       # 开仓
    ADD = "add"         # 加仓
    REDUCE = "reduce"   # 减仓
    CLOSE = "close"     # 平仓


@dataclass
class Position:
    """持仓"""
    stock_code: str
    shares: int
    avg_price: float
    current_price: float
    highest_price: float  # 持仓期间最高价
    stop_loss_price: float
    take_profit_price: float
    pnl_pct: float  # 浮盈比例


@dataclass
class RiskConfig:
    """风控配置"""
    max_single_position: float = 0.20      # 单股最大仓位
    max_total_position: float = 0.80       # 总仓最大仓位
    max_stocks: int = 10                    # 最大持仓股票数
    base_stop_loss: float = 0.05            # 基础止损比例
    base_take_profit: float = 0.15          # 基础止盈比例
    trailing_stop_pct: float = 0.05         # 跟踪止损比例
    profit_lock_threshold: float = 0.10     # 盈利锁定阈值
    profit_lock_stop: float = 0.03          # 盈利锁定止损


class RiskManager:
    """风控管理器"""
    
    def __init__(
        self,
        total_capital: float,
        config: Optional[RiskConfig] = None
    ):
        """
        Args:
            total_capital: 总资金
            config: 风控配置
        """
        self.total_capital = total_capital
        self.config = config or RiskConfig()
        
        self.positions: Dict[str, Position] = {}
        self.cash = total_capital
        
    def calculate_position_size(
        self,
        stock_code: str,
        price: float,
        risk_factor: float = 1.0
    ) -> int:
        """
        计算仓位大小
        
        Args:
            stock_code: 股票代码
            price: 买入价格
            risk_factor: 风险系数（0-1）
            
        Returns:
            可买股数
        """
        # 计算单股最大仓位金额
        max_single_amount = self.total_capital * self.config.max_single_position
        
        # 检查总仓限制
        current_total = self.get_total_position_value()
        max_total = self.total_capital * self.config.max_total_position
        remaining = max_total - current_total
        
        # 取最小值
        available_amount = min(max_single_amount, remaining) * risk_factor
        available_amount = min(available_amount, self.cash)
        
        # 计算股数（取整到100股）
        shares = int(available_amount / price / 100) * 100
        
        return shares
        
    def can_open_position(self, stock_code: str) -> Tuple[bool, str]:
        """
        检查是否可以开仓
        
        Args:
            stock_code: 股票代码
            
        Returns:
            (是否可以, 原因)
        """
        # 检查是否已持仓
        if stock_code in self.positions:
            return False, f"Already holding {stock_code}"
            
        # 检查股票数量限制
        if len(self.positions) >= self.config.max_stocks:
            return False, f"Max stocks limit ({self.config.max_stocks}) reached"
            
        # 检查总仓限制
        current_pct = self.get_total_position_pct()
        if current_pct >= self.config.max_total_position:
            return False, f"Max total position ({self.config.max_total_position*100}%) reached"
            
        # 检查现金
        if self.cash < self.total_capital * 0.05:  # 至少5%现金
            return False, "Insufficient cash"
            
        return True, "Can open position"
        
    def open_position(
        self,
        stock_code: str,
        shares: int,
        price: float
    ) -> Optional[Position]:
        """
        开仓
        
        Args:
            stock_code: 股票代码
            shares: 股数
            price: 价格
            
        Returns:
            Position对象
        """
        can_open, reason = self.can_open_position(stock_code)
        if not can_open:
            return None
            
        amount = shares * price
        if amount > self.cash:
            return None
            
        # 扣除现金
        self.cash -= amount
        
        # 计算止损止盈价
        stop_loss = price * (1 - self.config.base_stop_loss)
        take_profit = price * (1 + self.config.base_take_profit)
        
        position = Position(
            stock_code=stock_code,
            shares=shares,
            avg_price=price,
            current_price=price,
            highest_price=price,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            pnl_pct=0
        )
        
        self.positions[stock_code] = position
        return position
        
    def update_position(self, stock_code: str, current_price: float):
        """
        更新持仓
        
        Args:
            stock_code: 股票代码
            current_price: 当前价格
        """
        if stock_code not in self.positions:
            return
            
        pos = self.positions[stock_code]
        pos.current_price = current_price
        
        # 更新最高价
        if current_price > pos.highest_price:
            pos.highest_price = current_price
            
        # 更新浮盈
        pos.pnl_pct = (current_price - pos.avg_price) / pos.avg_price
        
        # 动态调整止损
        pos.stop_loss_price = self.calculate_dynamic_stop_loss(pos)
        
    def calculate_dynamic_stop_loss(self, position: Position) -> float:
        """
        计算动态止损价
        
        规则：
        1. 盈利超过 profit_lock_threshold 时，止损上移到保本线
        2. 盈利继续增加，使用跟踪止损
        
        Args:
            position: 持仓
            
        Returns:
            止损价
        """
        buy_price = position.avg_price
        highest_price = position.highest_price
        pnl_pct = position.pnl_pct
        
        # 盈利锁定
        if pnl_pct > self.config.profit_lock_threshold:
            # 止损上移到保本线或盈利锁定止损
            base_stop = buy_price * (1 + self.config.profit_lock_stop)
            trailing_stop = highest_price * (1 - self.config.trailing_stop_pct)
            return max(base_stop, trailing_stop)
            
        # 未达盈利锁定，使用基础止损
        return buy_price * (1 - self.config.base_stop_loss)
        
    def check_stop_loss(self, stock_code: str, current_price: float) -> bool:
        """
        检查是否触发止损
        
        Args:
            stock_code: 股票代码
            current_price: 当前价格
            
        Returns:
            是否触发
        """
        if stock_code not in self.positions:
            return False
            
        self.update_position(stock_code, current_price)
        pos = self.positions[stock_code]
        
        return current_price <= pos.stop_loss_price
        
    def check_take_profit(self, stock_code: str, current_price: float) -> bool:
        """
        检查是否触发止盈
        
        Args:
            stock_code: 股票代码
            current_price: 当前价格
            
        Returns:
            是否触发
        """
        if stock_code not in self.positions:
            return False
            
        pos = self.positions[stock_code]
        return current_price >= pos.take_profit_price
        
    def close_position(self, stock_code: str, price: float) -> Optional[Dict]:
        """
        平仓
        
        Args:
            stock_code: 股票代码
            price: 卖出价格
            
        Returns:
            交易结果
        """
        if stock_code not in self.positions:
            return None
            
        pos = self.positions[stock_code]
        
        # 计算盈亏
        sell_amount = pos.shares * price
        buy_amount = pos.shares * pos.avg_price
        pnl = sell_amount - buy_amount
        pnl_pct = (price - pos.avg_price) / pos.avg_price * 100
        
        # 回收现金
        self.cash += sell_amount
        
        # 删除持仓
        del self.positions[stock_code]
        
        return {
            'stock_code': stock_code,
            'shares': pos.shares,
            'buy_price': pos.avg_price,
            'sell_price': price,
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 2)
        }
        
    def get_total_position_value(self) -> float:
        """获取总持仓市值"""
        return sum(
            pos.shares * pos.current_price 
            for pos in self.positions.values()
        )
        
    def get_total_position_pct(self) -> float:
        """获取总仓位比例"""
        return self.get_total_position_value() / self.total_capital
        
    def get_portfolio_summary(self) -> Dict:
        """
        获取组合摘要
        
        Returns:
            dict: {
                'total_capital',
                'cash',
                'position_value',
                'position_pct',
                'num_stocks',
                'total_pnl',
                'positions': List
            }
        """
        position_value = self.get_total_position_value()
        
        positions_info = []
        total_pnl = 0
        
        for code, pos in self.positions.items():
            market_value = pos.shares * pos.current_price
            pnl = market_value - pos.shares * pos.avg_price
            total_pnl += pnl
            
            positions_info.append({
                'stock_code': code,
                'shares': pos.shares,
                'avg_price': pos.avg_price,
                'current_price': pos.current_price,
                'market_value': round(market_value, 2),
                'pnl': round(pnl, 2),
                'pnl_pct': round(pos.pnl_pct * 100, 2),
                'stop_loss_price': round(pos.stop_loss_price, 2),
                'take_profit_price': round(pos.take_profit_price, 2)
            })
            
        return {
            'total_capital': round(self.total_capital, 2),
            'cash': round(self.cash, 2),
            'position_value': round(position_value, 2),
            'position_pct': round(self.get_total_position_pct() * 100, 2),
            'num_stocks': len(self.positions),
            'total_pnl': round(total_pnl, 2),
            'positions': positions_info
        }
        
    def adjust_for_market(self, market_status: str):
        """
        根据市场环境调整风控参数
        
        Args:
            market_status: 市场状态 (bull/bear/sideways)
        """
        if market_status == 'bull':
            self.config.max_total_position = 0.80
            self.config.base_stop_loss = 0.08
            self.config.base_take_profit = 0.20
        elif market_status == 'bear':
            self.config.max_total_position = 0.30
            self.config.base_stop_loss = 0.03
            self.config.base_take_profit = 0.10
        else:  # sideways
            self.config.max_total_position = 0.50
            self.config.base_stop_loss = 0.05
            self.config.base_take_profit = 0.15


def calculate_position(
    total_capital: float,
    single_stock_limit: float = 0.20,
    risk_factor: float = 1.0
) -> float:
    """
    计算可用仓位金额
    
    Args:
        total_capital: 总资金
        single_stock_limit: 单股仓位上限
        risk_factor: 风险系数
        
    Returns:
        可用金额
    """
    return total_capital * single_stock_limit * risk_factor


def calculate_remaining_position(
    total_capital: float,
    current_positions: float,
    max_total_position: float = 0.80
) -> float:
    """
    计算剩余可用仓位
    
    Args:
        total_capital: 总资金
        current_positions: 当前持仓市值
        max_total_position: 总仓上限
        
    Returns:
        剩余可用金额
    """
    max_total = total_capital * max_total_position
    remaining = max_total - current_positions
    return max(0, remaining)


def calculate_trailing_stop(
    highest_price: float,
    trailing_pct: float = 0.05
) -> float:
    """
    计算跟踪止损价
    
    Args:
        highest_price: 最高价
        trailing_pct: 回撤比例
        
    Returns:
        止损价
    """
    return highest_price * (1 - trailing_pct)
