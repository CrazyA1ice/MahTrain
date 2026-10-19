/* Conventional score sheet outside the original Majiang board. */
import {summarizeSettlement,signed,seatName,WIN_KIND,KONG_KIND,
  nonZeroBreakdown} from "./settlement.mjs";
const n=(tag,cls,txt)=>{
 const e=document.createElement(tag);
 if(cls)e.className=cls;
 if(txt!==undefined)e.textContent=String(txt);
 return e;
};
const summaryCell=(row,text,tag="td",cls="")=>{
 const cell=n(tag,cls,text);row.append(cell);return cell;
};
function financialTable(root,headings,records){
 const table=n("table","classic-ledger-table");
 const head=n("thead"),tr=n("tr");
 for(const heading of headings)summaryCell(tr,heading,"th");
 head.append(tr);table.append(head);
 const body=n("tbody");
 for(const record of records){
  const row=n("tr");
  for(const value of record){
   const cls=typeof value==="number"&&value>0?"is-plus":
     typeof value==="number"&&value<0?"is-minus":"";
   const text=typeof value==="number"?signed(value):value;
   summaryCell(row,text,"td",cls);
  }
  body.append(row);
 }
 table.append(body);root.append(table);return table;
}
function details(root,label){
 const el=n("details","classic-ledger-details");
 const summary=n("summary","",label);el.append(summary);
 root.append(el);return el;
}
function chips(record){
 const values=[
  ...nonZeroBreakdown(record.combinations),
  ...nonZeroBreakdown(record.bonuses),
 ];
 return values.length?values.join("、"):"无额外番型与加成";
}
export function renderSettlement(root,view){
 const data=summarizeSettlement(view);
 root.replaceChildren();root.hidden=!data;
 if(!data)return;
 const h=n("h2","","本局收支结算");root.append(h);
 const line=n("p","classic-ledger-notice",
  data.wallPending?
   "牌山耗尽：流局查花猪／查大叫尚未完成入账核验。下表仅是已确认收支，不能视为最终结果。":
   data.posted?"胡牌、杠钱和流局赔付均以服务器正式入账数据为准。":
   "胡牌与杠钱均以服务器正式入账账本为准。");
 root.append(line);
 if(!data.totalsMatch||!data.zeroSum){
  root.append(n("p","classic-ledger-warning",
   "结算校验不一致：请以服务器账本为准，暂勿采用此表中的合计。"));
 }
 const summary=n("section","classic-ledger-section");
 summary.append(n("h3","","四家净收支"));
 const rows=data.seats.map(s=>[
  s.name+(s.won?"（已胡）":""),
  s.patterns.length?s.patterns.map(p=>
   (WIN_KIND[p.kind]||"胡")+"·"+p.name+" "+p.fan+"番").join("；"):"未胡",
  s.win,s.kong,s.draw,s.total,
 ]);
 financialTable(summary,["玩家","实际胡牌番型","胡牌积分",
  "杠钱","流局赔付","本局净收支"],rows);
 root.append(summary);
 const winSection=n("section","classic-ledger-section");
 winSection.append(n("h3","","胡牌番型与付款明细"));
 if(!data.wins.length)winSection.append(n("p","","本局无胡牌收入记录。"));
 data.wins.forEach((win,index)=>{
  const card=n("article","classic-ledger-win");
  card.append(n("strong","",String(index+1)+". "+seatName(win.winner)+
   " · "+(WIN_KIND[win.kind]||"胡")+" · "+
   (win.main_pattern||"未命名番型")+" · "+
   win.effective_fan+"番"+(win.raw_fan!==win.effective_fan?
    "（原始"+win.raw_fan+"番，按封顶入账）":"")));
  card.append(n("p","","牌型组合："+chips(win)));
  card.append(n("p","","付款方："+win.payers.map(seatName).join("、")+
   " · 每人 "+signed(win.amount_per_payer)+
   " · 实收 "+signed(win.total_received)));
  winSection.append(card);
 });
 if(data.ledgerEntries.length){
  const detail=details(winSection,"展开逐笔胡牌支付流水（"+
   data.ledgerEntries.length+"笔）");
  financialTable(detail,["胡牌方","支付方","事件","金额"],data.ledgerEntries.map(e=>[
   seatName(e.winner),seatName(e.payer),
   (WIN_KIND[e.kind]||e.kind||"胡牌")+" · "+(e.effective_fan??"—")+"番",
   e.amount,
  ]));
 }
 root.append(winSection);
 const kong=n("section","classic-ledger-section");
 kong.append(n("h3","","杠钱明细"));
 if(!data.kongPriced)kong.append(n("p","classic-ledger-warning",
   "本局未设置杠钱单价，杠事件不计价；不能把缺失金额当作零元收入。"));
 else kong.append(n("p","","服务器杠钱底分："+data.kongBase+
   "（杠账本已合并入本局净收支）"));
 if(!data.kongEvents.length)kong.append(n("p","","本局无杠事件。"));
 else {
  financialTable(kong,["杠牌方","杠种","付款方","每人付款",
   "状态／说明"],data.kongEvents.map(e=>[
    seatName(e.seat),KONG_KIND[e.type]||e.type,
    (e.payers||[]).map(seatName).join("、"),
    e.amount_per_payer??"未计价",
    e.status==="voided"?"已撤销／冲正":e.status==="posted"?"正式入账":"未计价",
  ]));
  if(data.kongEntries.length){
   const detail=details(kong,"展开杠钱逐笔实收实付与冲正（"+
    data.kongEntries.length+"笔）");
   financialTable(detail,["杠流水","支付方","收款方","方向","金额"],
    data.kongEntries.map(e=>[
     "#"+e.kong_id,seatName(e.payer),seatName(e.recipient),
     e.kind==="reversal"?"撤销冲正":"正常杠钱",e.amount,
    ]));
  }
 }
 root.append(kong);
 if(data.posted||data.wallPending){
  const draw=n("section","classic-ledger-section");
  draw.append(n("h3","","流局查花猪／查大叫"));
  if(!data.posted)draw.append(n("p","classic-ledger-warning",
    "服务器尚未核验完成，流局赔付不计入确认金额。"));
  else if(data.exhaustive?.entries?.length){
   const ledger=data.exhaustive.entries;
   const detail=details(draw,"查看流局赔付账本（"+ledger.length+"笔）");
   for(const entry of ledger){
    detail.append(n("p","",JSON.stringify(entry)));
   }
  }else draw.append(n("p","","流局无额外赔付。"));
  root.append(draw);
 }
 root.append(n("p","classic-ledger-footnote",
  "所有金额直接读取 Python 的 win_ledger、kong_ledger、"+
  "exhaustive_settlement 和 settled_balances，未在前端重算番数或倍数。"));
}
