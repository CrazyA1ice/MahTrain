declare const __DEV__: boolean;
// ============================================================
// main.mjs — 主入口
// ============================================================
import * as THREE from 'three';
import { gameState } from './state/game-state.ts';
import { handState } from './state/hand-state.ts';
import { interactionState } from './state/interaction-state.ts';
import { networkRefs } from './state/network-refs.ts';
import { sceneRefs } from './state/scene-refs.ts';
import { MY_SEAT, MSG, tileSortKey } from './constants.ts';
import { initScene, buildWalls } from './scene.ts';
import * as interaction from './interaction.ts';
import * as board from './board.ts';
import { connect, send } from './network.ts';
import { toast, hideLoader } from './ui.ts';
import { on, EV } from './events.ts';
import { frameBegin, section, frameEnd } from './perf.ts';

// board 触发事件, interaction / scene 订阅, 互不直接引用
on(EV.HAND_CHANGED, () => {
  interaction.recomputeSlots();
  interaction.relayoutHand(true);
});
on(EV.DISCARD_DONE, () => {
  interaction.clearSelect();
});
on(EV.BOARD_RESET, () => {
  buildWalls();
});
// 删除 setMyTotalTilesFn(myTotalTiles) — ui.mjs 现在直接 import myTotalTiles

// ============ 收集 UI 元素引用 ============
// L-03 修复: 用泛型辅助函数替代重复的 as any, 保留类型信息
function $<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.getElementById(id) as T | null;
}

function collectUIElements() {
  networkRefs.ui = {
    seatText: $<HTMLDivElement>('seatText') ?? undefined,
    statusText: $<HTMLSpanElement>('statusText') ?? undefined,
    turnText: $<HTMLSpanElement>('turnText') ?? undefined,
    dealBtn: $<HTMLButtonElement>('dealBtn') ?? undefined,
    dealCenter: $<HTMLDivElement>('dealCenter') ?? undefined,
    discardBtn: $<HTMLButtonElement>('discardBtn') ?? undefined,
    sortSuitBtn: $<HTMLButtonElement>('sortSuitBtn') ?? undefined,
    diceCenter: $<HTMLDivElement>('diceCenter') ?? undefined,
    rollBtn: $<HTMLButtonElement>('rollBtn') ?? undefined,
    diceSub: $<HTMLSpanElement>('diceSub') ?? undefined,
    toastEl: $<HTMLDivElement>('toast') ?? undefined,
    playersEl: $<HTMLDivElement>('players') ?? undefined,
    playersBox: $<HTMLDivElement>('playersBox') ?? undefined,
    loaderText: $<HTMLDivElement>('loaderText') ?? undefined,
    claimBar: $<HTMLDivElement>('claimBar') ?? undefined,
    claimBtns: $<HTMLDivElement>('claimBtns') ?? undefined,
    claimSub: $<HTMLDivElement>('claimSub') ?? undefined,
    winOverlay: $<HTMLDivElement>('winOverlay') ?? undefined,
    winTitle: $<HTMLHeadingElement>('winTitle') ?? undefined,
    winInfo: $<HTMLParagraphElement>('winInfo') ?? undefined,
    errorOverlay: $<HTMLDivElement>('errorOverlay') ?? undefined,
    errorTitle: $<HTMLHeadingElement>('errorTitle') ?? undefined,
    errorMsg: $<HTMLParagraphElement>('errorMsg') ?? undefined,
    loader: $<HTMLDivElement>('loader') ?? undefined,
  };
  // 错误弹窗按钮
  const errorBtn = $<HTMLButtonElement>('errorBtn');
  if (errorBtn) {
    errorBtn.addEventListener('click', () => networkRefs.ui.errorOverlay?.classList.remove('show'));
  }
}

