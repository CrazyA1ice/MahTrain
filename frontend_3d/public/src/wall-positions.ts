// ============================================================
// wall-positions.ts — 牌墙位置生成 (纯函数)
// ============================================================
// 提供 3 个纯函数:
//   - generateWallPositions(count): 正常摸牌顺序的位置 (南→西→北→东, 每面从右到左)
//   - generateWallBackPositions(count): 杠后摸牌从牌尾取的位置 (逆序)
//   - generateQuadrantGridPositions(everything): 重整动画天上矩阵位置 (按方位分组就近)
// 这些函数不依赖任何运行时状态, 输入 count/everything → 输出位置数组.
// 单元测试可独立验证, 不需要 Three.js 场景.
// ------------------------------------------------------------
import { CFG } from './constants.ts';

// 4 个方位的基础定义 (南/西/北/东, 与 seat 顺序一致)
const WALL_SIDES = [
  { x: 0, z: CFG.wall.offset, rotY: 0 }, // 南 (seat 0)
  { x: -CFG.wall.offset, z: 0, rotY: -Math.PI / 2 }, // 西 (seat 1)
  { x: 0, z: -CFG.wall.offset, rotY: Math.PI }, // 北 (seat 2)
  { x: CFG.wall.offset, z: 0, rotY: Math.PI / 2 }, // 东 (seat 3)
];

function getLayerY() {
  return [CFG.table.feltHeight + CFG.tile.d / 2, CFG.table.feltHeight + CFG.tile.d + CFG.tile.d / 2];
}

function getSpacing() {
  return CFG.tile.w + CFG.tile.gap;
}

// 牌墙位置点
export interface WallPosition {
  x: number;
  y: number;
  z: number;
  rotY: number;
  layer: number;
}

// 牌对象 (轻量引用, 仅需 mesh.position)
interface TileObjLike {
  mesh?: { position: { x: number; z: number } } | null;
}

// 生成牌墙位置 (4 面顺时针: 南→西→北→东)
// /R2-2: 顺序与 buildWalls/finalizeAnimatedWall 中 wallTiles.push 顺序严格一致
// 每个 side 从右到左 (c 从 perSide-1 递减), 每两列一组 (top, bot, top_c0, bot_c0)
export function generateWallPositions(count: number) {
  const positions: WallPosition[] = [];
  const { perSide, layers } = CFG.wall;
  const layerY = getLayerY();
  const sp = getSpacing();
  const top = layers - 1,
    bot = 0;
  for (let si = 0; si < WALL_SIDES.length; si++) {
    const side = WALL_SIDES[si];
    const cos = Math.cos(side.rotY);
    const sin = Math.sin(side.rotY);
    // 从右到左: c 从 perSide-1 递减到 0, 每两列一组 (与 buildWalls 一致)
    for (let c = perSide - 1 - (perSide % 2 ? 0 : 1); c >= 0; c -= 2) {
      const c0 = c - 1;
      // 当前列 c: top, bot
      const localXc = (c - (perSide - 1) / 2) * sp;
      const xc = side.x + localXc * cos;
      const zc = side.z - localXc * sin;
      positions.push({ x: xc, y: layerY[top], z: zc, rotY: side.rotY, layer: top });
      positions.push({ x: xc, y: layerY[bot], z: zc, rotY: side.rotY, layer: bot });
      // 前一列 c0: top, bot
      if (c0 >= 0) {
        const localXc0 = (c0 - (perSide - 1) / 2) * sp;
        const xc0 = side.x + localXc0 * cos;
        const zc0 = side.z - localXc0 * sin;
        positions.push({ x: xc0, y: layerY[top], z: zc0, rotY: side.rotY, layer: top });
        positions.push({ x: xc0, y: layerY[bot], z: zc0, rotY: side.rotY, layer: bot });
      }
    }
  }
  // 截断到 count (可能 everything.length < 136)
  return positions.slice(0, count);
}

// 生成 wallBack 位置 (与 buildWalls 顺序一致: side 3→0 逆序, 每个 side 从左到右)
export function generateWallBackPositions(count: number) {
  const positions: WallPosition[] = [];
  const { perSide, layers } = CFG.wall;
  const layerY = getLayerY();
  const sp = getSpacing();
  const top = layers - 1,
    bot = 0;
  for (let si = WALL_SIDES.length - 1; si >= 0; si--) {
    const side = WALL_SIDES[si];
    const cos = Math.cos(side.rotY);
    const sin = Math.sin(side.rotY);
    for (let c = 0; c < perSide; c += 2) {
      // c0
      const localX0 = (c - (perSide - 1) / 2) * sp;
      const x0 = side.x + localX0 * cos;
      const z0 = side.z - localX0 * sin;
      positions.push({ x: x0, y: layerY[top], z: z0, rotY: side.rotY, layer: top });
      positions.push({ x: x0, y: layerY[bot], z: z0, rotY: side.rotY, layer: bot });
      // c1
      const localX1 = (c + 1 - (perSide - 1) / 2) * sp;
      const x1 = side.x + localX1 * cos;
      const z1 = side.z - localX1 * sin;
      positions.push({ x: x1, y: layerY[top], z: z1, rotY: side.rotY, layer: top });
      positions.push({ x: x1, y: layerY[bot], z: z1, rotY: side.rotY, layer: bot });
    }
  }
  return positions.slice(0, count);
}

