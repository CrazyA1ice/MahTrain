import test from "node:test";
import assert from "node:assert/strict";
import {seatOutcome} from "../src/seat-status.mjs";

test("ordinary unclaimed seats show no Hu marker",()=>{
 const state={won:[false,false,false,false],win_ledger:{wins:[]}};
 for(let seat=0;seat<4;seat++)assert.deepEqual(seatOutcome(state,seat),
  {won:false,label:"",detail:"",center:""});
});
test("AI Hu is permanent while game continues, with real pattern and method",()=>{
 const state={phase:"await_discard",won:[false,true,false,false],
  win_ledger:{wins:[{winner:1,kind:"self_draw",main_pattern:"seven_pairs",
    effective_fan:2,total_received:600}]}};
 const result=seatOutcome(state,1);
 assert.equal(result.label,"已胡");
 assert.match(result.detail,/自摸 · 七对 · 2番/);
 assert.match(result.center,/七对 2番/);
 assert.equal(seatOutcome(state,0).won,false);
 // A continued frame may keep the same posted win; never remove its badge.
 assert.deepEqual(seatOutcome({...state,phase:"claim_window"},1),result);
});
test("multi-winner and multi-record Hu retain independent seats",()=>{
 const state={won:[true,false,true,false],win_ledger:{wins:[
  {winner:0,kind:"ron",main_pattern:"pure_suit",effective_fan:3},
  {winner:2,kind:"rob_kong",main_pattern:"all_pungs",effective_fan:2},
 ]}};
 assert.match(seatOutcome(state,0).detail,/点炮胡 · 清一色/);
 assert.match(seatOutcome(state,2).detail,/抢杠胡 · 对对胡/);
 assert.equal(seatOutcome(state,1).won,false);
 assert.equal(seatOutcome(state,3).won,false);
});
test("posted won flag alone marks a player without inventing a Hu pattern",()=>{
 const result=seatOutcome({won:[false,false,false,true],win_ledger:{wins:[]}},3);
 assert.equal(result.won,true);
 assert.equal(result.label,"已胡");
 assert.equal(result.detail,"服务器已确认胡牌");
 assert.doesNotMatch(result.center,/七对|平胡|番/);
});
test("invalid seat refuses untrusted metadata",()=>{
 assert.throws(()=>seatOutcome({},-1),TypeError);
 assert.throws(()=>seatOutcome({},4),TypeError);
});
