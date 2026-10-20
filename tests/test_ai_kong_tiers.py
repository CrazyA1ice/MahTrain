"""M3.86 exact priority-tier kong acceleration vs frozen M3.85 policy.

The reference function below is a verbatim M3.85 _challenge_kong with only
its name changed. The new algorithm may skip FULL evaluations only when
lexicographic exact-shanten priority already makes them irrelevant.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"tests")]

from mahtrain_core.ai import (
    MahjongAgent, _call_outlook, _call_settings, _cut_shanten,
    _own_view, _outlook_better_than_baseline, _challenge_kong,
)
from mahtrain_core.ai_tournament import simulate_match
from mahtrain_core.efficiency import shanten_13
from mahtrain_core.rules import TILE_INDEX
from test_ai_calls import offer_kongs
from test_ai_kong_prune import offer_seven_pairs_disrupting_kong


def _m385_challenge_kong(view: Mapping[str, Any]) -> dict[str, str] | None:
    """Rank all legal own kongs without evaluating impossible worse shapes.

    Compare legal 14-effective kongs with the *best* post-discard 13-tile
    stage. A kong with worse exact shanten can never pass the original
    _outlook_better_than_baseline test, regardless of its fan/copy counts.
    Compute that cheap structural bound first, before evaluating any
    expensive multi-draw/fan outlook or collecting reference values.
    """
    hand, melds, missing = _own_view(view)
    public, cap, tian = _call_settings(view)
    allowed = sorted(set(hand), key=TILE_INDEX.__getitem__)
    forced = [tile for tile in allowed if tile[0] == missing]
    if forced:
        allowed = forced
    quick = [(tile, _cut_shanten(hand, melds, missing, tile))
             for tile in allowed]
    least = min(n for _, n in quick)

    # Handle every legal kong kind, but discard candidates whose exact
    # shanten ALREADY loses to best lawful hand cut. This rejects only
    # outcomes that the old full _call_outlook would certainly reject.
    prepared = []
    for choice in view["kong_options"]:
        tile, kind = choice["tile"], choice["type"]
        after = list(hand)
        extra = [dict(group) for group in melds]
        if kind == "an_gang":
            for _ in range(4):
                after.remove(tile)
            extra.append({"type": "an_gang", "tile": tile})
        elif kind == "bu_gang":
            after.remove(tile)
            extra = [
                {"type": "bu_gang" if group["type"] == "peng"
                 and group["tile"] == tile else group["type"],
                 "tile": group["tile"]}
                for group in extra
            ]
        else:
            continue
        stage = shanten_13(after, extra, missing)
        if stage > least:
            continue
        prepared.append((stage, after, extra, choice))
    if not prepared:
        return None

    # Full reference-value enumeration is needed only for same-stage
    # candidates. A strictly better-shanten kong is accepted by the
    # original rule without any ukeire/value comparison.
    before = None
    if any(stage == least for stage, *_ in prepared):
        baselines = []
        for tile, shanten in quick:
            if shanten != least:
                continue
            after = list(hand)
            after.remove(tile)
            baselines.append(_call_outlook(
                after, melds, missing, [*public, tile], cap, tian,
            ))
        before = max(
            (x for x in baselines if x["shanten"] == least),
            key=lambda x: (x["value"], x["ukeire"]),
        )

    candidates = []
    for stage, after, extra, choice in prepared:
        outlook = _call_outlook(after, extra, missing, public, cap, tian)
        if tian.get("eligible") and not outlook["tian_kept"]:
            continue
        if (before is not None
                and not _outlook_better_than_baseline(
                    outlook, before, fraction=0.75)):
            continue
        # Same ranking and deterministic tie breaks as M3.79. A strictly
        # better stage than baseline is always accepted, but every viable
        # candidate still gets its real fan-weighted value for ordering.
        tile, kind = choice["tile"], choice["type"]
        candidates.append((
            (-outlook["shanten"], outlook["value"], outlook["ukeire"],
             int(kind == "an_gang"), -TILE_INDEX[tile]),
            dict(choice),
        ))
    return max(candidates, key=lambda entry: entry[0])[1] if candidates else None



class KongTierParityTests(unittest.TestCase):
    def test_actual_two_legal_own_kongs_match_frozen_m385(self):
        game,seat,view=offer_kongs()
        original=copy.deepcopy(view)
        self.assertEqual(_m385_challenge_kong(view),_challenge_kong(view))
        self.assertEqual(original,view)
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_real_regressing_seven_pair_kong_still_rejected(self):
        game,seat,view=offer_seven_pairs_disrupting_kong()
        self.assertIsNone(_m385_challenge_kong(view))
        with patch("mahtrain_core.ai._call_outlook",
                   side_effect=AssertionError("regressing kong cannot score")):
            self.assertIsNone(_challenge_kong(view))
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_75_percent_ukeire_shortcut_preserves_two_kong_decisions(self):
        # Both kongs are legal, equally tenpai by exact stage. Only m1
        # cannot preserve 75% of the baseline's publicly remaining copies.
        game, seat, view=offer_kongs()
        scores={"old":[], "new":[]}
        def effective(hand,melds,missing,public):
            if melds and melds[-1]["tile"]=="m1":
                copies=[("m2",4),("p3",4),("p7",2)]
            else:
                copies=[("m2",4),("m4",4),("m7",4),("p3",4),("p7",4)]
            return {"shanten":0,
                    "effective_tile_count":sum(n for _,n in copies),
                    "effective_details":[{"tile":t,"remaining":n}
                                         for t,n in copies]}
        for version,policy in (("old",_m385_challenge_kong),
                               ("new",_challenge_kong)):
            def score(hand,melds,missing,cap,context):
                scores[version].append(
                    melds[-1]["tile"] if melds else "baseline")
                return {"multiplier":2}
            with patch("mahtrain_core.ai._cut_shanten",return_value=0), \
                 patch("test_ai_kong_tiers._cut_shanten",return_value=0), \
                 patch("mahtrain_core.ai.shanten_13",return_value=0), \
                 patch("test_ai_kong_tiers.shanten_13",return_value=0), \
                 patch("mahtrain_core.ai.effective_draws",side_effect=effective), \
                 patch("mahtrain_core.ai.score_win",side_effect=score):
                self.assertEqual(policy(view),{"type":"an_gang","tile":"m9"})
        self.assertIn("m1",scores["old"])
        self.assertNotIn("m1",scores["new"],
           "below the real cutoff, per-wait score_win must not execute")
        self.assertIn("m9",scores["new"])
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_ukeire_floor_boundary_still_scores_all_required_waits(self):
        from mahtrain_core.ai import _call_outlook
        info={"shanten":0,"effective_tile_count":12,
              "effective_details":[
                  {"tile":"m7","remaining":4},
                  {"tile":"p8","remaining":4},
                  {"tile":"p9","remaining":4}]}
        with patch("mahtrain_core.ai.effective_draws",return_value=info), \
             patch("mahtrain_core.ai.score_win",
                   return_value={"multiplier":3}) as wins:
            rejected=_call_outlook([],[],"s",[],3,{},minimum_ukeire=12.001)
            self.assertTrue(rejected["insufficient_ukeire"])
            self.assertEqual(wins.call_count,0)
            accepted=_call_outlook([],[],"s",[],3,{},minimum_ukeire=12)
            self.assertNotIn("insufficient_ukeire",accepted)
            self.assertEqual(accepted["value"],36)
            self.assertEqual(wins.call_count,3)

    def test_equal_stage_compares_all_and_preserves_original_fan_ranking(self):
        _,_,view=offer_kongs()
        evidence={"old":[],"new":[]}
        def scorer(calls):
            def func(hand,melds,missing,public,cap,tian,**kwargs):
                tag=melds[-1]["tile"] if melds else "baseline"
                calls.append(tag)
                val={"m1":12,"m9":15,"baseline":8}[tag]
                return {"shanten":1,"value":val,"ukeire":val,
                        "tian_kept":True}
            return func
        for name,policy in (("old",_m385_challenge_kong),
                            ("new",_challenge_kong)):
            with patch("mahtrain_core.ai._cut_shanten",return_value=1), \
                 patch("test_ai_kong_tiers._cut_shanten",return_value=1), \
                 patch("mahtrain_core.ai.shanten_13",return_value=1), \
                 patch("test_ai_kong_tiers.shanten_13",return_value=1), \
                 patch("mahtrain_core.ai._call_outlook",
                       side_effect=scorer(evidence[name])), \
                 patch("test_ai_kong_tiers._call_outlook",
                       side_effect=scorer(evidence[name])):
                self.assertEqual(policy(view),{"type":"an_gang","tile":"m9"})
        self.assertEqual(evidence["old"].count("baseline"),
                         evidence["new"].count("baseline"))
        self.assertEqual(set(evidence["new"]),{"baseline","m1","m9"})

    def test_hidden_future_wall_and_opponents_cannot_affect_priority(self):
        game,seat,view=offer_kongs()
        expected=_m385_challenge_kong(view)
        poisoned=copy.deepcopy(view)
        poisoned["future_wall"]=["m9"]*88
        poisoned["ai_hidden_hands"]=[["p8"]*14]*3
        self.assertEqual(_challenge_kong(poisoned),expected)
        self.assertEqual(game.debug_tile_counts()["total"],108)

    def test_two_full_official_matches_same_actions_and_all_ledgers(self):
        class M385Agent(MahjongAgent):
            def kong(self,view):
                if self.level=="challenge" and view["kong_options"]:
                    return _m385_challenge_kong(view)
                return super().kong(view)

        for seed,seat in ((11,0),(29,2)):
            with self.subTest(seed=seed,seat=seat):
                lineup=["advanced","basic","baseline","challenge"]
                while lineup[seat]!="challenge":
                    lineup=lineup[1:]+lineup[:1]
                older=simulate_match(
                    seed,lineup=lineup,offline_kong_base=1,
                    offline_agent_overrides={
                       seat:M385Agent("challenge",seed=seed,seat=seat)})
                newer=simulate_match(seed,lineup=lineup,offline_kong_base=1)
                for key in ("trace","public_events","public_replay",
                            "winners","official_settled_balances",
                            "partial_win_balances","official_kong_balances",
                            "official_exhaustive_balances","terminal_phase",
                            "physical_count"):
                    self.assertEqual(older[key],newer[key],
                        "M3.86 may not change authoritative match "+key)
                self.assertEqual(newer["physical_count"],108)


if __name__=="__main__":
    unittest.main()
