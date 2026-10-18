"""M3.59 risk model freeze, cross-policy generalization, whole-ledger paired games."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from mahtrain_core.ai_ron_calibration import NAMES, public_candidate_features
from mahtrain_core.ai_ron_frozen_experiment import (
    POLICY_FAMILIES, PROTOCOL, _check_seed_sets, _pair,
    _frozen_candidate_scores, run_frozen_risk_research,
)
from mahtrain_core.ai_tournament import simulate_match


def visible():
    return {
        "seat":0,"phase":"await_discard","wall_count":18,
        "hand":["m1","m2","m3","s2"],
        "missing_suits":["p","m","s","p"],"won":[False]*4,
        "melds":[[],[],[],[]],
        "discards":[{"seat":1,"tile":"m4"},
                    {"seat":2,"tile":"p7"}],
    }


def observed(seed, ron=False, safe=False):
    view=visible()
    feat=list(public_candidate_features(view,1,"s2"))
    feat[NAMES.index("target_dingque_safe")]=float(safe)
    return {
        "seed":seed,"features":tuple(feat),"ron":int(ron),
        "payout_multiplier":2 if ron else 0,
    }


class FrozenRonPolicyTests(unittest.TestCase):
    def test_seed_sets_are_complete_and_disjoint(self):
        _check_seed_sets([1,2],[3,4],[5,6])
        for groups in [([1],[1],[2]),([1,1],[2],[3]),
                       ([1],[2],[]),([1],[2],[True]),
                       ([1],[2],[-1])]:
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                _check_seed_sets(*groups)

    def test_frozen_risk_never_changes_shanten_and_ignores_hidden_injection(self):
        rows=[
            {"discard":"m1","shanten":0,"score":10.,
             "effective_tile_count":5},
            {"discard":"s2","shanten":0,"score":9.5,
             "effective_tile_count":5},
        ]
        view=visible()
        with patch("mahtrain_core.ai_ron_frozen_experiment._predict",
                   side_effect=lambda row,p,prior: (
                       .2 if row["features"][NAMES.index("tile_m")] else .0
                   )):
            ranked=_frozen_candidate_scores(
                view,rows,(0.,)*len(NAMES),mean_payout=2)
            evil=copy.deepcopy(view)
            evil.update({
                "_hands":[["m1"]*14]*4,
                "opponent_hands":[["m1"]*13]*3,
                "future_wall":["m1"]*40,
                "match_seed":123,
            })
            again=_frozen_candidate_scores(
                evil,rows,(0.,)*len(NAMES),mean_payout=2)
        self.assertEqual(ranked,again)
        self.assertEqual(ranked[0]["discard"],"s2")
        self.assertEqual(ranked[0]["shanten"],0)
        self.assertLessEqual(ranked[1]["offline_risk_penalty"],.12)
        broken=[dict(rows[0]),dict(rows[1],shanten=1)]
        with self.assertRaises(ValueError):
            _frozen_candidate_scores(view,broken,(0.,)*len(NAMES))
        with self.assertRaises(ValueError):
            _frozen_candidate_scores(view,rows,(0.,)*len(NAMES),risk_scale=0)

    def test_paired_game_has_same_seed_seat_and_priced_settlements(self):
        def fake_simulate(seed,rotation,lineup,offline_kong_base,
                          offline_agent_overrides=None):
            self.assertEqual(seed,44)
            self.assertEqual(offline_kong_base,1)
            self.assertEqual(lineup.count("challenge"),1)
            s=lineup.index("challenge")
            if offline_agent_overrides is not None:
                self.assertEqual(set(offline_agent_overrides),{s})
                self.assertEqual(offline_agent_overrides[s].level,"challenge")
            balances=[-1]*4
            balances[s]=3
            return {
                "assignment":lineup,"physical_count":108,
                "official_settled_balances":balances,
                "scoring_rules":{"kong_base":1},
                "terminal_phase":"finished",
                "official_exhaustive_posted":False,
                "winners":[{"seat":s,"source":None}],
                "unpriced_kong_events":0,
            }
        with patch("mahtrain_core.ai_ron_frozen_experiment.simulate_match",
                   side_effect=fake_simulate) as sim:
            result=_pair(44,2,(0.,)*len(NAMES),1.5,risk_scale=1.8)
        self.assertEqual(sim.call_count,2)
        self.assertEqual(result["delta_net"],0)
        self.assertEqual(result["baseline_net"],result["treatment_net"])
        self.assertEqual(result["baseline_win_events"],1)
        self.assertEqual(result["baseline_discard_ron_sources"],0)

    def test_frozen_report_never_contains_private_rows_or_coefficients(self):
        def sealed(seed, *, stride=3, lineup=None):
            self.assertEqual(stride,2)
            return [observed(seed,ron=True),observed(seed,ron=False),
                    observed(seed,ron=False,safe=True)]
        def fake_pair(seed,rotation,coefficients,mean_multiplier,*,risk_scale):
            self.assertEqual(risk_scale,1.8)
            self.assertEqual(len(coefficients),len(NAMES))
            return {
                "seed":seed,"rotation":rotation,"treated_seat":rotation,
                "baseline_net":100,"treatment_net":101,
                "delta_net":1,"risk_observations":2,
                "changed_discard_decisions":1,
                "baseline_discard_ron_sources":1,
                "treatment_discard_ron_sources":0,
            }
        with patch("mahtrain_core.ai_ron_frozen_experiment.collect_ron_labels",
                   side_effect=sealed) as collect, patch(
                   "mahtrain_core.ai_ron_frozen_experiment._pair",
                   side_effect=fake_pair) as paired:
            report=run_frozen_risk_research(
                [11,12],[13,14],[15,16],stride=2,bootstrap=128,
            )
        self.assertEqual(collect.call_count,6)
        self.assertEqual(paired.call_count,8)
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertFalse(report["online_policy_modified"])
        self.assertFalse(report["can_claim_superior_policy"])
        self.assertFalse(report["contains_private_hands"])
        self.assertEqual(report["paired"]["game_pairs"],8)
        self.assertEqual(report["paired"]["paired_net_delta"],8)
        self.assertEqual(report["paired"]["total_changed_discards"],8)
        self.assertEqual(set(report["cross_policy"]),set(POLICY_FAMILIES))
        self.assertEqual(len(report["frozen_model_fingerprint"]),16)
        self.assertEqual(
            report["paired"]["seed_bootstrap_net_delta"]["seed_clusters"],2)
        blob=json.dumps(report)
        for private in ('"features":','"payout_multiplier":',
                        '"opponent_hands":','"future_wall":',
                        '"waits":','"coefficients":','"_hands":',
                        '"trace":','"public_replay":'):
            self.assertNotIn(private,blob)

    def test_invalid_offline_match_override_rejected_before_simulation(self):
        lineup=["challenge","advanced","basic","baseline"]
        with self.assertRaises(ValueError):
            simulate_match(4,lineup=lineup,offline_agent_overrides={1:object()})
        with self.assertRaises(ValueError):
            simulate_match(4,lineup=lineup,offline_kong_base=-1)


if __name__=="__main__":
    unittest.main()
