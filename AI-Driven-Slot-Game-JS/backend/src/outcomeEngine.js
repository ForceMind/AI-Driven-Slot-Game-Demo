const fs = require('fs');
const path = require('path');

// 游戏结果引擎类：负责生成拉霸游戏结果，基于 PRD 算法和桶机制
class OutcomeEngine {
    constructor(configOverride = null) {
        // 初始化配置和数据结构
        this.config = {}; // 游戏配置
        this.buckets = {}; // 桶集合，每个桶存储可能的停止位置
        this.reels = []; // 转轮配置
        this.symbols = {}; // 符号定义
        this.payTable = {}; // 赔付表
        this.lines = {}; // 中奖线定义
        this.isReady = false; // 引擎是否已初始化
        this.bucketStats = {}; // 桶统计信息

        // 如果提供配置覆盖，则使用它，否则加载默认配置
        if (configOverride) {
            this.config = configOverride;
            this._parseConfig();
        } else {
            this.loadConfig();
        }
    }

    // 从文件加载默认配置
    loadConfig() {
        const configPath = path.join(__dirname, 'game_config.json');
        if (!fs.existsSync(configPath)) {
            console.error(`Config not found at ${configPath}`);
            return;
        }
        const rawData = fs.readFileSync(configPath);
        this.config = JSON.parse(rawData);
        this._parseConfig();
    }

    // 解析配置并初始化数据结构
    _parseConfig() {
        // 提取配置中的关键数据
        this.reels = this.config.reel_sets; // 转轮符号集合
        this.symbols = this.config.symbols; // 符号名称映射
        this.payTable = this.config.pay_table; // 赔付倍数表
        this.lines = this.config.lines; // 中奖线坐标
        this.bucketsConfig = this.config.buckets; // 桶配置（胜负分类）
        this.settings = this.config.settings; // 全局设置（RTP、C值等）

        // 标准化桶配置，确保 min_win 和 max_win 字段存在
        for (const key in this.bucketsConfig) {
            const cfg = this.bucketsConfig[key];
            if (cfg.min !== undefined && cfg.min_win === undefined) cfg.min_win = cfg.min;
            if (cfg.max !== undefined && cfg.max_win === undefined) cfg.max_win = cfg.max;
            if (cfg.min_win === undefined) cfg.min_win = 0;
            if (cfg.max_win === undefined) cfg.max_win = 0;
        }

        // 初始化桶数组
        for (const key in this.bucketsConfig) {
            this.buckets[key] = [];
        }

        console.log("Initializing buckets...");
        this.initializeBuckets(); // 开始初始化桶
    }

    // 初始化桶：遍历所有可能的转轮停止位置，分类存储到桶中
    initializeBuckets() {
        const reelLen = this.config.reels_length; // 每个转轮的符号数量
        const totalCombinations = Math.pow(reelLen, 5); // 5个转轮的总组合数
        const useSampling = totalCombinations > 2000000; // 如果组合数过大，使用采样

        const startTime = Date.now();

        if (useSampling) {
            // 使用采样：随机生成10万样本，避免遍历所有组合
            console.log(`State space ${totalCombinations} too large, using sampling (100k samples).`);
            for (let i = 0; i < 100000; i++) {
                const stops = Array.from({ length: 5 }, () => Math.floor(Math.random() * reelLen));
                this._processStop(stops); // 处理每个停止位置
            }
        } else {
            // 遍历所有组合：迭代生成所有可能的停止位置
            console.log(`Traversing all ${totalCombinations} combinations...`);
            const stops = [0, 0, 0, 0, 0];
            while (true) {
                this._processStop([...stops]);

                // 递增停止位置（类似计数器）
                let i = 4;
                while (i >= 0) {
                    stops[i]++;
                    if (stops[i] < reelLen) {
                        break;
                    }
                    stops[i] = 0;
                    i--;
                }
                if (i < 0) break; // 所有组合已遍历
            }
        }

        console.log(`Buckets initialized in ${(Date.now() - startTime) / 1000}s`);
        // 输出每个桶的大小
        for (const key in this.buckets) {
            console.log(`Bucket ${key}: ${this.buckets[key].length} outcomes`);
        }
        this.isReady = true; // 初始化完成
    }

