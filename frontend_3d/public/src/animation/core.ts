// ============================================================
// animation/core.ts — 动画系统核心骨架 (tweenBody 通用工厂 + 共享工具)
// ============================================================
// 从 animation.ts 拆分而来 (方案2). 提供所有动画共享的:
//   - markDirty / cancelAnimsFor / settleBody 工具
//   - tweenBody 通用骨架 (8 个飞牌动画的统一模板)
//   - _X_AXIS / _tmpQ 共享对象 (减少 GC)
import * as THREE from 'three';
import * as CANNON from '../physics.ts';
import { interactionState } from '../state/interaction-state.ts';
import { STAND_TILE_Y } from '../constants.ts';
import { yawQuat, restBody } from '../geo.ts';
import type { BodyWithUserData } from '../geo.ts';
import type { Animation } from '../types';

// 共享 X 轴单位向量 (替代 5 处重复的 new THREE.Vector3(1, 0, 0))
export const _X_AXIS = new THREE.Vector3(1, 0, 0);

// 临时四元数 (slerp 用, 避免每帧 new)
const _tmpQ = new THREE.Quaternion();

interface Vec3Like {
  x: number;
  y: number;
  z: number;
}

// 标记 body 为 dirty (本帧需要 mesh.copy 同步)
// dirty 改为 Map, 同时存 mesh 引用, 主循环直接遍历 dirty, 无需全量遍历
export function markDirty(body: CANNON.Body): void {
  const ud = (body as BodyWithUserData).userData;
  const mesh = ud && (ud._mesh as THREE.Mesh | undefined);
  if (mesh) interactionState.dirtyBodies.set(body, mesh);
  else interactionState.dirtyBodies.set(body, null); // 兜底: 极少数情况 body 无 userData (如骰子)
}

// 标记取消某 body 上正在进行的动画 (不直接 splice 数组, 主循环统一清理)
export function cancelAnimsFor(body: CANNON.Body): void {
  for (const a of interactionState.animations) {
    if (a.body === body) a.dead = true;
  }
}

// 把牌"安放"到精确槽位 (不触碰 animations 数组)
export function settleBody(body: CANNON.Body, x: number, z: number, rotY: number): void {
  body.type = CANNON.Body.KINEMATIC;
  body.position.set(x, STAND_TILE_Y, z);
  const q = yawQuat(rotY);
  body.quaternion.set(q.x, q.y, q.z, q.w);
  restBody(body);
  markDirty(body);
}

type EaseFn = (t: number) => number;
type VerticalFn = ((t: number, sy: number, ey: number, peak: number | null) => number) | null;

export interface TweenBodyOpts {
  body: CANNON.Body | null;
  mesh: THREE.Mesh | null;
  eP: Vec3Like;
  eQ: THREE.Quaternion;
  dur: number;
  peak?: number | null;
  easeFn?: EaseFn;
  verticalFn?: VerticalFn;
  rotScale?: number;
  onDone?: (() => void) | null;
}

