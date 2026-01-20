<script setup>
import { ref, onMounted, computed, provide } from 'vue'
import SlotGrid from './components/SlotGrid.vue'
import ConfigModal from './components/ConfigModal.vue'

const sessionId = ref('')

const initSession = () => {
    let sid = sessionStorage.getItem('slot_session_id')
    if (!sid) {
        // Simple UUID generator fallback
        sid = 'sess_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36)
        if (window.crypto && window.crypto.randomUUID) {
            sid = window.crypto.randomUUID()
        }
        sessionStorage.setItem('slot_session_id', sid)
    }
    sessionId.value = sid
}

// Global fetch wrapper with session header
const fetchAPI = async (url, options = {}) => {
    const headers = {
        ...options.headers,
        'X-Session-ID': sessionId.value
    }
    return fetch(url, { ...options, headers })
}

// Provide fetchAPI to child components
provide('fetchAPI', fetchAPI)

const gameState = ref({
    matrix: [
        ["?", "?", "?", "?", "?"],
        ["?", "?", "?", "?", "?"],
        ["?", "?", "?", "?", "?"],
    ],
    balance: 1000,
    bet: 10,
    lastWin: 0,
    winningLines: [],
    failStreak: 0,
    bucket: "Ready",
    totalWagered: 0,
    totalWon: 0,
    totalSpins: 0,
    initialBalance: 1000
})

const isSpinning = ref(false)
const config = ref(null)
const showConfig = ref(false)
const showSim = ref(false)

// Simulation State
const simConfig = ref({
    n_spins: 1000,
    bet: 10
})
const simResult = ref(null)
const isSimulating = ref(false)
const isSavingConfig = ref(false)
const hoverPoint = ref(null)

const symbolMap = {
  "H1": "💎", "H2": "7️⃣", "H3": "🎰", 
  "L1": "🍒", "L2": "🍋", "L3": "🍇", 
  "WILD": "🃏"
}

const configFields = [
    { key: 'target_rtp', label: '目标 RTP (Target RTP)', desc: '全局玩家回报率目标 (0.0 - 1.0)' },
    { key: 'base_c_value', label: '基础 C 值 (Base C)', desc: 'PRD 算法的基础概率常数' },
    { key: 'max_win_ratio', label: '最大余额倍数 (Max Balance Ratio)', desc: '允许账户余额达到的最大倍数 (相对于初始余额)' }
]

const getSymbol = (s) => symbolMap[s] || s

const handleMouseMove = (e) => {
    if (!simResult.value || !simResult.value.history) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = e.clientX - rect.left
    const percent = x / rect.width
    const index = Math.round(percent * (simResult.value.history.length - 1))
    if (index >= 0 && index < simResult.value.history.length) {
        const point = simResult.value.history[index]
        const range = (chartData.value.maxBal - chartData.value.minBal) || 1
        hoverPoint.value = {
            ...point,
            x: (index / (simResult.value.history.length - 1)) * 100,
            y: 100 - ((Number(point.balance) - chartData.value.minBal) / range) * 100
        }
    }
}

const spin = async () => {
    if (isSpinning.value) return
    
    // Check balance
    if (gameState.value.balance < gameState.value.bet) {
        alert("余额不足，请点击绿色按钮 '+' 号充值！")
        return
    }

    isSpinning.value = true
    
    try {
        // Ensure config is loaded or use default
        const llmConfig = config.value?.llm_config || {
            provider: "openai",
            model: "gpt-3.5-turbo",
            debug_mode: true,
            target_rtp: 0.95
        }

        const res = await fetchAPI('/api/spin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                bet: gameState.value.bet, 
                user_id: sessionId.value, // Use session ID as user ID
                current_balance: gameState.value.balance,
                history_rtp: gameState.value.totalWagered > 0 ? (gameState.value.totalWon / gameState.value.totalWagered) : 0,
                config: llmConfig,
                user_state: {
                    wallet_balance: gameState.value.balance,
                    initial_balance: gameState.value.initialBalance,
                    current_bet: gameState.value.bet,
                    total_spins: gameState.value.totalSpins,
                    fail_streak: gameState.value.failStreak
                }
            })
        })
        
        const contentType = res.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            const text = await res.text();
            throw new Error(`Server returned non-JSON response: ${res.status} ${res.statusText}. Body preview: ${text.substring(0, 100)}...`);
        }

        const data = await res.json()
        
        if (data.detail) {
            alert("Error: " + JSON.stringify(data.detail, null, 2))
            isSpinning.value = false
            return
        }
        
        gameState.value.totalSpins++
        gameState.value.matrix = data.matrix
        // Update balance using balance_update from backend
        gameState.value.balance += data.balance_update
        gameState.value.lastWin = data.total_payout
        gameState.value.winningLines = data.winning_lines
        
        // Update stats from backend
        gameState.value.failStreak = data.fail_streak || 0
        
        gameState.value.bucket = data.bucket_type
        gameState.value.totalWagered += gameState.value.bet
        gameState.value.totalWon += data.total_payout
        
    } catch (e) {
        console.error(e)
        alert("Spin Error: " + e)
    } finally {
        isSpinning.value = false
    }
}

