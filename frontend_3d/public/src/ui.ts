// ============================================================
// ui.mjs — DOM UI (toast / showError / renderPlayers / claimBar / loader)
// ============================================================
import { DIR_NAME, PHASE } from './constants.ts';
import { gameState } from './state/game-state.ts';
import { handState } from './state/hand-state.ts';
import { interactionState } from './state/interaction-state.ts';
import { networkRefs } from './state/network-refs.ts';
import { myTotalTiles } from './state.ts';

let toastTimer: any = null;

function toast(msg: any, dur = 1600) {
  const { toastEl } = networkRefs.ui;
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), dur);
}

function showError(title: any, msg: any) {
  const { errorOverlay, errorTitle, errorMsg } = networkRefs.ui;
  if (!errorOverlay) return;
  errorTitle.textContent = title || '出错了';
  errorMsg.textContent = msg || '';
  errorOverlay.classList.add('show');
}

// 错误分级: 根据消息内容判断严重程度
function handleServerError(msg: any) {
  const severe = /没有这张牌|内部错误|即将关闭|非法 JSON|缺少 type/;
  const fatal = /游戏已开始|座位已被占用/;
  if (fatal.test(msg)) {
    showError('无法加入', msg);
    setTimeout(() => (location.href = 'index.html'), 2000);
    return;
  }
  if (severe.test(msg)) {
    showError('出错了', msg);
    return;
  }
  toast(msg, 2000);
}

function renderPlayers() {
  const { playersEl } = networkRefs.ui;
  if (!playersEl) return;
  playersEl.textContent = '';
  const { currentTurn, phase, MY_SEAT } = gameState;
  for (let s = 0; s < 4; s++) {
    const p = gameState.playerInfo[s];
    const isTurn = s === currentTurn && phase === PHASE.PLAY;
    const isMe = s === MY_SEAT;
    const diceTxt = p.dice == null ? '—' : p.dice[0] + '+' + p.dice[1] + '=' + (p.dice[0] + p.dice[1]);

    const row = document.createElement('div');
    row.className = 'pl' + (isTurn ? ' turn' : '') + (p.disconnected ? ' disconnected' : '');

    const nm = document.createElement('div');
    nm.className = 'nm';
    const dirSpan = document.createElement('span');
    dirSpan.className = 'dir';
    dirSpan.textContent = DIR_NAME[s];
    nm.appendChild(dirSpan);
    nm.appendChild(document.createTextNode(p.name || '空位'));
    if (p.disconnected) {
      const disc = document.createElement('span');
      disc.className = 'me';
      disc.style.color = '#ff9a8a';
      disc.textContent = '(断线)';
      nm.appendChild(disc);
    } else if (isMe) {
      const me = document.createElement('span');
      me.className = 'me';
      me.textContent = '(你)';
      nm.appendChild(me);
    }
    row.appendChild(nm);

    const dice = document.createElement('div');
    dice.className = 'dice';
    dice.textContent = diceTxt;
    row.appendChild(dice);

    playersEl.appendChild(row);
  }
}

function setPhaseUI(p: any) {
  gameState.phase = p;
  const { statusText, diceCenter, dealCenter, discardBtn } = networkRefs.ui;
  statusText!.textContent = ({ waiting: '等待', dice: '骰子', deal: '发牌', play: '出牌' } as any)[p] || p;
  if (diceCenter) diceCenter.classList.remove('show');
  if (p !== PHASE.DEAL && dealCenter) dealCenter.classList.remove('show');
  if (p !== PHASE.PLAY && discardBtn) discardBtn.disabled = true;
}

// 更新"打出"按钮状态
// 直接使用 state.mjs 导出的 myTotalTiles, 删除 require_totalTiles/setMyTotalTilesFn 注入反模式
function updateDiscardBtn() {
  const { discardBtn } = networkRefs.ui;
  if (!discardBtn) return;
  discardBtn.disabled = !(
    gameState.phase === PHASE.PLAY &&
    gameState.currentTurn === gameState.MY_SEAT &&
    myTotalTiles() >= 14 &&
    interactionState.selected &&
    handState.myHand.includes(interactionState.selected)
  );
}

// ============ Claim Bar ============
let claimTimer: any = null;
const CLAIM_LABEL = { pong: '碰', kong: '杠', ckong: '暗杠', addKong: '续杠', win: '胡' };

function hideClaimBar() {
  const { claimBar, claimBtns } = networkRefs.ui;
  if (claimBar) claimBar.classList.remove('show');
  if (claimBtns) claimBtns.innerHTML = '';
  if (claimTimer) {
    clearInterval(claimTimer);
    claimTimer = null;
  }
}

function showClaimBar(buttons: any, subText: any, deadline: any) {
  const { claimBtns, claimBar, claimSub } = networkRefs.ui;
  if (!claimBtns || !claimBar || !claimSub) return;
  claimBtns.innerHTML = '';
  for (const b of buttons) {
    const el = document.createElement('button');
    el.textContent = b!.label;
    if (b!.cls) el.className = b!.cls;
    el.onclick = () => {
      hideClaimBar();
      b!.onClick();
    };
    claimBtns.appendChild(el);
  }
  claimBar.classList.add('show');
  const deadlineMs = deadline || Date.now() + 8000;
  const updateLeft = () => {
    const leftMs = deadlineMs - Date.now();
    const left = Math.max(0, Math.ceil(leftMs / 1000));
    claimSub!.textContent = subText + `（${left}s）`;
    if (left <= 0) hideClaimBar();
  };
  updateLeft();
  if (claimTimer) clearInterval(claimTimer);
  claimTimer = setInterval(updateLeft, 250);
}

// ============ Loader ============
let loaderHidden = false;
function hideLoader() {
  if (loaderHidden) return;
  loaderHidden = true;
  const { loader } = networkRefs.ui;
  if (loader) loader.classList.add('hide');
}

export {
  toast,
  showError,
  handleServerError,
  renderPlayers,
  setPhaseUI,
  updateDiscardBtn,
  hideClaimBar,
  showClaimBar,
  CLAIM_LABEL,
  hideLoader,
};
