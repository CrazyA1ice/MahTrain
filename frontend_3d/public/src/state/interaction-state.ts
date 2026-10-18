// ============================================================
// state/interaction-state.mjs — 交互 + 动画
// ============================================================
// 由 state.mjs 拆分而来 (P2-2). 持有选牌/拖拽/ghost/弃牌高亮 + 动画队列.
// 在 interaction.mjs / animation.mjs / board.mjs / main.mjs 中读写.
import type * as THREE from 'three';
import type * as CANNON from '../physics.ts';
import type { Animation, TileObject } from '../types';

export const interactionState: {
  selected: TileObject | null;
  dragMode: string | null;
  dragging: boolean;
  ghost: THREE.Mesh | null;
  pending: { obj: TileObject; sx: number; sy: number } | null;
  discardArrow: THREE.Object3D | null;
  arrowToken: number;
  animations: Animation[];
  dirtyBodies: Map<CANNON.Body, THREE.Mesh | null>;
} = {
  // === 选牌/拖拽 ===
  selected: null,
  dragMode: null,
  dragging: false,
  ghost: null,
  pending: null,

  // === 弃牌高亮 ===
  discardArrow: null,
  arrowToken: 0,

  // === 动画队列 ===
  animations: [],

  // 牌的 body 是 KINEMATIC, 位置只在动画期间变化.
  // dirty 改为 Map<body, {mesh}>, 主循环直接遍历 dirty 即可, 避免 232 次全量 Set.has 查询.
  // 用法: interactionState.dirtyBodies.set(body, { mesh }) /
  //       for (const [body, {mesh}] of interactionState.dirtyBodies) {...}
  dirtyBodies: new Map(),
};
