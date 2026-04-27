# 回测使用指南

## 快速开始

### 1. 配置 API（已完成 ✓）

你的 API 配置已保存在 `.env` 文件中：
```bash
AI_API_KEY=_y82PeXl9UmxQ4I
DEEPSEEK_BASE_URL=https://ms-cnhh7fpx-100005643178-sw.gw.ap-shanghai.ti.tencentcs.com/ms-cnhh7fpx/v1/
AI_MODEL=deepseek-chat
```

### 2. 测试连接

```bash
cd /Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy

# 安装依赖（首次使用）
pip install -r requirements.txt

# 测试连接
python3 test_connection.py
```

### 3. 运行回测

#### 单只股票
```bash
# 基础回测
python3 backtest.py sh.600000

# 指定时间范围
python3 backtest.py sh.600000 --start 2026-01-01 --end 2026-04-14

# 指定初始资金
python3 backtest.py sh.600000 --capital 500000
```

#### 多只股票
```bash
python3 backtest.py sh.600000 sh.600001 sh.600002
```

#### 禁用 AI 评估（仅规则引擎）
```bash
python3 backtest.py sh.600000 --no-ai
```

### 4. 查看报告

报告默认保存在 `output/` 目录：
```
output/sh.600000_report.md
```

## 回测流程

```
输入股票代码
    ↓
获取历史数据（baostock）
    ↓
缠论结构分析（笔/线段/中枢）
    ↓
信号识别（涨停+买点）
    ↓
AI 评估（使用你的 API）
    ↓
生成评估报告
```

## 示例输出

```markdown
# 📊 sh.600000 缠论评估报告

## 基本信息
- 股票代码: sh.600000
- 当前价格: 10.85
- 评估时间: 2026-04-14 17:45

## 缠论结构
- 分型数量: 15
- 笔数量: 8
- 线段数量: 3
- 中枢: ZG=11.20, ZD=10.50

## 信号统计
- 发现信号: 2 个

### 信号 1
- 日期: 2026-04-10
- 价格: 10.92
- 类型: limit_up_breakout
- 涨停幅度: 9.95%

**AI 建议**:
- 操作: wait
- 理由: 当前处于中枢震荡，建议等待更明确信号
```

## 高级用法

### 自定义代理 Agent

创建专用 agent 进行股票评估：

```bash
# 在 Control UI 中选择 chanlun-evaluator agent
# 发送股票代码即可获得评估报告
```

### 批量回测

创建股票池文件 `stock_pool.txt`：
```
sh.600000
sh.600001
sh.600002
sh.600003
```

运行批量回测：
```bash
python3 backtest.py $(cat stock_pool.txt)
```

## 注意事项

1. **数据时间**: 交易日 9:30-15:00 数据最新
2. **API 限制**: 注意 API 调用频率限制
3. **资金设置**: 根据实际情况调整 `--capital`
4. **报告保存**: 默认保存在 `output/` 目录

## 问题排查

### AI API 连接失败
```bash
# 检查环境变量
cat .env

# 测试 API
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print(f'API Key: {os.getenv(\"AI_API_KEY\")[:10]}...')
print(f'Base URL: {os.getenv(\"DEEPSEEK_BASE_URL\")}')
"
```

### 数据获取失败
```bash
# baostock 登录测试
python3 -c "
import baostock as bs
lg = bs.login()
print(f'登录结果: {lg.error_msg}')
bs.logout()
"
```

### 模块导入失败
```bash
# 安装依赖
pip install baostock pandas numpy python-dotenv requests
```

## 下一步

- [ ] 添加更多股票进行测试
- [ ] 调整策略参数
- [ ] 分析 AI 评估准确率
- [ ] 实盘模拟验证
