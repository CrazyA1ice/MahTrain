"""M4.21 protected first-real-change and right-censored observed tenpai tests."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT),str(ROOT/"tests")]
from mahtrain_core.ai_bounded_first_split_tenpai_audit import (
    PROTOCOL, REPLAY_GROUPS, FirstSplitBoundedAuditAgent,
    observed_tenpai_after_first_split, paired_audit_position,cohort,study,
)
from mahtrain_core.ai_discard_first_divergence_ledger import (
    first_real_discard_divergence,
)


def discard(seat=2,shanten=1,tile="m1"):
    return {
        "seat":seat,"action":"discard","tile":tile,
        "minimum_shanten":shanten,"shanten_after":shanten,
        "shanten_regret":0,"effective_copies":12,
    }


class M421BoundedSplitTenpaiAuditTests(unittest.TestCase):
    def test_one_real_change_with_first_original_action_not_hidden(self):
        shared={"action":"exchange_three","seat":2}
        base=[shared,discard(tile="m1"),discard(tile="m2")]
        changed=[shared,discard(tile="m3"),discard(tile="m2")]
        change=[{"own_discard_ordinal":1,
                 "projected_ratio":1.20,"minimum_shanten":1}]
        result=first_real_discard_divergence(
            base,changed,seat=2,changes=change)
        self.assertEqual(result["event_ordinal"],2)
        self.assertEqual(result["own_discard_ordinal"],1)
        self.assertEqual(result["exact_minimum_shanten"],1)
        self.assertEqual(result["first_policy_change"]["projected_ratio"],1.20)
        for secret in ('"tile"','"m1"','"m2"','"m3"','"hand"'):
            self.assertNotIn(secret,json.dumps(result))

    def test_first_later_zero_shanten_after_two_own_cuts(self):
        trace=[
            discard(shanten=1),
            {"action":"draw","seat":2},
            discard(shanten=1),
            {"action":"peng","seat":3},
            {"action":"draw","seat":2},
            discard(shanten=0),
            {"action":"all_pass","seat":0},
        ]
        x=observed_tenpai_after_first_split(
            trace,seat=2,first_event_index=0)
        self.assertEqual(x["own_later_discards_until_tenpai"],2)
        self.assertEqual(x["events_after_split"],5)
        self.assertEqual(x["own_later_discards_total"],2)
        self.assertTrue(x["observed_zero_shanten"])
        self.assertFalse(x["censored"])

    def test_no_later_observed_zero_shanten_is_censored_not_no_tenpai(self):
        trace=[discard(),{"action":"draw","seat":2},discard(shanten=1),
               {"action":"self_draw_win","seat":2}]
        x=observed_tenpai_after_first_split(
            trace,seat=2,first_event_index=0)
        self.assertTrue(x["censored"])
        self.assertFalse(x["observed_zero_shanten"])
        self.assertIsNone(x["events_after_split"])
        self.assertIsNone(x["own_later_discards_until_tenpai"])
        self.assertEqual(x["own_later_discards_total"],1)

    def test_invalid_first_split_never_fabricates_observation(self):
        for bad in (-1,3,True):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                observed_tenpai_after_first_split(
                    [discard()],seat=2,first_event_index=bad)
        with self.assertRaises(RuntimeError):
            observed_tenpai_after_first_split(
                [{"action":"draw","seat":2}],seat=2,first_event_index=0)
        with self.assertRaises(RuntimeError):
            observed_tenpai_after_first_split(
                [discard(),{"action":"discard","seat":2,
                            "shanten_after":None}],
                seat=2,first_event_index=0)

    def test_agent_baseline_has_no_shadow_forensic_revisions(self):
        agent=FirstSplitBoundedAuditAgent(
            seed=42,seat=0,arm="baseline")
        self.assertFalse(agent.anonymous_changes)
        self.assertEqual(agent.safe_counts().get("actual_changes",0),0)
        self.assertTrue(agent._offline_reference_cut)

    def test_true_m420_seed_60000_rotation_zero_is_not_phantom(self):
        p=paired_audit_position(60000,0)
        self.assertEqual(p["seed"],60000)
        self.assertEqual(p["rotation"],0)
        self.assertEqual(p["actual_changes"],0)
        self.assertIsNone(p["first_split"])
        self.assertEqual(p["authoritative_deltas"]["official_net"],0)
        self.assertEqual(p["terminal_stage_deltas"],{
            "flower_pig":0,"da_jiao":0,
        })
        for arm in ("baseline","bounded_two_transition"):
            official=p["arms"][arm]["official"]
            self.assertEqual(official["official_net"],sum(official[k]
                for k in ("win_points","kong_points","exhaustive_points")))
        raw=json.dumps(p)
        for prohibited in ('"tile"','"hand"','"opponent_hands"',
                           '"future_wall"','"_trace"','"public_events"'):
            self.assertNotIn(prohibited,raw)

    def test_matched_real_m420_changed_game_records_a_real_first_split(self):
        # Seed60001 is the first historical independent shuffle in which
        # the frozen M4.20 research arm actually modified a cut. Four
        # seating rotations are inspected rather than assuming the seat.
        affected=[paired_audit_position(60001,r) for r in range(4)]
        changed=[r for r in affected if r["actual_changes"]]
        self.assertEqual(sum(p["actual_changes"] for p in changed),1)
        self.assertEqual(len(changed),1)
        row=changed[0]
        f=row["first_split"]
        self.assertIsNotNone(f)
        self.assertEqual(f["exact_minimum_shanten"],1)
        self.assertEqual(f["first_policy_change"]["minimum_shanten"],1)
        self.assertGreaterEqual(f["first_policy_change"]["projected_ratio"],1.12)
        self.assertEqual(f["first_policy_change"]["own_discard_ordinal"],
                         f["own_discard_ordinal"])
        self.assertIn("baseline",f["observed_tenpai_after_split"])
        self.assertIn("bounded_two_transition",f["observed_tenpai_after_split"])
        self.assertEqual(row["authoritative_deltas"]["official_net"],0)
        self.assertEqual(row["terminal_stage_deltas"]["flower_pig"],0)
        self.assertEqual(row["terminal_stage_deltas"]["da_jiao"],0)
        for protected in ('"tile"','"hand"','"future_wall"','"_trace"'):
            self.assertNotIn(protected,json.dumps(row))

    def test_two_arms_and_source_action_have_exact_same_ledger_components(self):
        row=paired_audit_position(61000,0)
        self.assertEqual(row["authoritative_deltas"]["official_net"],
                         sum(row["authoritative_deltas"][k] for k in (
                             "win_points","kong_points","exhaustive_points")))
        self.assertEqual(row["authoritative_deltas"]["exhaustive_points"],
                         sum(row["terminal_stage_deltas"].values()))

    def test_cohort_aggregates_seed_not_seat_and_zero_sum_stages(self):
        def fake(seed,rotation):
            changed=int(seed==62000 and rotation==2)
            delta={k:0 for k in (
                "official_net","win_points","kong_points",
                "exhaustive_points","win_events","deal_in_events",
                "realized_kongs")}
            return {
                "seed":seed,"rotation":rotation,"challenge_seat":rotation,
                "actual_changes":changed,"first_split":(
                    {"event_ordinal":8} if changed else None),
                "authoritative_deltas":delta,
                "terminal_stage_deltas":{"flower_pig":0,"da_jiao":0},
            }
        with patch("mahtrain_core.ai_bounded_first_split_tenpai_audit.paired_audit_position",
                   side_effect=fake) as call:
            r=cohort(62000,2)
        self.assertEqual(call.call_count,8)
        self.assertEqual(r["independent_historical_shuffles"],2)
        self.assertEqual(r["complete_paired_games"],16)
        self.assertEqual(r["total_actual_changes"],1)
        self.assertEqual(r["changed_seat_positions"],1)
        self.assertEqual(r["unchanged_position_count"],7)
        self.assertTrue(r["retrospective_not_new_validation"])

    def test_disjoint_fixed_history_and_no_live_ai_changes(self):
        self.assertEqual(REPLAY_GROUPS,{
            "development":(60000,3),"holdout":(61000,3)})
        with patch("mahtrain_core.ai_bounded_first_split_tenpai_audit.cohort",
                   side_effect=lambda start,n:{"start":start,"seeds":n}) as call:
            report=study()
        self.assertEqual([c.args for c in call.call_args_list],[
            (60000,3),(61000,3)])
        self.assertEqual(report["protocol"],PROTOCOL)
        self.assertTrue(report["retrospective_not_independent_validation"])
        self.assertFalse(report["online_ai_modified"])

    def test_invalid_seed_rotation_and_cohort_fail_closed(self):
        for seed,rotation in ((True,0),(-1,0),(2**32,0),
                              (60000,True),(60000,4)):
            with self.subTest(seed=seed,rotation=rotation),self.assertRaises(ValueError):
                paired_audit_position(seed,rotation)
        for seed,n in ((True,3),(62000,True),(62000,0),
                       (62000,7),(2**32-2,3)):
            with self.subTest(seed=seed,n=n),self.assertRaises(ValueError):
                cohort(seed,n)


if __name__=="__main__":
    unittest.main()
