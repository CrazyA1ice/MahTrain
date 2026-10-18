"use strict";
/* M3.61 real Chrome layout regression, not a mock-DOM structural test.
   Uses the actual server HTML/CSS and a deterministic STRESS-ONLY 56-slot
   fixture. These are NOT simulated valid 224 concurrent discarded tiles.
   The stress fixture checks four trays independently at their physical
   maximum, with no private opponent state or server-game mutation. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {execFileSync}=require("node:child_process");
const {chromium}=require("playwright-core");

function browserBinary(){
  for(const name of ["google-chrome","google-chrome-stable",
                      "chromium","chromium-browser"]){
    try {
      return execFileSync("which",[name],{encoding:"utf8"}).trim();
    } catch {}
  }
  return undefined; // caller may have installed Playwright's Chromium.
}

const specs=[
  {width:320,height:800},
  {width:375,height:812}, {width:390,height:844},
  {width:700,height:880}, {width:701,height:900},
  {width:1024,height:900}, {width:1440,height:900},
];
const output=path.join(process.cwd(),"test-artifacts","match-layout");
fs.mkdirSync(output,{recursive:true});

function check(report,w,label){
  assert.ok(report.board.width>0, w+" "+label+": zero board width");
  assert.ok(report.board.left>=-1, w+" "+label+": board starts offscreen");
  assert.ok(report.board.right<=w+1,
    w+" "+label+": board exceeds viewport (right="+report.board.right+")");
  assert.ok(report.riverHandGap>=0,
    w+" "+label+": human hand intersects bottom river, gap="+report.riverHandGap);
  for(const river of report.rivers){
    assert.equal(river.scrollY,"hidden",w+" river "+river.seat+" scrolls");
    assert.equal(river.scrollX,"hidden",w+" river "+river.seat+" scrolls horizontally");
    assert.ok(river.clientWidth>=river.scrollWidth-1.5,
      w+" river "+river.seat+" hides physical columns ("+
      river.clientWidth+" < "+river.scrollWidth+")");
    assert.ok(river.clientHeight>=river.scrollHeight-1.5,
      w+" river "+river.seat+" hides physical rows ("+
      river.clientHeight+" < "+river.scrollHeight+")");
    assert.ok(river.outside.length===0,
      w+" river "+river.seat+" clipped "+river.outside.join(","));
    assert.ok(river.cellOverlap.length===0,
      w+" river "+river.seat+" overlapping grid slots "+river.cellOverlap.join(","));
    assert.equal(river.slotCount,56);
    assert.equal(river.occupiedPositions,56);
  }
  if(w>=701){
    assert.ok(report.hand.clientWidth>=report.hand.scrollWidth-2,
      w+" desktop must show all 14 hand tiles without own scroll");
  }else{
    assert.equal(report.hand.overflowX,"auto",
      w+" mobile may scroll only the own hand horizontally");
  }
}

async function main(){
  const browser=await chromium.launch({
    headless:true,executablePath:browserBinary(),
    args:["--no-sandbox","--disable-dev-shm-usage"],
  });
  try{
    const page=await browser.newPage({viewport:specs[0],deviceScaleFactor:1});
    await page.goto("http://127.0.0.1:8765/",{waitUntil:"load",timeout:30000});
    await page.locator("#home-open-match").click();
    await page.locator("#match-new").click();
    await page.waitForFunction(()=>{
      const stage=document.getElementById("match-stage");
      return stage && !stage.hidden &&
        !!document.querySelector("#match-river-0 .match-river-tiles");
    },{timeout:30000});
    // The DOM fixture uses REAL game board boxes and REAL computed CSS,
    // never reads or creates a hidden opponent hand.
    await page.evaluate(()=>{
      for(let seat=0;seat<4;seat++){
        const tray=document.querySelector(
          "#match-river-"+seat+" .match-river-tiles"
        );
        tray.replaceChildren();
        for(let n=0;n<56;n++){
          const r=Math.floor(n/14),c=n%14;
          const pos=seat===0?[r+1,c+1]:
            seat===2?[4-r,14-c]:
            seat===3?[c+1,4-r]:[14-c,r+1];
          const cell=document.createElement("div");
          cell.className="match-river-cell";
          cell.dataset.riverIndex=String(n);
          cell.dataset.riverRow=String(pos[0]);
          cell.dataset.riverColumn=String(pos[1]);
          cell.style.gridRow=String(pos[0]);
          cell.style.gridColumn=String(pos[1]);
          const tile=document.createElement("div");
          tile.className="tile";
          tile.textContent=String(n+1);
          cell.append(tile);
          tray.append(cell);
        }
      }
      const hand=document.getElementById("match-hand");
      hand.replaceChildren();
      for(let i=0;i<14;i++){
        const tile=document.createElement("div");
        tile.className="tile"+(i===13?" match-new-draw":"");
        tile.textContent=String(i+1);
        hand.append(tile);
      }
    });
    for(const spec of specs){
      await page.setViewportSize(spec);
      await page.evaluate(()=>new Promise(requestAnimationFrame));
      const report=await page.evaluate(()=>{
        function box(e){
          const r=e.getBoundingClientRect();
          return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,
                  width:r.width,height:r.height};
        }
        const boardElement=document.getElementById("match-board");
        const board=box(boardElement);
        const computedBoard=getComputedStyle(boardElement);
        const viewportDebug={
          innerWidth:innerWidth,bodyMinWidth:getComputedStyle(document.body).minWidth,
          matchNarrow:matchMedia("(min-width:320px) and (max-width:359px)").matches,
          boardColumns:computedBoard.gridTemplateColumns,
          riverHCell:computedBoard.getPropertyValue("--river-h-cell").trim(),
          center:box(document.querySelector(".match-board-center")),
        };
        const handEl=document.getElementById("match-hand");
        const handBounds=box(handEl);
        const bottomRiver=box(document.getElementById("match-river-0"));
        const rivers=[];
        for(let seat=0;seat<4;seat++){
          const el=document.querySelector(
            "#match-river-"+seat+" .match-river-tiles"
          );
          const bounds=box(el);
          const css=getComputedStyle(el);
          const cells=Array.from(el.querySelectorAll(".match-river-cell"));
          const rects=cells.map(box);
          const outside=[];
          const overlap=[];
          for(let i=0;i<rects.length;i++){
            const r=rects[i];
            if(r.left<bounds.left-.75||r.right>bounds.right+.75||
               r.top<bounds.top-.75||r.bottom>bounds.bottom+.75){
              outside.push(i);
            }
            for(let j=0;j<i;j++){
              const p=rects[j];
              if(Math.min(r.right,p.right)-Math.max(r.left,p.left)>1 &&
                 Math.min(r.bottom,p.bottom)-Math.max(r.top,p.top)>1){
                overlap.push(i+":"+j);
              }
            }
            const tile=cells[i].querySelector(".tile");
            if(tile){
              const t=box(tile);
              if(t.left<r.left-1||t.right>r.right+1||
                 t.top<r.top-1||t.bottom>r.bottom+1){
                outside.push("tile-"+i);
              }
            }
          }
          rivers.push({
            seat,scrollY:css.overflowY,scrollX:css.overflowX,
            clientWidth:el.clientWidth,scrollWidth:el.scrollWidth,
            clientHeight:el.clientHeight,scrollHeight:el.scrollHeight,
            slotCount:cells.length,
            occupiedPositions:new Set(cells.map(c=>
              c.style.gridRow+":"+c.style.gridColumn)).size,
            outside,cellOverlap:overlap,
          });
        }
        return {
          board,viewportDebug,rivers,riverHandGap:handBounds.top-bottomRiver.bottom,
          hand:{
            clientWidth:handEl.clientWidth,scrollWidth:handEl.scrollWidth,
            overflowX:getComputedStyle(handEl).overflowX,
          },
        };
      });
      const name="width-"+spec.width;
      fs.writeFileSync(path.join(output,name+".json"),
                       JSON.stringify(report,null,2)+"\n");
      await page.screenshot({
        path:path.join(output,name+".png"),fullPage:true,
        animations:"disabled",
      });
      console.log("M3.61 measured "+spec.width+"px",
        JSON.stringify({
          board:report.board,viewportDebug:report.viewportDebug,riverHandGap:report.riverHandGap,
          hand:report.hand,
          rivers:report.rivers.map(r=>({seat:r.seat,
            size:[r.clientWidth,r.clientHeight],
            scroll:[r.scrollWidth,r.scrollHeight],
            outside:r.outside.slice(0,15),
            overlap:r.cellOverlap.slice(0,5)
          })),
        }));
      check(report,spec.width,"full-river");
      console.log("M3.61 real Chrome "+spec.width+
        "px: no river clipping / no overlap / 14 hand tiles PASS");
    }
  }finally{
    await browser.close();
  }
}
main().catch(err=>{console.error(err);process.exitCode=1;});
