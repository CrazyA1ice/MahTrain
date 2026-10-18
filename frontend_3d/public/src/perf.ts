// ============================================================
// ============================================================
// 用法 (main.mjs 主循环内):
//   import { perf } from './perf.ts';
//   perf.frameBegin();
//   perf.section('dice');   // ... 骰子同步代码 ...
//   perf.section('anim');   // ... 动画 update ...
//   perf.section('sync');   // ... mesh↔body 同步 ...
//   perf.section('render'); // ... renderer.render ...
//   perf.frameEnd();
//
// 自动行为:
//   - 每帧测量各 section 耗时, 累计到当前秒
//   - 每秒刷新浮层显示 FPS / 帧时间 / 各阶段平均耗时 / 内存
//   - 帧时间 > 30ms 时自动 console.warn 打印罪魁阶段 (含调用栈前 5 帧)
//   - 浮层可拖拽, 双击折叠/展开, 右键导出 CSV
// ------------------------------------------------------------

// 默认关闭, 仅在 URL 含 ?perf=1 时启用 (生产环境零开销, 调试时按需开启)
const PERF_ENABLED = (() => {
  try {
    const params = new URLSearchParams(location.search);
    return params.get('perf') === '1';
  } catch {
    return false;
  }
})();
const FRAME_BUDGET_MS = 16.67; // 60fps 预算
const FRAME_WARN_THRESHOLD_MS = 30; // 超过此值打印警告
const HISTORY_SIZE = 60; // 保留 60 秒历史

interface FrameSections {
  [name: string]: number;
}
interface CurFrame {
  start: number;
  sections: FrameSections;
  _curSec?: string | null;
  _secStart: number;
}
interface HistoryEntry {
  time: string;
  fps: number;
  fpsEma: number;
  frames: number;
  maxFrame: number;
  sections: FrameSections;
}
interface SlowFrame {
  time: number;
  total: number;
  sections: FrameSections;
}

interface PerfState {
  enabled: boolean;
  _curFrame: CurFrame | null;
  _secStart: number;
  _secFrames: number;
  _secSections: FrameSections;
  _secMaxFrame: number;
  _history: HistoryEntry[];
  _slowFrames: SlowFrame[];
  _hud: HTMLElement | null;
  _bars: HTMLElement | null;
  _folded: boolean;
  _fpsEma: number;
  _lastWarn?: number;
}

const perf: PerfState = {
  enabled: PERF_ENABLED,
  // 当前帧
  _curFrame: null,
  // 当前秒聚合
  _secStart: 0,
  _secFrames: 0,
  _secSections: {}, // {name: totalMs}
  _secMaxFrame: 0,
  // 历史秒 (用于看趋势)
  _history: [], // [{sec, fps, maxFrame, sections}]
  // 最近 N 个慢帧的详情 (用于归因)
  _slowFrames: [], // [{time, total, sections}]
  // DOM
  _hud: null,
  _bars: null,
  _folded: false,
  // FPS 平滑显示 (EMA)
  _fpsEma: 60,
};

// 扩展 window 上挂载的全局对象 (供 F12 控制台访问)
declare global {
  interface Window {
    __animCount?: number;
    __dirtyCount?: number;
    perf?: {
      summary: () => void;
      slowFrames: () => void;
      history: () => void;
      disable: () => void;
      enable: () => void;
    };
  }
}

// ============ 帧分段计时 ============
function frameBegin(): void {
  if (!perf.enabled) return;
  perf._curFrame = {
    start: performance.now(),
    sections: {}, // {name: ms}
    _secStart: 0,
  };
  // 秒聚合: 每秒重置一次
  const now = perf._curFrame.start;
  if (!perf._secStart) perf._secStart = now;
  if (now - perf._secStart >= 1000) {
    _flushSec();
    perf._secStart = now;
    perf._secFrames = 0;
    perf._secSections = {};
    perf._secMaxFrame = 0;
  }
}

function section(name: string | null): void {
  if (!perf.enabled || !perf._curFrame) return;
  // 闭合上一段
  const f = perf._curFrame;
  if (f._curSec) {
    f.sections[f._curSec] = (f.sections[f._curSec] || 0) + (performance.now() - f._secStart);
  }
  f._curSec = name;
  f._secStart = performance.now();
}

