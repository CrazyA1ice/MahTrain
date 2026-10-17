"use strict";
// M3.24 isolated Web Speech tests: public tile names only and no remote assets.
const assert=require("node:assert/strict");
const api=require("../web/match_voice.js");
assert.equal(api.tileLabel("m1"),"一万");
assert.equal(api.tileLabel("s9"),"九条");
assert.equal(api.tileLabel("p3"),"三筒");
assert.equal(api.tileLabel("private"),"");
assert.equal(api.phrase({type:"discard",seat:1,publicTile:"m5"}),"五万");
assert.equal(api.phrase({type:"peng",seat:3,publicTile:"p2"}),"3号碰二筒");
assert.equal(api.phrase({type:"an_gang",seat:2,publicTile:"s9"}),"2号暗杠",
  "without explicit public reveal marker, never say a concealed card");
assert.equal(api.phrase({type:"an_gang",seat:2,publicTile:"s9",
  exposedKong:true}),"2号暗杠九条");
assert.equal(api.phrase({type:"an_gang",seat:0,publicTile:"m4",
  exposedKong:true}),"我方暗杠四万");
assert.equal(api.phrase({type:"an_gang",seat:3,publicTile:"SECRET",
  exposedKong:true}),"3号暗杠");
assert.equal(api.phrase({type:"multi_ron",winSeats:[1,3],publicTile:"p2"}),
  "1号、3号一炮多响，胡了");
assert.equal(api.phrase({type:"draw",seat:1,publicTile:"s4"}),"");
assert.equal(api.phrase({type:"discard",seat:1,publicTile:"SECRET-HAND"}),"");
const spoken=[];
const spokenRates=[];
let cancelled=0;
const fake={
  speechSynthesis:{
    cancel:()=>{cancelled++},
    speak:utterance=>{spoken.push({text:utterance.text,lang:utterance.lang});
      spokenRates.push(utterance.rate);},
  },
  SpeechSynthesisUtterance:class{
    constructor(text){this.text=text}
  },
};
const speaker=api.create(fake);
assert.equal(speaker.supported,true);
assert.equal(speaker.announceEvents([
  {type:"draw",seat:2,publicTile:"secret-private-draw"},
  {type:"discard",seat:1,publicTile:"p5"},
  {type:"an_gang",seat:2,publicTile:"SECRET-KONG"},
  {type:"self_draw_win",seat:3},
]),true);
assert.deepEqual(spoken[0],
  {text:"五筒。2号暗杠。3号自摸，胡了",lang:"zh-CN"});
assert.ok(cancelled>0);
assert.equal(spokenRates[0],1.12);
assert.equal(speaker.canRepeat(),true);
assert.equal(speaker.getRate(),"normal");
speaker.announceFrame({announcements:[
  {type:"peng",seat:1,publicTile:"m4"},
  {type:"ming_gang",seat:0,publicTile:"s8"},
]});
assert.equal(spoken[1].text,"1号碰四万。我方明杠八条");
speaker.announceFrame({announcements:[
  {type:"an_gang",seat:1,publicTile:"p7",exposedKong:true},
  {type:"kong_supplement",seat:1,publicTile:"hidden"},
]});
assert.equal(spoken[2].text,"1号暗杠七筒",
  "kong supplement identity is never spoken");
speaker.setEnabled(false);
assert.equal(speaker.announceEvents([{type:"discard",seat:0,publicTile:"m1"}]),false);
assert.equal(spoken.length,3);
assert.equal(speaker.canRepeat(),false);
assert.equal(speaker.repeatLast(),false,"mute must block manual replay");
speaker.setEnabled(true);
assert.equal(speaker.repeatLast(),true);
assert.equal(spoken[3].text,"1号暗杠七筒");
assert.equal(speaker.setRate("slow"),"slow");
assert.equal(speaker.announceEvents([{type:"discard",seat:0,publicTile:"m3"}]),true);
assert.equal(spokenRates.at(-1),0.85);
assert.equal(speaker.setRate("fast"),"fast");
assert.equal(speaker.repeatLast(),true);
assert.equal(spokenRates.at(-1),1.35);
assert.equal(speaker.setRate("__proto__"),"fast",
  "unknown or prototype keys cannot change the speech rate");
assert.equal(speaker.setRate("2"),"fast");
assert.equal(speaker.announceEvents([{type:"draw",seat:1,publicTile:"m5"}]),false);
assert.equal(spoken.at(-1).text,"三万",
  "hidden AI draw must never be remembered for replay");
speaker.reset();
assert.equal(speaker.canRepeat(),false);
assert.equal(speaker.repeatLast(),false,"new game clears previous round speech");
assert.equal(speaker.announceEvents([{type:"an_gang",seat:1,publicTile:"SECRET"}]),true);
assert.equal(spoken.at(-1).text,"1号暗杠");
const unsupported=api.create({});
assert.equal(unsupported.supported,false);
assert.equal(unsupported.canRepeat(),false);
assert.equal(unsupported.repeatLast(),false);
assert.equal(unsupported.setRate("slow"),"slow");
assert.equal(unsupported.announceFrame({type:"discard",seat:1,publicTile:"m2"}),false);
// End/failed/muted speech must release the next-turn gate; speaking a
// public discard is ONLY the tile name, not the player identity.
(async()=>{
  let finishUtterance,watchdog;
  const delayed=api.create({
    speechSynthesis:{
      cancel(){},speak(utterance){finishUtterance=utterance;}
    },
    SpeechSynthesisUtterance:class{constructor(text){this.text=text;}},
    setTimeout(fn){watchdog=fn;return 17;},
    clearTimeout(){watchdog=null;},
  });
  let resolved=false;
  const announced=delayed.announceFrameWait({
    type:"discard",seat:1,publicTile:"s7",
  }).then(()=>{resolved=true;});
  await Promise.resolve();
  assert.equal(resolved,false,"next seat cannot play during spoken tile");
  assert.equal(finishUtterance.text,"七条");
  finishUtterance.onend();
  await announced;
  assert.equal(resolved,true);
  assert.equal(watchdog,null);
  // Hung synthesis must release on the watchdog, not freeze an entire game.
  const stalled=delayed.announceFrameWait({
    type:"discard",seat:2,publicTile:"p6"
  });
  assert.equal(finishUtterance.text,"六筒");
  watchdog();
  await stalled;
  const muted=delayed.setEnabled(false);
  assert.equal(muted,false);
  await delayed.announceFrameWait({type:"discard",seat:2,publicTile:"p4"});
  const noAudio=api.create({});
  await noAudio.announceFrameWait({type:"discard",seat:3,publicTile:"m2"});
  console.log("M3.40 tile-only speech and onend/error/watchdog turn gate: PASS");
})().catch(e=>{console.error(e);process.exitCode=1});
console.log("M3.37 speech rate, public-only replay, reset, mute and privacy: PASS");
