"use strict";
/* M3.90: explain already-recorded PUBLIC-KNOWLEDGE discard adviser ranks.
 * Do not recompute as an omniscient end-of-game solver: the wall and other
 * players' hands must NEVER enter these counterfactual comparisons.
 */
(function(root,factory){
  const api=factory();
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
  if(root)root.MahTrainCutQuality=api;
})(typeof window!=="undefined"?window:null,function(){
  const natural=n=>Number.isSafeInteger(n)&&n>=0;
  const valid=c=>c&&typeof c.tile==="string"&&
    Number.isSafeInteger(c.shanten)&&natural(c.effective_copies)&&
    (c.fan_weighted===null||c.fan_weighted===undefined||
     natural(c.fan_weighted));
  function inspect(cut){
    const best=Array.isArray(cut?.top3)?cut.top3[0]:null;
    // M3.88 snapshots know metrics for top-three entries. New M3.90
    // archives additionally retain a player cut ranked BELOW third.
    const actual=cut?.played_candidate||cut?.top3?.find(x=>x.tile===cut.discard);
    if(!valid(best)||!valid(actual)){
      return {kind:"unrated",text:"旧档案未保存本次实际切牌的完整评分，无法计算差距",
        shantenGap:null,copyGap:null,weightedGap:null,measured:false};
    }
    const stage=actual.shanten-best.shanten;
    const copy=best.effective_copies-actual.effective_copies;
    const bothTenpai=best.shanten===0&&actual.shanten===0&&
      natural(best.fan_weighted)&&natural(actual.fan_weighted);
    const weighted=bothTenpai?best.fan_weighted-actual.fan_weighted:null;
    const common={measured:true,shantenGap:stage,
      copyGap:stage===0?copy:null,
      weightedGap:weighted};
    if(cut.optimal){
      return {...common,kind:"optimal",text:"符合当前策略并列最优"};
    }
    if(stage>0){
      return {...common,kind:"shanten",text:"退向听 "+stage+
        " 级：应优先保持更低向听数"};
    }
    if(stage<0){
      return {...common,kind:"unrated",measured:false,
        text:"历史评分次序不一致，无法解释",copyGap:null,weightedGap:null};
    }
    if(bothTenpai&&weighted>0){
      return {...common,kind:"weighted",text:
        "同为听牌，基础番值加权未知张数上界少 "+weighted+
        "；有效张相差 "+copy+" 张（可为负数）"};
    }
    if(copy>0){
      return {...common,kind:"ukeire",text:
        "同向听数，有效进张未知张数上界少 "+copy+" 张"};
    }
    return {...common,kind:"tie_detail",
      text:"同向听且未观察到正向有效张差；最终排序还受基础番值权重或固定同分规则影响"};
  }

  function thirds(cuts){
    const names=["前段","中段","后段"];
    const parts=names.map(name=>({
      name,total:0,optimal:0,regressed:0,ukeireLoss:0,weightedLoss:0,
      unrated:0,
    }));
    if(!cuts?.length)return parts;
    cuts.forEach((cut,index)=>{
      const part=parts[Math.min(2,Math.floor(index*3/cuts.length))];
      const result=inspect(cut);
      part.total++;
      if(cut.optimal)part.optimal++;
      if(result.kind==="shanten")part.regressed++;
      if(result.kind==="ukeire")part.ukeireLoss++;
      if(result.kind==="weighted")part.weightedLoss++;
      if(result.kind==="unrated")part.unrated++;
    });
    return parts;
  }
  return {inspect,thirds};
});
