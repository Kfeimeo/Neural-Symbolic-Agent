# Minimal DreamCoder V1

当前 Faithful DreamCoder 的 controlled benchmark 入口是
[`CONTROLLED_BENCHMARK_REPORT.md`](CONTROLLED_BENCHMARK_REPORT.md) 与
[`CONTROLLED_EXPERIMENT_REPORT.md`](CONTROLLED_EXPERIMENT_REPORT.md)，数据位于
`faithful/results/controlled/`。本页保留的旧 36/24 toy 分数仅作 regression/smoke
记录，不作为 abstraction recovery 或 compositional generalization 的性能证据。

从零实现的纯 Python Explore–Compress / Wake–Sleep 项目。不依赖旧 DreamCoder 仓库。识别模型使用 PyTorch，仅预测 primitive 的搜索 prior，程序始终由类型化枚举器生成。

## 快速运行

Python 3.11+，CPU 即可：

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python run_experiment.py
```

如需专用 conda 环境，在项目根目录执行：

```powershell
conda env create -f environment.yml
conda run -n minimal-dreamcoder python -m pytest -q
conda run -n minimal-dreamcoder python run_experiment.py
```

本机验收直接使用已安装的 Anaconda Python 3.13.9、PyTorch 2.12.1+cpu 和 pytest 8.4.2；无需修改已有环境，因此未额外创建 conda 环境。

默认命令固定 seed=7，生成 36 个训练任务、24 个 held-out 任务，每个任务有 4 对 I/O。运行顺序为：

1. 基础均匀 grammar 执行 Wake，保留每个任务的 top-3 frontier。
2. 使用每个已解任务的 MAP 程序构建压缩语料，发现重复子程序并注册复合 primitive。
3. 从新 grammar 采样 600 个 fantasy task/program pairs；Replay 收集真实 Wake frontiers 中的所有解。
4. 使用 fantasies 与五倍重采样的 replay 训练识别模型；训练 100 epochs。
5. 在 held-out 任务上运行 A/B/C/D 四组搜索，输出 JSON 指标与完整 frontiers。

```powershell
python run_experiment.py --seed 7 --train-tasks 36 --heldout-tasks 24 --dreams 600 --epochs 100 --top-k 3 --max-nodes 1500 --max-size 7 --output results/experiment.json
```

参数较小时可能没有足够重复程序支持压缩，或不足以训练识别模型。脚本会在识别模型未减少 C 相对 A 的平均枚举节点时以非零状态退出，同时保存实际结果，不会隐藏失败或自动挑选 seed。

## 模块结构

| 模块 | 职责 |
|---|---|
| `dreamcoder/language.py` | 不可变 AST、基础类型、函数签名、类型检查、求值、库定义展开 |
| `dreamcoder/tasks.py` | 任意 domain 的 I/O 任务及确定性 likelihood |
| `dreamcoder/grammar.py` | primitive log probability、计数学习、有限深度类型化采样 |
| `dreamcoder/search.py` | 带可采纳完成代价下界的 uniform-cost 枚举、top-K frontier、预算及统计 |
| `dreamcoder/abstraction.py` | 通用 Compressor 接口、基于重复子树的参数化压缩 |
| `dreamcoder/dreaming.py` | grammar 采样、fantasy I/O 生成、frontier replay |
| `dreamcoder/recognition.py` | 对多样本任务做池化的 MLP、primitive logits、contextual grammar |
| `dreamcoder/ec.py` | 完整迭代及四组对照的 domain-neutral 编排 |
| `dreamcoder/domains/grid/` | Grid 数据、primitives、合成任务、领域特征 |

核心模块不导入 Grid 插件。替换领域只需提供 Language、输入采样函数、任务集及特征编码函数。测试包含一个整数领域，验证这一边界。

## DSL 与概率搜索

类型包括 `Grid, Color, Int, Bool, Object, Objects` 和 `FunctionType(arguments, result)`。V1 是一阶 DSL，不实现 lambda calculus、高阶函数或多态类型推断。`$input` 是自由输入变量，函数应用以 `Program(name, arguments)` 表示。

18 个操作为 identity、rotate90、rotate180、flipH、flipV、transpose、trim、invert、recolor、objects、largest、crop、translate、count、is_empty、if_grid、border、solid；另有三个颜色常量及三个整数常量。Grid 是不可变矩形整数元组，颜色范围 0–3，0 表示背景。

`objects` 使用忽略颜色差异的非零四邻域连通分量；largest 面积相同时按扫描顺序选择。空对象 crop 为 `((0,),)`。translate 越界丢弃并补零。invert 保持背景，将非零颜色 v 映射为 4-v。

```python
from dreamcoder.language import INPUT, Program
from dreamcoder.domains.grid import make_language

