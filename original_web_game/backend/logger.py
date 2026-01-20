import csv
import time
import os
from datetime import datetime

class GameLogger:
    def __init__(self, filename="game_data.csv"):
        # Use an absolute path anchored to the backend directory to avoid CWD issues
        base_dir = os.path.dirname(__file__)
        self.filepath = os.path.join(base_dir, filename)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Spin_ID", "Bet", "Payout", "Is_Win", 
                    "Current_RTP", "AI_Provider", "Latency_ms"
                ])

    def log_spin(self, spin_id: str, bet: float, payout: float, 
                 current_rtp: float, provider: str, latency_ms: float):
        is_win = payout > 0
        with open(self.filepath, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                spin_id,
                bet,
                payout,
                is_win,
                current_rtp,
                provider,
                round(latency_ms, 2)
            ])
    def get_history_stats(self):
        """从 CSV 中计算历史总投注、总派彩和 RTP"""
        # 初始虚拟样本，防止前几局 RTP 波动过大导致走极端
        total_bet = 100.0 
        total_payout = 95.0
        try:
            if not os.path.exists(self.filepath):
                return total_bet, total_payout, 0.95
            
            with open(self.filepath, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        total_bet += float(row.get("Bet", 0))
                        total_payout += float(row.get("Payout", 0))
                    except ValueError:
                        continue
            
            rtp = total_payout / total_bet if total_bet > 0 else 0.95
            return total_bet, total_payout, round(rtp, 4)
        except Exception as e:
            print(f"Error reading history: {e}")
            return 100.0, 95.0, 0.95