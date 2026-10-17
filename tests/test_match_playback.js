"use strict";
/* M3.16 replay controls: deterministic fake clock, no external dependencies. */
const assert=require("node:assert/strict");
const {normalize,createController}=require("../web/match_playback.js");
function fakeClock(){
  let next=0;const pending=new Map();
  return {
    set(fn,delay){const id=++next;pending.set(id,{fn,delay});return id;},
    clear(id){pending.delete(id);},
    tick(){const pair=pending.entries().next().value;
      assert.ok(pair,"no scheduled animation frame");
      pending.delete(pair[0]);pair[1].fn();return pair[1].delay;},
    count(){return pending.size;},
    delays(){return [...pending.values()].map(x=>x.delay);},
  };
}
{
  const raw=[
    {type:"draw",seat:2,tile:"secret-drawn",hand:["m1"]},
    {type:"kong_supplement",seat:1,tile:"secret-tail"},
    {type:"an_gang",seat:3,tile:"secret-kong"},
    {type:"discard",seat:1,tile:"m9",discard_kind:"tsumogiri"},
    {type:"peng",seat:2,tile:"p4"},
    {type:"multi_ron",source:1,seats:[2,3],tile:"m9"},
    {type:"win_settlement",seat:2,hand:["p4"]},
  ];
  const publicFrames=normalize(raw);
  assert.equal(publicFrames.frames.length,6);
  const [draw,tail,hidden,cut,peng,ron]=publicFrames.frames;
  for(const frame of [draw,tail,hidden]){
    assert.equal(frame.publicTile,null);
    assert.equal(frame.concealed,true);
    assert.ok(!JSON.stringify(frame).includes("secret"));
  }
  assert.equal(cut.publicTile,"m9");
  assert.ok(cut.label.includes("摸切"));
  assert.equal(peng.publicTile,"p4");
  assert.equal(ron.winSeats.join(","),"2,3");
  assert.equal(ron.publicTile,"m9");
  assert.ok(ron.isWin);
  assert.equal(normalize(raw,2).omitted,4);
  assert.equal(normalize(raw,2).frames.length,2);
}
{
  const timer=fakeClock(),shown=[],statuses=[];
  let done=0,completed=0;
  const player=createController({
    onFrame:(frame,i,n)=>shown.push([frame.label,i,n]),
    onDone:()=>done++,
    onStatus:value=>statuses.push(value),
    clock:timer.set,clearClock:timer.clear,
  });
  player.setSpeed(180);
  assert.deepEqual(player.getState(),{
    playing:false,paused:false,index:-1,total:0,duration:180,
  });
  player.start(normalize([
    {type:"draw",seat:1},
    {type:"discard",seat:1,tile:"p3"},
    {type:"self_draw_win",seat:2},
  ]).frames,()=>completed++);
  assert.equal(shown.length,1);
  assert.equal(timer.count(),1);
  player.pause();
  assert.equal(timer.count(),0);
  assert.equal(player.getState().paused,true);
  player.setSpeed(900);
  assert.equal(timer.count(),0);
  player.resume();
  assert.deepEqual(timer.delays(),[900]);
  assert.equal(timer.tick(),900);
  assert.equal(shown.length,2);
  player.setSpeed(450);
  assert.deepEqual(timer.delays(),[450]);
  assert.equal(timer.tick(),450);
  assert.equal(shown.length,3);
  assert.equal(timer.tick(),450);
  assert.equal(done,1);
  assert.equal(completed,1);
  assert.equal(player.getState().playing,false);
  player.skip();
  assert.equal(done,1,"skip after completion cannot fire twice");
  assert.ok(statuses.some(x=>x.paused));
}
{
  const timer=fakeClock();let committed=0,ended=0;
  const player=createController({
    onFrame:()=>{},onDone:()=>ended++,
    onStatus:()=>{},clock:timer.set,clearClock:timer.clear,
  });
  const frames=normalize([{type:"discard",seat:1,tile:"m2"},
    {type:"draw",seat:3}]).frames;
  player.start(frames,()=>committed++);
  player.skip();
  assert.equal(timer.count(),0);
  assert.equal(committed,1);
  assert.equal(ended,1);
  player.start(frames,()=>committed++);
  player.cancel();
  assert.equal(committed,1);
  assert.equal(timer.count(),0);
  assert.throws(()=>player.setSpeed(10),RangeError);
}
{
  // Real transition snapshots, deliberately containing extra secret fields
  // to prove a strict UI allowlist is enforced.
  const before={
    phase:"await_discard",turn:1,wall_count:53,
    hand_counts:[13,14,13,13],won:[false,false,false,false],
    melds:[[],[],[{type:"an_gang",tile:"s9"}],[]],discards:[],
    hand:["private"],drawn_tile:"never-export",future_wall:["hidden"]
  };
  const after={...before,phase:"claim_window",wall_count:53,
    hand_counts:[13,13,13,13],
    discards:[{seat:1,tile:"p7",discard_kind:"tedashi",
      hand:["private"],future_wall:["hidden"]}]};
  const steps=[
    {events:[{type:"draw",seat:1,tile:"private-drawn",hand:["private"]}],
      board:before},
    {events:[{type:"discard",seat:1,tile:"p7",discard_kind:"tedashi"}],
      board:after},
  ];
  const packed=require("../web/match_playback.js").normalizeSteps(steps);
  assert.equal(packed.frames.length,2);
  assert.equal(packed.frames[0].board.hand_counts[1],14);
  assert.equal(packed.frames[1].board.hand_counts[1],13);
  assert.equal(packed.frames[0].board.wall_count,53);
  assert.equal(packed.frames[1].board.discards[0].tile,"p7");
  assert.equal(packed.frames[0].board.melds[2][0].tile,null);
  for(const secret of ["private","never-export","future_wall","s9"]){
    assert.ok(!JSON.stringify(packed).includes(secret),secret+" leaked");
  }
  assert.equal(require("../web/match_playback.js").normalizeSteps(steps,1)
    .omitted,1);
  assert.equal(require("../web/match_playback.js").normalizeSteps([
    {events:[{type:"an_gang",seat:2,tile:"s9"},
      {type:"kong_supplement",seat:2,tile:"p4"}],board:before},
  ]).frames.length,1,"two in-call events share one actual post-call board");
  assert.equal(require("../web/match_playback.js").normalizeSteps([
    {events:[{type:"draw",seat:1}],board:{
      ...before,hand_counts:[13],future_wall:["hidden"]}},
  ]).frames.length,0,"reject malformed board rather than fake it");
}
{
  const playback=require("../web/match_playback.js");
  const initial={
    phase:"await_discard",turn:1,wall_count:48,
    hand_counts:[13,14,13,13],won:[false,false,false,false],
    melds:[[],[],[],[]],discards:[],
  };
  const afterKong={...initial,wall_count:47,hand_counts:[13,11,13,13],
    melds:[[],[{type:"an_gang",tile:null}],[],[]]};
  const packed=playback.normalizeSteps([{
    events:[{type:"an_gang",seat:1,tile:"secret-an-gang"},
      {type:"kong_supplement",seat:1,tile:"secret-tail-draw"}],
    board:{...afterKong,secret_hand:["should-not-leak"]},
  }],80,initial);
  assert.equal(packed.frames.length,1);
  const frame=packed.frames[0];
  assert.equal(frame.isKong,true);
  assert.equal(frame.tailDraw,true);
  assert.equal(frame.important,true);
  assert.equal(frame.chain.length,2);
  assert.ok(frame.label.includes("暗杠"));
  assert.ok(frame.label.includes("杠后补摸"));
  assert.equal(frame.publicTile,null);
  assert.equal(frame.changes.wall,-1);
  assert.equal(frame.changes.backs[1],-3);
  assert.equal(frame.changes.melds[1],1);
  assert.equal(frame.holdScale,1.7);
  for(const secret of ["secret-an-gang","secret-tail-draw","should-not-leak"])
    assert.ok(!JSON.stringify(frame).includes(secret));

  const normal=playback.normalizeSteps([
    {events:[{type:"draw",seat:1}],board:initial},
    {events:[{type:"discard",seat:1,tile:"p2"}],board:initial},
    {events:[{type:"peng",seat:1,tile:"s3"}],board:afterKong},
    {events:[{type:"self_draw_win",seat:3}],board:{...afterKong,
      won:[false,false,false,true]}},
    {events:[{type:"draw",seat:2}],board:afterKong},
  ]);
  assert.equal(playback.highlightFrames(normal.frames).length,3);
  assert.deepEqual(playback.highlightFrames(normal.frames).map(x=>x.type),
    ["peng","self_draw_win","draw"],"final real public frame is retained");
  assert.deepEqual(playback.highlightFrames([]),[]);
}
{
  const timer=fakeClock(),shown=[];let committed=0,ended=0;
  const player=createController({
    onFrame:(frame,index)=>shown.push([frame.type,index]),
    onDone:()=>ended++,onStatus:()=>{},
    clock:timer.set,clearClock:timer.clear,
  });
  const frames=[{type:"an_gang",holdScale:1.7},
    {type:"kong_supplement",holdScale:1},
    {type:"self_draw_win",holdScale:2.2}];
  player.setSpeed(450);
  player.start(frames,()=>committed++);
  assert.deepEqual(timer.delays(),[765],
    "kong must hold longer, without consuming another server action");
  player.pause();
  assert.equal(timer.count(),0);
  player.step();
  assert.equal(shown.length,2);
  assert.equal(player.getState().paused,true);
  assert.equal(timer.count(),0);
  player.step();
  assert.equal(shown.length,3);
  assert.equal(player.getState().paused,true);
  player.step();
  assert.equal(committed,1);
  assert.equal(ended,1);
  assert.equal(player.getState().playing,false);
  player.step();
  assert.equal(committed,1);
  player.start(frames,()=>committed++);
  assert.deepEqual(timer.delays(),[765]);
  player.setSpeed(180);
  assert.deepEqual(timer.delays(),[306]);
  player.skip();
  assert.equal(committed,2);
  assert.equal(timer.count(),0);
}
console.log("M3.18 kong/tail-draw chain, critical-frame focus and paused step: PASS");
console.log("M3.17 recorded public board steps and privacy: PASS");
console.log("M3.16 public replay privacy and pause/skip/speed: PASS");
