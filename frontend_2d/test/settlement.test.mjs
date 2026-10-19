import test from 'node:test';
import assert from 'node:assert/strict';
import {
 summarizeSettlement,recentWins,publicActions,winTitle,nonZeroBreakdown,signed,patternLabel,
} from '../src/settlement.mjs';
const snapshot=()=>({
 phase:'finished',won:[true,false,true,false],
 win_ledger:{balances:[300,-200,500,-600],
  wins:[
   {winner:0,source:1,kind:'ron',tile:'m3',
    main_pattern:'清一色',effective_fan:3,raw_fan:4,
    combinations:{清一色:2},bonuses:{杠上炮:1},
    amount_per_payer:300,total_received:300,payers:[1]},
   {winner:2,source:3,kind:'self_draw',
    main_pattern:'对对胡',effective_fan:2,raw_fan:2,
    combinations:{对对胡:2},bonuses:{},
    amount_per_payer:250,total_received:500,payers:[1,3]},
  ],
  entries:[{winner:0,payer:1,amount:300,kind:'ron',effective_fan:3}],
 },
 kong_ledger:{base:100,balances:[200,-100,0,-100],
  events:[{id:1,type:'an_gang',seat:0,payers:[1,3],
    amount_per_payer:200,status:'posted'}],
  entries:[{kong_id:1,kind:'charge',payer:1,recipient:0,amount:100},
    {kong_id:1,kind:'charge',payer:3,recipient:0,amount:100}],
 },
 exhaustive_settlement:null,
 settled_balances:[500,-300,500,-700],
});
test('settlement presents exact server balances; sum zero and no local fan recalculation',()=>{
 const s=summarizeSettlement(snapshot());
 assert.ok(s);
 assert.deepEqual(s.seats.map(x=>x.total),[500,-300,500,-700]);
 assert.deepEqual(s.seats.map(x=>x.win),[300,-200,500,-600]);
 assert.deepEqual(s.seats.map(x=>x.kong),[200,-100,0,-100]);
 assert.equal(s.zeroSum,true);
 assert.equal(s.totalsMatch,true);
 assert.equal(s.seats[0].patterns[0].name,'清一色');
 assert.equal(s.seats[0].patterns[0].fan,3);
 assert.match(winTitle(s.wins[0]),/自己 点炮胡.*清一色.*3番.*\+300/);
 assert.deepEqual(nonZeroBreakdown(s.wins[0].bonuses),['杠上炮']);
});
test('unposted exhaustive does not pretend to have final net win income',()=>{
 const v=snapshot();
 v.phase='wall_exhausted';
 v.exhaustive_settlement={posted:false,balances:[90,-90,0,0],
  entries:[{amount:90}]};
 const s=summarizeSettlement(v);
 assert.equal(s.wallPending,true);
 assert.deepEqual(s.seats.map(x=>x.draw),[0,0,0,0]);
 assert.equal(s.posted,false);
});
test('posted exhaustive is included once and exact final server settlement wins',()=>{
 const v=snapshot();v.phase='wall_exhausted';
 v.exhaustive_settlement={posted:true,balances:[0,-40,40,0],entries:[{}]};
 v.settled_balances=[500,-340,540,-700];
 const s=summarizeSettlement(v);
 assert.equal(s.posted,true);assert.equal(s.wallPending,false);
 assert.deepEqual(s.seats.map(x=>x.draw),[0,-40,40,0]);
 assert.equal(s.totalsMatch,true);assert.equal(s.zeroSum,true);
});
test('reversed kong charges are read, never doubled or invented',()=>{
 const v=snapshot();v.kong_ledger.base=null;
 v.kong_ledger.balances=[0,0,0,0];
 v.kong_ledger.events[0].status='voided';
 v.kong_ledger.entries=[...v.kong_ledger.entries,
  {kong_id:1,kind:'reversal',payer:0,recipient:1,amount:100},
  {kong_id:1,kind:'reversal',payer:0,recipient:3,amount:100}];
 v.settled_balances=[300,-200,500,-600];
 const s=summarizeSettlement(v);
 assert.equal(s.kongPriced,false);
 assert.equal(s.kongEntries.length,4);
 assert.equal(s.seats[0].kong,0);
 assert.equal(s.totalsMatch,true);
});
test('same round already-won accounts never generate a repeated hu notice',()=>{
 const v=snapshot();
 const old=structuredClone(v);old.win_ledger.wins.splice(1);
 assert.deepEqual(recentWins(old,v),[v.win_ledger.wins[1]]);
 assert.deepEqual(recentWins(v,v),[]);
 assert.deepEqual(recentWins(null,v,true),[]);
 assert.equal(summarizeSettlement({...v,phase:'await_discard'}),null);
});
test('public voice action normalization does not expose private hands or wall',()=>{
 const frames=[{events:[
  {type:'draw',seat:2,tile:'m4',privateHand:['m1'],wall:['s1']},
  {type:'discard',seat:2,tile:'p7',privateHand:['m1']},
  {type:'peng',seat:3,tile:'p7'},
  {type:'multi_ron',source:2,seats:[0,1],tile:'p7'},
 ]}];
 const actions=publicActions(frames);
 assert.deepEqual(actions.map(x=>x.type),['discard','peng','multi_ron']);
 assert.equal(actions[0].publicTile,'p7');
 assert.equal(actions[1].publicTile,null);
 assert.deepEqual(actions[2].winSeats,[0,1]);
 assert.ok(!JSON.stringify(actions).includes('privateHand'));
 assert.ok(!JSON.stringify(actions).includes('"wall"'));
 assert.equal(signed(-100),'-100');assert.equal(signed(200),'+200');
});


test('genuine Sichuan rule codes are displayed in readable Chinese, never re-scored',()=>{
 const patterns={
  pinghu:'平胡',seven_pairs:'七对',pure_seven_pairs:'清七对',
  dragon_seven_pairs:'龙七对',pure_dragon_seven_pairs:'清龙七对',
  golden_hook:'金钩钓',pure_suit:'清一色',
  all_pungs:'对对胡',pure_all_pungs:'清对对胡',
  heaven_win:'天胡',earth_win:'地胡',tian_ting:'天听',
  roots:'根',kong_bloom:'杠上花',kong_discard_ron:'杠上炮',
  rob_added_kong:'抢杠胡',sea_bottom_draw:'海底捞月',
  river_bottom_ron:'海底炮'
 };
 for(const [raw,expected] of Object.entries(patterns))
  assert.equal(patternLabel(raw),expected,raw);
 const v=snapshot();v.win_ledger.wins[0].main_pattern='seven_pairs';
 v.win_ledger.wins[0].effective_fan=2;
 assert.match(winTitle(v.win_ledger.wins[0]),/七对.*2番/);
 assert.doesNotMatch(winTitle(v.win_ledger.wins[0]),/seven_pairs/);
 assert.equal(v.win_ledger.wins[0].main_pattern,'seven_pairs',
   'the original Python ledger code must stay unchanged');
});
