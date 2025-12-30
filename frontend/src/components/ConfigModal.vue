<script setup>
import { ref, onMounted, watch, computed, inject } from 'vue'

const props = defineProps({
  isOpen: Boolean,
  config: Object
})

const emit = defineEmits(['update:isOpen', 'save'])
const fetchAPI = inject('fetchAPI')

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
    const res = await fetchAPI('/api/config')
    const data = await res.json()
    gameConfigJson.value = JSON.stringify(data, null, 2)
    
    // Merge with defaults to ensure all fields exist
    const defaults = {
        symbols: {},
        bet_levels: [10, 20, 50, 100],
        buckets: {},
        lines: {},
        reels_length: 16,
        reel_sets: [],
        settings: {
            target_rtp: 0.95,
            max_win_ratio: 50,
            base_c_value: 0.05
        },
        pay_table: {}
    }
    
    visualConfig.value = { ...defaults, ...JSON.parse(JSON.stringify(data)) }
    
    // Deep merge for nested objects if necessary (simplified here)
    if (!visualConfig.value.bet_levels) visualConfig.value.bet_levels = defaults.bet_levels
    if (!visualConfig.value.settings) visualConfig.value.settings = defaults.settings
    
    // Ensure buckets have min_win/max_win initialized and normalize keys
    if (visualConfig.value.buckets) {
        for (const key in visualConfig.value.buckets) {
            const b = visualConfig.value.buckets[key]
            // Handle legacy keys (min/max) -> new keys (min_win/max_win)
            if (b.min !== undefined && b.min_win === undefined) b.min_win = b.min
            if (b.max !== undefined && b.max_win === undefined) b.max_win = b.max
            
            // Set defaults
            if (b.min_win === undefined) b.min_win = 0
            if (b.max_win === undefined) b.max_win = 0
        }
    }

  } catch (e) {
    console.error("Failed to load config", e)
    alert("加载配置失败: " + e.message)
  } finally {
    isLoading.value = false
  }
}

