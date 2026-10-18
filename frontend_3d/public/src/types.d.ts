// ============================================================
// public/src/types.d.ts — 前端模块公共类型声明
// ============================================================
// 此文件为 public/src/*.ts 浏览器模块提供 TypeScript 类型声明.
// 浏览器模块本身用 // @ts-nocheck 跳过严格类型检查 (历史遗留: 渐进式迁移策略),
// 此 .d.ts 提供 interface/type 定义供 IDE 智能提示使用.
//
// 现状: 客户端 35 个文件仍用 @ts-nocheck, 完整移除需逐文件修复
// 几百处类型错误(主要是 any 参数、隐式 null、THREE/CANNON 类型缺失), 风险较高.
// 当前方案: 保留 @ts-nocheck 但补全 types.d.ts, IDE 仍能提供智能提示.
// 长期目标: 逐文件移除 @ts-nocheck, 让 strict 真正覆盖全项目.
// 详见 CHANGELOG.md "类型保障" 章节.
// ------------------------------------------------------------

// === Three.js / cannon-es 简化引用类型 ===
import type * as THREE from 'three';
import type * as CANNON from './physics.ts';

// === 牌实例 (前端含 mesh/body 引用) ===
export interface TileObject {
  id: number;
  type: string;
  value: number | string;
  mesh: THREE.Mesh;
  body: CANNON.Body;
}

// === 副露组 ===
export interface MeldGroup {
  meldIdx: number;
  slot: number;
  objs: TileObject[];
  kind: 'pong' | 'kong' | 'ckong'; // 续杠 (addKong) 服务端广播时用 kind:'kong' + upgrade:true
}

// === 弃牌项 ===
export interface DiscardTile {
  id: number;
  obj: TileObject;
  bySeat: number;
}

// === 动画项 ===
// 旧字段 (start/duration/from/to/fromQuat/toQuat/onDone/arc/spin) 已不再使用,
// 当前动画系统使用 update 回调驱动, body 用于 cancelAnimsFor 匹配, t0 用于暂停恢复.
export interface Animation {
  body: CANNON.Body;
  mesh?: THREE.Mesh;
  start?: number;
  duration?: number;
  from?: { x: number; y: number; z: number };
  to?: { x: number; y: number; z: number };
  fromQuat?: { x: number; y: number; z: number; w: number };
  toQuat?: { x: number; y: number; z: number; w: number };
  onDone?: () => void;
  arc?: boolean;
  spin?: number;
  // 动画系统扩展字段 (animation/core.ts & dice-anims.ts 用):
  t0?: number; // 启动时间戳, 用于 visibilitychange 暂停恢复
  update?: () => boolean; // 自定义逐帧更新回调 (返回 false 表示动画完成)
  dead?: boolean; // 标记取消 (主循环统一清理)
}

// === 玩家信息 ===
export interface PlayerInfo {
  seat: number;
  name: string;
  dice: number[] | null;
  disconnected: boolean;
}

// === UI 元素引用 ===
export interface UIRefs {
  seatText?: HTMLElement;
  playersBox?: HTMLElement;
  playersEl?: HTMLElement;
  statusText?: HTMLElement;
  loaderText?: HTMLElement;
  loader?: HTMLElement;
  turnText?: HTMLElement;
  discardBtn?: HTMLButtonElement;
  claimBar?: HTMLElement;
  claimInfo?: HTMLElement;
  claimBtns?: HTMLElement;
  claimSub?: HTMLElement;
  claimTimer?: any;
  diceCenter?: HTMLElement;
  diceSub?: HTMLElement;
  rollBtn?: HTMLButtonElement;
  dealCenter?: HTMLElement;
  dealBtn?: HTMLButtonElement;
  sortSuitBtn?: HTMLButtonElement;
  winOverlay?: HTMLElement;
  winTitle?: HTMLElement;
  winInfo?: HTMLElement;
  errorOverlay?: HTMLElement;
  toast?: HTMLElement;
  [key: string]: any; // 允许动态属性访问
}

// === 模块声明 (让 .mjs 模块获得类型) ===

declare module './state/scene-refs.ts' {
  // 已迁移为完整 TypeScript 类型 (state/scene-refs.ts 已移除 @ts-nocheck)
}

declare module './state/hand-state.ts' {
  // 已迁移为完整 TypeScript 类型 (state/hand-state.ts 已移除 @ts-nocheck)
}

