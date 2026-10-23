"""M4.15 exact first changed discard / actual full-game cash forensic regressions."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]

from mahtrain_core.ai_discard_first_divergence_ledger import (
    PROTOCOL, FirstDivergenceAuditAgent, _dominant_component,
    first_real_discard_divergence, paired_audit_position, cohort, study,
)
from test_ai_calls import offer_kongs


def trace(*, first="m1", seat=1):
    return [
        {"action":"draw","phase":"await_draw","seat":seat},
        {"action":"discard","seat":seat,"tile":first,"minimum_shanten":1,
         "shanten_after":1,"shanten_regret":0,"effective_copies":8},
        {"action":"draw","phase":"await_draw","seat":(seat+1)%4},
    ]


class M415FirstSplitTests(unittest.TestCase):
    def test_replays_exact_first_authorized_cut_and_never_exposes_tile(self):
        original=trace(first="m1")
        revised=trace(first="m2")
        changed=[{
            "own_discard_ordinal":1,
            "minimum_shanten":1,"wall_stage":"early",
            "public_risk_index_drop_milli":110,
            "retained_fan_weighted_value_pct":92.0,
            "retained_effective_copies_pct":95.0,
        }]
        x=first_real_discard_divergence(original,revised,seat=1,
                                        changes=changed)
        self.assertEqual(x["event_ordinal"],2)
        self.assertEqual(x["own_discard_ordinal"],1)
        self.assertEqual(x["exact_minimum_shanten"],1)
        self.assertEqual(x["first_policy_change"],changed[0])
        raw=json.dumps(x)
        for hidden in ('"m1"','"m2"','"tile"','"hand"','"full_wall"'):
            self.assertNotIn(hidden,raw)

    def test_zero_change_requires_entire_event_trace_unchanged(self):
        original=trace()
        self.assertIsNone(first_real_discard_divergence(
            original,list(original),seat=1,changes=[]))
        with self.assertRaises(RuntimeError):
            first_real_discard_divergence(original,trace(first="m2"),
                                          seat=1,changes=[])
        with self.assertRaises(RuntimeError):
            first_real_discard_divergence(original,original[:-1],
                                          seat=1,changes=[])

    def test_no_changed_cut_or_nonseat_action_can_claim_first_split(self):
        source=trace()
        for modified in (
            [dict(source[0],seat=3),*source[1:]],
            [source[0],dict(source[1],action="peng",tile="m2"),source[2]],
            [source[0],dict(source[1],seat=2,tile="m2"),source[2]],
            [source[0],dict(source[1],minimum_shanten=0,tile="m2"),source[2]],
            [source[0],dict(source[1],shanten_regret=1,tile="m2"),source[2]],
        ):
            with self.subTest(modified=modified),self.assertRaises(RuntimeError):
                first_real_discard_divergence(
                    source,modified,seat=1,
                    changes=[{"own_discard_ordinal":1}])

    def test_changed_cut_ordinal_and_monotonicity_must_reconcile(self):
        source=trace()
        for notes in (
            [{"own_discard_ordinal":2}],
            [{"own_discard_ordinal":1},{"own_discard_ordinal":1}],
            [{"own_discard_ordinal":1},{"own_discard_ordinal":0}],
        ):
            with self.subTest(notes=notes),self.assertRaises(RuntimeError):
                first_real_discard_divergence(
                    source,trace(first="m2"),seat=1,changes=notes)

    def test_authoritative_net_component_category_is_descriptive_only(self):
        self.assertEqual(_dominant_component({
            "official_net":0,"win_points":50,"kong_points":-50,
            "exhaustive_points":0}),"zero_net_delta")
        self.assertEqual(_dominant_component({
            "official_net":-700,"win_points":-650,"kong_points":-50,
            "exhaustive_points":0}),"win_points")
        self.assertEqual(_dominant_component({
            "official_net":10,"win_points":10,"kong_points":-10,
            "exhaustive_points":10}),"mixed_components")

    def test_real_108_tile_authorized_rank_and_observer_does_not_export_hand(self):
        game,seat,v=offer_kongs()
        a=FirstDivergenceAuditAgent(seed=42,seat=seat,arm="baseline")
        b=FirstDivergenceAuditAgent(
            seed=42,seat=seat,arm="nearvalue_defense")
        self.assertEqual(
            a.discard(v),__import__(
                "mahtrain_core.ai",fromlist=["MahjongAgent"]
            ).MahjongAgent("challenge",seed=42,seat=seat).discard(v))
        self.assertIn(b.discard(v),v["hand"])
        self.assertEqual(game.debug_tile_counts()["total"],108)
        self.assertEqual(a._anonymous_changes,[])
        self.assertTrue(a._offline_reference_cut)
        self.assertTrue(b._offline_reference_cut)
        self.assertNotIn('"tile"',json.dumps(b._anonymous_changes))

    def test_replay_one_full_real_paired_match_authoritative_cash_and_privacy(self):
        x=paired_audit_position(52000,0)
        self.assertEqual(x["seed"],52000)
        self.assertEqual(x["rotation"],0)
        self.assertEqual(x["delta"]["official_net"],sum(
            x["delta"][key] for key in
            ("win_points","kong_points","exhaustive_points")))
        self.assertEqual(x["real_interventions"]>0,
                         x["first_divergence"] is not None)
        if not x["real_interventions"]:
            self.assertEqual(x["delta"]["official_net"],0)
        output=json.dumps(x)
        for prohibited in ('"tile"','"hand"','"full_wall"',
                           '"_trace"','"opponent_hands"','"public_events"'):
            self.assertNotIn(prohibited,output)

    def test_mocked_cluster_preserves_only_changed_seat_details(self):
        def mock_position(seed,rot):
            count=2 if seed==54000 and rot==1 else 0
            delta={"official_net":-12*count,"win_points":-10*count,
                   "kong_points":-2*count,"exhaustive_points":0,
                   "win_events":0,"deal_in_events":count,
                   "realized_kongs":0}
            return {
                "seed":seed,"rotation":rot,"challenge_seat":rot,
                "delta":delta,"real_interventions":count,
                "first_divergence":(
                    {"event_ordinal":3,"first_policy_change":{
                        "wall_stage":"late","own_discard_ordinal":1}}
                    if count else None),
                "dominant_cash_component":"win_points",
            }
        with patch("mahtrain_core.ai_discard_first_divergence_ledger.paired_audit_position",
                   side_effect=mock_position) as run:
            data=cohort(54000,2)
        self.assertEqual(run.call_count,8)
        self.assertEqual(data["independent_shuffle_seeds"],2)
        self.assertEqual(data["complete_games"],16)
        self.assertEqual(data["changed_positions"],1)
        self.assertEqual(data["actual_policy_changes"],2)
        self.assertEqual(data["official_deltas"]["official_net"],-24)
        self.assertEqual(data["mean_four_seat_net_delta"],-3)
        self.assertEqual(data["per_seed"][0]["win_delta"],-20)

    def test_old_development_holdout_are_retrospective_not_fresh_validation(self):
        with patch("mahtrain_core.ai_discard_first_divergence_ledger.cohort",
                   side_effect=lambda start,seeds:{"start":start,"seeds":seeds}
                   ) as called:
            summary=study()
        self.assertEqual([x.args for x in called.call_args_list],
                         [(52000,4),(53000,4)])
        self.assertEqual(summary["protocol"],PROTOCOL)
        self.assertTrue(summary["retrospective_not_independent_validation"])
        self.assertFalse(summary["online_policy_modified"])
        self.assertEqual(summary["development"]["start"],52000)
        self.assertEqual(summary["holdout"]["start"],53000)

    def test_invalid_independent_seed_and_seat_rejected(self):
        for seed,rotation in ((True,0),(-1,0),(2**32,0),
                              (52000,4),(52000,True)):
            with self.subTest(seed=seed,rotation=rotation),self.assertRaises(ValueError):
                paired_audit_position(seed,rotation)
        for start,seeds in ((True,4),(52000,True),(52000,0),
                            (52000,9),(2**32-2,4)):
            with self.subTest(start=start,seeds=seeds),self.assertRaises(ValueError):
                cohort(start,seeds)


if __name__=="__main__":
    unittest.main()
