// ============================================================
// handlers/reconnect.mjs — 重连状态恢复
// ============================================================
// 由 handlers.mjs 拆分而来 (P2-1). 处理 RECONNECT_STATE 消息:
//   applyReconnectState (主) + 8 个 restore* 子函数
import * as THREE from 'three';
import * as CANNON from '../physics.ts';
import { gameState } from '../state/game-state.ts';
import type { ServerMsg } from './index.ts';
import { handState } from '../state/hand-state.ts';
import { sceneRefs } from '../state/scene-refs.ts';
import { interactionState } from '../state/interaction-state.ts';
import { networkRefs } from '../state/network-refs.ts';
import {
  DIR_NAME,
  MY_SEAT,
  MSG,
  STAND_TILE_Y,
  GROUND_Y,
  HALF_D,
  EMISSIVE,
  handTrack,
  slotAlong,
  alongToWorld,
  discardCell,
  tileLabel,
} from '../constants.ts';
import { resetBoard, createStandTile, createStandTileBack, obtainTileObj, setEmissive } from '../board.ts';
import { hideLoader, toast, renderPlayers, updateDiscardBtn, showClaimBar, hideClaimBar } from '../ui.ts';
import { layFlatTile, meldAlong } from '../animation.ts';
import { setWallStart } from '../scene.ts';
import * as interaction from '../interaction.ts';
import { yawQuat, restBody } from '../geo.ts';
import { send } from '../network.ts';

// ============ E1 完整版: 重连状态恢复 ============
// applyReconnectState 拆为 8 个子函数, 主函数仅 10 行调用序列
// .4: 新增 restoreLastDiscard + restoreClaimAndSelfOptions
function applyReconnectState(m: ServerMsg) {
  resetBoard();
  restorePhase(m);
  restoreDice(m);
  restoreMyHand(m);
  restoreOppHands(m);
  restoreMelds(m);
  restoreDiscards(m);
  restoreWallConsumption(m); // 根据已发手牌消耗牌墙
  restoreLastDiscard(m); // .4: 恢复最后弃牌高亮
  restoreUI(m);
  restoreClaimAndSelfOptions(m); // .4: 恢复认领窗口/自摸选项
  hideLoader();
  toast('重连成功, 状态已恢复', 2000);
}

// .4: 恢复最后弃牌的高亮 (箭头)
function restoreLastDiscard(m: any) {
  if (m.lastDiscardId != null) {
    gameState.lastDiscardId = m.lastDiscardId;
    gameState.lastDiscardBy = m.lastDiscardBy >= 0 ? m.lastDiscardBy : -1;
    // 调用 board.ts 的 highlightLastDiscard 高亮最后弃牌
    // 注意: highlightLastDiscard 已在 restoreDiscards 中被调用的 tossDiscard 隐式触发
    // 这里只需确保 gameState 字段正确, 高亮会在下一帧自动生效
  }
}

// .4: 恢复认领窗口 (CLAIM_OFFER) 和自摸选项 (SELF_OPTIONS)
function restoreClaimAndSelfOptions(m: any) {
  // 如果处于认领窗口, 重新显示碰/杠/胡按钮
  if (m.claimOffer) {
    const opts = m.claimOffer.options || [];
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
    showClaimBar(
      btns,
      DIR_NAME[m.claimOffer.fromSeat] + ' 打出 ' + tileLabel(m.claimOffer.tile),
      m.claimOffer.deadline
    );
  } else if (m.selfOptions) {
    // 如果轮到自己且不在认领窗口, 显示自摸/暗杠/续杠按钮
    const so = m.selfOptions;
    const btns: any[] = [];
    if (so.canWin)
      btns.push({
        label: '自摸胡',
        cls: 'win',
        onClick: () => send({ type: MSG.CLAIM, action: 'win' }),
      });
    for (const t of so.ckong || [])
      btns.push({
        label: '暗杠' + tileLabel(t),
        onClick: () => send({ type: MSG.CLAIM, action: 'ckong', value: { type: t.type, value: t.value } }),
      });
    for (const t of so.addKong || [])
      btns.push({
        label: '续杠' + tileLabel(t),
        onClick: () => send({ type: MSG.CLAIM, action: 'addKong', value: { type: t.type, value: t.value } }),
      });
    if (btns.length) {
      btns.push({ label: '过', cls: 'pass', onClick: () => hideClaimBar() });
      showClaimBar(btns, '可操作');
    }
  }
}

