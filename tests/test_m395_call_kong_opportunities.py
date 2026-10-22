"""M3.95 call/kong optional-action research: legal ablations, official ledger, holdout."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"tests")]

from mahtrain_core.ai import MahjongAgent
from mahtrain_core.ai_challenge_call_kong_ablation import (
    PROTOCOL, ARMS, CallKongResearchAgent, _official_outcome,
    _paired, _peng_shanten_comparison, study,
)
from test_ai_calls import offer_peng, offer_kongs


class CallKongAblationTests(unittest.TestCase):
    def test_no_tie_peng_only_declines_when_not_improving_shanten(self):
        _,seat,view=offer_peng()
        view["claim_options"]=["pass","peng"]
        agent=CallKongResearchAgent(seed=42,seat=seat,arm="no_tie_peng")
        unchanged=copy.deepcopy(view)
        with patch.object(MahjongAgent,"response",return_value="peng"),patch(
                "mahtrain_core.ai_challenge_call_kong_ablation._peng_shanten_comparison",
                return_value=(2,2)):
            selected=agent.response(view)
        self.assertEqual(selected,"pass")
        self.assertEqual(agent.safe_counts()["nonimproving_peng_rejected"],1)
        self.assertEqual(agent.safe_counts()["changed_claim"],1)
        self.assertEqual(view,unchanged)
        scene=agent.safe_scenarios()[0]
        self.assertEqual(scene["trigger"],"claim")
        self.assertEqual(scene["original"],"peng")
        self.assertEqual(scene["revised"],"pass")
        self.assertNotIn("tile",scene)
        self.assertNotIn("seed",scene)
        for word in ("hand","wall_tiles","future_wall","opponent_hands"):
            self.assertNotIn(word,json.dumps(scene))
        agent2=CallKongResearchAgent(seed=42,seat=seat,arm="no_tie_peng")
        with patch.object(MahjongAgent,"response",return_value="peng"),patch(
                "mahtrain_core.ai_challenge_call_kong_ablation._peng_shanten_comparison",
                return_value=(2,1)):
            self.assertEqual(agent2.response(view),"peng")
        self.assertEqual(agent2.safe_counts()["interventions"],0)
        self.assertEqual(agent2.safe_counts()["nonimproving_peng_rejected"],0)

    def test_no_kong_control_preserves_hu_and_suppresses_ming_gang(self):
        _,seat,view=offer_peng()
        view["claim_options"]=["pass","peng","ming_gang"]
        bot=CallKongResearchAgent(seed=42,seat=seat,arm="no_kong")
        with patch.object(MahjongAgent,"response",return_value="ming_gang"):
            result=bot.response(view)
        self.assertEqual(result,"pass")
        self.assertEqual(bot.safe_counts()["changed_claim"],1)
        self.assertEqual(bot.safe_counts()["original_ming_gang"],1)
        with patch.object(MahjongAgent,"response",return_value="peng"):
            self.assertEqual(bot.response(view),"peng")
        view["claim_options"]=["pass","hu"]
        with patch.object(MahjongAgent,"response",return_value="hu"):
            self.assertEqual(bot.response(view),"hu")
        self.assertEqual(bot.safe_counts()["optional_claim_opportunities"],2)

    def test_no_kong_control_suppresses_own_kong_only(self):
        _,seat,view=offer_kongs()
        bot=CallKongResearchAgent(seed=42,seat=seat,arm="no_kong")
        selected=MahjongAgent("challenge",seed=42,seat=seat).kong(view)
        self.assertIsNotNone(selected)
        self.assertIsNone(bot.kong(view))
        counts=bot.safe_counts()
        self.assertEqual(counts["changed_own_kong"],1)
        self.assertEqual(counts["own_kong_opportunities"],1)
        self.assertEqual(counts["interventions"],1)
        self.assertEqual(bot.safe_scenarios()[0]["original"],selected["type"])
        baseline=CallKongResearchAgent(seed=42,seat=seat,arm="baseline")
        self.assertEqual(baseline.kong(view),selected)
        self.assertEqual(baseline.safe_counts()["interventions"],0)
        self.assertEqual(baseline.safe_scenarios(),[])

    def test_authored_legal_peng_comparison_does_not_inspect_hidden_world(self):
        _,_,view=offer_peng()
        original=copy.deepcopy(view)
        before=_peng_shanten_comparison(view)
        injected=copy.deepcopy(view)
        injected["_hands"]=[["m1"]*14]*4
        injected["future_wall"]=["s1"]*12
        injected["opponent_hands"]=[["m1"]*13]*3
        self.assertEqual(_peng_shanten_comparison(injected),before)
        self.assertEqual(view,original)
        self.assertEqual(len(before),2)
        self.assertTrue(all(type(x) is int for x in before))

    def test_official_score_reconciles_component_ledgers_and_rob_responsibility(self):
        lineup=["challenge","advanced","basic","baseline"]
        game={
            "assignment":lineup,
            "physical_count":108,
            "scoring_rules":{"kong_base":1},
            "terminal_phase":"wall_exhausted",
            "official_exhaustive_posted":True,
            "official_settled_balances":[12,-12,0,0],
            "partial_win_balances":[5,-5,0,0],
            "official_kong_balances":[2,-2,0,0],
            "official_exhaustive_balances":[5,-5,0,0],
            "winners":[{"seat":0,"source":1},{"seat":1,"source":0}],
            "public_events":[
                {"type":"peng","seat":0},
                {"type":"an_gang","seat":0},
                {"type":"bu_gang_declared","seat":0},
            ],
        }
        report=_official_outcome(game,0,lineup)
        self.assertEqual((report["official_net"],report["win_points"],
                          report["kong_points"],report["exhaustive_points"]),
                         (12,5,2,5))
        self.assertEqual(report["realized_kongs"],1)
        self.assertEqual(report["win_events"],report["deal_in_events"])
        invalid=copy.deepcopy(game)
        invalid["official_kong_balances"]=[3,-3,0,0]
        with self.assertRaisesRegex(RuntimeError,"reconcile"):
            _official_outcome(invalid,0,lineup)
        invalid=copy.deepcopy(game)
        invalid["physical_count"]=107
        with self.assertRaisesRegex(RuntimeError,"108"):
            _official_outcome(invalid,0,lineup)
        invalid=copy.deepcopy(game)
        invalid["official_exhaustive_posted"]=False
        with self.assertRaisesRegex(RuntimeError,"posted"):
            _official_outcome(invalid,0,lineup)

    def test_research_cohorts_are_disjoint_and_honor_exact_rotations(self):
        for kw in (
            {"development_start":13000,"holdout_start":13001,"seeds_per_group":2},
            {"development_start":True},{"holdout_start":True},
            {"seeds_per_group":True},{"seeds_per_group":0},{"seeds_per_group":5},
            {"holdout_start":2**32-1},{"development_start":-1},
        ):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                study(**kw)
        def fake_pair(seed,rotation):
            seat=(4-rotation)%4
            score={
                "official_net":0,"win_points":0,"kong_points":0,
                "exhaustive_points":0,"win_events":0,
                "deal_in_events":0,"realized_kongs":0,
            }
            result={}
            for arm in ARMS:
                s=dict(score)
                s["official_net"]=1 if arm=="no_kong" else 0
                result[arm]={
                    "score":s,
                    "opportunities":{
                        "optional_claim_opportunities":2,
                        "own_kong_opportunities":1,
                        "interventions":1 if arm=="no_kong" else 0,
                    },
                    "scenario_examples":[],
                }
            return {"seed":seed,"rotation":rotation,
                    "challenge_seat":seat,"arms":result}
        with patch("mahtrain_core.ai_challenge_call_kong_ablation._paired",
                   side_effect=fake_pair):
            summary=study(development_start=12000,
                          holdout_start=13000,seeds_per_group=2)
        self.assertEqual(summary["protocol"],PROTOCOL)
        for label,lower in (("development",12000),("holdout",13000)):
            group=summary[label]
            self.assertEqual(group["independent_seeds"],2)
            self.assertEqual(group["complete_games"],24)
            self.assertEqual([x["seed"] for x in group["per_seed"]],
                             [lower,lower+1])
            self.assertEqual(
                group["comparisons"]["no_kong"]["mean_seed_cluster_net_delta"],1)
            self.assertEqual(
                group["comparisons"]["no_tie_peng"]["mean_seed_cluster_net_delta"],0)
            self.assertIsNone(
                group["comparisons"]["no_kong"]["interval_95pct"])

    def test_one_real_position_is_deterministic_authoritative_and_private(self):
        first=_paired(12000,0)
        other=_paired(12000,0)
        self.assertEqual(first,other)
        self.assertEqual(first["challenge_seat"],0)
        for arm in ARMS:
            record=first["arms"][arm]
            self.assertGreaterEqual(record["opportunities"]["optional_claim_opportunities"],0)
            self.assertGreaterEqual(record["opportunities"]["own_kong_opportunities"],0)
            self.assertEqual(
                record["opportunities"]["interventions"],
                record["opportunities"]["changed_claim"]+
                record["opportunities"]["changed_own_kong"])
            self.assertNotIn("hand",str(record))
            self.assertNotIn("future_wall",str(record))
            self.assertNotIn("private",str(record))


if __name__=="__main__":
    unittest.main()
