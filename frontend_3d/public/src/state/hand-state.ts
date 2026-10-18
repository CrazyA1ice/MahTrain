// ============================================================
// state/hand-state.mjs — 牌实例管理
// ============================================================
// 由 state.mjs 拆分而来 (P2-2). 持有所有玩家的手牌、副露、弃牌、以及 mesh 索引等.
// 在 board.mjs / handlers.mjs / interaction.mjs 中读写.
import type { TileObject, MeldGroup, DiscardTile } from '../types';

export const handState: {
  myHand: TileObject[];
  discardTiles: DiscardTile[];
  oppHands: Record<number, TileObject[]>;
  meldGroups: Record<number, MeldGroup[]>;
  myIdCounter: number;
  handSlotPos: number[];
} = {
  // === 我的手牌 [{id, type, value, mesh, body}] ===
  myHand: [],

  // === 弃牌 [{id, obj, bySeat}] ===
  discardTiles: [],

  // === 对手手牌 (按座位索引, 仅含 mesh/body 数量信息) ===
  oppHands: { 0: [], 1: [], 2: [], 3: [] },

  // === 副露 (按座位索引) ===
  meldGroups: { 0: [], 1: [], 2: [], 3: [] },

  // 死代码清理 (方案2): handMeshById Map 已删除 (0 处 set/get, 永远空 Map)

  // === 客户端自增 id 计数器 (避免与服务器 id 冲突) ===
  myIdCounter: 100000,

  // === 手牌槽位 along 坐标列表 (开局/摸牌后重排) ===
  handSlotPos: [],
};
