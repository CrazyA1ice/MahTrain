/* Render public-knowledge-only Sichuan tenpai / effective-draw explanations.
 * Not a perfect-information recommendation or deck/wall estimator.
 */
import {tileLabel} from "./action-choice.mjs";

const element=(tag,cls="",value)=>{
 const node=document.createElement(tag);
 if(cls)node.className=cls;
 if(value!==undefined)node.textContent=String(value);
 return node;
};
const suffix=row=>row.shanten===0?"听牌":row.shanten+"向听";
export function renderClassicHint(root,report){
 root.replaceChildren();
 if(!report){root.hidden=true;return}
 root.hidden=false;
 root.append(element("h3","","四川血战 · 牌效参考（非 AI 最优策略）"));
 if(report.status==="already_winning"){
  root.append(element("p","", "当前手牌已成胡牌形，优先考虑服务器提供的自摸胡选项。"));
  return;
 }
 if(report.status!=="choose_discard"){
  root.append(element("p","","当前阶段暂无可展示的牌效。"));
  return;
 }
 root.append(element("p","classic-hint-note",
  (report.forced_missing?"仍有定缺花色：仅展示必须先打出的该花色。":"候选切牌按最少向听、再按未排除有效张数排序。")+
  " 0向听表示听牌；“≤”表示从公开信息未排除的物理张数上限，不代表牌墙实存张数。"));
 const table=element("table","classic-hint-table");
 const head=element("thead"),hr=element("tr");
 for(const title of ["切牌","切后进度","有效牌种","未排除张数上限","公开信息可见的有效进张"]){
  hr.append(element("th","",title));
 }
 head.append(hr);table.append(head);
 const body=element("tbody");
 for(const candidate of report.candidates||[]){
  const row=element("tr",candidate.reference_best?"classic-hint-reference":"");
  const tile=element("td");
  const image=element("img","classic-hint-tile");
  image.src="/classic/img/"+candidate.discard+".gif";
  image.alt="";
  tile.append(image,document.createTextNode(tileLabel(candidate.discard)));
  row.append(tile);
  row.append(element("td","",suffix(candidate)));
  row.append(element("td","",candidate.effective_type_count));
  row.append(element("td","",
   "≤ "+candidate.effective_tile_count_upper_bound+" 张"));
  row.append(element("td","",
   candidate.effective_details?.length?
    candidate.effective_details.map(x=>
     tileLabel(x.tile)+" ≤"+x.unknown_copies_upper_bound).join("、"):
    "暂无已知有效进张"));
  body.append(row);
 }
 table.append(body);root.append(table);
 root.append(element("p","classic-hint-footnote",
  "浅金底色仅代表当前模型的局部参考优先切牌；未估算隐藏牌分布、危险度、未来番型组合或综合最优期望。"+
  "本分析按需计算，下一次摸牌、碰杠或出牌后需重新查看。"));
}
