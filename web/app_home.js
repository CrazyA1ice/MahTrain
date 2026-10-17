"use strict";
/* M3.46: navigation only. All original feature modules remain initialized
   and retain their state while hidden. No simulated scores or new API. */
(function(root){
  const valid=new Set(["match","archives","training","quiz","history","research","demo"]);
  const labels={match:"四人人机对战",archives:"历史战绩与统计",training:"连续摸切训练",
    quiz:"单题训练",history:"训练历史与错题本",research:"AI策略研究",demo:"四人规则演示"};
  const pathname=()=>String(root.location?.hash||"").replace(/^#\/?/,"");
  function show(name){
    const module=valid.has(name)?name:"";
    const landing=root.document.getElementById("module-home");
    const nav=root.document.getElementById("module-navbar");
    landing.hidden=!!module;
    nav.hidden=!module;
    for(const section of root.document.querySelectorAll("[data-module-section]")){
      const active=section.getAttribute("data-module-section")===module;
      // Do not reset per-module gameplay "hidden" state on every route
      // transition: use CSS for visibility, never rewrite section.hidden.
      section.setAttribute("data-module-active",String(active));
    }
    root.document.getElementById("module-current-name").textContent=labels[module]||"";
    root.document.body.setAttribute("data-current-module",module||"home");
    if(module==="archives")root.MahTrainMatchArchives?.refresh();
    return module;
  }
  function go(name){
    const module=valid.has(name)?name:"";
    root.location.hash=module?"#/"+module:"#/";
    show(module);
    root.scrollTo?.({top:0,behavior:"instant"});
  }
  function init(){
    root.document.querySelectorAll("[data-open-module]").forEach(button=>
      button.addEventListener("click",()=>go(button.getAttribute("data-open-module"))));
    root.document.getElementById("module-back-home").addEventListener("click",()=>go(""));
    root.addEventListener?.("hashchange",()=>show(pathname()));
    show(pathname());
  }
  root.MahTrainHome={init,show,go};
  if(root.document.readyState==="loading")
    root.document.addEventListener("DOMContentLoaded",init);
  else init();
})(window);
