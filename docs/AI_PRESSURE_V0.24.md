# MahTrain M3.12：公开副露弱风险规则触发诊断（v0.24）

## 目标与边界

M3.11 的5种子对照中，完整挑战档与关闭弱风险平局规则的版本分别出现15次和18次胡牌事件，但不同策略参与的对局历史互相影响，不能把这3次差值直接归因于风险规则。M3.12 只增加诊断，不修改任何AI实际切牌或四人规则状态机。

## 同局面影子比较

对完整挑战、关闭弱风险两种策略的每次真实切牌，复用已经计算过的向听/有效进张候选及本家合法视图，只读取其他活跃玩家的**公开副露**。依次按定缺优先、最小向听、最大有效进张过滤；对余下并列牌分别执行“公开副露压力分数优先，再按固定牌序”和“仅按固定牌序”两个排序。记录两个排序是否选不同牌，但绝不把假设切牌提交游戏，也不把未出牌的影子候选牌种写入 trace 或可分享报表。

指标：decisions（真实切牌数）、effective_ties（有效进张仍并列）、pressure_present（存在公开副露压力）、pressure_discriminates（并列候选的压力分数不同）、would_change（启停压力会换一张牌）、actual_changed（完整挑战档实际因压力改变切牌）、games_with_would_change（至少一次不同的对局）及 wins_in_changed_games/deal_ins_in_changed_games（这类对局的真实胡牌与放铳事件）。

这些局内事件与规则触发只能描述**关联**，绝不能解释为压力规则导致获胜或放铳。压力分数不同也未必改变牌序选择。

## 命令行

~~~bash
python examples/benchmark_ablation_ai.py \
  --seed-start 30 --seeds 5 \
  --json-out results/m312.json \
  --csv-out results/m312_policy.csv \
  --contrast-csv-out results/m312_contrasts.csv \
  --pressure-csv-out results/m312_pressure.csv \
  --html-out results/m312_report.html
~~~

压力 CSV 为每独立种子、每策略的聚合整数，UTF-8 BOM。离线 HTML 新增触发诊断统计表，不需要网络，不含对手暗手、牌墙或影子候选牌种。M3.11 的方向统计、留一种子分析和 Bootstrap 仍保留，统计独立单位是**洗牌种子**，不是一个种子里的五局。

CI 对 Python 3.11/3.13 单测和五种子25局四人规则继续验收。M3.12 额外验证：actual_changed 不超过 would_change，不超过 pressure_discriminates，不超过 effective_ties，不超过 decisions；108张牌物理守恒；公开回放中没有影子候选牌。

## 后续方向

若压力规则几乎不改变动作，需要增加公开副露局面的覆盖，而不是据少数胡牌事件直接删除。若触发较多，也需要更大样本和独立策略测试。当前正式杠钱与流局结算仍未确认，胡牌事件不等于完整胜率。
