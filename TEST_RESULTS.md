# 🚀 回测系统使用指南

## ✅ 测试结果

```
✓ 数据: 50 条
✓ 分型: 29 个
✓ 笔: 3 个
✓ 中枢: ZG=9.94, ZD=9.67
✓ AI 评估器就绪
✅ 测试完成！
```

## 📋 可用命令

### 1. 快速测试（推荐）
```bash
cd /Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy
./venv/bin/python test_minimal.py
```

### 2. 完整回测
```bash
# 单只股票
./venv/bin/python backtest.py sh.600000 --start 2026-02-01 --end 2026-04-14

# 多只股票
./venv/bin/python backtest.py sh.600000 sh.600519 sh.600036

# 查看报告
cat output/sh.600000_report.md
```

### 3. AI 评估测试
```bash
./venv/bin/python test_ai.py
```

## 📊 系统状态

| 组件 | 状态 | 说明 |
|------|------|------|
| Python环境 | ✅ | venv + Python 3.9 |
| 依赖包 | ✅ | 22个包已安装 |
| API配置 | ✅ | 腾讯云API已配置 |
| 数据获取 | ✅ | baostock连接成功 |
| 缠论分析 | ✅ | 分型/笔/中枢识别正常 |
| AI评估 | ✅ | API连接正常 |

## ⚡ 性能提示

- 非交易时间会使用模拟数据
- 首次运行需连接 baostock
- AI API调用需要几秒钟

## 📁 输出位置

```
chanlun_strategy/
├── output/
│   └── sh.600000_report.md    <- 回测报告
├── test_output.log             <- 测试日志
└── .env                        <- API配置
```

## 🎯 下一步

你已经完成了：
1. ✅ 创建虚拟环境
2. ✅ 安装所有依赖
3. ✅ 配置腾讯云API
4. ✅ 测试缠论分析
5. ✅ 验证AI连接

现在可以：
- 运行完整回测分析股票
- 调整策略参数优化信号
- 分析历史数据验证策略

---

**准备好了吗？开始你的第一次实战回测！**
