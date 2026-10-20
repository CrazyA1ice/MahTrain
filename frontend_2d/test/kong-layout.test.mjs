import test from "node:test";
import assert from "node:assert/strict";
import {kongLayout,calledTilePosition} from "../src/kong-view.mjs";
import {convertView} from "../src/bridge.mjs";

function fixture(owner,source,kind="ming_gang"){
 const meld={type:kind,tile:"s7"};
 const melds=[[],[],[],[]];
 melds[owner]=[meld];
 return {seat:0,hand:[],hand_counts:[0,0,0,0],
   own_melds:owner===0?[meld]:[],melds,
   discards:[{seat:source,tile:"s7",claimed_by:owner}]};
}

test("all 4 seats interpret left/right/opposite relative to meld OWNER",()=>{
 for(let owner=0;owner<4;owner++){
  for(const [relative,position,index] of [[3,"left",0],[1,"right",3],[2,"opposite",2]]){
   const source=(owner+relative)%4;
   const v=convertView(fixture(owner,source));
   const meta=v.redactions[owner][0];
   assert.equal(meta.source,source);
   assert.equal(meta.kind,"ming_gang");
   const layout=kongLayout(meta,owner);
   assert.equal(calledTilePosition(owner,source),position);
   assert.equal(layout.position,position);
   assert.equal(layout.slots.length,4);
   assert.deepEqual(layout.slots.map(x=>x.orientation),
    Array.from({length:4},(_,i)=>i===index?"sideways":"upright"));
   assert.equal(layout.slots[index].role,"claimed");
   assert.equal(layout.slots.every(x=>x.tile==="s7"),true);
  }
 }
});

test("physical concealed kong has exactly three backs and one disclosed face",()=>{
 for(let owner=0;owner<4;owner++){
  const standard=kongLayout({kind:"an_gang",tile:"m9",revealed:true},owner);
  assert.deepEqual(standard.slots.map(x=>x.tile),[null,null,null,"m9"]);
  assert.equal(standard.slots.filter(x=>x.role==="back").length,3);
  assert.equal(standard.slots.filter(x=>x.role==="public-face").length,1);
  const legacy=kongLayout({kind:"an_gang",tile:null,revealed:false},owner);
  assert.equal(legacy.slots.every(x=>x.tile===null),true);
 }
});

test("self-drawn fourth kong tile lies horizontally ON three upright peng tiles",()=>{
 for(let owner=0;owner<4;owner++){
  const source=(owner+3)%4;
  const meta=convertView(fixture(owner,source,"bu_gang")).redactions[owner][0];
  assert.equal(meta.source,source,"retain original peng provenance");
  const layout=kongLayout(meta,owner);
  assert.equal(layout.position,"self");
  assert.equal(layout.slots.length,3);
  assert.deepEqual(layout.slots.map(x=>x.orientation),
   ["upright","upright","upright"]);
  assert.equal(layout.slots[1].overlay?.orientation,"sideways");
  assert.equal(layout.slots[1].overlay?.stacked,true);
  assert.equal(layout.slots[1].overlay?.role,"supplement");
  assert.equal(layout.slots[1].overlay?.tile,"s7");
 }
});

test("open-meld direction uses actual public claimed discard, never seat or latest river",()=>{
 const x=fixture(0,3);
 x.discards.unshift({seat:1,tile:"m1",claimed_by:2});
 x.discards.push({seat:2,tile:"s7"});
 const token=convertView(x).redactions[0][0];
 assert.equal(token.source,3);
 assert.equal(kongLayout(token,0).position,"left");
 assert.equal(convertView(fixture(1,3)).redactions[1][0].source,3);
});

test("historical source unknown does not fabricate a left/right claim",()=>{
 const x=fixture(0,3);
 x.discards=[];
 const token=convertView(x).redactions[0][0];
 assert.equal(token.source,null);
 assert.equal(kongLayout(token,0).position,"unknown");
 assert.equal(kongLayout(token,0).slots[2].role,"claimed");
});

test("unknown opponent concealed kong must not expose placeholder tile or private hand",()=>{
 const x=fixture(1,0,"an_gang");
 x.melds[1]=[{type:"an_gang",tile:null}];
 x.hand_counts[1]=9;
 x.discards=[];
 const v=convertView(x);
 assert.equal(v.redactions[1][0].hidden,true);
 assert.equal(v.redactions[1][0].tile,null);
 assert.equal(v.hands[1]._bingpai._,9);
 assert.equal(kongLayout(v.redactions[1][0],1).slots.every(x=>x.tile===null),true);
});

test("invalid concealed public tile, source or role cannot become open face",()=>{
 assert.throws(()=>kongLayout({kind:"ming_gang",tile:null,source:1},0),/untrusted/);
 assert.throws(()=>calledTilePosition(0,0),/invalid/);
 assert.throws(()=>calledTilePosition(4,2),/invalid/);
 assert.throws(()=>kongLayout({kind:"peng",tile:"m1"},0),/not a kong/);
});