// 按方位分组: 把牌按当前位置分到 4 个方位 (南/西/北/东)
// 返回 { groups: [[],[],[],[]], indices: [[],[],[],[]] }
// groups[si] = 该方位的牌对象数组, indices[si] = 这些牌在 everything 中的原始索引
export function groupByQuadrant(everything: TileObjLike[]) {
  const groups: TileObjLike[][] = [[], [], [], []];
  const indices: number[][] = [[], [], [], []];
  for (let i = 0; i < everything.length; i++) {
    const obj = everything[i];
    if (!obj || !obj.mesh) continue;
    const x = obj.mesh.position.x;
    const z = obj.mesh.position.z;
    // 按方位分组: 用 |x| vs |z| 判断主要方位
    // 南 (seat 0, z>0), 西 (seat 1, x<0), 北 (seat 2, z<0), 东 (seat 3, x>0)
    let si;
    if (Math.abs(z) >= Math.abs(x)) {
      si = z > 0 ? 0 : 2; // 南或北
    } else {
      si = x > 0 ? 3 : 1; // 东或西
    }
    groups[si].push(obj);
    indices[si].push(i);
  }
  return { groups, indices };
}

// 生成"分区域"天上矩阵位置: 每个方位的牌飞到该方位上方
// 返回 gridPositions 数组 (长度 = N), gridPositions[everythingIndex] = 该牌应飞到的天上位置
export function generateQuadrantGridPositions(everything: TileObjLike[]) {
  const { groups, indices } = groupByQuadrant(everything);
  const N = everything.length;
  const gridPositions: Array<{ x: number; y: number; z: number }> = new Array(N);
  const gridY = 8.0;

  // 网格间距: 用牌的长边 (h=1.1) + 裕度, 确保不穿模
  // 牌平放时占 w×h = 0.8×1.1, 间距需 > max(w,h) = 1.1
  const tileLong = 1.1; // CFG.tile.h, 牌的长边
  // 间距 = 长边 + 0.6 裕度 = 1.7, 确保牌之间有明显间隙
  const sp = tileLong + 0.6;

  // 4 个方位的天上矩阵中心点 (在对应牌墙上方)
  const centers = [
    { x: 0, z: CFG.wall.offset }, // 南 (seat 0)
    { x: -CFG.wall.offset, z: 0 }, // 西 (seat 1)
    { x: 0, z: -CFG.wall.offset }, // 北 (seat 2)
    { x: CFG.wall.offset, z: 0 }, // 东 (seat 3)
  ];

  for (let si = 0; si < 4; si++) {
    const group = groups[si];
    const idxList = indices[si];
    if (group.length === 0) continue;
    const center = centers[si];
    // 该方位的矩阵: 长方形排列, 居中在 center 上方
    // 限制最大列数为 8, 避免过宽
    const maxCols = 8;
    const cols = Math.min(maxCols, Math.ceil(Math.sqrt(group.length)));
    const rows = Math.ceil(group.length / cols);
    const startX = center.x - ((cols - 1) / 2) * sp;
    const startZ = center.z - ((rows - 1) / 2) * sp;
    for (let k = 0; k < group.length; k++) {
      const row = Math.floor(k / cols);
      const col = k % cols;
      const origIdx = idxList[k];
      // 轻微 Y 偏移: 按 row 层叠, 避免同一列的牌完全共面 Z-fighting
      // 每行向上偏移 0.02, 视觉上几乎无差异但消除 Z-fighting
      const yOffset = row * 0.02;
      gridPositions[origIdx] = {
        x: startX + col * sp,
        y: gridY + yOffset,
        z: startZ + row * sp,
      };
    }
  }
  // 兜底: 任何未赋值的 (理论上不应该有) 用全局矩阵
  for (let i = 0; i < N; i++) {
    if (!gridPositions[i]) {
      gridPositions[i] = { x: 0, y: gridY, z: 0 };
    }
  }
  return gridPositions;
}
