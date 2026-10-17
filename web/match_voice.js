"use strict";
/* M3.24 four-player public action announcements (Web Speech API).
   Only server-published events; never speak a concealed tile, wall or
   pending private choice. The browser's speech engine/voices determine
   availability, voice quality and any platform-specific processing. */
(function(root,factory){
  const api=factory();
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
  if(root)root.MahTrainMatchVoice=api;
})(typeof window!=="undefined"?window:null,function(){
  const SUITS={m:"万",s:"条",p:"筒"};
  const DIGITS=["","一","二","三","四","五","六","七","八","九"];
  const announced=new Set([
    "discard","peng","ming_gang","an_gang","bu_gang",
    "ron","multi_ron","rob_kong","self_draw_win",
  ]);
  const validTile=t=>typeof t==="string"&&/^[msp][1-9]$/.test(t);
  function tileLabel(t){
    return validTile(t)?DIGITS[Number(t[1])]+SUITS[t[0]]:"";
  }
  function phrase(item){
    if(!item||!announced.has(item.type))return "";
    const seat=Number.isInteger(item.seat)&&item.seat>=0&&item.seat<=3
      ?item.seat:null;
    const lead=seat===0?"我方":seat===null?"牌桌":seat+"号";
    const tile=tileLabel(item.publicTile);
    const winners=Array.isArray(item.winSeats)?
      [...new Set(item.winSeats.filter(n=>Number.isInteger(n)&&n>=0&&n<=3))]:[];
    switch(item.type){
      case "discard":return tile||""; // only tile name, no player prefix
      case "peng":return lead+"碰"+tile;
      case "ming_gang":return lead+"明杠"+tile;
      case "an_gang":return lead+"暗杠"; // do not reveal concealed tile
      case "bu_gang":return lead+"补杠"+tile;
      case "ron":return (winners.length?winners.map(x=>x+"号").join("、"):lead)+"胡了";
      case "multi_ron":return (winners.length?winners.map(x=>x+"号").join("、"):"多家")+"一炮多响，胡了";
      case "rob_kong":return (winners.length?winners.map(x=>x+"号").join("、"):lead)+"抢杠胡";
      case "self_draw_win":return lead+"自摸，胡了";
      default:return "";
    }
  }
  // Speech is entirely client-side and receives only public playback frames.
  // A manual repeat replays the last sanitized spoken phrase, not match state.
  const RATES=Object.freeze({slow:0.85,normal:1.12,fast:1.35});
  function create(env){
    const host=env||{};
    const synth=host.speechSynthesis;
    const Utterance=host.SpeechSynthesisUtterance;
    const supported=!!(synth&&typeof synth.speak==="function"&&typeof Utterance==="function");
    let enabled=supported,rate="normal",lastText="";
    let pendingFinish=null;
    const later=typeof host.setTimeout==="function"
      ?host.setTimeout.bind(host):setTimeout;
    const cancelLater=typeof host.clearTimeout==="function"
      ?host.clearTimeout.bind(host):clearTimeout;
    function clear(){
      // Explicit skips/mutes must release the playback gate as well as audio.
      if(pendingFinish)pendingFinish();
      if(supported&&typeof synth.cancel==="function")synth.cancel();
    }
    function speakText(text){
      if(!enabled||!supported||!text)return false;
      try{
        // Interrupt stale speech, especially during fast public playback.
        clear();
        const speech=new Utterance(text);
        speech.lang="zh-CN";
        speech.rate=RATES[rate];
        speech.volume=0.95;
        synth.speak(speech);
        lastText=text;
        return true;
      }catch(_error){return false;}
    }
    function speakTextWait(text){
      if(!supported||!enabled||!text)return Promise.resolve();
      return new Promise(resolve=>{
        let completed=false,watchdog=null;
        function finish(){
          if(completed)return;
          completed=true;
          if(watchdog!==null)cancelLater(watchdog);
          if(pendingFinish===finish)pendingFinish=null;
          resolve();
        }
        clear();
        try{
          const speech=new Utterance(text);
          speech.lang="zh-CN";
          speech.rate=RATES[rate];
          speech.volume=0.95;
          speech.onend=finish;
          speech.onerror=finish;
          pendingFinish=finish;
          lastText=text;
          // Some engines never fire onend after a background tab or failed
          // voice. Unlock interaction rather than freezing the table.
          watchdog=later(finish,2500);
          synth.speak(speech);
        }catch(_error){finish();}
      });
    }
    function announceEventsWait(events){
      const text=(Array.isArray(events)?events:[]).map(phrase)
        .filter(Boolean).slice(-8).join("。");
      return speakTextWait(text);
    }
    function announceFrameWait(frame){
      const actions=Array.isArray(frame?.announcements)
        ?frame.announcements:[frame];
      return announceEventsWait(actions);
    }
    function announceEvents(events){
      const text=(Array.isArray(events)?events:[]).map(phrase).filter(Boolean).slice(-8).join("。");
      return speakText(text);
    }
    function announceFrame(frame){
      const actions=Array.isArray(frame?.announcements)?
        frame.announcements:[frame];
      return announceEvents(actions);
    }
    return {
      supported,announceEvents,announceFrame,
      announceEventsWait,announceFrameWait,clear,
      // A new round must never offer a repeat from the previous round.
      reset(){lastText="";clear();},
      canRepeat:()=>supported&&enabled&&!!lastText,
      repeatLast(){return speakText(lastText);},
      getRate:()=>rate,
      setRate(value){
        if(Object.prototype.hasOwnProperty.call(RATES,value))rate=value;
        return rate;
      },
      getEnabled:()=>enabled,
      setEnabled(value){
        enabled=supported&&value===true;
        if(!enabled)clear();
        return enabled;
      },
    };
  }
  return {create,phrase,tileLabel};
});
