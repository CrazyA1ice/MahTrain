"""M3.9 baseline independence, legality and four-way seed-rotated metrics."""
from __future__ import annotations

import copy
import inspect
import json
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_baseline import ShapeBaselineAgent
from mahtrain_core.ai_independent_benchmark import (
    independent_lineup, independent_benchmark, LEVELS,
)
from mahtrain_core.ai_tournament import simulate_match
from mahtrain_core.four_player import FourPlayerOpening


def fake_match(seed: int, rotation: int, lineup: list[str]) -> dict:
    wins=[{"seat":lineup.index("challenge"),"source":lineup.index("baseline"),
           "kind":"ron"}] if seed%2==0 else []
    trace=[
        {"action":"discard","seat":i,
         "shanten_regret":int(level=="baseline" and seed%2==1),
         "locally_optimal":level!="baseline"}
        for i,level in enumerate(lineup)
    ]
    return {
        "seed":seed,"rotation":rotation,"dealer":seed%4,
        "assignment":lineup,"terminal_phase":"finished",
        "winners":wins,"trace":trace,
        "public_events":[],"public_replay":[],
        "partial_win_balances":[0,0,0,0],
        "official_settled_balances":[0,0,0,0],
        "official_exhaustive_posted":False,
        "scoring_rules":{"room_coefficient":100,"fan_cap":3,"kong_base":None},
        "physical_count":108,"actions":100,"wall_remaining":0,
    }


