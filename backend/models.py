from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union

class LLMConfig(BaseModel):
    provider: str = Field(..., description="LLM Provider: 'openai', 'ollama', 'gemini', 'deepseek'")
    api_key: Optional[str] = Field(None, description="API Key for providers")
    base_url: Optional[str] = Field(None, description="Base URL for custom API")
    model: str = Field(..., description="Model name e.g. 'gpt-4o', 'gemini-1.5-flash'")
    target_rtp: float = Field(0.97, description="Target RTP for the session")
    system_prompt_template: Optional[str] = Field(None, description="Custom system prompt template")
    debug_mode: bool = Field(False, description="Skip logic and return raw LLM response")

class UserState(BaseModel):
    user_level: int = 1
    wallet_balance: float = 1000.0
    current_bet: float = 10.0
    historical_rtp: float = 0.0
    max_historical_balance: float = 1000.0

class SpinRequest(BaseModel):
    bet: float
    current_balance: float
    history_rtp: float
    config: LLMConfig
    user_state: Optional[UserState] = None # Added for new logic

class WinningLine(BaseModel):
    line_id: int
    amount: float
    symbol: Optional[str] = None
    count: int = 0

class SpinResponse(BaseModel):
    matrix: List[List[str]]
    winning_lines: List[WinningLine]
    total_payout: float
    is_win: bool
    reasoning: str # Used for AI commentary now
    balance_update: float
    history_rtp: float
    bucket_type: str = "Unknown"
    raw_debug_info: Optional[Dict[str, Any]] = None

