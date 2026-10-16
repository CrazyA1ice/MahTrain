"use strict";
/* M3.2 LOCAL rule-state experimental match. Seat zero only; three scripted
   opponents, no AI skill, payment, flower-pig or end-wall settlement.
*/
(function(){
  const $=id=>document.getElementById(id);
  const names={m:"万",s:"条",p:"筒"};
  const directions={clockwise:"顺时针",counterclockwise:"逆时针",opposite:"对家"};
  const actionNames={hu:"胡这张",peng:"碰",ming_gang:"明杠",pass:"过",an_gang:"暗杠",bu_gang:"补杠"};
  let token=null,state=null,choice=new Set(),busy=false;
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
      token=data.match_token;state=data.match;choice.clear();render();
    }catch(err){
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
    state.hand.forEach((tile,i)=>{
      let onclick=null;
      if(phase==="exchange_select")onclick=()=>toggle(i);
      if((phase==="dealer_discard"||phase==="await_discard")&&state.turn===0)
        onclick=()=>action("match_discard",{tile});
      hand.append(card(tile,onclick,choice.has(i)));
    });
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
        "请点击自己的麻将切牌。其他三家是固定脚本，不是智能AI；合法胡牌将即时记录部分积分流水。"));
    }else{
      controls.append(el("p","review-intro",
        "本局摸切已结束。胡牌部分已计算，杠钱撤销及流局赔付尚未计入完整结算。可以重新开一局。"));
    }
    const publicInfo=$("match-public");publicInfo.replaceChildren();
    if(state.missing_suits){
      publicInfo.append(el("p","review-intro",
        "四家定缺："+state.missing_suits.map((s,i)=>i+"号缺"+names[s]).join(" · ")));
    }
    publicInfo.append(el("p","review-intro",
      "各家暗手牌张数："+state.hand_counts.map((v,i)=>
        i+"号"+v+"张"+(state.won[i]?"（已胡）":"")).join("，")));
    const myMelds=el("div","match-melds");
    myMelds.append(el("strong","","自己的副露区（已锁定，不可再出牌）"));
    if(!state.own_melds.length)myMelds.append(el("p","review-intro","尚无碰或杠。"));
    for(const m of state.own_melds){
      const row=el("div","match-meld");
      row.append(el("span","",actionNames[m.type]||m.type));
      const num=m.type==="peng"?3:4;
      for(let n=0;n<num;n++)row.append(card(m.tile,null,false));
      myMelds.append(row);
    }
    publicInfo.append(myMelds);
    const discards=el("div","match-discards");
    discards.append(el("strong","","公开弃牌记录"));
    for(const entry of state.discards.slice(-24)){
      const cell=el("div","match-discard");
      cell.append(el("span","",entry.seat+"号"+(entry.claimed_by!==undefined?"·已被碰杠":
        entry.won_by?"·已点炮":"")));
      cell.append(card(entry.tile,null,false));discards.append(cell);
    }
    if(!state.discards.length)discards.append(el("p","review-intro","暂无弃牌。"));
    publicInfo.append(discards);
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
        score.append(el("p","match-unpriced",
          "杠钱待定："+state.pending_kong_payments.length+
          "笔（底分与杠作废撤销规则尚需确认，暂未计入余额）。"));
      }
      score.append(el("p","review-footnote",
        "此处展示已确认的胡牌付款，不是现金账户；流局查花猪、大叫尚未实现。"));
      publicInfo.append(score);
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
    $("match-new").addEventListener("click",()=>{
      const seed=Number($("match-seed").value);
      action("match_new",{seed,
        room_coefficient:Number($("match-coefficient").value),
        fan_cap:Number($("match-fan-cap").value),
      });
    });
  }
  window.MahTrainMatch={init};
})();
