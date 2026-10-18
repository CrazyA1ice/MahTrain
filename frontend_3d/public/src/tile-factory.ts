// ============================================================
// tile-factory.ts — 牌 mesh 工厂 (正面/牌背)
// 使用 Texture Atlas, 34 种牌面共享 1 个 CanvasTexture
// 每张牌的 faceMat 仍是独立 MeshStandardMaterial 实例(因 UV offset 不同),
// 但 map 指向同一个 atlas 纹理, GPU 纹理上传从 34 次降到 1 次
// ============================================================
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { Tex } from './tex.ts';
import { CFG } from './constants.ts';

interface TileFactoryState {
  geo: RoundedBoxGeometry | null;
  sideMat: THREE.MeshStandardMaterial | null;
  backMat: THREE.MeshStandardMaterial | null;
  _atlasMat: THREE.CanvasTexture | null;
  init(): void;
  create(type: string, value: number | string): THREE.Mesh;
  createBack(): THREE.Mesh;
  dispose(): void;
}

const TileFactory: TileFactoryState = {
  geo: null,
  sideMat: null,
  backMat: null,
  _atlasMat: null, // 共享的 atlas 纹理(所有 faceMat 复用)
  init() {
    this.geo = new RoundedBoxGeometry(CFG.tile.w, CFG.tile.h, CFG.tile.d, 4, CFG.tile.radius);
    this.sideMat = new THREE.MeshStandardMaterial({ map: Tex.makeSide(), roughness: 0.35, metalness: 0.05 });
    this.backMat = new THREE.MeshStandardMaterial({ map: Tex.makeBack(), roughness: 0.4, metalness: 0.1 });
    // 预构建 atlas 纹理(懒加载, 首次 getAtlasTexture 时构建)
    this._atlasMat = Tex.getAtlasTexture();
  },
  create(type: string, value: number | string) {
    // faceMat 使用共享 atlas 纹理 + UV offset/repeat 取对应区域
    // 克隆纹理引用但设置独立 offset/repeat
    const atlasTex = this._atlasMat;
    if (!atlasTex) throw new Error('TileFactory.create called before init()');
    const uv = Tex.getFaceUV(type, value);
    // 用 CanvasTexture.clone() 共享底层图像, 但有独立 offset/repeat
    // 注: 不设 needsUpdate=true, clone 共享 source, atlas 首次上传后无需重传
    // 设 needsUpdate=true 会触发 gl.texSubImage2D 重传 14MB 数据(136 张墙牌 = 1.9GB 传输)
    const faceTex = atlasTex.clone();
    faceTex.offset.set(uv.offsetX, uv.offsetY);
    faceTex.repeat.set(uv.repeatX, uv.repeatY);
    faceTex.anisotropy = atlasTex.anisotropy;
    faceTex.colorSpace = atlasTex.colorSpace;
    const faceMat = new THREE.MeshStandardMaterial({ map: faceTex, roughness: 0.35, metalness: 0.05 });
    if (!this.sideMat || !this.backMat || !this.geo) throw new Error('TileFactory.create called before init()');
    const mats = [this.sideMat, this.sideMat, this.sideMat, this.sideMat, faceMat, this.backMat];
    const mesh = new THREE.Mesh(this.geo, mats);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData = { type, value, _faceTex: faceTex };
    return mesh;
  },
  createBack() {
    if (!this.sideMat || !this.backMat || !this.geo) throw new Error('TileFactory.createBack called before init()');
    const mats = [this.sideMat, this.sideMat, this.sideMat, this.sideMat, this.backMat, this.backMat];
    const mesh = new THREE.Mesh(this.geo, mats);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  },
  // 释放共享资源 (geometry + sideMat + backMat + atlas)
  // 在页面卸载或场景完全重建时调用
  dispose() {
    if (this.geo) {
      this.geo.dispose();
      this.geo = null;
    }
    if (this.sideMat) {
      if (this.sideMat.map) this.sideMat.map.dispose();
      this.sideMat.dispose();
      this.sideMat = null;
    }
    if (this.backMat) {
      if (this.backMat.map) this.backMat.map.dispose();
      this.backMat.dispose();
      this.backMat = null;
    }
    // _atlasMat 不在此 dispose(它是 Tex 持有的), 由 Tex.dispose() 统一释放
    this._atlasMat = null;
    // 同时释放 Tex 缓存(含 atlas 纹理)
    Tex.dispose();
  },
};

// 页面卸载时释放共享 GPU 资源, 避免多次刷新后内存残留
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    try {
      TileFactory.dispose();
    } catch {
      /* 忽略卸载时的异常 */
    }
  });
}

export { TileFactory };
