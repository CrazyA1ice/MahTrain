# MahTrain 连续14轮单人摸切训练与理牌规则（v0.1）

> 当前为 **Python标准库可运行训练原型**，不是四人真实血战对局、Web产品或正式房间计分系统。规则预设仍为 `v0.4 draft / enabled=false`。

## 1. 统一理牌规则

- 按固定花色顺序 **万 → 条 → 筒** 归组；不存在的花色不显示。
- 各花色内部按数字 **9 → 1** 降序排列，重复张紧挨展示。
- 相同输入始终得到同样的显示顺序；排序仅作用于展示，**绝不改变牌种、牌张数、牌墙、定缺、向听数和答案**。
- 适用：四种单题训练的手牌和选择项、旧切牌分析命令、连续14轮初始手牌/摸牌后手牌/可切牌项。
- 格式示例：`万[9 8 8 3 1] | 条[7 2] | 筒[9 4]`。
- 技术入口：`src/mahtrain_core/presentation.py` 内 `sort_hand()`、`grouped_hand()` 和 `format_hand()`，未来 Web 页面复用统一排序约定。

## 2. 连续训练流程

`src/mahtrain_core/session.py` 的 `SoloTrainingSession(seed, missing_suit=None, rounds=14)` 完成以下步骤：

1. 用**一副完整的108张牌**生成可复现、确定性的单人训练牌墙；随机发13张作为初始暗手牌，剩余95张。
2. `missing_suit` 可在训练开始时指定；未指定则依初始13张中数量最少的花色自动挑选，并列按万、条、筒先后取第一门。**这是单人训练简化设定**，并非四人对战完整的“换三张→定缺”流程。
3. 调用 `draw_next()`，从这副牌墙摸1张，手牌变14张；此时题目含理好的手牌、公开弃牌历史、已摸张、候选切牌、牌墙剩余数量，**不含未摸到的牌和标准答案**。
4. 玩家 `submit(tile)`，必须切掉自己确实持有的一种牌；使用**提交前**玩家暗牌及历史公开弃牌计算当前所有何切、切后向听、有效进张、下一摸改善/和牌概率，并检查是否属于「局部最优切」。
5. 选择提交后才公开正确动作、切牌解释与对照。切掉的实体张放进弃牌池；该张今后在计算未知牌剩余枚数时持续扣除，不会凭空返回牌墙。
6. 到下一轮后重新从**同一牌墙**摸牌。默认14次决策后结束；若摸牌后已有合法胡牌，可选 `win` 正确胡牌并**提前结束**；也可以选择放弃胡牌切牌继续训练（该轮判为非最优）。
7. `report()` 输出已完成轮数、正确轮数、最优选择率、退向听次数、同向听层平均有效进张损失、逐轮分析与弃牌历史。

不能连续调用 `draw_next()` 绕过切牌；不能提交不在手里的牌，不能未胡乱报 `win`。非法提交不消耗本轮，牌数与牌墙始终保持108张物理守恒。

## 3. 本地使用

在仓库根目录：

```bash
# 完整14轮的交互式训练
python examples/solo_14_rounds.py --seed 17

# 自动选择牌效最优切，演示所有阶段和成绩
python examples/solo_14_rounds.py --seed 17 --auto

# 快速练两轮，并固定定缺为筒
python examples/solo_14_rounds.py --seed 17 --rounds 2 --missing-suit p

# 此前四种单题训练仍支持
python examples/training_quiz.py --mode one_shanten --seed 9
python examples/training_quiz.py --mode tenpai_discard --seed 42
python examples/training_quiz.py --mode pure_suit_waits --seed 42
python examples/training_quiz.py --mode pure_suit_discard --seed 0
```

玩家切牌输入使用 `m9`（9万）、`s8`（8条）、`p7`（7筒）；合法和牌可输入 `win`。

Python 引用：

```python
from mahtrain_core import SoloTrainingSession

game = SoloTrainingSession(seed=17)
print(game.public_state())     # 初始13张
question = game.draw_next()    # 14张和题目，不显示答案
print(question["hand_groups"])
result = game.submit("m9")      # 仅当手中确实持有 m9
print(result["correct"], result["best_actions"])
print(game.report())
```

### 单元测试与CI

```bash
python -m unittest discover -s tests -v
```

测试验证：各花色9→1顺序、重复牌不丢失、排序不修改输入、四种单题排序、13→14→13切换、两轮连续性、非法动作、固定种子复现、完整14轮（不提前胡情况下）、剩余牌墙计数和公开信息不包含未来牌，及已有的牌型/牌效/番型逻辑。

## 4. 当前限制与下一步

- **只是单人独立摸切**：没有换三张事件、其他三人的动作、吃碰杠操作、真实AI和血战流局结算。缺门已在训练开始时给定；用户可自行指定。
- 只使用已知的当前暗牌与历史弃牌计算**单次下摸改善/和牌概率**；不声称知道未来牌顺序，也不将单次概率冒充多轮获胜概率。
- `--auto` 是脚本演示用算法参考答案，不是实战三档AI；只能在出题后用，以便对照。
- 训练记录当前只在本次Python进程内；未实现持久化、账号、联机鉴权、网页UI和题库统计后台。
- 下一步优先：丰富真实序数顺子、搭子、七对竞争题型，解决复杂局面分布；然后为连续会话接入服务API及牌图训练页面。
