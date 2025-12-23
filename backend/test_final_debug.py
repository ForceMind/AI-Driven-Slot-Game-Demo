import json
import os
from openai import OpenAI

# ⚠️ 1. 在这里填写您的 API Key
API_KEY = ""

# 2. 模拟真实环境的 Prompt
PROMPT = """
You are the Slot Game Engine. 
**Game Rules:**
- Grid: 3x5.
- Symbols & Paytable (5-of-a-kind match): 
  - H1(🐲): 50x, H2(🦁): 20x, M1(🧧): 10x, L1(🅰️): 2x, L2(👑): 1x.
  - Wild(🃏): Substitutes all.
  - Scatter(💎): 3+ triggers free games (visual only).
- Lines: Standard 3 horizontal lines (Row 0, Row 1, Row 2).

**Objective:**
Maintain a long-term RTP of 0.97. 
- If player is losing too much (consecutive_loss > 6), force a win (2x - 5x).
- If RTP > 1.2, force a loss.

**Context:**
Current Bet: 10
Current Balance: 1000
History RTP: 0.95

**Output Format:**
Strict JSON only (No markdown, no comments): 
{
  "matrix": [["H1","L1","L2","M1","H1"], ["L1","L1","L1","L1","L1"], ["H2","H2","H2","L2","L2"]], 
  "winning_lines": [{"line_id":1, "amount": 20}], 
  "total_payout": 20,
  "reasoning": "Player was losing, giving a small win."
}
"""

def clean_json_content(content: str) -> str:
    if not content: return "{}"
    content = content.strip()
    
    # 模拟后端清理逻辑
    if "```" in content:
        import re
        matches = re.findall(r"```(?:json)?(.*?)```", content, re.DOTALL)
        if matches:
            content = max(matches, key=len).strip()
        else:
            content = content.replace("```json", "").replace("```", "").strip()

    start = content.find('{')
    end = content.rfind('}')
    
    if start != -1 and end != -1:
        content = content[start : end + 1]
    elif '"matrix"' in content:
        print(">> 检测到裸数据，尝试补全大括号...")
        content = "{" + content + "}"
            
    return content

def test_deepseek_final():
    print("=========================================")
    print("   DeepSeek 终极诊断脚本 (Final Test)")
    print("=========================================")
    
    if "sk-" not in API_KEY:
        print("❌ 请先修改脚本第 5 行，填入您的 API Key！")
        return

    client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")
    
    print("正在发送请求...")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": "Generate next spin result in JSON."}
            ],
            temperature=0.7
        )
        
        raw_text = response.choices[0].message.content
        print("\n=== 原始返回内容 (RAW RESPONSE) ===")
        print(repr(raw_text))
        print("===================================\n")
        
        cleaned = clean_json_content(raw_text)
        print(f"清理后内容: {repr(cleaned)}")
        
        parsed = json.loads(cleaned)
        print("\n✅ JSON 解析成功！")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"\n❌ 失败: {e}")

if __name__ == "__main__":
    test_deepseek_final()
