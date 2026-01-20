import os
import sys
import glob
from flask import Flask, render_template, request, jsonify, send_from_directory

# Add current directory to sys.path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from strategies.json_store_strategy import JsonStoreStrategy
from engine import SimulationEngine
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

# Set non-interactive backend
matplotlib.use('Agg')

app = Flask(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # slot_sim_tool
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

@app.route('/')
def index():
    # List available JSON files
    files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    filenames = [os.path.basename(f) for f in files]
    return render_template('index.html', games=filenames)

@app.route('/run', methods=['POST'])
def run_simulation():
    try:
        data = request.json
        game_file = data.get('game_file')
        spins = int(data.get('spins', 1000))
        bet = float(data.get('bet', 10.0))
        
        file_path = os.path.join(DATA_DIR, game_file)
        if not os.path.exists(file_path):
            return jsonify({"error": "找不到数据文件"}), 404
            
        # Configure Strategy
        strategy_config = data.get('strategy_config', {})
        
        config = {
            "data_file": file_path,
            "base_win_rate": strategy_config.get("base_win_rate", 0.15),
            "loss_multiplier": strategy_config.get("loss_multiplier", 1.05),
            "rtp_conditions": strategy_config.get("rtp_conditions"), 
            "group_weights": strategy_config.get("group_weights", {}),
            "vip_config": strategy_config.get("vip_config", {}),
            "newbie_groups": strategy_config.get("newbie_groups", []),
            "low_bet_groups": strategy_config.get("low_bet_groups", []),
            "low_bet_threshold": strategy_config.get("low_bet_threshold", 100),
            "target_rtp": 0.96
        }
        
        # New: User / Simulation Config
        user_config = {
            "initial_balance": float(data.get('initial_balance', 10000.0)),
            "bet": bet,
            "vip_level": int(data.get('vip_level', 0))
        }
        num_users = int(data.get('num_users', 1))
        num_users = min(max(1, num_users), 100) # Cap at 100 for safety

        # Initialize Strategy ONCE (loading data is slow)
        strategy = JsonStoreStrategy(config)
        strategy.initialize()

        # Run Simulations Loop
        all_results = []
        
        for i in range(num_users):
            engine = SimulationEngine(strategy, user_config)
            engine.run_simulation(spins)
            
            # Store necessary data for aggression/charts
            # If 1 user, keep full history. If > 1, maybe just stats?
            # Let's keep data for the "first" user for charting, or finding the "median" user?
            # Keeping history for 100 users * 1000 spins is 100k objects. Doable.
            all_results.append({
                 "engine": engine,
                 "final_balance": engine.user_state["wallet_balance"],
                 "rtp": engine.user_state["historical_rtp"]
            })
            
        # Select "Representative" Run for Detailed Charts
        # For simplicity, if num_users > 1, show the one with median Final Balance
        sorted_results = sorted(all_results, key=lambda x: x['final_balance'])
        median_run = sorted_results[len(sorted_results)//2]
        engine = median_run['engine'] # This engine's data will populate the charts
        stats = engine.user_state

        # Aggregate Statistics if multiple users
        agg_stats = {}
        if num_users > 1:
            total_b = sum(r['final_balance'] for r in all_results)
            total_rtp = sum(r['rtp'] for r in all_results)
            agg_stats = {
                "avg_balance": total_b / num_users,
                "avg_rtp": total_rtp / num_users,
                "min_balance": sorted_results[0]['final_balance'],
                "max_balance": sorted_results[-1]['final_balance']
            }

        # Generate Plots
        df = engine.get_history_dataframe()
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)
            
        # Prepare Data for Frontend Charts (No Matplotlib)
        import numpy as np
        
        # 1. Detailed Stats
        detailed_stats = engine.get_detailed_stats()
        # Add Aggregates to details
        if agg_stats:
            detailed_stats.update(agg_stats)
            detailed_stats["sim_count"] = num_users
        
        # 2. Downsample for Line Charts (Max 2000 points)
        chart_df = df
        if len(df) > 2000:
             chart_df = df.iloc[::max(1, len(df)//2000)]
             
        # 3. Distribution Data
        dist_data = {"labels": [], "data": []}
        wins = df[df['payout'] > 0]['payout']
        if not wins.empty:
            # Use fixed number of bins or auto
            counts, bin_edges = np.histogram(wins, bins=20)
            dist_data["data"] = counts.tolist()
            # Format labels nicely
            dist_data["labels"] = [f"{int(bin_edges[i])}-{int(bin_edges[i+1])}" for i in range(len(counts))]
            
        chart_js_data = {
            "labels": chart_df['spin_id'].tolist(),
            "balance": chart_df['balance'].tolist(),
            "rtp": chart_df['rtp'].tolist(),
            "groups": chart_df['group'].tolist() if 'group' in chart_df.columns else [],
            "dist": dist_data
        }

        response = {
            "stats": {
                "total_spins": stats["total_spins"],
                "total_wagered": stats["total_wagered"],
                "total_won": stats["total_won"],
                "rtp": stats["historical_rtp"],
                "final_balance": stats["wallet_balance"],
                "delta": stats["wallet_balance"] - stats["initial_balance"],
                "details": detailed_stats
            },
            "chart_data": chart_js_data
        }
        return jsonify(response)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/output/<filename>')
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)

if __name__ == '__main__':
    print("Starting Web Interface on http://localhost:5000")
    app.run(debug=True, port=5000)
