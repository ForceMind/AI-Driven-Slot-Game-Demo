import time
import uuid
import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from models import SpinRequest, SpinResponse, WinningLine
from llm_client import LLMClient
from game_logic import ShadowAccountant
from logger import GameLogger
import logging

# Configure global logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

app = FastAPI(
    title="AI 老虎机后端 API (AI Slot Game Backend)",
    description="Backend API for AI Slot Game",
    version="1.0.0",
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
    traceback.print_exc() # Print full stack trace to console
    
    # 关键修改：即便是 500 错误，也返回一个符合前端预期的 JSON 结构
    # 这样前端的调试模式逻辑才能捕获到内容，而不是被浏览器直接拦截 500
    return JSONResponse(
        status_code=200, # 欺骗前端，返回 200 以便前端能读取 body
        content={
            "matrix": [["ERROR"]*5]*3,
            "winning_lines": [],
            "total_payout": 0,
            "is_win": False,
            "reasoning": f"Backend Error: {error_msg}",
            "balance_update": 0,
            "history_rtp": 0.95, # 提供默认值防止前端状态破坏
            "raw_debug_info": {
                "error": error_msg,
                "trace": traceback.format_exc()
            },
            "detail": error_msg 
        }
    )

@app.post("/spin", response_model=SpinResponse)
async def spin(req: SpinRequest):
    logger.info(f"Received Spin Request. Bet: {req.bet}, Provider: {req.config.provider}")
    
    start_time = time.time()
    spin_id = str(uuid.uuid4())

    # 0. 从后端日志获取真实的 RTP 统计，而不是依赖前端传参
    total_bet, total_payout, current_history_rtp = game_logger.get_history_stats()
    global_pl = total_bet - total_payout
    logger.info(f"Current History RTP: {current_history_rtp}, Global P/L: {global_pl}")
    
    # 1. Generate Result via LLM
    try:
        llm_result = LLMClient.generate_spin(
            config=req.config,
            bet=req.bet,
            balance=req.current_balance,
            history_rtp=current_history_rtp,
            global_pl=global_pl
        )
    except Exception as e:
        logger.error(f"LLM Client Failed: {e}")
        raise e

    # 2. Extract Matrix
    matrix = llm_result.get("matrix", [])
    
    # 3. Validation & Normalization (Deterministic calculation)
    real_payout, real_winning_lines, normalized_matrix = ShadowAccountant.calculate_payout(matrix, req.bet)

    # 如果是调试模式结果，直接返回
    if req.config.debug_mode:
        return SpinResponse(
            matrix=normalized_matrix,
            winning_lines=real_winning_lines,
            total_payout=real_payout,
            is_win=real_payout > 0,
            reasoning=llm_result.get("reasoning", "Debug Mode"),
            balance_update=real_payout - req.bet,
            history_rtp=current_history_rtp,
            raw_debug_info=llm_result.get("raw_debug_info")
        )
    
    # 关键修复：如果 AI 瞎编了一个中奖金额，但实际矩阵没中奖，以实际计算为准
    # 并在日志中记录这种不一致
    if abs(real_payout - llm_result.get("total_payout", 0)) > 0.01:
        logger.warning(f"LLM Payout ({llm_result.get('total_payout')}) mismatch with Real Payout ({real_payout}). Using Real.")

    # 4. Logging
    latency = (time.time() - start_time) * 1000
    
    try:
        game_logger.log_spin(
            spin_id=spin_id,
            bet=req.bet,
            payout=real_payout,
            current_rtp=current_history_rtp, 
            provider=req.config.provider,
            latency_ms=latency
        )
    except Exception as e:
        logger.error(f"CSV Logging Failed: {e}")

    # 重新计算最新的 RTP 返回给前端显示
    _, _, final_rtp = game_logger.get_history_stats()

    logger.info(f"Spin Complete. Payout: {real_payout}. Latency: {latency:.2f}ms")

    return SpinResponse(
        matrix=normalized_matrix,
        winning_lines=real_winning_lines,
        total_payout=real_payout,
        is_win=real_payout > 0,
        reasoning=llm_result.get("reasoning", "No reasoning provided."),
        balance_update=real_payout - req.bet,
        history_rtp=final_rtp
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
