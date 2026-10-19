# M3.72 · Windows localhost WinError 10053 / 10054 客户端断开修复

## 触发场景与根本原因

Windows Python 的 `ThreadingHTTPServer` 正在响应 `GET /api/match_archives`（历史对局列表）或其余页面/JSON 请求时，浏览器提前取消 HTTP 请求、关闭页面、刷新、关闭浏览器，或者防火墙/安全软件终止已建立的本地连接。旧 `web_server.py` 直接调用 `self.wfile.write(data)`，没有区分客户端主动断开和服务端异常，因此标准库向控制台输出大段回溯，例如：

```text
ConnectionAbortedError: [WinError 10053] 你的主机中的软件中止了一个已建立的连接。
```

这类异常说明**本次 HTTP 响应没有送达客户端**，**不能凭此判断 Mahjong 对局、SQLite 数据库或规则计算已损坏**；也不代表 Windows 防火墙一定有问题。

## 修改

1. `Handler._respond` 仅在 HTTP 输出时吞掉符合条件的正常对端断开：`BrokenPipeError`、`ConnectionResetError`、`ConnectionAbortedError`，以及 Windows socket 的 `10053`（连接中止）、`10054`（连接重置）、`10058`（套接字关闭）。关闭该连接，结束这次响应，不再由标准库打印堆栈。
2. 只屏蔽**这些预期的网络断开**；文件读写、SQLite、非法 JSON、业务逻辑异常，以及其他未知 `OSError` 会照旧反馈或抛出，不做大范围 `except Exception: pass`。如果浏览器真的没有收到数据，它仍应自己重新发起只读 GET；服务器不会擅自重试可能已经执行的出牌等 POST 命令。
3. `/api/match_archives`、`/api/history` 和 `/api/state` 先持有 `_LOCK` 完成必要读取和快照，再离开锁对客户端写入 JSON 字节，避免浏览器下载/取消慢连接时持有全局锁，干扰正在进行的 AI 牌局。
4. `tests/test_http_disconnect.py` 使用可重现的模拟断开，包括 WinError 10053、10054、10058 和 Python 的管道/重置异常，验证普通响应头/数据正常，非预期错误仍抛出，历史接口发送时已释放全局锁。

## 用户操作

在原 MahTrain 仓库执行：

```powershell
git pull origin main
# 退出旧的 Python 服务（Ctrl+C），然后重新启动新代码：
python web_server.py
```

已打开的网页用 `Ctrl+F5` 刷新。这里需要**重启 Python 进程**，单独刷新浏览器不会使旧 `Handler._respond` 替换为新代码。

若仍有网络故障，请留意浏览器 `Network` 面板中是 `GET /api/match_archives` 被取消还是 `POST /api/action` 实际失败。当前修复只让已取消连接的服务端日志安静并缩短锁持有时间，**不保证安全软件不会继续主动断开 TCP 连接**；如果服务器报的是非连接中止异常，应保留新的 traceback 继续定位。

## 验收

- `python -m unittest tests.test_http_disconnect -v`（或 `python -m unittest discover -s tests -p test_http_disconnect.py -v`）
- GitHub Actions `Sichuan Rules Kernel Tests` 的 Python 3.11 / 3.13 `Run no-dependency unit tests`，以及已有 HTTP 页面/规则回归。
