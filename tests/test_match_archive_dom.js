"use strict";
// M3.22 test real read-only archive browser script against fake same-origin GET.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
class Node{
  constructor(tag="div"){
    this.tagName=tag;this.children=[];this.textContent="";
    this.className="";this.value="";this.checked=false;this.disabled=false;
    this.hidden=false;this.handlers={};this.href="";this.download="";this.style={};
    this.classes=new Set();
    this.classList={add:name=>this.classes.add(name)};
  }
  append(...children){this.children.push(...children)}
  replaceChildren(...children){this.children=[...children]}
  addEventListener(event,handler){this.handlers[event]=handler}
  setAttribute(key,value){(this.attributes||(this.attributes={}))[key]=String(value)}
}
const ids=[
  "match-archives-refresh","match-archives-list","match-archives-summary",
  "match-archives-period","match-archives-review-summary",
  "match-archives-detail","match-archives-compare","match-archives-export",
  "match-archives-board","match-archives-seat","match-archives-action",
  "match-archives-message","match-archives-comparison",
  "match-archives-title","match-archives-detail-summary",
  "match-archives-balances","match-archives-wins",
  "match-archives-count","match-archives-actions",
  "match-scorecard-status","match-scorecard-seats","match-scorecard-trend",
  "match-stats-metrics","match-stats-cumulative","match-stats-outcomes",
  "match-history-groups-mode","match-history-groups-status",
  "match-history-groups-rows",
];
const dom=Object.fromEntries(ids.map(id=>[id,new Node()]));
dom["match-archives-seat"].value="all";
dom["match-archives-period"].value="all";
dom["match-archives-action"].value="all";
dom["match-history-groups-mode"].value="ai";
const board=(n,wall,won)=>({
  phase:won?"finished":"await_discard",turn:1,wall_count:wall,
  hand_counts:[13,13,10,13],
  won:[false,won,false,false],
  melds:[[],[],[{type:"an_gang",tile:null}],[]],
  discards:n?[{seat:1,tile:"p6"}]:[],
});
const result={
  archive_id:"savedA",created_at:"2026-10-17T00:00:00Z",
  report:{
    privacy:"public_board_only",phase:"finished",dealer:0,truncated:0,
    opening:board(0,54,false),
    steps:[{events:[{type:"discard",seat:1,tile:"p6",
      private_tiles:["never-show"]}],board:board(1,53,false)},
      {events:[{type:"self_draw_win",seat:1},
        {type:"win_settlement",seat:1,effective_fan:1,amount:16}],
       board:board(1,52,true)}],
    win_ledger:{balances:[-16,16,0,0],
      wins:[{winner:1,kind:"self_draw",main_pattern:"平胡",
        effective_fan:1,total_received:16,payers:[0]}]},
    kong_balances:[0,0,0,0],
  },
};
const requests=[];
let overrideList=null;
const fetch=async url=>{
  requests.push(url);
  if(overrideList&&!url.includes("archive_id="))return overrideList(url);
  const data=url.includes("archive_id=")?result:{
    matches:[
      {archive_id:"savedA",created_at:"2026-10-17T00:00:00Z",
       phase:"finished",win_b0:-16,settled_b0:-8,win_count:1},
      {archive_id:"savedB",created_at:"2026-10-16T00:00:00Z",
       phase:"wall_exhausted",win_b0:8,settled_b0:18,win_count:0},
    ],
    summary:{games:2,average_player0_win_balance:-4,
      average_player0_settled_balance:5,paid_wins:1},
    scorecard:{
      valid_games:2,excluded_games:1,zero_sum:true,
      seats:[
        {seat:0,hu_total:-8,draw_total:18,settled_total:10,
         average_settled:5,positive_games:1,negative_games:1,zero_games:0},
        {seat:1,hu_total:8,draw_total:-18,settled_total:-10,
         average_settled:-5,positive_games:1,negative_games:1,zero_games:0},
        {seat:2,hu_total:0,draw_total:0,settled_total:0,
         average_settled:0,positive_games:0,negative_games:0,zero_games:2},
        {seat:3,hu_total:0,draw_total:0,settled_total:0,
         average_settled:0,positive_games:0,negative_games:0,zero_games:2},
      ],
      trend:[
        {archive_id:"savedA",created_at:"2026-10-16T10:00:00Z",
         score:-8,cumulative:-8},
        {archive_id:"savedB",created_at:"2026-10-17T10:00:00Z",
         score:18,cumulative:10},
      ],
      trend_limit:30,
      groupings:{
        ai_lineups:[{
          ai_levels:["basic","advanced","challenge"],games:2,
          settled_total:10,hu_total:-8,draw_total:18,
          average_settled:5,positive_games:1,negative_games:1,
          zero_games:0,normalized_games:1,
          average_per_coefficient:0.5,rules_variant_count:2,
          small_sample:true,
        }],
        room_rules:[{
          room_coefficient:100,fan_cap:3,games:1,
          settled_total:18,hu_total:8,draw_total:10,
          average_settled:18,positive_games:1,negative_games:0,
          zero_games:0,normalized_games:1,
          average_per_coefficient:0.18,rules_variant_count:1,
          small_sample:true,
        }],
        missing_ai_games:0,missing_rules_games:1,
      },
    },
  };
  return {ok:true,json:async()=>data};
};
const win={MahTrainPlayback:require("../web/match_playback.js"),
  MahTrainMatchStats:require("../web/match_stats.js")};