// 重连后根据服务端 wallCursor/wallBackCursor 标记牌墙消耗
// 服务端 buildReconnectState 返回 wallCursor=dealCursor / wallBackCursor=backCursor,
// 客户端直接用这两个权威值, 不再自己推算
// 注: 重连时必须先调用 setWallStart 重排 wallTiles,
//   否则 wallTiles 是 buildWalls 原始顺序, dealCursor 是重排后的顺序, 不匹配 → 缺牌
function restoreWallConsumption(m: any) {
  // 先用骰子信息重排 wallTiles(与服务端对齐)
  if (m.dealer != null && m.dealerDiceSum != null && m.dealerDiceMin != null && m.dealerDiceSum > 0) {
    setWallStart(m.dealer, m.dealerDiceSum, m.dealerDiceMin);
  }

  // 牌墙头消耗(发牌 + 正常摸牌) — 服务端 dealCursor 是重排后的累计取牌数
  // 注意: 服务端 deck 是线性洗牌数组, dealCursor 从 0++ 不含任何 skipTiles
  //       客户端的 skipTiles (diceMin*2) 纯粹是视觉表现, 不在服务端 dealCursor 中
  const frontConsumed = m.wallCursor != null ? m.wallCursor : 0;
  // 牌墙尾消耗(杠后摸牌) — 服务端 backCursor 是从 deck.length-1 递减的索引, 转成消耗数
  const backConsumed = m.wallBackCursor != null ? (m.wallTotal != null ? m.wallTotal - 1 - m.wallBackCursor : 0) : 0;

  // 标记前 frontConsumed 张 wallTiles 为 _taken 并从场景移除
  // setWallStart 已重排 wallTiles 并跳过了 diceMin*2 张(标记为 _taken, wallCursor = diceMin*2)
  // 服务端 dealCursor 是从 0 开始的累计摸牌数, 额外标记 frontConsumed 张(不减去 alreadySkipped)
  const alreadySkipped = sceneRefs.wallCursor; // setWallStart 设置的 skipTiles = diceMin*2
  const extraFront = frontConsumed; // 服务端 dealCursor 不含 skipTiles, 直接累加
  const skipCount = Math.min(alreadySkipped + extraFront, sceneRefs.wallTiles.length);
  for (let i = alreadySkipped; i < skipCount; i++) {
    if (sceneRefs.wallTiles[i] && !(sceneRefs.wallTiles[i] as any).userData._taken) {
      (sceneRefs.wallTiles[i] as any).userData._taken = true;
      if ((sceneRefs.wallTiles[i] as any).parent) (sceneRefs.wallTiles[i] as any).parent.remove(sceneRefs.wallTiles[i]);
    }
  }
  sceneRefs.wallCursor = skipCount; // = skipTiles + dealCursor (正确)

  // 标记前 backConsumed 张 wallBack 为 _taken 并从场景移除
  const backSkip = Math.min(backConsumed, sceneRefs.wallBack.length);
  for (let i = 0; i < backSkip; i++) {
    if (sceneRefs.wallBack[i] && !(sceneRefs.wallBack[i] as any).userData._taken) {
      (sceneRefs.wallBack[i] as any).userData._taken = true;
      if ((sceneRefs.wallBack[i] as any).parent) (sceneRefs.wallBack[i] as any).parent.remove(sceneRefs.wallBack[i]);
    }
  }
  sceneRefs.wallBackCursor = backSkip;
}

// 子函数 1: 恢复 phase / dealer / currentTurn / gameEnded
function restorePhase(m: any) {
  gameState.phase = m.phase;
  gameState.dealerSeat = m.dealer;
  gameState.currentTurn = m.currentTurn;
  gameState.gameEnded = !!m.gameOver;
  gameState.myDealer = m.dealer === MY_SEAT;
  // 注意: 不调 setPhaseUI, 它会关掉所有 UI, 我们手动恢复
  if (networkRefs.ui.statusText) {
    networkRefs.ui.statusText.textContent =
      ({ waiting: '等待', dice: '骰子', deal: '发牌', play: '出牌' } as Record<string, string>)[m.phase] || m.phase;
  }
}

// 子函数 2: 恢复骰子结果
function restoreDice(m: any) {
  if (!m.diceResults) return;
  for (const seatStr of Object.keys(m.diceResults)) {
    const seat = +seatStr;
    gameState.playerInfo[seat].dice = m.diceResults[seat];
  }
  renderPlayers();
}

// 子函数 3: 恢复自己手牌 (正面朝上)
function restoreMyHand(m: any) {
  if (!m.yourHand || !m.yourHand.length) return;
  const tr = handTrack(MY_SEAT);
  const total = m.yourHand.length;
  m.yourHand.forEach((tile: any, idx: any) => {
    const obj = createStandTile(tile.type, tile.value, tile.id);
    sceneRefs.seatPivot!.add(obj.mesh);
    const along = slotAlong(idx, total);
    const pos = alongToWorld(MY_SEAT as number, along as number);
    obj.body.position.set(pos.x, STAND_TILE_Y, pos.z);
    const q = yawQuat(tr.rotY);
    obj.body.quaternion.set(q.x, q.y, q.z, q.w);
    obj.body.type = CANNON.Body.KINEMATIC;
    restBody(obj.body);
    interactionState.dirtyBodies.set(obj.body, obj.mesh);
    handState.myHand.push(obj);
  });
  interaction.recomputeSlots();
}

