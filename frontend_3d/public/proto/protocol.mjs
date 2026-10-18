// ============================================================
// 雀局 · 联机麻将 — 消息协议 (前后端共享, ESM 单一真相源)
// ============================================================
// 这个文件被前端 (public/game.html 通过 import) 和后端 (server.js 通过 import)
// 同时引用。**修改本文件后无需手动同步任何其他位置**。
//
// 座位约定 (绝对世界方向):
//   seat 0 = 南 (z=+HAND_DIST, rotY=0)   ← 默认视角
//   seat 1 = 西 (x=-HAND_DIST, rotY=-90°)
//   seat 2 = 北 (z=-HAND_DIST, rotY=180°)
//   seat 3 = 东 (x=+HAND_DIST, rotY=+90°) ← 庄家方向,骰子先投
// ------------------------------------------------------------

export const DIR_NAME = ['南', '西', '北', '东']; // seat -> 方位名
export const SEAT_OF_DIR = { 南: 0, 西: 1, 北: 2, 东: 3 };

// 骰子投掷顺序: 东(3) -> 南(0) -> 西(1) -> 北(2)
export const DICE_ORDER = [3, 0, 1, 2];

// 出牌(顺时针)顺序: 以庄家为起点, seat 序号取模循环
// 庄家先出; 顺时针在物理桌面上是 0->1->2->3 (南->西->北->东)
export const PHASE = {
  WAITING: 'waiting', // 大厅等位
  DICE: 'dice', // 骰子阶段
  DEAL: 'deal', // 发牌阶段
  PLAY: 'play', // 出牌阶段
};

export const MSG = {
  // C -> S
  JOIN: 'join', // { seat, name }
  ROLL_DICE: 'rollDice', // {}        当前玩家投骰子
  START_DEAL: 'startDeal', // {}        庄家点发牌
  TEST_DEAL: 'testDeal', // {}        测试: 非随机发牌(每家很多相同牌)
  RESTART: 'restart', // {}        胡牌后重新开一局
  DISCARD: 'discard', // { tileId, x, z, rotY }  玩家扔牌
  CLAIM: 'claim', // { action:'pong'|'kong'|'ckong'|'addKong'|'win'|'pass', value? }

  // S -> C
  WELCOME: 'welcome', // { yourSeat, roomSeats }
  ROOM_STATE: 'roomState', // { seats:[{seat,name,ready}x4] }
  PHASE: 'phase', // { phase, ...payload }
  DICE_TURN: 'diceTurn', // { seat }    轮到谁投
  DICE_RESULT: 'diceResult', // { seat, values:[a,b], sum } 动画结束后才发
  DEAL: 'deal', // { tile:{id,type,value}, toSeat, handIdx, faceUp }
  DEAL_END: 'dealEnd', // {}          发牌结束
  TURN_CHANGE: 'turnChange', // { seat, lastDiscardBy, draw }  轮到谁出; draw=该家是否需摸牌
  DISCARD_BC: 'discardBc', // { tileId, bySeat, x, z, rotY, faceUp, tile }
  DRAW_BC: 'drawBc', // { bySeat, handIdx, tile?, fromBack }  摸牌;fromBack=杠后从牌墙尾摸
  CLAIM_OFFER: 'claimOffer', // { tile, fromSeat, options:['pong'|'kong'|'win'], deadline }
  SELF_OPTIONS: 'selfOptions', // { canWin, ckong:[value...], addKong:[value...] }  自摸后可操作
  MELD_BC: 'meldBc', // { seat, kind:'pong'|'kong'|'ckong', tiles:[{id,type,value}], fromSeat, meldIdx, upgrade }
  WIN_BC: 'winBc', // { seat, tile, fromSeat, selfDraw, hands:[[..]x4], melds:[[..]x4] }
  ERROR: 'error', // { msg }
  SEAT_FULL: 'seatFull', // { seat }    选座失败(已被占)
  PLAYER_LEFT: 'playerLeft', // { seat, name }
  // { phase, dealer, currentTurn, diceResults, handCounts, yourHand, melds, lastDiscard }
  RECONNECT_STATE: 'reconnectState',
  RESTART_PROGRESS: 'restartProgress',
  // 补全: 之前被引用但未定义的 3 个广播常量, 导致客户端 switch 无对应 case 静默 fall through
  PLAYER_DISCONNECTED: 'playerDisconnected', // { seat } 某玩家断线
  PLAYER_RECONNECTED: 'playerReconnected', // { seat } 某玩家重连
  DICE_ROLL_START: 'diceRollStart', // { seat } 骰子动画启动信号
  //     服务端只回声 count 不校验内容, 是死协议。整理手牌只影响本地视图, 不广播。
};

// 牌面排序权重 (规律整理用)
// 万 1-9, 筒 1-9, 条 1-9, 字: 东南西北中發白
export function tileSortKey(t) {
  const typeOrder = { wan: 0, tong: 1, tiao: 2, feng: 3 };
  const v = t.value;
  let sub;
  if (t.type === 'feng') {
    const chOrder = ['東', '南', '西', '北', '中', '發', '白'];
    sub = chOrder.indexOf(v);
    if (sub < 0) sub = 99;
  } else {
    sub = v - 1;
  }
  return typeOrder[t.type] * 100 + sub;
}
