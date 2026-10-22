"""Real MahTrain full-round HTTP integration: NO private wall/AI hand access.

Runs normal browser-equivalent actions against the running Python web_server,
then saves the terminal token and exact authoritative score ledger for the
real Chromium Majiang UI to restore and audit. No fixture game states.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))
from mahtrain_core.ai import MahjongAgent

ORIGIN=os.environ.get("MAHTRAIN_TEST_ORIGIN","http://127.0.0.1:8765")
EVIDENCE=Path("/tmp/mahtrain-classic-authenticated-round.json")

def post(payload: dict) -> dict:
    data=json.dumps(payload,ensure_ascii=False).encode("utf8")
    req=Request(ORIGIN+"/api/action",data=data,method="POST",headers={
        "Content-Type":"application/json","X-MahTrain":"1",
    })
    try:
        with urlopen(req,timeout=35) as response:
            return json.load(response)
    except HTTPError as exc:
        msg=exc.read().decode("utf8",errors="replace")
        raise AssertionError(f"HTTP {exc.code}: {msg[:900]}, action={payload['action']}") from exc

def exchange_tiles(hand: list[str]) -> list[str]:
    for suit in "msp":
        found=[tile for tile in hand if tile[0]==suit]
        if len(found)>=3:
            return found[:3]
    raise AssertionError("no legal three-of-suit exchange in real initial hand")

def missing_suit(hand:list[str]) -> str:
    # Prefer to eliminate the fewest remaining cards, deterministic and legal.
    return min("msp",key=lambda s:(sum(x[0]==s for x in hand),"msp".index(s)))

def next_human(view:dict, human:MahjongAgent) -> dict:
    phase=view["phase"]
    if phase in ("dealer_discard","await_discard") and view["turn"]==0:
        if view["can_self_draw_win"]:
            return {"action":"match_win"}
        if view.get("kong_options"):
            k=view["kong_options"][0]
            return {"action":"match_kong","kind":k["type"],"tile":k["tile"]}
        hand=view["hand"]
        missing=view["missing_suits"][0]
        cut=human.discard(view)
        assert cut in hand, "authorized human AI must choose a tile in its own hand"
        drawn=view.get("drawn_tile")
        return {"action":"match_discard","tile":cut,
                "from_draw":cut==drawn}
    if phase in ("claim_window","rob_kong_window"):
        pending=view["pending_discard"] if phase=="claim_window" else view["pending_rob_kong"]
        options=view["claim_options"] if phase=="claim_window" else view["rob_options"]
        if pending and pending["seat"]!=0 and options and (
            0 not in view.get("claim_submitted",[])
        ):
            # HU always has priority; a deterministic simulated human otherwise
            # passes to avoid inventing a fake response.
            selected="hu" if "hu" in options else "pass"
            return {"action":"match_claim" if phase=="claim_window" else
                    "match_rob","choice":selected}
    if view.get("needs_continue"):
        return {"action":"match_continue"}
    raise AssertionError(f"Unresolvable turn: phase={phase}, turn={view.get('turn')}, "
                         f"claim={view.get('claim_options')}, rob={view.get('rob_options')}")

def verify_ledger(view:dict) -> None:
    win=view["win_ledger"]
    kong=view["kong_ledger"]
    draw=view["exhaustive_settlement"]
    expected=[
        win["balances"][i]+kong["balances"][i]+(
            draw["balances"][i] if draw is not None else 0)
        for i in range(4)
    ]
    assert expected==view["settled_balances"],(expected,view["settled_balances"])
    assert sum(expected)==0,expected
    assert win["zero_sum"] and kong["zero_sum"]
    if draw is not None:
        assert draw["posted"] is True,draw
        assert sum(draw["balances"])==0
    for row in win["wins"]:
        assert row["total_received"]==len(row["payers"])*row["amount_per_payer"]
        assert row["effective_fan"] <= row["raw_fan"]
        assert len(set(row["payers"])) == len(row["payers"])
    for row in kong["events"]:
        if row["status"]=="voided":
            # A reversal must appear as a posted opposite-sign transaction.
            if row["amount_per_payer"] is not None:
                related=[x for x in kong["entries"] if x["kong_id"]==row["id"]]
                assert len([x for x in related if x["kind"]=="reversal"])==len(row["payers"])

def verify_privacy(view:dict) -> None:
    assert view["seat"]==0
    for disallowed in ("wall","future_wall","ai_private_hands","opponent_hands"):
        assert disallowed not in view,disallowed
    assert len(view["hand_counts"])==4 and len(view["hand"])<=14
    assert len(view["melds"])==4

def finish_round(seed:int, level:str="basic") -> tuple[dict,dict,list[dict]]:
    human=MahjongAgent("advanced",seed=seed,seat=0)
    created=post({"action":"match_new","seed":seed,
                  "ai_levels":[level,level,level],
                  "self_draw_mode":"add_base","kong_base":100})
    token=created["match_token"]
    view=created["match"]
    record=[{"phase":view["phase"],"action":"match_new","events":[]}]
    verify_privacy(view)
    response=post({"action":"match_exchange","match_token":token,
                   "tiles":exchange_tiles(view["hand"])})
    view=response["match"]
    assert view["phase"]=="missing_select",view["phase"]
    response=post({"action":"match_missing","match_token":token,
                   "suit":missing_suit(view["hand"])})
    view=response["match"]
    assert view["phase"] in ("dealer_discard","await_discard","await_draw")
    start=time.monotonic()
    visible={}
    seen_kinds={}
    hint_checked=False
    for step in range(450):
        if view["phase"] in ("finished","wall_exhausted"):
            break
        assert time.monotonic()-start<170, f"seed={seed} timed out at step={step}"
        if (not hint_checked and view["phase"] in
                ("dealer_discard", "await_discard") and view["turn"]==0
                and not view["won"][0]):
            stable=post({"action":"match_resume","match_token":token})["match"]
            hint_result=post({"action":"match_hint","match_token":token})
            hint=hint_result["hint"]
            assert hint_result["match_token"]==token
            assert "match" not in hint_result
            assert hint["status"] in ("choose_discard","already_winning")
            if hint["status"]=="choose_discard":
                assert hint["candidates"]
                for row in hint["candidates"]:
                    assert row["discard"] in view["hand"]
                    assert row["effective_tile_count_upper_bound"]>=0
                    assert all(item["unknown_copies_upper_bound"] in (1,2,3,4)
                               for item in row["effective_details"])
                miss=view["missing_suits"][0]
                if any(x[0]==miss for x in view["hand"]):
                    assert all(x["discard"][0]==miss
                               for x in hint["candidates"])
            assert "opponent_hands" not in hint
            assert "wall" not in hint
            after=post({"action":"match_resume","match_token":token})["match"]
            for field in ("phase","turn","hand","wall_count","discards",
                          "win_ledger","kong_ledger"):
                assert after[field]==stable[field],field
            hint_checked=True
            print("REAL AUTHORIZED HINT HTTP: PASS",{
                "seed":seed,"status":hint["status"],
                "candidates":len(hint["candidates"]),
            },flush=True)
        cmd=next_human(view,human)
        response=post({"match_token":token,**cmd})
        view=response["match"]
        verify_privacy(view)
        frames=view.get("public_steps",[])
        for frame in frames:
            for ev in frame.get("events",[]):
                kind=ev["type"]
                seen_kinds[kind]=seen_kinds.get(kind,0)+1
                if kind=="win_settlement":
                    assert "hand" not in ev and "future_wall" not in ev
        # Public response frames cannot contain any additional AI-private views.
        assert isinstance(frames,list)
        if cmd["action"]!="match_continue" or any(
            x["type"] in ("ron","multi_ron","rob_kong","self_draw_win","peng",
                         "an_gang","ming_gang","bu_gang")
            for f in frames for x in f.get("events",[])
        ):
            record.append({"phase":view["phase"],"action":cmd["action"],
                           "events":[e["type"] for f in frames
                                     for e in f.get("events",[])]})
    else:
        raise AssertionError(f"seed={seed} did not terminate after 450 server actions")
    assert hint_checked,"real game never reached a seat-zero legal hint decision"
    verify_ledger(view)
    assert view["wall_count"]==0 or sum(view["won"])>=3
    assert view["match_archive_id"] is not None
    assert seen_kinds.get("discard",0)>0
    # M3.88: terminal archive has genuine 4-hand snapshots unavailable
    # to any in-progress bearer-token view.
    assert "terminal_review" not in view
    with urlopen(ORIGIN+"/api/match_archives?archive_id="+
                 view["match_archive_id"],timeout=35) as response:
        archived=json.load(response)["report"]
    detail=archived.get("terminal_review")
    assert detail is not None,"missing terminal review from real HTTP game"
    assert len(detail["opening"])==4
    assert sum(map(len,detail["opening"]))==53
    assert all(len(row["hands_after"])==4 for row in detail["steps"])
    cuts=[row["cut_review"] for row in detail["steps"]
          if row.get("cut_review") is not None]
    actual=sum(e.get("type")=="discard" and e.get("seat")==0
               for row in detail["steps"] for e in row["events"])
    assert len(cuts)==actual,(len(cuts),actual)
    assert cuts,"finished game must record at least one human cut"
    assert all(len(row["top3"])<=3 for row in cuts)
    assert all(row["cut_review"]["discard"] in row["hands_before"][0]
               for row in detail["steps"] if row.get("cut_review") is not None)
    print("REAL COMPLETED GAME FOUR-HAND HISTORY/TOP3: PASS",{
        "seed":seed,"steps":len(detail["steps"]),"human_cuts":len(cuts),
        "optimal":sum(row["optimal"] for row in cuts)},flush=True)
    return {"seed":seed,"level":level,"token":token,"steps":step,
            "events":seen_kinds,"match_archive_id":view["match_archive_id"],
            "win_count":len(view["win_ledger"]["wins"]),
            "kong_count":len(view["kong_ledger"]["events"])},view,record

def main():
    completed=[]
    # Two quick ordinary games catch complete no-Hu / full-wall payment cases.
    for seed in (8407,8419):
        summary,view,record=finish_round(seed)
        completed.append((summary,view,record))
        # The bearer match token is needed by the next Chromium step, but
        # must stay in the private /tmp evidence file, NEVER in public CI logs.
        safe_summary={k:v for k,v in summary.items()
                      if k not in ("token","match_archive_id")}
        print("REAL HTTP COMPLETED",json.dumps(
            safe_summary,ensure_ascii=False),flush=True)
    # Broaden coverage by using LEGAL advanced AI decisions for both the
    # human and opponents; still only sees seat-zero authorized private view.
    # Stop after the first genuine posted Hu, or after six honest attempts.
    for seed in (137,420,2026,1777,65,999):
        if any(x[0]["win_count"] for x in completed):
            break
        summary,view,record=finish_round(seed,level="advanced")
        completed.append((summary,view,record))
        print("REAL HTTP COMPLETED",json.dumps(summary,ensure_ascii=False),flush=True)
    chosen=max(completed,key=lambda x:(
        x[0]["win_count"]>0, x[0]["win_count"],x[0]["kong_count"]))
    summary,view,record=chosen
    payload={"summary":summary,"token":summary["token"],
             "terminal":view,"sequence":record,
             "all_runs":[x[0] for x in completed]}
    EVIDENCE.write_text(
        json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf8")
    print("FULL ROUND REAL WIN COVERAGE:", "covered" if summary["win_count"] else
          "not_observed_in_the_tested_seeds",flush=True)
    print("AUTHENTIC FULL ROUND FINAL AUDIT: PASS, seed=",summary["seed"],
          "terminal=",view["phase"],"win_count=",summary["win_count"],
          "kong_count=",summary["kong_count"],flush=True)

if __name__=="__main__":
    main()
