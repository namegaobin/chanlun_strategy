# ChanLun Strategy - 缠论量化策略系统

> 基于缠中说禅理论的A股量化选股与回测系统

---

## 📋 目录

- [项目概述](#项目概述)
- [核心功能](#核心功能)
- [快速开始](#快速开始)
- [缠论核心算法详解](#缠论核心算法详解)
  - [1. K线包含关系处理](#1-k线包含关系处理)
  - [2. 分型识别与笔的构建](#2-分型识别与笔的构建)
  - [3. 线段的识别](#3-线段的识别)
  - [4. 中枢的计算](#4-中枢的计算)
  - [5. 盘整背驰判断](#5-盘整背驰判断)
  - [6. 第三类买卖点识别](#6-第三类买卖点识别)
- [项目架构](#项目架构)
- [API文档](#api文档)
- [测试覆盖](#测试覆盖)
- [改进计划](#改进计划)

---

## 项目概述

**ChanLun Strategy** 是一个基于缠中说禅理论的量化交易系统，主要用于：

- **A股选股**：通过缠论形态识别发现潜在买卖点
- **策略回测**：基于历史数据验证交易策略
- **AI评估**：集成腾讯云AI对交易信号进行智能评估

### 核心策略

**目标**：捕捉"3-5天内涨停突破且形成5分钟级别第三类买点"的股票

**方法**：
1. 日线级别中枢识别，并在离开段里面有涨停
2. 日线回调出现的第三类买点筛选
3. 回调的这一笔在30分钟/5分钟级别区间套确认
4. AI风险评估与仓位建议

---

## 核心功能

| 模块 | 功能 | 状态 |
|------|------|------|
| 数据采集 | 直接连接数据库获取 | ✅ 已实现 |
| 分型识别 | 顶底分型检测 | ⚠️ 需完善包含关系 |
| 笔的构建 | 从分型构建笔 | ⚠️ 需完善穿越逻辑 |
| 中枢计算 | 笔中枢/线段中枢 | ⚠️ 需重构 |
| 第三类买点 | 突破回抽买点 | ⚠️ 需添加区间套 |
| AI评估 | 腾讯云API集成 | ✅ 已实现 |
| 回测系统 | backtrader集成 | ✅ 已实现 |

---

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
cd /Users/alvingao/.openclaw/workspace/tdd-architect/chanlun_strategy

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据采集

```bash
# 采集沪深300成分股日线数据（示例）
python fetch_data.py --codes 600000,600036,000001 --days 120

# 采集分钟数据
python fetch_data.py --codes 600000 --period 5 --days 30
```

### 3. 策略回测

```bash
# 单股回测
python backtest.py --code 600000 --start 2025-01-01 --end 2026-04-14

# 批量回测
python batch_backtest.py --codes hs300 --days 120
```

### 4. AI评估

```bash
# 配置腾讯云API密钥
cp .env.example .env
# 编辑 .env 文件，填入 TENCENT_SECRET_ID 和 TENCENT_SECRET_KEY

# 执行信号评估
python full_market_evaluation.py --output ./output/signals.json
```

---

## 缠论核心算法详解

### ⚠️ 重要提示

当前代码实现存在以下**关键缺陷**，需要在README中详细说明正确逻辑：

---

### 1. K线包含关系处理

#### 定义（缠论原文）

> **包含关系**：一根K线的高低点完全在另一根K线的高低点范围内。

#### 处理规则

**上升趋势中的包含处理**：
```
如果 高点1 < 高点2 且 低点1 < 低点2（K1包含在K2中）
→ 取 高点=高点2, 低点=max(低点1, 低点2)

处理原则：上升趋势中，高点取高的，低点取高的
```

**下降趋势中的包含处理**：
```
如果 高点1 > 高点2 且 低点1 > 低点2（K2包含在K1中）
→ 取 高点=min(高点1, 高点2), 低点=低点2

处理原则：下降趋势中，高点取低的，低点取低的
```

#### 当前实现问题

❌ **代码位置**：`src/chanlun_structure.py`

❌ **问题**：完全没有实现包含关系处理

#### 正确实现方案

```python
def process_inclusion(df: pd.DataFrame) -> pd.DataFrame:
    """
    处理K线包含关系
    
    Args:
        df: 原始K线数据（需包含 high, low, close 列）
        
    Returns:
        处理后的K线数据（包含关系已合并）
    """
    processed = []
    i = 0
    
    while i < len(df):
        if i + 1 >= len(df):
            processed.append(df.iloc[i])
            break
            
        k1 = df.iloc[i]
        k2 = df.iloc[i + 1]
        
        # 判断包含关系
        is_included = (
            (k1['high'] <= k2['high'] and k1['low'] >= k2['low']) or  # K1在K2中
            (k1['high'] >= k2['high'] and k1['low'] <= k2['low'])     # K2在K1中
        )
        
        if is_included:
            # 根据趋势方向处理
            # 判断趋势：用前一根K线的收盘价与当前K线的关系
            if i > 0:
                prev_close = df.iloc[i - 1]['close']
                trend = 'up' if k1['close'] > prev_close else 'down'
            else:
                # 无法判断趋势时，默认按下降趋势处理（保守）
                trend = 'down'
            
            if trend == 'up':
                # 上升趋势：取高高点、高低点
                merged = {
                    'high': max(k1['high'], k2['high']),
                    'low': max(k1['low'], k2['low']),
                    'open': k1['open'],
                    'close': k2['close'],
                    'date': k2['date']
                }
            else:
                # 下降趋势：取低高点、低低点
                merged = {
                    'high': min(k1['high'], k2['high']),
                    'low': min(k1['low'], k2['low']),
                    'open': k1['open'],
                    'close': k2['close'],
                    'date': k2['date']
                }
            
            # 创建合并后的K线
            merged_k = pd.Series(merged)
            processed.append(merged_k)
            i += 2  # 跳过已处理的K线
        else:
            processed.append(k1)
            i += 1
    
    return pd.DataFrame(processed)
```

#### 测试用例

```python
def test_inclusion_upward_trend():
    """
    上升趋势包含处理
    Given: K1=[10, 12], K2=[11, 13] (K1被包含在K2中)
    When: 处理包含关系（上升趋势）
    Then: 合并为 K=[12, 13] (取高高点、高低点)
    """
    df = pd.DataFrame({
        'high': [12, 13],
        'low': [10, 11],
        'close': [11, 12],
        'open': [10, 11],
        'date': ['2026-04-01', '2026-04-02']
    })
    result = process_inclusion(df)
    assert result.iloc[0]['high'] == 13
    assert result.iloc[0]['low'] == 11  # 取高低点
    
def test_inclusion_downward_trend():
    """
    下降趋势包含处理
    Given: K1=[10, 13], K2=[11, 12] (K2被包含在K1中)
    When: 处理包含关系（下降趋势）
    Then: 合并为 K=[11, 10] (取低高点、低低点)
    """
    df = pd.DataFrame({
        'high': [13, 12],
        'low': [10, 11],
        'close': [11, 10],
        'open': [13, 12],
        'date': ['2026-04-01', '2026-04-02']
    })
    result = process_inclusion(df)
    assert result.iloc[0]['high'] == 12  # 取低高点
    assert result.iloc[0]['low'] == 10   # 取低低点
```

---

### 2. 分型识别与笔的构建

#### 2.1 分型定义

**顶分型**：
```
中间K线的高点最高
K1: [10.0, 10.5]
K2: [10.5, 11.0] ← 顶分型
K3: [10.3, 10.8]
```

**底分型**：
```
中间K线的低点最低
K1: [10.3, 10.8]
K2: [9.8, 10.2] ← 底分型
K3: [10.0, 10.5]
```

#### 2.2 笔的定义

> **笔**：顶分型与底分型之间的价格走势

**向上笔**：底分型 → 顶分型
**向下笔**：顶分型 → 底分型

#### 2.3 笔的成立条件

1. **时间条件**：一笔至少包含5根K线（包含处理后的K线）
2. **空间条件**：必须穿越前一笔的中轴
3. **方向条件**：
   - 向上笔：终点 > 起点
   - 向下笔：终点 < 起点

#### 当前实现问题

❌ **代码位置**：`src/chanlun_structure.py` → `build_bi_from_fractals()`

❌ **问题**：
- 缺少穿越中轴的判断
- 缺少笔延伸的处理
- 笔的验证逻辑不完整

#### 正确实现方案

```python
def build_bi_from_fractals(
    fractals: List[Fractal],
    df: pd.DataFrame,
    min_klines: int = 5
) -> List[Bi]:
    """
    从分型构建笔（完整版）
    
    Args:
        fractals: 分型列表（已过滤相邻同类型）
        df: K线数据（已处理包含关系）
        min_klines: 最少K线数
        
    Returns:
        有效的笔列表
    """
    if len(fractals) < 2:
        return []
    
    bi_list = []
    
    for i in range(len(fractals) - 1):
        f1 = fractals[i]
        f2 = fractals[i + 1]
        
        # 必须是顶底交替
        if f1.type == f2.type:
            continue
        
        # 确定方向
        if f1.type == FractalType.BOTTOM and f2.type == FractalType.TOP:
            direction = Direction.UP
            start_price = f1.price
            end_price = f2.price
        elif f1.type == FractalType.TOP and f2.type == FractalType.BOTTOM:
            direction = Direction.DOWN
            start_price = f1.price
            end_price = f2.price
        else:
            continue
        
        # 检查K线数量（至少5根）
        kline_count = f2.index - f1.index + 1
        if kline_count < min_klines:
            continue
        
        # 检查方向一致性
        if direction == Direction.UP and end_price <= start_price:
            continue
        if direction == Direction.DOWN and end_price >= start_price:
            continue
        
        # 计算笔的高低点
        bi_data = df.iloc[f1.index:f2.index + 1]
        high = bi_data['high'].max()
        low = bi_data['low'].min()
        
        # 检查穿越前一笔的中轴（如果有前一笔）
        if bi_list:
            prev_bi = bi_list[-1]
            mid_line = (prev_bi.high + prev_bi.low) / 2
            
            if direction == Direction.UP:
                # 向上笔必须穿越前一笔中轴
                if low <= mid_line and end_price <= prev_bi.high:
                    continue
            else:
                # 向下笔必须穿越前一笔中轴
                if high >= mid_line and end_price >= prev_bi.low:
                    continue
        
        bi = Bi(
            direction=direction,
            start_index=f1.index,
            end_index=f2.index,
            start_price=start_price,
            end_price=end_price,
            high=high,
            low=low
        )
        
        bi_list.append(bi)
    
    return bi_list
```

#### 测试用例

```python
def test_bi_must_cross_middle_line():
    """
    笔必须穿越前笔中轴
    
    Given: 
    - 笔1: 向上笔 [10.0, 12.0]
    - 笔2: 向下笔，低点11.5（未穿越中轴11.0）
    When: 构建笔
    Then: 笔2无效，继续寻找下一个底分型
    """
    pass

def test_bi_minimum_klines():
    """
    笔至少包含5根K线
    
    Given: 顶分型和底分型之间只有3根K线
    When: 构建笔
    Then: 该笔无效
    """
    pass
```

---

### 3. 线段的识别

#### 定义

> **线段**：由至少3笔构成的、具有明确方向的走势

#### 线段破坏判断

**特征序列破坏法**：

```
向上线段的破坏条件：
1. 出现一笔向下笔，且该笔的低点 < 前一笔向上笔的高点
2. 该向下笔的高点，低于前一笔向上笔的低点

简化判断：连续两笔同向时，线段延伸
         反向笔出现时，检查是否构成线段破坏
```

#### 当前实现问题

⚠️ **代码位置**：`src/chanlun_structure.py` → `detect_xianduan_from_bi()`

⚠️ **问题**：线段破坏逻辑过于简化，缺少特征序列判断

#### 改进建议

```python
def detect_xianduan_from_bi_v2(bi_list: List[Bi], min_bi: int = 3) -> List[Xianduan]:
    """
    从笔构建线段（改进版）
    
    线段破坏条件：
    1. 特征序列：将线段中的反向笔视为特征序列
    2. 破坏判断：出现特征序列元素的新低/新高
    
    Args:
        bi_list: 笔列表
        min_bi: 最少笔数
        
    Returns:
        线段列表
    """
    if len(bi_list) < min_bi:
        return []
    
    xianduan_list = []
    start_idx = 0
    direction = bi_list[0].direction
    
    for i in range(1, len(bi_list)):
        # 检查是否出现破坏
        if bi_list[i].direction != direction:
            # 反向笔出现，检查是否构成破坏
            # 简化判断：统计同向笔数量
            same_dir_count = 0
            for j in range(start_idx, i):
                if bi_list[j].direction == direction:
                    same_dir_count += 1
            
            if same_dir_count >= min_bi // 2:
                # 构成线段
                segment_bi = [bi_list[j] for j in range(start_idx, i) 
                              if bi_list[j].direction == direction]
                
                if len(segment_bi) >= min_bi // 2:
                    xd = Xianduan(
                        direction=direction,
                        start_index=segment_bi[0].start_index,
                        end_index=segment_bi[-1].end_index,
                        start_price=segment_bi[0].start_price,
                        end_price=segment_bi[-1].end_price,
                        bi_list=segment_bi
                    )
                    xianduan_list.append(xd)
                
                # 开始新线段
                start_idx = i
                direction = bi_list[i].direction
    
    return xianduan_list
```

---

### 4. 中枢的计算

#### 定义（缠论原文）

> **中枢**：至少连续3笔（或线段）的价格重叠区间

**计算公式**：
```
ZG (中枢高点) = min(笔高点序列)
ZD (中枢低点) = max(笔低点序列)

有效中枢条件：ZG > ZD
```

#### 中枢的构成

一个完整的中枢包括：

```
笔1: 进入段（向上笔或向下笔，进入中枢）
笔2: 确认段1
笔3: 确认段2
笔4: 确认段3（至少3笔重叠）
笔5: 离开段（向上笔或向下笔，离开中枢）
```

**示意图**：
```
价格
 ↑
 │      ╭─╮        离开段（向上突破）
 │     ╱   ╲
 │    │     │ ZG ──── 中枢高点
 │    │     │
 │    │     │ ZD ──── 中枢低点
 │     ╲   ╱
 │      ╰─╯        进入段（向上进入）
 └─────────────────→ 时间
       ↑
    确认三笔
```

#### 当前实现问题

❌ **代码位置**：`src/chanlun_analyzer.py` → `calculate_zhongshu()`

❌ **严重错误**：使用K线而不是笔来计算中枢

```python
# ❌ 错误的实现
def calculate_zhongshu(df: pd.DataFrame, min_periods: int = 3) -> Optional[Dict]:
    # 使用K线计算，这是错误的！
    zg = np.min(highs[-min_periods:])
    zd = np.max(lows[-min_periods:])
```

#### 正确实现方案

```python
def calculate_zhongshu_from_bi(
    bi_list: List[Bi],
    min_bi: int = 3
) -> Optional[Zhongshu]:
    """
    从笔计算中枢（正确实现）
    
    中枢构成：
    - 进入段：第1笔（可以是任意方向）
    - 确认段：第2、3、4笔（至少3笔重叠）
    - 离开段：第5笔（可以是任意方向）
    
    Args:
        bi_list: 笔列表
        min_bi: 构成中枢的最少笔数（默认3）
        
    Returns:
        Zhongshu对象，无效时返回None
    """
    if len(bi_list) < min_bi:
        return None
    
    # 取最近的笔进行计算
    recent_bi = bi_list[-min_bi:]
    
    # ZG = min(笔高点)
    zg = min(bi.high for bi in recent_bi)
    
    # ZD = max(笔低点)
    zd = max(bi.low for bi in recent_bi)
    
    # 验证中枢有效性
    if zg <= zd:
        return None
    
    # 识别进入段和离开段
    enter_bi = None
    exit_bi = None
    
    if len(bi_list) > min_bi:
        # 进入段：中枢前的最后一笔
        enter_bi = bi_list[-(min_bi + 1)]
        # 离开段：中枢后的第一笔（如果有）
        if len(bi_list) > min_bi + 1:
            exit_bi = bi_list[-1]
    
    return Zhongshu(
        zg=zg,
        zd=zd,
        start_index=recent_bi[0].start_index,
        end_index=recent_bi[-1].end_index,
        level=1,  # 笔中枢
        bi_list=recent_bi,
        enter_bi=enter_bi,  # 进入段
        exit_bi=exit_bi     # 离开段
    )
```

#### 测试用例

```python
def test_zhongshu_from_bi():
    """
    中枢计算（基于笔）
    
    Given:
    - 笔1: 向上笔 [10.0 → 11.5]
    - 笔2: 向下笔 [11.5 → 10.5]
    - 笔3: 向上笔 [10.5 → 11.0]
    
    When: 计算中枢
    Then:
    - ZG = min(11.5, 11.5, 11.0) = 11.0
    - ZD = max(10.0, 10.5, 10.5) = 10.5
    """
    bi_list = [
        Bi(direction=Direction.UP, low=10.0, high=11.5),
        Bi(direction=Direction.DOWN, low=10.5, high=11.5),
        Bi(direction=Direction.UP, low=10.5, high=11.0)
    ]
    
    zhongshu = calculate_zhongshu_from_bi(bi_list)
    assert zhongshu.zg == 11.0
    assert zhongshu.zd == 10.5
```

---

### 5. 盘整背驰判断

#### 定义

> **盘整背驰**：在盘整走势中，离开段的力度小于进入段，且价格未创新高/新低

#### 判断标准

**使用MACD面积判断力度**：

```
进入段MACD面积 = A1
离开段MACD面积 = A2

背驰条件：
1. |A2| < |A1|（力度减弱）
2. 价格未创新高（向上离开）或未创新低（向下离开）
```

#### 当前实现问题

⚠️ **代码位置**：`src/chanlun_analyzer.py` → `check_divergence()`

⚠️ **问题**：
- 没有基于笔的中枢进入/离开段判断
- MACD面积计算过于简化

#### 改进方案

```python
def check_pan_divergence(
    bi_list: List[Bi],
    zhongshu: Zhongshu,
    df: pd.DataFrame
) -> Dict:
    """
    判断盘整背驰（形态学方法）
    
    Args:
        bi_list: 笔列表
        zhongshu: 中枢对象
        df: K线数据（用于计算MACD）
        
    Returns:
        {
            'has_divergence': bool,
            'divergence_type': 'top' | 'bottom' | None,
            'strength_ratio': float  # 离开段/进入段力度比
        }
    """
    if not zhongshu.enter_bi or not zhongshu.exit_bi:
        return {'has_divergence': False}
    
    # 计算进入段MACD面积
    enter_start = zhongshu.enter_bi.start_index
    enter_end = zhongshu.enter_bi.end_index
    enter_macd_area = calculate_macd_area(df.iloc[enter_start:enter_end + 1])
    
    # 计算离开段MACD面积
    exit_start = zhongshu.exit_bi.start_index
    exit_end = zhongshu.exit_bi.end_index
    exit_macd_area = calculate_macd_area(df.iloc[exit_start:exit_end + 1])
    
    # 判断背驰
    if exit_macd_area == 0:
        return {'has_divergence': False}
    
    strength_ratio = abs(exit_macd_area) / abs(enter_macd_area)
    
    # 力度减弱（< 0.618 认为是明显背驰）
    if strength_ratio < 0.618:
        # 检查是否创新高/新低
        if zhongshu.exit_bi.direction == Direction.UP:
            # 向上离开，检查是否创新高
            price_new_high = zhongshu.exit_bi.high > zhongshu.enter_bi.high
            if not price_new_high:
                return {
                    'has_divergence': True,
                    'divergence_type': 'top',
                    'strength_ratio': strength_ratio
                }
        else:
            # 向下离开，检查是否创新低
            price_new_low = zhongshu.exit_bi.low < zhongshu.enter_bi.low
            if not price_new_low:
                return {
                    'has_divergence': True,
                    'divergence_type': 'bottom',
                    'strength_ratio': strength_ratio
                }
    
    return {'has_divergence': False}


def calculate_macd_area(df: pd.DataFrame) -> float:
    """
    计算MACD柱状图面积
    
    Args:
        df: K线数据
        
    Returns:
        MACD面积（正值表示红柱，负值表示绿柱）
    """
    closes = df['close'].values
    
    # 计算MACD
    ema12 = pd.Series(closes).ewm(span=12).mean()
    ema26 = pd.Series(closes).ewm(span=26).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9).mean()
    macd = (dif - dea) * 2
    
    # 计算面积
    area = macd.sum()
    
    return area
```

---

### 6. 第三类买卖点识别

#### 定义（缠论原文）

> **第三类买点**：价格向上离开中枢后，回抽不破中枢高点（ZG），重新向上时买入。

#### 构成条件

```
1. 突破段：价格向上突破中枢ZG
2. 回抽段：价格回落，但低点 > ZG（不破中枢）
3. 反转段：价格重新向上，确认买点
```

**示意图**：
```
价格
 ↑
 │           ╭─╮  突破段
 │          ╱   ╲
 │         ╱     ╲ ← 回抽段（不破ZG）
 │        ╱       ╲
 │       ╱         ╲ ← 第三类买点
 │─────ZG───────────╱────────
 │      │         ╱
 │      │ 中枢   ╱
 │      │       ╱
 │─────ZD──────╱─────────────
 └──────────────────────────→ 时间
```

#### 区间套逻辑（关键！）

> **区间套**：在日线发现买点后，到30分钟/5分钟级别精确定位

**区间套步骤**：

```
步骤1：日线级别
- 发现日线第三类买点（突破中枢ZG，回抽不破ZG）
- 标记为"候选买点"

步骤2：30分钟级别
- 在日线买点附近，寻找30分钟级别的中枢
- 确认30分钟也出现第三类买点
- 如果确认，则加强信号

步骤3：5分钟级别
- 在30分钟买点附近，寻找5分钟级别的精确买点
- 等待5分钟出现底分型+向上笔确认
- 执行买入
```

#### 当前实现问题

❌ **代码位置**：`src/chanlun_analyzer.py` → `find_third_buy_points()`

❌ **严重缺陷**：
1. **没有区间套逻辑** - 只在单一级别判断
2. **没有多级别联立** - 缺少30分钟/5分钟确认
3. **回抽判断错误** - 使用 `pullback_price > zg` 而不是 `pullback_low > zg`

#### 正确实现方案

```python
def detect_third_buy_point_with_interval(
    df_daily: pd.DataFrame,
    df_30min: pd.DataFrame,
    df_5min: pd.DataFrame
) -> Dict:
    """
    第三类买点识别（区间套版本）
    
    Args:
        df_daily: 日线数据
        df_30min: 30分钟数据
        df_5min: 5分钟数据
        
    Returns:
        {
            'has_signal': bool,
            'daily_signal': dict,
            'min30_signal': dict,
            'min5_signal': dict,
            'confidence': float  # 信号强度（0-1）
        }
    """
    result = {
        'has_signal': False,
        'daily_signal': None,
        'min30_signal': None,
        'min5_signal': None,
        'confidence': 0.0
    }
    
    # Step 1: 日线级别检测
    daily_signal = find_third_buy_point_single_level(df_daily, level='daily')
    if not daily_signal:
        return result
    
    result['daily_signal'] = daily_signal
    result['confidence'] = 0.3  # 日线确认，初步信号
    
    # Step 2: 30分钟级别确认
    # 找到日线买点对应的30分钟数据区间
    daily_buy_date = daily_signal['date']
    min30_signal = find_third_buy_point_single_level(
        df_30min, 
        level='30min',
        near_date=daily_buy_date
    )
    
    if min30_signal:
        result['min30_signal'] = min30_signal
        result['confidence'] = 0.6  # 30分钟确认，信号加强
    
    # Step 3: 5分钟级别精确买入点
    min5_signal = find_precise_entry_in_5min(df_5min, daily_buy_date)
    
    if min5_signal:
        result['min5_signal'] = min5_signal
        result['confidence'] = 0.9  # 三级共振，强信号
        result['has_signal'] = True
    
    return result


def find_third_buy_point_single_level(
    df: pd.DataFrame,
    level: str = 'daily',
    near_date: str = None
) -> Optional[Dict]:
    """
    在单一级别寻找第三类买点
    
    Args:
        df: K线数据
        level: 级别名称
        near_date: 只在这个日期附近寻找（用于区间套）
        
    Returns:
        买点信息或None
    """
    # 1. 处理包含关系
    df_processed = process_inclusion(df)
    
    # 2. 识别分型
    fractals = detect_all_fractals(df_processed)
    fractals = filter_fractals(fractals)
    
    # 3. 构建笔
    bi_list = build_bi_from_fractals(fractals, df_processed)
    
    if len(bi_list) < 5:
        return None
    
    # 4. 计算中枢
    zhongshu = calculate_zhongshu_from_bi(bi_list[-5:])
    if not zhongshu:
        return None
    
    zg = zhongshu.zg
    
    # 5. 寻找第三类买点
    # 条件：突破ZG → 回抽不破ZG → 重新向上
    
    for i in range(len(bi_list) - 4):
        # 检查是否有笔向上突破ZG
        if bi_list[i].direction == Direction.UP and bi_list[i].high > zg:
            # 找到突破笔，检查后续回抽
            for j in range(i + 1, len(bi_list) - 1):
                if bi_list[j].direction == Direction.DOWN:
                    # 检查回抽是否不破ZG
                    if bi_list[j].low > zg:
                        # 回抽不破ZG，检查是否重新向上
                        if j + 1 < len(bi_list):
                            next_bi = bi_list[j + 1]
                            if next_bi.direction == Direction.UP:
                                # 确认第三类买点
                                signal = {
                                    'level': level,
                                    'date': df.iloc[next_bi.start_index]['date'],
                                    'price': next_bi.start_price,
                                    'zg': zg,
                                    'zd': zhongshu.zd,
                                    'breakout_bi': bi_list[i],
                                    'pullback_bi': bi_list[j],
                                    'entry_bi': next_bi
                                }
                                
                                # 如果指定了日期，检查是否在附近
                                if near_date:
                                    signal_date = pd.to_datetime(signal['date'])
                                    target_date = pd.to_datetime(near_date)
                                    if abs((signal_date - target_date).days) <= 5:
                                        return signal
                                else:
                                    return signal
    
    return None


def find_precise_entry_in_5min(
    df_5min: pd.DataFrame,
    target_date: str
) -> Optional[Dict]:
    """
    在5分钟级别寻找精确买入点
    
    条件：
    1. 形成底分型
    2. 收盘价突破底分型高点
    3. MACD金叉（可选）
    
    Args:
        df_5min: 5分钟K线数据
        target_date: 目标日期
        
    Returns:
        精确买点信息
    """
    # 过滤目标日期的数据
    df_day = df_5min[df_5min['date'].str.startswith(target_date)]
    
    if len(df_day) < 10:
        return None
    
    # 寻找底分型
    for i in range(1, len(df_day) - 1):
        k1 = df_day.iloc[i - 1]
        k2 = df_day.iloc[i]
        k3 = df_day.iloc[i + 1]
        
        # 底分型判断
        if k2['low'] < k1['low'] and k2['low'] < k3['low']:
            # 底分型确认
            # 检查是否向上突破
            if i + 2 < len(df_day):
                k4 = df_day.iloc[i + 2]
                if k4['close'] > k2['high']:
                    # 突破底分型高点，确认买点
                    return {
                        'level': '5min',
                        'time': k4['date'],
                        'price': k4['close'],
                        'fractal_low': k2['low']
                    }
    
    return None
```

#### 测试用例

```python
def test_third_buy_point_interval():
    """
    第三类买点区间套测试
    
    Given:
    - 日线：出现第三类买点
    - 30分钟：同一位置也出现第三类买点
    - 5分钟：形成底分型并向上突破
    
    When: 执行区间套检测
    Then: confidence = 0.9，确认为强信号
    """
    pass

def test_third_buy_point_pullback_not_break_zg():
    """
    第三类买点回抽不破ZG
    
    Given:
    - 中枢 ZG = 11.0, ZD = 10.5
    - 突破笔：high = 11.8
    - 回抽笔：low = 11.2 (> ZG)
    - 重新向上笔：确认
    
    When: 检测第三类买点
    Then: 返回买点信号
    """
    pass
```

---

## 项目架构

```
chanlun_strategy/
├── src/                      # 核心源码
│   ├── __init__.py
│   ├── data_fetcher.py       # 数据采集（baostock）
│   ├── limit_up_detector.py  # 涨停识别
│   ├── chanlun_structure.py  # 缠论形态识别 ⚠️
│   ├── chanlun_analyzer.py   # 缠论分析器 ⚠️
│   ├── market_filter.py      # 市场筛选
│   ├── risk_manager.py       # 风险管理
│   ├── ai_evaluator.py       # AI评估（腾讯云）
│   └── backtest_strategy.py  # 回测策略（backtrader）
│
├── tests/                    # 测试用例
│   ├── test_chanlun_structure.py
│   ├── test_chanlun_analyzer.py
│   └── ...
│
├── examples/                 # 示例脚本
├── output/                   # 输出结果
│
├── main.py                   # 主程序入口
├── backtest.py               # 回测脚本
├── batch_backtest.py         # 批量回测
├── fetch_data.py             # 数据获取
├── full_market_evaluation.py # 全市场评估
│
├── requirements.txt          # 依赖列表
├── .env                      # 环境变量（API密钥）
└── README.md                 # 本文档
```

---

## API文档

### 数据采集

```python
from src.data_fetcher import BaostockDataFetcher

# 初始化
fetcher = BaostockDataFetcher()

# 获取日线数据
df = fetcher.get_daily_data(
    code='sh.600000',
    start_date='2025-01-01',
    end_date='2026-04-14'
)

# 获取分钟数据
df_5min = fetcher.get_minute_data(
    code='sh.600000',
    period='5',
    start_date='2026-04-01',
    end_date='2026-04-14'
)
```

### 缠论分析

```python
from src.chanlun_structure import ChanLunStructureAnalyzer

# 初始化
analyzer = ChanLunStructureAnalyzer(df)

# 执行分析
result = analyzer.analyze()

# 获取结果
fractals = result['fractals']      # 分型列表
bi_list = result['bi_list']        # 笔列表
xianduan_list = result['xianduan_list']  # 线段列表
zhongshu = result['zhongshu']      # 中枢
```

### AI评估

```python
from src.ai_evaluator import AIEvaluator

# 初始化
evaluator = AIEvaluator()

# 评估信号
evaluation = evaluator.evaluate_signal(
    code='600000',
    signal_type='第三类买点',
    price=11.50,
    zhongshu={'zg': 11.0, 'zd': 10.5}
)

# 返回结果
{
    'risk_level': 'low',
    'suggestion': '建议买入',
    'stop_loss': 10.8,
    'target_price': 13.0,
    'confidence': 0.85
}
```

---

## 测试覆盖

运行测试：

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_chanlun_structure.py -v

# 查看覆盖率
pytest tests/ --cov=src --cov-report=html
```

当前测试状态：

| 模块 | 测试用例 | 覆盖率 | 状态 |
|------|---------|--------|------|
| 分型识别 | 5 | 60% | ⚠️ 需补充 |
| 笔的构建 | 4 | 40% | ⚠️ 需补充 |
| 中枢计算 | 3 | 30% | ❌ 需重构 |
| 第三类买点 | 2 | 20% | ❌ 需重构 |

---

## 改进计划

### 🔴 高优先级（P0）

1. **实现K线包含关系处理**
   - 文件：`src/chanlun_structure.py`
   - 工作量：2-3天
   - 影响：所有后续分析的基础

2. **重构中枢计算逻辑**
   - 文件：`src/chanlun_analyzer.py`
   - 问题：当前使用K线而非笔计算
   - 工作量：1-2天

3. **实现区间套逻辑**
   - 文件：新增 `src/interval_analysis.py`
   - 功能：多级别联立确认买点
   - 工作量：3-5天

### 🟡 中优先级（P1）

4. **完善笔的构建逻辑**
   - 添加穿越中轴判断
   - 添加笔延伸处理
   - 工作量：2天

5. **实现形态学盘整背驰**
   - 基于笔的进入/离开段判断
   - MACD面积计算
   - 工作量：2-3天

### 🟢 低优先级（P2）

6. **补充测试用例**
   - 覆盖所有核心逻辑
   - 目标覆盖率：80%+
   - 工作量：3-5天

7. **优化性能**
   - 批量处理优化
   - 缓存机制
   - 工作量：2天

---

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 许可证

本项目仅供学习研究使用，不构成投资建议。

---

## 联系方式

- 项目维护者：TDD 架构师
- 创建时间：2026-04-14
- 最后更新：2026-04-16

---

## 附录：缠论核心概念速查

| 概念 | 定义 | 计算 |
|------|------|------|
| 包含关系 | K线高低点完全在另一根K线范围内 | 合并处理 |
| 顶分型 | 三根K线，中间高点最高 | high2 > high1 且 high2 > high3 |
| 底分型 | 三根K线，中间低点最低 | low2 < low1 且 low2 < low3 |
| 笔 | 顶分型与底分型之间的走势 | 至少5根K线 |
| 线段 | 至少3笔构成的方向性走势 | 特征序列判断 |
| 中枢 | 至少3笔的价格重叠区间 | ZG=min(笔高点), ZD=max(笔低点) |
| 第三类买点 | 突破中枢后回抽不破ZG | 区间套精确定位 |
| 盘整背驰 | 离开段力度<进入段 | MACD面积对比 |

---

**⚠️ 重要提示**：本项目的缠论实现仍在完善中，建议结合缠论原文（教你炒股票系列）理解核心概念。
