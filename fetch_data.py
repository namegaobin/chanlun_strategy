#!/usr/bin/env python3
"""
数据采集脚本 - 从 baostock 获取 A 股数据并存入数据库
"""
import sys
sys.path.insert(0, 'src')

import baostock as bs
import pymysql
import pandas as pd
from datetime import datetime, timedelta
import time

print("="*60)
print("A股数据采集系统")
print("="*60)

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
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
# 3. 获取股票列表
# ============================================
print("\n[3] 获取股票列表...")

# 获取沪深300成分股（示例）
rs = bs.query_hs300_stocks()
hs300 = []
while (rs.error_code == '0') & rs.next():
    hs300.append(rs.get_row_data())

print(f"✓ 获取沪深300: {len(hs300)} 只")

# 取前10只作为示例
stock_list = hs300[:10]
print(f"✓ 将采集前 {len(stock_list)} 只股票数据")

# ============================================
# 4. 采集股票数据
# ============================================
print("\n[4] 开始采集股票数据...")

# 时间范围
end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

print(f"  时间范围: {start_date} ~ {end_date}")

success_count = 0
total_records = 0

for i, stock_info in enumerate(stock_list, 1):
    code = stock_info[0]  # 股票代码
    name = stock_info[1]  # 股票名称
    
    print(f"\n  [{i}/{len(stock_list)}] {code} {name}...", end=" ")
    
    try:
        # 获取日K线数据
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 不复权
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            print("无数据")
            continue
        
        # 插入数据库
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 批量插入
        insert_count = 0
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO stock_daily 
                    (ts_code, trade_date, open, high, low, close, volume, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    open=VALUES(open), high=VALUES(high), low=VALUES(low),
                    close=VALUES(close), volume=VALUES(volume), amount=VALUES(amount)
                """, (
                    row['code'],
                    row['date'],
                    float(row['open']) if row['open'] else None,
                    float(row['high']) if row['high'] else None,
                    float(row['low']) if row['low'] else None,
                    float(row['close']) if row['close'] else None,
                    int(row['volume']) if row['volume'] else None,
                    float(row['amount']) if row['amount'] else None
                ))
                insert_count += 1
            except Exception as e:
                pass
        
        conn.commit()
        total_records += insert_count
        success_count += 1
        print(f"✓ {insert_count} 条")
        
        # 避免频繁请求
        time.sleep(0.3)
        
    except Exception as e:
        print(f"✗ {e}")

# ============================================
# 5. 更新股票基本信息
# ============================================
print("\n[5] 更新股票基本信息...")
for stock_info in stock_list:
    code = stock_info[0]
    name = stock_info[1]
    
    try:
        cursor.execute("""
            INSERT INTO stock_basic (ts_code, name, market)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE name=VALUES(name)
        """, (code, name, 'HS300'))
    except:
        pass

conn.commit()
print("✓ 股票基本信息更新完成")

# ============================================
# 6. 统计结果
# ============================================
cursor.execute("SELECT COUNT(*) FROM stock_daily")
total = cursor.fetchone()[0]

print("\n" + "="*60)
print("数据采集完成")
print("="*60)
print(f"成功采集: {success_count}/{len(stock_list)} 只股票")
print(f"总记录数: {total_records} 条")
print(f"数据库总量: {total} 条")

# 关闭连接
cursor.close()
conn.close()
bs.logout()

print("\n下一步: 运行回测")
print("  ./venv/bin/python db_backtest.py sh.600000")
