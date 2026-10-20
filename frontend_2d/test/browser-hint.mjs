/* Genuine Majiang UI browser: on-demand hints below board, never dynamic
 * above-board banners. HTTP body fixtures match the real read-only contract.
 */
import assert from "node:assert/strict";
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
const errors=[];page.on("pageerror",x=>errors.push(x.message));
const hand=["m1","m1","m1","m4","m4","m4","p1","p1","p1",
 "p4","p4","p4","m9","p9"];
const common={
 seat:0,phase:"await_discard",turn:0,dealer:0,wall_count:34,
 hand,drawn_tile:"p9",hand_counts:[14,13,13,13],
 missing_suits:["s","p","m","p"],won:[false,false,false,false],
 own_melds:[],melds:[[],[],[],[]],discards:[],
 claim_options:[],rob_options:[],kong_options:[],
 can_self_draw_win:false,needs_continue:false,
 win_ledger:{wins:[],balances:[0,0,0,0],entries:[]},
 kong_ledger:{base:100,balances:[0,0,0,0],entries:[],events:[]},
 settled_balances:[0,0,0,0],public_steps:[],
};
const reference={
 status:"choose_discard",interpretation:"public_information_fan_weighted_upper_bound",fan_cap:3,
 forced_missing:false,missing_suit:"s",
 candidates:[
  {discard:"p9",shanten:0,reference_best:true,effective_type_count:1,
   effective_tile_count_upper_bound:2,fan_weighted_unknown_copies:4,
   winning_details:[{tile:"m9",unknown_copies_upper_bound:2,
    main_pattern:"all_pungs",effective_fan:1,multiplier:2,
    tian_ting_applied:false}],
   effective_details:[{tile:"m9",unknown_copies_upper_bound:2}]},
  {discard:"m9",shanten:0,reference_best:false,effective_type_count:1,
   effective_tile_count_upper_bound:1,fan_weighted_unknown_copies:2,
   winning_details:[{tile:"p9",unknown_copies_upper_bound:1,
    main_pattern:"all_pungs",effective_fan:1,multiplier:2,
    tian_ting_applied:false}],
   effective_details:[{tile:"p9",unknown_copies_upper_bound:1}]},
 ]};
const requests=[];
await page.route("**/api/action",async route=>{
 const command=route.request().postDataJSON();
 requests.push(command);
 const hint=command.action==="match_hint";
 const result=hint
  ?{match_token:"hint-browser-token",hint:reference}
  :{match_token:"hint-browser-token",match:{
    ...common,wall_count:command.action==="match_discard"?33:34}};
 await route.fulfill({status:200,contentType:"application/json",
  body:JSON.stringify(result)});
});
const geometry=()=>page.evaluate(()=>{
 const r=document.querySelector("#classic-board-host").getBoundingClientRect();
 return {top:r.top+scrollY,left:r.left,width:r.width,height:r.height};
});
try{
 await page.goto("http://127.0.0.1:8765/classic/game.html",
  {waitUntil:"load"});
 await page.waitForFunction(()=>document.getElementById("classic-hint-trigger")
  && !document.getElementById("classic-hint-trigger").disabled);
 const before=await geometry();
 assert.equal(await page.locator("#classic-hint-panel").isHidden(),true);
 await page.getByRole("button",{name:"查看当前牌效参考"}).click();
 await page.waitForFunction(()=>!document.getElementById("classic-hint-panel").hidden);
 const table=page.locator("#classic-hint-panel");
 assert.match(await table.textContent(),/听牌/);
 assert.match(await table.textContent(),/≤ 2 张/);
 assert.match(await table.textContent(),/九万 ≤2/);
 assert.match(await table.textContent(),/对对胡 1番 ×2/);
 assert.match(await table.textContent(),/≤ 4（倍率加权）/);
 assert.match(await table.textContent(),/听牌番值加权参考/);
 assert.equal(await table.locator("thead th").count(),6);
 assert.match(await table.textContent(),/不是实际期望积分、真实胜率或牌墙剩余张数/);
 assert.equal(await table.locator("tbody tr").count(),2);
 assert.equal(await page.locator('.shoupai.main img[data-tile="p9"].is-hint-cut').count(),1);
 const below=await page.evaluate(()=>{
  const board=document.querySelector("#classic-board-host").getBoundingClientRect();
  const panel=document.querySelector("#classic-hint-panel").getBoundingClientRect();
  return panel.top>=board.bottom-1;
 });
 assert.equal(below,true,"hint panel must be BELOW fixed four-sided table");
 assert.deepEqual(await geometry(),before);
 assert.equal(await page.locator("#classic-live-action").count(),0);
 assert.deepEqual(requests.map(x=>x.action),["match_new","match_hint"]);
 await page.getByRole("button",{name:"收起牌效参考"}).click();
 assert.equal(await table.isHidden(),true);
 assert.equal(await page.locator(".shoupai.main .is-hint-cut").count(),0);
 assert.deepEqual(await geometry(),before);
 await page.getByRole("button",{name:"查看当前牌效参考"}).click();
 await page.waitForFunction(()=>!document.getElementById("classic-hint-panel").hidden);
 const tile=page.locator('.shoupai.main img[data-tile="p9"]');
 await tile.click();await tile.click();
 await page.waitForFunction(()=>document.querySelector("#classic-wall-count")
  ?.textContent==="33");
 assert.equal(await table.isHidden(),true,"discard must revoke old hints");
 assert.equal(await page.locator(".shoupai.main .is-hint-cut").count(),0);
 assert.deepEqual(requests.map(x=>x.action),
  ["match_new","match_hint","match_hint","match_discard"]);
 assert.deepEqual(await geometry(),before);
 assert.deepEqual(errors,[]);
 console.log("REAL MAJIANG UI: PUBLIC HINTS ONLY BELOW FIXED BOARD / DISCARD INVALIDATES: PASS");
}finally{await browser.close()}
