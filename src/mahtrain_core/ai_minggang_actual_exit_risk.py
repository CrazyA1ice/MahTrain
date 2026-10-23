"""M4.10 offline pre-tail-vs-actual-post-tail Ming-Gang cut audit.

No future wall or other player's hand is read. The AFTER-tail observation
is the acting player's own authorized discard view, collected only once the
replacement has truly been drawn and the baseline AI actually chose its cut.
This is NOT a claim that the pre-tail heuristic predicts a Ron probability.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from .ai import MahjongAgent
from .ai_action_extended_study import _fixed_lineup
from .ai_challenge_call_kong_ablation import _official_outcome
from .ai_minggang_ledger_followthrough import MingGangFollowThroughAgent
from .ai_minggang_prospective_strata import reconcile_prospective_risk, risk_band
from .ai_table_read import read_discard_threat
from .ai_tournament import simulate_match

PROTOCOL = "m410_actual_supplement_exit_cut_public_risk_v1"
SEEDS_PER_COHORT = 8
BANDS = ("low", "mid", "high")


class AfterTailCutObserver(MingGangFollowThroughAgent):
    """Shadow-only agent: inherited challenge picks ALL actions verbatim."""

    def __init__(self, *, seed: int, seat: int) -> None:
        super().__init__(seed=seed, seat=seat)
        self._after_tail_exits: list[dict[str, Any]] = []

    def discard(self, view: Mapping[str, Any]) -> str:
        # Choose FIRST using the exact baseline policy. The separate
        # diagnostic after the choice cannot change any ranking or action.
        tile = super().discard(view)
        events = view.get("events") or []
        if not (len(events) >= 3
                and events[-1].get("type") == "kong_supplement"
                and events[-1].get("seat") == self.seat
                and events[-2].get("type") == "ming_gang"
                and events[-2].get("seat") == self.seat
                and events[-3].get("type") == "discard"):
            return tile
        claim = events[-3]
        if (events[-2].get("source") != claim.get("seat") or
                type(claim.get("index")) is not int or claim["index"] < 1):
            raise RuntimeError("actual supplement mismatches claimed discard")
        discards = view.get("discards") or []
        if not isinstance(discards, list):
            raise ValueError("cannot observe post-tail cut without public river")
        report = read_discard_threat(tile,view)
        # An aggregate-only private snapshot. No tile identity, drawn tile,
        # opponent hand, future wall, or per-opponent details survive.
        self._after_tail_exits.append({
            "claim_discard_index":claim["index"],
            "post_discard_index":len(discards)+1,
            "risk_index":report["risk_index"],
        })
        return tile


def reconcile_after_tail_cuts(
    observer: AfterTailCutObserver, outcome: Mapping[str, Any],
    board: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify every observed actual exit against terminal public authority.

    The post-tail diagnostic is collected only for a real baseline cut.
    A Ming-Gang with immediate self-draw win or subsequent Kong does not
    have a corresponding post-Kong discard: do NOT invent an exit.
    """
    prospective = reconcile_prospective_risk(observer,outcome,board)
    events = outcome["public_events"]
    ledger = board["kong_ledger"]["events"]
    discards = board["discards"]
    seen: set[int] = set()
    obs_by_idx = {}
    for observation in observer._after_tail_exits:
        claim_idx = observation["claim_discard_index"]
        if type(claim_idx) is not int or claim_idx in seen:
            raise RuntimeError("duplicate or invalid post-tail claim index")
        seen.add(claim_idx)
        obs_by_idx[claim_idx] = observation
    pre_by_idx = {e["discard_index"]:e for e in observer._dual_windows}
    if len(pre_by_idx) != len(observer._dual_windows):
        raise RuntimeError("duplicate prospective dual offer")
    counts: Counter[str] = Counter()
    minggang_refs = []
    ordinal = 0
    for n,e in enumerate(events):
        if e.get("type") not in ("ming_gang","an_gang","bu_gang"):
            continue
        if ordinal >= len(ledger):
            raise RuntimeError("missing authoritative Kong transaction")
        official = ledger[ordinal]
        ordinal += 1
        if e.get("type")!="ming_gang" or e.get("seat") != observer.seat:
            continue
        if n==0 or events[n-1].get("type")!="discard":
            raise RuntimeError("own actual Ming-Gang missing source discard")
        claim_index=events[n-1].get("index")
        if claim_index not in pre_by_idx:
            raise RuntimeError("actual own Ming-Gang missing prospective observation")
        if (official.get("type")!="ming_gang" or
                official.get("seat") != observer.seat or
                official.get("source") != e.get("source")):
            raise RuntimeError("physical Kong and official Kong disagreed")
        ref = official.get("id")
        exits = [x for x in discards if x.get("after_kong") is True
                 and x.get("kong_id") == ref]
        if len(exits) > 1:
            raise RuntimeError("Kong references two after-tail discards")
        if exits:
            exit_ = exits[0]
            observed=obs_by_idx.pop(claim_index,None)
            if (observed is None or
                    observed["post_discard_index"] != exit_.get("index") or
                    exit_.get("seat") != observer.seat):
                raise RuntimeError("missing/mismatched authorized actual cut")
            pre = risk_band(pre_by_idx[claim_index]["pre_tail_min_threat"])
            post = risk_band(observed["risk_index"])
            ron = bool(exit_.get("won_by"))
            if (official["status"] == "voided") != ron:
                raise RuntimeError("refund does not match actual Ron on exit")
            counts["real_exits"] += 1
            counts["pre_"+pre+"_exits"] += 1
            counts["post_"+post+"_exits"] += 1
            counts["transition_"+pre+"_to_"+post] += 1
            counts["upshift"] += int(BANDS.index(post) > BANDS.index(pre))
            counts["downshift"] += int(BANDS.index(post) < BANDS.index(pre))
            counts["same_band"] += int(pre==post)
            counts["ron"] += int(ron)
            counts["post_"+post+"_ron"] += int(ron)
            counts["ron_winners"] += len(exit_.get("won_by") or [])
            counts["risk_index_milli_total"] += round(observed["risk_index"]*1000)
        else:
            counts["awarded_without_exit"] += 1
        minggang_refs.append(ref)
    if ordinal != len(ledger) or obs_by_idx:
        raise RuntimeError("orphan actual Kong or extra unplayed diagnostic")
    if len(set(minggang_refs)) != len(minggang_refs):
        raise RuntimeError("reused actual authoritative Kong id")
    if (counts["real_exits"] != prospective.get("after_kong_discard",0)
            or counts["ron"] != prospective.get("actual_ron",0)
            or counts["ron_winners"] != prospective.get("actual_ron_winners",0)
            or counts["awarded_without_exit"] != prospective.get(
                "awarded_without_exit_discard",0)
            or counts["real_exits"] + counts["awarded_without_exit"]
                != prospective.get("awarded",0)):
        raise RuntimeError("post-tail actions diverge from official Kong lifecycle")
    if (counts["real_exits"] != counts["upshift"] +
            counts["downshift"] + counts["same_band"] or
            counts["real_exits"] != sum(counts["post_"+b+"_exits"] for b in BANDS)):
        raise RuntimeError("risk transitions do not account for all actual cuts")
    return {
        "post_tail_counts":dict(counts),
        "pre_tail_counts":prospective,
        "readiness":{
            "calibrated_ron_probability":None,
            "matched_policy_causal_net_gain":None,
        },
    }


