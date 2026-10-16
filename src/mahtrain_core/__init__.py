"""MahTrain: 四川麻将训练与对战所共用的牌型/牌效算法（持续开发中）。"""

from .rules import is_legal_win, score_win, tian_ting_qualifies, winning_tiles
from .efficiency import analyze_discards, effective_draws, shanten_13
from .training import MODES, generate_question, grade_answer

__all__ = [
    "is_legal_win",
    "score_win",
    "tian_ting_qualifies",
    "winning_tiles",
    "shanten_13",
    "effective_draws",
    "analyze_discards",
    "MODES",
    "generate_question",
    "grade_answer",
]