function frameEnd(): void {
  if (!perf.enabled || !perf._curFrame) return;
  // 闭合最后一段
  section(null);
  const f = perf._curFrame;
  const total = performance.now() - f.start;
  perf._curFrame = null;

  // 累计到当前秒
  perf._secFrames++;
  for (const k of Object.keys(f.sections)) {
    perf._secSections[k] = (perf._secSections[k] || 0) + f.sections[k];
  }
  if (total > perf._secMaxFrame) perf._secMaxFrame = total;

  // 慢帧归因
  if (total > FRAME_WARN_THRESHOLD_MS) {
    perf._slowFrames.push({ time: Date.now(), total, sections: { ...f.sections } });
    if (perf._slowFrames.length > 20) perf._slowFrames.shift();
    // 控制台实时打印 (限频: 同一秒内最多 3 条, 避免刷屏)
    const now = Date.now();
    if (!perf._lastWarn || now - perf._lastWarn > 333) {
      perf._lastWarn = now;
      const sorted = Object.entries(f.sections).sort((a, b) => b[1] - a[1]);
      const top = sorted
        .slice(0, 3)
        .map(([k, v]) => `${k}=${v.toFixed(1)}ms`)
        .join(' ');
      console.warn(
        `[perf] 慢帧 ${total.toFixed(1)}ms (预算 ${FRAME_BUDGET_MS}ms) | TOP: ${top} | anims=${window.__animCount ?? '?'} dirty=${window.__dirtyCount ?? '?'}`
      );
    }
  }
}

// ============ 秒级聚合 ============
function _flushSec(): void {
  const sec = (performance.now() - perf._secStart) / 1000;
  const fps = perf._secFrames / sec;
  // EMA 平滑
  perf._fpsEma = perf._fpsEma * 0.7 + fps * 0.3;
  const sections: FrameSections = {};
  for (const k of Object.keys(perf._secSections)) {
    sections[k] = perf._secSections[k] / perf._secFrames; // 每帧平均
  }
  const entry: HistoryEntry = {
    time: new Date().toISOString().slice(11, 19),
    fps: Math.round(fps),
    fpsEma: Math.round(perf._fpsEma),
    frames: perf._secFrames,
    maxFrame: perf._secMaxFrame,
    sections,
  };
  perf._history.push(entry);
  if (perf._history.length > HISTORY_SIZE) perf._history.shift();
  _updateHud(entry);
}

// ============ HUD 浮层 ============
function _buildHud(): void {
  if (perf._hud) return;
  const hud = document.createElement('div');
  hud.id = 'perf-hud';
  hud.style.cssText = `
    position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
    z-index: 9999; background: rgba(0,0,0,.85); color: #0f0;
    font-family: 'Sarasa Mono SC', 'Consolas', monospace; font-size: 11px;
    line-height: 1.5; padding: 8px 12px; border: 1px solid #0f0;
    border-radius: 6px; pointer-events: auto; user-select: none;
    cursor: move; min-width: 320px; backdrop-filter: blur(4px);
    box-shadow: 0 4px 16px rgba(0,0,0,.5);
  `;
  hud.innerHTML = `
    <div id="perf-head" style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #0f04;padding-bottom:4px;margin-bottom:6px;cursor:pointer">
      <b style="color:#0f0">PERF MONITOR</b>
      <span id="perf-fold" style="color:#888;font-size:10px">[双击折叠]</span>
    </div>
    <div id="perf-body">
      <div id="perf-summary"></div>
      <div id="perf-bars" style="margin-top:6px"></div>
      <div id="perf-mem" style="margin-top:6px;color:#888;font-size:10px"></div>
      <div id="perf-slow" style="margin-top:6px;color:#f80;font-size:10px;max-height:80px;overflow:auto"></div>
    </div>
  `;
  document.body.appendChild(hud);
  perf._hud = hud;

  // 拖拽
  let dragging = false;
  let dx = 0,
    dy = 0;
  hud.addEventListener('mousedown', (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.tagName === 'B' || target.id === 'perf-fold' || target.id === 'perf-head') {
      dragging = true;
      const rect = hud.getBoundingClientRect();
      dx = e.clientX - rect.left;
      dy = e.clientY - rect.top;
      hud.style.transform = 'none';
      hud.style.left = rect.left + 'px';
      hud.style.top = rect.top + 'px';
      e.preventDefault();
    }
  });
  document.addEventListener('mousemove', (e: MouseEvent) => {
    if (!dragging) return;
    hud.style.left = e.clientX - dx + 'px';
    hud.style.top = e.clientY - dy + 'px';
  });
  document.addEventListener('mouseup', () => {
    dragging = false;
  });

  // 双击折叠
  const head = hud.querySelector('#perf-head') as HTMLElement;
  head.addEventListener('dblclick', () => {
    perf._folded = !perf._folded;
    (hud.querySelector('#perf-body') as HTMLElement).style.display = perf._folded ? 'none' : 'block';
    (hud.querySelector('#perf-fold') as HTMLElement).textContent = perf._folded ? '[展开]' : '[双击折叠]';
  });

  // 右键导出 CSV
  hud.addEventListener('contextmenu', (e: MouseEvent) => {
    e.preventDefault();
    _exportCsv();
  });
}

