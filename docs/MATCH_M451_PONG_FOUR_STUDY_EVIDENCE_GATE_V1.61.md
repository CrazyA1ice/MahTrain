# M4.51：四轮真实碰／过研究的安全证据审计与停止门槛

## 为什么不再继续盲目扩展

用户已在本机完成M4.47~M4.50四份安全报告：

|轮次|独立原始洗牌簇|真实完整对局|有首次合法碰但原Challenge过的簇|每簇碰－过净分均值|独立簇正/负/零|
|---|---:|---:|---:|---:|---|
|M4.47|8|40|8|+20|3/3/2|
|M4.48|24|96|18|−30.83333|8/9/7|
|M4.49|24|92|17|+21.25|9/8/7|
|M4.50|48|180|33|−35|12/19/17|

这些是**条件在各自已实现真实局面上的pass/peng强制分支终局差**，不是“原Challenge vs 新AI的整局胜率”对照。各轮均值方向连续翻转3次。两个未来墙世界在同一个原始shuffle中相关，不能当成两个独立原始洗牌样本。

M4.49事后发现中盘20～39张剩余牌墙7个shuffle，强制碰减过均值+157.14286；前盘≥40张10个shuffle为−59。M4.50冻结这个唯一主比较，用完全新的48个原shuffle发现：中盘15簇均值−64.66667，前盘16簇均值−44.375，主差−20.29167；簇级4096次重抽样探索性95%区间[−163.49479,+119.30208]跨过零。新样本**没有支持中盘强碰更好**，也没有证明碰牌在所有真实牌局中普遍不好。

## M4.51程序的工作范围

M4.51 在本地只读取以上4份SAFE JSON：
- 验证四份协议版本、独立原shuffle数量8/24/24/48、基准与完整分支数、配对世界数、正负零原shuffle计数。
- 检验胡牌、杠钱、流局净分三分项与报告每轮的碰减过净分均值一致，允许五位小数的有限舍入误差。
- 要求各轮“原Challenge未更改”“旧测试未用于训练/混入新结果”“两个未来墙不是独立原始shuffle”的声明存在且为真。
- 核对M4.49和M4.50的前中后盘种子总数；从M4.50前/中盘均值重算主差值、核验Bootstrap区间和方向标记。
- 生成总览，仅记录每轮分别的样本量、样本均值、均值符号变化次数及当前决策 HOLD_CURRENT_CHALLENGE_POLICY_NO_PROMOTION。绝不合并各轮成未经定义的总效应估计，不依据哪次均值为正来修改策略。

**验证能力边界：** 这个程序只检查用户可分享SAFE数值汇总内部是否一致，不能独立重新证明私有原始对局真实执行、原seed从未复用或底层模型绝对不变。要证明那些，还必须继续保留之前各轮PRIVATE计划、真实结算分片和真实规则引擎证据；审计输出会标注这一限制。新的代码不改在线AI或判定规则。

## Windows PowerShell

先更新：

~~~powershell
cd D:\ChatGPT\MahTrain
git switch main
git pull --ff-only origin main

python examples\audit_pong_research_evidence.py
~~~

默认读取：
- data/selfplay/m447-pong-pass-8/safe_pong_pass_branch_rollouts.json
- data/selfplay/m448-pong-pass-24/safe_pong_pass_replication.json
- data/selfplay/m449-pong-strata-24/safe_pong_actor_strata.json
- data/selfplay/m450-phase-48/safe_pong_phase_confirmation.json

若另存了历史报告，可在CLI中以 --m447 / --m448 / --m449 / --m450 明确指定各文件。

安全输出目录：

data/selfplay/m451-pong-audit/safe_pong_evidence_gate.json

本轮**不运行新增的真实麻将对局，不需要再准备新种子，不会生成私有牌谱或改变挑战级AI**。只上传safe_pong_evidence_gate.json即可。任何PRIVATE结算分片继续保留在本地。

测试：

~~~powershell
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m451_pong_evidence_gate.py" -v
~~~

## 真正需要继续做的AI改进

目前这些实验只针对第一处可碰却过的单动作强制分支，不能证明“反复主动碰牌”的新候选策略在**整个真实游戏**中能赢更多分。后续应该在完全不同的训练集上使用行动者可见信息开发候选，冻结完整版本，然后用未见过的全新shuffle做完整四人牌局的候选与Challenge比较：胡/杠/流局的官方净分、不同座位、胡牌率、动作延迟。一个shuffle内的多座位不是新的独立样本。没有这个完整候选整局比较证据之前，继续保留Challenge和现有碰牌决策。
