// ============================================================
// handlers/play.mjs — 出牌/认领/副露消息处理
// ============================================================
// 由 handlers.mjs 拆分而来 (P2-1). 处理出牌阶段消息:
//   DISCARD_BC, DRAW_BC, CLAIM_OFFER, SELF_OPTIONS, MELD_BC
// WIN_BC 与 RESTART_PROGRESS 见 handlers/win.mjs
import { gameState } from '../state/game-state.ts';
import { handState } from '../state/hand-state.ts';
import type { ServerMsg } from './index.ts';
import { sceneRefs } from '../state/scene-refs.ts';
import { interactionState } from '../state/interaction-state.ts';
import { DIR_NAME, MSG, MY_SEAT, STAND_TILE_Y, CFG, EMISSIVE, handTrack, tileLabel } from '../constants.ts';
import {
  createStandTile,
  createStandTileBack,
  relayoutOpp,
  setEmissive,
  highlightLastDiscard,
  obtainTileObj,
} from '../board.ts';
import { toast, updateDiscardBtn, hideClaimBar, showClaimBar, CLAIM_LABEL } from '../ui.ts';
import { flyTileTo, flyToFlat, layFlatTile, meldAlong, tossDiscard } from '../animation.ts';
import { popWallTile, popWallTileBack } from '../scene.ts';
import { world } from '../physics.ts';
import * as interaction from '../interaction.ts';
import { send } from '../network.ts';

function onDiscardBc(m: ServerMsg) {
  if (m.bySeat === MY_SEAT && handState.discardTiles.some((d: any) => d.id === m.tileId)) return;
  if (handState.oppHands[m.bySeat] && handState.oppHands[m.bySeat].length) {
    const back = handState.oppHands[m.bySeat].pop();
    sceneRefs.seatPivot!.remove(back!.mesh);
    if (back!.body) world.removeBody(back!.body);
    relayoutOpp(m.bySeat);
  }
  const tv = m.tile || { type: 'feng', value: '白' };
  const id = m.tileId ?? ++handState.myIdCounter;
  const obj = createStandTile(tv.type, tv.value, id);
  sceneRefs.seatPivot!.add(obj.mesh);
  const tr = handTrack(m.bySeat);
  let sx, sz;
  if (tr.axis === 'z') {
    sx = 0;
    sz = tr.constZ! * 0.8;
  } else {
    sz = 0;
    sx = tr.constX! * 0.8;
  }
  obj.body.position.set(sx, STAND_TILE_Y, sz);
  obj.body.quaternion.set(0, 0, 0, 1);
  handState.discardTiles.push({ id: m.tileId, obj, bySeat: m.bySeat });
  gameState.lastDiscardId = m.tileId;
  gameState.lastDiscardBy = m.bySeat;
  tossDiscard(obj, m.x, m.z, m.rotY || 0);
  highlightLastDiscard();
}

function onDrawBc(m: ServerMsg) {
  const startPos = m.fromBack ? popWallTileBack() : popWallTile();
  const sp = CFG.tile.w + CFG.spacing.handGap;
  if (m.bySeat === MY_SEAT && m.tile) {
    const id = m.tile.id ?? ++handState.myIdCounter;
    const obj = createStandTile(m.tile.type, m.tile.value, id);
    sceneRefs.seatPivot!.add(obj.mesh);
    obj.body.position.set(startPos.x, startPos.y, startPos.z);
    const n0 = handState.myHand.length;
    const along = (n0 - (n0 - 1) / 2) * sp;
    handState.myHand.push(obj);
    const tr = handTrack(MY_SEAT);
    flyTileTo(obj, along, tr.rotY, () => {
      toast('摸到一张牌', 1000);
    });
    updateDiscardBtn();
  } else {
    const obj = createStandTileBack(++handState.myIdCounter);
    sceneRefs.seatPivot!.add(obj.mesh);
    obj.body.position.set(startPos.x, startPos.y, startPos.z);
    const n0 = handState.oppHands[m.bySeat].length;
    const along = (n0 - (n0 - 1) / 2) * sp;
    handState.oppHands[m.bySeat].push(obj);
    const tr = handTrack(m.bySeat);
    flyTileTo(obj as any, along as any, tr.rotY, null as any);
  }
}

function onClaimOffer(m: ServerMsg) {
  const opts = m.options || [];
  const btns: any[] = [];
  if (opts.includes('win'))
    btns.push({
      label: '胡',
      cls: 'win',
      onClick: () => send({ type: MSG.CLAIM, action: 'win' }),
    });
  if (opts.includes('kong')) btns.push({ label: '杠', onClick: () => send({ type: MSG.CLAIM, action: 'kong' }) });
  if (opts.includes('pong')) btns.push({ label: '碰', onClick: () => send({ type: MSG.CLAIM, action: 'pong' }) });
  btns.push({
    label: '过',
    cls: 'pass',
    onClick: () => send({ type: MSG.CLAIM, action: 'pass' }),
  });
  showClaimBar(btns, DIR_NAME[m.fromSeat] + ' 打出 ' + tileLabel(m.tile), m.deadline);
}

