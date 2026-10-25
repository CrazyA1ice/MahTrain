# M4.43：同向听、同有效进张约束下的公开风险与番值择优对照（v1.53）

## 真实依据与局限

已收到用户 M4.42 的可分享文件：2 个**新的**原始洗牌种子，2 场完整四人原挑战级对局，总计101次切牌，其中50次有多个最低向听合法候选，31次至少有一张**有效进张数与原挑战级相同**的备选，共47张此类备选。18张同牌效备选有公开风险指数差异，6张有预计加权番值差异；这些是**备选牌数量，不是18/6次独立决策，更不是胜率增益**。101次原挑战级选择均在合法最低向听候选中拥有最多的有效进张。样本仅有2个原始洗牌种子。

M4.41 另已表明旧冻结离线模型负权重造成的低牌效改切，在保守约束下全部被否决，候选一张牌都不再主动改变，与原Challenge实战分数差为0。这是回退安全机制，不是模型更强。

## M4.43 已预先固定的两条研究候选

仍使用原 Challenge MahjongAgent 处理换三张、定缺、胡、碰杠、基础切牌及全部随机数；在 Challenge 已计算完本人真实合法候选列表后，才观察和决定是否在**完全相同最低向听、完全相同有效进张数**的切牌之间替换。没有查看未来牌墙、对手暗手，不用以往测试结果再拟合权重。正式Challenge线上策略**一行未改**。

- 风险优先 risk_first：备选的**公开风险指数**必须比原选牌至少低 0.03，且预计番值加权剩余张数不得低于原方案的95%；对满足条件的同牌效备选优先取公开风险指数最低者。
- 番值优先 fan_first：备选**预期番值加权剩余张数**必须比原选牌高至少2%，且公开风险指数最多增加 0.05；同牌效备选按预计番值优先。
- 这些参数仅为事先固定的、易理解的研究启发式，**没有经过外部标定**。公开风险指数不是放铳概率；加权番值是一步收益替代指标，不是整场胜率。即使相同有效进张仍可能造成听口质量或进攻/防守上的变化，因此这不是对真实净积分的无风险保证。

## 新洗牌官方真实比赛

每一个未见过的自然洗牌seed执行 **9场真正完整、官方结算、四人血战麻将**：

1. 四名原 Challenge AI 的原版基准：1局。
2. 研究性 risk_first AI 分别在四个座位替换其中一名 Challenge：4局。
3. 研究性 fan_first AI 分别在四个座位替换其中一名 Challenge：4局。

同一自然洗牌中的四座位相关对照，统计单位仍是一个原始洗牌seed；只对真实改切发生时报告策略净分差，未改切若最终官方分数发生变化视为错误。按官方胡牌、杠、流局结算分开统计，且逐局核验真实账本零和。两种策略采用同一种子同一基础对照，不比较旧种子上已经看到的负权重候选分数。

## 本地 Windows PowerShell 运行

先更新 main 后执行：

~~~powershell
cd D:\ChatGPT\MahTrain
git switch main
git pull --ff-only origin main

python examples\run_safe_tie_risk_fan_trial.py --train-dir data/selfplay/m434-smoke --prior-m437-dir data/selfplay/m437-shadow-2 --prior-m439-dir data/selfplay/m439-actor-2 --prior-m441-dir data/selfplay/m441-guarded-2 --prior-m442-dir data/selfplay/m442-safe-ties-2 --seed-start 91900 --seeds 2 --out-dir data/selfplay/m443-safe-tie-2
~~~

上例91900、91901需确保**没有用在其他未登记的本地实验**。代码读取 M4.34 原TRAIN与M4.37、M4.39、M4.41、M4.42 私有计划，仅用于来源校验和排除其已知seed区间；不会读取过去的收益标签来训练。2个新seed会产生18场新完整对局。

中途中断可使用完全相同命令尾部加 --resume。**只复用整个9局已结算且SHA-256校验通过的原始洗牌簇**；不复用九局中途已打的一部分。不要删旧证据，也不要覆盖先前私人评估目录。

成功后只读取并上传：

~~~powershell
Get-Content data/selfplay/m443-safe-tie-2/safe_tie_risk_fan_trial.json
~~~

需要保留在本地 gitignored data/selfplay 的私有文件：
- PRIVATE_safe_tie_policy_plan.json（真实独立洗牌种子和模型来源指纹等）。
- PRIVATE_safe_tie_policy_seed_clusters/（每个原始shuffle的9场实际结算、私有种子及SHA校验）。

可分享安全 JSON 包含两条策略各自与原Challenge的官方净分差、胡/杠/流局账本构成、真正发生的同牌效切牌改变次数、候选出现机会、四座位对应差异和原洗牌种子簇符号计数，不包含真实seed/手牌/具体切牌/冻结模型的权重。

## 研究边界与后续

两个独立洗牌seed仅可确认程序是否有实际改切和初步方向，**不能证明总体优劣**；若其中一个候选改切0次，其对照分数为0只能说明未改变策略。即使发生改切，同seed不同后续的对局分数也只能用于全策略配对比较，不是某一手的单动作反事实因果收益。

如果两种候选的主动改切覆盖率都很低，说明原Challenge已经把这段安全切牌空间占得较充分，下一阶段更应考虑碰/杠/胡等复杂行动的合法独立评估，而不是继续追逐低牌效切牌。

## 验收

~~~powershell
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m443_safe_tie_policy_trial.py" -v
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m436_frozen_shadow_four_seat.py" -v
~~~

快速测试验证固定门槛、安全同牌效、原始seed区间隔离、崩溃恢复、被篡改SHA、完整九局真实支付合约。真实规则引擎集成测试还会真正执行9场麻将，检查共同Challenge基准、四座位、积分分项与未改切回退。以 GitHub Actions 的实际结果为准。
