// ============================================================
// state/game-state.mjs — 游戏状态机
// ============================================================
// 由 state.mjs 拆分而来 (P2-2). 持有回合/庄家/胡牌等游戏状态字段.
// 在 handlers.mjs / board.mjs / ui.mjs 中读写.
// 注意: MY_SEAT 是从 constants.mjs 引入的常量, 这里仅作引用聚合.

import { PHASE, MY_SEAT } from '../constants.ts';
import type * as THREE from 'three';
import type { PlayerInfo, TileObject } from '../types';

interface PendingWallStart {
  dealer: number;
  diceSum: number;
  diceMin: number;
}

export interface GameState {
  phase: string;
  myDealer: boolean;
  dealerSeat: number;
  currentTurn: number;
  lastDiscardBy: number;
  lastDiscardId: number | null;
  lastDiscardObj: TileObject | null;
  gameEnded: boolean;
  winnerSeat: number;
  boardAnimEndTime: number;
  pendingDiceTurnForMe: boolean;
  _flyingWallMeshes: THREE.Mesh[] | null;
  _jumpDealStarted: boolean;
  _pendingWallStart: PendingWallStart | null;
  playerInfo: PlayerInfo[];
  MY_SEAT: number;
}

export const gameState: GameState = {
  // === 阶段 ===
  phase: PHASE.WAITING,

  // === 庄家 ===
  myDealer: false,
  dealerSeat: -1,

  // === 当前回合 ===
  currentTurn: -1,
  lastDiscardBy: -1,
  lastDiscardId: null,
  lastDiscardObj: null,

  // === 结算 ===
  gameEnded: false,
  winnerSeat: -1,

  // === 动画/牌墙启动状态 ===
  boardAnimEndTime: 0,
  pendingDiceTurnForMe: false,
  _flyingWallMeshes: null,
  _jumpDealStarted: false,
  _pendingWallStart: null,

  // === 玩家信息 ===
  playerInfo: [
    { seat: 0, name: '', dice: null, disconnected: false },
    { seat: 1, name: '', dice: null, disconnected: false },
    { seat: 2, name: '', dice: null, disconnected: false },
    { seat: 3, name: '', dice: null, disconnected: false },
  ],

  // === 常量 (从 constants 透出, 方便引用) ===
  MY_SEAT,
};
