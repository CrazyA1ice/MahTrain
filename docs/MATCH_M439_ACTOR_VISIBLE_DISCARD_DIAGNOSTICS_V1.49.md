# M4.39：独立新洗牌种子下的行动者可见改切诊断（v1.49）

## 出发点

用户提供的 M4.38 安全结算报告：2组原始洗牌、10场真实完整对局，冻结模型115次切牌机会改切70次；平均净积分差-370，其中流局-200、胡牌-162.5、杠钱-7.5。七次改切的座位轮换最终得分差为负，一次未改切得分不变。但只有2个原始洗牌种子，不能据此选阈值并复用这组数据声称独立提升。

特别提醒：流局损失比例54.1%是**已发生的支付构成**，并不能证明“由听牌不足造成”，更不是针对单张切牌的可识别因果效应。

## 本轮 M4.39 的代码范围

- 原正式挑战级AI不变；M4.37默认评估接口、结果协议不变。冻结离线模型仍不晋升在线策略。
- 新增仅M4.39可开启的逐次出牌私人诊断：行动者本人正常 private_view 里计算的原挑战AI切牌、候选切牌、是否改切、最低向听、两种切牌的有效进张数及进张概率、有效进张牌种类数、冻结模型评分差。不会取得对手暗手、真实未见牌墙或保存完整个人手牌。
- 每个新独立洗牌种子依旧进行五场完整的官方结算对照（1原版基准+4个座位轮换）。每簇原子持久化，只保存已完整结束的5场，不在中途修改旧档。
- 新批次种子与原 M4.34 训练/留出，以及指定的旧 M4.37 评估种子区间严格不重叠。读取旧 M4.37 私有计划仅核对冻结权重SHA-256及排除种子，不使用旧评估得分训练或选阈值。
- 汇总按原始洗牌种子簇平均，不把相关的四个座位当4份独立样本。行动者具体切牌只在本机私有文件；可分享JSON仅包含无具体牌名/种子/手牌/模型权重的聚合量。

## Windows 本地执行

更新仓库后，在根目录直接运行（使用系统 Python，不必有 .venv）：

~~~powershell
cd D:\ChatGPT\MahTrain
git switch main
git pull --ff-only origin main
python examples\run_actor_discard_diagnostics.py --train-dir data/selfplay/m434-smoke --prior-evaluation-dir data/selfplay/m437-shadow-2 --seed-start 91300 --seeds 2 --out-dir data/selfplay/m439-actor-2
~~~

这会重新运行全新91300、91301两个原始洗牌种子的10场真实完整对局；旧M4.37的10场不会重复跑。91300只是与已知91100、91101不重叠的例子：若在其他历史实验用过91300、91301，需另选从未使用过的种子，程序只自动核对你指定的两个私有计划。

如果当前新批次中断，用同一命令加 --resume，可跳过已完整保存的整个5局簇：

~~~powershell
python examples\run_actor_discard_diagnostics.py --train-dir data/selfplay/m434-smoke --prior-evaluation-dir data/selfplay/m437-shadow-2 --seed-start 91300 --seeds 2 --out-dir data/selfplay/m439-actor-2 --resume
~~~

完成后读取：

~~~powershell
Get-Content data/selfplay/m439-actor-2/safe_actor_decision_diagnostics.json
~~~

## 输出安全级别

| 文件 | 用途与隐私 |
|---|---|
| PRIVATE_actor_diagnostic_plan.json | 包含训练路径、旧评估路径与模型SHA-256，仅本机 |
| PRIVATE_actor_diagnostic_seed_clusters/index-00000000.json等 | 每5局真实积分及行动者真实原版/候选切牌的逐手记录、具体种子，只存本机，不能公开 |
| safe_actor_decision_diagnostics.json | 可分享的原始洗牌簇级统计、行动覆盖、改切方向和座位净分均值 |

诊断切牌后的有效进张数量变化只是**同一当时可见信息下的局部牌效比较**。同种子基准局与候选局在改切后可能发生不同后续轨迹，不能把最终净分差简单归因给其中某个动作。

## 测试

~~~powershell
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m439_actor_discard_diagnostics.py" -v
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m436_frozen_shadow_four_seat.py" -v
~~~

前者是针对受控合法数据的快速保护测试，后者用真实引擎完成五局结算并核对M4.39本家观察数据。只有实际CI通过才能称为完成验证。
