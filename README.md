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

## 已开始的代码

`src/mahtrain_core/rules.py`：判胡、七对/金钩钓等部分番型、定缺、听牌集合、天听历史校验及计番。\n\n`src/mahtrain_core/efficiency.py`：13有效张向听数、有效进张（剩余牌种/枚数）、下一摸改善/胡牌概率、14有效张候选切牌与并列「局部最优切」排序。全部为纯 Python 标准库代码。**暂未实现**连续多摸动态概率、完整四人对战、计分账本、AI和前端页面。

本地运行切牌分析示例：

```bash
python examples/analyze_hand.py
```

示例打印各合法切牌的切后向听数、有效进张、下一摸概率及并列「局部最优切」。已在 GitHub Actions 的 Python 3.11 / 3.13 环境通过单元测试，测试记录：[Sichuan Rules Kernel Tests](https://github.com/CrazyA1ice/MahTrain/actions/runs/38838059744)。

本地运行固定牌例测试：

```bash
python -m unittest discover -s tests -v
```

已添加 `.github/workflows/rules-tests.yml`，用于在推送/Pull Request 时尝试自动运行 Python 3.11 与3.13 的单元测试。

## 仓库资源

- `assets/tiles/`：已有万、条、筒各 1～9 的牌面图片；页面设计优先复用并确认其许可。

当前开发顺序：**规则 v0.4 + 基础判胡/向听/有效进张/局部最优切已初步实现并测试 → 训练题目生成与评分 → 普通与清一色训练 UI → 四人对战状态机及三档 AI**。仅启用已验证且已确认的规则；复杂番型与结算边界仍按 v0.4 待确认事项逐项完善。
