"use strict";
/* M3.22: read-only browser for server-generated completed public archives. */
(function(){
  const $=id=>document.getElementById(id);
  const playback=()=>window.MahTrainPlayback;
  const cutQuality=()=>window.MahTrainCutQuality;
  let listed=[],opened=null,selected=new Set(),frames=[],active=null;
  // The saved cut adviser scored PRE-discard cards, not the post-action board.
  let handPhase="auto";
  let lastGrouping=null,refreshVersion=0;
  const el=(tag,kind,txt)=>{
    const n=document.createElement(tag);
    if(kind)n.className=kind;
    if(txt!==undefined)n.textContent=String(txt);
    return n;
  };
  const add=(root,child)=>{root.append(child);return child;};
  const sign=n=>(n>=0?"+":"")+n;
  const uri=id=>"/api/match_archives?archive_id="+encodeURIComponent(id);
  const winType={ron:"点炮胡",rob_kong:"抢杠胡",self_draw:"自摸"};
  const makeButton=(txt,callback)=>{
    const b=el("button","match-archive-button",txt);
    b.type="button";b.addEventListener("click",callback);return b;
  };
  async function api(url){
    const result=await fetch(url,{cache:"no-store"});
    const data=await result.json();
    if(!result.ok)throw new Error(data.error||"对局档案请求失败");
    return data;
  }
  function fail(err){$("match-archives-message").textContent=err.message||String(err);}
  function comparison(){
    const panel=$("match-archives-comparison");
    panel.replaceChildren();
    const compared=listed.filter(x=>selected.has(x.archive_id));
    $("match-archives-compare").disabled=compared.length!==2;
    if(compared.length!==2)return;
    const a=compared[0],b=compared[1];
    const title=el("strong","","已完成对局比较 · 0号正式净额（含新版已计价杠钱）");
    panel.append(title);
    for(const match of compared){
      panel.append(el("p","",
        match.created_at+" · "+(match.phase==="finished"?"三家胡牌":"牌山耗尽")+
        " · 0号正式净额 "+sign(match.settled_b0??match.win_b0)+
        "（胡牌 "+sign(match.win_b0)+"）"+
        " · "+match.win_count+"笔胡牌"));
    }
    panel.append(el("p","",
      "两局正式积分差额："+sign(
        (a.settled_b0??a.win_b0)-(b.settled_b0??b.win_b0))+
      " · 胡牌部分差额："+sign(a.win_b0-b.win_b0)+
      "（第一局减第二局；新版正式净额含已计价杠钱，旧版试验杠钱不追溯计入）"));
  }
  function renderScorecard(board){
    const status=$("match-scorecard-status");
    const seats=$("match-scorecard-seats");
    const trend=$("match-scorecard-trend");
    seats.replaceChildren();
    trend.replaceChildren();
    if(!board || !Array.isArray(board.seats) || board.seats.length!==4){
      status.textContent="暂无可核验的历史成绩。";
      return;
    }
    status.textContent="已核验 "+board.valid_games+" 局"+
      (board.excluded_games?" · 排除"+board.excluded_games+"局缺失或不一致的旧档案":"")+
      " · 所有座位正式积分合计零和："+(board.zero_sum?"通过":"异常");
    for(const seat of board.seats){
      const card=el("div","match-scorecard-seat");
      card.append(el("strong","",seat.seat===0?"0号 · 玩家":"座位"+seat.seat+" · AI"));
      card.append(el("b",seat.settled_total>=0?"is-credit":"is-debit",
        sign(seat.settled_total)));
      card.append(el("span","",
        "胡牌 "+sign(seat.hu_total)+" · 流局 "+sign(seat.draw_total)));
      card.append(el("span","",
        "场均 "+sign(seat.average_settled)+
        " · 正/负/零局 "+seat.positive_games+"/"+
        seat.negative_games+"/"+seat.zero_games));
      seats.append(card);
    }
    const history=Array.isArray(board.trend)?board.trend:[];
    if(!history.length){
      trend.append(el("p","review-footnote","尚无可核验的已完成对局。"));
      return;
    }
    const max=Math.max(1,...history.map(x=>Math.abs(x.score)));
    for(const item of history){
      const row=el("div","match-scorecard-trend-row");
      row.append(el("span","match-scorecard-date",item.created_at.slice(0,10)));
      const negative=el("div","match-scorecard-half negative");
      const positive=el("div","match-scorecard-half positive");
      if(item.score!==0){
        const bar=el("span","match-scorecard-bar");
        bar.style.width=(Math.abs(item.score)/max*100).toFixed(1)+"%";
        (item.score<0?negative:positive).append(bar);
      }
      row.append(negative,positive);
      row.append(el("span","match-scorecard-round",sign(item.score)));
      row.append(el("span","match-scorecard-cumulative","累计 "+sign(item.cumulative)));
      trend.append(row);
    }
  }
  function renderGroupings(){
    const status=$("match-history-groups-status");
    const root=$("match-history-groups-rows");
    root.replaceChildren();
    const mode=$("match-history-groups-mode").value;
    const byAI=mode!=="rules";
    const rows=lastGrouping?.[byAI?"ai_lineups":"room_rules"]||[];
    const missing=lastGrouping?.[byAI?"missing_ai_games":"missing_rules_games"]||0;
    status.textContent=(byAI?"按AI难度组合":"按房间系数与番封顶")+
      " · 共"+rows.reduce((sum,r)=>sum+r.games,0)+"局进入分组"+
      " · "+missing+"局缺少对应历史配置未参与该分组";
    if(!rows.length){
      root.append(el("p","review-footnote",
        "暂无具有完整配置和有效结算账本的对局；新对局完成后将自动加入。"));
      return;
    }
    const level={basic:"入门",advanced:"进阶",challenge:"挑战"};
    for(const item of rows){
      const card=el("div","match-history-group-item");
      const name=byAI?
        item.ai_levels.map((x,i)=>(i+1)+"号"+(level[x]||x)).join(" · "):
        "房间系数"+item.room_coefficient+" · 封顶"+item.fan_cap+"番"+
        " · 自摸"+({add_base:"加底",add_fan:"加番",legacy:"旧版"}[
          item.self_draw_mode]||"未知");
      card.append(el("strong","",name));
      card.append(el("span","match-history-group-total",
        "0号正式净额合计 "+sign(item.settled_total)+
        " · 场均 "+sign(item.average_settled)));
      card.append(el("span","",
        "胡牌 "+sign(item.hu_total)+" · 流局 "+sign(item.draw_total)+
        " · "+item.games+"局 · 正/负/零 "+
        item.positive_games+"/"+item.negative_games+"/"+item.zero_games));
      card.append(el("small","",
        "按房间系数折算的场均 "+
        (item.average_per_coefficient===null?"不可计算":
          sign(item.average_per_coefficient)+"系数单位")+
        "（可计算"+item.normalized_games+"/"+item.games+"局）"+
        (byAI&&item.rules_variant_count>1?
          " · 含"+item.rules_variant_count+"种房间配置":"")));
      if(item.small_sample){
        card.append(el("small","match-history-group-warning",
          "样本不足5局，仅供观察，不支持判断哪种AI更强。"));
      }
      root.append(card);
    }
  }
  function renderList(){
    const root=$("match-archives-list");
    root.replaceChildren();
    if(!listed.length)root.append(el("p","","暂无已完成的四人对局档案。"));
    for(const match of listed){
      const row=el("div","match-archive-entry");
      const check=el("input");
      check.type="checkbox";check.checked=selected.has(match.archive_id);
      check.addEventListener("change",()=>{
        if(check.checked){
          if(selected.size===2){
            check.checked=false;
            $("match-archives-message").textContent="一次最多比较两局。";
            return;
          }
          selected.add(match.archive_id);
        }else selected.delete(match.archive_id);
        comparison();
      });
      row.append(check);
      row.append(el("span","",
        match.created_at+" · "+(match.phase==="finished"?"三家已胡":"牌山耗尽")+
        " · "+match.win_count+"笔胡牌 · 0号正式净额 "+
        sign(match.settled_b0??match.win_b0)+
        "（胡牌 "+sign(match.win_b0)+"）"));
      row.append(makeButton("查看公开复盘",()=>openMatch(match.archive_id)));
      root.append(row);
    }
    comparison();
  }
  async function refresh(){
    const version=++refreshVersion;
    try{
      $("match-archives-message").textContent="";
      const period=$("match-archives-period")?.value||"all";
      const response=await api("/api/match_archives?limit=5000&period="+encodeURIComponent(period));
      // Slow earlier replies must never overwrite a newer visit's chart.
      if(version!==refreshVersion)return;
      listed=response.matches||[];
      const limited=response.summary.games>listed.length;
      const periodName={all:"全部历史",week:"最近一周",month:"最近一月",year:"最近一年"}[period]||period;
      selected=new Set([...selected].filter(id=>
        listed.some(x=>x.archive_id===id)));
      $("match-archives-summary").textContent=
        periodName+"：已保存 "+response.summary.games+" 局"+(limited?"（列表显示最新"+listed.length+"局）":"")+" · 0号平均正式净额 "+
        Number(response.summary.average_player0_settled_balance??
          response.summary.average_player0_win_balance).toFixed(1)+
        "（平均胡牌 "+Number(
          response.summary.average_player0_win_balance).toFixed(1)+"）"+
        " · 累计 "+response.summary.paid_wins+"笔胡牌";
      renderList();
      renderScorecard(response.scorecard);
      window.MahTrainMatchStats?.render(response.scorecard,document);
      lastGrouping=response.scorecard?.groupings||null;
      renderGroupings();
    }catch(err){if(version===refreshVersion)fail(err)}
  }
  function renderArchiveBoard(frame){
    const root=$("match-archives-board");
    root.replaceChildren();
    if(!frame||!frame.board){
      root.append(el("p","","请选择一项公开历史动作。"));return;
    }
    const board=frame.board;
    const terminal=opened?.report?.terminal_review;
    // Public steps carry no private cards. Finished version-2 archives
    // unlock their separately sanitized authentic all-seat snapshots;
    // historical version-1 archives MUST remain visibly incomplete.
    const snapshot=terminal?.steps?.[frame.sequence-2]||
      (frame.sequence===1&&terminal?
       {hands_after:terminal.opening}:null);
    root.append(el("strong","","第"+frame.sequence+"步 · "+frame.label+
      " · 牌山"+board.wall_count+"张"));
    // Preserve the true decision moment in a finished archive. The public
    // board (river/melds/turn/remaining wall) is always the action's AFTER
    // state, so never mislabel it as if it were a pre-action public board.
    const validFourHands=hands=>Array.isArray(hands)&&hands.length===4&&
      hands.every(hand=>Array.isArray(hand));
    const beforeHands=validFourHands(snapshot?.hands_before)?
      snapshot.hands_before:null;
    const afterHands=validFourHands(snapshot?.hands_after)?
      snapshot.hands_after:null;
    const shownPhase=handPhase==="before"&&beforeHands?"before":
      handPhase==="after"&&afterHands?"after":
      snapshot?.cut_review&&beforeHands?"before":
      afterHands?"after":beforeHands?"before":null;
    const shownHands=shownPhase==="before"?beforeHands:afterHands;
    if(beforeHands&&afterHands){
      const controls=el("div","match-archive-hand-switch");
      for(const phase of ["before","after"]){
        const button=makeButton(phase==="before"?"动作前手牌":"动作后手牌",()=>{
          handPhase=phase;
          renderArchiveBoard(frame);
        });
        button.setAttribute("aria-pressed",String(shownPhase===phase));
        if(phase===shownPhase)button.classList.add("is-selected");
        controls.append(button);
      }
      root.append(controls);
    }
    if(shownHands){
      root.append(el("p","review-footnote",
        "当前显示四家"+(shownPhase==="before"?"动作前":"动作后")+
        "真实手牌；下方的牌河、副露、已胡标记及牌山数量始终来自动作后公开快照。"+
        (snapshot?.cut_review&&shownPhase==="before"?
          "切牌前三推荐以这里的0号出牌前手牌和当时可见公开信息计算。":"")));
    }else if(snapshot?.cut_review){
      root.append(el("p","review-footnote",
        "旧档案未保存本巡出牌前手牌，无法直接核对决策时刻；请勿将动作后牌面当作评分输入。"));
    }
    if(snapshot?.cut_review&&!beforeHands&&afterHands){
      root.append(el("p","review-footnote",
        "本档案只有动作后手牌，没有可供核对的出牌前快照；前三推荐来自当时另行保存的评分。"));
    }
    if(!terminal){
      root.append(el("p","review-footnote",
        "旧档案只记录公开牌和牌背：当时各家暗手未保存，无法真实还原或计算逐巡最优切符合率。"));
    }
    if(snapshot?.cut_review){
      const cut=snapshot.cut_review;
      const head=el("p","match-archive-cut-note",
        "本巡你切 "+cut.discard+" · "+
        (cut.optimal?"符合并列最优方案":("未符合最优方案"+
        (cut.rank?"（排序第"+cut.rank+"）":""))));
      root.append(head);
      const comparison=cutQuality().inspect(cut);
      const desc=el("p","match-archive-cut-diagnosis",
        "与当巡最佳方案比较："+comparison.text);
      desc.classList.add("match-archive-cut-"+comparison.kind);
      root.append(desc);
      if(comparison.measured){
        const actual=cut.played_candidate||
          cut.top3.find(x=>x.tile===cut.discard);
        root.append(el("p","match-archive-cut-metrics",
          "实际切牌：向听"+actual.shanten+
          " · 有效张上界"+actual.effective_copies+
          (actual.fan_weighted===null?"":" · 基础番值加权"+
            actual.fan_weighted)));
      }
      const three=el("div","match-archive-cut-top3");
      three.append(el("strong","","当前公开信息下，切牌参考前三名："));
      cut.top3.forEach((cand,i)=>{
        three.append(el("span","",
          (i+1)+". 切"+cand.tile+
          " · 向听"+cand.shanten+
          " · 有效张上界"+cand.effective_copies+
          (cand.fan_weighted!==null?" · 番值加权"+cand.fan_weighted:"")+
          (cand.reference_best?"（最优）":"")));
      });
      root.append(three);
    }
    const groups=el("div","match-archive-four-seats");
    for(let seat=0;seat<4;seat++){
      const cell=el("div","match-archive-public-seat");
      const actual=shownHands?.[seat];
      cell.append(el("strong","",
        seat+"号"+(board.won[seat]?" · 已胡（动作后）":"")+
        " · 暗手"+(actual?actual.length:board.hand_counts[seat])+"张"+
        (shownPhase?"（动作"+(shownPhase==="before"?"前":"后")+"）":"")));
      const backs=el("div","match-archive-back-count");
      if(Array.isArray(actual)){
        const suit={m:"万",p:"筒",s:"条"};
        for(const tile of actual){
          const tileView=el("span","match-archive-revealed-tile",
            tile.slice(1)+(suit[tile[0]]||tile[0]));
          if(seat===0&&shownPhase==="before"&&
             snapshot?.cut_review?.discard===tile){
            tileView.classList.add("match-archive-actual-cut");
            tileView.setAttribute("title","本巡实际切出的牌型");
          }
          backs.append(tileView);
        }
        cell.append(el("small","", "终局复盘：当时真实手牌已公开"));
      }else{
        for(let i=0;i<board.hand_counts[seat];i++)
          backs.append(el("span","match-archive-back",""));
      }
      cell.append(backs);
      cell.append(el("p","",
        "公开副露："+board.melds[seat].map(m=>
          (m.type==="an_gang"?(m.revealed===true&&m.tile?
            "暗杠 "+m.tile+"（翻一张）":"暗杠（历史隐牌）"):
           (m.type==="peng"?"碰":m.type==="ming_gang"?"明杠":"补杠")+
           " "+m.tile)).join("、")||"无"));
      cell.append(el("p","",
        "牌河："+board.discards.filter(d=>d.seat===seat).map(d=>d.tile).join(" ")||
        "牌河为空"));
      groups.append(cell);
    }
    root.append(groups);
  }
  function renderSteps(){
    if(!opened)return;
    const seat=$("match-archives-seat").value||"all";
    const kind=$("match-archives-action").value||"all";
    const matching=playback().filterReviewEntries(frames,seat,kind);
    // A completed archive must permit tracing EVERY saved action, not
    // silently hide the first turns when a blood-battle has over 200 steps.
    // The server already bounds its archive at 2048 genuine public steps.
    const shown=matching;
    const count=$("match-archives-count");
    count.textContent="符合条件 "+matching.length+"步 · 全部可追溯";
    const root=$("match-archives-actions");
    root.replaceChildren();
    for(const f of shown){
      const b=makeButton("第"+f.sequence+"步 · "+f.label,()=>{
        active=f.sequence;handPhase="auto";renderSteps();
      });
      if(f.sequence===active)b.classList.add("is-selected");
      root.append(b);
    }
    if(!shown.some(f=>f.sequence===active))
      active=shown.length?shown[shown.length-1].sequence:null;
    for(const item of root.children){
      if(item.textContent.startsWith("第"+active+"步 · "))
        item.classList.add("is-selected");
    }
    renderArchiveBoard(shown.find(f=>f.sequence===active));
  }
  function renderCutTimeline(report){
    const root=$("match-archives-cut-timeline");
    if(!root)return;
    root.replaceChildren();
    const review=report?.terminal_review;
    const decisions=(review?.steps||[]).flatMap((step,index)=>
      step.cut_review?[{step:index+2,cut:step.cut_review}]:[]);
    if(!decisions.length){
      root.append(el("p","review-footnote",
        "本局无可用逐巡切牌评分；早期档案没有保存真实暗手，无法补算。"));
      return;
    }
    const header=el("strong","","我的逐巡切牌对照 · 共"+decisions.length+"巡");
    root.append(header);
    const choices=el("div","match-archive-cut-timeline-list");
    let optimal=0;
    decisions.forEach(({step,cut},index)=>{
      if(cut.optimal)optimal++;
      const rank=cut.rank?(" · 排名"+cut.rank):"";
      const qualityLabel=cutQuality().inspect(cut);
      const action=makeButton(
        "第"+(index+1)+"巡｜切"+cut.discard+
        "｜"+(cut.optimal?"符合最优":"可改进"+rank)+
        "｜"+qualityLabel.text+
        "｜前三："+cut.top3.map(x=>x.tile).join(" / "),
        ()=>{
          // Point into the exact saved public-state frame; retain history's
          // seat/action filters by switching to the complete public trace.
          $("match-archives-seat").value="all";
          $("match-archives-action").value="all";
          active=step;
          handPhase="auto";
          renderSteps();
          $("match-archives-board").scrollIntoView?.({
            behavior:"smooth",block:"nearest"
          });
        }
      );
      action.classList.add(cut.optimal?"is-optimal":"is-review");
      choices.append(action);
    });
    root.append(el("p","review-footnote",
      "已评估 "+decisions.length+" 巡 · 符合最优 "+
      optimal+" 巡 · 仍可改进 "+(decisions.length-optimal)+
      " 巡。点击任一巡可回到当时四家真实手牌和前三种切牌的逐步对照。"));
    root.append(choices);
  }
  async function openMatch(archiveId){
    try{
      $("match-archives-message").textContent="";
      const details=await api(uri(archiveId));
      const report=details.report;
      const start=playback().openingFrame(report.opening);
      const steps=playback().normalizeHistorySteps(
        report.steps||[],report.opening);
      frames=[...(start?[start]:[]),...steps]
        .map((frame,index)=>({...frame,sequence:index+1}));
      opened=details;active=null;handPhase="auto";
      $("match-archives-seat").value="all";
      $("match-archives-action").value="all";
      $("match-archives-detail").hidden=false;
      $("match-archives-title").textContent=
        "档案 "+archiveId+" · "+details.created_at;
      $("match-archives-detail-summary").textContent=
        (report.phase==="finished"?"三家胡牌结束":"牌山耗尽")+
        " · 庄家"+report.dealer+"号 · 自摸"+
        ({add_base:"加底",add_fan:"加番",legacy:"旧版"}[
          report.match_config?.self_draw_mode||"legacy"]||"未知")+
        " · "+report.steps.length+
        "个已保存动作快照 · "+report.win_ledger.wins.length+
        "笔胡牌"+(report.exhaustive_settlement?.posted?
          " · "+report.exhaustive_settlement.entries.length+
          "笔方案A流局赔付已入账":
          " · 无已入账流局赔付")+
        (report.truncated?" · 最早省略"+report.truncated+"步":"");
      $("match-archives-export").href=uri(archiveId);
      $("match-archives-export").download="mahtrain_"+archiveId+".json";
      const score=$("match-archives-balances");score.replaceChildren();
      const exhaustive=report.exhaustive_settlement;
      // Pre-settled_b0 JSON may have no combined total. Reconstruct ONLY
      // previously official HU + posted draw, never promote trial kongs.
      const official=Array.isArray(report.settled_balances)&&
        report.settled_balances.length===4?report.settled_balances:
        report.win_ledger.balances.map((n,i)=>n+
          (exhaustive?.posted?exhaustive.balances[i]:0));
      report.win_ledger.balances.forEach((n,i)=>score.append(
        el("span","match-archive-balance",
          i+"号正式净额 "+sign(official[i])+
          "（胡牌 "+sign(n)+"；"+
          (report.kong_included?"已入账杠钱 ":"旧局试验杠钱 ")+
          sign(report.kong_balances?.[i]||0)+"）")));
      if(exhaustive){
        const status=el("p","match-net",
          exhaustive.posted?
          "方案A流局正式结算："+exhaustive.balances.map((n,i)=>
            i+"号"+sign(n)).join(" · "):
          "流局异常牌形待核验，未执行流局赔付");
        score.append(status);
      }
      const wins=$("match-archives-wins");wins.replaceChildren();
      for(const w of report.win_ledger.wins)wins.append(el("p","",
        w.winner+"号"+(winType[w.kind]||"胡牌")+
        " · "+w.main_pattern+" · "+w.effective_fan+
        "番 · 实收 "+sign(w.total_received)+
        " · 付款 "+w.payers.join("、")+"号"));
      if(exhaustive?.posted){
        for(const e of exhaustive.entries)wins.append(el("p","",
          "流局"+(e.stage==="flower_pig"?"查花猪":"查大叫")+
          " · "+e.payer+"号付"+e.recipient+"号 "+
          e.amount+(e.stage==="da_jiao"?
            " · "+e.effective_fan+"番":"")));
      }
      const review=report.terminal_review;
      const cuts=(review?.steps||[]).map(x=>x.cut_review).filter(Boolean);
      const reviewed=cuts.length;
      const optimal=cuts.filter(x=>x.optimal).length;
      const heading=$("match-archives-review-summary");
      heading.replaceChildren();
      heading.append(el("strong","","整局最优切符合率："+(reviewed?
        (optimal/reviewed*100).toFixed(1)+"%（"+optimal+"/"+reviewed+"巡）":
        "不可计算")));
      heading.append(el("p","",reviewed?
        "按每次出牌前己方手牌与当时公开信息，用向听数优先、有效进张与听牌番值加权排序；并列第一也视为符合。此项不是完全信息下的保证最优策略。":
        "本局缺少可验证的逐巡切牌数据，不能根据最终胜负推测最优切符合率。"));
      const stages=$("match-archives-stage-summary");
      if(stages){
        stages.replaceChildren();
        if(reviewed){
          stages.append(el("strong","","整局切牌质量分段 · 按已记录切牌顺序均分"));
          for(const part of cutQuality().thirds(cuts)){
            const card=el("div","match-archive-stage-card");
            card.append(el("strong","",part.name+
              " · 符合最优 "+part.optimal+"/"+part.total));
            card.append(el("span","",
              "退向听 "+part.regressed+" 巡 · 同向听有效张损失 "+
              part.ukeireLoss+" 巡 · 听牌番值权重落后 "+
              part.weightedLoss+" 巡"));
            if(part.unrated)card.append(el("small","",
              "历史指标缺失 "+part.unrated+" 巡，不强行补算"));
            stages.append(card);
          }
          stages.append(el("p","review-footnote",
            "有效张与番值都是当时公开信息下的未知张数上界比较；不是胡牌概率、实际剩余墙牌或确定可得的分数。"));
        }
      }
      renderCutTimeline(report);
      renderSteps();
    }catch(err){fail(err)}
  }
  function init(){
    $("match-archives-period")?.addEventListener("change",refresh);
    $("match-history-groups-mode").addEventListener("change",renderGroupings);
    $("match-archives-refresh").addEventListener("click",refresh);
    $("match-archives-compare").addEventListener("click",comparison);
    for(const id of ["match-archives-seat","match-archives-action"]){
      $(id).addEventListener("change",()=>{active=null;handPhase="auto";renderSteps()});
    }
    refresh();
  }
  window.MahTrainMatchArchives={init,refresh};
})();
