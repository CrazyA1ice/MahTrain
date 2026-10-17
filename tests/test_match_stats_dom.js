"use strict";
// M3.46: charts only use the existing SQLite verified-scorecard contract.
const assert=require("node:assert/strict");
const stats=require("../web/match_stats.js");
class Node{
  constructor(tag){
    this.tagName=tag;this.children=[];this.attributes={};this.textContent="";
    this.className="";this.style={};
  }
  append(...xs){this.children.push(...xs)}
  replaceChildren(...xs){this.children=[...xs]}
  setAttribute(name,val){this.attributes[name]=String(val)}
}
const ids=["match-stats-metrics","match-stats-cumulative","match-stats-outcomes"];
const nodes=Object.fromEntries(ids.map(id=>[id,new Node("div")]));
const doc={
  getElementById:id=>nodes[id],
  createElement:tag=>new Node(tag),
  createElementNS:(ns,tag)=>{
    assert.equal(ns,"http://www.w3.org/2000/svg");
    return new Node(tag);
  },
};
const board={
  valid_games:3,excluded_games:2,
  seats:[{seat:0,hu_total:-7,draw_total:11,settled_total:4,
    positive_games:1,negative_games:1,zero_games:1}],
  // Recent trend includes cumulative total from BEFORE the window.
  trend:[
    {created_at:"2026-10-12T18:00:00Z",score:-9,cumulative:-13},
    {created_at:"2026-10-14T12:00:00Z",score:0,cumulative:-13},
    {created_at:"2026-10-17T12:00:00Z",score:17,cumulative:4},
  ],
};
const s=stats.summary(board);
assert.equal(s.games,3);assert.equal(s.settled,4);
assert.equal(s.positiveRate,100/3);
assert.equal(s.avg,4/3);
stats.render(board,doc);
assert.equal(nodes["match-stats-metrics"].children.length,4);
assert.equal(nodes["match-stats-metrics"].children[1].children[1].textContent,"+4");
assert.equal(nodes["match-stats-metrics"].children[3].children[1].textContent,"33.3%");
const plot=nodes["match-stats-cumulative"].children[0];
assert.equal(plot.tagName,"svg");
assert.equal(plot.attributes.role,"img");
assert.ok(plot.attributes["aria-label"].includes("-13到+4"));
const poly=plot.children.find(x=>x.tagName==="polyline");
assert.equal(poly.attributes.points.split(" ").length,3);
const dots=plot.children.filter(x=>x.tagName==="circle");
assert.equal(dots.length,3);
assert.ok(dots[0].children[0].textContent.includes("单局净额 -9"));
assert.ok(dots[2].children[0].textContent.includes("截至该局累计 +4"));
const rows=nodes["match-stats-outcomes"].children;
assert.equal(rows.length,4,"3 positive/negative/zero bars + explanatory note");
assert.equal(rows[0].children[2].textContent,"1 局 · 33.3%");
assert.equal(rows[1].children[2].textContent,"1 局 · 33.3%");
assert.equal(rows[2].children[2].textContent,"1 局 · 33.3%");
assert.equal(rows[0].children[1].children[0].style.width,"33.3%");
assert.ok(rows[3].textContent.includes("胡牌部分 -7"));
assert.ok(rows[3].textContent.includes("流局部分 +11"));
assert.ok(!JSON.stringify(nodes).includes("private-hand"));
stats.render({valid_games:0,excluded_games:1,seats:[],trend:[]},doc);
assert.equal(nodes["match-stats-cumulative"].children[0].tagName,"p");
assert.ok(nodes["match-stats-cumulative"].children[0].textContent.includes("暂无"));
assert.equal(nodes["match-stats-outcomes"].children[0].tagName,"p");
assert.equal(nodes["match-stats-metrics"].children[3].children[1].textContent,"0.0%");
const same=stats.makeLinePoints([{cumulative:100}]);
assert.equal(same.points.length,1);
assert.ok(Number.isFinite(same.zeroY));
console.log("M3.46 audited official trend SVG and outcome distribution: PASS");
