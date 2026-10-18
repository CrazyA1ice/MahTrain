// ============================================================
// board.ts — 牌实例管理 (创建/移动/高亮/副露渲染/弃牌抛出)
// ============================================================
// board 通过 events.ts 触发事件, 不直接调用 interaction / scene (避免循环依赖)
// 牌墙位置生成已拆到独立模块 wall-positions.ts:
//   - generateWallPositions / generateWallBackPositions / generateQuadrantGridPositions
// 本文件保留牌实例创建/高亮/出牌/副露渲染/重置编排 (含 forceCompleteResetAnim 本地实现) 职责.
import * as THREE from 'three';
import { TileFactory } from './tile-factory.ts';
import { world, matTile } from './physics.ts';
import { gameState } from './state/game-state.ts';
import { handState } from './state/hand-state.ts';
import { interactionState } from './state/interaction-state.ts';
import { networkRefs } from './state/network-refs.ts';
import { sceneRefs } from './state/scene-refs.ts';
import { myTotalTiles } from './state.ts';
import {
  MY_SEAT,
  MSG,
  STAND_TILE_Y,
  HALF_W,
  HALF_H,
  HALF_D,
  CFG,
  EMISSIVE,
  handTrack,
  alongToWorld,
  discardCell,
} from './constants.ts';
import { tossDiscard, flyToGrid, flyFromGridToWall, _X_AXIS } from './animation.ts';
import { toast, hideClaimBar, updateDiscardBtn } from './ui.ts';
import { emit, EV } from './events.ts';
import { send as wsSend } from './network.ts';
import { makeTileBody, yawQuat } from './geo.ts';
import { generateWallPositions, generateWallBackPositions, generateQuadrantGridPositions } from './wall-positions.ts';

// re-export 拆分后的函数, 保持外部调用方兼容
export { generateWallPositions, generateWallBackPositions, generateQuadrantGridPositions };

// ============ 牌实例创建 (P1-D: 用 makeTileBody 工厂, 35行 → 4行) ============
const _TILE_DEPS = { HALF_W, HALF_H, HALF_D, matTile, world };

function createStandTile(type: any, value: any, id: any) {
  return makeTileBody(TileFactory.create(type, value) as any, { id, type, value } as any, _TILE_DEPS as any);
}

function createStandTileBack(id: any) {
  return makeTileBody(TileFactory.createBack(), { id, isOpponent: true }, _TILE_DEPS);
}

// 别人手牌: 按座位分组重排
function relayoutOpp(seat: any) {
  const arr = handState.oppHands[seat];
  if (!arr) return;
  const tr = handTrack(seat);
  const sp = CFG.tile.w + CFG.spacing.handGap;
  // 用 yawQuat 替代 new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), tr.rotY)
  const q = yawQuat(tr.rotY);
  for (let i = 0; i < arr.length; i++) {
    const along = (i - (arr.length - 1) / 2) * sp;
    const { x, z } = alongToWorld(seat as number, along as number);
    const o = arr[i];
    o.body.position.set(x as number, STAND_TILE_Y, z as number);
    o.body.quaternion.set(q.x, q.y, q.z, q.w);
    interactionState.dirtyBodies.set(o.body, o.mesh);
  }
}

// ============ 弃牌高亮 ============
function ensureArrow() {
  if (interactionState.discardArrow) return interactionState.discardArrow;
  const s = 64,
    c = document.createElement('canvas');
  c.width = s;
  c.height = s;
  const x: any = c.getContext('2d');
  x.fillStyle = '#ffffff';
  x.strokeStyle = 'rgba(60,60,60,.6)';
  x.lineWidth = 3;
  x.lineJoin = 'round';
  x.beginPath();
  x.moveTo(32, 54);
  x.lineTo(12, 24);
  x.lineTo(24, 24);
  x.lineTo(24, 10);
  x.lineTo(40, 10);
  x.lineTo(40, 24);
  x.lineTo(52, 24);
  x.closePath();
  x.fill();
  x.stroke();
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  sp.scale.set(0.32, 0.32, 0.32);
  sp.renderOrder = 999;
  sp.visible = false;
  sceneRefs.scene!.add(sp);
  interactionState.discardArrow = sp;
  return sp;
}

function setEmissive(mesh: any, color: any) {
  if (!mesh.material) return;
  const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  const face = mats[4] || mats[0];
  if (face && face.emissive) face.emissive.setHex(color);
}

