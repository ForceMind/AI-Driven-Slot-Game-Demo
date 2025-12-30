<script setup>
import { ref, onMounted, computed } from 'vue'
import SlotGrid from './components/SlotGrid.vue'
import ConfigModal from './components/ConfigModal.vue'

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
        hoverPoint.value = {
            ...point,
            x: (index / (simResult.value.history.length - 1)) * 100,
            y: 100 - ((Number(point.balance) - chartData.value.minBal) / (chartData.value.maxBal - chartData.value.minBal)) * 100
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

        const res = await fetch('/api/spin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                bet: gameState.value.bet, 
                user_id: "default_user",
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
        const res = await fetch('/api/simulate', {
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
    const res = await fetch('/api/config')
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

        const res = await fetch(url, {
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
    await fetch('/api/reset/default_user', { method: 'POST' })
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
    if(!confirm("是否充值 100 🪙?")) return
    try {
        await fetch('/api/topup', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: 100 })
        })
        gameState.value.balance += 100
        alert("充值成功！")
    } catch (e) {
        alert("充值失败: " + e)
    }
}

const chartData = computed(() => {
    if (!simResult.value || !simResult.value.history) return null
    const hist = simResult.value.history
    if (hist.length === 0) return null
    
    // Ensure balances are numbers
    const balances = hist.map(h => Number(h.balance))
    balances.push(0) // Start at 0
    
    // Filter out any NaNs just in case
    const validBalances = balances.filter(b => !isNaN(b))
    
    if (validBalances.length === 0) return null

    const maxBal = Math.max(...validBalances)
    const minBal = Math.min(...validBalances)
    const range = maxBal - minBal || 1
    
    const balancePoints = hist.map((h, i) => {
        const val = Number(h.balance)
        if (isNaN(val)) return `${(i / (hist.length - 1)) * 100},100`
        
        const x = (i / (hist.length - 1)) * 100
        const y = 100 - ((val - minBal) / range) * 100
        return `${x},${y}`
    }).join(" ")
    
    // RTP
    const maxRtp = 2.0
    const rtpPoints = hist.map((h, i) => {
        const val = Number(h.rtp)
        if (isNaN(val)) return `${(i / (hist.length - 1)) * 100},100`
        
        const x = (i / (hist.length - 1)) * 100
        const y = 100 - (Math.min(val, maxRtp) / maxRtp) * 100
        return `${x},${y}`
    }).join(" ")
    
    return {
        balancePoints,
        rtpPoints,
        maxBal,
        minBal,
        maxRtp
    }
})

onMounted(() => {
    loadConfig()
})
</script>

<template>
    <div class="min-h-screen flex flex-col items-center p-8 gap-8 font-sans">
        <h1 class="text-4xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
            Slot Master Pro
        </h1>
        
        <!-- Stats -->
        <div class="flex gap-8 text-xl font-mono">
            <div class="flex flex-col items-center">
                <span class="text-xs text-slate-500">余额 (BALANCE)</span>
                <span class="text-yellow-400">🪙 {{ gameState.balance.toFixed(2) }}</span>
            </div>
            <div class="flex flex-col items-center">
                <span class="text-xs text-slate-500">赢取 (WIN)</span>
                <span class="text-green-400">🪙 {{ gameState.lastWin.toFixed(2) }}</span>
            </div>
            <div class="flex flex-col items-center group relative cursor-help">
                <span class="text-xs text-slate-500">用户 RTP</span>
                <span class="text-blue-400 border-b border-dotted border-blue-400/30">{{ gameState.totalWagered > 0 ? ((gameState.totalWon / gameState.totalWagered) * 100).toFixed(1) : '0.0' }}%</span>
                <div class="absolute top-full mt-2 hidden group-hover:block bg-slate-900 text-xs p-3 rounded border border-slate-700 whitespace-nowrap z-50 shadow-xl text-left">
                    <div class="text-slate-400 mb-1">统计数据 (Stats)</div>
                    <div class="flex justify-between gap-4"><span>总下注:</span> <span class="text-white">🪙 {{ gameState.totalWagered.toFixed(2) }}</span></div>
                    <div class="flex justify-between gap-4"><span>总赢取:</span> <span class="text-green-400">🪙 {{ gameState.totalWon.toFixed(2) }}</span></div>
                </div>
            </div>
            <div class="flex flex-col items-center">
                <span class="text-xs text-slate-500">连败 (FAIL STREAK)</span>
                <span class="text-red-400">{{ gameState.failStreak }}</span>
            </div>
            <div class="flex flex-col items-center">
                <span class="text-xs text-slate-500">旋转数 (SPINS)</span>
                <span class="text-purple-400">{{ gameState.totalSpins }}</span>
            </div>
        </div>

        <!-- Grid Area -->
        <div class="flex flex-col lg:flex-row gap-8 items-start justify-center w-full max-w-6xl relative">
            
            <!-- Slot Grid (Centered on Desktop) -->
            <div class="flex-1 flex justify-center">
                <SlotGrid 
                    :matrix="gameState.matrix" 
                    :winning-lines="gameState.winningLines"
                    :is-spinning="isSpinning"
                />
            </div>
            
            <!-- Winning Lines List (Right Side on Large Screens, Bottom on Mobile/Tablet) -->
            <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 w-full lg:w-64 h-48 lg:h-[340px] overflow-y-auto lg:absolute lg:right-0 lg:top-0 shadow-xl">
                <h3 class="text-sm font-bold text-slate-400 mb-2 flex justify-between items-center">
                    <span>中奖线 (Lines)</span>
                    <span v-if="gameState.lastWin > 0" class="text-green-400 text-xs">+ 🪙 {{ gameState.lastWin.toFixed(2) }}</span>
                </h3>
                <div v-if="gameState.winningLines.length > 0" class="space-y-2">
                    <div v-for="(line, i) in gameState.winningLines" :key="i" class="text-xs bg-slate-800 p-2 rounded border border-yellow-900/50 hover:bg-slate-700 transition-colors">
                        <div class="flex justify-between text-yellow-400 font-bold items-center">
                            <span>Line {{ line.line_id + 1 }}</span>
                            <div class="text-right">
                                <div>🪙 {{ line.amount.toFixed(2) }}</div>
                                <div class="text-[10px] text-slate-500 font-normal">
                                    {{ (line.amount / gameState.bet).toFixed(1) }}x
                                </div>
                            </div>
                        </div>
                        <div class="text-slate-500 mt-1 flex items-center gap-1">
                            <span class="bg-slate-900 px-1 rounded text-[10px]">{{ line.count }}</span>
                            <span>x</span>
                            <span>{{ getSymbol(line.symbol) }}</span>
                        </div>
                    </div>
                </div>
                <div v-else class="text-xs text-slate-600 text-center mt-10 flex flex-col items-center gap-2">
                    <span class="text-2xl opacity-20">🎰</span>
                    <span>无中奖</span>
                </div>
            </div>
        </div>

        <!-- Controls -->
        <div class="flex gap-4 items-center">
            <div class="flex items-center bg-slate-900 rounded-lg p-2 gap-4">
                <button @click="changeBet(-1)" class="w-10 h-10 bg-slate-800 rounded hover:bg-slate-700">-</button>
                <div class="text-center w-20">
                    <div class="text-xs text-slate-500">下注 (BET)</div>
                    <div class="font-bold">🪙 {{ gameState.bet }}</div>
                </div>
                <button @click="changeBet(1)" class="w-10 h-10 bg-slate-800 rounded hover:bg-slate-700">+</button>
            </div>
            
            <!-- Fixed width to prevent jumping -->
            <button @click="spin" :disabled="isSpinning" 
                    class="w-48 h-16 bg-yellow-600 hover:bg-yellow-500 text-white font-bold rounded-xl shadow-lg text-xl disabled:opacity-50 flex items-center justify-center transition-colors">
                {{ isSpinning ? '旋转中...' : '旋转 (SPIN)' }}
            </button>

            <!-- Refill Button -->
            <button @click="topUpBalance" class="w-10 h-10 bg-green-600 hover:bg-green-500 text-white rounded-full flex items-center justify-center shadow-lg" title="充值 (Top Up)">
                +
            </button>
        </div>

        <!-- Debug/Config -->
        <div class="flex gap-4 text-sm text-slate-500">
            <button @click="showConfig = true" class="hover:text-white underline">配置 (Config)</button>
            <button @click="showSim = true" class="hover:text-white underline">快速模拟 (Simulate)</button>
            <button @click="resetUser" class="hover:text-white underline">重置用户 (Reset)</button>
            <span class="ml-4">Bucket: {{ gameState.bucket }}</span>
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
                        <label class="text-xs text-slate-400">旋转次数</label>
                        <input v-model.number="simConfig.n_spins" type="number" class="w-full bg-slate-800 p-2 rounded mt-1 text-white">
                    </div>
                    <div>
                        <label class="text-xs text-slate-400">单次下注</label>
                        <input v-model.number="simConfig.bet" type="number" class="w-full bg-slate-800 p-2 rounded mt-1 text-white">
                    </div>
                </div>

                <button @click="runSim" :disabled="isSimulating"
                        class="w-full bg-purple-600 hover:bg-purple-500 py-3 rounded font-bold text-white disabled:opacity-50 mb-6">
                    {{ isSimulating ? '模拟计算中...' : '开始纯数学模拟' }}
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
                            <div class="text-xl font-bold text-white">🪙 {{ (simConfig.n_spins * simConfig.bet).toFixed(0) }}</div>
                        </div>
                        <div>
                            <div class="text-xs text-slate-400">实际 RTP</div>
                            <div class="text-xl font-bold text-blue-400">{{ ((simResult.total_rtp ?? 0) * 100).toFixed(2) }}%</div>
                        </div>
                    </div>

                    <!-- Chart -->
                    <div class="text-xs text-slate-500 mb-2 text-center">
                        * 余额曲线 (Balance) vs RTP 曲线 (RTP)
                    </div>
                    <div class="h-64 w-full bg-slate-900 rounded border border-slate-700 relative p-2 flex">
                        <!-- Y Axis Labels -->
                        <div class="w-12 flex flex-col justify-between text-[10px] text-slate-500 text-right pr-2 py-4" v-if="chartData">
                            <span class="text-green-400">{{ chartData.maxBal.toFixed(0) }}</span>
                            <span>{{ ((chartData.maxBal + chartData.minBal)/2).toFixed(0) }}</span>
                            <span class="text-red-400">{{ chartData.minBal.toFixed(0) }}</span>
                        </div>
                        
                        <div class="flex-1 relative" v-if="chartData">
                            <svg class="w-full h-full cursor-crosshair" viewBox="0 0 100 100" preserveAspectRatio="none"
                                 @mousemove="handleMouseMove" @mouseleave="hoverPoint = null">
                                <!-- Grid lines -->
                                <line x1="0" y1="0" x2="100" y2="0" stroke="#334155" stroke-width="0.5" stroke-dasharray="2"/>
                                <line x1="0" y1="50" x2="100" y2="50" stroke="#334155" stroke-width="0.5" stroke-dasharray="2"/>
                                <line x1="0" y1="100" x2="100" y2="100" stroke="#334155" stroke-width="0.5" stroke-dasharray="2"/>
                                
                                <!-- Zero Line (if within range) -->
                                <line v-if="chartData.maxBal > 0 && chartData.minBal < 0" 
                                      x1="0" :y1="100 - ((0 - chartData.minBal) / (chartData.maxBal - chartData.minBal)) * 100" 
                                      x2="100" :y2="100 - ((0 - chartData.minBal) / (chartData.maxBal - chartData.minBal)) * 100" 
                                      stroke="#94a3b8" stroke-width="1" stroke-opacity="0.5" />

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
                            <div class="absolute top-2 right-2 text-xs text-slate-500 flex gap-2 bg-slate-900/80 p-1 rounded">
                                <span class="text-green-400 font-bold">Balance</span>
                                <span class="text-blue-400 font-bold">RTP (Max 200%)</span>
                            </div>
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
