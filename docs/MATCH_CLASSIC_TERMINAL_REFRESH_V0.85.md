# M3.74 · 经典麻将结束后刷新不丢失胡牌与结算

## 本轮发现并修复的用户可见问题

旧的 `frontend_2d/src/main.js` 在 `store()` 中执行：

```js
if(token&&state&&!DONE.has(state.phase))sessionStorage.setItem(SESSION_KEY,token);
else sessionStorage.removeItem(SESSION_KEY);
```

只要牌局刚进入 `finished` 或 `wall_exhausted`，应用就把该局的会话令牌删除。**结果是对局一结束，用户刚看过胡牌、杠钱、流局收支，按 F5 / Ctrl+F5 就会重新创建另一局，而无法恢复前一局的完整结算。**此前某个终局测试每次加载都会把测试令牌重新注入到 sessionStorage，掩盖了此缺陷。

现在只在没有有效令牌或状态时移除存储，**已结束的游戏仍留在同一标签页的 sessionStorage**。只有用户明确按「再来一局」并成功收到新局令牌，才替换旧的令牌。浏览器正常刷新使用服务端 `match_resume` 只读获取终局数据。

这保证：

- 真实胡牌后四家固定座位的「已胡」常驻标记不会因刷新丢失；
- 从 Python `win_ledger`、`kong_ledger`、`exhaustive_settlement` 读取的四家番型、杠钱和最终收支仍能恢复；
- 牌桌继续固定，不恢复上方动态弃牌条，不添加任何额外动画；
- 用户主动开始新局才清除旧局胡牌标志和结束结算，更新至新局会话。

## 验收

1. `frontend_2d/test/browser-finished-refresh.mjs`：真实 Chromium + 原版 Majiang UI，模拟权威已结束状态，检查胡牌/番型/收支与真实 DOM 显示，按 F5 后继续保持同一局，**确认没有任何 `match_new`**；主动点「再来一局」才从服务端获得新 token，旧胡牌标志清理、新牌桌维持相同几何，刷新后重新打开该新局。
2. `frontend_2d/test/browser-real-round.mjs`：此前实际通过 Python HTTP 跑完的四川血战真实对局，测试从会话令牌**仅一次初始化**、F5 后必须由应用自持的令牌恢复，逐家核对胡牌番型、杠钱与净收支，同时验证请求始终只有 `match_resume`。防止测试每次注入同一令牌而产生误报。
3. 保持 `browser-smoke.mjs`、`browser-fixed-table.mjs`、`browser-settlement.mjs` 和全部 Node 单元测试回归。

## 操作

```powershell
cd D:\ChatGPT\MahTrain
git pull origin main
# 结束当前旧 Python 服务并重启
python web_server.py
```

打开 `http://127.0.0.1:8765/classic/game.html`，用 Ctrl+F5 强制刷新前端资源。

注意：使用的是 `sessionStorage`，这保障**同一标签页的刷新恢复**；关闭整个标签页后是否能恢复由浏览器会话恢复策略决定，不属于跨设备/长期云端归档功能。对于在修复前已经被旧前端删除的历史 token，不能凭这次修改自动恢复，可继续查阅游戏历史归档。不会声称具备永久保存能力。
