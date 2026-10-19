/*
 * MahTrain public-event -> classic 2D action cue.
 * Receives only server-published frames and authoritative posted win records;
 * never inspects another player's concealed cards or the future wall.
 * Does not score tiles or enforce gameplay rules.
 */
import {KONG_KIND,seatName,recentWins,publicActions,winTitle} from "./settlement.mjs";

const FAN_TILES={m:"万",p:"筒",s:"条"};
const NUMERALS=["","一","二","三","四","五","六","七","八","九"];
export function publicTileLabel(value){
  if(typeof value!=="string"||!/^[mps][1-9]$/.test(value))return "";
  return NUMERALS[Number(value[1])]+FAN_TILES[value[0]];
}
const legalSeat=s=>Number.isInteger(s)&&s>=0&&s<4;
function normalizeSeats(s){
  return [...new Set((Array.isArray(s)?s:[])
    .filter(legalSeat))];
}
export function liveActionCue(steps,previous,current,restoring=false){
  if(restoring)return null;
  const actions=publicActions(steps);
  const wins=recentWins(previous,current);
  if(wins.length){
    const seats=normalizeSeats(wins.map(x=>x.winner));
    const many=seats.length>1;
    return {
      kind:"win",seats,
      title:many?
        "一炮多响 · "+seats.map(seatName).join("、")+" 胡牌":
        winTitle(wins[0]),
      detail:many?wins.map(x=>winTitle(x)).join("；"):
        wins[0].kind==="self_draw"?"自摸 · 已按服务器确认入账":
        "点炮／抢杠 · 已按服务器确认入账",
    };
  }
  // For ordinary play, use the LAST visible action; silent rule transitions
  // never manufacture an animation. An event after a kong can be a public
  // supplementary DRAW, which is intentionally excluded from publicActions.
  const action=actions.at(-1);
  if(!action)return null;
  const seats=normalizeSeats(action.winSeats);
  switch(action.type){
    case "self_draw_win":
    case "ron":
    case "rob_kong":
    case "multi_ron":{
      const who=seats.length?seats.map(seatName).join("、"):"牌桌";
      return {
        kind:"win",seats,
        title:(seats.length>1?"一炮多响 · ":"")+who+" 胡牌",
        detail:"已确认的公开胡牌事件",
      };
    }
    case "peng":
      return {kind:"peng",seats:normalizeSeats([action.seat]),
        title:seatName(action.seat)+" 碰",detail:"公开副露已更新"};
    case "ming_gang":
    case "an_gang":
    case "bu_gang":
      return {kind:"kong",seats:normalizeSeats([action.seat]),
        title:seatName(action.seat)+" "+
          (KONG_KIND[action.type]||"杠"),
        detail:"杠牌已由服务器确认，账本金额以最终结算为准"};
    case "discard":
      return {kind:"discard",seats:normalizeSeats([action.seat]),
        title:seatName(action.seat)+" 打出 "+publicTileLabel(action.publicTile),
        detail:"公开弃牌",};
    default:return null;
  }
}
