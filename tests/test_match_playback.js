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
{
  // Next visible move must wait for BOTH the animation hold and actual
  // speech completion; pause/skip invalidate pending async completions.
  (async()=>{
    const clock=fakeClock();
    let releaseSpeech;
    let seen=0;
    const player=createController({
      onFrame:()=>{
        seen++;
        return seen===1?new Promise(resolve=>{releaseSpeech=resolve;}):undefined;
      },
      onDone:()=>{},onStatus:()=>{},
      clock:clock.set,clearClock:clock.clear,
    });
    player.setSpeed(180);
    player.start([{type:"discard"},{type:"discard"}]);
    clock.tick();
    assert.equal(seen,1,"timer alone must not launch next player");
    releaseSpeech();
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(seen,2,"speech onend unlocks the next visible frame");
    player.skip();
    assert.equal(clock.count(),0);
  })().catch(e=>{console.error(e);process.exitCode=1;});
}
{
  const playback=require("../web/match_playback.js");
  const board={
    phase:"await_draw",turn:2,wall_count:40,
    hand_counts:[13,13,13,13],
    melds:[[],[],[],[]],discards:[],
    won:[false,true,false,true],
  };
  const frame=playback.normalizeSteps([{
    events:[
      {type:"win_settlement",seat:1,source:0,
        kind:"ron",effective_fan:2,amount:800,
        payers:[0],amount_per_payer:800,
        private_hand:["m1"]},
      {type:"win_settlement",seat:3,source:0,
        kind:"ron",effective_fan:1,amount:400,
        payers:[0],amount_per_payer:400,
        future_wall:["p9"]},
      {type:"multi_ron",source:0,seats:[1,3],tile:"p5"},
    ],
    board,
  }]).frames[0];
  assert.equal(frame.isWin,true);
  assert.equal(frame.type,"multi_ron");
  assert.deepEqual(frame.winSeats,[1,3]);
  assert.equal(frame.settlements.length,2);
  assert.deepEqual(frame.settlements.map(x=>x.amount),[800,400]);
  assert.deepEqual(frame.settlements.map(x=>x.seat),[1,3]);
  assert.deepEqual(frame.settlements.map(x=>x.payers),[[0],[0]]);
  assert.deepEqual(frame.settlements.map(x=>x.amount_per_payer),[800,400]);
  const malformed=playback.normalizeSteps([{
    events:[
      {type:"win_settlement",seat:1,amount:1000,effective_fan:2,
        payers:[0,0],amount_per_payer:500,private_hand:["hidden"]},
      {type:"self_draw_win",seat:1}
    ],board,
  }]).frames[0];
  assert.equal(malformed.settlements[0].amount,1000);
  assert.deepEqual(malformed.settlements[0].payers,[],
    "malformed payer list must not fabricate debit notices");
  assert.equal(malformed.settlements[0].amount_per_payer,null);
  const selfDraw=playback.normalizeSteps([{
    events:[
      {type:"win_settlement",seat:2,amount:1200,effective_fan:2,
        payers:[0,1,3],amount_per_payer:400},
      {type:"self_draw_win",seat:2}
    ],board,
  }]).frames[0];
  assert.deepEqual(selfDraw.settlements[0].payers,[0,1,3]);
  assert.ok(!JSON.stringify(frame).includes("private_hand"));
  assert.ok(!JSON.stringify(frame).includes("future_wall"));
  const invalid=playback.normalizeSteps([{
    events:[
      {type:"win_settlement",seat:5,amount:100,effective_fan:1},
      {type:"win_settlement",seat:1,amount:-5,effective_fan:1},
      {type:"self_draw_win",seat:1},
    ],board,
  }]).frames[0];
  assert.deepEqual(invalid.settlements,[]);
}
{
  const playback=require("../web/match_playback.js");
  const start={
    phase:"await_discard",turn:0,wall_count:54,
    hand_counts:[14,13,10,13],
    melds:[[],[],[{type:"an_gang",tile:"secret-kong"}],[]],
    won:[false,false,false,false],discards:[],
    hand:["hidden-self"],future_wall:["hidden-wall"],
  };
  const first={...start,wall_count:53,turn:1,
    hand_counts:[13,14,10,13]};
  const settled={...first,phase:"finished",
    hand_counts:[13,13,10,13],won:[false,true,false,false],
    discards:[{seat:1,tile:"p8",discard_kind:"tedashi",
      private_tile:"never-forward"}]};
  const opening=playback.openingFrame(start);
  assert.equal(opening.board.melds[2][0].tile,null);
  assert.equal(opening.board.wall_count,54);
  const steps=playback.normalizeHistorySteps([
    {events:[{type:"exchange_selected",seat:2,
      tiles:["private"]}],board:first},
    {events:[{type:"discard",seat:1,tile:"p8"}],board:settled},
    {events:[{type:"win_settlement",seat:1,amount:24,
      effective_fan:2,private_hand:["danger"]},
      {type:"self_draw_win",seat:1}],board:settled},
  ],start);
  assert.equal(steps.length,3);
  assert.equal(steps[0].type,"state",
    "a real post-rule state with no playable event must be preserved");
  assert.equal(steps[0].board.wall_count,53);
  assert.equal(steps[1].publicTile,"p8");
  assert.equal(steps[2].settlements[0].amount,24);
  const all=[opening,...steps];
  assert.equal(playback.filterReviewEntries(all,"all","all").length,4);
  assert.equal(playback.filterReviewEntries(all,"1","win").length,1);
  assert.equal(playback.filterReviewEntries(all,"1","discard").length,1);
  assert.equal(playback.filterReviewEntries(all,"3","all").length,0);
  assert.equal(playback.filterReviewEntries(all,"all","key").length,1);
  assert.equal(playback.filterReviewEntries(all,"-1","all").length,0);
  assert.equal(playback.filterReviewEntries(all,"all","malicious").length,0);
  for(const forbidden of ["secret-kong","hidden-self","hidden-wall",
      "private_tile","never-forward","private_hand","danger","exchange_selected"]){
    assert.ok(!JSON.stringify(all).includes(forbidden),
      forbidden+" must not survive public review normalization");
  }
  assert.equal(playback.openingFrame({hand_counts:[2]}),null);
}
console.log("M3.21 public history archive and seat/type filter privacy: PASS");
console.log("M3.20 multi-ron settlement grouping and payment privacy: PASS");
console.log("M3.18 kong/tail-draw chain, critical-frame focus and paused step: PASS");
console.log("M3.17 recorded public board steps and privacy: PASS");
console.log("M3.16 public replay privacy and pause/skip/speed: PASS");
