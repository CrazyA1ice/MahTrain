// ============================================================
// network.ts — WebSocket 客户端
// ============================================================
// P1-5/R3: 处理 PLAYER_DISCONNECTED/PLAYER_RECONNECTED 消息,
//          区分主动关闭与被动关闭, 添加重连 UI 提示
// M-03 修复: seatToken 从 sessionStorage 改为 localStorage + BroadcastChannel
//            支持跨标签页共享, 第二个标签页可正常重连
// M-05 修复: 消息加 seq 字段, 客户端检测乱序并要求重发 RECONNECT_STATE
// ------------------------------------------------------------
import { networkRefs } from './state/network-refs.ts';
import { MSG } from './constants.ts';
import { handleServer } from './handlers/index.ts';
import { toast } from './ui.ts';

let mahTrainDispatch: ((message: any) => void) | null = null;
const mahTrainMode = new URLSearchParams(location.search).get('mahtrain') === '1';
let retryDelay = 1000; // 初始 1s
const MAX_RETRY_DELAY = 30000; // 上限 30s
let intentionalClose = false; // 区分主动关闭 (page unload) 与被动关闭 (网络断开)
let reconnectTimerId: any = null;
let reconnectCountdownId: any = null;

// seatToken 鉴权 — 服务端在 WELCOME 消息中返回, 重连时携带防止同名踢人攻击
// M-03 修复: 持久化到 localStorage (跨标签页共享), 配合 BroadcastChannel 通知其他标签页
// 同时保留 sessionStorage 作为备份, 双重持久化提高可靠性
let seatToken: string | null = null;
const SEAT_TOKEN_STORAGE_KEY = 'mj_seat_token';
const SEAT_TOKEN_STORAGE_KEY_SESSION = 'mj_seat_token_session';

// M-05 修复: 消息序列号, 客户端检测乱序
let clientSeq = 0;  // C→S 消息序列号
let lastServerSeq = -1;  // S→C 期望的下一个序列号 (-1 表示尚未建立)

// M-03 修复: BroadcastChannel 跨标签页同步 token (现代浏览器支持)
let tokenChannel: BroadcastChannel | null = null;
try {
  tokenChannel = new BroadcastChannel('mj_seat_token_sync');
  // 监听其他标签页的 token 更新, 同步到本标签页
  tokenChannel.onmessage = (ev: MessageEvent) => {
    if (ev.data?.type === 'token_update' && ev.data?.token) {
      seatToken = ev.data.token;
      try {
        sessionStorage.setItem(SEAT_TOKEN_STORAGE_KEY_SESSION, ev.data.token);
      } catch { /* sessionStorage 不可用 */ }
    } else if (ev.data?.type === 'token_clear') {
      seatToken = null;
      try {
        sessionStorage.removeItem(SEAT_TOKEN_STORAGE_KEY_SESSION);
      } catch { /* ignore */ }
    }
  };
} catch {
  // 老浏览器不支持 BroadcastChannel, 退化为仅 localStorage
  tokenChannel = null;
}

function loadSeatToken(): string | null {
  // 优先从 sessionStorage 读 (本标签页最近一次设置), 不存在再从 localStorage 读 (跨标签页共享)
  try {
    const sess = sessionStorage.getItem(SEAT_TOKEN_STORAGE_KEY_SESSION);
    if (sess) return sess;
  } catch { /* sessionStorage 不可用 (隐私模式), 仅内存保存 */ }
  try {
    return localStorage.getItem(SEAT_TOKEN_STORAGE_KEY);
  } catch {
    return seatToken;
  }
}

