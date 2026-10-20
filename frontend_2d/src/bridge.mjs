/*
 * MahTrain -> original kobalab/Majiang 2D component data adapter.
 * All seat-zero private tiles stay local. Opponents contribute counts,
 * public rivers and public melds only. This is NOT Japanese rule code.
 */
export const SESSION_KEY="mahtrain.match.session.v1";
const LEGAL_TILE=/^[mps][1-9]$/;
const PHASE_TURNS=new Set(["await_discard","dealer_discard"]);
const MELD_SIGNS={1:"+",2:"=",3:"-"};
export function tile(value) {
  if (typeof value!=="string" || !LEGAL_TILE.test(value))
    throw new TypeError("invalid MahTrain tile");
  return value;
}
export function closedHandModel(tiles,drawnTile=null) {
  if (!Array.isArray(tiles)||tiles.length>14)throw new TypeError("invalid hand");
  const model={_bingpai:{m:Array(10).fill(0),p:Array(10).fill(0),
    s:Array(10).fill(0),z:Array(8).fill(0),_:0},
    _zimo:null,_fulou:[]};
  for (const value of tiles){tile(value);model._bingpai[value[0]][+value[1]]++}
  if(drawnTile!=null && tiles.includes(drawnTile))model._zimo=tile(drawnTile);
  return model;
}
function concealedModel(n){
  if(!Number.isInteger(n)||n<0||n>14)throw new TypeError("invalid count");
  const m=closedHandModel([]);
  m._bingpai._=n;
  return m;
}
export function meldToken(meld,seat=0) {
  if(!meld || !["peng","ming_gang","an_gang","bu_gang"].includes(meld.type))
    throw new TypeError("unsupported meld");
  // Some historical public records redact the tile of an opponent's
  // concealed kong. The placeholder is rendered as backs by the viewer;
  // the fake m1 never becomes a public face, a hint, or a command.
  const hidden=meld.tile==null ||
    (meld.type==="an_gang" && seat!==0 && meld.revealed!==true);
  const v=hidden?"m1":tile(meld.tile);
  const s=v[0],n=v[1],sign=MELD_SIGNS[seat]||"+";
  const kind=meld.type;
  const code=kind==="peng"?s+n.repeat(3)+sign:
    kind==="bu_gang"?s+n.repeat(3)+sign+n:
    kind==="ming_gang"?s+n.repeat(4)+sign:s+n.repeat(4);
  return {code,hidden};
}
export function convertView(view) {
  if(view?.seat!==0||!Array.isArray(view.hand_counts)||
    view.hand_counts.length!==4||!Array.isArray(view.hand))
    throw new TypeError("expected authorized MahTrain seat-zero view");
  const hands=[],rivers=[],redactions=[];
  for(let seat=0;seat<4;seat++){
    const m=seat===0
      ?closedHandModel(view.hand,view.drawn_tile):concealedModel(view.hand_counts[seat]);
    const melds=seat===0 ?(view.own_melds||[]) :(view.melds?.[seat]||[]);
    // The official discard river contains the actual source of every
    // successful peng/ming-gang (and of the peng later upgraded to bu-gang).
    // Direction is SOURCE-relative-to-OWNER, never fixed by screen seat.
    // Public history has no opponent concealed hand or future wall data.
    redactions[seat]=melds.map(x=>{
      const info=meldToken(x,seat);
      const claim=(view.discards||[]).find(d=>d.claimed_by===seat&&
        d.tile===x.tile&&d.seat!==seat);
      return {...info,kind:x.type,tile:info.hidden?null:x.tile,
        revealed:x.type==="an_gang"?(seat===0||x.revealed===true):true,
        source:claim?claim.seat:null};
    });
    m._fulou=redactions[seat].map(x=>x.code);
    hands[seat]=m;
    const raw=(view.discards||[]).filter(x=>x.seat===seat);
    rivers[seat]={_pai:raw.map(x=>tile(x.tile)),
      claimed:raw.map(x=>x.claimed_by!==undefined)};
  }
  const drawnIndex=typeof view.drawn_tile==="string"?
    view.hand.lastIndexOf(view.drawn_tile):-1;
  const indexed=view.hand.map((value,index)=>({value,index}))
    .filter(x=>x.index!==drawnIndex)
    .sort((a,b)=> "mps".indexOf(a.value[0])-"mps".indexOf(b.value[0]) ||
      Number(a.value[1])-Number(b.value[1]) || a.index-b.index);
  if(drawnIndex>=0)indexed.push({value:view.hand[drawnIndex],index:drawnIndex,
    fromDraw:true});
  return {hands,rivers,redactions,indexed};
}
export function choiceAction(view,kind,details={}) {
  if(view?.seat!==0)return null;
  const phase=view.phase;
  if(kind==="discard"&&PHASE_TURNS.has(phase)&&view.turn===0){
    const index=details.index;
    if(!Number.isInteger(index)||index<0||index>=view.hand.length)return null;
    const drawnIndex=view.hand.lastIndexOf(view.drawn_tile);
    return {action:"match_discard",tile:tile(view.hand[index]),
      from_draw:!!view.drawn_tile&&index===drawnIndex};
  }
  if(kind==="claim"&&["claim_window","rob_kong_window"].includes(phase)){
    const options=phase==="claim_window"?view.claim_options:view.rob_options;
    // Both normal claims and rob-kong responses share Python's _responses,
    // published as claim_submitted in public_state(). There is no separate
    // rob_submitted field in MahTrain's actual API.
    const submitted=view.claim_submitted??view.rob_submitted;
    const pending=phase==="claim_window"?view.pending_discard:view.pending_rob_kong;
    const option=details.option;
    if(pending?.seat===0||submitted?.includes(0)||!options?.includes(option))
      return null;
    return {action:phase==="claim_window"?"match_claim":"match_rob",choice:option};
  }
  if(kind==="kong"&&PHASE_TURNS.has(phase)&&view.turn===0){
    const {kind:operation,tile:value}=details;
    if((view.kong_options||[]).some(k=>k.type===operation&&k.tile===value))
      return {action:"match_kong",kind:operation,tile:tile(value)};
  }
  if(kind==="win"&&PHASE_TURNS.has(phase)&&view.turn===0&&
    view.can_self_draw_win===true)return {action:"match_win"};
  return null;
}
