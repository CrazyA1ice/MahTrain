// ============================================================
// constants.mjs — 全局常量与座位相关工具
// ============================================================
import { DIR_NAME, PHASE, MSG, tileSortKey } from '/proto/protocol.mjs';

// URL 参数
const params = new URLSearchParams(location.search);
const MY_SEAT = parseInt(params.get('seat') ?? '-1', 10);
const MY_NAME = decodeURIComponent(params.get('name') || '玩家');

// 主配置
export interface CFGAnim {
  deal: number;
  dealFly: number;
  discard: number;
  meld: number;
  rearrange: number;
  dice: number;
  diceTurn: number;
  claimTimeout: number;
  turnDelay: number;
  // 可选的动画调优参数 (调用方用 `|| default` 兜底)
  flyTilePeak?: number;
  discardPeakAdd?: number;
  tipOver?: number;
  flyToFlatPeakAdd?: number;
}
export interface CFG {
  table: { outerSize: number; holeSize: number; feltHeight: number; woodHeight: number; rimWidth: number };
  tile: { w: number; h: number; d: number; gap: number; radius: number };
  wall: { offset: number; perSide: number; layers: number };
  dice: { size: number; trayBottomY: number; glassY: number };
  anim: CFGAnim;
  spacing: {
    handGap: number;
    meldGap: number;
    wallGap: number;
    discardCellGap: number;
    dragThresh: number;
  };
}
const CFG: CFG = {
  table: { outerSize: 23.0, holeSize: 3.4, feltHeight: 0.4, woodHeight: 0.8, rimWidth: 0.5 },
  tile: { w: 0.8, h: 1.1, d: 0.5, gap: 0.015, radius: 0.05 },
  wall: { offset: 7.6, perSide: params.get('mahtrain') === '1' ? 14 : 17, layers: 2 },
  dice: { size: 0.45, trayBottomY: -0.77, glassY: 0.35 },
  anim: {
    deal: 60, // 发牌每张间隔 60ms (客户端参考, 实际由服务器 dealStep 控制)
    dealFly: 130, // 发牌飞行时长 130ms (≤ dealStep 140ms, 避免牌到手卡帧)
    discard: 460,
    meld: 460,
    rearrange: 200,
    dice: 1700,
    diceTurn: 1200,
    claimTimeout: 8000,
    turnDelay: 2500,
  },
  spacing: {
    handGap: 0.02,
    meldGap: 0.04,
    wallGap: 0.015,
    discardCellGap: 0.12,
    dragThresh: 6,
  },
};

// 派生常量
const GROUND_Y = CFG.table.feltHeight;
const HALF_W = CFG.tile.w / 2;
const HALF_H = CFG.tile.h / 2;
const HALF_D = CFG.tile.d / 2;
const SPACING = CFG.tile.w + CFG.tile.gap;

// 牌发光色 (setEmissive 用) — 替代散落各处的 0xc88a20/0x6a5a30/0x000000 魔法数字
const EMISSIVE = {
  OFF: 0x000000, // 默认: 不发光
  SELECT: 0x6a5a30, // 选中: 暗金
  HIGHLIGHT: 0xc88a20, // 高亮/赢家: 亮金
};

const LAYER_Y = [GROUND_Y + HALF_D, GROUND_Y + CFG.tile.d + HALF_D];
const STAND_TILE_Y = GROUND_Y + HALF_H;
const HAND_DIST = 9.2; // 手牌中心距桌心 (原 9.6, 前移 0.4 避免与牌墙穿模)
const MELD_DIST = 10.2; // 副露中心距桌心 (贴近桌边, 与手牌拉开距离)
const HAND_HALF_RANGE = 6.0;
const FELT_OUTER_LIMIT = CFG.table.outerSize / 2 - CFG.table.rimWidth - 0.5;
const FELT_INNER_LIMIT = CFG.table.holeSize / 2 + 0.5;
const TILE_SP = CFG.tile.w + 0.02;
const TILE_RISE = CFG.tile.h;
const DRAG_THRESH = 6;

