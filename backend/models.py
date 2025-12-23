from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any

class LLMConfig(BaseModel):
    provider: str = Field(..., description="LLM Provider: 'openai', 'ollama', 'gemini', 'deepseek'")
    api_key: Optional[str] = Field(None, description="API Key for providers")
    base_url: Optional[str] = Field(None, description="Base URL for custom API")
    model: str = Field(..., description="Model name e.g. 'gpt-4o', 'gemini-1.5-flash'")
    target_rtp: float = Field(0.97, description="Target RTP for the session")
    system_prompt_template: Optional[str] = Field(None, description="Custom system prompt template")
    debug_mode: bool = Field(False, description="Skip logic and return raw LLM response")

class SpinRequest(BaseModel):
    bet: float
    current_balance: float
    history_rtp: float
    config: LLMConfig

class WinningLine(BaseModel):
    line_id: int
    amount: float
    symbol: Optional[str] = None # 关键修复：允许为空，防止 DeepSeek 返回的数据校验失败

class SpinResponse(BaseModel):
    matrix: List[List[str]]
    winning_lines: List[WinningLine]
    total_payout: float
    is_win: bool
    reasoning: str
    balance_update: float
    history_rtp: float # 新增：返回后端计算的实时 RTP
    # Extra field for debug info
    raw_debug_info: Optional[Dict[str, Any]] = None
