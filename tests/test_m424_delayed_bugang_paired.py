"""M4.24 offline no-cash late supplement-kong policy comparison tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tests")]
from mahtrain_core.ai_delayed_bugang_paired import (
    PROTOCOL, ARMS, DEFAULT_GROUPS, DelayedBuGangPairedAgent,
    eligible_delayed_bugang, cohort, paired_position, study,
)
from mahtrain_core.four_player import FourPlayerOpening
from test_m423_bugang_draw_turn_cash import (
    ready_to_draw_fourth, reach_next_turn_holding_fourth,
)


class M424CashlessPairedTests(unittest.TestCase):
    def test_delayed_own_bugang_uses_authorized_draw_only(self):
        g = ready_to_draw_fourth()
        immediate = g.private_view(0)
        self.assertFalse(eligible_delayed_bugang(immediate))
        delayed = reach_next_turn_holding_fourth(g).private_view(0)
        self.assertTrue(eligible_delayed_bugang(delayed))
        self.assertNotIn("hand", g.public_state())
        with self.assertRaises(ValueError):
            eligible_delayed_bugang({**delayed,
                "legacy_bugang_cash_rule": True})

    def test_both_arms_only_change_the_no_cash_guard(self):
        g = reach_next_turn_holding_fourth(ready_to_draw_fourth())
        view = g.private_view(0)
        # The fixture has a second unrelated an-gang: isolate only the
        # legal bu-gang whose guard we are experimentally ablating.
        view["kong_options"] = [{"type": "bu_gang", "tile": "m9"}]
        old = deepcopy(view)
        def outlook(hand, melds, missing, public, cap, tian, **kwargs):
            num = 9 if any(m["type"] == "bu_gang" for m in melds) else 10
            return {"shanten": 1, "ukeire": num,
                    "value": num, "tian_kept": False}
        current = DelayedBuGangPairedAgent(
            seed=42, seat=0, arm="current_guard")
        ablated = DelayedBuGangPairedAgent(
            seed=42, seat=0, arm="old_guard_ablation")
        with patch("mahtrain_core.ai._cut_shanten", return_value=1), \
             patch("mahtrain_core.ai.shanten_13", return_value=1), \
             patch("mahtrain_core.ai._call_outlook", side_effect=outlook):
            self.assertIsNone(current.kong(view))
            self.assertEqual(ablated.kong(view),
                             {"type": "bu_gang", "tile": "m9"})
        self.assertEqual(current.counts["disagreements_on_actual_window"], 1)
        self.assertEqual(ablated.counts["policy_interventions"], 1)
        self.assertEqual(
            ablated.counts["changed_to_delayed_bugang"], 1)
        self.assertEqual(view, old)
        self.assertEqual(g.debug_tile_counts()["total"], 108)

    def test_when_fourth_is_newly_drawn_no_ablation_applies(self):
        g = ready_to_draw_fourth()
        view = g.private_view(0)
        agent = DelayedBuGangPairedAgent(
            seed=42, seat=0, arm="old_guard_ablation")
        result = agent.kong(view)
        self.assertTrue(result is None or result in view["kong_options"])
        self.assertEqual(dict(agent.counts), {})

    def test_reject_legacy_research_mode_inside_new_comparison(self):
        v = ready_to_draw_fourth().private_view(0)
        v["legacy_bugang_cash_rule"] = True
        for arm in ARMS:
            agent = DelayedBuGangPairedAgent(seed=42,seat=0,arm=arm)
            with self.assertRaises(ValueError):
                agent.kong(v)
        with self.assertRaises(ValueError):
            DelayedBuGangPairedAgent(seed=42,seat=0,arm="auto_tuned")

    def test_prespecified_seed_cohorts_do_not_overlap(self):
        self.assertEqual(DEFAULT_GROUPS,
                         {"development": 64000, "holdout": 65000})
        for args in (
            {"development":64000,"holdout":64001,"seeds":2},
            {"development":64000,"holdout":64000,"seeds":2},
            {"development":64000,"holdout":65000,"seeds":0},
            {"development":-1,"holdout":65000,"seeds":2},
            {"development":64000,"holdout":65000,"seeds":5},
        ):
            with self.subTest(args=args),self.assertRaises(ValueError):
                study(**args)
        for rotation in (-1,4,True):
            with self.subTest(rotation=rotation),self.assertRaises(ValueError):
                paired_position(64000,rotation)

    def test_current_ruleset_is_explicit_in_both_full_game_arms(self):
        # Fake only the multi-minute whole-game driver in this *unit*
        # test. An Actions matrix separately runs real full 108-tile games.
        from mahtrain_core.ai_delayed_bugang_paired import _fixed_lineup
        def simulated(seed, **kwargs):
            self.assertEqual(kwargs["offline_ruleset"],"current_m423")
            self.assertEqual(kwargs["offline_kong_base"],1)
            self.assertEqual(len(kwargs["offline_agent_overrides"]),1)
            lineup = kwargs["lineup"]
            seat = lineup.index("challenge")
            self.assertEqual(
                kwargs["offline_agent_overrides"][seat].seat,seat)
            return {"assignment":lineup, "physical_count":108,
                "terminal_phase":"finished",
                "scoring_rules":{"kong_base":1},
                "official_settled_balances":[0,0,0,0],
                "partial_win_balances":[0,0,0,0],
                "official_kong_balances":[0,0,0,0],
                "official_exhaustive_balances":[0,0,0,0],
                "official_exhaustive_posted":False,
                "winners":[],
                "public_events":[]}
        with patch(
            "mahtrain_core.ai_delayed_bugang_paired.simulate_match",
            side_effect=simulated,
        ) as driver:
            row=paired_position(64000,0)
            self.assertEqual(driver.call_count,2)
            self.assertEqual(row["component_deltas"]["official_net"],0)
            self.assertEqual(row["challenge_seat"],
                             _fixed_lineup(0)[1])
            group=cohort(64000,1)
        self.assertEqual(group["independent_shuffle_seeds"],1)
        self.assertEqual(group["paired_positions"],4)
        self.assertEqual(group["complete_games"],8)
        self.assertEqual(group["mean_current_minus_unguarded"]["official_net"],0)
        self.assertEqual(group["confidence_interval_95pct"],None)

    def test_new_current_ruleset_is_not_historical_default(self):
        from mahtrain_core.ai_tournament import simulate_match
        # Reject unexpected rule labels BEFORE a game is constructed.
        with self.assertRaises(ValueError):
            simulate_match(64000, offline_ruleset="unknown")
        g = FourPlayerOpening(42)
        self.assertFalse(g._legacy_bugang_cash)


if __name__ == "__main__":
    unittest.main()
