"use strict";
/* Local-only SQLite history browser; no account or cloud synchronization. */
(function(){
  const $=id=>document.getElementById(id);
  let selectedId=null;
  let selectedDetail=null;
  let busy=false;
  const names={m:"万",s:"条",p:"筒"};
  const name=t=>t==="win"?"胡牌":(t.slice(1)+names[t[0]]);
  const percent=value=>(value*100).toFixed(1)+"%";
  function el(tag,css,text){
    const n=document.createElement(tag);
    if(css)n.className=css;
    if(text!==undefined)n.textContent=String(text);
    return n;
  }
  function btn(text,kind,handler){
    const b=el("button",kind,text);b.type="button";b.addEventListener("click",handler);return b;
  }
  function error(message){
    const root=$("history-detail");
    root.replaceChildren(el("p","review-attention",message));
  }
  async function get(url){
    const res=await fetch(url,{cache:"no-store"});
    const data=await res.json();
    if(!res.ok)throw new Error(data.error||"读取历史记录失败");
    return data;
  }
  async function post(action,params){
    const res=await fetch("/api/action",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-MahTrain":"1"},
      body:JSON.stringify({action,...params}),
    });
    const data=await res.json();
    if(!res.ok)throw new Error(data.error||"历史操作失败");
    return data;
  }
  function metric(title,value){
    const box=el("div","history-metric");
    box.append(el("span","",title),el("strong","",value));
    return box;
  }
  function localDate(s){
    const date=new Date(s);
    return Number.isNaN(date.valueOf())?s:date.toLocaleString("zh-CN");
  }
  function renderSummary(summary){
    const root=$("history-summary");
    root.replaceChildren(
      metric("累计训练",summary.session_count+"局"),
      metric("已切/胡牌轮数",summary.rounds_total+"轮"),
      metric("所有回合正确率",summary.rounds_total
        ?percent(summary.correct_total/summary.rounds_total):"—"),
      metric("历史错误切牌",summary.mistake_total+"次")
    );
    const progress=$("history-progress");
    progress.textContent=(summary.session_count<2)
      ?"记录更多训练后，这里将显示不同阶段的成绩变化。"
      :"最早最多5局平均正确率 "+
       percent(summary.first_five_average)+" → 最新最多5局 "+
       percent(summary.latest_five_average)+
       "（相差 "+((summary.latest_five_average-summary.first_five_average)*100).toFixed(1)+
       " 个百分点）。仅比较已有训练，样本较小时波动可能很大。";
  }
  async function refresh(){
    if(busy)return;
    busy=true;
    try{
      const res=await get("/api/history?limit=40");
      renderSummary(res.summary);
      const list=$("history-list");
      list.replaceChildren();
      for(const entry of res.sessions){
        const box=el("div","history-entry");
        const top=el("div","history-entry-top");
        top.append(el("strong","",localDate(entry.created_at)),
          el("span","",entry.completed_rounds+"轮 · "+
            percent(entry.accuracy)+" · 错 "+entry.mistake_count+"道"));
        box.append(top);
        box.append(btn("查看历史报告","review-control",()=>openDetail(entry.archive_id)));
        list.append(box);
      }
      if(!res.sessions.length){
        list.append(el("p","review-intro","目前还没有已结束的训练记录。完成一次14轮训练后，将自动保存到本机SQLite数据库。"));
      }
    }catch(err){error(err.message);}
    finally{busy=false;}
  }
  function textline(box,label,value){
    const p=el("p","review-detail-line");
    p.append(el("b","",label),document.createTextNode(" "+value));box.append(p);
  }
  function showDetail(data){
    selectedDetail=data;
    selectedId=data.archive_id;
    const board=$("history-detail");
    board.replaceChildren();
    const header=el("div","history-detail-title");
    header.append(el("h4","","历史训练 · "+localDate(data.created_at)));
    header.append(btn("关闭报告","review-control",()=>{
      selectedDetail=null;selectedId=null;board.replaceChildren();
    }));
    board.append(header);
    const report=data.report;
    board.append(el("p","review-intro",
      "定缺 "+names[data.missing_suit]+
      " · "+report.completed_rounds+"轮 · 正确 "+report.correct_rounds+
      "轮 · 最优率 "+percent(report.accuracy)+
      " · 暗杠 "+report.kong_count+"次"));
    const summary=report.progress_summary||{};
    board.append(el("p","review-intro",
      "由首轮至末轮切牌：向听 "+(summary.first_shanten??"—")+" → "+
      (summary.last_shanten??"—")+
      "；有效进张 "+(summary.first_effective_tile_count??"—")+" → "+
      (summary.last_effective_tile_count??"—")+" 张。"));
    const rows=el("div","history-rounds");
    for(const round of report.round_review||[]){
      const details=el("details","history-round");
      details.append(el("summary","", "第"+round.round+"轮 · "+
        (round.is_win?"确认胡牌":"切 "+name(round.choice))+
        " · "+(round.correct?"最优":"可改进")));
      const panel=el("div","history-round-body");
      textline(panel,"当时摸牌：",round.drawn_tile?name(round.drawn_tile):"—");
      textline(panel,"最佳动作：",round.best_actions.map(name).join("、"));
      if(!round.is_win)textline(panel,"切后牌效：",
        "向听 "+round.shanten+"，进张 "+round.effective_tile_count+
        " 张，下摸模型概率 "+percent(round.next_draw_probability));
      textline(panel,"原因：",round.explanation);
      if(!round.correct){
        panel.append(btn("重新练这道题","review-control",()=>startRetry(round.round)));
      }
      details.append(panel);rows.append(details);
    }
    board.append(rows);
    const controls=el("div","retry-controls");
    controls.append(btn("返回历史列表","review-control",()=>board.replaceChildren()));
    controls.append(btn("永久删除这局及重练记录","history-delete",()=>{
      if(confirm("确定永久删除这一局训练及所有对应重练记录？此操作不能撤销。")){
        deleteHistory(data.archive_id);
      }
    }));
    board.append(controls);
  }
  async function openDetail(id){
    try{showDetail(await get("/api/history?archive_id="+encodeURIComponent(id)));}
    catch(err){error(err.message);}
  }
  async function startRetry(round){
    const archive_id=selectedId;
    if(!archive_id)return;
    try{
      const {question:q}=await post("history_retry_question",{archive_id,round});
      const board=$("history-detail");
      board.replaceChildren();
      board.append(el("h4","retry-heading","历史错题重练 · 第"+round+"轮"));
      board.append(el("p","review-intro",
        "定缺 "+names[q.missing_suit]+"，摸 "+name(q.drawn_tile)+
        "；先重新判断，提交后再与旧答案比较。"));
      const hand=el("div","retry-hand");
      q.concealed.forEach(tile=>hand.append(window.MahTrainUI.tileElement(tile)));
      board.append(hand);
      if(q.exposed_kongs.length){
        const melds=el("div","retry-melds");
        for(const group of q.exposed_kongs){
          const m=el("div","retry-meld");
          m.append(el("span","","当时已开的暗杠"));
          group.tiles.forEach(tile=>m.append(window.MahTrainUI.tileElement(tile,{small:true})));
          melds.append(m);
        }
        board.append(melds);
      }
      board.append(el("p","retry-label","点击重新切牌或确认胡牌"));
      const options=el("div","retry-choices");
      for(const tile of q.choices){
        if(tile==="win")options.append(btn("确认胡牌","primary",()=>gradeRetry(archive_id,round,tile)));
        else options.append(window.MahTrainUI.tileElement(tile,{
          selectable:true,onClick:()=>gradeRetry(archive_id,round,tile),
        }));
      }
      board.append(options,btn("返回历史报告","review-control",()=>openDetail(archive_id)));
    }catch(err){error(err.message);}
  }
  async function gradeRetry(archive_id,round,tile){
    try{
      const reply=await post("history_retry_submit",{archive_id,round,tile});
      const result=reply.result;
      const board=$("history-detail");board.replaceChildren();
      board.append(el("h4","retry-heading",
        "历史第"+round+"轮 · "+(result.correct?"重练答对":"重练仍可优化")));
      const cards=el("div","retry-compare");
      for(const [heading,choice,data] of [
        ["首次选择",result.original_choice,result.original_candidate],
        ["重练选择",result.retry_choice,result.retry_candidate],
      ]){
        const card=el("div","retry-compare-card");
        card.append(el("span","retry-overline",heading),el("strong","",name(choice)),
          el("p","",data?"向听 "+data.shanten+" · 进张 "+
            data.effective_tile_count+" 张 · "+percent(data.next_draw_probability):
            "胡牌（无切后进张）"));
        cards.append(card);
      }
      board.append(cards);
      board.append(el("p","retry-answer","正确选择："+result.best_actions.map(name).join("、")));
      board.append(el("p","review-intro",result.explanation));
      const controls=el("div","retry-controls");
      controls.append(btn("再练一次","review-control",()=>startRetry(round)));
      controls.append(btn("返回历史报告","review-control",()=>openDetail(archive_id)));
      board.append(controls);
    }catch(err){error(err.message);}
  }
  async function deleteHistory(id){
    try{
      await post("history_delete",{archive_id:id});
      selectedId=null;selectedDetail=null;
      $("history-detail").replaceChildren();
      await refresh();
    }catch(err){error(err.message);}
  }
  function init(){
    $("history-refresh").addEventListener("click",refresh);
    refresh();
  }
  window.MahTrainHistory={init,refresh};
})();
