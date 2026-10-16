"use strict";
/* Resolution-independent MahTrain tile faces; native SVG, no remote images. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const numbers = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"];
  const ink = "#214c45", green = "#24704e", red = "#c13d35", blue = "#27678a";
  function el(tag, attrs={}, text=null) {
    const e=document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k, String(v)));
    if (text!==null) e.textContent=text;
    return e;
  }
  function circle(svg,x,y,r,fill,stroke=null,sw=1) {
    svg.append(el("circle",{cx:x,cy:y,r,fill, ...(stroke?{stroke,"stroke-width":sw}:{})}));
  }
  function text(svg,x,y,str,size,fill,weight="700") {
    svg.append(el("text",{x,y,fill,"text-anchor":"middle","font-size":size,
      "font-family":'"Noto Serif CJK SC","Microsoft YaHei","PingFang SC",serif',
      "font-weight":weight},str));
  }
  function dot(svg,x,y,size=7,color=green) {
    circle(svg,x,y,size,color,ink,1.1);
    circle(svg,x,y,size*0.65,"#e3f2df");
    circle(svg,x,y,size*0.28,color);
  }
  function tong(svg,n) {
    const patterns={
      1:[[32,43]],2:[[20,27],[44,59]],3:[[20,24],[32,43],[44,62]],
      4:[[20,27],[44,27],[20,59],[44,59]],
      5:[[20,25],[44,25],[32,43],[20,61],[44,61]],
      6:[[22,22],[42,22],[22,43],[42,43],[22,64],[42,64]],
      7:[[22,19],[42,19],[22,36],[42,36],[22,53],[42,53],[32,68]],
      8:[[22,17],[42,17],[22,34],[42,34],[22,51],[42,51],[22,68],[42,68]],
      9:[[16,22],[32,22],[48,22],[16,43],[32,43],[48,43],[16,64],[32,64],[48,64]]
    };
    const size=n===1?13:n<=5?8.3:n<=8?6.2:5.9;
    patterns[n].forEach(([x,y],i)=>dot(svg,x,y,size,i%3===2?red:green));
  }
  function bamboo(svg,x,y,scale=1,col=green) {
    const width=8*scale,height=13*scale;
    svg.append(el("rect",{x:x-width/2,y:y-height/2,width,height,rx:2.1*scale,fill:col}));
    svg.append(el("path",{d:`M ${x-width/2+1} ${y} H ${x+width/2-1}`,
      stroke:"#e7f0d0","stroke-width":2*scale}));
    svg.append(el("path",{d:`M ${x} ${y-height/2+1} V ${y+height/2-1}`,
      stroke:"#d0e6ce","stroke-width":.9*scale}));
  }
  function suo(svg,n) {
    if(n===1) {
      // Large single bamboo stalk with foliage; clearly distinguishable from pips.
      svg.append(el("path",{d:"M32 13 Q25 30 31 47 Q37 60 30 73",fill:"none",stroke:green,"stroke-width":5}));
      for(const [x,y,dir] of [[29,22,-1],[34,30,1],[29,43,-1],[35,53,1]]) {
        svg.append(el("ellipse",{cx:x+dir*8,cy:y,rx:8,ry:3.5,
          transform:`rotate(${dir*27} ${x+dir*8} ${y})`,fill:dir>0?blue:green}));
      }
      text(svg,32,80,"竹",9,red);
      return;
    }
    const patterns={
      2:[[32,28],[32,58]],3:[[32,21],[22,54],[42,54]],
      4:[[22,26],[42,26],[22,58],[42,58]],
      5:[[22,23],[42,23],[32,43],[22,63],[42,63]],
      6:[[22,22],[42,22],[22,43],[42,43],[22,64],[42,64]],
      7:[[22,17],[42,17],[22,34],[42,34],[22,51],[42,51],[32,68]],
      8:[[22,16],[42,16],[22,34],[42,34],[22,52],[42,52],[22,70],[42,70]],
      9:[[16,19],[32,19],[48,19],[16,43],[32,43],[48,43],[16,67],[32,67],[48,67]]
    };
    let scale=n<=5?1.14:n===9?.72:.86;
    patterns[n].forEach(([x,y],i)=>bamboo(svg,x,y,scale,i%4===2?blue:green));
  }
  function wan(svg,n) {
    text(svg,32,39,numbers[n],29,n===1?blue:ink);
    text(svg,32,73,"萬",31,red);
  }
  function render(tile) {
    if(!/^[msp][1-9]$/.test(tile)) return null;
    const s=tile[0],n=Number(tile[1]);
    const svg=el("svg",{viewBox:"0 0 64 86",xmlns:NS,"aria-hidden":"true",
      focusable:"false",class:"tile-vector"});
    // The tile edge itself is CSS; the subtle vector border keeps art crisp.
    svg.append(el("rect",{x:3,y:3,width:58,height:80,rx:5,
      fill:"#fffefa",stroke:"#c5d5be","stroke-width":1.8}));
    if(s==="m")wan(svg,n);
    else if(s==="p")tong(svg,n);
    else suo(svg,n);
    return svg;
  }
  window.MahTrainTiles={render};
})();
