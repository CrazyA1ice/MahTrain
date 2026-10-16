"use strict";
/* M3.9: aggregate-only independent shape rule benchmark, no concealed tiles. */
(function(){
  const $=id=>document.getElementById(id);
  const names={baseline:"独立牌形基线",basic:"入门",advanced:"进阶",challenge:"挑战"};
  let taskToken=null,serial=0,result=null;
  function el(tag,cls,str){
    const node=document.createElement(tag);
    if(cls)node.className=cls;
    if(str!==undefined)node.textContent=String(str);
    return node;
  }
  async function action(kind,payload={}){
    const res=await fetch("/api/action",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-MahTrain":"1"},
      body:JSON.stringify({action:kind,...payload}),
    });
    const data=await res.json();
    if(!res.ok)throw new Error(data.error||"独立基线请求失败");
    return data;
  }
  function fraction(value){
    return typeof value==="number"?(value*100).toFixed(1)+"%":"无切牌样本";
  }
  function stat(name,value,rate){
    const box=el("div","ai-replay-stat");
    box.append(el("span","",name),el("strong","",value));
    if(typeof rate==="number"){
      const rail=el("div","ai-replay-rail");
      const fill=el("div","ai-replay-bar");
      fill.style.width=(Math.max(0,Math.min(1,rate))*100)+"%";
      rail.append(fill);box.append(rail);
    }
    return box;
  }
  function render(report){
    result=report;
    const summary=$("ai-baseline-summary");
    summary.replaceChildren();
    for(const level of report.opponents){
      const item=report.levels[level];
      const card=el("section","ai-replay-score");
      card.append(el("h5","",names[level]));
      const stats=el("div","ai-replay-stats");
      stats.append(stat("参与次数",item.exposures));
      stats.append(stat("胡牌事件",item.wins));
      stats.append(stat("放铳责任",item.deal_ins));
      stats.append(stat("最低向听切牌率",
        fraction(item.min_shanten_fraction),item.min_shanten_fraction));
      stats.append(stat("局部最优切牌率",
        fraction(item.local_optimal_fraction),item.local_optimal_fraction));
      card.append(stats);summary.append(card);
    }
    $("ai-baseline-caveat").textContent=
      "独立洗牌："+report.independent_shuffle_seeds+
      "个，四轮共享同一牌墙种子（不能当成四个独立样本）。"+
      (report.intervals===null?
        "少于5个独立种子：不生成区间。":"区间只是探索性成组重抽样，并非真人胜率区间。")+
      "这是一套独立切牌规则基线，不是外部机器学习模型。";
    const delta=$("ai-baseline-differences");
    delta.replaceChildren();
    for(const level of ["basic","advanced","challenge"]){
      const section=el("section","ai-replay-comparison");
      section.append(el("strong","",names[level]+"－独立牌形基线"));
      for(const [metric,title] of [
        ["win_event_fraction","胡牌事件率差"],
        ["min_shanten_fraction","最低向听率差"],
        ["local_optimal_fraction","局部最优率差"],
      ]){
        const value=report.paired_differences_vs_baseline[level][metric];
        const interval=report.intervals?.paired_differences_vs_baseline?.[level]?.[metric];
        section.append(el("p","review-footnote",
          title+"："+(typeof value==="number"?
            (value>=0?"+":"")+(value*100).toFixed(1)+"个百分点":"无可比切牌")+
          (interval?"（探索 "+(interval[0]*100).toFixed(1)+"～"+
            (interval[1]*100).toFixed(1)+"）":"")));
      }
      delta.append(section);
    }
    $("ai-baseline-results").hidden=false;
  }
  async function check(expected){
    if(expected!==serial)return;
    try{
      const data=await action("ai_baseline_status",{baseline_token:taskToken});
      if(expected!==serial)return;
      const job=data.baseline;
      $("ai-baseline-progress").textContent=
        "独立基线实验："+job.completed_games+" / "+job.total_games+"局"+
        (job.status==="running"?"，后台执行中…":"");
      if(job.status==="running"){
        setTimeout(()=>check(expected),1300);
      }else{
        $("ai-baseline-start").disabled=false;
        if(job.status==="done")render(job.overview);
        else $("ai-baseline-error").textContent=job.error||"评测未完成";
      }
    }catch(error){
      $("ai-baseline-start").disabled=false;
      $("ai-baseline-error").textContent=error.message;
    }
  }
  async function start(){
    serial+=1;const expected=serial;
    result=null;taskToken=null;
    $("ai-baseline-results").hidden=true;
    $("ai-baseline-error").textContent="";
    $("ai-baseline-start").disabled=true;
    $("ai-baseline-progress").textContent="正在创建独立基线实验…";
    try{
      const seed=Number($("ai-baseline-seed").value);
      const seeds=Number($("ai-baseline-seeds").value);
      const data=await action("ai_baseline_start",{
        seed_start:seed,seeds:seeds,
      });
      if(expected!==serial)return;
      taskToken=data.baseline_token;
      await check(expected);
    }catch(error){
      $("ai-baseline-start").disabled=false;
      $("ai-baseline-error").textContent=error.message;
    }
  }
  function exportCSV(){
    if(!result)return;
    const fields=["seed","policy","exposures","wins","deal_ins","discards",
      "minimum_shanten","local_optimal"];
    const rows=[fields.join(",")];
    for(const entry of result.per_seed){
      for(const level of result.opponents){
        const item=entry.levels[level];
        rows.push([entry.seed,level,item.exposures,item.wins,item.deal_ins,
          item.discards,item.minimum_shanten,item.local_optimal].join(","));
      }
    }
    const csv=String.fromCharCode(0xFEFF)+rows.join("\r\n")+"\r\n";
    const blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    const anchor=document.createElement("a");
    anchor.href=url;anchor.download="mahtrain-independent-ai-seeds.csv";
    anchor.click();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
  }
  function init(){
    $("ai-baseline-start").addEventListener("click",start);
    $("ai-baseline-export").addEventListener("click",exportCSV);
  }
  window.MahTrainAIBaseline={init};
})();
