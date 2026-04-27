"""
ChanLun Strategy - 缠论第三类买点量化策略（完整版）

基于涨停突破中枢+回抽不破ZG的第三类买点策略
包含：缠论形态识别、大盘环境过滤、风控管理
"""

from .data_fetcher import (
    DataFetcher,
    fetch_daily_kline,
    fetch_5min_kline,
    fetch_multiple_stocks
)

from .limit_up_detector import (
    detect_limit_up,
    is_limit_up,
    check_zg_breakout,
    filter_by_time_window,
    find_recent_limit_ups,
    validate_limit_up_with_zg_breakout
)

from .chanlun_analyzer import (
    calculate_zhongshu,
    detect_third_buy_point,
    check_divergence,
    confirm_5min_signal,
    ChanLunAnalyzer
)

from .chanlun_structure import (
    # 分型识别
    FractalType,
    Direction,
    Fractal,
    detect_fractal,
    detect_all_fractals,
    filter_fractals,
    # 笔识别
    Bi,
    build_bi_from_fractals,
    validate_bi,
    # 线段识别
    Xianduan,
    detect_xianduan_from_bi,
    # 中枢计算
    Zhongshu,
    calculate_zhongshu_from_bi,
    calculate_zhongshu_from_xianduan,
    # 分析器
    ChanLunStructureAnalyzer
)

from .market_filter import (
    MarketStatus,
    TrendStatus,
    detect_market_environment,
    get_strategy_params,
    should_filter_signal,
    MarketFilter
)

from .risk_manager import (
    PositionAction,
    Position,
    RiskConfig,
    RiskManager,
    calculate_position,
    calculate_remaining_position,
    calculate_trailing_stop
)

from .ai_evaluator import (
    AIEvaluator,
    LLMClient,
    LLMConfig,
    call_ai,
    evaluate_third_buy_point,
    build_evaluation_prompt
)

try:
    from .backtest_strategy import (
        ChanLunStrategy,
        run_backtest,
        calculate_performance_metrics,
        generate_report
    )
except ImportError:
    ChanLunStrategy = None
    run_backtest = None
    calculate_performance_metrics = None
    generate_report = None

__version__ = '2.0.0'
__all__ = [
    # Data Fetcher
    'DataFetcher',
    'fetch_daily_kline',
    'fetch_5min_kline',
    'fetch_multiple_stocks',
    
    # Limit Up Detector
    'detect_limit_up',
    'is_limit_up',
    'check_zg_breakout',
    'filter_by_time_window',
    'find_recent_limit_ups',
    'validate_limit_up_with_zg_breakout',
    
    # ChanLun Analyzer (简化版)
    'calculate_zhongshu',
    'detect_third_buy_point',
    'check_divergence',
    'confirm_5min_signal',
    'ChanLunAnalyzer',
    
    # ChanLun Structure (完整版)
    'FractalType',
    'Direction',
    'Fractal',
    'detect_fractal',
    'detect_all_fractals',
    'filter_fractals',
    'Bi',
    'build_bi_from_fractals',
    'validate_bi',
    'Xianduan',
    'detect_xianduan_from_bi',
    'Zhongshu',
    'calculate_zhongshu_from_bi',
    'calculate_zhongshu_from_xianduan',
    'ChanLunStructureAnalyzer',
    
    # Market Filter
    'MarketStatus',
    'TrendStatus',
    'detect_market_environment',
    'get_strategy_params',
    'should_filter_signal',
    'MarketFilter',
    
    # Risk Manager
    'PositionAction',
    'Position',
    'RiskConfig',
    'RiskManager',
    'calculate_position',
    'calculate_remaining_position',
    'calculate_trailing_stop',
    
    # Backtest Strategy
    'ChanLunStrategy',
    'run_backtest',
    'calculate_performance_metrics',
    'generate_report',
    
    # AI Evaluator
    'AIEvaluator',
    'LLMClient',
    'LLMConfig',
    'call_ai',
    'evaluate_third_buy_point',
    'build_evaluation_prompt'
]
