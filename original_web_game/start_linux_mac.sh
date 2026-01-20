#!/bin/bash

# AI 驱动老虎机演示 - Linux/Mac 启动脚本

echo "Starting Slot Master Pro..."

# 获取脚本所在目录
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"

# 启动后端
echo "Starting Backend..."
cd "$BACKEND_DIR"
# 检查是否有 venv，如果有则激活
if [ -d "venv" ]; then
    source venv/bin/activate
fi
# 后台运行后端
pip install -r requirements.txt
python3 -m uvicorn app:app --reload --port 8000 &
BACKEND_PID=$!

# 启动前端
echo "Starting Frontend..."
cd "$FRONTEND_DIR"
npm install
npm run dev &
FRONTEND_PID=$!

echo ""
echo "==================================================="
echo "  Slot Master Pro is starting!"
echo "  Backend: http://localhost:8000/docs"
echo "  Frontend: http://localhost:5173"
echo "==================================================="
echo "Press Ctrl+C to stop both servers."

# 等待用户中断
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
