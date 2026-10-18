/*
 * Only data/protocol translation lives here. 3D rendering is the unmodified
 * MIT-licensed Queju implementation in public/src/{scene,board,animation}.
 * MahTrain remains the sole rules/AI authority. No AI concealed tiles or
 * future wall order pass through this boundary.
 */
export const CLIENT_SEAT = Object.freeze([0,3,2,1]);
export const SESSION_KEY = "mahtrain.match.session.v1";
export function clientSeat(seat) {
  if (!Number.isInteger(seat) || seat < 0 || seat > 3)
    throw new TypeError("invalid MahTrain seat");
  return CLIENT_SEAT[seat];
}
export function tileTo3d(tile) {
  if (typeof tile !== "string" || !/^[msp][1-9]$/.test(tile))
    throw new TypeError("invalid public tile");
  const type = {m:"wan",p:"tong",s:"tiao"}[tile[0]];
  return {type,value:Number(tile[1])};
}
const BACK = Object.freeze({type:"wan",value:1});
export function meldTo3d(meld, own=false) {
  const kind = {peng:"pong",ming_gang:"kong",an_gang:"ckong",
    bu_gang:"kong"}[meld?.type];
  if (!kind) throw new TypeError("unsupported public meld");
  // An unrevealed opponent kong NEVER enters the 3D layer as a face tile.
  const concealed = meld.type==="an_gang" &&
    (!own && meld.revealed !== true || !meld.tile);
  const count = meld.type==="peng" ? 3 : 4;
  const face = concealed ? BACK : tileTo3d(meld.tile);
  return {kind,tiles:Array.from({length:count},(_,i)=>({...face,id:null})),
    hidden:concealed};
}
const ACTIVE = new Set(["dealer_discard","await_discard"]);
const TERMINAL = new Set(["finished","wall_exhausted"]);
export function toQuejuSnapshot(view) {
  if (!view || view.seat!==0 || !Array.isArray(view.hand) ||
      !Array.isArray(view.hand_counts) || view.hand_counts.length!==4)
    throw new TypeError("not a private seat-zero MahTrain snapshot");
  const melds=[[],[],[],[]],discards=[[],[],[],[]];
  for(let seat=0;seat<4;seat++){
    const groups=seat===0 ? (view.own_melds||[]) : (view.melds?.[seat]||[]);
    melds[clientSeat(seat)] = groups.map(m=>meldTo3d(m,seat===0));
  }
  for(let i=0;i<(view.discards||[]).length;i++){
    const item=view.discards[i];
    const seat=clientSeat(item.seat);
    // A taken discard is a permanent EMPTY physical slot; do not shift
    // later discards or accidentally recreate the claimed tile.
    discards[seat].push(item.claimed_by!==undefined
      ? null : {...tileTo3d(item.tile),id:1000+i});
  }
  const counts=[0,0,0,0];
  view.hand_counts.forEach((n,seat)=>{
    if (!Number.isInteger(n) || n<0 || n>14)throw new TypeError("bad hand count");
    counts[clientSeat(seat)]=n;
  });
  const originalLast=(view.discards||[]).at(-1);
  const lastId=originalLast && originalLast.claimed_by===undefined
    ?1000+view.discards.length-1:null;
  const phase=view.phase;
  const pending=phase==="claim_window" ?view.pending_discard
    :phase==="rob_kong_window"?view.pending_rob_kong:null;
  const opts=phase==="claim_window" ?view.claim_options
    :phase==="rob_kong_window"?view.rob_options:null;
  const alreadySubmitted=view.claim_submitted?.includes(0)===true ||
    view.rob_submitted?.includes(0)===true;
  const mappedOpts=(opts||[]).map(t=>({hu:"win",peng:"pong",
    ming_gang:"kong"}[t])).filter(Boolean);
  const claimOffer=pending && pending.seat!==0 &&
    mappedOpts.length && !alreadySubmitted
    ?{fromSeat:clientSeat(pending.seat),tile:tileTo3d(pending.tile),
      options:mappedOpts}:null;
  const kongs=(view.kong_options||[]);
  const result={
    type:"reconnectState",phase:"play",
    currentTurn:ACTIVE.has(phase)&&view.turn!==null?
      clientSeat(view.turn):0,
    dealer:clientSeat(view.dealer||0),gameOver:TERMINAL.has(phase),
    wallTotal:112,wallCursor:Math.max(0,112-(view.wall_count||0)),
    wallBackCursor:111,
    yourHand:view.hand.map((tile,id)=>({...tileTo3d(tile),id:id+1})),
    handCounts:counts, melds,discards,lastDiscardId:lastId,
    lastDiscardBy:originalLast?clientSeat(originalLast.seat):-1,
    isMyTurn:ACTIVE.has(phase)&&view.turn===0,
    claimOffer,
    selfOptions:ACTIVE.has(phase)&&view.turn===0?{
      canWin:view.can_self_draw_win===true,
      ckong:kongs.filter(k=>k.type==="an_gang").map(k=>tileTo3d(k.tile)),
      addKong:kongs.filter(k=>k.type==="bu_gang").map(k=>tileTo3d(k.tile))
    }:null,
  };
  return result;
}
export function decode3dAction(message,view) {
  if (!message || !view || view.seat!==0)return null;
  if(message.type==="discard" && ACTIVE.has(view.phase) &&
      view.turn===0 && Number.isInteger(message.tileId)){
    const index=message.tileId-1;
    const tile=view.hand[index];
    if(index<0||index>=view.hand.length||!tile)return null;
    // Server's private "drawn_tile" is the final copy, even when the
    // same value occurs earlier in the hand.
    const lastDrawn=typeof view.drawn_tile==="string"
      ?view.hand.lastIndexOf(view.drawn_tile):-1;
    return {action:"match_discard",tile,from_draw:index===lastDrawn};
  }
  if(message.type==="claim"){
    const a=message.action;
    if(view.phase==="claim_window" || view.phase==="rob_kong_window"){
      const opts=view.phase==="claim_window"?view.claim_options:view.rob_options;
      const choice={win:"hu",pong:"peng",kong:"ming_gang",
        pass:"pass"}[a];
      if(!choice || !opts?.includes(choice))return null;
      return {action:view.phase==="claim_window"?"match_claim":"match_rob",
        choice};
    }
    if(ACTIVE.has(view.phase)&&view.turn===0){
      if(a==="win" && view.can_self_draw_win)return {action:"match_win"};
      if((a==="ckong"||a==="addKong") && message.value){
        const tile=from3dTile(message.value);
        const kind=a==="ckong"?"an_gang":"bu_gang";
        if((view.kong_options||[]).some(k=>k.type===kind&&k.tile===tile))
          return {action:"match_kong",kind,tile};
      }
    }
  }
  if(message.type==="restart")return {action:"match_new",
    ai_levels:["challenge","challenge","challenge"],
    self_draw_mode:"add_base"};
  return null;
}
export function from3dTile(tile) {
  if(!tile || !Number.isInteger(tile.value) || tile.value<1 || tile.value>9)
    throw new TypeError("invalid tile");
  const suit={wan:"m",tiao:"s",tong:"p"}[tile.type];
  if(!suit)throw new TypeError("unsupported suit");
  return suit+tile.value;
}