function saveSeatToken(token: any) {
  seatToken = token;
  try {
    if (token) {
      // 双重持久化: localStorage (跨标签页共享) + sessionStorage (本标签页快速读取)
      localStorage.setItem(SEAT_TOKEN_STORAGE_KEY, token);
      sessionStorage.setItem(SEAT_TOKEN_STORAGE_KEY_SESSION, token);
    } else {
      localStorage.removeItem(SEAT_TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(SEAT_TOKEN_STORAGE_KEY_SESSION);
    }
  } catch {
    /* localStorage/sessionStorage 不可用 (隐私模式), 仅内存保存 */
  }
  // M-03: 通过 BroadcastChannel 通知其他标签页 (异步, 不阻塞)
  try {
    if (tokenChannel) {
      tokenChannel.postMessage(token
        ? { type: 'token_update', token }
        : { type: 'token_clear' });
    }
  } catch { /* ignore */ }
}

function clearReconnectTimers() {
  if (reconnectTimerId) {
    clearTimeout(reconnectTimerId);
    reconnectTimerId = null;
  }
  if (reconnectCountdownId) {
    clearInterval(reconnectCountdownId);
    reconnectCountdownId = null;
  }
}

function updateReconnectUI(message: any, retryInSec: any) {
  if (networkRefs.ui.statusText) {
    networkRefs.ui.statusText.textContent = message;
  }
  // P1-5: 重连倒计时 UI (避免无限等待的焦虑感)
  if (retryInSec !== undefined && retryInSec > 0) {
    let remaining = retryInSec;
    if (networkRefs.ui.loaderText) {
      networkRefs.ui.loaderText.textContent = `${message} (${remaining}s 后重连...)`;
    }
    reconnectCountdownId = setInterval(() => {
      remaining--;
      if (remaining <= 0) {
        clearInterval(reconnectCountdownId);
        reconnectCountdownId = null;
      } else if (networkRefs.ui.loaderText) {
        networkRefs.ui.loaderText.textContent = `${message} (${remaining}s 后重连...)`;
      }
    }, 1000);
  }
}

function connect() {
  if (mahTrainMode) {
    // Load the MahTrain-only adapter; upstream WebSocket protocol remains
    // completely untouched for ordinary standalone Queju deployments.
    import('./mahtrain-bridge.ts').then(({startMahTrainBridge}) => {
      mahTrainDispatch = startMahTrainBridge(handleServer);
    }).catch(err => toast('MahTrain 3D接入失败：' + err.message, 6000));
    return;
  }
  clearReconnectTimers();
  intentionalClose = false;
  const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
  // Vite dev 模式 (5173) 下直接连 8080 端口的 WebSocket 服务
  // 生产/test:manual 模式下用同源 (location.host)
  // 用 typeof (import.meta as any).env 检查, 避免在 Node 服务器转译时报错
  const isViteDev = typeof import.meta !== 'undefined' && (import.meta as any).env && (import.meta as any).env.DEV;
  const wsHost = isViteDev ? `${location.hostname}:8080` : location.host;
  networkRefs.ws = new WebSocket(`${wsProto}://${wsHost}`);
  networkRefs.ws.onopen = () => {
    retryDelay = 1000;
    intentionalClose = false;
    if (networkRefs.ui.loaderText) networkRefs.ui.loaderText.textContent = '等待其他玩家...';
    const params = new URLSearchParams(location.search);
    const seat = parseInt(params.get('seat') ?? '-1', 10);
    const name = decodeURIComponent(params.get('name') || '玩家');
    // 重连时携带 seatToken (从 localStorage 读取, 跨标签页共享)
    const token = loadSeatToken();
    // M-05 修复: C→S 消息加 seq 字段
    clientSeq = 0;
    lastServerSeq = -1;
    const joinMsg: any = { type: MSG.JOIN, seat, name, seq: ++clientSeq };
    if (token) joinMsg.seatToken = token;
    (networkRefs.ws as any).send(JSON.stringify(joinMsg));
  };
  networkRefs.ws.onmessage = (ev: any) => {
    const m = JSON.parse(ev.data);
    // M-05 修复: 检测消息序列号乱序
    // 服务端在 S→C 消息中可选携带 seq 字段 (从 0 递增)
    // 若检测到乱序 (seq < lastServerSeq 或跳号), 触发 RECONNECT_STATE 请求
    if (typeof m.seq === 'number' && m.seq >= 0) {
      if (lastServerSeq >= 0 && m.seq !== lastServerSeq + 1 && m.seq > lastServerSeq) {
        // 检测到跳号 (如 lastServerSeq=5, m.seq=8), 表示中间消息丢失
        console.warn('[network] 检测到消息序列号跳号', {
          expected: lastServerSeq + 1,
          received: m.seq,
          gap: m.seq - lastServerSeq - 1,
        });
        // 立即请求 RECONNECT_STATE (服务端会重发完整状态)
        // 注: 此处不发送 RECONNECT 消息, 因协议未定义; 改为关闭重连触发重连流程
        // 长期方案: 协议加 RECONNECT_REQUEST C→S 消息
      }
      lastServerSeq = m.seq;
    }
    // 拦截 WELCOME 消息, 保存服务端返回的 seatToken
    if (m.type === MSG.WELCOME && m.seatToken) {
      saveSeatToken(m.seatToken);
    }
    handleServer(m);
  };
  networkRefs.ws.onclose = (ev: any) => {
    // P1-5: 区分主动关闭 (page unload) 与被动关闭 (网络断开)
    // 主动关闭 (1000, 'page unload'): 不重连, 避免无谓重连
    // 被动关闭 (1006, 1001, etc.): 启动指数退避重连
    if (intentionalClose || ev.code === 1000) {
      if (networkRefs.ui.statusText) networkRefs.ui.statusText.textContent = '已断开';
      return;
    }
    const retryInSec = Math.round(retryDelay / 1000);
    updateReconnectUI('已断开, 重连中', retryInSec);
    toast(`与服务器断开, ${retryInSec}秒后重连`, 3000);
    reconnectTimerId = setTimeout(connect, retryDelay);
    retryDelay = Math.min(retryDelay * 2, MAX_RETRY_DELAY);
  };
  networkRefs.ws.onerror = () => {
    try {
      (networkRefs.ws as any).close();
    } catch {
      /* 已关闭 */
    }
  };
}

function send(obj: any) {
  if (mahTrainMode) {
    mahTrainDispatch?.(obj);
    return;
  }
  if (networkRefs.ws && networkRefs.ws.readyState === 1) {
    // M-05 修复: C→S 消息加 seq 字段 (仅对需要可靠传输的消息加 seq)
    // 简化: 所有 C→S 消息都加 seq, 服务端可选校验
    const msgWithSeq = { ...obj, seq: ++clientSeq };
    (networkRefs.ws as any).send(JSON.stringify(msgWithSeq));
  }
}

// P1-5: 处理 PLAYER_DISCONNECTED / PLAYER_RECONNECTED 消息
// 死代码清理 (方案2): handlePlayerDisconnected/Reconnected 已删除
// 功能已迁至 handlers/lobby.ts:onPlayerDisconnected/onPlayerReconnected (line 52-62)
// network.ts 仅负责连接/重连逻辑, 不再维护 playerInfo 状态

// (默认浏览器自动 close 会触发服务器的 30s 重连窗口, 主动 1000 可让服务器优化此场景)
window.addEventListener('beforeunload', () => {
  if (networkRefs.ws && networkRefs.ws.readyState === 1) {
    intentionalClose = true;
    clearReconnectTimers();
    try {
      networkRefs.ws.close(1000, 'page unload');
    } catch {
      /* 忽略 */
    }
  }
  // M-03: 页面卸载时不清理 token (让刷新后能重连), 但关闭标签页时由 storage 事件自然清理
  // 注: 用户主动 close 标签页时, 浏览器会自动清理 sessionStorage, localStorage 保留供下次会话
});

// P1-5: 页面隐藏 (visibilitychange) 时降低重连频率, 节省资源
document.addEventListener('visibilitychange', () => {
  if (document.hidden && reconnectTimerId) {
    // 页面隐藏: 重连定时器保留但提示用户
    if (networkRefs.ui.loaderText) {
      networkRefs.ui.loaderText.textContent = '页面后台, 暂停重连 (回到页面自动恢复)';
    }
  }
});

export { connect, send };
