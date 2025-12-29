<script setup>
import SlotGrid from './components/SlotGrid.vue'
import ConfigModal from './components/ConfigModal.vue'
import SimulationPanel from './components/SimulationPanel.vue'
import { ref, reactive, onMounted, computed } from 'vue'

const isConfigOpen = ref(false)
const isSimOpen = ref(false)
const isSpinning = ref(false)
const skipAI = ref(false)

const betLevels = ref([0.1, 0.5, 1, 2, 5, 10, 20, 50, 100])
const currentBetIndex = ref(5)

const gameState = reactive({
  balance: 1000,
  bet: 10,
  lastWin: 0,
  historyRtp: 0.0,
  sessionWagered: 0,
  sessionWon: 0,
  matrix: [
    ["H1","L1","L2","L3","H1"], 
    ["L1","L1","L1","L1","L1"], 
    ["H2","H2","H2","L2","L2"]
  ],
  winningLines: [],
  debugLog: null,
  commentary: "欢迎！点击旋转开始游戏！",
  bucketType: "Ready"
})

const sessionRtp = computed(() => {
    if (gameState.sessionWagered === 0) return 0
    return gameState.sessionWon / gameState.sessionWagered
})

const userState = reactive({
    user_level: 1,
    max_historical_balance: 1000
})

const config = reactive({
  provider: 'openai',
  base_url: '',
  api_key: '', 
  model: 'gpt-4o',
  target_rtp: 0.97,
  system_prompt_template: '',
  debug_mode: false
})

onMounted(async () => {
  await refreshConfig()
})

const refreshConfig = async () => {
  try {
    const res = await fetch('http://localhost:8000/config')
    const data = await res.json()
    if (data.bet_levels && data.bet_levels.length > 0) {
        betLevels.value = [...data.bet_levels].sort((a, b) => a - b)
        let idx = betLevels.value.findIndex(b => b >= gameState.bet)
        if (idx === -1) idx = 0
        currentBetIndex.value = idx
        gameState.bet = betLevels.value[idx]
    }
  } catch (e) {
    console.error("Failed to load config", e)
  }
}

const changeBet = (delta) => {
    if (isSpinning.value) return
    const newIndex = currentBetIndex.value + delta
    if (newIndex >= 0 && newIndex < betLevels.value.length) {
        currentBetIndex.value = newIndex
        gameState.bet = betLevels.value[newIndex]
        console.log("Bet changed to:", gameState.bet, "Index:", currentBetIndex.value)
    }
}

const spin = async () => {
  if (gameState.balance < gameState.bet) {
    alert("余额不足! (Insufficient Balance)")
    return
  }

  isSpinning.value = true
  gameState.winningLines = []
  gameState.commentary = skipAI.value ? "快速模式..." : "旋转中..."
  
  // Temporarily enable debug mode if Skip AI is checked
  const originalDebug = config.debug_mode
  if (skipAI.value) config.debug_mode = true

  try {
    const response = await fetch('http://localhost:8000/spin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bet: gameState.bet,
        current_balance: gameState.balance,
        history_rtp: gameState.historyRtp,
        config: config,
        user_state: {
            user_level: userState.user_level,
            wallet_balance: gameState.balance,
            current_bet: gameState.bet,
            historical_rtp: gameState.historyRtp,
            max_historical_balance: userState.max_historical_balance
        }
      })
    })
    
    // Restore debug mode
    if (skipAI.value) config.debug_mode = originalDebug

    const data = await response.json();
    
    if (config.debug_mode && !skipAI.value) { // If actual debug mode is on
        gameState.debugLog = data.raw_debug_info || data
        return
    }

    // Update Game State
    gameState.matrix = data.matrix
    gameState.winningLines = data.winning_lines
    gameState.lastWin = data.total_payout
    gameState.balance += data.balance_update
    gameState.historyRtp = data.history_rtp
    gameState.commentary = data.reasoning
    gameState.bucketType = data.bucket_type
    
    // Update Session Stats
    gameState.sessionWagered += gameState.bet
    gameState.sessionWon += data.total_payout
    
    // Update Max Balance
    if (gameState.balance > userState.max_historical_balance) {
        userState.max_historical_balance = gameState.balance
    }
    
    gameState.debugLog = data
    
  } catch (e) {
    console.error("Spin Error:", e)
    gameState.commentary = "连接错误!"
    gameState.debugLog = { error: e.message }
  } finally {
    isSpinning.value = false
    if (skipAI.value) config.debug_mode = originalDebug // Ensure restored
  }
}