export interface SeatTrack {
  axis: 'x' | 'z';
  constX?: number;
  constZ?: number;
  rotY: number;
}
export interface SeatDiscardZone {
  axis: 'x' | 'z';
  near: number;
  far: number;
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
}
const SEAT_TRACK: SeatTrack[] = [
  { axis: 'z', constZ: HAND_DIST, rotY: 0 },
  { axis: 'x', constX: -HAND_DIST, rotY: -Math.PI / 2 },
  { axis: 'z', constZ: -HAND_DIST, rotY: Math.PI },
  { axis: 'x', constX: HAND_DIST, rotY: Math.PI / 2 },
];
// 副露轨道: 比手牌更靠外 (贴近桌边), 与手牌在不同距离避免穿模
const SEAT_MELD_TRACK: SeatTrack[] = [
  { axis: 'z', constZ: MELD_DIST, rotY: 0 },
  { axis: 'x', constX: -MELD_DIST, rotY: -Math.PI / 2 },
  { axis: 'z', constZ: -MELD_DIST, rotY: Math.PI },
  { axis: 'x', constX: MELD_DIST, rotY: Math.PI / 2 },
];
const SEAT_DISCARD_ZONE: SeatDiscardZone[] = [
  { axis: 'z', near: 3.8, far: 7.4, minX: -4, maxX: 4, minZ: 3.8, maxZ: 7.4 },
  { axis: 'x', near: -3.8, far: -7.4, minX: -7.4, maxX: -3.8, minZ: -4, maxZ: 4 },
  { axis: 'z', near: -3.8, far: -7.4, minX: -4, maxX: 4, minZ: -7.4, maxZ: -3.8 },
  { axis: 'x', near: 3.8, far: 7.4, minX: 3.8, maxX: 7.4, minZ: -4, maxZ: 4 },
];
const SEAT_PIVOT_ROT = [0, Math.PI / 2, Math.PI, -Math.PI / 2];
const SEAT_LEFT_SIGN = [-1, -1, 1, 1];

function handTrack(seat: number) {
  return SEAT_TRACK[seat];
}
function meldTrack(seat: number) {
  return SEAT_MELD_TRACK[seat];
}
function discardZone(seat: number) {
  return SEAT_DISCARD_ZONE[seat];
}
function pivotRotYForSeat(seat: number) {
  return SEAT_PIVOT_ROT[seat];
}
function leftSign(seat: number) {
  return SEAT_LEFT_SIGN[seat];
}

// A3: 沿轨道 along 坐标 → 世界 {x, z}
function alongToWorld(seat: number, along: number) {
  const tr = SEAT_TRACK[seat];
  if (tr.axis === 'z') return { x: along, z: tr.constZ };
  return { x: tr.constX, z: along };
}

// 弃牌格
function discardCell(seat: number, index: number) {
  const zone = discardZone(seat);
  const colSpacing = CFG.tile.w + 0.12; // 列间距 (牌宽 + 间隙)
  const rowSpacing = CFG.tile.h + 0.15; // 行间距 (牌长 + 间隙, 修复上下层穿模)
  const perRow = 6;
  const col = index % perRow,
    row = Math.floor(index / perRow);
  if (zone.axis === 'z') {
    const x = (col - (perRow - 1) / 2) * colSpacing;
    const z = zone.near + (zone.far > zone.near ? 1 : -1) * (row + 0.5) * rowSpacing;
    return { x, z };
  } else {
    const z = (col - (perRow - 1) / 2) * colSpacing;
    const x = zone.near + (zone.far > zone.near ? 1 : -1) * (row + 0.5) * rowSpacing;
    return { x, z };
  }
}

function seatTotal(seat: number, dealerSeat: number) {
  return seat === dealerSeat ? 14 : 13;
}
function slotAlong(handIdx: number, total: number) {
  return (handIdx - (total - 1) / 2) * TILE_SP;
}

function seatFromRotY(rotY: number) {
  const r = ((rotY % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
  if (Math.abs(r - 0) < 0.1) return 0;
  if (Math.abs(r - Math.PI * 1.5) < 0.1) return 1;
  if (Math.abs(r - Math.PI) < 0.1) return 2;
  if (Math.abs(r - Math.PI * 0.5) < 0.1) return 3;
  return 0;
}

interface TileLike {
  type: string;
  value: number | string;
}
function tileLabel(t: TileLike | null | undefined) {
  if (!t) return '';
  if (t.type === 'feng') return String(t.value);
  const suit = ({ wan: '万', tong: '筒', tiao: '条' } as Record<string, string>)[t.type] || '';
  return String(t.value) + suit;
}

export {
  DIR_NAME,
  PHASE,
  MSG,
  tileSortKey,
  MY_SEAT,
  MY_NAME,
  CFG,
  GROUND_Y,
  HALF_W,
  HALF_H,
  HALF_D,
  SPACING,
  EMISSIVE,
  LAYER_Y,
  HAND_DIST,
  MELD_DIST,
  STAND_TILE_Y,
  HAND_HALF_RANGE,
  FELT_OUTER_LIMIT,
  FELT_INNER_LIMIT,
  TILE_SP,
  TILE_RISE,
  DRAG_THRESH,
  SEAT_TRACK,
  SEAT_DISCARD_ZONE,
  SEAT_PIVOT_ROT,
  SEAT_LEFT_SIGN,
  handTrack,
  meldTrack,
  discardZone,
  pivotRotYForSeat,
  leftSign,
  alongToWorld,
  discardCell,
  seatTotal,
  slotAlong,
  seatFromRotY,
  tileLabel,
};
