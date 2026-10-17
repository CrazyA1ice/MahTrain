"use strict";
/* M3.14 no-dependency DOM-level smoke test: real match.js, fake DOM only.
   The test never constructs an extra private-hand endpoint. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");

class Node {
  constructor(tag="div"){
    this.tagName=tag;this.children=[];this.className="";this.textContent="";
    this.attributes={};this.handlers={};this.disabled=false;this.hidden=false;
    this.value="";this.title="";
    this.classes=new Set();
    this.classList={
      add: name=>this.classes.add(name),
      toggle:(name,condition)=>{
        if(condition)this.classes.add(name);else this.classes.delete(name);
      },
      contains:name=>this.classes.has(name),
    };
  }
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=[...children];}
  setAttribute(name,value){this.attributes[name]=value;}
  addEventListener(type,fn){this.handlers[type]=fn;}
}
const ids=[
  "match-new","match-enable-kong","match-kong-base","match-seed",
  "match-coefficient","match-fan-cap","match-ai-1","match-ai-2","match-ai-3",
  "match-error","match-stage","match-title","match-status",
  "match-hand","match-controls","match-public","match-wall","match-wall-count",
  "match-self-melds","match-self-status","match-ready-hint","match-win-alert",
  "match-playback","match-playback-progress","match-playback-status",
  "match-playback-speed","match-playback-pause","match-playback-skip",
  "match-playback-note","match-motion","match-motion-text","match-motion-card",
  ...[0,1,2,3].flatMap(n=>["match-seat-"+n,"match-river-"+n])
];
const dom=Object.fromEntries(ids.map(id=>[id,new Node()]));
for(const id of ids)dom[id].id=id;
dom["match-seed"].value="42";
dom["match-coefficient"].value="100";
dom["match-fan-cap"].value="3";
dom["match-playback-speed"].value="450";
for(const n of [1,2,3])dom["match-ai-"+n].value="advanced";
const hand=["m1","m2","m3","m4","m5","m6","m7","s1","s2","s3","s4","s5","p1","p2"];
const base={
  phase:"await_discard",seat:0,turn:0,dealer:0,wall_count:54,
  exchange_direction:"clockwise",hand,hand_counts:[14,13,10,13],
  missing_suits:["p","s","p","m"],won:[false,false,false,false],
  melds:[[],[],[{type:"an_gang",tile:null}],
    [{type:"peng",tile:"p4"}]],
  own_melds:[],ai_opponents:[
    {seat:1,difficulty:"basic",description:"公开策略1"},
    {seat:2,difficulty:"advanced",description:"公开策略2"},
    {seat:3,difficulty:"challenge",description:"公开策略3"}
  ],
  discards:[
    {seat:1,tile:"m5"},
    {seat:2,tile:"s3",claimed_by:3},
    {seat:0,tile:"p1"},
  ],
  pending_discard:null,pending_rob_kong:null,can_self_draw_win:false,
  claim_options:[],rob_options:[],kong_options:[],
  tian_ting:null,ready_waits:[],ready_after_discards:[],drawn_tile:null,
  win_ledger:null,kong_ledger:null,exhaustive_review:null,
  winners:[],events:[]
};
const next={...base,wall_count:53,discards:[
  ...base.discards,{seat:0,tile:"m1"}
]};
let requests=[];
let startMatch=base,replyMatch=next;
const window={
  MahTrainUI:{
    tileName:tile=>tile,
    tileElement:(tile,opts)=>{
      const node=new Node("button");
      node.tile=tile;
      node.className="tile";
      if(opts.onClick)node.addEventListener("click",opts.onClick);
      return node;
    }
  }
};
const playbackModule=require("../web/match_playback.js");
window.MahTrainPlayback={
  normalize:playbackModule.normalize,
  createController:callbacks=>playbackModule.createController({
    ...callbacks,
    clock:(fn,delay)=>context.setTimeout(fn,delay),
    clearClock:id=>context.clearTimeout(id),
  }),
};
let timerIndex=0;
const pendingTimers=new Map();
const context={
  document:{createElement:tag=>new Node(tag),getElementById:id=>{
    assert.ok(dom[id],"missing required DOM id "+id);
    return dom[id];
  }},
  window,
  fetch:async (url,opts)=>{
    assert.equal(url,"/api/action");
    assert.equal(opts.method,"POST");
    const req=JSON.parse(opts.body);
    requests.push(req);
    return {ok:true,json:async()=>({match_token:"test-session",match:
      req.action==="match_new"?startMatch:replyMatch})};
  },
  confirm:()=>true,
  setTimeout:(fn,delay)=>{
    const id=++timerIndex;
    pendingTimers.set(id,{fn,delay});
    return id;
  },
  clearTimeout:id=>pendingTimers.delete(id),
  console,
};
const script=fs.readFileSync(path.join(__dirname,"../web/match.js"),"utf8");
vm.runInNewContext(script,context,{filename:"web/match.js"});
window.MahTrainMatch.init();
function visit(node,fn){
  fn(node);
  for(const child of node.children)if(child instanceof Node)visit(child,fn);
}
function descendants(node,test){
  const out=[];visit(node,x=>{if(test(x))out.push(x);});return out;
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));

(async()=>{
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(requests[0].action,"match_new");
  assert.equal(dom["match-stage"].hidden,false);
  assert.equal(dom["match-wall-count"].textContent,"54");
  assert.equal(dom["match-hand"].children.length,14);

  for(const n of [0,1,2,3]){
    assert.ok(dom["match-seat-"+n]);
    assert.ok(dom["match-river-"+n]);
  }
  const opponent=dom["match-seat-1"];
  assert.equal(descendants(opponent,x=>x.className==="match-tile-back").length,13);
  assert.equal(descendants(opponent,x=>x.tile!==undefined).length,0);

  // Concealed an-gang remains redacted even if melds are visible.
  const anonymous=dom["match-seat-2"];
  assert.equal(descendants(anonymous,x=>x.tile!==undefined).length,0);
  assert.equal(descendants(anonymous,x=>x.className==="match-tile-back").length,14);
  // Public peng remains visible as exactly three declared tile faces.
  const declared=dom["match-seat-3"];
  assert.equal(descendants(declared,x=>x.tile==="p4").length,3);

  const river=dom["match-river-2"];
  assert.equal(descendants(river,x=>x.tile==="s3").length,0,
    "claimed discard must not be duplicated as a physical tile in river");
  assert.equal(descendants(river,x=>x.className==="match-river-claimed").length,1);
  assert.equal(descendants(dom["match-river-0"],x=>x.tile==="p1").length,1);
  assert.equal(dom["match-seat-0"].classList.contains("is-active"),true);
  assert.equal(dom["match-seat-1"].classList.contains("is-active"),false);

  assert.equal(typeof dom["match-hand"].children[0].handlers.click,"function");
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(requests[1].action,"match_discard");
  assert.equal(requests[1].match_token,"test-session");
  assert.equal(requests[1].tile,"m1");
  assert.equal(requests[1].from_draw,false);
  assert.equal(dom["match-wall-count"].textContent,"53");
  assert.equal(descendants(dom["match-river-0"],x=>x.tile==="m1").length,1);

  // Same-valued physical copy: own old m1 and freshly drawn m1 must be
  // separate clickable cards. Only the far-right card is marked drawn.
  const duplicated=[...hand];duplicated[1]="m1";
  startMatch={...base,hand:duplicated,drawn_tile:"m1",
    ready_after_discards:[{discard:"m3",waits:["m6","s2"]}]};
  replyMatch={...next,drawn_tile:null,ready_waits:["p3","p6"],
    ready_after_discards:[],winners:[{seat:2,kind:"self_draw",source:2}],
    won:[false,false,true,false],
    discards:[...base.discards,{
      seat:0,tile:"m1",discard_kind:"tsumogiri"
    }]};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-hand"].children.length,14);
  const oldCopy=dom["match-hand"].children.find(x=>x.tile==="m1");
  const newCopy=dom["match-hand"].children.at(-1);
  assert.equal(newCopy.tile,"m1");
  assert.equal(newCopy.classList.contains("match-new-draw"),true);
  assert.equal(oldCopy.classList.contains("match-new-draw"),false);
  assert.ok(descendants(dom["match-ready-hint"],x=>x.tile==="m3").length);
  // Hand cut of an identical tile differs from a draw cut.
  oldCopy.handlers.click();
  await settle();
  assert.equal(requests.at(-1).from_draw,false);
  assert.equal(dom["match-win-alert"].hidden,false);
  assert.ok(descendants(dom["match-win-alert"],
    x=>x.textContent.includes("2号AI 自摸")).length);
  assert.equal(descendants(dom["match-ready-hint"],x=>x.tile==="p3").length,1);
  assert.equal(descendants(dom["match-river-0"],
    x=>x.className==="match-discard-kind" && x.textContent==="摸切").length,1);

  dom["match-new"].handlers.click();
  await settle();
  dom["match-hand"].children.at(-1).handlers.click();
  await settle();
  assert.equal(requests.at(-1).tile,"m1");
  assert.equal(requests.at(-1).from_draw,true);
  // M3.16: the server already completed the actual turn; only the new
  // public events play in the visual overlay, with private draw tile hidden.
  startMatch={...base,events:[{type:"missing_suits_revealed"}]};
  replyMatch={...next,events:[
    {type:"missing_suits_revealed"},
    {type:"draw",seat:1,tile:"secret-must-not-render"},
    {type:"discard",seat:1,tile:"p8",discard_kind:"tsumogiri"},
    {type:"an_gang",seat:2,tile:"secret-an-gang"},
    {type:"self_draw_win",seat:3},
  ]};
  dom["match-new"].handlers.click();
  await settle();
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(dom["match-playback"].hidden,false);
  assert.equal(dom["match-motion"].hidden,false);
  assert.ok(dom["match-motion-text"].textContent.includes("摸牌"));
  assert.equal(descendants(dom["match-motion-card"],
    x=>x.className==="match-tile-back").length,1);
  assert.equal(descendants(dom["match-motion-card"],x=>
    x.tile==="secret-must-not-render").length,0);
  assert.equal(dom["match-wall-count"].textContent,"54",
    "intermediate playback must not present invented historic wall counts");
  assert.equal(pendingTimers.size,1);

  dom["match-playback-pause"].handlers.click();
  assert.equal(pendingTimers.size,0);
  assert.equal(dom["match-playback-status"].textContent,"已暂停");
  dom["match-playback-speed"].value="180";
  dom["match-playback-speed"].handlers.change();
  dom["match-playback-pause"].handlers.click();
  assert.equal(pendingTimers.size,1);
  const scheduled=pendingTimers.entries().next().value;
  pendingTimers.delete(scheduled[0]);
  scheduled[1].fn();
  assert.ok(dom["match-motion-text"].textContent.includes("摸切"));
  assert.equal(descendants(dom["match-motion-card"],x=>x.tile==="p8").length,1);
  dom["match-playback-skip"].handlers.click();
  await settle();
  assert.equal(dom["match-motion"].hidden,true);
  assert.equal(dom["match-playback"].hidden,true);
  assert.equal(pendingTimers.size,0);
  assert.equal(dom["match-wall-count"].textContent,"53");
  assert.equal(dom["match-seat-1"].classList.contains("is-replay-acting"),false);
  // M3.17: each frame is an actual recorded post-rule-action public board.
  // Counts, wall, river and the opponent's publicly visible melds update
  // BEFORE the overall HTTP response reaches the final-state render.
  startMatch={...base,events:[],wall_count:54};
  const step1={
    phase:"await_discard",turn:1,wall_count:53,
    hand_counts:[13,14,10,13],won:[false,false,false,false],
    melds:base.melds,discards:base.discards,
  };
  const step2={
    ...step1,phase:"claim_window",hand_counts:[13,13,10,13],
    discards:[...base.discards,{
      seat:1,tile:"s5",discard_kind:"tedashi",
    }],
  };
  replyMatch={...next,wall_count:53,
    events:[{type:"draw",seat:1},{type:"discard",seat:1,tile:"s5"}],
    public_steps:[
      {events:[{type:"draw",seat:1,tile:"private-never-display"}],board:step1},
      {events:[{type:"discard",seat:1,tile:"s5",
        discard_kind:"tedashi"}],board:step2},
    ],
    discards:step2.discards,
  };
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-wall-count"].textContent,"54");
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(dom["match-wall-count"].textContent,"53",
    "first event must update real public wall count");
  assert.equal(descendants(dom["match-seat-1"],
    x=>x.className==="match-tile-back").length,14,
    "first real draw must increase AI concealed back count");
  assert.equal(descendants(dom["match-river-1"],x=>x.tile==="s5").length,0,
    "the discard must not render before its actual completed action");
  assert.ok(dom["match-seat-0"].classList.contains("is-public-replay"),
    "do not pretend the old own private hand is a true historical snapshot");
  assert.equal(descendants(dom["match-motion-card"],
    x=>x.tile==="private-never-display").length,0);
  assert.equal(pendingTimers.size,1);
  let nextTimer=pendingTimers.entries().next().value;
  pendingTimers.delete(nextTimer[0]);
  nextTimer[1].fn();
  assert.equal(descendants(dom["match-seat-1"],
    x=>x.className==="match-tile-back").length,13);
  assert.equal(descendants(dom["match-river-1"],x=>x.tile==="s5").length,1);
  assert.equal(dom["match-wall-count"].textContent,"53");
  dom["match-playback-skip"].handlers.click();
  await settle();
  assert.equal(dom["match-seat-0"].classList.contains("is-public-replay"),false);
  assert.equal(dom["match-wall-count"].textContent,"53");
  assert.equal(requests.at(-1).action,"match_discard");
  console.log("M3.17 real incremental wall/back/river DOM smoke: PASS");
  console.log("M3.16 live match public action playback DOM smoke: PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
