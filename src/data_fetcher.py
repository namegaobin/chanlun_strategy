"""
数据获取模块 - 基于 baostock API
功能：获取A股日K线、5分钟K线数据
"""
import baostock as bs
import pandas as pd
from typing import Optional, Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DataFetcher:
    """数据获取器"""
    
    def __init__(self):
        self._login_result = None
        
    def __enter__(self):
        """上下文管理器 - 登录"""
        self._login_result = bs.login()
        if self._login_result.error_code != '0':
            raise ConnectionError(f"Baostock login failed: {self._login_result.error_msg}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器 - 登出"""
        bs.logout()
        
    def fetch_daily_kline(
        self, 
        stock_code: str, 
        start_date: str, 
        end_date: str,
        adjustflag: str = "3"  # 3: 不复权
    ) -> Optional[pd.DataFrame]:
        """
        获取日K线数据
        
        Args:
            stock_code: 股票代码，如 "sh.600000"
            start_date: 开始日期，格式 "2026-01-01"
            end_date: 结束日期，格式 "2026-04-14"
            adjustflag: 复权类型，"3"不复权，"2"前复权，"1"后复权
            
        Returns:
            DataFrame with columns: date, code, open, high, low, close, volume, amount, pct_change
        """
        try:
            rs = bs.query_history_k_data_plus(
                stock_code,
                "date,code,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag=adjustflag
            )
            
            if rs.error_code != '0':
                logger.error(f"Query failed: {rs.error_msg}")
                return None
                
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
                
            if not data_list:
                logger.warning(f"No data returned for {stock_code}")
                return pd.DataFrame()
                
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 类型转换
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pctChg']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    
            # 重命名列
            df = df.rename(columns={'pctChg': 'pct_change'})
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching daily kline: {e}")
            raise
            
    def fetch_5min_kline(
        self,
        stock_code: str,
        date: str
    ) -> Optional[pd.DataFrame]:
        """
        获取5分钟K线数据
        
        Args:
            stock_code: 股票代码
            date: 日期，格式 "2026-04-14"
            
        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        try:
            rs = bs.query_history_k_data_plus(
                stock_code,
                "date,time,code,open,high,low,close,volume,amount",
                start_date=date,
                end_date=date,
                frequency="5",
                adjustflag="3"
            )
            
            if rs.error_code != '0':
                logger.error(f"Query 5min failed: {rs.error_msg}")
                return None
                
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
                
            if not data_list:
                return pd.DataFrame()
                
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # 类型转换
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    
            return df
            
        except Exception as e:
            logger.error(f"Error fetching 5min kline: {e}")
            raise
            
    def fetch_multiple_stocks(
        self,
        stock_pool: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, pd.DataFrame]:
        """
        并发获取多只股票的日K线数据
        
        Args:
            stock_pool: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            字典：{stock_code: DataFrame}
        """
        results = {}
        
        for stock_code in stock_pool:
            try:
                df = self.fetch_daily_kline(stock_code, start_date, end_date)
                if df is not None and not df.empty:
                    results[stock_code] = df
                else:
                    logger.warning(f"No data for {stock_code}")
            except Exception as e:
                logger.error(f"Failed to fetch {stock_code}: {e}")
                continue
                
        return results


def fetch_daily_kline(stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    便捷函数：获取日K线数据
    
    使用示例：
        df = fetch_daily_kline("sh.600000", "2026-01-01", "2026-04-14")
    """
    with DataFetcher() as fetcher:
        return fetcher.fetch_daily_kline(stock_code, start_date, end_date)


def fetch_5min_kline(stock_code: str, date: str) -> Optional[pd.DataFrame]:
    """
    便捷函数：获取5分钟K线数据
    """
    with DataFetcher() as fetcher:
        return fetcher.fetch_5min_kline(stock_code, date)


def fetch_multiple_stocks(stock_pool: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
    """
    便捷函数：并发获取多只股票数据
    """
    with DataFetcher() as fetcher:
        return fetcher.fetch_multiple_stocks(stock_pool, start_date, end_date)
