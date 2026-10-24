# M4.25：延迟补杠收益规则的独立样本扩容与账本审计（v1.35）

## 研究问题

M4.24 已合并 PR #124（合并提交 `dd06eda2`），修复了挑战级 AI 在补杠候选评分中误用先前弃牌循环残留牌名的错误。此前在 `current_m423` 新补杠杠钱规则下的真实配对试点（开发种子 64000–64001，留出种子 65000–65001）发现：开发组没有行动分歧，留出组存在一次真实改变成延迟补杠的行动；严格守门－旧门槛的座位平均正式净积分差为 -75（实验记分单位）。这不足以推断收益阈值最优。

本轮不更改规则引擎、不更改挑战级现行阈值、不使用旧研究种子直接充当新留出样本。目标仅是开展更大但仍属探索性的全新独立样本研究，在胡牌、杠钱、流局和净分四个维度检验守门策略是否有真正可观察的变化。

## 冻结策略和真实规则

两种 `MahjongAgent('challenge')` 均启用 `offline_ruleset='current_m423'` 且 `offline_kong_base=1`，即延迟补杠**都无法取得杠钱**，但杠成功后根番及尾部补摸保持正常：

1. `current_guard`：最新挑战级 AI，延迟补杠在同向听时要求牌效不退且有所改善。
2. `old_guard_ablation`：只关闭该保守门槛，其他碰杠、何切、抢杠、自摸、换三张、定缺均与上述完全一致。

实验只读取自家授权 `private_view`，从不把真实未来牌墙或其他玩家暗手提供给 AI。两策略按相同初始洗牌和同一座位配对，但行为分叉后后续墙牌抽取序列可能改变，因此不将“相同随机种子”说成“每巡面对完全相同的未来”。

## 固定的全新种子范围（不能先看结果挑选）

| CI分片 | 用途 | 独立初始洗牌种子 | 四座位轮换 | 策略数 | 完整对局 |
|---|---|---|---:|---:|---:|
| development_a | 开发 | 66000–66003 | 4 | 2 | 32 |
| development_b | 开发 | 66004–66007 | 4 | 2 | 32 |
| holdout_a | 留出 | 67000–67003 | 4 | 2 | 32 |
| holdout_b | 留出 | 67004–67007 | 4 | 2 | 32 |
| **合计** | **互不重叠** | **16个独立洗牌簇** | | | **128** |

每组独立洗牌种子8个，而不是64个。对照 128 局**不等于**有128个互相独立样本。不能以座位轮换或多次碰杠次数虚增有效独立样本数。

两个策略臂都由权威 `FourPlayerOpening` 完成真实108牌对局。报告每组每种子四座位平均的净分差（当前守门减去旧门槛）以及 Hu、杠钱、流局分项、赢牌、点炮、杠次数和真实干预次数。按独立洗牌种子计数正值、负值、零值簇。8个独立种子/组仍是探索，**不自动发布可信的长期优势结论或在看到结果后调参并复用同一留出组**。

## 新增代码

- `src/mahtrain_core/ai_delayed_bugang_scaleup.py`：预注册四个独立样本分片、保留完整128局官方结算审计、按独立洗牌种子汇总。拒绝分片错误、重复或漏记座位、非真实结束状态、单局胡牌/杠钱/流局官方净额不守恒、任何挑战座位或策略臂不一致。
- `examples/audit_delayed_bugang_scaleup.py`：分片运行与四份实战结果的**严格合并**；不保存暗手、未来牌墙或逐巡隐私记录，只保存合法的分量评分与公开类别计数。
- `tests/test_m425_delayed_bugang_scaleup.py`：正常样本、重复/遗漏、非法种子范围、旧规则混入、伪造分账、非零合法动作计数及样本独立性验证。
- `.github/workflows/m425-delayed-bugang-scaleup.yml`：Python 3.11/3.13 新旧规则回归；四分片平行跑128场；聚合任务自动下载全部CI实验记录，严格检查完整度、真实官方分账和种子集；最终报告写入 GitHub Actions Summary，并上传 `m425-audited-summary.json`。
- 全仓原始 CI 必须同时通过才允许合并。

## 运行与验收

```bash
python -m unittest discover -s tests -p 'test_m425_delayed_bugang_scaleup.py' -v
python examples/audit_delayed_bugang_scaleup.py --shard development_a --out m425-development_a.json
python examples/audit_delayed_bugang_scaleup.py --shard development_b --out m425-development_b.json
python examples/audit_delayed_bugang_scaleup.py --shard holdout_a --out m425-holdout_a.json
python examples/audit_delayed_bugang_scaleup.py --shard holdout_b --out m425-holdout_b.json
python examples/audit_delayed_bugang_scaleup.py --combine --input-dir . --out m425-audited-summary.json
```

## 结果的决策口径

如果新守门策略在开发与留出组都有足够数量的真实干预，净分方向一致且没有明显在胡牌、流局或其他规则上引入问题，可以在**新的下一批独立种子**上进一步开展后续确认，或者有针对性地研究当巡补杠的尾摸价值/抢杠风险。若没有真实干预、差异波动大、或收益不一致，**不应宣称更强，不应盲目收紧/放宽阈值**。

此文档记录的是试验前冻结协议，不包含尚未从真实GitHub Actions产生的统计结论。完成CI后以真实 Job Logs 与审计 JSON 为准补充最终报告。
