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
  "match-new","match-again","match-lab-enabled","match-voice-enabled",
  "match-voice-status","match-voice-speed","match-voice-repeat",
  "match-enable-kong","match-kong-base","match-seed",
  "match-coefficient","match-fan-cap","match-self-draw-mode","match-ai-1","match-ai-2","match-ai-3",
  "match-error","match-stage","match-title","match-status","match-request-status",
  "match-resume-tools","match-resume-message","match-resume-retry",
  "home-match-state",
  "match-hud-turn","match-hud-wall","match-hud-missing","match-hud-tip",
  "match-focus-toggle","match-skin-toggle","match-decision",
  "match-back-color","match-self-missing-flag",
  "match-confirm-discard",
  "match-board",
  "match-hand-prev","match-hand-next","match-hand-draw",
  "match-hand-position","match-table-self-summary",
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
  "match-motion-big-action","match-score-bursts",
  ...[0,1,2,3].flatMap(n=>["match-seat-"+n,"match-river-"+n])
];
const dom=Object.fromEntries(ids.map(id=>[id,new Node()]));
for(const id of ids)dom[id].id=id;
dom["match-seed"].value="42";
dom["match-coefficient"].value="100";
dom["match-fan-cap"].value="3";
dom["match-self-draw-mode"].value="add_base";
dom["match-playback-speed"].value="450";
dom["match-voice-speed"].value="normal";
dom["match-back-color"].value="jade";
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
const sessionStore=new Map();
let startMatch=base,replyMatch=next;
const speechCalls=[];
const window={
  speechSynthesis:{
    cancel:()=>speechCalls.push({kind:"cancel"}),
    speak:utterance=>{
      speechCalls.push({kind:"speak",text:utterance.text});
      utterance.onend?.();
    },
  },
  SpeechSynthesisUtterance:class{
    constructor(text){this.text=text;}
  },
  MahTrainMatchVoice:require("../web/match_voice.js"),
  sessionStorage:{
    getItem:key=>sessionStore.has(key)?sessionStore.get(key):null,
    setItem:(key,val)=>sessionStore.set(key,String(val)),
    removeItem:key=>sessionStore.delete(key),
  },
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
  assert.equal(sessionStore.get("mahtrain.match.session.v1"),"test-session");
  assert.ok([...sessionStore.values()].every(v=>!v.includes("hand")),
    "Web Storage must contain only an opaque capability, never tile state");

  assert.equal(requests[0].self_draw_mode,"add_base");
  assert.equal(Object.hasOwn(requests[0],"seed"),false,
    "ordinary match must let the server select an unused random seed");
  assert.equal(dom["match-voice-enabled"].checked,true);
  // No game request occurs simply from selecting a rule for the next game.
  dom["match-self-draw-mode"].value="add_fan";
  assert.equal(requests.length,1);
  dom["match-self-draw-mode"].value="add_base";
  assert.equal(dom["match-voice-speed"].disabled,false);
  assert.equal(dom["match-voice-repeat"].disabled,true,
    "new round must forget the previous round's spoken actions");
  const voiceRequests=requests.length;
  dom["match-voice-speed"].value="slow";
  dom["match-voice-speed"].handlers.change();
  assert.equal(dom["match-voice-speed"].value,"slow");
  dom["match-voice-repeat"].handlers.click();
  assert.equal(requests.length,voiceRequests,
    "manual voice replay cannot send a game request");
  dom["match-voice-enabled"].checked=false;
  dom["match-voice-enabled"].handlers.change();
  assert.equal(dom["match-voice-speed"].disabled,true);
  assert.equal(dom["match-voice-repeat"].disabled,true);
  dom["match-voice-enabled"].checked=true;
  dom["match-voice-enabled"].handlers.change();
  assert.equal(dom["match-voice-speed"].disabled,false);
  dom["match-voice-speed"].value="normal";
  dom["match-voice-speed"].handlers.change();
  assert.equal(dom["match-stage"].hidden,false);
  assert.ok(dom["match-request-status"].textContent.includes("已同步"));
  assert.equal(dom["match-wall-count"].textContent,"54");
  assert.equal(dom["match-hand"].children.length,14);
  // Simulate a narrow handset scroll region; navigation is local only and
  // must not generate any server request or alter hand order.
  const handStrip=dom["match-hand"];
  handStrip.scrollWidth=1120;
  handStrip.clientWidth=320;
  handStrip.scrollLeft=0;
  handStrip.handlers.scroll();
  const originalRequests=requests.length;
  assert.equal(dom["match-hand-prev"].disabled,true);
  dom["match-hand-next"].handlers.click();
  assert.ok(handStrip.scrollLeft>0);
  assert.equal(dom["match-hand-prev"].disabled,false);
  const afterRight=handStrip.scrollLeft;
  dom["match-hand-prev"].handlers.click();
  assert.ok(handStrip.scrollLeft<afterRight);
  assert.equal(requests.length,originalRequests);
  assert.ok(dom["match-hand-position"].textContent.includes("14张手牌"));
  assert.equal(dom["match-hud-turn"].textContent,"轮到你出牌");
  assert.equal(dom["match-hud-wall"].textContent,"54 张");
  assert.equal(dom["match-hud-missing"].textContent,"缺筒");
  assert.equal(dom["match-self-missing-flag"].textContent,"缺筒");
  assert.equal(dom["match-self-missing-flag"].hidden,false);
  assert.ok(descendants(dom["match-seat-1"],x=>
    x.className.includes("match-missing-flag")&&
    x.textContent==="缺条").length);
  dom["match-back-color"].value="indigo";
  dom["match-back-color"].handlers.change();
  assert.equal(dom["match-board"].attributes["data-back-color"],"indigo");
  dom["match-back-color"].value="red";
  dom["match-back-color"].handlers.change();
  assert.equal(dom["match-board"].attributes["data-back-color"],"red");
  dom["match-back-color"].value="__unsafe";
  dom["match-back-color"].handlers.change();
  assert.equal(dom["match-back-color"].value,"red");
  assert.equal(dom["match-board"].attributes["data-back-color"],"red");
  assert.ok(dom["match-hud-tip"].textContent.includes("点击手牌"));
  dom["match-focus-toggle"].handlers.click();
  assert.equal(dom["match-stage"].classList.contains("is-immersive"),true);
  assert.equal(dom["match-focus-toggle"].attributes["aria-pressed"],"true");
  dom["match-focus-toggle"].handlers.click();
  assert.equal(dom["match-stage"].classList.contains("is-immersive"),false);
  dom["match-skin-toggle"].handlers.click();
  assert.equal(dom["match-board"].classList.contains("is-midnight-felt"),true);
  assert.equal(dom["match-skin-toggle"].attributes["aria-pressed"],"true");
  assert.equal(dom["match-skin-toggle"].textContent,"绿色桌布");
  dom["match-skin-toggle"].handlers.click();
  assert.equal(dom["match-board"].classList.contains("is-midnight-felt"),false);
  assert.equal(dom["match-skin-toggle"].attributes["aria-pressed"],"false");

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
  assert.equal(dom["match-hand-draw"].disabled,false);
  const countBeforeJump=requests.length;
  dom["match-hand-draw"].handlers.click();
  assert.equal(dom["match-hand"].scrollLeft,800);
  assert.equal(requests.length,countBeforeJump,
    "locating the drawn tile is purely visual");
  const rightEnd=dom["match-hand"].scrollLeft;
  assert.ok(descendants(dom["match-ready-hint"],x=>x.tile==="m3").length);
  // Optional tap-confirm: selecting a hand copy must NOT submit a discard.
  // Even when the same tile is the new draw, hand-cut must stay explicit.
  dom["match-confirm-discard"].checked=true;
  dom["match-confirm-discard"].handlers.change();
  const priorCount=requests.length;
  dom["match-hand"].children.find(x=>x.tile==="m1"&&
    !x.classList.contains("match-new-draw")).handlers.click();
  await settle();
  assert.equal(requests.length,priorCount);
  assert.ok(dom["match-hud-tip"].textContent.includes("已选"));
  assert.equal(dom["match-hand"].scrollLeft,rightEnd,
    "rerendering selected cards must preserve phone scroll location");
  assert.equal(dom["match-hand"].children.filter(x=>
    x.classList.contains("match-pending-discard")).length,1,
    "a duplicate of the same tile must not be raised together");
  const confirmCut=dom["match-controls"].children.find(x=>
    x.textContent.includes("确认打出"));
  assert.ok(confirmCut);
  assert.ok(confirmCut.textContent.includes("手切"));
  const cancel=dom["match-controls"].children.find(x=>
    x.textContent==="取消选牌");
  cancel.handlers.click();
  assert.equal(dom["match-hand"].scrollLeft,rightEnd);
  assert.equal(requests.length,priorCount);
  assert.equal(dom["match-hand"].children.some(x=>
    x.classList.contains("match-pending-discard")),false);
  dom["match-hand"].children.find(x=>x.tile==="m1"&&
    !x.classList.contains("match-new-draw")).handlers.click();
  dom["match-controls"].children.find(x=>
    x.textContent.includes("确认打出")).handlers.click();
  await settle();
  assert.equal(requests.length,priorCount+1);
  dom["match-confirm-discard"].checked=false;
  dom["match-confirm-discard"].handlers.change();
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
  assert.ok(dom["match-table-self-summary"].textContent.includes("-8"));
  assert.ok(dom["match-table-self-summary"].textContent.includes("包含已确认胡牌和杠钱积分"));
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
      amount:16,effective_fan:1,payers:[0],amount_per_payer:16},
    {type:"win_settlement",seat:3,source:0,kind:"ron",
      amount:8,effective_fan:1,payers:[0],amount_per_payer:8},
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
  assert.equal(dom["match-motion-big-action"].textContent,"一炮多响");
  const scoreBursts=dom["match-score-bursts"];
  assert.equal(scoreBursts.hidden,false);
  assert.equal(scoreBursts.children.length,3);
  assert.ok(scoreBursts.children.some(x=>x.textContent==="-24"&&
    x.classes.has("match-score-burst--0")));
  assert.ok(scoreBursts.children.some(x=>x.textContent==="+16"&&
    x.classes.has("match-score-burst--1")));
  assert.ok(scoreBursts.children.some(x=>x.textContent==="+8"&&
    x.classes.has("match-score-burst--3")));
  assert.equal(dom["match-table-settlement"].hidden,true);
  dom["match-playback-skip"].handlers.click();
  await settle();
  assert.equal(dom["match-round-report"].hidden,false);
  assert.equal(dom["match-table-settlement"].hidden,false);
  assert.equal(dom["match-score-bursts"].hidden,false,
    "verified transfers remain readable when replay finishes");
  assert.equal(dom["match-round-report-seats"].children.length,4);
  assert.equal(descendants(dom["match-round-report-wins"],
    x=>x.className==="match-win-record").length,2);
  assert.equal(descendants(dom["match-table-history"],
    x=>x.className==="match-win-record").length,2);
  assert.ok(dom["match-round-report-status"].textContent.includes("2笔胡牌"));
  assert.ok(dom["match-round-report-note"].textContent.includes("未入账"));
  assert.equal(dom["match-round-report-events"].children.length,2,
    "opening snapshot and single authoritative multi-ron rule transition");
  assert.equal(descendants(dom["match-round-report-events"],
    x=>x.textContent.includes("一炮多响")).length,1,
    "two paid wins must share one authentic post-transition board");

  // End-of-wall WITHOUT paid wins must still yield a report, with no
  // fabricated transfer, no fake whole-room settlement.
  startMatch={...base,phase:"wall_exhausted",wall_count:0,
    win_ledger:{balances:[0,0,0,0],wins:[]},
    kong_ledger:{base:null,balances:[0,0,0,0],events:[],entries:[]}};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-round-report"].hidden,false);
  assert.equal(dom["match-table-settlement"].hidden,false,
    "a terminal draw without HU should still explain why the final settlement is pending");
  assert.ok(dom["match-table-self-summary"].textContent.includes("待核验"));
  assert.ok(dom["match-table-score-note"].textContent.includes("不能视为最终净积分"));
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
  assert.equal(dom["match-score-bursts"].hidden,false,
    "playback-off mode still shows the posted HU score delta");
  assert.equal(dom["match-score-bursts"].children.length,2);
  assert.ok(dom["match-score-bursts"].children.some(x=>x.textContent==="+16"));
  assert.ok(dom["match-score-bursts"].children.some(x=>x.textContent==="-16"));
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
  // M3.36: high-stakes claim actions are large, prioritized and retain
  // real action payloads. PASS must remain visually quieter than HU.
  startMatch={...base,phase:"claim_window",turn:2,
    claim_options:["pass","peng","hu","ming_gang"],
    pending_discard:{seat:2,tile:"p2"}};
  replyMatch={...next};
  dom["match-new"].handlers.click();
  await settle();
  const reaction=dom["match-decision"].children.find(x=>
    x.className==="match-reaction-actions");
  assert.equal(dom["match-decision"].hidden,false,
    "claim must be selectable from table center");
  assert.equal(dom["match-controls"].hidden,true,
    "unused below-table claim toolbar must be completely hidden");
  assert.equal(dom["match-decision"].children.filter(x=>
    x.className==="match-reaction-actions").length,1,
    "the live server-supplied claim is the only dialog trigger");
  assert.ok(reaction);
  assert.deepEqual(reaction.children.map(x=>x.textContent),[
    "胡 · 优先响应","明杠","碰","过 · 放弃本次响应"
  ]);
  assert.ok(reaction.children[0].className.includes("match-reaction--hu"));
  assert.ok(reaction.children[3].className.includes("match-reaction--pass"));
  const beforeReaction=requests.length;
  reaction.children[0].handlers.click();
  await settle();
  assert.equal(requests.length,beforeReaction+1);
  assert.equal(requests.at(-1).action,"match_claim");
  assert.equal(requests.at(-1).choice,"hu");
  startMatch={...base,phase:"rob_kong_window",
    rob_options:["pass","hu"],
    pending_rob_kong:{seat:2,tile:"s2"}};
  dom["match-new"].handlers.click();
  await settle();
  const rob=dom["match-decision"].children.find(x=>
    x.className==="match-reaction-actions");
  assert.deepEqual(rob.children.map(x=>x.textContent),
    ["胡 · 优先响应","过 · 放弃本次响应"]);
  rob.children[1].handlers.click();
  await settle();
  assert.equal(requests.at(-1).action,"match_rob");
  assert.equal(requests.at(-1).choice,"pass");
  // A human response already submitted must NEVER show an old popup
  // while the other 2 AI seats finish arbitration.
  startMatch={...base,phase:"claim_window",turn:2,
    claim_options:["pass","peng","hu"],
    claim_submitted:[0],pending_discard:{seat:2,tile:"p2"},
    needs_continue:false};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-decision"].hidden,true,
    "already committed response must not reappear during AI arbitration");
  assert.equal(dom["match-controls"].hidden,true);

  // M3.45: PASS-only claim is already auto-resolved by the server.
  // Do not flash a modal or make the human click an unnecessary "过".
  startMatch={...base,phase:"claim_window",turn:2,
    claim_options:["pass"],pending_discard:{seat:2,tile:"p2"},
    needs_continue:false};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-decision"].hidden,true,
    "PASS-only response must never produce a blocking dialog");
  assert.equal(dom["match-controls"].hidden,true,
    "PASS-only response should not leave an empty bottom toolbar");
  startMatch={...base,phase:"rob_kong_window",turn:2,
    rob_options:["pass"],pending_rob_kong:{seat:2,tile:"s2"},
    needs_continue:false};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-decision"].hidden,true,
    "PASS-only rob-kong response should not display a modal");

  // Starting a new game resets stale navigation even after scrolling far.
  dom["match-hand"].scrollLeft=600;
  startMatch={...base};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-hand"].scrollLeft,0);
  assert.equal(dom["match-hand-draw"].disabled,true);

  // M3.24: seed is ONLY supplied when the laboratory fixed mode is chosen.
  dom["match-lab-enabled"].checked=true;
  dom["match-lab-enabled"].handlers.change();
  assert.equal(dom["match-seed"].disabled,false);
  dom["match-seed"].value="12345";
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(requests.at(-1).seed,12345);
  assert.equal(dom["match-stage"].hidden,false);
  dom["match-again"].handlers.click();
  await settle();
  assert.equal(requests.at(-1).action,"match_new");
  assert.equal(Object.hasOwn(requests.at(-1),"seed"),false,
    "rematch must ignore even the enabled lab seed and use server randomness");
  dom["match-voice-enabled"].checked=false;
  dom["match-voice-enabled"].handlers.change();
  const spoken=speechCalls.filter(x=>x.kind==="speak").map(x=>x.text);
  assert.ok(spoken.some(x=>x==="碰"||x==="杠"||x==="胡"||/[一二三四五六七八九][万条筒]/.test(x)),
    "public live actions should be spoken");
  assert.ok(spoken.every(x=>!x.includes("hidden-")&&!x.includes("secret-")));
  // M3.39: preview comes ONLY from the authorized server-supplied quote;
  // neither the room selector nor a guessed future tile can price a win.
  startMatch={...base,can_self_draw_win:true,
    self_draw_preview:{
      posted:false,main_pattern:"heaven_win",raw_fan:4,effective_fan:3,
      base_multiplier:8,payment_multiplier:9,self_draw_mode:"add_base",
      payers:[1,2,3],amount_per_payer:900,total_received:2700,
      room_coefficient:100
    }};
  dom["match-new"].handlers.click();
  await settle();
  const quoteNode=dom["match-controls"].children.find(x=>
    x.className==="match-self-win-preview");
  assert.ok(quoteNode,"eligible HU must show a real server-authored quote");
  assert.ok(quoteNode.children.some(x=>x.textContent.includes("尚未入账")));
  assert.ok(quoteNode.children.some(x=>x.textContent.includes("自摸加底")));
  assert.ok(quoteNode.children.some(x=>x.textContent.includes("原始4番")));
  assert.ok(quoteNode.children.some(x=>x.textContent.includes("每家付900")));
  assert.ok(quoteNode.children.some(x=>x.textContent.includes("2700")));
  const beforeConfirm=requests.length;
  assert.equal(requests.length,beforeConfirm,
    "showing a preview does not commit or query a settlement");
  dom["match-controls"].children.find(x=>
    x.className.includes("match-self-win-action")).handlers.click();
  await settle();
  assert.equal(requests.length,beforeConfirm+1);
  assert.equal(requests.at(-1).action,"match_win");
  startMatch={...base,can_self_draw_win:false,self_draw_preview:null};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-controls"].children.some(x=>
    x.className==="match-self-win-preview"),false,
    "a nonwinning/old round must not retain the prior quote");

  // M3.44: each owner-oriented side river retains chronological source
  // order, grouped in 8-tile VERTICAL lanes for desktop. CSS makes the left
  // lanes top-to-bottom and right lanes bottom-to-top, without reversing
  // source history, hidden hands, claimed removals or latest highlighting.
  const lateral=[];
  for(let i=0;i<17;i++){
    lateral.push({seat:3,tile:"m"+(i%9+1),
      discard_kind:i%2?"tedashi":"tsumogiri"});
    lateral.push({seat:1,tile:"s"+(i%9+1)});
  }
  startMatch={...base,discards:lateral};
  dom["match-new"].handlers.click();
  await settle();
  for(const seat of [3,1]){
    const root=dom["match-river-"+seat];
    const riverTiles=root.children.find(x=>x.className==="match-river-tiles");
    assert.deepEqual(riverTiles.children.map(x=>x.className),
      ["match-river-lane","match-river-lane","match-river-lane"]);
    assert.deepEqual(riverTiles.children.map(x=>x.children.length),[8,8,1]);
    const indexed=riverTiles.children.flatMap(lane=>
      lane.children.map(cell=>Number(cell.attributes["data-discard-order"])));
    assert.deepEqual(indexed,lateral.map((e,i)=>e.seat===seat?i:null)
      .filter(x=>x!==null));
    assert.equal(riverTiles.children[2].children[0].classList.contains(
      "is-latest"),seat===1);
  }
  assert.equal(dom["match-decision"].hidden,true,
    "normal discard phase must not block the table with a reaction panel");
  assert.equal(dom["match-controls"].children.some(x=>
    x.className==="match-reaction-actions"),false);
  startMatch={...base,phase:"await_discard",
    kong_options:[{type:"an_gang",tile:"m9"}]};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(dom["match-decision"].hidden,false,
    "own legally offered kong should be centered, never below the table");
  const kongGroup=dom["match-decision"].children.find(x=>
    x.className==="match-reaction-actions");
  assert.equal(kongGroup.children.length,2,
    "one kong action and one dismiss button, never a persistent modal");
  assert.ok(kongGroup.children[0].textContent.includes("暗杠"));
  assert.ok(kongGroup.children[1].textContent.includes("暂不杠"));
  const beforeDismiss=requests.length;
  kongGroup.children[1].handlers.click();
  await settle();
  assert.equal(requests.length,beforeDismiss,
    "choosing to continue discarding must not send a kong request");
  assert.equal(dom["match-decision"].hidden,true,
    "declining one kong opportunity must keep the table unobstructed");
  // Re-rendering the same turn MUST NOT reopen the optional kong modal.
  dom["match-focus-toggle"].handlers.click();
  assert.equal(dom["match-decision"].hidden,true);
  const reopenKong=dom["match-controls"].children.find(x=>
    x.className.includes("match-open-kong"));
  assert.ok(reopenKong,"own kong remains available as a small control");
  reopenKong.handlers.click();
  await settle();
  assert.equal(dom["match-decision"].hidden,false,
    "manual reopen should work while this legal kong opportunity persists");
  const reopenedKongGroup=dom["match-decision"].children.find(x=>
    x.className==="match-reaction-actions");
  assert.equal(dom["match-controls"].children.some(x=>
    x.textContent.includes("暗杠")),false);
  const kongBefore=requests.length;
  reopenedKongGroup.children[0].handlers.click();
  await settle();
  assert.equal(requests.length,kongBefore+1);
  assert.equal(requests.at(-1).action,"match_kong");
  assert.equal(requests.at(-1).kind,"an_gang");
  assert.equal(requests.at(-1).tile,"m9");
  console.log("M3.44 left-down/right-up river lanes and centered peng/kong: PASS");

  // M3.42: all four concealed-kong backs remain if an old board had no
  // explicit public marker. A newly-declared kong flips only the last tile.
  startMatch={...base,melds:[[],[],
    [{type:"an_gang",tile:"m7",revealed:true}],[]]};
  dom["match-new"].handlers.click();
  await settle();
  const newKong=dom["match-seat-2"];
  assert.equal(descendants(newKong,x=>x.tile==="m7").length,1);
  assert.equal(descendants(newKong,x=>
    x.className==="match-tile-back").length,13);
  assert.equal(descendants(newKong,x=>
    x.classList.contains("match-kong-revealed")).length,1);
  // The full rack has one authorized visible face and 3 backs.
  assert.ok(descendants(newKong,x=>x.attributes["aria-label"]?.includes(
    "一张翻开")).length===1);
  assert.equal(requests.at(-1).action,"match_new");
  // Old archived/legacy redacted kong stays strictly face-down.
  startMatch={...base,melds:[[],[],
    [{type:"an_gang",tile:null}],[]]};
  dom["match-new"].handlers.click();
  await settle();
  assert.equal(descendants(dom["match-seat-2"],x=>x.tile==="m7").length,0);
  // All sides still display the exact public concealed-hand COUNTS.
  assert.equal(descendants(dom["match-seat-1"],x=>
    x.className==="match-tile-back").length,13);
  console.log("M3.42 one flipped kong tile and concealed legacy DOM: PASS");

  // M3.41: a continuation may include silent authentic steps followed by
  // one spoken discard. Quiet intermediate visual placeholders are skipped,
  // while the complete verified snapshots remain inspectable in review.
  startMatch={...base,events:[]};
  replyMatch={...next,events:[],public_steps:[],needs_continue:true};
  dom["match-playback-speed"].value="0";
  dom["match-playback-speed"].handlers.change();
  dom["match-new"].handlers.click();
  await settle();
  dom["match-hand"].children[0].handlers.click();
  await settle();
  const scheduledContinuation=[...pendingTimers.entries()].find(
    ([,slot])=>slot.delay===0);
  assert.ok(scheduledContinuation,"AI continuation must be scheduled");
  dom["match-playback-speed"].value="450";
  dom["match-playback-speed"].handlers.change();
  dom["match-playback-focus"].checked=false;
  const m341DrawBoard={phase:"await_discard",turn:1,wall_count:52,
    hand_counts:[14,14,10,13],won:base.won,
    melds:base.melds,discards:next.discards};
  const m341DiscardBoard={...m341DrawBoard,phase:"claim_window",
    hand_counts:[14,13,10,13],
    discards:[...next.discards,
      {seat:1,tile:"s5",discard_kind:"tedashi"}]};
  replyMatch={...next,wall_count:52,phase:"claim_window",
    turn:1,hand_counts:m341DiscardBoard.hand_counts,discards:m341DiscardBoard.discards,
    events:[{type:"draw",seat:1},
      {type:"discard",seat:1,tile:"s5",discard_kind:"tedashi"}],
    public_steps:[
      {events:[{type:"draw",seat:1}],board:m341DrawBoard},
      {events:[{type:"discard",seat:1,tile:"s5",
        discard_kind:"tedashi"}],board:m341DiscardBoard},
    ],needs_continue:false};
  pendingTimers.delete(scheduledContinuation[0]);
  scheduledContinuation[1].fn();
  await settle();
  assert.equal(requests.at(-1).action,"match_continue");
  assert.equal(dom["match-playback"].hidden,false);
  assert.ok(dom["match-motion-text"].textContent.includes("出牌"),
    "first visible continuation frame should be the actual audible cut");
  assert.ok(dom["match-playback-note"].textContent.includes(
    "已合并1个无声中间画面"));
  assert.ok(descendants(dom["match-motion-card"],x=>x.tile==="s5").length);
  dom["match-playback-skip"].handlers.click();
  await settle();
  assert.equal(dom["match-wall-count"].textContent,"52");
  dom["match-review-seat-filter"].value="all";
  dom["match-review-type-filter"].value="all";
  dom["match-review-type-filter"].handlers.change();
  assert.ok(dom["match-review-count"].textContent.includes("4 步"),
    "full review should keep opening, real manual state, draw and discard");
  assert.equal(pendingTimers.size,0);
  // M3.48: simulate a full JS reload with the same TAB storage and a new
  // DOM instance, but the server's original token and authorized state.
  const reloadDom=Object.fromEntries(ids.map(id=>[id,new Node()]));
  for(const id of ids)reloadDom[id].id=id;
  reloadDom["match-stage"].hidden=true;
  reloadDom["match-resume-tools"].hidden=true;
  reloadDom["match-playback-speed"].value="450";
  reloadDom["match-voice-speed"].value="normal";
  reloadDom["match-back-color"].value="jade";
  reloadDom["match-self-draw-mode"].value="add_base";
  reloadDom["match-coefficient"].value="100";
  reloadDom["match-fan-cap"].value="3";
  reloadDom["match-seed"].value="42";
  for(const n of [1,2,3])reloadDom["match-ai-"+n].value="advanced";
  const reopenedRequests=[];
  const reopenedWindow={...window};
  const resumedState={...base,needs_continue:false};
  let dropDiscardReply=false,denyReconcile=false;
  let authoritativeState=resumedState;
  const reloadedContext={
    document:{createElement:tag=>new Node(tag),getElementById:id=>{
      assert.ok(reloadDom[id],"missing reloaded id "+id);return reloadDom[id];
    }},
    window:reopenedWindow,
    fetch:async (_url,opts)=>{
      const req=JSON.parse(opts.body);
      reopenedRequests.push(req);
      if(req.action==="match_discard"&&dropDiscardReply){
        // The server already committed the discard; its HTTP reply was
        // lost. Sending the same discard again would be a dangerous retry.
        dropDiscardReply=false;
        throw new Error("simulated connection drop after server commit");
      }
      if(req.action==="match_resume"&&denyReconcile){
        throw new Error("simulated temporary recovery outage");
      }
      return {ok:true,json:async()=>({
        match_token:"test-session",match:authoritativeState,
      })};
    },
    confirm:()=>true,
    setTimeout:(fn,delay)=>{pendingTimers.set(++timerIndex,{fn,delay});return timerIndex},
    clearTimeout:id=>pendingTimers.delete(id),
    console,
  };
  vm.runInNewContext(script,reloadedContext,{filename:"web/match.js"});
  reopenedWindow.MahTrainMatch.init();
  await settle();
  assert.deepEqual(reopenedRequests.map(r=>r.action),["match_resume"]);
  assert.deepEqual(Object.keys(reopenedRequests[0]).sort(),
    ["action","match_token"]);
  assert.equal(reopenedRequests[0].match_token,"test-session");
  assert.equal(reloadDom["match-stage"].hidden,false);
  assert.equal(reloadDom["match-wall-count"].textContent,"54");
  assert.equal(reloadDom["match-hand"].children.length,14);
  assert.equal(reloadDom["match-resume-tools"].hidden,true);
  assert.ok(reloadDom["match-request-status"].textContent.includes("已恢复原对局"));
  assert.ok(reloadDom["home-match-state"].textContent.includes("已有对局"));
  assert.equal(sessionStore.get("mahtrain.match.session.v1"),"test-session");
  assert.equal(reopenedRequests.length,1,"restoring must not issue new/continue");
  // M3.49: a discard was committed, but its HTTP response never reached the
  // browser. Reconcile with a READ-ONLY snapshot; do not cut the same tile.
  authoritativeState={...resumedState,
    hand:resumedState.hand.slice(1),
    wall_count:53,
    discards:[...resumedState.discards,{seat:0,tile:"m1"}],
    events:[{type:"discard",seat:0,tile:"m1"}],
    needs_continue:false,
  };
  dropDiscardReply=true;
  reloadDom["match-hand"].children[0].handlers.click();
  await settle();
  assert.deepEqual(reopenedRequests.slice(1).map(x=>x.action),
    ["match_discard","match_resume"],
    "a lost mutation reply must cause exactly one read-only reconciliation");
  assert.equal(reopenedRequests[1].tile,"m1");
  assert.equal(reopenedRequests[2].match_token,"test-session");
  assert.equal(reloadDom["match-wall-count"].textContent,"53");
  assert.equal(reloadDom["match-hand"].children.length,13);
  assert.equal(reloadDom["match-resume-tools"].hidden,true);
  assert.ok(reloadDom["match-request-status"].textContent.includes("没有重复提交"));
  assert.equal(reopenedRequests.filter(x=>x.action==="match_discard").length,1);
  // A second lost HTTP response AND a temporarily unavailable recovery
  // endpoint must freeze all game mutations until manual reconnection.
  authoritativeState={...resumedState};
  // The client is still in an await-discard phase. Restore that on the
  // server via an authorized snapshot before simulating another attempt.
  reloadDom["match-resume-retry"].handlers.click();
  await settle();
  denyReconcile=true;dropDiscardReply=true;
  const requestCountBefore=reopenedRequests.length;
  reloadDom["match-hand"].children[0].handlers.click();
  await settle();
  assert.deepEqual(reopenedRequests.slice(requestCountBefore).map(x=>x.action),
    ["match_discard","match_resume"]);
  assert.equal(reloadDom["match-resume-tools"].hidden,false);
  const frozenRequestCount=reopenedRequests.length;
  reloadDom["match-hand"].children[0].handlers.click();
  await settle();
  assert.equal(reopenedRequests.length,frozenRequestCount,
    "no duplicate discard is permitted while state is uncertain");
  denyReconcile=false;
  reloadDom["match-resume-retry"].handlers.click();
  await settle();
  assert.equal(reopenedRequests.at(-1).action,"match_resume");
  assert.equal(reloadDom["match-resume-tools"].hidden,true);
  assert.ok(reloadDom["match-request-status"].textContent.includes("已恢复原对局"));
  console.log("M3.49 lost POST reply reconciles without duplicate mutation: PASS");
  // A response lost during navigation may already have changed the server
  // phase. Resume only schedules the NEXT safe AI continuation once.
  reopenedWindow.sessionStorage.setItem("mahtrain.match.session.v1","stale-token");
  const expiredDom=Object.fromEntries(ids.map(id=>[id,new Node()]));
  for(const id of ids)expiredDom[id].id=id;
  expiredDom["match-resume-tools"].hidden=true;
  expiredDom["match-stage"].hidden=true;
  expiredDom["match-playback-speed"].value="450";
  expiredDom["match-voice-speed"].value="normal";
  const expiredWindow={...window};
  let invalidCalls=0;
  const expiredCtx={
    document:{createElement:tag=>new Node(tag),getElementById:id=>expiredDom[id]},
    window:expiredWindow,
    fetch:async (_,opts)=>{
      invalidCalls++;
      assert.equal(JSON.parse(opts.body).action,"match_resume");
      return {ok:false,status:400,json:async()=>({
        error:"对局会话已失效，请重新开局",
      })};
    },
    confirm:()=>true,setTimeout:(fn,delay)=>0,clearTimeout:()=>{},console,
  };
  vm.runInNewContext(script,expiredCtx,{filename:"web/match.js"});
  expiredWindow.MahTrainMatch.init();
  await settle();
  assert.equal(invalidCalls,1);
  assert.equal(sessionStore.has("mahtrain.match.session.v1"),false);
  assert.equal(expiredDom["match-stage"].hidden,true,
    "invalid stored token cannot create a pretend game");
  assert.equal(expiredDom["match-hand"].children.length,0);
  assert.equal(expiredDom["match-resume-tools"].hidden,true);
  assert.ok(expiredDom["match-error"].textContent.includes("已失效"));
  console.log("M3.48 same-tab resume, zero new draws, stale-token cleanup: PASS");
  console.log("M3.41 silent AI frame coalescing and complete public review: PASS");

  console.log("M3.39 server-only HU quote and no booking before confirmation: PASS");
  console.log("M3.24 random rematch, lab seed, speech and privacy DOM smoke: PASS");
  console.log("M3.21 cross-turn public history, seat/filter navigation and reset DOM smoke: PASS");
  console.log("M3.20 grouped settlement animation and round report DOM smoke: PASS");
  console.log("M3.19 in-table settlement and directional meld DOM smoke: PASS");
  console.log("M3.18 focused kong/win and manual-step live DOM smoke: PASS");
  console.log("M3.17 real wall/back/river incremental DOM smoke: PASS");
  console.log("M3.16 live match public action playback DOM smoke: PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
