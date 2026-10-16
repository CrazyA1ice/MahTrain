# MahTrain

四川麻将（川麻）牌效训练与人机对战项目。

> 当前阶段：需求及架构设计。核心算法、训练页面、人机对战尚未实现。

## 项目方向

- **普通牌效训练**：一向听何切、听牌何切、14 轮独立摸切训练。
- **清一色训练**：13 张手牌听牌集合选择、14 张手牌最优何切或已和牌判断。
- **可解释牌效**：向听数、有效进张（牌种与剩余枚数）、概率及“局部最优切”：首版坚持不退向听，允许多个并列最优答案；退向听换更高收益暂缓。
- **人机对战**：1 人对 3 AI，多种难度、多局积分结算。
- **可配置玩法**：通过规则预设管理川麻的定缺、换三张、胡牌、续局和算分细则。

## 规则与项目文档

- [项目设计稿](docs/PROJECT_DESIGN_V0.1.md) — 训练、AI对战、局部最优切、开发分期。
- [**四川血战到底 v0.4 当前规则说明**](docs/SICHUAN_BLOOD_BATTLE_RULES_V0.4.md) — 天听保留原听口（碰牌取消、杠牌本身不取消）、金钩钓清一色天听三重复合6番。
- [**v0.4 配置草案**](configs/rulesets/sichuan_blood_battle_v0.4.draft.json) — `draft / enabled=false`，未解决所有边界前不得作为正式对战规则。
- [固定规则测试牌例（29例）](tests/fixtures/win_fan_cases_v0.4.json) — 胡牌、定缺、七对/龙七对、金钩钓、天听/听口与封顶计番。
- v0.1、v0.2、v0.3 规则均已作废，其同名旧配置已标记 `superseded`。

## 已完成的第一批计算与训练代码

- `src/mahtrain_core/rules.py`：判胡、七对/金钩钓等部分番型、定缺、天听保留原听口（碰取消、杠不自动取消）及原始/封顶番数。
- `src/mahtrain_core/efficiency.py`：13有效张向听、有效进张及余张统计、下一摸概率、14有效张「局部最优切」及并列排名。
- **`src/mahtrain_core/training.py`**：四类训练题的固定种子出题、题号和答案校验、错题解释；公开题目默认**不包含标准答案**。
- `examples/training_quiz.py`：可交互的中文命令行训练入口；前端 Web 页面仍未完成。

完整设计、接口示例和限制见 [**M2 训练题目引擎 v0.1 说明**](docs/TRAINING_ENGINE_V0.1.md)。

在仓库根目录体验四种训练题：

```bash
python examples/training_quiz.py --mode one_shanten --seed 9
python examples/training_quiz.py --mode tenpai_discard --seed 42
python examples/training_quiz.py --mode pure_suit_waits --seed 42
python examples/training_quiz.py --mode pure_suit_discard --seed 0
```

其中 `m1` = 1万、`s2` = 2条、`p9` = 9筒；清一色多选题以 `m1,m4,m7` 格式提交，`win` 为胡牌。可以使用 `--print-only` 只显示题目。

继续保留基础切牌分析示例：

```bash
python examples/analyze_hand.py
```

本地运行所有测试：

```bash
python -m unittest discover -s tests -v
```

GitHub CI 对 Python 3.11 / 3.13 运行规则、牌效、出题与判题测试，并验证四种训练题的命令行展示：[Actions](https://github.com/CrazyA1ice/MahTrain/actions)。

**实现边界**：当前题目来自受控牌形构造，并非完整随机四人对局；尚无连续14轮训练会话、完整多摸胡牌概率、网络服务/题目存储、Web 前端或 AI 对战。

## 仓库资源

- `assets/tiles/`：已有万、条、筒各 1～9 的牌面图片；页面设计优先复用并确认其许可。

当前开发顺序：**基础规则/牌效和四种训练题出题判题初步完成 → 扩充真实牌型与连续14轮训练会话 → 普通与清一色训练 UI → 四人对战状态机及三档 AI**。仅启用已验证且已确认的规则；复杂番型与结算边界仍按 v0.4 待确认事项逐项完善。