language = make_language()
program = Program("rotate90", (Program("trim", (INPUT,)),))
result = language.evaluate(program, ((0, 0, 0), (0, 1, 2)))
```

primitive logits 经全词表 log-softmax 归一化。程序的 log prior 是所有 primitive 出现次数对应 log probability 的和；`$input` 没有额外代价。确定性任务中，满足全部训练 I/O 的程序 log likelihood=0，其余为负无穷。

搜索按负 log prior 排序，使用类型孔及该类型最小完成成本作为下界。`max_size` 限制 AST 节点数，包括变量和常量；`max_nodes` 限制完整候选程序数；`max_states` 限制从堆中取出的部分或完整状态数。重复的语法程序不会产生，但语义等价程序有意保留，使 frontier 能包含多个解。达到 K 个解即可终止，因为完整程序按 prior 顺序产出；同分边界可保留任意等价评分的候选。预算耗尽时可能只有不足 K 个解。

程序 prior 是用于有界搜索和 posterior 排序的乘积分数，不声称在所有有限 AST 上构成一个归一化分布。Dream 使用依类型、深度约束局部归一化的生成过程，并赋予输入变量终止权重；它不是对无限程序空间乘积 prior 的精确无条件采样。

## 库学习与识别模型

压缩器统计训练 MAP 程序中的重复、含输入的 Grid 子树。将选中的子树抽象为一个接收 Grid 参数的新 primitive。候选收益为：

```text
出现次数 × (原子树 AST 大小 − 宏调用 AST 大小) − (定义 AST 大小 + 1)
```

仅接受严格正收益候选，一轮最多引入一个宏。MDL 使用语料 AST token 总数加新库定义开销，和概率 prior 的目标明确区分。宏注册于新 Language 中，不修改基础 Language。注册后使用重写程序的 primitive 计数加平滑更新 grammar。

识别模型对每个 I/O 样本提取特征，经共享 MLP 输出 logits，再对样本平均池化。特征包括网格尺寸以及原图/去背景边界图在六个固定方向下的颜色对应矩阵。这是有领域知识的轻量 MLP baseline，不是从原始像素学习所有几何关系的 CNN。特征不读取 ground truth、已求解程序或测试标签，也不调用枚举器。

训练目标是 primitive 出现频次分布的交叉熵。推理时将模型分布与原 grammar 按 90% / 10% 混合，保证所有 primitive 可达。C 与 D 使用相同训练 pairs；C 的标签将宏展开成基础 primitive，D 保留新词表。R0 在第一次 Wake 中等价于未提供识别模型。

## 实测结果

完整原始结果见 `results/experiment.json`，包括每个测试任务的 top-3 程序及 prior。下表来自默认 seed=7 的本机运行；时间会随机器负载变化。

| 配置 | Library | Recognition | Solve rate | 平均枚举节点 | 平均搜索时间 | 宏展开 AST 恢复率 |
|---|---|---|---:|---:|---:|---:|
| A | Base | No | 100% | 131.33 | 188.42 ms | 100% |
| B | Learned | No | 100% | 19.67 | 3.89 ms | 100% |
| C | Base | Yes | 100% | 12.04 | 2.28 ms | 100% |
| D | Learned | Yes | 100% | 10.96 | 2.17 ms | 100% |

节点数为收集 top-3 的完整候选程序数，不是到首个解的节点数；JSON 另外报告首解节点和展开状态数。搜索时间包括枚举与候选求值，不含 recognition 前向推理、特征计算或离线训练；主要验收结论使用节点数。C 相比 A 的平均节点数减少约 90.8%。

库学习的语料与定义总 MDL 从 108 降为 100。行为恢复率也为 100%：frontier 中至少一个程序在额外 20 个随机 probe 输入上与 ground truth 相同；有限 probe 测试不是等价性证明。旧报告把宏展开 AST 恢复率命名为 exact；审计已修正为独立的 `expanded_ast_recovery_rate`。`exact_program_recovery_rate` 现在比较原始 AST，原任务 B/D 组为 66.7%，不能将宏语法差异视作求解失败。

这些 held-out 任务有独立随机输入，覆盖 `rotate90(trim(input))`、`flipH(trim(input))`、`invert(trim(input))` 三个程序族，训练集与测试集共享这些程序族。因此结果验证的是同分布新 I/O 任务上的搜索加速，不是未见组合或真实 ARC 的泛化。没有依据测试结果选择 epoch、seed 或模型。B 与 D 的 Learned grammar 同时包含新宏和计数学习 prior，所以 B/A 的差异不能全部归因于宏。

## 验证

`python -m pytest -q`：22 项测试全部通过，覆盖：

- 类型错误与具体 Grid 操作的语义。
- 非 Grid 领域、prior 改变枚举顺序及代价单调性。
- 对照穷举结果检查真实 top-K、确定性全部样本匹配。
- 合成已知程序恢复。
- 宏展开与执行等价、MDL 严格下降、基础词表不被修改。
- Dream 有效性与随机种子复现、Replay 数据来源。
- 搜索状态预算。
- PyTorch 训练 loss 下降、例子顺序不变性、contextual grammar 归一化。

四组完整实验是额外的端到端验收，不放入快速单元测试。固定 seed 后任务、训练与搜索节点可复现；耗时不可逐位复现。

## 严格审计与压力测试

```powershell
python run_audit.py
```

审计不改变 DSL、recognition 架构或 V1 训练超参数。它先完成原始训练并冻结模型，再建立与 Wake 和 Dream/Replay 中所有训练程序隔离的新组合测试集。完整结果见 `AUDIT_REPORT.md` 和 `results/audit/`。

- `original.json`：原 24 个任务、A/B/C/D、3 次独立 derangement shuffle、base_fitted 和 library_uniform 控制。
- `transfer.json`：12 个新的 `g(f(x))` / `f(h(x))` 组合，同样的全套对照。
- `stress.json`：48 个测试任务，按化简后的应用深度 1–2、3–4、5–6、7–8 分桶。
- `manifest.json`：训练 provenance、MDL 明细、prior、数据隔离检查、超参数和 benchmark 哈希。
- `benchmark.json` / `training_data.json`：完整测试集、训练集及 Dream/Replay 标签，便于复核。
- `model_C.pt` / `model_D.pt`：模型参数与词表，可由当前 RecognitionModel 加载。

新组合测试统一限制 600 个完整候选、6000 个展开状态、AST size≤33、top-K=3。所有配置使用同一组任务与预算。复杂度是去除已知等价冗余后的 AST 应用深度，不声称是可证明的最短程序复杂度。每个任务用 64 个独立 probe 评估行为；另有 32 个只用于数据隔离的 probe，两组用途分离。

新指标区分 raw exact、expanded AST、canonical 和有限 probe behavioral recovery；首解均值只统计已解任务，并额外报告样本数与截尾均值。预算耗尽可能发生在已经找到一两个解但尚未填满 top-K 的任务上，所以同时报告“未解且耗尽”比例。JSON 分开记录搜索时间、特征/recognition 时间与二者之和。

`results/audit_initial/` 保留改进复杂度化简前的诊断结果，不作为正式压力测试结论。独立测试验证化简的语义、含分支枚举的穷举一致性、metadata/ground-truth 隔离、shuffle、MDL、Dream 边界及恢复指标。审计脚本会如实保留失败结果，不要求 D 必须获胜才写报告。

## Haskell core 与官方 golden tests

`faithful/` 是独立的 Haskell + PyTorch 实现；本页原有 Python 实现继续作为 DreamCoder-lite。
新增内核包括 typed λ calculus、conditional grammar probability、contextual search、Bayesian frontier、
inside–outside update、inverse-β compression 和多轮 EC。

执行 `python -m faithful.run_acceptance` 可重建并实际运行固定官方版本的 golden 对照及旧 V1 回归。
该完整命令使用现有 WSL Ubuntu-24.04 运行官方 OCaml 压缩器。
范围、证据、已知差异见 `FAITHFUL_DREAMCODER_REPORT.md`，算法对比见 `FAITHFUL_VS_LITE.md`。

## Phase 1: abstraction learning study (latent-abstraction benchmark)

`benchmarks/latent_abstraction/` generates frozen benchmark instances from a hidden
library of latent abstractions (reuse regimes zero/low/medium/high, depth 2–8,
compositional held-out split). `experiments/abstraction_learning/` compares
abstraction-discovery methods (A no compression, B DreamCoder, C Stitch, D hybrid,
E DreamCoder proposals + Stitch objective, oracle and perfect-Wake controls) on the
unchanged core. Results are in `results/abstraction_recovery.json`,
`results/solve_curves.json`, `results/compression_results.json` and the report
`PHASE1_REPORT.md`.

```bash
python -m experiments.abstraction_learning.run benchmark
python -m experiments.abstraction_learning.run train --workers 4
python -m experiments.abstraction_learning.run perfect-wake --workers 4
python -m experiments.abstraction_learning.run evaluate --workers 4
python -m experiments.abstraction_learning.run analyze
python -m pytest tests/test_abstraction_learning.py -q
```

## Phase 2: full faithful DreamCoder (recognition ON)

`experiments/full_dreamcoder/` re-runs the Phase 1 B arm with the recognition
pathway enabled (Dream + Replay + task-conditioned AST-bigram recognition, guided
Wake) on the same frozen benchmark, compressor, objective, budgets and evaluation
protocol; nothing else changes. It measures whether recognition relieves the Wake
exposure bottleneck found in Phase 1 (training solve rate, latent frontier support,
ER@1/ER@2, behavioural recovery, held-out solve curves, first-solution ranks, gap
closure against B / perfect-Wake / oracle). Results are in `results/full_dreamcoder/`
and the report `PHASE2_REPORT.md`.

```bash
python -m experiments.full_dreamcoder.run train --workers 4
python -m experiments.full_dreamcoder.run evaluate --workers 4
python -m experiments.full_dreamcoder.run parity
python -m experiments.full_dreamcoder.run analyze
python -m experiments.full_dreamcoder.run figures
python -m pytest tests/test_full_dreamcoder.py -q
```
