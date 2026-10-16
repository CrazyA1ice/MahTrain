# MahTrain M3.15：右侧摸牌、听口、摸切手切、AI 胡牌提示（v0.27）

## 本轮新增功能

1. 本人刚摸到的牌独立放在手牌最右边，金色描边并写明“摸牌”；点击这张牌为摸切，点击原本手牌为手切。同牌多副本通过前端显式 from_draw 参数区分。未摸牌的庄家起手切牌与碰牌后出牌均是手切。
2. 听牌提示使用项目原有 winning_tiles。本人13有效张时显示真实结构听口；本人14有效张准备切牌时显示“切哪张→听哪些牌”。提示只来自本人的暗手、本人副露及已公开定缺，不依赖 AI 暗牌，不承诺未知墙牌还剩几张。
3. AI 背牌一条不换行：顶部 AI 牌背横向排成一行，左右 AI 牌背纵向排列为一条连续单列。
4. 四家牌河真实弃牌增加“摸切/手切”标签；类型由规则引擎在出牌发生时公开记录，而不是前端尝试查看对手摸到什么。
5. AI 胡牌后，牌桌上方显示醒目的自摸/点炮/抢杠胡公告，同时保留座位已胡状态及原有事件、积分账本。

## 数据接口及真实性

FourPlayerOpening 将最新牌放在 _drawn_tiles 中（服务器私有），正常牌墙摸牌和杠后尾摸都会更新它，弃牌或胡牌则清除。public_state() 只有弃牌完成后才公开 discard_kind：tsumogiri 是摸切，tedashi 是手切；不公开其他玩家的最新摸牌具体牌种。

private_view(seat) 只向拥有该座位视图的调用者提供 drawn_tile；HTTP 人机对战只返回 0号玩家 private_view(0)。若 from_draw=true，但所切牌并非刚摸的牌，直接拒绝；若 from_draw=false，但玩家只有这一张刚摸牌，不能冒充已有手牌。同名牌恰有两张及以上时，允许玩家分别明确选择其来源；旧调用省略参数时维持兼容的同名牌默认摸切。

ready_waits、ready_after_discards 是仅返回给真人的结构听口提示，不能当作剩余牌数量或听牌获胜概率。起手换三张、密封定缺仍不向外泄漏信息。原四家胡牌规则、牌山守恒和记分接口不变。

## 修改文件及测试

- src/mahtrain_core/four_player.py：权威摸牌来源/弃牌公开类型。
- web_server.py：真人专用听口计算和 from_draw 参数。
- web/index.html、web/match.js、web/app.css：听口区域、右侧金色摸牌、单排背牌、牌河“摸切/手切”、AI 胡牌横幅。
- tests/test_match_draw_discard.py：真引擎的摸切手切、同牌两副本、非法来源和信息保护。
- tests/test_match_board_dom.js：真实前端 JS 的右侧摸牌、同牌来源、听牌、AI 胡牌及弃牌标签 DOM 测试。
- tests/test_web_app.py：页面标识与 HTTP 私密视图测试。

运行：python web_server.py，访问 http://127.0.0.1:8765 ，进入四人血战人机对战。自动测试：node tests/test_match_board_dom.js；python -m unittest discover -s tests -v。GitHub CI 在 Python 3.11 / 3.13 都要通过完整测试和原有五种子25场回归。

## 尚未实现的部分

AI 自动执行的多步操作仍可能在一次响应中快速完成，没有逐动作暂停动画。当前听口仅是合法牌种集合，不是对牌山里未知牌的推测；正式的血战完整流局结算仍未完成。