// 子函数 4: 恢复别人手牌 (牌背)
function restoreOppHands(m: any) {
  for (let s = 0; s < 4; s++) {
    if (s === MY_SEAT) continue;
    const cnt = m.handCounts[s] || 0;
    const tr = handTrack(s);
    const q = yawQuat(tr.rotY);
    for (let i = 0; i < cnt; i++) {
      const obj = createStandTileBack(++handState.myIdCounter);
      sceneRefs.seatPivot!.add(obj.mesh);
      const along = slotAlong(i, cnt);
      const pos = alongToWorld(s as number, along as number);
      obj.body.position.set(pos.x, STAND_TILE_Y, pos.z);
      obj.body.quaternion.set(q.x, q.y, q.z, q.w);
      obj.body.type = CANNON.Body.KINEMATIC;
      restBody(obj.body);
      interactionState.dirtyBodies.set(obj.body, obj.mesh);
      handState.oppHands[s].push(obj);
    }
  }
}

// 子函数 5: 恢复副露
function restoreMelds(m: any) {
  if (!m.melds) return;
  for (let s = 0; s < 4; s++) {
    const seatMelds = m.melds[s] || [];
    seatMelds.forEach((md: any, slot: any) => {
      const objs: any[] = [];
      const prevKinds = handState.meldGroups[s].map((g: any) => g.kind);
      md.tiles.forEach((tv: any, col: any) => {
        const isBack = md.kind === 'ckong' && (col === 0 || col === 3);
        const obj = obtainTileObj(s, tv, isBack);
        setEmissive(obj.mesh, EMISSIVE.OFF);
        layFlatTile(obj, s, meldAlong(s, slot, col, prevKinds));
        objs.push(obj);
      });
      handState.meldGroups[s].push({ meldIdx: slot, slot, objs, kind: md.kind });
    });
  }
}

// 子函数 6: 恢复弃牌堆
function restoreDiscards(m: any) {
  if (!m.discards) return;
  for (let s = 0; s < 4; s++) {
    const arr = m.discards[s] || [];
    arr.forEach((tile: any, idx: any) => {
      const id = tile.id ?? ++handState.myIdCounter;
      const obj = createStandTile(tile.type, tile.value, id);
      sceneRefs.seatPivot!.add(obj.mesh);
      const cell = discardCell(s, idx);
      const tr = handTrack(s);
      const yaw = yawQuat(tr.rotY);
      const flat = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -Math.PI / 2);
      const q = yaw.multiply(flat);
      obj.body.position.set(cell.x, GROUND_Y + HALF_D, cell.z);
      obj.body.quaternion.set(q.x, q.y, q.z, q.w);
      obj.body.type = CANNON.Body.KINEMATIC;
      restBody(obj.body);
      interactionState.dirtyBodies.set(obj.body, obj.mesh);
      handState.discardTiles.push({ id: tile.id, obj, bySeat: s });
    });
  }
}

// 子函数 7: 按阶段恢复 UI
function restoreUI(m: any) {
  if (m.phase === 'dice') {
    if (m.diceCursor !== undefined && m.diceOrder) {
      const curSeat = m.diceOrder[m.diceCursor];
      if (curSeat === MY_SEAT) {
        if (networkRefs.ui.diceCenter) networkRefs.ui.diceCenter.classList.add('show');
        if (networkRefs.ui.diceSub) networkRefs.ui.diceSub!.textContent = '轮到你投骰子';
        if (networkRefs.ui.rollBtn) networkRefs.ui.rollBtn.disabled = false;
      } else {
        if (networkRefs.ui.diceCenter) networkRefs.ui.diceCenter.classList.remove('show');
        if (networkRefs.ui.diceSub) networkRefs.ui.diceSub!.textContent = `等待 ${DIR_NAME[curSeat]} 投骰子`;
      }
    }
  } else if (m.phase === 'deal') {
    if (gameState.myDealer) {
      if (networkRefs.ui.dealBtn) (networkRefs.ui.dealBtn as any).disabled = false;
      if (networkRefs.ui.dealCenter) networkRefs.ui.dealCenter.classList.add('show');
    } else {
      if (networkRefs.ui.dealCenter) networkRefs.ui.dealCenter.classList.remove('show');
    }
  } else if (m.phase === 'play') {
    if (networkRefs.ui.turnText) {
      networkRefs.ui.turnText.textContent = DIR_NAME[m.currentTurn] + (m.currentTurn === MY_SEAT ? '(你)' : '');
    }
    updateDiscardBtn();
    if (m.isMyTurn) {
      toast(m.mustDiscardOnly ? '你已碰, 请出牌' : '轮到你出牌', 2000);
    }
  }
  if (m.gameOver) {
    if (networkRefs.ui.winTitle) networkRefs.ui.winTitle.textContent = '本局已结束';
    if (networkRefs.ui.winInfo) networkRefs.ui.winInfo.textContent = '等待再来一局';
    if (networkRefs.ui.winOverlay) networkRefs.ui.winOverlay.classList.add('show');
  }
}

export { applyReconnectState };
