/* Original kobalab/Majiang UI components; MahTrain Python is the only game authority. */
import $ from "jquery";
import MajiangTile from "@kobalab/majiang-ui/lib/pai.js";
import MajiangShoupai from "@kobalab/majiang-ui/lib/shoupai.js";
import MajiangHe from "@kobalab/majiang-ui/lib/he.js";
import {SESSION_KEY,convertView,choiceAction} from "./bridge.mjs";
const CLS=["main","xiajia","duimian","shangjia"];
const SUIT={m:"万",p:"筒",s:"条"};
const TURN=new Set(["dealer_discard","await_discard"]);
const DONE=new Set(["finished","wall_exhausted"]);
const el=id=>document.getElementById(id);
let token=null,state=null,pai=null,busy=false,timer=null;
const selected=new Set();
function status(t){el("classic-status").textContent=t}
function saved(){try{return sessionStorage.getItem(SESSION_KEY)}catch{return null}}
function store(){try{
 if(token&&state&&!DONE.has(state.phase))sessionStorage.setItem(SESSION_KEY,token);
 else sessionStorage.removeItem(SESSION_KEY);
}catch{}}
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
 if(!buttons.length)return;
 el("classic-actions-title").textContent=title;
 el("classic-actions-buttons").replaceChildren(...buttons);
}
function draw(){
 if(!state)return;
 const view=convertView(state);
 for(let s=0;s<4;s++){
  const cls=CLS[s];
  new MajiangShoupai($(".shoupai."+cls),pai,view.hands[s],s===0)
    .redraw(s===0).adjust();
  $(".shoupai."+cls+" .fulou .mianzi").each((i,node)=>{
   if(!view.redactions[s][i]?.hidden)return;
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
  el("classic-player-"+s).textContent=(s===0?"自己":s+"号AI")+suffix+
    (state.won?.[s]?" · 已胡":"");
  el("classic-score-"+s).textContent=s+"号"+suffix+" · "+
    state.hand_counts[s]+"张";
  el("classic-score-"+s).classList.toggle("lunban",state.turn===s);
 }
 el("classic-wall-count").textContent=String(state.wall_count??"—");
 el("classic-dealer").textContent=String(state.dealer??"—")+"号";
 const nodes=[...document.querySelectorAll(".shoupai.main .bingpai > img.pai"),
  ...document.querySelectorAll(".shoupai.main .bingpai .zimo img.pai")];
 if(nodes.length!==view.indexed.length){
  status("手牌显示不匹配，已禁用出牌");console.error("Hand size mismatch",nodes.length,view.indexed.length);
 }else nodes.forEach((img,i)=>{
  const info=view.indexed[i];img.dataset.handIndex=info.index;
  img.setAttribute("tabindex","0");img.setAttribute("role","button");
  img.setAttribute("aria-label",info.value+(info.fromDraw?"摸牌":"手牌"));
  img.classList.toggle("is-picked",selected.has(info.index));
  img.classList.toggle("is-draw",!!info.fromDraw);
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
  const rob=state.phase==="rob_kong_window";
  const opts=rob?state.rob_options:state.claim_options;
  const submitted=rob?state.rob_submitted:state.claim_submitted;
  const target=rob?state.pending_rob_kong:state.pending_discard;
  if(target?.seat!==0 && !submitted?.includes(0)&&opts?.some(x=>x!=="pass")){
   buttons=["hu","ming_gang","peng","pass"].filter(o=>opts.includes(o))
    .map(o=>btn(({hu:"胡",ming_gang:"杠",peng:"碰",pass:"过"})[o],
      ()=>run("claim",{option:o}),o==="hu",busy));
  }
  center("请选择碰、杠、胡或过",buttons);status("等待碰杠胡处理");
 }else if(TURN.has(state.phase)&&state.turn===0){
  if(state.can_self_draw_win)buttons.push(btn("自摸胡",()=>run("win"),true,busy));
  for(const k of state.kong_options||[])buttons.push(btn("杠 "+k.tile,()=>
   run("kong",{kind:k.type,tile:k.tile}),false,busy));
  center("轮到你出牌",buttons);
  status("点击一张手牌选中，再点同张打出；胡牌/杠在中央");
 }else if(DONE.has(state.phase)){
  center("本局结束",[btn("再来一局",()=>void submit({action:"match_new"}),true,busy)]);
  status("本局结束");
 }else {center("",[]);status("AI 行动中 · 等待服务器同步")}
 resize();
}
function selectHand(node){
 if(busy||!state)return;
 const i=Number(node?.dataset.handIndex);
 if(!Number.isInteger(i)||i<0||i>=state.hand.length)return;
 if(state.phase==="exchange_select"){
  if(selected.has(i))selected.delete(i);
  else if(selected.size<3)selected.add(i);
  draw();
 }else if(TURN.has(state.phase)&&state.turn===0){
  const cmd=choiceAction(state,"discard",{index:i});if(!cmd)return;
  if(selected.has(i))void submit(cmd);
  else{selected.clear();selected.add(i);draw()}
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
  headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
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
  const result=await api(cmd);
  token=result.match_token;state=result.match;selected.clear();
  store();draw();advance();
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
 const hand=document.querySelector(".shoupai.main .bingpai");
 hand.addEventListener("click",e=>{
  const target=e.target.closest("[data-hand-index]");if(target)selectHand(target);
 });
 hand.addEventListener("keydown",e=>{
  if(e.key==="Enter"||e.key===" "){
   const t=e.target.closest("[data-hand-index]");
   if(t){e.preventDefault();selectHand(t)}
  }
 });
 el("classic-new").onclick=()=>{if(confirm("开始新的牌局？"))
  void submit({action:"match_new"})};
 window.addEventListener("resize",resize);resize();
 token=saved();void submit({action:token?"match_resume":"match_new"});
}
boot();
