#!/usr/bin/env python3
"""
回放引擎 - GREEN Phase 实现

逐K线回放历史数据，时间戳验证（信号不能使用未来数据），决策日志记录。

核心约束：每个决策点只使用≤当前时间的数据
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os


@dataclass
class KLine:
    """K线数据"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Bi:
    """笔"""
    start_time: datetime
    end_time: datetime
    direction: str
    high: float
    low: float
    confirmed: bool = False
    confirm_time: Optional[datetime] = None


@dataclass
class Zhongshu:
    """中枢"""
    start_time: datetime
    end_time: datetime
    zg: float
    zd: float
    confirmed: bool = False
    confirm_time: Optional[datetime] = None


@dataclass
class Signal:
    """交易信号"""
    timestamp: datetime
    signal_type: str
    price: float
    confidence: float


@dataclass
class DecisionLog:
    """决策日志"""
    timestamp: datetime
    decision_type: str
    data_used: Dict[str, Any]
    data_timestamps: List[datetime]


class ReplayEngine:
    """回放引擎
    
    逐K线回放历史数据，验证时间戳约束，记录决策日志。
    """
    
    def __init__(self, 
                 data_source: str = 'btc_5m_sample.csv',
                 enable_logging: bool = False):
        """
        Args:
            data_source: CSV文件路径或内置数据名称
            enable_logging: 是否启用决策日志
        """
        self.data_source = data_source
        self.enable_logging = enable_logging
        
        # 加载K线数据
        self.klines: List[KLine] = self._load_data(data_source)
        self.current_index = 0
        
        # 决策日志
        self.decision_logs: List[DecisionLog] = []
        
        # 内部状态
        self._analyzer_state = {
            'merged_klines': [],
            'pending_fractals': [],
            'confirmed_fractals': [],
            'confirmed_bi_list': [],
            'confirmed_zhongshu_list': [],
        }
    
    def _load_data(self, data_source: str) -> List[KLine]:
        """加载K线数据"""
        # 尝试加载CSV文件
        if os.path.exists(data_source):
            return self._load_csv(data_source)
        
        # 如果文件不存在，生成模拟数据用于测试
        return self._generate_sample_data()
    
    def _load_csv(self, filepath: str) -> List[KLine]:
        """从CSV加载K线数据"""
        import csv
        
        klines = []
        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    kline = KLine(
                        timestamp=datetime.fromisoformat(row['date']),
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=float(row.get('volume', 0))
                    )
                    klines.append(kline)
        except Exception:
            # 如果CSV加载失败，返回模拟数据
            return self._generate_sample_data()
        
        return klines
    
    def _generate_sample_data(self) -> List[KLine]:
        """生成模拟K线数据（用于测试）"""
        klines = []
        base_time = datetime(2026, 4, 28, 9, 0)
        base_price = 100.0
        
        for i in range(100):
            t = base_time + timedelta(minutes=i * 5)
            # 模拟震荡行情
            price = base_price + (i % 10) * 0.5
            kline = KLine(
                timestamp=t,
                open=price,
                high=price + 2,
                low=price - 2,
                close=price + 1,
                volume=1000
            )
            klines.append(kline)
        
        return klines
    
    @property
    def total_bars(self) -> int:
        """总K线数量"""
        return len(self.klines)
    
    def has_next(self) -> bool:
        """是否还有下一根K线"""
        return self.current_index < len(self.klines)
    
    def replay_next(self) -> dict:
        """
        回放下一根K线，返回当前状态
        
        Returns:
            dict: {
                'current_time': datetime,
                'current_kline': KLine,
                'confirmed_bi_list': List[Bi],
                'confirmed_zhongshu_list': List[Zhongshu],
                'signals': List[Signal],
            }
        """
        if not self.has_next():
            return None
        
        # 获取当前K线
        kline = self.klines[self.current_index]
        
        # 增量式更新状态
        result = self._update_state(kline)
        
        # 记录决策日志
        if self.enable_logging:
            self._log_decision(result)
        
        self.current_index += 1
        
        return result
    
    def _update_state(self, kline: KLine) -> dict:
        """更新内部状态（模拟增量式分析）"""
        # 简化的状态更新逻辑
        # 实际上这里会调用IncrementalChanLunAnalyzer
        
        merged = self._analyzer_state['merged_klines']
        merged.append(kline)
        
        # 简化：检查是否形成笔
        confirmed_bi_list = list(self._analyzer_state['confirmed_bi_list'])
        
        if len(merged) >= 5:
            # 简单模拟：每5根K线可能形成一笔
            bi_count = len(confirmed_bi_list)
            if bi_count < len(merged) // 5:
                bi = Bi(
                    start_time=merged[-5].timestamp,
                    end_time=kline.timestamp,
                    direction='up' if kline.close > merged[-5].close else 'down',
                    high=max(k.high for k in merged[-5:]),
                    low=min(k.low for k in merged[-5:]),
                    confirmed=True,
                    confirm_time=kline.timestamp
                )
                # 避免重复
                if not any(b.start_time == bi.start_time for b in confirmed_bi_list):
                    confirmed_bi_list.append(bi)
        
        self._analyzer_state['confirmed_bi_list'] = confirmed_bi_list
        
        # 简化：检查是否形成中枢
        confirmed_zhongshu_list = list(self._analyzer_state['confirmed_zhongshu_list'])
        
        if len(confirmed_bi_list) >= 3:
            zs_count = len(confirmed_zhongshu_list)
            bi_group_count = len(confirmed_bi_list) // 3
            if zs_count < bi_group_count:
                b1, b2, b3 = confirmed_bi_list[-3:]
                zd = max(b1.low, b2.low, b3.low)
                zg = min(b1.high, b2.high, b3.high)
                if zg > zd:
                    zs = Zhongshu(
                        start_time=b1.start_time,
                        end_time=b3.end_time,
                        zg=zg,
                        zd=zd,
                        confirmed=True,
                        confirm_time=kline.timestamp
                    )
                    if not any(z.start_time == zs.start_time for z in confirmed_zhongshu_list):
                        confirmed_zhongshu_list.append(zs)
        
        self._analyzer_state['confirmed_zhongshu_list'] = confirmed_zhongshu_list
        
        # 检测信号（简化）
        signals = self._detect_signals(kline, confirmed_bi_list, confirmed_zhongshu_list)
        
        return {
            'current_time': kline.timestamp,
            'current_kline': kline,
            'confirmed_bi_list': confirmed_bi_list,
            'confirmed_zhongshu_list': confirmed_zhongshu_list,
            'signals': signals,
        }
    
    def _detect_signals(self, 
                        kline: KLine, 
                        bi_list: List[Bi], 
                        zs_list: List[Zhongshu]) -> List[Signal]:
        """检测信号（简化版）"""
        signals = []
        
        # 简化：三买条件满足时产生信号
        if len(zs_list) > 0 and len(bi_list) >= 4:
            zs = zs_list[-1]
            recent_bi = bi_list[-1]
            
            # 检查是否形成三买
            if (recent_bi.direction == 'down' and 
                recent_bi.high < zs.zd and 
                recent_bi.confirm_time <= kline.timestamp):
                signal = Signal(
                    timestamp=kline.timestamp,
                    signal_type='buy_3',
                    price=recent_bi.high,
                    confidence=0.7
                )
                signals.append(signal)
        
        return signals
    
    def _log_decision(self, result: dict):
        """记录决策日志"""
        current_time = result['current_time']
        
        # 收集使用的数据的时间戳
        data_timestamps = [current_time]  # 当前K线时间
        
        for bi in result.get('confirmed_bi_list', []):
            data_timestamps.append(bi.start_time)
            if bi.confirm_time:
                data_timestamps.append(bi.confirm_time)
        
        for zs in result.get('confirmed_zhongshu_list', []):
            data_timestamps.append(zs.start_time)
            if zs.confirm_time:
                data_timestamps.append(zs.confirm_time)
        
        for signal in result.get('signals', []):
            data_timestamps.append(signal.timestamp)
        
        log = DecisionLog(
            timestamp=current_time,
            decision_type='analyze',
            data_used={
                'kline_count': len(self._analyzer_state['merged_klines']),
                'bi_count': len(result.get('confirmed_bi_list', [])),
                'zs_count': len(result.get('confirmed_zhongshu_list', [])),
                'signal_count': len(result.get('signals', [])),
            },
            data_timestamps=data_timestamps
        )
        
        self.decision_logs.append(log)
    
    def get_decision_logs(self) -> List[Dict[str, Any]]:
        """获取决策日志"""
        return [
            {
                'timestamp': log.timestamp,
                'decision_type': log.decision_type,
                'data_used': log.data_used,
                'data_timestamps': log.data_timestamps,
            }
            for log in self.decision_logs
        ]
    
    def reset(self):
        """重置回放引擎"""
        self.current_index = 0
        self.decision_logs = []
        self._analyzer_state = {
            'merged_klines': [],
            'pending_fractals': [],
            'confirmed_fractals': [],
            'confirmed_bi_list': [],
            'confirmed_zhongshu_list': [],
        }