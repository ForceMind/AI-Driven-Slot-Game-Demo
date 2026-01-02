
// 引入依赖
const express = require('express'); // Web 框架
const cors = require('cors'); // 跨域支持
const bodyParser = require('body-parser'); // 解析 JSON 请求体
const { v4: uuidv4 } = require('uuid'); // 生成唯一 Session ID
const OutcomeEngine = require('./outcomeEngine'); // 游戏核心逻辑
const fs = require('fs');
const path = require('path');


const app = express(); // 创建 Express 应用
const PORT = 3000; // 后端监听端口


app.use(cors()); // 启用 CORS
app.use(bodyParser.json()); // 解析 JSON 请求体


// --- 会话管理与引擎缓存 ---
const sessions = {}; // 存储所有用户会话
const engineCache = {}; // 缓存 OutcomeEngine 实例，避免重复初始化

// 加载默认配置
let defaultConfig = {};
const configPath = path.join(__dirname, 'game_config.json');
if (fs.existsSync(configPath)) {
    defaultConfig = JSON.parse(fs.readFileSync(configPath));
} else {
    console.error("CRITICAL: No configuration file found!");
}


// 获取（或缓存）OutcomeEngine 实例，避免重复初始化（初始化很耗时）
function getCachedEngine(config) {
    // Simple hash based on stringified config (simplified)
    const configStr = JSON.stringify(config);
    // In a real app, use a proper hash. Here we just use the object reference if possible or a simple key.
    // Since JS objects are by reference, we can't easily key by object content without hashing.
    // For this demo, we'll just create a new engine if config changes or use a singleton if config is static.
    // Let's just use a singleton for the default config and new instances for custom configs.
    
    // Optimization: Just return a new engine for now, initialization is fast enough or we can optimize later.
    // Actually, initialization takes time (traversing combinations). We MUST cache.
    
    // Let's use a simple approach: if config is strictly equal to default, use default engine.
    // Otherwise, create new.
    if (JSON.stringify(config) === JSON.stringify(defaultConfig)) {
        if (!engineCache['default']) {
            console.log("Initializing default engine...");
            engineCache['default'] = new OutcomeEngine(config);
        }
        return engineCache['default'];
    }
    // 自定义配置暂不缓存，防止内存泄漏
    return new OutcomeEngine(config);
}


// 预热默认引擎，首次启动时提前初始化
getCachedEngine(defaultConfig);


// 获取或创建用户 Session（基于 X-Session-ID）
function getSession(req) {
    let sessionId = req.header('X-Session-ID');
    if (!sessionId) {
        sessionId = uuidv4(); // 若无则新建
    }

    if (!sessions[sessionId]) {
        console.log(`Creating new session: ${sessionId}`);
        sessions[sessionId] = {
            id: sessionId,
            config: JSON.parse(JSON.stringify(defaultConfig)), // 独立配置副本
            history: [], // 近 100 次操作记录
            totalBet: 0.0,
            totalPayout: 0.0,
            lastAccess: Date.now()
        };
    }
    sessions[sessionId].lastAccess = Date.now();
    return sessions[sessionId];
}


// ========================
//       API 路由定义
// ========================


// 获取当前会话的配置
app.get('/api/config', (req, res) => {
    const session = getSession(req);
    res.json(session.config);
});


// 兼容老接口，获取配置
app.get('/config', (req, res) => {
    const session = getSession(req);
    res.json(session.config);
});


// 更新当前会话的配置
app.post('/config', (req, res) => {
    const session = getSession(req);
    try {
        session.config = req.body;
        // 配置变更后，spin 时会动态获取新引擎
        console.log(`[${session.id}] Configuration updated`);
        res.json({ status: "ok", message: "Config updated" });
    } catch (e) {
        console.error(e);
        res.status(400).json({ detail: `Invalid Configuration: ${e.message}` });
    }
});


