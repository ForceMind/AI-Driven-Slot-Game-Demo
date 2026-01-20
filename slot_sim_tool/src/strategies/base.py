from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List, Optional

class GameStrategy(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def initialize(self):
        """Load data and prepare strategy."""
        pass

    @abstractmethod
    def spin(self, user_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a spin based on user state.
        
        Args:
            user_state: {
                "wallet_balance": float,
                "current_bet": float,
                "total_spins": int,
                "fail_streak": int,
                "is_newbie": bool,
                "level": int,
                "historical_rtp": float
            }
            
        Returns:
            {
                "is_win": bool,
                "total_payout": float,
                "stops": List[int],
                "win_lines": List[int],
                "group_id": str,
                "meta": Any
            }
        """
        pass
