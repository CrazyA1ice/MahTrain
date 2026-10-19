/* A completed Mahjong game must remain reviewable across page refreshes.
 * This is a genuine Chromium + real compiled Majiang UI test with mocked
 * server-authoritative responses; no dummy title-only HTML is used.
 */
import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {chromium} from "playwright-core";

function browserPath(){
 for(const exe of ["google-chrome","google-chrome-stable","chromium","chromium-browser"]){
  try{return execFileSync("which",[exe],{encoding:"utf8"}).trim()}catch{}
 }
 return undefined;
}
const browser=await chromium.launch({headless:true,executablePath:browserPath(),
 args:["--no-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const KEY="mahtrain.match.session.v1";
const hand=["m1","m2","m3","m4","m5","p1","p2","p3","p4","s1","s2","s3","s4"];
const common={
 seat:0,turn:0,dealer:0,hand,drawn_tile:null,hand_counts:[13,13,13,13],
 missing_suits:["p","m","s","p"],won:[false,false,false,false],
 own_melds:[],melds:[[],[],[],[]],discards:[],wall_count:9,
 can_self_draw_win:false,kong_options:[],claim_options:[],rob_options:[],
 public_steps:[],needs_continue:false,
};
const final={
 ...common,phase:"finished",won:[false,true,false,false],
 win_ledger:{wins:[{winner:1,source:null,kind:"self_draw",tile:"m8",
  main_pattern:"seven_pairs",raw_fan:2,effective_fan:2,
  payers:[0,2,3],amount_per_payer:200,total_received:600,
  combinations:{seven_pairs:2},bonuses:{}}],
  balances:[-200,600,-200,-200],entries:[]},
 kong_ledger:{base:100,balances:[0,0,0,0],events:[],entries:[]},
 settled_balances:[-200,600,-200,-200],
 exhaustive_settlement:null,
};
const fresh={
 ...common,phase:"await_discard",wall_count:56,
 win_ledger:{wins:[],balances:[0,0,0,0],entries:[]},
 kong_ledger:{base:100,balances:[0,0,0,0],events:[],entries:[]},
 settled_balances:[0,0,0,0],exhaustive_settlement:null,
};
const requests=[];
await page.addInitScript((storageKey)=>{
 // Seed the AUTHENTIC terminal token ONCE. Never fake success by
 // re-injecting the old token each time the browser reloads.
 if(sessionStorage.getItem("__mahtrain_test_once")!=="1"){
  sessionStorage.setItem("__mahtrain_test_once","1");
  sessionStorage.setItem(storageKey,"completed-token");
 }
},KEY);
await page.route("**/api/action",async route=>{
 const input=route.request().postDataJSON();
 requests.push({action:input.action,token:input.match_token});
 const renew=input.action==="match_new";
 const isFresh=renew||input.match_token==="fresh-token";
 await route.fulfill({
  status:200,contentType:"application/json",
  body:JSON.stringify({match:isFresh?fresh:final,
   match_token:isFresh?"fresh-token":"completed-token"}),
 });
});
const getToken=()=>page.evaluate(key=>sessionStorage.getItem(key),KEY);
const geometry=()=>page.evaluate(()=>{
 const table=document.getElementById("classic-board-host").getBoundingClientRect();
 return {top:table.top+window.scrollY,left:table.left,
  width:table.width,height:table.height};
});
async function waitForFinished(){
 await page.waitForFunction(()=>{
  const report=document.getElementById("classic-result-report");
  return report&&!report.hidden&&
   document.querySelector("#classic-player-1 .classic-won-badge");
 },null,{timeout:10000});
}
const errors=[];page.on("pageerror",e=>errors.push(e.message));
try{
 await page.goto("http://127.0.0.1:8765/classic/game.html",
  {waitUntil:"load",timeout:30000});
 await waitForFinished();
 const initial=await geometry();
 assert.equal(await getToken(),"completed-token",
  "finished match must stay available in sessionStorage");
 assert.match(await page.locator("#classic-score-1").textContent(),/七对 2番/);
 assert.match(await page.locator("#classic-result-report").textContent(),/七对/);
 assert.equal(requests.length,1);
 assert.equal(requests[0].action,"match_resume");

 await page.reload({waitUntil:"load"});
 await waitForFinished();
 assert.equal(await getToken(),"completed-token");
 assert.deepEqual(await geometry(),initial,
  "loading a completed game cannot change original table size");
 assert.equal(await page.locator("#classic-player-1 .classic-won-badge").count(),1);
 assert.match(await page.locator("#classic-result-report").textContent(),/七对/);
 assert.deepEqual(requests.map(x=>x.action),["match_resume","match_resume"]);
 assert.ok(requests.every(x=>x.token==="completed-token"),
  "no phantom match_new during finished-game reload");

 await page.getByRole("button",{name:"再来一局"}).click();
 await page.waitForFunction(key=>{
  return sessionStorage.getItem(key)==="fresh-token" &&
   document.getElementById("classic-result-report").hidden;
 },KEY,{timeout:9000});
 assert.equal(await page.locator("#classic-player-1 .classic-won-badge").count(),0,
  "new game must clear the old winner badges");
 assert.deepEqual(await geometry(),initial,
  "new game must reuse the same stable physical Mahjong table");
 assert.equal(requests.at(-1).action,"match_new",
  "only explicit new-round action starts another game");

 await page.reload({waitUntil:"load"});
 await page.waitForFunction(()=>
  document.getElementById("classic-wall-count")?.textContent==="56");
 assert.equal(await getToken(),"fresh-token");
 assert.equal(requests.at(-1).action,"match_resume");
 assert.equal(requests.at(-1).token,"fresh-token");
 assert.deepEqual(await geometry(),initial);
 assert.equal(await page.locator("#classic-player-1 .classic-won-badge").count(),0);
 assert.equal(errors.length,0,errors.join(" | "));
 console.log("CLASSIC COMPLETED GAME REFRESH & EXPLICIT NEW ROUND: PASS",{
  calls:requests,table:initial,
 });
}finally{
 await browser.close();
}
