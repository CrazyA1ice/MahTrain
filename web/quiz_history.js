"use strict";
/* Persistent independent-question results and opt-in level recommendation.
   Scoring and recommendations are computed on server from SQLite. */
(function(){
  const $=id=>document.getElementById(id);
  const labels={basic:"基础",intermediate:"进阶",challenge:"挑战"};
  const modes={one_shanten:"一向听何切",tenpai_discard:"听牌何切",
    pure_suit_waits:"清一色选听口",pure_suit_discard:"清一色何切"};
  const name=t=>t==="win"?"胡牌":window.MahTrainUI.tileName(t);
  let current=null,lastDetail=null,pending=null,busy=false,fetchSeq=0;
  function el(tag,css,s){
    const v=document.createElement(tag);
    if(css)v.className=css;
    if(s!==undefined)v.textContent=String(s);
    return v;
  }
  function button(s,css,fn){
    const b=el("button",css,s);
    b.type="button";b.addEventListener("click",fn);return b;
  }
  async function call(action,data={}){
    const res=await fetch("/api/action",{method:"POST",
      headers:{"Content-Type":"application/json","X-MahTrain":"1"},
      body:JSON.stringify({action,...data})});
    const result=await res.json();
    if(!res.ok)throw new Error(result.error||"单题历史读取失败");
    return result;
  }
  function percent(x){return x===null?"—":(100*x).toFixed(1)+"%";}
  function error(err){
    $("quiz-history-detail").replaceChildren(el("p","review-attention",err.message||String(err)));
  }
  async function refresh(){
    const myFetch=++fetchSeq;
    const mode=$("quiz-mode").value,difficulty=$("quiz-level").value;
    try{
      const response=await call("quiz_progress",{mode,difficulty});
      if(myFetch!==fetchSeq)return;
      current=response.progress;
      render(response.progress);
    }catch(err){if(myFetch===fetchSeq)error(err);}
  }
  function render(p){
    const root=$("quiz-history-stats");
    root.replaceChildren();
    for(const difficulty of ["basic","intermediate","challenge"]){
      const level=p.level_totals[difficulty];
      const block=el("div","quiz-history-metric");
      block.append(el("span","",labels[difficulty]),
        el("strong","",level.total+"题"),
        el("small","",level.total?percent(level.accuracy)+" 正确率":"尚未练习"));
      root.append(block);
    }
    const recommendation=$("quiz-recommendation");
    recommendation.replaceChildren();
    recommendation.append(el("strong","","近期表现与难度建议"));
    recommendation.append(el("p","",
      "当前"+labels[p.difficulty]+" · 近"+p.recent.attempts+
      "/"+p.recent.window+"题 · 正确率"+percent(p.recent.accuracy)));
    recommendation.append(el("p","",p.recommendation.reason));
    if(p.recommendation.level!==p.difficulty){
      recommendation.append(button("采用推荐："+labels[p.recommendation.level],
        "review-control",()=>{
          $("quiz-level").value=p.recommendation.level;
          $("quiz-level").dispatchEvent(new Event("change",{bubbles:true}));
        }));
    }
    const weaknesses=p.weaknesses;
    const area=$("quiz-weaknesses");
    area.replaceChildren();
    area.append(el("h4","","错因分析与专项强化"));
    area.append(el("p","review-footnote",
      "统计该模式最近最多30道首次答错的题；同题可能同时漏选和误选听口。"));
    const entries=Object.entries(weaknesses.counts).sort((a,b)=>b[1]-a[1]);
    const grid=el("div","quiz-weakness-grid");
    for(const [key,count] of entries){
      const item=el("div","quiz-weakness-item");
      item.append(el("strong","",weaknesses.labels[key]),
        el("span","",count+"次"));
      item.append(button("专项练习","review-control",()=>{
        window.MahTrainQuiz.focus(key);
      }));
      grid.append(item);
    }
    area.append(grid);
    if(weaknesses.top_focus){
      const top=weaknesses.labels[weaknesses.top_focus];
      area.append(el("p","review-intro","近期主要错因："+top));
      area.append(button("开启薄弱项强化 · 按错因频次出题",
        "primary",()=>window.MahTrainQuiz.focus("auto")));
    }else{
      area.append(el("p","review-intro",
        "该模式尚无已记录的错误，可以先自由选择专项练习。"));
    }
    const list=$("quiz-attempt-list");
    list.replaceChildren();
    if(!p.attempts.length){
      list.append(el("p","review-intro","该模式尚无单题答题记录，完成一题后会自动存入本机数据库。"));
      return;
    }
    for(const row of p.attempts){
      const item=el("div","quiz-history-entry");
      const desc=el("div","quiz-history-caption");
      const date=new Date(row.created_at);
      desc.append(el("strong","",labels[row.difficulty]+" · "+(row.correct?"答对":"可改进")));
      desc.append(el("span","",Number.isNaN(date.valueOf())
        ?row.created_at:date.toLocaleString("zh-CN")));
      item.append(desc);
      item.append(button(row.correct?"查看解析":"查看 / 重练",
        "review-control",()=>openDetail(row.answer_id)));
      list.append(item);
    }
  }
  function explain(detail){
    const root=$("quiz-history-detail");
    root.replaceChildren();
    lastDetail=detail;
    root.append(el("h4","",modes[detail.mode]+" · "+labels[detail.difficulty]));
    const q=detail.question,r=detail.result;
    const cards=el("div","retry-hand");
    q.concealed.forEach(t=>cards.append(window.MahTrainUI.tileElement(t)));
    root.append(cards);
    const answers=q.answer_type==="tile_set"?r.correct_tiles:r.best_actions;
    const chosen=q.answer_type==="tile_set"
      ?detail.selection.map(name).join("、"):name(detail.selection);
    root.append(el("p","review-detail-line","原始作答："+(chosen||"未选择")));
    root.append(el("p","review-detail-line","最佳答案："+answers.map(name).join("、")));
    root.append(el("p","review-intro",r.reason));
    root.append(el("p","review-footnote",
      "生成牌型："+(r.construction_family||"基础组合")+
      " · 重练次数："+detail.retry.attempts+
      " · 最近重练："+(detail.retry.latest_correct===null?"尚无":
        (detail.retry.latest_correct?"正确":"可改进"))));
    const actions=el("div","retry-controls");
    if(!detail.correct){
      actions.append(button("重新做这道错题","review-control",()=>openRetry(detail.answer_id)));
    }
    actions.append(button("关闭详情","review-control",()=>root.replaceChildren()));
    actions.append(button("删除此单题记录","history-delete",async()=>{
      if(!confirm("确定删除这道单题及对应重练记录？不可撤销。"))return;
      try{
        await call("quiz_delete",{answer_id:detail.answer_id});
        lastDetail=null;pending=null;root.replaceChildren();
        await refresh();
      }catch(err){error(err);}
    }));
    root.append(actions);
  }
  async function openDetail(answerId){
    if(busy)return;
    busy=true;
    try{
      const data=await call("quiz_detail",{answer_id:answerId});
      explain(data.detail);
    }catch(err){error(err);}
    finally{busy=false;}
  }
  async function openRetry(answerId){
    if(busy)return;
    busy=true;
    try{
      const response=await call("quiz_retry_question",{answer_id:answerId});
      pending={answerId,question:response.question,selected:new Set()};
      renderRetry();
    }catch(err){error(err);}
    finally{busy=false;}
  }
  function renderRetry(){
    const item=pending;
    if(!item)return;
    const q=item.question,root=$("quiz-history-detail");
    root.replaceChildren();
    root.append(el("h4","","单题错题重练 · "+labels[q.difficulty]));
    root.append(el("p","review-intro",
      "恢复原题手牌。请重新判断，提交前这里不会展示标准答案。"));
    const hand=el("div","retry-hand");
    q.concealed.forEach(tile=>hand.append(window.MahTrainUI.tileElement(tile)));
    root.append(hand);
    const options=el("div","quiz-options");
    for(const tile of q.choices){
      const b=tile==="win"
        ?button("确认胡牌","primary",()=>pick(tile))
        :window.MahTrainUI.tileElement(tile,{selectable:true,onClick:()=>pick(tile)});
      b.classList.add("quiz-option");
      if(item.selected.has(tile))b.classList.add("chosen");
      options.append(b);
    }
    root.append(options);
    const row=el("div","retry-controls");
    row.append(button("提交重练答案","primary",submitRetry));
    row.append(button("返回历史列表","review-control",()=>{
      pending=null;root.replaceChildren();
    }));
    root.append(row);
  }
  function pick(tile){
    if(!pending||busy)return;
    const selected=pending.selected;
    if(pending.question.answer_type==="tile_set"){
      if(selected.has(tile))selected.delete(tile);else selected.add(tile);
    }else{selected.clear();selected.add(tile);}
    renderRetry();
  }
  async function submitRetry(){
    if(!pending||busy)return;
    const q=pending.question,answerId=pending.answerId;
    if(q.answer_type!=="tile_set"&&!pending.selected.size){
      error(new Error("请先选择一张切牌或胡牌。"));return;
    }
    const selection=q.answer_type==="tile_set"
      ?[...pending.selected]:[...pending.selected][0];
    busy=true;
    try{
      const response=await call("quiz_retry_answer",{
        answer_id:answerId,selection,
      });
      pending=null;
      const result=response.result;
      const root=$("quiz-history-detail");
      root.replaceChildren();
      root.append(el("h4","",
        result.correct?"这次重练正确":"这次仍未达到最优"));
      const format=v=>Array.isArray(v)?v.map(name).join("、"):name(v);
      root.append(el("p","review-detail-line","首次选择："+(format(result.original_selection)||"空")));
      root.append(el("p","review-detail-line","本次选择："+(format(result.selection)||"空")));
      root.append(el("p","review-detail-line","正确答案："+result.correct_answers.map(name).join("、")));
      root.append(el("p","review-intro",result.reason));
      root.append(el("p","review-footnote","这次重练已单独保存，不会计入首次单题正确率。"));
      root.append(button("再练一次","review-control",()=>openRetry(answerId)));
      root.append(button("关闭","review-control",()=>root.replaceChildren()));
      await refresh();
    }catch(err){error(err);}
    finally{busy=false;}
  }
  function init(){refresh();}
  window.MahTrainQuizHistory={init,refresh};
})();
