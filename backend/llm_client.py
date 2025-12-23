import json
import httpx
from openai import OpenAI
from models import LLMConfig
import re
import logging
import os

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMClient")

# 加载游戏配置以生成 Prompt
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "game_config.json")
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        GAME_CONFIG = json.load(f)
except Exception as e:
    logger.error(f"Failed to load game_config.json: {e}")
    GAME_CONFIG = {}

def get_symbol_list_str():
    lines = []
    symbols = GAME_CONFIG.get("symbols", {})
    if not isinstance(symbols, dict):
        logger.error(f"GAME_CONFIG['symbols'] is not a dict: {type(symbols)}")
        return "No symbols configured"
    
    for symbol_id, s in symbols.items():
        if isinstance(s, dict):
            val = s.get('base_value', 0)
            lines.append(f"  - ID {symbol_id}: {val}x base value")
        else:
            lines.append(f"  - ID {symbol_id}: {s}")
    return "\n".join(lines)

def get_multipliers_str():
    multipliers = GAME_CONFIG.get("multipliers", {})
    lines = []
    for count, mult in multipliers.items():
        lines.append(f"  - {count}-of-a-kind: {mult}x multiplier")
    return "\n".join(lines)

DEFAULT_SYSTEM_PROMPT = """
You are the Slot Game Engine. 
**Game Rules:**
- Grid: 3x5.
- Symbols Base Values: 
{SYMBOL_LIST}
- Paytable Multipliers:
{MULTIPLIER_LIST}
- Payout Formula: Bet * Base Value * Multiplier.
- Lines: Standard 3 horizontal lines (Row 0, Row 1, Row 2).

**Objective:**
Maintain a long-term RTP of {TARGET_RTP}. 
- If History RTP < {TARGET_RTP}, you MAY give a small win (2x - 5x bet). 
- If History RTP > {TARGET_RTP}, you MUST force a loss.
- NEVER give a win larger than 10x bet.
- Current History RTP is {HISTORY_RTP}. If this is > {TARGET_RTP}, you are OVER-PAYING. STOP IT.
- Global Profit/Loss: {GLOBAL_PL}. If this is negative, the house is losing money. BE EXTREMELY STINGY.

**Critical Instruction:**
- Most spins (90%+) should be LOSSES.
- A WIN means 3+ identical symbols (or Wilds) on a horizontal line starting from the leftmost column.
- A LOSS means no 3-of-a-kind matches on any horizontal line.
- **WARNING on WILDs**: 3 or more WILDs on a line is a HUGE WIN. If you want the player to LOSE, DO NOT use more than one WILD in the entire matrix.
- **NO FULL SCREENS**: Never fill the matrix with the same symbol or all WILDs.
- Use ONLY numeric IDs in the matrix. Do not use emojis or string codes.

**Context:**
Current Bet: {BET}
Current Balance: {BALANCE}
History RTP: {HISTORY_RTP}
Global P/L: {GLOBAL_PL}
Random Seed: {RANDOM_SEED}

**Output Format (IMPORTANT: DO NOT COPY THIS EXAMPLE):**
Strict JSON only: 
{{
  "matrix": [["1","2","3","4","5"], ["1","1","2","3","4"], ["5","4","3","2","1"]], 
  "winning_lines": [], 
  "total_payout": 0,
  "reasoning": "RTP is high and house profit is low, providing a standard loss."
}}
"""

