/* Read-only accounting: the Python ledger is the ONLY scoring authority. */
export const WIN_KIND=Object.freeze({self_draw:"自摸",ron:"点炮胡",rob_kong:"抢杠胡"});
export const KONG_KIND=Object.freeze({ming_gang:"明杠",an_gang:"暗杠",bu_gang:"补杠"});
export const PATTERN_ZH=Object.freeze({
 pinghu:"平胡",seven_pairs:"七对",pure_seven_pairs:"清七对",
 dragon_seven_pairs:"龙七对",pure_dragon_seven_pairs:"清龙七对",
 golden_hook:"金钩钓",all_pungs:"对对胡",pure_all_pungs:"清对对胡",
 pure_suit:"清一色",heaven_win:"天胡",earth_win:"地胡",
 tian_ting:"天听",kong_bloom:"杠上花",kong_discard_ron:"杠上炮",
 rob_added_kong:"抢杠胡",sea_bottom_draw:"海底捞月",
 river_bottom_ron:"海底炮",roots:"根",
});
export const patternLabel=key=>PATTERN_ZH[key]||String(key??"未命名番型");
export const TERMINAL=new Set(["finished","wall_exhausted"]);
export const signed=n=>typeof n==="number"&&Number.isSafeInteger(n)
  ?(n>0?"+":"")+String(n):"未计价";
export const seatName=n=>n===0?"自己":n+"号AI";
export function winTitle(win){
 return seatName(win.winner)+" "+(WIN_KIND[win.kind]||"胡牌")+
  " · "+patternLabel(win.main_pattern||"已胡牌")+" · "+(win.effective_fan??0)+
  "番 · 实收"+signed(win.total_received);
}
function balances(ledger){
 if(Array.isArray(ledger?.balances)&&ledger.balances.length===4&&
  ledger.balances.every(Number.isSafeInteger))return ledger.balances;
 return [0,0,0,0];
}
export function summarizeSettlement(view){
 if(!view||!TERMINAL.has(view.phase))return null;
 const wins=Array.isArray(view.win_ledger?.wins)?view.win_ledger.wins:[];
 const ledgerEntries=Array.isArray(view.win_ledger?.entries)?view.win_ledger.entries:[];
 const kongEvents=Array.isArray(view.kong_ledger?.events)?view.kong_ledger.events:[];
 const kongEntries=Array.isArray(view.kong_ledger?.entries)?view.kong_ledger.entries:[];
 const win=balances(view.win_ledger),kong=balances(view.kong_ledger);
 const exhaustive=view.exhaustive_settlement;
 const posted=exhaustive?.posted===true;
 const draw=posted?balances(exhaustive):[0,0,0,0];
 const reported=Array.isArray(view.settled_balances)&&
  view.settled_balances.length===4&&
  view.settled_balances.every(Number.isSafeInteger)
  ?view.settled_balances:null;
 const seats=Array.from({length:4},(_,i)=>({
  seat:i,name:seatName(i),won:view.won?.[i]===true,
  patterns:wins.filter(x=>x.winner===i)
   .map(x=>({name:x.main_pattern||"未命名番型",
    fan:x.effective_fan,rawFan:x.raw_fan,kind:x.kind,
    combinations:x.combinations||{},bonuses:x.bonuses||{},
    received:x.total_received})),
  win:win[i],kong:kong[i],draw:draw[i],
  // The backend number is sovereign; never quietly fix mismatches.
  total:reported?reported[i]:win[i]+kong[i]+draw[i],
 }));
 const zeroSum=seats.reduce((sum,x)=>sum+x.total,0)===0;
 const totalsMatch=seats.every(x=>x.total===x.win+x.kong+x.draw);
 return {
  seats,wins,ledgerEntries,kongEvents,kongEntries,exhaustive,
  wallPending:view.phase==="wall_exhausted"&&!posted,
  posted,zeroSum,totalsMatch,kongPriced:view.kong_ledger?.base!=null,
  kongBase:view.kong_ledger?.base??null,
 };
}
export function publicActions(publicSteps){
 const seen=[];
 for(const frame of Array.isArray(publicSteps)?publicSteps:[]){
  for(const ev of Array.isArray(frame?.events)?frame.events:[]){
   if(!ev||!["discard","peng","ming_gang","an_gang","bu_gang",
    "ron","multi_ron","rob_kong","self_draw_win"].includes(ev.type))continue;
   seen.push({
    type:ev.type,seat:Number.isInteger(ev.seat)?ev.seat:null,
    publicTile:ev.type==="discard"?ev.tile:null,
    winSeats:Array.isArray(ev.seats)?ev.seats:
     Number.isInteger(ev.seat)?[ev.seat]:[],
   });
  }
 }
 return seen;
}
export function recentWins(previous,current,restoring=false){
 if(restoring)return [];
 const a=previous?.win_ledger?.wins,b=current?.win_ledger?.wins;
 if(!Array.isArray(b))return [];
 const from=Array.isArray(a)?a.length:0;
 return b.slice(Math.max(0,Math.min(from,b.length)));
}
export function nonZeroBreakdown(record){
 return Object.entries(record||{}).filter(([_,value])=>
  value!==0&&value!==false&&value!=null).map(([key,value])=>
  typeof value==="number"&&value!==1?key+"×"+value:key);
}