const context={document:{
  getElementById:id=>{
    assert.ok(dom[id],"missing archive DOM id "+id);return dom[id];
  },
  createElement:tag=>new Node(tag),
  createElementNS:(_,tag)=>new Node(tag),
},window:win,fetch,console};
vm.runInNewContext(
  fs.readFileSync(path.join(__dirname,"../web/match_archives.js"),"utf8"),
  context,{filename:"match_archives.js"});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  win.MahTrainMatchArchives.init();
  await settle();
  assert.equal(dom["match-archives-list"].children.length,2);
  assert.ok(dom["match-archives-summary"].textContent.includes("已保存 2 局"));
  assert.ok(dom["match-archives-summary"].textContent.includes("平均正式净额 5.0"));
  assert.ok(dom["match-archives-list"].children[0].children[1].textContent.includes("-8"));
  assert.equal(dom["match-scorecard-seats"].children.length,4);
  assert.ok(dom["match-scorecard-status"].textContent.includes("已核验 2 局"));
  assert.ok(dom["match-scorecard-status"].textContent.includes("排除1局"));
  assert.ok(dom["match-scorecard-seats"].children[0].children[1].textContent.includes("+10"));
  assert.ok(dom["match-scorecard-seats"].children[0].children[2].textContent.includes("胡牌 -8"));
  assert.equal(dom["match-scorecard-trend"].children.length,2);
  assert.equal(dom["match-stats-metrics"].children.length,4);
  assert.equal(dom["match-stats-metrics"].children[1].children[1].textContent,"+10");
  assert.equal(dom["match-stats-cumulative"].children[0].tagName,"svg");
  assert.equal(dom["match-stats-outcomes"].children.length,4);
  assert.equal(dom["match-stats-outcomes"].children[0].children[2].textContent,
    "1 局 · 50.0%");

  assert.equal(dom["match-scorecard-trend"].children[0].children[3].textContent,"-8");
  assert.equal(dom["match-scorecard-trend"].children[1].children[4].textContent,"累计 +10");
  assert.ok(dom["match-scorecard-trend"].children[0].children[1].children[0].style.width.endsWith("%"));
  assert.equal(dom["match-scorecard-trend"].children[1].children[2].children.length,1);
  assert.ok(!JSON.stringify(dom).includes("hidden-hand"));
  assert.equal(dom["match-history-groups-rows"].children.length,1);
  assert.ok(dom["match-history-groups-rows"].children[0].children[0]
    .textContent.includes("1号入门"));
  assert.ok(dom["match-history-groups-rows"].children[0].children[3]
    .textContent.includes("系数单位"));
  assert.ok(dom["match-history-groups-rows"].children[0].children[4]
    .textContent.includes("样本不足5局"));
  assert.ok(dom["match-history-groups-status"].textContent.includes("0局缺少"));
  dom["match-history-groups-mode"].value="rules";
  dom["match-history-groups-mode"].handlers.change();
  assert.equal(dom["match-history-groups-rows"].children.length,1);
  assert.ok(dom["match-history-groups-rows"].children[0].children[0]
    .textContent.includes("房间系数100"));
  assert.ok(dom["match-history-groups-status"].textContent.includes("1局缺少"));
  dom["match-history-groups-mode"].value="ai";
  dom["match-history-groups-mode"].handlers.change();
  assert.ok(dom["match-history-groups-status"].textContent.includes("按AI难度组合"));
  let rows=dom["match-archives-list"].children;
  rows[0].children[0].checked=true;rows[0].children[0].handlers.change();
  rows[1].children[0].checked=true;rows[1].children[0].handlers.change();
  assert.equal(dom["match-archives-compare"].disabled,false);
  assert.ok(dom["match-archives-comparison"].children
    .some(x=>x.textContent.includes("差额")));
  assert.ok(dom["match-archives-comparison"].children
    .some(x=>x.textContent.includes("-26")),
    "formal settled delta must include published exhaustive payments");
  assert.ok(dom["match-archives-comparison"].children
    .some(x=>x.textContent.includes("-24")),
    "original HU-only comparison remains separately visible");
  rows[0].children[2].handlers.click();
  await settle();
  assert.equal(dom["match-archives-detail"].hidden,false);
  assert.equal(dom["match-archives-actions"].children.length,3);
  assert.ok(dom["match-archives-board"].children.length>=2);
  assert.equal(dom["match-archives-balances"].children.length,4);
  assert.equal(dom["match-archives-export"].href,
    "/api/match_archives?archive_id=savedA");
  dom["match-archives-action"].value="win";
  dom["match-archives-action"].handlers.change();
  assert.equal(dom["match-archives-actions"].children.length,1);
  dom["match-archives-action"].value="all";
  dom["match-archives-action"].handlers.change();
  dom["match-archives-actions"].children[1].handlers.click();
  assert.ok(dom["match-archives-board"].children[0].textContent.includes("牌山53张"));
  assert.ok(!JSON.stringify(dom).includes("never-show"));
  assert.ok(requests.every(url=>url.startsWith("/api/match_archives")));
  // M3.89: a long genuine archived round must expose ALL saved public
  // transitions, not silently drop every step before the last 200.
  const originalSteps=result.report.steps;
  result.report.steps=Array.from({length:225},(_,i)=>({
    board:board(i+1,Math.max(0,54-Math.floor(i/5)),false),
    events:[{type:"discard",seat:1,tile:"p6"}],
  }));
  rows=dom["match-archives-list"].children;
  rows[0].children[2].handlers.click();
  await settle();
  assert.equal(dom["match-archives-actions"].children.length,226,
    "one opening board plus every 225 true saved transitions");
  assert.match(dom["match-archives-count"].textContent,/全部可追溯/);
  assert.match(dom["match-archives-actions"].children[1].textContent,/第2步/);
  dom["match-archives-actions"].children[1].handlers.click();
  assert.match(dom["match-archives-board"].children[0].textContent,/第2步/);
  result.report.steps=originalSteps;
  // M3.88 version-2 terminal archive: every seat's genuine archived tiles
  // become visible ONLY here, and an actual human discard has a top-three
  // explanation plus series-level optimal-cut compliance.
  const terminalHands=[
    ["m1","m2"],["p4","p5"],["s1","s2"],["m7","m8"]
  ];
  result.report.terminal_review={
    opening:terminalHands,
    scope:"terminal_replay_only",
    steps:[
      {hands_after:terminalHands,cut_review:{
        discard:"m1",rank:1,optimal:true,
        top3:[
          {tile:"m1",shanten:1,effective_copies:8,
           fan_weighted:null,reference_best:true},
          {tile:"m2",shanten:1,effective_copies:6,
           fan_weighted:null,reference_best:false},
          {tile:"p4",shanten:2,effective_copies:4,
           fan_weighted:null,reference_best:false},
        ],
      }},
      {hands_after:terminalHands},
    ],
  };
  rows=dom["match-archives-list"].children;
  rows[0].children[2].handlers.click();
  await settle();
  const collect=node=>[node.textContent||"",
    ...node.children.flatMap(collect)].join(" ");
  assert.match(collect(dom["match-archives-review-summary"]),/100\.0%/);
  dom["match-archives-action"].value="all";
  dom["match-archives-action"].handlers.change();
  dom["match-archives-actions"].children[1].handlers.click();
  const reviewText=collect(dom["match-archives-board"]);
  assert.match(reviewText,/1万/);
  assert.match(reviewText,/4筒/);
  assert.match(reviewText,/1条/);
  assert.match(reviewText,/切m1/);
  assert.match(reviewText,/切m2/);
  assert.match(reviewText,/切p4/);
  assert.match(reviewText,/有效张上界/);
  // M3.88: one period control governs server-side leaderboard, chart,
  // history list and the grouping totals. Never substitute stale all-time
  // aggregates after the selector changes.
  dom["match-archives-period"].value="month";
  dom["match-archives-period"].handlers.change();
  await settle();
  assert.ok(requests.at(-1).includes("period=month"));
  assert.ok(dom["match-archives-summary"].textContent.includes("最近一月"));
  dom["match-archives-period"].value="all";
  dom["match-archives-period"].handlers.change();
  await settle();
  assert.ok(requests.at(-1).includes("period=all"));
  // M3.47: simulate two rapid visits to history. The SLOW response
  // from the first request cannot replace the new SQLite scorecard.
  const baselineResponse=await fetch("/api/match_archives?limit=50");
  const baseline=await baselineResponse.json();
  const pending=[];
  overrideList=()=>new Promise(resolve=>pending.push(resolve));
  const slow=win.MahTrainMatchArchives.refresh();
  const fast=win.MahTrainMatchArchives.refresh();
  assert.equal(pending.length,2);
  const newest=JSON.parse(JSON.stringify(baseline));
  newest.summary.games=3;
  newest.scorecard.valid_games=3;
  pending[1]({ok:true,json:async()=>newest});
  await fast;
  assert.ok(dom["match-archives-summary"].textContent.includes("已保存 3 局"));
  assert.ok(dom["match-scorecard-status"].textContent.includes("已核验 3 局"));
  pending[0]({ok:true,json:async()=>baseline});
  await slow;
  assert.ok(dom["match-archives-summary"].textContent.includes("已保存 3 局"),
    "older delayed archive reply must not revert freshly loaded stats");
  assert.ok(dom["match-scorecard-status"].textContent.includes("已核验 3 局"));
  overrideList=null;
  console.log("M3.47 stale history chart response is ignored: PASS");
  console.log("M3.28 audited four-seat official scoreboard and recent net trend DOM: PASS");
  console.log("M3.22 SQLite archive browser, two-game comparison, reopen and privacy: PASS");
})().catch(error=>{console.error(error);process.exitCode=1});
