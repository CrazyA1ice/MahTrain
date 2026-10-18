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
  let recoveryRequired=false;
  let pendingDiscard=null,immersive=false,midnightFelt=false;
  // The owner may decline an optional self-kong without losing the right
  // to reopen it. Never reopen the same offer on each render or redraw.
  let dismissedKongKey=null,kongPromptReopened=false;
  let backColor="indigo";
  let playback=null,liveBoard=null,voice=null;
  const MAX_REVIEW_STEPS=512;
  const MATCH_SESSION_KEY="mahtrain.match.session.v1";
  const activeMatch=()=>state&&!["finished","wall_exhausted"].includes(state.phase);
  // sessionStorage is scoped to this tab, not durable disk or synced across
  // devices. Store ONLY the opaque session token, never hands, walls or seed.
  function savedMatchToken(){
    try{return window.sessionStorage?.getItem(MATCH_SESSION_KEY)||null}
    catch(_){return null}
  }
  function saveMatchToken(){
    try{
      if(activeMatch()&&token)window.sessionStorage?.setItem(MATCH_SESSION_KEY,token);
      else window.sessionStorage?.removeItem(MATCH_SESSION_KEY);
    }catch(_){/* private browsing may disable Web Storage */}
  }
  function clearSavedMatchToken(){
    try{window.sessionStorage?.removeItem(MATCH_SESSION_KEY)}
    catch(_){/* no storage access */}
  }
  function syncHomeMatchHint(){
    const label=$("home-match-state");
    if(label)label.textContent=activeMatch()?"已有对局界面，点击继续查看":"";
  }
  // Both reload and an uncertain HTTP mutation reconcile through this
  // read-only endpoint. There is NO automatic re-send of a discard or kong.
  async function fetchMatchSnapshot(stored){
    const response=await fetch("/api/action",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-MahTrain":"1"},
      body:JSON.stringify({action:"match_resume",match_token:stored}),
    });
    const data=await response.json();
    if(!response.ok){
      const error=new Error(data.error||"恢复对局失败");
      error.expired=response.status===400 &&
        /失效|不存在|未初始化/.test(error.message);
      throw error;
    }
    if(data.match_token!==stored||!data.match||data.match.seat!==0)
      throw new Error("服务器返回的对局身份不一致，已停止恢复");
    return data.match;
  }
  function acceptMatchSnapshot(stored,snapshot){
    // A snapshot might be ahead of the browser's last rendered turn.
    // Never replay/speak old events or guess the hidden wall contents.
    playback?.cancel();
    $("match-playback").hidden=true;
    $("match-motion").hidden=true;
    voice?.reset();
    syncVoiceControls();
    token=stored;state=snapshot;
    choice.clear();pendingDiscard=null;
    dismissedKongKey=null;kongPromptReopened=false;
    liveBoard=null;reviewHistory=[];reviewDropped=0;reviewSelected=null;
    const opening=window.MahTrainPlayback.openingFrame(state);
    if(opening)appendReviewFrames([{
      ...opening,type:"state",label:"恢复时的当前公开状态",
    }]);
    recoveryRequired=false;
    saveMatchToken();syncHomeMatchHint();render();
    $("match-resume-tools").hidden=true;
    return state.needs_continue===true;
  }
  function invalidateLostSession(){
    clearSavedMatchToken();
    token=null;state=null;recoveryRequired=false;
    liveBoard=null;reviewHistory=[];reviewDropped=0;reviewSelected=null;
    $("match-stage").hidden=true;
    $("match-resume-tools").hidden=true;
    syncHomeMatchHint();
  }
  async function resumeMatch(){
    if(busy)return;
    const stored=savedMatchToken()||(recoveryRequired?token:null);
    const tools=$("match-resume-tools");
    if(!stored){tools.hidden=true;return}
    busy=true;
    tools.hidden=false;
    $("match-resume-message").textContent="正在恢复上次对局…";
    $("match-resume-retry").disabled=true;
    $("match-error").textContent="";
    let pendingContinue=false;
    try{
      const snapshot=await fetchMatchSnapshot(stored);
      pendingContinue=acceptMatchSnapshot(stored,snapshot);
      $("match-request-status").textContent=
        "已恢复原对局 · 历史语音不会重复播放，复盘从恢复时的公开状态继续";
    }catch(err){
      if(err.expired){
        invalidateLostSession();
        $("match-error").textContent="上次对局会话已失效，请开始新局。";
      }else{
        recoveryRequired=true;
        tools.hidden=false;
        $("match-resume-message").textContent=
          "原对局暂时无法连接，已暂停操作。请检查网络后点击重新连接。";
        $("match-error").textContent=err.message||String(err);
      }
    }finally{
      busy=false;
      $("match-resume-retry").disabled=false;
      if(pendingContinue&&token===stored){
        setTimeout(()=>{
          if(!busy&&!recoveryRequired&&token===stored&&state?.needs_continue===true)
            action("match_continue");
        },0);
      }
    }
  }
  function syncVoiceControls(){
    const on=!!voice?.getEnabled();
    $("match-voice-speed").disabled=!on;
    $("match-voice-repeat").disabled=!voice?.canRepeat();
  }
  let reviewHistory=[],reviewDropped=0,reviewSelected=null;
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
    // An interrupted mutation may ALREADY have run on the server. Until a
    // read-only snapshot resolves that ambiguity, NEVER repeat the action.
    if(busy||(recoveryRequired&&name!=="match_new"))return;
    busy=true;
    $("match-request-status").textContent=
      name==="match_continue"?"正在执行下一步 AI 操作…":"已收到操作，正在计算本步…";
    $("match-error").textContent="";
    const previousEvents=state?.events?.length||0;
    const previousWinCount=state?.win_ledger?.wins?.length||0;
    let announcedByPlayback=false,needsContinue=false;
    const requestToken=token;
    try{
      const response=await fetch("/api/action",{
        method:"POST",
        headers:{"Content-Type":"application/json","X-MahTrain":"1"},
        body:JSON.stringify({action:name,match_token:token,...fields}),
      });
      const data=await response.json();
      if(!response.ok){
        const failure=new Error(data.error||"对局操作失败");
        // Explicit 4xx responses reject the operation. Lost HTTP/5xx
        // responses can be ambiguous: the server may have committed it.
        failure.rejected=response.status>=400&&response.status<500;
        throw failure;
      }
      const service=Number(data.server_elapsed_ms);
      $("match-request-status").textContent=Number.isFinite(service)?
        "服务器本步计算 "+service.toFixed(0)+" ms · 正在同步牌桌与语音":
        "服务器已完成本步 · 正在同步牌桌与语音";
      // Preserve real, sanitized post-action boards EVEN when playback is
      // disabled or focus mode skips animation frames. Never archive a
      // remote private view or reconstruct intermediate wall contents.
      const reviewSteps=name!=="match_new"&&state&&
        Array.isArray(data.match.public_steps)
        ?window.MahTrainPlayback.normalizeHistorySteps(
          data.match.public_steps,state):[];
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
          let frames=focusOnly
            ?window.MahTrainPlayback.highlightFrames(result.frames)
            :result.frames;
          // An interactive AI continuation may include multiple real quiet
          // transitions before ONE announced move. Keep every server board
          // in reviewHistory, but do not make users watch separate 450ms
          // placeholders for hidden draws and non-announced PASS responses.
          let omittedQuiet=0;
          if(name==="match_continue" && frames.length>1){
            const audible=new Set([
              "discard","peng","ming_gang","an_gang","bu_gang_declared",
              "bu_gang","ron","multi_ron","rob_kong","self_draw_win",
            ]);
            const meaningful=frames.filter(frame=>
              frame.actionTypes?.some(type=>audible.has(type)));
            const reduced=meaningful.length?meaningful:[frames.at(-1)];
            omittedQuiet=frames.length-reduced.length;
            frames=reduced;
          }
          if(frames.length){
            announcedByPlayback=true;
            $("match-playback").hidden=false;
            $("match-playback-note").textContent=
              (Array.isArray(recorded)
                ?"逐动作展示真实公开牌山、牌河、副露与各家牌背数；本人的暗手在结束后同步。"
                :"按公开事件顺序播放；完整牌桌在播放结束时同步。")+
              (result.omitted?" 事件较多，已略过前"+result.omitted+"项。":"")+
              (focusOnly?" 精简模式：本次"+fullCount+
                "个动作快照中播放"+frames.length+"个重点/最终画面。":"")+
              (omittedQuiet?" 已合并"+omittedQuiet+
                "个无声中间画面，完整公开快照仍在回顾记录中。":"");
            await new Promise(resolve=>playback.start(frames,resolve));
          }
        }
      }
      if(name==="match_new"){
        voice?.reset();
        syncVoiceControls();
        if(playback){
          playback.cancel();
          $("match-playback").hidden=true;
          $("match-motion").hidden=true;
        }
      }
      // On playback-off games, show the confirmed river / scoreboard first.
      // Speech starts only AFTER the public tile is actually in the DOM;
      // waiting here would produce invisible spoken discards.
      liveBoard=null;
      if(name==="match_new"){
        reviewHistory=[];reviewDropped=0;reviewSelected=null;
        $("match-hand").scrollLeft=0;
        $("match-review-seat-filter").value="all";
        $("match-review-type-filter").value="all";
      }
      token=data.match_token;state=data.match;choice.clear();
      recoveryRequired=false;
      kongPromptReopened=false;
      saveMatchToken();
      syncHomeMatchHint();
      $("match-resume-tools").hidden=true;
      needsContinue=data.match.needs_continue===true;
      pendingDiscard=null;
      if(name==="match_new"){
        const opening=window.MahTrainPlayback.openingFrame(state);
        if(opening)appendReviewFrames([opening]);
      }else if(reviewSteps.length){
        appendReviewFrames(reviewSteps);
      }else{
        // An older server may expose no detailed public_steps. We can
        // preserve its actual FINAL public board only, not invent frames.
        const board=window.MahTrainPlayback.normalizeBoard(state);
        const prior=reviewHistory[reviewHistory.length-1]?.board;
        if(board&&JSON.stringify(board)!==JSON.stringify(prior)){
          appendReviewFrames([{
            ...window.MahTrainPlayback.openingFrame(board),
            type:"state",label:"本次操作最终公开状态",
          }]);
        }
      }
      render();
      $("match-request-status").textContent=Number.isFinite(service)?
        "服务器本步计算 "+service.toFixed(0)+" ms · 牌桌已同步":
        "牌桌已同步";
      if(name==="match_new")renderScoreBursts([]);
      else if(!announcedByPlayback){
        // Disabled/empty replay still exposes ONLY already-booked ledger
        // transfers, never guesses a payment from fan or a private tile.
        const latest=(state.win_ledger?.wins||[]).slice(previousWinCount);
        renderScoreBursts(latest.map(win=>({
          seat:win.winner,amount:win.total_received,
          payers:win.payers,amount_per_payer:win.amount_per_payer,
        })));
      }
      if(name!=="match_new" && !announcedByPlayback && voice){
        const events=(data.match.events||[]).slice(previousEvents);
        // Audio is optional UI feedback. Never delay an already-computed AI turn
        // until browser speechSynthesis fires onend (or its 1.3s hard stop).
        voice.announceEvents(
          window.MahTrainPlayback.normalize(events,96).frames);
        syncVoiceControls();
      }
    }catch(err){
      liveBoard=null;
      if(name!=="match_new"&&requestToken&&!err.rejected){
        recoveryRequired=true;
        const tools=$("match-resume-tools");
        tools.hidden=false;
        $("match-resume-message").textContent=
          "本步响应中断，正在核对服务器真实牌局；请不要重复出牌…";
        try{
          const snapshot=await fetchMatchSnapshot(requestToken);
          needsContinue=acceptMatchSnapshot(requestToken,snapshot);
          $("match-request-status").textContent=
            "网络响应中断 · 已重新同步服务器牌局，本步没有重复提交";
          $("match-error").textContent="";
        }catch(resyncError){
          needsContinue=false;
          if(resyncError.expired){
            invalidateLostSession();
            $("match-error").textContent="对局会话已失效，无法恢复本步，请重新开局。";
          }else{
            recoveryRequired=true;
            tools.hidden=false;
            $("match-resume-message").textContent=
              "本步结果尚未确认，已暂停出牌与碰杠。请重新连接原对局。";
            $("match-error").textContent=resyncError.message||String(resyncError);
          }
        }
      }else{
        if(state)render();
        $("match-error").textContent=err.message||String(err);
        $("match-request-status").textContent="操作未完成，请检查错误提示";
      }
    }finally{
      busy=false;
      // A server-approved next AI transition follows the short visual hold;
      // speech never gates rule execution, but HTTP requests remain serialized.
      if(needsContinue && token && (name==="match_new"||requestToken===token)){
        const expectedToken=token;
        setTimeout(()=>{
          if(!busy&&!recoveryRequired&&token===expectedToken&&state?.needs_continue===true)
            action("match_continue");
        },0);
      }
    }
  }
  // Preserve the user's scroll focus across redraws (including touch
  // confirm/cancel) without changing the order or identity of the tiles.
  function updateHandNavigation(){
    const hand=$("match-hand"), total=hand.children.length;
    const left=Number(hand.scrollLeft)||0;
    const viewport=Number(hand.clientWidth)||0;
    const width=Number(hand.scrollWidth)||0;
    const max=Math.max(0,width-viewport);
    const drawn=total>0&&hand.children[total-1].classList.contains(
      "match-new-draw");
    $("match-hand-position").textContent=total?
      total+"张手牌 · "+(drawn?"最右侧是刚摸的牌":"左右滑动查看"):
      "暂无手牌";
    $("match-hand-prev").disabled=!total||left<=1;
    $("match-hand-next").disabled=!total||(max>0&&left>=max-1);
    $("match-hand-draw").disabled=!drawn;
  }
  function navigateHand(destination){
    const hand=$("match-hand");
    const viewport=Number(hand.clientWidth)||270;
    const max=Math.max(0,(Number(hand.scrollWidth)||0)-
      (Number(hand.clientWidth)||0));
    const current=Number(hand.scrollLeft)||0;
    const step=Math.max(120,Math.round(viewport*.75));
    const next=destination==="draw"?max:
      Math.max(0,Math.min(max,current+(destination==="left"?-step:step)));
    // Set the exact position for immediate button state and keyboard users.
    // No server call, hand mutation or inferred private tile is involved.
    hand.scrollLeft=next;
    updateHandNavigation();
  }
  function chooseDiscard(tile,fromDraw,index=null){
    if(busy||!state||state.turn!==0||
       !["dealer_discard","await_discard"].includes(state.phase))return;
    if(!$("match-confirm-discard").checked){
      action("match_discard",{tile,from_draw:fromDraw});
      return;
    }
    // Keep drawn and hand copies of the same tile distinct: a physical
    // draw-cut must never silently turn into a hand-cut.
    pendingDiscard={tile,fromDraw,index};
    render();
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
  function renderScoreBursts(settlements){
    const root=$("match-score-bursts");
    root.replaceChildren();
    const deltas=[0,0,0,0];
    let hasPayment=false;
    for(const entry of Array.isArray(settlements)?settlements:[]){
      if(!entry||!Number.isInteger(entry.seat)||
          entry.seat<0||entry.seat>3||
          !Number.isSafeInteger(entry.amount)||entry.amount<0)continue;
      // A verified winner credit remains renderable on older public events
      // where the individual payer entries were not yet published.
      deltas[entry.seat]+=entry.amount;
      if(entry.amount>0)hasPayment=true;
      const payers=entry.payers,unit=entry.amount_per_payer;
      if(Array.isArray(payers)&&payers.length>=1&&payers.length<=3&&
          new Set(payers).size===payers.length&&
          payers.every(p=>Number.isInteger(p)&&p>=0&&p<=3&&p!==entry.seat)&&
          Number.isSafeInteger(unit)&&unit>0&&
          Number.isSafeInteger(unit*payers.length)&&
          unit*payers.length===entry.amount){
        for(const payer of payers)deltas[payer]-=unit;
      }
    }
    root.hidden=!hasPayment;
    if(!hasPayment)return;
    for(let seat=0;seat<4;seat++){
      if(!deltas[seat])continue;
      const value=deltas[seat];
      const badge=el("span","match-score-burst "+(value>0?
        "is-credit":"is-debit"),(value>0?"+":"")+value);
      badge.classList.add("match-score-burst--"+seat);
      badge.setAttribute("aria-label",seat+"号本次真实胡牌净变化 "+
        (value>0?"+":"")+value+"积分");
      root.append(badge);
    }
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
    const big=$("match-motion-big-action");
    const actionTypes=frame.actionTypes||[frame.type];
    big.textContent=frame.isWin?
      (actionTypes.includes("multi_ron")?"一炮多响":
        actionTypes.includes("self_draw_win")?"自摸":"胡"):
      frame.isKong?"杠":frame.isPeng?"碰":"";
    big.hidden=!big.textContent;
    renderScoreBursts(frame.settlements||[]);
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
    const payouts=$("match-motion-settlements");
    payouts.replaceChildren();
    const posted=frame.settlements||[];
    for(const [index,entry] of posted.entries()){
      const chip=el("span","match-motion-payment",
        entry.seat+"号胡牌 · 已入账 +"+entry.amount+
        " · "+entry.fan+"番");
      chip.classList.add("match-motion-payment--"+Math.min(index,3));
      payouts.append(chip);
    }
    payouts.hidden=posted.length===0;
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
    // Start speech after rendering, but do not gate playback on its duration.
    voice?.announceFrame(frame);
    syncVoiceControls();
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
    // Do not cancel the last callout just because the short animation ended.
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
      const flipped=kind==="an_gang"&&
        typeof meld.tile==="string"&&/^[msp][1-9]$/.test(meld.tile)&&
        (showOwn||meld.revealed===true);
      item.setAttribute("aria-label",label+
        (kind==="an_gang"?(flipped?"，三张盖牌、一张翻开"+tileName(meld.tile):
          "，历史未公开牌种"):
          "，"+(kind==="peng"?"3":"4")+"张牌"));
      item.append(el("small","",label));
      const tiles=el("div","match-meld-tiles");
      for(let n=0;n<(meld.type==="peng"?3:4);n++){
        if(kind==="an_gang"){
          // Three backs face down. One server-authorized public face is
          // flipped for new kongs; legacy redacted archives stay private.
          if(n===3&&flipped){
            const face=card(meld.tile,null,false);
            face.classList.add("match-kong-revealed");
            tiles.append(face);
          }else tiles.append(tileBack());
        }else if(meld.tile===null || meld.tile===undefined){
          tiles.append(tileBack());
        }else tiles.append(card(meld.tile,null,false));
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
      const flag=$("match-self-missing-flag");
      flag.hidden=!missing;
      flag.textContent=missing?"缺"+names[missing]:"";
      flag.className="match-missing-flag"+
        (missing?" match-missing-flag--"+missing:"");
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
    const identity=el("div","match-seat-identity");
    identity.append(el("span","match-seat-avatar match-seat-avatar--"+seat,
      String(seat)));
    identity.append(el("strong","match-seat-name",
      seat+"号 · "+seats[seat].label+(ai?" · "+(levels[ai.difficulty]||ai.difficulty):"")));
    const missing=state.missing_suits?.[seat];
    if(missing){
      const flag=el("strong","match-missing-flag match-missing-flag--"+missing,
        "缺"+names[missing]);
      flag.setAttribute("aria-label",seat+"号定缺"+names[missing]);
      identity.append(flag);
    }
    root.append(identity);
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
  // M3.60: Four seat-local copies of ONE preallocated river matrix:
  // bottom: 14 columns x 4 rows (56 physical slots, enough for the 55-wall
  // game plus the dealer's first discard); other seats are geometric 90,
  // 180 and 270 degree rotations of this exact row-major layout.
  // Each discard receives its permanent grid coordinate on arrival. Claimed
  // discards keep their position as an empty marker, never slide later tiles.
  const RIVER_PER_ROW=14, RIVER_ROWS=4, RIVER_CAPACITY=56;
  const SIDE_RIVER_LANE_SIZE=RIVER_PER_ROW;
  function riverSlot(seat,index){
    const row=Math.floor(index/RIVER_PER_ROW),column=index%RIVER_PER_ROW;
    if(index<0||index>=RIVER_CAPACITY)throw Error("牌河超出实体牌容量");
    if(seat===0)return {row:row+1,column:column+1};
    if(seat===2)return {row:RIVER_ROWS-row,column:RIVER_PER_ROW-column};
    if(seat===3)return {row:column+1,column:RIVER_ROWS-row};
    if(seat===1)return {row:RIVER_PER_ROW-column,column:row+1};
    throw Error("无效座位");
  }
  // Reuse the actual physical river slots between public playback frames.
  // Rebuild only if an earlier public discard changed (claimed/won/type),
  // playback rewound, or a different table replaced the existing DOM.
  // Never cache/inspect an opponent's private hand or the unseen wall.
  const riverSnapshots=new WeakMap();
  function renderRiver(seat){
    const view=publicBoard();
    const root=$("match-river-"+seat);
    const entries=view.discards.map((entry,index)=>({...entry,order:index}))
      .filter(entry=>entry.seat===seat);
    // Global order matters: a new discard by ANOTHER seat can remove our
    // previous "latest" highlight without changing our own river entries.
    const keys=entries.map(entry=>JSON.stringify([
      entry.order,entry.tile,entry.claimed_by,entry.won_by,entry.discard_kind,
    ]));
    const previous=riverSnapshots.get(root);
    const appendOnly=!!previous && root.children.length===2 &&
      root.children[1]===previous.tiles &&
      previous.keys.length<=keys.length &&
      previous.keys.every((key,index)=>key===keys[index]);
    let tiles,cells,lane,fromIndex;
    if(appendOnly){
      tiles=previous.tiles;
      cells=previous.cells;
      lane=previous.lane;
      fromIndex=previous.keys.length;
      if(fromIndex===0 && entries.length)tiles.replaceChildren();
    }else{
      root.replaceChildren();
      root.append(el("strong","match-river-title",seats[seat].label+"牌河"));
      tiles=el("div","match-river-tiles");
      // All 56 grid positions are reserved by CSS before the first discard.
      tiles.setAttribute("data-river-capacity",String(RIVER_CAPACITY));
      tiles.setAttribute("data-river-seat",String(seat));
      root.append(tiles);
      cells=[];lane=null;fromIndex=0;
      if(!entries.length){
        tiles.append(el("span","match-river-empty","尚无弃牌"));
      }
    }
    for(let index=fromIndex;index<entries.length;index++){
      const entry=entries[index];
      if((seat===1||seat===3)&&index%SIDE_RIVER_LANE_SIZE===0){
        lane=el("div","match-river-lane");
        lane.setAttribute("aria-label","第"+
          (Math.floor(index/SIDE_RIVER_LANE_SIZE)+1)+"列牌河");
        tiles.append(lane);
      }
      const cell=el("div","match-river-cell");
      const slot=riverSlot(seat,index);
      cell.setAttribute("data-river-index",String(index));
      cell.setAttribute("data-river-row",String(slot.row));
      cell.setAttribute("data-river-column",String(slot.column));
      if(cell.style){
        cell.style.gridRow=String(slot.row);
        cell.style.gridColumn=String(slot.column);
      }
      const claimed=entry.claimed_by!==undefined;
      if(claimed){
        cell.classList.add("is-claimed");
        cell.append(el("span","match-river-claimed","已取走"));
        cell.title="本张弃牌已被碰或杠取走";
      }else{
        cell.append(card(entry.tile,null,false));
        cell.title=tileName(entry.tile);
      }
      if(entry.won_by)cell.classList.add("is-winning-discard");
      if(entry.discard_kind==="tsumogiri" || entry.discard_kind==="tedashi"){
        const drawCut=entry.discard_kind==="tsumogiri";
        cell.classList.add(drawCut?"is-tsumogiri":"is-tedashi");
        cell.append(el("span","match-discard-kind",drawCut?"摸切":"手切"));
        cell.title+=(drawCut?" · 摸切":" · 手切");
      }
      if(entry.order===view.discards.length-1){
        cell.classList.add("is-latest");
      }
      cell.setAttribute("data-discard-order",String(entry.order));
      (lane||tiles).append(cell);
      cells.push(cell);
    }
    const latestIndex=entries.length &&
      entries[entries.length-1].order===view.discards.length-1
      ?entries.length-1:-1;
    if(appendOnly && previous.latestIndex!==latestIndex){
      if(previous.latestIndex>=0){
        cells[previous.latestIndex].classList.toggle("is-latest",false);
      }
      if(latestIndex>=0){
        cells[latestIndex].classList.toggle("is-latest",true);
      }
    }
    riverSnapshots.set(root,{keys,tiles,cells,lane,latestIndex});
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
    return !liveBoard && Array.isArray(state?.win_ledger?.balances) &&
      (state.win_ledger.wins.length>0 ||
       (state.exhaustive_settlement?.posted===true &&
        state.exhaustive_settlement.entries.length>0) ||
        state.kong_ledger?.balances?.some(n=>n!==0));
  }
  function signedScore(value){
    return (value>=0?"+":"")+value;
  }
  function seatScoreText(seat){
    const amount=state.settled_balances?.[seat]??state.win_ledger.balances[seat];
    return "已入账积分 "+signedScore(amount);
  }
  function appendWinRecord(container,win,index){
    const type={self_draw:"自摸",ron:"点炮胡",rob_kong:"抢杠胡"}[win.kind]||
      "胡牌";
    const detail=el("details","match-win-record");
    detail.append(el("summary","",
      "第"+(index+1)+"笔 · "+win.winner+"号"+type+
      " · "+(win.main_pattern||"已确认胡牌")+
      " · 实收 "+signedScore(win.total_received)));
    const body=el("div","match-win-record-body");
    body.append(el("p","",
      "原始"+win.raw_fan+"番 → 计分"+win.effective_fan+
      "番 · 倍率 ×"+win.multiplier));
    body.append(el("p","",
      "付款："+win.payers.map(n=>n+"号").join("、")+
      " · 每人支付 "+win.amount_per_payer+
      " · 赢家实收 "+signedScore(win.total_received)));
    const bonuses=Object.entries(win.bonuses||{}).map(
      ([label,value])=>label+" +"+value);
    body.append(el("p","",
      "附加番："+(bonuses.length?bonuses.join("、"):"无")));
    detail.append(body);
    container.append(detail);
  }
  function appendReviewFrames(frames){
    for(const frame of frames){
      if(!frame?.board)continue;
      reviewHistory.push({...frame,
        sequence:reviewDropped+reviewHistory.length+1});
      if(reviewHistory.length>MAX_REVIEW_STEPS){
        reviewHistory.shift();
        reviewDropped++;
      }
    }
  }
  function filteredHistory(){
    const seat=$("match-review-seat-filter").value||"all";
    const kind=$("match-review-type-filter").value||"all";
    return window.MahTrainPlayback.filterReviewEntries(
      reviewHistory,seat,kind);
  }
  function renderReviewInspector(visible){
    const chosen=visible.find(x=>x.sequence===reviewSelected);
    const inspector=$("match-review-inspector");
    const contents=$("match-review-preview-seats");
    contents.replaceChildren();
    if(!chosen){
      inspector.hidden=true;
      $("match-review-prev").disabled=true;
      $("match-review-next").disabled=true;
      return;
    }
    inspector.hidden=false;
    const idx=visible.indexOf(chosen);
    $("match-review-prev").disabled=idx<=0;
    $("match-review-next").disabled=idx>=visible.length-1;
    $("match-review-selected").textContent=
      "第"+chosen.sequence+"步 · "+chosen.label;
    const board=chosen.board;
    $("match-review-board-status").textContent=
      "规则调用结束后的公开状态 · 牌山剩余"+board.wall_count+
      "张 · 当前座位"+(board.turn??"—")+
      "号 · 阶段 "+board.phase;
    for(const seat of seats){
      const sid=seat.id;
      const box=el("section","match-review-seat");
      if(board.won[sid])box.classList.add("is-won");
      box.append(el("strong","",sid+"号 · "+seat.label+
        (board.won[sid]?" · 已胡":"")));
      box.append(el("span","",
        "暗手 "+board.hand_counts[sid]+"张 · 公开副露"+
        board.melds[sid].length+"组"));
      const backs=el("div","match-review-backs");
      for(let n=0;n<board.hand_counts[sid];n++)backs.append(tileBack());
      box.append(backs);
      const meld=el("div","match-review-melds");
      renderMelds(meld,board.melds[sid],false);
      box.append(meld);
      const river=el("div","match-review-river");
      for(const discard of board.discards.filter(x=>x.seat===sid)){
        const item=el("span","match-review-river-tile");
        if(discard.claimed_by!==undefined){
          item.append(el("small","","已取走"));
        }else item.append(card(discard.tile,null,false));
        river.append(item);
      }
      box.append(river);
      contents.append(box);
    }
  }
  function renderReviewFiltered(){
    if(!state||liveBoard)return;
    const seat=$("match-review-seat-filter").value||"all";
    const wins=state.win_ledger?.wins||[];
    const shownWins=seat==="all"?wins:wins.filter(win=>
      win.winner===Number(seat)||win.payers?.includes(Number(seat)));
    const payouts=$("match-round-report-wins");
    payouts.replaceChildren();
    payouts.append(el("h5","",
      "逐笔胡牌流水 · "+shownWins.length+"笔"+
      (seat!=="all"?"（本座位赢家或付款者）":"")));
    if(!shownWins.length)payouts.append(el("p","match-round-no-wins",
      "此筛选条件下没有已入账胡牌。"));
    for(const win of shownWins)
      appendWinRecord(payouts,win,wins.indexOf(win));
    const found=filteredHistory();
    // A bounded DOM list; every retained snapshot remains reachable
    // through the most-recent 200 matching items.
    const visible=found.slice(-200);
    $("match-review-count").textContent=
      "匹配 "+found.length+" 步"+(found.length>200?
        "；列表仅显示最后200步。":"")+
      (reviewDropped?" 浏览器已省略最早"+reviewDropped+"个公开快照。":"");
    const timeline=$("match-round-report-events");
    timeline.replaceChildren();
    for(const frame of visible){
      const entry=button("第"+frame.sequence+"步 · "+frame.label,
        "match-review-action",()=>{
          reviewSelected=frame.sequence;
          renderReviewFiltered();
        });
      if(frame.important)entry.classList.add("is-key");
      if(frame.sequence===reviewSelected)entry.classList.add("is-selected");
      timeline.append(entry);
    }
    if(!visible.some(x=>x.sequence===reviewSelected))
      reviewSelected=visible.length?visible[visible.length-1].sequence:null;
    // The first render must also visibly mark the default selected item.
    for(const buttonNode of timeline.children){
      if(buttonNode.textContent.startsWith("第"+reviewSelected+"步 · "))
        buttonNode.classList.add("is-selected");
    }
    renderReviewInspector(visible);
  }
  function stepReview(direction){
    const visible=filteredHistory().slice(-200);
    const idx=visible.findIndex(x=>x.sequence===reviewSelected);
    const next=visible[idx+direction];
    if(!next)return;
    reviewSelected=next.sequence;
    renderReviewFiltered();
  }
  function renderRoundReport(){
    const report=$("match-round-report");
    const terminal=!!state && !liveBoard &&
      (state.phase==="finished"||state.phase==="wall_exhausted");
    report.hidden=!terminal;
    if(!terminal)return;
    const wallEnd=state.phase==="wall_exhausted";
    $("match-round-report-title").textContent=wallEnd?
      "牌山耗尽 · 本局复盘":"三家胡牌 · 本局复盘";
    const ledger=state.win_ledger;
    const postedWins=ledger?.wins||[];
    const kong=state.kong_ledger;
    const discarded=seats.map(seat=>
      state.discards.filter(item=>item.seat===seat.id).length);
    $("match-round-report-status").textContent=
      "本局共"+postedWins.length+"笔胡牌入账"+
      (state.exhaustive_settlement?.posted?
        " · "+state.exhaustive_settlement.entries.length+"笔流局赔付入账":"")+
      " · "+state.discards.length+"次公开弃牌 · 牌山剩余"+
      state.wall_count+"张";
    const summary=$("match-round-report-seats");
    summary.replaceChildren();
    for(const seat of seats){
      const id=seat.id;
      const seatCard=el("div","match-round-seat");
      const winnerCount=postedWins.filter(win=>win.winner===id).length;
      seatCard.append(el("strong","",id+"号 · "+seat.label+
        (state.won[id]?" · 已胡":"")));
      seatCard.append(el("span","",
        "胡牌"+winnerCount+"次 · 弃牌"+discarded[id]+"张"+
        " · 公开副露"+state.melds[id].length+"组"));
      seatCard.append(el("b","match-round-seat-balance",
        "胡牌积分 "+signedScore(ledger?.balances?.[id]??0)+
        " · 杠钱 "+signedScore(kong?.balances?.[id]??0)+
        (state.exhaustive_settlement?.posted?
          " · 流局 "+signedScore(state.exhaustive_settlement.balances[id])+
          " · 流局赔付已入账":"")+
        " · 本局合计 "+signedScore(state.settled_balances?.[id]??0)));
      seatCard.append(el("small","",
        kong?.base==null?"旧局杠钱未计价":
        "杠钱底分 "+kong.base+" · 已计入本局合计"));
      summary.append(seatCard);
    }
    renderReviewFiltered();
    $("match-round-report-note").textContent=
      "胡牌积分依据服务器已入账账本；历史局面来自本次浏览器会话逐次保存的真实公开快照，刷新页面后不保留。"+
      (reviewDropped?"已省略最早"+reviewDropped+"个公开快照。":"")+
      (wallEnd?(state.exhaustive_settlement?.posted?
        " 方案A（仅未胡玩家参与）已完成流局零和结算。":
        " 牌山耗尽后的查花猪、查大叫存在待核验事项或旧局记录，流局赔付未入账。"):
        " 本局未发生流局，流局赔付未入账。")+
      " 本局已计价杠钱计入净收益，胡牌流水单列。";
  }
  function renderTableSettlement(){
    const panel=$("match-table-settlement");
    const ledger=state.win_ledger;
    const terminal=state.phase==="finished"||state.phase==="wall_exhausted";
    // A terminal round deserves a readable score sheet even with zero HUs.
    // In an unresolved wall draw that is NOT a finalized zero balance.
    const hasLedger=Array.isArray(ledger?.balances)&&
      ledger.balances.length===4&&ledger.balances.every(Number.isSafeInteger);
    const visible=settlementAvailable()||(terminal&&hasLedger);
    panel.hidden=!visible;
    if(!visible)return;
    const wallPending=state.phase==="wall_exhausted"&&
      state.exhaustive_settlement?.posted!==true;
    $("match-table-settlement-title").textContent=wallPending?
      "流局待核验 · 当前显示胡牌和杠钱已入账金额":
      state.exhaustive_settlement?.posted?
        "本局胡牌 + 杠钱 + 流局结算 · 已入账":"本局胡牌 + 杠钱结算 · 已入账";
    $("match-table-round-phase").textContent=terminal?"摸切已结束":"对局进行中";
    const myPosted=state.settled_balances?.[0]??ledger.balances[0];
    $("match-table-self-summary").textContent=
      "我的已入账积分 "+signedScore(myPosted)+" · "+
      (wallPending?"牌山耗尽 · 流局赔付待核验，不代表最终净积分":
        state.exhaustive_settlement?.posted?
          "包含胡牌、杠钱及方案A已确认的流局赔付":"包含已确认胡牌和杠钱积分");
    const scores=$("match-table-scores");
    scores.replaceChildren();
    for(const seat of seats){
      const amount=state.settled_balances?.[seat.id]??ledger.balances[seat.id];
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
    const history=$("match-table-history");
    history.replaceChildren();
    const all=el("details","match-win-history");
    all.append(el("summary","",
      "查看本局全部"+ledger.wins.length+"笔胡牌详情"));
    for(const [index,win] of ledger.wins.entries())
      appendWinRecord(all,win,index);
    history.append(all);
    const kongEnabled=state.kong_ledger?.base!=null;
    $("match-table-score-note").textContent=
      (state.exhaustive_settlement?.posted?
        "以上为胡牌 + 杠钱 + 方案A流局已入账合计":
        "以上为胡牌及已计价杠钱的总额")+
      (kongEnabled?"；杠钱已计入本栏":"；本局杠钱未计价")+
      (wallPending?"；本局流局赔付待核验，当前合计不能视为最终净积分。":
        state.exhaustive_settlement?.posted?"。":"；无正式流局结算。");
  }
  function renderWall(){
    const remaining=publicBoard().wall_count;
    $("match-wall-count").textContent=String(remaining);
    $("match-wall").classList.toggle("is-exhausted",remaining===0);
  }
  function renderHUD(){
    const board=publicBoard();
    if(!board||!state)return;
    const phase=liveBoard?"公开动作回放":
      (["finished","wall_exhausted"].includes(state.phase)?"本局结束":
        ["exchange_select","missing_select"].includes(state.phase)?"开局准备":
          ["claim_window","rob_kong_window"].includes(state.phase)?"等待碰杠胡":
            state.won?.[0]?"已胡等待结算":
              state.turn===0?"轮到你出牌":board.turn+"号正在行动");
    $("match-hud-turn").textContent=phase;
    $("match-hud-wall").textContent=String(
      board.wall_count??state.wall_count??0)+" 张";
    const missing=state.missing_suits?.[0];
    $("match-hud-missing").textContent=missing?"缺"+names[missing]:"待选择";
    let tip="查看牌桌公开动作";
    if(liveBoard){
      tip="回放中 · 暗手不更新";
    }else if(state.phase==="exchange_select"){
      tip="请选择3张同花色牌";
    }else if(state.phase==="missing_select"){
      tip="选择本局定缺花色";
    }else if(["claim_window","rob_kong_window"].includes(state.phase)){
      const opts=state.phase==="claim_window"?
        state.claim_options:state.rob_options;
      tip=!state.claim_submitted?.includes(0)&&
        opts?.some(option=>option!=="pass")?
        "可响应 · 请在牌桌中央选择碰、杠、胡或过":
        "暂无可响应动作 · 正在继续对局";
    }else if(["finished","wall_exhausted"].includes(state.phase)){
      tip="本局结束 · 查看结算和复盘";
    }else if(state.won?.[0]){
      tip="你已胡牌 · 等待本局结束";
    }else if(state.can_self_draw_win){
      tip="可自摸 · 在下方确认胡牌";
    }else if(state.turn===0 && pendingDiscard){
      tip="已选"+tileName(pendingDiscard.tile)+" · 请确认出牌";
    }else if(state.turn===0){
      tip=$("match-confirm-discard").checked?
        "点选手牌，再确认打出":"点击手牌即可打出";
    }else{
      tip="观察三家行动 · 等待你的回合";
    }
    $("match-hud-tip").textContent=tip;
    const stage=$("match-stage");
    stage.classList.toggle("is-immersive",immersive);
    $("match-board").classList.toggle("is-midnight-felt",midnightFelt);
    $("match-skin-toggle").setAttribute("aria-pressed",String(midnightFelt));
    $("match-skin-toggle").textContent=midnightFelt?"经典深蓝桌布":"午夜深蓝桌布";
    $("match-focus-toggle").setAttribute("aria-pressed",String(immersive));
    $("match-focus-toggle").textContent=immersive?"显示详细信息":"沉浸牌桌";
  }
  function renderBoard(){
    renderHUD();
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
      wall_exhausted:"牌墙耗尽 · 方案A流局已结算或等待牌形核验",
    };
    const phase=state.phase;
    $("match-title").textContent=phaseLabels[phase]||phase;
    $("match-status").textContent=
      "你是0号位 · 庄家"+state.dealer+"号 · "+directions[state.exchange_direction]+
      "换牌 · 剩余"+state.wall_count+"张 · 当前行动："+(state.turn??"—");
    const hand=$("match-hand");
    const previousHandScroll=Number(hand.scrollLeft)||0;
    hand.replaceChildren();
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
        onclick=()=>chooseDiscard(tile,false,i);
      const tileNode=card(tile,onclick,choice.has(i));
      if(pendingDiscard?.index===i&&!pendingDiscard.fromDraw){
        // Visually lift only the physical hand copy the player tapped.
        tileNode.classList.add("match-pending-discard");
      }
      hand.append(tileNode);
    });
    if(drawnIndex>=0){
      const last=card(drawn,()=>chooseDiscard(drawn,true,drawnIndex),false);
      if(pendingDiscard?.fromDraw&&pendingDiscard.tile===drawn){
        last.classList.add("match-pending-discard");
      }
      last.classList.add("match-new-draw");
      last.title="刚摸到："+tileName(drawn)+" · 点击摸切";
      last.setAttribute("aria-label","刚摸到"+tileName(drawn)+"，点击摸切");
      hand.append(last);
    }
    hand.scrollLeft=previousHandScroll;
    updateHandNavigation();
    renderBoard();
    renderReadyHint();
    renderWinAlert();
    renderRoundReport();
    const controls=$("match-controls");controls.replaceChildren();
    const decision=$("match-decision");
    decision.replaceChildren();decision.hidden=true;
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
      // If PASS is the only legal response, the server automatically
      // advances it. A blocking popup with only "过" is not an opportunity.
      // A real opportunity exists only BEFORE seat zero has submitted a
      // response. Waiting for other AI players must not reopen the popup.
      const humanCanRespond=!state.claim_submitted?.includes(0)&&
        target?.seat!==0&&options?.some(option=>option!=="pass");
      if(humanCanRespond){
      decision.append(el("strong","match-decision-title",
        phase==="claim_window"?"请选择碰、杠、胡或过":"请选择抢杠胡或过"));
      decision.append(el("p","match-decision-hint",
        "目标："+(target?tileName(target.tile):"—")+
        " · 胡牌优先；请确认本次响应"));
      const reactions=el("div","match-reaction-actions");
      reactions.setAttribute("role","group");
      reactions.setAttribute("aria-label","本次碰杠胡响应");
      const priority=["hu","ming_gang","peng","pass"];
      for(const option of [...options].sort((a,b)=>
        priority.indexOf(a)-priority.indexOf(b))){
        const label=option==="pass"?"过 · 放弃本次响应":
          option==="hu"?"胡 · 优先响应":
            actionNames[option]||option;
        const btn=button(label,
          "match-reaction-button match-reaction--"+option+
          (option==="hu"?" primary":" review-control"),
          ()=>{
            decision.hidden=true;
            action(phase==="claim_window"?"match_claim":"match_rob",
              {choice:option});
          });
        btn.setAttribute("aria-label",
          (actionNames[option]||option)+
          (option==="pass"?"，跳过本次机会":"，提交本次响应"));
        reactions.append(btn);
      }
      decision.append(reactions);
      decision.hidden=false;
      }
    }else if(phase==="dealer_discard"||phase==="await_discard"){
      if(state.can_self_draw_win){
        // Server-confirmed, seat-0-only quote. Never calculate payouts from
        // a guessed concealed hand, future tile or stale room selector.
        const quote=state.self_draw_preview;
        if(quote && quote.posted===false &&
           Array.isArray(quote.payers) && quote.payers.length &&
           Number.isSafeInteger(quote.amount_per_payer) &&
           Number.isSafeInteger(quote.total_received)){
          const preview=el("section","match-self-win-preview");
          preview.setAttribute("aria-label","本次自摸结算预览，尚未入账");
          preview.append(el("strong","","可自摸 · 结算预览（尚未入账）"));
          const mode={add_base:"自摸加底",add_fan:"自摸加番",
            legacy:"旧版规则"}[quote.self_draw_mode]||"自摸规则";
          preview.append(el("span","",
            (quote.main_pattern||"合法胡牌")+" · "+mode+
            " · 原始"+quote.raw_fan+"番 → 有效"+quote.effective_fan+
            "番 · 牌型×"+quote.base_multiplier+
            " → 每家支付×"+quote.payment_multiplier));
          preview.append(el("span","",
            "付款："+quote.payers.map(s=>s+"号").join("、")+
            "（"+quote.payers.length+"家），每家付"+
            quote.amount_per_payer+"，确认后预计共收"+
            quote.total_received));
          preview.append(el("small","",
            "按服务器当前已确认牌型和仍未胡的玩家计算；点击胡牌后正式结算，不含杠钱及流局赔付。"));
          controls.append(preview);
        }
        controls.append(button("胡！确认自摸入账",
          "primary match-self-win-action",
          ()=>action("match_win")));
      }
      if(state.kong_options?.length){
        const kongKey=[token,phase,state.events?.length||0,
          state.drawn_tile||"",
          state.kong_options.map(k=>k.type+":"+k.tile).join(",")].join("|");
        controls.append(button("可杠牌 · 查看选项",
          "review-control match-open-kong",()=>{
            kongPromptReopened=true;
            render();
          }));
        if(dismissedKongKey!==kongKey||kongPromptReopened){
          decision.append(el("strong","match-decision-title","本回合可杠牌"));
          decision.append(el("p","match-decision-hint",
            "可以选择杠牌，也可以暂不杠，继续出牌"));
          const kongActions=el("div","match-reaction-actions");
          kongActions.setAttribute("role","group");
          kongActions.setAttribute("aria-label","本回合可执行的杠牌操作");
          for(const kong of state.kong_options){
            kongActions.append(button(
              actionNames[kong.type]+" "+tileName(kong.tile),
              "match-reaction-button match-reaction--ming_gang",
              ()=>{
                if(confirm("确认"+actionNames[kong.type]+tileName(kong.tile)+
                    "？合法杠后从牌墙尾部补牌。")){
                  decision.hidden=true;
                  action("match_kong",{kind:kong.type,tile:kong.tile});
                }
              }));
          }
          kongActions.append(button("暂不杠 · 继续出牌",
            "match-reaction-button match-reaction--pass",()=>{
              dismissedKongKey=kongKey;
              kongPromptReopened=false;
              render();
            }));
          decision.append(kongActions);
          decision.hidden=false;
        }
      }
      if(pendingDiscard && $("match-confirm-discard").checked){
        const selected=pendingDiscard;
        const confirmCut=button("确认打出 "+tileName(selected.tile)+
          "（"+(selected.fromDraw?"摸切":"手切")+"）","primary match-confirm-cut",
          ()=>action("match_discard",{
            tile:selected.tile,from_draw:selected.fromDraw,
          }));
        controls.append(confirmCut);
        controls.append(button("取消选牌","review-control",()=>{
          pendingDiscard=null;render();
        }));
      }
      controls.append(el("p","review-intro",
        $("match-confirm-discard").checked
          ?"点选手牌后使用“确认打出”，可减少手机误触；摸到的牌仍位于最右边。"
          :"点击自己的麻将即可切牌；右侧发光标记是刚摸的牌。"));
    }else{
      controls.append(el("p","review-intro",
        "本局摸切已结束。胡牌已入账；牌山耗尽时按方案A处理流局赔付（如牌形未核验则暂缓），杠钱仍为独立模拟。可以重新开一局。"));
    }
    // A claim/rob decision now lives on the TABLE, not an empty sticky
    // toolbar below it. Keep the toolbar for exchange and manual discard.
    controls.hidden=controls.children.length===0;
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
      score.append(el("h4","","四家胡牌流水（净收益另含杠钱）"));
      score.append(el("p","review-footnote",
        "房间系数"+ledger.room_coefficient+
        " · 最终番数封顶"+ledger.fan_cap+
        " · 自摸方式"+({add_base:"加底",add_fan:"加番",
          legacy:"旧版标准"}[ledger.self_draw_mode]||"未知")+
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
            win.effective_fan+"番 / 牌型×"+win.multiplier+
            (win.kind==="self_draw"?
              " / 自摸"+({add_base:"加底",add_fan:"加番",
                legacy:"旧版"}[ledger.self_draw_mode]||"")+
              " / 每家×"+(win.amount_per_payer/ledger.room_coefficient):"")));
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
        "胡牌、已计价杠钱与合法流局赔付单独记账，共同计入本局正式收益。"));
      publicInfo.append(score);
    }
    const kongLedger=state.kong_ledger;
    if(kongLedger){
      const k=el("section","match-kong-ledger");
      k.append(el("h4","","杠钱结算与冲销流水"));
      k.append(el("p","review-footnote",kongLedger.base===null
        ?"旧局未设置杠钱底分：杠钱尚未计价。"
        :"本局杠钱底分 "+kongLedger.base+"；已计入本局正式净收益。"));
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
      const net=state.settled_balances||[0,0,0,0];
      k.append(el("p","match-net",
        "胡牌 + 杠钱 + 流局正式净收益："+net.map((n,i)=>
          i+"号"+(n>=0?"+":"")+n).join(" · ")));
      publicInfo.append(k);
    }
    const review=state.exhaustive_review;
    const settled=state.exhaustive_settlement;
    if(review?.triggered){
      const sec=el("section","match-exhaustive-review");
      sec.append(el("h4","",
        settled?.posted?"流局查花猪 / 查大叫 · 方案A已正式入账":
        "流局查花猪 / 查大叫 · 尚未正式入账"));
      sec.append(el("p","review-intro",
        "仅"+review.participating_active_seats.length+
        "位未胡玩家参与流局收付款；已胡玩家不收也不付。"+
        (settled?.posted?" 已由服务器逐笔结算并完成四家零和校验。":
          " 当前是旧局试算或存在待核验牌形，不作实际扣款。")));
      const kinds={flower_pig:"花猪",listening:"合法听牌",
        unready:"未听牌",unresolved_exposed_missing:"缺门公开副露待核验",
        unresolved_nonstable_hand:"非稳定手牌待核验"};
      for(const item of review.seats){
        sec.append(el("p","review-footnote",
          item.seat+"号："+(kinds[item.classification]||"待核验")+
          (item.max_effective_fan!==null?
            " · 最大可结"+item.max_effective_fan+"番":"")));
      }
      const transfers=settled?.posted?settled.entries:review.proposed_transfers;
      for(const entry of transfers){
        sec.append(el("p","review-footnote",
          (entry.stage==="flower_pig"?"查花猪":"查大叫")+
          (settled?.posted?"（已入账）":"（仅预览）")+"："+
          entry.payer+"号向"+entry.recipient+"号付"+entry.amount));
      }
      if(settled?.posted){
        sec.append(el("p","match-net",
          "四家流局净额："+settled.balances.map((n,i)=>
            i+"号"+signedScore(n)).join(" · ")+
          " · 零和"+(settled.zero_sum?"通过":"异常")));
      }else{
        sec.append(el("p","match-unpriced",
          settled?.reason==="unresolved_terminal_hand"?
            "存在异常公开缺门副露或非稳定手牌，正式赔付已暂缓；没有扣除任何流局积分。":
            "此记录尚未进行正式流局入账。"));
      }
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
  function startNewGame(alwaysRandom){
    if(busy)return;
    if(state && !["finished","wall_exhausted"].includes(state.phase) &&
       !confirm("当前对局尚未结束，新开一局会放弃本局未完成的进度。确定开始吗？"))return;
    const options={
      room_coefficient:Number($("match-coefficient").value),
      fan_cap:Number($("match-fan-cap").value),
      self_draw_mode:$("match-self-draw-mode").value,
      ai_levels:[1,2,3].map(n=>$("match-ai-"+n).value),
      kong_base:$("match-enable-kong").checked
        ?Number($("match-kong-base").value):Number($("match-coefficient").value),
    };
    if(!alwaysRandom && $("match-lab-enabled").checked){
      const raw=$("match-seed").value.trim();
      const number=Number(raw);
      if(!/^\d+$/.test(raw)||!Number.isSafeInteger(number)||
         number<0||number>4294967295){
        $("match-error").textContent="实验室种子必须为0至4294967295的整数。";
        return;
      }
      options.seed=number;
    }
    action("match_new",options);
  }
  function init(){
    if(window.MahTrainMatchVoice){
      voice=window.MahTrainMatchVoice.create(window);
    }
    const toggleVoice=$("match-voice-enabled");
    toggleVoice.checked=!!voice?.supported;
    $("match-voice-status").textContent=voice?.supported
      ?"公开牌名与碰杠胡语音最长播报1.3秒，超时中断且不阻塞AI，可关闭"
      :"此浏览器暂不支持语音合成，仍可正常对局";
    toggleVoice.disabled=!voice?.supported;
    toggleVoice.addEventListener("change",()=>{
      voice?.setEnabled(toggleVoice.checked);
      syncVoiceControls();
    });
    const voiceSpeed=$("match-voice-speed");
    voiceSpeed.value=voice?.getRate()||"normal";
    voiceSpeed.addEventListener("change",()=>{
      voiceSpeed.value=voice?.setRate(voiceSpeed.value)||"normal";
    });
    $("match-voice-repeat").addEventListener("click",()=>{
      voice?.repeatLast();
      syncVoiceControls();
    });
    syncVoiceControls();
    $("match-focus-toggle").addEventListener("click",()=>{
      immersive=!immersive;
      if(state)renderHUD();
    });
    $("match-hand-prev").addEventListener("click",()=>navigateHand("left"));
    $("match-hand-next").addEventListener("click",()=>navigateHand("right"));
    $("match-hand-draw").addEventListener("click",()=>navigateHand("draw"));
    $("match-hand").addEventListener("scroll",updateHandNavigation);
    updateHandNavigation();
    $("match-skin-toggle").addEventListener("click",()=>{
      midnightFelt=!midnightFelt;
      if(state)renderHUD();
    });
    const picker=$("match-back-color");
    picker.value=backColor;
    $("match-board").setAttribute("data-back-color",backColor);
    picker.addEventListener("change",()=>{
      if(["jade","indigo","red","gold"].includes(picker.value))
        backColor=picker.value;
      picker.value=backColor;
      $("match-board").setAttribute("data-back-color",backColor);
    });
    // Prefer safer two-tap confirmation on touch-first phones and tablets.
    // Desktop mouse keeps the fast existing one-click behavior by default.
    $("match-confirm-discard").checked=
      !!window.matchMedia?.("(pointer: coarse)")?.matches;
    $("match-confirm-discard").addEventListener("change",()=>{
      pendingDiscard=null;
      if(state)render();
    });
    $("match-lab-enabled").addEventListener("change",()=>{
      $("match-seed").disabled=!$("match-lab-enabled").checked;
    });
    playback=window.MahTrainPlayback.createController({
      onFrame:showPublicMotion,onStatus:onPlaybackStatus,
      onDone:onPlaybackDone,
    });
    const speed=$("match-playback-speed");
    playback.setSpeed(Number(speed.value)||180);
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
    for(const id of ("match-review-seat-filter match-review-type-filter").split(" ")){
      $(id).addEventListener("change",()=>renderReviewFiltered());
    }
    $("match-review-prev").addEventListener("click",()=>stepReview(-1));
    $("match-review-next").addEventListener("click",()=>stepReview(1));
    $("match-enable-kong").addEventListener("change",()=>{
      $("match-kong-base").disabled=!$("match-enable-kong").checked;
    });
    $("match-new").addEventListener("click",()=>startNewGame(false));
    $("match-again").addEventListener("click",()=>startNewGame(true));
    $("match-resume-retry").addEventListener("click",()=>resumeMatch());
    // The route hub is initialized later; no navigation or new-game
    // mutation occurs while restoring, and stale sessions are recoverable.
    void resumeMatch();
  }
  window.MahTrainMatch={init};
})();
