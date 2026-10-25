# M4.29：延迟补杠与保留手牌的真实终局结算对照（v1.39）

## 核心问题与过往证据

M4.26在24个人工构造且符合108张物理牌守恒的合法延迟补杠检查点中，发现挑战级 AI 在5例（**10、12、18、20、22**）对“严格新守门”与“旧门槛消融”实际作出不同选择。M4.27归因确认其中2例有效进张减少、3例代理进张不变，说明决策门槛确实改变了这5个案例的动作。M4.28进一步验证正常的根番和番数封顶、杠后真实尾摸，以及抢杠的不确定性，但仍未衡量行动之后的**最终官方净积分**。

本轮首次在这5个已知争议场景，从**同一个真实物理牌局快照**，对照“本巡强制延迟补杠”与“本巡不补杠并按正式挑战级 AI 选择普通切牌”，随后让全部四家 AI 使用真实规则，打完到三家胡牌或牌墙用尽。正式补杠钱规则仍为 `current_m423`：前一巡留下的第四张可以晚补杠但没有任何杠钱；根番+1只在随后有法定胡牌及番数结算时体现。

## 预先冻结的试验

- 案例ID `(10, 12, 18, 20, 22)` —— 仅来自**之前已记录的策略分歧案例**，不根据本轮输赢挑选。每例3种预先固定的未来牌墙重排种子（`79000 + 案例ID×100 + 复制序号0/1/2`）。同一次序号的两策略臂接收**完全一致的现有对手暗手、实体牌及未公开未来墙顺序**。
- 每个案例3个条件化未来牌墙，共15组配对；每组2场实打到底的权威比赛，**合计30场完整对局**。对局共同条件：已合法碰三张并留下第四张、下一巡再次真实摸牌；其它三家正常轮流摸切后才能到自己的选择节点。四家控制策略固定：玩家0挑战级、玩家1基础、玩家2高级、玩家3独立形状基线。
- 实验臂：
  - `forced_cashless_bugang`：玩家0本巡合法声明保留第四张的**延迟补杠**，必须确认抢杠窗口之前的 `cash_eligible=False`；后续该杠可被真实对手抢杠，失败时不得获得杠钱。
  - `forced_no_bugang`：玩家0本巡放弃这次补杠，使用正式挑战级 AI 的现有普通弃牌选择；并不额外禁止下一巡 AI 自主碰杠。两分支后续均按当前AI真实规则行事。
- 配对比较只允许发生在本次唯一干预上；两分支随机数生成器、对手初始暗手和初始牌墙一致，但**第一次行动不同以后，摸牌、响应、补杠、补摸机会与整个未来事件序列都可能分叉**，不能把对应轮次的未来视为完全相同。
- 记录玩家0的权威`official_net`、`win_points`、`kong_points`、`exhaustive_points`、胡牌、点炮、完成的杠和被抢杠次数；每局必须真实结束，所有座位总账本归零、三项分账严格等于总净分、牌数保持108实体守恒。

## 有效性边界

**这是条件化、已有决策争议的人工牌局实验，不是自然牌局采样！** 15组有物理约束的未来墙不是15个自然独立洗牌种子，三个墙排列仍共享同一人工设置的玩家手牌、碰牌和历史，5个案例是刻意选择出的决策分歧，不是随机人群分布。所以最终每例可报告实际官方净积分差，但是：
- **不能把分组平均差当成长期获利期望或胜率优势**，不提供虚假的95%置信区间或显著性检验；
- 除实际权威支付之外，不将“已有根番”“保留牌效”“尾摸未知副本比例”“被抢杠可能性”直接转换为固定期望分值；
- 不外传对手暗手、真实未来牌墙、内部完整私人状态；只发布各局可审计的汇总数据和经过验证的真实三项分账；
- 无论正负，都**不据这15个条件化样本直接调在线挑战级 AI 门槛**，后续需进行新独立自然采样和有数据支持的对手抢杠风险校准。

## 实现与复现

- `src/mahtrain_core/ai_delayed_bugang_terminal_paired.py`：从原合法场景克隆物理牌局、指定唯一首步行动、由四个真实AI打完权威对局；审计每个 seat 的真值胡牌/杠钱/流局/净分零和；封存5个案例×3种未来墙×2策略臂。
- `tests/test_m429_bugang_terminal_paired.py`：验证真实实体守恒、正常补杠无杠钱、配对墙与玩家视图可复现、实际终局分账、拒绝缺少或篡改案例和账本。
- `examples/audit_delayed_bugang_terminal_paired.py`：运行各案例分片、严格合并全部输出。
- `.github/workflows/m429-bugang-terminal-paired.yml`：Python3.11/3.13新旧规则回归、5分片平行真实对局、最终合并检查30场真实结束对局及正式分账，并保留每案例差异JSON。

```bash
python -m unittest discover -s tests -p 'test_m429_bugang_terminal_paired.py' -v
python examples/audit_delayed_bugang_terminal_paired.py --shard case_10 --out m429-case_10.json
python examples/audit_delayed_bugang_terminal_paired.py --shard case_12 --out m429-case_12.json
python examples/audit_delayed_bugang_terminal_paired.py --shard case_18 --out m429-case_18.json
python examples/audit_delayed_bugang_terminal_paired.py --shard case_20 --out m429-case_20.json
python examples/audit_delayed_bugang_terminal_paired.py --shard case_22 --out m429-case_22.json
python examples/audit_delayed_bugang_terminal_paired.py --combine --input-dir . --out m429-audited-conditional-terminal.json
```

## 决策口径

如出现某一人工案例中选择晚补杠带来的正或负的官方净分，这是**预先指定牌局和对手策略下的结果**，用于发现需要进一步研究的情境。若正负交错则保留不同案例的重要异质性；若恰好同向也不足以宣布已验证 AI 更优。M4.29 的代码**不更改任何现有线上AI、分数计算、庄家规则或 UI**。
