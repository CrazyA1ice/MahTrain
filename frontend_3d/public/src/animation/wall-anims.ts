// ============================================================
// animation/wall-anims.ts — 牌墙动画 (重整牌墙: 飞到天上矩阵 → 飞回新牌墙)
// ============================================================
import * as THREE from 'three';
import { yawQuat } from '../geo.ts';
import { flyAlongParabola, _X_AXIS } from './core.ts';
import type { TileObject } from '../types';

interface Vec3Like {
  x: number;
  y: number;
  z: number;
}

// 飞到天上矩阵 (cubic-out + 二次贝塞尔抛物线 + 旋转 1.3× 早完成)
// peakAdd=1.5: 适中的弧线高度, 避免不同方位的牌在飞行途中交叉穿模
export function flyToGrid(obj: TileObject, gridPos: Vec3Like) {
  const eQ = new THREE.Quaternion().setFromAxisAngle(_X_AXIS, Math.PI / 2);
  const eP = { x: gridPos.x, y: gridPos.y, z: gridPos.z };
  flyAlongParabola(obj, eP, eQ, 500, 1.5, 1.3);
}

// 飞回新牌墙 (cubic-out + 二次贝塞尔抛物线 + 旋转 1.2× 早完成)
export function flyFromGridToWall(obj: TileObject, wallPos: Vec3Like & { rotY: number }) {
  const yaw = yawQuat(wallPos.rotY);
  const flat = new THREE.Quaternion().setFromAxisAngle(_X_AXIS, Math.PI / 2);
  const eQ = yaw.multiply(flat);
  const eP = { x: wallPos.x, y: wallPos.y, z: wallPos.z };
  flyAlongParabola(obj, eP, eQ, 400, 1.0, 1.2);
}