function highlightLastDiscard() {
  gameState.lastDiscardObj = null;
  for (const d of handState.discardTiles) {
    const on = d.id === gameState.lastDiscardId;
    setEmissive(d.obj.mesh, on ? EMISSIVE.HIGHLIGHT : EMISSIVE.OFF);
    if (on) gameState.lastDiscardObj = d.obj;
  }
  const a = ensureArrow();
  a.visible = false;
  const tok = ++interactionState.arrowToken;
  if (gameState.lastDiscardObj) {
    setTimeout(() => {
      if (tok === interactionState.arrowToken && gameState.lastDiscardObj) a.visible = true;
    }, 480);
  }
}

// ============ 出牌 (抛牌动画 + 发送 DISCARD) ============
function finalizeThrow(obj: any) {
  if (gameState.currentTurn !== MY_SEAT) {
    toast('不是你的回合', 1200);
    return;
  }
  if (myTotalTiles() < 14) {
    toast('请先摸牌', 1500);
    return;
  }
  const idx = handState.myHand.indexOf(obj);
  if (idx < 0) return;
  const count = handState.discardTiles.filter((d: any) => d.bySeat === MY_SEAT).length;
  const placed = discardCell(MY_SEAT, count);
  const rotY = handTrack(MY_SEAT).rotY;
  handState.myHand.splice(idx, 1);
  // 通知 interaction 重算 slot 与重排
  emit(EV.HAND_CHANGED);
  handState.discardTiles.push({ id: obj.id, obj, bySeat: MY_SEAT });
  gameState.lastDiscardId = obj.id;
  gameState.lastDiscardBy = MY_SEAT;
  if (obj.mesh.parent !== sceneRefs.seatPivot) sceneRefs.seatPivot!.add(obj.mesh);
  tossDiscard(obj, placed.x, placed.z, rotY);
  wsSend({ type: MSG.DISCARD, tileId: obj.id, x: placed.x, z: placed.z, rotY });
  highlightLastDiscard();
  // 通知 interaction 清除选中
  emit(EV.DISCARD_DONE);
  updateDiscardBtn();
}

// ============ 取牌对象 (用于副露渲染) ============
function obtainTileObj(seat: any, tv: any, isBack: any) {
  if (seat === MY_SEAT && !isBack) {
    // 关键: 用 id 匹配 (不是 type/value), 保证 splice 的牌与服务端 takeFromHand 取的是同一张
    // 否则手里有多张同牌时, 客户端 splice 的 id 可能与服务端不一致,
    // 导致后续打出剩余牌时服务端报"你没有这张牌"
    let i = -1;
    if (tv.id != null) {
      i = handState.myHand.findIndex((o: any) => o.id === tv.id);
    }
    // 原 fallback 到 type/value 匹配会掩盖客户端与服务端状态不同步的 bug
    // 现在 fallback 触发时, 上报错误日志 (便于排查), 但仍尝试 fallback 让游戏不卡死
    if (i < 0) {
      console.error('[sync] obtainTileObj: id 匹配失败, 客户端与服务端状态可能不同步', {
        tileId: tv.id,
        tileType: tv.type,
        tileValue: tv.value,
        myHandIds: handState.myHand.map((o: any) => o.id),
      });
      i = handState.myHand.findIndex((o: any) => o.type === tv.type && o.value === tv.value);
    }
    if (i >= 0) {
      const o = handState.myHand.splice(i, 1)[0];
      // 手牌变化, 通知 interaction
      emit(EV.HAND_CHANGED);
      return o;
    }
  }
  if (seat !== MY_SEAT) {
    if (handState.oppHands[seat].length) {
      const b = handState.oppHands[seat].pop();
      sceneRefs.seatPivot!.remove(b!.mesh);
      if (b!.body) world.removeBody(b!.body);
    }
  }
  const id = tv.id ?? ++handState.myIdCounter;
  const o = isBack ? createStandTileBack(id) : createStandTile(tv.type, tv.value, id);
  sceneRefs.seatPivot!.add(o.mesh);
  const tr = handTrack(seat);
  if (tr.axis === 'z') {
    o.body.position.set(0, STAND_TILE_Y, tr.constZ);
  } else {
    o.body.position.set(tr.constX, STAND_TILE_Y, 0);
  }
  // 关键: 立即同步 mesh 到 body 位置
  o.mesh.position.copy(o.body.position);
  o.mesh.quaternion.copy(o.body.quaternion);
  return o;
}

