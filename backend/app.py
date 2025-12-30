import time
import uuid
import traceback
import json
import os
import csv
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from models import SpinRequest, SpinResponse, WinningLine, UserState
from llm_client import LLMClient
from outcome_engine import engine
from logger import GameLogger
import logging

# Configure global logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("API")
# Force uvicorn loggers to use our level
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

app = FastAPI(
    title="Slot Master Pro API",
    description="Backend API for Slot Master Pro",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

game_logger = GameLogger()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = f"{type(exc).__name__}: {str(exc)}"
    logger.error(f"Global Exception: {error_msg}")
    traceback.print_exc() 
    return JSONResponse(
        status_code=200, 
        content={
            "matrix": [["ERROR"]*5]*3,
            "winning_lines": [],
            "total_payout": 0,
            "is_win": False,
            "reasoning": f"Backend Error: {error_msg}",
            "balance_update": 0,
            "history_rtp": 0.95,
            "bucket_type": "Error",
            "raw_debug_info": {
                "error": error_msg,
                "trace": traceback.format_exc()
            }
        }
    )

@app.get("/config")
async def get_config():
    return engine.config

@app.post("/config")
async def update_config(config: dict = Body(...)):
    logger.info(">>> Configuration Update Request Received")
    config_path = os.path.join(os.path.dirname(__file__), "game_config_v2.json")
    
    # Backup current config
    backup_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                backup_config = json.load(f)
        except:
            pass

    try:
        # Save to file
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        
        # Reload engine
        logger.info("Reloading OutcomeEngine with new configuration...")
        engine.load_config()
        logger.info("<<< Configuration updated successfully")
        return {"status": "ok", "message": "Config updated and engine reloaded"}
        
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        traceback.print_exc()
        
        # Restore backup
        if backup_config:
            logger.info("Restoring backup config...")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(backup_config, f, indent=2)
            try:
                engine.load_config()
            except:
                pass 
                
        raise HTTPException(status_code=400, detail=f"Invalid Configuration: {str(e)}")

@app.post("/spin", response_model=SpinResponse)
async def spin(req: SpinRequest):
    logger.info(f"--- SPIN START | Bet: {req.bet} | Balance: {req.current_balance} ---")
    
    start_time = time.time()
    spin_id = str(uuid.uuid4())

    # 0. Get History Stats
    total_bet, total_payout, current_history_rtp = game_logger.get_history_stats()
    
    # 1. Construct User State
    user_state = req.user_state
    if not user_state:
        # Fallback for backward compatibility
        user_state = UserState(
            current_bet=req.bet,
            wallet_balance=req.current_balance,
            initial_balance=req.current_balance, # Best guess if not provided
            historical_rtp=current_history_rtp,
            max_historical_balance=req.current_balance * 1.5 # Estimate
        )
    
    # Update RTP in user state
    user_state.historical_rtp = current_history_rtp

    # 2. Generate Outcome (The Core Logic)
    try:
        result = engine.spin(user_state.dict())
    except Exception as e:
        logger.error(f"Engine Failed: {e}")
        raise e

    # 3. Create Response Object
    spin_response = SpinResponse(
        matrix=result["matrix"],
        winning_lines=result["winning_lines"],
        total_payout=result["total_payout"],
        is_win=result["is_win"],
        bucket_type=result["bucket_type"],
        reasoning="Generating commentary...",
        balance_update=result["balance_update"],
        history_rtp=current_history_rtp,
        fail_streak=result.get("fail_streak", 0)
    )

    # 4. Generate AI Commentary
    try:
        commentary = LLMClient.generate_commentary(req.config, spin_response, user_state)
        spin_response.reasoning = commentary
    except Exception as e:
        logger.error(f"AI Commentary Failed: {e}")
        spin_response.reasoning = "Good luck!"

    # 5. Logging
    latency = (time.time() - start_time) * 1000
    game_logger.log_spin(
        spin_id=spin_id,
        bet=req.bet,
        payout=spin_response.total_payout,
        current_rtp=current_history_rtp, 
        provider=req.config.provider,
        latency_ms=latency
    )

    # Update RTP for return
    _, _, final_rtp = game_logger.get_history_stats()
    spin_response.history_rtp = final_rtp

    logger.info(f"--- SPIN END | Payout: {spin_response.total_payout} | Bucket: {spin_response.bucket_type} | Latency: {latency:.2f}ms ---")

    return spin_response

@app.post("/simulate")
async def simulate(params: dict = Body(...)):
    """
    Fast simulation endpoint.
    params: { "spins": 1000, "bet": 10 }
    """
    count = params.get("spins", 100)
    logger.info(f">>> REALISTIC SIMULATION START | Spins: {count} | Bet: {params.get('bet', 10)}")
    # Cap count to prevent timeout
    if count > 10000:
        count = 10000
        
    bet = params.get("bet", 10)
    # Simulation starts with a virtual balance of 1000 to test the ceiling logic
    initial_balance = 1000
    current_balance = initial_balance
    max_balance = balance
    
    total_wagered = 0
    total_won = 0
    fail_streak = 0
    
    for i in range(count):
        # Calculate current RTP for the engine to use in its logic
        current_rtp = (total_won / total_wagered) if total_wagered > 0 else 0
        
        user_state = {
            "current_bet": bet,
            "wallet_balance": current_balance,
            "initial_balance": initial_balance,
            "max_historical_balance": max_balance,
            "historical_rtp": current_rtp,
            "fail_streak": fail_streak,
            "simulation_mode": True # Enable pure math mode
        }
        
        try:
            res = engine.spin(user_state)
            
            # Update fail streak
            fail_streak = res.get("fail_streak", 0)
            
            # Ensure balance_update is float
            bal_update = float(res.get("balance_update", 0))
            current_balance += bal_update
            max_balance = max(max_balance, current_balance)
            
            total_wagered += bet
            total_won += res["total_payout"]
            
            # Sample up to 1000 points for the chart to ensure high resolution
            sample_rate = max(1, count // 1000)
            if i == 0 or i == count - 1 or i % sample_rate == 0:
                history.append({
                    "spin": i + 1,
                    "balance": current_balance,
                    "rtp": (total_won / total_wagered) if total_wagered > 0 else 0
                })
        except Exception as e:
            logger.error(f"Simulation error at spin {i}: {e}")
            break
            
    # Final RTP calculation: Total Won / Total Wagered
    final_rtp = (total_won / total_wagered) if total_wagered > 0 else 0
    
    # Force reload config to ensure weights are updated if changed
    engine.load_config()
    
    logger.info(f"<<< SIMULATION END | Final RTP: {final_rtp*100:.2f}% | Net Profit: {current_balance:.2f}")

    return {
        "final_balance": current_balance,
        "net_profit": current_balance - initial_balance,
        "total_rtp": final_rtp,
        "history": history
    }

@app.get("/history")
async def get_history():
    """返回最近的 50 条历史记录"""
    history = []
    # Use the same absolute path as GameLogger
    filename = game_logger.filepath
    
    if not os.path.exists(filename):
        return []
    
    try:
        with open(filename, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            # Return last 50
            history = rows[-50:]
            history.reverse()
    except Exception as e:
        logger.error(f"Error reading history: {e}")
        
    return history

@app.post("/topup")
async def top_up(req: dict = Body(...)):
    """充值余额"""
    amount = req.get("amount", 100)
    # In a real app, we would update a database.
    # Here, since we don't have a persistent user DB other than the client state passed in /spin,
    # we can't easily "update" the balance server-side unless we store it.
    # However, the frontend maintains the state.
    # So this endpoint might just be a dummy to log the transaction or return success.
    # BUT, wait. The frontend sends `user_id`.
    # If we want to persist, we need a store.
    # Currently `spin` takes `user_state` from request.
    # So the frontend is the source of truth for balance in this demo?
    # Let's check `spin` endpoint.
    
    # SpinRequest has `user_state`.
    # So yes, frontend holds state.
    # But `reset` endpoint exists:
    # @app.post("/reset/{user_id}")
    
    return {"status": "success", "added": amount, "message": f"Successfully added ${amount}"}

@app.post("/reset/{user_id}")
async def reset_user(user_id: str):
    # This endpoint seems to just return success, 
    # implying the frontend should reset its local state.
    return {"status": "reset", "balance": 1000}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

