"""
加密货币数据获取模块
支持：Binance、OKX 等交易所的 BTC/ETH 等币种数据
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging
import time
import os

logger = logging.getLogger(__name__)


class CryptoDataFetcher:
    """加密货币数据获取器"""
    
    def __init__(self, exchange: str = "binance", proxy: str = None):
        """
        初始化
        
        Args:
            exchange: 交易所名称 (binance, okx)
            proxy: 代理地址，如 "http://127.0.0.1:7890"
        """
        self.exchange = exchange
        self.base_url = self._get_base_url()
        self.proxy = proxy or os.environ.get('https_proxy') or os.environ.get('HTTP_PROXY')
    
    def _get_base_url(self) -> str:
        """获取交易所 API 基础 URL"""
        urls = {
            "binance": "https://api.binance.com",
            "binance_futures": "https://fapi.binance.com",
            "okx": "https://www.okx.com"
        }
        return urls.get(self.exchange, urls["binance"])
    
    def fetch_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        limit: int = 1000,
        start_time: int = None,
        end_time: int = None
    ) -> Optional[pd.DataFrame]:
        """
        获取 K 线数据
        
        Args:
            symbol: 交易对，如 "BTCUSDT"
            interval: K线周期 (1m, 5m, 15m, 1h, 4h, 1d)
            limit: 获取数量，最大 1000
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
            
        Returns:
            DataFrame: date, open, high, low, close, volume
        """
        import requests
        
        try:
            if self.exchange in ["binance", "binance_futures"]:
                return self._fetch_binance_klines(
                    symbol, interval, limit, start_time, end_time
                )
            elif self.exchange == "okx":
                return self._fetch_okx_klines(
                    symbol, interval, limit, start_time, end_time
                )
            else:
                logger.error(f"Unsupported exchange: {self.exchange}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            return None
    
    def _fetch_binance_klines(
        self,
        symbol: str,
        interval: str,
        limit: int,
        start_time: int = None,
        end_time: int = None
    ) -> Optional[pd.DataFrame]:
        """获取 Binance K线数据"""
        import requests
        
        # Binance 现货/合约 API
        if self.exchange == "binance_futures":
            url = f"{self.base_url}/fapi/v1/klines"
        else:
            url = f"{self.base_url}/api/v3/klines"
        
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1000)
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        # 代理设置
        proxies = None
        if self.proxy:
            proxies = {
                "http": self.proxy,
                "https": self.proxy
            }
        
        response = requests.get(url, params=params, proxies=proxies, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"Binance API error: {response.status_code} - {response.text}")
            return None
        
        data = response.json()
        
        if not data:
            logger.warning(f"No data returned for {symbol}")
            return None
        
        # 转换为 DataFrame
        df = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # 类型转换
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['date'] = df['open_time']
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 只保留需要的列
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
        
        return df
    
    def _fetch_okx_klines(
        self,
        symbol: str,
        interval: str,
        limit: int,
        start_time: int = None,
        end_time: int = None
    ) -> Optional[pd.DataFrame]:
        """获取 OKX K线数据"""
        import requests
        
        # OKX interval 映射
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "1H", "4h": "4H", "1d": "1D"
        }
        
        bar = interval_map.get(interval, "5m")
        
        url = f"{self.base_url}/api/v5/market/candles"
        
        params = {
            "instId": symbol,
            "bar": bar,
            "limit": min(limit, 300)
        }
        
        if start_time:
            params["before"] = str(start_time)
        if end_time:
            params["after"] = str(end_time)
        
        # 代理设置
        proxies = None
        if self.proxy:
            proxies = {
                "http": self.proxy,
                "https": self.proxy
            }
        
        response = requests.get(url, params=params, proxies=proxies, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"OKX API error: {response.status_code}")
            return None
        
        data = response.json()
        
        if data.get('code') != '0' or not data.get('data'):
            logger.warning(f"No data from OKX: {data.get('msg')}")
            return None
        
        # OKX 返回的数据是倒序的
        candles = data['data'][::-1]
        
        df = pd.DataFrame(candles, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'volCcy', 'volCcyQuote', 'confirm'
        ])
        
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
        df['date'] = df['timestamp']
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
        
        return df
    
    def fetch_historical_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        days: int = 7
    ) -> Optional[pd.DataFrame]:
        """
        获取历史 K 线数据（分批获取，突破 1000 条限制）
        
        Args:
            symbol: 交易对
            interval: K线周期
            days: 获取天数
            
        Returns:
            完整的 DataFrame
        """
        # 计算 interval 对应的毫秒数
        interval_ms = {
            "1m": 60 * 1000,
            "5m": 5 * 60 * 1000,
            "15m": 15 * 60 * 1000,
            "1h": 60 * 60 * 1000,
            "4h": 4 * 60 * 60 * 1000,
            "1d": 24 * 60 * 60 * 1000
        }
        
        ms_per_candle = interval_ms.get(interval, 5 * 60 * 1000)
        
        # 计算总时间范围
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = end_time - days * 24 * 60 * 60 * 1000
        
        # 分批获取
        all_data = []
        current_start = start_time
        
        while current_start < end_time:
            # 每批 1000 条
            df = self.fetch_klines(
                symbol=symbol,
                interval=interval,
                limit=1000,
                start_time=current_start
            )
            
            if df is None or df.empty:
                break
            
            all_data.append(df)
            
            # 更新下一次的起始时间
            last_time = int(df['date'].iloc[-1].timestamp() * 1000)
            current_start = last_time + ms_per_candle
            
            # 避免请求过快
            time.sleep(0.1)
            
            # 如果获取的数据少于 1000 条，说明已经到最新数据
            if len(df) < 1000:
                break
        
        if not all_data:
            return None
        
        # 合并所有数据
        result = pd.concat(all_data, ignore_index=True)
        
        # 去重
        result = result.drop_duplicates(subset=['date'])
        result = result.sort_values('date').reset_index(drop=True)
        
        logger.info(f"Fetched {len(result)} candles for {symbol} {interval}")
        
        return result


# ============================================================================
# 便捷函数
# ============================================================================

def fetch_btc_5min(days: int = 7) -> Optional[pd.DataFrame]:
    """
    获取 BTC 5分钟 K 线数据
    
    优先级：
    1. yfinance (Yahoo Finance) - 更稳定
    2. Binance API
    3. 模拟数据
    
    Args:
        days: 获取天数（建议 <= 1，5分钟数据量大）
        
    Returns:
        DataFrame: date, open, high, low, close, volume
    """
    # 尝试方法1: yfinance（更稳定）
    try:
        import yfinance as yf
        
        # yfinance 获取 BTC 数据
        ticker = yf.Ticker("BTC-USD")
        df = ticker.history(period=f"{days}d", interval="5m")
        
        if df is not None and not df.empty:
            df = df.reset_index()
            df = df.rename(columns={
                'Datetime': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
            logger.info(f"Fetched BTC data from yfinance: {len(df)} rows")
            return df
    except Exception as e:
        logger.warning(f"yfinance failed: {e}")
    
    # 尝试方法2: Binance
    try:
        fetcher = CryptoDataFetcher(exchange="binance")
        df = fetcher.fetch_historical_klines(
            symbol="BTCUSDT",
            interval="5m",
            days=days
        )
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.warning(f"Binance failed: {e}")
    
    # 方法3: 生成模拟数据（用于测试）
    logger.warning("Using simulated BTC data for testing")
    return generate_simulated_btc_data(days=days)


def fetch_eth_5min(days: int = 7) -> Optional[pd.DataFrame]:
    """获取 ETH 5分钟 K 线数据"""
    fetcher = CryptoDataFetcher(exchange="binance")
    return fetcher.fetch_historical_klines(
        symbol="ETHUSDT",
        interval="5m",
        days=days
    )


def fetch_crypto_klines(
    symbol: str = "BTCUSDT",
    interval: str = "5m",
    days: int = 7,
    exchange: str = "binance"
) -> Optional[pd.DataFrame]:
    """
    通用加密货币 K 线获取函数
    
    Args:
        symbol: 交易对
        interval: K线周期
        days: 天数
        exchange: 交易所
        
    Returns:
        DataFrame
    """
    fetcher = CryptoDataFetcher(exchange=exchange)
    return fetcher.fetch_historical_klines(
        symbol=symbol,
        interval=interval,
        days=days
    )


# ============================================================================
# 数据验证
# ============================================================================

def validate_crypto_data(df: pd.DataFrame) -> Dict:
    """
    验证加密货币数据质量
    
    Returns:
        验证结果字典
    """
    if df is None or df.empty:
        return {"valid": False, "reason": "No data"}
    
    result = {
        "valid": True,
        "total_rows": len(df),
        "date_range": None,
        "missing_values": 0,
        "issues": []
    }
    
    # 日期范围
    if 'date' in df.columns:
        result["date_range"] = {
            "start": str(df['date'].min()),
            "end": str(df['date'].max())
        }
    
    # 缺失值检查
    missing = df.isnull().sum().sum()
    result["missing_values"] = int(missing)
    if missing > 0:
        result["issues"].append(f"Missing values: {missing}")
    
    # 价格异常检查
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            if (df[col] <= 0).any():
                result["issues"].append(f"Invalid {col} values (<= 0)")
                result["valid"] = False
    
    # 高低点关系检查
    if 'high' in df.columns and 'low' in df.columns:
        invalid_hl = df[df['high'] < df['low']]
        if len(invalid_hl) > 0:
            result["issues"].append(f"High < Low in {len(invalid_hl)} rows")
    
    return result


def generate_simulated_btc_data(days: int = 7) -> pd.DataFrame:
    """
    生成模拟的 BTC 5分钟数据（用于离线测试）
    
    基于真实 BTC 波动特征生成
    """
    np.random.seed(42)
    
    # 5分钟K线，一天 288 根
    candles_per_day = 288
    total_candles = days * candles_per_day
    
    # 生成日期
    dates = pd.date_range(
        start=pd.Timestamp.now() - pd.Timedelta(days=days),
        periods=total_candles,
        freq='5min'
    )
    
    # BTC 价格特征
    # - 价格范围: 60000-70000
    # - 5分钟波动: ~0.1-0.3%
    # - 日波动: 2-5%
    
    start_price = 65000.0
    
    # 生成收益率序列
    # 使用较小的波动率
    returns = np.random.randn(total_candles) * 0.002  # 0.2% 波动
    
    # 添加趋势
    trend = np.sin(np.linspace(0, days * 2 * np.pi, total_candles)) * 0.001
    returns = returns + trend
    
    # 限制极端值
    returns = np.clip(returns, -0.02, 0.02)  # 最大 2% 波动
    
    # 累积收益率（使用对数收益率）
    log_returns = returns
    cumulative_log_returns = np.cumsum(log_returns)
    
    # 收盘价
    close = start_price * np.exp(cumulative_log_returns)
    
    # 确保 price 在合理范围
    close = np.clip(close, 50000, 80000)
    
    # 生成 OHLC
    # 高低点波动
    range_pct = np.abs(np.random.randn(total_candles)) * 0.003  # 0.3% 范围
    
    high = close * (1 + range_pct)
    low = close * (1 - range_pct)
    
    # 开盘价基于前一根收盘价
    open_price = np.roll(close, 1)
    open_price[0] = start_price
    
    # 确保 high >= max(open, close), low <= min(open, close)
    high = np.maximum(high, np.maximum(open_price, close))
    low = np.minimum(low, np.minimum(open_price, close))
    
    # 成交量
    volume = np.random.uniform(100, 500, total_candles) * (1 + np.abs(returns) * 50)
    
    # 构建 DataFrame
    df = pd.DataFrame({
        'date': dates,
        'open': np.round(open_price, 2),
        'high': np.round(high, 2),
        'low': np.round(low, 2),
        'close': np.round(close, 2),
        'volume': np.round(volume, 2)
    })
    
    return df
