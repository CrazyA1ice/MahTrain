// ============================================================
// handlers/dice-deal.mjs — 骰子与发牌消息处理
// ============================================================
// 由 handlers.mjs 拆分而来 (P2-1). 处理骰子阶段、发牌阶段、回合切换:
//   PHASE, DICE_TURN, DICE_ROLL_START, DICE_RESULT,
//   DEAL, DEAL_END, TURN_CHANGE
import { gameState } from '../state/game-state.ts';
import { handState } from '../state/hand-state.ts';
import type { ServerMsg } from './index.ts';
import { sceneRefs } from '../state/scene-refs.ts';
import { networkRefs } from '../state/network-refs.ts';
import { DIR_NAME, PHASE, MY_SEAT, handTrack, seatTotal, slotAlong } from '../constants.ts';
import {
  createStandTile,
  createStandTileBack,
  relayoutOpp,
  resetBoard,
  forceCompleteResetAnim,
  highlightLastDiscard,
} from '../board.ts';
import { toast, setPhaseUI, updateDiscardBtn, hideClaimBar, renderPlayers } from '../ui.ts';
import { popWallTile, popWallTileJumpDeal, showDiceResult, startJumpDeal, setWallStart } from '../scene.ts';
import { flyTileTo } from '../animation.ts';
import { world } from '../physics.ts';
import * as interaction from '../interaction.ts';

function onPhase(m: ServerMsg) {
  setPhaseUI(m.phase);
  if (m.phase === PHASE.DICE) {
    const willAnimate = gameState.gameEnded;
    gameState.gameEnded = false;
    for (let s = 0; s < 4; s++) gameState.playerInfo[s].dice = null;
    renderPlayers();
    resetBoard(willAnimate, () => {
      // 动画结束后, 如果当前轮到本玩家投骰子, 补显示投骰子按钮
      // (服务器可能在动画期间已广播 DICE_TURN, onDiceTurn 因 boardAnimEndTime 延后了)
      if (gameState.pendingDiceTurnForMe) {
        gameState.pendingDiceTurnForMe = false;
        _showDiceTurnUIForMe();
      }
    });
    toast(willAnimate ? '重新整理牌墙...' : '骰子阶段开始');
  } else if (m.phase === PHASE.DEAL) {
    gameState.dealerSeat = m.dealer;
    gameState.myDealer = m.dealer === MY_SEAT;
    gameState.gameEnded = false;
    gameState._jumpDealStarted = false; // 重置跳牌阶段标记
    // (因为再来一局时 PHASE.DEAL 可能在重整牌墙动画期间到达, 此时牌墙还没重建好)
    gameState._pendingWallStart =
      m.diceSum && m.diceMin ? { dealer: m.dealer, diceSum: m.diceSum, diceMin: m.diceMin } : null;
    if (networkRefs.ui.winOverlay) networkRefs.ui.winOverlay.classList.remove('show');
    hideClaimBar();
    for (const s of [0, 1, 2, 3]) {
      for (const g of handState.meldGroups[s])
        for (const o of g.objs) {
          sceneRefs.seatPivot!.remove(o.mesh);
          if (o.body) world.removeBody(o.body);
        }
      handState.meldGroups[s] = [];
    }
    if (gameState.myDealer) {
      if (networkRefs.ui.dealBtn) (networkRefs.ui.dealBtn as any).disabled = false;
      if (networkRefs.ui.dealCenter) networkRefs.ui.dealCenter.classList.add('show');
      toast(`你是庄家(${DIR_NAME[m.dealer]}),请点击「发牌」`, 2500);
    } else {
      if (networkRefs.ui.dealCenter) networkRefs.ui.dealCenter.classList.remove('show');
      toast(`庄家:${DIR_NAME[m.dealer]},等待发牌`, 2000);
    }
  } else if (m.phase === PHASE.PLAY) {
    gameState.currentTurn = m.turn;
    if (networkRefs.ui.turnText) {
      networkRefs.ui.turnText.textContent = DIR_NAME[m.turn] + (m.turn === MY_SEAT ? '(你)' : '');
    }
    updateDiscardBtn();
    if (m.turn === MY_SEAT) toast('轮到你出牌', 1500);
    renderPlayers();
  }
}

function _showDiceTurnUIForMe() {
  if (!networkRefs.ui.diceCenter || !networkRefs.ui.diceSub || !networkRefs.ui.rollBtn) return;
  networkRefs.ui.diceSub!.textContent = '轮到你投骰子';
  networkRefs.ui.diceCenter.classList.add('show');
  networkRefs.ui.rollBtn.disabled = false;
}