    // 处理单个停止位置：计算中奖并分类到桶中
    _processStop(stops) {
        const matrix = this._getMatrixFromStops(stops); // 生成结果矩阵
        const { totalPayout, isNearMiss } = this._calculateWin(matrix); // 计算中奖
        const bucketName = this._classifyWin(totalPayout, isNearMiss); // 分类桶

        // 将停止位置添加到对应桶中（限制每个桶最多5万条）
        if (bucketName && this.buckets[bucketName]) {
            if (this.buckets[bucketName].length < 50000) {
                this.buckets[bucketName].push(stops);
            }
        }
    }

    // 根据停止位置生成3x5的结果矩阵
    _getMatrixFromStops(stops) {
        const matrix = [];
        const reelLen = this.config.reels_length;
        for (let r = 0; r < 3; r++) { // 3行
            const row = [];
            for (let c = 0; c < 5; c++) { // 5列
                const idx = (stops[c] + r) % reelLen; // 计算符号索引（考虑偏移）
                let symbolId = "L1"; // 默认符号
                if (c < this.reels.length && idx < this.reels[c].length) {
                    symbolId = this.reels[c][idx]; // 从转轮配置获取符号
                }
                row.push(symbolId);
            }
            matrix.push(row);
        }
        return matrix;
    }

    // 计算矩阵的中奖情况：遍历所有中奖线，计算总赔付
    _calculateWin(matrix) {
        let totalPayout = 0.0; // 总赔付倍数
        const winningLines = []; // 中奖线列表

        // 遍历每条中奖线
        for (const lineIdStr in this.lines) {
            const coords = this.lines[lineIdStr]; // 线的坐标 [(r,c), ...]
            const lineSymbols = coords.map(([r, c]) => matrix[r][c]); // 提取线上的符号
            const { count, symbolId } = this._checkLineMatch(lineSymbols); // 检查匹配

            if (count >= 3) { // 至少3个连续匹配
                if (this.payTable[symbolId] && this.payTable[symbolId][count]) {
                    const multiplier = this.payTable[symbolId][count]; // 获取赔付倍数
                    totalPayout += multiplier;
                    
                    let symbolName = "Unknown";
                    if (this.symbols[symbolId]) {
                        symbolName = this.symbols[symbolId].name; // 获取符号名称
                    }

                    winningLines.push({
                        line_id: parseInt(lineIdStr),
                        amount: multiplier, // 倍数（后续会乘以下注）
                        symbol: symbolName,
                        count: count
                    });
                }
            }
        }

        // 检查近失（Near Miss）：如果有2个SCATTER，标记为近失
        let isNearMiss = false;
        let scatterCount = 0;
        for (const row of matrix) {
            for (const s of row) {
                if (s === "SCATTER") scatterCount++;
            }
        }
        if (scatterCount === 2) isNearMiss = true;

        return { totalPayout, winningLines, isNearMiss };
    }

    // 检查线上的符号匹配：计算连续相同符号的数量
    _checkLineMatch(line) {
        if (!line || line.length === 0) return { count: 0, symbolId: "" };

        const first = line[0];
        let matchId = first;

        // 如果第一个是WILD，寻找下一个非WILD符号作为匹配目标
        if (first === "WILD") {
            for (const s of line) {
                if (s !== "WILD") {
                    matchId = s;
                    break;
                }
            }
        }

        let count = 0;
        for (const s of line) {
            if (s === matchId || s === "WILD") { // WILD可以匹配任何符号
                count++;
            } else {
                break; // 连续匹配中断
            }
        }
        return { count, symbolId: matchId };
    }

    // 根据赔付倍数和近失情况分类桶
    _classifyWin(multiplier, isNearMiss) {
        if (multiplier === 0) {
            return isNearMiss ? "Loss_NearMiss" : "Loss_Random"; // 近失或普通亏损
        }

        // 根据倍数范围匹配胜级桶
        for (const tier in this.bucketsConfig) {
            if (tier.startsWith("Win_Tier")) {
                const cfg = this.bucketsConfig[tier];
                if (multiplier >= cfg.min_win && multiplier < cfg.max_win) {
                    return tier;
                }
                if (cfg.max_win >= 1000 && multiplier >= cfg.min_win) { // 处理大奖
                    return tier;
                }
            }
        }
        return "Win_Tier_1"; // 默认胜级
    }

