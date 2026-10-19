# M3.68 · 正式采用 E 方案：kobalab/Majiang 经典 2D 牌桌

## 这是实际接入已有前端，不是自己重新画风格

**上游库：** https://github.com/kobalab/majiang-ui ，`@kobalab/majiang-ui@1.6.1`，作者 Satoshi Kobayashi，MIT。
**完整原游戏：** https://github.com/kobalab/Majiang ，`2.5.4` 原版桌面布局及 GIF 实体牌面，MIT。

在 `frontend_2d/src/main.js` 中直接使用下列上游源码实现：

- `@kobalab/majiang-ui/lib/pai.js`：原版麻将牌面克隆器（不是自写图片组件）。
- `@kobalab/majiang-ui/lib/shoupai.js`：四家手牌及原版 `mianzi` 碰杠副露排版器。
- `@kobalab/majiang-ui/lib/he.js`：牌河。
- `frontend_2d/upstream-css/*.styl`：原版桌布、四向坐席、手牌与牌河、桌面 800×680 布局、横屏平板版，直接保留原始 8 个 Stylus 文件并采用 Stylus 0.64.0 构建。
- `frontend_2d/assets/img/*.gif`：从 Majiang 原仓库 `dist/img` 原样复制的 27 张万筒条实体牌图，以及 `pai.gif` 牌背。MIT 原始声明分别附于 `frontend_2d/LICENSE-MAJIANG.txt` 和 `LICENSE-MAJIANG-UI.txt`。

这是完整集成真实 Majiang 的核心**视觉组件与原版桌面排布**，并非独立重写相同外观。但不导入上游 `UI.Player` 或日麻规则引擎：因为该类直接使用立直、吃牌、日麻番种判定，与无吃牌的四川血战冲突。独立 `bridge.mjs` 只负责 MahTrain 状态 → UI 数据模型 / 合法服务器动作映射。

## 入口和启动

更新仓库后，原有命令即可运行：

```bash
git pull origin main
python web_server.py
```

进入 `http://127.0.0.1:8765/` → **四人血战 → 开始经典 2D 血战（Majiang UI）**。或者直接访问 `http://127.0.0.1:8765/classic/game.html`。

本版本已经将 Vite 真正构建产物 `frontend_2d/dist/game.html`、JS/CSS、28 张 GIF 图片提交到仓库，因此用户直接运行 Python 即可，无需安装 Node 或启动原 Majiang 网络服务器。

如需升级上游版本或修改适配代码：

```bash
cd frontend_2d
npm install
npm run test:bridge
npm run build
```

## 四川血战适配

- 游戏服务器仍是 MahTrain Python `/api/action`；不会引用日麻规则、日麻计分或外部联机服务器。
- 同一标签页使用 `mahtrain.match.session.v1` 会话 token。掉线后通过 **只读 match_resume** 恢复，出牌网络异常不重复执行可能已提交的命令。
- 四家暗手使用数量构建 Majiang `Shoupai._bingpai._` 牌背，**不能读取或猜测对手的实体暗牌**。
- 公开碰杠调用原 `mianzi`；未知的对手暗杠统一覆盖为原版牌背，不展示虚构的花色/点数。
- 各家使用原 `He` 展示弃牌，14列×4行固定 56 个位置；已被碰走的弃牌仍占据原有实体格位，视觉隐藏而不把后续牌向前挤。
- 真实摸牌独立在手牌最右边。每张实体牌使用其对应的原始手牌索引而不是仅以牌值标识；两张同牌不会混淆摸切/手切。
- 中央互动安全区只在换三张、定缺、碰杠胡、胡牌及本局结束时显示；它精确占据原 Majiang 的中央计分区，**不覆盖底边手牌、牌河及副露**。
- 桌面保留 Majiang 原有 800×680 几何，浏览器 100% 缩放时按视口等比例整体缩放而不是裁切牌河。原版布局的麻将牌较经典；这一轮不再额外叠加“科技风”皮肤。

## 自动验收

GitHub Actions 的 `majiang-2d.yml`：

1. 安装真正的 `@kobalab/majiang-ui@1.6.1` + Stylus + Vite，并成功编译。
2. 运行纯 Node 隐私/牌河/副露/摸切/碰杠合法动作单测。
3. 检查 28 张原生 GIF、编译产物和 Python 静态路径严格白名单。
4. **真实 Chromium、真实 MahTrain Python API**：启动新局、展示4家手牌和 4 家 Majiang `He`、实际点击三张同色牌并换三张、进入定缺后实际定缺、归档2张真实浏览器截图。
5. 成功后将 `frontend_2d/dist/` 的编译产物提交回开发分支，再合并主分支。

### 验证边界

当前优先验证完整的视觉接入、换三张、定缺与基础操作映射。尚未把所有血战杠、抢杠胡、胡牌结算及最晚极端 56 格牌河做全场景浏览器自动交互覆盖，也暂时沿用 MahTrain 后端 AI 决策延迟（可能超过1.5秒）。这次不宣称接入日本麻将全部功能或复制原 Majiang 网络大厅。
