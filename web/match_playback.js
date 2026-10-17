"use strict";
/* M3.16: public, post-commit action playback only.
   No intermediate hands, wall positions or concealed draws are reconstructed. */
(function(root,factory){
  const api=factory();
  if(typeof module!=="undefined" && module.exports)module.exports=api;
  if(root)root.MahTrainPlayback=api;
})(typeof window!=="undefined"?window:null,function(){
  const ALLOWED=new Set([
    "draw","discard","peng","ming_gang","an_gang",
    "bu_gang_declared","bu_gang","kong_supplement",
    "ron","multi_ron","rob_kong","self_draw_win",
  ]);
  const VISIBLE_TILE=new Set([
    "discard","peng","ming_gang","bu_gang_declared",
    "bu_gang","ron","multi_ron","rob_kong",
  ]);
  const NAMES={
    draw:"摸牌",discard:"出牌",peng:"碰牌",ming_gang:"明杠",
    an_gang:"暗杠",bu_gang_declared:"补杠待响应",
    bu_gang:"补杠",kong_supplement:"杠后补摸",
    ron:"点炮胡",multi_ron:"一炮多响",rob_kong:"抢杠胡",
    self_draw_win:"自摸胡牌",
  };
  function normalize(events,maxFrames=80){
    const allowed=(Array.isArray(events)?events:[])
      .filter(x=>x && ALLOWED.has(x.type));
    const omitted=Math.max(0,allowed.length-maxFrames);
    const tail=allowed.slice(omitted);
    // allowlist each output field: never propagate an_gang tile, unrevealed
    // draws, pending responses, hands, future wall or private draw info.
    return {omitted,frames:tail.map(item=>{
      const winners=item.type==="multi_ron" || item.type==="rob_kong" ||
        item.type==="ron" ? item.seats : null;
      const seat=Number.isInteger(item.seat)?item.seat:
        Number.isInteger(item.source)?item.source:null;
      const revealed=VISIBLE_TILE.has(item.type) &&
        typeof item.tile==="string"?item.tile:null;
      const winSeats=Array.isArray(winners)?
        winners.filter(x=>Number.isInteger(x)&&x>=0&&x<4):[];
      const isWin=["ron","multi_ron","rob_kong","self_draw_win"].includes(item.type);
      const cut=(item.type==="discard" &&
        (item.discard_kind==="tsumogiri"||item.discard_kind==="tedashi"))
        ?(item.discard_kind==="tsumogiri"?"摸切":"手切"):"";
      const actorLabel=(item.type==="ron"||item.type==="multi_ron"||
        item.type==="rob_kong") && winSeats.length?
        winSeats.map(n=>n+"号").join("、"):seat===0?"自己":
        seat===null?"牌桌":seat+"号AI";
      const label=actorLabel+" "+NAMES[item.type]+
        (cut?"（"+cut+"）":"");
      return {
        type:item.type,seat,winSeats,publicTile:revealed,
        concealed:!revealed&&["draw","kong_supplement","an_gang"].includes(item.type),
        label,isWin,
      };
    })};
  }
  function createController({onFrame,onDone,onStatus,clock,clearClock}){
    if(typeof onFrame!=="function"||typeof onDone!=="function"||
        typeof onStatus!=="function")throw new TypeError("playback callbacks required");
    const later=clock||setTimeout, cancel=clearClock||clearTimeout;
    let items=[],index=-1,timer=null,playing=false,paused=false,
      duration=550,completed=null;
    function clear(){if(timer!==null){cancel(timer);timer=null;}}
    function status(){onStatus({
      playing,paused,index,total:items.length,duration,
    });}
    function finish(){
      if(!playing)return;
      clear();playing=false;paused=false;
      const done=completed;completed=null;
      status();if(done)done();onDone();
    }
    function advance(){
      timer=null;
      if(!playing||paused)return;
      index++;
      if(index>=items.length){finish();return;}
      onFrame(items[index],index+1,items.length);
      status();
      timer=later(advance,duration);
    }
    return {
      start(frames,done){
        clear();items=Array.isArray(frames)?frames.slice():[];
        index=-1;playing=items.length>0;paused=false;
        completed=typeof done==="function"?done:null;
        if(playing){advance();}
        else {status();if(completed){const fn=completed;completed=null;fn();}onDone();}
        return playing;
      },
      pause(){if(!playing||paused)return;paused=true;clear();status();},
      resume(){if(!playing||!paused)return;paused=false;status();timer=later(advance,duration);},
      skip(){finish();},
      cancel(){clear();playing=false;paused=false;completed=null;status();},
      setSpeed(ms){
        if(![180,450,900].includes(ms))throw new RangeError("unsupported animation speed");
        duration=ms;
        if(playing&&!paused){clear();timer=later(advance,duration);}
        status();
      },
      getState(){return {playing,paused,index,total:items.length,duration};},
    };
  }
  return {normalize,createController};
});
