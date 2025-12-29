<script setup>
import { ref, onMounted, watch, computed } from 'vue'

const props = defineProps({
  isOpen: Boolean,
  config: Object
})

const emit = defineEmits(['update:isOpen', 'save'])

const activeTab = ref('visual')
const gameConfigJson = ref('{}')
const visualConfig = ref({
    symbols: {},
    bet_levels: [],
    buckets: {},
    lines: {},
    reels_length: 16,
    reel_sets: [],
    settings: {}
})
const historyData = ref([])
const isLoading = ref(false)

const loadGameConfig = async () => {
  isLoading.value = true
  try {
    const res = await fetch('http://localhost:8000/config')
    const data = await res.json()
    gameConfigJson.value = JSON.stringify(data, null, 2)
    visualConfig.value = JSON.parse(JSON.stringify(data))
  } catch (e) {
    console.error("Failed to load config", e)
  } finally {
    isLoading.value = false
  }
}

const loadHistory = async () => {
    try {
        const res = await fetch('http://localhost:8000/history')
        const data = await res.json()
        historyData.value = data
    } catch (e) {
        console.error("Failed to load history", e)
    }
}

const saveGameConfig = async () => {
  try {
    let payload = {}
    if (activeTab.value === 'visual') {
        payload = visualConfig.value
        gameConfigJson.value = JSON.stringify(payload, null, 2)
    } else if (activeTab.value === 'json') {
        payload = JSON.parse(gameConfigJson.value)
    } else {
        // LLM tab or others
        return
    }

    const res = await fetch('http://localhost:8000/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    
    if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Server Error: ${res.status}`)
    }

    alert("配置已保存并重载！")
    loadGameConfig() // Refresh
  } catch (e) {
    alert("配置无效: " + e.message)
  }
}

watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    loadGameConfig()
    loadHistory()
  }
})

const localConfig = ref({ ...props.config })

const saveLLMConfig = () => {
  emit('save', localConfig.value)
  emit('update:isOpen', false)
}

const addSymbol = () => {
    if (!visualConfig.value) return
    const id = `NEW_${Object.keys(visualConfig.value.symbols).length + 1}`
    visualConfig.value.symbols[id] = { id, name: "New Symbol", type: "standard", base_value: 1 }
}

const removeSymbol = (key) => {
    if (!visualConfig.value) return
    delete visualConfig.value.symbols[key]
}

const addBetLevel = () => {
    if (!visualConfig.value) return
    if (!visualConfig.value.bet_levels) visualConfig.value.bet_levels = []
    visualConfig.value.bet_levels.push(10)
    visualConfig.value.bet_levels.sort((a, b) => a - b)
}

const removeBetLevel = (index) => {
    if (!visualConfig.value || !visualConfig.value.bet_levels) return
    visualConfig.value.bet_levels.splice(index, 1)
}
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
      
      <!-- Header -->
      <div class="p-6 border-b border-slate-700 flex justify-between items-center sticky top-0 bg-slate-900 z-10">
        <h2 class="text-xl font-bold text-white flex items-center gap-2">
          <span>⚙️</span> 游戏配置 (Configuration)
          <button @click="loadGameConfig" class="ml-2 p-1 hover:bg-slate-800 rounded transition-colors" title="刷新配置">
            <span :class="{ 'animate-spin inline-block': isLoading }">🔄</span>
          </button>
        </h2>
        <button @click="$emit('update:isOpen', false)" class="text-slate-400 hover:text-white transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Tabs -->
      <div class="flex border-b border-slate-700 px-6 overflow-x-auto scrollbar-hide">
        <button 
          v-if="false"
          @click="activeTab = 'llm'"
          class="px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex-shrink-0"
          :class="activeTab === 'llm' ? 'border-purple-500 text-purple-400' : 'border-transparent text-slate-400 hover:text-slate-200'"
        >
          LLM 设置
        </button>
        <button 
          @click="activeTab = 'visual'"
          class="px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex-shrink-0"
          :class="activeTab === 'visual' ? 'border-purple-500 text-purple-400' : 'border-transparent text-slate-400 hover:text-slate-200'"
        >
          可视化编辑器
        </button>
        <button 
          @click="activeTab = 'json'"
          class="px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex-shrink-0"
          :class="activeTab === 'json' ? 'border-purple-500 text-purple-400' : 'border-transparent text-slate-400 hover:text-slate-200'"
        >
          原始配置
        </button>
        <button 
          @click="activeTab = 'history'"
          class="px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex-shrink-0"
          :class="activeTab === 'history' ? 'border-purple-500 text-purple-400' : 'border-transparent text-slate-400 hover:text-slate-200'"
        >
          历史记录
        </button>
      </div>

      <!-- Content -->
      <div class="p-6 flex-1 overflow-y-auto">
        
        <!-- LLM Tab -->
        <div v-if="activeTab === 'llm'" class="space-y-6">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="space-y-2">
              <label class="text-sm text-slate-400">提供商 (Provider)</label>
              <select v-model="localConfig.provider" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white focus:ring-2 focus:ring-purple-500 outline-none">
                <option value="openai">OpenAI</option>
                <option value="deepseek">DeepSeek</option>
                <option value="ollama">Ollama (Local)</option>
                <option value="gemini">Gemini</option>
              </select>
            </div>
            <div class="space-y-2">
              <label class="text-sm text-slate-400">模型名称 (Model Name)</label>
              <input v-model="localConfig.model" type="text" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white focus:ring-2 focus:ring-purple-500 outline-none">
            </div>
            <div class="space-y-2 md:col-span-2">
              <label class="text-sm text-slate-400">API Key</label>
              <input v-model="localConfig.api_key" type="password" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white focus:ring-2 focus:ring-purple-500 outline-none" placeholder="sk-...">
            </div>
            <div class="space-y-2 md:col-span-2">
              <label class="text-sm text-slate-400">Base URL (可选)</label>
              <input v-model="localConfig.base_url" type="text" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white focus:ring-2 focus:ring-purple-500 outline-none" placeholder="https://api.openai.com/v1">
            </div>
            <div class="flex items-center gap-3 md:col-span-2 bg-slate-800/50 p-3 rounded border border-slate-700">
              <input v-model="localConfig.debug_mode" type="checkbox" id="debug" class="w-5 h-5 rounded border-slate-600 text-purple-600 focus:ring-purple-500 bg-slate-700">
              <label for="debug" class="text-sm text-slate-200 cursor-pointer select-none">
                <span class="font-bold text-yellow-400">调试模式 (Debug Mode)</span> (跳过 LLM, 返回随机结果)
              </label>
            </div>
          </div>
          <div class="pt-4 border-t border-slate-700">
             <button @click="saveLLMConfig" class="w-full py-3 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-lg shadow-lg transition-all">
               保存 LLM 设置 (Save LLM Settings)
             </button>
          </div>
        </div>

        <!-- Visual Editor Tab -->
        <div v-if="activeTab === 'visual' && visualConfig" class="space-y-8">
            
            <!-- Bet Levels Section -->
            <div class="space-y-4">
                <div class="flex justify-between items-center">
                    <h3 class="text-lg font-bold text-slate-300">下注档位 (Bet Levels)</h3>
                    <button @click="addBetLevel" class="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded text-white">+ 添加档位</button>
                </div>
                <div class="flex flex-wrap gap-2 bg-slate-800 p-4 rounded border border-slate-700">
                    <div v-for="(level, index) in visualConfig.bet_levels" :key="index" class="relative group">
                        <input v-model.number="visualConfig.bet_levels[index]" type="number" class="w-20 bg-slate-900 border border-slate-600 rounded px-2 py-1 text-center text-white focus:ring-2 focus:ring-purple-500 outline-none">
                        <button @click="removeBetLevel(index)" class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-4 h-4 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">×</button>
                    </div>
                </div>
            </div>

            <!-- Symbols Section -->
            <div class="space-y-4 pt-4 border-t border-slate-700">
                <div class="flex justify-between items-center">
                    <h3 class="text-lg font-bold text-slate-300">符号 (Symbols)</h3>
                    <button @click="addSymbol" class="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded text-white">+ 添加符号</button>
                </div>
                <div class="grid grid-cols-1 gap-4">
                    <div v-for="(sym, key) in visualConfig.symbols" :key="key" class="bg-slate-800 p-4 rounded border border-slate-700 flex flex-wrap gap-4 items-end">
                        <div class="w-20">
                            <label class="text-xs text-slate-500 block">ID</label>
                            <input v-model="sym.id" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-white" readonly>
                        </div>
                        <div class="flex-1 min-w-[120px]">
                            <label class="text-xs text-slate-500 block">名称 (Name)</label>
                            <input v-model="sym.name" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-sm text-white">
                        </div>
                        <div class="w-24">
                            <label class="text-xs text-slate-500 block">基础价值</label>
                            <input v-model.number="sym.base_value" type="number" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-sm text-white">
                        </div>
                        <div class="w-24">
                            <label class="text-xs text-slate-500 block">类型</label>
                            <select v-model="sym.type" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-sm text-white">
                                <option value="standard">Standard</option>
                                <option value="wild">Wild</option>
                                <option value="scatter">Scatter</option>
                            </select>
                        </div>
                        <button @click="removeSymbol(key)" class="text-red-400 hover:text-red-300 p-1">🗑️</button>
                    </div>
                </div>
            </div>

            <!-- Buckets Section -->
            <div class="space-y-4 pt-4 border-t border-slate-700">
                <h3 class="text-lg font-bold text-slate-300">结果权重 (Result Buckets)</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div v-for="(bucket, key) in visualConfig.buckets" :key="key" class="bg-slate-800 p-4 rounded border border-slate-700">
                        <div class="flex justify-between items-center mb-2">
                            <span class="font-bold text-purple-400">{{ key }}</span>
                            <span class="text-xs text-slate-500">权重 (Weight)</span>
                        </div>
                        <input v-model.number="bucket.weight" type="number" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-white">
                        <div class="flex gap-2 mt-2">
                            <div class="flex-1">
                                <label class="text-[10px] text-slate-500">最小赢分 (Min Win)</label>
                                <input v-model.number="bucket.min_win" type="number" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300">
                            </div>
                            <div class="flex-1">
                                <label class="text-[10px] text-slate-500">最大赢分 (Max Win)</label>
                                <input v-model.number="bucket.max_win" type="number" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <button @click="saveGameConfig" class="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg shadow-lg transition-all">
                保存可视化更改 (Save Visual Changes)
            </button>
        </div>

        <!-- JSON Tab -->
        <div v-if="activeTab === 'json'" class="space-y-4 h-full flex flex-col">
          <p class="text-sm text-slate-400">直接编辑后端 `game_config.json`。请小心！</p>
          <textarea 
            v-model="gameConfigJson" 
            class="w-full h-96 bg-slate-950 border border-slate-700 rounded p-4 font-mono text-xs text-green-400 focus:ring-2 focus:ring-purple-500 outline-none resize-none"
            spellcheck="false"
          ></textarea>
          <button @click="saveGameConfig" class="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg shadow-lg transition-all">
             保存并重载配置 (Save & Reload)
          </button>
        </div>

        <!-- History Tab -->
        <div v-if="activeTab === 'history'" class="space-y-4">
            <div class="flex justify-between items-center">
                <h3 class="text-lg font-bold text-slate-300">最近 50 次旋转记录</h3>
                <button @click="loadHistory" class="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded text-white">刷新</button>
            </div>
            <div class="overflow-x-auto border border-slate-700 rounded-lg">
                <table class="w-full text-left text-xs">
                    <thead class="bg-slate-800 text-slate-400 uppercase">
                        <tr>
                            <th class="px-4 py-2">时间</th>
                            <th class="px-4 py-2">下注</th>
                            <th class="px-4 py-2">派彩</th>
                            <th class="px-4 py-2">RTP</th>
                            <th class="px-4 py-2">AI</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800">
                        <tr v-for="(row, i) in historyData" :key="i" class="hover:bg-slate-800/50">
                            <td class="px-4 py-2 text-slate-500">{{ row.Timestamp?.split('T')[1]?.split('.')[0] }}</td>
                            <td class="px-4 py-2">${{ row.Bet }}</td>
                            <td class="px-4 py-2" :class="row.Payout > 0 ? 'text-green-400 font-bold' : 'text-slate-400'">${{ row.Payout }}</td>
                            <td class="px-4 py-2 text-slate-400">{{ (row.Current_RTP * 100).toFixed(1) }}%</td>
                            <td class="px-4 py-2 text-slate-500">{{ row.AI_Provider }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

      </div>
    </div>
  </div>
</template>


