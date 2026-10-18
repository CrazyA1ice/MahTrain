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
  // The application explicitly supports 320px as its narrowest viewport.
  assert.ok(w>=320,"supported layout audit starts at 320px");
  assert.equal(report.viewportDebug.bodyMinWidth,"320px");
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
    assert.ok(report.board.height<=report.viewportDebug.innerHeight+1,
      w+" desktop board must fit one 100%-zoom viewport");
    assert.ok(report.board.top>=-1&&
      report.board.bottom<=report.viewportDebug.innerHeight+1,
      w+" board must be completely visible when scrolled into view");
    assert.equal(report.safeLayout?.allVisible,true,
      w+" all four river/meld/missing zones must fit their own seats");
    assert.equal(report.safeLayout?.promptInsideCenter,true,
      w+" exchange prompt must stay inside the central safe bay");
    assert.equal(report.safeLayout?.promptOverlaps.length,0,
      w+" exchange prompt overlays a hand, river, exposed meld or missing badge");
    assert.ok(report.safeLayout?.safeBox.width<=205,
      w+" center counter must be compact; no giant empty square");
    assert.ok(report.safeLayout?.safeBox.height<=320,
      w+" center counter or controls must stay inside the reserved central band");
    assert.equal(report.safeLayout?.tableSkin,"riichi",
      w+" match board should load the standalone table skin");
    assert.equal(report.safeLayout?.handBackground,"rgba(0, 0, 0, 0)",
      w+" the own hand should sit directly on the felt, not a colored bar");
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
          tile.dataset.fixtureIndex=String(n);
          // The real MahTrain tile is an atlas face, not oversized text.
          // Text "55" can overflow an otherwise correctly clipped 10px slot.
          const face=document.createElement("span");
          face.className="tile-atlas-face";
          tile.append(face);
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
      if(spec.width>=701){
        // Public-only visual stress: four possible open melds, a missing
        // suit badge and 14 physical hand tiles simultaneously in every seat.
        // This is a layout test, not a claim of a reachable 108-tile state.
        await page.evaluate(()=>{
          for(let seat=0;seat<4;seat++){
            const root=seat===0
              ?document.getElementById("match-self-melds")
              :document.querySelector("#match-seat-"+seat+" .match-seat-melds");
            root.replaceChildren();
            for(let meld=0;meld<4;meld++){
              const group=document.createElement("div");
              group.className="match-seat-meld";
              const name=document.createElement("small");
              name.textContent="碰/杠";
              group.append(name);
              const tiles=document.createElement("div");
              tiles.className="match-meld-tiles";
              for(let n=0;n<4;n++){
                const tile=document.createElement("div");
                tile.className="tile";
                const face=document.createElement("span");
                face.className="tile-atlas-face";
                tile.append(face);
                tiles.append(tile);
              }
              group.append(tiles);
              root.append(group);
            }
            let missing=seat===0
              ?document.getElementById("match-self-missing-flag")
              :document.querySelector("#match-seat-"+seat+" .match-missing-flag");
            if(!missing){
              missing=document.createElement("strong");
              missing.className="match-missing-flag";
              document.querySelector("#match-seat-"+seat+" .match-seat-identity")
                .append(missing);
            }
            missing.hidden=false;
            missing.textContent="缺条";
          }
        });
        // Explicitly center the entire table instead of leaving 7px out.
        await page.evaluate(()=>document.getElementById("match-board")
          .scrollIntoView({block:"center",inline:"nearest",behavior:"instant"}));
      }
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
          innerWidth:innerWidth,innerHeight:innerHeight,
          bodyMinWidth:getComputedStyle(document.body).minWidth,
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
        // M3.65: geometric visibility checks independent of real private
        // state. All synthetic melds are visibly PUBLIC tile placeholders.
        const overlaps=(a,b)=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&
          Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1;
        const inside=(small,large)=>small.left>=large.left-2&&
          small.right<=large.right+2&&small.top>=large.top-2&&
          small.bottom<=large.bottom+2;
        const prompt=document.querySelector("#match-controls:not([hidden])");
        const safeBox=box(document.getElementById("match-wall"));
        const handBox=box(handEl);
        const vulnerable=[
          handEl,...Array.from(document.querySelectorAll(
            ".match-river, #match-self-melds .match-seat-meld, "+
            ".match-seat:not(.match-seat--bottom) .match-seat-meld, "+
            ".match-board .match-missing-flag:not([hidden])"))
        ];
        let allVisible=true;
        for(let seat=0;seat<4;seat++){
          const holder=document.getElementById("match-seat-"+seat);
          const seatBox=box(holder);
          const flag=seat===0
            ?document.getElementById("match-self-missing-flag")
            :holder.querySelector(".match-missing-flag");
          if(!flag||flag.hidden||!inside(box(flag),seatBox))allVisible=false;
          const melds=seat===0
            ?document.getElementById("match-self-melds")
            :holder.querySelector(".match-seat-melds");
          if(!melds||melds.querySelectorAll(".match-seat-meld").length!==4||
             !inside(box(melds),seatBox))allVisible=false;
          for(const tile of melds?.querySelectorAll(".tile")||[]){
            if(!inside(box(tile),seatBox))allVisible=false;
          }
        }
        const promptBox=prompt?box(prompt):null;
        const safeLayout={
          allVisible,promptInsideCenter:!!promptBox&&inside(promptBox,safeBox),
          promptOverlaps:promptBox?vulnerable
            .filter(item=>overlaps(promptBox,box(item)))
            .map(item=>item.id||item.className):[],
          safeBox,promptBox,handBox,
          tableSkin:document.getElementById("match-board").classList
            .contains("match-board--riichi")?"riichi":"legacy",
          handBackground:getComputedStyle(handEl).backgroundColor,
        };
        return {
          board,viewportDebug,rivers,safeLayout,
          riverHandGap:handBounds.top-bottomRiver.bottom,
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
      // M3.62: Test progressive placement on the REAL Chrome grid, not
      // just an already-full 56-slot synthetic river. From 0 -> 1 -> 13 ->
      // 14 -> 15 -> 56 cards, its outer tray / opponent seat / hand bounds
      // must not shift by a pixel (including the first row wrap). At #6
      // an already-claimed physical discard leaves a stable empty slot.
      // The stress fixture is re-built, never sent to the server.
      if([320,390,701,1024].includes(spec.width)){
        let reference=null;
        for(const count of [0,1,13,14,15,28,56]){
          const step=await page.evaluate((count)=>{
            const slots=[];
            function bounds(node){
              const r=node.getBoundingClientRect();
              return [r.left,r.top,r.width,r.height].map(v=>
                Math.round(v*100)/100);
            }
            for(let seat=0;seat<4;seat++){
              const tray=document.querySelector(
                "#match-river-"+seat+" .match-river-tiles"
              );
              const river=document.getElementById("match-river-"+seat);
              tray.replaceChildren();
              for(let n=0;n<count;n++){
                const r=Math.floor(n/14),c=n%14;
                const pos=seat===0?[r+1,c+1]:
                  seat===2?[4-r,14-c]:
                  seat===3?[c+1,4-r]:[14-c,r+1];
                const cell=document.createElement("div");
                cell.className="match-river-cell";
                cell.style.gridRow=String(pos[0]);
                cell.style.gridColumn=String(pos[1]);
                cell.dataset.riverIndex=String(n);
                if(n===5){
                  cell.classList.add("is-claimed");
                  const placeholder=document.createElement("span");
                  placeholder.className="match-river-claimed";
                  placeholder.textContent="已取走";
                  cell.append(placeholder);
                }else{
                  const tile=document.createElement("div");
                  tile.className="tile";
                  tile.append(document.createElement("span"));
                  cell.append(tile);
                }
                tray.append(cell);
              }
              const occupied=new Set(Array.from(tray.children).map(el=>
                el.style.gridRow+":"+el.style.gridColumn));
              slots.push({
                seat,count:tray.children.length,
                unique:occupied.size,
                tray:bounds(tray),river:bounds(river),
                noScroll:getComputedStyle(tray).overflowY==="hidden",
                claimed:count<=5||(
                  tray.children[5].classList.contains("is-claimed") &&
                  !tray.children[5].querySelector(".tile")
                ),
              });
            }
            return {
              slots,board:bounds(document.getElementById("match-board")),
              hand:bounds(document.getElementById("match-hand")),
            };
          },count);
          assert.ok(step.slots.every(x=>x.count===count &&
            x.unique===count && x.noScroll && x.claimed),
            spec.width+"px "+count+" discards: fixed slot contract failed");
          const geometry={board:step.board,hand:step.hand,
            slots:step.slots.map(x=>({seat:x.seat,tray:x.tray,river:x.river}))};
          if(reference===null)reference=geometry;
          else {
            for(const key of ["board","hand"]){
              assert.deepEqual(geometry[key],reference[key],
                spec.width+"px "+count+": "+key+" shifted during discarding");
            }
            for(let seat=0;seat<4;seat++){
              assert.deepEqual(geometry.slots[seat],reference.slots[seat],
                spec.width+"px "+count+": river "+seat+" shifted");
            }
          }
          if([0,14,56].includes(count)){
            await page.screenshot({
              path:path.join(output,"width-"+spec.width+"-discards-"+count+".png"),
              fullPage:true,animations:"disabled",
            });
          }
        }
        console.log("M3.62 real Chrome "+spec.width+
          "px: progressive empty/1/13/14/15/28/56 fixed positions PASS");
      }
    }
  }finally{
    await browser.close();
  }
}
main().catch(err=>{console.error(err);process.exitCode=1;});
