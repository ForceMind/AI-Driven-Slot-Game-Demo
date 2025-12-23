# AI-Driven Slot Game Demo - Architecture Plan

## 1. Project Structure

```
/
├── backend/
│   ├── app.py                 # Main FastAPI application & endpoints
│   ├── llm_client.py          # LLM Provider logic (OpenAI/Ollama adapter)
│   ├── game_logic.py          # Shadow Accountant (Validation & Math)
│   ├── models.py              # Pydantic data models
│   ├── logger.py              # CSV logging logic
│   └── requirements.txt       # Python dependencies
├── frontend/                  # Vue.js + Vite project
│   ├── index.html
│   ├── vite.config.js
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── components/
│       │   ├── SlotGrid.vue
│       │   ├── ControlPanel.vue
│       │   ├── ConfigModal.vue
│       │   └── StatsDisplay.vue
│       └── assets/
└── plans/
    └── architecture.md
```

## 2. Backend Components (Python/FastAPI)

### A. Data Models (`models.py`)
- **SpinRequest**: `bet`, `current_balance`, `history_rtp`, `config` (provider, api_key, model, etc.)
- **SpinResponse**: `matrix`, `winning_lines`, `total_payout`, `reasoning`, `balance_update`

### B. LLM Client (`llm_client.py`)
- **Interface**: `generate_spin(context, config)`
- **Providers**:
  - `OpenAIClient`: Uses `openai` library.
  - `OllamaClient`: Uses raw HTTP requests to local Ollama instance.
- **System Prompt**: Dynamically injected with `TARGET_RTP` and game rules.

### C. Shadow Accountant (`game_logic.py`)
- **Symbols**: Map Emojis to IDs/Values.
  - H1(🐲), H2(🦁), M1(🧧), L1(🅰️), L2(👑), Wild(🃏), Scatter(💎)
- **Paytable**:
  - 5-of-a-kind payouts as specified.
  - *Self-correction*: Need to define payouts for 3 and 4 matches too? The prompt only specified "5-of-a-kind match" but standard slots usually pay for 3, 4, and 5. **Clarification Assumption**: We will implement standard 3, 4, 5 logic or strictly follow prompt (Prompt says "Symbols & Paytable (5-of-a-kind match): ..."). I will implement 3, 4, 5 scaling logic (e.g., 3x=10%, 4x=50%, 5x=100% of max) or just stick to 5x if strictly interpreted. *Decision: Implement payouts for 3, 4, and 5 to make it playable, deriving lower tiers.*
- **Validation**:
  1. Receive `matrix` from LLM.
  2. Run deterministic line checks (Row 0, 1, 2).
  3. Calculate "Real Payout".
  4. Compare with LLM's `total_payout`.
  5. If mismatch -> Log warning, Use Real Payout.

### D. CSV Logger (`logger.py`)
- Handles writing to `game_data.csv`.
- Columns: `Timestamp`, `Spin_ID`, `Bet`, `Payout`, `Is_Win`, `Current_RTP`, `AI_Provider`, `Latency_ms`.

## 3. Frontend Components (Vue 3)

### A. State
- **Game State**: `matrix`, `balance`, `lastWin`, `debugLog`.
- **Config State**: `provider` (default: 'openai'), `apiKey`, `baseUrl`, `model`, `targetRTP`.

### B. UI
- **Grid**: 3x5 grid using Flexbox/Grid.
- **Animations**: CSS transitions for "spinning" (blur/movement) and "win" (flash).
- **Debug**: Collapsible section to show the raw JSON and Reasoning from the AI.

## 4. Implementation Strategy

1. **Step 1: Backend Core** - Setup FastAPI, Pydantic models, and the Shadow Accountant logic. Verify math works.
2. **Step 2: LLM Integration** - Implement the client to talk to OpenAI/Ollama.
3. **Step 3: API Endpoint** - Wire up `/spin` to call LLM -> Validate -> Return.
4. **Step 4: Frontend Scaffolding** - Vite + Tailwind.
5. **Step 5: Frontend Logic** - Connect UI to `/spin`.

## 5. Technical Considerations
- **Error Handling**: What if LLM returns bad JSON? -> Retry logic or Fallback RNG spin.
- **Latency**: LLM calls are slow. Frontend needs a "Spinning..." state that can last 2-5 seconds.
