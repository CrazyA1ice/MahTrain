"use strict";
/* M3.46: one focused module per page, no extra requests or resetting games.
   Existing DOM nodes/IDs and their initialized handlers remain mounted. */
(function(root,factory){
  const api=factory();
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
  if(root)root.MahTrainNavigation=api;
})(typeof window!=="undefined"?window:null,function(){
  const GROUPS=Object.freeze({
    solo:["solo-intro","game","history-panel"],
    quiz:["quiz-center"],
    match:["match-panel"],
    records:["match-archives-panel"],
    lab:["ai-replay-panel","ai-baseline-panel","four-player-demo"],
  });
  const LABELS=Object.freeze({
    solo:"连续摸切训练",quiz:"单题专项训练",match:"四人人机对战",
    records:"历史战绩与统计图",lab:"策略与规则实验室",
  });
  function init(doc,host){
    const d=doc||(typeof document!=="undefined"?document:null);
    const w=host||(typeof window!=="undefined"?window:null);
    if(!d||!w)return;
    const byId=id=>d.getElementById(id);
    const home=byId("module-home"),nav=byId("module-navigation");
    if(!home||!nav)return;
    const panels=Object.values(GROUPS).flat().map(id=>byId(id));
    if(panels.some(x=>!x))throw Error("missing MahTrain module panel");
    const recognized=s=>Object.prototype.hasOwnProperty.call(GROUPS,s)?s:"home";
    const hashModule=()=>recognized(String(w.location?.hash||"").slice(1));
    function select(name,updateHash=true){
      const selected=recognized(name);
      const isHome=selected==="home";
      home.hidden=!isHome;
      home.classList.toggle("module-inactive",!isHome);
      nav.hidden=isHome;
      // Do not touch panel.hidden. In particular 'game' is toggled by
      // existing training state: preserve it when switching modules.
      for(const [group,ids] of Object.entries(GROUPS)){
        for(const id of ids){
          byId(id).classList.toggle("module-inactive",group!==selected);
        }
      }
      byId("module-current-label").textContent=isHome?"":LABELS[selected];
      for(const key of Object.keys(GROUPS)){
        const btn=byId("module-go-"+key);
        btn.setAttribute("aria-current",selected===key?"page":"false");
      }
      if(updateHash&&w.location){
        const hash=isHome?"#home":"#"+selected;
        if(w.location.hash!==hash)w.location.hash=hash;
      }
      // Returning home and switching views never posts any game mutation.
      if(typeof w.scrollTo==="function")w.scrollTo(0,0);
      return selected;
    }
    for(const group of Object.keys(GROUPS)){
      byId("home-open-"+group).addEventListener("click",()=>select(group));
      byId("module-go-"+group).addEventListener("click",()=>select(group));
    }
    byId("module-back-home").addEventListener("click",()=>select("home"));
    w.addEventListener?.("hashchange",()=>select(hashModule(),false));
    select(hashModule(),false);
    return {select,active:()=>hashModule()};
  }
  return {init,GROUPS,LABELS};
});
