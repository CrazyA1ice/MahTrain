/* Only authoritative MahTrain public won flags and posted win_ledger. */
import {WIN_KIND,patternLabel} from "./settlement.mjs";

export function seatOutcome(view,seat){
 if(!Number.isInteger(seat)||seat<0||seat>3)throw new TypeError("invalid seat");
 const records=(Array.isArray(view?.win_ledger?.wins)?
   view.win_ledger.wins:[]).filter(x=>x.winner===seat);
 const won=view?.won?.[seat]===true||records.length>0;
 if(!won)return {won:false,label:"",detail:"",center:""};
 const details=records.map(row=>
   (WIN_KIND[row.kind]||"胡牌")+" · "+
   patternLabel(row.main_pattern||"已胡牌")+
   (Number.isInteger(row.effective_fan)?" · "+row.effective_fan+"番":"")
 );
 // A public won flag is enough to mark the seat even before its detailed
 // ledger entry arrives. Never infer a pattern or fan from private tiles.
 return {
   won:true,
   label:"已胡",
   detail:details.join("；")||"服务器已确认胡牌",
   center:details.length?
     details.map(x=>x.replaceAll(" · "," ")).join("；"):"已胡",
 };
}