// animate=true 时播放飞到天上矩阵→飞回牌墙的两阶段动画 (仅用于胡牌后重开)
// animate=false 时直接清理 (首次进入/重连)
// 重整动画与发牌动画衔接 bug 修复
//   原问题: 重整动画用 setTimeout 链调度, finalize 在动画末尾才执行;
//           如果发牌消息在 finalize 之前到达, forceCompleteResetAnim 只清空 boardAnimEndTime,
//           不真正执行 finalize, 导致 wallTiles 仍是旧数组/空数组, 发牌从错误位置飞出(虚空发牌)
//   修复: (1) 把 everything/wallPositions/timers 存到模块级 _resetAnimState,
//         forceCompleteResetAnim 真正执行 finalize(立即把所有 mesh 吸附到 wallPositions);
//         (2) wallPositions 始终用 136 张标准布局, 不根据 N 截断(避免牌墙缺牌);
//         (3) 多余的手牌/弃牌/副露 mesh 在 finalize 时 kill 释放, 不混入新牌墙
let _resetAnimState: any = null; // { everything, wallPositions, timers, finalized, onComplete }

// 就近原则匹配 — 贪心算法为每张牌找最近的牌墙位置
// 返回 assignments: [{ obj, wallPos, gridPos, dist }]
function _assignNearestPositions(everything: any, gridPositions: any, wallPositions: any) {
  const N = everything.length;
  const assignments = new Array(N);
  // 收集每张牌的当前位置
  const currentPositions = everything.map((obj: any) => {
    if (!obj || !obj.mesh) return { x: 0, y: 0, z: 0 };
    return { x: obj.mesh.position.x, y: obj.mesh.position.y, z: obj.mesh.position.z };
  });

  // 阶段1就近: 每张牌飞到最近的 gridPosition
  // gridPositions 已按方位分组(generateQuadrantGridPositions), 这里进一步细化:
  // 对每张牌, 找离它最近的 gridPosition
  const usedGrid = new Set();
  for (let i = 0; i < N; i++) {
    const cp = currentPositions[i];
    let bestGrid = -1,
      bestGridDist = Infinity;
    for (let j = 0; j < gridPositions.length; j++) {
      if (usedGrid.has(j)) continue;
      const gp = gridPositions[j];
      const dx = cp.x - gp.x,
        dz = cp.z - gp.z;
      const d = dx * dx + dz * dz;
      if (d < bestGridDist) {
        bestGridDist = d;
        bestGrid = j;
      }
    }
    if (bestGrid >= 0) {
      usedGrid.add(bestGrid);
      assignments[i] = {
        obj: everything[i],
        gridPos: gridPositions[bestGrid],
        gridIdx: bestGrid,
        wallPos: null,
        currentPos: cp,
      };
    }
  }

  // 阶段2就近: 每张牌(此时在天上矩阵)飞到最近的 wallPosition
  // 用贪心匹配: 把所有 (牌当前位置, wallPosition) 距离排序, 从小到大依次匹配
  const usedWall = new Set();
  const pairs: any[] = [];
  for (let i = 0; i < N; i++) {
    if (!assignments[i]) continue;
    const gp = assignments[i].gridPos;
    for (let j = 0; j < wallPositions.length; j++) {
      const wp = wallPositions[j];
      const dx = gp.x - wp.x,
        dz = gp.z - wp.z;
      pairs.push({ assignIdx: i, wallIdx: j, dist: dx * dx + dz * dz });
    }
  }
  pairs.sort((a: any, b: any) => a.dist - b!.dist);
  for (const p of pairs) {
    if (assignments[p.assignIdx].wallPos) continue;
    if (usedWall.has(p.wallIdx)) continue;
    usedWall.add(p.wallIdx);
    assignments[p.assignIdx].wallPos = wallPositions[p.wallIdx];
    assignments[p.assignIdx].wallIdx = p.wallIdx;
  }

  return assignments;
}

