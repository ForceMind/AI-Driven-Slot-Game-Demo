import json
import os
import httpx
import time
from typing import List, Dict, Any

# 配置
API_URL = "http://localhost:8000/spin"
LOG_FILE = "api_debug_session.log"

def log_interaction(request_data: Dict[str, Any], response_data: Dict[str, Any], error: str = None):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*50}\n")
        f.write(f"TIMESTAMP: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"--- REQUEST TO BACKEND ---\n")
        f.write(json.dumps(request_data, indent=2, ensure_ascii=False))
        f.write("\n\n--- RESPONSE FROM BACKEND ---\n")
        if error:
            f.write(f"ERROR: {error}\n")
        else:
            f.write(json.dumps(response_data, indent=2, ensure_ascii=False))
        f.write(f"\n{'='*50}\n")

def run_test_spins(count: int = 5):
    print(f"Starting {count} test spins...")
    
    # 模拟前端配置
    config = {
        "provider": "deepseek",
        "api_key": "", # 请在此处填写您的 API Key
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "target_rtp": 0.97,
        "system_prompt_template": "",
        "debug_mode": False
    }

    current_balance = 1000.0
    
    with httpx.Client(timeout=60.0) as client:
        for i in range(count):
            print(f"Spin {i+1}/{count}...", end=" ", flush=True)
            payload = {
                "bet": 10.0,
                "current_balance": current_balance,
                "history_rtp": 0.0, # 后端现在会忽略这个值，自行计算
                "config": config
            }
            
            try:
                resp = client.post(API_URL, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    current_balance += data.get("balance_update", 0)
                    log_interaction(payload, data)
                    print(f"DONE. Payout: {data.get('total_payout')}, New Balance: {current_balance}")
                else:
                    error_text = resp.text
                    log_interaction(payload, {}, error=f"Status {resp.status_code}: {error_text}")
                    print(f"FAILED. Status {resp.status_code}")
            except Exception as e:
                log_interaction(payload, {}, error=str(e))
                print(f"ERROR: {e}")

if __name__ == "__main__":
    # 确保后端正在运行
    print("Note: Make sure the backend server is running on http://localhost:8000")
    run_test_spins(10)
    print(f"\nAll interactions logged to {LOG_FILE}")
