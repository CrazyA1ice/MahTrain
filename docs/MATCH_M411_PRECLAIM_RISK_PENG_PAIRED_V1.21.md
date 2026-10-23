# M4.11：基于合法公开危险度的明杠→碰牌实验候选（v1.21）

## 开发目的与前轮真实证据

M4.10 [PR #110](https://github.com/CrazyA1ice/MahTrain/pull/110) 已在最终分支通过专项与全量测试，合并主分支。前轮固定开发 44000–44007、独立保留 45000–45007，16个独立初始洗牌、64局。6次**实际获杠后弃牌**中，3次补牌后原挑战级实际出牌的公开危险等级较补牌前既有手牌最低危险等级上升，3次不变；没有真实点炮。这只是描述性研究，不能证明任何策略改善。

本轮问题更进一步：**如果在真实可选择明杠的当时，仅使用可见信息，按固定门槛在部分局面改选碰牌，最终整局净积分是否发生变化？** 注意补牌后的危险度本来在决策时不可知，不进入策略公式。

## 冻结的研究策略

仅当规则引擎在同一回应窗口授权 `pass + peng + ming_gang` 且**没有合法胡牌**，原 `MahjongAgent("challenge")` 明确选择 `ming_gang`、非天听保护条件时，计算 M4.07 的 `public_minggang_exit_risk(view)["min_existing_cut_threat_index"]`。这个公开风险指数是本家原有手牌在明杠后、尚未实际补牌时可选弃牌种类的最低启发式威胁总和，而非点炮概率；它可能大于1。

- 若原挑战级明杠，且 **指数 ≥ 0.25**，实验臂改选授权的 `peng`。
- 其余局面、合法胡牌和抢杠胡、单选项窗口、天听保护、本人暗杠／补杠、出牌及其余动作全部保留原挑战级 AI。
- **0.25 在新洗牌种子运行前固定**；不按实验结果改阈值，不使用真实补牌、未来墙尾、对手暗手或终局信息进行当前决策。
- `baseline` 臂始终按原挑战级策略行动；`risk_peng` 臂仅按上述边界做真实授权的 `ming_gang → peng` 干预。该改动是离线研究代理，正式游戏中的挑战级 AI 代码一行不改。

## 权威配对实验与审计

开发组种子 **46000–46003**、独立保留组 **47000–47003**，两组均事前固定、不与 M4.06–M4.10 已用样本重叠。每种子分别四座位轮换，每位置用完全相同初始洗牌运行 `baseline` 和 `risk_peng` 两条完整正式规则对局，得到 **8个独立洗牌种子、32个配对座位、64场完整对局**。

所有实测收益来自游戏权威 `_official_outcome`：
`official_net = win_points + kong_points + exhaustive_points`，不拿“理论上能获得的明杠钱”冒充最终收益。不干预时，两臂完整可公开对局事件、动作轨迹与正式终局完全一致，否则测试立即失败；一旦改选，整局路径可能分叉，记录的是真正的完整牌局净积分差，而非明杠一个决策的因果局部价值。

以**独立初始洗牌种子**为汇总单位，列出每组真实干预次数、四座位平均净分差、正／负／无变化种子数和输赢／杠钱／流局分账差异。没有实际干预时净差必须为零；若干预次数太少、正负方向不一致、保留组失效，**不改线上策略**。

## 文件与复现

- `src/mahtrain_core/ai_minggang_preclaim_paired.py`：合法回应窗口的公开风险提议、基准/候选双臂代理、整局真实零和账目配对。
- `tests/test_m411_preclaim_risk_peng_paired.py`：真实108实体牌的授权碰／明杠窗口、0.25上下边界、风险总和超过1的处理、必须胡／抢杠胡/天听保护、隐私字段隔离、实际终局配对和独立种子汇总。
- `examples/audit_minggang_preclaim_risk_peng.py`：结果JSON和控制台聚合统计。
- `.github/workflows/m411-preclaim-risk-peng-paired.yml`：专项测试、M4.10/M4.09历史回归以及两组32场自然配对，归档仅含必要数据的匿名报告。

运行：

```bash
python -m unittest discover -s tests -p 'test_m411_preclaim_risk_peng_paired.py' -v
python examples/audit_minggang_preclaim_risk_peng.py --cohort development --seeds 4 --output results/m411-development.json
python examples/audit_minggang_preclaim_risk_peng.py --cohort holdout --seeds 4 --output results/m411-holdout.json
```

## 安全边界和结论门槛

任何可见危险指数不是 `P(Ron)`、不是实际预期杠钱，也不是完整对局期望。干预后牌墙进程、对手碰胡、出牌和后续每次决策都可能改变。同种子四座位循环不是四个独立观测。固定门槛是可证伪的实验候选，不是已经证实的最佳行动。

没有真实且足够多的干预、跨独立种子的稳定正式净收益优势、足够延迟与合法性证据之前，**不得上线此候选，也不可以把一局中的最佳行动向玩家宣称为已知真值**。本轮不改变 Web、对战桌面、人类决策提示或真实挑战级 AI。