declare module './state/game-state.ts' {
  // 已迁移为完整 TypeScript 类型 (state/game-state.ts 已移除 @ts-nocheck)
}

declare module './state/interaction-state.ts' {
  // 已迁移为完整 TypeScript 类型 (state/interaction-state.ts 已移除 @ts-nocheck)
}

declare module './state/network-refs.ts' {
  // 已迁移为完整 TypeScript 类型 (state/network-refs.ts 已移除 @ts-nocheck)
}

declare module './state.ts' {
  // 已迁移为完整 TypeScript 类型 (state.ts 已移除 @ts-nocheck)
}

declare module './events.ts' {
  export function emit(event: string, ...args: any[]): void;
  export function on(event: string, handler: (...args: any[]) => void): void;
}

declare module './physics.ts' {
  // 已迁移为完整 TypeScript 类型 (physics.ts 已移除 @ts-nocheck)
}

declare module './tile-factory.ts' {
  // 已迁移为完整 TypeScript 类型 (tile-factory.ts 已移除 @ts-nocheck)
}

declare module './geo.ts' {
  // 已迁移为完整 TypeScript 类型 (geo.ts 已移除 @ts-nocheck)
  // 保留空 declare 防止其他文件还在 import './geo.ts' 时找不到类型
}

declare module './board.ts' {
  import type { TileObject } from './types';
  export function createStandTile(type: string, value: number | string, id: number): TileObject;
  export function createStandTileBack(id: number): TileObject;
  export function relayoutOpp(seat: number): void;
  export function setEmissive(mesh: THREE.Mesh, color: number): void;
  export function highlightLastDiscard(): void;
  export function obtainTileObj(seat: number, tile: any, isBack: boolean): TileObject;
  export function resetBoard(willAnimate?: boolean, onDone?: () => void): void;
  export function forceCompleteResetAnim(): void;
}

declare module './animation.ts' {
  import type { TileObject, Animation } from './types';
  export function flyTileTo(obj: TileObject, along: number, rotY: number, onDone?: () => void): void;
  export function flyToFlat(obj: TileObject, seat: number, along: number): void;
  export function layFlatTile(obj: TileObject, seat: number, along: number): void;
  export function meldAlong(seat: number, slot: number, col: number, prevKinds: string[]): number;
  export function tossDiscard(obj: TileObject, x: number, z: number, rotY: number): void;
  export function tipOverTile(obj: TileObject, seat: number): void;
  export function tickAnimations(): void;
}

declare module './scene.ts' {
  import type * as THREE from 'three';
  export function initScene(): void;
  export function setCam(seat: number): void;
  export function buildTable(): { feltMat: THREE.MeshStandardMaterial };
  export function buildDice(): void;
  export function buildWalls(): void;
  export function buildLights(): any;
  export function buildEnvironment(): THREE.Group;
  export function showDiceResult(values: number[], onComplete: () => void): void;
  export function popWallTile(): { x: number; y: number; z: number };
  export function popWallTileJumpDeal(): { x: number; y: number; z: number };
  export function popWallTileBack(): { x: number; y: number; z: number };
  export function startJumpDeal(): void;
  export function setWallStart(dealer: number, diceSum: number, diceMin: number): void;
}

declare module './interaction.ts' {
  export function recomputeSlots(): void;
  export function relayoutHand(animated: boolean): void;
  export function setupInteraction(): void;
}

declare module './network.ts' {
  export function connect(): void;
  export function send(obj: any): void;
  export function handlePlayerDisconnected(seat: number): void;
  export function handlePlayerReconnected(seat: number): void;
}

declare module './ui.ts' {
  export function toast(msg: string, duration: number): void;
  export function showError(title: string, body: string): void;
  export function handleServerError(msg: string): void;
  export function renderPlayers(): void;
  export function setPhaseUI(phase: string): void;
  export function updateDiscardBtn(): void;
  export function hideClaimBar(): void;
  export function showClaimBar(btns: any[], info: string, deadline?: number): void;
  export function hideLoader(): void;
}

declare module './handlers/index.ts' {
  export function handleServer(m: any): void;
  export function applyReconnectState(m: any): void;
}

declare module './lobby.ts' {
  // 已迁移为完整 TypeScript 类型 (lobby.ts 已移除 @ts-nocheck)
}

declare module './perf.ts' {
  // 已迁移为完整 TypeScript 类型 (perf.ts 已移除 @ts-nocheck)
}

declare module './main.ts' {
  export function init(): void;
}
