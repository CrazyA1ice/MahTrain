"use strict";
/* No external audio files; sounds are generated locally with Web Audio.
 * Context is unlocked synchronously by the actual mouse/touch/key action. */
(function(){
  const AudioCtor=window.AudioContext||window.webkitAudioContext;
  let context=null;
  let enabled=true;
  function unlock(){
    if(!enabled || !AudioCtor)return;
    try{
      if(!context)context=new AudioCtor();
      if(context.state==="suspended")void context.resume().catch(()=>{});
    }catch(e){context=null;}
  }
  function note(freq,at,length,peak=0.10,wave="triangle"){
    const osc=context.createOscillator();
    const gain=context.createGain();
    osc.type=wave;
    osc.frequency.setValueAtTime(freq,at);
    osc.frequency.exponentialRampToValueAtTime(Math.max(60,freq*.72),at+length);
    gain.gain.setValueAtTime(.0001,at);
    gain.gain.exponentialRampToValueAtTime(peak,at+.008);
    gain.gain.exponentialRampToValueAtTime(.0001,at+length);
    osc.connect(gain);gain.connect(context.destination);
    osc.start(at);osc.stop(at+length+.01);
  }
  function play(kind){
    if(!enabled||!AudioCtor)return;
    unlock();
    if(!context || context.state!=="running")return;
    const at=context.currentTime+.005;
    if(kind==="draw"){
      note(380,at,.078,.065);note(510,at+.042,.073,.065);
    }else if(kind==="discard"){
      note(600,at,.035,.095,"square");
      note(210,at+.018,.115,.090,"triangle");
    }else if(kind==="kong"){
      for(let i=0;i<3;i++)note(270-i*20,at+i*.108,.095,.125);
    }else if(kind==="win"){
      [523,659,784,1046].forEach((f,i)=>note(f,at+i*.106,.29,.11,"sine"));
    }
  }
  window.MahTrainSound={
    unlock,play,
    getEnabled:()=>enabled&&!!AudioCtor,
    setEnabled(value){
      enabled=!!value;
      if(!enabled&&context&&context.state==="running")void context.suspend().catch(()=>{});
      if(enabled)unlock();
      return enabled&&!!AudioCtor;
    },
  };
})();