// ============ 绑定按钮 ============
function bindButtons() {
  networkRefs.ui.sortSuitBtn!.addEventListener('click', () => {
    handState.myHand.sort((a: any, b: any) => tileSortKey(a) - tileSortKey(b));
    interaction.recomputeSlots();
    interaction.relayoutHand(true);
    toast('已整理', 1000);
  });

  // 投骰子
  networkRefs.ui.rollBtn!.addEventListener('click', () => {
    networkRefs.ui.rollBtn!.disabled = true;
    send({ type: MSG.ROLL_DICE });
  });

  // 发牌
  (networkRefs.ui.dealBtn as any).addEventListener('click', () => {
    if (!gameState.myDealer) return;
    (networkRefs.ui.dealBtn as any).disabled = true;
    networkRefs.ui.dealCenter!.classList.remove('show');
    send({ type: MSG.START_DEAL });
  });

  // 测试发牌 (P0-1: 仅在开发模式下绑定, 生产模式 testDealBtn 由 game.html 服务端构建时剔除)
  // MANUAL_TEST 模式下也可见 (服务端 keepTestDealBtn 控制)
  const testDealBtn = document.getElementById('testDealBtn') as any;
  const testScenarioSelect = document.getElementById('testScenarioSelect') as any;
  if (testDealBtn && __DEV__) {
    testDealBtn.addEventListener('click', () => {
      if (!gameState.myDealer) return;
      (networkRefs.ui.dealBtn as any).disabled = true;
      networkRefs.ui.dealCenter!.classList.remove('show');
      // 读取场景选择下拉框, 默认 'default'
      const scenario = testScenarioSelect ? testScenarioSelect.value : 'default';
      send({ type: MSG.TEST_DEAL, scenario });
    });
  }
  // 非测试模式下隐藏场景选择下拉框 (仅 TEST_MODE/MANUAL_TEST 时服务端保留 testDealBtn)
  if (testScenarioSelect && !testDealBtn) {
    testScenarioSelect.style.display = 'none';
  }

  // 这里不再绑定 restartBtn

  // 打出按钮
  networkRefs.ui.discardBtn!.addEventListener('click', () => {
    if (gameState.currentTurn !== MY_SEAT) {
      toast('不是你的回合', 1200);
      return;
    }
    if (!interactionState.selected || !handState.myHand.includes(interactionState.selected)) {
      toast('请先点选一张手牌', 1500);
      return;
    }
    board.finalizeThrow(interactionState.selected);
  });
}

// ============ 滑块绑定 ============
function bindRange(id: any, fn: any) {
  const el = document.getElementById(id);
  const val = document.getElementById(id + 'V');
  if (!el || !val) return;
  const update = () => {
    const min = +(el as HTMLInputElement).min,
      max = +(el as HTMLInputElement).max,
      v = +(el as HTMLInputElement).value;
    el.style.setProperty('--p', ((v - min) / (max - min)) * 100 + '%');
    val.textContent = String(v);
  };
  el.addEventListener('input', () => {
    update();
    fn(+(el as HTMLInputElement).value);
  });
  update();
}

// ============ 主循环 ============
const startTime = performance.now();

