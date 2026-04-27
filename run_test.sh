#!/bin/bash
# 完整测试启动脚本

cd /Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy

# 加载环境变量
export $(cat .env | grep -v '^#' | xargs)

# 运行测试
./venv/bin/python test_connection.py
