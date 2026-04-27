#!/bin/bash
# 一键回测脚本

echo "=================================="
echo "缠论策略回测系统"
echo "=================================="

# 切换到项目目录
cd /Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy

# 运行快速测试
echo ""
echo "[快速测试]"
./venv/bin/python test_minimal.py 2>&1 | grep -v Warning

echo ""
echo "=================================="
echo "测试完成！"
echo ""
echo "运行完整回测："
echo "  ./venv/bin/python backtest.py sh.600000"
echo "=================================="