const runSim = async () => {
    isSimulating.value = true
    simResult.value = null
    try {
        const res = await fetchAPI('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(simConfig.value)
        })
        simResult.value = await res.json()
    } catch (e) {
        alert("模拟失败: " + e)
    } finally {
        isSimulating.value = false
    }
}

const loadConfig = async () => {
    const res = await fetchAPI('/api/config')
    config.value = await res.json()
}

const saveConfig = async (payloadOrAutoTune = false) => {
    isSavingConfig.value = true
    try {
        let payload = config.value
        let url = '/api/config'
        
        if (payloadOrAutoTune === true) {
            url = '/api/config?auto_tune=true'
        } else if (payloadOrAutoTune && typeof payloadOrAutoTune === 'object') {
            payload = payloadOrAutoTune
        }

        const res = await fetchAPI(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        const data = await res.json()
        if (payloadOrAutoTune === true && data.new_c) {
            config.value.settings.base_c_value = data.new_c
            alert(`自动调整完成! 新的 C 值: ${data.new_c}`)
        } else {
            alert("配置已保存!")
            // Refresh local config to match server
            await loadConfig()
        }
        showConfig.value = false
    } catch (e) {
        alert("保存失败: " + e)
    } finally {
        isSavingConfig.value = false
    }
}

const resetUser = async () => {
    if(!confirm("确定要重置用户数据吗？")) return
    await fetchAPI('/api/reset/' + sessionId.value, { method: 'POST' })
    window.location.reload()
}

const changeBet = (delta) => {
    if (!config.value || !config.value.bet_levels) {
        // Fallback if config not loaded
        gameState.value.bet = Math.max(10, gameState.value.bet + (delta * 10))
        return
    }
    const levels = config.value.bet_levels
    let currentIndex = levels.indexOf(gameState.value.bet)
    
    // If current bet is not in levels, find the closest one
    if (currentIndex === -1) {
        currentIndex = levels.findIndex(l => l >= gameState.value.bet)
        if (currentIndex === -1) currentIndex = levels.length - 1
    }

    let nextIndex = currentIndex + delta
    if (nextIndex < 0) nextIndex = 0
    if (nextIndex >= levels.length) nextIndex = levels.length - 1
    gameState.value.bet = levels[nextIndex]
}

const topUpBalance = async () => {
    const input = prompt("请输入充值金额 (Please enter top-up amount):", "100")
    if (input === null) return
    
    const amount = parseFloat(input)
    if (isNaN(amount) || amount <= 0) {
        alert("请输入有效的金额！")
        return
    }

    try {
        await fetchAPI('/api/topup', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: amount })
        })
        gameState.value.balance += amount
        // Update initialBalance to reflect the new "principal"
        // This ensures Max Win Ratio scales with the new total investment
        gameState.value.initialBalance += amount
        alert(`充值成功！已添加 🪙 ${amount}`)
    } catch (e) {
        alert("充值失败: " + e)
    }
}

