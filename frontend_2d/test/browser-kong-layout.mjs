/* M3.84: actual Chromium SVG/GIF layout for the 4 rotated Mahjong seats.
 * The stub only provides a realistic AUTHORIZED public-view contract.
 * Python remains the game authority; no opponent hand or wall peeking.
 */
import assert from "node:assert/strict";
import {chromium} from "playwright-core";
import {execFileSync} from "node:child_process";

function chrome(){
 for(const exe of ["google-chrome","chromium","chromium-browser"]){
  try {return execFileSync("which",[exe],{encoding:"utf8"}).trim()}catch{}
 }
}
const CLS=["main","xiajia","duimian","shangjia"];
const TILES=["m1","p2","s3","m4"];
const fixture=(kind,relative)=>{
 const melds=[[],[],[],[]],discards=[];
 for(let owner=0;owner<4;owner++){
  const tile=TILES[owner];
  melds[owner]=[kind==="an_gang"
   ?{type:kind,tile,revealed:true}:{type:kind,tile}];
  if(kind!=="an_gang"){
   discards.push({seat:(owner+relative)%4,tile,claimed_by:owner});
  }
 }
 return {
  seat:0,phase:"await_discard",turn:0,dealer:0,wall_count:50,
  hand:["m2","m3","m5","m6","m7","m8","p1","p3","p4","p5","p6","s1","s2","s4"],
  drawn_tile:"s4",hand_counts:[14,10,10,10],
  missing_suits:["p","m","s","p"],
  won:[false,false,false,false],
  own_melds:melds[0],melds,discards,
  kong_options:[],claim_options:[],rob_options:[],
  can_self_draw_win:false,needs_continue:false,
  win_ledger:{balances:[0,0,0,0],wins:[],entries:[]},
  kong_ledger:{base:100,balances:[0,0,0,0],events:[],entries:[]},
  settled_balances:[0,0,0,0],public_steps:[],
 };
};
let current=fixture("ming_gang",3);
const browser=await chromium.launch({headless:true,executablePath:chrome(),
 args:["--no-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errors=[];
page.on("pageerror",e=>errors.push(e.message));
// The real "random new match" button requires explicit user confirmation.
page.on("dialog",dialog=>dialog.accept());
await page.route("**/api/action",async route=>{
 await route.fulfill({status:200,contentType:"application/json",
  body:JSON.stringify({match_token:"kong-ui-test",match:current})});
});
const getState=()=>page.evaluate(classes=>{
 return classes.map(cls=>{
  const board=document.querySelector("#classic-board-host").getBoundingClientRect();
  const parent=document.querySelector(".shoupai."+cls);
  const group=parent.querySelector(".fulou .mahtrain-kong");
  if(!group)return {missing:true};
  const tiles=[...group.querySelectorAll("img.pai")];
  return {
   kind:group.dataset.kongType,
   position:group.dataset.claimPosition,
   roles:[...group.querySelectorAll(".mahtrain-kong-slot")]
     .map(x=>x.dataset.role),
   orientations:[...group.querySelectorAll(".mahtrain-kong-slot")]
     .map(x=>x.dataset.orientation),
   stackCount:group.querySelectorAll(".mahtrain-kong-overlay").length,
   tileFaces:tiles.map(t=>t.dataset.pai),
   rotation:getComputedStyle(parent).transform,
   groupWidth:group.getBoundingClientRect().width,
   tableWidth:board.width,
   tableHeight:board.height,
  };
 });
},CLS);
try{
 await page.goto("http://127.0.0.1:8765/classic/game.html",
  {waitUntil:"load",timeout:30000});
 try{
  await page.waitForFunction(()=>
   document.querySelectorAll(".mahtrain-kong").length===4,null,{timeout:12000});
 }catch(err){
  const diagnostic=await page.evaluate(()=>({
   status:document.querySelector("#classic-status")?.textContent,
   melds:[...document.querySelectorAll(".shoupai .fulou")].map(el=>({
    className:el.parentElement?.className,
    html:el.innerHTML.slice(0,1200),
   })),
   scripts:[...document.scripts].map(x=>x.src||x.type),
  }));
  console.error("M3.84 BROWSER STATE:",JSON.stringify(diagnostic));
  console.error("M3.84 PAGE ERRORS:",JSON.stringify(errors));
  throw err;
 }
 const dimensions=(await getState())[0];
 for(const [offset,side,index] of [
  [3,"left",0],[2,"opposite",2],[1,"right",3]
 ]){
  current=fixture("ming_gang",offset);
  await page.locator("#classic-new").click();
  await page.waitForFunction(expected=>
   [...document.querySelectorAll(".mahtrain-kong")]
    .every(g=>g.dataset.claimPosition===expected),side);
  const rows=await getState();
  for(const [owner,row] of rows.entries()){
   assert.equal(row.kind,"ming_gang");
   assert.equal(row.position,side);
   assert.equal(row.orientations.length,4);
   assert.equal(row.orientations[index],"sideways",
    "seat "+owner+" should orient actual claimed fourth from "+side);
   assert.equal(row.orientations.filter(x=>x==="sideways").length,1);
   assert.equal(row.tileFaces.filter(x=>x===TILES[owner]).length,4);
   assert.ok(row.groupWidth>0);
   assert.equal(row.tableWidth,dimensions.tableWidth);
   assert.equal(row.tableHeight,dimensions.tableHeight);
   if(owner>0)assert.notEqual(row.rotation,"none",
    "side seat should retain own full-row rotated reading direction");
  }
  await page.screenshot({path:"/tmp/m384-ming-"+side+".png"});
 }
 for(const kind of ["bu_gang","an_gang"]){
  current=fixture(kind,3);
  await page.locator("#classic-new").click();
  await page.waitForFunction(expected=>
   [...document.querySelectorAll(".mahtrain-kong")]
    .every(g=>g.dataset.kongType===expected),kind);
  const rows=await getState();
  for(const [owner,row] of rows.entries()){
   if(kind==="bu_gang"){
    assert.deepEqual(row.orientations,["upright","upright","upright"]);
    assert.equal(row.stackCount,1);
    assert.equal(row.tileFaces.length,4);
    assert.deepEqual(row.tileFaces,[TILES[owner],TILES[owner],TILES[owner],TILES[owner]]);
   }else{
    assert.equal(row.stackCount,0);
    assert.deepEqual(row.orientations,Array(4).fill("upright"));
    assert.deepEqual(row.tileFaces,["_","_","_",TILES[owner]]);
   }
   assert.equal(row.tableWidth,dimensions.tableWidth);
   assert.equal(row.tableHeight,dimensions.tableHeight);
  }
  await page.screenshot({path:"/tmp/m384-"+kind+".png"});
 }
 assert.deepEqual(errors,[],"browser must not emit JS errors");
 console.log("M3.84 ALL FOUR SEATS × LEFT/RIGHT/OPPOSITE + KONG STACK/BACK: PASS");
}finally{await browser.close()}
