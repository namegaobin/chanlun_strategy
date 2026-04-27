# 测试用例汇总

## 模块测试矩阵

### 1. 涨停识别模块 (test_limit_up_detector.py)

| ID | Priority | Type | Description | Status |
|----|----------|------|-------------|--------|
| TC001 | P0 | happy_path | 标准涨停识别（涨幅9.9%） | ⏳ |
| TC002 | P0 | happy_path | 涨停突破中枢ZG判断 | ⏳ |
| TC003 | P1 | exception | 股价下跌不触发涨停 | ⏳ |
| TC004 | P1 | exception | 空数据处理 | ⏳ |
| TC005 | P2 | boundary | 涨幅9.89%不触发涨停 | ⏳ |
| TC006 | P2 | boundary | 涨幅9.90%触发涨停 | ⏳ |
| TC007 | P2 | boundary | 涨停后第2天在窗口内 | ⏳ |
| TC008 | P2 | boundary | 涨停后第6天超出窗口 | ⏳ |

### 2. 缠论分析模块 (test_chanlun_analyzer.py)

| ID | Priority | Type | Description | Status |
|----|----------|------|-------------|--------|
| TC010 | P0 | happy_path | 计算中枢（ZG/ZD） | ⏳ |
| TC011 | P0 | happy_path | 第三类买点识别 | ⏳ |
| TC012 | P0 | happy_path | 跌破ZG不构成第三买点 | ⏳ |
| TC009 | P1 | exception | 存在盘整背驰过滤信号 | ⏳ |
| TC013 | P1 | exception | 无背驰时继续信号 | ⏳ |
| TC014 | P1 | exception | 数据不足返回空 | ⏳ |
| TC015 | P2 | boundary | 5分钟K线买点确认 | ⏳ |

### 3. 数据获取模块 (test_data_fetcher.py)

| ID | Priority | Type | Description | Status |
|----|----------|------|-------------|--------|
| TC016 | P0 | happy_path | 获取日K线数据 | ⏳ |
| TC017 | P0 | happy_path | 获取5分钟K线数据 | ⏳ |
| TC003 | P1 | exception | API超时处理 | ⏳ |
| TC004 | P1 | exception | API返回空数据 | ⏳ |
| TC018 | P1 | exception | 无效股票代码 | ⏳ |
| TC019 | P2 | concurrency | 并发获取多只股票 | ⏳ |

### 4. 回测策略模块 (test_backtest_strategy.py)

| ID | Priority | Type | Description | Status |
|----|----------|------|-------------|--------|
| TC002 | P0 | happy_path | 策略初始化 | ⏳ |
| TC020 | P0 | happy_path | 回测生成交易信号 | ⏳ |
| TC002 | P0 | happy_path | 绩效指标计算 | ⏳ |
| TC021 | P1 | exception | 无信号时不交易 | ⏳ |
| TC022 | P2 | boundary | 止损触发 | ⏳ |
| TC023 | P2 | boundary | 止盈触发 | ⏳ |
| TC010 | P1 | integration | 端到端回测流程 | ⏳ |

### 5. 缠论形态识别模块 (test_chanlun_structure.py) - 新增

| ID | Priority | Type | Description | Status |
|----|----------|------|-------------|--------|
| TC024 | P0 | happy_path | 顶分型识别 | ⏳ |
| TC025 | P0 | happy_path | 底分型识别 | ⏳ |
| TC034 | P0 | happy_path | 笔的构建 | ⏳ |
| TC026 | P0 | happy_path | 线段识别 | ⏳ |
| TC035 | P1 | exception | 线段破坏判断 | ⏳ |
| TC027 | P0 | happy_path | 中枢计算（基于笔） | ⏳ |
| TC036 | P2 | boundary | 中枢延伸判断 | ⏳ |
| TC037 | P1 | exception | 平坦K线无分型 | ⏳ |
| TC038 | P1 | exception | 笔必须穿越中轴 | ⏳ |

### 6. 大盘环境过滤模块 (test_market_filter.py) - 新增

| ID | Priority | Type | Description | Status |
|----|----------|------|-------------|--------|
| TC028 | P1 | happy_path | 牛市识别（均线多头） | ⏳ |
| TC029 | P1 | happy_path | 熊市识别（均线空头） | ⏳ |
| TC030 | P1 | happy_path | 震荡市识别 | ⏳ |
| TC039 | P1 | happy_path | 牛市策略参数调整 | ⏳ |
| TC040 | P1 | happy_path | 熊市策略参数调整 | ⏳ |
| TC041 | P1 | exception | 熊市信号过滤 | ⏳ |
| TC042 | P2 | boundary | 数据不足返回中性 | ⏳ |

### 7. 风控模块 (test_risk_manager.py) - 新增

| ID | Priority | Type | Description | Status |
|----|----------|------|-------------|--------|
| TC031 | P0 | happy_path | 单股仓位计算 | ⏳ |
| TC032 | P0 | happy_path | 总仓控制 | ⏳ |
| TC043 | P0 | happy_path | 多股票仓位分配 | ⏳ |
| TC033 | P1 | happy_path | 动态止损调整 | ⏳ |
| TC044 | P1 | happy_path | 跟踪止损 | ⏳ |
| TC045 | P1 | happy_path | 动态止盈调整 | ⏳ |
| TC046 | P1 | exception | 最大持仓股票数限制 | ⏳ |
| TC047 | P2 | exception | 风险敞口计算 | ⏳ |
| TC048 | P2 | exception | 回撤减仓 | ⏳ |
| TC049 | P1 | exception | 零资金异常处理 | ⏳ |
| TC050 | P1 | exception | 仓位超限处理 | ⏳ |

### 8. AI 评估模块 (test_ai_evaluator.py) - 新增 ✨

| ID | Priority | Type | Description | Status |
|----|----------|------|-------------|--------|
| TC051 | P0 | happy_path | LLM 客户端初始化 | ⏳ |
| TC052 | P0 | happy_path | LLM 生成成功 | ⏳ |
| TC053 | P0 | happy_path | Prompt 构建 | ⏳ |
| TC054 | P1 | exception | 无效 Prompt 处理 | ⏳ |
| TC055 | P1 | exception | API 调用失败 | ⏳ |
| TC056 | P1 | exception | JSON 解析 | ⏳ |
| TC057 | P1 | exception | 非法 JSON 处理 | ⏳ |
| TC058 | P2 | integration | 信号评估集成测试 | ⏳ |
| TC059 | P2 | integration | 快速评估 | ⏳ |

## 测试统计

- **总用例数**: 59
- **P0 核心路径**: 19
- **P1 异常场景**: 31
- **P2 边界条件**: 9

## 模块概览

| 模块 | 用例数 | P0 | P1 | P2 |
|------|--------|----|----|----|
| 涨停识别 | 8 | 2 | 2 | 4 |
| 缠论分析 | 7 | 3 | 3 | 1 |
| 数据获取 | 6 | 2 | 3 | 1 |
| 回测策略 | 7 | 3 | 1 | 3 |
| 缠论形态 | 9 | 4 | 4 | 1 |
| 大盘过滤 | 7 | 0 | 6 | 1 |
| 风控管理 | 11 | 3 | 5 | 3 |
| AI 评估 | 9 | 3 | 4 | 2 |

## 覆盖率目标

- 核心模块（P0）：100%
- 重要模块（P1）：>80%
- 辅助模块（P2）：>60%
