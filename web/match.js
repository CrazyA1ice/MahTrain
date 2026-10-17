"use strict";
/* M3.4 LOCAL trial: seat zero versus three information-limited heuristic
   opponents (not machine-learned). Draw-end payments unposted.
*/
(function(){
  const $=id=>document.getElementById(id);
  const names={m:"万",s:"条",p:"筒"};
  const directions={clockwise:"顺时针",counterclockwise:"逆时针",opposite:"对家"};
  const actionNames={hu:"胡这张",peng:"碰",ming_gang:"明杠",pass:"过",an_gang:"暗杠",bu_gang:"补杠"};
  let token=null,state=null,choice=new Set(),busy=false;
  let playback=null,liveBoard=null;
  const publicBoard=()=>liveBoard||state;
  const tileName=t=>window.MahTrainUI.tileName(t);
  function el(tag,css,label){
    const v=document.createElement(tag);
    if(css)v.className=css;
    if(label!==undefined)v.textContent=String(label);
    return v;
  }
  function button(label,kind,fn){
    const b=el("button",kind,label);b.type="button";b.addEventListener("click",fn);
    return b;
  }
  function card(tile,onclick,marked){
    const b=window.MahTrainUI.tileElement(tile,{
      selectable:typeof onclick==="function",onClick:onclick,
    });
    if(marked)b.classList.add("match-selected");
    return b;
  }
  async function action(name,fields={}){
    if(busy)return;
    busy=true;
    $("match-error").textContent="";
    try{
      const response=await fetch("/api/action",{
        method:"POST",
        headers:{"Content-Type":"application/json","X-MahTrain":"1"},
        body:JSON.stringify({action:name,match_token:token,...fields}),
      });
      const data=await response.json();
      if(!response.ok)throw new Error(data.error||"对局操作失败");
      // Replay only NEW public events from this response, never seek a wall
      // or a concealed AI draw. The trusted final state is applied once at
      // completion; intermediate historic hand/wall layouts are NOT forged.
      if(name!=="match_new" && state && playback &&
          Number($("match-playback-speed").value)!==0){
        const before=state.events?.length||0;
        const newEvents=data.match.events||[];
        if(newEvents.length>=before){
          const recorded=data.match.public_steps;
          const result=Array.isArray(recorded)
            ?window.MahTrainPlayback.normalizeSteps(recorded,80,state)
            :window.MahTrainPlayback.normalize(newEvents.slice(before));
          const fullCount=result.frames.length;
          const focusOnly=$("match-playback-focus").checked===true;
          const frames=focusOnly
            ?window.MahTrainPlayback.highlightFrames(result.frames)
            :result.frames;
          if(frames.length){
            $("match-playback").hidden=false;
            $("match-playback-note").textContent=
              (Array.isArray(recorded)
                ?"逐动作展示真实公开牌山、牌河、副露与各家牌背数；本人的暗手在结束后同步。"
                :"按公开事件顺序播放；完整牌桌在播放结束时同步。")+
              (result.omitted?" 事件较多，已略过前"+result.omitted+"项。":"")+
              (focusOnly?" 精简模式：本次"+fullCount+
                "个动作快照中播放"+frames.length+"个重点/最终画面。":"");
            await new Promise(resolve=>playback.start(frames,resolve));
          }
        }
      }
      if(name==="match_new" && playback){
        playback.cancel();
        $("match-playback").hidden=true;
        $("match-motion").hidden=true;
      }
      liveBoard=null;
      token=data.match_token;state=data.match;choice.clear();render();
    }catch(err){
      liveBoard=null;
      if(state)renderBoard();
      $("match-error").textContent=err.message||String(err);
    }finally{busy=false;}
  }
  function toggle(i){
    if(busy||state.phase!=="exchange_select")return;
    if(choice.has(i)){choice.delete(i);render();return;}
    if(choice.size===3){
      $("match-error").textContent="最多选3张，请先取消一张。";return;
    }
    if(choice.size && [...choice].some(j=>state.hand[j][0]!==state.hand[i][0])){
      $("match-error").textContent="换三张必须是同一花色。";return;
    }
    choice.add(i);render();
  }
  // M3.14: the API already gives seat-zero private hand and four public
  // seats. Never request, infer, or draw an opponent's concealed tile faces.
  const seats=[
    {id:0,label:"自己"}, {id:1,label:"下家"},
    {id:2,label:"对家"}, {id:3,label:"上家"},
  ];
  function tileBack(){
    const back=el("span","match-tile-back");
    back.setAttribute("aria-hidden","true");
    return back;
  }
  function showPublicMotion(frame,step,total){
    if(frame.board){
      liveBoard=frame.board;
      renderBoard();
    }
    const root=$("match-motion"),target=$("match-motion-card");
    root.hidden=false;
    root.classList.toggle("is-winning-motion",!!frame.isWin);
    root.classList.toggle("is-kong-motion",!!frame.isKong);
    root.classList.toggle("is-peng-motion",!!frame.isPeng);
    $("match-motion-text").textContent=frame.label;
    const chain=$("match-motion-chain");
    chain.replaceChildren();
    if(frame.chain?.length>1){
      // This is ONE completed rules action. Multiple labels are presentation
      // stages, not invented intermediate game states.
      for(const [i,label] of frame.chain.entries()){
        if(i)chain.append(el("span","match-motion-arrow","→"));
        chain.append(el("span","match-motion-chip",label));
      }
    }
    const delta=$("match-motion-delta");
    const change=frame.changes;
    const notes=[];
    if(change){
      if(change.wall)notes.push("牌山 "+(change.wall>0?"+":"")+change.wall);
      for(let i=1;i<4;i++){
        if(change.backs[i])notes.push(i+"号牌背 "+
          (change.backs[i]>0?"+":"")+change.backs[i]);
        if(change.melds[i])notes.push(i+"号副露 "+
          (change.melds[i]>0?"+":"")+change.melds[i]+"组");
      }
      if(change.rivers>0)notes.push("牌河 +"+change.rivers);
    }
    delta.textContent=notes.join(" · ");
    delta.hidden=notes.length===0;
    target.replaceChildren();
    // Only publicly revealed physical tile kinds are depicted face-up.
    if(frame.publicTile){
      target.append(card(frame.publicTile,null,false));
    }else if(frame.concealed){
      target.append(tileBack());
    }
    for(const seat of seats){
      $("match-seat-"+seat.id).classList.toggle(
        "is-replay-acting",seat.id===frame.seat||
          frame.winSeats.includes(seat.id));
    }
  }
  function onPlaybackStatus(status){
    $("match-playback-progress").textContent=
      (status.playing?status.index+1:status.total)+
      " / "+status.total;
    $("match-playback-status").textContent=
      !status.playing?"播放完毕":status.paused?"已暂停":"播放中";
    const pause=$("match-playback-pause");
    pause.textContent=status.paused?"继续播放":"暂停";
    pause.disabled=!status.playing;
    $("match-playback-step").disabled=!status.playing||!status.paused;
    $("match-playback-skip").disabled=!status.playing;
  }
  function onPlaybackDone(){
    $("match-motion").hidden=true;
    $("match-playback").hidden=true;
    for(const seat of seats)$("match-seat-"+seat.id)
      .classList.toggle("is-replay-acting",false);
  }
  function renderMelds(root,groups,showOwn){
    root.replaceChildren();
    if(!groups?.length){
      root.append(el("span","match-empty-melds","暂无公开碰杠"));
      return;
    }
    for(const meld of groups){
      const item=el("div","match-seat-meld");
      const label=actionNames[meld.type]||"公开副露";
      const kind=["peng","ming_gang","an_gang","bu_gang"].includes(meld.type)
        ?meld.type:"other";
      item.classList.add("match-seat-meld--"+kind);
      item.setAttribute("aria-label",label+
        (kind==="an_gang"&&!showOwn?"，牌种保密":"，"+
          (kind==="peng"?"3":"4")+"张牌"));
      item.append(el("small","",label));
      const tiles=el("div","match-meld-tiles");
      for(let n=0;n<(meld.type==="peng"?3:4);n++){
        // Public an-gang is intentionally redacted by public_state().
        if(meld.tile===null || meld.tile===undefined){
          tiles.append(tileBack());
        }else{
          tiles.append(card(meld.tile,null,false));
        }
      }
      item.append(tiles);
      root.append(item);
    }
  }
  function renderSeat(seat){
    const view=publicBoard();
    const root=$("match-seat-"+seat);
    root.classList.toggle("is-active",
      view.turn===seat && !view.won[seat] &&
      ["dealer_discard","await_discard"].includes(view.phase));
    root.classList.toggle("is-won",!!view.won[seat]);
    if(seat===0){
      const missing=state.missing_suits?.[0];
      root.classList.toggle("is-public-replay",!!liveBoard);
      $("match-self-status").textContent=liveBoard
        ?"公开状态：手牌"+view.hand_counts[0]+"张 · 手牌牌面在播放结束后同步"
        :(state.won[0]?"已胡 · ":"")+
          (missing?"定缺"+names[missing]+" · ":"定缺待公开 · ")+
          "庄家"+state.dealer+"号 · 当前手牌"+state.hand.length+"张";
      renderMelds($("match-self-melds"),
        liveBoard?view.melds[0]:state.own_melds,!liveBoard);
      const ownScore=$("match-own-score");
      ownScore.hidden=!settlementAvailable();
      if(!ownScore.hidden)ownScore.textContent=seatScoreText(0);
      return;
    }
    root.replaceChildren();
    const ai=state.ai_opponents?.find(x=>x.seat===seat);
    const levels={basic:"入门",advanced:"进阶",challenge:"挑战"};
    root.append(el("strong","match-seat-name",
      seat+"号 · "+seats[seat].label+(ai?" · "+(levels[ai.difficulty]||ai.difficulty):"")));
    const missing=state.missing_suits?.[seat];
    root.append(el("div","match-seat-status",
      (view.won[seat]?"已胡 · ":"")+
      (missing?"定缺"+names[missing]+" · ":"定缺待公开 · ")+
      "暗手"+view.hand_counts[seat]+"张"));
    const backs=el("div","match-seat-backs");
    backs.setAttribute("aria-label","暗手"+view.hand_counts[seat]+"张，牌面不可见");
    for(let n=0;n<view.hand_counts[seat];n++)backs.append(tileBack());
    root.append(backs);
    const melds=el("div","match-seat-melds");
    renderMelds(melds,view.melds[seat],false);
    root.append(melds);
    if(settlementAvailable()){
      root.append(el("div","match-seat-score",seatScoreText(seat)));
    }
  }
  function renderRiver(seat){
    const view=publicBoard();
    const root=$("match-river-"+seat);
    root.replaceChildren();
    root.append(el("strong","match-river-title",seats[seat].label+"牌河"));
    const tiles=el("div","match-river-tiles");
    const entries=view.discards.map((entry,index)=>({...entry,order:index}))
      .filter(entry=>entry.seat===seat);
    if(!entries.length){
      tiles.append(el("span","match-river-empty","尚无弃牌"));
    }
    for(const entry of entries){
      const cell=el("div","match-river-cell");
      const claimed=entry.claimed_by!==undefined;
      if(claimed){
        // A claimed discard is physically held in another player's meld,
        // never show a duplicate face still lying in the river.
        cell.classList.add("is-claimed");
        cell.append(el("span","match-river-claimed","已取走"));
        cell.title="本张弃牌已被碰或杠取走";
      }else{
        cell.append(card(entry.tile,null,false));
        cell.title=tileName(entry.tile);
      }
      if(entry.won_by)cell.classList.add("is-winning-discard");
      // Read the authoritative public classification; never infer it from
      // another player's private latest-drawn tile.
      if(entry.discard_kind==="tsumogiri" || entry.discard_kind==="tedashi"){
        const drawCut=entry.discard_kind==="tsumogiri";
        cell.classList.add(drawCut?"is-tsumogiri":"is-tedashi");
        cell.append(el("span","match-discard-kind",drawCut?"摸切":"手切"));
        cell.title+=(drawCut?" · 摸切":" · 手切");
      }
      if(entry.order===view.discards.length-1){
        cell.classList.add("is-latest");
      }
      tiles.append(cell);
    }
    root.append(tiles);
  }
  function renderReadyHint(){
    const root=$("match-ready-hint");
    root.replaceChildren();
    const waits=state.ready_waits||[];
    if(waits.length){
      root.append(el("strong","","已听牌 · 听 "+waits.length+" 种："));
      for(const tile of waits)root.append(card(tile,null,false));
      root.append(el("span","match-ready-note","结构听口，并非牌山中剩余数量"));
      return;
    }
    const cuts=state.ready_after_discards||[];
    if(cuts.length){
      root.append(el("strong","","听牌提示："));
      for(const item of cuts){
        const group=el("span","match-ready-option");
        group.append(el("span","","切"));
        group.append(card(item.discard,null,false));
        group.append(el("span","","听 "+item.waits.map(tileName).join("、")));
        root.append(group);
      }
    }
  }
  function renderWinAlert(){
    const banner=$("match-win-alert");
    const wins=state.winners||[];
    const aiWins=wins.filter(w=>w.seat!==0);
    banner.hidden=!aiWins.length;
    banner.replaceChildren();
    if(!aiWins.length)return;
    const latest=aiWins.slice(-3);
    const kind={self_draw:"自摸",ron:"点炮胡",rob_kong:"抢杠胡"};
    banner.append(el("strong","","AI 胡牌！"));
    banner.append(el("span","",latest.map(w=>
      w.seat+"号AI "+(kind[w.kind]||"胡牌")+
      (w.kind==="ron"||w.kind==="rob_kong"?" · 来自"+w.source+"号":"")
    ).join(" ｜ ")));
  }
  function settlementAvailable(){
    return !liveBoard && Array.isArray(state?.win_ledger?.wins) &&
      state.win_ledger.wins.length>0 &&
      Array.isArray(state.win_ledger.balances);
  }
  function signedScore(value){
    return (value>=0?"+":"")+value;
  }
  function seatScoreText(seat){
    const amount=state.win_ledger.balances[seat];
    return "胡牌积分 "+signedScore(amount);
  }
  function renderTableSettlement(){
    const panel=$("match-table-settlement");
    const visible=settlementAvailable();
    panel.hidden=!visible;
    if(!visible)return;
    const ledger=state.win_ledger;
    const terminal=state.phase==="finished"||state.phase==="wall_exhausted";
    $("match-table-settlement-title").textContent="本局胡牌结算 · 已入账";
    $("match-table-round-phase").textContent=terminal?"摸切已结束":"对局进行中";
    const scores=$("match-table-scores");
    scores.replaceChildren();
    for(const seat of seats){
      const amount=ledger.balances[seat.id];
      const cell=el("div","match-table-score");
      cell.classList.add(amount>0?"is-credit":amount<0?"is-debit":"is-zero");
      cell.append(el("span","",seat.id+"号 · "+seat.label+
        (state.won[seat.id]?" · 已胡":"")));
      cell.append(el("strong","",signedScore(amount)));
      scores.append(cell);
    }
    const wins=$("match-table-wins");
    wins.replaceChildren();
    for(const win of ledger.wins.slice(-2)){
      const mode={self_draw:"自摸",ron:"点炮胡",rob_kong:"抢杠胡"}[win.kind]||
        "胡牌";
      const row=el("div","match-table-win-row");
      row.append(el("strong","",win.winner+"号"+mode+
        " · "+win.main_pattern));
      row.append(el("span","",
        "实收 "+signedScore(win.total_received)+
        " · "+win.effective_fan+"番 · 付款 "+
        win.payers.map(x=>x+"号").join("、")));
      wins.append(row);
    }
    const kongEnabled=state.kong_ledger?.base!=null;
    $("match-table-score-note").textContent=
      "以上仅为胡牌已入账积分"+(kongEnabled?
        "；独立杠钱另以试验积分记账，不计入此栏":"，不含独立杠钱")+
      "；流局查花猪、查大叫仍未正式入账。";
  }
  function renderWall(){
    const remaining=publicBoard().wall_count;
    $("match-wall-count").textContent=String(remaining);
    $("match-wall").classList.toggle("is-exhausted",remaining===0);
  }
  function renderBoard(){
    renderWall();
    for(const seat of seats){
      renderSeat(seat.id);
      renderRiver(seat.id);
    }
    renderTableSettlement();
  }

  function render(){
    if(!state)return;
    $("match-stage").hidden=false;
    const phaseLabels={
      exchange_select:"第一步：看牌后选择3张同花色牌换出",
      missing_select:"第二步：看交换后的手牌，再盖牌定缺",
      dealer_discard:"庄家14张，直接切牌或判断自摸",
      await_discard:"你的回合：切牌、胡牌或选择杠",
      claim_window:"别人打出一张牌：请确认碰、明杠或胡牌",
      rob_kong_window:"别人补杠：判断是否抢杠胡",
      finished:"已有三家胡牌，摸切结束（胡牌已入账，其他项目待定）",
      wall_exhausted:"牌墙耗尽，待实现查花猪与查大叫",
    };
    const phase=state.phase;
    $("match-title").textContent=phaseLabels[phase]||phase;
    $("match-status").textContent=
      "你是0号位 · 庄家"+state.dealer+"号 · "+directions[state.exchange_direction]+
      "换牌 · 剩余"+state.wall_count+"张 · 当前行动："+(state.turn??"—");
    const hand=$("match-hand");hand.replaceChildren();
    // Exactly one equal-valued copy is the newly drawn physical tile.
    // Other equal copies remain selectable as an explicit HAND-cut.
    const drawn=(state.turn===0 &&
      (phase==="dealer_discard"||phase==="await_discard"))
      ?state.drawn_tile:null;
    let drawnIndex=drawn===null?-1:state.hand.lastIndexOf(drawn);
    state.hand.forEach((tile,i)=>{
      if(i===drawnIndex)return;
      let onclick=null;
      if(phase==="exchange_select")onclick=()=>toggle(i);
      if((phase==="dealer_discard"||phase==="await_discard")&&state.turn===0)
        onclick=()=>action("match_discard",{tile,from_draw:false});
      hand.append(card(tile,onclick,choice.has(i)));
    });
    if(drawnIndex>=0){
      const last=card(drawn,()=>action("match_discard",{
        tile:drawn,from_draw:true,
      }),false);
      last.classList.add("match-new-draw");
      last.title="刚摸到："+tileName(drawn)+" · 点击摸切";
      last.setAttribute("aria-label","刚摸到"+tileName(drawn)+"，点击摸切");
      hand.append(last);
    }
    renderBoard();
    renderReadyHint();
    renderWinAlert();
    const controls=$("match-controls");controls.replaceChildren();
    if(phase==="exchange_select"){
      controls.append(el("p","review-intro","已选择"+choice.size+
        "/3张相同花色牌，等待四家确认后统一换牌。"));
      const confirm=button("确认换出三张","primary",()=>action("match_exchange",{
        tiles:[...choice].sort((a,b)=>a-b).map(i=>state.hand[i]),
      }));
      confirm.disabled=choice.size!==3;
      controls.append(confirm);
    }else if(phase==="missing_select"){
      const counts={m:0,s:0,p:0};state.hand.forEach(t=>counts[t[0]]++);
      controls.append(el("p","review-intro",state.tianque?
        "换牌后符合天缺：可以直接定缺手中没有的一门。":
        "已完成四家换三张，请在看牌后选择缺门。"));
      for(const suit of ["m","s","p"]){
        controls.append(button("定缺"+names[suit]+"（现有"+counts[suit]+"张）",
          "review-control",()=>action("match_missing",{suit})));
      }
    }else if(phase==="claim_window"||phase==="rob_kong_window"){
      const options=phase==="claim_window"?state.claim_options:state.rob_options;
      const target=phase==="claim_window"?state.pending_discard:state.pending_rob_kong;
      controls.append(el("p","review-intro",
        "当前目标："+(target?tileName(target.tile):"—")+
        "。必须确认响应，胡牌优先于杠、碰；系统会等待所有活跃玩家提交。"));
      for(const option of options){
        controls.append(button(actionNames[option]||option,
          option==="hu"?"primary":"review-control",
          ()=>action(phase==="claim_window"?"match_claim":"match_rob",
            {choice:option})));
      }
    }else if(phase==="dealer_discard"||phase==="await_discard"){
      if(state.can_self_draw_win){
        controls.append(button("确认自摸胡牌","primary",
          ()=>action("match_win")));
      }
      for(const kong of state.kong_options||[]){
        controls.append(button(actionNames[kong.type]+" "+tileName(kong.tile),
          "review-control",()=>{
            if(confirm("确认"+actionNames[kong.type]+tileName(kong.tile)+
                "？合法杠后从牌墙尾部补牌。")){
              action("match_kong",{kind:kong.type,tile:kong.tile});
            }
          }));
      }
      controls.append(el("p","review-intro",
        "请点击自己的麻将切牌。其他三家由各自策略AI操作，合法胡牌将即时计入部分积分。"));
    }else{
      controls.append(el("p","review-intro",
        "本局摸切已结束。胡牌部分已入账，杠钱仅按可选模拟底分计入，流局赔付仍需确认。可以重新开一局。"));
    }
    const publicInfo=$("match-public");publicInfo.replaceChildren();
    if(state.missing_suits){
      publicInfo.append(el("p","review-intro",
        "四家定缺："+state.missing_suits.map((s,i)=>i+"号缺"+names[s]).join(" · ")));
    }
    if(state.ai_opponents){
      const levels={basic:"入门",advanced:"进阶",challenge:"挑战"};
      const ai=el("section","match-ai-info");
      ai.append(el("strong","","本局三名策略AI（仅自家暗牌 + 公开信息）"));
      for(const agent of state.ai_opponents){
        ai.append(el("p","review-footnote",
          agent.seat+"号 · "+(levels[agent.difficulty]||agent.difficulty)+
          "："+agent.description));
      }
      publicInfo.append(ai);
    }
    publicInfo.append(el("p","review-intro",
      "各家暗手牌张数："+state.hand_counts.map((v,i)=>
        i+"号"+v+"张"+(state.won[i]?"（已胡）":"")).join("，")));
    const tian=state.tian_ting;
    if(tian){
      const status=tian.reason==="not_initialized"?"尚未定缺，等待判定":
        tian.eligible?"天听资格有效":
        ({dealer_not_eligible:"庄家不具备天听资格",
          not_initially_listening:"起手未听牌",
          peng_called:"碰牌后天听资格取消",
          waiting_set_changed:"摸切后听口变化，天听资格取消"}[tian.reason]||"天听资格无效");
      publicInfo.append(el("p","match-tian-status",
        "本人天听："+status+" · 稳定听口检查"+
        (tian.checkpoints||0)+"次"+
        (tian.initial_waits.length?" · 原始听口："+tian.initial_waits.map(tileName).join("、"):"")));
    }
    const ledger=state.win_ledger;
    if(ledger){
      const score=el("section","match-ledger");
      score.append(el("h4","","四家胡牌结算账本（不含杠钱）"));
      score.append(el("p","review-footnote",
        "房间系数"+ledger.room_coefficient+
        " · 最终番数封顶"+ledger.fan_cap+
        " · 零和校验："+(ledger.zero_sum?"通过":"异常")));
      const balances=el("div","match-balances");
      ledger.balances.forEach((v,i)=>{
        const item=el("div","match-balance");
        item.append(el("span","",i+"号"+(state.won[i]?" · 已胡":"")));
        item.append(el("strong",v>=0?"match-positive":"match-negative",
          (v>=0?"+":"")+v));
        balances.append(item);
      });
      score.append(balances);
      if(ledger.wins.length){
        const details=el("div","match-score-rows");
        for(const win of ledger.wins){
          const row=el("div","match-score-entry");
          const kind={self_draw:"自摸",ron:"点炮胡",rob_kong:"抢杠胡"}[win.kind]||win.kind;
          row.append(el("strong","",win.winner+"号"+kind+
            " · "+win.main_pattern));
          row.append(el("span","",
            "原始"+win.raw_fan+"番 → 封顶"+
            win.effective_fan+"番 / ×"+win.multiplier));
          row.append(el("span","",
            "付款："+win.payers.map(x=>x+"号").join("、")+
            "各付"+win.amount_per_payer+"；赢家共得"+win.total_received));
          row.append(el("small","","附加番："+(
            Object.entries(win.bonuses).map(([key,v])=>key+" +"+v).join("、")||"无")));
          details.append(row);
        }
        score.append(details);
      }else{
        score.append(el("p","review-intro","尚未发生合法胡牌，因此四家胡牌余额均为0。"));
      }
      if(state.pending_kong_payments?.length){
        const unsettled=state.pending_kong_payments.filter(
          x=>x.status==="unpriced").length;
        const voided=state.pending_kong_payments.filter(
          x=>x.status==="voided").length;
        score.append(el("p","match-unpriced",
          "杠钱尚未入账："+unsettled+"笔待定，"+
          voided+"笔杠上炮作废（底分和撤销细则待确认，未产生虚构退款）。"));
      }
      score.append(el("p","review-footnote",
        "胡牌零和流水已入账；独立杠钱只有明确勾选后才模拟入账，流局赔付只提供预览。"));
      publicInfo.append(score);
    }
    const kongLedger=state.kong_ledger;
    if(kongLedger){
      const k=el("section","match-kong-ledger");
      k.append(el("h4","","独立杠钱模拟与冲销流水"));
      k.append(el("p","review-footnote",kongLedger.base===null
        ?"未设置杠钱底分：不自动计价，所有杠钱为待定。"
        :"已启用单独杠钱底分"+kongLedger.base+
          "（仅为试验积分，不代表已确定的正式房间规则）。"));
      k.append(el("p","review-intro",
        "四家杠钱余额："+kongLedger.balances.map(
          (n,i)=>i+"号"+(n>=0?"+":"")+n).join(" · ")));
      if(kongLedger.events.length){
        for(const item of kongLedger.events){
          const kind={ming_gang:"明杠",an_gang:"暗杠",bu_gang:"补杠"}[item.type];
          const stateLabel={posted:"已模拟入账",unpriced:"未计价",
            voided:"已作废并冲销"}[item.status];
          k.append(el("p","review-footnote",
            "第"+item.id+"笔 · "+item.seat+"号"+kind+
            " · "+stateLabel+(item.amount_per_payer!==null
              ?" · 每付款者"+item.amount_per_payer+"积分":"")));
        }
      }
      if(kongLedger.entries.length){
        const details=el("details","match-transfers");
        details.append(el("summary","","查看杠钱原始与反向流水（"+
          kongLedger.entries.length+"条）"));
        for(const item of kongLedger.entries){
          details.append(el("p","review-footnote",
            "第"+item.kong_id+"笔 · "+(item.kind==="reversal"?"冲销":"入账")+
            "："+item.payer+"号付"+item.recipient+"号 "+
            item.amount));
        }
        k.append(details);
      }
      const net=state.combined_balances||[0,0,0,0];
      k.append(el("p","match-net",
        "胡牌 + 模拟杠钱余额："+net.map((n,i)=>
          i+"号"+(n>=0?"+":"")+n).join(" · ")));
      publicInfo.append(k);
    }
    const review=state.exhaustive_review;
    if(review?.triggered){
      const sec=el("section","match-exhaustive-review");
      sec.append(el("h4","","流局查花猪 / 查大叫：待确认结算预览"));
      sec.append(el("p","review-intro",
        "本局牌墙耗尽，仍有"+review.participating_active_seats.length+
        "位活跃玩家。仅按“活跃玩家之间付款”方案试算，"+
        "已胡玩家是否参与尚未确认；以下金额没有进入实际账本。"));
      const kinds={flower_pig:"花猪",listening:"合法听牌",
        unready:"未听牌",unresolved_exposed_missing:"有缺门公开副露，待核验",
        unresolved_nonstable_hand:"非稳定张数，待核验"};
      for(const item of review.seats){
        sec.append(el("p","review-footnote",
          item.seat+"号："+(kinds[item.classification]||"待核验")+
          (item.max_effective_fan!==null?
            " · 最大可结"+item.max_effective_fan+"番":"")));
      }
      for(const entry of review.proposed_transfers){
        sec.append(el("p","review-footnote",
          (entry.stage==="flower_pig"?"花猪":"查大叫")+
          "（仅试算）："+entry.payer+"号向"+entry.recipient+
          "号付"+entry.amount));
      }
      sec.append(el("p","match-unpriced",
        "流局付款状态：未入账。赔付参与人及缺门副露归属确认后才能正式结算。"));
      publicInfo.append(sec);
    }
    const winners=state.winners;
    if(winners.length)publicInfo.append(el("p","match-win-note",
      "已胡牌："+winners.map(x=>x.seat+"号"+(
        x.kind==="self_draw"?"自摸":x.kind==="rob_kong"?"抢杠胡":"点炮胡")).join(" · ")));
    const log=el("div","match-events");
    log.append(el("strong","","近期公开事件"));
    for(const e of state.events.slice(-8)){
      const type={
        exchange_complete:"四家完成换三张",missing_suits_revealed:"四家同时定缺",
        discard:"出牌",peng:"碰",ming_gang:"明杠",an_gang:"暗杠",
        bu_gang_declared:"补杠待响应",bu_gang:"补杠",
        kong_supplement:"杠后尾部补摸",ron:"点炮胡",multi_ron:"一炮多响",
        rob_kong:"抢杠胡",self_draw_win:"自摸",all_pass:"全体过牌",
      };
      log.append(el("p","review-footnote",
        (type[e.type]||e.type)+
        (e.seat!==undefined?" · 座位"+e.seat:"")+
        (e.tile&&e.type!=="kong_supplement"?" · "+tileName(e.tile):"")));
    }
    publicInfo.append(log);
  }
  function init(){
    playback=window.MahTrainPlayback.createController({
      onFrame:showPublicMotion,onStatus:onPlaybackStatus,
      onDone:onPlaybackDone,
    });
    const speed=$("match-playback-speed");
    playback.setSpeed(Number(speed.value)||450);
    speed.addEventListener("change",()=>{
      const milliseconds=Number(speed.value);
      if(milliseconds===0){playback.skip();return;}
      playback.setSpeed(milliseconds);
    });
    $("match-playback-pause").addEventListener("click",()=>{
      const status=playback.getState();
      if(status.paused)playback.resume();
      else playback.pause();
    });
    $("match-playback-step").addEventListener("click",()=>playback.step());
    $("match-playback-skip").addEventListener("click",()=>playback.skip());
    $("match-enable-kong").addEventListener("change",()=>{
      $("match-kong-base").disabled=!$("match-enable-kong").checked;
    });
    $("match-new").addEventListener("click",()=>{
      const seed=Number($("match-seed").value);
      action("match_new",{seed,
        room_coefficient:Number($("match-coefficient").value),
        fan_cap:Number($("match-fan-cap").value),
        ai_levels:[1,2,3].map(n=>$("match-ai-"+n).value),
        kong_base:$("match-enable-kong").checked
          ?Number($("match-kong-base").value):null,
      });
    });
  }
  window.MahTrainMatch={init};
})();
