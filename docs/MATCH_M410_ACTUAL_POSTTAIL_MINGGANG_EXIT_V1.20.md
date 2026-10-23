# M4.10：明杠后真实补牌与弃牌风险的合法时间顺序审计（v1.20）

## 承接前轮

M4.09 在开发组 42000–42007、独立保留组 43000–43007 共64局自然对战中，观察到12次合法碰／明杠双选项，原挑战级实际获得7次明杠，未出现相应杠后弃牌被胡。因此尚无足够事件支持“公开危险指数能准确预测点炮概率”。前一轮还修复了一个基本统计边界：`read_discard_threat` 是最多三名活跃对手危险度之**和**，可能高于1，不能当成0–1概率或将超过1错误拒绝。M4.09 全部自然专项验证完成后仍需整体Python全量CI才能合并。

## 本轮实际新增

本轮坚持**不改正式AI选择**。在 `AfterTailCutObserver.discard` 中先照原 `MahjongAgent.discard` 作出切牌决策，再判断当前仅本人可见的合法游戏状态是否为：最近公开动作正好是“自己明杠→自己尾摸补牌”，且公开记录能够唯一回溯到此前源玩家的出牌编号。符合条件时，才根据此刻合法可见的公开牌桌和已选择的真实切牌调用 `read_discard_threat` 记录*实际出口风险指数*。

这个指数计算于尾摸补牌**已真实发生之后**，是新时间点的合法观察，不可提前使用来替明杠做决策，不可读取墙尾的未来牌、不输出尾摸种类、不输出暗手，也不会影响原有切牌、碰杠或胡牌优先级。

只有终局以后才把：

1. 明杠前：`MingGangFollowThroughAgent` 的真实合法双选项窗口、初始弃牌 `discard.index`、既有手牌候选的公开最低风险等级；
2. 牌权获授：规则仲裁后确实成功 `ming_gang` 与唯一官方 `KongLedger.id`；
3. 明杠后：是否真的发生 `kong_supplement` 后的本家出牌、真实 `after_kong` 且同一 `kong_id` 的公开弃牌编号，以及切出前本人视图中计算的公开危险等级；
4. 结果：是否被一炮多响／普通点炮，是否因此冲销**同一笔**杠钱；

连接为只包含聚合频数的 `low/mid/high` 前后转移矩阵，另按开发／保留、独立初始洗牌种子报告同级、升档、降档和真实点炮次数。

如果明杠后出现自摸胡、再次杠补牌等情况而没有针对该明杠的直接出口切牌，就单独计 `awarded_without_exit`，不能把它算作“低风险或安全弃牌”。错序、重复出口、假冲销、偷取暗信息的人工参数全部被测试拦截或完全忽略。

## 新固定样本及验收

开发组 **44000–44007**，保留组 **45000–45007**；每组8个新独立洗牌×4个挑战级座位 = 32完整牌局，共64局，**16独立洗牌种子**。样本均按编号连续取，不按是否被胡挑选，重复座位的局数不当成独立样本。

文件：
- `src/mahtrain_core/ai_minggang_actual_exit_risk.py`：离线补牌后原策略切牌视图与终局账本对应。
- `tests/test_m410_minggang_actual_exit_risk.py`：真实108张牌合法明杠并尾摸切牌、基线行动不变、账本一次冲销、多玩家同炮、缺失或伪造观测拒绝、自然终局匿名性。
- `examples/audit_minggang_actual_exit_risk.py`：独立自然种子聚合 CLI。
- `.github/workflows/m410-actual-posttail-minggang-exit.yml`：专项与两组真实自然对战，保存不含暗牌的结果 JSON。

```bash
python -m unittest discover -s tests -p 'test_m410_minggang_actual_exit_risk.py' -v
python examples/audit_minggang_actual_exit_risk.py --cohort development --seeds 8 --output results/m410-development.json
python examples/audit_minggang_actual_exit_risk.py --cohort holdout --seeds 8 --output results/m410-holdout.json
```

## 研究限制与上线条件

“补牌前最低候选风险”和“补牌后实际选择切牌风险”是不同时间点、不同决策对象的**描述性指数**；前者不知尾摸和新手牌，后者只在真实已获杠且最终实际出牌者身上可观测。因此升档/降档不能归因于明杠这个行动的作用，更不能把0次点炮推成0%的风险。

至少要有足够多的**独立洗牌种子**承载不同分组的实际获杠和实际点炮，之后才可讨论校准、置信区间或真实反事实对照。此处不引入“期望收益”假数，不修改在线AI、Web页面、官方规则或胡／杠／流局钱数。每次合并都以当前提交的专项和全量CI全部通过为前提。
