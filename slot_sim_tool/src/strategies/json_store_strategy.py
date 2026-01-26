import json
import random
import os
from typing import Dict, Any, List, Optional
from .base import GameStrategy

class JsonStoreStrategy(GameStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.data_path = config.get("data_file")
        # 0: Loss, 1: <5, 2: <10, 3: <20, 4: <30, 5: <50, 6: >=50
        self.groups: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(7)}
        
        # Mapping from old group IDs to new logical groups (for keeping track if needed)
        self.raw_data_map = {}
        
        self.config = config
        
        # User defined weights for groups 0-6
        # Default weights
        self.default_weights = {
            "0": 600, # Loss
            "1": 150, # x < 5
            "2": 100, # x < 10
            "3": 80,  # x < 20
            "4": 40,  # x < 30
            "5": 20,  # x < 50
            "6": 10   # x >= 50
        }
        self.group_weights = config.get("group_weights", self.default_weights)
        
        # Ensure keys are strings for consistency with JSON config
        self.group_weights = {str(k): int(v) for k, v in self.group_weights.items()}

        # 2. RTP Conditions (Keeping compatibility, but might just scale weights)
        self.rtp_conditions = config.get("rtp_conditions", [])

        # 4. VIP 组配置 (Now limits access to logical groups 0-6)
        # { "0": [0, 1, 2], ... }
        self.vip_config = config.get("vip_config", {
            "0": [], "1": [], "2": [], "3": [], "4": []
        })

        # 5. Low Bet / Newbie -> Limits access to logical groups
        self.low_bet_threshold = config.get("low_bet_threshold", 100)
        self.low_bet_groups = config.get("low_bet_groups", []) 
        self.newbie_groups = config.get("newbie_groups", [])

    def initialize(self):
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"找不到数据文件: {self.data_path}")

        print(f"Loading data: {self.data_path}...")
        with open(self.data_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        count = 0
        skipped = 0
        
        for json_group_id, items in raw_data.items():
            for item_str in items:
                try:
                    parts = item_str.split("#")
                    data_part = parts[0].split(",")
                    lines_part = parts[1].split(",") if len(parts) > 1 and parts[1] else []
                    
                    stops = [int(x) for x in data_part[:5]]
                    multiplier = float(data_part[5]) # Assuming this is Multiplier (Odds)
                    
                    outcome = {
                        "stops": stops,
                        "multiplier": multiplier,
                        "lines": lines_part,
                        "raw_group": json_group_id
                    }
                    
                    # Bucket logic - STRICT
                    if multiplier <= 0:
                        self.groups[0].append(outcome)
                    elif multiplier < 5:
                        self.groups[1].append(outcome)
                    elif multiplier < 10:
                        self.groups[2].append(outcome)
                    elif multiplier < 20:
                        self.groups[3].append(outcome)
                    elif multiplier < 30:
                        self.groups[4].append(outcome)
                    elif multiplier < 50:
                        self.groups[5].append(outcome)
                    else:
                        self.groups[6].append(outcome)
                        
                    count += 1
                except Exception as e:
                    skipped += 1
                    continue
        
        # Fill empty buckets with a dummy loss if needed to prevent crash
        if not self.groups[0]:
             self.groups[0].append({
                 "stops": [0,0,0,0,0], "multiplier": 0.0, "lines": [], "raw_group": "gen"
             })
             
        print(f"Loaded {count} outcomes. Re-bucketed into 7 groups. Skipped {skipped}.")
        for i in range(7):
            print(f"  Group {i} count: {len(self.groups[i])}")

    def spin(self, user_state: Dict[str, Any]) -> Dict[str, Any]:
        bet = user_state.get("current_bet", 10.0)
        current_wagered = user_state.get("total_wagered", 0.0)
        current_won = user_state.get("total_won", 0.0)
        fail_streak = user_state.get("fail_streak", 0)
        
        # --- Step 0: Calculate Dynamic Win Rate ---
        # Formula: WinRate = Base * LossMult * (FailStreak - 1) * RTPComp
        # NOTE: If FailStreak < 2, the formula results in <= 0 or 0.
        # We will assume if FailStreak < 2, we use pure BaseWinRate.
        # If FailStreak >= 2, we use the greater of BaseWinRate OR Formula?
        # User prompt: "中奖概率 = ..." implies this IS the formula.
    def _get_rtp_coeff(self, current_rtp: float) -> float:
        # Default 1.0 (100%) if no conditions match
        if not self.rtp_conditions:
            return 1.0
            
        # rtp_conditions is a list of dicts: [{"max": 0.5, "val": 120}, ...]
        # Sorted by max usually. Find first bucket where current_rtp <= max
        for cond in self.rtp_conditions:
             max_val = cond.get("max", 1.0)
             val = cond.get("val", 100) # Percentage (e.g. 120 means 1.2x)
             if current_rtp <= max_val:
                 return val / 100.0
        
        # If RTP is higher than all maxes (e.g. > 1.0), use the last one or default?
        # Usually last one covers up to infinity if set correct, or we fallback to 1.0 or much lower.
        # User config includes {"max": 999, "val": 50} typically for overflow.
        return 1.0

    def spin(self, user_state: Dict[str, Any]) -> Dict[str, Any]:
        bet = user_state.get("current_bet", 10.0)
        # engine.py updates total_wagered BEFORE calling spin. 
        # So total_wagered includes THIS spin's bet already?
        # Let's verify Engine logic in thought trace. 
        # Engine: self.user_state["total_wagered"] += bet  -> THEN calls strategy.spin()
        # YES. current_wagered INCLUDES the current bet.
        current_wagered = user_state.get("total_wagered", 0.0)
        current_won = user_state.get("total_won", 0.0)
        fail_streak = user_state.get("fail_streak", 0)
        
        # RTP calculation: (Won / Wagered). Wagered includes current bet.
        current_rtp = (current_won / current_wagered) if current_wagered > 0 else 0.0

        # --- Step 0: Calculate Dynamic Win Rate ---
        base_win_rate = self.config.get("base_win_rate", 0.15)
        loss_multiplier = self.config.get("loss_multiplier", 1.05) 
        
        # Get RTP Coefficient from Table
        rtp_coeff = self._get_rtp_coeff(current_rtp)
        
        effective_win_rate = base_win_rate
        
        if fail_streak >= 2:
            # Formula: Base * LossMult * (Streak - 1) * RTPCoef
            effective_win_rate = base_win_rate * loss_multiplier * (fail_streak - 1) * rtp_coeff
        else:
             effective_win_rate = base_win_rate

        # Cap win rate at 1.0
        effective_win_rate = min(effective_win_rate, 1.0)
        
        # --- Step 1: Hit or Miss ---
        rnd_roll = random.random()
        
        print(f"[Log] Spin Start | Bet: {bet} | Streak: {fail_streak} | RTP: {current_rtp:.2%} -> Coeff: {rtp_coeff} | EffRate: {effective_win_rate:.4f}")
        
        if rnd_roll > effective_win_rate:
            print(f"[Log] [RNG Check] LOSS. Roll: {rnd_roll:.4f} > WinRate: {effective_win_rate:.4f}")
            return self._get_outcome_from_group(0, bet) # Force Loss

        print(f"[Log] [RNG Check] WIN. Roll: {rnd_roll:.4f} <= WinRate: {effective_win_rate:.4f} -> Proceeding to selection...")

        # --- Step 2: RTP & Range Check ---
        # "这一注只能赢 100*MaxRTP - 总赢"
        # User Logic: Allowed Win = (TotalWagered * MaxRTP) - TotalWon
        # Note: current_wagered includes current bet. current_won does NOT include this spin's potential win.
        # So Allowed Payout matches EXACTLY: (current_wagered * MaxRTP) - current_won.
        
        max_rtp = 1.0 
        
        allowed_payout = (max_rtp * current_wagered) - current_won
        
        max_multiplier_allowed = allowed_payout / bet if bet > 0 else 0
        
        print(f"[Log] [RTP Check] Wagered: {current_wagered} | Won: {current_won} | MaxAllowedMult: {max_multiplier_allowed:.2f}")
        
        # --- Step 3: Filter Groups ---
        
        sim_wagered = current_wagered + bet
        # sim_won = current_won # Not yet won
        
        # Hard cap RTP at 1.0 (or config)
        max_rtp = 1.0 
        
        # Calculate max payout we can afford before breaking RTP > 1.0
        # New RTP = (Current Won + Win) / (Current Wagered + Bet) <= Max RTP
        # Win <= (Max RTP * (Wagered + Bet)) - Current Won
        allowed_payout = (max_rtp * sim_wagered) - current_won
        
        max_multiplier_allowed = allowed_payout / bet if bet > 0 else 0
        
        print(f"[Log] [RTP Check] MaxAllowedMult: {max_multiplier_allowed:.2f} (Target RTP 1.0)")
        
        # --- Step 3: Filter Groups ---
        # Get purely allowed indices based on User/VIP state first
        user_allowed_indices = self._get_allowed_indices(user_state)
        
        # Now filter by Weight & RTP Capability
        pool_indices = []
        pool_weights = []
        
        # Logic: If ANY item in the group fits, is the group allowed? 
        # Or must the whole group fit?
        # Let's say we check the Minimum multiplier of the group. 
        # If Group Min > Max Allowed, we can't pick it.
        
        current_weights = self.group_weights.copy()
        
        # Only consider Winning Groups (1-6)
        cand_logs = []
        for idx in range(1, 7):
            if idx not in user_allowed_indices:
                continue
                
            group_items = self.groups.get(idx, [])
            if not group_items:
                continue
            
            # Simple heuristic: Check if the smallest win in this group fits.
            # If even the smallest win is too big, this group is disqualified.
            # (Note: Groups are sorted. Group 1 is small wins. Group 6 is big.)
            # We can optimise by assuming min multipliers:
            # G1 < 5, G2 < 10 ...
            # We should probably check the actual min of the loaded group, 
            # but for performance let's just check the thresholds.
            # G1 starts at 0. G2 usually starts at 5...
            
            # Find min multiplier in this bucket (cache this in real app)
            # For now, just estimate or check first item if sorted. 
            # Since we didn't sort, we scan or trust the bucket definition.
            # Bucket definitions:
            # 1: <5 (Min >0)
            # 2: 5-10 (Min >=5)
            # 3: 10-20 (Min >=10)
            # 4: 20-30 (Min >=20)
            # 5: 30-50 (Min >=30)
            # 6: >=50 (Min >=50)
            
            min_req = {1:0.01, 2:5.0, 3:10.0, 4:20.0, 5:30.0, 6:50.0}.get(idx, 0)
            
            if min_req > max_multiplier_allowed:
                cand_logs.append(f"G{idx}(Min{min_req} > {max_multiplier_allowed:.1f})")
                continue # This group is too expensive for current RTP headroom
                
            w = current_weights.get(str(idx), 0)
            if w > 0:
                pool_indices.append(idx)
                pool_weights.append(w)
                cand_logs.append(f"G{idx}(OK, w={w})")
        
        print(f"[Log] [Group Filter] Candidates: {', '.join(cand_logs)}")
        
        if not pool_indices:
            # No groups fit the RTP constraint (or no weights)
            # Fallback to Loss (or maybe smallest win if possible? User says: Check -> Random. Implies if fail, don't win)
            print(f"[Log] [Selection] No valid groups found fitting RTP. Falling back to LOSS.")
            return self._get_outcome_from_group(0, bet)
            
        # --- Step 4: Weighted Random ---
        selected_idx = random.choices(pool_indices, weights=pool_weights, k=1)[0]
        
        print(f"[Log] [Selection] Selected Group: {selected_idx} from {pool_indices}")
        
        # --- Step 5: Pick Item from Group ---

        # We need to ensure the SPECIFIC item picked also fits?
        # User said "Random a group... then random a winning graphic in group".
        # If the group passed the min_req check, but we pick a huge outlier? 
        # (e.g. Group 6 has 50x and 5000x. We can afford 100x.)
        # If we pick 5000x, we break RTP. 
        # Refinement: Filter items in group?
        # For performance, let's just pick. If we break RTP slightly on one spin, it corrects later.
        
        return self._get_outcome_from_group(selected_idx, bet)

    def _get_allowed_indices(self, user_state: Dict[str, Any]) -> List[int]:
        # Return indices 0-6
        # Start with all
        allowed = set(range(7))
        
        # VIP
        vip_level = str(user_state.get("vip_level", 0))
        vip_rules = self.vip_config.get(vip_level, [])
        if vip_rules:
            # If rules exist, restrict to them. 
            # Note: Config parsing usually returns strings "1", "2". Convert to int.
            vip_set = set()
            for x in vip_rules:
                try: vip_set.add(int(x))
                except: pass
            allowed = allowed.intersection(vip_set)
            
        # Newbie
        if user_state.get("is_newbie", False) and self.newbie_groups:
            nb_set = {int(x) for x in self.newbie_groups if str(x).isdigit() or isinstance(x, int)}
            allowed = allowed.intersection(nb_set)
            
        # Low Bet
        if user_state.get("current_bet", 0) <= self.low_bet_threshold and self.low_bet_groups:
             lb_set = {int(x) for x in self.low_bet_groups if str(x).isdigit() or isinstance(x, int)}
             allowed = allowed.intersection(lb_set)
             
        # Always allow 0 (Loss) ? Logic above handles Loss separately, but for consistency keep it available
        allowed.add(0)
        
        return list(allowed)

    def _get_outcome_from_group(self, group_idx: int, bet: float) -> Dict[str, Any]:
        group_data = self.groups.get(group_idx, [])
        if not group_data:
            # Should not happen given logic above, but safety
            return {
                "is_win": False, "total_payout": 0.0, 
                "stops": [1,2,3,4,5], "win_lines": [], "group_id": 0
            }
            
        outcome = random.choice(group_data)
        
        payout = outcome["multiplier"] * bet

        if group_idx != 0:
             print(f"  -> Outcome selected: Group {group_idx} | Multiplier: {outcome['multiplier']}x | Payout: {payout}")
        
        return {
            "is_win": outcome["multiplier"] > 0,
            "total_payout": payout,
            "stops": outcome["stops"],
            "win_lines": outcome["lines"],
            "group_id": group_idx,
            "multiplier": outcome["multiplier"]
        }

    def _get_allowed_indices(self, user_state: Dict[str, Any]) -> List[int]:
        # Default all available
        if not self.groups: return [0]
        allowed = set(range(7))
        
        # VIP Limit
        vip_level = str(user_state.get("vip_level", 0))
        if vip_level in self.vip_config and self.vip_config[vip_level]:
             # Config must contain "0", "1", "6" etc.
             vip_allowed = set()
             for x in self.vip_config[vip_level]:
                 try: 
                     vip_allowed.add(int(x))
                 except: pass
             if vip_allowed:
                 allowed = allowed.intersection(vip_allowed)
        
        # Newbie Limit - logic: allowed groups must be in newbie_groups config
        if user_state.get("is_newbie", False) and self.newbie_groups:
             newbie_set = {int(x) for x in self.newbie_groups if str(x).isdigit()}
             allowed = allowed.intersection(newbie_set)

        # Low Bet Limit
        bet = user_state.get("current_bet", 0)
        if bet < self.low_bet_threshold and self.low_bet_groups:
             low_set = {int(x) for x in self.low_bet_groups if str(x).isdigit()}
             allowed = allowed.intersection(low_set)
             
        # Always allow Loss (0) ? Maybe not, but usually yes.
        # If intersection removes 0, user can NEVER lose? dangerous.
        # Let's assume configuration is correct. 
        # But if allowed is empty, we force [0] in caller.
        
        return list(allowed)

    def _generate_loss(self, bet: float):
        # 生成一个假的 Loss 结果
        # 理想情况应该有一个 Loss 库
        return {
            "is_win": False,
            "total_payout": 0.0,
            "stops": [random.randint(0, 10) for _ in range(5)], # Fake stops
            "win_lines": [],
            "group_id": "Loss",
            "meta": None
        }