const updateConfig = (newConfig) => {
    Object.assign(config, newConfig)
}
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-white font-sans selection:bg-purple-500 selection:text-white">
    
    <!-- Navbar -->
    <nav class="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-40">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg flex items-center justify-center font-bold text-lg shadow-lg shadow-purple-500/20">7</div>
          <span class="font-bold text-xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">Slot Master Pro</span>
        </div>
        <div class="flex items-center gap-4">
          <div class="hidden md:flex items-center gap-6 text-sm font-medium text-slate-400">
            <div class="flex flex-col items-end">
               <span class="text-[10px] uppercase tracking-wider text-slate-500">Session RTP</span>
               <span :class="sessionRtp > 1 ? 'text-red-400' : 'text-blue-400'">{{ (sessionRtp * 100).toFixed(1) }}%</span>
            </div>
            <div class="flex flex-col items-end">
               <span class="text-[10px] uppercase tracking-wider text-slate-500">Total RTP</span>
               <span :class="gameState.historyRtp > 1 ? 'text-red-400' : 'text-green-400'">{{ (gameState.historyRtp * 100).toFixed(1) }}%</span>
            </div>
            <div class="h-8 w-px bg-slate-800"></div>
            <div class="flex flex-col items-end">
               <span class="text-xs uppercase tracking-wider">余额 (Balance)</span>
               <span class="text-yellow-400 font-mono text-lg">${{ gameState.balance.toFixed(2) }}</span>
            </div>
          </div>
          <button @click="isSimOpen = true" class="p-2 text-slate-400 hover:text-white transition-colors rounded-lg hover:bg-slate-800" title="模拟 (Simulation)">
            🚀
          </button>
          <button @click="isConfigOpen = true" class="p-2 text-slate-400 hover:text-white transition-colors rounded-lg hover:bg-slate-800" title="设置 (Settings)">
            ⚙️
          </button>
        </div>
      </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
      
      <!-- Left Column: Game Area -->
      <div class="lg:col-span-2 space-y-6">
        
        <!-- AI Commentary Box (Hidden) -->
        <div v-if="false" class="bg-gradient-to-r from-slate-900 to-slate-800 rounded-2xl p-6 border border-slate-700 shadow-xl relative overflow-hidden group">
            <div class="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-purple-500 to-blue-500"></div>
            <div class="flex items-start gap-4">
                <div class="w-12 h-12 rounded-full bg-slate-700 flex-shrink-0 flex items-center justify-center text-2xl border-2 border-slate-600 group-hover:border-purple-500 transition-colors">
                    🤖
                </div>
                <div class="flex-1">
                    <div class="text-xs font-bold text-purple-400 uppercase tracking-wider mb-1">AI 导演解说 (Director Commentary)</div>
                    <p class="text-lg text-slate-200 font-medium leading-relaxed animate-pulse-once">
                        "{{ gameState.commentary }}"
                    </p>
                </div>
            </div>
        </div>

        <!-- Slot Grid -->
        <div class="bg-slate-900 rounded-3xl p-8 border-4 border-slate-800 shadow-2xl relative">
            <!-- Decorative lights -->
            <div class="absolute -inset-1 bg-gradient-to-r from-purple-600 to-blue-600 rounded-[2rem] opacity-20 blur-lg"></div>
            
            <SlotGrid 
              :matrix="gameState.matrix" 
              :winningLines="gameState.winningLines" 
              :isSpinning="isSpinning"
            />
            
            <!-- Controls -->
            <div class="mt-8 flex flex-col sm:flex-row items-center justify-between gap-6">
                <div class="flex items-center gap-4 bg-slate-950/50 p-2 rounded-xl border border-slate-800">
                    <button @click="changeBet(-1)" :disabled="isSpinning || currentBetIndex <= 0" class="w-10 h-10 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-white font-bold transition-colors">-</button>
                    <div class="text-center min-w-[80px]">
                        <div class="text-xs text-slate-500 uppercase font-bold">下注 (Bet)</div>
                        <div class="text-xl font-mono font-bold text-white">${{ gameState.bet }}</div>
                    </div>
                    <button @click="changeBet(1)" :disabled="isSpinning || currentBetIndex >= betLevels.length - 1" class="w-10 h-10 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-white font-bold transition-colors">+</button>
                </div>

                <button 
                  @click="spin" 
                  :disabled="isSpinning"
                  class="w-full sm:w-auto px-12 py-4 bg-gradient-to-r from-yellow-600 to-yellow-500 hover:from-yellow-500 hover:to-yellow-400 text-white font-black text-xl rounded-xl shadow-lg shadow-yellow-900/20 transform transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <span v-if="isSpinning" class="animate-spin">↻</span>
                  {{ isSpinning ? '旋转中...' : '旋转 (SPIN)' }}
                </button>
            </div>
            
            <div v-if="false" class="mt-4 flex justify-center">
                <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer group">
                    <input v-model="skipAI" type="checkbox" class="w-5 h-5 rounded border-slate-600 text-purple-600 focus:ring-purple-500 bg-slate-800 cursor-pointer">
                    <span class="group-hover:text-slate-200 transition-colors">⚡ 快速模式 (跳过 AI 解说)</span>
                </label>
            </div>
        </div>

        <!-- User State Controls (Debug) -->
        <div class="bg-slate-900 rounded-xl p-4 border border-slate-800">
            <h3 class="text-sm font-bold text-slate-400 mb-3 uppercase tracking-wider">用户状态模拟 (User State Simulation)</h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                    <label class="text-xs text-slate-500 block mb-1">用户等级 (Level)</label>
                    <input v-model.number="userState.user_level" type="number" class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm">
                </div>
                <div>
                    <label class="text-xs text-slate-500 block mb-1">历史最高余额</label>
                    <input v-model.number="userState.max_historical_balance" type="number" class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm">
                </div>
                <div>
                    <label class="text-xs text-slate-500 block mb-1">当前余额 (Live)</label>
                    <input v-model.number="gameState.balance" type="number" class="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-yellow-400 font-bold">
                </div>
            </div>
        </div>

      </div>

      <!-- Right Column: Logs & Stats -->
      <div class="space-y-6">
        <div class="bg-slate-900 rounded-xl border border-slate-800 h-full flex flex-col max-h-[calc(100vh-8rem)]">
            <div class="p-4 border-b border-slate-800 bg-slate-900/50">
                <h3 class="font-bold text-slate-300 flex items-center gap-2">
                    <span>📜</span> 实时逻辑日志 (Live Log)
                </h3>
            </div>
            <div class="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-4 custom-scrollbar">
                <div v-if="gameState.lastWin > 0" class="p-3 bg-green-900/20 border border-green-900/50 rounded text-green-400">
                    🎉 赢取: ${{ gameState.lastWin.toFixed(2) }}
                </div>
                
                <div v-if="gameState.bucketType" class="p-3 bg-slate-800 rounded border border-slate-700">
                    <div class="text-slate-500 mb-1">结果类型 (Bucket)</div>
                    <div class="text-blue-400 font-bold">{{ gameState.bucketType }}</div>
                </div>

                <div v-if="gameState.debugLog" class="space-y-2">
                    <div class="text-slate-500">服务器响应:</div>
                    <pre class="text-slate-400 whitespace-pre-wrap break-all">{{ JSON.stringify(gameState.debugLog, null, 2) }}</pre>
                </div>
            </div>
        </div>
      </div>

    </main>

    <ConfigModal 
      v-model:isOpen="isConfigOpen" 
      :config="config" 
      @save="updateConfig"
    />

    <SimulationPanel
      v-model:isOpen="isSimOpen"
    />

  </div>
</template>

<style>
body {
  background-color: #020617;
}
.animate-pulse-once {
    animation: pulse-text 0.5s ease-out;
}
@keyframes pulse-text {
    0% { opacity: 0.5; transform: translateY(2px); }
    100% { opacity: 1; transform: translateY(0); }
}
</style>