function onDiceTurn(m: ServerMsg) {
  if (!networkRefs.ui.diceCenter || !networkRefs.ui.diceSub || !networkRefs.ui.rollBtn) return;
  if (m.seat === MY_SEAT) {
    if (gameState.boardAnimEndTime && Date.now() < gameState.boardAnimEndTime) {
      gameState.pendingDiceTurnForMe = true;
      // 仍然更新副文本, 让玩家知道轮到自己了
      networkRefs.ui.diceSub!.textContent = '轮到你投骰子 (等待整理完毕)';
      networkRefs.ui.diceCenter.classList.remove('show'); // 不显示按钮, 只显示文字
      return;
    }
    _showDiceTurnUIForMe();
  } else {
    networkRefs.ui.diceCenter.classList.remove('show');
    networkRefs.ui.diceSub!.textContent = `等待 ${DIR_NAME[m.seat]} 投骰子`;
  }
}

function onDiceRollStart(_m?: ServerMsg) {
  // 客户端这里只隐藏投骰子按钮, 动画由 DICE_RESULT 触发 (原版完整动画)
  if (networkRefs.ui.diceCenter) networkRefs.ui.diceCenter.classList.remove('show');
}

function onDiceResult(m: ServerMsg) {
  // 点数文本 (toast + 玩家列表) 由动画 onComplete 回调显示, 不立即显示
  showDiceResult(m.values, () => {
    showDiceResultText(m.values, m.seat, m.sum);
  });
}

function onDeal(m: ServerMsg) {
  const toSeat = m.toSeat;
  const isMine = toSeat === MY_SEAT;
  // BUGFIX (round6): 如果 resetBoard 飞牌动画还在进行, 立即同步完成
  // 否则 wallTiles 顺序错乱, 发牌会从错误位置飞出
  forceCompleteResetAnim();
  if (gameState._pendingWallStart) {
    setWallStart(
      gameState._pendingWallStart.dealer,
      gameState._pendingWallStart.diceSum,
      gameState._pendingWallStart.diceMin
    );
    gameState._pendingWallStart = null;
  }
  // 第一个 jump:true 时启动跳牌阶段 (初始化取牌 offset 队列)
  if (m.jump && !gameState._jumpDealStarted) {
    startJumpDeal();
    gameState._jumpDealStarted = true;
  }
  const startPos = m.jump ? popWallTileJumpDeal() : popWallTile();
  const tr = handTrack(toSeat);
  const total = seatTotal(toSeat, gameState.dealerSeat);
  const along = slotAlong(m.handIdx, total);
  if (isMine) {
    const id = m.tile.id ?? ++handState.myIdCounter;
    const obj = createStandTile(m.tile.type, m.tile.value, id);
    sceneRefs.seatPivot!.add(obj.mesh);
    obj.body.position.set(startPos.x, startPos.y, startPos.z);
    handState.myHand[m.handIdx] = obj;
    flyTileTo(obj as never, along as never, tr.rotY, undefined);
  } else {
    const obj = createStandTileBack(++handState.myIdCounter);
    sceneRefs.seatPivot!.add(obj.mesh);
    obj.body.position.set(startPos.x, startPos.y, startPos.z);
    handState.oppHands[toSeat][m.handIdx] = obj;
    flyTileTo(obj as never, along as never, tr.rotY, undefined);
  }
}

function onDealEnd(_m?: ServerMsg) {
  if (networkRefs.ui.statusText) networkRefs.ui.statusText.textContent = '发牌完毕';
  updateDiscardBtn();
  setTimeout(() => {
    interaction.recomputeSlots();
    interaction.relayoutHand(false);
    for (const seat of [0, 1, 2, 3]) relayoutOpp(seat);
  }, 600);
}

function onTurnChange(m: ServerMsg) {
  gameState.currentTurn = m.seat;
  gameState.lastDiscardBy = m.lastDiscardBy;
  if (networkRefs.ui.turnText) {
    networkRefs.ui.turnText.textContent = DIR_NAME[m.seat] + (m.seat === MY_SEAT ? '(你)' : '');
  }
  hideClaimBar();
  updateDiscardBtn();
  renderPlayers();
  highlightLastDiscard();
  if (m.seat === MY_SEAT) toast('轮到你出牌', 1200);
}

// 这样玩家看到完整的翻滚+落定动画后, 点数才出现 (toast + 玩家列表)
function showDiceResultText(values: any, seat: any, sum: any) {
  gameState.playerInfo[seat].dice = values;
  renderPlayers();
  if (seat === MY_SEAT) {
    toast(`你投了 ${sum} 点 (${values[0]}+${values[1]})`, 2200);
  }
}

export { onPhase, onDiceTurn, onDiceRollStart, onDiceResult, onDeal, onDealEnd, onTurnChange, showDiceResultText };