const chartData = computed(() => {
    if (!simResult.value || !simResult.value.history) return null
    const hist = simResult.value.history
    if (hist.length === 0) return null
    
    // --- Balance Axis (Left) ---
    const balances = hist.map(h => Number(h.balance))
    // We don't push 0 anymore to allow "zooming" into the balance fluctuations
    const maxBal = Math.max(...balances)
    const minBal = Math.min(...balances)
    const balRange = (maxBal - minBal) || 1
    
    const balancePoints = hist.map((h, i) => {
        const val = Number(h.balance)
        const x = (i / (hist.length - 1)) * 100
        const y = 100 - ((val - minBal) / balRange) * 100
        return `${x},${y}`
    }).join(" ")
    
    // --- RTP Axis (Right) ---
    // RTP usually stays around 0.0 to 1.5, we fix it to 0-2.0 for stability
    const minRtp = 0
    const maxRtp = 2.0
    const rtpRange = maxRtp - minRtp
    
    const rtpPoints = hist.map((h, i) => {
        const val = Number(h.rtp)
        const x = (i / (hist.length - 1)) * 100
        const y = 100 - ((Math.min(val, maxRtp) - minRtp) / rtpRange) * 100
        return `${x},${y}`
    }).join(" ")
    
    return {
        balancePoints,
        rtpPoints,
        maxBal,
        minBal,
        maxRtp,
        minRtp
    }
})

onMounted(() => {
    initSession()
    loadConfig()
})
</script>

