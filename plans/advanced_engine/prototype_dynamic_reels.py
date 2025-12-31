import random
import time
from typing import List, Dict, Any, Optional

# --- 1. 配置模型 (支持动态卷轴) ---

class DynamicReelConfig:
    def __init__(self):
        # 模拟卷轴带：每个符号用 ID 表示
        # 假设有 6 个卷轴 (支持 6 列)
        # 符号: 0=Low, 1=Mid, 2=High, 9=Wild, 10=Scatter
        # 为了演示 Loss，我们需要让某些符号在某些卷轴上完全不出现，或者很难连起来
        # 这里我们故意把 Reel 3 弄得很难匹配
        self.reel_strips = [
            [0, 1, 0, 2, 0, 1, 0, 0, 0, 1, 0, 2, 0, 10, 0, 1] * 5, # Reel 1
            [0, 1, 0, 2, 0, 1, 0, 0, 0, 1, 0, 2, 0, 10, 0, 1] * 5, # Reel 2
            [3, 4, 3, 5, 3, 4, 3, 5, 3, 4, 3, 5, 3, 10, 3, 4] * 5, # Reel 3 (全是 3,4,5，很难跟 0,1,2 连上)
            [0, 1, 0, 2, 0, 1, 0, 9, 0, 1, 0, 2, 0, 10, 0, 1] * 5, # Reel 4
            [0, 1, 0, 2, 0, 1, 0, 9, 0, 1, 0, 2, 0, 10, 0, 1] * 5, # Reel 5
            [0, 1, 0, 2, 0, 1, 0, 9, 0, 1, 0, 2, 0, 10, 0, 1] * 5, # Reel 6
        ]
        
        # 赔率表 (Symbol ID -> {Count -> Multiplier})
        self.paytable = {
            9: {3: 5.0, 4: 10.0, 5: 50.0, 6: 200.0}, # Wild
            2: {3: 2.0, 4: 5.0,  5: 20.0, 6: 100.0}, # High
            1: {3: 0.5, 4: 1.5,  5: 5.0,  6: 20.0},  # Mid
            0: {3: 0.1, 4: 0.5,  5: 1.0,  6: 5.0},   # Low
        }
        
        # 布局配置
        self.min_rows = 2
        self.max_rows = 7
        self.cols = 6

# --- 2. 核心逻辑：Ways 算奖 ---

class WaysEvaluator:
    def __init__(self, config: DynamicReelConfig):
        self.config = config

    def evaluate(self, view: List[List[int]]) -> Dict[str, Any]:
        """
        计算 Ways 中奖
        view: 二维数组，view[col][row] = symbol_id
        """
        total_win = 0.0
        winning_details = []
        
        # 1. 统计每列符号数量
        # col_counts[col_idx][symbol_id] = count
        col_counts = []
        for col in view:
            counts = {}
            for sym in col:
                # 处理 Wild: Wild 可以被视为任何符号
                # 在 Ways 逻辑中，通常先统计物理符号，Wild 单独处理或在遍历时处理
                # 这里简化：假设 Wild 替代所有符号
                counts[sym] = counts.get(sym, 0) + 1
            col_counts.append(counts)
            
        # 2. 遍历所有可能的付费符号
        checked_symbols = set(self.config.paytable.keys())
        
        for target_sym in checked_symbols:
            if target_sym == 9: continue # Wild 单独算或作为百搭
            
            # 检查连击
            consecutive_cols = 0
            ways_product = 1
            
            for c_idx in range(len(col_counts)):
                count = col_counts[c_idx].get(target_sym, 0)
                wild_count = col_counts[c_idx].get(9, 0) # Wild ID = 9
                
                effective_count = count + wild_count
                
                if effective_count > 0:
                    consecutive_cols += 1
                    ways_product *= effective_count
                else:
                    break # 断连
            
            # 查表算奖
            if consecutive_cols >= 3:
                payouts = self.config.paytable.get(target_sym, {})
                if consecutive_cols in payouts:
                    mult = payouts[consecutive_cols]
                    win_amount = mult * ways_product # Ways 核心公式：赔率 * 路数
                    total_win += win_amount
                    winning_details.append({
                        "symbol": target_sym,
                        "count": consecutive_cols,
                        "ways": ways_product,
                        "win": win_amount
                    })
                    
        return {
            "total_win": total_win,
            "details": winning_details,
            "is_win": total_win > 0
        }

