"use strict";
// M3.30 inspect public-only controlled-score DOM and CSV with no browser/network.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
class Node {
  constructor(tag="div") {
    this.tagName=tag;this.children=[];this.textContent="";this.className="";
    this.value="";this.checked=false;this.disabled=false;this.hidden=false;
    this.handlers={};this.style={};this.max="0";this.attributes={};
    this.classList={add(){}};
  }
  append(...items){this.children.push(...items)}
  replaceChildren(...items){this.children=[...items]}
  addEventListener(type,fn){this.handlers[type]=fn}
  setAttribute(k,v){this.attributes[k]=v}
  click(){this.clicked=true}
}
const ids=[
  "ai-replay-start","ai-replay-results","ai-replay-error","ai-replay-progress",
  "ai-replay-summary","ai-replay-terminations","ai-replay-match",
  "ai-replay-clusters","ai-replay-official-scores","ai-replay-official-download",
  "ai-replay-official-caveat","ai-replay-official-levels",
  "ai-replay-official-differences","ai-replay-seed","ai-replay-seeds",
  "ai-replay-detail","ai-replay-download","ai-replay-prev","ai-replay-next",
  "ai-replay-step","ai-replay-cluster-download","ai-replay-cluster-warning",
  "ai-replay-cluster-differences","ai-replay-cluster-table",
  "ai-replay-step-title","ai-replay-step-note","ai-replay-explanation-text",
  "ai-replay-board",
];
const dom=Object.fromEntries(ids.map(x=>[x,new Node()]));
dom["ai-replay-seed"].value="11";
dom["ai-replay-seeds"].value="1";
const names=["basic","advanced","challenge"];
const levels=Object.fromEntries(names.map(level=>[level,{
  win_events:1,seat_exposures:4,deal_in_events:0,
  discard_min_shanten_fraction:null,discard_local_optimal_fraction:null,
  mean_shanten_regret:null,
}]));
const official={
  protocol:"paired_initial_shuffle_3_rotation_official_a_v1",
  room_coefficient:100,fan_cap:3,requested_seeds:1,
  valid_seeds:1,excluded_seed_count:0,complete_games:3,
  per_seed:[{seed:11,levels:{
    basic:{seat_exposures:4,official_total:-120,official_mean_per_exposure:-30},
    advanced:{seat_exposures:4,official_total:0,official_mean_per_exposure:0},
    challenge:{seat_exposures:4,official_total:120,official_mean_per_exposure:30},
  }}],
  levels:{
    basic:{seat_exposures:4,official_total:-120,official_mean_per_exposure:-30},
    advanced:{seat_exposures:4,official_total:0,official_mean_per_exposure:0},
    challenge:{seat_exposures:4,official_total:120,official_mean_per_exposure:30},
  },
  paired_differences:{challenge_minus_basic:60,challenge_minus_advanced:30},
  intervals:null,interval_status:"insufficient_valid_independent_seeds_need_5",
};
const responses=[];
const fetch=async (_url,options)=>{
  const query=JSON.parse(options.body);
  responses.push(query.action);
  if(query.action==="ai_replay_start")
    return {ok:true,json:async()=>({replay_token:"public-only"})};
  if(query.action==="ai_replay_status")
    return {ok:true,json:async()=>({replay:{
      status:"done",completed_games:3,total_games:3,
      overview:{
        games:3,levels,official_score_analysis:official,seed_analysis:null,
        terminal_phase_counts:{finished:3,wall_exhausted:0},
        matches:[{index:0,seed:11,rotation:0,dealer:0,terminal_phase:"finished"}],
      },
    }})};
  if(query.action==="ai_replay_match")
    return {ok:true,json:async()=>({match:{
      seed:11,rotation:0,assignment:["basic","advanced","challenge","basic"],
      steps:[],
    }})};
  throw Error("unexpected fake route "+query.action);
};
let csv=null,clicked=false;
const win={MahTrainUI:{}};
const document={
  getElementById(id){
    assert.ok(dom[id],"missing M3.30 DOM id "+id);
    return dom[id];
  },
  createElement(tag){
    const obj=new Node(tag);
    if(tag==="a")obj.click=()=>{clicked=true};
    return obj;
  },
};
const FakeBlob=class{constructor(parts){csv=parts.join("")}};
const ctx={document,window:win,fetch,console,
  Blob:FakeBlob,URL:{createObjectURL:()=>"blob:fake",revokeObjectURL(){}},
  setTimeout(){}};
vm.runInNewContext(
  fs.readFileSync(path.join(__dirname,"../web/ai_replay.js"),"utf8"),
  ctx,{filename:"ai_replay.js"});
const settle=()=>new Promise(done=>setImmediate(done));
(async()=>{
  win.MahTrainAIReplay.init();
  dom["ai-replay-start"].handlers.click();
  for(let i=0;i<5;i++)await settle();
  assert.equal(dom["ai-replay-official-scores"].hidden,false);
  assert.equal(dom["ai-replay-official-levels"].children.length,3);
  assert.equal(dom["ai-replay-official-differences"].children.length,2);
  assert.ok(dom["ai-replay-official-caveat"].textContent.includes("已核验1个"));
  assert.ok(dom["ai-replay-official-caveat"].textContent.includes("少于5个"));
  assert.ok(dom["ai-replay-official-differences"].children[0].textContent.includes("+60"));
  assert.ok(dom["ai-replay-official-levels"].children[2].children[1]
    .children[2].children[1].textContent.includes("+30"));
  dom["ai-replay-official-download"].handlers.click();
  assert.ok(clicked);
  assert.ok(csv.includes("11,challenge,4,120,30"));
  assert.ok(csv.includes("11,basic,4,-120,-30"));
  assert.ok(!csv.includes("hidden"));
  assert.deepEqual(responses,["ai_replay_start","ai_replay_status","ai_replay_match"]);
  console.log("M3.30 controlled AI official scores, excluded-seed disclosure and public CSV: PASS");
})().catch(error=>{console.error(error);process.exitCode=1});
