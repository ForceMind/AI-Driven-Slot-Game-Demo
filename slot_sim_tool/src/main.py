import argparse
import sys
import os
import matplotlib.pyplot as plt
import pandas as pd

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.json_store_strategy import JsonStoreStrategy
from engine import SimulationEngine

def main():
    # Determine default data path based on script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir) # slot_sim_tool root
    default_data_path = os.path.join(project_root, "data", "slot.json")

    parser = argparse.ArgumentParser(description="Slot 游戏数据模拟工具 (By GitHub Copilot)")
    parser.add_argument("--file", type=str, default=default_data_path, help="Slot 数据 JSON 文件路径")
    parser.add_argument("--spins", type=int, default=1000, help="模拟旋转的总次数")
    parser.add_argument("--bet", type=float, default=10.0, help="单次下注金额")
    parser.add_argument("--output", type=str, default="../output", help="图表输出目录")
    
    args = parser.parse_args()
    
    # Setup Strategy
    data_path = os.path.abspath(args.file)
    config = {
        "data_file": data_path,
        "base_win_rate": 0.15, # Adjusted to 15% due to high payouts
        "target_rtp": 0.96
    }
    
    try:
        strategy = JsonStoreStrategy(config)
        engine = SimulationEngine(strategy)
        
        # Override initial bet
        engine.user_state["current_bet"] = args.bet
        
        engine.initialize()
        engine.run_simulation(args.spins)
        
        # Analysis & Plotting
        df = engine.get_history_dataframe()
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
            
        if not os.path.exists(args.output):
            os.makedirs(args.output)
            
        # 1. Balance Curve
        plt.figure(figsize=(10, 6))
        plt.plot(df['spin_id'], df['balance'], label='资金余额')
        plt.axhline(y=engine.user_state['initial_balance'], color='r', linestyle='--', label='初始余额')
        plt.title('资金变化历史 (Balance History)')
        plt.xlabel('旋转次数 (Spins)')
        plt.ylabel('余额 (Balance)')
        plt.legend()
        plt.savefig(os.path.join(args.output, 'balance_curve.png'))
        print(f"已保存资金曲线图到 {args.output}")
        
        # 2. RTP Curve
        plt.figure(figsize=(10, 6))
        plt.plot(df['spin_id'], df['rtp'], color='orange', label='实时 RTP')
        plt.axhline(y=config['target_rtp'], color='g', linestyle='--', label='目标 RTP')
        plt.title('RTP 回归演变 (RTP Evolution)')
        plt.xlabel('旋转次数 (Spins)')
        plt.ylabel('RTP')
        plt.legend()
        plt.savefig(os.path.join(args.output, 'rtp_curve.png'))
        print(f"已保存 RTP 演变图到 {args.output}")
        
        # 3. Win Distribution (Histogram)
        wins = df[df['payout'] > 0]['payout']
        if not wins.empty:
            plt.figure(figsize=(10, 6))
            plt.hist(wins, bins=30, alpha=0.7, color='green')
            plt.title('中奖金额分布 (Win Distribution)')
            plt.xlabel('奖金金额 (Payout)')
            plt.ylabel('频次 (Frequency - Log)')
            plt.yscale('log') # Log scale for better visibility of rare big wins
            plt.savefig(os.path.join(args.output, 'win_dist.png'))
            print(f"已保存中奖分布图到 {args.output}")

    except Exception as e:
        print(f"模拟失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
