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
console.log("M3.16 public replay privacy and pause/skip/speed: PASS");
