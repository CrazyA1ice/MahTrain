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
    this.hidden=false;this.handlers={};this.href="";this.download="";
    this.classes=new Set();
    this.classList={add:name=>this.classes.add(name)};
  }
  append(child){this.children.push(child)}
  replaceChildren(...children){this.children=[...children]}
  addEventListener(event,handler){this.handlers[event]=handler}
}
const ids=[
  "match-archives-refresh","match-archives-list","match-archives-summary",
  "match-archives-detail","match-archives-compare","match-archives-export",
  "match-archives-board","match-archives-seat","match-archives-action",
  "match-archives-message","match-archives-comparison",
  "match-archives-title","match-archives-detail-summary",
  "match-archives-balances","match-archives-wins",
  "match-archives-count","match-archives-actions",
];
const dom=Object.fromEntries(ids.map(id=>[id,new Node()]));
dom["match-archives-seat"].value="all";
dom["match-archives-action"].value="all";
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
const fetch=async url=>{
  requests.push(url);
  const data=url.includes("archive_id=")?result:{
    matches:[
      {archive_id:"savedA",created_at:"2026-10-17T00:00:00Z",
       phase:"finished",win_b0:-16,settled_b0:-8,win_count:1},
      {archive_id:"savedB",created_at:"2026-10-16T00:00:00Z",
       phase:"wall_exhausted",win_b0:8,settled_b0:18,win_count:0},
    ],
    summary:{games:2,average_player0_win_balance:-4,
      average_player0_settled_balance:5,paid_wins:1},
  };
  return {ok:true,json:async()=>data};
};
const win={MahTrainPlayback:require("../web/match_playback.js")};
const context={document:{
  getElementById:id=>{
    assert.ok(dom[id],"missing archive DOM id "+id);return dom[id];
  },
  createElement:tag=>new Node(tag),
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
  console.log("M3.22 SQLite archive browser, two-game comparison, reopen and privacy: PASS");
})().catch(error=>{console.error(error);process.exitCode=1});