function resetBoard(animate = false, onComplete: any) {
  if (!animate) {
    doResetBoard();
    if (typeof onComplete === 'function') onComplete();
    return;
  }

  // 收集所有牌 (手牌 + 弃牌 + 副露) — 这些是"桌面上的牌", 重整后要回到牌墙
  const allTiles: any[] = [];
  for (const o of handState.myHand) allTiles.push(o);
  for (const s of [0, 1, 2, 3]) for (const o of handState.oppHands[s]) allTiles.push(o);
  for (const d of handState.discardTiles) allTiles.push(d.obj);
  for (const s of [0, 1, 2, 3]) for (const g of handState.meldGroups[s]) for (const o of g.objs) allTiles.push(o);

  // 牌墙也飞(剩余未取的牌墙 mesh)
  const wallMeshes: any[] = [];
  if (sceneRefs.wallGroup) {
    for (const child of sceneRefs.wallGroup!.children) {
      if (child.userData._taken) continue;
      wallMeshes.push(child);
    }
  }

  if (allTiles.length === 0 && wallMeshes.length === 0) {
    doResetBoard();
    if (typeof onComplete === 'function') onComplete();
    return;
  }

  const wallObjs = wallMeshes.map((m: any) => ({ mesh: m }));
  const everything = allTiles.concat(wallObjs);

  // 把牌墙 mesh 从 wallGroup 移到 seatPivot
  gameState._flyingWallMeshes = wallMeshes.slice();
  if (sceneRefs.wallGroup) {
    for (const m of wallMeshes) {
      sceneRefs.wallGroup!.remove(m);
      sceneRefs.seatPivot!.add(m);
    }
    sceneRefs.seatPivot!.remove(sceneRefs.wallGroup);
    (sceneRefs as any).wallGroup = null;
  }

  const FULL_WALL_COUNT = CFG.wall.perSide * CFG.wall.layers * 4; // 136
  const gridPositions = generateQuadrantGridPositions(everything);
  const wallPositions = generateWallPositions(FULL_WALL_COUNT);

  // 就近原则匹配 — 每张牌飞到最近的矩阵位置, 再飞到最近的牌墙位置
  const assignments = _assignNearestPositions(everything, gridPositions, wallPositions);

  // 按距离排序启动顺序 — 离目标近的先飞, 远的后飞(更有规律, 不杂乱)
  // 阶段1: 按到 gridPos 的距离排序
  const phase1Order = assignments
    .map((a: any, i: any) => ({
      idx: i,
      dist: a ? (a.currentPos.x - a.gridPos.x) ** 2 + (a.currentPos.z - a.gridPos.z) ** 2 : Infinity,
    }))
    .filter((x: any) => x.dist < Infinity)
    .sort((a: any, b: any) => a.dist - b!.dist)
    .map((x: any) => x.idx);

  // 阶段2: 按到 wallPos 的距离排序(从天上矩阵到牌墙, 近的先落)
  const phase2Order = assignments
    .map((a: any, i: any) => ({
      idx: i,
      dist: a && a.wallPos ? (a.gridPos.x - a.wallPos.x) ** 2 + (a.gridPos.z - a.wallPos.z) ** 2 : Infinity,
    }))
    .filter((x: any) => x.dist < Infinity)
    .sort((a: any, b: any) => a.dist - b!.dist)
    .map((x: any) => x.idx);

  // 记录动画状态, 供 forceCompleteResetAnim 使用
  const timers: any[] = [];
  // finalize 用 assignments 的 wallPos 信息组装牌墙(无缝衔接)
  _resetAnimState = { everything, wallPositions, assignments, timers, finalized: false, onComplete };

  // 优化动画参数 — 更快更流畅
  const PHASE1_STEP = 8; // 每张牌启动间隔 8ms(原 12ms, 加快 33%)
  const PHASE1_FLY = 500; // 飞行时长 500ms(原 600ms, 加快 17%)
  const PHASE2_STEP = 6; // 阶段2启动间隔 6ms(原 10ms, 加快 40%)
  const PHASE2_FLY = 400; // 阶段2飞行时长 400ms(原 500ms, 加快 20%)

  // === 阶段1: 所有牌按就近顺序飞到天上矩阵 ===
  for (let k = 0; k < phase1Order.length; k++) {
    const idx = phase1Order[k];
    const assign = assignments[idx];
    if (!assign || !assign.gridPos) continue;
    timers.push(
      setTimeout(() => {
        if (_resetAnimState && !_resetAnimState.finalized) {
          flyToGrid(assign.obj, assign.gridPos);
        }
      }, k * PHASE1_STEP)
    );
  }

  const phase1Time = phase1Order.length * PHASE1_STEP + PHASE1_FLY;
  timers.push(
    setTimeout(() => {
      if (!_resetAnimState || _resetAnimState.finalized) return;
      // === 阶段2: 所有牌按就近顺序从矩阵飞到牌墙位置 ===
      for (let k = 0; k < phase2Order.length; k++) {
        const idx = phase2Order[k];
        const assign = assignments[idx];
        if (!assign || !assign.wallPos) continue;
        timers.push(
          setTimeout(() => {
            if (_resetAnimState && !_resetAnimState.finalized) {
              flyFromGridToWall(assign.obj, assign.wallPos);
            }
          }, k * PHASE2_STEP)
        );
      }
      const phase2Time = phase2Order.length * PHASE2_STEP + PHASE2_FLY;
      timers.push(
        setTimeout(() => {
          if (_resetAnimState && !_resetAnimState.finalized) {
            _finalizeResetAnim();
          }
        }, phase2Time)
      );
    }, phase1Time)
  );

  const totalTime = phase1Time + phase2Order.length * PHASE2_STEP + PHASE2_FLY + 100;
  gameState.boardAnimEndTime = Date.now() + totalTime;
}

