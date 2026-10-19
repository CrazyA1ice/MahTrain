# M3.71 · 经典 Majiang UI 真实完整对局验收与七对番型中文显示

## 本轮确实执行过什么

与以前仅在浏览器里使用手写终局快照的测试不同，`frontend_2d/test/full_round_http.py` 使用 MahTrain **真实 Python HTTP 服务**（`/api/action`）连续完成多局四人四川血战。在标准 108 张麻将牌、真实 `MahjongAgent`、玩家端只持有自己授权视图的约束下，依次执行：

1. 真实创建随机种子对局（固定种子用于可复现测试，不改变产品每局默认随机种子）；
2. 从仅属于玩家0的手牌选择三张同花色牌，4家完成换三张，选择定缺；
3. 轮到玩家0时通过已授权手牌调用真实合法 AI 切法，必要时自摸或杠；响应窗口只在服务端给出合法选项时请求胡或过；
4. AI 通过服务器 `match_continue` 逐动作推进，**从不提供或读取任何其他三家暗手、未来牌墙**；
5. 直到 `finished` 或 `wall_exhausted`，验证所有胡牌、杠牌和流局赔付、四家最终余额及零和关系，检查正式归档 ID；
6. 将终局 token 和包含玩家私有手牌的正式服务器快照暂存在 CI 主机的 **/tmp 临时文件**，只供同一次作业的 Chromium 只读恢复使用，**不打包到公开的截图 Artifacts 中**。

测试的后半程由 `frontend_2d/test/browser-real-round.mjs` 打开真实 Chromium/原版 Majiang UI，通过**合法只读 `match_resume`** 从同一个 Python 服务恢复已经实际完成的牌局，检查四家页面上的番型、胡牌收支、杠钱、流局收入和总计与真实账本完全一致。再次刷新，确认不会重复出牌或重复播报历史动画。保存实际页面结算截图。

## 发现并修复的问题

真实测试发现一项明确的界面问题：真实 Python 胡牌记录使用 `seven_pairs`、`pure_suit`、`tian_ting` 等内部英文标识，上一轮 UI 把这些标识直接展示给用户。现在新增 **只用于显示** 的 `patternLabel`：

- `seven_pairs` → 七对；`pure_seven_pairs` → 清七对；`dragon_seven_pairs` → 龙七对；`pure_dragon_seven_pairs` → 清龙七对；
- `pure_suit` → 清一色；`all_pungs` → 对对胡；`pure_all_pungs` → 清对对胡；`golden_hook` → 金钩钓；
- `heaven_win` → 天胡；`earth_win` → 地胡；`tian_ting` → 天听；
- `kong_bloom` → 杠上花；`kong_discard_ron` → 杠上炮；`rob_added_kong` → 抢杠胡；
- `sea_bottom_draw` → 海底捞月；`river_bottom_ron` → 海底炮；`roots` → 根。

这些只是字面翻译，**不改变任何后端胡牌倍率或封顶规则**。Majiang 的原始牌面、桌布、牌河、副露渲染均没有重写。

## 本轮证据与边界

- `frontend_2d/test/full_round_http.py`：至少两局完整真实网络对局的后端账本审计，并尽可能扩大真实胡牌样本；
- `frontend_2d/test/browser-real-round.mjs`：从**真正的终局会话**恢复原版 Majiang UI，逐格核对净收益、中文番型及只读恢复行为；
- `frontend_2d/test/settlement.test.mjs`：覆盖全部实际四川规则内部番型和加成显示；
- `.github/workflows/majiang-2d.yml`：共享同一个临时服务实例完成对局并立刻在 Chromium 恢复；保证前后账本一致。

此测试涵盖真实自摸及杠钱时，对其他稀有场景（抢杠胡、一炮多响、流局所有赔付组合）仍需继续构造可复现的**真实服务端情境**，不能因前端已有模拟 fixture 就把它们宣称全部实战覆盖。本版本强调诚实记录未覆盖的条件和真实账本。

## 本地使用

```bash
git pull origin main
python web_server.py
```

访问 `http://127.0.0.1:8765/classic/game.html`，前端编译资源已随仓库提交，直接使用原版开源 Majiang UI。
