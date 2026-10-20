import test from "node:test";
import assert from "node:assert/strict";
import {claimDecision,ownKongChoices,tileLabel,seatLabel}
 from "../src/action-choice.mjs";
import {choiceAction} from "../src/bridge.mjs";

const base=()=>({
 seat:0,phase:"claim_window",pending_discard:{seat:3,tile:"p5"},
 claim_options:["pass","peng","ming_gang","hu"],claim_submitted:[],
 turn:3,
});
test("all original tile IDs are formatted in Chinese, without forging unknown tiles",()=>{
 assert.equal(tileLabel("m1"),"一万");
 assert.equal(tileLabel("p7"),"七筒");
 assert.equal(tileLabel("s9"),"九条");
 assert.equal(tileLabel("z4"),"未知牌");
 assert.equal(tileLabel(undefined),"未知牌");
 assert.equal(seatLabel(3),"3号AI");
 assert.equal(seatLabel(0),"自己");
});
test("one physical discard shows the actual source and ONLY Python-legal choices",()=>{
 const v=base(), before=structuredClone(v);
 const decision=claimDecision(v);
 assert.match(decision.title,/3号AI打出五筒/);
 assert.deepEqual(decision.choices.map(x=>x.key),["hu","ming_gang","peng","pass"]);
 assert.deepEqual(decision.choices.map(x=>x.command),[
  {action:"match_claim",choice:"hu"},
  {action:"match_claim",choice:"ming_gang"},
  {action:"match_claim",choice:"peng"},
  {action:"match_claim",choice:"pass"},
 ]);
 assert.equal(decision.choices[0].primary,true);
 assert.ok(decision.choices[3].explanation.includes("放弃"));
 assert.deepEqual(v,before,"UI adapter must not change server state");
});
test("rob-kong offers Hu/pass, never Peng or ming-gang",()=>{
 const v={...base(),phase:"rob_kong_window",
  pending_rob_kong:{seat:2,tile:"s8"},
  rob_options:["pass","hu"],claim_submitted:[]};
 const decision=claimDecision(v);
 assert.match(decision.title,/2号AI补杠八条/);
 assert.deepEqual(decision.choices.map(x=>x.key),["hu","pass"]);
 assert.deepEqual(decision.choices.map(x=>x.command),[
  {action:"match_rob",choice:"hu"},
  {action:"match_rob",choice:"pass"},
 ]);
});
test("already submitted rob-kong reply cannot be submitted twice",()=>{
 const v={...base(),phase:"rob_kong_window",
  pending_rob_kong:{seat:2,tile:"s8"},
  rob_options:["pass","hu"],claim_submitted:[0]};
 assert.equal(choiceAction(v,"claim",{option:"hu"}),null);
 assert.equal(choiceAction(v,"claim",{option:"pass"}),null);
 assert.equal(claimDecision(v),null);
});
test("source-self and pass-only windows never display a misleading choice",()=>{
 const v=base();
 v.pending_discard.seat=0;
 assert.equal(claimDecision(v),null);
 v.pending_discard.seat=3;
 v.claim_options=["pass"];
 assert.equal(claimDecision(v),null);
 v.claim_options=["hu","pass"];v.claim_submitted=[0];
 assert.equal(claimDecision(v),null);
});
test("self kong buttons distinguish An-gang and Bu-gang with Chinese names",()=>{
 const v={...base(),phase:"await_discard",turn:0,
  kong_options:[{type:"an_gang",tile:"m4"},{type:"bu_gang",tile:"p7"}]};
 assert.deepEqual(ownKongChoices(v).map(x=>x.label),["暗杠 四万","补杠 七筒"]);
 assert.deepEqual(ownKongChoices(v).map(x=>x.command),[
  {action:"match_kong",kind:"an_gang",tile:"m4"},
  {action:"match_kong",kind:"bu_gang",tile:"p7"},
 ]);
 v.turn=2;assert.deepEqual(ownKongChoices(v),[]);
 v.turn=0;v.kong_options=[];
 assert.deepEqual(ownKongChoices(v),[]);
});
