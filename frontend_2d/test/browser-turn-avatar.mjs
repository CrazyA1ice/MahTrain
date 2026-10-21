/* M3.87: authentic Chromium classic-seat avatar turn focus, inherited
 * dealer indicator and server-controlled "match_next" action route.
 * Stubbed response uses the authorized server-public-and-seat-zero schema;
 * it tests UI only. Python unit tests check real authoritative outcomes.
 */
import assert from "node:assert/strict";
import {chromium} from "playwright-core";
import {execFileSync} from "node:child_process";

function chrome(){
 for(const path of ["google-chrome","chromium","chromium-browser"]){
  try{return execFileSync("which",[path],{encoding:"utf8"}).trim()}catch{}
 }
}
const classes=["main","xiajia","duimian","shangjia"];
const hand=["m1","m2","m3","m4","m5","m6","m7","p1","p2","p3","s2","s3","s4","s5"];
function state(turn=0,phase="dealer_discard",dealer=0){
 return {
  seat:0,phase,turn,dealer,
  series_round:2,dealer_origin:"首位胡牌玩家坐庄",
  wall_count:56,hand,drawn_tile:null,hand_counts:[14,13,13,13],
  melds:[[],[],[],[]],own_melds:[],discards:[],
  missing_suits:["p","m","s","p"],won:[false,false,false,false],
  claim_options:[],kong_options:[],rob_options:[],
  can_self_draw_win:false,needs_continue:false,
  win_ledger:{balances:[0,0,0,0],wins:[],entries:[]},
  kong_ledger:{balances:[0,0,0,0],events:[],entries:[]},
  settled_balances:[0,0,0,0],public_steps:[],
 };
}
let current=state(0),sent=[];
const browser=await chromium.launch({headless:true,executablePath:chrome(),
 args:["--no-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errors=[];
page.on("pageerror",e=>errors.push(e.message));
page.on("dialog",dialog=>dialog.accept());
await page.route("**/api/action",async route=>{
 const payload=route.request().postDataJSON();
 sent.push(payload.action);
 await route.fulfill({status:200,contentType:"application/json",
  body:JSON.stringify({match_token:"m387-round-token",match:current})});
});
async function rows(){
 return page.evaluate(() => {
  const host=document.querySelector("#classic-board-host").getBoundingClientRect();
  const result=[...Array(4)].map((_,seat)=>{
   const plate=document.querySelector("#classic-player-"+seat);
   const avatar=plate.querySelector(".classic-seat-avatar");
   const rect=plate.getBoundingClientRect();
   return {
    active:plate.classList.contains("classic-seat-active"),
    dealer:plate.classList.contains("classic-seat-dealer"),
    avatar:avatar?.textContent,
    role:plate.getAttribute("aria-label"),
    ring:getComputedStyle(plate).outlineStyle,
    x:rect.x,y:rect.y,width:rect.width,height:rect.height,
   };
  });
  return {board:{x:host.x,y:host.y,w:host.width,h:host.height},result};
 });
}
try{
 await page.goto("http://127.0.0.1:8765/classic/game.html",
  {waitUntil:"load",timeout:30000});
 await page.waitForFunction(()=>
   document.querySelectorAll(".classic-seat-avatar").length===4);
 const initial=await rows();
 assert.deepEqual(initial.result.map(x=>x.avatar),["我","1","2","3"]);
 for(const seat of [0,1,2,3]){
  current=state(seat,"await_discard",1);
  await page.locator("#classic-new").click();
  await page.waitForFunction(expected=>
    [...document.querySelectorAll("#classic-player-0,#classic-player-1,#classic-player-2,#classic-player-3")]
    .filter(x=>x.classList.contains("classic-seat-active")).length===1 &&
    document.querySelector("#classic-player-"+expected).classList.contains("classic-seat-active"),seat);
  const snapshot=await rows();
  assert.deepEqual(snapshot.board,initial.board,"board must not reflow");
  assert.equal(snapshot.result.filter(x=>x.active).length,1);
  assert.equal(snapshot.result[seat].ring,"solid");
  assert.equal(snapshot.result[1].dealer,true);
  assert.match(snapshot.result[seat].role,/当前行动玩家/);
  for(let i=0;i<4;i++)assert.equal(snapshot.result[i].height,
    initial.result[i].height,"seat plate must not resize when turn changes");
 }
 current=state(null,"claim_window",1);
 await page.locator("#classic-new").click();
 await page.waitForFunction(()=>
  [...document.querySelectorAll("#classic-player-0,#classic-player-1,#classic-player-2,#classic-player-3")]
  .every(x=>!x.classList.contains("classic-seat-active")));
 current=state(null,"finished",1);
 current.won=[false,true,true,true];
 current.next_dealer={
  dealer:3,reason:"lost_to_three",label:"输三家，下局坐庄"
 };
 current.win_ledger.wins=[
  {winner:1,source:0,kind:"ron",payers:[0],main_pattern:"standard"},
  {winner:2,source:2,kind:"self_draw",payers:[0,3]},
  {winner:3,source:0,kind:"ron",payers:[0],main_pattern:"standard"},
 ];
 await page.locator("#classic-new").click();
 await page.getByText("下一局 · 继承庄家").waitFor();
 assert.match(await page.locator("#classic-actions-title").innerText(),/下局庄家 3号/);
 assert.match(await page.locator("#classic-actions-title").innerText(),/输三家/);
 current=state(3,"dealer_discard",3);
 await page.getByText("下一局 · 继承庄家").click();
 await page.waitForFunction(()=>
  document.querySelector("#classic-player-3").classList.contains("classic-seat-active") &&
  document.querySelector("#classic-dealer").textContent==="3号");
 assert.equal(sent.at(-1),"match_next");
 assert.match(await page.locator("#classic-round").textContent(),/第2局/);
 assert.equal(await page.locator("#classic-dealer").getAttribute("title"),
              "首位胡牌玩家坐庄");
 const last=await rows();
 assert.equal(last.result[3].active,true);
 assert.equal(last.result[3].dealer,true);
 assert.deepEqual(last.board,initial.board);
 await page.screenshot({path:"/tmp/m387-dealer-active-avatars.png"});
 assert.deepEqual(errors,[]);
 console.log("M3.87 CLASSIC CHROMIUM FOUR ACTIVE AVATARS + NEXT INHERITED DEALER: PASS");
}finally{await browser.close()}
