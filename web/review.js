"use strict";
/* Review only completed/graded rounds. The server never sends future-wall
   information or current unsubmitted candidate analyses to this component. */
(function(){
  const $=id=>document.getElementById(id);
  function el(tag,css,text){
    const e=document.createElement(tag);
    if(css)e.className=css;
    if(text!==undefined)e.textContent=String(text);
    return e;
  }
  const pct = n=>n==null?"—":(n*100).toFixed(1)+"%";
  const count = n=>n==null?"—":n+"张";
  const signed = (n,unit="")=>n==null?"—":(n>0?"+":"")+n+unit;
  const signedPct = n=>n==null?"—":(n>0?"+":"")+(n*100).toFixed(1)+"百分点";
  function smallStat(name,value){
    const block=el("div","review-stat");
    block.append(el("span","review-stat-label",name),el("strong","",value));
    return block;
  }
  function line(parent,label,value){
    const p=el("p","review-detail-line");
    p.append(el("b","",label),document.createTextNode(" "+value));
    parent.append(p);
  }
  function barChart(rows){
    const frame=el("div","review-chart");
    frame.append(el("h4","", "切后有效进张走势（张）"));
    const bars=el("div","review-bars");
    bars.setAttribute("role","img");
    bars.setAttribute("aria-label","历次切牌后有效进张枚数对照图");
    const known=rows.filter(row=>row.effective_tile_count!==null);
    const max=Math.max(1,...known.map(r=>r.effective_tile_count));
    for(const row of rows){
      const item=el("div","review-bar-item");
      const value=row.effective_tile_count;
      if(value!==null){
        const number=el("span","review-bar-number",String(value));
        const bar=el("div","review-bar "+(row.correct?"optimal":"suboptimal"));
        bar.style.height=(Math.max(3,value/max*94)).toFixed(1)+"px";
        bar.title="第"+row.round+"轮：切后有效进张"+value+"张，向听"+row.shanten;
        item.append(number,bar);
      }else{
        item.append(el("span","review-bar-number","胡"));
        item.append(el("div","review-bar winning"));
      }
      item.append(el("span","review-bar-caption",""+row.round));
      bars.append(item);
    }
    frame.append(bars);
    frame.append(el("p","review-footnote","每根柱代表当轮实际切牌后的有效进张枚数；灰金为非最优，绿色为最优。新摸牌与已见牌的变化也会影响数值。"));
    return frame;
  }
  function detailedRows(rows,tileName){
    const container=el("div","review-round-list");
    for(const round of rows){
      const entry=el("details","review-round "+(round.correct?"review-correct":"review-incorrect"));
      const summary=el("summary");
      const displayTile=t=>t==="win"?"胡牌":tileName(t);
      const action=displayTile(round.choice);
      const status=round.correct?"正确":"可优化";
      summary.append(el("span","review-index","#"+round.round));
      summary.append(el("span","review-choice","摸 "+(round.drawn_tile?displayTile(round.drawn_tile):"—")+" · "+(round.is_win?"胡牌":("切 "+action))));
      summary.append(el("span","review-result "+(round.correct?"review-ok":"review-warn"),status));
      summary.append(el("span","review-mini-stat",round.is_win?"提前胡牌":"向听"+round.shanten+" · "+count(round.effective_tile_count)+"进张"));
      summary.append(el("span","review-chevron","⌄"));
      const panel=el("div","review-round-body");
      line(panel,"最佳选择：",round.best_actions.map(displayTile).join("、")||"—");
      line(panel,"切后牌效：",round.is_win?"胡牌成功，不需要切牌":
        ("向听 "+round.shanten+" ｜ 有效进张 "+count(round.effective_tile_count)+
         " ｜ 下一摸改善/胡牌估计 "+pct(round.next_draw_probability)));
      if(!round.is_win){
        const bestCount=round.best_effective_tile_count;
        if(bestCount!==null)line(panel,"同层最佳进张：",count(bestCount));
        if(round.shanten_loss>0)line(panel,"向听损失：","+"+round.shanten_loss+" 向听");
        else if(round.ukeire_loss>0)line(panel,"有效进张损失：",count(round.ukeire_loss));
        const delta=round.change_from_previous_discard;
        if(delta)line(panel,"较上一切牌：","向听 "+signed(delta.shanten)+
          " ｜ 有效进张 "+signed(delta.effective_tile_count,"张")+
          " ｜ 估计概率 "+signedPct(delta.next_draw_probability));
        if(round.effective_details?.length){
          line(panel,"有效牌明细：",
            round.effective_details.map(d=>displayTile(d.tile)+"×"+d.remaining).join("、"));
        }else line(panel,"有效牌明细：","无剩余可改善进张");
      }
      if(round.hand_before?.length)line(panel,"当轮14有效张暗手：",round.hand_before.map(displayTile).join("、"));
      line(panel,"判题解析：",round.explanation||"—");
      entry.append(summary,panel);
      container.append(entry);
    }
    return container;
  }
  function render(report,tileName){
    const panel=$("report-panel");
    const root=$("report");
    if(!report?.completed_rounds){panel.hidden=true;root.replaceChildren();return;}
    panel.hidden=false;
    root.replaceChildren();
    $("report-title").textContent=report.finished?"训练结束 · 完整复盘":"训练进行中 · 已完成回合";
    $("report-subtitle").textContent=report.completed_rounds+" / "+
      report.round_limit+" 轮 · "+(report.finished?"最终报告":"实时更新，尚未提交的轮次不显示答案");
    const kpis=el("div","report-grid");
    const summary=report.progress_summary||{};
    kpis.append(
      smallStat("最优切牌正确率",pct(report.accuracy)),
      smallStat("累计退向听选择",report.shanten_regression_rounds+"次"),
      smallStat("同向听层进张损失合计",count(summary.missed_ukeire_total_at_same_shanten??0)),
      smallStat("完成切牌轮次",summary.discard_rounds??0)
    );
    root.append(kpis);
    const trend=el("div","review-trend");
    trend.append(el("h4","","阶段牌效变化总结"));
    if(summary.discard_rounds>0){
      const shantenChange=signed(summary.shanten_change);
      const tileChange=signed(summary.effective_tile_count_change,"张");
      const probChange=signedPct(summary.probability_change);
      const text="首轮至最近一次切牌：向听 "+summary.first_shanten+
        " → "+summary.last_shanten+"（变化 "+shantenChange+"）；有效进张 "+
        count(summary.first_effective_tile_count)+" → "+
        count(summary.last_effective_tile_count)+"（变化 "+tileChange+
        "）；下一摸改善/胡牌估计 "+pct(summary.first_next_draw_probability)+
        " → "+pct(summary.last_next_draw_probability)+"（变化 "+probChange+"）。";
      trend.append(el("p","review-intro",text));
      const improvement="按相邻已完成切牌比较，向听下降 "+
        summary.shanten_improved_rounds+" 次、上升 "+
        summary.shanten_worsened_rounds+" 次、持平 "+
        summary.shanten_unchanged_rounds+" 次。持平且有效进张增加 "+
        summary.same_shanten_ukeire_increased_rounds+" 次。";
      trend.append(el("p","review-intro",improvement));
    }else{
      trend.append(el("p","review-intro","本次已胡牌结束，没有产生切牌牌效曲线。"));
    }
    if(summary.missed_win_rounds)trend.append(el("p","review-attention",
      "注意：曾 "+summary.missed_win_rounds+" 次放弃已提示的合法胡牌。"));
    root.append(trend);
    root.append(barChart(report.round_review||[]));
    const title=el("div","review-table-title");
    title.append(el("h4","","逐轮切牌复盘"));
    title.append(el("span","review-small","点击每轮展开手牌、最优选择、有效进张明细与解析"));
    root.append(title);
    root.append(detailedRows(report.round_review||[],tileName));
    root.append(el("p","review-footnote",
      "说明：牌效概率仅以当轮自己手牌与已公开弃牌为已知信息估算，并非真实牌墙的精确未来概率；跨轮变化还受到新摸牌、可见牌变化影响，不能将其全部归因于上一轮切牌。"));
    if(report.finished)root.append(el("p","review-finished",
      report.finished_reason==="self_drawn_win"
        ?"训练因自摸胡牌提前结束，所有已完成轮次均已纳入复盘。"
        :"本次训练已结束，所有已完成轮次均已纳入复盘。"));
  }
  window.MahTrainReview={render};
})();
