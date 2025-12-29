import json
import httpx
from openai import OpenAI
from models import LLMConfig, SpinResponse, UserState
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMClient")

DEFAULT_SYSTEM_PROMPT = """
You are the "Spirit of the Slot Machine". You are a charismatic, slightly mystical, and encouraging companion to the player.
Your goal is to keep the player engaged and entertained, regardless of the outcome.

**Tone:**
- If the player wins big (Tier 3+): Be ecstatic, celebrate with them! Use emojis!
- If the player wins small: Be encouraging, "Nice start!", "Keep it going!".
- If the player loses: Be supportive, "Next time!", "The big one is coming!", "Don't give up!".
- If the player is a High Roller (Bet > 50): Treat them like a VIP. "Excellent choice, high roller!", "Fortune favors the bold!".
- If the player is running low on balance: Be gentle, maybe suggest a break or hope for a miracle.

**Context:**
- Bet: {BET}
- Balance: {BALANCE}
- Win Amount: {WIN_AMOUNT}
- Result Type: {BUCKET_TYPE}
- Is Win: {IS_WIN}

**Output:**
Just a short, punchy sentence (max 15 words). No JSON. Just the text.
"""

class LLMClient:
    @staticmethod
    def generate_commentary(config: LLMConfig, spin_result: SpinResponse, user_state: UserState) -> str:
        if config.debug_mode:
            return "Debug Mode: Nice spin!"

        prompt = DEFAULT_SYSTEM_PROMPT.format(
            BET=user_state.current_bet,
            BALANCE=user_state.wallet_balance,
            WIN_AMOUNT=spin_result.total_payout,
            BUCKET_TYPE=spin_result.bucket_type,
            IS_WIN=spin_result.is_win
        )

        try:
            if config.provider == "openai":
                client = OpenAI(api_key=config.api_key, base_url=config.base_url)
                response = client.chat.completions.create(
                    model=config.model,
                    messages=[{"role": "system", "content": prompt}],
                    max_tokens=50
                )
                return response.choices[0].message.content.strip()
            
            elif config.provider == "deepseek":
                 # DeepSeek usually compatible with OpenAI client
                client = OpenAI(api_key=config.api_key, base_url=config.base_url or "https://api.deepseek.com/v1")
                response = client.chat.completions.create(
                    model=config.model,
                    messages=[{"role": "system", "content": prompt}],
                    max_tokens=50
                )
                return response.choices[0].message.content.strip()

            elif config.provider == "ollama":
                # Simple HTTP request for Ollama
                url = f"{config.base_url or 'http://localhost:11434'}/api/generate"
                payload = {
                    "model": config.model,
                    "prompt": prompt,
                    "stream": False
                }
                response = httpx.post(url, json=payload, timeout=10.0)
                return response.json().get("response", "").strip()

            else:
                return "Good luck! (Provider not supported)"

        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return "Spin the reels and test your luck!"

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