function _updateHud(entry: HistoryEntry): void {
  _buildHud();
  const hud = perf._hud;
  if (!hud) return;

  // summary
  const fpsColor = entry.fpsEma >= 55 ? '#0f0' : entry.fpsEma >= 40 ? '#ff0' : '#f44';
  const maxColor = entry.maxFrame <= 20 ? '#0f0' : entry.maxFrame <= 40 ? '#ff0' : '#f44';
  (hud.querySelector('#perf-summary') as HTMLElement).innerHTML = `
    <span style="color:${fpsColor}"><b>FPS: ${entry.fpsEma}</b></span>
    <span style="color:#888;margin-left:12px">raw: ${entry.fps}</span>
    <span style="color:${maxColor};margin-left:12px">max: ${entry.maxFrame.toFixed(1)}ms</span>
    <span style="color:#888;margin-left:12px">frames: ${entry.frames}</span>
  `;

  // bars: 各阶段平均耗时
  const sorted = Object.entries(entry.sections).sort((a, b) => b[1] - a[1]);
  const maxMs = Math.max(0.1, ...sorted.map((s) => s[1]));
  const barsHtml = sorted
    .map(([k, v]) => {
      const pct = (v / maxMs) * 100;
      const color = v > 10 ? '#f44' : v > 5 ? '#ff0' : '#0f0';
      return `<div style="display:flex;align-items:center;gap:6px;margin:1px 0">
        <span style="color:#888;width:60px">${k}</span>
        <div style="flex:1;background:#222;height:10px;border-radius:2px;overflow:hidden">
          <div style="width:${pct}%;height:100%;background:${color}"></div>
        </div>
        <span style="color:${color};width:50px;text-align:right">${v.toFixed(2)}ms</span>
      </div>`;
    })
    .join('');
  (hud.querySelector('#perf-bars') as HTMLElement).innerHTML = barsHtml || '<div style="color:#888">无分段数据</div>';

  // 内存 (Chrome only)
  const perfMem = (
    performance as unknown as { memory?: { usedJSHeapSize: number; totalJSHeapSize: number; jsHeapSizeLimit: number } }
  ).memory;
  if (perfMem) {
    const m = perfMem;
    const used = (m.usedJSHeapSize / 1024 / 1024).toFixed(1);
    const total = (m.totalJSHeapSize / 1024 / 1024).toFixed(1);
    const limit = (m.jsHeapSizeLimit / 1024 / 1024).toFixed(0);
    const memColor = parseFloat(used) > 100 ? '#f44' : parseFloat(used) > 50 ? '#ff0' : '#888';
    (hud.querySelector('#perf-mem') as HTMLElement).innerHTML = `
      <span style="color:${memColor}">mem: ${used}MB / ${total}MB (limit ${limit}MB)</span>
    `;
  } else {
    (hud.querySelector('#perf-mem') as HTMLElement).textContent = 'mem: N/A (Firefox/Safari)';
  }

  // 慢帧归因 (最近 3 个)
  const slowHtml = perf._slowFrames
    .slice(-3)
    .map((f) => {
      const top = Object.entries(f.sections)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 2)
        .map(([k, v]) => `${k}=${v.toFixed(1)}`)
        .join(' ');
      const time = new Date(f.time).toISOString().slice(11, 19);
      return `<div>${time} ${f.total.toFixed(1)}ms ← ${top}</div>`;
    })
    .join('');
  (hud.querySelector('#perf-slow') as HTMLElement).innerHTML = slowHtml ? '慢帧: ' + slowHtml : '';
}

// ============ CSV 导出 ============
function _exportCsv(): void {
  const firstSections = perf._history[0]?.sections || {};
  const rows: (string | number)[][] = [['time', 'fps', 'fpsEma', 'maxFrame', ...Object.keys(firstSections)]];
  for (const h of perf._history) {
    rows.push([
      h.time,
      h.fps,
      h.fpsEma,
      parseFloat(h.maxFrame.toFixed(2)),
      ...Object.values(h.sections).map((v) => parseFloat(v.toFixed(3))),
    ]);
  }
  const csv = rows.map((r) => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `perf-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  console.log('[perf] 已导出 CSV, 共', perf._history.length, '秒数据');
}

// ============ 控制台 API ============
// 在 F12 控制台输入:
//   perf.summary()      // 打印最近 10 秒汇总
//   perf.slowFrames()   // 打印所有慢帧详情
//   perf.history()      // 打印完整历史
//   perf.disable()      // 关闭监控
//   perf.enable()       // 开启监控
window.perf = {
  summary: () => {
    console.table(perf._history.slice(-10));
  },
  slowFrames: () => {
    console.table(perf._slowFrames);
  },
  history: () => {
    console.table(perf._history);
  },
  disable: () => {
    perf.enabled = false;
    if (perf._hud) perf._hud.style.display = 'none';
    console.log('[perf] 已关闭');
  },
  enable: () => {
    perf.enabled = true;
    if (perf._hud) perf._hud.style.display = 'block';
    console.log('[perf] 已开启');
  },
};

export { perf, frameBegin, section, frameEnd };
