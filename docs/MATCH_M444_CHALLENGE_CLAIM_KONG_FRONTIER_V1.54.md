# M4.44：真实四人挑战级对局中碰、杠、胡的合法行动空间审计（v1.54）

## 源于 M4.43 的实际结论

用户上传的 M4.43 真实安全聚合表明：两个新独立自然洗牌，18场真实完整结算比赛。风险优先与番值优先都各有92次本家切牌机会，其中22次存在原Challenge已允许、最低向听和有效进张完全相同的替代切牌，但所有22次又全部被新规则的风险/番值附加条件拒绝；两条研究候选均实际改切0次，八次座位轮换和原Challenge的真实官方净积分差都为0。

该零差是**策略根本没有实施改切**，不能说明强化成功、阈值最优、原Challenge达到理论极限，或新候选策略更强。在新种子未观察实际风险/番值分布前，不建议为拿到改切率而反复调整测试门槛。

## 研究方向与本轮实现

下一轮优先扩大合法行动空间的研究：四人四川血战麻将涉及拆碰、暗杠、补杠、明杠、抢杠胡等真实策略判断，仅优化切牌同效平局可能受限。M4.44只做**全新独立自然洗牌的原Challenge真实行动机会普查**，不训练任何新AI，也不修改原 Challenge、改变任何真实切牌或碰杠选择。

1. 原完整四人实战引擎，每原始seed仅1场真正官方结算对局；四家均为Challenge。观测代理继承正式 MahjongAgent，仍调用原版的 response 和 kong 决策，绝不另外随机抽取牌、访问对手暗手、窥视未来墙或增加预测工具。
2. 只从当前行动者正常的 own-view 合法选项统计：discard claim窗口中能碰/能明杠/能胡的次数，是否可碰又可明杠，是否有碰/杠机会但选择过；抢杠胡响应窗口提供胡/过的次数及原挑战级选择；自家摸牌后是否合法暗杠/补杠、是否可同时选择多种合法杠、选择杠还是保留不杠；自摸胡机会。
3. 将所有信息化为 per-seat **非牌面计数**，只存每个种子真实官方四座位净分和统计计数，没有牌名、真实暗手、未来墙、具体行动顺序、对手身份资料。
4. 每个原自然洗牌簇独立 SHA-256 原子保存，支持 --resume，旧保存簇不重打；验证四家官方积分零和、出牌前自摸胡/杠选项覆盖、响应动作合法、计数守恒和历史实验源模型指纹。
5. 用户的 M4.34 训练分片以及 M4.37、M4.39、M4.41、M4.42、M4.43 私有计划用来核对来源及排除已经见过的原始seed区间；不会把过去观察到的真实积分用于任何训练。

## Windows本地运行

合并后在仓库根目录更新并执行：

~~~powershell
cd D:\ChatGPT\MahTrain
git switch main
git pull --ff-only origin main

python examples\run_challenge_call_frontier_probe.py --train-dir data/selfplay/m434-smoke --prior-m442-dir data/selfplay/m442-safe-ties-2 --prior-m443-dir data/selfplay/m443-safe-tie-2 --seed-start 92100 --seeds 2 --out-dir data/selfplay/m444-call-frontier-2
~~~

新种子 **92100、92101** 是相对已知 M4.34、M4.37、M4.39、M4.41、M4.42、M4.43 独立区间的建议值；如你在其他未提供的本地研究中用过，请换成真正新的数字。两个新种子只需2场真正完整四人比赛（不是M4.43那样的18场策略轮换）。

中断后原命令末尾加 --resume；只复用完整结束、SHA校验通过的原始一局簇。

成功后查看：

~~~powershell
Get-Content data/selfplay/m444-call-frontier-2/safe_challenge_call_frontier.json
~~~

只需上传这个 **safe_challenge_call_frontier.json**。 PRIVATE_call_frontier_plan.json 和 PRIVATE_claim_frontier_seed_clusters/ 的真实源、seed及原分数只保留在本机仓库忽略的 data/selfplay 下，不上传 GitHub。

## 核心口径

- counts.claim_action_choice_windows：discard claim应答窗口中至少有碰或明杠选项的实际次数；不是独立洗牌数量，也不是有价值策略收益的事实。
- counts.claim_chose_pass_with_claim_available：尽管可碰/明杠，原Challenge选择过；后续最适合用来研究“过牌 vs 碰”的行动空间。
- counts.own_kong_checks_with_options：自摸/切牌阶段有合法暗杠或补杠选项的次数；counts.own_kong_chose_none_with_options表示保留不杠，下一轮可研究是否有更优的择机杠决策。
- counts.claim_legal_hu_windows / counts.rob_kong_legal_hu_windows / counts.own_self_win_opportunities：有合法胡牌机会的局面，不是默认“胡就最好”的理论证明。本轮只统计原Challenge是否执行，**不尝试故意放弃合法胡牌**。
- counts.response_pass_only_windows：仅能过牌，实际没有策略行动空间；用于避免把所有被动应答误记成可优化机会。

统计局部备选数量与真实全局收益之间仍存在区别。若碰和暗杠可选择且原挑战有明显pass行为，再进行一轮**合法行动价值归因的独立设计**；若这种机会数量很少，就应重新考虑是否需要重点研究全局形势而不是盲目增加打牌数量。

**两个独立shuffle只是小规模可行性和规则合规验收，不能据此作总体强度、显著性或单动作因果结论。**

## CI 与真实引擎验证

~~~powershell
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m444_challenge_call_frontier.py" -v
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m436_frozen_shadow_four_seat.py" -v
~~~

专项回归覆盖数据结构、种子隔离、原模型指纹、原子文件恢复、强制错误拒绝、响应与杠牌策略及随机流均不变。真实规则集成回归额外在同一自然洗牌seed下比较原版Challenge与新的观察代理**四家逐个官方终局净积分完全一致**。只有实际运行后才宣称通过。