class IndependentBaselineTests(unittest.TestCase):
    def test_baseline_isolation_from_efficiency_module(self):
        source=inspect.getsource(sys.modules["mahtrain_core.ai_baseline"])
        self.assertNotIn("from .efficiency",source)
        self.assertNotIn("from .ai import",source)
        self.assertNotIn("shanten_13(",source)
        self.assertNotIn("analyze_discards(",source)
        hand=["m1","m1","m2","m3","m5","s1","s3","s4",
              "s6","s7","s9","p1","p2","p3"]
        view={
            "phase":"dealer_discard","seat":0,"hand":hand,
            "own_melds":[],"missing_suits":["p","m","s","m"],
        }
        a=ShapeBaselineAgent(seed=42,seat=0)
        b=ShapeBaselineAgent(seed=42,seat=0)
        first=a.discard(view);second=b.discard(view)
        self.assertEqual(first,second)
        self.assertIn(first,hand)
        self.assertEqual(first[0],"p")
        # A baseline never reads injected secret data.
        secret=copy.deepcopy(view)
        secret["opponent_hands"]=[["m9"]*13 for _ in range(3)]
        secret["future_wall"]=["p9"]*30
        self.assertEqual(
            ShapeBaselineAgent(seed=42,seat=0).discard(secret),first)

    def test_exchange_missing_claims_and_kong_are_legal_and_simple(self):
        for seed in (11,42):
            game=FourPlayerOpening(seed)
            for seat in range(4):
                agent=ShapeBaselineAgent(seed=seed,seat=seat)
                view=game.private_view(seat)
                triple=agent.exchange(view)
                self.assertEqual(len(triple),3)
                self.assertEqual(len({x[0] for x in triple}),1)
                game.select_exchange(seat,triple)
            for seat in range(4):
                agent=ShapeBaselineAgent(seed=seed,seat=seat)
                view=game.private_view(seat)
                suit=agent.missing(view)
                self.assertIn(suit,("m","s","p"))
                game.select_missing(seat,suit)
            self.assertEqual(game.debug_tile_counts()["total"],108)
        for mode in (False,True):
            a=ShapeBaselineAgent(seed=1,seat=0)
            view={
                "phase":"rob_kong_window" if mode else "claim_window",
                "rob_options":["pass","hu"],"claim_options":["pass","peng","hu"],
            }
            self.assertEqual(a.response(view,rob=mode),"hu")
            view["rob_options"]=["pass"]
            view["claim_options"]=["pass","peng"]
            self.assertEqual(a.response(view,rob=mode),"pass")
        with self.assertRaises(ValueError):
            ShapeBaselineAgent(seed=True,seat=0)
        with self.assertRaises(ValueError):
            ShapeBaselineAgent(seed=1,seat=4)

    def test_four_rotations_balance_every_policy_in_every_seat(self):
        self.assertEqual(len(LEVELS),4)
        for seat in range(4):
            self.assertEqual(
                sorted(independent_lineup(r)[seat] for r in range(4)),
                sorted(LEVELS))
        for bad in (-1,4,True,"2"):
            with self.assertRaises(ValueError):
                independent_lineup(bad)

    def test_cluster_comparison_and_seed_bootstrap(self):
        def stub(seed,rotation=0,*,lineup=None):
            return fake_match(seed,rotation,lineup)
        with patch("mahtrain_core.ai_independent_benchmark.simulate_match",
                   side_effect=stub) as mock:
            result=independent_benchmark(20,5,bootstrap_replicates=200)
            self.assertEqual(mock.call_count,20)
        self.assertEqual(result["games"],20)
        self.assertEqual(result["independent_shuffle_seeds"],5)
        self.assertEqual(result["rotations_per_seed"],4)
        self.assertEqual(result["interval_status"],"exploratory_only")
        self.assertEqual(len(result["per_seed"]),5)
        self.assertEqual(result["levels"]["baseline"]["exposures"],20)
        for level in LEVELS:
            self.assertEqual(result["levels"][level]["exposures"],20)
        self.assertEqual(result["levels"]["baseline"]["wins"],0)
        self.assertGreater(result["levels"]["challenge"]["wins"],0)
        self.assertEqual(result["levels"]["challenge"]["local_optimal_fraction"],1)
        self.assertEqual(result["levels"]["baseline"]["local_optimal_fraction"],0)
        self.assertEqual(result["intervals"]["replications"],200)
        official=result["official_score_analysis"]
        self.assertEqual(official["valid_seeds"],5)
        self.assertEqual(official["excluded_seed_count"],0)
        self.assertEqual(official["complete_games"],20)
        self.assertTrue(official["zero_sum"])
        self.assertEqual(official["room_coefficient"],100)
        self.assertEqual(official["interval_status"],"exploratory_only")
        self.assertIsNotNone(official["intervals"])
        self.assertEqual(official["intervals"]["replications"],200)
        self.assertEqual(official["levels"]["baseline"]["seat_exposures"],20)
        self.assertEqual(
            result["intervals"]["paired_differences_vs_baseline"][
                "challenge"]["local_optimal_fraction"],[1.0,1.0])
        with patch("mahtrain_core.ai_independent_benchmark.simulate_match",
                   side_effect=stub):
            repeated=independent_benchmark(20,5,bootstrap_replicates=200)
        self.assertEqual(result,repeated)
        json.dumps(result,ensure_ascii=False)

    def test_one_seed_no_interval_invalid_inputs_and_compact_logs(self):
        called=[]
        with patch("mahtrain_core.ai_independent_benchmark.simulate_match",
                   side_effect=lambda seed,rotation=0,*,lineup=None:
                   fake_match(seed,rotation,lineup)):
            compact=independent_benchmark(11,1,on_match=lambda a,b:called.append((a,b)))
            self.assertEqual(called,[(1,4),(2,4),(3,4),(4,4)])
            self.assertIsNone(compact["intervals"])
            self.assertIsNone(compact["official_score_analysis"]["intervals"])
            self.assertEqual(compact["official_score_analysis"]["valid_seeds"],1)
            self.assertNotIn("trace",compact["matches"][0])
            self.assertNotIn("public_replay",compact["matches"][0])
            self.assertNotIn("public_events",compact["matches"][0])
        for bad in (0,-1,51,True,1.5):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                independent_benchmark(11,bad)
        for bad in (-1,2**32,"11",True):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                independent_benchmark(bad,1)

    def test_real_full_game_baseline_actions_and_physical_tiles(self):
        match=simulate_match(11,0,lineup=independent_lineup(0))
        self.assertEqual(match["physical_count"],108)
        self.assertEqual(len(match["assignment"]),4)
        self.assertIn(match["terminal_phase"],("finished","wall_exhausted"))
        self.assertEqual(sum(match["partial_win_balances"]),0)
        self.assertEqual(sum(match["official_settled_balances"]),0)
        self.assertEqual(match["scoring_rules"],{
            "room_coefficient":100,"fan_cap":3,"kong_base":None,
        })
        if match["terminal_phase"]=="finished":
            self.assertEqual(match["partial_win_balances"],
                             match["official_settled_balances"])
        self.assertTrue(any(
            frame["action"].get("level")=="baseline" and
            frame["explanation"]["code"] in ("baseline_shape_policy","discard_missing")
            for frame in match["public_replay"]
            if frame["action"]["action"]=="discard"))
        for frame in match["public_replay"]:
            self.assertNotIn("opponent_hands",frame)
            self.assertNotIn("future_wall",frame)


if __name__=="__main__":
    unittest.main()