// finalize 逻辑 — 用 assignments 的 wallPos 信息组装牌墙(无缝衔接)
// 飞回动画完成后, mesh 已在 wallPos 位置, finalize 直接把它们收编为新 wallGroup
// 不 kill 不替换, 实现真正的无缝过渡(无闪烁)
function _finalizeResetAnim() {
  if (!_resetAnimState) return;
  const { wallPositions, assignments, onComplete } = _resetAnimState;
  _resetAnimState.finalized = true;

  // 取消所有未触发的 timers
  for (const t of _resetAnimState.timers) clearTimeout(t);
  _resetAnimState.timers = [];

  // 取消所有进行中的飞牌动画
  for (const a of interactionState.animations) a.dead = true;
  interactionState.animations.length = 0;

  const FULL_WALL_COUNT = CFG.wall.perSide * CFG.wall.layers * 4; // 136

  // 检查是否有足够的 assignment(至少 136 个)用于组装完整牌墙
  const validAssignments = assignments.filter((a: any) => a && a.wallPos && a.obj && a.obj.mesh);
  if (validAssignments.length >= FULL_WALL_COUNT) {
    // 正常情况: 用 assignment mesh 组装新牌墙(无缝过渡)
    // mesh 已在 wallPos 位置(飞回动画完成), 直接收编
    const newWallGroup = new THREE.Group();
    sceneRefs.seatPivot!.add(newWallGroup);
    const orderedMeshes = new Array(FULL_WALL_COUNT).fill(null);
    for (const assign of validAssignments) {
      if (assign.wallIdx >= FULL_WALL_COUNT) continue;
      const obj = assign.obj;
      const target = assign.wallPos;
      if (obj.body) {
        world.removeBody(obj.body);
        obj.body = null;
      }
      if (obj.mesh.parent) obj.mesh.parent.remove(obj.mesh);
      // 确保精确位置(动画可能未完全到位)
      obj.mesh.position.set(target.x, target.y, target.z);
      const flat = new THREE.Quaternion().setFromAxisAngle(_X_AXIS, Math.PI / 2);
      const yaw = yawQuat(target.rotY || 0);
      obj.mesh.quaternion.copy(yaw).multiply(flat);
      newWallGroup.add(obj.mesh);
      if (obj.mesh.userData) obj.mesh.userData._taken = false;
      orderedMeshes[assign.wallIdx] = obj.mesh;
    }

    // 清理 handState/discardTiles/meldGroups(mesh 已移入 newWallGroup, 不再 kill)
    handState.myHand.length = 0;
    for (const s of [0, 1, 2, 3]) handState.oppHands[s].length = 0;
    handState.discardTiles.length = 0;
    for (const s of [0, 1, 2, 3]) handState.meldGroups[s] = [];
    gameState._flyingWallMeshes = null;

    // 设置 sceneRefs — wallTiles 按 wallIdx 排序(与 generateWallPositions 顺序一致)
    sceneRefs.wallGroup! = newWallGroup;
    sceneRefs.wallTiles = orderedMeshes.filter((m: any) => m !== null);
    // wallBack: 用 generateWallBackPositions 顺序, 通过坐标→mesh 映射查找
    const posKey = (x: any, y: any, z: any) =>
      `${Math.round(x * 1000)}|${Math.round(y * 1000)}|${Math.round(z * 1000)}`;
    const meshByPos = new Map();
    for (let i = 0; i < wallPositions.length; i++) {
      if (orderedMeshes[i]) {
        const t = wallPositions[i];
        meshByPos.set(posKey(t.x, t.y, t.z), orderedMeshes[i]);
      }
    }
    const wallBackPositions = generateWallBackPositions(wallPositions.length);
    sceneRefs.wallBack = [];
    for (const p of wallBackPositions) {
      const m = meshByPos.get(posKey(p.x, p.y, p.z));
      if (m) sceneRefs.wallBack.push(m);
    }
    sceneRefs.wallCursor = 0;
    sceneRefs.wallBackCursor = 0;
    gameState.gameEnded = false;
    if (networkRefs.ui.winOverlay) networkRefs.ui.winOverlay.classList.remove('show');
  } else {
    // 异常情况: assignment 不足 136, fallback 到 doResetBoard + buildWalls
    doResetBoard();
    emit(EV.BOARD_RESET);
    gameState._flyingWallMeshes = null;
    gameState.gameEnded = false;
    if (networkRefs.ui.winOverlay) networkRefs.ui.winOverlay.classList.remove('show');
  }

  // 清理状态
  gameState.lastDiscardId = null;
  gameState.lastDiscardObj = null;
  if (interactionState.discardArrow) interactionState.discardArrow.visible = false;

  gameState.boardAnimEndTime = 0;
  _resetAnimState = null;
  if (typeof onComplete === 'function') onComplete();
}

