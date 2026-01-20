@echo off
echo Starting Slot Master Pro...

echo Starting Backend...
cd backend
start "Slot Master Backend" cmd /k "pip install -r requirements.txt && python -m uvicorn app:app --reload --port 8000"

echo Starting Frontend...
cd ../frontend
start "Slot Master Frontend" cmd /k "npm install && npm run dev"

echo.
echo ===================================================
echo   Slot Master Pro is starting!
echo   Backend: http://localhost:8000/docs
echo   Frontend: http://localhost:5173
echo ===================================================
pause
