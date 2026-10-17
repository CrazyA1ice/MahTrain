"use strict";
// M3.24 isolated Web Speech tests: public tile names only and no remote assets.
const assert=require("node:assert/strict");
const api=require("../web/match_voice.js");
assert.equal(api.tileLabel("m1"),"一万");
assert.equal(api.tileLabel("s9"),"九条");
assert.equal(api.tileLabel("p3"),"三筒");
assert.equal(api.tileLabel("private"),"");
assert.equal(api.phrase({type:"discard",seat:1,publicTile:"m5"}),"1号打五万");
assert.equal(api.phrase({type:"peng",seat:3,publicTile:"p2"}),"3号碰二筒");
assert.equal(api.phrase({type:"an_gang",seat:2,publicTile:"s9"}),"2号暗杠");
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
  {text:"1号打五筒。2号暗杠。3号自摸，胡了",lang:"zh-CN"});
assert.ok(cancelled>0);
assert.equal(spokenRates[0],1.12);
assert.equal(speaker.canRepeat(),true);
assert.equal(speaker.getRate(),"normal");
speaker.announceFrame({announcements:[
  {type:"peng",seat:1,publicTile:"m4"},
  {type:"ming_gang",seat:0,publicTile:"s8"},
]});
assert.equal(spoken[1].text,"1号碰四万。我方明杠八条");
speaker.setEnabled(false);
assert.equal(speaker.announceEvents([{type:"discard",seat:0,publicTile:"m1"}]),false);
assert.equal(spoken.length,2);
assert.equal(speaker.canRepeat(),false);
assert.equal(speaker.repeatLast(),false,"mute must block manual replay");
speaker.setEnabled(true);
assert.equal(speaker.repeatLast(),true);
assert.equal(spoken[2].text,"1号碰四万。我方明杠八条");
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
assert.equal(spoken.at(-1).text,"我方打三万",
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
console.log("M3.37 speech rate, public-only replay, reset, mute and privacy: PASS");
