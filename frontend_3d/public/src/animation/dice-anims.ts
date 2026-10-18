// ============================================================
// animation/dice-anims.ts — 骰子动画 (showDiceResult)
// ============================================================
// 从 scene.ts:275-326 迁入 (方案2). 把散落在场景文件里的骰子动画收回到 animation/ 目录.
// 同时修复 BUG-A2: t0 挂到 anim 对象上, 让标签页恢复时偏移生效.
import * as THREE from 'three';
import * as CANNON from '../physics.ts';
import { CFG } from '../constants.ts';
import { sceneRefs } from '../state/scene-refs.ts';
import { interactionState } from '../state/interaction-state.ts';

// 显示骰子点数动画: 两个骰子从初始位置旋转飞到目标点数姿态
// values: [点数1, 点数2]; onComplete: 动画结束回调 (显示点数文本)
export function showDiceResult(values: number[], onComplete?: () => void): void {
  const map: Record<number, THREE.Vector3> = {
    1: new THREE.Vector3(1, 0, 0),
    2: new THREE.Vector3(-1, 0, 0),
    3: new THREE.Vector3(0, 1, 0),
    4: new THREE.Vector3(0, -1, 0),
    5: new THREE.Vector3(0, 0, 1),
    6: new THREE.Vector3(0, 0, -1),
  };
  const size = CFG.dice.size;
  const restY = CFG.dice.trayBottomY + size / 2 + 0.02;
  const halfHole = CFG.table.holeSize / 2;
  const R = halfHole - size / 2 - 0.12;
  const axis = new THREE.Vector3(0, 1, 0);
  let doneCount = 0;
  const total = sceneRefs.diceBodies.length;
  sceneRefs.diceBodies.forEach((b: CANNON.Body, i: number) => {
    b.type = 2; // CANNON.Body.KINEMATIC
    b.wakeUp();
    const baseX = -0.55 + i * 1.1;
    const target = map[values[i]] || new THREE.Vector3(0, 1, 0);
    const qFace = new THREE.Quaternion().setFromUnitVectors(target, new THREE.Vector3(0, 1, 0));
    const yaw = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), i * 0.6);
    const final = yaw.multiply(qFace);
    const turns = 4 + i * 0.5;
    const phase0 = i * Math.PI;
    const dur = CFG.anim.dice;
    // P0-A2 修复 (BUG-A2): t0 挂到 anim 对象上, 让 main.ts visibilitychange 的 pause-recovery 逻辑生效
    const t0 = performance.now();
    interactionState.animations.push({
      body: b, // 骰子 body, 用于 cancelAnimsFor 匹配
      t0, // 暴露 t0, 供标签页恢复时偏移
      update: (): boolean => {
        const t = Math.min((performance.now() - t0) / dur, 1);
        const ease = 1 - Math.pow(1 - t, 3);
        const ang = turns * 2 * Math.PI * ease + phase0;
        const spin = new THREE.Quaternion().setFromAxisAngle(axis, ang);
        (b.quaternion as unknown as THREE.Quaternion).copy(new THREE.Quaternion().slerpQuaternions(spin, final, t * t));
        const shrink = 1 - t * t;
        const ox = Math.cos(ang) * R,
          oz = Math.sin(ang) * R;
        b.position.set(baseX + (ox - baseX) * shrink, restY, oz * shrink);
        if (t >= 1) {
          doneCount++;
          // 最后一个骰子动画结束时, 调回调 (显示点数)
          if (doneCount === total && typeof onComplete === 'function') {
            onComplete();
          }
          return false;
        }
        return t < 1;
      },
    });
  });
}
