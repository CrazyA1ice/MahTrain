# M4.14：保留近似收益条件下的公开风险切牌配对实验（v1.24）

## 本轮要解决的问题

M4.13 [PR #113](https://github.com/CrazyA1ice/MahTrain/pull/113) 在最新分支通过29项专项及回归、64场完整配对和Python 3.11/3.13等全量CI，已合入主分支；真实观察到24次原AI选择碰，但0次按新候选条件改为过牌，净分差为0。继续调这种未触发的阈值可能造成反复试样后的虚假改进，因此本轮转向每局更高频发生的**切牌选择**。

现有挑战级AI在 `challenge_discard_scores` 中已经考虑：严格向听数、公开剩余有效牌数、听牌对应番值与天听、成牌结构先验、公开对手副露场况及有界风险；其输出 `_last_discard_scores` 是本人授权视图计算的同向听候选列表。M4.14 **不创建新的牌效搜索、不读取墙尾与对手暗手、不调用第二次番数枚举或隐藏牌蒙特卡洛**，而是仅复用原AI首次真实切牌时已经算出的列表。

## 冻结候选

原挑战级真实切牌后，只有存在多个同向听合法候选且当前不是已确认天听时才讨论改选。风险和收益阈值在新种子实验前冻结：

- 原切牌与备选必须具有**完全相同的最小严格向听数**。不退向听，不跨越定缺优先策略；
- 备选的 `expected_fan_weighted_copies` 不得低于原选 **80%**，有效进张剩余牌数 `effective_tile_count` 不得低于原选 **85%**；
- 备选 `table_threat_index` 至少低于原选 **0.08**，选符合条件中公开风险指数最低者，其他指标仅用于确定性平局排序；
- 当原切牌预计进张为零、候选列表为空或只有一个最小向听切牌时，保留原切牌；
- 即便天听有多个同向听候选，也暂时保留原切牌，避免无实证的天听收益／听口更改；
- 所有 `exchange`、`missing`、`response`、`kong`、胡牌优先级以及其他出牌决定机制完全使用原挑战级AI。候选策略只存在于离线研究子类 `NearValueDefenseResearchAgent`。

风险是公开信息推断的**累加启发式指数**，可能高于1，绝不是 `P(Ron)`。备选仍有实际被胡的可能。保留80%和85%的指标不意味着准确估计整局期望积分，任何收益改善都必须经过真实全局对战再检验。

## 预注册的自然配对实验

开发组连续种子 **52000–52003**、独立保留组 **53000–53003**。每种子挑战级分别坐四个位置，每座位同初始洗牌运行原挑战级 `baseline` 和 `nearvalue_defense` 两条真实完整108张牌血战比赛：**8个独立洗牌、32个坐席配对、64场正式对局**。

记录频数区分：所有真实挑战级切牌次数、至少两种最小向听合法切牌的次数、候选真实不同切牌次数、存在改选的独立种子数。按每个独立初始洗牌及四座位平均计算权威 `official_net`，分解真实胡牌分、杠钱分、流局分。无真实切牌变化时两臂的完整公开事件与动作轨迹、各项正式积分必须完全一致，否则失败。**不要把四座位循环计作四个独立统计样本**。

如果候选未真正改切，或开发/保留不同方向，或净分没有真实改善，结论为尚未证实有效，不得上线。配对同洗牌能控制开局，但任何改变切牌都可能使后续牌墙消耗和其它玩家的行动顺序改变，因此收益是完整对局路径差异，不是动作局部的无偏价值估计。

## 文件、测试与运行

- `src/mahtrain_core/ai_discard_nearvalue_risk_paired.py`：仅复用已经存在的公开合法排名，按固定收益保护改选，跑完整两臂对局并结算官方分量；
- `tests/test_m414_discard_nearvalue_risk_paired.py`：原AI行动保真、108实体牌、番值/进张保护、向听一致、天听保护、非法暗牌/NaN拦截、固定阈值与座位种子聚合；
- `examples/audit_discard_nearvalue_risk_paired.py`：输出匿名真实配对实验JSON；
- `.github/workflows/m414-discard-nearvalue-paired.yml`：11项新测试和M4.13/M4.12合计20项回归，两个全新自然配对组各32局并归档无完整事件牌种的结果。

```bash
python -m unittest discover -s tests -p 'test_m414_discard_nearvalue_risk_paired.py' -v
python examples/audit_discard_nearvalue_risk_paired.py --cohort development --seeds 4 --output results/m414-development.json
python examples/audit_discard_nearvalue_risk_paired.py --cohort holdout --seeds 4 --output results/m414-holdout.json
```

**上线条件：** 除合法性与不退向听，还要在足够多个真正发生干预的独立洗牌种子上，经过事前固定策略的更大规模对照和实时动作性能验证，并在保留样本显示稳定的正式净分优势。本轮不改正式对战AI、不向玩家宣称AI有全知最优切牌能力，且必须在最新PR头的全部专项与全量测试绿灯后合并研究工具。