def natural_position(seed: int, rotation: int) -> dict[str, Any]:
    if (type(seed) is not int or not 0 <= seed < 2**32 or
            type(rotation) is not int or rotation not in range(4)):
        raise ValueError("invalid seed/seat rotation")
    lineup,seat=_fixed_lineup(rotation)
    agent=AfterTailCutObserver(seed=seed,seat=seat)
    reference={}

    def remember_authority(game:Any)->None:
        reference["game"]=game

    match=simulate_match(
        seed,rotation=rotation%3,lineup=lineup,
        offline_kong_base=1,offline_agent_overrides={seat:agent},
        offline_observer=remember_authority,
    )
    if ("game" not in reference or
            reference["game"].phase != match["terminal_phase"]):
        raise RuntimeError("terminal state was not captured")
    board=reference["game"].public_state()
    counts=reconcile_after_tail_cuts(agent,match,board)
    official=_official_outcome(match,seat,lineup)
    return {
        "seed":seed,"rotation":rotation,"challenge_seat":seat,
        "terminal_phase":match["terminal_phase"],
        "official":official,**counts,
    }


def cohort(start:int,seeds:int=SEEDS_PER_COHORT)->dict[str,Any]:
    if (type(start) is not int or type(seeds) is not int or
            not 0<=start<2**32 or not 1<=seeds<=12 or start+seeds>2**32):
        raise ValueError("bad consecutive independent seed range")
    rows=[natural_position(seed,rotation)
          for seed in range(start,start+seeds) for rotation in range(4)]
    totals={"pre_tail":Counter(),"post_tail":Counter()}
    clusters=[]
    for seed in range(start,start+seeds):
        group=[x for x in rows if x["seed"]==seed]
        if sorted(x["challenge_seat"] for x in group)!=list(range(4)):
            raise RuntimeError("one independent shuffle lacks four challenge seats")
        per=Counter()
        for p in group:
            totals["pre_tail"].update(p["pre_tail_counts"])
            totals["post_tail"].update(p["post_tail_counts"])
            per.update(p["post_tail_counts"])
        clusters.append({
            "seed":seed, "awarded":sum(x["pre_tail_counts"].get("awarded",0)
                                       for x in group),
            "real_exits":per["real_exits"],"ron":per["ron"],
            "upshift":per["upshift"],"downshift":per["downshift"],
            "same_band":per["same_band"],
        })
    pre,post=totals["pre_tail"],totals["post_tail"]
    if (post["real_exits"] > pre["awarded"] or
            post["ron"] > post["real_exits"] or
            post["real_exits"]+post["awarded_without_exit"]!=pre["awarded"]):
        raise RuntimeError("natural prospect-to-terminal totals do not reconcile")
    return {
        "independent_shuffle_seeds":seeds,
        "complete_games":len(rows),
        "four_seat_positions":len(rows),
        "pre_tail_counts":dict(pre),
        "post_tail_counts":dict(post),
        "per_seed":clusters,"positions":rows,
        "seeds_with_actual_exit":sum(c["real_exits"]>0 for c in clusters),
        "seeds_with_actual_ron":sum(c["ron"]>0 for c in clusters),
        "calibrated_ron_probability":None,
        "uncertainty_interval":None,
    }


