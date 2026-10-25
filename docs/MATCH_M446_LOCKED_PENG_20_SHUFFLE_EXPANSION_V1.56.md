# M4.46：冻结原M4.45碰牌策略，独立20洗牌扩样对照

## 实验依据

用户提供的M4.45安全汇总：2个独立洗牌、10场完整比赛；原挑战级10次可碰却选择过，8次不满足向听/听牌规则、1次有明杠、1次候选真正改碰。官方平均净分差为0，胡牌-12.5和流局+12.5互相抵消。这不是策略变强的证据。

## 固定研究计划

本轮不再调节碰牌参数。使用原M4.45同向听、碰后有效进张增加1或2张才改碰的**完全相同**实现，不修改正式挑战级AI。此前的两枚测试种子绝不混入本轮样本或绩效均值。

新20个完全独立的原始自然洗牌，每个完成1场原Challenge完整基准局与4场依次轮换四座位的候选对局，总计100场真正四川血战麻将，全部用真实官方结算。四座位比较属于同一种子的相关重复，不计为独立样本。报告每簇真实分差和总体均值、胡/杠/流局分项、实际改碰次数、真正发生改碰的独立seed数量；禁止用单次改碰解释全局结算。

程序将校验先前M4.45私有计划、全部旧付分分片SHA256、公开安全报告与原训练源指纹，明确排除旧M4.45种子；底层M4.45继续验证M4.34训练与M4.37/39/41/42/43/44历史种子。新的M4.46私有计划额外冻结策略源代码SHA256、模型来源和所有运行参数，改变后无法续跑。中断可复用整个已完成的五局种子簇，失败的未完成簇从头打完。

## 本机 Windows PowerShell 命令

先更新主分支：

~~~powershell
cd D:\ChatGPT\MahTrain
git switch main
git pull --ff-only origin main
~~~

运行新20独立种子（92500到92519必须没有用于其他未登记实验）：

~~~powershell
python examples\run_pong_independent_expansion.py --train-dir data/selfplay/m434-smoke --prior-m445-dir data/selfplay/m445-pong-2 --seed-start 92500 --out-dir data/selfplay/m446-pong-20
~~~

出错或中断时，原命令尾部加 --resume；不能改变seed、模型来源、代码或实验计划。全部100场比赛在本机完成，不依赖额外付费Actions。

完成后：

~~~powershell
Get-Content data/selfplay/m446-pong-20/safe_pong_independent_expansion.json
~~~

只上传上面安全JSON，不上传任何PRIVATE前缀的文件、模型权重、手牌或私有种子。所有私有数据保存在本地被Git忽略的data/selfplay目录。

## 验收与统计边界

~~~powershell
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m446_pong_independent_expansion.py" -v
python -W error::SyntaxWarning -m unittest discover -s tests -p "test_m445_pong_threshold_trial.py" -v
~~~

M4.46快速测试用仿真完整结算结构验证数据合约及100场调用、数据隐私和断点恢复，不代表CI替你跑了100场真实麻将。真实五局引擎已经由未修改的M4.45集成测试覆盖。本轮20枚shuffle有利于估算研究候选的实际改碰覆盖率；若改碰仍少，不能承诺充分统计功效、显著性或政策强度改进。更不能看本轮分数再选阈值，并在同一测试集上报告新策略变强。
