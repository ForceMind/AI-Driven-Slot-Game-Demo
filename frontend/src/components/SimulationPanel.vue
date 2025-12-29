<script setup>
import { ref } from 'vue'
import { Chart, registerables } from 'chart.js'
import { LineChart } from 'vue-chart-3'

Chart.register(...registerables)

const props = defineProps({
  isOpen: Boolean
})

const emit = defineEmits(['update:isOpen'])

const simParams = ref({
  spins: 1000,
  bet: 10,
  start_balance: 1000
})

const isRunning = ref(false)
const result = ref(null)
const chartData = ref({
  labels: [],
  datasets: [
    {
      label: 'RTP Evolution',
      data: [],
      borderColor: '#4ade80',
      tension: 0.1
    }
  ]
})

const runSimulation = async () => {
  isRunning.value = true
  result.value = null
  
  try {
    const response = await fetch('http://localhost:8000/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(simParams.value)
    })
    
    const data = await response.json()
    result.value = data
    
    // Update Chart
    chartData.value = {
      labels: data.history.map(h => h.spin),
      datasets: [
        {
          label: 'RTP (%)',
          data: data.history.map(h => h.rtp * 100),
          borderColor: '#4ade80',
          yAxisID: 'y',
          tension: 0.1
        },
        {
          label: 'Balance ($)',
          data: data.history.map(h => h.balance),
          borderColor: '#facc15',
          yAxisID: 'y1',
          tension: 0.1
        }
      ]
    }
    
  } catch (e) {
    console.error(e)
    alert("Simulation failed")
  } finally {
    isRunning.value = false
  }
}
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl">
      <div class="p-6 border-b border-slate-700 flex justify-between items-center sticky top-0 bg-slate-900 z-10">
        <h2 class="text-xl font-bold text-white flex items-center gap-2">
          <span>🚀</span> 快速模拟 (Fast Simulation)
        </h2>
        <button @click="$emit('update:isOpen', false)" class="text-slate-400 hover:text-white transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="p-6 space-y-6">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="space-y-2">
            <label class="text-sm text-slate-400">模拟次数 (Spins)</label>
            <input v-model.number="simParams.spins" type="number" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white focus:ring-2 focus:ring-purple-500 outline-none">
          </div>
          <div class="space-y-2">
            <label class="text-sm text-slate-400">下注金额 (Bet)</label>
            <input v-model.number="simParams.bet" type="number" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white focus:ring-2 focus:ring-purple-500 outline-none">
          </div>
          <div class="space-y-2">
            <label class="text-sm text-slate-400">初始余额 (Start Balance)</label>
            <input v-model.number="simParams.start_balance" type="number" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white focus:ring-2 focus:ring-purple-500 outline-none">
          </div>
        </div>

        <button 
          @click="runSimulation" 
          :disabled="isRunning"
          class="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-bold rounded-lg shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2"
        >
          <span v-if="isRunning" class="animate-spin">⏳</span>
          {{ isRunning ? '模拟中 (Simulating)...' : '开始模拟 (Start Simulation)' }}
        </button>

        <div v-if="result" class="grid grid-cols-2 gap-4 bg-slate-800/50 p-4 rounded-lg border border-slate-700">
          <div class="text-center">
            <div class="text-sm text-slate-400">最终余额 (Final Balance)</div>
            <div class="text-2xl font-bold text-yellow-400">${{ result.final_balance.toFixed(2) }}</div>
          </div>
          <div class="text-center">
            <div class="text-sm text-slate-400">总 RTP</div>
            <div class="text-2xl font-bold text-blue-400">{{ (result.total_rtp * 100).toFixed(2) }}%</div>
          </div>
        </div>

        <div v-if="result" class="h-64 bg-slate-800 rounded-lg p-2">
           <LineChart :chartData="chartData" :options="{ 
               responsive: true, 
               maintainAspectRatio: false, 
               interaction: { mode: 'index', intersect: false },
               plugins: { legend: { display: true, labels: { color: '#94a3b8' } } }, 
               scales: { 
                   y: { type: 'linear', display: true, position: 'left', grid: { color: '#334155' }, title: { display: true, text: 'RTP (%)' } },
                   y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Balance ($)' } },
                   x: { grid: { display: false } } 
               } 
           }" />
        </div>
      </div>
    </div>
  </div>
</template>
