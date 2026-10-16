"use strict";
/* M3 LOCAL FOUR-SEAT OPENING DEMO, NOT A FULL BLOOD-BATTLE MATCH.
   Other three seats use transparent scripted behavior; discards deliberately
   bypass all pong/kong/ron responses using demo-only all-pass.
*/
(function(){
  const $=id=>document.getElementById(id);
  let token=null,table=null,selected=new Set(),busy=false;
  const names={m:"万",s:"条",p:"筒"};
  const directions={clockwise:"顺时针",counterclockwise:"逆时针",opposite:"对家"};
  const tileName=t=>window.MahTrainUI.tileName(t);
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
  async function request(action,fields){
    if(busy)return;
    busy=true;
    try{
      const response=await fetch("/api/action",{
        method:"POST",
        headers:{"Content-Type":"application/json","X-MahTrain":"1"},
        body:JSON.stringify({action,...fields}),
      });
      const result=await response.json();
      if(!response.ok)throw new Error(result.error||"四人开局演示操作失败");
      token=result.table_token;
      table=result.table;
      selected.clear();
      render();
    }catch(err){
      $("table-error").textContent=err.message||String(err);
    }finally{busy=false;}
  }
  function launch(){
    const seed=Number($("table-seed").value);
    return request("table_new",{seed});
  }
  function choice(index){
    if(!table || table.phase!=="exchange_select" || busy)return;
    if(selected.has(index)){selected.delete(index);render();return;}
    const suit=table.hand[index][0];
    if(selected.size===3){
      $("table-error").textContent="只能选择3张牌；请先取消一张。";
      return;
    }
    if(selected.size && [...selected].some(i=>table.hand[i][0]!==suit)){
      $("table-error").textContent="换三张必须是同一花色，请先取消不同花色的牌。";
      return;
    }
    selected.add(index);
    render();
  }
  function makeTile(tile,onClick,chosen=false){
    const e=window.MahTrainUI.tileElement(tile,{
      selectable:typeof onClick==="function",onClick,
    });
    if(chosen)e.classList.add("table-selected");
    if(!onClick)e.disabled=true;
    return e;
  }
  function render(){
    if(!table)return;
    $("table-error").textContent="";
    $("table-stage").hidden=false;
    const stage={
      exchange_select:"① 已发牌，请从自己的暗手牌选3张同花色牌",
      missing_select:"② 四家换牌完成，查看换后手牌并盖牌定缺",
      dealer_discard:"③ 定缺揭示，庄家先切牌（不先摸牌）",
      await_discard:"③ 轮到你切牌（其他三家为脚本模拟）",
      claim_window:"弃牌响应窗口（此演示尚未实现碰杠胡）",
      await_draw:"等候下一家摸牌",
      wall_exhausted:"演示牌墙已摸尽（暂无血战结算）",
    };
    $("table-stage-title").textContent=stage[table.phase]||table.phase;
    $("table-topline").textContent=
      "你的座位：0 · 庄家："+table.dealer+" · 换牌方向："+directions[table.exchange_direction]+
      " · 牌墙剩余："+table.wall_count+"张";
    const board=$("table-hand");board.replaceChildren();
    table.hand.forEach((tile,i)=>{
      const callback=table.phase==="exchange_select"
        ?()=>choice(i)
        :((table.phase==="dealer_discard"||table.phase==="await_discard")
          &&table.turn===0)
        ?()=>request("table_discard",{table_token:token,tile})
        :null;
      board.append(makeTile(tile,callback,selected.has(i)));
    });
    const submit=$("table-controls");submit.replaceChildren();
    if(table.phase==="exchange_select"){
      const suits=new Set([...selected].map(i=>table.hand[i][0]));
      submit.append(el("p","review-intro",
        "你已选："+selected.size+"/3张；必须来自同一门花色。四位玩家选齐后才会同时交换。"));
      const btn=button("确认盖牌换三张","primary",
        ()=>request("table_exchange",{
          table_token:token,
          tiles:[...selected].sort((a,b)=>a-b).map(i=>table.hand[i]),
        }));
      btn.disabled=selected.size!==3||suits.size!==1;
      submit.append(btn);
    }else if(table.phase==="missing_select"){
      const counts={m:0,s:0,p:0};
      table.hand.forEach(t=>counts[t[0]]++);
      if(table.tianque){
        submit.append(el("p","review-intro",
          "换后仅有两门牌：符合天缺，可直接定未持有的花色。"));
      }
      submit.append(el("p","review-intro",
        "盖牌定缺只声明花色，不从手里扣掉实体麻将牌；四家全提交后才揭示。"));
      for(const suit of ["m","s","p"]){
        const b=button("定缺"+names[suit]+"（现持"+counts[suit]+"张）",
          "review-control",()=>request("table_missing",{
            table_token:token,suit,
          }));
        submit.append(b);
      }
    }else if(table.phase==="dealer_discard"||table.phase==="await_discard"){
      submit.append(el("p","review-intro",
        "现在点击自己的手牌切牌。请注意：本版本只是轮转演示，"+
        "不处理其他玩家的碰、杠、胡或番数结算。"));
    }else{
      submit.append(el("p","review-intro",
        "这轮演示结束。可以输入新种子重新查看不同的四人开局。"));
    }
    const info=$("table-public");
    info.replaceChildren();
    if(table.missing_suits){
      info.append(el("p","review-intro",
        "四家同时定缺："+table.missing_suits.map(
          (s,i)=>i+"号缺"+names[s]
        ).join("；")));
    }else{
      info.append(el("p","review-intro",
        "换三张提交："+table.exchange_submitted.length+"/4；定缺提交："+
        table.missing_submitted.length+"/4。其他人的手牌和密封选牌不可查看。"));
    }
    info.append(el("p","review-intro","各家暗手张数："+table.hand_counts.map(
      (n,i)=>i+"号"+n+"张"
    ).join("，")));
    const log=el("div","table-discard-log");
    log.append(el("strong","","已公开弃牌"));
    if(table.discards.length){
      for(const item of table.discards){
        const cell=el("div","table-discard-item");
        cell.append(el("span","",item.seat+"号"));
        cell.append(makeTile(item.tile,null));
        log.append(cell);
      }
    }else{
      log.append(el("p","review-intro","暂无弃牌。"));
    }
    info.append(log);
  }
  function init(){
    $("table-new").addEventListener("click",launch);
  }
  window.MahTrainTableDemo={init};
})();
