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
  // A strict public-board allowlist. Never forward hidden hands, a private
  // latest draw, unrevealed kong tiles or the actual future wall.
  function normalizeBoard(board){
    if(!board||!Array.isArray(board.hand_counts)||
        board.hand_counts.length!==4||!Array.isArray(board.melds)||
        board.melds.length!==4||!Array.isArray(board.discards)||
        !Array.isArray(board.won)||board.won.length!==4||
        !Number.isInteger(board.wall_count)||board.wall_count<0){
      return null;
    }
    const validTile=t=>typeof t==="string"&&/^[msp][1-9]$/.test(t);
    const seat=n=>Number.isInteger(n)&&n>=0&&n<=3;
    const count=n=>Number.isInteger(n)&&n>=0&&n<=14;
    if(!board.hand_counts.every(count)||!board.melds.every(Array.isArray))
      return null;
    const melds=board.melds.map(groups=>groups.map(group=>{
      const type=["peng","ming_gang","an_gang","bu_gang"].includes(group?.type)
        ?group.type:"unknown";
      return {type,tile:type==="an_gang"?null:
        validTile(group?.tile)?group.tile:null};
    }));
    const discards=board.discards.filter(x=>seat(x?.seat)&&validTile(x?.tile))
      .map(x=>{
        const item={seat:x.seat,tile:x.tile};
        if(seat(x.claimed_by))item.claimed_by=x.claimed_by;
        if(Array.isArray(x.won_by))item.won_by=x.won_by.filter(seat);
        if(x.discard_kind==="tsumogiri"||x.discard_kind==="tedashi")
          item.discard_kind=x.discard_kind;
        if(x.rob_kong===true)item.rob_kong=true;
        return item;
      });
    return {
      phase:typeof board.phase==="string"?board.phase:"",
      turn:seat(board.turn)?board.turn:null,
      wall_count:board.wall_count,hand_counts:[...board.hand_counts],
      melds,discards,won:board.won.map(Boolean),
    };
  }
  function normalizeSteps(steps,maxFrames=80,initialBoard=null){
    const accepted=[];
    let previous=normalizeBoard(initialBoard);
    for(const step of Array.isArray(steps)?steps:[]){
      const board=normalizeBoard(step?.board);
      const events=normalize(step?.events).frames;
      if(!board||!events.length)continue;
      // A rules call may emit several events. The post-call public board
      // is authoritative; we do NOT fake an intermediate board per event.
      const last=events[events.length-1];
      const winner=events.find(f=>f.isWin);
      const exposed=[...events].reverse().find(f=>f.publicTile);
      const actionTypes=events.map(f=>f.type);
      const isKong=actionTypes.some(type=>[
        "an_gang","ming_gang","bu_gang","bu_gang_declared",
      ].includes(type));
      const isPeng=actionTypes.includes("peng");
      const isWin=events.some(f=>f.isWin);
      const tailDraw=actionTypes.includes("kong_supplement");
      const changes=previous?{
        wall:board.wall_count-previous.wall_count,
        backs:board.hand_counts.map((n,i)=>n-previous.hand_counts[i]),
        melds:board.melds.map((n,i)=>n.length-previous.melds[i].length),
        rivers:board.discards.length-previous.discards.length,
      }:null;
      accepted.push({
        ...last,label:events.map(f=>f.label).join(" → "),
        chain:events.map(f=>f.label),
        actionTypes,
        publicTile:exposed?.publicTile||null,
        isWin,winSeats:winner?.winSeats||last.winSeats,
        isKong,isPeng,tailDraw,
        important:isKong||isPeng||isWin,
        holdScale:isWin?2.2:(isKong?1.7:(isPeng?1.4:1)),
        changes,board,
      });
      previous=board;
    }
    const omitted=Math.max(0,accepted.length-maxFrames);
    return {omitted,frames:accepted.slice(omitted)};
  }
  function highlightFrames(frames){
    if(!Array.isArray(frames)||!frames.length)return [];
    // The final AUTHENTIC post-action snapshot must always be included,
    // even when all earlier non-critical draws/discards were skipped.
    return frames.filter((frame,index)=>
      frame.important||index===frames.length-1);
  }
  function createController({onFrame,onDone,onStatus,clock,clearClock}){
    if(typeof onFrame!=="function"||typeof onDone!=="function"||
        typeof onStatus!=="function")throw new TypeError("playback callbacks required");
    const later=clock||setTimeout, cancel=clearClock||clearTimeout;
    let items=[],index=-1,timer=null,playing=false,paused=false,
      duration=550,completed=null;
    function clear(){if(timer!==null){cancel(timer);timer=null;}}
    function schedule(){
      const multiplier=items[index]?.holdScale;
      timer=later(advance,Math.round(duration*(
        Number.isFinite(multiplier)&&multiplier>=1&&multiplier<=4
        ?multiplier:1)));
    }
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
      schedule();
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
      resume(){if(!playing||!paused)return;paused=false;status();schedule();},
      step(){
        if(!playing||!paused)return;
        index++;
        if(index>=items.length){finish();return;}
        onFrame(items[index],index+1,items.length);
        status();
      },
      skip(){finish();},
      cancel(){clear();playing=false;paused=false;completed=null;status();},
      setSpeed(ms){
        if(![180,450,900].includes(ms))throw new RangeError("unsupported animation speed");
        duration=ms;
        if(playing&&!paused){clear();schedule();}
        status();
      },
      getState(){return {playing,paused,index,total:items.length,duration};},
    };
  }
  return {normalize,normalizeSteps,highlightFrames,createController};
});