    // 执行一次拉霸旋转：选择桶、生成结果、计算赔付
    spin(userState, runtimeConfig = null) {
        if (!this.isReady) return { error: "Engine not ready" };

        // 提取用户状态参数
        const bet = userState.current_bet || 10.0; // 下注金额
        const balance = userState.wallet_balance || 1000.0; // 当前余额
        const initialBalance = userState.initial_balance || 1000.0; // 初始余额
        const totalSpins = userState.total_spins || 0; // 总旋转次数
        const failStreak = userState.fail_streak || 0; // 连败次数
        const maxHistoricalBalance = userState.max_historical_balance || balance; // 历史最高余额
        const historicalRtp = userState.historical_rtp || 0.0; // 历史 RTP
        const ignoreSafety = userState.simulation_mode || false; // 是否忽略安全检查（模拟模式）

        // 选择桶（基于 PRD 算法和用户状态）
        let bucketName = this._selectBucket(
            bet, balance, initialBalance, totalSpins, failStreak,
            ignoreSafety, maxHistoricalBalance, historicalRtp, runtimeConfig
        );

        if (!ignoreSafety) {
            console.log(`[OutcomeEngine] Bet: ${bet}, Balance: ${balance}, Spins: ${totalSpins}, FailStreak: ${failStreak}. Selected Bucket: ${bucketName}`);
        }

        // 如果桶为空，回退到 Loss_Random
        if (!this.buckets[bucketName] || this.buckets[bucketName].length === 0) {
            console.log(`[OutcomeEngine] Bucket ${bucketName} empty! Fallback to Loss_Random`);
            bucketName = "Loss_Random";
        }

        // 从桶中随机选择一个停止位置
        const stops = this.buckets[bucketName][Math.floor(Math.random() * this.buckets[bucketName].length)];
        const matrix = this._getMatrixFromStops(stops); // 生成矩阵
        const { totalPayout, winningLines } = this._calculateWin(matrix); // 计算中奖

        const totalPayoutAmount = totalPayout * bet; // 实际赔付金额
        
        // 更新中奖线金额（乘以下注）
        winningLines.forEach(wl => wl.amount = wl.amount * bet);

        // 更新连败次数
        const newFailStreak = totalPayoutAmount > 0 ? 0 : failStreak + 1;

        return {
            matrix, // 结果矩阵
            winning_lines: winningLines, // 中奖线详情
            total_payout: totalPayoutAmount, // 总赔付金额
            is_win: totalPayoutAmount > 0, // 是否中奖
            bucket_type: bucketName, // 使用的桶类型
            balance_update: totalPayoutAmount - bet, // 余额变化
            fail_streak: newFailStreak // 新连败次数
        };
    }

