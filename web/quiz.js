"use strict";
/* Standalone mode x difficulty quizzes. Answers and random seeds remain on
   the Python server until the learner submits an answer. */
(function(){
  const $=id=>document.getElementById(id);
  const TITLES={
    one_shanten:"一向听何切",tenpai_discard:"听牌何切",
    pure_suit_waits:"清一色选听口",pure_suit_discard:"清一色何切 / 已胡",
  };
  const LEVELS={basic:"基础",intermediate:"进阶",challenge:"挑战"};
  let token=null,question=null,selection=new Set(),submitted=false,busy=false;
  const name=t=>t==="win"?"胡牌":window.MahTrainUI.tileName(t);
  function el(tag,css,text){
    const e=document.createElement(tag);
    if(css)e.className=css;
    if(text!==undefined)e.textContent=String(text);
    return e;
  }
  function button(text,css,onClick){
    const b=el("button",css,text);
    b.type="button";b.addEventListener("click",onClick);return b;
  }
  async function request(action,payload){
    const response=await fetch("/api/action",{
      method:"POST",headers:{"Content-Type":"application/json","X-MahTrain":"1"},
      body:JSON.stringify({action,...payload}),
    });
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||"题目服务暂不可用");
    return data;
  }
  function showError(text){
    const root=$("quiz-feedback");
    root.replaceChildren(el("p","review-attention",text));
  }
  async function create(){
    if(busy)return;
    busy=true;
    try{
      const data=await request("quiz_new",{
        mode:$("quiz-mode").value,difficulty:$("quiz-level").value,
      });
      token=data.quiz_token;question=data.question;selection.clear();
      submitted=false;renderQuestion();
      $("quiz-feedback").replaceChildren(el("p","review-intro","请选择答案；提交前不会显示标准答案。"));
    }catch(err){showError(err.message);}
    finally{busy=false;}
  }
  function renderQuestion(){
    if(!question)return;
    const root=$("quiz-question");
    root.replaceChildren();
    root.append(el("p","quiz-meta",TITLES[question.mode]+" · "+
      LEVELS[question.difficulty]+" · 定缺 "+({m:"万",s:"条",p:"筒"}[question.missing_suit])));
    root.append(el("p","retry-label","手牌（万→条→筒，组内1→9）"));
    const hand=el("div","retry-hand");
    question.concealed.forEach(tile=>hand.append(window.MahTrainUI.tileElement(tile)));
    root.append(hand);
    const multiple=question.answer_type==="tile_set";
    root.append(el("p","review-intro",multiple
      ?"请点击全部能胡的牌种，可多选；再次点击取消选择。"
      :"请选择一种切牌；若已经胡牌，可以选择「确认胡牌」。"));
    const actions=el("div","quiz-options");
    for(const tile of question.choices){
      const b=tile==="win"
        ?button("确认胡牌","primary win-option",()=>pick(tile))
        :window.MahTrainUI.tileElement(tile,{
          selectable:!submitted,onClick:()=>pick(tile),
        });
      b.classList.add("quiz-option");
      if(selection.has(tile))b.classList.add("chosen");
      b.setAttribute("aria-pressed",String(selection.has(tile)));
      b.disabled=submitted;
      actions.append(b);
    }
    root.append(actions);
    const footer=el("div","retry-controls");
    footer.append(button("提交本题答案","primary",submit));
    footer.append(button("重新出一题","review-control",create));
    root.append(footer);
    footer.firstChild.disabled=submitted || (!selection.size && !multiple);
  }
  function pick(tile){
    if(submitted||!question)return;
    if(question.answer_type==="tile_set"){
      if(selection.has(tile))selection.delete(tile);
      else selection.add(tile);
    }else{
      selection.clear();
      selection.add(tile);
    }
    renderQuestion();
  }
  function summarize(result){
    const root=$("quiz-feedback");root.replaceChildren();
    root.append(el("h4","",result.correct?"本题回答正确":"本题仍有提升空间"));
    root.append(el("p","review-intro",result.reason));
    if(question.answer_type==="tile_set"){
      root.append(el("p","review-detail-line",
        "正确听口："+result.correct_tiles.map(name).join("、")));
      root.append(el("p","review-detail-line",
        "遗漏："+(result.missed_tiles.map(name).join("、")||"无")+"；误选："+
        (result.extra_tiles.map(name).join("、")||"无")));
      root.append(el("p","review-detail-line",
        "剩余有效张数："+result.effective_draws.effective_tile_count+"张"));
    }else{
      root.append(el("p","review-detail-line",
        "最优动作："+result.best_actions.map(name).join("、")));
      if(result.selected_candidate){
        root.append(el("p","review-detail-line",
          "所选切后向听："+result.selected_candidate.shanten+
          "；有效进张："+result.selected_candidate.effective_tile_count+"张"));
      }
    }
    if(result.construction_family){
      const family={
        sequence_melds:"顺子组合",seven_pairs:"七对听牌",
        seven_pairs_race:"七对竞争",adjacent_taatsu:"顺子+相邻搭子",
        mixed_melds:"顺子/刻子组合",meld_and_isolates:"面子与孤张",
      };
      root.append(el("p","review-footnote",
        "生成牌形："+(family[result.construction_family]||result.construction_family)+
        "。牌型只是构造来源，最优答案仍由完整牌效算法计算。"));
    }
  }
  async function submit(){
    if(busy||!question||submitted)return;
    const multiple=question.answer_type==="tile_set";
    if(!multiple&&!selection.size){
      showError("请先选择一张切牌或胡牌。");return;
    }
    busy=true;
    try{
      const answer=multiple?[...selection]:[...selection][0];
      const result=(await request("quiz_answer",{
        quiz_token:token,selection:answer,
      })).result;
      submitted=true;renderQuestion();summarize(result);
      window.MahTrainSound?.play(result.correct?"win":"discard");
    }catch(err){showError(err.message);}
    finally{busy=false;}
  }
  function init(){
    $("quiz-new").addEventListener("click",create);
    $("quiz-mode").addEventListener("change",()=>{
      question=null;token=null;selection.clear();submitted=false;
      $("quiz-question").replaceChildren();
      $("quiz-feedback").replaceChildren();
    });
    $("quiz-level").addEventListener("change",()=>{
      question=null;token=null;selection.clear();submitted=false;
      $("quiz-question").replaceChildren();
      $("quiz-feedback").replaceChildren();
    });
  }
  window.MahTrainQuiz={init};
})();
