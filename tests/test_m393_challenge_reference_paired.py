"""M3.93 seed-cluster trial: live challenge AI vs reference-only cut ablation."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_challenge_reference_paired import (
    PROTOCOL, ReferenceCutResearchAgent, compare_pair, compare_reference_cuts,
)
from mahtrain_core.classic_hint import classic_archive_seat_hint
from mahtrain_core.four_player import FourPlayerOpening
from test_four_player_claims import staged_game


class ChallengeCutPairedResearchTests(unittest.TestCase):
    def test_offline_reference_agent_uses_same_legally_owned_view(self):
        seed=next(i for i in range(50) if FourPlayerOpening(i).dealer==0)
        hand=["m1","m2","m4","m6","m8",
              "p1","p2","p4","p6","p8",
              "s1","s3","s5","s8"]
        game=staged_game({0:hand},{0:"p"},seed=seed)
        original=game.private_view(0)
        reference=classic_archive_seat_hint(original,0)["candidates"][0]["discard"]
        bot=ReferenceCutResearchAgent(seed=seed,seat=0)
        copy=json.loads(json.dumps(original))
        chosen=bot.discard(copy)
        self.assertEqual(chosen,reference)
        self.assertEqual(copy,original,"research policy must not mutate game view")
        self.assertIn(chosen,original["hand"])
        self.assertEqual(bot.decisions,1)
        self.assertEqual(bot.reference_available,1)
        self.assertEqual(bot.replaced_cuts,bot.baseline_reference_disagreement)
        # A reference-cut control is still an offline-only valid challenge
        # agent for all other choices: opening, claims and kong policy.
        self.assertIsInstance(bot,MahjongAgent)
        self.assertTrue(bot._offline_reference_cut)
        self.assertEqual(bot.level,"challenge")

    def test_paired_rotation_and_zero_sum_are_audited(self):
        observed=[]
        def fake(seed,rotation,*,lineup,offline_kong_base,
                 offline_agent_overrides=None):
            self.assertEqual(seed,8407)
            self.assertEqual(offline_kong_base,1)
            self.assertEqual(sorted(lineup),sorted(
                ["challenge","advanced","basic","baseline"]))
            seat=lineup.index("challenge")
            treated=offline_agent_overrides is not None
            if treated:
                self.assertEqual(set(offline_agent_overrides),{seat})
                self.assertIsInstance(
                    offline_agent_overrides[seat],ReferenceCutResearchAgent)
            observed.append((rotation,seat,treated))
            net=6 if treated else 3
            balances=[-net//3]*4
            balances[seat]=net
            return {
                "assignment":lineup,
                "physical_count":108,
                "official_settled_balances":balances,
                "scoring_rules":{"kong_base":1},
                "terminal_phase":"wall_exhausted",
                "official_exhaustive_posted":True,
                "winners":[],
            }
        with patch("mahtrain_core.ai_challenge_reference_paired.simulate_match",
                   side_effect=fake) as sim:
            summary=compare_reference_cuts(
                seed_start=8407,seeds=1,rotations=4)
        self.assertEqual(sim.call_count,8)
        self.assertEqual(len({row[1] for row in observed}),4)
        self.assertEqual(summary["protocol"],PROTOCOL)
        self.assertEqual(summary["paired_games"],4)
        self.assertEqual(summary["mean_delta_net_reference_minus_challenge"],3)
        self.assertEqual(summary["seed_clusters_positive"],1)
        self.assertEqual(summary["seed_clusters_negative"],0)
        self.assertEqual(summary["per_seed"][0]["rotation_deltas"],[3]*4)
        self.assertNotIn("private",str(summary))
        self.assertNotIn("future_wall",str(summary))

    def test_reject_bad_ranges_and_corrupted_settlements(self):
        for opts in (
            {"seed_start":True},{"seed_start":-1},{"seed_start":2**32-1,"seeds":2},
            {"seeds":0},{"seeds":33},{"seeds":True},
            {"rotations":0},{"rotations":5},{"rotations":True},
        ):
            with self.subTest(opts=opts),self.assertRaises(ValueError):
                compare_reference_cuts(**opts)
        def invalid(seed,rotation,*,lineup,offline_kong_base,
                    offline_agent_overrides=None):
            return {"assignment":lineup,"physical_count":108,
                    "official_settled_balances":[1,0,0,0],
                    "scoring_rules":{"kong_base":1},"terminal_phase":"finished",
                    "official_exhaustive_posted":False,"winners":[]}
        with patch("mahtrain_core.ai_challenge_reference_paired.simulate_match",
                   side_effect=invalid),self.assertRaises(RuntimeError):
            compare_pair(8407,0)

    def test_deterministic_real_finished_games_with_no_hidden_leak(self):
        # One full real seed, two arms. The wider four-seat multi-seed study
        # is intentionally opt-in via the separate offline CLI.
        a=compare_pair(8407,0)
        b=compare_pair(8407,0)
        self.assertEqual(a,b)
        self.assertEqual(a["seed"],8407)
        self.assertIn(a["baseline"]["official_net"],range(-50000,50001))
        self.assertEqual(a["delta_reference_minus_challenge"],
                         a["reference_cut"]["official_net"]-
                         a["baseline"]["official_net"])
        self.assertGreater(a["decision_counts"]["decisions"],0)
        self.assertNotIn("hand",a)
        self.assertNotIn("trace",a)


if __name__=="__main__":
    unittest.main()
