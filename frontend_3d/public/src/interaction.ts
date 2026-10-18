// ============================================================
// interaction.mjs — 鼠标交互 (选中 / 拖拽整理 / 右键打出)
// ============================================================
import * as THREE from 'three';
import { gameState } from './state/game-state.ts';
import { handState } from './state/hand-state.ts';
import { interactionState } from './state/interaction-state.ts';
import { sceneRefs } from './state/scene-refs.ts';
import {
  PHASE,
  MY_SEAT,
  STAND_TILE_Y,
  HAND_HALF_RANGE,
  TILE_RISE,
  DRAG_THRESH,
  EMISSIVE,
  handTrack,
  alongToWorld,
  CFG,
} from './constants.ts';
import { setEmissive, finalizeThrow } from './board.ts';
import { toast, updateDiscardBtn } from './ui.ts';
import { animateTo } from './animation.ts';
// /P1-I: 引入公共 yawQuatCached / restBody / _Y_AXIS 替代重复创建
import { yawQuatCached, restBody, _Y_AXIS } from './geo.ts';

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
const dragPlane = new THREE.Plane();
const intersectPt = new THREE.Vector3();
const _localPt = new THREE.Vector3();

function getNDC(e: any) {
  const r = sceneRefs.renderer!.domElement.getBoundingClientRect();
  mouse.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  mouse.y = -((e.clientY - r.top) / r.height) * 2 + 1;
}

function handMeshes() {
  return handState.myHand.map((o: any) => o.mesh);
}

function selectHand(obj: any) {
  for (const o of handState.myHand) setEmissive(o.mesh, EMISSIVE.OFF);
  interactionState.selected = obj;
  setEmissive(obj.mesh, EMISSIVE.SELECT);
  updateDiscardBtn();
}

function clearSelect() {
  if (interactionState.selected) {
    setEmissive(interactionState.selected.mesh, EMISSIVE.OFF);
  }
  interactionState.selected = null;
  updateDiscardBtn();
}

function onPointerDown(e: any) {
  if (e.button !== 0 && e.button !== 2) return;
  if (gameState.phase !== PHASE.PLAY && gameState.phase !== PHASE.DEAL) return;
  // 手牌推倒后 (胡牌/流局) 禁止操作手牌
  if (gameState.gameEnded) return;
  if (e.button === 2) {
    // 右键 = 打出已选中的牌
    if (gameState.currentTurn !== MY_SEAT) {
      toast('不是你的回合', 1200);
      return;
    }
    if (!interactionState.selected || !handState.myHand.includes(interactionState.selected)) {
      toast('先左键选一张牌, 再右键打出', 1600);
      return;
    }
    finalizeThrow(interactionState.selected);
    return;
  }
  // 左键: 选中高亮
  getNDC(e);
  raycaster.setFromCamera(mouse, sceneRefs.camera!);
  const hits = raycaster.intersectObjects(handMeshes());
  if (!hits.length) return;
  const obj = handState.myHand.find((o: any) => o.mesh === hits[0].object);
  if (!obj) return;
  selectHand(obj);
  interactionState.pending = { obj, sx: e.clientX, sy: e.clientY };
  // L-03 修复: sceneRefs.controls 已强类型化为 THREE.OrbitControls, 移除 as any 链
  if (sceneRefs.controls) sceneRefs.controls.enabled = false;
}

function makeGhost(srcObj: any, x: any, z: any, rotY: any) {
  const src = srcObj.mesh;
  const g = src.clone();
  g.material = (Array.isArray(src.material) ? src.material : [src.material]).map((mm: any) => {
    const c = mm.clone();
    c.transparent = true;
    c.opacity = 0.25;
    c.depthWrite = false;
    return c;
  });
  g.position.set(x, STAND_TILE_Y, z);
  // 用 _Y_AXIS 替代 new THREE.Vector3(0, 1, 0)
  g.quaternion.setFromAxisAngle(_Y_AXIS, rotY);
  sceneRefs.seatPivot!.add(g);
  return g;
}

function removeGhost() {
  if (interactionState.ghost) {
    sceneRefs.seatPivot!.remove(interactionState.ghost);
    interactionState.ghost = null;
  }
}

function localDragPoint() {
  if (!raycaster.ray.intersectPlane(dragPlane, intersectPt)) return null;
  _localPt.copy(intersectPt);
  sceneRefs.seatPivot!.worldToLocal(_localPt);
  return _localPt;
}

