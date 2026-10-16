"use strict";
/* Isolated practice of incorrectly answered completed rounds.
 * No draw/wall mutations, and no ungraded solution in retry question JSON. */
(function(){
  const $=id=>document.getElementById(id);
  let sessionId=null;
  let originalReport=null;
  let retryStatus=null;
  let activeQuestion=null;
  let busy=false;
  const ui=()=>window.MahTrainUI;
  const name=tile=>tile==="win"?"胡牌":ui().tileName(tile);
  function el(tag,css,label){
    const e=document.createElement(tag);
    if(css)e.className=css;
    if(label!==undefined)e.textContent=String(label);
    return e;
  }
  function button(label,css,cb){
    const b=el("button",css,label);
    b.type="button";b.addEventListener("click",cb);return b;
  }
  function error(message){
    const board=$("retry-board");
    board.replaceChildren(el("p","review-attention",message));
  }
  async function call(action,extras={}){
    if(busy)return null;
    busy=true;
    try{
      const token=window.MahTrainUI?.getToken();
      const response=await fetch("/api/action",{
        method:"POST",
        headers:{"Content-Type":"application/json","X-MahTrain":"1"},
        body:JSON.stringify({action,token,...extras}),
      });
      const json=await response.json();
      if(!response.ok)throw new Error(json.error||"错题重练请求失败");
      return json;
    }catch(err){error(err.message||String(err));return null;}
    finally{busy=false;}
  }
  function maskOldAnswers(mask){
    // The old answers were already revealed after the first submission.
    // Hide them in the UI during a new attempt to reduce answer-peeking.
    const report=$("report-panel"),feedback=$("feedback");
    if(report)report.hidden=mask;
    if(feedback)feedback.hidden=mask;
  }
  function showMenu(){
    activeQuestion=null;
    maskOldAnswers(false);
    const board=$("retry-board");
    board.replaceChildren();
    const mistakes=originalReport?.round_review?.filter(r=>!r.correct)||[];
    if(!mistakes.length){
      board.append(el("p","review-intro","本局没有需要重练的错误回合。"));
      return;
    }
    board.append(el("p","review-intro",
      "共 "+mistakes.length+" 道错题。点击任意回合，重新选择当时的切牌；重练不会消耗牌墙或修改原成绩。"));
    if(retryStatus){
      board.append(el("p","retry-progress",
        "已重练 "+retryStatus.attempted_count+"/"+retryStatus.mistake_count+
        " 道，其中最近一次答对 "+retryStatus.corrected_count+" 道。"));
    }
    const cards=el("div","retry-cards");
    for(const item of mistakes){
      const entry=el("div","retry-card");
      const latest=retryStatus?.questions?.find(q=>q.round===item.round);
      entry.append(el("strong","","第 "+item.round+" 轮"),
        el("span","",latest?.attempt_count
          ?("已练 "+latest.attempt_count+" 次 · "+
             (latest.latest_correct?"最近答对":"尚未答对"))
          :"尚未重练"));
      entry.append(button("重练这一题","review-control",()=>open(item.round)));
      cards.append(entry);
    }
    board.append(cards);
  }
  async function open(number){
    const response=await call("retry_question",{round:number});
    if(!response)return;
    activeQuestion=response.question;
    maskOldAnswers(true);
    const board=$("retry-board");
    board.replaceChildren();
    const q=activeQuestion;
    board.append(el("h4","retry-heading","重练第 "+q.round+" 轮 · 第 "+q.attempt_number+" 次尝试"));
    board.append(el("p","review-intro",
      "当时摸到 "+name(q.drawn_tile)+"，定缺 "+({m:"万",s:"条",p:"筒"}[q.missing_suit])+
      "。请按当时的牌型重新选择。不显示原回合正确答案。"));
    board.append(el("p","retry-label","原回合手牌"));
    const hand=el("div","retry-hand");
    q.concealed.forEach(tile=>hand.append(ui().tileElement(tile)));
    board.append(hand);
    if(q.exposed_kongs.length){
      const melds=el("div","retry-melds");
      q.exposed_kongs.forEach(m=>{
        const mrow=el("div","retry-meld");
        mrow.append(el("span","","当时已锁定暗杠"));
        m.tiles.forEach(tile=>mrow.append(ui().tileElement(tile,{small:true})));
        melds.append(mrow);
      });
      board.append(melds);
    }
    board.append(el("p","retry-label","重新作答（点击切牌或胡牌）"));
    const choices=el("div","retry-choices");
    q.choices.forEach(tile=>{
      if(tile==="win"){
        choices.append(button("确认胡牌","primary",()=>submit(tile)));
      }else{
        choices.append(ui().tileElement(tile,{
          selectable:true,onClick:()=>submit(tile),
        }));
      }
    });
    board.append(choices);
    board.append(button("退出重练，返回报告","review-control",showMenu));
  }
  function metric(row){
    if(!row)return "胡牌（无切后向听和有效进张）";
    return "向听 "+row.shanten+" · 进张 "+row.effective_tile_count+
      "张 · 下一摸模型概率 "+(row.next_draw_probability*100).toFixed(1)+"%";
  }
  async function submit(tile){
    if(!activeQuestion)return;
    const round=activeQuestion.round;
    // Do not mutate the original session. Server grades an immutable snapshot.
    const response=await call("retry_submit",{round,tile});
    if(!response)return;
    retryStatus=response.retry;
    const result=response.result;
    const board=$("retry-board");
    board.replaceChildren();
    board.append(el("h4","retry-heading",
      "第 "+result.round+" 轮重练 · "+(result.correct?"本次答对":"仍有改进空间")));
    const cols=el("div","retry-compare");
    const first=el("div","retry-compare-card");
    first.append(el("span","retry-overline","原始练习"),
      el("strong","",name(result.original_choice)),
      el("p","",metric(result.original_candidate)));
    const second=el("div","retry-compare-card"+(result.correct?" corrected":""));
    second.append(el("span","retry-overline","这次重练"),
      el("strong","",name(result.retry_choice)),
      el("p","",metric(result.retry_candidate)));
    cols.append(first,second);
    board.append(cols);
    board.append(el("p","retry-answer",
      "当轮全部最佳动作："+result.best_actions.map(name).join("、")));
    board.append(el("p","review-intro",result.explanation));
    board.append(el("p","review-footnote",
      "成绩仅用于这道重练题的对照；原14轮切牌和牌墙不受影响。"));
    const actions=el("div","retry-controls");
    actions.append(button("再练一次","review-control",()=>open(round)));
    const next=(originalReport?.round_review||[])
      .find(r=>!r.correct && r.round>round)
      ||(originalReport?.round_review||[]).find(r=>!r.correct && r.round!==round);
    if(next)actions.append(button("下一道错题","review-control",()=>open(next.round)));
    actions.append(button("返回报告","review-control",showMenu));
    board.append(actions);
    if(window.MahTrainSound)window.MahTrainSound.play(result.correct?"win":"discard");
  }
  function render(report){
    const panel=$("retry-panel");
    if(!panel)return;
    if(!report?.finished){
      // A live training has its own report visibility rules.
      if(activeQuestion){
        $("report-panel").hidden=!report?.completed_rounds;
        $("feedback").hidden=false;
      }
      panel.hidden=true;
      sessionId=null;originalReport=null;retryStatus=null;activeQuestion=null;
      return;
    }
    panel.hidden=false;
    if(report.session_id!==sessionId){
      sessionId=report.session_id;
      retryStatus=null;
      activeQuestion=null;
      originalReport=report;
      showMenu();
    }
  }
  window.MahTrainRetry={render};
})();
