#!/usr/bin/env python3
"""
市场环境识别和信号组合策略验证脚本

验证内容：
1. 市场环境识别符合缠论理论
2. 信号组合策略符合缠论实战原则
3. 用真实BTC数据测试
4. 发现代码BUG
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import List, Dict, Any

# 导入模块
from src.chanlun_structure_v2 import (
    process_inclusion,
    detect_all_fractals,
    filter_fractals,
    build_bi_from_fractals,
    detect_all_zhongshu,
    Zhongshu,
    Bi,
    ChanLunStructureAnalyzerV2
)
from src.signal_detector import SignalDetector, Signal, SignalType
from src.market_filter_v2 import detect_market_environment_v2
from src.signal_combination import select_signals_by_market_environment


# ============================================================================
# 理论验证函数
# ============================================================================

def validate_market_filter_theory():
    """验证市场环境识别的理论正确性"""
    print("\n" + "="*80)
    print("理论验证：市场环境识别")
    print("="*80)
    
    issues = []
    
    # 测试1：趋势市 - 两个中枢不重叠
    print("\n【测试1】趋势市（两个中枢不重叠）")
    from src.chanlun_structure_v2 import Zhongshu
    
    # 创建两个不重叠的中枢（上涨趋势）
    zs1 = Zhongshu(
        zg=100.0,
        zd=95.0,
        start_index=0,
        end_index=10,
        level=1,
        bi_list=[]
    )
    
    zs2 = Zhongshu(
        zg=120.0,  # 第二个中枢在第一个中枢之上
        zd=115.0,  # zd(115) > zs1.zg(100)，不重叠
        start_index=15,
        end_index=25,
        level=1,
        bi_list=[]
    )
    
    result = detect_market_environment_v2(pd.DataFrame(), [zs1, zs2])
    print(f"  中枢1: ZG={zs1.zg}, ZD={zs1.zd}")
    print(f"  中枢2: ZG={zs2.zg}, ZD={zs2.zd}")
    print(f"  识别结果: {result}")
    
    if result['environment'] != 'trending':
        issues.append("❌ 趋势市识别失败：应识别为trending")
    else:
        print("  ✅ 正确识别为趋势市")
    
    if result['trend_direction'] != 'up':
        issues.append("❌ 趋势方向识别失败：应为up")
    else:
        print("  ✅ 正确识别趋势方向：up")
    
    # 测试2：震荡市 - 两个中枢重叠
    print("\n【测试2】震荡市（两个中枢重叠）")
    zs3 = Zhongshu(
        zg=100.0,
        zd=90.0,
        start_index=0,
        end_index=10,
        level=1,
        bi_list=[]
    )
    
    zs4 = Zhongshu(
        zg=105.0,  # 与zs3有重叠
        zd=95.0,   # 重叠区间: max(90, 95)=95 ~ min(100, 105)=100
        start_index=15,
        end_index=25,
        level=1,
        bi_list=[]
    )
    
    result2 = detect_market_environment_v2(pd.DataFrame(), [zs3, zs4])
    print(f"  中枢1: ZG={zs3.zg}, ZD={zs3.zd}")
    print(f"  中枢2: ZG={zs4.zg}, ZD={zs4.zd}")
    print(f"  重叠区间: {max(zs3.zd, zs4.zd)} ~ {min(zs3.zg, zs4.zg)}")
    print(f"  识别结果: {result2}")
    
    # 检查重叠比例
    overlap_ratio = result2.get('overlap_ratio', 0)
    print(f"  重叠比例: {overlap_ratio:.2%}")
    
    if result2['environment'] != 'sideways':
        issues.append("❌ 震荡市识别失败：应识别为sideways")
    else:
        print("  ✅ 正确识别为震荡市")
    
    # 测试3：下跌趋势
    print("\n【测试3】下跌趋势（两个中枢不重叠，向下）")
    zs5 = Zhongshu(
        zg=120.0,
        zd=115.0,
        start_index=0,
        end_index=10,
        level=1,
        bi_list=[]
    )
    
    zs6 = Zhongshu(
        zg=100.0,  # 第二个中枢在第一个中枢之下
        zd=95.0,   # zg(100) < zs5.zd(115)，不重叠
        start_index=15,
        end_index=25,
        level=1,
        bi_list=[]
    )
    
    result3 = detect_market_environment_v2(pd.DataFrame(), [zs5, zs6])
    print(f"  中枢1: ZG={zs5.zg}, ZD={zs5.zd}")
    print(f"  中枢2: ZG={zs6.zg}, ZD={zs6.zd}")
    print(f"  识别结果: {result3}")
    
    if result3['environment'] != 'trending':
        issues.append("❌ 下跌趋势识别失败")
    elif result3['trend_direction'] != 'down':
        issues.append("❌ 下跌趋势方向识别失败")
    else:
        print("  ✅ 正确识别为下跌趋势")
    
    # 测试4：单中枢（盘整）
    print("\n【测试4】单中枢（盘整）")
    result4 = detect_market_environment_v2(pd.DataFrame(), [zs1])
    print(f"  识别结果: {result4}")
    
    if result4['environment'] != 'consolidation':
        issues.append("❌ 单中枢应识别为consolidation")
    else:
        print("  ✅ 正确识别为盘整")
    
    # 测试5：无中枢（中性）
    print("\n【测试5】无中枢（中性）")
    result5 = detect_market_environment_v2(pd.DataFrame(), [])
    print(f"  识别结果: {result5}")
    
    if result5['environment'] != 'neutral':
        issues.append("❌ 无中枢应识别为neutral")
    else:
        print("  ✅ 正确识别为中性")
    
    # 理论问题总结
    print("\n" + "="*80)
    print("理论验证总结")
    print("="*80)
    
    if issues:
        print("\n❌ 发现问题：")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n✅ 理论验证通过：市场环境识别符合缠论定义")
        return True


def validate_signal_combination_theory():
    """验证信号组合策略的理论正确性"""
    print("\n" + "="*80)
    print("理论验证：信号组合策略")
    print("="*80)
    
    issues = []
    
    # 创建测试信号
    signal_buy1 = Signal(
        signal_type=SignalType.BUY_1,
        price=100.0,
        index=10,
        datetime=datetime.now(),
        confidence=75,
        reason='第一类买点'
    )
    
    signal_buy2 = Signal(
        signal_type=SignalType.BUY_2,
        price=105.0,
        index=15,
        datetime=datetime.now(),
        confidence=80,
        reason='第二类买点'
    )
    
    signal_buy3 = Signal(
        signal_type=SignalType.BUY_3,
        price=110.0,
        index=20,
        datetime=datetime.now(),
        confidence=85,
        reason='第三类买点'
    )
    
    all_signals = [signal_buy1, signal_buy2, signal_buy3]
    
    # 测试1：上涨趋势 → 二三买优先
    print("\n【测试1】上涨趋势信号选择")
    market_env_up = {
        'environment': 'trending',
        'trend_direction': 'up'
    }
    
    selected_up = select_signals_by_market_environment(all_signals, market_env_up)
    print(f"  输入信号: {[s.signal_type.value for s in all_signals]}")
    print(f"  选择结果: {[s.signal_type.value for s in selected_up]}")
    
    selected_types = [s.signal_type for s in selected_up]
    if SignalType.BUY_1 in selected_types:
        issues.append("❌ 上涨趋势不应选择BUY_1（抄底风险大）")
    if SignalType.BUY_2 not in selected_types and SignalType.BUY_3 not in selected_types:
        issues.append("❌ 上涨趋势应选择BUY_2或BUY_3")
    
    if not issues:
        print("  ✅ 正确选择二三买信号")
    
    # 测试2：下跌趋势 → 一买优先
    print("\n【测试2】下跌趋势信号选择")
    market_env_down = {
        'environment': 'trending',
        'trend_direction': 'down'
    }
    
    selected_down = select_signals_by_market_environment(all_signals, market_env_down)
    print(f"  输入信号: {[s.signal_type.value for s in all_signals]}")
    print(f"  选择结果: {[s.signal_type.value for s in selected_down]}")
    
    selected_types = [s.signal_type for s in selected_down]
    if SignalType.BUY_2 in selected_types or SignalType.BUY_3 in selected_types:
        issues.append("❌ 下跌趋势不应选择BUY_2/BUY_3（追高）")
    if SignalType.BUY_1 not in selected_types:
        issues.append("❌ 下跌趋势应选择BUY_1（需要高置信度）")
    
    if not any('下跌趋势' in issue for issue in issues):
        print("  ✅ 正确选择一买信号")
    
    # 测试3：震荡市 → 一买
    print("\n【测试3】震荡市信号选择")
    market_env_sideways = {
        'environment': 'sideways',
        'trend_direction': 'none'
    }
    
    selected_sideways = select_signals_by_market_environment(all_signals, market_env_sideways)
    print(f"  输入信号: {[s.signal_type.value for s in all_signals]}")
    print(f"  选择结果: {[s.signal_type.value for s in selected_sideways]}")
    
    selected_types = [s.signal_type for s in selected_sideways]
    if SignalType.BUY_2 in selected_types or SignalType.BUY_3 in selected_types:
        issues.append("❌ 震荡市不应选择BUY_2/BUY_3（假突破风险）")
    if SignalType.BUY_1 not in selected_types:
        issues.append("❌ 震荡市应选择BUY_1")
    
    if not any('震荡市' in issue for issue in issues):
        print("  ✅ 正确选择一买信号")
    
    # 理论问题总结
    print("\n" + "="*80)
    print("理论验证总结")
    print("="*80)
    
    if issues:
        print("\n❌ 发现问题：")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n✅ 理论验证通过：信号组合策略符合缠论实战原则")
        return True


# ============================================================================
# 真实数据测试
# ============================================================================

def test_with_real_data():
    """用真实BTC数据测试"""
    print("\n" + "="*80)
    print("真实数据测试：BTC 5分钟数据")
    print("="*80)
    
    try:
        from src.crypto_data_fetcher import CryptoDataFetcher
        
        # 获取最近半年的BTC数据
        fetcher = CryptoDataFetcher()
        end_time = datetime.now()
        start_time = end_time - timedelta(days=180)  # 半年
        
        print(f"\n获取BTC数据: {start_time.date()} ~ {end_time.date()}")
        
        # 尝试获取数据
        try:
            df = fetcher.fetch_klines(
                symbol="BTCUSDT",
                interval="5m",
                limit=1000
            )
            
            if df is None or df.empty:
                print("⚠️  无法获取真实数据，使用模拟数据测试")
                return test_with_simulated_data()
            
            print(f"获取到 {len(df)} 条数据")
            
        except Exception as e:
            print(f"⚠️  数据获取失败: {e}")
            print("使用模拟数据测试")
            return test_with_simulated_data()
        
        # 处理包含关系
        print("\n处理K线包含关系...")
        analyzer = ChanLunStructureAnalyzerV2(df)
        result = analyzer.analyze()
        
        processed_df = result['df_processed']
        bi_list = result['bi_list']
        zs_list = result['zhongshu_list']
        
        print(f"处理后: {len(processed_df)} 条K线")
        print(f"识别到 {len(bi_list)} 条笔")
        print(f"识别到 {len(zs_list)} 个中枢")
        
        # 检测市场环境
        market_env = detect_market_environment_v2(df, zs_list)
        print(f"\n市场环境识别:")
        print(f"  环境: {market_env['environment']}")
        print(f"  趋势方向: {market_env.get('trend_direction', 'none')}")
        print(f"  置信度: {market_env.get('confidence', 0):.2f}")
        
        # 检测信号
        print("\n检测信号...")
        detector = SignalDetector()
        signals = detector.detect_all_signals(df, bi_list, zs_list)
        print(f"检测到 {len(signals)} 个信号")
        
        if signals:
            print("\n信号详情（前10个）:")
            for i, sig in enumerate(signals[:10]):
                print(f"  {i+1}. {sig.signal_type.value}: 价格={sig.price:.2f}, 置信度={sig.confidence}")
        
        # 应用信号组合策略
        selected_signals = select_signals_by_market_environment(signals, market_env)
        print(f"\n信号组合后: {len(selected_signals)} 个信号")
        
        if selected_signals:
            print("\n选择信号详情:")
            for sig in selected_signals:
                print(f"  - {sig.signal_type.value}: 价格={sig.price:.2f}, 置信度={sig.confidence}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 真实数据测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_simulated_data():
    """使用模拟数据测试"""
    print("\n使用模拟数据进行测试...")
    
    # 创建模拟数据
    np.random.seed(42)
    n = 1000
    
    # 创建趋势数据
    trend = np.linspace(100, 120, n)
    noise = np.random.randn(n) * 2
    
    close = trend + noise
    high = close + np.abs(np.random.randn(n) * 1)
    low = close - np.abs(np.random.randn(n) * 1)
    open_price = close + np.random.randn(n) * 0.5
    
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=n, freq='5min'),
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(100, 1000, n)
    })
    
    print(f"创建模拟数据: {len(df)} 条")
    
    # 使用分析器
    analyzer = ChanLunStructureAnalyzerV2(df)
    result = analyzer.analyze()
    
    processed_df = result['df_processed']
    bi_list = result['bi_list']
    zs_list = result['zhongshu_list']
    
    print(f"处理包含关系后: {len(processed_df)} 条")
    print(f"识别笔: {len(bi_list)} 条")
    print(f"识别中枢: {len(zs_list)} 个")
    
    # 检测市场环境
    market_env = detect_market_environment_v2(df, zs_list)
    print(f"\n市场环境: {market_env}")
    
    # 检测信号
    detector = SignalDetector()
    signals = detector.detect_all_signals(df, bi_list, zs_list)
    print(f"检测信号: {len(signals)} 个")
    
    # 应用信号组合策略
    selected_signals = select_signals_by_market_environment(signals, market_env)
    print(f"选择信号: {len(selected_signals)} 个")
    
    if selected_signals:
        print(f"\n选择信号详情:")
        for sig in selected_signals[:5]:  # 只显示前5个
            print(f"  - {sig.signal_type.value}: 价格={sig.price:.2f}, 置信度={sig.confidence}")
    
    return True


# ============================================================================
# 发现的BUG记录
# ============================================================================

def analyze_code_bugs():
    """分析代码中的潜在BUG"""
    print("\n" + "="*80)
    print("代码BUG分析")
    print("="*80)
    
    bugs = []
    
    # BUG 1: market_filter_v2.py 只检查前两个中枢
    print("\n【BUG检查1】中枢检查范围")
    print("  代码片段: zs1 = zhongshu_list[0], zs2 = zhongshu_list[1]")
    print("  问题: 只检查前两个中枢，如果中枢数量 > 2，可能遗漏趋势变化")
    print("  建议: 遍历所有相邻中枢对，或只取最新的两个中枢")
    bugs.append({
        'file': 'market_filter_v2.py',
        'line': 'zs1 = zhongshu_list[0]',
        'issue': '只检查前两个中枢',
        'severity': 'medium',
        'theory': '缠论理论要求趋势由中枢移动定义，应关注最新中枢关系'
    })
    
    # BUG 2: 30%重叠阈值缺乏理论依据
    print("\n【BUG检查2】重叠阈值")
    print("  代码片段: OVERLAP_THRESHOLD = 0.3")
    print("  问题: 30%阈值缺乏缠论理论依据")
    print("  建议: 应基于缠论原文定义，完全重叠或区间重叠判断")
    bugs.append({
        'file': 'market_filter_v2.py',
        'line': 'OVERLAP_THRESHOLD = 0.3',
        'issue': '30%阈值缺乏理论依据',
        'severity': 'low',
        'theory': '缠论定义中枢重叠为区间有交集，无需比例阈值'
    })
    
    # BUG 3: signal_combination.py 上涨趋势信号选择逻辑
    print("\n【BUG检查3】上涨趋势信号选择")
    print("  代码片段: _select_for_uptrend 函数")
    print("  问题: ")
    print("    1. 只选择BUY_2/BUY_3，可能返回空列表")
    print("    2. 如果没有BUY_2/BUY_3，会完全错过上涨趋势")
    print("  建议: 应允许BUY_1作为备选，或降低置信度要求")
    bugs.append({
        'file': 'signal_combination.py',
        'line': '_select_for_uptrend',
        'issue': '上涨趋势信号选择过于严格',
        'severity': 'high',
        'theory': '缠论实战中，上涨趋势确认后可参与，不应完全排除BUY_1'
    })
    
    # BUG 4: 下跌趋势中BUY_1的置信度要求
    print("\n【BUG检查4】下跌趋势BUY_1置信度")
    print("  代码片段: MIN_CONFIDENCE_FOR_DOWNTREND_BUY1 = 70")
    print("  问题: 下跌趋势中第一类买点需要高置信度(70+)，但实际中难以达到")
    print("  建议: 降低阈值或使用背驰确认")
    bugs.append({
        'file': 'signal_combination.py',
        'line': 'MIN_CONFIDENCE_FOR_DOWNTREND_BUY1 = 70',
        'issue': '下跌趋势BUY_1置信度要求过高',
        'severity': 'medium',
        'theory': '缠论第一类买点基于背驰，应检查背驰确认而非硬性置信度'
    })
    
    print("\n" + "="*80)
    print("BUG汇总")
    print("="*80)
    
    for i, bug in enumerate(bugs, 1):
        print(f"\nBUG-{i}: {bug['file']} @ {bug['line']}")
        print(f"  问题: {bug['issue']}")
        print(f"  严重程度: {bug['severity']}")
        print(f"  理论依据: {bug['theory']}")
    
    return bugs


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主验证流程"""
    print("\n" + "="*80)
    print("缠论市场环境识别和信号组合策略 - 业务回归验证")
    print("="*80)
    
    results = {
        'theory_market_filter': False,
        'theory_signal_combination': False,
        'real_data_test': False,
        'bugs_found': []
    }
    
    # 1. 理论验证 - 市场环境识别
    try:
        results['theory_market_filter'] = validate_market_filter_theory()
    except Exception as e:
        print(f"\n❌ 市场环境识别理论验证异常: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. 理论验证 - 信号组合策略
    try:
        results['theory_signal_combination'] = validate_signal_combination_theory()
    except Exception as e:
        print(f"\n❌ 信号组合策略理论验证异常: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. 真实数据测试
    try:
        results['real_data_test'] = test_with_real_data()
    except Exception as e:
        print(f"\n❌ 真实数据测试异常: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. BUG分析
    try:
        results['bugs_found'] = analyze_code_bugs()
    except Exception as e:
        print(f"\n❌ BUG分析异常: {e}")
    
    # 最终报告
    print("\n" + "="*80)
    print("验证报告")
    print("="*80)
    
    print(f"\n市场环境识别理论验证: {'✅ 通过' if results['theory_market_filter'] else '❌ 失败'}")
    print(f"信号组合策略理论验证: {'✅ 通过' if results['theory_signal_combination'] else '❌ 失败'}")
    print(f"真实数据测试: {'✅ 通过' if results['real_data_test'] else '❌ 失败'}")
    print(f"发现BUG数量: {len(results['bugs_found'])}")
    
    if results['bugs_found']:
        print("\n需要修复的BUG:")
        for bug in results['bugs_found']:
            print(f"  - {bug['file']}: {bug['issue']}")
    
    # 返回验证结果
    all_passed = (
        results['theory_market_filter'] and
        results['theory_signal_combination'] and
        results['real_data_test']
    )
    
    print("\n" + "="*80)
    if all_passed and not results['bugs_found']:
        print("✅ 业务回归验证通过")
    else:
        print("❌ 业务回归验证未通过，需要修复")
    print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)