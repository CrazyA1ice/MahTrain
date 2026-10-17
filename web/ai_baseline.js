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
  function renderOfficialScores(report){
    const analysis=report?.official_score_analysis;
    const area=$("ai-baseline-official");
    area.hidden=!analysis;
    if(!analysis)return;
    $("ai-baseline-official-caveat").textContent=
      "规则A（仅未胡玩家参加流局结算） · 系数"+
      analysis.room_coefficient+" · 封顶"+analysis.fan_cap+"番 · "+
      "不含模拟杠钱。请求"+analysis.requested_seeds+"个洗牌种子，"+
      "核验"+analysis.valid_seeds+"个，"+
      "未核验流局排除"+analysis.excluded_seed_count+"个种子的全部四轮。"+
      (analysis.intervals?
        "以下区间只是种子成组重抽样的探索性描述，非胜率置信区间。":
        "有效种子少于5个，不提供统计区间。");
    const cards=$("ai-baseline-official-levels");
    cards.replaceChildren();
    for(const level of report.opponents){
      const score=analysis.levels[level];
      const card=el("section","ai-replay-score");
      card.append(el("h5","",names[level]+" · 正式积分"));
      const figures=el("div","ai-replay-stats");
      figures.append(stat("合格座位出场",score.seat_exposures));
      figures.append(stat("正式净积分总额",score.official_total));
      figures.append(stat("每次出场平均正式积分",
        score.official_mean_per_exposure===null?"无已核验局":
        (score.official_mean_per_exposure>=0?"+":"")+
        score.official_mean_per_exposure));
      if(analysis.intervals){
        figures.append(stat("探索性区间",
          analysis.intervals.levels[level].join(" ～ ")));
      }
      card.append(figures);
      cards.append(card);
    }
    const differences=$("ai-baseline-official-differences");
    differences.replaceChildren();
    for(const level of ["basic","advanced","challenge"]){
      const delta=analysis.paired_differences_vs_baseline[level];
      const bounds=analysis.intervals?.differences_vs_baseline?.[level];
      differences.append(el("p","review-footnote",
        names[level]+"－独立牌形基线："+(
          delta===null?"有效种子不足":
          (delta>=0?"+":"")+delta+" 分/座位出场")+
        (bounds?" · 探索性区间 ["+bounds.join("，")+"]":"")));
    }
  }
  function exportOfficialScores(){
    const analysis=result?.official_score_analysis;
    if(!analysis)return;
    const rows=["seed,policy,seat_exposures,official_total,mean_per_exposure"];
    for(const entry of analysis.per_seed){
      for(const level of result.opponents){
        const item=entry.levels[level];
        rows.push([entry.seed,level,item.seat_exposures,
          item.official_total,item.official_mean_per_exposure].join(","));
      }
    }
    const csv=String.fromCharCode(0xFEFF)+rows.join("\r\n")+"\r\n";
    const blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    const link=document.createElement("a");
    link.href=url;
    link.download="mahtrain-independent-four-policy-official-scores.csv";
    link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
  }
  function renderDecisionScoreDiagnostics(report){
    const diagnostic=report?.decision_score_diagnostics;
    const panel=$("ai-baseline-decision-scores");
    panel.hidden=!diagnostic;
    if(!diagnostic)return;
    const official=report.official_score_analysis;
    $("ai-baseline-decision-caveat").textContent=
      "与方案A正式积分完全相同的已核验种子："+diagnostic.valid_seeds+
      "个（整簇排除"+diagnostic.excluded_seed_count+"个），"+
      diagnostic.complete_games+"局。只有赛后聚合数据，无暗手和未公开摸牌信息。";
    const table=$("ai-baseline-decision-table");
    table.replaceChildren();
    const columns=[
      "AI策略","正式分/出场","最低向听率","局部最优率",
      "选后有效张均值","放铳责任事件/百次切牌","切牌样本",
    ];
    const header=el("div","ai-decision-row ai-decision-heading");
    header.setAttribute("role","row");
    for(const name of columns){
      const cell=el("strong","",name);
      cell.setAttribute("role","columnheader");
      header.append(cell);
    }
    table.append(header);
    function showNumber(n,suffix="",decimals=2){
      return typeof n==="number" && Number.isFinite(n)
        ?(n>=0?"+":"")+n.toFixed(decimals)+suffix:"无可用样本";
    }
    function showRatio(n){
      return typeof n==="number" && Number.isFinite(n)
        ?(n*100).toFixed(1)+"%":"无可用样本";
    }
    for(const level of report.opponents){
      const data=diagnostic.levels[level];
      const points=official.levels[level].official_mean_per_exposure;
      const row=el("div","ai-decision-row");
      row.setAttribute("role","row");
      const values=[
        names[level],
        showNumber(points,"",2),
        showRatio(data.min_shanten_fraction),
        showRatio(data.local_optimal_fraction),
        typeof data.mean_effective_copies==="number"
          ?data.mean_effective_copies.toFixed(2):"无可用样本",
        typeof data.deal_in_events_per_100_discards==="number"
          ?data.deal_in_events_per_100_discards.toFixed(2):"无可用样本",
        String(data.discards),
      ];
      for(let i=0;i<values.length;i++){
        const cell=el("span",i===1?"ai-decision-official":"",values[i]);
        cell.setAttribute("role",i===0?"rowheader":"cell");
        if((i===2||i===3)&&typeof (
          i===2?data.min_shanten_fraction:data.local_optimal_fraction
        )==="number"){
          const rail=el("span","ai-decision-rail");
          const bar=el("span","ai-decision-bar");
          bar.style.width=(Math.max(0,Math.min(1,
            i===2?data.min_shanten_fraction:data.local_optimal_fraction))*100)+
            "%";
          rail.append(bar);
          cell.append(rail);
        }
        row.append(cell);
      }
      table.append(row);
    }
    const context=$("ai-baseline-decision-disagreements");
    context.replaceChildren();
    for(const level of ["basic","advanced","challenge"]){
      const counts=diagnostic.direction_disagreements_vs_baseline[level];
      context.append(el("p","review-footnote",
        names[level]+" 对基线：可比较种子"+counts.comparable_seeds+
        "个；最低向听率更高但正式积分更低 "+
        counts.higher_min_shanten_but_lower_score_seeds+"个；"+
        "最低向听率更低但正式积分更高 "+
        counts.lower_min_shanten_but_higher_score_seeds+
        "个。这是同期指标方向不同的计数，不说明因果。"));
    }
  }
  function exportDecisionScoreCSV(){
    const diagnostic=result?.decision_score_diagnostics;
    const official=result?.official_score_analysis;
    if(!diagnostic||!official)return;
    const rows=[
      "policy,valid_seeds,seat_exposures,official_mean_per_exposure,discards,"+
      "min_shanten_fraction,local_optimal_fraction,mean_effective_copies,"+
      "mean_shanten_regret,deal_in_events,deal_in_events_per_100_discards",
    ];
    for(const level of result.opponents){
      const x=diagnostic.levels[level];
      const y=official.levels[level];
      rows.push([
        level,diagnostic.valid_seeds,x.seat_exposures,
        y.official_mean_per_exposure,x.discards,
        x.min_shanten_fraction,x.local_optimal_fraction,
        x.mean_effective_copies,x.mean_shanten_regret,
        x.deal_in_events,x.deal_in_events_per_100_discards,
      ].map(value=>value===null?"":value).join(","));
    }
    const csv=String.fromCharCode(0xFEFF)+rows.join("\r\n")+"\r\n";
    const blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    const link=document.createElement("a");
    link.href=url;
    link.download="mahtrain-four-policy-decision-official-comparison.csv";
    link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
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
    renderOfficialScores(report);
    renderDecisionScoreDiagnostics(report);
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
    $("ai-baseline-official-export").addEventListener("click",exportOfficialScores);
    $("ai-baseline-decision-export").addEventListener("click",exportDecisionScoreCSV);
  }
  window.MahTrainAIBaseline={init};
})();
