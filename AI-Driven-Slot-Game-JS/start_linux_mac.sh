#!/bin/bash

echo "Starting AI Driven Slot Game (JS Version)..."

# Function to handle cleanup on exit
cleanup() {
    echo "Stopping all services..."
    kill $(jobs -p)
    exit
}

trap cleanup SIGINT SIGTERM

echo "Starting Node.js Backend..."
cd backend
npm install
node src/app.js &
BACKEND_PID=$!

echo "Starting Vue Frontend..."
cd ../frontend
npm install
npm run dev &
FRONTEND_PID=$!

echo ""
echo "==================================================="
echo "  Game is running!"
echo "  Backend API: http://localhost:3000"
echo "  Frontend UI: http://localhost:5173"
echo "  Press Ctrl+C to stop both servers"
echo "==================================================="

wait
