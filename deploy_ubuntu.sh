#!/bin/bash

# ==========================================
# AI Slot Game - Ubuntu/Linux Production Deployment Script
# ==========================================
# Features:
# 1. Uses non-conflicting ports (Backend: 8090, Frontend: 5180)
# 2. Uses pm2 for process management (auto-restart)
# 3. Uses Nginx as reverse proxy (optional, for domain mapping)
# ==========================================

BACKEND_PORT=8090
FRONTEND_PORT=5180
APP_DIR=$(pwd)

echo ">>> [1/5] Checking Environment..."

# Check Node/NPM
if ! command -v node &> /dev/null; then
    echo "Installing Node.js (LTS 20.x)..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# Check Python/Pip
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
fi

# Check PM2
if ! command -v pm2 &> /dev/null; then
    echo "Installing PM2..."
    sudo npm install -g pm2
fi

echo ">>> [2/5] Setting up Backend..."
cd $APP_DIR/backend
# Create venv to avoid conflicts
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

echo ">>> [3/5] Setting up Frontend..."
cd $APP_DIR/frontend
# Update vite config port to avoid conflict if needed, 
# or just pass --port flag in start command.
npm install
npm run build

echo ">>> [4/5] Starting Services with PM2..."
cd $APP_DIR

# Start Backend
# We run uvicorn on a specific port
pm2 delete ai-slot-backend 2>/dev/null || true
pm2 start "cd backend && source venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port $BACKEND_PORT" --name ai-slot-backend

# Start Frontend (Serving static build or dev server?)
# For production, we should serve the 'dist' folder.
# We can use 'pm2 serve' for static files.
pm2 delete ai-slot-frontend 2>/dev/null || true
pm2 serve frontend/dist $FRONTEND_PORT --name ai-slot-frontend --spa

echo ">>> [5/5] Deployment Complete!"
echo "------------------------------------------------"
echo "Backend running on: http://YOUR_SERVER_IP:$BACKEND_PORT"
echo "Frontend running on: http://YOUR_SERVER_IP:$FRONTEND_PORT"
echo "------------------------------------------------"
echo "To check status: pm2 status"
echo "To view logs:    pm2 logs"
echo "------------------------------------------------"

# Optional: Nginx Config hint
echo ""
echo "If you want to access via domain (e.g. slots.example.com), configure Nginx:"
echo "location /spin { proxy_pass http://127.0.0.1:$BACKEND_PORT; }"
echo "location / { proxy_pass http://127.0.0.1:$FRONTEND_PORT; }"
