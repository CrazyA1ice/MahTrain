# MahTrain M3.67 · 接入真正的第三方 3D 麻将前端

## 采用的开源产品
- **雀局 · 联机麻将**，作者 Aixineiar，项目地址：https://github.com/Aixineiar/queju_mahjong
- 精确上游版本：`3db63bd3c3bc4076950dca2cabcbdafe93eddcb1`
- 原代码许可：MIT，保留 `frontend_3d/LICENSE` 与 `frontend_3d/NOTICE`。
- 实际移植范围：`frontend_3d/public/src/scene.ts` / `board.ts` / `animation/*` / `interaction.ts` / `tile-factory.ts`、完整 `public/game.html`、`proto/protocol.mjs` 以及其余真实运行依赖源码。使用源项目的 **Three.js WebGL 实体牌桌、四边牌墙、暗牌和副露、光照、视角、操作与动画**。不是手写另一套同风格 HTML 或 CSS。
- 本项目 `frontend_3d/public/src/mahtrain-protocol.mjs`、`mahtrain-bridge.ts` 只负责 **状态映射、Python HTTP 命令与血战特有的换三张/定缺**，不会复制上游的联机计分规则，也不会更换 MahTrain 现有 AI。
- 原仓库近 1 MB 的 `public/assets/tiles-atlas.png` 因连接器无法取得可靠二进制内容，**未被导入**。MahTrain 模式在上游 `tex.ts` 自有的 Canvas 程序化麻将牌面上运行，后续若取得经授权原素材可完整替换。本项目并未导入任何商业天凤美术。

## 操作
在 MahTrain 仓库根目录运行原来的 Python 服务：

```bash
python web_server.py
```

打开 `http://127.0.0.1:8765/`，切换到「四人血战」，点击 **开始 3D 血战（雀局成熟前端）**。或者访问：

`http://127.0.0.1:8765/3d/game.html?mahtrain=1&seat=0&name=MahTrain`

构建后的 HTML/JS/CSS 已随代码存放在 `frontend_3d/dist/`；运行游戏不再要求额外的 Node 开发服务器，也不连接雀局原先的 WebSocket 对局服务。原 2D UI 保留为备用入口。

若要修改或升级上游源码：

```bash
cd frontend_3d
npm install
npm run test:bridge
npm run build
```

运行新版本测试 `.github/workflows/queju-3d.yml`，包含真实 Chrome / Three.js WebGL 加载、四人牌桌、一次完整的换三张和定缺 HTTP 对话，并归档截图。

## 数据边界与玩法
- MahTrain Python `FourPlayerOpening` 仍是游戏**唯一规则与胜负结算权威**；三家 AI 仍由原 Python `MahjongAgent` 驱动。3D 端无牌局规则权力。
- 只将**己方真实手牌、别人的暗手张数、已公开副露/牌河、剩余牌墙数量**送给 Three.js；没有对手私牌，也没有真实未揭示的牌墙顺序。
- 三套花色及 108 张制：三人对手加自己组成四人局；3D 示意牌墙按每侧14叠共112物理位置绘制，其中多出4张视为已消耗，实际剩余牌数完全取自 Python。
- 服务器被碰杠取走的弃牌映射为空位置（不会重新产生鬼牌）。从座位0到3的旋转映射是 `[0,3,2,1]`；暗杠若未公开，一律保留牌背。
- `match_new` / `match_resume` / `match_exchange` / `match_missing` / `match_continue` / `match_discard` / `match_claim` / `match_rob` / `match_kong` / `match_win` 通过已存在的、经过身份验证的 `/api/action` 处理。
- 真正点击 Three.js 手牌触发弃牌；闭门策略、合法碰杠胡等由服务端判定。前端仅暴露经服务端提供的响应选项。
- 发送 HTTP 断线后**先只读恢复、不会盲目重试出牌**，杜绝同一张牌重复切出。
- 换三张、定缺操作为四川血战专有：暂置于成熟 3D 页面原有控制区中，不会覆盖在手牌上；将来可改用原上游 `centerBtn` 容器，前提是实际浏览器证实不会遮挡牌河。

## 局限与后续
1. 源游戏原本采用 WebSocket 动画事件，当前 MahTrain 通过 Python **权威状态快照**重建牌桌，功能与隐私优先；3D 出牌等动画是原项目自带的，而服务器 AI 的动作未全部流式播放原始飞牌动画。下一阶段可利用已有公开 `public_steps` 增加逐动作动画适配，而不是重写 CSS。
2. 当前接入先验证 1280×800 WebGL 浏览器和核心流程；未声称已在手机、全部杠/胡/流局分支上完成全场景回归。
3. **性能上限**：HTTP AI 决策和网络不可保证1.5秒内；前端没有主动等待语音录音完毕才出牌。后续由统一动作队列支持既有语音设置。
4. 不把原上游游戏服务端打包或使用其麻将规则；不同规则的新增功能必须在 MahTrain 原 Python 后端实现。

## 回退与回归
旧 `web/match.js`、`web/app.css`、`web/match_table_v2.css` 目前不再是新版 3D 渲染基础，仅作为功能回退而保留。任何维护不能把该旧 CSS 叠加到 WebGL 牌桌上。