const loadHistory = async () => {
    try {
        const res = await fetchAPI('/api/history')
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
    } else if (activeTab.value === 'json') {
        payload = JSON.parse(gameConfigJson.value)
    } else {
        return
    }
    emit('save', payload)
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

const addProgressTier = () => {
    if (!visualConfig.value) return
    if (!visualConfig.value.settings.progress_tiers) visualConfig.value.settings.progress_tiers = []
    visualConfig.value.settings.progress_tiers.push({ min_spins: 0, allowed_buckets: ["ALL"] })
    visualConfig.value.settings.progress_tiers.sort((a, b) => a.min_spins - b.min_spins)
}

const removeProgressTier = (index) => {
    if (!visualConfig.value || !visualConfig.value.settings.progress_tiers) return
    visualConfig.value.settings.progress_tiers.splice(index, 1)
}

const updateAllowedBuckets = (tier, val) => {
    tier.allowed_buckets = val.split(',').map(s => s.trim()).filter(s => s)
}

const addLine = () => {
    if (!visualConfig.value) return
    if (!visualConfig.value.lines) visualConfig.value.lines = {}
    
    const existingIds = Object.keys(visualConfig.value.lines).map(Number).filter(n => !isNaN(n))
    const nextId = existingIds.length > 0 ? Math.max(...existingIds) + 1 : 1
    
    // Default horizontal line in middle
    visualConfig.value.lines[nextId] = [[1,0], [1,1], [1,2], [1,3], [1,4]]
}

const removeLine = (lineId) => {
    if (!visualConfig.value || !visualConfig.value.lines) return
    delete visualConfig.value.lines[lineId]
}

const toggleLineCell = (lineId, row, col) => {
    if (!visualConfig.value || !visualConfig.value.lines) return
    const line = visualConfig.value.lines[lineId]
    
    // Check if exists
    const index = line.findIndex(([r, c]) => r === row && c === col)
    if (index >= 0) {
        // Remove
        line.splice(index, 1)
    } else {
        // Add
        line.push([row, col])
        // Sort by column then row for consistency
        line.sort((a, b) => a[1] - b[1] || a[0] - b[0])
    }
}

onMounted(() => {
    if (props.isOpen) {
        loadGameConfig()
        loadHistory()
    }
})
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
      
      <!-- Header & Tabs (Sticky) -->
      <div class="sticky top-0 bg-slate-900 z-10 border-b border-slate-700 shadow-md">
          <div class="p-6 flex justify-between items-center">
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
          <div class="flex px-6 overflow-x-auto scrollbar-hide">
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
            
            <!-- Global Settings Section -->
            <div class="space-y-4">
                <h3 class="text-lg font-bold text-slate-300">全局设置 (Global Settings)</h3>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-800 p-4 rounded border border-slate-700">
                    <div>
                        <label class="text-xs text-slate-500 block">目标 RTP (Target RTP)</label>
                        <input v-model.number="visualConfig.settings.target_rtp" type="number" step="0.01" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-white focus:ring-2 focus:ring-purple-500 outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-slate-500 block">最大赢分倍率 (Max Win Ratio)</label>
                        <input v-model.number="visualConfig.settings.max_win_ratio" type="number" step="0.1" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-white focus:ring-2 focus:ring-purple-500 outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-slate-500 block">基础 C 值 (Base C)</label>
                        <input v-model.number="visualConfig.settings.base_c_value" type="number" step="0.001" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-white focus:ring-2 focus:ring-purple-500 outline-none">
                        <p class="text-[10px] text-slate-500 mt-1 leading-tight">
                            控制赢分频率。值越小，波动越大（周期越长）；值越大，小奖越多（周期越短）。
                        </p>
                    </div>
                </div>
            </div>

            <!-- Progress Tiers Section -->
            <div class="space-y-4">
                <div class="flex justify-between items-center">
                    <h3 class="text-lg font-bold text-slate-300">进度阶段 (Progress Tiers)</h3>
                    <button @click="addProgressTier" class="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded text-white">+ 添加阶段</button>
                </div>
                <div class="space-y-2">
                    <div v-for="(tier, index) in visualConfig.settings.progress_tiers" :key="index" class="bg-slate-800 p-4 rounded border border-slate-700 relative group">
                        <button @click="removeProgressTier(index)" class="absolute top-2 right-2 text-slate-600 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">🗑️</button>
                        <div class="flex gap-4 items-center mb-2">
                            <div class="w-32">
                                <label class="text-xs text-slate-500 block">最小旋转数</label>
                                <input v-model.number="tier.min_spins" type="number" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-white">
                            </div>
                            <div class="flex-1">
                                <label class="text-xs text-slate-500 block">允许的 Buckets (逗号分隔, 或 "ALL")</label>
                                <input :value="tier.allowed_buckets.join(', ')" @input="updateAllowedBuckets(tier, $event.target.value)" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-white text-xs">
                            </div>
                        </div>
                    </div>
                    <div v-if="!visualConfig.settings.progress_tiers || visualConfig.settings.progress_tiers.length === 0" class="text-xs text-slate-500 text-center p-4 border border-dashed border-slate-700 rounded">
                        无进度限制 (默认允许所有 Buckets)
                    </div>
                </div>
            </div>

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
                    <div v-for="(sym, key) in visualConfig.symbols" :key="key" class="bg-slate-800 p-4 rounded border border-slate-700 flex flex-col gap-4">
                        <div class="flex flex-wrap gap-4 items-end">
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
                        
                        <!-- Pay Table for this Symbol -->
                        <div v-if="visualConfig.pay_table && visualConfig.pay_table[sym.id]" class="bg-slate-900/50 p-2 rounded flex gap-4 items-center">
                            <span class="text-xs text-slate-400 font-mono">赔率表:</span>
                            <div class="flex gap-2">
                                <div v-for="count in ['3', '4', '5']" :key="count" class="flex items-center gap-1">
                                    <span class="text-[10px] text-slate-500">{{count}}连:</span>
                                    <input v-model.number="visualConfig.pay_table[sym.id][count]" type="number" class="w-16 bg-slate-950 border border-slate-700 rounded px-1 py-0.5 text-xs text-green-400 text-center">
                                </div>
                            </div>
                        </div>
                        <div v-else class="text-xs text-slate-600 italic">
                            无赔率数据 (No Pay Table Data)
                        </div>
                    </div>
                </div>
            </div>

            <!-- Reels Section -->
            <div class="space-y-4 pt-4 border-t border-slate-700">
                <h3 class="text-lg font-bold text-slate-300">卷轴配置 (Reel Sets)</h3>
                <div class="overflow-x-auto">
                    <div class="flex gap-4 min-w-max">
                        <div v-for="(reel, rIndex) in visualConfig.reel_sets" :key="rIndex" class="bg-slate-800 p-4 rounded border border-slate-700 w-48">
                            <div class="text-center font-bold text-slate-400 mb-2">Reel {{ rIndex + 1 }}</div>
                            <div class="space-y-1 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
                                <div v-for="(sym, sIndex) in reel" :key="sIndex" class="flex gap-1 items-center">
                                    <span class="text-xs text-slate-600 w-6 text-right">{{ sIndex }}:</span>
                                    <select v-model="visualConfig.reel_sets[rIndex][sIndex]" class="flex-1 bg-slate-900 border border-slate-600 rounded px-1 py-0.5 text-xs text-white">
                                        <option v-for="(s, k) in visualConfig.symbols" :key="k" :value="s.id">{{ s.name }}</option>
                                    </select>
                                    <button @click="visualConfig.reel_sets[rIndex].splice(sIndex, 1)" class="text-slate-500 hover:text-red-400 px-1" title="删除格子">×</button>
                                </div>
                            </div>
                            <div class="mt-2 text-center">
                                <button @click="visualConfig.reel_sets[rIndex].push('L1')" class="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded text-white w-full">+ Add Symbol</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Lines Section -->
            <div class="space-y-4 pt-4 border-t border-slate-700">
                <div class="flex justify-between items-center">
                    <h3 class="text-lg font-bold text-slate-300">中奖线 (Winning Lines)</h3>
                    <button @click="addLine" class="text-xs bg-slate-700 hover:bg-slate-600 px-2 py-1 rounded text-white">+ 添加中奖线</button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div v-for="(coords, lineId) in visualConfig.lines" :key="lineId" class="bg-slate-800 p-4 rounded border border-slate-700 relative group">
                        <button @click="removeLine(lineId)" class="absolute top-2 right-2 text-slate-600 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">🗑️</button>
                        <div class="font-bold text-yellow-400 mb-2">Line {{ lineId }}</div>
                        <div class="grid grid-cols-5 gap-1 mb-2">
                            <!-- Mini Grid Visualization -->
                            <div v-for="c in 5" :key="c" class="flex flex-col gap-1">
                                <div v-for="r in 3" :key="r" 
                                     @click="toggleLineCell(lineId, r-1, c-1)"
                                     class="w-6 h-6 border border-slate-600 rounded flex items-center justify-center text-[10px] cursor-pointer hover:border-white transition-colors"
                                     :class="coords.some(([row, col]) => row === r-1 && col === c-1) ? 'bg-yellow-500 text-black font-bold' : 'bg-slate-900 text-slate-600'">
                                </div>
                            </div>
                        </div>
                        <div class="text-xs text-slate-500 font-mono">
                            {{ JSON.stringify(coords) }}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Buckets Section -->
            <div class="space-y-4 pt-4 border-t border-slate-700">
                <h3 class="text-lg font-bold text-slate-300">结果权重 (Result Buckets)</h3>
                <p class="text-xs text-slate-400 bg-slate-800/50 p-2 rounded border border-slate-700/50">
                    "Buckets" (或赢分层级) 定义了不同赢分倍率区间的出现概率权重。
                    <br>引擎会根据 PRD 算法先决定是否中奖，然后根据权重选择一个 Bucket，最后在该 Bucket 的赢分范围内生成具体结果。
                </p>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <template v-for="(bucket, key) in visualConfig.buckets" :key="key">
                    <div v-if="key !== 'Loss'" class="bg-slate-800 p-4 rounded border border-slate-700">
                        <div class="flex justify-between items-center mb-2">
                            <span class="font-bold text-purple-400">{{ key }}</span>
                            <span class="text-xs text-slate-500">权重 (Weight)</span>
                        </div>
                        <input v-model.number="bucket.weight" type="number" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-white">
                        <div class="flex gap-2 mt-2">
                            <div class="flex-1 group relative">
                                <label class="text-[10px] text-slate-500 cursor-help border-b border-dotted border-slate-600">最小赢分 (Min Win)</label>
                                <input v-model.number="bucket.min_win" type="number" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300">
                                <div class="absolute bottom-full left-0 mb-1 hidden group-hover:block w-48 bg-black text-white text-[10px] p-2 rounded z-20">
                                    该 Bucket 允许的最小赢分倍率 (例如 10x)
                                </div>
                            </div>
                            <div class="flex-1 group relative">
                                <label class="text-[10px] text-slate-500 cursor-help border-b border-dotted border-slate-600">最大赢分 (Max Win)</label>
                                <input v-model.number="bucket.max_win" type="number" class="w-full bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-slate-300">
                                <div class="absolute bottom-full right-0 mb-1 hidden group-hover:block w-48 bg-black text-white text-[10px] p-2 rounded z-20">
                                    该 Bucket 允许的最大赢分倍率 (例如 50x)
                                </div>
                            </div>
                        </div>
                    </div>
                    </template>
                </div>
            </div>

            <button @click="saveGameConfig" class="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg shadow-lg transition-all">
                保存可视化更改 (Save Visual Changes)
            </button>
        </div>

        <!-- JSON Tab -->
        <div v-if="activeTab === 'json'" class="space-y-4 h-full flex flex-col">
          <p class="text-sm text-slate-400">直接编辑后端 `game_config_v2.json`。请小心！</p>
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
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800">
                        <tr v-for="(row, i) in historyData" :key="i" class="hover:bg-slate-800/50">
                            <td class="px-4 py-2 text-slate-500">{{ row.Timestamp?.split('T')[1]?.split('.')[0] }}</td>
                            <td class="px-4 py-2">🪙 {{ row.Bet }}</td>
                            <td class="px-4 py-2" :class="row.Payout > 0 ? 'text-green-400 font-bold' : 'text-slate-400'">🪙 {{ row.Payout }}</td>
                            <td class="px-4 py-2 text-slate-400">{{ (row.Current_RTP * 100).toFixed(1) }}%</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

      </div>
    </div>
  </div>
</template>


