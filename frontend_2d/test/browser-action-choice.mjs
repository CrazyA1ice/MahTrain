/* Run genuine Majiang UI in Chromium, drive actual DOM buttons and cards.
 * Authoritative API responses are fixed fixtures; gameplay rules remain in
 * Python and are separately tested by real full-match HTTP integration.
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
const hand=["m4","m4","m4","m4","p7","p1","p2","p3",
 "s1","s2","s3","s4","s8","s8"];
const common={
 seat:0,turn:0,dealer:0,wall_count:36,hand,drawn_tile:"s8",
 hand_counts:[14,13,13,13],missing_suits:["p","m","s","p"],
 won:[false,false,false,false],own_melds:[],melds:[[],[],[],[]],
 discards:[],kong_options:[],can_self_draw_win:false,claim_options:[],
 rob_options:[],claim_submitted:[],needs_continue:false,
 win_ledger:{wins:[],balances:[0,0,0,0],entries:[]},
 kong_ledger:{base:100,balances:[0,0,0,0],events:[],entries:[]},
 settled_balances:[0,0,0,0],public_steps:[],
};
const start={...common,phase:"await_discard",can_self_draw_win:true,
 kong_options:[{type:"an_gang",tile:"m4"},{type:"bu_gang",tile:"p7"}]};
const claimed={...common,phase:"claim_window",turn:3,
 pending_discard:{seat:3,tile:"p5"},drawn_tile:null,
 claim_options:["pass","hu","peng","ming_gang"]};
const rob={...common,phase:"rob_kong_window",turn:2,
 pending_rob_kong:{seat:2,tile:"s8"},drawn_tile:null,
 rob_options:["pass","hu"]};
let discardCount=0;const commands=[];
let current=start;
const sampleActionAdvice=()=>{
 const options=current.phase==="claim_window"?
   ["hu","ming_gang","peng","pass"]:
   current.phase==="rob_kong_window"?["hu","pass"]:
   ["hu","an_gang","bu_gang","pass"];
 const labels={hu:"胡",ming_gang:"明杠",peng:"碰",
   pass:"过",an_gang:"暗杠 四万",bu_gang:"补杠 七筒"};
 const candidates=options.map(action=>({
   action,tile:action==="an_gang"?"m4":action==="bu_gang"?"p7":null,
   label:labels[action],shanten:action==="hu"?null:1,
   effective_copies:action==="hu"?null:6,
   fan_weighted:action==="hu"?null:6,
   reason:action==="hu"?"规则已确认可立即胡牌":"公开牌效对照",
   reference_best:action==="hu",
 }));
 return {status:"choose_operation",seat:0,phase:current.phase,
   recommended:{action:"hu",tile:null},candidates,
   limitations:"仅为单步牌效参考，并非已知牌墙的完全信息最优。"};
};
const responseFor=cmd=>{
 if(cmd.action==="match_new")return start;
 if(cmd.action==="match_kong")return claimed;
 if(cmd.action==="match_claim")return rob;
 if(cmd.action==="match_rob")return commonAwait();
 if(cmd.action==="match_discard"){
  discardCount++;
  return {...commonAwait(),wall_count:36-discardCount};
 }
 return start;
};
const commonAwait=()=>({...common,phase:"await_discard",turn:0,
 can_self_draw_win:false,kong_options:[]});
await page.route("**/api/action",async route=>{
 const command=route.request().postDataJSON();
 commands.push(command);
 if(command.action==="match_operation_hint"){
  await route.fulfill({status:200,contentType:"application/json",
   body:JSON.stringify({match_token:"claim-ux-browser-fixture",
    hint:sampleActionAdvice()})});
  return;
 }
 current=responseFor(command);
 await route.fulfill({status:200,contentType:"application/json",
  body:JSON.stringify({match_token:"claim-ux-browser-fixture",
   match:current})});
});
const rect=()=>page.evaluate(()=>{
 const r=document.querySelector("#classic-board-host").getBoundingClientRect();
 return {top:r.top+scrollY,left:r.left,width:r.width,height:r.height};
});
try{
 await page.goto("http://127.0.0.1:8765/classic/game.html",
  {waitUntil:"load",timeout:30000});
 await page.waitForFunction(()=>document.querySelector("#classic-actions-title")
  ?.textContent?.includes("可自摸或杠"));
 const baseline=await rect();
 const labels=()=>page.locator("#classic-actions-buttons button").allTextContents();
 assert.deepEqual(await labels(),["自摸胡","暗杠 四万","补杠 七筒"]);
 assert.equal(await page.locator("#classic-live-action").count(),0);
 await page.getByRole("button",{name:"暗杠 四万"}).click();
 await page.waitForFunction(()=>document.querySelector("#classic-actions-title")
  ?.textContent?.includes("3号AI打出五筒"));
 assert.deepEqual(await rect(),baseline,"claim options may not move table");
 assert.deepEqual(await labels(),["胡","明杠","碰","过"]);
 await page.getByRole("button",{name:"碰",exact:true}).click();
 await page.waitForFunction(()=>document.querySelector("#classic-actions-title")
  ?.textContent?.includes("2号AI补杠八条"));
 assert.deepEqual(await labels(),["抢杠胡","过"],
  "rob-kong must never offer a misleading Peng or Kong");
 assert.deepEqual(await rect(),baseline);
 await page.getByRole("button",{name:"过",exact:true}).click();
 await page.waitForFunction(()=>document.querySelector(
  "#classic-actions-title")?.textContent==="");
 assert.equal(await page.locator("#classic-actions-buttons button").count(),0);

 const first=page.locator('.shoupai.main .bingpai img[data-hand-index="12"]');
 await first.focus();
 await page.keyboard.press("Enter");
 const focused=await page.evaluate(()=>document.activeElement?.dataset.handIndex);
 assert.equal(focused,"12","Shoupai redraw must retain keyboard focus on exact card");
 assert.equal(await first.evaluate(e=>e.classList.contains("is-picked")),true);
 await page.keyboard.press("Escape");
 assert.equal(await first.evaluate(e=>e.classList.contains("is-picked")),false);
 assert.equal(commands.filter(x=>x.action==="match_discard").length,0,
  "escape never transmits a match action");
 await page.locator('.shoupai.main .bingpai img[data-hand-index="13"]').focus();
 await page.keyboard.press("Enter");await page.keyboard.press("Enter");
 await page.waitForFunction(()=>document.querySelector("#classic-wall-count")
  ?.textContent==="35");
 const discards=()=>commands.filter(x=>x.action==="match_discard");
 assert.deepEqual(discards().map(x=>({tile:x.tile,from_draw:x.from_draw})),
  [{tile:"s8",from_draw:true}]);
 const older=page.locator('.shoupai.main .bingpai img[data-hand-index="12"]');
 await older.click();await older.click();
 await page.waitForFunction(()=>document.querySelector("#classic-wall-count")
  ?.textContent==="34");
 assert.deepEqual(discards().map(x=>({tile:x.tile,from_draw:x.from_draw})),
  [{tile:"s8",from_draw:true},{tile:"s8",from_draw:false}],
  "two identical tile faces must preserve drawn vs hand physical copy");
 const mutations=commands.filter(x=>
  x.action!=="match_operation_hint"&&x.action!=="match_new");
 assert.deepEqual(mutations.slice(0,3).map(x=>({action:x.action,kind:x.kind,
  choice:x.choice,tile:x.tile})),[
   {action:"match_kong",kind:"an_gang",choice:undefined,tile:"m4"},
   {action:"match_claim",kind:undefined,choice:"peng",tile:undefined},
   {action:"match_rob",kind:undefined,choice:"pass",tile:undefined},
 ]);
 assert.ok(commands.some(x=>x.action==="match_operation_hint"),
  "a real Hu/kong/claim window must query the read-only action reference");
 assert.deepEqual(await rect(),baseline,"no human action may resize the table");
 assert.deepEqual(errors,[]);
 console.log("CLASSIC CHINESE DECISIONS + ROB KONG + KEYBOARD + DRAWN COPY: PASS",
  commands.map(x=>x.action));
}finally{await browser.close()}
