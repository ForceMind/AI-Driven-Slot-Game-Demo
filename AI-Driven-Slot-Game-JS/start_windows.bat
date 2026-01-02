@echo off
echo Starting AI Driven Slot Game (JS Version)...

echo Starting Node.js Backend...
cd backend
start "Slot Game Backend (Node)" cmd /k "npm install && node src/app.js"

echo Starting Vue Frontend...
cd ../frontend
start "Slot Game Frontend" cmd /k "npm install && npm run dev"

echo.
echo ===================================================
echo   Game is starting!
echo   Backend API: http://localhost:3000
echo   Frontend UI: http://localhost:5173
echo ===================================================
pause
