@echo off
chcp 65001 >nul
title AI Slot Game Launcher
echo ===================================================
echo   AI Slot Game - 一键启动 (Windows - 调试模式)
echo ===================================================

:: 1. Check Python
echo [1/4] 正在检查 Python 环境...
python --version 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 'python' 命令!
    echo 请检查:
    echo 1. 是否安装了 Python?
    echo 2. 安装时是否勾选了 'Add Python to PATH'?
    echo.
    echo 尝试使用 'py' 命令检查...
    py --version 2>nul
    if %errorlevel% neq 0 (
        echo [FATAL] 依然无法找到 Python. 请安装 Python 3.9+.
        pause
        exit /b
    ) else (
        echo 检测到 'py' 命令，将使用 'py' 启动.
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

:: 2. Check Node
echo [2/4] 正在检查 Node.js 环境...
call node --version 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 'node' 命令!
    echo 请安装 Node.js v18+.
    pause
    exit /b
)

:: 3. Start Backend
echo [3/4] 启动后端 (Backend)...
:: Use 'start' with /wait is blocking, so we use separate window.
:: We keep the window open (/k) even if error occurs.
start "Backend Server (后端)" cmd /k "cd backend && echo [Installing Pip Deps] && %PYTHON_CMD% -m pip install -r requirements.txt && echo [Starting Uvicorn] && uvicorn app:app --reload --port 8000"

:: 4. Start Frontend
echo [4/4] 启动前端 (Frontend)...
start "Frontend Server (前端)" cmd /k "cd frontend && echo [Installing NPM Deps] && call npm install && echo [Starting Vite] && call npm run dev"

echo.
echo ===================================================
echo   启动命令已发送!
echo   请不要关闭此窗口，直到你确认另外两个窗口正常运行。
echo ===================================================
pause