function recomputeSlots() {
  handState.handSlotPos.length = 0;
  for (let i = 0; i < handState.myHand.length; i++) {
    handState.handSlotPos[i] = (i - (handState.myHand.length - 1) / 2) * (CFG.tile.w + CFG.spacing.handGap);
  }
}

function relayoutHand(animated: any, except: any) {
  const tr = handTrack(MY_SEAT);
  for (let i = 0; i < handState.myHand.length; i++) {
    const o = handState.myHand[i];
    if (o === except) continue;
    const along = handState.handSlotPos[i];
    const { x, z } = alongToWorld(MY_SEAT as number, along as number);
    if (animated) {
      animateTo(o.body, x as number, STAND_TILE_Y, z as number, tr.rotY, CFG.anim.rearrange);
    } else {
      o.body.position.set(x as number, STAND_TILE_Y, z as number);
      // /P1-I: 用 yawQuatCached + restBody 替代重复创建
      const q = yawQuatCached(tr.rotY);
      o.body.quaternion.set(q.x, q.y, q.z, q.w);
      restBody(o.body);
      interactionState.dirtyBodies.set(o.body, o.mesh);
    }
  }
}

function beginArrangeDrag(obj: any) {
  interactionState.dragMode = 'move';
  interactionState.dragging = true;
  sceneRefs.renderer!.domElement.style.cursor = 'grabbing';
  dragPlane.setFromNormalAndCoplanarPoint(_Y_AXIS, new THREE.Vector3(0, STAND_TILE_Y, 0));
  const tr = handTrack(MY_SEAT);
  recomputeSlots();
  const idx = handState.myHand.indexOf(obj);
  const { x: gx, z: gz } = alongToWorld(MY_SEAT, handState.handSlotPos[idx]);
  removeGhost();
  interactionState.ghost = makeGhost(obj, gx, gz, tr.rotY);
  // /P1-I: 用 yawQuatCached 替代
  const q = yawQuatCached(tr.rotY);
  obj.body.quaternion.set(q.x, q.y, q.z, q.w);
  obj.body.position.set(gx, STAND_TILE_Y + TILE_RISE, gz);
  interactionState.dirtyBodies.set(obj.body, obj.mesh);
}

function onPointerMove(e: any) {
  // 手牌推倒后禁止拖拽
  if (gameState.gameEnded) return;
  if (interactionState.pending && !interactionState.dragging) {
    if (Math.hypot(e.clientX - interactionState.pending.sx, e.clientY - interactionState.pending.sy) < DRAG_THRESH)
      return;
    beginArrangeDrag(interactionState.pending.obj);
  }
  if (!interactionState.dragging || !interactionState.selected || interactionState.dragMode !== 'move') return;
  getNDC(e);
  raycaster.setFromCamera(mouse, sceneRefs.camera!);
  const lp = localDragPoint();
  if (!lp) return;
  const tr = handTrack(MY_SEAT);
  let along = tr.axis === 'z' ? lp.x : lp.z;
  along = Math.max(-HAND_HALF_RANGE, Math.min(HAND_HALF_RANGE, along));
  const { x, z } = alongToWorld(MY_SEAT as number, along as number);
  // /P1-I: pointermove 每秒 60-120 次触发, 用 yawQuatCached 避免每次 new Quaternion+Vector3 (消除 GC 压力)
  const q = yawQuatCached(tr.rotY);
  interactionState.selected.body.quaternion.set(q.x, q.y, q.z, q.w);
  interactionState.selected.body.position.set(x as number, STAND_TILE_Y + TILE_RISE, z as number);
  interactionState.dirtyBodies.set(interactionState.selected.body, interactionState.selected.mesh);
  if (interactionState.ghost) interactionState.ghost.position.set(x as number, STAND_TILE_Y, z as number);
  reorderDuringDrag();
}

function reorderDuringDrag() {
  if (!interactionState.selected) return;
  const tr = handTrack(MY_SEAT);
  const along = tr.axis === 'z' ? interactionState.selected.body.position.x : interactionState.selected.body.position.z;
  const sp = CFG.tile.w + CFG.spacing.handGap;
  const n = handState.myHand.length;
  let want = Math.round(along / sp + (n - 1) / 2);
  want = Math.max(0, Math.min(n - 1, want));
  const cur = handState.myHand.indexOf(interactionState.selected);
  if (want !== cur && cur >= 0) {
    handState.myHand.splice(cur, 1);
    handState.myHand.splice(want, 0, interactionState.selected);
    recomputeSlots();
    // P1-5 修复: 拖拽中用 relayoutHand(false) (非动画), 消除每帧 ~28 个闭包 (原 relayoutHand(true) 每秒 1680 个闭包)
    relayoutHand(false, interactionState.selected);
  }
}

