#!/usr/bin/env python3
"""
股票数据采集 - 正确处理 baostock 数据
"""
import baostock as bs
import pymysql
import pandas as pd
import time
from datetime import datetime, timedelta
import sys

print("="*60)
print("股票数据采集系统")
print("="*60)

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 33306,  # SSH隧道映射端口
    'user': 'chanClaw',
    'password': 'chanClaw@2026',
    'database': 'chanClaw',
    'charset': 'utf8mb4'
}

# ============================================
# 1. 登录 baostock
# ============================================
print("\n[1] 连接 baostock...")
lg = bs.login()
if lg.error_code != '0':
    print(f"✗ 登录失败: {lg.error_msg}")
    sys.exit(1)
print("✓ baostock 登录成功")

# ============================================
# 2. 连接数据库
# ============================================
print("\n[2] 连接数据库...")
conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()
print("✓ 数据库连接成功")

# ============================================
# 3. 获取股票列表 - 手动指定
# ============================================
print("\n[3] 获取股票列表...")

# 手动指定一些测试股票（确保格式正确）
test_stocks = [
    ('sh.600000', '浦发银行'),
    ('sh.600036', '招商银行'),
    ('sh.600519', '贵州茅台'),
    ('sh.600887', '伊利股份'),
    ('sz.000001', '平安银行'),
    ('sz.000002', '万科A'),
    ('sz.000333', '美的集团'),
    ('sz.000651', '格力电器'),
    ('sh.601318', '中国平安'),
    ('sh.601398', '工商银行'),
]

stock_count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
stock_list = test_stocks[:stock_count]
print(f"✓ 将采集 {len(stock_list)} 只股票数据")

# ============================================
# 4. 采集股票数据
# ============================================
print("\n[4] 开始采集股票数据...")

# 时间范围 - 使用正确的格式 YYYY-MM-DD
end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

print(f"  时间范围: {start_date} ~ {end_date}")

success_count = 0
total_records = 0

for i, (code, name) in enumerate(stock_list, 1):
    print(f"  [{i}/{len(stock_list)}] {code} {name}...", end=" ", flush=True)
    
    try:
        # 获取日K线数据 - 使用正确格式
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,volume,amount,turn,pctChg",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            print("无数据")
            continue
        
        print(f"{len(data_list)} 条", end=" ")
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 批量插入数据库
        insert_count = 0
        for _, row in df.iterrows():
            try:
                cursor.execute(
                    """INSERT INTO stock_daily 
                    (ts_code, trade_date, open, high, low, close, volume, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    open=VALUES(open), high=VALUES(high), low=VALUES(low),
                    close=VALUES(close), volume=VALUES(volume), amount=VALUES(amount)""",
                    (
                        code,
                        str(row['date']),
                        float(row['open']) if row['open'] and row['open'] != '' else None,
                        float(row['high']) if row['high'] and row['high'] != '' else None,
                        float(row['low']) if row['low'] and row['low'] != '' else None,
                        float(row['close']) if row['close'] and row['close'] != '' else None,
                        int(float(row['volume'])) if row['volume'] and row['volume'] != '' else None,
                        float(row['amount']) if row['amount'] and row['amount'] != '' else None,
                    )
                )
                insert_count += 1
            except Exception as e:
                print(f"插入错误: {e}", end=" ")
                pass
        
        conn.commit()
        total_records += insert_count
        success_count += 1
        print(f"✓ 插入 {insert_count} 条")
        
        time.sleep(0.5)
        
    except Exception as e:
        print(f"✗ 错误: {e}")

# ============================================
# 5. 插入股票基本信息
# ============================================
print("\n[5] 更新股票基本信息...")
for code, name in stock_list:
    try:
        cursor.execute(
            """INSERT INTO stock_basic (ts_code, symbol, name, market)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE name=VALUES(name)""",
            (code, code.split('.')[1], name, code.split('.')[0].upper())
        )
    except:
        pass
conn.commit()
print("✓ 股票基本信息更新完成")

# ============================================
# 6. 统计结果
# ============================================
cursor.execute("SELECT COUNT(*) FROM stock_daily")
final_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(DISTINCT ts_code) FROM stock_daily")
stock_total = cursor.fetchone()[0]

print("\n" + "="*60)
print("采集完成")
print("="*60)
print(f"成功采集: {success_count} 只股票")
print(f"本次记录: {total_records} 条")
print(f"数据库总量: {final_count} 条")
print(f"股票数量: {stock_total} 只")
print("="*60)

# 关闭连接
cursor.close()
conn.close()
bs.logout()

print("\n✅ 数据已导入数据库！")
print("\n下一步: 运行回测")
print("  ./venv/bin/python db_backtest.py sh.600000")