#!/bin/bash
# 缠论策略回测启动脚本

echo "=================================="
echo "缠论策略回测系统"
echo "=================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3"
    exit 1
fi

# 检查环境变量
if [ -z "$AI_API_KEY" ]; then
    echo "警告: AI_API_KEY 未设置"
    echo "提示: export AI_API_KEY='your_key'"
fi

# 运行回测
python3 backtest.py "$@"
