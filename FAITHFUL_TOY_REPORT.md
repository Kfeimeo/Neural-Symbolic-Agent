# Faithful full-DSL toy run — 2026-09-18

本报告仅保留为 regression / smoke test。新的 abstraction、recognition 与
compositional-generalization 实验见 `CONTROLLED_BENCHMARK_REPORT.md` 和
`CONTROLLED_EXPERIMENT_REPORT.md`；本报告的 100% solved 不作为主要算法性能证据。

已补齐并实际运行**原始 toy**：seed=7，36 个训练任务、24 个测试任务，全部 24 个 Grid
productions。数据由原 `synthetic_tasks` 生成，种子与原实验一致；Haskell 承担执行、搜索、
概率、frontier、grammar update 和压缩，Python/PyTorch 负责 recognition。没有调用旧 learner。

最终重跑官方 golden 与全部回归：**94 passed in 19.32s**，无失败、无跳过。
当前源码哈希和官方版本证据见 `faithful/results/provenance.json`；toy 的运行版本记录另存于
`faithful/results/toy_original/implementation.json`。

## 本次补齐

* 同名同类型的 24 productions：新增 trim/recolor/objects/largest/crop/translate/count/
  is_empty/if_grid/border/solid/rotate180，以及颜色和整数常量。
* Objects 使用跨颜色的四邻域非零连通分量；largest 等大时选扫描顺序最早者；空 crop 为 `[[0]]`。
  操作语义在空图、边界、混色相连、等大对象与随机 grids 上和原 domain 对照。
* 新增 uniform-cost typed agenda，以完整程序数和 popped states 真正限制工作量；
  类型替换在兄弟参数间共享，probability model 不变。三个 tiny request 的完整有界集合
  和 logP 与实际运行的官方 enumerator 相同。
* 新增批量 Haskell I/O filtering、original/calibration dataset adapters、八组实验入口、
  checkpoints、manifest、程序恢复及独立 probe 指标。

## 固定配置

每任务最多 1500 个完整候选、60000 个 agenda states，DSL size≤7、maximum_depth=10、
topK=3。DSL size 计 primitive/invention/variable leaves，不计 λ/application scaffolding。
所有预算内候选均检查，最后按 generative prior 保留 top-K；与旧搜索提前填满 K 就停止的
口径有区别。本实验不是同墙钟预算的性能对比。

Compression：arity=1，最多连续学习 3 个 inventions，保留多解 frontier；没有改成 MAP-only。
Dream：600 次 ancestral draws，fuel=128；本次 accepted=600、rejected=0。
Recognition C/D 看到相同任务与程序语义，C 使用展开的 labels；各训练 1000 optimizer steps，
使用 faithful frontierBiasOptimal。1000 steps 不等同于旧 histogram model 的100 epochs。

训练 Wake 36/36。Library 从24扩展到27 productions。未读取测试 ground-truth 来训练或搜索；
ground-truth 在独立 evaluation 对象中，搜索 Task 只有名字、request、I/O examples。

## 实测结果

| 配置 | 解出任务 | 平均首解候选数 | Probe behavioral recovery |
|---|---:|---:|---:|
| A：base grammar | 24/24 | 60.33 | 100% |
| B：learned library/prior | 24/24 | 3.00 | 100% |
| C：base + recognition | 24/24 | 3.71 | 100% |
| D：library + recognition | 24/24 | 2.21 | 100% |
| base_fitted | 24/24 | 9.67 | 100% |
| library_uniform | 24/24 | 12.00 | 100% |
| C_shuffle | 24/24 | 3.67 | 100% |
| D_shuffle | 24/24 | 2.21 | 100% |

Probe 使用原实验同种子的20个独立 grids。B/D 的 expanded AST exact recovery 为1/3，
但全部 probe behavior 正确；代数等价的操作顺序不一定与原标签 AST 完全相同。

**原始 toy 很容易，不能据此证明新组合泛化。** 训练与测试使用相同的三个程序模板，
shuffle 几乎不影响首解排名，也不足以证明模型依赖任务特征获得了优势。没有因 shuffle
结果不理想而修改任务分布或重新选 seed。

静态配置共用候选流，guided 配置逐任务搜索，因此 JSON 中记录的 batch seconds 不应直接
作为 A/B 对 C/D 的同工程优化程度速度比较；首解候选数是这里更清晰的描述性指标。

## 复跑与输出

```powershell
E:\anaconda3\python.exe -m faithful.python.toy
```

结果位于 `faithful/results/toy_original/`：`summary.json`、八组 frontiers、`training_wake.json`、
`compression.json`、`dreams.json`、C/D checkpoints、loss histories、shuffle、I/O manifest 和
独立 evaluation labels。旧实验结果没有覆盖。

另已提供冻结的96-train/60-test calibration adapter：

```powershell
E:\anaconda3\python.exe -m faithful.python.toy --benchmark calibration --max-size 33 --output faithful/results/toy_calibration
```

此 adapter 检验原 benchmark 哈希和 label 隔离。本次**未运行60-task calibration完整预算曲线**，
上表全部是原始36/24 toy的实际结果，不与先前 DreamCoder-lite calibration 结果混用。
