import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {execFileSync} from "node:child_process";
import {chromium} from "playwright-core";
function chrome(){
 for(const name of ["google-chrome","google-chrome-stable","chromium","chromium-browser"]){
  try {return execFileSync("which",[name],{encoding:"utf8"}).trim()}catch{}
 }
 return undefined;
}
const browser=await chromium.launch({headless:true,executablePath:chrome(),
 args:["--no-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errors=[];
page.on("pageerror",err=>errors.push(err.message));
try {
 const res=await page.goto("http://127.0.0.1:8765/classic/game.html",
  {waitUntil:"load",timeout:30000});
 assert.equal(res.status(),200);
 await page.waitForFunction(()=>{
  const stage=document.querySelector(".shoupai.main .bingpai");
  const prompt=document.querySelector("#classic-actions-title");
  return !!stage && stage.querySelectorAll("img.pai[data-hand-index]").length>=13 &&
   prompt?.textContent?.includes("换三张");
 },{timeout:45000});
 const before=await page.evaluate(()=>{
  const view=document.querySelector("#classic-game-board").getBoundingClientRect();
  const imgs=[...document.querySelectorAll(".shoupai.main .bingpai img.pai")];
  const ribs=[...document.querySelectorAll(".he")];
  return {
   title:document.title,tableWidth:view.width,tableHeight:view.height,
   playerCount:document.querySelectorAll("#classic-game-board > .player").length,
   hand:imgs.map(i=>({tile:i.dataset.tile,index:i.dataset.handIndex,
       imageLoaded:i.complete&&i.naturalWidth>0,src:i.getAttribute("src")})),
   riverCount:ribs.length,
   riverGrid:getComputedStyle(document.querySelector(".he.main .dapai")).display,
   center:document.querySelector("#classic-center-actions").getBoundingClientRect().toJSON(),
   personal:document.querySelector(".shoupai.main").getBoundingClientRect().toJSON(),
  };
 });
 assert.equal(before.playerCount,4,"must display original 4 player seats");
 assert.equal(before.riverCount,4,"must use 4 genuine Majiang He objects");
 assert.equal(before.riverGrid,"grid","physical rivers reserve 14x4 space");
 assert.ok(before.hand.every(x=>x.imageLoaded),"all actual upstream GIF tiles must load");
 assert.ok(before.hand.length>=13&&before.hand.length<=14,"human hand count");
 assert.ok(before.tableWidth>=750&&before.tableHeight>=640,
  "native 800x680 Majiang source board visible at desktop 100% zoom");
 const out=path.resolve("frontend_2d/test-artifacts");
 fs.mkdirSync(out,{recursive:true});
 await page.screenshot({path:path.join(out,"classic-opening.png"),fullPage:true});
 const picked=[];
 for(const suit of ["m","p","s"]){
  const cards=before.hand.filter(x=>x.tile[0]===suit);
  if(cards.length>=3){picked.push(...cards.slice(0,3));break}
 }
 assert.equal(picked.length,3);
 for(const p of picked){
  await page.locator('.shoupai.main img.pai[data-hand-index="'+p.index+'"]').click();
 }
 assert.equal(await page.locator(".is-picked").count(),3);
 await page.getByRole("button",{name:/确认换三张/}).click();
 await page.waitForFunction(()=>
  document.querySelector("#classic-actions-title")?.textContent?.includes("定缺"),
  {timeout:35000});
 assert.equal(await page.locator("#classic-actions-buttons button").count(),3);
 await page.getByRole("button",{name:"缺万"}).click();
 await page.waitForFunction(()=>
  !document.querySelector("#classic-actions-title")?.textContent?.includes("定缺"),
  {timeout:35000});
 await page.screenshot({path:path.join(out,"classic-after-missing.png"),fullPage:true});
 assert.ok(!errors.length,"browser runtime errors: "+errors.join(" | "));
 console.log("REAL MAJIANG UI 2D + PYTHON exchange + missing: PASS",before);
}finally {await browser.close()}
