// ============================================================
// animation/tile-anims.ts — 牌飞行动画 (发牌/弃牌/副露/胡牌亮牌/平放)
// ============================================================
// 从 animation.ts 拆分而来 (方案2). 包含所有"牌从 A 飞到 B"的动画.
import * as THREE from 'three';
import * as CANNON from '../physics.ts';
import {
  STAND_TILE_Y,
  GROUND_Y,
  HALF_D,
  HALF_W,
  CFG,
  handTrack,
  meldTrack,
  seatFromRotY,
  FELT_OUTER_LIMIT,
  leftSign,
} from '../constants.ts';
import { yawQuat, restBody } from '../geo.ts';
import type { BodyWithUserData } from '../geo.ts';
import { tweenBody, markDirty, _X_AXIS } from './core.ts';
import type { TileObject } from '../types';

// 通用 tween 动画 (无 mesh, 直接传 body) — 整理牌用
export function animateTo(body: CANNON.Body, ex: number, ey: number, ez: number, rotY: number, dur: number): void {
  const ud = (body as BodyWithUserData).userData;
  const mesh = ud && (ud._mesh as THREE.Mesh | undefined);
  tweenBody({
    body,
    mesh: mesh ?? null,
    eP: { x: ex, y: ey, z: ez },
    eQ: yawQuat(rotY),
    dur,
  });
}

// 单张牌从当前位置高弧飞到目标槽位 (sin 抛物线 + cubic-out 水平)
// 用于发牌与摸牌动画
// 降低峰值(2.2 → 1.5), 配合更短时长(280ms), 动画更干脆
export function flyTileTo(obj: TileObject, along: number, rotY: number, done?: () => void): void {
  const body = obj.body;
  const seat = seatFromRotY(rotY);
  const tr = handTrack(seat);
  let ex: number, ez: number;
  if (tr.axis === 'z') {
    ex = along;
    ez = tr.constZ ?? 0;
  } else {
    ez = along;
    ex = tr.constX ?? 0;
  }
  // sin 单峰抛物线: y = STAND_TILE_Y + sin(t*π) * peak
  tweenBody({
    body,
    mesh: obj.mesh,
    eP: { x: ex, y: STAND_TILE_Y, z: ez },
    eQ: yawQuat(rotY),
    dur: CFG.anim.dealFly,
    verticalFn: (t: number, _sP_y: number, eP_y: number, _peak: number | null) =>
      eP_y + Math.sin(t * Math.PI) * (CFG.anim.flyTilePeak || 1.0),
    onDone: done ?? null,
  });
}

// 弃牌抛物线动画 (t^1.5 水平 + 二次贝塞尔垂直 + 旋转 1.3× 早完成)
export function tossDiscard(obj: TileObject, cx: number, cz: number, rotY: number): void {
  const yEnd = GROUND_Y + HALF_D;
  const peak = STAND_TILE_Y + (CFG.anim.discardPeakAdd || 3.0);
  const upFace = new THREE.Quaternion().setFromAxisAngle(_X_AXIS, -Math.PI / 2);
  tweenBody({
    body: obj.body,
    mesh: obj.mesh,
    eP: { x: cx, y: yEnd, z: cz },
    eQ: yawQuat(rotY).multiply(upFace),
    dur: CFG.anim.discard,
    peak,
    easeFn: (t: number) => Math.pow(t, 1.5), // 水平先慢后快
    rotScale: 1.3, // 旋转在前 77% 完成
  });
}

