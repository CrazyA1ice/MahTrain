# MahTrain M2 首批训练题目引擎（v0.1）

> 开发状态：四类基础训练题目生成、确定性评分及命令行演示已实现。**尚未开发 Web 页面或后端 API，也未启用正式对局计分规则**。本模块基于血战规则 v0.4 的已确认子集和计算内核。

## 1. 本次支持的四种模式

| 模式标识 | 中文名 | 公共题目 | 标准答案和判题 |
| --- | --- | --- | --- |
| `one_shanten` | 一向听何切 | 14张牌、定缺、可切牌 | 枚举所有切牌，**最低切后向听数=1**；在这一层按有效进张剩余枚数排名，允许并列 |
| `tenpai_discard` | 听牌何切 | 14张牌、定缺、可切牌 | **最低切后向听数=0**，优先有效可胡张数较多的合法听口；并列全对 |
| `pure_suit_waits` | 清一色听牌多选 | 13张同一花色、定缺、对应花色1～9可多选 | 必须提交**完整合法听口集合**；返回漏选、多选与各剩余张数 |
| `pure_suit_discard` | 清一色何切／识别已胡 | 14张同一花色、定缺、可切牌及胡牌键 | 已胡必须选择 `win`；否则按向听/有效张数排名，允许并列 |

全模式通用：最多每种牌4张；不生成违反定缺的合法胡牌答案；不允许将退向听但潜在番数更高的切牌判正确。候选排序目前不含预期得分或多摸模拟收益。

## 2. 题目生成原理

- 使用 Python `random.Random(seed)` 的局部随机数实例，**同种子、同模式、同实现版本复现同一题**，不会改变全局随机状态。
- 目前不是无约束随机抽14张：先程序化构造满足目标的基础牌形，再随机选择花色、数字、追加牌与手牌显示顺序，通过现有判胡/向听算法反向验证题目类别。
- 每个候选题先核验牌的物理合法性及目标向听，再输出题目；搜索有上限，失败时报错，不会把未经验证的牌误发给玩家。
- 清一色何切包括已成胡牌型的局面，用于训练“无需切牌、直接胡”识别。
- **当前题型多样性有意受控**：生成器主要围绕若干完整刻子、单骑、七对可识别结构展开；尚未覆盖所有高复杂度序数顺子、拆搭与多种复杂副露局面。后续扩展题库之前应先建立足够的基准牌例以保证题目正确性。

## 3. Python 接口

```python
from mahtrain_core import generate_question, grade_answer

question = generate_question("tenpai_discard", seed=42)
print(question)  # 默认不返回标准答案、最优切牌或正确听口

# 玩家提交选择，服务端通过私有 seed 复现并重新算答案：
result = grade_answer(
    "tenpai_discard",
    seed=42,
    selection="m1",
    question_id=question["question_id"],
)
print(result["correct"], result["best_actions"], result["reason"])
```

**重要约定**：

- `generate_question(mode, seed)` 返回公开题目：题号、模式、规则版本、手牌、定缺、选择项、答案类型；**不包含标准答案也不包含 seed**。
- `grade_answer(mode, seed, selection, question_id=...)` 内部**重新生成题目**，用同一个核心算法求标准答案；返回正误、最优切牌或听口、遗漏与多选、牌效对照和解释。
- 清一色听口模式接受牌种字符串数组，如 `["m2","m5"]`，无论答案顺序如何，只有集合完整匹配才算正确。
- 何切模式接受手中牌种字符串（如 `"m9"`）或 `"win"`（只限清一色何切）；不能选择手中不存在的牌。
- `question_id` 必须与服务端保存的模式、种子与手牌严格一致；**上线时 seed 只能留在可信后端/会话中**，不能依赖客户端自称的 seed 或手牌作为评分凭证。当前尚未实现 API/会话存储/身份验证，这只是受控本地演示。
- `ruleset_id` 使用 `sichuan_blood_battle_v0.4`。实际对战计分预设当前仍为 `draft / enabled=false`，训练的基础牌型子集不等于已经发布完整房间规则。

## 4. 如何本地体验

在仓库根目录：

```bash
python examples/training_quiz.py --mode one_shanten --seed 9
python examples/training_quiz.py --mode tenpai_discard --seed 42
python examples/training_quiz.py --mode pure_suit_waits --seed 42
python examples/training_quiz.py --mode pure_suit_discard --seed 0
```

牌标识：`m1`表示1万，`s2`表示2条，`p9`表示9筒；`win`表示胡。听口多选输入示例：`m1,m4,m7`。

只显示题目不等待用户回答（CI/脚本用）：

```bash
python examples/training_quiz.py --mode tenpai_discard --seed 42 --print-only
```

运行回归测试：

```bash
python -m unittest discover -s tests -v
```

CI `.github/workflows/rules-tests.yml` 覆盖 Python 3.11/3.13，执行规则、牌效、训练测试以及四种题型的公开题目冒烟测试。

## 5. 下一轮工作

1. 扩大真实题型牌形：序数顺子、两面/嵌张/边张、多组搭子与七对竞争，构造不同难度，保证分布丰富且每题类别真实。
2. 训练会话：连续14轮摸切、已知牌更新、题目种子/选择记录、回放和逐轮统计。
3. API：后端可信题目与种子存储、`questions`/`answer`，默认隐藏答案；在此之前不能将当前纯 Python 函数当作联网服务。
4. 前端：牌图、选择提示、提交反馈、并列局部最优对照以及清一色多选。
5. 延后高级能力：多摸真实胡牌概率、综合预期收益/番型、完整碰杠状态与天听事件的可靠对局追踪。

**不包含的功能**：当前题目生成不模拟强制换三张、定缺决策或真实对手动作。它将定缺视为已选完毕，使用独立训练牌池下的基础概率模型。
