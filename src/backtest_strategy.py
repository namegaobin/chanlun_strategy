"""
回测策略模块 - 基于 backtrader 框架
功能：缠论策略回测、信号生成、绩效计算
"""
import backtrader as bt
import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime


class ChanLunStrategy(bt.Strategy):
    """
    缠论第三类买点策略
    
    策略逻辑：
    1. 识别涨停突破中枢
    2. 等待回抽不破ZG
    3. 5分钟K线确认买点
    4. 买入持有，触发止盈/止损退出
    """
    
    params = (
        ('zhongshu_period', 20),    # 中枢计算周期
        ('limit_up_threshold', 9.9), # 涨停阈值
        ('stop_loss', 0.05),        # 止损比例（5%）
        ('take_profit', 0.15),      # 止盈比例（15%）
        ('max_hold_days', 10),      # 最大持仓天数
        ('min_hold_days', 3),       # 最少持仓天数（涨停后）
        ('max_hold_days', 5),       # 最大持仓天数（涨停后）
    )
    
    def __init__(self):
        """初始化指标"""
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        self.buy_date = None
        
        # 移动平均线
        self.sma20 = bt.indicators.SimpleMovingAverage(
            self.data.close, period=20
        )
        
        # MACD
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=12,
            period_me2=26,
            period_signal=9
        )
        
        # 记录中枢
        self.zhongshu = None
        self.zg = None
        self.zd = None
        
        # 信号状态
        self.limit_up_detected = False
        self.limit_up_date = None
        
    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
            
        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                self.buy_date = self.datas[0].datetime.date(0)
                print(f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                      f'Cost: {order.executed.value:.2f}, '
                      f'Comm: {order.executed.comm:.2f}')
            else:
                print(f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                      f'Cost: {order.executed.value:.2f}, '
                      f'Comm: {order.executed.comm:.2f}')
                      
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            print('Order Canceled/Margin/Rejected')
            
        self.order = None
        
    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return
            
        print(f'TRADE PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')
        
    def next(self):
        """策略主逻辑"""
        # 如果有订单在处理，不操作
        if self.order:
            return
            
        # 检查是否持仓
        if not self.position:
            # 无持仓，寻找买入机会
            
            # 1. 计算中枢
            if len(self.data) >= self.p.zhongshu_period:
                self.calculate_zhongshu()
                
            # 2. 检测涨停
            if self.zg and self.detect_limit_up():
                self.limit_up_detected = True
                self.limit_up_date = self.datas[0].datetime.date(0)
                print(f'Limit up detected on {self.limit_up_date}')
                
            # 3. 等待回抽不破ZG（3-5天后）
            if self.limit_up_detected and self.limit_up_date:
                days_since_limit_up = (self.datas[0].datetime.date(0) - self.limit_up_date).days
                
                if self.p.min_hold_days <= days_since_limit_up <= self.p.max_hold_days:
                    # 检查回抽是否不破ZG
                    current_low = self.data.low[0]
                    current_close = self.data.close[0]
                    
                    if current_low > self.zd and current_close > self.zg:
                        # 回抽不破ZG，买入信号
                        print(f'BUY SIGNAL: Pullback above ZG, Price: {current_close:.2f}')
                        self.order = self.buy()
                        
        else:
            # 有持仓，检查退出条件
            
            # 止损
            if self.data.close[0] < self.buy_price * (1 - self.p.stop_loss):
                print(f'STOP LOSS triggered at {self.data.close[0]:.2f}')
                self.order = self.sell()
                return
                
            # 止盈
            if self.data.close[0] > self.buy_price * (1 + self.p.take_profit):
                print(f'TAKE PROFIT triggered at {self.data.close[0]:.2f}')
                self.order = self.sell()
                return
                
            # 最大持仓天数
            if self.buy_date:
                hold_days = (self.datas[0].datetime.date(0) - self.buy_date).days
                if hold_days >= self.p.max_hold_days:
                    print(f'MAX HOLD DAYS reached, selling at {self.data.close[0]:.2f}')
                    self.order = self.sell()
                    
    def calculate_zhongshu(self):
        """计算中枢"""
        # 获取最近N根K线
        window = self.data.close.get(size=self.p.zhongshu_period)
        highs = self.data.high.get(size=self.p.zhongshu_period)
        lows = self.data.low.get(size=self.p.zhongshu_period)
        
        if len(window) < self.p.zhongshu_period:
            return
            
        # 简化中枢计算
        self.zg = min(highs[-10:])
        self.zd = max(lows[-10:])
        
    def detect_limit_up(self) -> bool:
        """检测涨停"""
        if len(self.data) < 2:
            return False
            
        prev_close = self.data.close[-1]
        curr_close = self.data.close[0]
        
        if prev_close <= 0:
            return False
            
        pct_change = ((curr_close - prev_close) / prev_close) * 100
        
        # 涨停判断
        is_limit_up = pct_change >= self.p.limit_up_threshold
        
        # 检查是否突破ZG
        if is_limit_up and self.zg:
            breaks_zg = curr_close > self.zg
            return breaks_zg
            
        return False


