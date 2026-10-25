# M4.27：挑战级 AI 延迟补杠决策的同局面归因与门槛解释（v1.37）

## 起点与目标

M4.26 已合并 [PR #126](https://github.com/CrazyA1ice/MahTrain/pull/126)，其24个合法构造检查点出现**5次**“当前挑战级延迟补杠守门策略 vs 离线仅去掉该守门条件”真实行动分歧（5/24）；同一批检查点中，当前策略在当巡补杠（可收钱）时选择补杠9/24，在下一巡延迟无钱情境下选择补杠0/24。

**本轮要解释分歧来自哪一条既有决策条件，暂不追求胜率或新的阈值**。自然样本在M4.25的128局中无延迟补杠策略行动分歧，故不能拿其零差异证明守门策略优秀，也不能把M4.26人工构造的24种检查点当成自然发生概率。

## 真正隔离的对照

同一个权威 `FourPlayerOpening` 构造局面，在真实完成其它三家摸打、回到自己下一巡且确有合法延迟补杠选项后，获取**玩家自己授权的`private_view(0)`**。用同一个视图做两次候选动作评估：

- **当前策略**：直接 `MahjongAgent("challenge").kong(view)`。
- **守门条件消融**：在**提供给 AI 的临时局部视图副本**把 `legacy_bugang_cash_rule` 改为 True，只用于跳过 AI 自己的严格延迟补杠门槛；权威游戏对象及其真实计价仍是最新 `current_m423`，不会因此发生任何非法收钱。

这一对照确保相同牌、相同摸牌、相同公开信息，不把下一巡新增手牌与另外三家弃牌变化混成所谓的“杠钱因果效应”。两套AI允许的杠动作都必须来自同一个真实服务端 `kong_options`。

## 逐检查点解释的决策顺序

新离线分析器严格复用已上线的 `_cut_shanten`、`shanten_13`、`_call_outlook`、`_outlook_better_than_baseline`（而不是另写一个竞争性的麻将评分器）：

1. 用所有合法普通切牌找最小向听，然后以真实公开已见牌计算最优普通切牌后的公开有效进张和番值代理。
2. 在合法补杠情况下计算补杠后的向听、有效进张与代理价值。不读取其他家暗手或真实未来牌墙；`value` 不是真实预测胜率、奖金期望或经校准的胡牌概率。
3. 先排除退向听、已验证天听未保留、有效进张彻底消失和未达到原`75%`进张或价值下限的候选。
4. 仅在**向听相同且通过前面原有下限**时，才归因为新增的严格延迟补杠限制：`guard_ukeire_down`（进张减少）、`guard_fan_proxy_down`（番值代理减少）、`guard_both_unchanged`（两者都没有增益）。
5. 分开报告“这个补杠候选被新增门槛拒绝”与“最终行动真正与消融策略不同”，因为玩家在同巡还可能有其它合法暗杠等候选。不能把多个候选的变化等同于实际可观察行动改变。
6. 若同一授权视图中两套策略确实选择了不同动作，必须可由严格守门这一条新增条件解释；如不是则主动抛错以阻止出具误导性对照结果。

逐局仅输出两种向听、有效副本数、番值代理、分类原因、是否真正行动分歧等**匿名摘要**。不对外发布任何对手暗手、墙牌、未公开听牌和隐藏的赢家数据，也不能用公开代理值反推成期望积分。

## 项目实现

- `src/mahtrain_core/ai_delayed_bugang_attribution.py`：只读、同授权局面逐候选解释和严格的四分片合并审计；真实行动必须与原因一致。
- `tests/test_m427_delayed_bugang_attribution.py`：合法状态、跨巡真实牌守恒、禁止旧规则、拒绝非本巡牌、旧75%门槛顺序、拒绝篡改原因、计数独立性。
- `examples/audit_delayed_bugang_attribution.py`：复用M4.26的24种检查点、四分片输出和合并CLI。
- `.github/workflows/m427-bugang-attribution.yml`：Python3.11/3.13单元，四个分片及不可缺项的审计汇总，自动打印各原因分类与5个分歧局面的解释资料；仍需全仓CI通过才能合并。

运行：

```bash
python -m unittest discover -s tests -p 'test_m427_delayed_bugang_attribution.py' -v
python examples/audit_delayed_bugang_attribution.py --shard set_a --out m427-set_a.json
python examples/audit_delayed_bugang_attribution.py --shard set_b --out m427-set_b.json
python examples/audit_delayed_bugang_attribution.py --shard set_c --out m427-set_c.json
python examples/audit_delayed_bugang_attribution.py --shard set_d --out m427-set_d.json
python examples/audit_delayed_bugang_attribution.py --combine --input-dir . --out m427-audited-summary.json
```

## 结论边界与后续方向

全部24个检查点是**条件化构造的研究案例，不是独立随机对局**。例如某个案例的有效进张数从10变9，但属于公开已见牌计算的牌效代理；不能据此宣称补杠会在实际对局损失固定积分。若发现5个行动分歧都由某条守门条件产生，也只证明因果上的“决策门槛改变→行动选择改变”，不能推出“哪种行动策略长期净分更高”。

本轮**不更改线上挑战级AI、没有调收益阈值、不改变补杠杠钱及根番规则**。后续要对实战收益提出结论，仍需让实际合法选择引导真正的对局延续、在独立隐藏世界或新自然种子上核验官方胡牌、杠钱、流局收益，并防止挑选有利的测试样本。
