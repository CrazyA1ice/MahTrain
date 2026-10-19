/* Browser-only geometry stress fixture, NOT a physically possible Mahjong
 * match: four players each have 56 discards. The actual Python rule and
 * ledger full-round checks run separately in this workflow. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {execFileSync} from "node:child_process";
import {chromium} from "playwright-core";

function chrome(){
 for(const n of ["google-chrome","google-chrome-stable","chromium","chromium-browser"]){
  try{return execFileSync("which",[n],{encoding:"utf8"}).trim()}catch{}
 }
}
const browser=await chromium.launch({headless:true,executablePath:chrome(),
 args:["--no-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errors=[];page.on("pageerror",e=>errors.push(e.message));
let full=false;
const hole=[5,13,24,41];
const makeDiscards=count=>{
 const out=[];
 for(let i=0;i<count;i++)for(let seat=0;seat<4;seat++){
  const obj={seat,tile:"mps"[(i+seat)%3]+String(1+(i+seat*2)%9),
   index:out.length+1};
  if(i===hole[seat])obj.claimed_by=(seat+1)%4;
  out.push(obj);
 }
 return out;
};
const melds=[
 [{type:"peng",tile:"m4"},{type:"ming_gang",tile:"s5"}],
 [{type:"peng",tile:"p7"},{type:"an_gang",tile:null}],
 [{type:"ming_gang",tile:"s2"},{type:"peng",tile:"m6"}],
 [{type:"bu_gang",tile:"p4"},{type:"peng",tile:"s8"}],
];
function view(n){
 return {seat:0,phase:"await_discard",turn:0,dealer:0,wall_count:50,
 hand:["m1","m2","m3","m4","m5","p1","p2","p3","p4","s1","s2","s3","s4","s8"],
 drawn_tile:"s8",hand_counts:[14,7,6,7],
 missing_suits:["p","m","s","p"],won:[false,true,false,false],
 own_melds:melds[0],melds,discards:makeDiscards(n),
 can_self_draw_win:false,kong_options:[],claim_options:[],
 rob_options:[],needs_continue:false,
 win_ledger:{wins:[{winner:1,kind:"ron",main_pattern:"seven_pairs",
  effective_fan:2,total_received:200}],balances:[0,0,0,0],entries:[]},
 kong_ledger:{base:100,balances:[0,0,0,0],events:[],entries:[]},
 settled_balances:[0,0,0,0],public_steps:[]};
}
const calls=[];
await page.route("**/api/action",async route=>{
 const a=route.request().postDataJSON().action;calls.push(a);
 assert.ok(["match_new","match_resume"].includes(a));
 await route.fulfill({status:200,contentType:"application/json",
  body:JSON.stringify({match_token:"river-test-token",match:view(full?56:52)})});
});
const snapshot=()=>page.evaluate(()=>{
 const rect=e=>{
  const r=e.getBoundingClientRect();
  return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,
   width:r.width,height:r.height};
 };
 const classes=["main","xiajia","duimian","shangjia"];
 return {
  table:rect(document.querySelector("#classic-board-host")),
  board:rect(document.querySelector("#classic-game-board")),
  score:rect(document.querySelector("#classic-score")),
  won:document.querySelector("#classic-player-1 .classic-won-badge")?.textContent,
  river:classes.map(cls=>{
   const root=document.querySelector(".he."+cls);
   const grid=root.querySelector(".dapai");
   const tiles=[...grid.querySelectorAll("img.pai")];
   const computed=getComputedStyle(grid);
   const m=[...document.querySelectorAll(".shoupai."+cls+" .fulou .mianzi")];
   return {root:rect(root),grid:rect(grid),count:tiles.length,
    coords:tiles.map(rect),
    tileCodes:tiles.map(t=>t.dataset.pai),
    hidden:tiles.flatMap((e,i)=>e.classList.contains("claimed")?[i]:[]),
    cols:computed.gridTemplateColumns.split(/\s+/).length,
    rows:computed.gridTemplateRows.split(/\s+/).length,
    display:computed.display,melds:m.map(rect),
    redacted:cls==="xiajia"?
     document.querySelectorAll(".shoupai.xiajia .fulou img[data-pai='_']").length:0};
  }),
 };
});
function overlap(a,b){
 return a.left<b.right-0.5 && a.right>b.left+0.5 &&
        a.top<b.bottom-0.5 && a.bottom>b.top+0.5;
}
function audit(s,n){
 assert.equal(s.won,"已胡");
 for(let seat=0;seat<4;seat++){
  const r=s.river[seat];
  assert.equal(r.count,n,"all tile slots seat "+seat);
  assert.equal(r.display,"grid");
  assert.equal(r.cols,14);
  assert.equal(r.rows,4);
  assert.equal(r.melds.length,2);
  assert.deepEqual(r.hidden,[hole[seat]],"claim hole remains seat "+seat);
  assert.ok(!overlap(r.root,s.score),"river container vs score "+seat);
  assert.ok(!overlap(r.grid,s.score),"river cells vs score "+seat);
  for(let i=0;i<r.count;i++){
   const box=r.coords[i];
   assert.ok(box.left>=s.board.left-1&&box.right<=s.board.right+1&&
    box.top>=s.board.top-1&&box.bottom<=s.board.bottom+1,
    "tile inside table seat "+seat+" index "+i);
   for(const meld of r.melds){
    if(overlap(box,meld))console.error("MELD INTERSECTION",JSON.stringify({seat,index:i,tile:box,meld,river:r.root,score:s.score,allMelds:r.melds}));
    assert.ok(!overlap(box,meld),"tile vs own meld seat "+seat+" index "+i);
   }
   assert.match(r.tileCodes[i],/^[mps][1-9]$/);
  }
  const first=r.coords[0],next=r.coords[1],row=r.coords[14];
  if(seat===0)assert.ok(next.left>first.left&&row.top>first.top);
  if(seat===1)assert.ok(next.top<first.top&&row.left>first.left);
  if(seat===2)assert.ok(next.left<first.left&&row.top<first.top);
  if(seat===3)assert.ok(next.top>first.top&&row.left<first.left);
 }
 for(let a=0;a<4;a++)for(let b=a+1;b<4;b++)
  assert.ok(!overlap(s.river[a].root,s.river[b].root),
   "different river zones overlap "+a+"/"+b);
}
try{
 await page.goto("http://127.0.0.1:8765/classic/game.html",{waitUntil:"load"});
 await page.waitForFunction(()=>document.querySelectorAll(".he.main .dapai img.pai").length===52);
 const before=await snapshot();audit(before,52);
 full=true;
 await page.reload({waitUntil:"load"});
 await page.waitForFunction(()=>document.querySelectorAll(".he.main .dapai img.pai").length===56);
 const after=await snapshot();audit(after,56);
 assert.deepEqual(before.table,after.table,
   "a near-full river must not resize/reposition the table");
 assert.deepEqual(calls,["match_new","match_resume"]);
 assert.deepEqual(errors,[]);
 const dir=path.resolve("frontend_2d/test-artifacts");
 fs.mkdirSync(dir,{recursive:true});
 await page.screenshot({path:path.join(dir,"four-native-56-tile-rivers.png"),fullPage:true});
 console.log("FOUR GENUINE MAJIANG RIVERS + CLAIMED HOLES + TWO MELDS PER SEAT: PASS");
 console.log(JSON.stringify({table:after.table,
  zones:after.river.map((r,i)=>({seat:i,river:r.root,redacted:r.redacted}))}));
}finally{await browser.close()}
