# M4.08：真实明杠终局入账／冲销与点炮结果审计（v1.18）

## 出发点与前一轮验收

[M4.07](https://github.com/CrazyA1ice/MahTrain/pull/107) 已在当前正式规则下完整执行预先声明的开发组 38000–38003、独立保留组 39000–39003：每组四席×四种子×两研究臂＝32局，共64局。全部专项／规则CI完成。**开发组仅1次自然碰／明杠双选项（基线选明杠），保留组2次（1次原策略过牌，1次原策略明杠）**；只读研究档与原挑战级动作轨迹、胡／杠／流局账目完全一致。正式策略无干预，因此没有“新策略更强”的证据。

M4.08 不再把“下一张尾摸”“可能获得杠钱”“候选弃牌危险指数”混为一个虚假的净收益指标。本轮从真实执行后的权威杠账建立**完整终局生命周期审计**：知道哪次明杠真正生效、是否结算了杠钱、最后是否因紧接的杠后弃牌被胡而退回。

## 权威事件的核对方式

- 对每局的实际 `FourPlayerOpening.public_state()` 核实 `KongLedger.events`、`entries`、`balances`，与模拟器原有的 `public_events`、`official_kong_balances` 一一对应。
- **明杠**是源出牌者支付 `2 × base`，**暗杠**由本房规指定仍活跃的付款者分别支付 `2 × base`，**补杠**分别支付 `1 × base`。只处理研究局明确传入的 `offline_kong_base=1`，绝不把未定价视作零，也不将系数当成杠钱底分。
- 每一笔 `charge` 的座位／金额／唯一杠事件ID都精确核验；`voided` 必须有同金额反向 `reversal`，并在实际弃牌历史中找到同 `kong_id` 的 `after_kong` 且 `won_by` 非空。支持多家同炮胡牌，但**只冲销一次杠钱**。总账四家严格零和。
- 利用 M4.07 的授权前置视图，记录同一合法窗口是否同时提供碰与明杠、原 AI 实际决定什么，再以**公开动作顺序**识别是否真正获得明杠的牌权。所选明杠可能被更高优先级胡牌抢先，不能将选择次数直接当成实际获杠次数。
- 仅在牌局终止后，从早先离线 `offline_observer` 保存的游戏对象中读取权威的公开账本状态；这个对象不传给 AI 动作决策、不写到结果 JSON，也不触及对手暗手、真实墙尾。入场时采集的风险指数只以“低／中／高”描述性区间进行匿名分组，**不是点炮概率**。
- 实际终局仍单独保留 `official_net = win_points + kong_points + exhaustive_points` 的核算，不把出现或未出现点炮归因于明杠选择，不在旧样本上反复调参。

## 代码与独立对照

- `src/mahtrain_core/ai_minggang_ledger_followthrough.py`：权威逐笔冲销验证、实际明杠与杠后弃牌关联、公开双操作决策与最终牌权匹配、真实独立种子统计。
- `tests/test_m408_minggang_ledger_followthrough.py`：名义付款、实际已入账、杠后多人胡牌与等额一次冲销、错误付款方／假冲销／坏账拒绝、真实108牌授权边界、真实终局与隐私检查。
- `examples/audit_minggang_ledger_followthrough.py`：新固定开发组 **40000–40003**，新独立保留组 **41000–41003**，共8个独立种子、32场单臂真实完整四席比赛，不人为构造自然明杠，零在线策略修改。
- `.github/workflows/m408-minggang-ledger-followthrough.yml`：专项与历史回归、两个自然组完整终局，保存两份聚合匿名审计文件。

复现：

```bash
python -m unittest discover -s tests -p 'test_m408_minggang_ledger_followthrough.py' -v
python examples/audit_minggang_ledger_followthrough.py --cohort development --seeds 4 --output results/m408-development.json
python examples/audit_minggang_ledger_followthrough.py --cohort holdout --seeds 4 --output results/m408-holdout.json
```

## 判断准则

同一个洗牌种子的四位置可以保证挑战级坐遍四家，但不是四个完全独立样本；窗口、事件与同局放炮均属于相关结果。**研究只有真实完成CI才能报告自然明杠、冲销和点炮数量**。出现零次冲销不能证明明杠没有风险。若自然样本过少，下一轮增加新的、预先固定的独立自然洗牌，不用人工构造出“收益显著”。

本轮完全不修改线上 `MahjongAgent`、实际前端、Web API、法律动作优先级、108张牌总数或权威胡／杠／流局结算；新增的是可审计的离线研究工具。