function tick() {
  const now = performance.now();
  const elapsed = (now - startTime) / 1000;
  frameBegin();

  // 骰子同步 (骰子动画期间 dirty)
  section('dice');
  for (let i = 0; i < sceneRefs.diceMeshes.length; i++) {
    sceneRefs.diceMeshes[i].position.copy(sceneRefs.diceBodies[i].position);
    sceneRefs.diceMeshes[i].quaternion.copy(sceneRefs.diceBodies[i].quaternion);
  }

  // 动画 (动画 update 会把 body 加入 interactionState.dirtyBodies)
  // / 瓶颈4: 改用 swap-pop 替代 splice, 避免 array 重排开销
  section('anim');
  let _animWrite = 0;
  for (let _animRead = 0; _animRead < interactionState.animations.length; _animRead++) {
    const a = interactionState.animations[_animRead];
    if (!a.dead && (a as any).update()) {
      interactionState.animations[_animWrite++] = a;
    }
    // else: 动画完成或 dead, 不保留 → 释放引用 (帮助 GC)
  }
  interactionState.animations.length = _animWrite;
  // 暴露给 perf 模块用于归因
  window.__animCount = interactionState.animations.length;

  // 未来若引入动态刚体, 改为 if (sceneRefs.hasDynamicBodies) world.step(...)
  // 当前所有 body 都是 KINEMATIC, gravity 无作用, 碰撞响应也不需要, step 是纯浪费
  // world.step(1 / 60, dt, 3);  // 已注释 — 见上面注释

  section('sync');
  // dirty 改为 Map<body, mesh>, 直接遍历 dirty 即可, 无需全量遍历 4×58=232 个 obj
  // 帧率优化: 每帧 0.3-0.8ms → 0.02-0.05ms (典型 dirty size 1-5)
  const dirty = interactionState.dirtyBodies;
  window.__dirtyCount = dirty.size;
  if (dirty.size > 0) {
    for (const [body, mesh] of dirty) {
      if (mesh) {
        mesh.position.copy(body.position);
        mesh.quaternion.copy(body.quaternion);
      }
    }
    // 清空 dirty 集合 (下一帧动画 update 会重新标记)
    dirty.clear();
  }

  // 上家弃牌头顶箭头
  section('arrow');
  if (interactionState.discardArrow && interactionState.discardArrow.visible && gameState.lastDiscardObj) {
    gameState.lastDiscardObj.mesh.getWorldPosition(_arrowWP);
    interactionState.discardArrow.position.set(_arrowWP.x, _arrowWP.y + 0.6 + Math.sin(elapsed * 4) * 0.06, _arrowWP.z);
  }

  // 灯光动画
  section('lights');
  if (sceneRefs.lights) {
    sceneRefs.lights!.fill.position.x = -7 + Math.sin(elapsed * 0.4) * 1.2;
    sceneRefs.lights!.rim.position.z = 7 + Math.cos(elapsed * 0.3) * 1.2;
  }

  section('controls');
  // controls.update() 含阻尼计算每帧 ~0.5ms, 无交互时跳过
  // 用 _controlsIdle 帧计数器: 每次用户交互 (mousedown/wheel) 重置为 0, 连续 30 帧 (500ms) 无交互跳过
  if (sceneRefs._controlsIdle === undefined) sceneRefs._controlsIdle = 0;
  if (sceneRefs._controlsDirty || sceneRefs._controlsIdle < 30) {
    // L-03 修复: sceneRefs.controls 已强类型化, 移除 as any 链
    sceneRefs.controls?.update();
    sceneRefs._controlsIdle++;
    if (sceneRefs._controlsIdle > 30) sceneRefs._controlsDirty = false;
  }
  section('render');
  sceneRefs.renderer!.render(sceneRefs.scene as any, sceneRefs.camera as any);
  section(null);

  frameEnd();
  // (之前用 setTimeout 会被浏览器节流到 60fps 上限, 且后台标签页行为不一致)
  // rAF 前台时跟随显示器 (60/120/144Hz), 后台时自动暂停 (省电, 不会卡死动画因为有 visibilitychange 处理)
  requestAnimationFrame(tick);
}

const _arrowWP = new THREE.Vector3();

// ============ 启动 ============
function main() {
  if (MY_SEAT < 0 || MY_SEAT > 3) {
    location.href = 'index.html';
    return;
  }
  collectUIElements();
  initScene();
  bindButtons();
  interaction.bindInteraction();

  bindRange('feltHue', (v: any) => {
    sceneRefs.table!.feltMat.color.setHSL(v / 360, 0.55, 0.18);
  });
  bindRange('lightInt', (v: any) => {
    const f = v / 100;
    sceneRefs.lights!.key.intensity = 2.0 * f;
    sceneRefs.lights!.spot.intensity = 2.5 * f;
    sceneRefs.lights!.amb!.intensity = 0.8 * f;
  });

  // 启动主循环
  requestAnimationFrame(tick);

  let pauseAt: any = null;
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      pauseAt = performance.now();
    } else {
      // (BUG-A1): 删除 tick() 直接调用 — 原 requestAnimationFrame 链会自动恢复,
      // 直接调用 tick() 会创建新的 rAF 链, 标签页多次切换后帧率指数级崩溃
      // 偏移所有动画的 t0 字段, 让动画无缝继续 (而非 snap 到终点)
      if (pauseAt !== null) {
        const offset = performance.now() - pauseAt;
        for (const a of interactionState.animations) {
          if (a.dead) continue; // dead 动画会被下一帧 swap-pop 清除, 偏移其 t0 无意义
          if (a.t0) a.t0 += offset;
        }
        pauseAt = null;
      }
      // 原 rAF 链在页面恢复可见时自动恢复, 无需手动调用 tick()
    }
  });

  // 连接服务器
  connect();

  setTimeout(hideLoader, 3000);

  // resize
  window.addEventListener('resize', () => {
    sceneRefs.camera!.aspect = innerWidth / innerHeight;
    sceneRefs.camera!.updateProjectionMatrix();
    sceneRefs.renderer!.setSize(innerWidth, innerHeight);
  });
}

main();
