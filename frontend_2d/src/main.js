/* Original kobalab/Majiang UI components; MahTrain Python is the only game authority. */
import $ from "jquery";
import MajiangTile from "@kobalab/majiang-ui/lib/pai.js";
import MajiangShoupai from "@kobalab/majiang-ui/lib/shoupai.js";
import MajiangHe from "@kobalab/majiang-ui/lib/he.js";
import {SESSION_KEY,convertView,choiceAction} from "./bridge.mjs";
import {publicActions,recentWins,winTitle} from "./settlement.mjs";
import {renderSettlement} from "./report.mjs";
import {seatOutcome} from "./seat-status.mjs";
import {claimDecision,ownKongChoices} from "./action-choice.mjs";
import {renderClassicHint,renderClassicOperationHint} from "./hint-view.mjs";
import {renderKongMeld} from "./kong-view.mjs";
const CLS=["main","xiajia","duimian","shangjia"];
const SUIT={m:"万",p:"筒",s:"条"};
const TURN=new Set(["dealer_discard","await_discard"]);
const DONE=new Set(["finished","wall_exhausted"]);
const el=id=>document.getElementById(id);
let token=null,state=null,pai=null,busy=false,timer=null,voice=null;
let terminalScrollTimeout=null;
let hintSource=null,hintReport=null,hintBusy=false;
let operationSource=null,operationReport=null,operationRequested=null;
const selected=new Set();
function status(t){el("classic-status").textContent=t}
function initializeVoice(){
 // Reuse the EXISTING tested MahTrain Mandarin speech module; no remote
 // audio downloads and no Japanese rule engine. Speech never blocks AI.
 const factory=window.MahTrainMatchVoice;
 voice=factory?.create?.(window)||null;
 const toggle=el("classic-voice-toggle"),repeat=el("classic-voice-repeat");
 const rate=el("classic-voice-rate");
 if(!voice?.supported){
  toggle.textContent="浏览器不支持中文语音";
  toggle.disabled=true;repeat.disabled=true;rate.disabled=true;
  return;
 }
 function sync(){
  const enabled=voice.getEnabled();
  toggle.textContent=enabled?"语音：开":"语音：关";
  toggle.setAttribute("aria-pressed",String(enabled));
  repeat.disabled=!voice.canRepeat();
 }
 toggle.onclick=()=>{voice.setEnabled(!voice.getEnabled());sync()};
 repeat.onclick=()=>{voice.repeatLast();sync()};
 rate.onchange=()=>{voice.setRate(rate.value);sync()};
 sync();
}
function renderWins(){
 const ticker=el("classic-win-announcement");
 const wins=Array.isArray(state?.win_ledger?.wins)?state.win_ledger.wins:[];
 ticker.hidden=!wins.length;
 ticker.replaceChildren();
 for(const item of wins){
  const row=document.createElement("div");
  row.className="classic-win-record";
  const strong=document.createElement("strong");
  strong.textContent=winTitle(item);
  row.append(strong);
  ticker.append(row);
 }
}
function announceResponse(previous,current,steps,isRestore){
 if(!voice||isRestore)return;
 const events=publicActions(steps);
 if(events.length)voice.announceEvents(events.slice(-1));
 else if(recentWins(previous,current).length)
  voice.announceEvents([{type:"self_draw_win"}]);
 const repeat=el("classic-voice-repeat");
 repeat.disabled=!voice.canRepeat();
}

