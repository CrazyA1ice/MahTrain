"use strict";
// M3.46: module navigation does not mutate any training/match state.
const assert=require("node:assert/strict");
const nav=require("../web/navigation.js");
class Node{
  constructor(){
    this.hidden=false;this.children=[];this.textContent="";
    this.attributes={};this.handlers={};this.classes=new Set();
    this.classList={
      toggle:(name,on)=>on?this.classes.add(name):this.classes.delete(name),
      contains:name=>this.classes.has(name),
    };
  }
  setAttribute(name,value){this.attributes[name]=String(value)}
  addEventListener(type,fn){this.handlers[type]=fn}
}
const all=[
  "module-home","module-navigation","module-back-home","module-current-label",
  ...Object.keys(nav.GROUPS).flatMap(key=>
    ["home-open-"+key,"module-go-"+key]),
  ...Object.values(nav.GROUPS).flat(),
];
const nodes=Object.fromEntries([...all,"home-match-state","match-stage"].map(id=>[id,new Node()]));
nodes["game"].hidden=true; // existing training has not started yet
nodes["match-stage"].hidden=true;
const handlers={},refreshes={records:0,history:0};
const win={
  location:{hash:""},scrolls:0,
  MahTrainMatchArchives:{refresh(){refreshes.records++;}},
  MahTrainHistory:{refresh(){refreshes.history++;}},
  scrollTo(){this.scrolls++;},
  addEventListener(type,fn){handlers[type]=fn;},
};
const api=nav.init({getElementById:id=>nodes[id]},win);
assert.equal(api.active(),"home");
assert.equal(nodes["module-home"].hidden,false);
assert.equal(nodes["module-navigation"].hidden,true);
for(const key of Object.keys(nav.GROUPS)){
  const btn=nodes["home-open-"+key];
  btn.handlers.click();
  assert.equal(win.location.hash,"#"+key);
  assert.equal(nodes["module-home"].hidden,true);
  assert.equal(nodes["module-navigation"].hidden,false);
  assert.equal(nodes["module-go-"+key].attributes["aria-current"],"page");
  for(const [moduleName,ids] of Object.entries(nav.GROUPS)){
    ids.forEach(id=>{
      assert.equal(nodes[id].classList.contains("module-inactive"),
        moduleName!==key,"wrong panel "+id+" in "+key);
    });
  }
  // The game is hidden by game logic itself and must retain that state.
  assert.equal(nodes["game"].hidden,true);
}
// The module switch does not fetch or mutate live match game state.
assert.equal(refreshes.records,1,"first records visit pulls current SQLite data");
assert.equal(refreshes.history,1,"standalone training archive refreshes on entry");
nodes["module-go-match"].handlers.click();
nodes["match-stage"].hidden=false; // an active match stays mounted
nodes["module-back-home"].handlers.click();
assert.equal(nodes["home-match-state"].textContent,
  "已有对局界面，点击继续查看");
nodes["module-go-records"].handlers.click();
assert.equal(refreshes.records,2,"return to historical records fetches new games");
handlers.hashchange(); // the hash write also emits browser hashchange
assert.equal(refreshes.records,2,"hashchange must not double-load records");
nodes["module-go-records"].handlers.click();
assert.equal(refreshes.records,2,"same module does not fetch again");
nodes["module-go-history"].handlers.click();
assert.equal(refreshes.history,2,"training history refreshes on re-entry");
nodes["module-go-match"].handlers.click();
assert.equal(nodes["match-stage"].hidden,false,
  "active match stays initialized and mounted after changing views");
nodes["module-back-home"].handlers.click();
assert.equal(nodes["home-match-state"].textContent,
  "已有对局界面，点击继续查看");
nodes["module-go-solo"].handlers.click();
nodes["game"].hidden=false; // player starts a 14-step training game
nodes["module-go-match"].handlers.click();
nodes["module-go-solo"].handlers.click();
assert.equal(nodes["game"].hidden,false,
  "navigation must preserve the in-progress training/game state");
nodes["module-back-home"].handlers.click();
assert.equal(nodes["module-home"].hidden,false);
assert.equal(nodes["module-navigation"].hidden,true);
assert.equal(win.location.hash,"#home");
win.location.hash="#records";handlers.hashchange();
assert.equal(nodes["match-archives-panel"].classList.contains("module-inactive"),false);
win.location.hash="#unsafe";handlers.hashchange();
assert.equal(nodes["module-home"].hidden,false,"unknown modules cannot expose content");
assert.ok(win.scrolls>0);
console.log("M3.46 home routes and retained module/game state: PASS");
