/* Chinese, server-authorized decision labels for genuine Majiang UI.
 * Contains ZERO Sichuan rules: all allowed choices come from MahTrain Python.
 */
import {choiceAction} from "./bridge.mjs";

const SUITS=Object.freeze({m:"万",p:"筒",s:"条"});
const CHINESE=Object.freeze(["","一","二","三","四","五","六","七","八","九"]);
const KONGS=Object.freeze({an_gang:"暗杠",bu_gang:"补杠"});

export const seatLabel=seat=>seat===0?"自己":
  Number.isInteger(seat)&&seat>=1&&seat<=3?seat+"号AI":"其他玩家";

export function tileLabel(value){
 if(typeof value!=="string"||!/^[mps][1-9]$/.test(value))
  return "未知牌";
 return CHINESE[Number(value[1])]+SUITS[value[0]];
}

export function claimDecision(view){
 const rob=view?.phase==="rob_kong_window";
 if(view?.phase!=="claim_window"&&!rob)return null;
 const pending=rob?view.pending_rob_kong:view.pending_discard;
 const source=pending?.seat;
 const options=rob?view.rob_options:view.claim_options;
 if(!Number.isInteger(source)||source<0||source>3||source===0||
    !Array.isArray(options))return null;
 const choices=[];
 for(const [key,verb] of [["hu",rob?"抢杠胡":"胡"],
                          ["ming_gang","明杠"],
                          ["peng","碰"],["pass","过"]]){
  if(!options.includes(key))continue;
  const command=choiceAction(view,"claim",{option:key});
  if(!command)continue;
  // Never expose an unoffered operation. A rob-kong phase has only Hu/pass.
  choices.push({key,label:verb,command,primary:key==="hu",
   explanation:key==="pass"?"放弃本次可执行的碰、杠、胡操作":"选择"+verb});
 }
 if(!choices.some(x=>x.key!=="pass"))return null;
 const subject=seatLabel(source)+(rob?"补杠":"打出")+tileLabel(pending.tile);
 return {
  title:subject+" · "+(rob?"是否抢杠胡？":"请选择碰、杠、胡或过"),
  choices,
 };
}

export function ownKongChoices(view){
 if(!["await_discard","dealer_discard"].includes(view?.phase)||
    view.turn!==0||!Array.isArray(view.kong_options))return [];
 return view.kong_options.flatMap(option=>{
  const command=choiceAction(view,"kong",{kind:option.type,tile:option.tile});
  if(!command)return [];
  return [{
   label:(KONGS[option.type]||"杠")+" "+tileLabel(option.tile),
   kind:option.type,command,
  }];
 });
}
