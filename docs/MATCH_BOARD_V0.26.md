# MahTrain M3.14：人机对战四边牌桌（v0.26）

## 范围和素材

0号真人固定在下方，1号下家在右、2号对家在上、3号上家在左。牌桌中间提供四家独立牌河与真实的牌山剩余张数；每个座位显示行动轮、定缺、已胡状态；AI 只显示暗手背牌与公开副露，本家手牌继续可点击切牌。

不需要额外上传图片：正面继续调用现有 MahTrainUI.tileElement 和项目自身的麻将图片；桌布、木色桌框、背牌、简化牌墙由 CSS 生成。之后如有高清桌布纹理、牌背纹理、桌框及音效素材，可无损替换美术样式。

## 修改位置

- web/index.html：四边座位 match-seat-0至3、牌河 match-river-0至3、中央牌山 match-wall-count；保留 match-hand、match-controls、match-public 等现有 ID。
- web/match.js：renderBoard / renderSeat / renderRiver / renderWall / renderMelds 将座位与牌河渲染独立于原来换三张、定缺、碰杠胡、胡牌和积分账本逻辑。
- web/app.css：新布局与绿色桌布、背牌、牌山装饰；仅使用 match- 范围内样式，不影响训练和旧版规则演示。
- tests/test_web_app.py：检查 DOM 的四座位四牌河节点、原按钮接口及隐私约束。
- tests/test_match_board_dom.js：无需额外依赖的 Node DOM 测试，真正加载 web/match.js，模拟开始一局和点击真人手牌，验证请求、牌山更新、四家牌河、AI 暗手遮蔽、公开碰牌与暗杠不泄漏。
- GitHub CI：Python3.11/3.13 两套测试额外运行 Node DOM 冒烟，原有五独立种子×5场策略试验保留。

## 后端信息边界

现有规则状态已包含 wall_count、hand_counts、melds、won、turn、discards、missing_suits。本家私有视图中有 hand、own_melds；未增加读取 AI 隐藏牌或牌墙顺序的新 API。服务器已把对手的暗杠牌种脱敏为 null，前端只绘制四张背牌；本人的副露使用合法的 own_melds。

一张弃牌被碰杠移走后，只在原牌河保留“已取走”文字占位，而不再绘制第二张实体牌面。未统一公开的定缺状态显示“待公开”，不推测密封声明。中央牌墙四周的 CSS 装饰牌不反映剩余实物数量；牌山数值以服务端 wall_count 为准。

## 手动与自动验收

在仓库根目录：

~~~bash
node --check web/match.js
node tests/test_match_board_dom.js
python -m unittest discover -s tests -v
~~~

在网页中启动“人机对战”，依次检查换三张、统一定缺、点击本人手牌、响应碰杠胡、杠后补摸、已胡退出、牌墙耗尽。宽屏保持四边正方位，窄屏容器可左右滚动，自己的手牌区域也能横向滚动而不会挤压操作区。

## 未改变的范围

本轮纯前端布局，不改变麻将规则、AI 决策、公平信息隔离与账本。四 AI 连续自动执行可能瞬间从多步更新到同一终态；还未制作逐动作动画或暂停播放。杠钱与流局查花猪/查大叫仍沿用试验功能，不能声称已经有完整正式血战结算。
