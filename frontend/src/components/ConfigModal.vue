<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  isOpen: Boolean,
  config: Object
})

const emit = defineEmits(['update:isOpen', 'save'])

const localConfig = ref({ ...props.config })
const activeTab = ref('general')

// Simplified view of prompt for easier editing
const promptSections = ref({
    game_rules: `**Game Rules:**
- Grid: 3x5.
- Symbols & Paytable (5-of-a-kind match): 
  - H1(🐲): 50x, H2(🦁): 20x, M1(🧧): 10x, L1(🅰️): 2x, L2(👑): 1x.
  - Wild(🃏): Substitutes all.
  - Scatter(💎): 3+ triggers free games (visual only).
- Lines: Standard 3 horizontal lines (Row 0, Row 1, Row 2).`,
    objective: `**Objective:**
Maintain a long-term RTP of {TARGET_RTP}. 
- If player is losing too much (consecutive_loss > 6), force a win (2x - 5x).
- If RTP > 1.2, force a loss.`,
    context_vars: `**Context:**
Current Bet: {BET}
Current Balance: {BALANCE}
History RTP: {HISTORY_RTP}`,
    output_format: `**Output Format:**
Strict JSON only (No markdown, no comments): 
{
  "matrix": [["H1","L1","L2","M1","H1"], ["L1","L1","L1","L1","L1"], ["H2","H2","H2","L2","L2"]], 
  "winning_lines": [{"line_id":1, "amount": 20}], 
  "total_payout": 20,
  "reasoning": "Player was losing, giving a small win."
}`
})

const isCustomPrompt = ref(false)

// Reconstruct full prompt when saving
const constructFullPrompt = () => {
    if (isCustomPrompt.value) return localConfig.value.system_prompt_template;
    return `You are the Slot Game Engine. 
${promptSections.value.game_rules}

${promptSections.value.objective}

${promptSections.value.context_vars}

${promptSections.value.output_format}`
}

const save = () => {
  localConfig.value.system_prompt_template = constructFullPrompt()
  emit('save', { ...localConfig.value })
  emit('update:isOpen', false)
}

const providers = [
    { 
        id: 'openai', 
        name: 'OpenAI Compatible', 
        defaultUrl: 'https://api.openai.com/v1',
        models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo']
    },
    { 
        id: 'deepseek', 
        name: 'DeepSeek (深度求索)', 
        defaultUrl: 'https://api.deepseek.com',
        models: ['deepseek-chat', 'deepseek-reasoner']
    },
    { 
        id: 'gemini', 
        name: 'Google Gemini', 
        defaultUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/',
        models: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash-exp']
    },
    { 
        id: 'ollama', 
        name: 'Ollama (Local)', 
        defaultUrl: 'http://localhost:11434',
        models: ['llama3', 'mistral', 'qwen2.5:7b', 'deepseek-r1']
    },
    { 
        id: 'custom', 
        name: 'Custom (自定义)', 
        defaultUrl: '',
        models: []
    },
]

const availableModels = computed(() => {
    const p = providers.find(x => x.id === localConfig.value.provider)
    return p ? p.models : []
})

const onProviderChange = () => {
    const selected = providers.find(p => p.id === localConfig.value.provider)
    if (selected) {
        localConfig.value.base_url = selected.defaultUrl
        if (selected.models.length > 0) {
            localConfig.value.model = selected.models[0]
        }
    }
}

