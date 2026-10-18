// ============================================================
// events.ts — 简单事件总线 (解耦 board ↔ interaction ↔ scene 循环依赖)
// ============================================================
// 各模块通过 on() 订阅事件, emit() 触发, 互不直接引用。
// 存在原因: board.ts 触发 HAND_CHANGED 时不能直接 import interaction.ts (会循环依赖),
// 通过事件总线让 main.ts 订阅并转发到 interaction.ts。

type EventHandler = (...args: unknown[]) => void;
const listeners = new Map<string, Set<EventHandler>>();

/** 订阅事件, 返回取消订阅函数 */
export function on(event: string, handler: EventHandler): () => void {
  if (!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event)!.add(handler);
  return () => listeners.get(event)?.delete(handler);
}

/** 触发事件, 所有 handler 同步执行 */
export function emit(event: string, ...args: any[]): void {
  const set = listeners.get(event);
  if (!set) return;
  for (const h of set) {
    try {
      h(...args);
    } catch (e) {
      console.error(`[events] handler for "${event}" threw:`, e);
    }
  }
}

// 事件名常量 (避免拼写错误)
export const EV = {
  // board → interaction: 手牌变化 (创建/移除/副露), 需要重算 slot 与重排
  HAND_CHANGED: 'hand:changed',
  // board → scene: 牌桌重置, 需要重建牌墙
  BOARD_RESET: 'board:reset',
  // board → interaction: 出牌完成, 需要清除选中
  DISCARD_DONE: 'discard:done',
} as const;
