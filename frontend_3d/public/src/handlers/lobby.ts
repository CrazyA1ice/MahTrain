// ============================================================
// handlers/lobby.mjs — 大厅/玩家状态消息处理
// ============================================================
// 由 handlers.mjs 拆分而来 (P2-1). 处理与大厅、座位、玩家进出相关的消息:
//   WELCOME, ROOM_STATE, SEAT_FULL, ERROR,
//   PLAYER_LEFT, PLAYER_DISCONNECTED, PLAYER_RECONNECTED
import { gameState } from '../state/game-state.ts';
import { networkRefs } from '../state/network-refs.ts';
import { DIR_NAME } from '../constants.ts';
import type { ServerMsg } from './index.ts';
import { toast, showError, handleServerError, renderPlayers, hideLoader } from '../ui.ts';

interface RoomSeat {
  name?: string | null;
  disconnected?: boolean;
}

interface _WelcomeMsg {
  yourSeat: number;
  roomSeats: RoomSeat[];
}
interface _RoomStateMsg {
  seats: RoomSeat[];
}
interface _PlayerLeftMsg {
  seat: number;
  name?: string;
}
interface _ErrorMsg {
  msg: string;
}

function onWelcome(m: ServerMsg): void {
  if (networkRefs.ui.seatText) networkRefs.ui.seatText.textContent = DIR_NAME[m.yourSeat];
  for (let i = 0; i < 4; i++) {
    const s = m.roomSeats[i];
    gameState.playerInfo[i].name = s && s.name ? s.name : '';
  }
  if (networkRefs.ui.playersBox) networkRefs.ui.playersBox.style.display = 'block';
  renderPlayers();
  hideLoader();
  toast(`你坐在 ${DIR_NAME[m.yourSeat]} 位`, 2000);
}

function onRoomState(m: ServerMsg): void {
  for (let i = 0; i < 4; i++) {
    const s = m.seats[i];
    gameState.playerInfo[i].name = s && s.name ? s.name : '';
    gameState.playerInfo[i].disconnected = !!(s && s.disconnected);
  }
  renderPlayers();
  if (m.seats.every((s: RoomSeat) => s && s.name && !s.disconnected)) {
    if (networkRefs.ui.loaderText) networkRefs.ui.loaderText.textContent = '准备开始...';
  }
}

function onSeatFull(): void {
  showError('座位已被占用', '该座位已被其他玩家选择, 请回大厅重新选座');
  setTimeout(() => (location.href = 'index.html'), 2000);
}

function onError(m: ServerMsg): void {
  handleServerError(m.msg);
}

function onPlayerLeft(m: ServerMsg): void {
  gameState.playerInfo[m.seat].name = '';
  renderPlayers();
  toast(`${m.name || '玩家'} 离开了`, 2000);
}

function onPlayerDisconnected(m: ServerMsg): void {
  gameState.playerInfo[m.seat].disconnected = true;
  renderPlayers();
  toast(`${m.name || '玩家'} 断线, 等待重连...`, 3000);
}

function onPlayerReconnected(m: ServerMsg): void {
  gameState.playerInfo[m.seat].disconnected = false;
  renderPlayers();
  toast(`${m.name || '玩家'} 已重连`, 2000);
}

export { onWelcome, onRoomState, onSeatFull, onError, onPlayerLeft, onPlayerDisconnected, onPlayerReconnected };