function onSelfOptions(m: ServerMsg) {
  const btns: any[] = [];
  if (m.canWin)
    btns.push({
      label: '自摸胡',
      cls: 'win',
      onClick: () => send({ type: MSG.CLAIM, action: 'win' }),
    });
  for (const t of m.ckong || [])
    btns.push({
      label: '暗杠' + tileLabel(t),
      onClick: () => send({ type: MSG.CLAIM, action: 'ckong', value: { type: t.type, value: t.value } }),
    });
  for (const t of m.addKong || [])
    btns.push({
      label: '续杠' + tileLabel(t),
      onClick: () => send({ type: MSG.CLAIM, action: 'addKong', value: { type: t.type, value: t.value } }),
    });
  if (!btns.length) return;
  btns.push({ label: '过', cls: 'pass', onClick: () => hideClaimBar() });
  showClaimBar(btns, '可操作');
}

function onMeldBc(m: ServerMsg) {
  const seat = m.seat,
    kind = m.kind,
    tiles = m.tiles || [];
  // 构造 prevKinds: 前面所有组的 kind 数组, 用于 meldAlong 累加偏移
  const prevKinds = handState.meldGroups[seat].map((g: any) => g.kind);

  if (m.upgrade) {
    const g =
      handState.meldGroups[seat].find((x: any) => x.meldIdx === m.meldIdx) ||
      handState.meldGroups[seat][handState.meldGroups[seat].length - 1];
    const tv = tiles[tiles.length - 1];
    const obj = obtainTileObj(seat, tv, false);
    if (seat === MY_SEAT) {
      interaction.recomputeSlots();
      interaction.relayoutHand(true);
    }
    const prevKindsForUpgrade = handState.meldGroups[seat].filter((x: any) => x !== g).map((x: any) => x.kind);
    const targetAlong = meldAlong(seat, g ? g.slot : 0, 3, prevKindsForUpgrade);
    // 用 onDone 回调替代固定 50ms 余量的 setTimeout, 帧率波动时也能精确吸附
    flyToFlat(obj as any, seat, targetAlong, () => {
      try {
        layFlatTile(obj, seat, targetAlong);
      } catch {
        /* 牌已被清理 */
      }
    });
    if (g) g.objs.push(obj);
    toast(`${DIR_NAME[seat]} 续杠`, 1400);
    return;
  }
  let claimedObj = null;
  if (m.fromSeat >= 0 && m.fromSeat !== seat) {
    const claimedId = tiles[tiles.length - 1].id;
    const di = handState.discardTiles.findIndex((d: any) => d.id === claimedId);
    if (di >= 0) {
      claimedObj = handState.discardTiles[di].obj;
      handState.discardTiles.splice(di, 1);
    }
  }
  if (claimedObj) setEmissive(claimedObj.mesh, EMISSIVE.OFF);
  if (interactionState.discardArrow) interactionState.discardArrow.visible = false;
  gameState.lastDiscardId = null;
  gameState.lastDiscardObj = null;
  interactionState.arrowToken++;

  const slot = handState.meldGroups[seat].length;
  const objs: any[] = [];
  // 碰: 3 张 (2 手牌 + 1 弃牌); 明杠: 4 张 (3 手牌 + 1 弃牌); 暗杠: 4 张全手牌
  const handTiles = kind === 'ckong' ? tiles.slice() : tiles.slice(0, tiles.length - 1);
  // 收集每张牌的目标 along, 动画完成后强制吸附
  const targets: any[] = [];
  let col = 0;
  handTiles.forEach((tv: any) => {
    const isBack = kind === 'ckong' && (col === 0 || col === 3);
    const obj = obtainTileObj(seat, tv, isBack);
    setEmissive(obj.mesh, EMISSIVE.OFF);
    const targetAlong = meldAlong(seat, slot, col, prevKinds);
    targets.push({ obj, targetAlong });
    flyToFlat(obj as any as any, seat as any, targetAlong as any);
    objs.push(obj);
    col++;
  });
  if (seat === MY_SEAT) {
    interaction.recomputeSlots();
    interaction.relayoutHand(true);
  } else relayoutOpp(seat);
  if (claimedObj) {
    const targetAlong = meldAlong(seat, slot, col, prevKinds);
    targets.push({ obj: claimedObj, targetAlong });
    flyToFlat(claimedObj as any as any as any, seat as any, targetAlong as any);
    objs.push(claimedObj as any);
  }
  // 用每张牌动画的 onDone 回调替代统一的 setTimeout
  // 每张牌动画完成时各自吸附到精确位置, 帧率波动也不影响
  // 同时保留一个兜底 setTimeout (CFG.anim.meld * 2 + 100ms), 防止 onDone 因 dead=true 未触发
  const settleAll = () => {
    for (const t of targets) {
      try {
        layFlatTile(t.obj as any, seat, t.targetAlong);
      } catch {
        /* 牌已被清理 */
      }
    }
  };
  // 兜底: 动画理论时长的 2 倍 + 100ms, 确保 onDone 万一丢失也能吸附
  setTimeout(settleAll, CFG.anim.meld * 2 + 100);
  handState.meldGroups[seat].push({ meldIdx: m.meldIdx, slot, objs, kind });
  toast(`${DIR_NAME[seat]} ${(CLAIM_LABEL as any)[kind] || ''}`, 1400);
}

export { onDiscardBc, onDrawBc, onClaimOffer, onSelfOptions, onMeldBc };
