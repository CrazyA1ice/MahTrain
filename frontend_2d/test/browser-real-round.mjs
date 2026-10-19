/* Verify ACTUAL Python-authored completed match via real read-only resume.
 * The JSON file is produced by full_round_http.py from two whole live
 * games, never a synthetic browser fixture. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {execFileSync} from "node:child_process";
import {chromium} from "playwright-core";
const evidence=JSON.parse(fs.readFileSync(
 "frontend_2d/test-artifacts/real-http-full-round.json","utf8"));
const terminal=evidence.terminal;
const seatRows=terminal.settled_balances;
function chrome(){
 for(const name of ["google-chrome","chromium","chromium-browser"]){
  try{return execFileSync("which",[name],{encoding:"utf8"}).trim()}catch{}
 }
 return undefined;
}
const browser=await chromium.launch({headless:true,executablePath:chrome(),
 args:["--no-sandbox","--disable-dev-shm-usage"]});
const context=await browser.newContext({viewport:{width:1440,height:900}});
await context.addInitScript((token)=>{
 sessionStorage.setItem("mahtrain.match.session.v1",token);
},evidence.token);
const page=await context.newPage();
const errors=[];
page.on("pageerror",err=>errors.push(err.message));
const stats={calls:0,states:[]};
page.on("request",r=>{
 if(r.url().includes("/api/action")){
  stats.calls++;
  const v=r.postDataJSON();
  stats.states.push(v.action);
  assert.equal(v.action,"match_resume",
   "terminal restoration MUST NOT mutate a real completed game");
 }
});
try{
 const response=await page.goto("http://127.0.0.1:8765/classic/game.html",
   {waitUntil:"load",timeout:30000});
 assert.equal(response?.status(),200);
 await page.waitForFunction(()=>{
  const report=document.querySelector("#classic-result-report");
  return report&&!report.hidden&&
   report.querySelectorAll(".classic-ledger-table tbody tr").length>=4;
 },null,{timeout:25000});
 const truth=await page.evaluate(()=>{
  const report=document.querySelector("#classic-result-report");
  const rows=[...report.querySelectorAll(".classic-ledger-table")[0]
     .querySelectorAll("tbody tr")].map(tr=>[...tr.children].map(td=>td.textContent.trim()));
  const win=document.querySelector("#classic-win-announcement");
  const cue=document.querySelector("#classic-live-action");
  const board=document.querySelector("#classic-board-host").getBoundingClientRect();
  const sheet=report.getBoundingClientRect();
  const human=document.querySelector(".shoupai.main .bingpai");
  return {
   rows,hasWin:!win.hidden,winText:win.textContent,
   reportText:report.textContent,
   cueHidden:cue.hidden,
   reportBelowBoard:sheet.top>=board.bottom-1,
   players:document.querySelectorAll("#classic-game-board > .player").length,
   handRendered:human.querySelectorAll("img.pai").length,
   scoreText:document.querySelector("#classic-status")?.textContent,
  };
 });
 assert.equal(truth.players,4);
 assert.equal(truth.rows.length,4);
 assert.equal(truth.reportBelowBoard,true,
  "real round financial report MUST NOT block any table tile or river");
 assert.equal(truth.cueHidden,true,"resume must not replay stale event animation");
 for(let i=0;i<4;i++){
  const expected=seatRows[i]>0?"+"+seatRows[i]:String(seatRows[i]);
  assert.equal(truth.rows[i][5],expected,
   "seat "+i+" final net does not match REAL posted Python ledger");
  const won=terminal.win_ledger.wins.filter(w=>w.winner===i);
  if(won.length){
   assert.ok(truth.rows[i][1].includes(won[0].main_pattern),
    "seat "+i+" server-posted win pattern absent from displayed table");
  }
 }
 assert.equal(truth.hasWin,terminal.win_ledger.wins.length>0);
 for(const posted of terminal.win_ledger.wins){
  assert.ok(truth.winText.includes(posted.main_pattern));
 }
 assert.equal(stats.calls,1);
 assert.deepEqual(stats.states,["match_resume"]);
 assert.ok(!errors.length,"new classic UI errors: "+errors.join("; "));
 const out=path.resolve("frontend_2d/test-artifacts");
 fs.mkdirSync(out,{recursive:true});
 await page.screenshot({path:path.join(out,"real-live-full-round-terminal.png"),
  fullPage:true});
 // Refresh is read-only. No duplicates, phantom wins or automatic scroll.
 await page.reload({waitUntil:"load"});
 await page.waitForFunction(()=>document.querySelector(
  "#classic-result-report")?.hidden===false,null,{timeout:25000});
 assert.equal(stats.calls,2);
 assert.ok(stats.states.every(x=>x==="match_resume"));
 assert.equal(await page.locator("#classic-live-action").isHidden(),true);
 console.log("REAL TERMINAL CLASSIC BROWSER: PASS",JSON.stringify({
  seed:evidence.summary.seed,phase:terminal.phase,
  summary:truth.rows,winCount:terminal.win_ledger.wins.length,
  kongCount:terminal.kong_ledger.events.length,
  passedChecks:["real posted balances","real fan patterns",
    "strict read-only resume","four player table","no duplicate cue",
    "out-of-table financial sheet"],
 }));
}finally{await browser.close()}