function onPointerUp() {
  if (interactionState.pending && !interactionState.dragging) {
    interactionState.pending = null;
    if (sceneRefs.controls) sceneRefs.controls.enabled = true;
    return;
  }
  interactionState.pending = null;
  if (!interactionState.dragging || !interactionState.selected) {
    if (sceneRefs.controls) sceneRefs.controls.enabled = true;
    sceneRefs.renderer!.domElement.style.cursor = 'grab';
    return;
  }
  if (interactionState.dragMode === 'move') {
    removeGhost();
    recomputeSlots();
    const idx = handState.myHand.indexOf(interactionState.selected);
    const { x, z } = alongToWorld(MY_SEAT, handState.handSlotPos[idx]);
    animateTo(interactionState.selected.body, x as number, STAND_TILE_Y, z as number, handTrack(MY_SEAT).rotY, 180);
    relayoutHand(true, interactionState.selected);
  }
  interactionState.dragging = false;
  interactionState.dragMode = null;
  if (sceneRefs.controls) sceneRefs.controls.enabled = true;
  sceneRefs.renderer!.domElement.style.cursor = 'grab';
}

function onContext(e: any) {
  e.preventDefault();
}

// M-11 修复: 移动端触摸适配 + 设备检测
// 检测移动设备 (touch + 小屏幕), 启用触摸手势 + 降低渲染质量
export const IS_MOBILE: boolean = (() => {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false;
  const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  const isSmallScreen = window.innerWidth < 768 || window.innerHeight < 600;
  const ua = navigator.userAgent.toLowerCase();
  const isMobileUA = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(ua);
  return hasTouch && (isSmallScreen || isMobileUA);
})();

// M-11 修复: 触摸手势状态 (双指捏合缩放视角, 单指拖拽手牌)
let _touchPinchDist = 0;
let _isPinching = false;

function onTouchStart(e: TouchEvent) {
  if (e.touches.length === 2) {
    // 双指捏合: 计算初始距离
    const dx = e.touches[0].clientX - e.touches[1].clientX;
    const dy = e.touches[0].clientY - e.touches[1].clientY;
    _touchPinchDist = Math.hypot(dx, dy);
    _isPinching = true;
    // 禁用 OrbitControls, 让 pinch 事件控制
    if (sceneRefs.controls) sceneRefs.controls.enabled = false;
  }
}

function onTouchMove(e: TouchEvent) {
  if (_isPinching && e.touches.length === 2) {
    e.preventDefault();
    const dx = e.touches[0].clientX - e.touches[1].clientX;
    const dy = e.touches[0].clientY - e.touches[1].clientY;
    const dist = Math.hypot(dx, dy);
    const delta = dist - _touchPinchDist;
    // 捏合缩放: 调整 camera 距离
    if (sceneRefs.camera) {
      const dir = new THREE.Vector3();
      sceneRefs.camera.getWorldDirection(dir);
      const moveAmount = delta * 0.02;
      sceneRefs.camera.position.addScaledVector(dir, -moveAmount);
      // 限制缩放范围
      const distFromTarget = sceneRefs.camera.position.length();
      if (distFromTarget < 12) sceneRefs.camera.position.setLength(12);
      if (distFromTarget > 42) sceneRefs.camera.position.setLength(42);
    }
    _touchPinchDist = dist;
  }
}

function onTouchEnd(e: TouchEvent) {
  if (e.touches.length < 2) {
    _isPinching = false;
    // 恢复 OrbitControls
    if (sceneRefs.controls) sceneRefs.controls.enabled = true;
  }
}

function bindInteraction() {
  const el = sceneRefs.renderer!.domElement;
  el.addEventListener('pointerdown', onPointerDown);
  el.addEventListener('pointermove', onPointerMove);
  el.addEventListener('pointerup', onPointerUp);
  el.addEventListener('contextmenu', onContext);
  el.style.cursor = 'grab';

  // M-11 修复: 移动端触摸手势 (双指捏合缩放)
  if (IS_MOBILE) {
    el.addEventListener('touchstart', onTouchStart, { passive: false });
    el.addEventListener('touchmove', onTouchMove, { passive: false });
    el.addEventListener('touchend', onTouchEnd, { passive: false });
    // 移动端隐藏鼠标光标
    el.style.cursor = 'default';
    console.log('[M-11] 移动端模式已启用: 触摸手势 + 降低渲染质量');
  }
}

export {
  bindInteraction,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onContext,
  selectHand,
  clearSelect,
  recomputeSlots,
  relayoutHand,
};