// 单次拉霸（Spin）接口
app.post('/spin', (req, res) => {
    const session = getSession(req);
    const reqBody = req.body;
    
    console.log(`[${session.id}] SPIN START | Bet: ${reqBody.bet} | Balance: ${reqBody.current_balance}`);
    const startTime = Date.now();
    const spinId = uuidv4();

    // 0. 获取历史统计数据（用于 RTP 调控）
    const currentTotalBet = session.totalBet + 100.0;
    const currentTotalPayout = session.totalPayout + 95.0;
    const currentHistoryRtp = currentTotalBet > 0 ? currentTotalPayout / currentTotalBet : 0.95;

    // 1. 构造用户状态
    let userState = reqBody.user_state || {};
    if (!reqBody.user_state) {
        userState = {
            current_bet: reqBody.bet,
            wallet_balance: reqBody.current_balance,
            initial_balance: reqBody.current_balance,
            historical_rtp: currentHistoryRtp,
            max_historical_balance: reqBody.current_balance * 1.5,
            total_spins: session.history.length, // 近似累计
            fail_streak: 0 // 连败数，客户端可传
        };
    }
    userState.historical_rtp = currentHistoryRtp;

    // 2. 生成本次结果
    const engine = getCachedEngine(session.config);
    let result;
    try {
        result = engine.spin(userState, session.config);
    } catch (e) {
        console.error(`Engine Failed: ${e}`);
        res.status(500).json({ error: e.message });
        return;
    }

    // 3. 构造响应
    const spinResponse = {
        matrix: result.matrix, // 结果矩阵
        winning_lines: result.winning_lines, // 中奖线
        total_payout: result.total_payout, // 总中奖金额
        is_win: result.is_win, // 是否中奖
        bucket_type: result.bucket_type, // 桶类型
        reasoning: "AI Commentary (Node.js Port): Good luck!", // 占位
        balance_update: result.balance_update, // 余额变化
        history_rtp: currentHistoryRtp, // 当前 RTP
        fail_streak: result.fail_streak || 0 // 连败数
    };

    // 4. 日志与历史记录
    const latency = Date.now() - startTime;
    session.totalBet += reqBody.bet;
    session.totalPayout += spinResponse.total_payout;
    
    const newRtp = (session.totalPayout + 95.0) / (session.totalBet + 100.0);
    spinResponse.history_rtp = newRtp;

    session.history.push({
        Timestamp: new Date().toISOString(),
        Spin_ID: spinId,
        Bet: reqBody.bet,
        Payout: spinResponse.total_payout,
        Is_Win: spinResponse.is_win,
        Current_RTP: newRtp,
        Latency_ms: latency
    });

    // 只保留最近 100 条历史
    if (session.history.length > 100) {
        session.history = session.history.slice(-100);
    }

    console.log(`[${session.id}] SPIN END | Payout: ${spinResponse.total_payout} | Bucket: ${spinResponse.bucket_type}`);
    res.json(spinResponse);
});


// 批量模拟接口（用于前端图表）
app.post('/simulate', (req, res) => {
    const session = getSession(req);
    const params = req.body;
    
    let count = parseInt(params.spins || params.n_spins || 1000);
    console.log(`DEBUG: Received simulation request for ${count} spins`);
    
    if (count > 1000000) count = 1000000; // 限制最大模拟次数
    if (count < 1) count = 1000;
    const bet = params.bet || 10;

    const initialBalance = count * bet;
    let currentBalance = initialBalance;
    let maxBalance = currentBalance;
    
    let totalWagered = 0;
    let totalWon = 0;
    let failStreak = 0;
    const history = [];
    const errors = [];

    const engine = getCachedEngine(session.config);

    for (let i = 0; i < count; i++) {
        const currentRtp = totalWagered > 0 ? totalWon / totalWagered : 0;
        
        const userState = {
            current_bet: bet,
            wallet_balance: currentBalance,
            initial_balance: initialBalance,
            max_historical_balance: maxBalance,
            historical_rtp: currentRtp,
            fail_streak: failStreak,
            simulation_mode: true, // 标记为模拟
            total_spins: i // 传递当前轮数
        };

        try {
            const res = engine.spin(userState, session.config);
            failStreak = res.fail_streak || 0;
            const balUpdate = res.balance_update;
            currentBalance += balUpdate;
            maxBalance = Math.max(maxBalance, currentBalance);
            totalWagered += bet;
            totalWon += res.total_payout;

            history.push({
                spin: i + 1,
                balance: currentBalance,
                rtp: totalWagered > 0 ? totalWon / totalWagered : 0
            });
        } catch (e) {
            const errorMsg = `Sim error at spin ${i+1}: ${e.message}`;
            console.error(errorMsg);
            errors.push(errorMsg);
            if (errors.length > 10) break;
        }
    }

    const finalRtp = totalWagered > 0 ? totalWon / totalWagered : 0;
    console.log(`[${session.id}] SIMULATION END | Generated ${history.length} points`);

    res.json({
        final_balance: currentBalance,
        net_profit: currentBalance - initialBalance,
        total_rtp: finalRtp,
        history: history,
        debug_info: {
            requested_spins: count,
            received_params: params,
            errors: errors
        }
    });
});


// 查询历史记录（近 100 条）
app.get('/history', (req, res) => {
    const session = getSession(req);
    res.json([...session.history].reverse());
});


// 充值接口（仅记录日志，实际余额由前端维护）
app.post('/topup', (req, res) => {
    res.json({ status: "success", message: "Topup logged" });
});


// 重置用户数据接口（返回初始余额）
app.post('/reset/:userId', (req, res) => {
    res.json({ status: "reset", balance: 1000 });
});


// 启动服务
app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});
