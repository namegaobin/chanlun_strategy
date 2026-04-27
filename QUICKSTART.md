# 🚀 缠论策略回测系统 - 快速启动

## 你的 API 配置（已保存）

```bash
AI_API_KEY=_y82PeXl9UmxQ4I
Base URL: https://ms-cnhh7fpx-100005643178-sw.gw.ap-shanghai.ti.tencentcs.com/ms-cnhh7fpx/v1/
Model: deepseek-chat
```

## 三步启动

### 第 1 步：测试连接
```bash
cd /Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy
python3 test_connection.py
```

### 第 2 步：运行回测
```bash
# 单只股票
python3 backtest.py sh.600000

# 多只股票
python3 backtest.py sh.600000 sh.600001 sh.600002
```

### 第 3 步：查看报告
```bash
# 报告保存在
open output/sh.600000_report.md
```

## 常用命令

```bash
# 指定时间范围
python3 backtest.py sh.600000 --start 2026-01-01 --end 2026-04-14

# 指定初始资金
python3 backtest.py sh.600000 --capital 500000

# 禁用 AI（仅规则引擎）
python3 backtest.py sh.600000 --no-ai

# 保存到指定路径
python3 backtest.py sh.600000 --output my_report.md
```

## 项目结构

```
chanlun_strategy/
├── .env                 ← API 配置（已完成）
├── backtest.py          ← 回测主程序
├── test_connection.py   ← 连接测试
├── run_backtest.sh      ← 启动脚本
├── BACKTEST_GUIDE.md    ← 详细文档
└── output/              ← 报告输出目录
    └── sh.600000_report.md
```

## 下一步

1. ✅ API 已配置
2. ⏳ 运行 `python3 test_connection.py` 测试连接
3. ⏳ 运行 `python3 backtest.py sh.600000` 开始回测

---

**遇到问题？** 查看 `BACKTEST_GUIDE.md` 获取详细帮助。
