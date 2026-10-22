/* Opt-in public-only Sichuan efficiency reference, NOT a game oracle.
 * Only Python's real rules and authorized seat-zero response provide data.
 */
import {tileLabel} from "./action-choice.mjs";

const element=(tag,cls="",value)=>{
 const node=document.createElement(tag);
 if(cls)node.className=cls;
 if(value!==undefined)node.textContent=String(value);
 return node;
};
const suffix=row=>row.shanten===0?"听牌":row.shanten+"向听";
const PATTERNS={
 pinghu:"平胡",all_pungs:"对对胡",pure_suit:"清一色",
 pure_all_pungs:"清对",seven_pairs:"七对",
 dragon_seven_pairs:"龙七对",pure_seven_pairs:"清七对",
 pure_dragon_seven_pairs:"清龙七对",golden_hook:"金钩钓",
 heaven_win:"天胡",earth_win:"地胡",
};
function weightedReference(candidate){
 const number=candidate.fan_weighted_unknown_copies;
 return candidate.shanten===0&&Number.isFinite(number)
  ?"≤ "+number+"（倍率加权）":"—";
}
function details(candidate){
 if(candidate.shanten===0){
  const win=candidate.winning_details||[];
  return win.length?win.map(x=>
   tileLabel(x.tile)+" ≤"+x.unknown_copies_upper_bound+"张 · "+
   (PATTERNS[x.main_pattern]||x.main_pattern)+" "+
   x.effective_fan+"番 ×"+x.multiplier+
   (x.tian_ting_applied?"（含已验证天听）":"")
  ).join("；"):"当前公开信息未排除的听口为零";
 }
 return candidate.effective_details?.length?
  candidate.effective_details.map(x=>
   tileLabel(x.tile)+" ≤"+x.unknown_copies_upper_bound).join("、"):
  "暂无已知有效进张";
}
export function renderClassicHint(root,report){
 root.replaceChildren();
 if(!report){root.hidden=true;return}
 root.hidden=false;
 root.append(element("h3","","四川血战 · 牌效及听口番值参考（非 AI 全局最优策略）"));
 if(report.status==="already_winning"){
  root.append(element("p","","当前手牌已成胡牌形，优先考虑服务器提供的自摸胡选项。"));
  return;
 }
 if(report.status!=="choose_discard"){
  root.append(element("p","","当前阶段暂无可展示的牌效。"));
  return;
 }
 root.append(element("p","classic-hint-note",
  (report.forced_missing?"仍有定缺花色：仅分析优先切除定缺花色的方案。":
   "候选切牌先比较向听；已听牌时比较番值加权参考，其余比较有效进张。")+
  " 0向听表示听牌；“≤”是公开信息未排除张数的上限，不代表墙内剩余或摸牌概率。"));
 const table=element("table","classic-hint-table");
 const head=element("thead"),hr=element("tr");
 for(const title of ["切牌","切后进度","有效牌种","未排除张数上限",
                     "听牌番值加权参考","可见有效进张与理论番型"]){
  hr.append(element("th","",title));
 }
 head.append(hr);table.append(head);
 const body=element("tbody");
 for(const candidate of report.candidates||[]){
  const row=element("tr",candidate.reference_best?"classic-hint-reference":"");
  const cell=element("td");
  const image=element("img","classic-hint-tile");
  image.src="/classic/img/"+candidate.discard+".gif";
  image.alt="";
  cell.append(image,document.createTextNode(tileLabel(candidate.discard)));
  row.append(cell);
  row.append(element("td","",suffix(candidate)));
  row.append(element("td","",candidate.effective_type_count));
  row.append(element("td","",
   "≤ "+candidate.effective_tile_count_upper_bound+" 张"));
  row.append(element("td","",weightedReference(candidate)));
  row.append(element("td","",details(candidate)));
  body.append(row);
 }
 table.append(body);root.append(table);
 root.append(element("p","classic-hint-footnote",
  "番值加权参考 = 各听口“未排除张数上限 × 本局计分封顶后的基础胡牌倍率”之和。"+
  "只在听牌后计算，不包含未来杠上花、海底、自摸附加支付或放铳风险。"+
  "它不是实际期望积分、真实胜率或牌墙剩余张数。"+
  "浅金底色仅表示此局部规则下的候选优先级；行动后需重新查看。"));
}

/* Operation opportunity guidance is advisory and NEVER chooses for the player.
 * A verified Hu is an immediate authorized win; pong/kong scores are
 * one-step public-copy references, not actual end-of-match EV.
 */
export function renderClassicOperationHint(root,report){
 root.replaceChildren();
 if(!report||report.status!=="choose_operation"){root.hidden=true;return;}
 root.hidden=false;
 root.append(element("h3","","碰、杠、胡行动参考 · 当前局面"));
 const recommend=report.candidates?.find(x=>x.reference_best);
 if(recommend){
  root.append(element("p","classic-hint-note",
   "当前建议："+recommend.label+"。"+recommend.reason));
 }
 const table=element("table","classic-hint-table");
 const head=element("thead"),tr=element("tr");
 for(const heading of ["可选操作","向听","有效张上界","番值加权代理值","参考原因"]){
  tr.append(element("th","",heading));
 }
 head.append(tr);table.append(head);
 const body=element("tbody");
 for(const candidate of report.candidates||[]){
  const row=element("tr",candidate.reference_best?"classic-hint-reference":"");
  row.append(element("td","",candidate.label));
  row.append(element("td","",candidate.shanten===null?"即时胡牌":
   candidate.shanten===0?"听牌":candidate.shanten+"向听"));
  row.append(element("td","",candidate.effective_copies===null?"—":
   "≤ "+candidate.effective_copies+" 张"));
  row.append(element("td","",candidate.fan_weighted===null?"—":
   String(candidate.fan_weighted)));
  row.append(element("td","",candidate.reason));
  body.append(row);
 }
 table.append(body);root.append(table);
 root.append(element("p","classic-hint-footnote",report.limitations+
  " 金色标注代表当前挑战级公开信息启发式参考；可自行选择其他合法行动，"
  +"实际行动由服务器规则确认。本表不会读取其他玩家暗手。"));
}
