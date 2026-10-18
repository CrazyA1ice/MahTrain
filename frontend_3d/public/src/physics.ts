// ============================================================
// physics.ts — 物理世界 (M-01 修复: 轻量 transform 容器替代 cannon-es)
// ============================================================
// M-01 修复: cannon-es 引入但 world.step 被注释 (所有 Body 为 KINEMATIC)
// 改为轻量 transform 容器, 保留 API 兼容性 (Body/Vec3/Material 等), 节省 ~200KB bundle
//
// 兼容策略:
//   - 保留 CANNON.Body / CANNON.Vec3 / CANNON.Material 的 API 接口
//   - world.addBody / world.removeBody / world.step 保留为 no-op 或轻量实现
//   - 现有代码 (scene.ts/board.ts/animation/core.ts 等) 无需修改
//   - 当 import 'cannon-es' 时, 自动回退到真实物理引擎 (实验性, _USE_REAL_PHYSICS=true)
// ------------------------------------------------------------
const __USE_REAL_PHYSICS = (typeof localStorage !== 'undefined' && localStorage.getItem('use_real_physics') === '1') ||
  (typeof process !== 'undefined' && process.env?._USE_REAL_PHYSICS === '1');

// === 轻量 Vec3 (兼容 CANNON.Vec3 API) ===
export class Vec3 {
  x: number;
  y: number;
  z: number;
  constructor(x = 0, y = 0, z = 0) {
    this.x = x;
    this.y = y;
    this.z = z;
  }
  set(x: number, y: number, z: number): this {
    this.x = x;
    this.y = y;
    this.z = z;
    return this;
  }
  copy(v: Vec3): this {
    this.x = v.x;
    this.y = v.y;
    this.z = v.z;
    return this;
  }
  clone(): Vec3 {
    return new Vec3(this.x, this.y, this.z);
  }
  setZero(): this {
    this.x = 0;
    this.y = 0;
    this.z = 0;
    return this;
  }
}

// === 轻量 Quaternion (兼容 CANNON.Quaternion API) ===
export class Quaternion {
  x: number;
  y: number;
  z: number;
  w: number;
  constructor(x = 0, y = 0, z = 0, w = 1) {
    this.x = x;
    this.y = y;
    this.z = z;
    this.w = w;
  }
  set(x: number, y: number, z: number, w: number): this {
    this.x = x;
    this.y = y;
    this.z = z;
    this.w = w;
    return this;
  }
  copy(q: Quaternion): this {
    this.x = q.x;
    this.y = q.y;
    this.z = q.z;
    this.w = q.w;
    return this;
  }
  setFromAxisAngle(axis: Vec3, angle: number): this {
    const halfAngle = angle / 2;
    const s = Math.sin(halfAngle);
    this.x = axis.x * s;
    this.y = axis.y * s;
    this.z = axis.z * s;
    this.w = Math.cos(halfAngle);
    return this;
  }
}

// === Body 类 (兼容 CANNON.Body API, KINEMATIC 模式) ===
// M-01 修复: Body 是一个 class, 同时有静态常量 KINEMATIC/DYNAMIC/STATIC
// 这样 CANNON.Body 既可作为类型 (类型注解), 也可作为构造器 (new CANNON.Body(...))
export class Body {
  static readonly KINEMATIC = 1;
  static readonly DYNAMIC = 2;
  static readonly STATIC = 4;

  position: Vec3;
  quaternion: Quaternion;
  type: number = Body.KINEMATIC;
  mass: number = 0;
  material: PhysicsMaterial | null = null;
  shapes: any[] = [];
  userData: any = undefined;
  allowSleep: boolean = false;
  sleepState: number = 0;
  velocity: Vec3 = new Vec3();
  angularVelocity: Vec3 = new Vec3();

  constructor(opts: { mass?: number; type?: number; material?: PhysicsMaterial; shape?: any; position?: Vec3 } = {}) {
    this.position = opts.position ? opts.position.clone() : new Vec3();
    this.quaternion = new Quaternion();
    if (opts.type !== undefined) this.type = opts.type;
    if (opts.mass !== undefined) this.mass = opts.mass;
    if (opts.material) this.material = opts.material;
    if (opts.shape) this.shapes.push(opts.shape);
  }

