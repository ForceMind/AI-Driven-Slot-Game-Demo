#!/bin/bash

echo "==================================================="
echo "  AI Slot Game - 一键启动 (Linux/Mac)"
echo "==================================================="

# Function to check command existence
check_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo "[错误] 未检测到 $1，请先安装。"
        echo "按回车键退出..."
        read
        exit 1
    else
        echo "检测到 $1: $(command -v $1)"
    fi
}

check_cmd python3
check_cmd node
check_cmd npm

echo "[1/2] 正在启动后端服务 (Backend)..."
# Check if backend directory exists
if [ ! -d "backend" ]; then
    echo "[错误] 找不到 backend 目录!"
    echo "按回车键退出..."
    read
    exit 1
fi

# Run in background with logging
(
    cd backend
    echo "[后端] 安装依赖..."
    pip3 install -r requirements.txt
    echo "[后端] 启动服务..."
    uvicorn app:app --reload --port 8000
) &
BACKEND_PID=$!
echo "后端进程 PID: $BACKEND_PID"

echo "[2/2] 正在启动前端服务 (Frontend)..."
if [ ! -d "frontend" ]; then
    echo "[错误] 找不到 frontend 目录!"
    kill $BACKEND_PID
    echo "按回车键退出..."
    read
    exit 1
fi

# Run in foreground
(
    cd frontend
    echo "[前端] 安装依赖..."
    npm install
    echo "[前端] 启动服务..."
    npm run dev
)

# Cleanup on exit
trap "kill $BACKEND_PID" EXIT