// ============ tweenBody 通用骨架 ============
// 8 个飞牌动画的统一模板: cancelAnimsFor → 记录 sP/sQ → 计算 eP/eQ → push 到 interactionState.animations
// update 回调内做位置/旋转插值 + markDirty + mesh.copy + 收尾
//
// 参数:
//   body, mesh: 物理体 + 视觉 mesh (body 可为 null, 仅操作 mesh)
//   eP: 终点位置 {x,y,z}; eQ: 终点姿态 Quaternion
//   dur: 时长 ms; peak: 抛物线峰值 (null=线性, 数字=抛物线)
//   easeFn: 自定义水平缓动 (默认 cubic-out); verticalFn: 自定义垂直插值
//   rotScale: 旋转时间缩放 (默认 1, 即旋转与位置同步完成; 1.3 = 前 77% 完成旋转)
//   onDone: 完成回调
export function tweenBody(opts: TweenBodyOpts): void {
  const {
    body,
    mesh,
    eP,
    eQ,
    dur,
    peak = null,
    easeFn = (t) => 1 - Math.pow(1 - t, 3),
    verticalFn = null,
    rotScale = 1,
    onDone = null,
  } = opts;
  const hasBody = !!body;
  if (hasBody && body) {
    cancelAnimsFor(body);
    body.type = CANNON.Body.KINEMATIC;
    body.wakeUp();
  }
  const sP =
    hasBody && body
      ? body.position.clone()
      : mesh
        ? new THREE.Vector3(mesh.position.x, mesh.position.y, mesh.position.z)
        : new THREE.Vector3();
  const sQ =
    hasBody && body
      ? new THREE.Quaternion(body.quaternion.x, body.quaternion.y, body.quaternion.z, body.quaternion.w)
      : mesh
        ? new THREE.Quaternion(mesh.quaternion.x, mesh.quaternion.y, mesh.quaternion.z, mesh.quaternion.w)
        : new THREE.Quaternion();
  // P0-A2 修复 (BUG-A2): t0 挂到 anim 对象上, 让 main.ts visibilitychange 的 pause-recovery 逻辑生效
  const t0 = performance.now();
  interactionState.animations.push({
    body: hasBody ? body : null,
    t0, // 暴露 t0, 供标签页恢复时偏移
    update: (): boolean => {
      const t = Math.min((performance.now() - t0) / dur, 1);
      const ease = easeFn(t);
      // 水平插值
      const px = sP.x + (eP.x - sP.x) * ease;
      const pz = sP.z + (eP.z - sP.z) * ease;
      // 垂直插值: 默认线性, peak 提供时用二次贝塞尔抛物线, verticalFn 自定义
      let py: number;
      if (verticalFn) {
        py = verticalFn(t, sP.y, eP.y, peak);
      } else if (peak !== null) {
        py = (1 - t) * (1 - t) * sP.y + 2 * (1 - t) * t * peak + t * t * eP.y;
      } else {
        py = sP.y + (eP.y - sP.y) * ease;
      }
      // 旋转: slerp + rotScale (支持旋转早完成)
      const rotT = Math.min(1, t * rotScale);
      _tmpQ.slerpQuaternions(sQ, eQ, rotT);
      if (hasBody && body) {
        body.position.set(px, py, pz);
        (body.quaternion as unknown as THREE.Quaternion).copy(_tmpQ);
        markDirty(body);
      }
      if (mesh) {
        mesh.position.set(px, py, pz);
        mesh.quaternion.copy(_tmpQ);
      }
      if (t >= 1) {
        if (hasBody && body) {
          body.position.set(eP.x, eP.y, eP.z);
          (body.quaternion as unknown as THREE.Quaternion).copy(eQ);
          restBody(body);
        }
        if (mesh) {
          mesh.position.set(eP.x, eP.y, eP.z);
          mesh.quaternion.copy(eQ);
        }
        if (typeof onDone === 'function') onDone();
        return false;
      }
      return true;
    },
  } as Animation);
}

// 方案3-A: 抽 flyAlongParabola 公共骨架 — 替代 flyToGrid/flyFromGridToWall 95% 重复代码
// obj: { mesh, body? }; eP: 终点 {x,y,z}; eQ: 终点 Quaternion
// dur: 时长 ms; peakAdd: 抛物线峰值加值 (相对 max(sP.y, eP.y)); rotScale: 旋转时间缩放
export function flyAlongParabola(
  obj: { mesh: THREE.Mesh; body?: CANNON.Body | null },
  eP: Vec3Like,
  eQ: THREE.Quaternion,
  dur: number,
  peakAdd: number,
  rotScale: number
): void {
  const hasBody = !!obj.body;
  const body = obj.body;
  const mesh = obj.mesh;
  const sP = hasBody && body ? body.position.clone() : mesh.position.clone();
  const peak = Math.max(sP.y, eP.y) + peakAdd;
  return tweenBody({
    body: hasBody && body ? body : null,
    mesh,
    eP,
    eQ,
    dur,
    peak,
    rotScale,
  });
}
