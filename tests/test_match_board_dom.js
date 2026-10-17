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
  "match-own-score","match-table-settlement","match-table-settlement-title",
  "match-table-round-phase","match-table-scores","match-table-wins",
  "match-table-score-note","match-table-history",
  "match-round-report","match-round-report-title",
  "match-round-report-status","match-round-report-seats",
  "match-round-report-wins","match-round-report-timeline",
  "match-round-report-events","match-round-report-note",
  "match-motion-settlements",
  "match-review-seat-filter","match-review-type-filter",
  "match-review-inspector","match-review-selected",
  "match-review-board-status","match-review-preview-seats",
  "match-review-prev","match-review-next",
  "match-review-count",
  "match-self-melds","match-self-status","match-ready-hint","match-win-alert",
  "match-playback","match-playback-progress","match-playback-status",
  "match-playback-speed","match-playback-pause","match-playback-step",
  "match-playback-focus","match-playback-skip",
  "match-playback-note","match-motion","match-motion-text","match-motion-card",
  "match-motion-chain","match-motion-delta",
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
  normalizeSteps:playbackModule.normalizeSteps,
  highlightFrames:playbackModule.highlightFrames,
  normalizeBoard:playbackModule.normalizeBoard,
  normalizeHistorySteps:playbackModule.normalizeHistorySteps,
  openingFrame:playbackModule.openingFrame,
  filterReviewEntries:playbackModule.filterReviewEntries,
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
  // M3.17: actual post-action public boards drive the visible intermediate
  // wall, AI concealed back counts, public river and melds.
  startMatch={...base,events:[],wall_count:54};
  const boardAfterDraw={
    phase:"await_discard",turn:1,wall_count:53,
    hand_counts:[13,14,10,13],
    won:[false,false,false,false],
    melds:base.melds,discards:base.discards,
  };
  const boardAfterDiscard={
    ...boardAfterDraw,phase:"claim_window",
    hand_counts:[13,13,10,13],
    discards:[...base.discards,
      {seat:1,tile:"s5",discard_kind:"tedashi"}],
  };
  replyMatch={
    ...next,wall_count:53,
    events:[{type:"draw",seat:1},
      {type:"discard",seat:1,tile:"s5"}],
    discards:boardAfterDiscard.discards,
    public_steps:[
      {events:[{type:"draw",seat:1,tile:"hidden-must-not-show"}],
        board:boardAfterDraw},
      {events:[{type:"discard",seat:1,tile:"s5",
        discard_kind:"tedashi"}],board:boardAfterDiscard},
    ],
  };
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-wall-count"].textContent,"54");
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(dom["match-playback"].hidden,false);
  assert.equal(dom["match-wall-count"].textContent,"53",
    "real draw must decrement displayed wall immediately");
  assert.equal(descendants(dom["match-seat-1"],
    x=>x.className==="match-tile-back").length,14,
    "AI dark hand must increase by one on true draw frame");
  assert.equal(descendants(dom["match-river-1"],
    x=>x.tile==="s5").length,0,
    "the unplayed discard must not appear in the draw frame");
  assert.equal(descendants(dom["match-motion-card"],
    x=>x.tile==="hidden-must-not-show").length,0);
  assert.equal(dom["match-seat-0"].classList.contains("is-public-replay"),true);
  assert.equal(pendingTimers.size,1);
  const tick=pendingTimers.entries().next().value;
  pendingTimers.delete(tick[0]);
  tick[1].fn();
  assert.equal(descendants(dom["match-seat-1"],
    x=>x.className==="match-tile-back").length,13,
    "AI dark hand must shrink after discard");
  assert.equal(descendants(dom["match-river-1"],
    x=>x.tile==="s5").length,1,
    "public discard enters only the correct seat river");
  assert.equal(dom["match-wall-count"].textContent,"53",
    "discard does not remove another wall tile");
  dom["match-playback-skip"].handlers.click();
  await settle();
  assert.equal(dom["match-playback"].hidden,true);
  assert.equal(dom["match-seat-0"].classList.contains("is-public-replay"),false);
  assert.equal(dom["match-wall-count"].textContent,"53");
  assert.equal(requests.at(-1).action,"match_discard");
  // M3.18 focus mode is selected BEFORE the action; it keeps the kong
  // with its linked tail draw and the final completed public board.
  dom["match-playback-focus"].checked=true;
  startMatch={...base,events:[],wall_count:54};
  const drawBoard={
    phase:"await_discard",turn:1,wall_count:53,
    hand_counts:[13,14,10,13],won:[false,false,false,false],
    melds:base.melds,discards:base.discards,
  };
  const kongBoard={
    ...drawBoard,wall_count:52,hand_counts:[13,11,10,13],
    melds:[[],[{type:"an_gang",tile:null}],...base.melds.slice(2)],
  };
  const winBoard={...kongBoard,won:[false,false,false,true]};
  replyMatch={...next,wall_count:52,
    hand_counts:winBoard.hand_counts,won:winBoard.won,
    events:[{type:"draw",seat:1},
      {type:"an_gang",seat:1},{type:"kong_supplement",seat:1},
      {type:"self_draw_win",seat:3}],
    public_steps:[
      {events:[{type:"draw",seat:1,tile:"hidden-draw"}],board:drawBoard},
      {events:[{type:"an_gang",seat:1,tile:"secret-kong"},
        {type:"kong_supplement",seat:1,tile:"secret-tail"}],board:kongBoard},
      {events:[{type:"self_draw_win",seat:3}],board:winBoard},
    ],
  };
  dom["match-new"].handlers.click();
  await settle();
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(dom["match-playback"].hidden,false);
  assert.equal(dom["match-wall-count"].textContent,"52",
    "focus mode starts at authentic post-kong board, not a guessed wall");
  assert.equal(dom["match-motion"].classList.contains("is-kong-motion"),true);
  assert.ok(dom["match-motion-text"].textContent.includes("暗杠"));
  assert.ok(dom["match-motion-text"].textContent.includes("杠后补摸"));
  assert.ok(descendants(dom["match-motion-chain"],
    x=>x.className==="match-motion-chip").length===2);
  assert.ok(dom["match-motion-delta"].textContent.includes("牌山 -1"));
  assert.ok(dom["match-playback-note"].textContent.includes("精简模式"));
  assert.equal(descendants(dom["match-motion-card"],
    x=>x.tile==="secret-kong"||x.tile==="secret-tail").length,0);
  assert.equal(descendants(dom["match-motion-card"],
    x=>x.className==="match-tile-back").length,1);
  assert.equal(pendingTimers.size,1);
  dom["match-playback-pause"].handlers.click();
  assert.equal(pendingTimers.size,0);
  assert.equal(dom["match-playback-step"].disabled,false);
  dom["match-playback-step"].handlers.click();
  assert.equal(dom["match-motion"].classList.contains("is-winning-motion"),true);
  assert.equal(dom["match-playback-status"].textContent,"已暂停");
  assert.equal(pendingTimers.size,0);
  assert.equal(dom["match-seat-3"].classList.contains("is-won"),true);
  dom["match-playback-step"].handlers.click();
  await settle();
  assert.equal(dom["match-playback"].hidden,true);
  assert.equal(dom["match-playback-step"].disabled,true);
  assert.equal(dom["match-wall-count"].textContent,"52");
  assert.equal(requests.at(-1).action,"match_discard");
  dom["match-playback-focus"].checked=false;
  // M3.19: a settled win appears INSIDE the four-sided board, with exact
  // ledger balances, while the original full accounting remains below.
  dom["match-playback-speed"].value="0";
  startMatch={...base,won:[false,false,false,false],
    win_ledger:{balances:[0,0,0,0],wins:[]},
    kong_ledger:{base:null,balances:[0,0,0,0],events:[],entries:[]}};
  replyMatch={...next,
    won:[false,true,false,false],
    melds:[[],[{type:"peng",tile:"p3"},{type:"ming_gang",tile:"s2"}],
      [{type:"an_gang",tile:null}],[]],
    own_melds:[{type:"an_gang",tile:"m4"}],
    win_ledger:{
      balances:[-8,16,-8,0],
      wins:[{winner:1,kind:"ron",main_pattern:"平胡",effective_fan:1,
        total_received:16,payers:[0,2],bonuses:{},raw_fan:1,multiplier:2,amount_per_payer:8}]
    },
    kong_ledger:{base:null,balances:[0,0,0,0],events:[],entries:[]},
  };
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-table-settlement"].hidden,true,
    "do not announce settlement before any win has happened");
  assert.equal(dom["match-own-score"].hidden,true);
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(dom["match-table-settlement"].hidden,false);
  const scores=dom["match-table-scores"];
  assert.equal(scores.children.length,4);
  assert.ok(descendants(scores,x=>x.textContent==="-8").length===2);
  assert.ok(descendants(scores,x=>x.textContent==="+16").length===1);
  assert.ok(descendants(dom["match-table-wins"],
    x=>x.textContent.includes("1号点炮胡")).length===1);
  assert.ok(descendants(dom["match-table-wins"],
    x=>x.textContent.includes("实收 +16")).length===1);
  assert.equal(dom["match-own-score"].hidden,false);
  assert.ok(dom["match-own-score"].textContent.includes("-8"));
  assert.ok(dom["match-seat-1"].classList.contains("is-won"));
  assert.ok(descendants(dom["match-seat-1"],
    x=>x.className==="match-seat-score").length===1);
  assert.equal(descendants(dom["match-seat-1"],
    x=>x.tile==="p3").length,3);
  assert.equal(descendants(dom["match-seat-1"],
    x=>x.tile==="s2").length,4);
  assert.equal(descendants(dom["match-seat-2"],
    x=>x.tile!==undefined).length,0,
    "another seat's concealed kong identity stays hidden");
  assert.equal(descendants(dom["match-seat-2"],
    x=>x.className==="match-tile-back").length,14);

  // The next request has a future win, but this must not be shown while
  // public-only M3.17 frames are still being played.
  dom["match-playback-speed"].value="450";
  startMatch={...base,events:[],
    win_ledger:{balances:[0,0,0,0],wins:[]}};
  replyMatch={...replyMatch,
    events:[{type:"draw",seat:1}],
    public_steps:[{events:[{type:"draw",seat:1}],board:{
      phase:"await_discard",turn:1,wall_count:53,
      hand_counts:[13,14,10,13],won:[false,false,false,false],
      melds:base.melds,discards:base.discards,
    }}]
  };
  dom["match-new"].handlers.click();
  await settle();
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(dom["match-playback"].hidden,false);
  assert.equal(dom["match-table-settlement"].hidden,true,
    "future winning ledger must not leak into intermediate board frame");
  dom["match-playback-skip"].handlers.click();
  await settle();
  assert.equal(dom["match-table-settlement"].hidden,false);
  // M3.20: a multiple-ron rule transition posts two independent
  // authoritative payments, but is still ONE real public board frame.
  const postEvents=[
    {type:"win_settlement",seat:1,source:0,kind:"ron",
      amount:16,effective_fan:1},
    {type:"win_settlement",seat:3,source:0,kind:"ron",
      amount:8,effective_fan:1},
    {type:"multi_ron",source:0,seats:[1,3],tile:"m1"},
  ];
  const record=(winner,total,source=0)=>({
    winner,kind:"ron",main_pattern:"平胡",raw_fan:1,
    effective_fan:1,multiplier:2,amount_per_payer:total,
    total_received:total,payers:[source],bonuses:{}
  });
  const completeLedger={
    balances:[-24,16,0,8],
    wins:[record(1,16),record(3,8)]
  };
  dom["match-playback-speed"].value="450";
  startMatch={...base,events:[],
    win_ledger:{balances:[0,0,0,0],wins:[]}};
  replyMatch={...next,
    phase:"finished",won:[false,true,false,true],
    win_ledger:completeLedger,
    kong_ledger:{base:null,balances:[0,0,0,0],events:[],entries:[]},
    events:postEvents,
    public_steps:[{events:postEvents,board:{
      phase:"finished",turn:0,wall_count:53,
      hand_counts:[13,13,10,13],
      melds:base.melds,
      discards:base.discards,
      won:[false,true,false,true],
    }}],
  };
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-round-report"].hidden,true);
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(dom["match-playback"].hidden,false);
  assert.equal(dom["match-round-report"].hidden,true,
    "future final report must not show during replay");
  const payments=dom["match-motion-settlements"];
  assert.equal(payments.hidden,false);
  assert.equal(payments.children.length,2);
  assert.ok(payments.children[0].textContent.includes("1号胡牌"));
  assert.ok(payments.children[0].textContent.includes("+16"));
  assert.ok(payments.children[1].textContent.includes("3号胡牌"));
  assert.ok(payments.children[1].textContent.includes("+8"));
  assert.equal(dom["match-table-settlement"].hidden,true);
  dom["match-playback-skip"].handlers.click();
  await settle();
  assert.equal(dom["match-round-report"].hidden,false);
  assert.equal(dom["match-table-settlement"].hidden,false);
  assert.equal(dom["match-round-report-seats"].children.length,4);
  assert.equal(descendants(dom["match-round-report-wins"],
    x=>x.className==="match-win-record").length,2);
  assert.equal(descendants(dom["match-table-history"],
    x=>x.className==="match-win-record").length,2);
  assert.ok(dom["match-round-report-status"].textContent.includes("2笔胡牌"));
  assert.ok(dom["match-round-report-note"].textContent.includes("未入账"));
  assert.equal(descendants(dom["match-round-report-events"],
    x=>x.textContent.includes("胡牌入账")).length,2);

  // End-of-wall WITHOUT paid wins must still yield a report, with no
  // fabricated transfer, no fake whole-room settlement.
  startMatch={...base,phase:"wall_exhausted",wall_count:0,
    win_ledger:{balances:[0,0,0,0],wins:[]},
    kong_ledger:{base:null,balances:[0,0,0,0],events:[],entries:[]}};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-round-report"].hidden,false);
  assert.equal(dom["match-table-settlement"].hidden,true);
  assert.ok(dom["match-round-report-note"].textContent.includes("查花猪"));
  assert.ok(descendants(dom["match-round-report-wins"],
    x=>x.textContent.includes("没有已入账胡牌")).length>0);
  // M3.21: archive two successful API responses while animations are OFF.
  // Old public boards remain accessible after the match ends without
  // interfering with the real current board or making further requests.
  dom["match-playback-speed"].value="0";
  startMatch={...base,events:[],win_ledger:{
    balances:[0,0,0,0],wins:[]}};
  const firstBoard={phase:"claim_window",turn:0,wall_count:54,
    hand_counts:[13,13,10,13],melds:base.melds,
    discards:[...base.discards,{seat:0,tile:"m1"}],
    won:[false,false,false,false]};
  const secondBoard={...firstBoard,phase:"await_discard",turn:1,
    wall_count:53,hand_counts:[13,14,10,13]};
  replyMatch={...next,events:[{type:"discard",seat:0,tile:"m1"}],
    public_steps:[
      {events:[{type:"discard",seat:0,tile:"m1"}],board:firstBoard},
      {events:[{type:"draw",seat:1,tile:"hidden-drawn"}],board:secondBoard},
    ],
    win_ledger:{balances:[0,0,0,0],wins:[]},
  };
  dom["match-new"].handlers.click();
  await settle();
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(dom["match-round-report"].hidden,true);
  const matchWin={winner:1,kind:"ron",main_pattern:"平胡",
    raw_fan:1,effective_fan:1,multiplier:2,
    amount_per_payer:16,total_received:16,payers:[0],
    bonuses:{}};
  const finishedBoard={...secondBoard,phase:"finished",
    wall_count:52,hand_counts:[13,13,10,13],
    won:[false,true,false,false],
    discards:[...secondBoard.discards,{seat:1,tile:"p8"}]};
  replyMatch={...replyMatch,phase:"finished",
    wall_count:52,hand_counts:finishedBoard.hand_counts,
    discards:finishedBoard.discards,won:finishedBoard.won,
    events:[{type:"discard",seat:0,tile:"m1"},
      {type:"win_settlement",seat:1,amount:16,effective_fan:1},
      {type:"ron",seat:1,source:0}],
    win_ledger:{balances:[-16,16,0,0],wins:[matchWin]},
    public_steps:[
      {events:[{type:"discard",seat:1,tile:"p8"}],board:finishedBoard},
      {events:[{type:"win_settlement",seat:1,amount:16,
        effective_fan:1,private_hand:["must-never-show"]},
        {type:"ron",seat:1,source:0}],board:finishedBoard},
    ],
  };
  dom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(dom["match-round-report"].hidden,false);
  assert.equal(dom["match-wall-count"].textContent,"52");
  assert.equal(dom["match-round-report-events"].children.length,5,
    "opening + two frames each across TWO successful turns");
  assert.equal(dom["match-review-preview-seats"].children.length,4);
  assert.ok(dom["match-review-board-status"].textContent.includes("牌山剩余52"));
  const callCount=requests.length;
  dom["match-review-seat-filter"].value="1";
  dom["match-review-seat-filter"].handlers.change();
  assert.equal(descendants(dom["match-round-report-wins"],
    x=>x.className==="match-win-record").length,1);
  dom["match-review-type-filter"].value="win";
  dom["match-review-type-filter"].handlers.change();
  assert.equal(dom["match-round-report-events"].children.length,1);
  assert.equal(dom["match-review-prev"].disabled,true);
  dom["match-review-type-filter"].value="all";
  dom["match-review-type-filter"].handlers.change();
  assert.ok(dom["match-round-report-events"].children.length>=3);
  dom["match-review-prev"].handlers.click();
  assert.ok(dom["match-review-board-status"].textContent.includes("牌山剩余52"));
  dom["match-review-prev"].handlers.click();
  assert.ok(dom["match-review-board-status"].textContent.includes("牌山剩余53"));
  assert.equal(dom["match-wall-count"].textContent,"52",
    "historical preview must never mutate live authoritative table");
  assert.equal(requests.length,callCount,
    "review navigation must not submit any game action");
  assert.equal(descendants(dom["match-review-preview-seats"],
    x=>x.tile==="hidden-drawn"||x.tile==="must-never-show").length,0);
  assert.equal(descendants(dom["match-review-preview-seats"],
    x=>x.tile!==undefined && x.tile==="p8").length,0,
    "older history must not display future discard");

  // Filter by a seat not involved in the only paid win, then reset the
  // match. Old history and old selections must not cross into a new game.
  dom["match-review-seat-filter"].value="2";
  dom["match-review-seat-filter"].handlers.change();
  assert.equal(descendants(dom["match-round-report-wins"],
    x=>x.className==="match-win-record").length,0);
  startMatch={...base,phase:"wall_exhausted",wall_count:0,
    win_ledger:{balances:[0,0,0,0],wins:[]},
    kong_ledger:{base:null,balances:[0,0,0,0],events:[],entries:[]}};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-review-seat-filter"].value,"all");
  assert.equal(dom["match-review-type-filter"].value,"all");
  assert.equal(dom["match-round-report-events"].children.length,1);
  assert.equal(dom["match-review-preview-seats"].children.length,4);
  assert.equal(dom["match-wall-count"].textContent,"0");
  console.log("M3.21 cross-turn public history, seat/filter navigation and reset DOM smoke: PASS");
  console.log("M3.20 grouped settlement animation and round report DOM smoke: PASS");
  console.log("M3.19 in-table settlement and directional meld DOM smoke: PASS");
  console.log("M3.18 focused kong/win and manual-step live DOM smoke: PASS");
  console.log("M3.17 real wall/back/river incremental DOM smoke: PASS");
  console.log("M3.16 live match public action playback DOM smoke: PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
