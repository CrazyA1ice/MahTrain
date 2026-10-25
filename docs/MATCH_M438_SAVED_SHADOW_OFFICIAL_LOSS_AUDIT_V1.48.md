# M4.38：冻结候选 AI 真实积分损失构成的只读审计（v1.48）

## 这轮针对什么问题

用户完成了 M4.37 的 2 个独立洗牌簇、10 场完整对局。已提供的安全聚合显示：共 115 次候选切牌机会、70 次实际改变切牌，四座位按原始洗牌簇配对后的官方净积分差为 **-370**；四个座位均为负，两个原始洗牌簇均为负。**这只是两个独立种子的观察结果，不足以得出正式 AI 强度结论。**

要判断“改切为什么导致劣势”，先必须把实际得分拆成胡牌、杠钱、流局三种**已发生的官方支付项目**，核对各座位和独立洗牌簇，排除积分统计混用。同时重要的是，**仅凭最后的积分并不能推断是哪一张切牌造成损失，更不能把积分差简单除以改切次数当作单次行动因果收益**。

本轮首先开展**只读、零重复计算**的账本分解。没有改动任何在线挑战级 AI、冻结权重或已经完成的评估结果。

## 对已有 M4.37 Windows 结果立即使用

在仓库根目录更新合并的 main：

~~~powershell
cd D:\ChatGPT\MahTrain
git switch main
git pull --ff-only origin main
~~~

用已经存在的评估目录做输入，另选全新报告目录：

~~~powershell
python examples\audit_saved_shadow_loss.py --evaluation-dir data/selfplay/m437-shadow-2 --report-dir data/selfplay/m438-audit-2
~~~

- 不需要再运行 M4.34、M4.35 或 M4.37。不会重新训练，也**绝不会重新打原来的10局**。
- 只读取 M4.37 的保存簇文件、原始私有压缩账本和公开安全汇总，要求原始种子数量、全部四座位、模型 SHA-256 指纹、簇级 SHA-256、真实支付组成与总数相互吻合。数据不完整或有破损就拒绝生成报告。
- 旧M4.36输出没有M4.37的独立保存簇，不能作为输入。输入的 PRIVATE_* 文件只能保留在本机。
- --report-dir 必须是不同且新建/空的目录；不要指向已有的 data/selfplay/m437-shadow-2，也不要覆盖原评估目录。
- 分析不需要额外依赖库，Python 3.11或更高版本即可。

成功后用：

~~~powershell
Get-Content data/selfplay/m438-audit-2/safe_shadow_loss_attribution_summary.json
~~~

## 生成的文件

| 文件 | 内容 | 共享范围 |
|---|---|---|
| safe_shadow_loss_attribution_summary.json | 各座位平均官方净分差、三类支付的四座位原始种子簇级平均、胜负方向计数、真实改切覆盖 | 可提供用于分析 |
| PRIVATE_seat_rotations.csv | 逐原始洗牌种子 × 四座位的私有原版/候选官方净分、胡牌/杠钱/流局差额、改切次数 | **不可公开** |
| PRIVATE_seed_cluster_totals.csv | 每个原始洗牌种子四座位均值与三类支付构成，用于本地独立簇统计 | **不可公开** |

安全 JSON 绝不包含具体洗牌 seed、手牌、隐藏未来牌墙、对手暗牌、模型权重或本机原训练路径。CSV 含真实种子，仅保留本地 gitignored 的 data/selfplay 下。

## 如何解读各字段

- paired_mean_official_net_delta_points：四座位对照的配对净分差，先在**每个独立原始洗牌簇内平均四座位，再跨簇平均**，应与已知 M4.37 报告一致。
- paid_net_delta_accounting_by_component_points.win / kong / exhaustive：胡牌、杠钱、流局官方分的**账本分解**，三项代数和必须等于总净分差。分解是事实记账，**不是因果归责**。
- paired_delta_by_seat_points：各个位置对应原版的净分差；0/1/2/3为四个座位，没有声称座位间独立。
- per_seat_negative_comparison_counts 等：每座位跨原始洗牌的负/正/零次数，帮助定位是否某些座位有系统性现象。2个种子只可视为线索。
- seed_clusters_positive / negative / tied：按独立原始洗牌簇汇总配对均值的符号，比把同一种子生成的四座位误记成4次独立试验更规范。
- negative_rotations_with_overrides：出现改切且对照终局净分为负的座位局数量。**同一局多次改切，无法定位哪一次导致后续差异**。

## 本轮范围与下一轮必要数据

由于旧M4.37只在每局汇总 shadow_override_count，没有逐手记录“原版切牌、候选切牌、冻结模型分差、改变前后公开可见牌效、剩余可见张数”等字段，本轮**不能**以现有文件做“70次改切中的具体哪次造成损失”的结论。若后续有需要，M4.39应在**全新评估种子**中对行动者视角合法决策逐手写私有诊断，禁止上传暗手、并明确比较并非同一后续轨迹的单动作反事实；需先冻结诊断口径，不能拿已经观察过的这2个种子选阈值后再称为独立测试。

## 测试

~~~powershell
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m438_saved_shadow_loss_audit.py" -v
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m436_frozen_shadow_four_seat.py" -v
~~~

前者使用可控合法协议形状做快速测试（无真实牌局）；后者在五场**真实运行并结算**的现成集成测试基础上，额外验证账本只读审计。最终是否通过必须以真实运行结果为准。
