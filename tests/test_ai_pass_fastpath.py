"""M3.82 pass-only response, Tian Ting and tenpai evaluation fast-path tests."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mahtrain_core.ai import (
    ABLATION_VARIANTS, AI_LEVELS, MahjongAgent, _call_outlook, visible_tiles,
)
from mahtrain_core.rules import winning_tiles
from test_ai_calls import offer_peng
from test_four_player_claims import deal_for_ron


def _real_claim_views():
    game = deal_for_ron()
    dealer = game.dealer
    game.discard(dealer, "s9")
    winning = game.private_view((dealer + 1) % 4)
    no_call = game.private_view((dealer + 3) % 4)
    assert "hu" in winning["claim_options"]
    assert no_call["claim_options"] == ["pass"], no_call["claim_options"]
    assert game.debug_tile_counts()["total"] == 108
    return game, winning, no_call


class NoCallFastPathTests(unittest.TestCase):
    def test_pass_only_for_every_tier_and_ablation_does_not_analyze_hand(self):
        game, _, view = _real_claim_views()
        snapshot = copy.deepcopy(view)
        for level in (*AI_LEVELS, *ABLATION_VARIANTS):
            with self.subTest(level=level):
                agent = MahjongAgent("challenge" if level in ABLATION_VARIANTS
                                     else level, seed=19, seat=view["seat"])
                if level in ABLATION_VARIANTS:
                    agent.level = level
                rng_before = agent._rng.getstate()
                with patch("mahtrain_core.ai._call_outlook",
                           side_effect=AssertionError("no outlook on forced pass")), \
                     patch("mahtrain_core.ai.shanten_13",
                           side_effect=AssertionError("no shanten on forced pass")):
                    self.assertEqual(agent.response(view), "pass")
                self.assertEqual(agent._rng.getstate(), rng_before)
                self.assertEqual(view, snapshot)
        self.assertEqual(game.debug_tile_counts()["total"], 108)

    def test_legal_winning_claim_is_never_skipped_by_fast_path(self):
        game, view, _ = _real_claim_views()
        for level in AI_LEVELS:
            with self.subTest(level=level):
                agent = MahjongAgent(level, seed=9, seat=view["seat"])
                with patch("mahtrain_core.ai._call_outlook",
                           side_effect=AssertionError("hu must be immediate")):
                    self.assertEqual(agent.response(view), "hu")
        self.assertEqual(game.debug_tile_counts()["total"], 108)

    def test_rob_kong_pass_remains_unconditional_and_no_scoring(self):
        _, _, view = _real_claim_views()
        view["phase"] = "rob_kong_window"
        view["rob_options"] = ["pass"]
        with patch("mahtrain_core.ai._call_outlook",
                   side_effect=AssertionError("rob-only pass must be cheap")):
            self.assertEqual(
                MahjongAgent("challenge", seed=19, seat=view["seat"])
                .response(view, rob=True), "pass")

    def test_verified_tian_ting_with_peng_only_never_calls_outlook(self):
        game, seat, view = offer_peng()
        view["claim_options"] = ["pass", "peng"]
        view["tian_ting"] = {"eligible": True, "initial_waits": ["m5"]}
        original = copy.deepcopy(view)
        with patch("mahtrain_core.ai._call_outlook",
                   side_effect=AssertionError("peng cannot preserve tian")):
            self.assertEqual(
                MahjongAgent("challenge", seed=42, seat=seat)
                .response(view), "pass")
        self.assertEqual(original, view)
        self.assertEqual(game.debug_tile_counts()["total"], 108)

    def test_unverified_tian_and_real_peng_still_run_actual_evaluation(self):
        game, seat, view = offer_peng()
        agent = MahjongAgent("challenge", seed=42, seat=seat)
        with patch("mahtrain_core.ai._call_outlook", wraps=_call_outlook) as call:
            result = agent.response(view)
        self.assertGreater(call.call_count, 0)
        self.assertIn(result, view["claim_options"])
        self.assertEqual(game.debug_tile_counts()["total"], 108)

    def test_no_duplicate_tenpai_wait_enumeration_without_tian(self):
        game, own, _ = _real_claim_views()
        hand = own["hand"]
        missing = own["missing_suits"][own["seat"]]
        visible = visible_tiles(own)
        # The authoritative effective_draws already computes normal waits.
        with patch("mahtrain_core.ai.winning_tiles",
                   side_effect=AssertionError("duplicate winning_tiles")):
            ordinary = _call_outlook(
                hand, own["own_melds"], missing, visible, 3, {})
        self.assertEqual(ordinary["shanten"], 0)
        self.assertFalse(ordinary["tian_kept"])
        self.assertGreater(ordinary["ukeire"], 0)
        self.assertGreaterEqual(ordinary["value"], ordinary["ukeire"])
        # Only when Tian Ting is actually verified must the full wait set be
        # recomputed to check identity against the frozen initial wait set.
        original_waits = winning_tiles(hand, own["own_melds"], missing)
        with patch("mahtrain_core.ai.winning_tiles", wraps=winning_tiles) as waits:
            protected = _call_outlook(
                hand, own["own_melds"], missing, visible, 3,
                {"eligible": True, "initial_waits": original_waits})
        self.assertEqual(waits.call_count, 1)
        self.assertTrue(protected["tian_kept"])
        self.assertGreaterEqual(protected["value"], ordinary["value"])
        self.assertEqual(game.debug_tile_counts()["total"], 108)

    def test_invalid_response_phase_still_raises_without_side_effects(self):
        _, _, view = _real_claim_views()
        view["phase"] = "await_draw"
        with self.assertRaisesRegex(ValueError, "phase mismatch"):
            MahjongAgent("challenge", seed=11, seat=view["seat"]).response(view)
        view["phase"] = "claim_window"
        view["claim_options"] = []
        with self.assertRaisesRegex(ValueError, "eligible claim"):
            MahjongAgent("challenge", seed=11, seat=view["seat"]).response(view)


    def test_two_real_full_games_match_the_pre_shortcut_policy(self):
        from mahtrain_core.ai import _challenge_claim
        from mahtrain_core.ai_tournament import simulate_match

        class PreviousChallenge(MahjongAgent):
            def response(self, view, *, rob=False):
                if (not rob and view["phase"] == "claim_window"
                        and "hu" not in view["claim_options"]
                        and "peng" not in view["claim_options"]
                        and "ming_gang" not in view["claim_options"]):
                    # M3.81 would evaluate a full candidate outlook even
                    # when only pass was legally possible.
                    return _challenge_claim(view)
                return super().response(view, rob=rob)

        lineup = ["challenge", "advanced", "basic", "baseline"]
        for seed in (11, 29):
            with self.subTest(seed=seed):
                previous = simulate_match(
                    seed, lineup=lineup, offline_kong_base=1,
                    offline_agent_overrides={
                        0: PreviousChallenge("challenge", seed=seed, seat=0)
                    },
                )
                current = simulate_match(
                    seed, lineup=lineup, offline_kong_base=1
                )
                for key in (
                    "trace", "public_events", "public_replay", "winners",
                    "official_settled_balances", "partial_win_balances",
                    "official_kong_balances", "official_exhaustive_balances",
                    "terminal_phase", "physical_count",
                ):
                    self.assertEqual(
                        previous[key], current[key],
                        "new pass shortcut may not change match outcome: " + key,
                    )
                self.assertEqual(previous["physical_count"], 108)


if __name__ == "__main__":
    unittest.main()
