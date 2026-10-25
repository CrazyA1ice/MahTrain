# M4.45：可碰却过的等向听 +1/+2 有效进张对照（v1.55）

## 实验起点

M4.44 真实安全汇总：两个新独立洗牌，2局真正四人挑战级比赛，192 次响应中 175 次只能过牌；14 次有碰/明杠可选，原Challenge碰8次、明杠2次、有合法碰杠而过牌4次；自家杠检查79次但合法暗杠/补杠0次。四次过牌不等于四次错误或已有因果结论。

复查原Challenge的碰牌规则：若碰后不改变向听阶段（且仍未听牌），则要求碰后最佳切牌的有效进张至少比过牌多3张，才会主动碰。M4.45在训练/评估分离的前提下，**事先冻结一个更小的研究性机会窗**：仅在原Challenge选择pass、合法允许peng但不可明杠、天听没有被破坏、碰后向听相同且仍未听牌、有效进张增加恰好1或2张时，新候选改为peng。其他行动（胡、换三张、定缺、杠、自摸、切牌）继续沿用原Challenge。无任何线上AI变更，不对旧M4.44已看过的结果调整阈值。

## 真正的官方积分对照

每一个全新自然洗牌种子运行5场完整血战麻将：1场原四家Challenge基准，4场候选轮流占据四座位（其他3家维持Challenge）。记录每场真正终局净积分差、胡牌/杠钱/流局官方账本构成、行动机会和实际改碰数量。同一个原shuffle内4次座位轮换相关，只当作1个统计簇。

M4.45保留错误即失败的SHA-256私有原子种子分片、完整5局才归档的中断续跑规则、四人官方净分零和与5局结算核验、训练模型指纹及原历史shuffle区间排除。报告只保存统计数字，不含具体牌、暗手、种子、墙序或训练模型权重。只有两个新shuffle时，不能做显著性、总体更强或单动作因果结论。未改碰且得分差0仅表示退回原Challenge。

## Windows PowerShell

在仓库根目录更新并执行：

~~~powershell
cd D:\ChatGPT\MahTrain
git switch main
git pull --ff-only origin main
python examples\run_pong_threshold_trial.py --train-dir data/selfplay/m434-smoke --prior-m444-dir data/selfplay/m444-call-frontier-2 --seed-start 92300 --seeds 2 --out-dir data/selfplay/m445-pong-2
~~~

92300、92301不应与**其他没有登记的私人实验**重叠；代码自动排除已知M4.34/37/39/41/42/43/44原shuffle范围。默认需10场真正完整的四人官方结算。中断后将原命令原样重新运行，加 --resume；已经保存且校验完整的5局簇不会重打，未完成簇会完整重打。

执行后查看并**仅上传安全JSON**：

~~~powershell
Get-Content data/selfplay/m445-pong-2/safe_pong_threshold_trial.json
~~~

PRIVATE_pong_threshold_plan.json、PRIVATE_pong_trial_seed_clusters及过去所有PRIVATE文件保留在本地 data/selfplay 的 gitignore 目录，不向公开GitHub提交。

## 验收

~~~powershell
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m445_pong_threshold_trial.py" -v
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m436_frozen_shadow_four_seat.py" -v
~~~

专项与真正规则引擎集成测试均须核对后才能合并主分支。本轮只是探索相同向听阶段碰/过的收益差异，不承诺新策略优于原Challenge。
