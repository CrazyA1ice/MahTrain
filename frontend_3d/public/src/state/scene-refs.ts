// ============================================================
// state/scene-refs.mjs — Three.js / 场景 + 牌墙 + 骰子引用
// ============================================================
// 由 state.mjs 拆分而来 (P2-2). 持有所有 Three.js / cannon-es 场景对象的引用,
// 以及牌墙与骰子的 mesh/body 集合. 这些字段在 scene.mjs / board.mjs / main.mjs 中读写.
import type * as THREE from 'three';
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type * as CANNON from '../physics.ts';

interface TableRefs {
  feltMat: THREE.MeshStandardMaterial;
}

interface LightsRefs {
  key: THREE.Light;
  fill: THREE.Light;
  rim: THREE.Light;
  spot: THREE.SpotLight;
  amb: THREE.AmbientLight;
}

export interface SceneRefs {
  scene: THREE.Scene | null;
  camera: THREE.PerspectiveCamera | null;
  renderer: THREE.WebGLRenderer | null;
  // L-03 修复: controls 类型从 unknown 改为 OrbitControls (从 three/examples 导入), 移除 as any 链
  controls: OrbitControls | null;
  seatPivot: THREE.Group | null;
  table: TableRefs | null;
  lights: LightsRefs | null;
  diceMeshes: THREE.Mesh[];
  diceBodies: CANNON.Body[];
  wallGroup: THREE.Group | null;
  wallTiles: THREE.Mesh[];
  wallBack: { x: number; z: number; rotY: number }[];
  wallCursor: number;
  wallBackCursor: number;
  _controlsDirty: boolean;
  _controlsIdle: number;
}

export const sceneRefs: SceneRefs = {
  // === Three.js 核心 ===
  scene: null,
  camera: null,
  renderer: null,
  controls: null,  // L-03 修复: 类型从 unknown 改为 THREE.OrbitControls | null
  seatPivot: null,
  table: null, // { feltMat }
  lights: null, // { key, fill, rim, spot, amb }

  // === 骰子 ===
  diceMeshes: [],
  diceBodies: [],

  // === 牌墙 ===
  wallGroup: null,
  wallTiles: [],
  wallBack: [],
  wallCursor: 0,
  wallBackCursor: 0,

  // === 控制器帧计数 (动态添加, 迁入此域以集中管理) ===
  _controlsDirty: false,
  _controlsIdle: 0,
};
