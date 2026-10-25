# M4.42：新种子真实Challenge基线的安全同牌效改切空间（v1.52）

## 研究依据

用户最新 M4.41 的预注册两原始洗牌种子、18局真实官方付分结果为：原冻结影子 59/114 次改切，按原始洗牌簇的平均实际净分差 -140；保守影子 0/95 次改切，46 次被“不减少可见有效进张”门槛阻止，最终与原Challenge官方结算差0。两种子不足以做显著性或强度论断。

此前M4.40还验证了M4.35冻结模型三个牌效特征权重均为负，在M4.39的61次改切全部牺牲本家有效进张。保守约束的“零改切、零差异”意味着旧负权重下难以主动实现强化，但保守回退避免了相关场景中的局部倒退。

**下一步首要问题**：挑战级已在公开场况下优化向听、有效进张与预计番值/风险，究竟还剩多少无需牺牲当前可见有效进张的可选切牌？如果每个局面几乎唯一，就没有必要继续训练一个仅在严格相等有效进张下择优的模型。

## 本轮实际实现

- 使用 **新原始自然洗牌种子**，每个种子只运行1场真正完整的四个原Challenge座位的对局，不运行9场影子对照，不改任何正式策略决策。
- 观察器继承正式 Challenge MahjongAgent，在真实 discard 调用后只读取原算法已经算好的私有本家合法候选评分列表（_last_discard_scores）。不重复分析对手手牌，也不重采样未来牌墙；不会改选牌或消耗额外随机数。
- 原评分器的候选已经过滤为合法最低向听数的切牌，并遵循原定缺优先策略。本轮只统计每次原版切牌是否有其他同向听的合法候选，进一步按有效进张数分为“相同 / 更多 / 更少（不计入安全替代）”。
- 对相同有效进张候选，再核对原挑战级评分、预计加权番值、公开副露压力和公开风险指数是否有差异。这四种比较是机会分布，并不是研究候选优胜概率或正式胜率。
- 按原始洗牌簇完整保存断点、核验四座位真实官方结算的零和与计数恒等式，遇错误不私自重算覆盖原数据；支持 --resume。
- 读取旧 M4.34、M4.37、M4.39、M4.41 **私有计划用于核对冻结模型指纹和排除已经看过的种子区间**，不读取其中的对局分数作为新模型训练标签，不调整模型权重。未提供的其他历史实验 seed 需要用户自行排除。
- 安全 JSON 只包含统计计数与来源有效性旗标，不含真实洗牌编号、某次具体切牌、私有手牌、未来牌墙或模型权重。

## Windows运行

在 MahTrain 项目根目录执行：

~~~powershell
cd D:\ChatGPT\MahTrain
git switch main
git pull --ff-only origin main

python examples\run_challenge_tie_opportunity_probe.py --train-dir data/selfplay/m434-smoke --prior-m437-dir data/selfplay/m437-shadow-2 --prior-m439-dir data/selfplay/m439-actor-2 --prior-m441-dir data/selfplay/m441-guarded-2 --seed-start 91700 --seeds 2 --out-dir data/selfplay/m442-safe-ties-2
~~~

这只会运行新种子 91700～91701 的2场Challenge基线，不重复上一次18场旧比赛，也不修改旧评估数据。91700～91701只是与**当前已知**实验种子分离的示例；若其他历史实验已经用过这两个种子，请换成未使用过的。

若某一完整原始洗牌簇执行后程序中断，原样重运行上面命令，加 --resume，即可不重打完整保存并通过核验的种子。

成功后读取：

~~~powershell
Get-Content data/selfplay/m442-safe-ties-2/safe_challenge_tie_opportunities.json
~~~

将该安全 JSON 上传即可。PRIVATE_challenge_tie_probe_plan.json 与 PRIVATE_challenge_tie_seed_clusters 内的种子、冻结指纹和真实对局元数据均不能上传公开GitHub。

## 如何解读

- counts.discard_decisions：新真实对局中4个Challenge角色切牌次数。
- counts.single_policy_choice_decisions：按定缺等正式策略限制，只有一种最低向听候选时的决策次数。
- counts.multichoice_minimum_shanten_decisions：有两种以上正式策略允许的最低向听切牌。
- counts.decisions_with_equal_ukeire_alternative：原版所选切牌有至少一种另一切牌，最低向听数相同且剩余可见有效进张总张数相同；它只是一种**安全约束下的可用备选**，绝不表示能得到更好官方积分。
- counts.decisions_with_higher_ukeire_alternative：原版因综合预计番值和风险倾向，当前所选有效进张反而少于其他同向听候选的次数。这种情况不能单凭张数断言原版选错了。
- equal_ukeire_alternatives_different_fan_value / different_public_pressure / different_public_risk_index：同有效进张下是否尚有其他公开评估维度可以有意义地区分切法。

如果同牌效替代比例很低，说明只学习切牌平局分歧作用有限；下一阶段研究应考虑训练在更多风险/番型目标、碰杠胡响应以及终局结算收益上的策略，但仍必须坚持仅行动者可见信息和冻结研究-评估分离。

## 验收

~~~powershell
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m442_challenge_tie_opportunities.py" -v
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m436_frozen_shadow_four_seat.py" -v
~~~

第一组是可控已结算结果与方案隔离的快速回归；第二组新增真正完整的Challenge牌局，与无探针的原 Challenge **相同 seed、相同四家策略**比对终局各座位官方结算，核对新观测不会改变策略本身。专项测试和真实牌局检查通过后再将M4.42合并main。
