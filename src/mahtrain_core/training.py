"""Deterministic, answer-safe (until graded) MahTrain training-question engine.

This module supplies a local/Python API, not a network authentication system.
The host must keep the seed and use it as the authority when grading; do not
trust a modified browser hand or a client-provided correct_answer field.

Four v1 modes: one_shanten, tenpai_discard, pure_suit_waits,
pure_suit_discard. No calls, opponents, score awards or round management.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Any, Sequence

from .efficiency import analyze_discards, shanten_13, effective_draws
from .rules import SUITS, TILES, TILE_INDEX, is_legal_win, winning_tiles
from .presentation import sort_hand, grouped_hand

MODES = (
    "one_shanten", "tenpai_discard", "pure_suit_waits", "pure_suit_discard"
)
RULE_VERSION = "sichuan_blood_battle_v0.4"
MAX_ATTEMPTS = 32


def _check_args(mode: str, seed: int) -> None:
    if mode not in MODES:
        raise ValueError(f"unsupported training mode: {mode!r}")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")


def _pick_unique(rng: random.Random, count: int, exclude: Sequence[int] = ()) -> list[int]:
    ranks = [rank for rank in range(1, 10) if rank not in exclude]
    return rng.sample(ranks, count)


def _ordinary_ready(rng: random.Random) -> tuple[list[str], str]:
    """Four separated triplets + isolated tile; always a real tenpai shape."""
    a, b, missing = rng.sample(SUITS, 3)
    ra, rb = _pick_unique(rng, 2), _pick_unique(rng, 2)
    single = _pick_unique(rng, 1, ra)[0]
    cards = (
        [f"{a}{ra[0]}"] * 3 + [f"{a}{ra[1]}"] * 3
        + [f"{b}{rb[0]}"] * 3 + [f"{b}{rb[1]}"] * 3
        + [f"{a}{single}"]
    )
    return cards, missing


def _ordinary_one_shanten(rng: random.Random) -> tuple[list[str], str]:
    """Three triplets, one pair and two isolated tiles (validated below)."""
    a, b, missing = rng.sample(SUITS, 3)
    ar = _pick_unique(rng, 3)
    br = _pick_unique(rng, 3)
    cards = (
        [f"{a}{ar[0]}"] * 3 + [f"{a}{ar[1]}"] * 3
        + [f"{b}{br[0]}"] * 3 + [f"{b}{br[1]}"] * 2
        + [f"{a}{ar[2]}", f"{b}{br[2]}"]
    )
    return cards, missing


def _pure_ready(rng: random.Random) -> tuple[list[str], str, str]:
    """All 13 tiles are of the same suit with four triplets plus a singleton."""
    suit, missing = rng.sample(SUITS, 2)
    ranks = _pick_unique(rng, 5)
    hand = sum(([f"{suit}{rank}"] * 3 for rank in ranks[:4]), [])
    hand.append(f"{suit}{ranks[4]}")
    return hand, missing, suit


def _minimum_cut_shanten(hand: Sequence[str], missing: str) -> int:
    return min(
        shanten_13(_remove_one(hand, t), missing_suit=missing)
        for t in set(hand)
    )


def _remove_one(hand: Sequence[str], discard: str) -> list[str]:
    remainder = list(hand)
    remainder.remove(discard)
    return remainder


def _draw_candidates(
    rng: random.Random, hand: Sequence[str], allowed_suits: Sequence[str]
) -> list[str]:
    counts = Counter(hand)
    choices = [
        tile for tile in TILES
        if tile[0] in allowed_suits and counts[tile] < 4
    ]
    rng.shuffle(choices)
    return choices


def _make_hand(mode: str, rng: random.Random, force_winning: bool = False) -> tuple[list[str], str]:
    if mode == "pure_suit_waits":
        for _ in range(MAX_ATTEMPTS):
            hand, missing, _ = _pure_ready(rng)
            if winning_tiles(hand, missing_suit=missing):
                return hand, missing
    else:
        for _ in range(MAX_ATTEMPTS):
            if mode == "one_shanten":
                base, missing = _ordinary_one_shanten(rng)
                if shanten_13(base, missing_suit=missing) != 1:
                    continue
            elif mode == "tenpai_discard":
                base, missing = _ordinary_ready(rng)
            else:
                base, missing, suit = _pure_ready(rng)

            if mode == "pure_suit_discard":
                # Include already-won situations so the learner must recognize
                # an immediate legal win, as requested for 清一色何切.
                if force_winning:
                    candidates = winning_tiles(base, missing_suit=missing)
                    if candidates:
                        hand = [*base, rng.choice(candidates)]
                        rng.shuffle(hand)
                        return hand, missing
                allowed_suits = (suit,)
                desired = 0
            else:
                allowed_suits = SUITS
                desired = 1 if mode == "one_shanten" else 0

            for drawn_tile in _draw_candidates(rng, base, allowed_suits):
                hand = [*base, drawn_tile]
                if is_legal_win(hand, missing_suit=missing):
                    continue
                if _minimum_cut_shanten(hand, missing) == desired:
                    rng.shuffle(hand)
                    return hand, missing
    raise RuntimeError("failed to generate a verified problem within the search budget")


def _question_id(mode: str, seed: int, hand: Sequence[str], missing: str) -> str:
    payload = f"{RULE_VERSION}|{mode}|{seed}|{missing}|{','.join(hand)}"
    return hashlib.sha256(payload.encode("ascii")).hexdigest()[:20]


def generate_question(mode: str, seed: int) -> dict[str, Any]:
    """Public question without answer, correct cut, waits or efficiency ranking.

    The caller/server retains seed for grading and replay; it must not return
    the seed to the learner in a real online session.
    """
    _check_args(mode, seed)
    hand, missing = _make_hand(
        mode, random.Random(seed), force_winning=(mode == "pure_suit_discard" and seed % 5 == 0)
    )
    # Uniform 理牌 display: 万/条/筒 grouped, 9→1 within each suit.
    # The hand and choices are display-only copies, not new tile draws.
    hand = sort_hand(hand)
    choices = (
        sort_hand(tile for tile in TILES if tile[0] == hand[0][0])
        if mode == "pure_suit_waits"
        else sort_hand(set(hand))
    )
    if mode == "pure_suit_discard":
        choices = [*choices, "win"]
    return {
        "question_id": _question_id(mode, seed, hand, missing),
        "mode": mode,
        "rule_version": RULE_VERSION,
        "concealed": hand,
        "hand_groups": grouped_hand(hand),
        "missing_suit": missing,
        "choices": choices,
        "answer_type": "tile_set" if mode == "pure_suit_waits" else "single_action",
        "reveals_answer": False,
    }


def _validate_selection(question: dict[str, Any], selection: Any) -> Any:
    if question["answer_type"] == "tile_set":
        if not isinstance(selection, (list, tuple)):
            raise ValueError("waiting tiles answer must be a list/tuple of tiles")
        if any(type(t) is not str for t in selection):
            raise ValueError("waiting tile choices must be tile strings")
        if len(selection) != len(set(selection)):
            raise ValueError("duplicate tile in multi-select answer")
        if not set(selection).issubset(question["choices"]):
            raise ValueError("selected tile is not among the available choices")
        return sorted(selection, key=TILE_INDEX.__getitem__)
    if type(selection) is not str or selection not in question["choices"]:
        raise ValueError("selection is not a permitted question action")
    return selection


def grade_answer(
    mode: str, seed: int, selection: Any, *, question_id: str | None = None
) -> dict[str, Any]:
    """Replay the authoritative seed, then reveal full, justified feedback.

    Invalid input raises ValueError. A legal but suboptimal answer returns
    correct=False, and all genuinely tied optima count as correct.
    """
    question = generate_question(mode, seed)
    if question_id is not None and question_id != question["question_id"]:
        raise ValueError("question_id does not match the authoritative seed")
    chosen = _validate_selection(question, selection)
    hand = question["concealed"]
    missing = question["missing_suit"]

    if mode == "pure_suit_waits":
        correct_tiles = winning_tiles(hand, missing_suit=missing)
        details = effective_draws(hand, missing_suit=missing)
        missed = [t for t in correct_tiles if t not in chosen]
        extras = [t for t in chosen if t not in correct_tiles]
        return {
            "question_id": question["question_id"],
            "correct": chosen == correct_tiles,
            "your_selection": chosen,
            "correct_tiles": correct_tiles,
            "missed_tiles": missed,
            "extra_tiles": extras,
            "effective_draws": details,
            "reason": (
                "必须选全所有合法听牌牌种；按定缺与剩余张数复核。"
                if chosen != correct_tiles
                else "完整识别全部合法听口。"
            ),
        }

    analysis = analyze_discards(hand, missing_suit=missing)
    winning = analysis["status"] == "already_winning"
    best_actions = ["win"] if winning else analysis["best_discards"]
    correct = chosen in best_actions
    chosen_row = next(
        (row for row in analysis["candidates"] if row["discard"] == chosen), None
    )
    if winning:
        reason = (
            "手牌已经满足定缺及胡牌结构，应直接胡牌。"
            if correct else "这是可直接胡牌的局面，普通切牌不是本题最优动作。"
        )
    elif chosen_row is not None and not chosen_row["non_regressing"]:
        reason = "这张切牌增加了本轮可达的最小向听数，违反局部最优切的求稳约束。"
    elif correct:
        reason = "切后向听数处于最优层级，且有效进张枚数最多；并列选项同样正确。"
    else:
        reason = "虽然没有退向听，但有其他切法保留更多有效进张枚数。"
    return {
        "question_id": question["question_id"],
        "correct": correct,
        "your_selection": chosen,
        "best_actions": best_actions,
        "reason": reason,
        "selected_candidate": chosen_row,
        "analysis": analysis,
    }
