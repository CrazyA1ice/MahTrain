/* M3.88: actual Chromium constraints for native central black score and
 * popup, without changing table dimensions or pushing rivers/revealing hands.
 */
import assert from "node:assert/strict";
import {execFileSync} from "node:child_process";
import {chromium} from "playwright-core";
function chrome(){
 for(const name of ["google-chrome","chromium","chromium-browser"]){
  try{return execFileSync("which",[name],{encoding:"utf8"}).trim()}catch{}
 }
}
const hand=["m1","m2","m3","m4","m5","m6","m7","p1","p2","p3","s1","s2","s3","s4"];
const state={seat:0,phase:"finished",turn:null,dealer:3,
 series_round:19,dealer_origin:"因上一局一炮双响点炮者坐庄",
 wall_count:0,hand,hand_counts:[14,13,13,13],drawn_tile:null,
 missing_suits:["s","m","p","s"],won:[true,true,true,false],
 melds:[[],[],[],[]],own_melds:[],discards:[],
 can_self_draw_win:false,kong_options:[],claim_options:[],rob_options:[],
 public_steps:[],needs_continue:false,
 win_ledger:{balances:[0,0,0,0],wins:[],entries:[]},
 kong_ledger:{base:100,balances:[0,0,0,0],events:[],entries:[]},
 settled_balances:[0,0,0,0],
 next_dealer:{dealer:2,reason:"lost_to_three",
 label:"输三家，包括此前每家自摸或点炮胡所结算的支付记录，下局应由该输三家的座位接任"},
};
const browser=await chromium.launch({headless:true,
 executablePath:chrome(),args:["--no-sandbox","--disable-dev-shm-usage"]});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errs=[];page.on("pageerror",e=>errs.push(e.message));
await page.route("**/api/action",async r=>r.fulfill({
 status:200,contentType:"application/json",
 body:JSON.stringify({match_token:"m388-visual-only",match:state}),
}));
function check(){
 return page.evaluate(()=>{
  const board=document.getElementById("classic-board-host").getBoundingClientRect();
  const score=document.getElementById("classic-score");
  const scoreRect=score.getBoundingClientRect();
  const center=document.getElementById("classic-center-actions");
  const actionTitle=document.getElementById("classic-actions-title");
  const titleRect=actionTitle.getBoundingClientRect();
  const actionRect=center.getBoundingClientRect();
  return {
   board:{w:board.width,h:board.height,x:board.x,y:board.y},
   score:{width:scoreRect.width,height:scoreRect.height,
          overflow:getComputedStyle(score).overflow},
   action:{width:actionRect.width,height:actionRect.height,
    overflowX:getComputedStyle(center).overflowX,
    titleLeft:titleRect.left,titleRight:titleRect.right,
    innerLeft:actionRect.left,innerRight:actionRect.right,
    titleScrollWidth:actionTitle.scrollWidth,
    titleClientWidth:actionTitle.clientWidth},
  };
 });
}
try{
 await page.goto("http://127.0.0.1:8765/classic/game.html",
  {waitUntil:"load",timeout:30000});
 await page.waitForFunction(()=>document.getElementById(
  "classic-actions-title")?.textContent.includes("输三家"));
 const initial=await check();
 assert.equal(initial.score.overflow,"hidden");
 assert.equal(initial.action.overflowX,"hidden");
 assert.ok(initial.action.width<initial.board.w);
 assert.ok(initial.action.height<initial.board.h);
 assert.ok(initial.action.titleLeft>=initial.action.innerLeft-1);
 assert.ok(initial.action.titleRight<=initial.action.innerRight+1);
 assert.ok(initial.action.titleScrollWidth<=initial.action.titleClientWidth+1,
  "long terminal explanation must wrap inside black panel width");
 assert.ok(!errs.length,errs.join(" ; "));
 await page.screenshot({path:"/tmp/m388-black-center-contained.png"});
 console.log("M3.88 BLACK CENTRAL SCORE/TITLE TEXT CONTAINED: PASS",initial);
}finally{await browser.close()}
