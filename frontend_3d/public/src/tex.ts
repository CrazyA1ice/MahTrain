// ============================================================
// tex.mjs — 牌面/牌背/骰子面纹理工厂
// ============================================================
// Texture Atlas: 34 种牌面合并到一张大 canvas, 共享 1 个 CanvasTexture
// 每张牌的 faceMat 通过 map.offset/repeat 取 atlas 中对应区域
// GPU 纹理上传从 34 次降到 1 次, 内存省 60%+, 纹理切换开销消除
import * as THREE from 'three';

// Atlas 布局: 4 行 × 9 列 = 36 格 (实际用 34 格, 9万+9筒+9条+7字)
// 每格 256×384, atlas 总尺寸 2304×1536
const ATLAS_COLS = 9;
const ATLAS_ROWS = 4;
const TILE_W = 256;
const TILE_H = 384;
const ATLAS_W = ATLAS_COLS * TILE_W; // 2304
const ATLAS_H = ATLAS_ROWS * TILE_H; // 1536

// 高清牌面素材图集 (由 scripts/bake-tile-atlas.py 从矢量麻将素材烘焙)
// 布局与本文件一致: 行0 萬 / 行1 筒 / 行2 条 / 行3 字牌
// 用 import.meta.url 解析, 兼容 Vite 构建与 server.ts 原样静态服务两种模式
const ATLAS_IMAGE_URL = new URL('../assets/tiles-atlas.png', import.meta.url).href;

// 牌 key → atlas 索引(行 * 9 + 列)
// 行 0: wan 1-9 (索引 0-8)
// 行 1: tong 1-9 (索引 9-17)
// 行 2: tiao 1-9 (索引 18-26)
// 行 3: feng 東南西北中發白 (索引 27-32), 33-35 留空
function tileKeyToAtlasIndex(type: any, value: any) {
  if (type === 'wan') return value - 1; // 0-8
  if (type === 'tong') return 9 + (value - 1); // 9-17
  if (type === 'tiao') return 18 + (value - 1); // 18-26
  if (type === 'feng') {
    const order = ['東', '南', '西', '北', '中', '發', '白'];
    return 27 + order.indexOf(value); // 27-33
  }
  return 0;
}

