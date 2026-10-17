"use strict";
/* M3.22: read-only browser for server-generated completed public archives. */
(function(){
  const $=id=>document.getElementById(id);
  const playback=()=>window.MahTrainPlayback;
  let listed=[],opened=null,selected=new Set(),frames=[],active=null;
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
          (m.type==="an_gang"?"暗杠（隐牌）":
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
        " · 庄家"+report.dealer+"号 · "+report.steps.length+
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
    $("match-archives-refresh").addEventListener("click",refresh);
    $("match-archives-compare").addEventListener("click",comparison);
    for(const id of ["match-archives-seat","match-archives-action"]){
      $(id).addEventListener("change",()=>{active=null;renderSteps()});
    }
    refresh();
  }
  window.MahTrainMatchArchives={init,refresh};
})();