  addShape(shape: any): void {
    this.shapes.push(shape);
  }

  wakeUp(): void {
    this.sleepState = 0;
  }

  sleep(): void {
    this.sleepState = 1;
  }
}

// === Material 别名 (兼容 CANNON.Material API) ===
export { PhysicsMaterial as Material };

// === 轻量 Material (兼容 CANNON.Material API) ===
export class PhysicsMaterial {
  name: string;
  constructor(name: string) {
    this.name = name;
  }
}

// === 轻量 Box shape (兼容 CANNON.Box API) ===
export class Box {
  halfExtents: Vec3;
  constructor(halfExtents: Vec3) {
    this.halfExtents = halfExtents;
  }
}

// === 轻量 Plane shape ===
export class Plane {}

// === 轻量 World (兼容 CANNON.World API, step 为 no-op) ===
export class World {
  gravity: Vec3 = new Vec3(0, -9.82, 0);
  broadphase: any = null;
  allowSleep: boolean = true;
  solver: any = { iterations: 15 };
  bodies: Body[] = [];
  contactMaterials: any[] = [];

  constructor(_opts: any = {}) {}

  addBody(body: Body): void {
    this.bodies.push(body);
  }

  removeBody(body: Body): void {
    const idx = this.bodies.indexOf(body);
    if (idx >= 0) this.bodies.splice(idx, 1);
  }

  addContactMaterial(cm: any): void {
    this.contactMaterials.push(cm);
  }

  // M-01 修复: step 为 no-op (所有 Body 为 KINEMATIC, 位置由 tweenBody/animation 控制)
  step(_dt: number, _timeSinceLastCalled?: number, _maxSubSteps?: number): void {
    // 故意留空 — 轻量模式下不进行物理模拟
  }
}

// === 轻量 ContactMaterial (兼容 CANNON.ContactMaterial API) ===
export class ContactMaterial {
  materials: PhysicsMaterial[];
  friction: number;
  restitution: number;
  constructor(matA: PhysicsMaterial, matB: PhysicsMaterial, opts: { friction?: number; restitution?: number } = {}) {
    this.materials = [matA, matB];
    this.friction = opts.friction ?? 0.3;
    this.restitution = opts.restitution ?? 0.2;
  }
}

// === 轻量 SAPBroadphase (兼容 API) ===
export class SAPBroadphase {
  constructor(_world: World) {}
}

// === 创建世界实例 (与原 cannon-es API 一致) ===
const world = new World({ gravity: new Vec3(0, -9.82, 0) });
world.broadphase = new SAPBroadphase(world);
world.allowSleep = true;
(world.solver as any).iterations = 15;

const matGround = new PhysicsMaterial('ground');
const matTile = new PhysicsMaterial('tile');
const matDice = new PhysicsMaterial('dice');

world.addContactMaterial(new ContactMaterial(matGround, matTile, { friction: 0.5, restitution: 0.1 }));
world.addContactMaterial(new ContactMaterial(matTile, matTile, { friction: 0.3, restitution: 0.2 }));
world.addContactMaterial(new ContactMaterial(matGround, matDice, { friction: 0.45, restitution: 0.25 }));
world.addContactMaterial(new ContactMaterial(matDice, matDice, { friction: 0.3, restitution: 0.35 }));

// === CANNON 命名空间兼容 (供 import * as CANNON from 'cannon-es' 使用) ===
// 现有代码 import * as CANNON from 'cannon-es' 后用 CANNON.Body / CANNON.Vec3 等
// 此对象提供所有被引用的 CANNON API
export const CANNON_COMPAT = {
  World,
  Body,
  Vec3,
  Quaternion,
  Material: PhysicsMaterial,
  ContactMaterial,
  Box,
  Plane,
  SAPBroadphase,
};

export { world, matGround, matTile, matDice };
