"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const {inspect,thirds}=require("../web/match_cut_quality.js");

const pick=(tile,shanten,copies,weighted=null,best=false)=>({
 tile,shanten,effective_copies:copies,fan_weighted:weighted,
 reference_best:best,
});
const decision=(top3,played,opt=false)=>({
 discard:played?.tile||"m9",optimal:opt,
 rank:opt?1:4,top3,played_candidate:played,
});

test("outside-top-three cut preserves real regressing shanten",()=>{
 const best=pick("m1",1,12,null,true);
 const chosen=pick("m9",2,16);
 const a=inspect(decision([best,pick("m2",1,11),pick("m3",1,10)],chosen));
 assert.equal(a.kind,"shanten");
 assert.equal(a.shantenGap,1);
 assert.equal(a.copyGap,null,"different shanten stages cannot claim an effective-draw loss");
 assert.match(a.text,/退向听 1/);
});

test("non-tenpai equal-stage explanation uses exact unknown-copy gap",()=>{
 const best=pick("m1",2,15,null,true);
 const chosen=pick("p9",2,7);
 const a=inspect(decision([best],chosen));
 assert.equal(a.kind,"ukeire");
 assert.equal(a.copyGap,8);
 assert.match(a.text,/少 8 张/);
});

test("tenpai fan ranking takes precedence over unknown copy count",()=>{
 const best=pick("m1",0,7,32,true);
 const chosen=pick("s7",0,10,27);
 const a=inspect(decision([best],chosen));
 assert.equal(a.kind,"weighted");
 assert.equal(a.weightedGap,5);
 assert.equal(a.copyGap,-3,
  "more copies can still give a worse fan-weighted tenpai score");
 assert.match(a.text,/可为负数/);
});

test("exact 0 and identical top-score keep parity, no invented loss",()=>{
 const best=pick("m1",0,11,33,true);
 const a=inspect(decision([best],best,true));
 assert.equal(a.kind,"optimal");
 assert.equal(a.shantenGap,0);
 assert.equal(a.copyGap,0);
 assert.equal(a.weightedGap,0);
});

test("old version 2 archive with rank >= 4 has no invented metrics",()=>{
 const best=pick("m1",1,15);
 const a=inspect({discard:"m9",rank:4,optimal:false,top3:[
   best,pick("m2",1,12),pick("m3",1,10)
 ]});
 assert.equal(a.kind,"unrated");
 assert.equal(a.measured,false);
 assert.equal(a.copyGap,null);
 assert.match(a.text,/无法计算/);
});

test("old archive where played was within top3 reuses genuine saved metrics",()=>{
 const best=pick("m1",1,15,null,true);
 const actual=pick("m3",1,11);
 const a=inspect({discard:"m3",optimal:false,rank:3,
   top3:[best,pick("m2",1,12),actual]});
 assert.equal(a.kind,"ukeire");
 assert.equal(a.copyGap,4);
});

test("three chronological phases handle partial and missing historical data",()=>{
 const base=pick("m1",1,12,null,true);
 const cuts=[
  decision([base],base,true),
  decision([base],pick("m9",2,14)),
  decision([base],pick("m8",1,10)),
  {discard:"m7",optimal:false,top3:[base]},
  decision([base],base,true),
  decision([base],base,true),
 ];
 const report=thirds(cuts);
 assert.deepEqual(report.map(x=>x.total),[2,2,2]);
 assert.deepEqual(report.map(x=>x.optimal),[1,0,2]);
 assert.equal(report[0].regressed,1);
 assert.equal(report[1].ukeireLoss,1);
 assert.equal(report[1].unrated,1);
 assert.deepEqual(thirds([]).map(x=>x.total),[0,0,0]);
});

test("bad or unavailable reference never fabricates ranked probabilities",()=>{
 const a=inspect({discard:"m1",top3:[]});
 assert.equal(a.kind,"unrated");
 assert.equal(a.shantenGap,null);
 assert.equal(a.weightedGap,null);
});
