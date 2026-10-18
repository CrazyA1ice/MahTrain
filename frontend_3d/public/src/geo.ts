// ============================================================
// geo.ts — 几何与物理体辅助工具 (P1-D 重构: 消除重复)
// ============================================================
// 抽离自 animation / board / interaction / handlers 中
// 14 处重复的 yawQuat 构造 + 10 处重复的 restBody 三连击 + 5 处重复的 placeStandTile
// 集中在此模块管理, 减少冗余与 GC 压力
//
// 死代码清理 (方案2):
//   - restBodyAt: 全工程 0 处调用, 已删除
//   - alongToWorld / discardCell / seatFromRotY / tileLabel: 与 constants.ts 重复, 已删除
//     (constants.ts 是唯一所有者, 调用方均从 constants.ts 导入)
import * as THREE from 'three';
import * as CANNON from './physics.ts';

// 共享 Y 轴单位向量 (避免每次 new THREE.Vector3(0, 1, 0))
export const _Y_AXIS = new THREE.Vector3(0, 1, 0);

// yawQuat 工厂 — 替代 14 处重复的
// new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), rotY)
// 消除每次 new Vector3 的 GC 压力
export function yawQuat(rotY: number): THREE.Quaternion {
  return new THREE.Quaternion().setFromAxisAngle(_Y_AXIS, rotY);
}

// 缓存常用 rotY 的 yawQuat (90° 整数倍)
// 牌桌四个方位 seat 0/1/2/3 对应 rotY 0/-90/180/90, 缓存命中率高
const _yawQuatCache = new Map<number, THREE.Quaternion>();
export function yawQuatCached(rotY: number) {
  let q = _yawQuatCache.get(rotY);
  if (!q) {
    q = yawQuat(rotY);
    _yawQuatCache.set(rotY, q);
  }
  return q;
}

// restBody 工具 — 替代 10 处重复的
// body.velocity.setZero(); body.angularVelocity.setZero(); body.sleep();
export function restBody(body: CANNON.Body) {
  body.velocity.setZero();
  body.angularVelocity.setZero();
  body.sleep();
}

// makeTileBody 工厂 — 替代 board.ts 中 createStandTile / createStandTileBack 90% 重复
//   mesh: 已创建的 Three.js mesh (TileFactory.create 或 createBack)
//   extra: 附加到返回对象的字段 (如 { id, type, value } 或 { id, isOpponent: true })
//   deps:  { HALF_W, HALF_H, HALF_D, matTile, world }
export interface MakeTileBodyDeps {
  HALF_W: number;
  HALF_H: number;
  HALF_D: number;
  matTile: CANNON.Material;
  world: CANNON.World;
}
export function makeTileBody<T extends Record<string, unknown>>(
  mesh: THREE.Mesh,
  extra: T,
  deps: MakeTileBodyDeps
): T & { mesh: THREE.Mesh; body: CANNON.Body } {
  const { HALF_W, HALF_H, HALF_D, matTile, world } = deps;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  const body = new CANNON.Body({
    mass: 0,
    type: CANNON.Body.KINEMATIC,
    shape: new CANNON.Box(new CANNON.Vec3(HALF_W, HALF_H, HALF_D)),
    material: matTile,
  });
  // 把 mesh 引用存到 body.userData, 主循环 dirty 同步时直接取出, 无需遍历全量手牌
  (body as BodyWithUserData).userData = { _mesh: mesh };
  world.addBody(body);
  mesh.position.copy(body.position);
  mesh.quaternion.copy(body.quaternion);
  return { mesh, body, ...extra };
}

// CANNON.Body 默认不带 userData, 此处为其扩展 (见 types.d.ts 模块增强)
export interface BodyWithUserData extends CANNON.Body {
  userData: Record<string, unknown> | undefined;
}
