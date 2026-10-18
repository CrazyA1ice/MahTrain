// ============================================================
// handlers/index.ts — 服务器消息处理主分发
// ============================================================
// 由 handlers.mjs 拆分而来 (P2-1). 此文件仅包含:
//   - handleServer(m) 主分发函数, 把 22 个 case 路由到 4 个子文件
//   - 公共错误处理 (未知消息类型日志)
// 各 case 的具体实现分别位于:
//   - handlers/lobby.ts      (WELCOME/ROOM_STATE/SEAT_FULL/ERROR/PLAYER_LEFT/DISCONNECTED/RECONNECTED)
//   - handlers/dice-deal.ts  (PHASE/DICE_TURN/DICE_ROLL_START/DICE_RESULT/DEAL/DEAL_END/TURN_CHANGE)
//   - handlers/play.ts       (DISCARD_BC/DRAW_BC/CLAIM_OFFER/SELF_OPTIONS/MELD_BC/WIN_BC/RESTART_PROGRESS)
//   - handlers/reconnect.ts  (RECONNECT_STATE)
// L-02 修复: 移除 msg as never 断言, 改用统一的 ServerMsg 类型 (Record<string, unknown>)
//   各 handler 内部自行 narrow 字段, 编译器不强制但 IDE 智能提示可用
// ------------------------------------------------------------
import { MSG } from '../constants.ts';
import * as lobby from './lobby.ts';
import * as diceDeal from './dice-deal.ts';
import * as play from './play.ts';
import * as win from './win.ts';
import { applyReconnectState } from './reconnect.ts';

// 服务器消息统一信封: type 字段是 string, 其他字段由各 handler 自行 narrow
// L-02 修复: 用 ServerMsg 替代 as never, 提供最小类型信息
// 注: 各 handler 接收 ServerMsg (索引签名 unknown), 内部访问字段时用 as 断言到具体类型
// 这是协议层边界的合理折衷 — 服务端消息字段是动态的, 编译期无法完全静态化
export type ServerMsg = Record<string, any> & { type: string; seq?: number };

function handleServer(m: ServerMsg): void {
  // L-02 修复: msg 已是 ServerMsg 类型, 直接传给各 handler (无需 as never)
  switch (m.type) {
    // === 大厅/玩家状态 ===
    case MSG.WELCOME:
      lobby.onWelcome(m);
      break;
    case MSG.ROOM_STATE:
      lobby.onRoomState(m);
      break;
    case MSG.SEAT_FULL:
      lobby.onSeatFull();
      break;
    case MSG.ERROR:
      lobby.onError(m);
      break;
    case MSG.PLAYER_LEFT:
      lobby.onPlayerLeft(m);
      break;
    case MSG.PLAYER_DISCONNECTED:
      lobby.onPlayerDisconnected(m);
      break;
    case MSG.PLAYER_RECONNECTED:
      lobby.onPlayerReconnected(m);
      break;

    // === 骰子/发牌 ===
    case MSG.PHASE:
      diceDeal.onPhase(m);
      break;
    case MSG.DICE_TURN:
      diceDeal.onDiceTurn(m);
      break;
    case MSG.DICE_ROLL_START:
      diceDeal.onDiceRollStart(m);
      break;
    case MSG.DICE_RESULT:
      diceDeal.onDiceResult(m);
      break;
    case MSG.DEAL:
      diceDeal.onDeal(m);
      break;
    case MSG.DEAL_END:
      diceDeal.onDealEnd(m);
      break;
    case MSG.TURN_CHANGE:
      diceDeal.onTurnChange(m);
      break;

    // === 出牌/认领/副露/胡牌 ===
    case MSG.DISCARD_BC:
      play.onDiscardBc(m);
      break;
    case MSG.DRAW_BC:
      play.onDrawBc(m);
      break;
    case MSG.CLAIM_OFFER:
      play.onClaimOffer(m);
      break;
    case MSG.SELF_OPTIONS:
      play.onSelfOptions(m);
      break;
    case MSG.MELD_BC:
      play.onMeldBc(m);
      break;
    case MSG.WIN_BC:
      win.onWinBc(m);
      break;
    case MSG.RESTART_PROGRESS:
      win.onRestartProgress(m);
      break;

    // === 重连状态恢复 ===
    case MSG.RECONNECT_STATE:
      applyReconnectState(m);
      break;

    default:
      // 记录未知消息类型, 防止协议变更时静默 fall through
      console.warn('[handlers] 未知消息类型:', m.type, m);
      break;
  }
}

export { handleServer, applyReconnectState };