function saved(){try{return sessionStorage.getItem(SESSION_KEY)}catch{return null}}
function store(){try{
 // A completed 四川血战 match is still a valid read-only archive view.
 // Keep its same-tab token until the player EXPLICITLY starts another game,
 // otherwise refreshing after Hu silently opens an unrelated fresh round and
 // loses the final settlement and every persistent winner marker.
 if(token&&state)sessionStorage.setItem(SESSION_KEY,token);
 else sessionStorage.removeItem(SESSION_KEY);
}catch{}}
function clearOperationHint(){
 operationSource=null;operationReport=null;operationRequested=null;
 renderClassicOperationHint(el("classic-operation-hint-panel"),null);
}
function operationWindow(view){
 if(!view||view.seat!==0||view.won?.[0])return false;
 if(["claim_window","rob_kong_window"].includes(view.phase)){
  const options=view.phase==="claim_window"?view.claim_options:view.rob_options;
  const pending=view.phase==="claim_window"?view.pending_discard:view.pending_rob_kong;
  return pending?.seat!==0&&!view.claim_submitted?.includes(0)&&
   options?.some(x=>x!=="pass");
 }
 return TURN.has(view.phase)&&view.turn===0&&
  (view.can_self_draw_win||view.kong_options?.length>0);
}
async function loadOperationHint(snapshot){
 if(operationRequested===snapshot)return;
 operationRequested=snapshot;
 const currentToken=token;
 try{
  const response=await fetch("/api/action",{
   method:"POST",headers:{"Content-Type":"application/json","X-MahTrain":"1"},
   body:JSON.stringify({action:"match_operation_hint",
                        match_token:currentToken}),
  });
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"碰杠胡参考暂不可用");
  if(snapshot!==state||currentToken!==token)return;
  if(result.hint?.status!=="choose_operation")throw Error("操作建议格式异常");
  operationSource=snapshot;operationReport=result.hint;
  renderClassicOperationHint(el("classic-operation-hint-panel"),operationReport);
  draw();
 }catch(err){
  if(snapshot===state)status("操作参考暂不可用："+err.message);
 }
}
function currentOperationLabel(){
 if(operationSource!==state||!operationReport)return null;
 return operationReport.candidates?.find(x=>x.reference_best)?.label||null;
}
function clearHint(){
 hintSource=null;hintReport=null;
 renderClassicHint(el("classic-hint-panel"),null);
 el("classic-hint-trigger").textContent="查看当前牌效参考";
}
async function toggleHint(){
 if(hintBusy||!state)return;
 if(hintReport&&hintSource===state){clearHint();draw();return}
 const current=state,currentToken=token;
 if(!TURN.has(current.phase)||current.turn!==0||current.won?.[0])return;
 hintBusy=true;
 el("classic-hint-trigger").disabled=true;
 el("classic-hint-trigger").textContent="正在计算…";
 try{
  const response=await fetch("/api/action",{
   method:"POST",headers:{"Content-Type":"application/json","X-MahTrain":"1"},
   body:JSON.stringify({action:"match_hint",match_token:currentToken}),
  });
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"牌效计算失败");
  if(current!==state||currentToken!==token)return;
  if(!result.hint||result.match_token!==currentToken)
   throw Error("牌效返回会话不匹配");
  hintSource=current;hintReport=result.hint;
  renderClassicHint(el("classic-hint-panel"),hintReport);
  el("classic-hint-trigger").textContent="收起牌效参考";
  draw();
 }catch(err){
  if(current===state)status("牌效暂不可用："+err.message);
 }finally{
  hintBusy=false;
  if(!hintReport)el("classic-hint-trigger").textContent="查看当前牌效参考";
  if(state)draw();
 }
}
function setupImages(){
 const rack=el("loaddata");
 for(const s of ["m","p","s"])for(let n=1;n<=9;n++){
  const img=document.createElement("img");img.className="pai";
  img.dataset.pai=s+n;img.src="/classic/img/"+s+n+".gif";rack.append(img);
 }
 const back=document.createElement("img");back.className="pai";
 back.dataset.pai="_";back.src="/classic/img/pai.gif";rack.append(back);
}
function resize(){
 const width=window.innerWidth-12;
 // The classic table is sized ONLY from viewport/toolbar geometry. Public
 // discard/kong/win events MUST NOT affect the table position or its scale.
 const height=window.innerHeight-el("classic-toolbar").getBoundingClientRect().height-45;
 const scale=Math.max(.31,Math.min(1.32,width/800,height/680));
 el("classic-board-host").style.width=800*scale+"px";
 el("classic-board-host").style.height=680*scale+"px";
 el("board").style.transform="scale("+scale+")";
}
function btn(label,callback,primary=false,disabled=false){
 const b=document.createElement("button");b.type="button";b.textContent=label;
 b.onclick=callback;b.disabled=disabled;
 if(primary)b.className="action-primary";
 return b;
}
function center(title,buttons){
 const node=el("classic-center-actions");
 node.hidden=!buttons.length;
 el("classic-score").style.visibility=buttons.length?"hidden":"visible";
 if(!buttons.length){
  el("classic-actions-title").textContent="";
  el("classic-actions-buttons").replaceChildren();
  return;
 }
 el("classic-actions-title").textContent=title;
 el("classic-actions-buttons").replaceChildren(...buttons);
}
function draw(){
 if(!state)return;
 const view=convertView(state);
 for(let s=0;s<4;s++){
  const cls=CLS[s];
  // A full four-meld hand has only two physical concealed tiles left.
  // Mark its fixed-width rack BEFORE the native redraw/adjust, so the
  // local-side compact kong measurements cannot push melds to a 2nd row.
  $(".shoupai."+cls).attr("data-meld-count",String(view.redactions[s].length));
  new MajiangShoupai($(".shoupai."+cls),pai,view.hands[s],s===0)
    .redraw(s===0).adjust();
  $(".shoupai."+cls+" .fulou .mianzi").each((i,node)=>{
   const meld=view.redactions[s][i];
   if(!meld)return;
   if(["an_gang","ming_gang","bu_gang"].includes(meld.kind)){
    // Native Majiang notation rotates every claimed tile by a seat-fixed
    // sign. Replace only kong DOM, using the real PUBLIC claimed-discard
    // source to orient the sideways fourth tile within this seat's frame.
    renderKongMeld(node,meld,s);
    return;
   }
   if(!meld.hidden)return;
   $("img.pai",node).each((_,img)=>{
    img.src="/classic/img/pai.gif";img.dataset.pai="_";
    img.alt="未公开的暗杠";img.removeAttribute("title");
   });
  });
  new MajiangHe($(".he."+cls),pai,view.rivers[s],true).redraw(true);
  $(".he."+cls+" .dapai img.pai").each((i,node)=>{
   if(view.rivers[s].claimed[i])node.classList.add("claimed");
  });
  const missing=state.missing_suits?.[s];
  const suffix=missing?" · 缺"+SUIT[missing]:" · 待定缺";
  const plate=el("classic-player-"+s);
  const outcome=seatOutcome(state,s);
  plate.replaceChildren();
  const playing=["dealer_discard","await_discard","await_draw"].includes(state.phase)
      && state.turn===s && !state.won?.[s];
  plate.classList.toggle("classic-seat-active",playing);
  plate.classList.toggle("classic-seat-dealer",state.dealer===s);
  plate.setAttribute("aria-label",
    (s===0?"你":s+"号AI")+(state.dealer===s?"，本局庄家":"")+
    (playing?"，当前行动玩家":"")+(outcome.won?"，已胡牌":""));
  const avatar=document.createElement("span");
  avatar.className="classic-seat-avatar classic-seat-avatar-"+s;
  avatar.textContent=s===0?"我":String(s);
  avatar.setAttribute("aria-hidden","true");
  plate.append(avatar);
  const playerName=document.createElement("span");
  playerName.className="classic-seat-name";
  playerName.textContent=(s===0?"自己":s+"号AI")+suffix;
  plate.append(playerName);
  plate.classList.toggle("classic-seat-won",outcome.won);
  if(outcome.won){
   const badge=document.createElement("span");
   badge.className="classic-won-badge";
   badge.textContent=outcome.label;
   badge.title=outcome.detail;
   badge.setAttribute("aria-label",outcome.detail);
   plate.append(badge);
  }
  // The fixed-size black central scoreboard retains the Hu pattern, not
  // a dynamically inserted announcement that pushes the entire table.
  const score=el("classic-score-"+s);
  score.textContent=s+"号"+(outcome.won?
   " · 已胡 "+outcome.center:suffix+" · "+state.hand_counts[s]+"张");
  score.title=outcome.won?outcome.detail:"";
  score.classList.toggle("classic-score-won",outcome.won);
  score.classList.toggle("lunban",playing);
 }
 el("classic-wall-count").textContent=String(state.wall_count??"—");
 el("classic-round").textContent="第"+String(state.series_round??1)+"局 · 血战到底";
 el("classic-dealer").textContent=String(state.dealer??"—")+"号";
 el("classic-dealer").title=state.dealer_origin||"首局随机庄";
 const nodes=[...document.querySelectorAll(".shoupai.main .bingpai > img.pai"),
  ...document.querySelectorAll(".shoupai.main .bingpai .zimo img.pai")];
 if(nodes.length!==view.indexed.length){
  status("手牌显示不匹配，已禁用出牌");console.error("Hand size mismatch",nodes.length,view.indexed.length);
 }else nodes.forEach((img,i)=>{
  const info=view.indexed[i];img.dataset.handIndex=info.index;
  img.dataset.tile=info.value;
  img.setAttribute("tabindex","0");img.setAttribute("role","button");
  img.setAttribute("aria-label",info.value+(info.fromDraw?"摸牌":"手牌"));
  img.classList.toggle("is-picked",selected.has(info.index));
  img.classList.toggle("is-draw",!!info.fromDraw);
  img.classList.toggle("is-hint-cut",hintSource===state&&
   !!hintReport?.candidates?.some(x=>x.reference_best&&x.discard===info.value));
 });
 let buttons=[];
 if(state.phase==="exchange_select"){
  const chosen=[...selected].map(i=>state.hand[i]);
  const legal=chosen.length===3&&chosen.every(t=>t[0]===chosen[0][0]);
  buttons=[
   btn("确认换三张 "+selected.size+"/3",()=>void submit({
    action:"match_exchange",tiles:chosen}),true,!legal||busy),
   btn("清空",()=>{selected.clear();draw()},false,!selected.size)
  ];
  center("换三张：点击三张同花色手牌",buttons);
  status("点击手牌选择三张，中央确认");
 }else if(state.phase==="missing_select"){
  buttons=["m","p","s"].map(s=>btn("缺"+SUIT[s],()=>void submit({
   action:"match_missing",suit:s}),false,busy));
  center("定缺：选择一门花色",buttons);status("请选择定缺花色");
 }else if(["claim_window","rob_kong_window"].includes(state.phase)){
  const decision=claimDecision(state);
  if(decision){
   buttons=decision.choices.map(choice=>{
    const control=btn(choice.label,()=>void submit(choice.command),
      choice.primary,busy);
    control.title=choice.explanation;
    return control;
   });
  }
  center((decision?.title||"")+
   (currentOperationLabel()?" · 参考："+currentOperationLabel():""),buttons);
  status(decision?"请选择合法操作；也可以点「过」":"等待其他玩家响应");
 }else if(TURN.has(state.phase)&&state.turn===0){
  if(state.can_self_draw_win)buttons.push(btn("自摸胡",()=>run("win"),true,busy));
  for(const offer of ownKongChoices(state)){
   const button=btn(offer.label,()=>void submit(offer.command),false,busy);
   button.title="可以不杠，直接点选手牌出牌";
   buttons.push(button);
  }
  center((buttons.length?"可自摸或杠，也可直接出牌":"")+
   (currentOperationLabel()?" · 参考："+currentOperationLabel():""),buttons);
  status("点击手牌选中、再点同一张打出；按 Esc 可取消选牌");
 }else if(DONE.has(state.phase)){
  const next=state.next_dealer;
  const dealerNote=next?" · 下局庄家 "+next.dealer+"号（"+next.label+"）":"";
  center("本局结束"+dealerNote,[
   btn("查看结算",()=>el("classic-result-report").scrollIntoView({
    behavior:"smooth",block:"start",
   }),true),
   btn("下一局 · 继承庄家",()=>void submit({action:"match_next"}),false,busy),
  ]);
  status("本局结束"+dealerNote);
 }else {center("",[]);status("AI 行动中 · 等待服务器同步")}
 const available=TURN.has(state.phase)&&state.turn===0&&
  state.won?.[0]!==true;
 el("classic-hint-trigger").disabled=!available||hintBusy;
 renderWins();
 renderSettlement(el("classic-result-report"),state);
 if(operationWindow(state)&&operationRequested!==state){
  void loadOperationHint(state);
 }
 resize();
}
function focusTile(index){
 // Shoupai.redraw() replaces the original GIF nodes. Restore keyboard
 // focus to the SAME physical copy, including duplicate and drawn tiles.
 const replacement=document.querySelector(
  '.shoupai.main .bingpai [data-hand-index="'+index+'"]');
 replacement?.focus({preventScroll:true});
}
function selectHand(node,restoreKeyboardFocus=false){
 if(busy||!state)return;
 const i=Number(node?.dataset.handIndex);
 if(!Number.isInteger(i)||i<0||i>=state.hand.length)return;
 if(state.phase==="exchange_select"){
  if(selected.has(i))selected.delete(i);
  else if(selected.size<3)selected.add(i);
  draw();
  if(restoreKeyboardFocus)focusTile(i);
 }else if(TURN.has(state.phase)&&state.turn===0){
  const cmd=choiceAction(state,"discard",{index:i});if(!cmd)return;
  if(selected.has(i))void submit(cmd);
  else{
   selected.clear();selected.add(i);draw();
   if(restoreKeyboardFocus)focusTile(i);
  }
 }
}
function run(kind,details={}){
 const cmd=choiceAction(state,kind,details);if(cmd)void submit(cmd);
}
async function api(cmd){
 const payload={...cmd};
 if(cmd.action!=="match_new"){
  if(!token)throw Error("会话不存在，请重新开局");
  payload.match_token=token;
 }else Object.assign(payload,{ai_levels:["challenge","challenge","challenge"],
  self_draw_mode:"add_base"});
 const response=await fetch("/api/action",{method:"POST",
  headers:{"Content-Type":"application/json","X-MahTrain":"1"},body:JSON.stringify(payload)});
 const result=await response.json();
 if(!response.ok)throw Error(result.error||"服务器拒绝操作");
 if(typeof result.match_token!=="string"||result.match?.seat!==0)
  throw Error("对局身份异常，停止同步");
 return result;
}
function advance(){
 if(timer!==null)clearTimeout(timer);
 if(state?.needs_continue && !DONE.has(state.phase))
  timer=setTimeout(()=>void submit({action:"match_continue"}),240);
}
async function submit(cmd){
 if(busy)return;
 busy=true;if(timer!==null)clearTimeout(timer);
 try{
  const newRound=["match_new","match_next"].includes(cmd.action);
  const previous=newRound?null:state;
  const result=await api(cmd);
  token=result.match_token;state=result.match;selected.clear();
  // A change of turn/hand invalidates all reference counts, even if the
  // same tile values later recur. Do not show stale advice after a move.
  clearHint();
  clearOperationHint();
  if(newRound){
   voice?.reset();
   if(terminalScrollTimeout!==null)clearTimeout(terminalScrollTimeout);
  }
  store();
  draw();
  const restoring=cmd.action==="match_resume";
  announceResponse(previous,state,result.match.public_steps,restoring);
  if(previous && !DONE.has(previous.phase) && DONE.has(state.phase) &&
     !restoring){
   if(terminalScrollTimeout!==null)clearTimeout(terminalScrollTimeout);
   terminalScrollTimeout=setTimeout(()=>{
    if(state&&DONE.has(state.phase))
     el("classic-result-report").scrollIntoView({
      behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?
       "instant":"smooth",block:"start",
     });
   },1700);
  }
  advance();
 }catch(e){
  console.error("Majiang UI match",e);status("操作失败："+e.message);
  if(token){
   try{const r=await api({action:"match_resume"});state=r.match;draw();advance()}
   catch(err){status("恢复失败："+err.message)}
  }
 }finally{busy=false;if(state)draw()}
}
function boot(){
 setupImages();pai=MajiangTile($("#loaddata"));
 initializeVoice();
 const hand=document.querySelector(".shoupai.main .bingpai");
 hand.addEventListener("click",e=>{
  const target=e.target.closest("[data-hand-index]");if(target)selectHand(target);
 });
 hand.addEventListener("keydown",e=>{
  const t=e.target.closest("[data-hand-index]");
  if(e.key==="Escape"&&selected.size){
   e.preventDefault();selected.clear();draw();
   if(t)focusTile(Number(t.dataset.handIndex));
  }else if(t&&(e.key==="Enter"||e.key===" ")){
   e.preventDefault();selectHand(t,true);
  }
 });
 el("classic-hint-trigger").onclick=()=>void toggleHint();
 el("classic-new").onclick=()=>{if(confirm("开始新的牌局？"))
  void submit({action:"match_new"})};
 window.addEventListener("resize",resize);resize();
 token=saved();void submit({action:token?"match_resume":"match_new"});
}
boot();
