"""Completed-only four-seat replay. Never send these frames in a live response.

Capture trusted server hands immediately before and after an actual move,
but persist/reveal them ONLY in an officially finished match archive.
There is no wall order, future draw, seed, session token or AI search tree.
"""
from __future__ import annotations

from copy import deepcopy
from .ai import visible_tiles
from .efficiency import analyze_discards, effective_draws
from .rules import TILE_INDEX

def record_transition(game, new_events, before_hands, before_views):
    # Called after an authenticated action, only if public events were posted.
    result={"hands":[list(h) for h in game._hands]}
    discard=next((e for e in new_events if e.get("type")=="discard"),None)
    if discard:
        seat=discard["seat"]
        pre=before_views[seat]
        result["decision"]={
            "seat":seat,"played":discard["tile"],
            "hand":list(before_hands[seat]),
            "melds":deepcopy(pre["own_melds"]),
            "missing":pre["missing_suits"][seat],
            "visible":visible_tiles(pre),
        }
    return result

def _rank(one):
    hand, melds, missing, visible = (
        one["hand"],one["melds"],one["missing"],one["visible"])
    if missing not in ("m","p","s") or len(hand)+3*len(melds)!=14:
        return {"status":"not_applicable","top_three":[],"optimal":None}
    forced=sorted({t for t in hand if t[0]==missing},
                  key=TILE_INDEX.__getitem__)
    if forced:
        rows=[]
        for tile in forced:
            after=list(hand);after.remove(tile)
            result=effective_draws(after,melds,missing,[*visible,tile])
            rows.append({"discard":tile,**result})
        rows.sort(key=lambda x:(x["shanten"],-x["effective_tile_count"],
                               TILE_INDEX[x["discard"]]))
        best=(rows[0]["shanten"],rows[0]["effective_tile_count"])
        for row in rows:
            row["local_optimal"]=(row["shanten"],row["effective_tile_count"])==best
    else:
        result=analyze_discards(hand,melds,missing,visible)
        if result["status"]!="choose_discard":
            return {"status":"winning_hand","top_three":[],"optimal":None}
        rows=result["candidates"]
    played=one["played"]
    good=[r["discard"] for r in rows if r["local_optimal"]]
    top=[{"discard":r["discard"],"shanten":r["shanten"],
          "effective_tile_count":r["effective_tile_count"],
          "optimal":r["local_optimal"]} for r in rows[:3]]
    return {"status":"analyzed","top_three":top,
            "optimal":played in good,
            "played_rank":next((i+1 for i,r in enumerate(rows)
                                if r["discard"]==played),None),
            "optimal_ties":good}

def completed_review(rows: list[dict], *, maximum=2048,
                     opening_hands=None):
    """Validate private review data before a completed archive exposes it."""
    if type(rows) is not list or len(rows)>maximum:
        raise ValueError("invalid completed replay frame count")
    all_frames=[]; decisions=[]; evaluated=0; compliant=0
    for index, frame in enumerate(rows):
        hands=frame.get("hands")
        if (type(hands) is not list or len(hands)!=4
                or any(type(h) is not list or len(h)>14 or
                       any(type(t) is not str or t not in TILE_INDEX for t in h)
                       for h in hands)):
            raise ValueError("invalid completed four-seat hands")
        all_frames.append({"hands":[list(h) for h in hands]})
        before=frame.get("decision")
        if before is None:continue
        seat=before.get("seat")
        tile=before.get("played")
        if type(seat) is not int or seat not in range(4) or tile not in TILE_INDEX:
            raise ValueError("invalid completed discard")
        if (type(before.get("hand")) is not list or
                len(before["hand"])>14 or tile not in before["hand"]):
            raise ValueError("invalid pre-discard actual hand")
        assessed=_rank(before)
        row={"step_index":index,"seat":seat,"played":tile,
             "before_hand":list(before["hand"]),**assessed}
        decisions.append(row)
        if seat==0 and assessed["optimal"] is not None:
            evaluated+=1
            compliant+=int(assessed["optimal"])
    opening=None
    if opening_hands is not None:
        if (type(opening_hands) is not list or len(opening_hands)!=4
                or any(type(h) is not list or len(h)>14 or
                       any(type(t) is not str or t not in TILE_INDEX for t in h)
                       for h in opening_hands)):
            raise ValueError("invalid completed opening four-seat hands")
        opening=[list(h) for h in opening_hands]
    return {"availability":"complete_post_round",
            "opening_hands":opening,
            "frames":all_frames,"decisions":decisions,
            "player0":{"compared":evaluated,"optimal":compliant,
                       "rate":round(100*compliant/evaluated,2)
                       if evaluated else None},
            "scope":"only_archived_completed_rounds_no_live_hands"}
