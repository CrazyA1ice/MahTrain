// ============================================================
// lobby.ts — 房间预览页面 (选座)
// ============================================================
const EL_SEAT_NAME = ['南', '西', '北', '东'];
let mySeat = -1;
interface SeatInfo {
  name?: string | null;
}
let roomSeats: (SeatInfo | null)[] = [null, null, null, null];

// 只读预览连接: 订阅房间状态 (不占座)
const proto = location.protocol === 'https:' ? 'wss' : 'ws';
// Vite dev 模式 (5173) 下直接连 8080 端口的 WebSocket 服务
// 生产/test:manual 模式下用同源 (location.host)
const isViteDev =
  typeof import.meta !== 'undefined' &&
  (import.meta as { env?: { DEV?: boolean } }).env !== undefined &&
  !!(import.meta as { env?: { DEV?: boolean } }).env?.DEV;
const wsHost = isViteDev ? `${location.hostname}:8080` : location.host;
const ws = new WebSocket(`${proto}://${wsHost}`);

function renderSeats(): void {
  const box = document.getElementById('seats') as HTMLElement;
  box.innerHTML = '';
  for (let i = 0; i < 4; i++) {
    const s = roomSeats[i];
    const taken = !!(s && s.name);
    const el = document.createElement('div');
    el.className = 'seat' + (taken ? ' taken' : '') + (i === mySeat ? ' me' : '');
    // 安全: 用 DOM API 而非 innerHTML 拼接, 避免玩家名包含 HTML 注入
    const dirDiv = document.createElement('div');
    dirDiv.className = 'dir';
    dirDiv.textContent = EL_SEAT_NAME[i];
    const whoDiv = document.createElement('div');
    whoDiv.className = 'who';
    whoDiv.textContent = taken ? s!.name! : '空 位';
    el.appendChild(dirDiv);
    el.appendChild(whoDiv);
    el.onclick = () => {
      if (taken) return;
      mySeat = i === mySeat ? -1 : i;
      updateGo();
      renderSeats();
    };
    box.appendChild(el);
  }
}

function updateGo(): void {
  const name = (document.getElementById('name') as HTMLInputElement).value.trim();
  const ok = !!name && mySeat >= 0 && !roomSeats[mySeat]?.name;
  (document.getElementById('go') as HTMLButtonElement).disabled = !ok;
  (document.getElementById('tip') as HTMLElement).textContent = ok
    ? `将以「${name}」坐在${EL_SEAT_NAME[mySeat]}位`
    : '输入名字并选择座位后进入';
}

ws.onmessage = (ev: MessageEvent) => {
  const m = JSON.parse(ev.data as string) as { type: string; seats: (SeatInfo | null)[] };
  if (m.type === 'roomState') {
    roomSeats = m.seats;
    // 若我选的座已被别人抢走
    if (mySeat >= 0 && roomSeats[mySeat] && roomSeats[mySeat]!.name) mySeat = -1;
    renderSeats();
    updateGo();
  }
};
ws.onopen = () => {
  /* 服务器在连接时自动发 roomState */
};

(document.getElementById('name') as HTMLInputElement).addEventListener('input', updateGo);

(document.getElementById('go') as HTMLButtonElement).addEventListener('click', () => {
  const name = (document.getElementById('name') as HTMLInputElement).value.trim() || '玩家';
  if (mySeat < 0) return;
  // 不在此连接占座 —— 直接跳转到游戏页, 真正占座在 game.html 完成
  location.href = `game.html?seat=${mySeat}&name=${encodeURIComponent(name)}`;
});

(document.getElementById('ipnote') as HTMLElement).textContent = `服务器: ${location.host}`;
renderSeats();
