# M3.70 · 经典麻将公开动作提示及对局结束自动结算

## 本轮对现有 Majiang UI 做了什么

这轮保留上游开源 [kobalab/majiang-ui](https://github.com/kobalab/majiang-ui) 的所有真实牌面、手牌、牌河、副露和桌面布局，不重新自绘麻将前端。仅新增读服务器公开事件的`frontend_2d/src/event-feedback.mjs` 和独立反馈区。

- **实时动作提示**：三家 AI 或玩家公开弃牌时显示哪家打出了哪张牌；碰、明杠、暗杠、补杠有对应短提示及行动玩家名字短暂高亮。
- **胡牌反馈**：以 Python `win_ledger.wins` 已入账的记录优先显示每位胡牌人、主番型和实际实收；一炮多响列出全部胡牌玩家并高亮各自座位。若已有公开胡事件但本次状态中没有新增入账记录，仍按公开事件作不含虚构积分的动作提示。
- **位置安全**：动作反馈条在牌桌外、胡牌记录下方；姓名牌只做颜色高亮，不能在手牌、牌河、副露上弹窗。桌面缩放会考虑条幅占高，条幅消失后自动恢复可用牌桌尺寸。
- **与 AI 解耦**：提示时长约 1～1.65 秒，用独立定时器控制；不会延长后端 `match_continue`，也不会等待语音播放。系统设置减少动态效果时禁用动画，保留静态文字反馈。
- **对局结束**：仅当已有对局从非终局实际转为 `finished` 或 `wall_exhausted` 才自动滚动至上轮完成的四家账本。重新进入旧终局或刷新后执行只读 `match_resume` 不会触发误导性的“新结束局”动画或主动滚动。

## 安全与计分约束

客户端只会接收经过 Python 发布的公开 `public_steps` 和带 server 账本校验的 `win_ledger`；不能读对手隐藏手牌、未来牌墙或私有 AI 合法动作。未确认的补杠声明 `bu_gang_declared` 不能当作真实杠结算动画；等 `bu_gang` 成功发布再出现杠提示。胡牌、杠钱和流局的账本都由 Python 统一计算，这轮不改动核心规则。

## 自动验收

- `frontend_2d/test/event-feedback.test.mjs`：合法公开弃牌中文播报、碰牌归属、三种杠牌、一炮多响两赢家、未确认补杠不报喜、恢复不重复、隐私校验。
- `frontend_2d/test/browser-settlement.mjs`：真实 Chromium 测试在模拟的正式双赢家结算数据上检测两家高亮、失败方无高亮、动作栏不盖住牌桌、自动滚动至结算区。
- `frontend_2d/test/browser-smoke.mjs`：仍使用真实 Python 开局、换三张、定缺。
- 构建产物由 `.github/workflows/majiang-2d.yml` 更新至 `frontend_2d/dist`，因此用户只需在本地 `git pull origin main` 并运行 `python web_server.py`。

## 尚未覆盖的地方

浏览器完成三家胡完、最后一张流局，真实 AI 全局跑到终局的所有边界，还有进一步的实际长局完整验收空间。此轮的终局 browser fixture 是服务器字段的可重现测试数据，不能把它误称成已实测全部真实牌局。
