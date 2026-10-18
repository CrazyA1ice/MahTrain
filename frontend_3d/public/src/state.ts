// ============================================================
// state.mjs — 客户端共享状态 (P2-2 完成版)
// ============================================================
// 此文件已重构完成: 实际状态分散到 5 个域对象中 (public/src/state/*.mjs).
// 各模块直接 import 域对象, 不再使用聚合 state.
//
// 此文件仅作为:
//   1. 域对象的统一导出入口 (方便个别模块一次性 import 多个域)
//   2. myTotalTiles 工具函数的归属 (因为它跨 handState 与 gameState 两个域)
import { MY_SEAT } from './constants.ts';
import { sceneRefs } from './state/scene-refs.ts';
import { handState } from './state/hand-state.ts';
import { gameState } from './state/game-state.ts';
import { interactionState } from './state/interaction-state.ts';
import { networkRefs } from './state/network-refs.ts';

// 工具: 计算自己手牌总数 (含副露)
// 跨 handState (myHand, meldGroups) 与 gameState (MY_SEAT) 两个域, 因此保留在 state.mjs
function myTotalTiles(): number {
  return handState.myHand.length + handState.meldGroups[MY_SEAT].length * 3;
}

export { myTotalTiles, sceneRefs, handState, gameState, interactionState, networkRefs };
