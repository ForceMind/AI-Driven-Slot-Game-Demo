import time
import math
from typing import Dict, Any, List
from strategies.base import GameStrategy

class SimulationEngine:
    def __init__(self, strategy: GameStrategy, user_config: Dict[str, Any] = None):
        self.strategy = strategy
        
        # Default Config
        defaults = {
            "initial_balance": 10000.0,
            "bet": 10.0,
            "vip_level": 0
        }
        if user_config:
            defaults.update(user_config)
            
        self.user_state = {
            "wallet_balance": float(defaults["initial_balance"]),
            "initial_balance": float(defaults["initial_balance"]),
            "current_bet": float(defaults["bet"]),
            "total_spins": 0,
            "fail_streak": 0,
            "is_newbie": True,
            "level": 1,
            "vip_level": int(defaults["vip_level"]),
            "historical_rtp": 0.0,
            "total_wagered": 0.0,
            "total_won": 0.0
        }
        self.history = []

    def initialize(self):
        self.strategy.initialize()

    def run_simulation(self, iterations: int):
        print(f"正在启动 {iterations} 次旋转的模拟...")
        start_time = time.time()
        
        for i in range(iterations):
            self._spin()
            if (i + 1) % 1000 == 0:
                print(f"当前进度: {i + 1}/{iterations}. 实时 RTP: {self.user_state['historical_rtp']:.2%}")
                
        duration = time.time() - start_time
        print(f"模拟完成，耗时 {duration:.2f} 秒")
        self._print_stats()

    def _spin(self):
        bet = self.user_state["current_bet"]
        self.user_state["wallet_balance"] -= bet
        self.user_state["total_wagered"] += bet
        self.user_state["total_spins"] += 1
        
        # 更新新手状态: 下注小于10000 或者 旋转小于100
        self.user_state["is_newbie"] = (self.user_state["total_spins"] < 100) or (self.user_state["total_wagered"] < 10000)
        
        # 执行策略
        result = self.strategy.spin(self.user_state)
        
        payout = result["total_payout"]
        is_win = result["is_win"]
        
        # 结算
        self.user_state["wallet_balance"] += payout
        self.user_state["total_won"] += payout
        
        if is_win:
            self.user_state["fail_streak"] = 0
            # 升级逻辑简单模拟
            if payout > bet * 10:
                self.user_state["level"] = min(100, self.user_state["level"] + 1)
        else:
            self.user_state["fail_streak"] += 1
            
        # 更新 RTP
        if self.user_state["total_wagered"] > 0:
            self.user_state["historical_rtp"] = self.user_state["total_won"] / self.user_state["total_wagered"]

        # 记录历史 (为了绘图，采样记录)
        # 每 10 次记录一次，或者记录重要事件
        self.history.append({
            "spin_id": self.user_state["total_spins"],
            "balance": self.user_state["wallet_balance"],
            "rtp": self.user_state["historical_rtp"],
            "is_win": is_win,
            "payout": payout,
            "group": result.get("group_id", "")
        })

    def _print_stats(self):
        s = self.user_state
        print("\n=== 模拟统计结果 (Simulation Statistics) ===")
        print(f"总旋转次数 (Total Spins): {s['total_spins']}")
        print(f"总下注额 (Total Wagered): {s['total_wagered']:.2f}")
        print(f"最终奖金额 (Total Won): {s['total_won']:.2f}")
        print(f"最终 RTP: {s['historical_rtp']:.2%}")
        print(f"最终余额 (Final Balance): {s['wallet_balance']:.2f} (盈亏: {s['wallet_balance'] - s['initial_balance']:.2f})")
        print(f"最高等级 (Max Level): {s['level']}")
        
        # 简单的连赢连输统计
        wins = [h for h in self.history if h['is_win']]
        print(f"中奖率 (Win Rate): {len(wins) / len(self.history):.2%}")
        
    def get_detailed_stats(self):
        try:
            import pandas as pd
            import numpy as np
        except ImportError:
            return {}
            
        df = self.get_history_dataframe()
        if isinstance(df, list):
            df = pd.DataFrame(df)
            
        if df.empty:
            return {}
            
        bet = self.user_state["current_bet"]
        
        # 1. Hit Rate
        total_spins = len(df)
        wins = df[df['payout'] > 0]
        win_count = len(wins)
        hit_rate = win_count / total_spins if total_spins > 0 else 0
        
        # 2. Volatility (Std Dev of Returns/Multipliers)
        # Return = (Payout - Bet) / Bet ?? Or just Payout/Bet? 
        # Usually Volatility in slots is StdDev of Payout Multipliers.
        multipliers = df['payout'] / bet
        volatility = multipliers.std()
        
        # 3. Max Drawdown (Money)
        balances = df['balance'].values
        # Fast max drawdown calc
        peak = balances[0]
        max_dd = 0
        for b in balances:
            if b > peak: 
                peak = b
            dd = peak - b
            if dd > max_dd: 
                max_dd = dd
                
        # 4. Win Analysis
        avg_win = wins['payout'].mean() if not wins.empty else 0
        
        big_wins = len(df[df['payout'] >= 50 * bet])
        mega_wins = len(df[df['payout'] >= 100 * bet])
        
        return {
            "hit_rate": hit_rate,
            "volatility": float(volatility) if pd.notnull(volatility) else 0.0,
            "max_drawdown": float(max_dd),
            "avg_win_amt": float(avg_win),
            "avg_win_mult": float(avg_win / bet) if bet > 0 else 0,
            "big_wins": int(big_wins),
            "mega_wins": int(mega_wins),
            "max_win_amt": float(df['payout'].max()),
            "max_win_mult": float(df['payout'].max() / bet) if bet > 0 else 0
        }

    def get_history_dataframe(self):
        try:
            import pandas as pd
            return pd.DataFrame(self.history)
        except ImportError:
            return self.history
