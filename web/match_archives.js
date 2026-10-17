"use strict";
/* M3.22: read-only browser for server-generated completed public archives. */
(function(){
  const $=id=>document.getElementById(id);
  const playback=()=>window.MahTrainPlayback;
  let listed=[],opened=null,selected=new Set(),frames=[],active=null;
  let lastGrouping=null;
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
    const title=el("strong","","已完成对局比较 · 0号正式净额（胡牌 + 已入账流局）");
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
      "（第一局减第二局；正式积分=胡牌+已入账方案A流局赔付，不含模拟杠钱）"));
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
    try{
      $("match-archives-message").textContent="";
      const response=await api("/api/match_archives?limit=50");
      listed=response.matches||[];
      selected=new Set([...selected].filter(id=>
        listed.some(x=>x.archive_id===id)));
      $("match-archives-summary").textContent=
        "已保存 "+response.summary.games+" 局 · 0号平均正式净额 "+
        Number(response.summary.average_player0_settled_balance??
          response.summary.average_player0_win_balance).toFixed(1)+
        "（平均胡牌 "+Number(
          response.summary.average_player0_win_balance).toFixed(1)+"）"+
        " · 累计 "+response.summary.paid_wins+"笔胡牌";
      renderList();
      renderScorecard(response.scorecard);
      lastGrouping=response.scorecard?.groupings||null;
      renderGroupings();
    }catch(err){fail(err)}
  }
  function renderArchiveBoard(frame){
    const root=$("match-archives-board");
    root.replaceChildren();
    if(!frame||!frame.board){
      root.append(el("p","","请选择一项公开历史动作。"));return;
    }
    const board=frame.board;
    root.append(el("strong","","第"+frame.sequence+"步 · "+frame.label+
      " · 牌山"+board.wall_count+"张"));
    const groups=el("div","match-archive-four-seats");
    for(let seat=0;seat<4;seat++){
      const cell=el("div","match-archive-public-seat");
      cell.append(el("strong","",
        seat+"号"+(board.won[seat]?" · 已胡":"")+
        " · 暗手"+board.hand_counts[seat]+"张"));
      const backs=el("div","match-archive-back-count");
      // Pure backs, not the saved values of concealed cards.
      for(let i=0;i<board.hand_counts[seat];i++)
        backs.append(el("span","match-archive-back",""));
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
    const shown=matching.slice(-200);
    const count=$("match-archives-count");
    count.textContent="符合条件 "+matching.length+"步"+
      (matching.length>shown.length?" · 仅列最后200条":"");
    const root=$("match-archives-actions");
    root.replaceChildren();
    for(const f of shown){
      const b=makeButton("第"+f.sequence+"步 · "+f.label,()=>{
        active=f.sequence;renderSteps();
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
      opened=details;active=null;
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
      report.win_ledger.balances.forEach((n,i)=>score.append(
        el("span","match-archive-balance",i+"号胡牌已入账 "+sign(n)+
          "（独立杠钱试验额 "+
          sign(report.kong_balances[i])+"）")));
      const exhaustive=report.exhaustive_settlement;
      if(exhaustive){
        const status=el("p","match-net",
          exhaustive.posted?
          "方案A流局正式结算："+exhaustive.balances.map((n,i)=>
            i+"号"+sign(n)).join(" · "):
          "流局异常牌形待核验，未执行流局赔付");
        score.append(status);
        if(exhaustive.posted){
          score.append(el("p","review-footnote",
            "正式已入账合计："+report.settled_balances.map((n,i)=>
              i+"号"+sign(n)).join(" · ")+"（不含独立模拟杠钱）"));
        }
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
      renderSteps();
    }catch(err){fail(err)}
  }
  function init(){
    $("match-history-groups-mode").addEventListener("change",renderGroupings);
    $("match-archives-refresh").addEventListener("click",refresh);
    $("match-archives-compare").addEventListener("click",comparison);
    for(const id of ["match-archives-seat","match-archives-action"]){
      $(id).addEventListener("change",()=>{active=null;renderSteps()});
    }
    refresh();
  }
  window.MahTrainMatchArchives={init,refresh};
})();