watch(() => props.config, (newVal) => {
    localConfig.value = { ...newVal }
}, { deep: true })
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
    <div class="bg-gray-800 rounded-lg w-full max-w-2xl border border-gray-600 flex flex-col max-h-[90vh]">
      
      <!-- Header -->
      <div class="p-6 border-b border-gray-700 flex justify-between items-center">
         <h2 class="text-xl font-bold text-slot-gold">⚙️ AI Director Config</h2>
         <button @click="$emit('update:isOpen', false)" class="text-gray-400 hover:text-white">✕</button>
      </div>

      <!-- Tabs -->
      <div class="flex border-b border-gray-700">
        <button 
           @click="activeTab = 'general'"
           class="px-6 py-3 font-medium transition-colors"
           :class="activeTab === 'general' ? 'bg-gray-700 text-white border-b-2 border-slot-gold' : 'text-gray-400 hover:text-gray-200'"
        >
           通用设置 (General)
        </button>
        <button 
           @click="activeTab = 'prompt'"
           class="px-6 py-3 font-medium transition-colors"
           :class="activeTab === 'prompt' ? 'bg-gray-700 text-white border-b-2 border-slot-gold' : 'text-gray-400 hover:text-gray-200'"
        >
           提示词工程 (Prompt)
        </button>
      </div>
      
      <!-- Content -->
      <div class="p-6 overflow-y-auto custom-scrollbar flex-1">
        
        <!-- Tab: General -->
        <div v-show="activeTab === 'general'" class="space-y-4">
          <div>
            <label class="block text-sm mb-1 text-gray-300">Provider (模型厂商)</label>
            <select @change="onProviderChange" v-model="localConfig.provider" class="w-full bg-gray-900 border border-gray-700 p-2 rounded text-white focus:border-slot-gold outline-none">
              <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">Model (模型选择)</label>
            <div v-if="availableModels.length > 0">
                 <select v-model="localConfig.model" class="w-full bg-gray-900 border border-gray-700 p-2 rounded text-white focus:border-slot-gold outline-none">
                    <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
                 </select>
            </div>
            <input v-else v-model="localConfig.model" type="text" placeholder="e.g. gpt-4o" class="w-full bg-gray-900 border border-gray-700 p-2 rounded text-white focus:border-slot-gold outline-none" />
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">API Key (密钥)</label>
            <input v-model="localConfig.api_key" type="password" placeholder="sk-..." class="w-full bg-gray-900 border border-gray-700 p-2 rounded text-white focus:border-slot-gold outline-none" />
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">Base URL (接口地址)</label>
            <input v-model="localConfig.base_url" type="text" :placeholder="providers.find(p=>p.id===localConfig.provider)?.defaultUrl" class="w-full bg-gray-900 border border-gray-700 p-2 rounded text-white focus:border-slot-gold outline-none" />
            <p class="text-xs text-gray-500 mt-1">如果留空，将自动使用上方厂商的默认地址。</p>
          </div>

          <div>
            <label class="block text-sm mb-1 text-gray-300">Target RTP (目标返奖率 0.5 - 1.5)</label>
            <div class="flex items-center gap-4">
               <input v-model.number="localConfig.target_rtp" type="range" min="0.5" max="1.5" step="0.01" class="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer" />
               <input v-model.number="localConfig.target_rtp" type="number" step="0.01" class="w-20 bg-gray-900 border border-gray-700 p-2 rounded text-white text-center" />
            </div>
          </div>

          <!-- DEBUG MODE TOGGLE -->
          <div class="mt-4 pt-4 border-t border-gray-700">
             <div class="flex items-center justify-between">
                <div>
                    <div class="text-sm font-bold text-red-400">🔧 Debug Mode (调试模式)</div>
                    <div class="text-xs text-gray-500">跳过游戏逻辑，直接显示 API 返回的原始内容。用于排查连接问题。</div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" v-model="localConfig.debug_mode" class="sr-only peer">
                  <div class="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
                </label>
             </div>
          </div>

        </div>

        <!-- Tab: Prompt -->
        <div v-show="activeTab === 'prompt'" class="h-full flex flex-col space-y-4">
            <div class="flex justify-between items-center">
                <label class="text-sm text-gray-300 font-bold">System Prompt Configuration</label>
                <div class="flex items-center gap-2">
                    <input type="checkbox" id="customMode" v-model="isCustomPrompt" class="rounded bg-gray-700 border-gray-600 text-yellow-600 focus:ring-yellow-600">
                    <label for="customMode" class="text-xs text-gray-400 select-none">Advanced (Raw Mode)</label>
                </div>
            </div>

            <div v-if="!isCustomPrompt" class="space-y-4">
                <div>
                    <label class="text-xs text-blue-400 block mb-1">Game Rules & Paytable (Editable)</label>
                    <textarea v-model="promptSections.game_rules" class="w-full h-32 bg-gray-900 border border-gray-700 p-2 rounded text-xs text-gray-300 font-mono"></textarea>
                </div>
                <div>
                    <label class="text-xs text-blue-400 block mb-1">Objective & Logic (Editable)</label>
                    <textarea v-model="promptSections.objective" class="w-full h-24 bg-gray-900 border border-gray-700 p-2 rounded text-xs text-gray-300 font-mono"></textarea>
                </div>
            </div>

            <div v-else class="flex-1 flex flex-col">
                <textarea 
                    v-model="localConfig.system_prompt_template" 
                    class="w-full flex-1 min-h-[400px] bg-gray-900 border border-gray-700 p-3 rounded text-sm text-gray-300 font-mono focus:border-slot-gold outline-none resize-none"
                    spellcheck="false"
                ></textarea>
            </div>
        </div>

      </div>

      <!-- Footer -->
      <div class="p-6 border-t border-gray-700 flex justify-end space-x-3 bg-gray-800 rounded-b-lg">
        <button @click="$emit('update:isOpen', false)" class="px-4 py-2 text-gray-400 hover:text-white transition-colors">取消 (Cancel)</button>
        <button @click="save" class="px-6 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded font-bold shadow-lg transition-transform transform active:scale-95">保存 (Save)</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
