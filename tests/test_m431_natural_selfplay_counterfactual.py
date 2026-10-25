"""M4.31 physically lawful 4-challenge natural self-play and paired action labels."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_selfplay_learning import _assert_public
from mahtrain_core.ai_selfplay_counterfactual import (
    PROTOCOL, WALL_WORLDS,FEATURE_NAMES, _ledger,_wall_variant,
    _force_and_finish,natural_selfplay,paired_natural_seed,
    _train_from_rows,_holdout_analysis,run_experiment,
)


class NaturalFourChallengeCounterfactualTests(unittest.TestCase):
    def test_natural_four_challenge_public_replay_and_private_checkpoint(self):
        public,private,checkpoint=natural_selfplay(89500)
        self.assertEqual(public["protocol"],PROTOCOL)
        self.assertEqual(public["policies"],["challenge"]*4)
        self.assertIn(public["phase"],("finished","wall_exhausted"))
        self.assertEqual(len(public["official_final_balances"]),4)
        self.assertEqual(sum(public["official_final_balances"]),0)
        self.assertGreater(len(public["public_frames"]),20)
        self.assertEqual(public["game_id"],"unassigned-public-id")
        self.assertTrue(private["actor_observation_only"])
        self.assertEqual(private["private_seed"],89500)
        _assert_public(public)
        self.assertNotIn("private_seed",str(public))
        if checkpoint is not None:
            game,selection=checkpoint
            seat=selection["seat"]
            view=game.private_view(seat)
            self.assertIn(selection["baseline"],view["hand"])
            self.assertIn(selection["alternative"],view["hand"])
            self.assertNotEqual(selection["baseline"],selection["alternative"])
            self.assertEqual(game.debug_tile_counts()["total"],108)
            self.assertEqual(len(selection["features"]),2)
            self.assertTrue(all(len(x)==len(FEATURE_NAMES)
                                for x in selection["features"].values()))
            self.assertNotIn("_wall",selection)
            self.assertNotIn("_hands",selection)

    def test_genuine_wall_counterfactual_keeps_same_authorized_view(self):
        public,private,checkpoint=natural_selfplay(89501)
        if checkpoint is None:
            self.skipTest("natural seed never produced two equal-shanten cuts")
        original,choice=checkpoint
        before=deepcopy(original.private_view(choice["seat"]))
        expected=deepcopy(original.public_state())
        for world in WALL_WORLDS:
            with self.subTest(world=world):
                shifted=_wall_variant(original,89501,world,choice)
                self.assertEqual(shifted.private_view(choice["seat"]),before)
                self.assertEqual(shifted.public_state(),expected)
                self.assertEqual(shifted.debug_tile_counts()["total"],108)
        self.assertEqual(original.private_view(choice["seat"]),before)
        for bad in (-1,2,True,"1"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                _wall_variant(original,89501,bad,choice)

    def test_real_terminal_pair_official_score_decomposition(self):
        public,private=paired_natural_seed(89502)
        self.assertEqual(public["policies"],["challenge"]*4)
        _assert_public(public)
        pair=private["paired"]
        if pair["status"]=="no_two_same_stage_legal_discards":
            self.assertEqual(pair["worlds"],[])
            return
        self.assertEqual(pair["status"],"two_real_terminal_actions")
        self.assertEqual(pair["world_count"],2)
        self.assertTrue(pair["not_calibrated_action_EV"])
        for world in pair["worlds"]:
            self.assertTrue(world["same_actor_observation"])
            delta=world["alternative_minus_baseline"]
            self.assertEqual(delta["official_net"],
                delta["win_points"]+delta["kong_points"]+
                delta["exhaustive_points"])
            for key in ("baseline","alternative"):
                result=world[key]
                self.assertEqual(result["official_net"],
                    result["win_points"]+result["kong_points"]+
                    result["exhaustive_points"])
                self.assertEqual(result["physical_tiles"],108)
                self.assertIn(result["terminal_phase"],("finished","wall_exhausted"))
                self.assertNotIn("future_wall",result)
                self.assertNotIn("opponent_hands",result)

    def test_invalid_seeds_do_not_launch_long_running_simulation(self):
        for bad in (-1,True,2**32,1.5,"89500"):
            with self.subTest(seed=bad),self.assertRaises(ValueError):
                natural_selfplay(bad)
        for t in (
            (-1,1,1),(True,1,1),(89500,0,1),(89500,1,0),
            (89500,5,1),(89500,1,5),(2**32-1,1,1),
        ):
            with self.subTest(args=t),self.assertRaises(ValueError):
                run_experiment(*t)

    def test_offline_model_refuses_causal_and_online_promotion_claims(self):
        natural={
            "private_seed":1,
            "checkpoint_actor":{
                "baseline":"m1","alternative":"m2",
                "features":{
                    "m1":[0.25,0.10,0.14],
                    "m2":[0.35,0.11,0.18],
                },
            },
            "paired":{
                "status":"two_real_terminal_actions",
                "average_alternative_minus_baseline_official_net":200,
                "worlds":[{"world":0},{"world":1}],
            },
        }
        model=_train_from_rows([natural])
        self.assertEqual(model["status"],
                         "bounded_offline_action_preference_fitted")
        self.assertEqual(model["trained_samples"],1)
        self.assertFalse(model["online_policy_changed"])
        self.assertEqual(len(model["feature_names"]),3)
        self.assertTrue(all(-0.2<=w<=0.2 for w in model["weights"]))
        result=_holdout_analysis([natural],model)
        self.assertEqual(result["natural_covered_decisions"],1)
        self.assertEqual(result["fully_terminal_counterfactual_games"],4)
        self.assertFalse(result["confirmed_stronger"])
        self.assertFalse(result["online_model_promoted"])
        nothing={
            "private_seed":2,"checkpoint_actor":None,
            "paired":{"status":"no_two_same_stage_legal_discards","worlds":[]},
        }
        missing=_train_from_rows([nothing])
        self.assertEqual(missing["trained_samples"],0)
        self.assertFalse(missing["online_policy_changed"])
        self.assertEqual(_holdout_analysis([nothing],missing)[
            "natural_covered_decisions"],0)


if __name__=="__main__":
    unittest.main()
