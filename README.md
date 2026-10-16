# MahTrain

四川麻将（川麻）牌效训练与人机对战项目。

> 当前阶段：基础判胡/牌效算法、四种单题训练、统一理牌与14轮单人摸切已实现，新增**可点击的本地网页训练原型**；正式四人对战与AI尚未实现。

## 项目方向

- **普通牌效训练**：一向听何切、听牌何切、14 轮独立摸切训练。
- **清一色训练**：13 张手牌听牌集合选择、14 张手牌最优何切或已和牌判断。
- **可解释牌效**：向听数、有效进张（牌种与剩余枚数）、概率及“局部最优切”：首版坚持不退向听，允许多个并列最优答案；退向听换更高收益暂缓。
- **人机对战**：1 人对 3 AI，多种难度、多局积分结算。
- **可配置玩法**：通过规则预设管理川麻的定缺、换三张、胡牌、续局和算分细则。

## 规则与项目文档

- [项目设计稿](docs/PROJECT_DESIGN_V0.1.md) — 训练、AI对战、局部最优切、开发分期。
- [**连续训练网页 v0.3（当前）**](docs/SOLO_TRAINING_V0.3.md) — 胡牌结构与定缺双重诊断、较大高清矢量牌面、原图切换、可开关摸切/杠/胡音效。
- [连续训练 v0.2（历史说明）](docs/SOLO_TRAINING_V0.2.md) — 升序理牌、自动胡牌/暗杠弹窗、独立杠区和墙尾补牌。
- [**四川血战到底 v0.4 当前规则说明**](docs/SICHUAN_BLOOD_BATTLE_RULES_V0.4.md) — 天听保留原听口（碰牌取消、杠牌本身不取消）、金钩钓清一色天听三重复合6番。
- [**v0.4 配置草案**](configs/rulesets/sichuan_blood_battle_v0.4.draft.json) — `draft / enabled=false`，未解决所有边界前不得作为正式对战规则。
- [固定规则测试牌例（29例）](tests/fixtures/win_fan_cases_v0.4.json) — 胡牌、定缺、七对/龙七对、金钩钓、天听/听口与封顶计番。
- v0.1、v0.2、v0.3 规则均已作废，其同名旧配置已标记 `superseded`。

## 已实现的 Python 训练原型

- **统一理牌与高清牌面**：`src/mahtrain_core/presentation.py` 将同花色集中，固定 **万→条→筒**，组内按 **1→9升序**，重复牌相邻；排序不改变实际牌效、手牌张数或随机牌墙。
- **胡牌及部分计番**：`src/mahtrain_core/rules.py`，涵盖定缺、七对、金钩钓、天听（碰取消、杠不自动取消）等已验证子集。
- **牌效计算**：`src/mahtrain_core/efficiency.py`，向听数、有效进张、余张、下一摸概率与局部最优切。
- **四类单题训练**：`src/mahtrain_core/training.py`，固定种子出题、答案校验、提交后解析；`examples/training_quiz.py` 可交互体验。
- **连续14轮摸切训练**：`src/mahtrain_core/session.py`；独立108张实体牌墙、逐轮摸切、实时理牌、判题解释、正确率/进张损失/退向听次数。命令行入口 `examples/solo_14_rounds.py`。

### 本地可点击网页（新增）

```bash
git pull origin main
python web_server.py
```

浏览器打开 **http://127.0.0.1:8765**。网页默认采用 **64×88 的清晰矢量麻将牌面**，也可在右上角切换回仓库原始牌图；可开启/关闭摸牌、切牌、杠牌及胡牌音效。胡牌必须同时满足**四面子一对将/七对结构与定缺花色已清空**。如果仍持定缺牌，即使牌型结构完整，页面也会告知剩余数量，不会误弹胡牌。点击手牌切牌；能胡或暗杠时系统自动弹窗提示。详细参见[单人训练网页 v0.3](docs/SOLO_TRAINING_V0.3.md)。

### 运行连续训练

```bash
# 在仓库根目录执行，默认14轮，手动出牌
python examples/solo_14_rounds.py --seed 17

# 自动选择最优切，观看完整训练与报告（若合法胡牌可提前结束）
python examples/solo_14_rounds.py --seed 17 --auto

# 简短体验两轮，指定定缺筒
python examples/solo_14_rounds.py --seed 17 --rounds 2 --missing-suit p
```

输入示例：`m9` = 9万、`s8` = 8条、`p7` = 7筒；胡牌由系统自动询问确认，不需自己输入 `win`。显示示例：`万[3 7 9 9] | 条[5 8] | 筒[1 3 9]`。

其他独立单题：

```bash
python examples/training_quiz.py --mode one_shanten --seed 9
python examples/training_quiz.py --mode tenpai_discard --seed 42
python examples/training_quiz.py --mode pure_suit_waits --seed 42
python examples/training_quiz.py --mode pure_suit_discard --seed 0
```

本地验证：

```bash
python -m unittest discover -s tests -v
```

GitHub Actions 对 Python 3.11/3.13 运行规则、牌效、四类单题、理牌、14轮会话单元测试，并冒烟运行命令行训练：[测试记录](https://github.com/CrazyA1ice/MahTrain/actions)。

**实现边界**：当前是单人独立牌墙的训练原型，只加入手牌内的**暗杠**和尾牌补摸；没有四人换三张、碰牌/明杠/补杠、四人交互或 AI。可用的是本地网页原型，不是公网可部署的正式产品；多摸动态概率、房间账本与VRF仍未完成。

## 仓库资源

- `assets/tiles/`：已有万、条、筒各 1～9 的牌面图片；页面设计优先复用并确认其许可。

当前开发顺序：**基础规则/牌效、四类单题、统一理牌与连续14轮单人训练原型已完成 → 扩充序数顺子/搭子题型及题库 → 扩展四类独立单题网页交互和训练历史保存 → 四人对战状态机及三档 AI**。仅启用已验证且已确认的规则；复杂番型与结算边界仍按 v0.4 待确认事项逐项完善。
