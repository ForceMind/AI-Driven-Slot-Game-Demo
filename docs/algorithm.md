# Slot Master Pro - 核心算法文档

## 1. 核心机制概述

本项目采用 **PRD (Pseudo Random Distribution)** 伪随机分布算法来控制中奖频率，结合 **动态 RTP 平衡** 和 **阶梯式解锁** 机制，实现可控、成瘾且数值安全的博彩体验。

### 1.1 C值系统 (PRD 算法)
不同于传统老虎机的独立随机事件，本系统引入 "C值" (Constant) 累加机制：
- **机制**：每次未中奖，中奖概率线性增加。
- **公式**：$P(n) = C \times n$
  - $P(n)$: 第 $n$ 次旋转的中奖概率
  - $C$: 基础概率常数 (Base Probability)
  - $n$: 当前连续未中奖次数 (Fail Streak) + 1
- **效果**：
  - 避免了玩家长期不中奖的挫败感（保底机制）。
  - 避免了连续中奖导致的数值失控。
  - 使得中奖分布更加均匀，符合 "运气守恒" 的直觉。

### 1.2 资金安全风控 (20% 规则)
- **规则**：单次中奖金额不得超过当前账户余额的 **20%**。
- **目的**：防止滚雪球效应导致系统破产，延长用户游戏时间。
- **实现**：在筛选中奖结果集时，自动过滤掉 `Payout > Balance * 0.2` 的选项。

### 1.3 阶梯式解锁 (Tiered Unlocking)
- **规则**：高倍率奖项需要用户的 "累计下注额" (Total Wagered) 达到一定阈值才能解锁。
- **目的**：奖励忠诚用户，防止新号一发入魂后流失。
- **配置示例**：
  - Tier 1 (1-5倍): 无限制
  - Tier 2 (10-20倍): 累计下注 > $1000
  - Tier 3 (50-100倍): 累计下注 > $5000

### 1.4 长期 RTP 控制
- **目标**：97% (可配置)
- **实现**：
  - 系统维护一个全局或个人的 `Current RTP`。
  - 当 `Current RTP > Target RTP` 时，动态降低 $C$ 值或暂时禁用高倍率 Bucket。
  - 当 `Current RTP < Target RTP` 时，动态增加 $C$ 值或增加高倍率 Bucket 的权重。

---

## 2. 结果生成流程 (Spin Logic)

1.  **输入**：用户下注 (Bet), 当前余额 (Balance), 累计下注 (Total Wagered), 连续未中次数 (Fail Streak)。
2.  **判定是否中奖 (PRD Check)**：
    - 计算当前概率 $P = C \times (Fail Streak + 1)$
    - 随机数 $R \in [0, 1)$
    - 若 $R < P$ -> **判定为中奖 (WIN)**
    - 若 $R \ge P$ -> **判定为未中奖 (LOSS)**
3.  **结果集筛选 (Bucket Selection)**：
    - **IF LOSS**:
        - 从 `Loss Buckets` 中随机选取一个结果（图形不连线）。
        - `Fail Streak += 1`
    - **IF WIN**:
        - 筛选所有 `Win Buckets`：
            1.  **风控过滤**：`Win Amount <= Balance * 0.2`
            2.  **阶梯过滤**：`Bucket Tier Requirement <= Total Wagered`
        - 如果筛选后列表为空（例如余额太低无法支付最小奖），强制转为 **LOSS**。
        - 根据 Bucket 权重 (Weight) 加权随机选择一个结果。
        - `Fail Streak = 0`
4.  **输出**：矩阵 (Matrix), 赢分 (Payout), 赢线 (Lines)。

---

## 3. 数据结构

### 3.1 Bucket (结果桶)
预先生成并分类好的结果集，存储在内存中。
```json
{
  "id": "Tier_1_5x",
  "multiplier_range": [1, 5],
  "outcomes": [ ...list of reel stops... ],
  "weight": 1000,
  "unlock_threshold": 0
}
```

### 3.2 User State (用户状态)
```python
class UserState:
    balance: float
    total_wagered: float
    fail_streak: int
    current_c: float # 动态调整的C值
```
