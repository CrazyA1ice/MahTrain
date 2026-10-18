import test from 'node:test';
import assert from 'node:assert/strict';
import {
  clientSeat,tileTo3d,from3dTile,meldTo3d,
  toQuejuSnapshot,decode3dAction,
} from '../public/src/mahtrain-protocol.mjs';

const privateView={
  seat:0,phase:'await_discard',turn:0,dealer:2,wall_count:54,
  hand:['m1','m2','m3','m4','s1','s2','s3','p1','p2','p3','p4','p5','m8','m8'],
  drawn_tile:'m8',hand_counts:[14,13,10,13],
  missing_suits:['p','m','s','p'],own_melds:[],
  melds:[[],[{type:'an_gang',tile:null}],
    [{type:'peng',tile:'p5'}],[{type:'ming_gang',tile:'s3'}]],
  discards:[{seat:0,tile:'m2'},{seat:2,tile:'s6',claimed_by:3},
    {seat:1,tile:'p5'},{seat:3,tile:'m4'}],
  can_self_draw_win:false,kong_options:[],claim_options:[],rob_options:[],
};
const view=()=>structuredClone(privateView);
test('valid tile and strict seat mapping',()=>{
  assert.deepEqual([0,1,2,3].map(clientSeat),[0,3,2,1]);
  assert.deepEqual(tileTo3d('s7'),{type:'tiao',value:7});
  assert.equal(from3dTile({type:'tong',value:9}),'p9');
  assert.throws(()=>tileTo3d('z1'),/invalid/);
  assert.throws(()=>clientSeat(4),/invalid/);
});
test('private opponent tiles and concealed kong NEVER enter 3D public UI',()=>{
  const m=toQuejuSnapshot(view());
  assert.equal(m.yourHand.length,14);
  assert.equal(m.handCounts[0],14);
  assert.equal(m.handCounts[3],13);
  assert.equal(m.handCounts[1],13);
  assert.equal(m.handCounts[2],10);
  assert.equal(m.melds[3][0].hidden,true);
  assert.deepEqual(m.melds[3][0].tiles.map(t=>t.type),Array(4).fill('wan'));
  assert.ok(!JSON.stringify(m).includes('pending_wall'));
  assert.equal(m.discards[2][0],null);
  assert.equal(m.discards[0][0].value,2);
  assert.equal(m.discards[3][0].value,5);
  assert.equal(m.discards[1][0].value,4);
  assert.equal(m.wallTotal,112);
  assert.equal(m.wallCursor,58);
});
test('owned closed kong may expose its known tile; opponent kong stays redacted',()=>{
  assert.deepEqual(meldTo3d({type:'an_gang',tile:'m3'},true).tiles
    .map(t=>t.value),[3,3,3,3]);
  assert.ok(meldTo3d({type:'an_gang',tile:'m3'},false).hidden);
});
test('same-valued draw cuts the correct physical copy',()=>{
  const m=view();
  assert.deepEqual(decode3dAction({type:'discard',tileId:14},m),{
    action:'match_discard',tile:'m8',from_draw:true,
  });
  assert.deepEqual(decode3dAction({type:'discard',tileId:13},m),{
    action:'match_discard',tile:'m8',from_draw:false,
  });
  assert.equal(decode3dAction({type:'discard',tileId:50},m),null);
});
test('exchange/missing phases reject 3D discard before MahTrain allows it',()=>{
  const m=view();m.phase='exchange_select';
  assert.equal(decode3dAction({type:'discard',tileId:1},m),null);
  m.phase='missing_select';
  assert.equal(decode3dAction({type:'discard',tileId:1},m),null);
});
test('legal reactions and claim priority remain server-authoritative',()=>{
  const m=view();m.phase='claim_window';
  m.pending_discard={seat:3,tile:'s1'};
  m.claim_options=['hu','peng','pass'];
  const snap=toQuejuSnapshot(m);
  assert.deepEqual(snap.claimOffer.options,['win','pong']);
  assert.deepEqual(decode3dAction({type:'claim',action:'win'},m),
    {action:'match_claim',choice:'hu'});
  assert.equal(decode3dAction({type:'claim',action:'kong'},m),null);
  m.claim_submitted=[0];
  assert.equal(toQuejuSnapshot(m).claimOffer,null);
});
test('real kong and win decoded only when exposed by Python authority',()=>{
  const m=view();m.can_self_draw_win=true;
  assert.deepEqual(decode3dAction({type:'claim',action:'win'},m),
    {action:'match_win'});
  m.kong_options=[{type:'bu_gang',tile:'s3'}];
  assert.deepEqual(decode3dAction({
    type:'claim',action:'addKong',value:{type:'tiao',value:3},
  },m),{action:'match_kong',kind:'bu_gang',tile:'s3'});
  assert.equal(decode3dAction({
    type:'claim',action:'ckong',value:{type:'tiao',value:3},
  },m),null);
});
test('no mutation from caller changes authoritative snapshot',()=>{
  const src=view();
  const before=structuredClone(src);
  toQuejuSnapshot(src);
  assert.deepEqual(src,before);
});
