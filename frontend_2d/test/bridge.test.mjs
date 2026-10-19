import test from 'node:test';
import assert from 'node:assert/strict';
import {convertView,closedHandModel,choiceAction,SESSION_KEY,
  meldToken,tile} from '../src/bridge.mjs';

const original={
 seat:0,phase:'await_discard',turn:0,dealer:2,wall_count:44,
 hand:['m1','m1','m2','m3','m4','p1','p2','p3','s1','s2','s3','s4','s8','s8'],
 drawn_tile:'s8',hand_counts:[14,13,9,13],
 missing_suits:['p','m','s','p'],
 own_melds:[],melds:[[],[{type:'an_gang',tile:null}],
   [{type:'peng',tile:'p5'}],[{type:'ming_gang',tile:'s3'}]],
 discards:[{seat:0,tile:'m2'}, {seat:2,tile:'s6',claimed_by:3},
   {seat:1,tile:'p5'}, {seat:3,tile:'m4'}],
 kong_options:[],can_self_draw_win:false
};
const clone=()=>structuredClone(original);
test('package has a compatible same-tab session contract',()=>{
 assert.equal(SESSION_KEY,'mahtrain.match.session.v1');
 assert.deepEqual(tile('s9'),'s9');
 assert.throws(()=>tile('z1'),/invalid/);
});
test('Majiang Shoupai model retains duplicate physical copies and drawn separation',()=>{
 const v=convertView(clone());
 assert.equal(v.hands[0]._bingpai.m[1],2);
 assert.equal(v.hands[0]._zimo,'s8');
 assert.equal(v.indexed.length,14);
 assert.equal(v.indexed.at(-1).index,13);
 assert.equal(v.indexed.at(-1).fromDraw,true);
 assert.equal(v.hands[0]._bingpai._,0);
 assert.equal(v.hands[1]._bingpai._,13);
 assert.equal(v.hands[2]._bingpai._,9);
 assert.equal(v.hands[3]._bingpai._,13);
 assert.equal(v.hands[1]._bingpai.m[1],0,'do not leak opponents concealed faces');
 assert.equal(v.hands[2]._bingpai.s[8],0);
});
test('Majiang He retains claimed discards in their original physical positions',()=>{
 const v=convertView(clone());
 assert.deepEqual(v.rivers[2]._pai,['s6']);
 assert.deepEqual(v.rivers[2].claimed,[true]);
 assert.deepEqual(v.rivers[0].claimed,[false]);
 assert.equal(v.rivers[3]._pai[0],'m4');
});
test('public meld token conversion uses native Majiang miyazi notation',()=>{
 const v=convertView(clone());
 assert.equal(v.hands[2]._fulou[0],'p555=');
 assert.equal(v.hands[3]._fulou[0],'s3333-');
 assert.equal(v.hands[1]._fulou[0],'m1111');
 assert.equal(v.redactions[1][0].hidden,true);
 assert.equal(meldToken({type:'an_gang',tile:'m4'},0).code,'m4444');
 assert.equal(meldToken({type:'bu_gang',tile:'s5'},2).code,'s555=5');
 assert.throws(()=>meldToken({type:'chi',tile:'s4'},1),/unsupported/);
});
test('real drawn copy vs hand copy produce different discard commands',()=>{
 const v=clone();
 assert.deepEqual(choiceAction(v,'discard',{index:13}),
   {action:'match_discard',tile:'s8',from_draw:true});
 assert.deepEqual(choiceAction(v,'discard',{index:12}),
   {action:'match_discard',tile:'s8',from_draw:false});
 assert.equal(choiceAction(v,'discard',{index:100}),null);
 v.phase='exchange_select';
 assert.equal(choiceAction(v,'discard',{index:0}),null);
});
test('claim only available when server explicitly authorizes unsent choice',()=>{
 const v=clone();v.phase='claim_window';v.pending_discard={seat:3,tile:'m1'};
 v.claim_options=['hu','peng','pass'];
 assert.deepEqual(choiceAction(v,'claim',{option:'hu'}),
   {action:'match_claim',choice:'hu'});
 assert.equal(choiceAction(v,'claim',{option:'ming_gang'}),null);
 v.claim_submitted=[0];
 assert.equal(choiceAction(v,'claim',{option:'hu'}),null);
});
test('self-draw and kang must be server-authorized',()=>{
 const v=clone();
 assert.equal(choiceAction(v,'win'),null);
 v.can_self_draw_win=true;
 assert.deepEqual(choiceAction(v,'win'),{action:'match_win'});
 v.kong_options=[{type:'an_gang',tile:'m1'}];
 assert.deepEqual(choiceAction(v,'kong',{kind:'an_gang',tile:'m1'}),
  {action:'match_kong',kind:'an_gang',tile:'m1'});
 assert.equal(choiceAction(v,'kong',{kind:'bu_gang',tile:'m1'}),null);
});
test('no mutation of the Python source snapshot',()=>{
 const v=clone(),before=structuredClone(v);convertView(v);
 assert.deepEqual(v,before);
 assert.throws(()=>convertView({seat:1,hand:[],hand_counts:[1,2,3,4]}));
});

test("56 original discard positions per seat preserve each claimed gap and original ordering",()=>{
 const v=clone();
 const holes=[5,13,24,41];
 v.discards=[];
 for(let n=0;n<56;n++)for(let seat=0;seat<4;seat++){
  const entry={seat,tile:"mps"[(n+seat)%3]+String(1+(n+seat)%9)};
  if(n===holes[seat])entry.claimed_by=(seat+1)%4;
  v.discards.push(entry);
 }
 const original=structuredClone(v.discards);
 const converted=convertView(v);
 for(let seat=0;seat<4;seat++){
  assert.equal(converted.rivers[seat]._pai.length,56);
  assert.equal(converted.rivers[seat].claimed.length,56);
  assert.deepEqual(converted.rivers[seat].claimed.flatMap(
    (flag,index)=>flag?[index]:[]),[holes[seat]]);
  assert.equal(converted.rivers[seat]._pai[55],
   "mps"[(55+seat)%3]+String(1+(55+seat)%9));
 }
 assert.deepEqual(v.discards,original,
  "rendering must not edit public Python discard history");
});
