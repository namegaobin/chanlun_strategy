#!/usr/bin/env python3
"""
ChanLun Strategy - 主程序入口
缠论第三类买点量化策略

用法：
    python main.py --stock sh.600000 --start 2026-01-01 --end 2026-04-14
    python main.py --backtest --config config.yaml
"""
import argparse
import logging
from datetime import datetime, timedelta
import pandas as pd

from src.data_fetcher import fetch_daily_kline, fetch_5min_kline, DataFetcher
from src.limit_up_detector import find_recent_limit_ups, validate_limit_up_with_zg_breakout
from src.chanlun_analyzer import ChanLunAnalyzer, calculate_zhongshu
from src.backtest_strategy import run_backtest, generate_report

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def scan_limit_up_stocks(
    stock_pool: list,
    start_date: str,
    end_date: str,
    min_days: int = 3,
    max_days: int = 5
) -> pd.DataFrame:
    """
    扫描股票池中的涨停股
    
    Args:
        stock_pool: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        min_days: 最小天数
        max_days: 最大天数
        
    Returns:
        涨停股票信息DataFrame
    """
    results = []
    
    with DataFetcher() as fetcher:
        for stock_code in stock_pool:
            try:
                logger.info(f"Scanning {stock_code}...")
                
                # 获取日K线数据
                df = fetcher.fetch_daily_kline(stock_code, start_date, end_date)
                if df is None or df.empty:
                    continue
                    
                # 查找涨停
                limit_ups = find_recent_limit_ups(df, end_date, max_days)
                
                if not limit_ups.empty:
                    for _, row in limit_ups.iterrows():
                        results.append({
                            'stock_code': stock_code,
                            'limit_up_date': row['date'],
                            'limit_up_price': row['close'],
                            'pct_change': row['pct_change']
                        })
                        
            except Exception as e:
                logger.error(f"Error scanning {stock_code}: {e}")
                continue
                
    return pd.DataFrame(results)


def analyze_third_buy_point(
    stock_code: str,
    start_date: str,
    end_date: str
) -> dict:
    """
    分析股票的第三类买点
    
    Args:
        stock_code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        分析结果
    """
    logger.info(f"Analyzing {stock_code} from {start_date} to {end_date}")
    
    # 获取数据
    df = fetch_daily_kline(stock_code, start_date, end_date)
    if df is None or df.empty:
        return {'status': 'error', 'message': 'No data available'}
        
    # 计算中枢
    zhongshu = calculate_zhongshu(df)
    if not zhongshu:
        return {'status': 'error', 'message': 'Cannot calculate zhongshu'}
        
    # 分析买点
    analyzer = ChanLunAnalyzer(df)
    buy_points = analyzer.find_third_buy_points()
    
    return {
        'status': 'success',
        'stock_code': stock_code,
        'zhongshu': zhongshu,
        'buy_points': buy_points,
        'data': df
    }


def run_strategy_backtest(
    stock_code: str,
    start_date: str,
    end_date: str,
    strategy_params: dict = None
) -> dict:
    """
    执行策略回测
    
    Args:
        stock_code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        strategy_params: 策略参数
        
    Returns:
        回测结果
    """
    logger.info(f"Running backtest for {stock_code}")
    
    # 获取数据
    df = fetch_daily_kline(stock_code, start_date, end_date)
    if df is None or df.empty:
        return {'status': 'error', 'message': 'No data available'}
        
    # 执行回测
    metrics = run_backtest(df, strategy_params)
    
    # 生成报告
    report = generate_report(metrics)
    
    return {
        'status': 'success',
        'stock_code': stock_code,
        'metrics': metrics,
        'report': report
    }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='ChanLun Strategy - 缠论第三类买点策略')
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # scan 命令 - 扫描涨停股
    scan_parser = subparsers.add_parser('scan', help='Scan for limit-up stocks')
    scan_parser.add_argument('--stocks', nargs='+', required=True, help='Stock codes')
    scan_parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    scan_parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    
    # analyze 命令 - 分析买点
    analyze_parser = subparsers.add_parser('analyze', help='Analyze third buy point')
    analyze_parser.add_argument('--stock', required=True, help='Stock code')
    analyze_parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    analyze_parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    
    # backtest 命令 - 执行回测
    backtest_parser = subparsers.add_parser('backtest', help='Run backtest')
    backtest_parser.add_argument('--stock', required=True, help='Stock code')
    backtest_parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    backtest_parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    backtest_parser.add_argument('--stop-loss', type=float, default=0.05, help='Stop loss ratio')
    backtest_parser.add_argument('--take-profit', type=float, default=0.15, help='Take profit ratio')
    
    args = parser.parse_args()
    
    if args.command == 'scan':
        # 扫描涨停股
        results = scan_limit_up_stocks(args.stocks, args.start, args.end)
        if not results.empty:
            print("\n=== Limit-Up Stocks ===")
            print(results.to_string(index=False))
        else:
            print("No limit-up stocks found.")
            
    elif args.command == 'analyze':
        # 分析买点
        result = analyze_third_buy_point(args.stock, args.start, args.end)
        if result['status'] == 'success':
            print(f"\n=== Analysis Result for {args.stock} ===")
            print(f"Zhongshu: ZG={result['zhongshu']['zg']}, ZD={result['zhongshu']['zd']}")
            if result['buy_points']:
                print(f"\nFound {len(result['buy_points'])} third buy point(s):")
                for bp in result['buy_points']:
                    print(f"  Date: {bp['date']}, Price: {bp['price']}")
            else:
                print("\nNo third buy points found.")
        else:
            print(f"Error: {result['message']}")
            
    elif args.command == 'backtest':
        # 执行回测
        params = {
            'stop_loss': args.stop_loss,
            'take_profit': args.take_profit
        }
        result = run_strategy_backtest(args.stock, args.start, args.end, params)
        if result['status'] == 'success':
            print(result['report'])
        else:
            print(f"Error: {result['message']}")
            
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
