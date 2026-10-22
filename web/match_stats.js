"use strict";
/* M3.46: SVG chart of VERIFIED, completed match scorecard only.
   No invented win rate and no opponent concealed tiles or remote chart APIs. */
(function(root,factory){
  const api=factory();
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
  if(root)root.MahTrainMatchStats=api;
})(typeof window!=="undefined"?window:null,function(){
  const NS="http://www.w3.org/2000/svg";
  const sign=n=>(n>0?"+":"")+n;
  const number=x=>typeof x==="number"&&Number.isFinite(x)?x:0;
  function summary(board){
    const games=Number.isSafeInteger(board?.valid_games)&&board.valid_games>=0
      ?board.valid_games:0;
    const seat=Array.isArray(board?.seats)?board.seats[0]||{}:{};
    const pos=number(seat.positive_games),neg=number(seat.negative_games),
      zero=number(seat.zero_games);
    return {
      games,excluded:number(board?.excluded_games),
      settled:number(seat.settled_total),avg:games?
        number(seat.settled_total)/games:0,
      hu:number(seat.hu_total),draw:number(seat.draw_total),
      positive:pos,negative:neg,zero,
      positiveRate:games?pos/games*100:0,
    };
  }
  function makeLinePoints(trend){
    const values=trend.map(item=>number(item.cumulative));
    const lo=Math.min(0,...values),hi=Math.max(0,...values);
    const span=Math.max(1,hi-lo);
    const left=56,right=690,top=20,bottom=194;
    const points=values.map((v,i)=>({
      x:left+(values.length===1?.5:i/(values.length-1))*(right-left),
      y:bottom-(v-lo)/span*(bottom-top),
      value:v,
    }));
    return {points,lo,hi,zeroY:bottom-(0-lo)/span*(bottom-top)};
  }
  function render(board,doc){
    const d=doc||(typeof document!=="undefined"?document:null);
    if(!d)return;
    const by=id=>d.getElementById(id);
    const metric=by("match-stats-metrics"),
      curve=by("match-stats-cumulative"),outcome=by("match-stats-outcomes");
    if(!metric||!curve||!outcome)return;
    metric.replaceChildren();curve.replaceChildren();outcome.replaceChildren();
    const stats=summary(board);
    const el=(tag,cls,text)=>{
      const n=d.createElement(tag);
      if(cls)n.className=cls;
      if(text!==undefined)n.textContent=String(text);
      return n;
    };
    const metrics=[
      ["已核验对局",stats.games+" 局"],
      ["累计正式净额",sign(stats.settled)],
      ["场均正式净额",sign(Number(stats.avg.toFixed(1)))],
      ["正收益局占比",stats.positiveRate.toFixed(1)+"%"],
    ];
    for(const [label,value] of metrics){
      const card=el("div","match-stat-metric");
      card.append(el("span","",label),el("strong","",value));
      metric.append(card);
    }
    const history=(Array.isArray(board?.trend)?board.trend:[])
      .filter(x=>x&&Number.isFinite(x.cumulative)&&
        Number.isFinite(x.score));
    if(!history.length){
      curve.append(el("p","match-stats-empty",
        "暂无可核验的已完成对局，完成一次人机对战后这里会显示真实积分曲线。"));
    }else{
      const {points,lo,hi,zeroY}=makeLinePoints(history);
      const svg=d.createElementNS(NS,"svg");
      svg.setAttribute("viewBox","0 0 720 240");
      svg.setAttribute("role","img");
      svg.setAttribute("aria-label",
        "所选周期"+history.length+"局正式累计积分走势，从"+
        sign(points[0].value)+"到"+sign(points.at(-1).value));
      const svgNode=(tag,attrs={})=>{
        const n=d.createElementNS(NS,tag);
        for(const [key,val] of Object.entries(attrs))
          n.setAttribute(key,String(val));
        return n;
      };
      const axis=svgNode("line",{x1:56,x2:690,y1:zeroY,y2:zeroY,
        class:"match-stats-zero-line"});
      svg.append(axis);
      for(const [value,y] of [[hi,20],[lo,194]]){
        const label=svgNode("text",{x:44,y:y+4,
          "text-anchor":"end",class:"match-stats-axis-label"});
        label.textContent=sign(value);
        svg.append(label);
      }
      const poly=svgNode("polyline",{
        points:points.map(p=>p.x.toFixed(1)+","+p.y.toFixed(1)).join(" "),
        class:"match-stats-line",
      });
      svg.append(poly);
      points.forEach((p,i)=>{
        const dot=svgNode("circle",{cx:p.x.toFixed(1),cy:p.y.toFixed(1),
          r:i===points.length-1?5.2:3.6,
          class:"match-stats-dot"});
        const title=svgNode("title");
        const day=String(history[i].created_at||"").slice(0,10);
        title.textContent=day+" · 单局净额 "+
          sign(history[i].score)+" · 截至该局累计 "+sign(p.value);
        dot.append(title);svg.append(dot);
      });
      for(const [i,anchor] of [[0,"start"],[history.length-1,"end"]]){
        const label=svgNode("text",{
          x:points[i].x,y:224,"text-anchor":anchor,
          class:"match-stats-axis-label",
        });
        label.textContent=String(history[i].created_at||"").slice(0,10);
        svg.append(label);
        if(history.length===1)break;
      }
      curve.append(svg);
      curve.append(el("p","match-stats-chart-summary",
        "所选周期显示的"+history.length+"局："+
        sign(points[0].value)+" → "+sign(points.at(-1).value)+
        "，最新单局 "+sign(history.at(-1).score)));
    }
    if(!stats.games){
      outcome.append(el("p","match-stats-empty","暂无可统计的正负收益局数。"));
    }else{
      for(const [name,count,cls] of [
        ["正收益",stats.positive,"positive"],
        ["负收益",stats.negative,"negative"],
        ["零净额",stats.zero,"zero"]]){
        const row=el("div","match-stats-outcome-row");
        row.append(el("span","",name));
        const track=el("div","match-stats-outcome-track");
        const fill=el("span","match-stats-outcome-fill is-"+cls);
        fill.style.width=(Math.max(0,Math.min(100,count/stats.games*100))).toFixed(1)+"%";
        track.append(fill);row.append(track);
        row.append(el("strong","",count+" 局 · "+
          (count/stats.games*100).toFixed(1)+"%"));
        outcome.append(row);
      }
      outcome.append(el("p","match-stats-chart-summary",
        "0号座位：胡牌部分 "+sign(stats.hu)+
        " · 流局部分 "+sign(stats.draw)+
        "。这里统计的是每局正式净额正负，不等同胡牌次数。"));
    }
  }
  return {render,summary,makeLinePoints};
});