// 强制同步完成重整动画 — 真正执行 finalize, 而非只清空 boardAnimEndTime
// 这修复了"发牌在 finalize 之前到达导致虚空发牌"的 bug
function forceCompleteResetAnim() {
  if (_resetAnimState && !_resetAnimState.finalized) {
    _finalizeResetAnim();
  } else {
    // 无动画在进行, 仅清空 boardAnimEndTime(原行为)
    gameState.boardAnimEndTime = 0;
  }
}

// generateWallPositions / generateWallBackPositions 已迁到 wall-positions.ts
// (board.ts 顶部 import, 不再在此定义)

// 实际清理牌桌 (原 resetBoard 逻辑)
// + 内存泄漏 — kill 时补充 material.dispose() + cloned faceTex.dispose()
// 共享资源 (geometry/sideMat/backMat/atlas 纹理) 守护不释放
function doResetBoard() {
  const kill = (o: any) => {
    if (!o) return;
    if (o.mesh) {
      sceneRefs.seatPivot!.remove(o.mesh);
      // 释放每张牌独立持有的 faceMat (TileFactory.create 内 new MeshStandardMaterial)
      // 共享的 geometry / sideMat / backMat (TileFactory.geo/sideMat/backMat) 不能 dispose, 否则其他牌会失效
      if (Array.isArray(o.mesh.material)) {
        for (const m of o.mesh.material) {
          if (m !== TileFactory.sideMat && m !== TileFactory.backMat && typeof m.dispose === 'function') {
            // faceMat.map 是 atlas 纹理的 clone, 需单独 dispose(底层图像共享, 不释放)
            if (
              (m as any).map &&
              (m as any).map !== (TileFactory.sideMat as any).map &&
              (m as any).map !== (TileFactory.backMat as any).map &&
              typeof (m as any).map.dispose === 'function'
            ) {
              (m as any).map.dispose();
            }
            m.dispose();
          }
        }
      } else if (
        o.mesh.material &&
        o.mesh.material !== TileFactory.sideMat &&
        o.mesh.material !== TileFactory.backMat &&
        typeof o.mesh.material.dispose === 'function'
      ) {
        // 同上, 释放 cloned faceTex
        if (
          (o.mesh.material as any).map &&
          (o.mesh.material as any).map !== (TileFactory.sideMat as any).map &&
          (o.mesh.material as any).map !== (TileFactory.backMat as any).map &&
          typeof (o.mesh.material as any).map.dispose === 'function'
        ) {
          (o.mesh.material as any).map.dispose();
        }
        o.mesh.material.dispose();
      }
      // geometry 共享于 TileFactory.geo, 不在此 dispose (TileFactory 自身管理生命周期)
    }
    if (o.body) world.removeBody(o.body);
  };
  for (const o of handState.myHand) kill(o);
  handState.myHand.length = 0;
  for (const s of [0, 1, 2, 3]) {
    for (const o of handState.oppHands[s]) kill(o);
    handState.oppHands[s].length = 0;
  }
  for (const d of handState.discardTiles) kill(d.obj);
  handState.discardTiles.length = 0;
  for (const s of [0, 1, 2, 3]) {
    for (const g of handState.meldGroups[s]) for (const o of g.objs) kill(o);
    handState.meldGroups[s] = [];
  }
  // 不 kill 会导致孤儿 mesh 残留, 新建墙叠在老墙上, 视觉上"牌墙不同步"
  if (gameState._flyingWallMeshes) {
    for (const m of gameState._flyingWallMeshes) {
      if (m && m.parent) m.parent.remove(m);
      // 释放每张飞行墙 mesh 的 material 数组 [sideMat×4, faceMat, backMat]
      // 共享的 sideMat/backMat (TileFactory.sideMat/backMat) 不能 dispose, 仅 dispose cloned faceMat
      if (m.material) {
        const mats = Array.isArray(m.material) ? m.material : [m.material];
        for (const mat of mats) {
          if (mat === TileFactory.sideMat || mat === TileFactory.backMat) continue;
          if (
            (mat as any).map &&
            (mat as any).map !== (TileFactory.sideMat as any).map &&
            (mat as any).map !== (TileFactory.backMat as any).map &&
            typeof (mat as any).map.dispose === 'function'
          ) {
            (mat as any).map.dispose();
          }
          if (typeof mat.dispose === 'function') mat.dispose();
        }
      }
    }
    gameState._flyingWallMeshes = null;
  }
  if (interactionState.discardArrow) interactionState.discardArrow.visible = false;
  gameState.lastDiscardId = null;
  gameState.lastDiscardObj = null;

  // 牌墙处理: 完整则重置标记复用, 残缺/不存在才重建
  // 这是首次进入/刷新掉帧的核心修复 — 避免 136 张 mesh 的重复创建
  const FULL_WALL_COUNT = CFG.wall.perSide * CFG.wall.layers * 4; // 17 * 2 * 4 = 136
  if (sceneRefs.wallGroup! && sceneRefs.wallGroup!.children.length === FULL_WALL_COUNT) {
    // 牌墙完整 (initScene 建的, 首次进入/刷新场景): 只重置 _taken 标记, 复用 mesh
    for (const child of sceneRefs.wallGroup!.children) {
      if (child.userData) child.userData._taken = false;
    }
    sceneRefs.wallCursor = 0;
    sceneRefs.wallBackCursor = 0;
    // wallTiles / wallBack 数组里的 mesh 引用仍然有效, 只需重置游标
    for (const m of sceneRefs.wallTiles as any[]) if (m.userData) m.userData._taken = false;
    for (const m of sceneRefs.wallBack as any[]) if (m.userData) m.userData._taken = false;
  } else {
    // 牌墙残缺 (重连时消耗过) 或不存在 (再来一局 animate 阶段清理了): 重建
    if (sceneRefs.wallGroup) {
      sceneRefs.seatPivot!.remove(sceneRefs.wallGroup);
      // 重建前释放旧牌墙 mesh 的 material 数组 [sideMat×4, faceMat, backMat]
      // 共享的 sideMat/backMat/geometry 不释放
      for (const child of sceneRefs.wallGroup!.children) {
        if (!(child as any).material) continue;
        const mats = Array.isArray((child as any).material) ? (child as any).material : [(child as any).material];
        for (const mat of mats) {
          if (mat === TileFactory.sideMat || mat === TileFactory.backMat) continue;
          if (
            (mat as any).map &&
            (mat as any).map !== (TileFactory.sideMat as any).map &&
            (mat as any).map !== (TileFactory.backMat as any).map &&
            typeof (mat as any).map.dispose === 'function'
          ) {
            (mat as any).map.dispose();
          }
          if (typeof mat.dispose === 'function') mat.dispose();
        }
      }
    }
    sceneRefs.wallTiles.length = 0;
    sceneRefs.wallBack.length = 0;
    emit(EV.BOARD_RESET);
  }

  gameState.gameEnded = false;
  if (networkRefs.ui.winOverlay) networkRefs.ui.winOverlay.classList.remove('show');
  hideClaimBar();
}

export {
  createStandTile,
  createStandTileBack,
  relayoutOpp,
  ensureArrow,
  setEmissive,
  highlightLastDiscard,
  finalizeThrow,
  obtainTileObj,
  resetBoard,
  forceCompleteResetAnim,
};
