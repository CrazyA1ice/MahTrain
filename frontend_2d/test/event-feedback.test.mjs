import test from "node:test";
import assert from "node:assert/strict";
import {liveActionCue,publicTileLabel} from "../src/event-feedback.mjs";
const empty={
 phase:"await_discard",win_ledger:{wins:[]},
};
const frame=(...events)=>[{events}];
test("actual public AI discard is localized, private tiles never echo",()=>{
 const steps=frame(
  {type:"draw",seat:3,privateTile:"m1",wall:["s3"]},
  {type:"discard",seat:3,tile:"p8",privateHand:["m4"]},
 );
 const cue=liveActionCue(steps,empty,empty);
 assert.deepEqual(cue.seats,[3]);
 assert.equal(cue.kind,"discard");
 assert.equal(cue.title,"3号AI 打出 八筒");
 assert.ok(!JSON.stringify(cue).includes("privateHand"));
 assert.ok(!JSON.stringify(cue).includes("wall"));
 assert.equal(publicTileLabel("z1"),"");
});
test("concealed or supplemental draw does not fabricate an action",()=>{
 assert.equal(liveActionCue(frame({type:"draw",seat:1}),empty,empty),null);
 assert.equal(liveActionCue([],empty,empty),null);
 assert.equal(liveActionCue(frame({type:"an_gang",seat:1}),empty,empty,true),null);
});
test("three public kong variants animate only the actual owning seat",()=>{
 for(const [action,phrase] of [
  ["an_gang","暗杠"],["ming_gang","明杠"],["bu_gang","补杠"]
 ]){
  const cue=liveActionCue(frame({type:action,seat:2,tile:"m6"}),
   empty,empty);
  assert.equal(cue.title,"2号AI "+phrase);
  assert.equal(cue.kind,"kong");
  assert.deepEqual(cue.seats,[2]);
 }
 const declared=liveActionCue(frame({type:"bu_gang_declared",seat:2}),
  empty,empty);
 assert.equal(declared,null,"unconfirmed add-kong is not a booked KONG");
});
test("peng animation belongs to claimant, not the discarding player",()=>{
 const cue=liveActionCue(frame({type:"peng",seat:1,source:3,tile:"s7"}),
  empty,empty);
 assert.equal(cue.kind,"peng");
 assert.deepEqual(cue.seats,[1]);
 assert.equal(cue.title,"1号AI 碰");
});
test("two actual winners get one multi-ron banner, exact patterns and totals",()=>{
 const current={phase:"await_draw",win_ledger:{wins:[
  {winner:0,main_pattern:"清一色",effective_fan:3,total_received:800,
   kind:"ron"},
  {winner:2,main_pattern:"对对胡",effective_fan:2,total_received:400,
   kind:"ron"},
 ]}};
 const steps=frame({type:"multi_ron",seats:[0,2],source:3,tile:"m5"});
 const cue=liveActionCue(steps,empty,current);
 assert.equal(cue.kind,"win");assert.deepEqual(cue.seats,[0,2]);
 assert.match(cue.title,/一炮多响.*自己、2号AI/);
 assert.match(cue.detail,/清一色.*\+800/);
 assert.match(cue.detail,/对对胡.*\+400/);
 assert.equal(liveActionCue(steps,current,current),null===undefined?null:
  liveActionCue(steps,current,current).kind&&"never");
});
test("a server-published win without ledger delta still displays event cue",()=>{
 const w=liveActionCue(frame({type:"self_draw_win",seat:1}),empty,empty);
 assert.equal(w.title,"1号AI 胡牌");
 assert.deepEqual(w.seats,[1]);
});
test("resume suppresses stale win and stale kong animations",()=>{
 const win={phase:"finished",win_ledger:{wins:[{
  winner:1,main_pattern:"清一色",effective_fan:2,total_received:400,kind:"ron",
 }]}};
 assert.equal(liveActionCue(frame({type:"an_gang",seat:1}),null,win,true),null);
});