# --- 3. 混合生成引擎 ---

class HybridEngine:
    def __init__(self):
        self.config = DynamicReelConfig()
        self.evaluator = WaysEvaluator(self.config)
        
    def generate_layout(self) -> List[int]:
        """随机生成每列的高度 (Megaways 风格)"""
        return [random.randint(self.config.min_rows, self.config.max_rows) for _ in range(self.config.cols)]
        
    def get_view_from_stops(self, stops: List[int], layout: List[int]) -> List[List[int]]:
        """根据停止位置和布局截取符号"""
        view = []
        for col_idx, stop in enumerate(stops):
            reel = self.config.reel_strips[col_idx]
            height = layout[col_idx]
            col_symbols = []
            for r in range(height):
                sym = reel[(stop + r) % len(reel)]
                col_symbols.append(sym)
            view.append(col_symbols)
        return view

    def spin_rejection_sampling(self, target_type: str, max_attempts=100):
        """
        策略 A: 拒绝采样 (Rejection Sampling)
        适用于：Loss, Small Win
        """
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            
            # 1. 随机布局
            layout = self.generate_layout()
            
            # 2. 随机停止位置
            stops = [random.randint(0, len(self.config.reel_strips[i])-1) for i in range(self.config.cols)]
            
            # 3. 构建画面
            view = self.get_view_from_stops(stops, layout)
            
            # 4. 算奖
            result = self.evaluator.evaluate(view)
            win = result["total_win"]
            
            # 5. 判定是否符合目标
            match = False
            if target_type == "LOSS" and win == 0:
                match = True
            elif target_type == "WIN_SMALL" and 0 < win < 10.0:
                match = True
            elif target_type == "WIN_BIG" and win > 50.0:
                match = True
                
            if match:
                return {
                    "type": "Generated (Rejection)",
                    "attempts": attempts,
                    "layout": layout,
                    "stops": stops,
                    "result": result
                }
                
        return {"error": "Failed to generate target within attempts"}

    def spin_constructive(self, target_symbol=9, count=6):
        """
        策略 B: 构造法 (Constructive / Pattern Injection)
        适用于：Jackpot, Ultra Big Win
        直接找到能产生特定结果的停止位置
        """
        # 简单演示：暴力搜索包含特定符号的停止位置
        # 实际生产中，这些位置是预先计算好存入数据库的 (Golden Seeds)
        
        layout = [4, 4, 4, 4, 4, 4] # 固定一个较好的布局
        forced_stops = []
        
        for col_idx in range(self.config.cols):
            reel = self.config.reel_strips[col_idx]
            found = False
            # 在该卷轴上寻找目标符号
            for i in range(len(reel)):
                # 检查窗口内是否会出现目标符号
                window = [reel[(i+r)%len(reel)] for r in range(layout[col_idx])]
                if target_symbol in window:
                    forced_stops.append(i)
                    found = True
                    break
            if not found:
                forced_stops.append(random.randint(0, len(reel)-1))
                
        view = self.get_view_from_stops(forced_stops, layout)
        result = self.evaluator.evaluate(view)
        
        return {
            "type": "Constructed (Pattern Injection)",
            "layout": layout,
            "stops": forced_stops,
            "result": result
        }

# --- 4. 测试运行 ---

if __name__ == "__main__":
    engine = HybridEngine()
    
    print("--- Test 1: Rejection Sampling (Loss) ---")
    # 这种非常快，通常 1 次就能随到
    res = engine.spin_rejection_sampling("LOSS")
    print(res)
    print("\n")
    
    print("--- Test 2: Rejection Sampling (Small Win) ---")
    # 这种可能需要几次尝试
    res = engine.spin_rejection_sampling("WIN_SMALL")
    print(res)
    print("\n")
    
    print("--- Test 3: Constructive (Force 6 Wilds) ---")
    # 这种直接构造，无需随机
    res = engine.spin_constructive(target_symbol=9, count=6)
    print(res)