def study(*,development:int=44000,holdout:int=45000,
          seeds:int=SEEDS_PER_COHORT)->dict[str,Any]:
    if (type(development) is not int or type(holdout) is not int or
            type(seeds) is not int or not 1<=seeds<=12 or
            not 0<=development<2**32 or not 0<=holdout<2**32 or
            max(development,holdout)+seeds>2**32 or
            (development<holdout+seeds and holdout<development+seeds)):
        raise ValueError("independent development/holdout blocks must not overlap")
    return {
        "protocol":PROTOCOL,"online_policy_modified":False,
        "development_seed_range":[development,development+seeds],
        "holdout_seed_range":[holdout,holdout+seeds],
        "development":cohort(development,seeds),
        "holdout":cohort(holdout,seeds),
        "limitations":[
            "Pre-tail is a proxy over existing-hand cuts only; actual supplement may change cut availability.",
            "Post-tail is an authorized view after seeing the REAL own supplement, not an oracle of the future at claim time.",
            "Public additive risk can exceed one; threshold bins are not P(Ron) forecasts.",
            "Only baseline-chosen and physically awarded Ming-Gang provides observed exits; no causal policy comparison exists.",
            "Four seat rotations share each initial shuffle; independent count is seeds, not games or exits.",
            "If no natural Ron occurs, absence of failures does not prove safety or calibrate a risk distribution.",
        ],
    }
