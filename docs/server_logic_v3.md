# Slot Game Server Simulation Logic

## 1. 核心模块 (Core Modules)

服务器端模拟主要由以下三个 Python 模块组成：

1.  **Engine (`src/engine.py`)**: 
    -   负责管理用户状态（余额、下注、RTP统计、连输计数等）。
    -   执行模拟循环（Simulation Loop）。
    -   不包含核心数学逻辑，只负责流程控制和状态更新。

2.  **Strategy (`src/strategies/json_store_strategy.py`)**: 
    -   **核心数学引擎**。
    -   负责计算单次旋转的结果 (Outcome)。
    -   读取配置文件和 JSON 赔率表。

3.  **App (`src/app.py`)**:
    -   Web 接口 (Flask)。
    -   处理前端请求，启动 `Engine`，并聚合统计数据返回给前端。

---

## 2. 参数读取与配置 (Configuration)

前端界面传递的参数包含以下关键项：

### 2.1 基础参数 (User Context)
-   `initial_balance`: 初始余额
-   `bet`: 单次下注额
-   `vip_level`: 用户 VIP 等级 (影响可用的赔率组)

### 2.2 策略参数 (Strategy Config)
这些参数直接决定了数学模型的行为：
-   **Base Win Rate (`base_win_rate`)**: 基础中奖概率 (例如 0.15)。
-   **Loss Multiplier (`loss_multiplier`)**: 亏损补偿系数 (例如 1.05)。
-   **RTP Compensation (`rtp_compensation`)**: RTP 补偿系数 (例如 1.0)。
-   **Group Weights (`group_weights`)**: 各赔率组 (Group 1-6) 的基础权重。
-   **RTP Conditions (`rtp_conditions`)**: (当前版本暂未使用，保留接口)。

---

## 3. 中奖逻辑流程 (Spin Logic)

每次旋转 (`spin`) 的决策过程分为以下几个严格的步骤：

### Step 1: 计算动态胜率 (Dynamic Win Rate)

系统首先计算当前旋转的胜率。

-   **RTP 系数查找 (RTP Coefficient)**:
    -   系统根据玩家当前的 RTP (`current_rtp`) 查找配置表 `rtp_conditions`。
    -   查找逻辑：`if current_rtp <= condition.max`: 使用该行的 `val / 100` 作为系数。
    -   例如：如果配置 `{max: 0.95, val: 120}`, 且当前 RTP 为 0.90，则 RTP系数 = 1.20。

-   **公式**:
    ```python
    if fail_streak >= 2:
        WinRate = BaseWinRate * LossMultiplier * (Streak - 1) * RTP_Coefficient
    else:
        WinRate = BaseWinRate
    ```
-   **逻辑说明**:
    -   如果用户连输次数 (`Streak`) 小于 2，使用基础胜率。
    -   如果连输 2 次或以上，胜率开始按公式非线性提升。
    -   `(Streak - 1)`: 连输次数越多，概率提升越显著。
    -   `RTP_Coefficient`: 如果玩家历史亏损较多 (Low RTP)，该系数通常 > 1.0，从而进一步提升中奖率；反之如果赢多了，系数 < 1.0 降低胜率。

### Step 2: 随机判定 (RNG Check)

-   系统生成一个 0.0 到 1.0 之间的随机数 (`rnd_roll`)。
-   **判定**:
    -   如果 `rnd_roll > WinRate`: **判定为未中奖 (LOSS)**。直接从 Group 0 (Loss Group) 返回结果。
    -   如果 `rnd_roll <= WinRate`: **判定为预中奖 (WIN)**，进入下一步筛选。

### Step 3: RTP 安全检查 (RTP Safety Check)

即使判定为中奖，系统必须确保这次派彩不会导致整体 RTP 超过上限（默认 1.0）。

-   **计算允许最大赔付 (Max Payout)**:
    -   Target MaxRTP = 1.0
    -   `AllowedPayout = (MaxRTP * (TotalWagered + CurrentBet)) - TotalWon`
    -   逻辑：假设本次下注后，玩家总RTP刚好达到 100%。此时允许玩家拿走的最大金额就是 `MaxRTP * 总投入 - 已赢取金额`。
-   **计算最大允许倍数 (Max Multiplier)**:
    -   `MaxMultAllowed = AllowedPayout / Bet`
-   **筛选**:
    -   系统会检查 Group 1 到 Group 6。
    -   如果某组的**最低赔率要求**高于 `MaxMultAllowed`，该组被**剔除**。
    -   例如：如果当前RTP空间只能赔付 15倍，那么 Group 4 (20x-30x) 及以上的组都会被剔除。

### Step 4: 权重选择 (Weighted Selection)

-   从剩余的合格组 (Candidates) 中，根据配置的 `group_weights` 进行加权随机选择。
-   **如果是空集**:
    -   如果没有任何组符合 RTP 要求（例如允许赔付极低），系统会强制**转为未中奖 (LOSS)**。

### Step 5: 结果生成 (Outcome Generation)

-   确定了 Group ID 后（例如 Group 2），系统从对应的 JSON 数据文件 (`data/xxx.json`) 的该该组列表中，随机抽取一个具体的条目 (Item)。
-   返回条目包含：`stops` (卷轴停止位置), `multiplier` (实际赔率), `lines` (中奖线)。

---

## 4. 示例追踪 (Trace Example)

假设参数: Base=0.15, LossMult=1.05, RTPComp=1.0. 连输 4 次 (Streak=4).

1.  **胜率计算**:
    -   `WinRate = 0.15 * 1.05 * (4 - 1) * 1.0 = 0.15 * 1.05 * 3 = 0.4725` (47.25%)
2.  **RNG**:
    -   随机数 0.30。 0.30 <= 0.4725 -> **WIN**.
3.  **RTP 检查**:
    -   历史总押 100, 总赢 80. Bet 10.
    -   MaxRTP = 1.0. 允许总赢 = 1.0 * (100+10) = 110.
    -   AllowedPayout = 110 - 80 = 30.
    -   MaxMult = 30 / 10 = 3.0x.
4.  **筛选**:
    -   Group 1 (Wait, Group definitions usually start small. Let's say G1 is <5x). G1 OK.
    -   Group 2 (Min 5x). 5x > 3.0x -> Excluded.
    -   ... Excluded.
    -   **Result**: 只能选 Group 1.
5.  **最终结果**:
    -   返回 Group 1 的某个结果（例如 2.5x）。