const Tex: any = {
  _cache: {}, // 旧的单张纹理缓存(向后兼容, 不再使用)
  _atlasTexture: null, // 共享的 atlas CanvasTexture
  _atlasCanvas: null, // atlas 的 canvas(用于 dispose 时释放)

  // 获取共享的 atlas 纹理(懒加载, 首次调用时构建)
  getAtlasTexture() {
    if (this._atlasTexture) return this._atlasTexture;
    const c = document.createElement('canvas');
    c.width = ATLAS_W;
    c.height = ATLAS_H;
    this._atlasCanvas = c;
    const ctx: any = c.getContext('2d');
    // 先程序化绘制 34 张占位牌面(素材图集异步加载完成前显示, 避免首帧空白)
    for (let v = 1; v <= 9; v++) this._drawFaceToAtlas(ctx, 'wan', v);
    for (let v = 1; v <= 9; v++) this._drawFaceToAtlas(ctx, 'tong', v);
    for (let v = 1; v <= 9; v++) this._drawFaceToAtlas(ctx, 'tiao', v);
    for (const ch of ['東', '南', '西', '北', '中', '發', '白']) this._drawFaceToAtlas(ctx, 'feng', ch);
    const tex = new THREE.CanvasTexture(c);
    tex.anisotropy = 8;
    tex.colorSpace = THREE.SRGBColorSpace;
    this._atlasTexture = tex;
    // 异步加载高清素材图集, 完成后覆盖占位并刷新纹理
    // 所有牌面 faceMat 共享同一 atlas source, 只需一次 needsUpdate 即可全部更新
    this._loadAtlasImage(ctx, tex);
    return tex;
  },

  // 异步加载烘焙好的高清牌面图集, 覆盖程序化占位
  _loadAtlasImage(ctx: any, tex: any) {
    if (typeof Image === 'undefined') return; // 非浏览器环境(测试)跳过
    const img = new Image();
    img.onload = () => {
      // atlas 已被 dispose 时不再写入(避免竞态)
      if (this._atlasTexture !== tex) return;
      ctx.clearRect(0, 0, ATLAS_W, ATLAS_H);
      ctx.drawImage(img, 0, 0, ATLAS_W, ATLAS_H);
      tex.needsUpdate = true; // 触发一次 GPU 重传(共享 source, 全部牌面同步更新)
    };
    img.onerror = () => {
      // 素材加载失败时保留程序化占位, 不影响游戏
      console.warn('[tex] 牌面素材图集加载失败, 使用程序化牌面:', ATLAS_IMAGE_URL);
    };
    img.src = ATLAS_IMAGE_URL;
  },

  // 把一张牌面绘制到 atlas 的对应位置
  _drawFaceToAtlas(ctx: any, type: any, value: any) {
    const idx = tileKeyToAtlasIndex(type, value);
    const col = idx % ATLAS_COLS;
    const row = Math.floor(idx / ATLAS_COLS);
    const ox = col * TILE_W;
    const oy = row * TILE_H;
    // 绘制牌面背景 + 内容(与原 _makeFace 一致, 只是偏移到 ox, oy)
    const g = ctx.createLinearGradient(ox, oy, ox, oy + TILE_H);
    g.addColorStop(0, '#fbf3e0');
    g.addColorStop(0.5, '#f4ead8');
    g.addColorStop(1, '#e8dcc0');
    ctx.fillStyle = g;
    ctx.fillRect(ox, oy, TILE_W, TILE_H);
    ctx.strokeStyle = 'rgba(80,60,40,.25)';
    ctx.lineWidth = 4;
    ctx.strokeRect(ox + 10, oy + 10, TILE_W - 20, TILE_H - 20);
    ctx.fillStyle = 'rgba(80,60,40,.08)';
    ctx.fillRect(ox + 20, oy + 18, TILE_W - 40, 6);
    // 子图绘制(传 ox/oy 偏移)
    if (type === 'wan') this._wan(ctx, value, TILE_W, TILE_H, ox, oy);
    else if (type === 'tong') this._tong(ctx, value, TILE_W, TILE_H, ox, oy);
    else if (type === 'tiao') this._tiao(ctx, value, TILE_W, TILE_H, ox, oy);
    else if (type === 'feng') this._feng(ctx, value, TILE_W, TILE_H, ox, oy);
  },

  // 获取牌面对应的 UV offset/repeat (用于 faceMat.map)
  // 返回 { offset: {x, y}, repeat: {x, y} }
  getFaceUV(type: any, value: any) {
    const idx = tileKeyToAtlasIndex(type, value);
    const col = idx % ATLAS_COLS;
    const row = Math.floor(idx / ATLAS_COLS);
    return {
      offsetX: col / ATLAS_COLS,
      offsetY: 1 - (row + 1) / ATLAS_ROWS, // Three.js UV 原点在左下, canvas 原点在左上, 需翻转
      repeatX: 1 / ATLAS_COLS,
      repeatY: 1 / ATLAS_ROWS,
    };
  },

  getFace(type: any, value: any) {
    const key = `${type}-${value}`;
    if (!this._cache[key]) this._cache[key] = this._makeFace(type, value);
    return this._cache[key];
  },
  _makeFace(type: any, value: any) {
    const W = 256,
      H = 384,
      c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    const ctx: any = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#fbf3e0');
    g.addColorStop(0.5, '#f4ead8');
    g.addColorStop(1, '#e8dcc0');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(80,60,40,.25)';
    ctx.lineWidth = 4;
    ctx.strokeRect(10, 10, W - 20, H - 20);
    ctx.fillStyle = 'rgba(80,60,40,.08)';
    ctx.fillRect(20, 18, W - 40, 6);
    if (type === 'wan') this._wan(ctx, value, W, H);
    else if (type === 'tong') this._tong(ctx, value, W, H);
    else if (type === 'tiao') this._tiao(ctx, value, W, H);
    else if (type === 'feng') this._feng(ctx, value, W, H);
    const tex = new THREE.CanvasTexture(c);
    tex.anisotropy = 8;
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  },
  makeBack() {
    const W = 256,
      H = 384,
      c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    const ctx: any = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#1b5e3a');
    g.addColorStop(1, '#0c3a22');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(212,160,76,.4)';
    ctx.lineWidth = 3;
    ctx.strokeRect(18, 18, W - 36, H - 36);
    ctx.lineWidth = 1.5;
    ctx.strokeRect(28, 28, W - 56, H - 56);
    ctx.fillStyle = 'rgba(212,160,76,.85)';
    ctx.font = 'bold 80px "KaiTi",serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('雀', W / 2, H / 2);
    const tex = new THREE.CanvasTexture(c);
    tex.anisotropy = 8;
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  },
  makeSide() {
    const W = 64,
      H = 256,
      c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    const ctx: any = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, W, 0);
    g.addColorStop(0, '#d8c8a8');
    g.addColorStop(0.5, '#f0e4cc');
    g.addColorStop(1, '#d8c8a8');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  },
  makeDiceFace(n: any) {
    const S = 128,
      c = document.createElement('canvas');
    c.width = c.height = S;
    const ctx: any = c.getContext('2d');
    // 象牙色骰身: 铺满整格 (圆角由几何体倒角提供, 不留透明角 → 棱角是白色而非黑色)
    const g = ctx.createRadialGradient(S * 0.4, S * 0.36, 6, S / 2, S / 2, S * 0.85);
    g.addColorStop(0, '#fffefa');
    g.addColorStop(0.7, '#f7f0e2');
    g.addColorStop(1, '#efe6d2');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, S, S);
    const pos = {
      1: [[64, 64]],
      2: [[42, 42], [86, 86]],
      3: [[42, 42], [64, 64], [86, 86]],
      4: [[42, 42], [86, 42], [42, 86], [86, 86]],
      5: [[42, 42], [86, 42], [64, 64], [42, 86], [86, 86]],
      6: [[42, 34], [86, 34], [42, 64], [86, 64], [42, 94], [86, 94]],
    };
    (pos as any)[n].forEach(([x, y]: [number, number]) => {
      const isRed = n === 1 || n === 4;
      const r = n === 1 ? 13 : 10.5;
      // 点子投影
      ctx.beginPath();
      ctx.arc(x, y + 1.5, r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(30,20,10,.18)';
      ctx.fill();
      // 点子本体 (径向渐变模拟凹陷)
      const pg = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, 1, x, y, r);
      if (isRed) {
        pg.addColorStop(0, '#e2564a');
        pg.addColorStop(1, '#9e2318');
      } else {
        pg.addColorStop(0, '#3c3c3c');
        pg.addColorStop(1, '#0d0d0d');
      }
      ctx.fillStyle = pg;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
      // 高光点
      ctx.beginPath();
      ctx.arc(x - r * 0.32, y - r * 0.36, r * 0.28, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,.5)';
      ctx.fill();
    });
    const tex = new THREE.CanvasTexture(c);
    tex.anisotropy = 8;
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  },

  // ===== 场景/桌子 程序化纹理 (木纹/绒布/地板/背景) =====
  // 温暖胡桃木纹 (桌框/桌腿)
  makeWood() {
    const W = 512,
      H = 512,
      c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    const ctx: any = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, W, 0);
    g.addColorStop(0, '#5b3819');
    g.addColorStop(0.5, '#714623');
    g.addColorStop(1, '#552f13');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    // 竖向木纹 (正弦扰动)
    for (let i = 0; i < 70; i++) {
      const x0 = Math.random() * W;
      const dark = Math.random() < 0.7;
      ctx.strokeStyle = dark
        ? `rgba(40,22,8,${0.05 + Math.random() * 0.14})`
        : `rgba(150,100,55,${0.04 + Math.random() * 0.08})`;
      ctx.lineWidth = 0.6 + Math.random() * 2.2;
      ctx.beginPath();
      for (let y = 0; y <= H; y += 6) {
        const x = x0 + Math.sin(y * 0.021 + i) * 5 + Math.sin(y * 0.004 + i * 0.5) * 16;
        if (y === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    // 少量木节
    for (let i = 0; i < 4; i++) {
      const kx = Math.random() * W,
        ky = Math.random() * H;
      for (let r = 14; r > 0; r -= 2) {
        ctx.strokeStyle = `rgba(35,18,6,${0.05 + (14 - r) * 0.01})`;
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.ellipse(kx, ky, r, r * 1.6, 0.5, 0, Math.PI * 2);
        ctx.stroke();
      }
    }
    const tex = new THREE.CanvasTexture(c);
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.anisotropy = 8;
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  },
  // 台面绒布 (细噪点 + 边缘暗角)
  makeFelt() {
    const W = 256,
      H = 256,
      c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    const ctx: any = c.getContext('2d');
    ctx.fillStyle = '#1f7a46';
    ctx.fillRect(0, 0, W, H);
    const img = ctx.getImageData(0, 0, W, H);
    const d = img.data;
    for (let i = 0; i < d.length; i += 4) {
      const n = (Math.random() - 0.5) * 26;
      d[i] = Math.max(0, Math.min(255, d[i] + n * 0.6));
      d[i + 1] = Math.max(0, Math.min(255, d[i + 1] + n));
      d[i + 2] = Math.max(0, Math.min(255, d[i + 2] + n * 0.6));
    }
    ctx.putImageData(img, 0, 0);
    const tex = new THREE.CanvasTexture(c);
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.anisotropy = 8;
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  },
  // 木地板 (横向拼板 + 板缝 + 每板色差)
  makeFloor() {
    const W = 1024,
      H = 1024,
      c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    const ctx: any = c.getContext('2d');
    const plankH = 128;
    for (let py = 0; py < H; py += plankH) {
      const shade = 0.85 + Math.random() * 0.3;
      const base = [Math.round(122 * shade), Math.round(84 * shade), Math.round(48 * shade)];
      ctx.fillStyle = `rgb(${base[0]},${base[1]},${base[2]})`;
      ctx.fillRect(0, py, W, plankH);
      // 板内木纹
      for (let i = 0; i < 26; i++) {
        const y = py + Math.random() * plankH;
        ctx.strokeStyle = `rgba(50,30,14,${0.04 + Math.random() * 0.09})`;
        ctx.lineWidth = 0.6 + Math.random() * 1.6;
        ctx.beginPath();
        for (let x = 0; x <= W; x += 24) {
          ctx.lineTo(x, y + Math.sin(x * 0.01 + i) * 2.5);
        }
        ctx.stroke();
      }
      // 板缝 (底部暗线 + 顶部高光)
      ctx.fillStyle = 'rgba(20,10,4,.5)';
      ctx.fillRect(0, py + plankH - 3, W, 3);
      ctx.fillStyle = 'rgba(190,150,100,.10)';
      ctx.fillRect(0, py, W, 2);
    }
    const tex = new THREE.CanvasTexture(c);
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.anisotropy = 8;
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  },
  // 背景天幕 (等距柱状投影暖色竖向渐变, 替代纯黑背景)
  makeBackground() {
    const W = 1024,
      H = 512,
      c = document.createElement('canvas');
    c.width = W;
    c.height = H;
    const ctx: any = c.getContext('2d');
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#3f342a'); // 顶部(顶棚)暖褐
    g.addColorStop(0.5, '#6d5943'); // 中部(墙面)暖棕
    g.addColorStop(1, '#4a3a2c'); // 底部(地面)暖影
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    const tex = new THREE.CanvasTexture(c);
    tex.mapping = THREE.EquirectangularReflectionMapping;
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  },
  _wan(ctx: any, num: any, W: any, H: any, ox = 0, oy = 0) {
    const ch = ['一', '二', '三', '四', '五', '六', '七', '八', '九'][num - 1];
    ctx.fillStyle = '#c8473a';
    ctx.font = `bold ${H * 0.28}px "KaiTi","STKaiti",serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(ch, ox + W / 2, oy + H * 0.32);
    ctx.fillStyle = '#1a1a1a';
    ctx.font = `bold ${H * 0.32}px "KaiTi","STKaiti",serif`;
    ctx.fillText('萬', ox + W / 2, oy + H * 0.7);
  },
  _tong(ctx: any, num: any, W: any, H: any, ox = 0, oy = 0) {
    const pos = {
      1: [[0.5, 0.5]],
      2: [
        [0.5, 0.32],
        [0.5, 0.68],
      ],
      3: [
        [0.32, 0.32],
        [0.5, 0.5],
        [0.68, 0.68],
      ],
      4: [
        [0.32, 0.32],
        [0.68, 0.32],
        [0.32, 0.68],
        [0.68, 0.68],
      ],
      5: [
        [0.32, 0.3],
        [0.68, 0.3],
        [0.5, 0.5],
        [0.32, 0.7],
        [0.68, 0.7],
      ],
      6: [
        [0.32, 0.28],
        [0.68, 0.28],
        [0.32, 0.5],
        [0.68, 0.5],
        [0.32, 0.72],
        [0.68, 0.72],
      ],
      7: [
        [0.5, 0.22],
        [0.32, 0.42],
        [0.68, 0.42],
        [0.32, 0.6],
        [0.68, 0.6],
        [0.32, 0.78],
        [0.68, 0.78],
      ],
      8: [
        [0.32, 0.25],
        [0.68, 0.25],
        [0.32, 0.43],
        [0.68, 0.43],
        [0.32, 0.61],
        [0.68, 0.61],
        [0.32, 0.79],
        [0.68, 0.79],
      ],
      9: [
        [0.32, 0.22],
        [0.5, 0.22],
        [0.68, 0.22],
        [0.32, 0.42],
        [0.5, 0.42],
        [0.68, 0.42],
        [0.32, 0.62],
        [0.5, 0.62],
        [0.68, 0.62],
      ],
    };
    const r = Math.min(W, H) * 0.11;
    for (const [px, py] of (pos as any)[num]) {
      const cx = ox + px * W,
        cy = oy + py * H;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = num === 5 ? '#c8473a' : '#1a1a1a';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(cx, cy, r * 0.5, 0, Math.PI * 2);
      ctx.fillStyle = '#f4ead8';
      ctx.fill();
    }
  },
  _tiao(ctx: any, num: any, W: any, H: any, ox = 0, oy = 0) {
    if (num === 1) {
      ctx.fillStyle = '#c8473a';
      ctx.font = `bold ${H * 0.5}px "KaiTi",serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('鳥', ox + W / 2, oy + H * 0.5);
      return;
    }
    const cols = num <= 3 ? 1 : 2,
      perCol = Math.ceil(num / cols);
    const lw = W * 0.08,
      lineH = H * 0.5,
      startY = H * 0.25;
    for (let i = 0; i < num; i++) {
      const col = Math.floor(i / perCol),
        row = i % perCol;
      const x = ox + (cols === 1 ? W / 2 : W * (0.35 + col * 0.3));
      const y = oy + startY + (row + 0.5) * (lineH / perCol);
      ctx.fillStyle = num === 5 && i === 2 ? '#c8473a' : '#1a1a1a';
      ctx.fillRect(x - lw / 2, y - (lineH / perCol) * 0.35, lw, (lineH / perCol) * 0.7);
    }
  },
  _feng(ctx: any, ch: any, W: any, H: any, ox = 0, oy = 0) {
    ctx.fillStyle = '#1a1a1a';
    ctx.font = `bold ${H * 0.6}px "KaiTi","STKaiti",serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(ch, ox + W / 2, oy + H / 2 + H * 0.04);
  },
  // + 释放缓存中的所有 CanvasTexture + 共享的 atlas 纹理
  // 在 TileFactory.dispose() 中自动调用
  dispose() {
    for (const key of Object.keys(this._cache)) {
      const tex = this._cache[key];
      if (tex && typeof tex.dispose === 'function') {
        tex.dispose();
      }
      delete this._cache[key];
    }
    // 释放共享的 atlas 纹理
    if (this._atlasTexture) {
      this._atlasTexture.dispose();
      this._atlasTexture = null;
      this._atlasCanvas = null;
    }
  },
};

export { Tex };
