// ============================================================
// state/network-refs.mjs — 网络 + UI 引用
// ============================================================
// 由 state.mjs 拆分而来 (P2-2). 持有 WebSocket 实例与 UI DOM 元素引用.
// 在 network.mjs / ui.mjs / main.mjs / handlers.mjs / board.mjs 中读写.
import type { UIRefs } from '../types';

export const networkRefs: {
  ws: WebSocket | null;
  ui: UIRefs;
} = {
  // === WebSocket 实例 ===
  ws: null,

  // === UI 元素引用 (在 main.mjs 中填充) ===
  ui: {},
};
