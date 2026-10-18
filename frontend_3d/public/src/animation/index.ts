// ============================================================
// animation/index.ts — 动画系统统一入口 (方案2 拆分)
// ============================================================
// 原 animation.ts (330 行) 拆分为 5 个文件:
//   - core.ts: tweenBody 骨架 + markDirty/cancelAnimsFor/settleBody + flyAlongParabola
//   - tile-anims.ts: 牌飞行动画 (发牌/弃牌/副露/胡牌亮牌/平放)
//   - wall-anims.ts: 牌墙动画 (重整牌墙: 飞到天上矩阵 → 飞回新牌墙)
//   - dice-anims.ts: 骰子动画 (showDiceResult, 从 scene.ts 迁入)
//   - index.ts: 统一 re-export, 调用方只需 import { ... } from '../animation.ts'
//
// 调用方无需修改 import 路径 (animation.ts 仍可用, 内部改为 re-export).
export { tweenBody, flyAlongParabola, markDirty, cancelAnimsFor, settleBody, _X_AXIS } from './core.ts';
export {
  animateTo,
  flyTileTo,
  tossDiscard,
  flatSlot,
  layFlatTile,
  tipOverTile,
  flyToFlat,
  meldAlong,
} from './tile-anims.ts';
export { flyToGrid, flyFromGridToWall } from './wall-anims.ts';
export { showDiceResult } from './dice-anims.ts';
