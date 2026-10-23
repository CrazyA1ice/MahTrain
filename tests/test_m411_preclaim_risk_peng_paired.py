"""M4.11: licensed dual-claim counterfactual without post-tail information."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]
from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_minggang_preclaim_paired import (
    ARMS, METRICS, PROTOCOL, PUBLIC_THREAT_GATE,
    PreclaimRiskPengResearchAgent, proposed_claim,
    paired_position, cohort, study,
)
from mahtrain_core.ai_minggang_public_risk_audit import public_minggang_exit_risk
from test_m405_dual_claim_fastpath import real_dual_offer
from test_ai_calls import offer_peng


def mock_risk(index):
    return {
        "min_existing_cut_threat_index":index,
        "risk_index_is_probability":False,
        "supplement_tile_known":False,
    }


class M411PreclaimPairedTests(unittest.TestCase):
    def test_real_108_tile_dual_offer_is_immutable_and_licensed(self):
        game,seat,view=real_dual_offer()
        original=copy.deepcopy(view)
        with patch("mahtrain_core.ai_minggang_preclaim_paired.public_minggang_exit_risk",
                   return_value=mock_risk(.8)):
            out,reason=proposed_claim(view,"ming_gang")
        self.assertEqual((out,reason),("peng","public_threat_gate"))
        self.assertEqual(view,original)
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertFalse("opponent_hands" in json.dumps(original))

    def test_bounded_threshold_is_not_a_probability(self):
        _,seat,view=real_dual_offer()
        self.assertEqual(PUBLIC_THREAT_GATE,.25)
        for index,expected in ((0., "ming_gang"),(.2499,"ming_gang"),
                               (.25,"peng"),(.8,"peng"),(1.75,"peng")):
            with self.subTest(index=index),patch(
                "mahtrain_core.ai_minggang_preclaim_paired.public_minggang_exit_risk",
                return_value=mock_risk(index)):
                choice,reason=proposed_claim(view,"ming_gang")
                self.assertEqual(choice,expected)
        self.assertEqual(ARMS,("baseline","risk_peng"))

    def test_original_pass_peng_mandatory_hu_and_rob_all_preserved(self):
        _,seat,view=real_dual_offer()
        with patch("mahtrain_core.ai_minggang_preclaim_paired.public_minggang_exit_risk",
                   side_effect=AssertionError("forbidden read")):
            self.assertEqual(proposed_claim(view,"peng")[0],"peng")
            self.assertEqual(proposed_claim(view,"pass")[0],"pass")
            protected=copy.deepcopy(view)
            protected["tian_ting"]={"eligible":True}
            self.assertEqual(proposed_claim(protected,"ming_gang")[0],"ming_gang")
            legal_hu=copy.deepcopy(view)
            legal_hu["claim_options"]=["pass","hu","peng","ming_gang"]
            self.assertEqual(proposed_claim(legal_hu,"hu"),("hu","mandatory_hu"))
            rob=copy.deepcopy(view)
            rob["phase"]="rob_kong_window"
            rob["rob_options"]=["pass","hu"]
            self.assertEqual(proposed_claim(rob,"hu"),("hu","mandatory_hu"))
            with self.assertRaises(RuntimeError):
                proposed_claim(rob,"pass")
            rob_pass=copy.deepcopy(rob)
            rob_pass["rob_options"]=["pass"]
            self.assertEqual(proposed_claim(rob_pass,"pass")[0],"pass")
        _,_,single=offer_peng()
        self.assertEqual(proposed_claim(single,"peng")[0],"peng")

    def test_corrupted_authority_and_oracle_claims_fail_closed(self):
        _,_,view=real_dual_offer()
        with self.assertRaises(ValueError):
            proposed_claim(view,"hu")
        for bad in (
            {"min_existing_cut_threat_index":.6,
             "risk_index_is_probability":True,"supplement_tile_known":False},
            {"min_existing_cut_threat_index":.6,
             "risk_index_is_probability":False,"supplement_tile_known":True},
            mock_risk(-.01),
        ):
            with self.subTest(bad=bad),patch(
                "mahtrain_core.ai_minggang_preclaim_paired.public_minggang_exit_risk",
                return_value=bad),self.assertRaises(RuntimeError):
                proposed_claim(view,"ming_gang")

    def test_real_public_risk_does_not_depend_on_injected_oracle_fields(self):
        _,_,view=real_dual_offer()
        baseline=public_minggang_exit_risk(view)
        injected=copy.deepcopy(view)
        injected["future_wall"]=["m1"]*12
        injected["opponent_hands"]=[["p1"]*13]*4
        self.assertEqual(public_minggang_exit_risk(injected),baseline)

    def test_research_agent_keeps_baseline_arm_and_only_legal_response(self):
        _,seat,view=real_dual_offer()
        frozen=copy.deepcopy(view)
        with (patch("mahtrain_core.ai.MahjongAgent.response",
                    return_value="ming_gang"),
              patch("mahtrain_core.ai_minggang_preclaim_paired.public_minggang_exit_risk",
                    return_value=mock_risk(.31))):
            a=PreclaimRiskPengResearchAgent(seed=42,seat=seat,arm="baseline")
            b=PreclaimRiskPengResearchAgent(seed=42,seat=seat,arm="risk_peng")
            self.assertEqual(a.response(view),"ming_gang")
            self.assertEqual(b.response(view),"peng")
            self.assertEqual(a.safe_counts()["actual_changes"],0)
            self.assertEqual(b.safe_counts()["actual_changes"],1)
            self.assertEqual(b.safe_counts()["proposed_differences"],1)
            self.assertEqual(b.safe_counts()["legal_dual_windows"],1)
        self.assertEqual(view,frozen)

    def test_real_paired_terminal_no_change_still_exactly_identical(self):
        x=paired_position(46000,0)
        self.assertEqual(x["challenge_seat"] in range(4),True)
        self.assertEqual(x["seed"],46000)
        for arm in ARMS:
            a=x["arms"][arm]["official"]
            self.assertEqual(a["official_net"],sum(a[k] for k in (
                "win_points","kong_points","exhaustive_points")))
            self.assertIn(x["arms"][arm]["terminal_phase"],
                          ("finished","wall_exhausted"))
        if x["actual_interventions"]==0:
            self.assertTrue(x["same_state_when_unchanged"])
            self.assertEqual(x["paired_deltas"]["official_net"],0)
        raw=json.dumps(x)
        for forbidden in ('"hand"','"tile"','future_wall',
                          'opponent_hands','full_wall'):
            self.assertNotIn(forbidden,raw)

    def test_independent_seed_cluster_delta_is_not_window_sample_count(self):
        def official(net):
            return {
                "official_net":net,"win_points":net,
                "kong_points":0,"exhaustive_points":0,
                "win_events":0,"deal_in_events":0,"realized_kongs":0,
            }
        def fake(seed,rotation):
            change=seed==48000 and rotation==2
            diff=5 if change else 0
            d={m:0 for m in METRICS}
            d["official_net"]=diff;d["win_points"]=diff
            return {
                "seed":seed,"rotation":rotation,
                "challenge_seat":rotation,
                "arms":{
                    "baseline":{"official":official(0),
                                "counts":{"actual_changes":0}},
                    "risk_peng":{"official":official(diff),
                                 "counts":{"actual_changes":int(change)}},
                },
                "paired_deltas":d,"actual_interventions":int(change),
            }
        with patch("mahtrain_core.ai_minggang_preclaim_paired.paired_position",
                   side_effect=fake) as call:
            c=cohort(48000,2)
        self.assertEqual(call.call_count,8)
        self.assertEqual(c["independent_shuffle_seeds"],2)
        self.assertEqual(c["complete_games"],16)
        self.assertEqual(c["candidate_real_policy_changes"],1)
        self.assertEqual(c["seed_mean_official_net_delta"],.625)
        self.assertEqual(c["positive_delta_seeds"],1)
        self.assertEqual(c["unchanged_delta_seeds"],1)
        self.assertIsNone(c["confidence_interval"])
        self.assertFalse(c["risk_is_probability"])

    def test_preregistered_disjoint_holdout_and_protocol(self):
        for bad in ({"seeds":0},{"seeds":9},{"seeds":True},
                    {"development":True},{"holdout":46000},
                    {"holdout":46003},{"holdout":2**32-1}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                study(**bad)
        with patch("mahtrain_core.ai_minggang_preclaim_paired.cohort",
                   return_value={"independent_shuffle_seeds":4}) as run:
            s=study()
        self.assertEqual([k.args for k in run.call_args_list],
                         [(46000,4),(47000,4)])
        self.assertEqual(s["protocol"],PROTOCOL)
        self.assertFalse(s["online_policy_modified"])


if __name__=="__main__":
    unittest.main()
