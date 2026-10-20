"""M3.86 matched actual-kong evaluation against frozen M3.85.

All timings run on the SAME authorized 108-tile observations with warmed
shared M3.81 caches. A separate instrumented pass records actual expensive
_call_outlook invocations; the timer excludes the mock instrument itself.
The synthetic tier test is in tests/, not a claimed performance measurement.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from statistics import mean, median
from time import perf_counter_ns
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"tests")]
from mahtrain_core.ai import _challenge_kong, _call_outlook, _cut_shanten, _own_view
from mahtrain_core.efficiency import shanten_13
from test_ai_calls import offer_kongs
from test_ai_kong_prune import offer_seven_pairs_disrupting_kong
from test_ai_kong_tiers import _m385_challenge_kong


def compare(samples=24,warmups=4):
    if type(samples) is not int or not 2<=samples<=500:
        raise ValueError("samples must be 2..500")
    if type(warmups) is not int or not 0<=warmups<=100:
        raise ValueError("warmups must be 0..100")
    rows=[]
    for label,maker in [
        ("two_actual_legal_concealed_kongs",offer_kongs),
        ("real_seven_pairs_regressing_kong",offer_seven_pairs_disrupting_kong),
    ]:
        game,seat,view=maker()
        saved=copy.deepcopy(view)
        hand,melds,missing=_own_view(view)
        allowed=[tile for tile in sorted(set(hand)) if tile[0]==missing]
        if not allowed:
            allowed=sorted(set(hand))
        best_cut=min(_cut_shanten(hand,melds,missing,t) for t in allowed)
        candidate_shanten=[]
        for choice in view["kong_options"]:
            remain=list(hand)
            extra=[dict(m) for m in melds]
            tile=choice["tile"]
            if choice["type"]=="an_gang":
                for _ in range(4):remain.remove(tile)
                extra.append({"type":"an_gang","tile":tile})
            elif choice["type"]=="bu_gang":
                remain.remove(tile)
                extra=[
                    {"type":"bu_gang" if m["type"]=="peng" and m["tile"]==tile
                     else m["type"],"tile":m["tile"]} for m in extra]
            candidate_shanten.append({"type":choice["type"],"tile":tile,
                                      "stage":shanten_13(remain,extra,missing)})
        latencies={"m385":[],"m386":[]}
        policies={"m385":_m385_challenge_kong,"m386":_challenge_kong}
        invocations={}
        for name,policy in policies.items():
            with patch("mahtrain_core.ai._call_outlook",wraps=_call_outlook) as calls:
                action=policy(view)
                invocations[name]={"action":action,"outlook_calls":calls.call_count}
        if invocations["m385"]["action"]!=invocations["m386"]["action"]:
            raise AssertionError("M3.86 changed the legal kong choice")
        for i in range(warmups+samples):
            versions=("m385","m386") if i%2==0 else ("m386","m385")
            for name in versions:
                begin=perf_counter_ns()
                decision=policies[name](view)
                elapsed=(perf_counter_ns()-begin)/1e6
                if decision!=invocations[name]["action"]:
                    raise AssertionError("different action in equal view")
                if i>=warmups:
                    latencies[name].append(elapsed)
            if view!=saved or game.debug_tile_counts()["total"]!=108:
                raise AssertionError("mutation or lost tile")
        rows.append({
            "scenario":label,"samples_each":samples,
            "best_cut_shanten":best_cut,"candidate_shanten":candidate_shanten,
            "m385_outlook_calls":invocations["m385"]["outlook_calls"],
            "m386_outlook_calls":invocations["m386"]["outlook_calls"],
            "same_action":True,"physical_tiles":108,
            "m385_median_ms":round(median(latencies["m385"]),6),
            "m386_median_ms":round(median(latencies["m386"]),6),
            "m385_mean_ms":round(mean(latencies["m385"]),6),
            "m386_mean_ms":round(mean(latencies["m386"]),6),
        })
    return {
        "protocol":"m386_same_observation_kong_priority_tier_v1",
        "warmups":warmups,"rows":rows,
        "caveat":("CPU microbench on selected real staged legal views; "
                  "not all matches, AI win rate, or official net score. "
                  "M3.86 gain needs mixed exact-stage viable candidates."),
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples",type=int,default=24)
    p.add_argument("--warmups",type=int,default=4)
    p.add_argument("--json-out",type=Path)
    args=p.parse_args()
    report=compare(args.samples,args.warmups)
    s=json.dumps(report,indent=2,ensure_ascii=False)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(s+"\n",encoding="utf-8")
    print(s)


if __name__=="__main__":
    main()
