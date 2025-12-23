import json
import os
from llm_client import LLMClient
from models import LLMConfig

# Default prompt from models/config used in the app
TEST_PROMPT = """
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

def test_live_api():
    print("=========================================")
    print("   AI Slot Game - DeepSeek Live Test")
    print("=========================================")
    print("This script will attempt to connect to DeepSeek (or other provider)")
    print("and verify if the response can be parsed correctly.")
    print("=========================================")
    
    api_key = input("Please enter your API Key (e.g., sk-...): ").strip()
    if not api_key:
        print("Error: API Key is required.")
        return

    # Default to DeepSeek config
    config = LLMConfig(
        provider="deepseek",
        api_key=api_key,
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        target_rtp=0.97,
        system_prompt_template=TEST_PROMPT
    )

    print(f"\nSending request to {config.base_url} (Model: {config.model})...")
    print("Waiting for response...")

    try:
        # Use the prompt format logic from the app
        # Note: In the app we format the template. Here we use the raw prompt directly 
        # but LLMClient.generate_spin usually expects to format it.
        # Let's bypass generate_spin and call the internal method directly to isolate the networking/parsing
        # OR use generate_spin but with a template that doesn't need formatting or is pre-formatted.
        
        # Actually, let's use the exact flow.
        # We need a template with placeholders or just use the pre-filled one and trick the formatter?
        
        # Let's manually call the internal _call_openai_direct to be direct.
        result = LLMClient._call_openai_direct(config, TEST_PROMPT)
        
        print("\n✅ SUCCESS! Response parsed successfully:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if "matrix" in result:
            print("\nVerification: 'matrix' field found.")
        else:
            print("\n⚠️ WARNING: JSON parsed but 'matrix' field missing.")

    except Exception as e:
        print("\n❌ FAILED!")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        
        # If it's the specific ValueError we threw
        if "Raw:" in str(e):
             print("\n--- Raw Response content causing error ---")
             # Extract raw from error message if possible, or just look at logs if enabled
             pass

if __name__ == "__main__":
    test_live_api()
