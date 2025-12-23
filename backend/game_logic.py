import json
import os
from typing import List, Dict, Tuple, Optional, Any
from models import WinningLine

# Load Configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "game_config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    GAME_CONFIG = json.load(f)

SYMBOLS = GAME_CONFIG["symbols"]
MULTIPLIERS = {int(k): v for k, v in GAME_CONFIG["multipliers"].items()}

# Line Definitions (3x5 Grid)
LINES = {
    0: [(0,0), (0,1), (0,2), (0,3), (0,4)], # Top
    1: [(1,0), (1,1), (1,2), (1,3), (1,4)], # Middle
    2: [(2,0), (2,1), (2,2), (2,3), (2,4)], # Bottom
}

class ShadowAccountant:
    @staticmethod
    def _normalize_symbol(s: str) -> str:
        """将输入转换为字符串 ID (如 "1", "10")"""
        if s is None: return "5"
        s = str(s).strip()
        
        # 如果已经是合法的 ID
        if s in SYMBOLS:
            return s
            
        # 处理可能的别名 (兼容旧逻辑)
        name_map = {v["name"]: k for k, v in SYMBOLS.items()}
        if s.upper() in name_map:
            return name_map[s.upper()]
            
        # 默认返回最低价值符号 ID
        return "5"

    @staticmethod
    def calculate_payout(matrix: List[List[Any]], bet: float) -> Tuple[float, List[WinningLine], List[List[str]]]:
        """
        Validates the matrix and calculates the deterministic payout.
        Returns (total_payout, winning_lines, normalized_matrix)
        """
        total_payout = 0.0
        winning_lines = []
        
        # 1. 矩阵标准化
        normalized_matrix = []
        try:
            for r in range(3):
                row = []
                for c in range(5):
                    symbol = matrix[r][c]
                    row.append(ShadowAccountant._normalize_symbol(symbol))
                normalized_matrix.append(row)
        except (IndexError, TypeError):
            return 0.0, [], [["5"]*5]*3
        
        # 2. 计算中奖
        for line_id, coords in LINES.items():
            symbols_on_line = [normalized_matrix[r][c] for r, c in coords]
            match_count, symbol_id = ShadowAccountant._check_line_match(symbols_on_line)
            
            if match_count >= 3 and symbol_id in SYMBOLS:
                base_val = SYMBOLS[symbol_id]["base_value"]
                multiplier = MULTIPLIERS.get(match_count, 0)
                
                line_payout = bet * base_val * multiplier
                
                total_payout += line_payout
                winning_lines.append(WinningLine(
                    line_id=line_id,
                    amount=round(line_payout, 2),
                    symbol=SYMBOLS[symbol_id]["name"] # 返回名称供前端显示
                ))
                
        return round(total_payout, 2), winning_lines, normalized_matrix

    @staticmethod
    def _check_line_match(line: List[str]) -> Tuple[int, str]:
        """
        Returns (count, symbol_id) for the longest left-to-right match.
        ID "10" is WILD.
        """
        if not line:
            return 0, ""
        
        first_symbol = line[0]
        match_symbol_id = first_symbol
        
        # Identify the target symbol for the line
        if first_symbol == "10": # WILD
            match_symbol_id = "10" 
            for s in line:
                if s != "10":
                    match_symbol_id = s
                    break
            if match_symbol_id == "10": 
                match_symbol_id = "1" # All Wilds pay as H1
        
        count = 0
        for s in line:
            if s == match_symbol_id or s == "10":
                count += 1
            else:
                break
        
        return count, match_symbol_id

