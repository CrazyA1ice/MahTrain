// ============================================================
// handlers/win.mjs — 胡牌弹窗与重启进度
// ============================================================
// 由 handlers.mjs 拆分而来 (P2-1). 处理 WIN_BC 弹窗展示与 RESTART_PROGRESS:
//   - onWinBc: 展示所有人手牌正面、赢家高亮、弹窗与"再来一局"按钮
//   - showRestartFloat: 显示浮动"再来一局"按钮
//   - onRestartProgress: 更新准备进度
import * as CANNON from '../physics.ts';
import { gameState } from '../state/game-state.ts';
import { handState } from '../state/hand-state.ts';
import type { ServerMsg } from './index.ts';
import { sceneRefs } from '../state/scene-refs.ts';
import { interactionState } from '../state/interaction-state.ts';
import { networkRefs } from '../state/network-refs.ts';
import { DIR_NAME, MSG, MY_SEAT, STAND_TILE_Y, CFG, EMISSIVE, handTrack, alongToWorld } from '../constants.ts';
import { createStandTile, setEmissive } from '../board.ts';
import { hideClaimBar } from '../ui.ts';
import { tipOverTile } from '../animation.ts';
import { world } from '../physics.ts';
import { send } from '../network.ts';
import { yawQuat, restBody } from '../geo.ts';

interface ProtocolTile {
  type: string;
  value: number | string;
  id: number;
}
interface ScoreBreakdown {
  name: string;
  fan: number;
}
interface ScoreInfo {
  fan?: number;
  breakdown?: ScoreBreakdown[];
}
interface _WinBcMsg {
  seat: number;
  hands?: Record<number, ProtocolTile[]> | ProtocolTile[][];
  draw?: boolean;
  selfDraw?: boolean;
  fromSeat?: number;
  score?: ScoreInfo;
}
interface _RestartProgressMsg {
  ready: number[];
  total: number;
}