// 副露区某格的局部落点 + 平放姿态
export function flatSlot(seat: number, alongPos: number): { x: number; y: number; z: number; q: THREE.Quaternion } {
  const tr = meldTrack(seat); // 用副露轨道 (MELD_DIST), 与手牌拉开距离
  // 贴桌边: 用 FELT_OUTER_LIMIT 减去半个牌宽, 让副露牌的外边贴桌沿
  const edge = FELT_OUTER_LIMIT - HALF_W * 0.5;
  let x: number, z: number;
  if (tr.axis === 'z') {
    x = alongPos;
    z = tr.constZ != null ? (tr.constZ > 0 ? edge : -edge) : 0;
  } else {
    z = alongPos;
    x = tr.constX != null ? (tr.constX > 0 ? edge : -edge) : 0;
  }
  const yaw = yawQuat(tr.rotY);
  const flat = new THREE.Quaternion().setFromAxisAngle(_X_AXIS, -Math.PI / 2);
  const q = yaw.multiply(flat);
  return { x, y: GROUND_Y + HALF_D, z, q };
}

// 直接平放到位 (无动画) — 副露动画收尾吸附用
export function layFlatTile(obj: TileObject, seat: number, alongPos: number): void {
  const s = flatSlot(seat, alongPos);
  obj.body.type = CANNON.Body.KINEMATIC;
  obj.body.position.set(s.x, s.y, s.z);
  (obj.body.quaternion as unknown as THREE.Quaternion).copy(s.q);
  restBody(obj.body);
  markDirty(obj.body);
}

// 模拟胡牌后亮牌: 牌原地向前推倒, 正面朝上 (cubic-out + 平移到 y=GROUND_Y+HALF_D)
export function tipOverTile(obj: TileObject, _seat: number): void {
  const body = obj.body;
  const sP = body.position.clone();
  const sQ = new THREE.Quaternion(body.quaternion.x, body.quaternion.y, body.quaternion.z, body.quaternion.w);
  // 目标姿态: 当前 yaw + 绕 X 轴 -90° (平躺正面朝上)
  const flat = new THREE.Quaternion().setFromAxisAngle(_X_AXIS, -Math.PI / 2);
  const eQ = sQ.clone().multiply(flat);
  tweenBody({
    body,
    mesh: obj.mesh,
    eP: { x: sP.x, y: GROUND_Y + HALF_D, z: sP.z },
    eQ,
    dur: CFG.anim.tipOver || 400,
  });
}

// 从当前位置走弧线飞到副露区并平放 (线性水平 + 二次贝塞尔垂直 + 旋转 1.2× 早完成)
// 新增 onDone 回调, 让调用方在动画完成时精确触发后续逻辑 (替代固定 50ms 余量的 setTimeout)
export function flyToFlat(obj: TileObject, seat: number, alongPos: number, onDone?: () => void): void {
  const e = flatSlot(seat, alongPos);
  const body = obj.body;
  const sP = body.position.clone();
  const peak = Math.max(sP.y, STAND_TILE_Y) + (CFG.anim.flyToFlatPeakAdd || 1.4);
  tweenBody({
    body,
    mesh: obj.mesh,
    eP: { x: e.x, y: e.y, z: e.z },
    eQ: e.q,
    dur: CFG.anim.meld,
    peak,
    easeFn: (t: number) => t, // 水平线性 (与原实现一致, 风格略不同)
    rotScale: 1.2,
    onDone: onDone ?? null,
  });
}

// 副露第 slot 组、第 col 张牌的 along 坐标
// prevKinds: 前面所有组的 kind 数组 (['pong','kong',...]), 用来累加实际占用的宽度
// 碰(pong)占 3 列, 杠(kong/ckong)占 4 列, 每列宽度 sp
// 副露从桌边角落向内排列, 限制最大向内延伸以避免与手牌穿模
export function meldAlong(seat: number, slot: number, col: number, prevKinds: string[] = []): number {
  const sp = CFG.tile.w + CFG.spacing.meldGap;
  const s = leftSign(seat);
  const corner = FELT_OUTER_LIMIT - CFG.tile.w * 0.5;
  const edgeStart = s > 0 ? corner : -corner;
  // 累加前面所有组的实际宽度 (碰3, 杠4)
  let offset = 0;
  for (const k of prevKinds) {
    offset += k === 'pong' ? 3 * sp : 4 * sp;
  }
  return edgeStart - s * (offset + col * sp);
}