def run_backtest(
    data: pd.DataFrame,
    strategy_params: Optional[Dict] = None
) -> Dict:
    """
    执行回测
    
    Args:
        data: 日K线数据，需包含 date, open, high, low, close, volume 列
        strategy_params: 策略参数
        
    Returns:
        dict: {
            'total_return': float,
            'max_drawdown': float,
            'sharpe_ratio': float,
            'total_trades': int,
            'win_rate': float
        }
    """
    # 创建回测引擎
    cerebro = bt.Cerebro()
    
    # 添加策略
    if strategy_params:
        cerebro.addstrategy(ChanLunStrategy, **strategy_params)
    else:
        cerebro.addstrategy(ChanLunStrategy)
        
    # 准备数据
    data = data.copy()
    if 'date' in data.columns:
        data['date'] = pd.to_datetime(data['date'])
        data = data.set_index('date')
        
    # 添加数据源
    data_feed = bt.feeds.PandasData(
        dataname=data,
        datetime=None,
        open='open',
        high='high',
        low='low',
        close='close',
        volume='volume',
        openinterest=-1
    )
    cerebro.adddata(data_feed)
    
    # 设置初始资金
    cerebro.broker.setcash(100000.0)
    
    # 设置手续费
    cerebro.broker.setcommission(commission=0.001)
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # 运行回测
    print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')
    results = cerebro.run()
    print(f'Final Portfolio Value: {cerebro.broker.getvalue():.2f}')
    
    # 计算绩效指标
    metrics = calculate_performance_metrics(results[0])
    
    return metrics


def calculate_performance_metrics(strategy_result) -> Dict:
    """
    计算绩效指标
    
    Args:
        strategy_result: backtrader 运行结果
        
    Returns:
        dict: {
            'total_return': float,
            'max_drawdown': float,
            'sharpe_ratio': float,
            'total_trades': int,
            'win_rate': float
        }
    """
    metrics = {
        'total_return': 0.0,
        'max_drawdown': 0.0,
        'sharpe_ratio': 0.0,
        'total_trades': 0,
        'win_rate': 0.0
    }
    
    # 提取分析器结果
    sharpe_analysis = strategy_result.analyzers.sharpe.get_analysis()
    drawdown_analysis = strategy_result.analyzers.drawdown.get_analysis()
    returns_analysis = strategy_result.analyzers.returns.get_analysis()
    trades_analysis = strategy_result.analyzers.trades.get_analysis()
    
    # 总收益率
    if 'rtot' in returns_analysis:
        metrics['total_return'] = returns_analysis['rtot'] * 100
        
    # 最大回撤
    if 'max' in drawdown_analysis and 'drawdown' in drawdown_analysis['max']:
        metrics['max_drawdown'] = drawdown_analysis['max']['drawdown']
        
    # 夏普比率
    if 'sharperatio' in sharpe_analysis and sharpe_analysis['sharperatio']:
        metrics['sharpe_ratio'] = sharpe_analysis['sharperatio']
        
    # 交易统计
    if 'total' in trades_analysis:
        total_trades = trades_analysis['total']['total']
        won_trades = trades_analysis.get('won', {}).get('total', 0)
        
        metrics['total_trades'] = total_trades
        if total_trades > 0:
            metrics['win_rate'] = (won_trades / total_trades) * 100
            
    return metrics


def generate_report(metrics: Dict) -> str:
    """
    生成回测报告
    
    Args:
        metrics: 绩效指标
        
    Returns:
        报告文本
    """
    report = f"""
====================================
ChanLun Strategy Backtest Report
====================================

Performance Metrics:
--------------------
Total Return:      {metrics['total_return']:.2f}%
Max Drawdown:      {metrics['max_drawdown']:.2f}%
Sharpe Ratio:      {metrics['sharpe_ratio']:.2f}

Trade Statistics:
-----------------
Total Trades:      {metrics['total_trades']}
Win Rate:          {metrics['win_rate']:.2f}%

====================================
"""
    return report
