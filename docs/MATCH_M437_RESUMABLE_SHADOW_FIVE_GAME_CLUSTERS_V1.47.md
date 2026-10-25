# M4.37：冻结模型四人实战的断点续跑和簇级账本审计（v1.47）

## 目标

M4.36 已实现每个**独立原始自然洗牌种子**五场真实终局对局：1场全挑战级基准＋4场仅替换一个座位为冻结离线候选，最终比较官方积分。它原本等整个批次跑完后才保存所有对局结果。若Windows本机关闭、系统更新或Python进程中断，已经完成的五场对局也会丢失，扩大到20个以上新种子时尤其浪费CPU。

M4.37 只改**实验调度、落盘和校验**，不改在线挑战级 AI、不改变冻结权重、不触碰真实规则结算。每成功完成一整个五局簇就原子保存一份私有文件；--resume 精确恢复同一模型、同一训练源、同一评价种子区间，只重算尚未完整保存的簇。

## Windows 本地命令

先更新代码，并确认已有M4.35模型存在：

~~~powershell
cd D:\ChatGPT\MahTrain
git switch main
git pull --ff-only origin main
python examples\run_local_uncertainty_analysis.py --out-dir data/selfplay/m434-smoke
~~~

使用**新**输出目录启动（示例新评价种子90100，与此前89800起的训练/留出不重叠）：

~~~powershell
.\.venv\Scripts\python.exe examples\run_local_shadow_headtohead.py --train-dir data/selfplay/m434-smoke --seed-start 90100 --seeds 20 --out-dir data/selfplay/m437-shadow-20
~~~

若任何原因中断，仅在同一个目录重新运行**完全相同**的命令，并在末尾加入 --resume：

~~~powershell
.\.venv\Scripts\python.exe examples\run_local_shadow_headtohead.py --train-dir data/selfplay/m434-smoke --seed-start 90100 --seeds 20 --out-dir data/selfplay/m437-shadow-20 --resume
~~~

注意：

- 首次运行**不要**添加 --resume。恢复必须已经有 PRIVATE_frozen_benchmark_plan.json。
- 不要变更 --train-dir、--seed-start、--seeds 或冻结的M4.35模型。恢复时这些内容都将核验，不相符直接拒绝。
- 首轮没有 --resume 时绝不会覆盖已有输出；重跑另一套参数，请使用新目录。
- 旧版 M4.36 已经生成的最终报告没有本轮逐簇检查点和新版计划标志，不能伪装成可恢复任务；必须用新的 M4.37 输出目录重新运行。
- 如果曾经写出最终汇总，但之后丢失了任何应有的逐簇文件，恢复会拒绝补算，防止误把损坏的完成记录当作正常中断。
- 五场真实对局必须全部完成才形成一个原始种子簇；如果程序在一簇中的第2或第4场中断，会重新计算**当前尚未完整落盘的这一簇**。已安全保存的簇不再模拟。
- 独立统计单位仍是原始洗牌种子：--seeds 20 意味着20个独立簇、100场真实对局，**不是**100个独立统计样本。
- 程序没有断点续跑的进度条服务，也没有跨机器任务分发或性能提速承诺；数据只保存本机私有目录。

## 输出文件与完整性

| 文件 | 含义 | 公开性 |
|---|---|---|
| PRIVATE_frozen_benchmark_plan.json | 同一训练文件夹、冻结模型指纹、新评价区间 | **仅本机** |
| PRIVATE_eval_seed_clusters/index-00000000.json 等 | 每簇五场结果、四座位逐项官方积分与SHA-256校验 | **仅本机** |
| PRIVATE_four_seat_paired_matches.jsonl.gz | 由通过审计的簇顺序合并的私有历史兼容结果 | **仅本机** |
| safe_four_seat_shadow_summary.json | 同一簇配对四座位的聚合积分、真实改切数、断点复用簇数 | 可公开 |

恢复会在启动任何新一局前，逐一检查已落盘簇的：编号范围、原始种子匹配、冻结模型指纹、四个座位各有一条、真实阶段已结束、胡牌／杠钱／流局账本差值一致、改切数不超过切牌机会、没有改切就不能凭空出现积分差，以及规范序列化摘要。任一异常直接抛错，**不把损坏文件当成成功进度**，也不会悄悄重跑并覆盖可疑簇。SHA-256用于发现意外文件损坏，不是对有权重写文件的恶意操作者的数字签名。

原子临时文件可能在进程异常退出时保留 .tmp-... 后缀：恢复时不加载、不计入任何成功簇；确认不再运行其他进程后可自行清理这些孤立临时文件。**不可同时对同一个输出目录运行两个实验进程**，因为不是多进程共享写入锁。

本轮的模型还仅是两个条件未来墙的有限特征离线研究候选；即使少数种子结果为正，也不能证明正式策略提升，仍应增加全新独立种子和跨批次验证。

## 验收与回归

~~~powershell
.\.venv\Scripts\python.exe -W error::SyntaxWarning -m unittest discover -s tests -p "test_m437_resumable_shadow_benchmark.py" -v
.\.venv\Scripts\python.exe -W error::SyntaxWarning -m unittest discover -s tests -p "test_m436_frozen_shadow_four_seat.py" -v
~~~

M4.37测试用受控五局结果替身验证崩溃、恢复、不重跑、文件篡改/截断与防种子/模型混用；M4.36测试继续负责真实引擎全局账本五局的集成检查。必须运行后才能称为已通过，不以创建测试文件代替运行结果。

## 本轮不做

不修改线上 MahjongAgent("challenge")、不读取或提交私有暗手、不改变官方赢/杠/流局规则，不把四座位五局当作独立样本，不把小样本平均积分差当作统计显著的胜率提升。