    // 选择桶：基于 PRD 算法和多种因素选择合适的桶
    _selectBucket(bet, balance, initialBalance, totalSpins, failStreak, ignoreSafety, maxHistoricalBalance, historicalRtp, runtimeConfig) {
        // 使用运行时配置或默认设置
        let settings = this.settings;
        let bucketsConfig = this.bucketsConfig;

        if (runtimeConfig) {
            settings = runtimeConfig.settings || this.settings;
            const rawBuckets = runtimeConfig.buckets || this.bucketsConfig;
            bucketsConfig = {};
            for (const k in rawBuckets) {
                const cfg = { ...rawBuckets[k] };
                if (cfg.min !== undefined && cfg.min_win === undefined) cfg.min_win = cfg.min;
                if (cfg.max !== undefined && cfg.max_win === undefined) cfg.max_win = cfg.max;
                if (cfg.min_win === undefined) cfg.min_win = 0;
                if (cfg.max_win === undefined) cfg.max_win = 0;
                bucketsConfig[k] = cfg;
            }
        }

        // 基础 C 值（PRD 概率常数）
        let baseC = settings.base_c_value || 0.05;
        const targetRtp = settings.target_rtp || 0.97;

        // 根据历史 RTP 动态调整 C 值（RTP 调控）
        if (totalSpins > 50) {
            const rtpRatio = targetRtp > 0 ? historicalRtp / targetRtp : 1.0;
            if (rtpRatio < 0.5) baseC *= 2.5; // RTP 太低，增加中奖概率
            else if (rtpRatio < 0.7) baseC *= 1.8;
            else if (rtpRatio < 0.8) baseC *= 1.2;
            else if (rtpRatio < 0.95) baseC *= 1.1;
            else if (rtpRatio > 2.0) baseC *= 0.3; // RTP 太高，减少中奖概率
            else if (rtpRatio > 1.5) baseC *= 0.5;
            else if (rtpRatio > 1.05) baseC *= 0.6;
        }

        // 计算中奖概率（PRD 公式）
        let winProb = baseC * (failStreak + 1);
        if (winProb > 1.0) winProb = 1.0;

        // 决定是否中奖
        const isPrdWin = Math.random() < winProb;

        // 初始化桶权重
        const weights = {};
        for (const k in bucketsConfig) {
            weights[k] = bucketsConfig[k].weight;
        }

        // 根据 PRD 结果过滤桶
        if (!isPrdWin) {
            // 不中奖：禁用所有胜级桶
            for (const k in weights) {
                if (k.startsWith("Win_Tier")) weights[k] = 0;
            }
        } else {
            // 中奖：禁用所有亏损桶
            for (const k in weights) {
                if (k.startsWith("Loss_")) weights[k] = 0;
            }
        }

        // 进度阶梯：根据总旋转次数限制可用桶
        const progressTiers = settings.progress_tiers || [];
        if (progressTiers.length > 0) {
            let currentTier = null;
            const sortedTiers = [...progressTiers].sort((a, b) => a.min_spins - b.min_spins);
            for (const tier of sortedTiers) {
                if (totalSpins >= tier.min_spins) {
                    currentTier = tier;
                } else {
                    break;
                }
            }

            if (currentTier) {
                const allowed = currentTier.allowed_buckets || ["ALL"];
                if (!allowed.includes("ALL")) {
                    for (const k in weights) {
                        if (!allowed.includes(k)) weights[k] = 0;
                    }
                }
            }
        }

        // 高额玩家过滤：小额下注禁用大奖桶
        const highRollerThreshold = settings.high_roller_threshold || 50.0;
        if (bet < highRollerThreshold) {
            if (weights["Win_Tier_4"]) weights["Win_Tier_4"] = 0;
            if (weights["Win_Tier_5"]) weights["Win_Tier_5"] = 0;
        }

        // 最大余额限制：防止单次中奖超过初始余额的倍数
        const maxWinRatio = settings.max_win_ratio || 1.2;
        const maxAllowedBalance = initialBalance * maxWinRatio;

        let totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);

        // 如果权重为0，尝试回退
        if (totalWeight === 0) {
            if (isPrdWin) {
                // 中奖但无胜级桶可用，回退到亏损桶
                for (const k in bucketsConfig) {
                    if (k.startsWith("Loss_")) weights[k] = bucketsConfig[k].weight;
                }
                totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
                if (totalWeight === 0) return "Loss_Random";
            } else {
                return "Loss_Random";
            }
        }

        // 加权随机选择桶，最多重试3次（避免超出余额限制）
        for (let i = 0; i < 3; i++) {
            const r = Math.random() * totalWeight;
            let current = 0;
            let selected = "Loss_Random";
            
            for (const k in weights) {
                current += weights[k];
                if (r <= current) {
                    selected = k;
                    break;
                }
            }

            // 检查是否会超出最大余额
            const maxPotentialWin = bucketsConfig[selected].max_win * bet;
            if (balance + maxPotentialWin > maxAllowedBalance) {
                // 移除此桶，重新选择
                totalWeight -= weights[selected];
                weights[selected] = 0;
                if (totalWeight <= 0) return "Loss_Random";
                continue;
            }
            return selected;
        }

        return "Loss_Random"; // 默认回退
    }
}

module.exports = OutcomeEngine;
