import json
import os
import random
import time
from typing import List, Dict, Tuple, Any, Optional
from models import WinningLine

class OutcomeEngine:
    def __init__(self):
        self.config = {}
        self.buckets = {}
        self.reels = []
        self.symbols = {}
        self.pay_table = {}
        self.lines = {}
        self.is_ready = False
        self.load_config()

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "game_config_v2.json")
        if not os.path.exists(config_path):
            print(f"Config not found at {config_path}")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.reels = self.config["reel_sets"]
        self.symbols = self.config["symbols"]
        self.pay_table = self.config["pay_table"]
        self.lines = self.config["lines"]
        self.buckets_config = self.config["buckets"]
        self.settings = self.config["settings"]
        
        # Initialize buckets
        for key in self.buckets_config:
            self.buckets[key] = []

        print("Config loaded. Initializing buckets...")
        self.initialize_buckets()

    def initialize_buckets(self):
        # Traverse all reel positions (or sample if too large)
        # Reel length is 16. 16^5 = 1,048,576. Feasible.
        
        reel_len = self.config["reels_length"]
        
        # Optimization: If space is too big, use sampling.
        total_combinations = reel_len ** 5
        use_sampling = total_combinations > 2000000 # Limit to ~2M
        
        start_time = time.time()
        
        if use_sampling:
            print(f"State space {total_combinations} too large, using sampling (100k samples).")
            for _ in range(100000):
                stops = [random.randint(0, reel_len - 1) for _ in range(5)]
                self._process_stop(stops)
        else:
            print(f"Traversing all {total_combinations} combinations...")
            # Recursive or Iterative traversal
            # Using Iterative for 5 reels
            import itertools
            ranges = [range(reel_len) for _ in range(5)]
            for stops in itertools.product(*ranges):
                self._process_stop(list(stops))
                
        print(f"Buckets initialized in {time.time() - start_time:.2f}s")
        for k, v in self.buckets.items():
            print(f"Bucket {k}: {len(v)} outcomes")
            
        self.is_ready = True

    def _process_stop(self, stops: List[int]):
        # 1. Build Matrix
        matrix = self._get_matrix_from_stops(stops)
        
        # 2. Calculate Win
        total_win_multiplier, _, is_near_miss = self._calculate_win(matrix)
        
        # 3. Classify
        bucket_name = self._classify_win(total_win_multiplier, is_near_miss)
        
        if bucket_name:
            # Store only stops to save memory
            # We might want to limit the size of buckets if they get too big (e.g. Loss_Random)
            if len(self.buckets[bucket_name]) < 50000: # Cap at 50k per bucket to save RAM
                self.buckets[bucket_name].append(stops)

    def _get_matrix_from_stops(self, stops: List[int]) -> List[List[str]]:
        matrix = []
        reel_len = self.config["reels_length"]
        for r in range(3): # 3 rows
            row = []
            for c in range(5): # 5 cols
                # Reel strip is circular
                idx = (stops[c] + r) % reel_len
                
                # Safety check for reel index
                if c < len(self.reels) and idx < len(self.reels[c]):
                    symbol_id = self.reels[c][idx]
                else:
                    # Fallback if config is inconsistent
                    symbol_id = "L1" 
                    
                row.append(symbol_id)
            matrix.append(row)
        return matrix

    def _calculate_win(self, matrix: List[List[str]]) -> Tuple[float, List[WinningLine], bool]:
        total_payout = 0.0
        winning_lines = []
        
        # Check Lines
        for line_id_str, coords in self.lines.items():
            line_symbols = [matrix[r][c] for r, c in coords]
            count, symbol_id = self._check_line_match(line_symbols)
            
            if count >= 3:
                # Lookup pay
                if symbol_id in self.pay_table:
                    pay_info = self.pay_table[symbol_id]
                    if str(count) in pay_info:
                        multiplier = pay_info[str(count)]
                        total_payout += multiplier
                        
                        symbol_name = "Unknown"
                        if symbol_id in self.symbols:
                            symbol_name = self.symbols[symbol_id]["name"]
                            
                        winning_lines.append(WinningLine(
                            line_id=int(line_id_str),
                            amount=multiplier,
                            symbol=symbol_name,
                            count=count
                        ))
        
        # Check Near Miss (Simplified: 2 Scatters or 4-in-a-row line miss)
        is_near_miss = False
        # Scatter check
        scatter_count = sum(row.count("SCATTER") for row in matrix)
        if scatter_count == 2:
            is_near_miss = True
            
        return total_payout, winning_lines, is_near_miss

    def _check_line_match(self, line: List[str]) -> Tuple[int, str]:
        if not line: return 0, ""
        
        first = line[0]
        match_id = first
        
        # Handle Wilds (WILD is ID "WILD")
        if first == "WILD":
            # Find first non-wild
            for s in line:
                if s != "WILD":
                    match_id = s
                    break
            # If all wilds, match_id remains WILD
        
        count = 0
        for s in line:
            if s == match_id or s == "WILD":
                count += 1
            else:
                break
                
        return count, match_id

    def _classify_win(self, multiplier: float, is_near_miss: bool) -> str:
        if multiplier == 0:
            if is_near_miss:
                return "Loss_NearMiss"
            return "Loss_Random"
        
        # Check tiers
        for tier, cfg in self.buckets_config.items():
            if tier.startswith("Win_Tier"):
                if cfg["min_win"] <= multiplier < cfg["max_win"]:
                    return tier
                # Handle the last tier (max_win might be inclusive or just high)
                if cfg["max_win"] >= 1000 and multiplier >= cfg["min_win"]:
                     return tier
                     
        return "Win_Tier_1" # Fallback

    def spin(self, user_state: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_ready:
            return {"error": "Engine not ready"}

        bet = user_state.get("current_bet", 10.0)
        balance = user_state.get("wallet_balance", 1000.0)
        max_hist_bal = user_state.get("max_historical_balance", 1000.0)
        
        # 1. Select Bucket
        bucket_name = self._select_bucket(bet, balance, max_hist_bal)
        print(f"[OutcomeEngine] Bet: {bet}, Balance: {balance}. Selected Bucket: {bucket_name}")
        
        # 2. Pick Outcome from Bucket
        if not self.buckets[bucket_name]:
            # Fallback if bucket empty
            print(f"[OutcomeEngine] Bucket {bucket_name} empty! Fallback to Loss_Random")
            bucket_name = "Loss_Random"
            
        stops = random.choice(self.buckets[bucket_name])

        
        # 3. Generate Details
        matrix = self._get_matrix_from_stops(stops)
        multiplier, winning_lines, _ = self._calculate_win(matrix)
        
        total_payout = multiplier * bet
        
        # Update winning lines with actual amounts
        for wl in winning_lines:
            wl.amount = wl.amount * bet
            
        return {
            "matrix": matrix,
            "winning_lines": winning_lines,
            "total_payout": total_payout,
            "is_win": total_payout > 0,
            "bucket_type": bucket_name,
            "balance_update": total_payout - bet
        }

    def _select_bucket(self, bet: float, balance: float, max_hist_bal: float) -> str:
        # Logic:
        # 1. Filter available buckets based on High Roller Threshold
        # 2. Apply RTP Safety Cap
        # 3. Weighted Random Selection
        
        available_buckets = list(self.buckets_config.keys())
        weights = {k: v["weight"] for k, v in self.buckets_config.items()}
        
        # High Roller Check
        high_roller_threshold = self.settings.get("high_roller_threshold", 50.0)
        if bet < high_roller_threshold:
            # Remove high tiers
            weights["Win_Tier_4"] = 0
            weights["Win_Tier_5"] = 0
            
        # RTP Safety Cap
        # If (Balance + Potential Win) > Max * 1.2, forbid high wins
        # Since we don't know the exact win yet, we conservatively block tiers that COULD exceed it.
        # Or simpler: Pick a bucket, check max win of that bucket. If too high, reroll.
        
        # Let's do the "Pick then Validate" approach for Safety Cap
        
        max_allowed_balance = max_hist_bal * self.settings.get("max_historical_balance_buffer", 1.2)
        
        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight == 0: return "Loss_Random"
        
        # Selection Loop (Try up to 3 times)
        for _ in range(3):
            r = random.uniform(0, total_weight)
            current = 0
            selected = "Loss_Random"
            for k, w in weights.items():
                current += w
                if r <= current:
                    selected = k
                    break
            
            # Validate Safety Cap
            max_potential_win = self.buckets_config[selected]["max_win"] * bet
            if balance + max_potential_win > max_allowed_balance:
                # Too risky, try lower tier
                # Temporarily remove this tier and retry
                total_weight -= weights[selected]
                weights[selected] = 0
                if total_weight <= 0: return "Loss_Random"
                continue
            else:
                return selected
                
        return "Loss_Random"

# Singleton instance
engine = OutcomeEngine()
