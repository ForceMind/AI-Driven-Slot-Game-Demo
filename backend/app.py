import time
import uuid
import traceback
import json
import os
import csv
import copy
from typing import Dict
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, Body, Header, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from models import SpinRequest, SpinResponse, WinningLine, UserState
from llm_client import LLMClient
from outcome_engine import OutcomeEngine
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

# --- Session Management ---

# Global Engine Cache to avoid re-initializing for same config
engine_cache: Dict[str, OutcomeEngine] = {}

def get_cached_engine(config: dict) -> OutcomeEngine:
    """获取或创建缓存的引擎实例"""
    # 创建一个临时引擎来获取哈希（轻量级，不初始化桶）
    temp_engine = OutcomeEngine(config_override=config)
    config_hash = temp_engine._get_config_hash()
    
    if config_hash not in engine_cache:
        logger.info(f"Engine cache miss for hash {config_hash}. Initializing...")
        # 此时 temp_engine 已经完成了初始化（从磁盘缓存或计算）
        engine_cache[config_hash] = temp_engine
    else:
        logger.info(f"Engine cache hit for hash {config_hash}.")
    
    return engine_cache[config_hash]

class SessionData:
    def __init__(self, default_config):
        self.id = str(uuid.uuid4())
        self.config = copy.deepcopy(default_config)
        # 使用缓存引擎
        self.engine = get_cached_engine(self.config)
        self.history = [] # List of dicts
        self.total_bet = 0.0
        self.total_payout = 0.0
        self.last_access = time.time()

# Global Sessions Store (In-Memory)
sessions: Dict[str, SessionData] = {}

# Load default config once
DEFAULT_CONFIG = {}
config_path = os.path.join(os.path.dirname(__file__), "game_config_v2.json")
if not os.path.exists(config_path):
    config_path = os.path.join(os.path.dirname(__file__), "game_config.json")

if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        DEFAULT_CONFIG = json.load(f)
else:
    logger.error("CRITICAL: No configuration file found!")

def get_session(x_session_id: str = Header(None)) -> SessionData:
    """
    Dependency to retrieve or create a session based on the X-Session-ID header.
    """
    if not x_session_id:
        # If no header, create a temporary one (though frontend should send it)
        x_session_id = str(uuid.uuid4())
    
    if x_session_id not in sessions:
        logger.info(f"Creating new session: {x_session_id}")
        sessions[x_session_id] = SessionData(DEFAULT_CONFIG)
    
    session = sessions[x_session_id]
    session.last_access = time.time()
    return session

# --- Endpoints ---

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

@app.get("/api/config")
async def get_config_api(session: SessionData = Depends(get_session)):
    """Get current game configuration (API alias)"""
    # Inject real bucket stats if available
    if hasattr(session.engine, 'bucket_stats'):
        if "buckets" in session.config:
            for k, avg_mult in session.engine.bucket_stats.items():
                if k in session.config["buckets"]:
                    session.config["buckets"][k]["real_avg_mult"] = avg_mult
    return session.config

@app.get("/config")
async def get_config(session: SessionData = Depends(get_session)):
    # Inject real bucket stats if available
    if hasattr(session.engine, 'bucket_stats'):
        if "buckets" in session.config:
            for k, avg_mult in session.engine.bucket_stats.items():
                if k in session.config["buckets"]:
                    session.config["buckets"][k]["real_avg_mult"] = avg_mult
    return session.engine.config

@app.post("/config")
async def update_config(config: dict = Body(...), session: SessionData = Depends(get_session)):
    logger.info(f"[{session.id}] Configuration Update Request")
    try:
        # Update session config
        session.config = config
        # Reload engine with cached instance
        session.engine = get_cached_engine(session.config)
        logger.info(f"[{session.id}] Configuration updated successfully")
        return {"status": "ok", "message": "Config updated for this session"}
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Invalid Configuration: {str(e)}")

