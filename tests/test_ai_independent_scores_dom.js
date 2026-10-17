"use strict";
// M3.31 fake-browser test: aggregate-only baseline official scores and CSV.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");

class Element{
  constructor(tag="div"){
    this.tag=tag;this.children=[];this.textContent="";this.value="";
    this.hidden=false;this.disabled=false;this.handlers={};this.style={};this.attributes={};
  }
  append(...children){this.children.push(...children)}
  replaceChildren(...children){this.children=[...children]}
  addEventListener(event,handler){this.handlers[event]=handler}
  click(){this.clicked=true}
  setAttribute(k,v){this.attributes[k]=v}
}
const ids=[
  "ai-baseline-start","ai-baseline-results","ai-baseline-error",
  "ai-baseline-progress","ai-baseline-seed","ai-baseline-seeds",
  "ai-baseline-summary","ai-baseline-caveat","ai-baseline-differences",
  "ai-baseline-export","ai-baseline-official",
  "ai-baseline-official-export","ai-baseline-official-caveat",
  "ai-baseline-official-levels","ai-baseline-official-differences",
  "ai-baseline-decision-scores","ai-baseline-decision-caveat",
  "ai-baseline-decision-table","ai-baseline-decision-disagreements",
  "ai-baseline-decision-export",
];
const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));
nodes["ai-baseline-seed"].value="11";
nodes["ai-baseline-seeds"].value="1";
const opponents=["baseline","basic","advanced","challenge"];
const levels=Object.fromEntries(opponents.map(name=>[name,{
  exposures:4,wins:0,deal_ins:0,discards:3,minimum_shanten:2,
  local_optimal:2,win_event_fraction:0,min_shanten_fraction:2/3,
  local_optimal_fraction:2/3,
}]));
const comparison=Object.fromEntries(opponents.slice(1).map(level=>[level,{
  win_event_fraction:0,min_shanten_fraction:0,local_optimal_fraction:0,
}]));
const officialTotals=[-120,-40,40,120];
const rows=Object.fromEntries(opponents.map((level,index)=>[level,{
  seat_exposures:4,official_total:officialTotals[index],
  official_mean_per_exposure:officialTotals[index]/4,
}]));
const official={
  protocol:"paired_initial_shuffle_4_rotation_official_a_v1",
  room_coefficient:100,fan_cap:3,requested_seeds:1,valid_seeds:1,
  excluded_seed_count:0,complete_games:4,
  levels:rows,per_seed:[{seed:11,levels:rows}],
  paired_differences_vs_baseline:{basic:20,advanced:40,challenge:60},
  intervals:null,
};
const decision={
  protocol:"decision_quality_vs_rule_a_official_points_v1",
  valid_seeds:1,excluded_seed_count:0,complete_games:4,
  levels:Object.fromEntries(opponents.map((level,index)=>[level,{
    seat_exposures:4,discards:8,min_shanten_cuts:index*2,
    local_optimal_cuts:index*2,effective_copies_total:(3+index)*8,
    min_shanten_fraction:index/4,local_optimal_fraction:index/4,
    mean_effective_copies:3+index,mean_shanten_regret:3-index,
    deal_in_events:index,deal_in_events_per_100_discards:index*12.5,
  }])),
  direction_disagreements_vs_baseline:Object.fromEntries(
    opponents.slice(1).map(level=>[level,{
      comparable_seeds:1,higher_min_shanten_but_lower_score_seeds:1,
      lower_min_shanten_but_higher_score_seeds:0,
    }]),
  ),
};
const report={
  opponents,levels,independent_shuffle_seeds:1,intervals:null,
  paired_differences_vs_baseline:comparison,
  per_seed:[{seed:11,levels}],official_score_analysis:official,
  decision_score_diagnostics:decision,
};
const requests=[];
const fetch=async(_url,options)=>{
  const action=JSON.parse(options.body).action;
  requests.push(action);
  if(action==="ai_baseline_start"){
    return {ok:true,json:async()=>({baseline_token:"test-token"})};
  }
  if(action==="ai_baseline_status"){
    return {ok:true,json:async()=>({baseline:{
      status:"done",completed_games:4,total_games:4,overview:report,
    }})};
  }
  throw Error("unexpected action: "+action);
};
let csv=null,exportClicks=0;
const document={
  getElementById(id){assert.ok(nodes[id],"missing DOM control "+id);return nodes[id]},
  createElement(tag){
    const node=new Element(tag);
    if(tag==="a")node.click=()=>exportClicks++;
    return node;
  },
};
const ctx={window:{},document,fetch,
  Blob:class{constructor(parts){csv=parts.join("")}},
  URL:{createObjectURL:()=>"blob:public",revokeObjectURL(){}},
  setTimeout(){},console};