class LLMClient:
    @staticmethod
    def generate_spin(config: LLMConfig, bet: float, balance: float, history_rtp: float, global_pl: float = 0.0):
        # 1. 构造 Prompt - 强力默认值
        template = config.system_prompt_template
        if not template or not template.strip():
            logger.info("⚠️ 检测到 Prompt 为空，使用系统默认 Prompt")
            template = DEFAULT_SYSTEM_PROMPT
        
        # 2. 变量替换
        import time
        import random
        system_prompt = template
        system_prompt = system_prompt.replace("{TARGET_RTP}", str(config.target_rtp))
        system_prompt = system_prompt.replace("{BET}", str(bet))
        system_prompt = system_prompt.replace("{BALANCE}", str(balance))
        system_prompt = system_prompt.replace("{HISTORY_RTP}", str(history_rtp))
        system_prompt = system_prompt.replace("{GLOBAL_PL}", f"{global_pl:.2f}")
        system_prompt = system_prompt.replace("{SYMBOL_LIST}", get_symbol_list_str())
        system_prompt = system_prompt.replace("{MULTIPLIER_LIST}", get_multipliers_str())
        system_prompt = system_prompt.replace("{RANDOM_SEED}", f"{time.time()}-{random.random()}")
            
        # 记录发送给 AI 的完整 Prompt
        with open("llm_payload.log", "a", encoding="utf-8") as f:
            f.write(f"\n\n{'#'*60}\n")
            f.write(f"TIMESTAMP: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"--- FULL SYSTEM PROMPT ---\n{system_prompt}\n")
            f.write(f"{'#'*60}\n")

        logger.info(f"--- 启动请求 ---")
        logger.info(f"Provider: {config.provider}")
        logger.info(f"URL: {config.base_url}")
        
        logger.info(f"发送 Prompt (前200字符): {repr(system_prompt[:200])}...")
        
        # 3. 调试模式
        if config.debug_mode:
            logger.info("!! DEBUG MODE ENABLED !!")
            return LLMClient._call_debug(config, system_prompt)

        # 4. 核心调用逻辑
        try:
            if config.provider in ["openai", "deepseek", "gemini"]:
                return LLMClient._call_openai_direct(config, system_prompt)
            elif config.provider == "ollama":
                return LLMClient._call_ollama(config, system_prompt)
            else:
                raise ValueError(f"Unknown provider: {config.provider}")
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            raise e

    @staticmethod
    def _clean_json_content(content: str) -> str:
        if not content: return "{}"
        content = content.strip()
        
        # 1. 尝试提取 Markdown 代码块中的内容
        if "```" in content:
            matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if matches:
                # 取最长的一个，通常是真正的 JSON
                content = max(matches, key=len).strip()
            else:
                # 备选方案：移除标记
                content = re.sub(r"```(?:json)?", "", content)
                content = content.replace("```", "").strip()

        # 2. 寻找第一个 { 和最后一个 }
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            content = content[start : end + 1]
        elif '"matrix"' in content:
            # 如果没找到大括号但有关键字段，尝试补全
            logger.warning("检测到疑似 JSON 裸数据但缺失大括号，尝试补全")
            if not content.startswith('{'): content = '{' + content
            if not content.endswith('}'): content = content + '}'

        return content

    @staticmethod
    def _call_openai_direct(config: LLMConfig, prompt: str):
        base_url = config.base_url or "https://api.deepseek.com"
        api_key = config.api_key
        
        if not api_key:
            raise ValueError("API Key is missing!")

        client = OpenAI(api_key=api_key, base_url=base_url)
        raw_text = ""
        
        try:
            # 针对 DeepSeek 和 GPT-4o 等支持 JSON Mode 的模型开启 response_format
            extra_params = {}
            if "deepseek" in config.model.lower() or "gpt" in config.model.lower():
                extra_params["response_format"] = {"type": "json_object"}
                logger.info(f"Enabled JSON Mode for model: {config.model}")

            response = client.chat.completions.create(
                model=config.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Generate next spin result in JSON."}
                ],
                temperature=0.7,
                **extra_params
            )
            
            raw_text = response.choices[0].message.content
            
            # 记录 AI 的原始返回
            with open("llm_payload.log", "a", encoding="utf-8") as f:
                f.write(f"--- RAW AI RESPONSE ---\n{raw_text}\n")
                f.write(f"{'#'*60}\n")

            if not raw_text:
                raise ValueError("API returned empty response")

            # 清理并解析
            cleaned = LLMClient._clean_json_content(raw_text)
            logger.info(f"Cleaned JSON: {repr(cleaned)}")
            
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as je:
                # 如果解析失败，尝试进一步清理（移除注释等）
                logger.warning(f"标准 JSON 解析失败，尝试移除注释: {je}")
                # 移除 // 注释
                cleaned_no_comments = re.sub(r"//.*", "", cleaned)
                # 移除 /* */ 注释
                cleaned_no_comments = re.sub(r"/\*.*?\*/", "", cleaned_no_comments, flags=re.DOTALL)
                return json.loads(cleaned_no_comments)
            
        except Exception as e:
            # 详细报错
            error_detail = f"解析失败: {str(e)} | 原始返回: {repr(raw_text)}"
            logger.error(error_detail)
            print(f"!!! CRITICAL ERROR: {error_detail}")
            raise ValueError(error_detail)

    @staticmethod
    def _call_debug(config: LLMConfig, prompt: str):
        base_url = config.base_url or "https://api.deepseek.com"
        client = OpenAI(api_key=config.api_key, base_url=base_url)
        try:
            resp = client.chat.completions.create(
                model=config.model,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": "JSON"}],
                temperature=0.7
            )
            txt = resp.choices[0].message.content
            
            return {
                "matrix": [["D","E","B","U","G"]]*3,
                "winning_lines": [],
                "total_payout": 0,
                "is_win": False,
                "reasoning": "DEBUG MODE",
                "balance_update": 0,
                "raw_debug_info": {
                    "raw_response": txt,
                    "provider": config.provider,
                    "model": config.model
                }
            }
        except Exception as e:
            raise ValueError(f"Debug Request Failed: {e}")

    @staticmethod
    def _call_ollama(config: LLMConfig, prompt: str):
        url = f"{config.base_url or 'http://localhost:11434'}/api/chat"
        payload = {
            "model": config.model,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": "JSON"}],
            "stream": False, "format": "json"
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload)
            data = resp.json()
            return json.loads(data.get("message", {}).get("content", "{}"))
