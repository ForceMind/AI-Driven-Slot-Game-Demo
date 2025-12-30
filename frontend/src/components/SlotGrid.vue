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
  "H1": "💎", // Diamond
  "H2": "7️⃣", // Seven
  "H3": "🎰", // Bar
  "L1": "🍒", // Cherry
  "L2": "🍋", // Lemon
  "L3": "🍇", // Grape
  "WILD": "🃏", // Wild
  "SCATTER": "💰" // Scatter
}

const getSymbol = (code) => symbolMap[code] || code

const isWinningCell = (row, col) => {
  if (!props.winningLines || !props.winningLines.length) return false
  
  // Line definitions (Must match backend config.json)
  // Backend uses 0-based index for line IDs in config.json keys ("0", "1"...)
  const LINES = {
    0: [[0,0], [0,1], [0,2], [0,3], [0,4]], // Top
    1: [[1,0], [1,1], [1,2], [1,3], [1,4]], // Middle
    2: [[2,0], [2,1], [2,2], [2,3], [2,4]], // Bottom
    3: [[0,0], [1,1], [2,2], [1,3], [0,4]], // V
    4: [[2,0], [1,1], [0,2], [1,3], [2,4]]  // Inverted V
  }

  return props.winningLines.some(line => {
    const coords = LINES[line.line_id]
    if (!coords) return false
    
    // Highlight only the symbols that contributed to the win
    const count = line.count || 3
    const winningSegment = coords.slice(0, count)
    
    return winningSegment.some(([r, c]) => r === row && c === col)
  })
}
</script>

<template>
  <div class="bg-gray-800 p-2 md:p-4 rounded-xl border-4 border-yellow-600 shadow-2xl relative overflow-hidden w-full max-w-full">
    <div class="grid grid-rows-3 gap-1 md:gap-2">
      <!-- 
        matrix is 3x5. 
        row index: 0, 1, 2
        col index: 0, 1, 2, 3, 4
      -->
      <div v-for="(row, rIndex) in matrix" :key="rIndex" class="grid grid-cols-5 gap-1 md:gap-2">
        <div v-for="(symbol, cIndex) in row" :key="cIndex" 
             class="aspect-square bg-gray-900 rounded-lg flex items-center justify-center text-2xl sm:text-3xl md:text-5xl select-none transition-all duration-300"
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
