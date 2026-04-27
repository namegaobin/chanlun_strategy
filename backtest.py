#!/usr/bin/env python3
"""
ChanLun Strategy 回测系统
支持历史数据回测 + AI 评估验证
"""
import os
import sys
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, project_root)

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 导入项目模块
from data_fetcher import DataFetcher, fetch_daily_kline
from chanlun_structure import ChanLunStructureAnalyzer, calculate_zhongshu_from_bi
from limit_up_detector import find_recent_limit_ups, detect_limit_up
from market_filter import detect_market_environment, MarketStatus
from risk_manager import RiskManager, RiskConfig
from ai_evaluator import AIEvaluator, build_evaluation_prompt


class ChanLunBacktestSystem:
    """缠论策略回测系统"""
    
    def __init__(
        self,
        start_date: str = None,
        end_date: str = None,
        initial_capital: float = 1000000,
        enable_ai: bool = True
    ):
        """
        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            initial_capital: 初始资金
            enable_ai: 是否启用 AI 评估
        """
        self.start_date = start_date or (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        self.end_date = end_date or datetime.now().strftime('%Y-%m-%d')
        self.initial_capital = initial_capital
        self.enable_ai = enable_ai
        
        # 初始化组件
        self.risk_manager = RiskManager(
            total_capital=initial_capital,
            config=RiskConfig()
        )
        
        # AI 评估器
        if enable_ai:
            api_key = os.getenv("AI_API_KEY")
            if api_key:
                self.ai_evaluator = AIEvaluator(
                    api_key=api_key,
                    provider="deepseek"
                )
                print(f"✓ AI 评估器已初始化")
            else:
                print("⚠ AI_API_KEY 未配置，将跳过 AI 评估")
                self.enable_ai = False
                self.ai_evaluator = None
        else:
            self.ai_evaluator = None
            
        # 回测结果
        self.results = []
        self.signals = []
        
    def run_single_stock(self, stock_code: str) -> dict:
        """
        回测单只股票
        
        Args:
            stock_code: 股票代码
            
        Returns:
            回测结果
        """
        print(f"\n{'='*60}")
        print(f"开始回测: {stock_code}")
        print(f"时间范围: {self.start_date} ~ {self.end_date}")
        print(f"{'='*60}")
        
        result = {
            'stock_code': stock_code,
            'status': 'pending',
            'data': None,
            'signals': [],
            'trades': [],
            'metrics': {}
        }
        
        try:
            # 1. 获取数据
            print("\n【步骤 1】获取数据...")
            with DataFetcher() as fetcher:
                df = fetcher.fetch_daily_kline(
                    stock_code,
                    self.start_date,
                    self.end_date
                )
            
            if df is None or df.empty:
                result['status'] = 'no_data'
                print(f"✗ 未获取到数据")
                return result
                
            print(f"✓ 获取数据: {len(df)} 条记录")
            result['data'] = df
            
            # 2. 缠论结构分析
            print("\n【步骤 2】缠论结构分析...")
            analyzer = ChanLunStructureAnalyzer(df)
            structure = analyzer.analyze()
            
            print(f"✓ 分型: {len(structure['fractals'])} 个")
            print(f"✓ 笔: {len(structure['bi_list'])} 个")
            print(f"✓ 线段: {len(structure['xianduan_list'])} 个")
            
            if structure['zhongshu']:
                zs = structure['zhongshu']
                print(f"✓ 中枢: ZG={zs.zg:.2f}, ZD={zs.zd:.2f}")
            else:
                print("⚠ 未检测到有效中枢")
                
            # 3. 信号识别
            print("\n【步骤 3】信号识别...")
            signals = self._detect_signals(df, structure)
            result['signals'] = signals
            print(f"✓ 发现 {len(signals)} 个信号")
            
            # 4. AI 评估（如果启用）
            if self.enable_ai and signals:
                print("\n【步骤 4】AI 评估...")
                for i, signal in enumerate(signals):
                    print(f"\n  评估信号 {i+1}/{len(signals)}...")
                    ai_result = self._ai_evaluate_signal(
                        stock_code, df, structure, signal
                    )
                    signal['ai_evaluation'] = ai_result
                    
            # 5. 生成报告
            result['status'] = 'success'
            print(f"\n✓ 回测完成")
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            print(f"✗ 回测失败: {e}")
            
        return result
        
    def _detect_signals(self, df: pd.DataFrame, structure: dict) -> list:
        """检测交易信号（优化版）"""
        signals = []
        
        # 需要足够的数据
        if len(df) < 20:
            return signals
            
        # 获取中枢
        zs = structure.get('zhongshu')
        if not zs:
            # 如果没有中枢，尝试计算
            from chanlun_analyzer import calculate_zhongshu
            zs_data = calculate_zhongshu(df)
            if zs_data:
                from chanlun_structure import Zhongshu
                zs = Zhongshu(
                    zg=zs_data['zg'],
                    zd=zs_data['zd'],
                    start_index=0,
                    end_index=len(df)-1,
                    level=1,
                    bi_list=[]
                )
        
        # 遍历寻找信号
        for i in range(5, len(df)):
            window_df = df.iloc[:i+1]
            current_price = df.iloc[i]['close']
            
            # 信号类型 1: 涨停突破
            limit_up_info = detect_limit_up(window_df)
            if limit_up_info and limit_up_info['is_limit_up']:
                if zs and current_price > zs.zg:
                    signals.append({
                        'date': str(df.iloc[i]['date']),
                        'price': float(current_price),
                        'type': 'limit_up_breakout',
                        'limit_up_pct': float(limit_up_info['pct_change']),
                        'zhongshu': {'zg': float(zs.zg), 'zd': float(zs.zd)}
                    })
            
            # 信号类型 2: 第三类买点（简化版）
            if zs and len(window_df) >= 10:
                # 检查是否在中枢下方
                recent_low = window_df['low'].tail(10).min()
                
                # 回抽不破ZD
                if recent_low > zs.zd and current_price < zs.zg:
                    # 当前价格在中枢区间内，从下方回升
                    if current_price > recent_low:
                        signals.append({
                            'date': str(df.iloc[i]['date']),
                            'price': float(current_price),
                            'type': 'third_buy_candidate',
                            'limit_up_pct': 0.0,
                            'zhongshu': {'zg': float(zs.zg), 'zd': float(zs.zd)}
                        })
        
        # 去重（同一天可能有多个信号）
        unique_signals = []
        seen_dates = set()
        for sig in signals:
            if sig['date'] not in seen_dates:
                unique_signals.append(sig)
                seen_dates.add(sig['date'])
                
        return unique_signals
        
    def _ai_evaluate_signal(
        self,
        stock_code: str,
        df: pd.DataFrame,
        structure: dict,
        signal: dict
    ) -> dict:
        """AI 评估信号"""
        if not self.ai_evaluator:
            return {'status': 'ai_disabled'}
            
        try:
            # 准备评估数据
            structure_data = {
                'zhongshu': signal.get('zhongshu', {}),
                'bi_direction': structure['bi_list'][-1].direction.value if structure['bi_list'] else 'unknown',
                'bi_done': True
            }
            
            signal_data = {
                'signal_type': signal['type'],
                'strength': '待评估',
                'trigger_condition': f"涨停 {signal['limit_up_pct']:.1f}%"
            }
            
            # 调用 AI 评估
            result = self.ai_evaluator.evaluate_signal(
                stock_code=stock_code,
                price=signal['price'],
                structure_data=structure_data,
                signal_data=signal_data,
                market_status='neutral'
            )
            
            if result['success']:
                print(f"    ✓ AI 评估完成")
                return result['evaluation']
            else:
                print(f"    ✗ AI 评估失败: {result.get('error')}")
                return {'status': 'error', 'error': result.get('error')}
                
        except Exception as e:
            print(f"    ✗ AI 评估异常: {e}")
            return {'status': 'exception', 'error': str(e)}
            
    def run_multiple_stocks(self, stock_codes: list) -> list:
        """
        回测多只股票
        
        Args:
            stock_codes: 股票代码列表
            
        Returns:
            回测结果列表
        """
        results = []
        for code in stock_codes:
            result = self.run_single_stock(code)
            results.append(result)
            
        return results
        
    def generate_report(self, result: dict) -> str:
        """生成评估报告"""
        if result['status'] != 'success':
            return f"# ⚠️ 回测失败\n\n错误: {result.get('error', '未知错误')}"
            
        stock_code = result['stock_code']
        df = result['data']
        signals = result.get('signals', [])
        
        # 基本信息
        current_price = float(df['close'].iloc[-1])
        report = f"""# 📊 {stock_code} 缠论评估报告

## 基本信息
- **股票代码**: {stock_code}
- **当前价格**: {current_price:.2f}
- **评估时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- **数据范围**: {self.start_date} ~ {self.end_date}
- **数据量**: {len(df)} 条

## 价格统计
- 最高价: {df['high'].max():.2f}
- 最低价: {df['low'].min():.2f}
- 平均价: {df['close'].mean():.2f}
- 波动率: {(df['close'].std() / df['close'].mean() * 100):.2f}%

## 缠论结构
- 分型数量: {len(result.get('fractals', []))}
- 笔数量: {len(result.get('bi_list', []))}
- 线段数量: {len(result.get('xianduan_list', []))}

## 信号统计
- 发现信号: {len(signals)} 个
"""
        
        # 信号详情
        if signals:
            report += "\n### 信号详情\n\n"
            for i, signal in enumerate(signals, 1):
                report += f"#### 信号 {i}\n"
                report += f"- **日期**: {signal['date']}\n"
                report += f"- **价格**: {signal['price']:.2f}\n"
                report += f"- **类型**: {signal['type']}\n"
                report += f"- **涨停幅度**: {signal['limit_up_pct']:.2f}%\n"
                
                if 'ai_evaluation' in signal:
                    ai_eval = signal['ai_evaluation']
                    if isinstance(ai_eval, dict):
                        action_rec = ai_eval.get('action_recommendation', {})
                        report += f"\n**AI 建议**:\n"
                        report += f"- 操作: {action_rec.get('action', 'N/A')}\n"
                        report += f"- 理由: {action_rec.get('reasoning', 'N/A')}\n"
                        
        # 风控建议
        report += f"""
## 风控建议
- **初始资金**: {self.initial_capital:,.0f} 元
- **单股上限**: {self.risk_manager.config.max_single_position:.0%}
- **总仓上限**: {self.risk_manager.config.max_total_position:.0%}
- **止损比例**: {self.risk_manager.config.base_stop_loss:.0%}
- **止盈比例**: {self.risk_manager.config.base_take_profit:.0%}

---
*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*本报告仅供参考，不构成投资建议*
"""
        
        return report


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='缠论策略回测系统')
    parser.add_argument('stock_codes', nargs='+', help='股票代码（如 sh.600000）')
    parser.add_argument('--start', help='开始日期 YYYY-MM-DD')
    parser.add_argument('--end', help='结束日期 YYYY-MM-DD')
    parser.add_argument('--capital', type=float, default=1000000, help='初始资金')
    parser.add_argument('--no-ai', action='store_true', help='禁用 AI 评估')
    parser.add_argument('--output', help='输出报告文件路径')
    
    args = parser.parse_args()
    
    # 创建回测系统
    system = ChanLunBacktestSystem(
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        enable_ai=not args.no_ai
    )
    
    # 运行回测
    results = system.run_multiple_stocks(args.stock_codes)
    
    # 生成报告
    for result in results:
        report = system.generate_report(result)
        print("\n" + report)
        
        # 保存报告
        if args.output:
            output_path = args.output
        else:
            output_path = f"output/{result['stock_code']}_report.md"
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n报告已保存: {output_path}")


if __name__ == '__main__':
    main()
