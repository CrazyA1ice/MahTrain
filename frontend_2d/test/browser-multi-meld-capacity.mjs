/* M3.85 true Chromium layout capacity regression.
 * All 4 seats, four actual meld groups, draw-discard after reflow,
 * mixed pong/kongs, and narrow side rack must stay single-row.
 * Scenario fixtures use only the server's authorized PUBLIC-view schema;
 * they test CSS geometry, not claim to be complete real-game outcomes.
 */
import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {chromium} from "playwright-core";

const chrome=()=>{
 for(const name of ["google-chrome","chromium","chromium-browser"]){
  try{return execFileSync("which",[name],{encoding:"utf8"}).trim()}catch{}
 }
};
const CLS=["main","xiajia","duimian","shangjia"];
const TILES=["m1","m4","p2","s7"];
const all=["ming_gang","an_gang","bu_gang","peng"];

function fixture(kinds){
 const groups=[[],[],[],[]],discards=[];
 for(let owner=0;owner<4;owner++){
  for(let i=0;i<kinds.length;i++){
   const kind=kinds[i],tile=TILES[i];
   groups[owner].push(kind==="an_gang"
    ?{type:kind,tile,revealed:true}:{type:kind,tile});
   if(["ming_gang","bu_gang","peng"].includes(kind)){
    // Various REAL claimant-relative seats; never hardcode one direction
    // based on the viewer or the owner seat.
    discards.push({
     seat:(owner+([3,2,1,3][i]))%4,tile,claimed_by:owner,
    });
   }
  }
 }
 const remaining=14-3*kinds.length;
 const hand=Array.from({length:remaining},(_,i)=>[
  "m2","m3","m5","p1","p3","p4","p5","s1","s2","s3","s4","s8","s9","p6"
 ][i]);
 return {
  seat:0,phase:"await_discard",turn:0,dealer:0,wall_count:47,
  hand,drawn_tile:null,hand_counts:[remaining,remaining,remaining,remaining],
  missing_suits:["p","m","s","p"],won:[false,false,false,false],
  own_melds:groups[0],melds:groups,discards,
  kong_options:[],claim_options:[],rob_options:[],
  can_self_draw_win:false,needs_continue:false,
  win_ledger:{balances:[0,0,0,0],wins:[],entries:[]},
  kong_ledger:{base:100,balances:[0,0,0,0],events:[],entries:[]},
  settled_balances:[0,0,0,0],public_steps:[],
 };
}
let state=fixture(["ming_gang","ming_gang","ming_gang","ming_gang"]);
const browser=await chromium.launch({headless:true,executablePath:chrome(),
 args:["--no-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errors=[];
page.on("pageerror",e=>errors.push(e.message));
page.on("dialog",dialog=>dialog.accept());
await page.route("**/api/action",async route=>{
 await route.fulfill({status:200,contentType:"application/json",
  body:JSON.stringify({match_token:"m385-four-meld-fixture",match:state})});
});

async function geometry(){
 return page.evaluate(classes=>{
  const host=document.querySelector("#classic-board-host").getBoundingClientRect();
  const score=document.querySelector("#classic-score");
  return {host:{x:host.x,y:host.y,width:host.width,height:host.height},
   scorescore:score?.getBoundingClientRect().toJSON(),
   rows:classes.map(cls=>{
    const root=document.querySelector(".shoupai."+cls);
    const hand=root.querySelector(".bingpai"),fulou=root.querySelector(".fulou");
    const nodes=[...fulou.children].filter(x=>x.classList.contains("mianzi"));
    return {
     cls,rootWidth:root.offsetWidth,handWidth:hand.offsetWidth,
     handOffsetLeft:hand.offsetLeft,handOffsetTop:hand.offsetTop,
     fulouOffsetTop:fulou.offsetTop,fulouOffsetLeft:fulou.offsetLeft,
     fulouWidth:fulou.offsetWidth,
     meldCount:root.dataset.meldCount,
     compact:getComputedStyle(root).getPropertyValue("--mh-kong-w").trim(),
     direction:getComputedStyle(fulou).flexDirection,
     wrap:getComputedStyle(fulou).flexWrap,
     nodes:nodes.map(x=>({
      x:x.offsetLeft,w:x.offsetWidth,y:x.offsetTop,h:x.offsetHeight,
      kind:x.querySelector(".mahtrain-kong")?.dataset.kongType||
       "peng",
      source:x.querySelector(".mahtrain-kong")?.dataset.claimPosition,
      tiles:x.querySelectorAll("img.pai").length,
      overlay:x.querySelectorAll(".mahtrain-kong-overlay").length,
     })),
     styles:{
      width:getComputedStyle(root).width,
      overflow:getComputedStyle(root).overflow,
     },
    };
   })};
 },CLS);
}
async function update(kinds){
 state=fixture(kinds);
 await page.locator("#classic-new").click();
 await page.waitForFunction(count=>[...document.querySelectorAll(
  ".shoupai")].length===4 && [...document.querySelectorAll(
  ".shoupai")].every(x=>x.dataset.meldCount===String(count) &&
  x.querySelectorAll(".fulou .mianzi").length===count),kinds.length);
 return geometry();
}

try{
 await page.goto("http://127.0.0.1:8765/classic/game.html",
  {waitUntil:"load",timeout:30000});
 await page.waitForFunction(()=>[...document.querySelectorAll(".shoupai")]
  .every(x=>x.querySelectorAll(".fulou .mianzi").length===4),
 null,{timeout:12000});
 const base=await geometry();
 for(const kinds of [
  ["ming_gang","ming_gang","ming_gang","ming_gang"],
  ["bu_gang","an_gang","ming_gang","peng"],
  ["peng","ming_gang","bu_gang","peng"],
  ["ming_gang","ming_gang","ming_gang"],
  ["an_gang","ming_gang"],
  ["bu_gang"],
 ]){
  const {rows,host}=await update(kinds);
  assert.deepEqual(host,base.host,"changing meld count MUST NOT move board");
  for(const row of rows){
   assert.equal(row.nodes.length,kinds.length,row.cls+" group count");
   assert.equal(row.meldCount,String(kinds.length));
   assert.equal(row.direction,"row-reverse",row.cls+" owner reading order");
   assert.equal(row.wrap,"nowrap",row.cls+" no meld wrapping");
   assert.equal(row.compact,kinds.length===4?"26px":"30px");
   assert.ok(row.fulouWidth>0,"meld row must have actual width");
   assert.ok(row.fulouWidth+row.handWidth<=row.rootWidth+1,
    row.cls+" hand+melds exceed original "+row.rootWidth+
    "px available: "+JSON.stringify(row));
   const sorted=[...row.nodes].sort((a,b)=>a.x-b.x);
   for(let i=1;i<sorted.length;i++){
    assert.ok(sorted[i].x>=sorted[i-1].x+sorted[i-1].w-1,
     row.cls+" meld groups overlap: "+JSON.stringify(sorted));
   }
   assert.ok(sorted[0].x>=-1,row.cls+" left meld cropped");
   assert.ok(sorted.at(-1).x+sorted.at(-1).w<=row.fulouWidth+1,
    row.cls+" right meld cropped: "+JSON.stringify(row));
   if(kinds.length===4){
    assert.equal(row.nodes.filter(x=>x.overlay===1).length,
     kinds.filter(x=>x==="bu_gang").length,
     row.cls+" supplement stacks still visible");
   }
  }
  if(kinds.length===4){
   const file=kinds.every(x=>x==="ming_gang")
    ?"four-ming-gang":"mixed-four-meld";
   await page.screenshot({path:"/tmp/m385-"+file+".png"});
  }
 }
 assert.deepEqual(errors,[],"browser must not log fatal exceptions");
 console.log("M3.85 4-SEAT 4-MELD CAPACITY/FLEX/BOARD GEOMETRY: PASS");
}finally{await browser.close()}
