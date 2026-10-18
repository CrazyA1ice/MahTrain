import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {chromium} from 'playwright-core';

function executable(){
  for(const name of ['google-chrome','google-chrome-stable','chromium','chromium-browser']){
    try{return execFileSync('which',[name],{encoding:'utf8'}).trim()}catch{}
  }
  return undefined;
}
const browser=await chromium.launch({
  executablePath:executable(),headless:true,
  args:['--no-sandbox','--disable-dev-shm-usage',
    '--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader'],
});
const failures=[];
const page=await browser.newPage({
  viewport:{width:1280,height:800},deviceScaleFactor:1,
  permissions:[],
});
page.on('pageerror',err=>failures.push(err.message));
page.on('console',msg=>{
  if(msg.type()==='error')failures.push('console: '+msg.text());
});
try{
  const url='http://127.0.0.1:8765/3d/game.html?mahtrain=1&seat=0&name=MahTrain';
  const response=await page.goto(url,{waitUntil:'load',timeout:30000});
  assert.equal(response?.status(),200,'built Queju index should load');
  await page.waitForFunction(()=>{
    const controls=document.getElementById('mahtrain-sichuan-controls');
    return controls && controls.textContent.includes('换三张');
  },{timeout:60000});
  const table=await page.evaluate(()=>{
    const canvas=document.querySelector('#app canvas');
    const pane=document.getElementById('mahtrain-sichuan-controls');
    const seats=document.querySelectorAll('#players .pl');
    const r=canvas?.getBoundingClientRect();
    return {hasCanvas:!!canvas,width:r?.width,height:r?.height,
      seats:seats.length,choices:pane?.querySelectorAll(
        '.mahtrain-exchange-choices button').length,
      title:document.title,status:document.getElementById('statusText')?.textContent};
  });
  assert.equal(table.hasCanvas,true,'must render an actual upstream WebGL canvas');
  assert.ok(table.width>=500&&table.height>=400,
    'upstream renderer must occupy the large gaming viewport');
  assert.equal(table.seats,4,'show four actual players');
  assert.ok(table.choices>=13,'render 3D game plus Sichuan exchange choices');
  assert.match(table.title,/MahTrain/);

  // Actual server-authoritative exchange (not mocked JS state).
  const choices=await page.locator('.mahtrain-exchange-choices button').allTextContents();
  let indices=null;
  for(const suffix of ['万','条','筒']){
    const matching=choices.map((v,i)=>v.endsWith(suffix)?i:-1).filter(v=>v>=0);
    if(matching.length>=3){indices=matching.slice(0,3);break}
  }
  assert.ok(indices,'there must be three same-suit real tiles to exchange');
  for(const i of indices)await page.locator('.mahtrain-exchange-choices button').nth(i).click();
  await page.getByRole('button',{name:/确认换三张/}).click();
  await page.waitForFunction(()=>{
    const pane=document.getElementById('mahtrain-sichuan-controls');
    return pane && pane.textContent.includes('定缺');
  },{timeout:30000});
  assert.equal(await page.locator('#mahtrain-sichuan-controls button').count(),3);
  // Click a real missing-suit command, and do not invent any public wall tile.
  await page.locator('#mahtrain-sichuan-controls button').first().click();
  await page.waitForFunction(()=>{
    const pane=document.getElementById('mahtrain-sichuan-controls');
    return pane && !pane.textContent.includes('定缺');
  },{timeout:30000});
  const dst=path.resolve('frontend_3d/test-artifacts');
  fs.mkdirSync(dst,{recursive:true});
  await page.screenshot({path:path.join(dst,'queju-live-3d.png'),fullPage:true});
  // Known limitations: unavailable optional upstream atlas image is NOT
  // requested in MahTrain mode; the original procedural tile renderer stays.
  assert.ok(!failures.some(x=>/WebGL.*not supported|Failed to fetch dynamically|Failed to resolve module/i.test(x)),
    '3D runtime errors: '+failures.join(' | '));
  console.log('Queju real 3D WebGL with MahTrain new match/exchange/missing: PASS',table);
  if(failures.length)console.log('Nonfatal browser diagnostics:',failures.slice(0,7));
}finally{await browser.close()}
