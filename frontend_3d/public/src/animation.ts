// ============================================================
// animation.ts — 兼容性 re-export (方案2 拆分后保留)
// ============================================================
// 原动画系统已拆分到 animation/ 目录 (core/tile-anims/wall-anims/dice-anims).
// 此文件仅作 re-export, 让现有 import { ... } from './animation.ts' 继续可用.
// 新代码建议直接 import { ... } from './animation/index.ts'.
export { tweenBody, flyAlongParabola, markDirty, cancelAnimsFor, settleBody, _X_AXIS } from './animation/core.ts';
export {
  animateTo,
  flyTileTo,
  tossDiscard,
  flatSlot,
  layFlatTile,
  tipOverTile,
  flyToFlat,
  meldAlong,
} from './animation/tile-anims.ts';
export { flyToGrid, flyFromGridToWall } from './animation/wall-anims.ts';
export { showDiceResult } from './animation/dice-anims.ts';