@app.post("/spin", response_model=SpinResponse)
async def spin(req: SpinRequest, session: SessionData = Depends(get_session)):
    logger.info(f"[{session.id}] SPIN START | Bet: {req.bet} | Balance: {req.current_balance}")
    
    start_time = time.time()
    spin_id = str(uuid.uuid4())

    # 0. Get History Stats (Session specific)
    # Initial virtual stats to prevent extreme RTP swings at start
    current_total_bet = session.total_bet + 100.0
    current_total_payout = session.total_payout + 95.0
    current_history_rtp = current_total_payout / current_total_bet if current_total_bet > 0 else 0.95
    
    # 1. Construct User State
    user_state = req.user_state
    if not user_state:
        user_state = UserState(
            current_bet=req.bet,
            wallet_balance=req.current_balance,
            initial_balance=req.current_balance,
            historical_rtp=current_history_rtp,
            max_historical_balance=req.current_balance * 1.5
        )
    
    user_state.historical_rtp = current_history_rtp

    # 2. Generate Outcome
    try:
        # Pass session.config as runtime_config to ensure session-specific settings (weights, RTP) are used
        # even if the engine instance is shared/cached.
        result = session.engine.spin(user_state.dict(), runtime_config=session.config)
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

    # 5. Logging (In-Memory Session History)
    latency = (time.time() - start_time) * 1000
    
    session.total_bet += req.bet
    session.total_payout += spin_response.total_payout
    
    # Calculate new RTP
    new_rtp = (session.total_payout + 95.0) / (session.total_bet + 100.0)
    spin_response.history_rtp = new_rtp

    # Append to session history
    session.history.append({
        "Timestamp": datetime.now().isoformat(),
        "Spin_ID": spin_id,
        "Bet": req.bet,
        "Payout": spin_response.total_payout,
        "Is_Win": spin_response.is_win,
        "Current_RTP": new_rtp,
        "Latency_ms": round(latency, 2)
    })
    
    # Keep history size manageable
    if len(session.history) > 100:
        session.history = session.history[-100:]

    logger.info(f"[{session.id}] SPIN END | Payout: {spin_response.total_payout} | Bucket: {spin_response.bucket_type}")

    return spin_response

@app.post("/simulate")
async def simulate(params: dict = Body(...), session: SessionData = Depends(get_session)):
    """
    Fast simulation endpoint.
    Uses the session's current engine configuration.
    """
    count = params.get("spins", 100)
    logger.info(f"[{session.id}] SIMULATION START | Spins: {count}")
    
    if count > 10000: count = 10000
    bet = params.get("bet", 10)
    
    # 理论上模拟需要足够的本金来支撑所有旋转
    # 如果本金太少，会触发 "Max Win Ratio" 限制，导致大奖被过滤，从而拉低 RTP
    # 因此我们将初始余额设置为：旋转次数 * 单次下注
    initial_balance = count * bet
    current_balance = initial_balance
    max_balance = current_balance
    
    total_wagered = 0
    total_won = 0
    fail_streak = 0
    history = []
    
    # Use session engine
    engine = session.engine
    
    for i in range(count):
        current_rtp = (total_won / total_wagered) if total_wagered > 0 else 0
        
        user_state = {
            "current_bet": bet,
            "wallet_balance": current_balance,
            "initial_balance": initial_balance,
            "max_historical_balance": max_balance,
            "historical_rtp": current_rtp,
            "fail_streak": fail_streak,
            "simulation_mode": True
        }
        
        try:
            # Pass session.config as runtime_config to ensure simulation uses the current session's settings
            res = engine.spin(user_state, runtime_config=session.config)
            fail_streak = res.get("fail_streak", 0)
            bal_update = float(res.get("balance_update", 0))
            current_balance += bal_update
            max_balance = max(max_balance, current_balance)
            total_wagered += bet
            total_won += res["total_payout"]
            
            sample_rate = max(1, count // 1000)
            if i == 0 or i == count - 1 or i % sample_rate == 0:
                history.append({
                    "spin": i + 1,
                    "balance": current_balance,
                    "rtp": (total_won / total_wagered) if total_wagered > 0 else 0
                })
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            break
            
    final_rtp = (total_won / total_wagered) if total_wagered > 0 else 0
    
    return {
        "final_balance": current_balance,
        "net_profit": current_balance - initial_balance,
        "total_rtp": final_rtp,
        "history": history
    }

@app.get("/history")
async def get_history(session: SessionData = Depends(get_session)):
    """返回当前会话的历史记录"""
    # Return reversed copy (newest first)
    return list(reversed(session.history))

@app.post("/topup")
async def top_up(req: dict = Body(...)):
    return {"status": "success", "message": "Topup logged"}

@app.post("/reset/{user_id}")
async def reset_user(user_id: str):
    return {"status": "reset", "balance": 1000}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

