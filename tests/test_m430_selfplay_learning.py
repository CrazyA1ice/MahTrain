"""M4.30 actor-only self-play archive / offline learned pilot protections."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT)]

from mahtrain_core.ai_selfplay_learning import (
    PROTOCOL,MODEL_PROTOCOL,FEATURES,_lineup,_assert_public,
    selfplay_seed,fit_trajectory_pilot,OfflineLearnedChallengeAgent,
    run_pilot,heldout_trial,_settlement,
)


def _synthetic_actor_game(seed,rotation,net):
    # These hand-crafted rows are for train VALIDATOR unit tests ONLY.
    # They must never appear in performance reports as empirical self-play.
    candidates=[
        {"discard":"m1","features":[0.3,0.5,0,0,1,0.2]},
        {"discard":"m2","features":[0.5,0.3,0,0,1,0.2]},
    ]
    return {
        "protocol":PROTOCOL,"actor_observations_only":True,
        "rule_set":"current_m423",
        "private_shuffle_seed":seed,"rotation":rotation,
        "terminal_outcome":{"official_net":net},
        "decisions":[{
            "kind":"discard","chosen_action":"m1",
            "discard_ranked":candidates,
        }],
    }


class M430SelfPlayLearningTests(unittest.TestCase):
    def test_four_rotation_exact_seat_exposure(self):
        positions=[]
        for r in range(4):
            a,seat=_lineup(r)
            self.assertEqual(sorted(a),sorted(
                ("challenge","basic","advanced","baseline")))
            self.assertEqual(a[seat],"challenge")
            positions.append(seat)
        self.assertEqual(sorted(positions),[0,1,2,3])
        for wrong in (True,-1,4,1.0,"0"):
            with self.subTest(rotation=wrong),self.assertRaises(ValueError):
                _lineup(wrong)

    def test_real_selfplay_public_redaction_private_own_hand_and_ledger(self):
        public,private=selfplay_seed(88031,0,public_id="game-local-0")
        self.assertEqual(public["protocol"],PROTOCOL)
        self.assertEqual(public["rule_set"],"current_m423")
        self.assertEqual(public["game_id"],private["game_id"])
        self.assertNotIn("seed",str(public))
        _assert_public(public)
        self.assertEqual(private["private_shuffle_seed"],88031)
        self.assertEqual(private["rotation"],0)
        self.assertTrue(private["actor_observations_only"])
        self.assertGreater(len(public["public_frames"]),15)
        self.assertGreater(len(private["decisions"]),2)
        self.assertEqual(
            private["terminal_outcome"]["official_net"],
            sum(private["terminal_outcome"][k] for k in (
                "win_points","kong_points","exhaustive_points",
            )),
        )
        for row in private["decisions"]:
            self.assertIn("own_hand",row)
            self.assertIn("public_melds",row)
            self.assertNotIn("opponent_hands",row)
            self.assertNotIn("future_wall",row)
            self.assertNotIn("drawn_tile",row)
            if row["kind"]=="discard" and row.get("discard_ranked"):
                self.assertIn(row["chosen_action"],
                    [item["discard"] for item in row["discard_ranked"]])
                self.assertTrue(all(len(item["features"])==len(FEATURES)
                                    for item in row["discard_ranked"]))

    def test_public_sanitizer_recurses_in_nested_frames(self):
        _assert_public({"public_frames":[{"action":{"tile":"s3"},
                        "board":{"hand_counts":[3,4,5,6]}}]})
        for name in ("hand","own_hand","future_wall","drawn_tile",
                     "seed","opponent_hands","kong_options"):
            with self.subTest(secret=name),self.assertRaises(RuntimeError):
                _assert_public({"frames":[{"board":{name:["m1"]}}]})

    def test_bounded_trajectory_fitter_requires_four_rotations(self):
        g=[_synthetic_actor_game(1,r,100) for r in range(4)]
        model=fit_trajectory_pilot(g)
        self.assertEqual(model["protocol"],MODEL_PROTOCOL)
        self.assertEqual(model["training_games"],4)
        self.assertEqual(model["training_seed_clusters"],1)
        self.assertEqual(model["eligible_discard_decisions"],4)
        self.assertEqual(len(model["weights"]),len(FEATURES))
        self.assertTrue(all(-0.2<=w<=0.2 for w in model["weights"]))
        self.assertFalse(model["online_promotion_allowed"])
        with self.assertRaises(ValueError):
            fit_trajectory_pilot(g[:-1])
        with self.assertRaises(ValueError):
            fit_trajectory_pilot([*g,g[0]])
        bad=deepcopy(g)
        bad[0]["actor_observations_only"]=False
        with self.assertRaises(ValueError):
            fit_trajectory_pilot(bad)

    def test_model_will_not_override_legacy_actor_or_illegal_stage(self):
        g=[_synthetic_actor_game(1,r,100) for r in range(4)]
        model=fit_trajectory_pilot(g)
        agent=OfflineLearnedChallengeAgent(seed=123,seat=0,model=model)
        self.assertEqual(agent.level,"challenge")
        self.assertEqual(agent.seat,0)
        for value in (0.5,float("nan"),"negative"):
            bad=deepcopy(model)
            bad["weights"][0]=value
            with self.subTest(value=str(value)),self.assertRaises(ValueError):
                OfflineLearnedChallengeAgent(seed=123,seat=0,model=bad)
        bad=deepcopy(model)
        bad["online_promotion_allowed"]=True
        with self.assertRaises(ValueError):
            OfflineLearnedChallengeAgent(seed=123,seat=0,model=bad)
        bad=deepcopy(model)
        bad["protocol"]="future_unvalidated_policy"
        with self.assertRaises(ValueError):
            OfflineLearnedChallengeAgent(seed=123,seat=0,model=bad)

    def test_untrained_and_holdout_seed_overlap_rejected_by_planning(self):
        for case in (
            (-1,1,1),(2**32-1,1,1),
            (0,0,1),(0,1,0),(0,11,1),(True,1,1),
            (10,True,1),(10,1,True),(10,1,11),
        ):
            with self.subTest(case=case),self.assertRaises(ValueError):
                run_pilot(*case)

    def test_real_disjoint_holdout_two_arms_with_fixed_model(self):
        g=[_synthetic_actor_game(1,r,100) for r in range(4)]
        model=fit_trajectory_pilot(g)
        result=heldout_trial(88035,1,model)
        self.assertEqual(result["heldout_independent_seed_clusters"],1)
        self.assertEqual(result["heldout_complete_games"],8)
        self.assertEqual(len(result["pairs"]),4)
        self.assertEqual(sorted(x["challenge_seat"] for x in result["pairs"]),
                         [0,1,2,3])
        self.assertFalse(result["confirmed_stronger"])
        self.assertFalse(result["promoted_to_live_ai"])
        self.assertAlmostEqual(
            result["mean_conditional_holdout_delta"],
            result["sum_conditional_holdout_delta"]/4,places=4,
        )

    def test_wrong_ledgers_cannot_enter_training(self):
        valid={
            "terminal_phase":"finished","physical_count":108,
            "scoring_rules":{"kong_base":20},
            "partial_win_balances":[100,-100,0,0],
            "official_kong_balances":[0,0,0,0],
            "official_exhaustive_balances":[0,0,0,0],
            "official_settled_balances":[100,-100,0,0],
        }
        self.assertEqual(_settlement(valid,0)["official_net"],100)
        bad=deepcopy(valid)
        bad["official_settled_balances"]=[0,0,0,0]
        with self.assertRaises(RuntimeError):
            _settlement(bad,0)
        bad=deepcopy(valid)
        bad["scoring_rules"]["kong_base"]=None
        with self.assertRaises(RuntimeError):
            _settlement(bad,0)


if __name__=="__main__":
    unittest.main()
