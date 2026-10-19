/* M3.73: successive real Chromium state updates MUST NOT resize table.
   Also verify the AI Hu marker survives future turns and a read-only refresh. */
import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {chromium} from "playwright-core";
const chrome=()=>{
 for(const n of ["google-chrome","chromium","chromium-browser"]){
  try{return execFileSync("which",[n],{encoding:"utf8"}).trim()}catch{}
 }
};
const browser=await chromium.launch({executablePath:chrome(),headless:true,
 args:["--no-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errors=[];page.on("pageerror",x=>errors.push(x.message));
const base={
 seat:0,phase:"await_discard",turn:0,dealer:0,wall_count:50,
 hand:["m1","m2","m3","m4","m5","p1","p2","p3","p4","s1","s2","s3","s4","s8"],
 drawn_tile:"s8",hand_counts:[14,13,13,13],
 missing_suits:["p","m","s","p"],won:[false,false,false,false],
 own_melds:[],melds:[[],[],[],[]],discards:[],can_self_draw_win:false,
 kong_options:[],claim_options:[],rob_options:[],needs_continue:false,
 win_ledger:{balances:[0,0,0,0],wins:[],entries:[]},
 kong_ledger:{base:100,balances:[0,0,0,0],events:[],entries:[]},
 settled_balances:[0,0,0,0],public_steps:[],
};
const win={winner:1,source:null,kind:"self_draw",tile:"s6",
 main_pattern:"seven_pairs",effective_fan:2,raw_fan:2,total_received:600,
 amount_per_payer:200,payers:[0,2,3],combinations:{seven_pairs:2},bonuses:{}};
let discards=0;
const responseFor=(act)=>{
 if(act==="match_new")return base;
 if(act==="match_discard")discards++;
 const wasWon=discards>=2;
 return {...base,
  wall_count:50-discards,
  won:[false,wasWon,false,false],
  win_ledger:wasWon?{balances:[-200,600,-200,-200],wins:[win],entries:[]}:base.win_ledger,
  public_steps:[{events:[{type:"discard",seat:discards%4,tile:"p2"}]}],
 };
};
await page.route("**/api/action",async route=>{
 const action=route.request().postDataJSON()?.action;
 await route.fulfill({status:200,contentType:"application/json",
  body:JSON.stringify({match_token:"stable-fixture",match:responseFor(action)})});
});
const geometry=()=>page.evaluate(()=>{
 const table=document.querySelector("#classic-board-host").getBoundingClientRect();
 const game=document.querySelector("#classic-game-board").getBoundingClientRect();
 return {top:table.top+scrollY,left:table.left,width:table.width,height:table.height,
  gameWidth:game.width,gameHeight:game.height};
});
let expectedDiscards=0;
async function discard(){
 const tile=page.locator('.shoupai.main .bingpai img.pai[data-hand-index="0"]');
 await tile.click();await tile.click();
 expectedDiscards++;
 await page.waitForFunction(count=>Number(document.querySelector(
  "#classic-wall-count")?.textContent)===50-count,
  expectedDiscards,{timeout:8000});
}
try{
 await page.goto("http://127.0.0.1:8765/classic/game.html",
  {waitUntil:"load",timeout:30000});
 await page.waitForFunction(()=>document.querySelector(
  '.shoupai.main .bingpai img[data-hand-index="0"]'));
 const start=await geometry();
 assert.equal(await page.locator("#classic-live-action").count(),0,
  "do not mount the transient discard/peng/kong bar anywhere");
 await discard();
 assert.deepEqual(await geometry(),start,"1st ordinary discard must not move table");
 assert.equal(await page.locator("#classic-player-1 .classic-won-badge").count(),0);
 await discard();
 assert.deepEqual(await geometry(),start,"AI Hu record must not resize table");
 const ai=page.locator("#classic-player-1");
 assert.equal(await ai.locator(".classic-won-badge").textContent(),"已胡");
 assert.match(await ai.locator(".classic-won-badge").getAttribute("title"),/自摸 · 七对/);
 assert.match(await page.locator("#classic-score-1").textContent(),/七对 2番/);
 assert.equal(await page.locator("#classic-player-0 .classic-won-badge").count(),0);
 assert.equal(await page.locator("#classic-player-2 .classic-won-badge").count(),0);
 const below=await page.evaluate(()=>{
  const board=document.querySelector("#classic-board-host").getBoundingClientRect();
  const notice=document.querySelector("#classic-win-announcement").getBoundingClientRect();
  return notice.top>=board.bottom-1;
 });
 assert.equal(below,true,"durable Hu history must be below board");
 await page.waitForTimeout(1950);
 assert.equal(await ai.locator(".classic-won-badge").count(),1,
  "Hu marker cannot expire with short-lived action animation");
 await discard();
 assert.deepEqual(await geometry(),start,"subsequent discard must not move table");
 assert.equal(await ai.locator(".classic-won-badge").count(),1);
 await page.reload({waitUntil:"load"});
 await page.waitForFunction(()=>document.querySelector("#classic-player-1")
  ?.classList.contains("classic-seat-won"));
 assert.deepEqual(await geometry(),start,"session resume must retain exact table geometry");
 assert.equal(await ai.locator(".classic-won-badge").count(),1);
 assert.equal(errors.length,0,errors.join("; "));
 console.log("MAJIANG FIXED TABLE + PERSISTENT AI HU: PASS",start);
}finally{
 await browser.close();
}
