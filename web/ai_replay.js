"use strict";
/* M3.7 read-only four-AI replay. No hidden hands or future wall in client. */
(function(){
  const $=id=>document.getElementById(id);
  const LABEL={basic:"入门",advanced:"进阶",challenge:"挑战"};
  const ACTION={
    exchange_three:"密封换出三张",declare_missing:"提交定缺",
    draw:"摸牌（牌种保密）",discard:"出牌",pass:"过",
    peng:"申请碰",ming_gang:"申请明杠",an_gang:"暗杠",
    bu_gang:"补杠",hu:"申请胡牌",self_draw_win:"自摸胡牌",
    response_submitted:"密封响应已提交",response_resolved:"碰杠胡响应裁决完成",
  };
  const SUITS={m:"万",s:"条",p:"筒"};
  let token=null,generation=0,overview=null,current=null,currentIndex=0,stepIndex=0;
  function el(tag,cls,text){
    const node=document.createElement(tag);
    if(cls)node.className=cls;
    if(text!==undefined)node.textContent=String(text);
    return node;
  }
  function tile(value){
    if(value===null){
      return el("span","ai-replay-hidden-tile","暗杠保密");
    }
    const item=window.MahTrainUI.tileElement(value,{selectable:false});
    item.classList.add("ai-replay-tile");
    item.setAttribute("aria-label",window.MahTrainUI.tileName(value));
    return item;
  }
  async function request(action,rest={}){
    const response=await fetch("/api/action",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-MahTrain":"1"},
      body:JSON.stringify({action,replay_token:token,...rest}),
    });
    const result=await response.json();
    if(!response.ok)throw new Error(result.error||"AI复盘请求失败");
    return result;
  }
  function textError(error){
    $("ai-replay-error").textContent=error?.message||String(error);
  }
  function showRate(value){
    return value===null||value===undefined?"暂无切牌":""
      +(value*100).toFixed(1)+"%";
  }
  function makeStat(name,value,ratio){
    const box=el("div","ai-replay-stat");
    box.append(el("span","",name));
    box.append(el("strong","",value));
    if(typeof ratio==="number"){
      const rail=el("div","ai-replay-rail");
      const bar=el("div","ai-replay-bar");
      bar.style.width=(Math.max(0,Math.min(1,ratio))*100)+"%";
      rail.append(bar);box.append(rail);
    }
    return box;
  }
  function renderSummary(){
    const panel=$("ai-replay-summary");
    panel.replaceChildren();
    for(const name of ["basic","advanced","challenge"]){
      const stat=overview.levels[name];
      const card=el("section","ai-replay-score");
      card.append(el("h5","",LABEL[name]+" AI"));
      const stats=el("div","ai-replay-stats");
      stats.append(makeStat("胡牌事件 / 参局",stat.win_events+" / "+stat.seat_exposures));
      stats.append(makeStat("放铳责任",stat.deal_in_events));
      stats.append(makeStat("最低向听切牌率",
        showRate(stat.discard_min_shanten_fraction),
        stat.discard_min_shanten_fraction));
      stats.append(makeStat("局部最优切牌率",
        showRate(stat.discard_local_optimal_fraction),
        stat.discard_local_optimal_fraction));
      stats.append(makeStat("平均向听劣势",
        stat.mean_shanten_regret===null?"—":stat.mean_shanten_regret));
      card.append(stats);panel.append(card);
    }
    const ended=overview.terminal_phase_counts;
    $("ai-replay-terminations").textContent=
      overview.games+"局（完成三家胡牌："+ended.finished+
      "，牌墙耗尽："+ended.wall_exhausted+"）；每个独立种子轮换3局，不能当作独立胜率样本。";
    const selection=$("ai-replay-match");selection.replaceChildren();
    for(const m of overview.matches){
      const label="种子"+m.seed+" · 轮换"+(m.rotation+1)+
        " · 庄"+m.dealer+"号 · "+(m.terminal_phase==="finished"?
          "三家已胡":"牌墙耗尽");
      const option=el("option","",label);option.value=String(m.index);
      selection.append(option);
    }
    $("ai-replay-results").hidden=false;
  }
  function stepTitle(frame,n,total){
    const action=frame.action,board=frame.board;
    const actionText=ACTION[action.action]||action.action;
    const seat=action.seat;
    let suffix="";
    if(action.tile)suffix=" · "+window.MahTrainUI.tileName(action.tile);
    if(action.suit)suffix=" · 缺"+SUITS[action.suit];
    if(action.source!==undefined)suffix+=" · 来自"+action.source+"号";
    if(action.action==="an_gang")suffix=" · 牌面保密";
    if(action.resolution){
      const resolved={
        ron:"点炮胡",multi_ron:"一炮多响",peng:"碰",
        ming_gang:"明杠",all_pass:"全体过牌",
        rob_kong:"抢杠胡",bu_gang:"补杠成立",
      };
      suffix+=" · 裁决："+(resolved[action.resolution]||action.resolution);
    }
    $("ai-replay-step-title").textContent=
      "动作 "+(n+1)+"/"+total+"："+
      seat+"号（"+LABEL[current.assignment[seat]]+"）"+actionText+suffix;
    $("ai-replay-step-note").textContent=
      "当前阶段："+board.phase+" · 剩余牌墙 "+board.wall_count+
      " 张 · 下一行动座位："+(board.turn===null?"—":board.turn)+
      " · 只显示该动作结束后的公开牌桌快照；所有选牌/定缺按正式同时揭示时点显示。";
  }
  function renderSeat(board,seat){
    const seatNode=el("div","ai-replay-seat");
    const who=el("div","ai-replay-seat-title");
    who.append(el("strong","",seat+"号 · "+LABEL[current.assignment[seat]]));
    who.append(el("span","",
      "暗手"+board.hand_counts[seat]+"张"+
      (board.won[seat]?" · 已胡":"")+
      (board.missing_suits===null?" · 定缺未公开":
        " · 缺"+SUITS[board.missing_suits[seat]])));
    seatNode.append(who);
    const exposed=el("div","ai-replay-melds");
    for(const meld of board.melds[seat]){
      const group=el("div","ai-replay-meld");
      if(meld.tile===null){
        group.append(el("span","ai-replay-hidden-tile","暗杠4张 · 牌面保密"));
      }else{
        const count=meld.type==="peng"?3:4;
        for(let i=0;i<count;i++)group.append(tile(meld.tile));
      }
      exposed.append(group);
    }
    if(!board.melds[seat].length)exposed.append(
      el("span","ai-replay-empty","暂无公开副露"));
    seatNode.append(el("p","ai-replay-subtitle","副露 / 杠"));
    seatNode.append(exposed);
    const river=el("div","ai-replay-river");
    for(const item of board.discards){
      if(item.seat!==seat)continue;
      const wrap=el("span","ai-replay-river-tile");
      wrap.append(tile(item.tile));
      if(item.claimed_by!==undefined||item.won_by){
        wrap.classList.add("ai-replay-claimed");
        wrap.title=item.won_by?"已被胡牌":"被碰或明杠";
      }
      river.append(wrap);
    }
    if(!river.childNodes.length)river.append(
      el("span","ai-replay-empty","暂未弃牌"));
    seatNode.append(el("p","ai-replay-subtitle","公开牌河"));
    seatNode.append(river);
    return seatNode;
  }
  function renderStep(){
    if(!current)return;
    const steps=current.steps;
    if(!steps.length)return;
    stepIndex=Math.max(0,Math.min(steps.length-1,stepIndex));
    const frame=steps[stepIndex];
    $("ai-replay-step").max=String(steps.length-1);
    $("ai-replay-step").value=String(stepIndex);
    $("ai-replay-prev").disabled=stepIndex===0;
    $("ai-replay-next").disabled=stepIndex===steps.length-1;
    stepTitle(frame,stepIndex,steps.length);
    const board=$("ai-replay-board");board.replaceChildren();
    for(let s=0;s<4;s++)board.append(renderSeat(frame.board,s));
  }
  async function openMatch(index,expected){
    $("ai-replay-detail").hidden=true;
    $("ai-replay-download").disabled=true;
    try{
      const received=await request("ai_replay_match",{match_index:index});
      if(expected!==generation)return;
      current=received.match;currentIndex=index;stepIndex=0;
      renderStep();
      $("ai-replay-detail").hidden=false;
      $("ai-replay-download").disabled=false;
    }catch(e){if(expected===generation)textError(e);}
  }
  async function poll(expected){
    if(expected!==generation)return;
    try{
      const payload=await request("ai_replay_status");
      if(expected!==generation)return;
      const job=payload.replay;
      $("ai-replay-progress").textContent=
        "已计算 "+job.completed_games+"/"+job.total_games+" 局"+
        (job.status==="running"?"；后台运算中…":"");
      if(job.status==="done"){
        overview=job.overview;
        renderSummary();
        $("ai-replay-start").disabled=false;
        await openMatch(0,expected);
      }else if(job.status==="error"){
        $("ai-replay-start").disabled=false;
        textError(new Error(job.error||"复盘运算失败"));
      }else{
        setTimeout(()=>poll(expected),1200);
      }
    }catch(e){
      $("ai-replay-start").disabled=false;
      textError(e);
    }
  }
  async function start(){
    generation+=1;const expected=generation;
    token=null;current=null;overview=null;currentIndex=0;stepIndex=0;
    $("ai-replay-start").disabled=true;
    $("ai-replay-results").hidden=true;
    $("ai-replay-error").textContent="";
    $("ai-replay-progress").textContent="提交后台复盘任务…";
    try{
      const seed=Number($("ai-replay-seed").value);
      const seeds=Number($("ai-replay-seeds").value);
      const response=await request("ai_replay_start",
        {seed_start:seed,seeds});
      if(expected!==generation)return;
      token=response.replay_token;
      await poll(expected);
    }catch(e){
      $("ai-replay-start").disabled=false;
      textError(e);
    }
  }
  function download(){
    if(!current)return;
    // Download contains only the already redacted public replay data.
    const data=JSON.stringify(current,null,2);
    const blob=new Blob([data],{type:"application/json;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;
    a.download="mahtrain-public-replay-"+current.seed+"-"+current.rotation+".json";
    a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1500);
  }
  function init(){
    $("ai-replay-start").addEventListener("click",start);
    $("ai-replay-match").addEventListener("change",e=>{
      if(overview)openMatch(Number(e.target.value),generation);
    });
    $("ai-replay-step").addEventListener("input",e=>{
      stepIndex=Number(e.target.value);renderStep();
    });
    $("ai-replay-prev").addEventListener("click",()=>{
      stepIndex-=1;renderStep();
    });
    $("ai-replay-next").addEventListener("click",()=>{
      stepIndex+=1;renderStep();
    });
    $("ai-replay-download").addEventListener("click",download);
  }
  window.MahTrainAIReplay={init};
})();
