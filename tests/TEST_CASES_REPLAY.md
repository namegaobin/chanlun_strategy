# 📋 历史数据回放测试体系 - 测试用例矩阵

> 需求：以历史数据回放方式进行策略测试，形成胜率、收益率关键指标，驱动策略迭代优化

---

## 测试框架：pytest
## 技术栈：Python 3.9 + pandas + pytest

---

## P0 核心路径 (必须通过)

### TC-RP-001: 回放引擎逐 bar 推进
- **Given**: 一段 120 天的日线数据（DataFrame）
- **When**: 启动回放引擎，逐 bar 推进
- **Then**: 每个时间点，引擎只看到当前及之前的数据，不泄露未来数据
- **验证**: `engine.current_bar_index` 递增，`available_data == df[:i+1]`

### TC-RP-002: 买入信号触发并模拟成交
- **Given**: 回放过程中，缠论策略识别到第三类买点信号
- **When**: 信号触发且风控通过
- **Then**: 以次日开盘价模拟买入成交，记录交易（code, entry_date, entry_price, direction=LONG）
- **验证**: `trade.entry_price == next_bar_open`，持仓状态变更为 HOLDING

### TC-RP-003: 卖出信号触发（止损/止盈/超时）
- **Given**: 持仓中，价格触发止损/止盈/最大持仓天数
- **When**: 任一退出条件满足
- **Then**: 以次日开盘价模拟卖出成交，记录交易（exit_date, exit_price, pnl, pnl_pct）
- **验证**: 
  - 止损：`trade.exit_price <= trade.entry_price * (1 - stop_loss)`
  - 止盈：`trade.exit_price >= trade.entry_price * (1 + take_profit)`
  - 超时：`hold_days >= max_hold_days`

### TC-RP-004: 胜率计算
- **Given**: 回放结束，有 N 笔已完成交易
- **When**: 计算胜率
- **Then**: `win_rate = 盈利交易数 / 总交易数 * 100%`
- **验证**: 已知 5 笔交易中 3 笔盈利 → `win_rate == 60.0%`

### TC-RP-005: 收益率计算
- **Given**: 回放结束，有 N 笔已完成交易
- **When**: 计算收益率指标
- **Then**: 
  - `total_return = (final_capital - initial_capital) / initial_capital * 100%`
  - `avg_trade_return = mean(trade.pnl_pct for trade in trades)`
  - `max_drawdown = max(peak_to_trough_decline)`
- **验证**: 初始 100 万，最终 115 万 → `total_return == 15.0%`

### TC-RP-006: 完整回放流程端到端
- **Given**: 准备好的历史数据（至少 60 天）
- **When**: 执行完整回放流程
- **Then**: 输出完整的回测报告，包含：
  - 总交易次数、胜率、收益率
  - 最大回撤、夏普比率
  - 每笔交易明细
- **验证**: 报告包含所有字段且数值合理

---

## P1 异常场景 (重要)

### TC-RP-007: 无信号数据回放
- **Given**: 平稳无趋势的行情数据（无缠论买点）
- **When**: 执行完整回放
- **Then**: 交易次数为 0，资金不变，胜率/收益率为 N/A 或 0
- **验证**: `len(trades) == 0`，`final_capital == initial_capital`

### TC-RP-008: 未来数据泄露检测
- **Given**: 回放引擎在某个 bar 位置
- **When**: 策略函数调用获取数据
- **Then**: 只能获取 `current_index` 及之前的数据，不能看到后续 bar
- **验证**: `engine.get_available_data().iloc[-1]['date'] == df.iloc[current_index]['date']`

### TC-RP-009: 连续亏损后风控熔断
- **Given**: 连续 3 笔交易止损
- **When**: 风控检测到连续亏损
- **Then**: 暂停交易 N 天（冷却期），避免情绪化操作
- **验证**: 冷却期内无新开仓信号

### TC-RP-010: 涨跌停无法成交
- **Given**: 信号触发次日，股票涨停/跌停
- **When**: 尝试以开盘价买入
- **Then**: 涨停日无法买入（排队），跳过该信号
- **验证**: 涨停日不产生成交记录

### TC-RP-011: 资金不足无法开仓
- **Given**: 可用资金不足一手
- **When**: 信号触发
- **Then**: 跳过该信号，记录"资金不足"日志
- **验证**: 无成交，`available_capital < position_cost`

---

## P2 边界条件 (一般)

### TC-RP-012: 极端行情（连续涨停/跌停）
- **Given**: 连续涨停数据
- **When**: 回放
- **Then**: 买入后连续涨停不触发止盈（每日涨停板无法卖出），直到开板
- **验证**: 持仓穿越涨停期

### TC-RP-013: 数据缺失处理
- **Given**: 历史数据中有停牌日（缺失 bar）
- **When**: 回放到缺失日期
- **Then**: 跳过停牌日，持仓天数计算排除停牌日
- **验证**: 停牌日无成交、无价格变动

### TC-RP-014: 单笔交易收益率边界
- **Given**: 买入后次日即触发止损（-5%）
- **When**: 计算该笔收益率
- **Then**: `pnl_pct ≈ -5% - 手续费`
- **验证**: `trade.pnl_pct < 0`，`abs(trade.pnl_pct + 0.05) < 0.01`

### TC-RP-015: 多股票并行回放指标汇总
- **Given**: 10 只股票各自回放完毕
- **When**: 汇总指标
- **Then**: 输出汇总胜率、汇总收益率、各股指标排名
- **验证**: `aggregate_win_rate == total_wins / total_trades * 100`

---

## 指标驱动迭代测试

### TC-RP-016: 策略参数变更后指标对比
- **Given**: 基线策略（stop_loss=5%, take_profit=15%）胜率 40%，收益率 8%
- **When**: 调整参数（stop_loss=3%, take_profit=10%）
- **Then**: 重新回放，对比指标变化，输出对比报告
- **验证**: 新旧指标均有记录，diff 可追溯

### TC-RP-017: 指标基准线（Baseline）记录
- **Given**: 首次完整回放完成
- **When**: 保存结果
- **Then**: 将胜率、收益率作为 baseline 存入 JSON 文件
- **验证**: `baseline.json` 包含 `win_rate`, `total_return`, `timestamp`

---

## 测试用例汇总

| 优先级 | 数量 | 覆盖范围 |
|--------|------|----------|
| P0 | 6 | 回放引擎核心、交易模拟、指标计算、端到端 |
| P1 | 5 | 无信号、数据泄露、风控熔断、涨跌停、资金不足 |
| P2 | 4 | 极端行情、数据缺失、边界计算、多股汇总 |
| 迭代 | 2 | 参数对比、基准线记录 |
| **合计** | **17** | |

---
