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
let cancelled=0;
const fake={
  speechSynthesis:{
    cancel:()=>{cancelled++},
    speak:utterance=>spoken.push({text:utterance.text,lang:utterance.lang}),
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
speaker.announceFrame({announcements:[
  {type:"peng",seat:1,publicTile:"m4"},
  {type:"ming_gang",seat:0,publicTile:"s8"},
]});
assert.equal(spoken[1].text,"1号碰四万。我方明杠八条");
speaker.setEnabled(false);
assert.equal(speaker.announceEvents([{type:"discard",seat:0,publicTile:"m1"}]),false);
assert.equal(spoken.length,2);
const unsupported=api.create({});
assert.equal(unsupported.supported,false);
assert.equal(unsupported.announceFrame({type:"discard",seat:1,publicTile:"m2"}),false);
console.log("M3.24 public action speech, mute, privacy, unsupported browser: PASS");
