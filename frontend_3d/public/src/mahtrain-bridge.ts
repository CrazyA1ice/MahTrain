/* Adapter ONLY: Queju owns the complete WebGL scene and game UI.
   MahTrain/Python owns ALL rules, AI, hand secrecy and scoring. */
import {gameState} from './state/game-state.ts';
import {renderPlayers,toast} from './ui.ts';
import {SESSION_KEY,clientSeat,toQuejuSnapshot,decode3dAction} from './mahtrain-protocol.mjs';

const HEADERS={'Content-Type':'application/json','X-MahTrain':'1'};
const START={action:'match_new',ai_levels:['challenge','challenge','challenge'],
  self_draw_mode:'add_base'};
const suits={m:'万',s:'条',p:'筒'};
const terminal=new Set(['finished','wall_exhausted']);
let token=null,board=null,pending=false,refreshTimer=null,selected=new Set(),emit=null;
function storage(){
  try{return sessionStorage.getItem(SESSION_KEY)}catch{return null}
}
function saveSession(){
  try{
    if(token&&board&&!terminal.has(board.phase))
      sessionStorage.setItem(SESSION_KEY,token);
    else sessionStorage.removeItem(SESSION_KEY);
  }catch{}
}
function message(err){
  const text=err instanceof Error?err.message:String(err);
  toast('MahTrain：'+text,5200);
  const status=document.getElementById('statusText');
  if(status)status.textContent='连接或操作错误';
}
async function api(payload){
  const response=await fetch('/api/action',{method:'POST',headers:HEADERS,
    body:JSON.stringify(payload)});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'服务器拒绝了操作');
  if(typeof data.match_token!=='string'||data.match?.seat!==0)
    throw new Error('对局身份异常，已停止更新');
  return data;
}
function button(label,run,disabled=false){
  const el=document.createElement('button');el.type='button';
  el.textContent=label;el.disabled=disabled;el.onclick=run;return el;
}
function controlPane(){
  let pane=document.getElementById('mahtrain-sichuan-controls');
  if(!pane){
    pane=document.createElement('section');pane.id='mahtrain-sichuan-controls';
    pane.setAttribute('aria-label','四川血战特有操作');
    const origin=document.querySelector('.panel');
    if(!origin)throw new Error('雀局游戏操作区不存在');
    origin.appendChild(pane);
  }
  return pane;
}
function controls(){
  if(!board)return;
  const pane=controlPane();pane.replaceChildren();
  const titles={exchange_select:'换三张',missing_select:'定缺',
    dealer_discard:'庄家出牌',await_discard:'你的回合',
    claim_window:'请响应碰杠胡',rob_kong_window:'抢杠胡',
    finished:'对局结束',wall_exhausted:'牌墙耗尽'};
  const head=document.createElement('strong');
  head.textContent=titles[board.phase]||board.phase;pane.append(head);
  if(board.phase==='exchange_select'){
    const tip=document.createElement('div');
    tip.textContent='请选择三张相同花色的实体手牌';pane.append(tip);
    const rack=document.createElement('div');
    rack.className='mahtrain-exchange-choices';
    board.hand.forEach((tile,index)=>{
      const b=button(tile.slice(1)+suits[tile[0]],()=>{
        if(selected.has(index))selected.delete(index);
        else if(selected.size<3)selected.add(index);
        controls();
      });
      b.setAttribute('aria-pressed',String(selected.has(index)));
      b.title='第'+(index+1)+'张';if(selected.has(index))b.classList.add('selected');
      rack.append(b);
    });
    pane.append(rack);
    const chosen=[...selected].map(i=>board.hand[i]);
    const same=chosen.length===3&&chosen.every(t=>t[0]===chosen[0][0]);
    pane.append(button('确认换三张（'+selected.size+'/3）',()=>
      void perform({action:'match_exchange',tiles:chosen}),!same||pending));
    pane.append(button('清空选择',()=>{selected.clear();controls()},!selected.size));
  }else if(board.phase==='missing_select'){
    for(const s of ['m','s','p']){
      const n=board.hand.filter(t=>t[0]===s).length;
      pane.append(button('定缺'+suits[s]+'（'+n+'张）',()=>
        void perform({action:'match_missing',suit:s}),pending));
    }
  }else if(['dealer_discard','await_discard'].includes(board.phase)){
    const help=document.createElement('span');
    help.textContent='选中3D手牌打出；副露/胡牌以服务器判定为准';
    pane.append(help);
    if(board.can_self_draw_win)pane.append(button('自摸胡',
      ()=>void perform({action:'match_win'}),pending));
    for(const k of board.kong_options||[])
      pane.append(button('杠 '+k.tile,()=>void perform({
        action:'match_kong',kind:k.type,tile:k.tile}),pending));
  }else if(terminal.has(board.phase)){
    pane.append(button('再来一局',()=>{
      if(confirm('开始新一局？'))void perform(START);
    },pending));
  }
  const info=document.createElement('small');
  info.textContent='剩余 '+board.wall_count+' 张 · '+
    (board.missing_suits||[]).map((s,i)=>
      i+'号缺'+(s?suits[s]:'未定')).join(' / ');
  pane.append(info);
}
function render(){
  if(!board)return;
  for(let i=0;i<4;i++){
    const seat=clientSeat(i),s=board.missing_suits?.[i];
    gameState.playerInfo[seat].name=(i===0?'我':'AI '+i)+
      (s?' · 缺'+suits[s]:'');
  }
  emit(toQuejuSnapshot(board));
  renderPlayers();
  controls();
}
function schedule(){
  if(refreshTimer)clearTimeout(refreshTimer);
  if(board?.needs_continue && !terminal.has(board.phase))
    refreshTimer=setTimeout(()=>void perform({action:'match_continue'}),220);
}
async function perform(command){
  if(pending)return;
  pending=true;
  if(refreshTimer)clearTimeout(refreshTimer);
  try{
    const payload={...command};
    if(command.action!=='match_new'){
      if(!token)throw new Error('没有可恢复的对局会话');
      payload.match_token=token;
    }
    const result=await api(payload);
    token=result.match_token;board=result.match;
    selected.clear();saveSession();render();schedule();
  }catch(err){
    message(err);
    // Ambiguous HTTP failures must be reconciled READ-ONLY: never retry
    // a discard/kong that the Python server might already have committed.
    if(token){
      try{
        const read=await api({action:'match_resume',match_token:token});
        board=read.match;render();schedule();
      }catch(error){message(error)}
    }
  }finally{
    // Controls are rendered while the HTTP command is pending; they must
    // be re-enabled AFTER the authoritative response has been accepted.
    pending=false;
    if(board)controls();
  }
}
export function startMahTrainBridge(accept){
  emit=accept;
  const players=[{name:'自己'},{name:'AI 上家'},
    {name:'AI 对家'},{name:'AI 下家'}];
  emit({type:'welcome',yourSeat:0,roomSeats:players});
  token=storage();
  if(token)void perform({action:'match_resume'});
  else void perform(START);
  return msg=>{
    if(!board)return;
    const action=decode3dAction(msg,board);
    if(action)void perform(action);
    else if(['discard','claim'].includes(msg?.type))
      message('当前四川血战阶段不允许此操作');
  };
}
