<script setup>
import { computed } from 'vue'

const props = defineProps({
  matrix: {
    type: Array,
    default: () => [
      ["?", "?", "?", "?", "?"],
      ["?", "?", "?", "?", "?"],
      ["?", "?", "?", "?", "?"],
    ]
  },
  winningLines: {
    type: Array,
    default: () => []
  },
  isSpinning: Boolean
})

const symbolMap = {
  "1": "🐲",
  "2": "🦁",
  "3": "🧧",
  "4": "🅰️",
  "5": "👑",
  "10": "🃏",
  "11": "💎"
}

const getSymbol = (code) => symbolMap[code] || code

const isWinningCell = (row, col) => {
  if (!props.winningLines || !props.winningLines.length) return false
  
  // Basic line definitions (matches backend)
  // 0: Top Row, 1: Middle Row, 2: Bottom Row
  const LINES = {
    0: [[0,0], [0,1], [0,2], [0,3], [0,4]],
    1: [[1,0], [1,1], [1,2], [1,3], [1,4]],
    2: [[2,0], [2,1], [2,2], [2,3], [2,4]]
  }

  return props.winningLines.some(line => {
    // line might be just an object {line_id: 1, amount: 20}
    // We need to map line_id to coordinates
    const coords = LINES[line.line_id]
    if (!coords) return false
    
    // Check if this cell (row, col) is in the winning line definition
    return coords.some(([r, c]) => r === row && c === col)
  })
}
</script>

<template>
  <div class="bg-gray-800 p-4 rounded-xl border-4 border-yellow-600 shadow-2xl relative overflow-hidden">
    <div class="grid grid-rows-3 gap-2">
      <!-- 
        matrix is 3x5. 
        row index: 0, 1, 2
        col index: 0, 1, 2, 3, 4
      -->
      <div v-for="(row, rIndex) in matrix" :key="rIndex" class="grid grid-cols-5 gap-2">
        <div v-for="(symbol, cIndex) in row" :key="cIndex" 
             class="h-16 w-16 md:h-24 md:w-24 bg-gray-900 rounded-lg flex items-center justify-center text-3xl md:text-5xl select-none transition-all duration-300"
             :class="{
               'animate-pulse bg-yellow-900': isWinningCell(rIndex, cIndex),
               'blur-sm': isSpinning
             }">
          {{ isSpinning ? '🎰' : getSymbol(symbol) }}
        </div>
      </div>
    </div>
  </div>
</template>