function onWinBc(m: ServerMsg): void {
  hideClaimBar();
  gameState.gameEnded = true;
  gameState.winnerSeat = m.seat;

  // 1. 展示所有人手牌正面朝上 (替换别人的牌背为真实牌面)
  if (m.hands) {
    for (let s = 0; s < 4; s++) {
      if (s === MY_SEAT) continue; // 自己的手牌已经是正面
      const realHand: ProtocolTile[] = (m.hands as unknown as Record<number, ProtocolTile[]>)[s] || [];
      // 移除旧的牌背占位
      for (const o of handState.oppHands[s]) {
        if (sceneRefs.seatPivot) sceneRefs.seatPivot.remove(o.mesh);
        if (o.body) world.removeBody(o.body);
      }
      handState.oppHands[s] = [];
      // 用真实牌面重建
      const tr = handTrack(s);
      const q = yawQuat(tr.rotY);
      realHand.forEach((tile: ProtocolTile, idx: number) => {
        const obj = createStandTile(tile.type, tile.value, tile.id);
        if (sceneRefs.seatPivot) sceneRefs.seatPivot.add(obj.mesh);
        const along = (idx - (realHand.length - 1) / 2) * (CFG.tile.w + CFG.spacing.handGap);
        const pos = alongToWorld(s, along);
        obj.body.position.set(pos.x, STAND_TILE_Y, pos.z);
        obj.body.quaternion.set(q.x, q.y, q.z, q.w);
        obj.body.type = CANNON.Body.KINEMATIC;
        restBody(obj.body);
        interactionState.dirtyBodies.set(obj.body, obj.mesh);
        handState.oppHands[s].push(obj);
      });
    }
  }

  // 自己的手牌
  for (const o of handState.myHand) tipOverTile(o, MY_SEAT);
  // 别人的手牌
  for (let s = 0; s < 4; s++) {
    if (s === MY_SEAT) continue;
    for (const o of handState.oppHands[s]) tipOverTile(o, s);
  }

  // 2. 赢家手牌高亮 (金色发光)
  // 流局 (m.seat === -1) 时跳过赢家高亮
  if (m.seat >= 0) {
    const winnerSeat = m.seat;
    const winnerTiles = winnerSeat === MY_SEAT ? handState.myHand : handState.oppHands[winnerSeat];
    for (const o of winnerTiles) {
      setEmissive(o.mesh, EMISSIVE.HIGHLIGHT);
    }
    // 赢家副露也高亮
    for (const g of handState.meldGroups[winnerSeat]) {
      for (const o of g.objs) setEmissive(o.mesh, EMISSIVE.HIGHLIGHT);
    }
  }

  // 3. 显示胡牌弹窗 (2 秒后自动关闭, 不挡视线)
  // 流局处理 (seat=-1 + draw=true) — 显示"流局"提示, 不高亮赢家
  // (BUG-05): 展示番数明细, 让 calcScore 不再形同虚设
  if (networkRefs.ui.winTitle) networkRefs.ui.winTitle.textContent = m.draw ? '流 局' : m.selfDraw ? '自 摸' : '胡 牌';
  if (networkRefs.ui.winInfo) {
    if (m.draw) {
      networkRefs.ui.winInfo.textContent = '牌墙已空, 无人胡牌';
    } else {
      const who = m.seat === MY_SEAT ? '你' : DIR_NAME[m.seat];
      let info =
        `${who} 胡牌` +
        (m.fromSeat !== undefined && m.fromSeat >= 0 && !m.selfDraw ? `（${DIR_NAME[m.fromSeat]} 点炮）` : '');
      // : 展示番数明细 (服务端 WIN_BC.score 已携带 {fan, breakdown})
      if (m.score && m.score.breakdown && m.score.breakdown.length > 0) {
        const fanText = `${m.score.fan ?? 0} 番: ${m.score.breakdown.map((b: ScoreBreakdown) => `${b.name}(${b.fan})`).join('、')}`;
        info += '\n' + fanText;
      }
      networkRefs.ui.winInfo.textContent = info;
    }
  }
  if (networkRefs.ui.winOverlay) networkRefs.ui.winOverlay.classList.add('show');

  // 4. 2 秒后关闭弹窗, 显示浮动"再来一局"按钮 (不挡视线)
  setTimeout(() => {
    if (networkRefs.ui.winOverlay) {
      networkRefs.ui.winOverlay.classList.remove('show');
    }
    showRestartFloat();
  }, 2000);
}

function showRestartFloat(): void {
  const restartFloat = document.getElementById('restartFloat');
  if (restartFloat) {
    restartFloat.classList.add('show');
    const btn = document.getElementById('restartFloatBtn') as HTMLButtonElement | null;
    const info = document.getElementById('restartFloatInfo');
    if (btn) {
      btn.disabled = false;
      btn.textContent = '再 来 一 局';
      btn.onclick = () => {
        send({ type: MSG.RESTART });
        btn.disabled = true;
        btn.textContent = '已 准 备';
      };
    }
    if (info) info.textContent = '已准备 0/4';
  }
}

function onRestartProgress(m: ServerMsg): void {
  const readyCount = m.ready.length;
  const total = m.total;
  const info = document.getElementById('restartFloatInfo');
  if (info) {
    info.textContent = `已准备 ${readyCount}/${total}`;
  }
  // 如果自己也准备了, 禁用按钮
  if (m.ready.includes(MY_SEAT)) {
    const btn = document.getElementById('restartFloatBtn') as HTMLButtonElement | null;
    if (btn) {
      btn.disabled = true;
      btn.textContent = '已 准 备';
    }
  }
  // 全员准备后隐藏浮动按钮
  if (readyCount >= total) {
    const restartFloat = document.getElementById('restartFloat');
    if (restartFloat) restartFloat.classList.remove('show');
  }
}

export { onWinBc, onRestartProgress };
