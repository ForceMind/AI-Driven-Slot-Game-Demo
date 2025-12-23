<script setup>
import SlotGrid from './components/SlotGrid.vue'
import ConfigModal from './components/ConfigModal.vue'
import { ref, reactive } from 'vue'

const isConfigOpen = ref(false)
const isSpinning = ref(false)

const gameState = reactive({
  balance: 1000,
  bet: 10,
  lastWin: 0,
  historyRtp: 0.95, // Simulated initial
  matrix: [
    ["1","4","5","3","1"], 
    ["4","4","4","4","4"], 
    ["2","2","2","5","5"]
  ],
  winningLines: [],
  debugLog: null
})

const config = reactive({
  provider: 'deepseek',
  base_url: 'https://api.deepseek.com',
  api_key: '', 
  model: 'deepseek-chat',
  target_rtp: 0.97,
  system_prompt_template: '',
  debug_mode: false
})

const spin = async () => {
  if (gameState.balance < gameState.bet) {
    alert("余额不足! (Insufficient Balance)")
    return
  }

  isSpinning.value = true
  gameState.winningLines = []
  
  try {
    const response = await fetch('/api/spin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bet: gameState.bet,
        current_balance: gameState.balance,
        history_rtp: gameState.historyRtp,
        config: config
      })
    })

    const text = await response.text();
    let data;
    try {
        data = JSON.parse(text);
    } catch (jsonError) {
        throw new Error(`Server returned invalid JSON: ${text.substring(0, 100)}...`);
    }
    
    // 如果是调试模式，仅展示日志，不更新游戏状态 (防止格式不匹配导致的崩溃)
    // 即使 response.ok 为 false，如果是调试模式且有数据，也显示
    if (config.debug_mode) {
        // 优先显示 debug info，没有则显示 data
        gameState.debugLog = data.raw_debug_info || data
        
        if (!response.ok) {
             // 如果是错误，也显示出来，但不要 throw 导致上面的日志被覆盖
             alert(`调试模式 (API 返回错误 ${response.status}): 请查看右侧日志。`)
        } else {
             alert("调试模式：已获取原始响应，请查看右侧日志。")
        }
        return
    }

    if (!response.ok) {
        throw new Error(data.detail || data.error || 'Unknown API Error');
    }
    
    // 正常模式：更新游戏状态
    gameState.matrix = data.matrix
    gameState.winningLines = data.winning_lines
    gameState.lastWin = data.total_payout
    gameState.balance += data.balance_update
    
    // 使用后端返回的权威 RTP
    gameState.historyRtp = data.history_rtp
    
    gameState.debugLog = data
    
  } catch (e) {
    console.error("Spin Error:", e)
    alert("旋转失败 (Spin Failed): " + e.message)
    gameState.debugLog = { error: e.message }
  } finally {
    isSpinning.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center p-4 bg-gray-900 text-white font-sans">
    <header class="w-full max-w-4xl flex justify-between items-center mb-8">
      <h1 class="text-3xl font-bold text-yellow-500 flex items-center gap-2">
        <span>🎰</span> AI 老虎机 (AI Slots)
      </h1>
      <div class="flex gap-4 items-center">
        <span v-if="config.debug_mode" class="text-xs bg-red-600 px-2 py-1 rounded animate-pulse">调试模式开启</span>
        <button @click="isConfigOpen = true" class="px-4 py-2 bg-gray-700 rounded hover:bg-gray-600 flex items-center gap-2">
            <span>⚙️</span> 设置 (Config)
        </button>
      </div>
    </header>

    <main class="w-full max-w-4xl flex flex-col md:flex-row gap-8">
      
      <!-- Left: Game Area -->
      <div class="flex-1 flex flex-col items-center">
        <SlotGrid 
          :matrix="gameState.matrix" 
          :winningLines="gameState.winningLines"
          :isSpinning="isSpinning"
        />
        
        <div class="mt-8 w-full bg-gray-800 p-4 rounded-lg flex justify-between items-center border border-gray-700">
          <div class="text-center">
            <div class="text-xs text-gray-400">余额 (BALANCE)</div>
            <div class="text-xl font-mono text-green-400">${{ (gameState.balance || 0).toFixed(2) }}</div>
          </div>
          
          <div class="text-center">
             <div class="text-xs text-gray-400">下注 (BET)</div>
             <div class="text-xl font-bold">{{ gameState.bet }}</div>
          </div>

          <div class="text-center">
            <div class="text-xs text-gray-400">赢取 (WIN)</div>
            <div class="text-xl font-mono text-yellow-400">${{ (gameState.lastWin || 0).toFixed(2) }}</div>
          </div>

          <div class="text-center border-l border-gray-700 pl-4">
            <div class="text-xs text-gray-400">历史 RTP</div>
            <div class="text-xl font-mono" :class="gameState.historyRtp > 1 ? 'text-red-400' : 'text-blue-400'">
              {{ (gameState.historyRtp * 100).toFixed(1) }}%
            </div>
          </div>
        </div>

        <button 
          @click="spin" 
          :disabled="isSpinning"
          class="mt-6 w-full py-4 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-2xl font-bold shadow-lg transform active:scale-95 transition-all text-white"
        >
          {{ isSpinning ? '旋转中 (SPINNING)...' : '开始旋转 (SPIN) 🎲' }}
        </button>
      </div>

      <!-- Right: Debug/Info Area -->
      <div class="w-full md:w-80 bg-gray-800 p-4 rounded-lg border border-gray-700 overflow-hidden flex flex-col h-[500px]">
        <h3 class="text-lg font-bold mb-2 text-gray-300">🧠 AI 导演日志 (Director Log)</h3>
        <div class="flex-1 overflow-auto text-xs font-mono bg-black p-2 rounded text-green-500 whitespace-pre-wrap custom-scrollbar">
          {{ gameState.debugLog ? JSON.stringify(gameState.debugLog, null, 2) : '// 点击旋转查看 AI 推理过程...' }}
        </div>
      </div>

    </main>

    <ConfigModal 
      v-model:isOpen="isConfigOpen" 
      :config="config" 
      @save="(newConfig) => Object.assign(config, newConfig)"
    />
  </div>
</template>

<style>
/* Global scrollbar for logs */
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #1f2937; 
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #4b5563; 
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #6b7280; 
}
</style>
