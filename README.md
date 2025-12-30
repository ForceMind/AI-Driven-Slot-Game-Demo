# Slot Master Pro

A high-performance, algorithmic slot machine engine with advanced probability control.

## Features

- **Core Algorithm**: Uses Pseudo Random Distribution (PRD) to balance win/loss streaks dynamically based on a "C-value".
- **Bucket System**: Pre-calculated outcome buckets (1M+ combinations) for instant spin results and precise RTP control.
- **Risk Management**: Built-in safety caps (e.g., max win per spin <= 20% of balance).
- **Tiered Unlocking**: Higher volatility buckets unlock as the player wagers more.
- **Modern Stack**: Python FastAPI backend + Vue 3 & Tailwind CSS frontend.

## Quick Start (Windows)

Double-click `start_windows.bat` to launch both the backend and frontend.

## Manual Setup

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload
```
Server runs at: http://localhost:8000

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Client runs at: http://localhost:5173

## Configuration

Game rules and math model can be tweaked in `backend/config.json`.
- `target_rtp`: Global Return to Player target.
- `base_c_value`: The 'C' constant for the PRD formula.
- `buckets`: Define payout ranges and probabilities for different win tiers.
