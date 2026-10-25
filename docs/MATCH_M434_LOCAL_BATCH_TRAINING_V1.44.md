# M4.34 Windows 本地批量自对战与断点续跑（v1.44）

## 本轮变化

M4.33 已合并主分支：4个独立自然洗牌簇、4场原局和32场反事实终局共36场真实完赛。8个双候选决策点中0个通过两个未来墙下净分差严格同向筛选；不能认为现有离线模型已变强。

本轮改为 **本机 CPU 多进程自对战**，不用 GitHub Actions 做长期批量任务，也不依赖 GPU、PyTorch、外部API或收费云服务器。当前仅增加可靠的批量数据生产和诊断，没有自动部署新的在线麻将AI。

- 源码 src/mahtrain_core/ai_selfplay_local_batch.py：四名挑战级AI自然对战，继续调用M4.32真实规则和官方108张实体牌、杠钱、胡牌、流局分账。每自然原始种子最多2个不同玩家的合法双候选切牌节点，每节点两种合法后续墙序×两种出牌选择，都打到正式终局。
- 采用 Windows 可兼容的 ProcessPoolExecutor + 主入口保护，至多2×workers个任务在途，默认2个worker，最多16个。每个原始自然洗牌种子是一个独立任务，一个任务结束即保存本地私人分片。
- 每个分片采用临时文件、fsync和os.replace原子写入。中断后以完全相同参数运行 --resume：读取冻结的私人实验计划与哈希，所有已完成分片均重新核对原始种子所属训练/留出组、官方最终积分、真实分支计分、合法候选及隐私保护。校验失败即报错而非删掉负面样本或悄悄重跑。
- 批量汇总按种子顺序流式输出公开牌谱、私有训练数据和留出数据；逐原始自然种子先聚合再跨种子汇总离线权重，不把同种子两个动作×两个墙序误当成4个独立训练簇。
- 额外输出两个未来墙下配对终局积分差的绝对差值合计、均值、最大值，明确只能描述有限条件化分支的差异，不能当成总体方差、动作Q值或实力提升。
- 隐私输出限制：项目仓库内部仅可写入已有Git忽略的 data/selfplay 文件夹；也允许用户指定仓库外个人磁盘路径。私有洗牌种子、本家暗手与动作标签、研究模型权重都不进入公开CI附件。

## Windows PowerShell 本地操作

在项目根目录进入已经配置好的 Python 虚拟环境后运行烟雾实验：

~~~powershell
.\.venv\Scripts\python.exe examples\run_local_selfplay_batch.py --seed-start 89800 --train-seeds 2 --holdout-seeds 2 --max-checkpoints 1 --workers 2 --out-dir data/selfplay/m434-smoke
~~~

出现中断、或希望检验所有已有分片无需重新模拟：

~~~powershell
.\.venv\Scripts\python.exe examples\run_local_selfplay_batch.py --seed-start 89800 --train-seeds 2 --holdout-seeds 2 --max-checkpoints 1 --workers 2 --out-dir data/selfplay/m434-smoke --resume
~~~

独立的新批量试验示例（这只是本机计划，不代表已经实际跑完）：

~~~powershell
.\.venv\Scripts\python.exe examples\run_local_selfplay_batch.py --seed-start 100000 --train-seeds 100 --holdout-seeds 40 --max-checkpoints 2 --workers 4 --out-dir data/selfplay/m434-140seeds
~~~

新的种子区间、训练/留出个数、每局决策点限制都应使用**新的输出目录**。相同原始种子不得重复当成独立证据。建议先用2个worker，再按CPU和内存逐步提高进程数量。支持多至10万个原始自然洗牌簇的实验计划，但真实运行数千个原局与数万场条件化分支需占用大量CPU时间与磁盘空间，并未在云CI内完成此规模的实测。

## 文件与保护

| 本地输出 | 用途 |
|---|---|
| PRIVATE_plan.json | 参数、初始种子和SHA256指纹，保证续跑数据归属一致 |
| PRIVATE_seed_shards/index-*.json | 每独立原始种子一份真实已完成状态，是崩溃后续跑依据 |
| public_four_challenge_replays.jsonl.gz | 不含隐私种子、其他家未公开暗手、未知未来墙的完整公开对局快照 |
| PRIVATE_actor_train.jsonl.gz | 本家有权看到的真实动作特征、对应权威终局净分差和研究标签 |
| PRIVATE_actor_holdout.jsonl.gz | 与训练原始洗牌种子不重叠的独立留出样本 |
| PRIVATE_offline_model.json | 按自然种子簇加权的离线研究模型，并未上线 |
| PRIVATE_holdout_diagnostics.jsonl.gz | 留出条件化预测方向检验 |
| safe_aggregate_summary.json | 仅包含独立簇数、真实终局数、合法动作点数、严格同号标签、两墙分歧等聚合指标 |

## 当前可得结论

这是一套可靠批量运行和低风险数据采集工具，并不是已经会通过强化学习不断升级的麻将AI。仍需要更多合法条件未知世界、低方差收益估计、不同策略的冻结对抗和新的独立种子/座位均衡测试。留出实际可评分动作少于5时不输出准确率；即使样本足够，方向一致率也不能当成赢牌率或AI实力增幅。现有挑战AI、碰杠胡规则、牌桌UI和官方结算维持不变。