<template>
    <div class="h-[100dvh] flex flex-col items-center p-2 md:p-8 gap-2 md:gap-8 font-sans overflow-hidden bg-slate-950 text-slate-200 select-none touch-manipulation">
        <h1 class="text-xl md:text-4xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent text-center flex-shrink-0">
            Slot Master Pro
        </h1>
        
        <!-- Stats -->
        <div class="flex flex-wrap justify-center gap-2 md:gap-8 text-sm md:text-xl font-mono w-full flex-shrink-0 bg-slate-900/50 p-2 rounded-lg">
            <div class="flex flex-col items-center min-w-[70px] md:min-w-[80px]">
                <span class="text-[11px] md:text-xs text-slate-500">余额 (Balance)</span>
                <span class="text-yellow-400">🪙 {{ gameState.balance.toFixed(0) }}</span>
            </div>
            <div class="flex flex-col items-center min-w-[70px] md:min-w-[80px]">
                <span class="text-[11px] md:text-xs text-slate-500">赢取 (Win)</span>
                <span class="text-green-400">🪙 {{ gameState.lastWin.toFixed(0) }}</span>
            </div>
            <div class="flex flex-col items-center group relative cursor-help min-w-[70px] md:min-w-[80px]">
                <span class="text-[11px] md:text-xs text-slate-500">用户 RTP</span>
                <span class="text-blue-400 border-b border-dotted border-blue-400/30">{{ gameState.totalWagered > 0 ? ((gameState.totalWon / gameState.totalWagered) * 100).toFixed(1) : '0' }}%</span>
                <!-- Tooltip -->
                <div class="absolute top-full mt-2 left-1/2 -translate-x-1/2 w-48 bg-slate-800 p-2 rounded shadow-xl text-[10px] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 border border-slate-700">
                    <div class="flex justify-between mb-1">
                        <span class="text-slate-400">总下注:</span>
                        <span class="text-white">🪙 {{ gameState.totalWagered.toFixed(0) }}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">总赢取:</span>
                        <span class="text-green-400">🪙 {{ gameState.totalWon.toFixed(0) }}</span>
                    </div>
                </div>
            </div>
            <div class="flex flex-col items-center min-w-[70px] md:min-w-[80px]">
                <span class="text-[11px] md:text-xs text-slate-500">连败 (Streak)</span>
                <span class="text-red-400">{{ gameState.failStreak }}</span>
            </div>
            <div class="flex flex-col items-center min-w-[70px] md:min-w-[80px]">
                <span class="text-[11px] md:text-xs text-slate-500">旋转数 (Spins)</span>
                <span class="text-purple-400">{{ gameState.totalSpins }}</span>
            </div>
        </div>

        <!-- Grid Area -->
        <div class="flex-1 flex flex-col lg:flex-row gap-4 items-center justify-center w-full max-w-5xl relative min-h-0">
            
            <!-- Slot Grid (Centered on Desktop, Scaled down on Mobile) -->
            <div class="flex justify-center items-center w-full max-w-[95vw] md:max-w-3xl mx-auto flex-shrink-0">
                <SlotGrid 
                    :matrix="gameState.matrix" 
                    :winning-lines="gameState.winningLines"
                    :is-spinning="isSpinning"
                    :lines-config="config?.lines"
                    class="max-h-[50vh] lg:max-h-full w-auto aspect-[5/3]"
                />
            </div>
            
            <!-- Winning Lines List (Right Side on Large Screens, Bottom on Mobile/Tablet) -->
            <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 w-full lg:w-64 h-48 lg:h-[340px] overflow-y-auto lg:absolute lg:right-[-280px] lg:top-0 shadow-xl order-last lg:order-none">
                <h3 class="text-sm font-bold text-slate-400 mb-2 flex justify-between items-center sticky top-0 bg-slate-900 pb-2 border-b border-slate-800">
                    <span>中奖线 (Lines)</span>
                    <span v-if="gameState.lastWin > 0" class="text-green-400 text-xs">+ 🪙 {{ gameState.lastWin.toFixed(2) }}</span>
                </h3>
                <div v-if="gameState.winningLines.length > 0" class="space-y-2">
                    <div v-for="(line, i) in gameState.winningLines" :key="i" class="text-xs bg-slate-800 p-2 rounded border border-yellow-900/50 hover:bg-slate-700 transition-colors">
                        <div class="flex justify-between text-yellow-400 font-bold items-center">
                            <span>Line {{ line.line_id + 1 }}</span>
                            <div class="text-right">
                                <div>🪙 {{ line.amount.toFixed(2) }}</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div v-else class="text-xs text-slate-600 text-center mt-4 lg:mt-10 flex flex-col items-center gap-2">
                    <span class="text-2xl opacity-20">🎰</span>
                    <span>无中奖 (No Win)</span>
                </div>
            </div>
        </div>

        <!-- Controls -->
        <div class="flex flex-col md:flex-row gap-2 md:gap-4 items-center w-full max-w-md z-10 flex-shrink-0 pb-2">
            <div class="flex items-center justify-between bg-slate-900 rounded-lg p-1 gap-2 w-full md:w-auto">
                <button @click="changeBet(-1)" class="w-10 h-10 bg-slate-800 rounded hover:bg-slate-700 flex-shrink-0 text-xl">-</button>
                <div class="text-center flex-1 md:w-20">
                    <div class="text-[11px] text-slate-500">下注 (Bet)</div>
                    <div class="font-bold text-base">🪙 {{ gameState.bet }}</div>
                </div>
                <button @click="changeBet(1)" class="w-10 h-10 bg-slate-800 rounded hover:bg-slate-700 flex-shrink-0 text-xl">+</button>
            </div>
            
            <div class="flex gap-2 w-full md:w-auto h-12 md:h-16">
                <!-- Fixed width to prevent jumping -->
                <button @click="spin" :disabled="isSpinning" 
                        class="flex-1 md:w-48 bg-yellow-600 hover:bg-yellow-500 text-white font-bold rounded-xl shadow-lg text-lg md:text-xl disabled:opacity-50 flex items-center justify-center transition-colors active:scale-95 transform touch-manipulation">
                    {{ isSpinning ? '...' : 'SPIN' }}
                </button>

                <!-- Refill Button -->
                <button @click="topUpBalance" class="w-12 md:w-16 bg-green-600 hover:bg-green-500 text-white rounded-xl flex items-center justify-center shadow-lg flex-shrink-0 text-xl" title="充值">
                    +
                </button>
            </div>
        </div>

        <!-- Debug/Config -->
        <div class="flex flex-wrap justify-center gap-4 text-xs text-slate-500 pb-2 md:pb-8 flex-shrink-0">
            <button @click="showConfig = true" class="hover:text-white underline">配置 (Config)</button>
            <button @click="showSim = true" class="hover:text-white underline">模拟 (Sim)</button>
            <button @click="resetUser" class="hover:text-white underline">重置 (Reset)</button>
        </div>

        <!-- Config Modal -->
        <ConfigModal 
            v-if="showConfig && config" 
            v-model:isOpen="showConfig" 
            :config="config"
            @save="saveConfig"
        />

        <!-- Loading Overlay for Config Saving -->
        <div v-if="isSavingConfig" class="fixed inset-0 bg-black/60 flex flex-col items-center justify-center z-[100] backdrop-blur-sm">
            <div class="w-12 h-12 border-4 border-yellow-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <div class="text-white font-bold">正在保存配置并重载引擎...</div>
        </div>

        <!-- Simulation Modal -->
        <div v-if="showSim" class="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm">
            <div class="bg-slate-900 p-6 rounded-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto border border-slate-700">
                <h2 class="text-xl font-bold mb-6 text-white">快速模拟 (Fast Simulation)</h2>
                
                <div class="grid grid-cols-2 gap-4 mb-6">
                    <div>
                        <label class="text-xs text-slate-400">旋转次数 (Spins) <span class="text-[10px] text-slate-500">(Max 1M)</span></label>
                        <input v-model.number="simConfig.n_spins" type="number" class="w-full bg-slate-800 p-2 rounded mt-1 text-white">
                    </div>
                    <div>
                        <label class="text-xs text-slate-400">单次下注 (Bet)</label>
                        <input v-model.number="simConfig.bet" type="number" class="w-full bg-slate-800 p-2 rounded mt-1 text-white">
                    </div>
                </div>

                <button @click="runSim" :disabled="isSimulating"
                        class="w-full bg-purple-600 hover:bg-purple-500 py-3 rounded font-bold text-white disabled:opacity-50 mb-6">
                    {{ isSimulating ? '模拟计算中... (Simulating...)' : '开始纯数学模拟 (Start Simulation)' }}
                </button>

                <div v-if="simResult" class="bg-slate-800 p-4 rounded-lg">
                    <div class="grid grid-cols-3 gap-4 mb-4 text-center">
                        <div>
                            <div class="text-xs text-slate-400">净利润 (Net Profit)</div>
                            <div class="text-xl font-bold" :class="(simResult.net_profit ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'">
                                🪙 {{ (simResult.net_profit ?? 0).toFixed(2) }}
                            </div>
                        </div>
                        <!-- Removed Final Balance as it is redundant with Net Profit in pure sim mode -->
                        <div>
                            <div class="text-xs text-slate-400">总下注 (Total Bet)</div>
                            <div class="text-xl font-bold text-white">
                                🪙 {{ (simConfig.n_spins * simConfig.bet).toFixed(0) }}
                                <span class="text-xs text-slate-400 block">({{ simConfig.n_spins }} spins)</span>
                            </div>
                        </div>
                        <div>
                            <div class="text-xs text-slate-400">实际 RTP (Real RTP)</div>
                            <div class="text-xl font-bold text-blue-400">{{ ((simResult.total_rtp ?? 0) * 100).toFixed(2) }}%</div>
                        </div>
                    </div>

                    <!-- Chart -->
                    <div class="text-xs text-slate-500 mb-2 text-center flex justify-between px-4 items-start">
                        <span>* 余额曲线 (Balance) vs RTP 曲线 (RTP)</span>
                        <div class="flex flex-col items-end">
                            <span v-if="simResult?.history" class="text-yellow-500 font-bold">Actual Points: {{ simResult.history.length }}</span>
                            <div v-if="simResult?.debug_info" class="text-[10px] text-slate-500 text-right">
                                Req: {{ simResult.debug_info.requested_spins }} | Err: {{ simResult.debug_info.errors.length }} | LB: {{ simResult.debug_info.loss_bucket_size }}
                                <div v-if="simResult.debug_info.errors.length > 0" class="text-red-400 max-w-[200px] truncate" :title="simResult.debug_info.errors[0]">
                                    {{ simResult.debug_info.errors[0] }}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="h-64 w-full bg-slate-900 rounded border border-slate-700 relative p-2 flex">
                        <!-- Left Y Axis (Balance) -->
                        <div class="w-14 flex flex-col justify-between text-[10px] text-slate-500 text-right pr-2 py-4" v-if="chartData">
                            <span class="text-green-400 font-bold">{{ chartData.maxBal.toFixed(0) }}</span>
                            <span>{{ ((chartData.maxBal + chartData.minBal)/2).toFixed(0) }}</span>
                            <span class="text-red-400 font-bold">{{ chartData.minBal.toFixed(0) }}</span>
                        </div>
                        
                        <div class="flex-1 relative" v-if="chartData">
                            <svg class="w-full h-full cursor-crosshair" viewBox="0 0 100 100" preserveAspectRatio="none"
                                 @mousemove="handleMouseMove" @mouseleave="hoverPoint = null">
                                <!-- Grid lines -->
                                <line x1="0" y1="0" x2="100" y2="0" stroke="#334155" stroke-width="0.5" stroke-dasharray="2"/>
                                <line x1="0" y1="50" x2="100" y2="50" stroke="#334155" stroke-width="0.5" stroke-dasharray="2"/>
                                <line x1="0" y1="100" x2="100" y2="100" stroke="#334155" stroke-width="0.5" stroke-dasharray="2"/>
                                
                                <!-- Zero Line (Balance) -->
                                <line v-if="chartData.maxBal > 0 && chartData.minBal < 0" 
                                      x1="0" :y1="100 - ((0 - chartData.minBal) / (chartData.maxBal - chartData.minBal)) * 100" 
                                      x2="100" :y2="100 - ((0 - chartData.minBal) / (chartData.maxBal - chartData.minBal)) * 100" 
                                      stroke="#34d399" stroke-width="1" stroke-opacity="0.3" />
                                
                                <!-- 100% RTP Line -->
                                <line x1="0" y1="50" x2="100" y2="50" stroke="#60a5fa" stroke-width="1" stroke-opacity="0.3" stroke-dasharray="4" />

                                <!-- Balance Graph (Green) -->
                                <polyline :points="chartData.balancePoints" fill="none" stroke="#34d399" stroke-width="2" vector-effect="non-scaling-stroke" />
                                
                                <!-- RTP Graph (Blue Dashed) -->
                                <polyline :points="chartData.rtpPoints" fill="none" stroke="#60a5fa" stroke-width="2" stroke-dasharray="4" vector-effect="non-scaling-stroke" />

                                <!-- Hover Line & Point -->
                                <g v-if="hoverPoint">
                                    <line :x1="hoverPoint.x" y1="0" :x2="hoverPoint.x" y2="100" stroke="#ffffff" stroke-width="0.5" stroke-opacity="0.5" />
                                    <circle :cx="hoverPoint.x" :cy="hoverPoint.y" r="1.5" fill="#34d399" />
                                </g>
                            </svg>
                            
                            <!-- Tooltip -->
                            <div v-if="hoverPoint" 
                                 class="absolute z-10 bg-slate-800 border border-slate-600 p-2 rounded shadow-xl text-[10px] pointer-events-none"
                                 :style="{ left: hoverPoint.x > 50 ? 'auto' : (hoverPoint.x + 2) + '%', right: hoverPoint.x > 50 ? (100 - hoverPoint.x + 2) + '%' : 'auto', top: '10%' }">
                                <div class="text-slate-400">Point: {{ hoverPoint.spin }}</div>
                                <div class="text-green-400 font-bold">Profit: 🪙 {{ Number(hoverPoint.balance).toFixed(2) }}</div>
                                <div class="text-blue-400">RTP: {{ (Number(hoverPoint.rtp) * 100).toFixed(1) }}%</div>
                            </div>

                            <!-- Legend -->
                            <div class="absolute top-2 right-2 text-[10px] text-slate-500 flex gap-2 bg-slate-900/80 p-1 rounded">
                                <span class="text-green-400 font-bold">Balance (Left)</span>
                                <span class="text-blue-400 font-bold">RTP (Right)</span>
                            </div>
                        </div>

                        <!-- Right Y Axis (RTP) -->
                        <div class="w-14 flex flex-col justify-between text-[10px] text-slate-500 text-left pl-2 py-4" v-if="chartData">
                            <span class="text-blue-400 font-bold">200%</span>
                            <span>100%</span>
                            <span class="text-slate-600 font-bold">0%</span>
                        </div>
                    </div>
                </div>

                <div class="mt-6 text-right">
                    <button @click="showSim = false" class="text-slate-400 hover:text-white">关闭</button>
                </div>
            </div>
        </div>

    </div>
</template>