vm.runInNewContext(
  fs.readFileSync(path.join(__dirname,"../web/ai_baseline.js"),"utf8"),
  ctx,{filename:"ai_baseline.js"});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  ctx.window.MahTrainAIBaseline.init();
  nodes["ai-baseline-start"].handlers.click();
  for(let i=0;i<6;i++)await settle();
  assert.deepEqual(requests,["ai_baseline_start","ai_baseline_status"]);
  assert.equal(nodes["ai-baseline-results"].hidden,false);
  assert.equal(nodes["ai-baseline-official"].hidden,false);
  assert.equal(nodes["ai-baseline-official-levels"].children.length,4);
  assert.equal(nodes["ai-baseline-official-differences"].children.length,3);
  const notice=nodes["ai-baseline-official-caveat"].textContent;
  assert.ok(notice.includes("核验1个"));
  assert.ok(notice.includes("排除0个"));
  assert.ok(notice.includes("少于5个"));
  assert.ok(nodes["ai-baseline-official-levels"].children[0].children[0]
    .textContent.includes("独立牌形基线"));
  assert.ok(nodes["ai-baseline-official-levels"].children[3].children[1]
    .children[2].children[1].textContent.includes("+30"));
  assert.ok(nodes["ai-baseline-official-differences"].children[2]
    .textContent.includes("+60"));
  assert.equal(nodes["ai-baseline-decision-scores"].hidden,false);
  assert.equal(nodes["ai-baseline-decision-table"].children.length,5);
  assert.equal(nodes["ai-baseline-decision-table"].children[0].children.length,7);
  assert.equal(nodes["ai-baseline-decision-disagreements"].children.length,3);
  assert.ok(nodes["ai-baseline-decision-table"].children[4].children[4]
    .textContent.includes("6.00"));
  assert.ok(nodes["ai-baseline-decision-table"].children[4].children[2]
    .textContent.includes("75.0%"));
  assert.ok(nodes["ai-baseline-decision-caveat"].textContent.includes("核验种子：1"));
  nodes["ai-baseline-decision-export"].handlers.click();
  assert.equal(exportClicks,1);
  assert.ok(csv.includes("challenge,1,4,30,8,0.75,0.75,6"));
  assert.ok(!csv.includes("opponent_hands")&&!csv.includes("private_tile"));
  nodes["ai-baseline-official-export"].handlers.click();
  assert.equal(exportClicks,2);
  assert.ok(csv.includes("11,baseline,4,-120,-30"));
  assert.ok(csv.includes("11,challenge,4,120,30"));
  assert.ok(!csv.includes("future_wall"));
  assert.ok(!csv.includes("opponent_hands"));
  // All four rotations missing one verified wall should suppress
  // official averages while retaining the original event-stat panel.
  report.official_score_analysis={
    ...official,valid_seeds:0,excluded_seed_count:1,
    complete_games:0,per_seed:[],
    levels:Object.fromEntries(opponents.map(level=>[level,{
      seat_exposures:0,official_total:0,official_mean_per_exposure:null,
    }])),
    paired_differences_vs_baseline:{basic:null,advanced:null,challenge:null},
  };
  report.decision_score_diagnostics={
    ...decision,valid_seeds:0,excluded_seed_count:1,complete_games:0,
    levels:Object.fromEntries(opponents.map(level=>[level,{
      seat_exposures:0,discards:0,min_shanten_cuts:0,local_optimal_cuts:0,
      effective_copies_total:0,mean_effective_copies:null,
      min_shanten_fraction:null,local_optimal_fraction:null,
      mean_shanten_regret:null,deal_in_events:0,
      deal_in_events_per_100_discards:null,
    }])),
    direction_disagreements_vs_baseline:Object.fromEntries(
      opponents.slice(1).map(level=>[level,{
        comparable_seeds:0,higher_min_shanten_but_lower_score_seeds:0,
        lower_min_shanten_but_higher_score_seeds:0,
      }]),
    ),
  };
  nodes["ai-baseline-start"].handlers.click();
  for(let i=0;i<6;i++)await settle();
  assert.equal(nodes["ai-baseline-official-levels"].children.length,4);
  assert.ok(nodes["ai-baseline-decision-table"].children[1].children[2]
    .textContent.includes("无可用样本"));
  nodes["ai-baseline-decision-export"].handlers.click();
  assert.equal(exportClicks,3);
  assert.ok(csv.includes("challenge,0,0,,0"));
  assert.ok(!csv.includes("NaN"));
  assert.ok(nodes["ai-baseline-official-caveat"].textContent.includes("排除1个"));
  assert.ok(nodes["ai-baseline-official-levels"].children[0].children[1]
    .children[2].children[1].textContent.includes("无已核验局"));
  nodes["ai-baseline-official-export"].handlers.click();
  assert.equal(exportClicks,4);
  assert.equal(csv.trim().split("\r\n").length,1,
    "unverified seed must not enter official-point CSV");
  console.log("M3.32 joint decision metrics vs verified score, missing data and aggregate CSV: PASS");
  console.log("M3.31 4-policy official-score cards, exclusion, paired difference, CSV privacy: PASS");
})().catch(error=>{console.error(error);process.exitCode=1});
