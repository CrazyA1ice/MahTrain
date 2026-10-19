/* Browser fixture test. Real Python new/exchange/missing is covered separately;
 * this verifies terminal snapshots render 4-seat finances and spoken hu safely. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {chromium} from 'playwright-core';
const findChrome=()=>{
 for(const name of ['google-chrome','chromium','chromium-browser']){
  try{return execFileSync('which',[name],{encoding:'utf8'}).trim()}catch{}
 }
};
const browser=await chromium.launch({headless:true,executablePath:findChrome(),
 args:['--no-sandbox','--disable-dev-shm-usage']});
const tileHand=['m1','m2','m3','m4','p1','p2','p3','s1','s2','s3','s4','s5','s7','s8'];
const base={
 seat:0,phase:'await_discard',turn:0,dealer:0,wall_count:42,
 hand:tileHand,drawn_tile:'s8',hand_counts:[14,13,13,13],
 missing_suits:['p','m','s','p'],won:[false,false,false,false],
 own_melds:[],melds:[[],[],[],[]],discards:[],can_self_draw_win:false,
 kong_options:[],claim_options:[],rob_options:[],needs_continue:false,
 win_ledger:{balances:[0,0,0,0],wins:[],entries:[]},
 kong_ledger:{base:100,balances:[0,0,0,0],events:[],entries:[]},
 settled_balances:[0,0,0,0],public_steps:[],
};
const terminated={
 ...base,phase:'wall_exhausted',turn:null,wall_count:0,
 won:[true,false,true,false],discards:[{seat:3,tile:'m3',won_by:[0,2]}],
 win_ledger:{
  balances:[200,0,200,-400],
  wins:[
   {winner:0,source:3,kind:'ron',tile:'m3',main_pattern:'清一色',
    effective_fan:2,raw_fan:2,amount_per_payer:200,total_received:200,
    payers:[3],combinations:{清一色:2},bonuses:{}},
   {winner:2,source:3,kind:'ron',tile:'m3',main_pattern:'对对胡',
    effective_fan:2,raw_fan:2,amount_per_payer:200,total_received:200,
    payers:[3],combinations:{对对胡:2},bonuses:{}},
  ],
  entries:[{winner:0,payer:3,amount:200,kind:'ron',effective_fan:2},
   {winner:2,payer:3,amount:200,kind:'ron',effective_fan:2}],
 },
 kong_ledger:{
  base:100,balances:[-200,600,-200,-200],
  events:[{id:1,type:'an_gang',seat:1,source:null,payers:[0,2,3],
   amount_per_payer:200,status:'posted'}],
  entries:[{kong_id:1,kind:'charge',payer:0,recipient:1,amount:200},
   {kong_id:1,kind:'charge',payer:2,recipient:1,amount:200},
   {kong_id:1,kind:'charge',payer:3,recipient:1,amount:200}],
 },
 exhaustive_settlement:{posted:true,balances:[0,0,0,0],entries:[]},
 settled_balances:[0,600,0,-600],
 public_steps:[{events:[{type:'multi_ron',seats:[0,2],source:3,tile:'m3'}]}],
};
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>{
 window.__spoken=[];
 const synthesis={
  speak(utterance){window.__spoken.push(utterance.text);utterance.onend?.()},
  cancel(){},
 };
 Object.defineProperty(window,'speechSynthesis',{value:synthesis,configurable:true});
 window.SpeechSynthesisUtterance=class{
  constructor(text){this.text=text;}
 };
});
let requests=0;
await page.route('**/api/action',async route=>{
 const input=route.request().postDataJSON();
 const current=input.action==='match_new'?base:terminated;
 requests++;
 await route.fulfill({status:200,contentType:'application/json',
  body:JSON.stringify({match_token:'fixture-session-only',match:current})});
});
try{
 const response=await page.goto('http://127.0.0.1:8765/classic/game.html',
  {waitUntil:'load',timeout:30000});
 assert.equal(response.status(),200);
 await page.waitForFunction(()=>document.querySelector('.shoupai.main img[data-hand-index]'));
 const voice=page.locator('#classic-voice-toggle');
 console.log('VOICE INIT',await page.evaluate(()=>({
  label:document.getElementById('classic-voice-toggle').textContent,
  pressed:document.getElementById('classic-voice-toggle').getAttribute('aria-pressed'),
  engine:!!window.MahTrainMatchVoice,
  utteranceType:typeof window.SpeechSynthesisUtterance,
  synthType:typeof window.speechSynthesis,
  canSpeak:typeof window.speechSynthesis?.speak,
 })));
 assert.equal(await voice.getAttribute('aria-pressed'),'true');
 const first=page.locator('.shoupai.main img[data-hand-index="0"]');
 await first.click();await first.click();
 await page.waitForFunction(()=>!document.querySelector('#classic-result-report').hidden,
  null,{timeout:15000});
 const activity=await page.evaluate(()=>{
  const cue=document.querySelector('#classic-live-action');
  const river=document.querySelector('#classic-board-host').getBoundingClientRect();
  const geom=cue.getBoundingClientRect();
  return {
   title:cue.querySelector('#classic-live-action-title')?.textContent,
   kind:cue.dataset.kind,visible:!cue.hidden,above:geom.bottom<=river.top+1,
   winners:[0,2].every(i=>document.querySelector(
    '#classic-player-'+i).classList.contains('classic-action-win')),
   losers:[1,3].every(i=>!document.querySelector(
    '#classic-player-'+i).classList.contains('classic-action-win')),
  };
 });
 assert.equal(activity.kind,'win','show a real confirmed HU action');
 assert.match(activity.title,/一炮多响/);
 assert.equal(activity.above,true,'activity strip does not cover rivers');
 assert.equal(activity.winners,true,'both winners highlighted on their real seats');
 assert.equal(activity.losers,true,'losers do not receive false HU badges');
 const audit=await page.evaluate(()=>{
  const report=document.querySelector('#classic-result-report');
  const ticker=document.querySelector('#classic-win-announcement');
  const table=report.querySelector('.classic-ledger-table');
  const rowTexts=[...table.querySelectorAll('tbody tr')].map(x=>x.textContent);
  const board=document.querySelector('#classic-board-host').getBoundingClientRect();
  const note=ticker.getBoundingClientRect();
  const sheet=report.getBoundingClientRect();
  return {
   report:report.innerText,rows:rowTexts,ticker:ticker.innerText,
   spoken:window.__spoken,voice:document.querySelector('#classic-voice-toggle').textContent,
   independent:note.bottom<=board.top+1 && sheet.top>=board.bottom-1,
  };
 });
 assert.match(audit.ticker,/自己.*清一色/);
 assert.match(audit.ticker,/2号AI.*对对胡/);
 assert.equal(audit.rows.length,4,'4 real settlements');
 assert.ok(audit.rows[1].includes('+600'));
 assert.ok(audit.rows[3].includes('-600'));
 assert.match(audit.report,/杠钱明细/);
 assert.match(audit.report,/明杠|暗杠/);
 assert.match(audit.report,/付款方/);
 assert.match(audit.report,/清一色/);
 assert.match(audit.report,/对对胡/);
 assert.ok(audit.spoken.some(x=>x==='胡'),'existing voice speaks only HU');
 assert.equal(audit.independent,true,'neither banner nor score sheet covers four rivers');
 // A genuinely finished live round must automatically bring the final
 // accounts into view, without an extra manual click.
 await page.waitForFunction(()=>window.scrollY>50,null,{timeout:5500});
 assert.equal(errors.length,0,'fatal browser errors: '+errors.join(';'));
 assert.ok(requests>=2);
 const root=path.resolve('frontend_2d/test-artifacts');
 fs.mkdirSync(root,{recursive:true});
 await page.screenshot({path:path.join(root,'classic-hu-and-settlement.png'),
  fullPage:true});
 console.log('CLASSIC Majiang UI hu/score/kong/voice fixture PASS',JSON.stringify({
  rows:audit.rows,spoken:audit.spoken,geometry:audit.independent,
 }));
}finally{
 await browser.close();
}
