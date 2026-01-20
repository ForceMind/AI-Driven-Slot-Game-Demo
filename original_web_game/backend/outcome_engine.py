import json
import os
import random
import time
import hashlib
import pickle
from typing import List, Dict, Tuple, Any, Optional
from models import WinningLine

class OutcomeEngine:
    def __init__(self, config_override=None):
        self.config = {}
        self.buckets = {}
        self.reels = []
        self.symbols = {}
        self.pay_table = {}
        self.lines = {}
        self.is_ready = False
        
        if config_override:
            self.config = config_override
            self._parse_config()
        else:
            self.load_config()

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "game_config_v2.json")
        if not os.path.exists(config_path):
            # Fallback to v1 if v2 not found
            config_path = os.path.join(os.path.dirname(__file__), "game_config.json")
            
        if not os.path.exists(config_path):
            print(f"Config not found at {config_path}")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        self._parse_config()

    def _get_config_hash(self):
        """
        生成配置的结构化哈希。只有影响桶内容的参数改变时，哈希才会变。
        权重、C值、RTP等不影响桶内容的参数不计入哈希。
        """
        structural_parts = {
            "reel_sets": self.config.get("reel_sets"),
            "symbols": self.config.get("symbols"),
            "pay_table": self.config.get("pay_table"),
            "lines": self.config.get("lines"),
            "reels_length": self.config.get("reels_length"),
            "buckets_ranges": {k: {"min": v.get("min_win"), "max": v.get("max_win")} 
                              for k, v in self.config.get("buckets", {}).items()}
        }
        config_str = json.dumps(structural_parts, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    def _load_from_cache(self) -> bool:
        cache_hash = self._get_config_hash()
        cache_path = os.path.join(os.path.dirname(__file__), f"cache_{cache_hash}.pkl")
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    data = pickle.load(f)
                    self.buckets = data["buckets"]
                    self.bucket_stats = data["bucket_stats"]
                return True
            except Exception as e:
                print(f"Failed to load cache: {e}")
        return False

    def _save_to_cache(self):
        cache_hash = self._get_config_hash()
        cache_path = os.path.join(os.path.dirname(__file__), f"cache_{cache_hash}.pkl")
        try:
            with open(cache_path, "wb") as f:
                pickle.dump({
                    "buckets": self.buckets,
                    "bucket_stats": self.bucket_stats
                }, f)
            print(f"Buckets cached to {cache_path}")
        except Exception as e:
            print(f"Failed to save cache: {e}")

    def _parse_config(self):
        self.reels = self.config["reel_sets"]
        self.symbols = self.config["symbols"]
        self.pay_table = self.config["pay_table"]
        self.lines = self.config["lines"]
        self.buckets_config = self.config["buckets"]
        
        # 规范化奖池配置（兼容 min/max 与 min_win/max_win）
        for key, cfg in self.buckets_config.items():
            if "min" in cfg and "min_win" not in cfg:
                cfg["min_win"] = cfg["min"]
            if "max" in cfg and "max_win" not in cfg:
                cfg["max_win"] = cfg["max"]
            # 默认值
            if "min_win" not in cfg: cfg["min_win"] = 0
            if "max_win" not in cfg: cfg["max_win"] = 0

        self.settings = self.config["settings"]
        
        # 尝试从缓存加载
        if self._load_from_cache():
            print("Buckets loaded from cache.")
            self.is_ready = True
        else:
            # 初始化奖池
            for key in self.buckets_config:
                self.buckets[key] = []

            print("No valid cache found. Initializing buckets (this may take a few seconds)...")
            self.initialize_buckets()
            self._save_to_cache()
        
        # 自动校准 RTP (已禁用：由前端手动计算)
        # self._auto_calibrate_rtp()

    def _auto_calibrate_rtp(self):
        """
        根据 target_rtp 自动计算并覆盖 base_c_value。
        公式: Target_RTP = Hit_Frequency * Avg_Win_Multiplier
        Hit_Frequency (PRD) ≈ base_c_value * Avg_Fail_Streak_Factor (经验值约 6.0)
        => base_c_value = Target_RTP / (Avg_Win_Multiplier * 6.0)
        """
        target_rtp = self.settings.get("target_rtp", 0.97)
        
        # 1. 计算平均中奖倍数 (Avg Win Multiplier)
        total_weight = 0
        weighted_sum = 0
        
        for key, cfg in self.buckets_config.items():
            if key.startswith("Win_Tier"):
                w = cfg["weight"]
                # 取该奖池的平均倍数 (min+max)/2
                avg_mult = (cfg["min_win"] + cfg["max_win"]) / 2
                # 如果 max_win 太大（如 Tier 5），取保守值
                if cfg["max_win"] > 100: avg_mult = cfg["min_win"] * 2
                
                weighted_sum += w * avg_mult
                total_weight += w
                
        if total_weight == 0:
            print("Warning: No winning buckets found!")
            return

        avg_win_multiplier = weighted_sum / total_weight
        
        # 2. 反推需要的中奖频率 (Hit Frequency)
        # Target_RTP = Hit_Freq * Avg_Win_Mult
        required_hit_freq = target_rtp / avg_win_multiplier
        
        # 3. 反推 base_c_value
        # 在 PRD 算法中，平均中奖概率 P ≈ C * (1/C + 1)/2 ... 比较复杂
        # 经验公式：对于 C=0.05~0.2，平均连输次数 N ≈ 1/P - 1
        # 简单近似：Hit_Freq ≈ C * 4.5 (经验值，取决于 C 的大小)
        # 更准确的模拟反推：
        # C=0.15 -> HitFreq ≈ 25%
        # C=0.05 -> HitFreq ≈ 12%
        # 线性插值系数 k ≈ 1.6
        
        # 让我们用一个更稳健的公式：base_c = required_hit_freq / 1.8
        # 这个 1.8 是基于 PRD 模拟的经验系数
        
        calculated_c = required_hit_freq / 1.8
        
        # 限制范围
        calculated_c = max(0.01, min(0.3, calculated_c))
        
        print(f"[Auto-Calibrate] Target RTP: {target_rtp}")
        print(f"[Auto-Calibrate] Avg Win Mult: {avg_win_multiplier:.2f}")
        print(f"[Auto-Calibrate] Required Hit Freq: {required_hit_freq:.2%}")
        print(f"[Auto-Calibrate] Calculated Base C: {calculated_c:.4f} (Old: {self.settings.get('base_c_value')})")
        
        # 覆盖配置
        self.settings["base_c_value"] = calculated_c

    def initialize_buckets(self):
        # 遍历所有卷轴位置（如果空间太大则采样）
        # 卷轴长度为16，16^5=1,048,576，完全可行。
        
        reel_len = self.config["reels_length"]
        
        # 优化：如果空间过大则采样
        total_combinations = reel_len ** 5
        use_sampling = total_combinations > 2000000 # 限制在约200万
        
        start_time = time.time()
        
        if use_sampling:
            print(f"State space {total_combinations} too large, using sampling (100k samples).")
            for _ in range(100000):
                stops = [random.randint(0, reel_len - 1) for _ in range(5)]
                self._process_stop(stops)
        else:
            print(f"Traversing all {total_combinations} combinations...")
            # 递归或迭代遍历，5卷轴用迭代
            import itertools
            ranges = [range(reel_len) for _ in range(5)]
            for stops in itertools.product(*ranges):
                self._process_stop(list(stops))
                
        print(f"Buckets initialized in {time.time() - start_time:.2f}s")
        for k, v in self.buckets.items():
            print(f"Bucket {k}: {len(v)} outcomes")
            
        # 计算并存储每个 Bucket 的真实平均倍数
        self.bucket_stats = {}
        for k, stops_list in self.buckets.items():
            if not stops_list:
                self.bucket_stats[k] = 0.0
                continue
                
            # 为了性能，如果数据量太大，只采样前 1000 个计算平均值
            sample_size = min(len(stops_list), 1000)
            total_mult = 0.0
            
            # 随机采样以获得更准确的估算
            samples = random.sample(stops_list, sample_size)
            
            for stops in samples:
                matrix = self._get_matrix_from_stops(stops)
                mult, _, _ = self._calculate_win(matrix)
                total_mult += mult
                
            self.bucket_stats[k] = total_mult / sample_size
            # print(f"Bucket {k} Real Avg Multiplier: {self.bucket_stats[k]:.2f}x")

        self.is_ready = True

    def _process_stop(self, stops: List[int]):
        # 1. 构建矩阵
        matrix = self._get_matrix_from_stops(stops)
        
        # 2. 计算中奖
        total_win_multiplier, _, is_near_miss = self._calculate_win(matrix)
        
        # 3. 分类
        bucket_name = self._classify_win(total_win_multiplier, is_near_miss)
        
        if bucket_name:
            # 只存 stops 节省内存
            # 如果奖池过大（如 Loss_Random），可限制其大小
            if len(self.buckets[bucket_name]) < 50000: # 每个奖池最多5万条，节省内存
                self.buckets[bucket_name].append(stops)

    def _get_matrix_from_stops(self, stops: List[int]) -> List[List[str]]:
        matrix = []
        reel_len = self.config["reels_length"]
        for r in range(3): # 3行
            row = []
            for c in range(5): # 5列
                # 卷轴带为环形
                idx = (stops[c] + r) % reel_len
                
                # 卷轴索引安全检查
                if c < len(self.reels) and idx < len(self.reels[c]):
                    symbol_id = self.reels[c][idx]
                else:
                    # 配置不一致时兜底
                    symbol_id = "L1" 
                    
                row.append(symbol_id)
            matrix.append(row)
        return matrix

    def _calculate_win(self, matrix: List[List[str]]) -> Tuple[float, List[WinningLine], bool]:
        total_payout = 0.0
        winning_lines = []
        
        # 检查所有中奖线
        for line_id_str, coords in self.lines.items():
            line_symbols = [matrix[r][c] for r, c in coords]
            count, symbol_id = self._check_line_match(line_symbols)
            
            if count >= 3:
                # 查表获取赔率
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
        
        # 检查 Near Miss（简化：2个Scatter或4连线未中奖）
        is_near_miss = False
        # Scatter 检查
        scatter_count = sum(row.count("SCATTER") for row in matrix)
        if scatter_count == 2:
            is_near_miss = True
            
        return total_payout, winning_lines, is_near_miss

    def _check_line_match(self, line: List[str]) -> Tuple[int, str]:
        if not line: return 0, ""
        
        first = line[0]
        match_id = first
        
        # 处理百搭（WILD）
        if first == "WILD":
            # 找到第一个非百搭符号
            for s in line:
                if s != "WILD":
                    match_id = s
                    break
            # 如果全是百搭，match_id 仍为 WILD
        
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
        
        # 检查各层级
        for tier, cfg in self.buckets_config.items():
            if tier.startswith("Win_Tier"):
                if cfg["min_win"] <= multiplier < cfg["max_win"]:
                    return tier
                # 处理最后一层（max_win 可能为无穷大）
                if cfg["max_win"] >= 1000 and multiplier >= cfg["min_win"]:
                     return tier
                     
        return "Win_Tier_1" # 兜底

    def spin(self, user_state: Dict[str, Any], runtime_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_ready:
            return {"error": "Engine not ready"}

        bet = user_state.get("current_bet", 10.0)
        balance = user_state.get("wallet_balance", 1000.0)
        initial_balance = user_state.get("initial_balance", 1000.0)
        total_spins = user_state.get("total_spins", 0)
        fail_streak = user_state.get("fail_streak", 0)
        max_historical_balance = user_state.get("max_historical_balance", balance)
        historical_rtp = user_state.get("historical_rtp", 0.0) # 获取用户历史 RTP
        ignore_safety = user_state.get("simulation_mode", False)
        
        # 1. 选择奖池
        bucket_name = self._select_bucket(
            bet, balance, initial_balance, 
            total_spins, fail_streak, 
            ignore_safety=ignore_safety,
            max_historical_balance=max_historical_balance,
            historical_rtp=historical_rtp, # 传入 RTP
            runtime_config=runtime_config
        )
        if not ignore_safety:
            print(f"[OutcomeEngine] Bet: {bet}, Balance: {balance}, Spins: {total_spins}, FailStreak: {fail_streak}. Selected Bucket: {bucket_name}")
        
        # 2. 从奖池中抽取结果
        if not self.buckets[bucket_name]:
            # 如果奖池为空，兜底到 Loss_Random
            print(f"[OutcomeEngine] Bucket {bucket_name} empty! Fallback to Loss_Random")
            bucket_name = "Loss_Random"
            
        stops = random.choice(self.buckets[bucket_name])

        
        # 3. 生成详细结果
        matrix = self._get_matrix_from_stops(stops)
        multiplier, winning_lines, _ = self._calculate_win(matrix)
        
        total_payout = multiplier * bet
        
        # 更新中奖线实际金额
        for wl in winning_lines:
            wl.amount = wl.amount * bet
            
        # 更新连败计数
        new_fail_streak = 0 if total_payout > 0 else fail_streak + 1
            
        return {
            "matrix": matrix,
            "winning_lines": winning_lines,
            "total_payout": total_payout,
            "is_win": total_payout > 0,
            "bucket_type": bucket_name,
            "balance_update": total_payout - bet,
            "fail_streak": new_fail_streak
        }

    def _select_bucket(self, bet: float, balance: float, initial_balance: float, total_spins: int = 0, fail_streak: int = 0, ignore_safety: bool = False, max_historical_balance: float = 0, historical_rtp: float = 0.0, runtime_config: Optional[Dict[str, Any]] = None) -> str:
        
        # Determine settings and buckets_config to use
        settings = self.settings
        buckets_config = self.buckets_config
        
        if runtime_config:
            settings = runtime_config.get("settings", self.settings)
            raw_buckets = runtime_config.get("buckets", self.buckets_config)
            # 简单的运行时规范化 (确保有 min_win/max_win)
            buckets_config = {}
            for k, v in raw_buckets.items():
                cfg = v.copy()
                if "min" in cfg and "min_win" not in cfg: cfg["min_win"] = cfg["min"]
                if "max" in cfg and "max_win" not in cfg: cfg["max_win"] = cfg["max"]
                if "min_win" not in cfg: cfg["min_win"] = 0
                if "max_win" not in cfg: cfg["max_win"] = 0
                buckets_config[k] = cfg

        # 1. PRD逻辑：决定本次是否中奖
        base_c = settings.get("base_c_value", 0.05)
        
        # 动态 RTP 调控 (RTP Control)
        target_rtp = settings.get("target_rtp", 0.97)
        
        # 如果用户玩了足够多把 (比如 > 50)，且 RTP 严重偏离，进行分级修正
        if total_spins > 50:
            rtp_ratio = historical_rtp / target_rtp if target_rtp > 0 else 1.0
            
            if rtp_ratio < 0.5:   # 极度亏损 (RTP < 50% Target)
                base_c *= 2.5     # 强力提升中奖率
            elif rtp_ratio < 0.7: # 明显亏损 (RTP < 70% Target)
                base_c *= 1.8     # 提升中奖率
            elif rtp_ratio < 0.8: # 中度亏损 (RTP < 80% Target)
                base_c *= 1.2     # 提升中奖率
            elif rtp_ratio < 0.95: # 轻微亏损
                base_c *= 1.1     # 微调
            elif rtp_ratio > 2.0: # 极度盈利 (RTP > 200% Target)
                base_c *= 0.3     # 强力降低中奖率
            elif rtp_ratio > 1.5: # 明显盈利 (RTP > 150% Target)
                base_c *= 0.5     # 降低中奖率
            elif rtp_ratio > 1.05: # 轻微盈利
                base_c *= 0.6     # 微调

        win_prob = base_c * (fail_streak + 1)
        
        # 安全：中奖概率最大为1.0
        if win_prob > 1.0: win_prob = 1.0
        
        is_prd_win = random.random() < win_prob
        
        # 2. 过滤可用奖池
        weights = {k: v["weight"] for k, v in buckets_config.items()}
        
        # PRD判定为未中奖，只允许Loss奖池
        if not is_prd_win:
            for k in list(weights.keys()):
                if k.startswith("Win_Tier"):
                    weights[k] = 0
        else:
            # PRD判定为中奖，只允许Win奖池
            for k in list(weights.keys()):
                if k.startswith("Loss_"):
                    weights[k] = 0
        
        # 3. 进度分层检查
        progress_tiers = settings.get("progress_tiers", [])
        if progress_tiers:
            current_tier = None
            # 找到满足当前旋转数的最高层
            for tier in sorted(progress_tiers, key=lambda x: x["min_spins"]):
                if total_spins >= tier["min_spins"]:
                    current_tier = tier
                else:
                    break
            
            if current_tier:
                allowed = current_tier.get("allowed_buckets", ["ALL"])
                if "ALL" not in allowed:
                    for k in list(weights.keys()):
                        if k not in allowed:
                            weights[k] = 0

        # 4. 高额投注检查
        high_roller_threshold = settings.get("high_roller_threshold", 50.0)
        if bet < high_roller_threshold:
            # 移除高层奖池
            if "Win_Tier_4" in weights: weights["Win_Tier_4"] = 0
            if "Win_Tier_5" in weights: weights["Win_Tier_5"] = 0
            
        # 5. RTP安全上限（天花板）
        # 逻辑：严格按照初始余额限制最大余额。
        # 模拟和真实旋转完全共用此逻辑。
        
        max_win_ratio = settings.get("max_win_ratio", 1.2)
        max_allowed_balance = initial_balance * max_win_ratio
        
        # 归一化权重
        total_weight = sum(weights.values())
        
        # 兜底：PRD判定为中奖但所有Win奖池被过滤，强制转Loss
        if total_weight == 0:
            if is_prd_win:
                weights = {k: v["weight"] for k, v in buckets_config.items() if k.startswith("Loss_")}
                total_weight = sum(weights.values())
                if total_weight == 0: return "Loss_Random"
            else:
                return "Loss_Random"
        
        # 6. 选择循环（最多尝试3次）
        for _ in range(3):
            r = random.uniform(0, total_weight)
            current = 0
            selected = "Loss_Random"
            for k, w in weights.items():
                current += w
                if r <= current:
                    selected = k
                    break
            
            # 校验安全上限——现在无论模拟还是真实都强制执行
            max_potential_win = buckets_config[selected]["max_win"] * bet
            if balance + max_potential_win > max_allowed_balance:
                # 超出风险，尝试更低层
                total_weight -= weights[selected]
                weights[selected] = 0
                if total_weight <= 0: 
                    return "Loss_Random"
                continue
            
            return selected
                
        return "Loss_Random"

# 单例实例
engine = OutcomeEngine()
