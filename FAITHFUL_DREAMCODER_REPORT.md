# DreamCoder core fidelity acceptance

本阶段以 **实际运行的官方 oracle** 为标准。新增实现位于 `faithful/`；旧
`dreamcoder/` 保留为 DreamCoder-lite。所有 PASS 都指下述有限、可复跑的测试配置，
不是对无限程序空间的形式化等价证明，也不是原论文实验结果的复现声明。

初始全套验收为 87 项；2026-09-18 已补齐 24-operation Grid toy 支持及受预算控制的 agenda。
最新测试数量与状态见 `faithful/results/junit.xml`；实验结果见 `FAITHFUL_TOY_REPORT.md`。

## Reference 与配置

论文：[Ellis et al., PLDI 2021](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf)，
尤其 §2 的 typed generative model、§2.4 Eq.1–4 的 library objective 与 wake/sleep。
官方固定提交：[cb0e63f5c33cd2de360b791038b0f5272750270e](https://github.com/ellisk42/ec/tree/cb0e63f5c33cd2de360b791038b0f5272750270e)。
实际运行该提交的 Python type/program/grammar/frontier/recognition 模块，以及仓库随附的
Linux OCaml `compression` 二进制。源码与二进制 SHA-256 见
`faithful/results/provenance.json`，输入/输出见 `golden_trace.jsonl` 和 compression JSON。
没有通过复制期望常数来代替官方执行。

Haskell 使用 de Bruijn AST、独立类型推导与 grammar 实现；Python reference 仅在测试进程中导入。
测试绕过官方包 `__init__.py` 的所有旧 domain eager imports，**不修改核心模块**。
每次 Python oracle 调用均启动新进程，避免官方可变默认字典的跨调用污染。

配置：generative unigram；recognition AST bigram（root / variable parent / production × argument）；
frontier K=5；positive pseudo-count=1；recognition `frontierBiasOptimal`，另实现
posterior-sampled `frontierKL`。压缩选择原 OCaml version-space/inverse-β 路线，
不使用 Stitch 或旧 exact-subtree compressor。tiny compression arity=1，inline=true，
AIC=1，structure penalty=.001，官方 topK=5、topI=300、beam=1,000,000。
这些 fixture 的候选数低于 topI；Haskell 显式搜索全部有限候选，不做候选 beam 截断。
arity 是每个子项允许的逆 β 步数，**不是 invention 的参数数上限**。

## 验收矩阵

| Component | Paper definition / official behavior | Our implementation | Fidelity test | Status / known deviation |
|---|---|---|---|---|
| A Program / types | Typed λ calculus, polymorphic library；`type.py`, `program.py` | `Syntax.hs`：Primitive/Index/App/Lam/Inv，替换、occurs check、principal type、capture-free β reduction | unification 成功/失败、共享 type variables、主类型、AST round-trip、capture test | PASS；不实现非核心 Hole/Sketch AST |
| B Program probability | `grammar.py:buildCandidates,likelihoodSummary` 的 request/environment conditional normalization | `Grammar.hs:candidates,summary,score` | 常量、应用、多态、多个变量、函数变量、invention、不同 request 的数值对照 | PASS；绝对容差 1e-12，非全局 softmax |
| C Wake enumeration | Typed cost-bounded enumeration；`grammar.py:enumeration` | `Grammar.hs:enumerate` 与 `Agenda.hs:budgetEnumeration` | 原有四类 request 对照；新增 agenda 的完整有界集合、logP 与官方对照 | PASS；toy 使用真实 candidate/state caps；尚无内核 wall-clock 取消；不移植其他 domain 的硬编码 symmetry pruning |
| D Guidance separation | `dreamcoder.py` 用 generative grammar 重新评分 recognition 搜得的 frontier | Haskell 双 grammar 输入；`ec.py:wake` | contextual search 下同程序 search score 与 generative prior 分别对照 | PASS；未混用 proposal score |
| E Frontier objective | Eq.3 有限 frontier 的 log-sum-exp；`frontier.py` | `Grammar.hs:frontier` | 固定 Grid I/O 的合法解集合、prior、likelihood、normalized posterior、marginal likelihood | PASS；保留多程序；不把容器称作完整无限 posterior |
| F Grammar learning | Expected actual/possible usage；`Grammar.insideOutside`、OCaml `inside_outside` | `Grammar.hs:insideOutside` | pseudo-count 1/.25 的一次更新、三次独立官方更新的组合 | PASS；多次统计量每轮清零，见下方官方 Python bug |
| G Library learning | Eq.4/AIC approximation；`solvers/compression.ml`, `versions.ml` | `Compression.hs`：有限 inverse β、free-variable closure、refactoring、library cost、联合权重估计、多次加入 invention | 两个实际 OCaml golden corpus：候选 β 等价类、选中 invention、frontier rewrite、权重、目标改善 | PASS（这些 fixture）；显式集合较慢，候选代表的去重方式不同，见下方 |
| H Dream | 由 generative grammar 的合法 conditional probabilities 生成程序 | `Grammar.hs:sampleProgram`；`ec.py:dream` | 12 组相同随机数流与官方 `_sample` 的 AST / logP 一致 | PASS（未触及官方 depth-forced-leaf）；使用无强制叶子的 ancestral draws，资源失败计数，不隐瞒拒绝的 conditioning |
| I Replay | 真实 frontier posterior sampling；`Frontier.sample`、recognition training | `recognition.py:replay_sample,fit_frontiers` | 非均匀 posterior 的采样频率；完整 frontier 用于 BO | PASS；BO 使用所有 entries，KL 才按 posterior 抽 entry；不等权重复固定次数 |
| J Recognition objective | Search grammar 的 typed program likelihood；`RecognitionModel.frontierBiasOptimal/frontierKL` | PyTorch MLP + Haskell likelihood events | 直接运行官方 BO 方法比较 loss；KL gradient 与 replay 检查 | PASS；BO 为主验收路径，KL exact expectation 是 sampled NLL 的期望，未添加 posterior entropy |
| K Contextual grammar | 官方 `ContextualGrammar` 的 AST bigram family | parent / argument rows；type/environment legality 留在 Haskell | root、primitive child、variable parent likelihood；guided enumeration | PASS；encoder architecture 不要求逐层一致 |
| L Multi-round EC | Wake → Compress → Dream/Replay → recognition → next Wake | `ec.py:explore_compress`，持久 grammar/frontiers，每轮 checkpoint | 三轮真实 Grid I/O smoke；第二个 compression fixture 学到引用旧 invention 的双显式参数新函数 | PASS（流程与层级能力分别验证）；Grid smoke 本身未声称发现层级库 |

## 最重要的五项 golden tests

1. **Type judgement**：成功与失败均对照；包括 `t0 ~ t0`、共享变量、occurs failure。
2. **Program probability**：每个合法 expansion 的候选集合和归一化，变量共享质量；包括开放环境与函数变量。
3. **Enumeration ordering**：比較整个 cost/depth 有界集合及每项 score，检查全局非增序，因此覆盖该集合内任意不截断 tie 的 Top-N。官方 DFS 原始生成顺序本身并非全局概率顺序，先按 cost 排序后比较。
4. **Frontier statistics**：generative rescoring、log marginal 和归一化 posterior；有不同非零 likelihood 的额外用例，避免只有等权 deterministic frontier 的弱测试。
5. **Grammar update**：同一 synthetic 多程序 frontier，一次 expected actual/possible update；变量、不可用类型和 invention 均参与。

核心概率为

`log P(p) = Σ_events [w(actual) − logsumexp(w(possible)) + variable_constant]`。

其中变量类别在 possible 中只出现一次；选择具体变量时再加 `−log(number_of_legal_variables)`。
更新为 `w_i' = log(E actual_i + α) − log(E possible_i + α)`；期望依据 **generative** posterior。
候选的类型约束随各参数从左到右传播，不能每个参数独立重新推导。

## Compression evidence

| Fixture | Before | After | Result |
|---|---:|---:|---|
| parameterized fragment | −67.22470932606645 | −45.49052323562313 | 官方与 Haskell 都学到 `#(lambda (+ (+ $0 1)))`；完整 rewrite 和更新权重相同 |
| hierarchical / multiple parameters | −75.94035022260282 | −67.6920367030259 | 新 invention 有两个显式 λ 参数，并两次引用上一轮 invention；两端 rewrite、权重、目标相同 |

这里的 `+ / 1 / 2 / 3` **仅用于 compression fidelity fixtures**，方便运行官方已注册 primitives；
没有移植其 arithmetic benchmark。真实 demo 仍为自己的 Grid domain。

候选集合比较在去掉已有 library 项、展开 invention 后按 β-normal form 比较。
第一个 fixture 归一化候选完全同集；第二个 fixture Haskell 保留四个额外的 inlining
代表，它们都属于已有候选的同一 β 等价类，官方还会尝试一个已在库中的重复项。
**不能声称原始候选列表逐项相同。** 两个 fixture 的可表示 β 等价类相同，最优选择和
目标值相同。原版使用共享 version-space 节点和 minimum-cost representatives，
本实现使用显式 finite sets；复杂 corpus 上的性能与代表筛选行为仍需单独评测。

结构代价采用 OCaml `program_size`：primitive / index / invented leaf 各计 1，
application/lambda 不额外计结构 token。每个 invention 的 definition 单独计入 library prior。
目标是 fitted finite-frontier log evidence − AIC × library size − λ × definition size。
不把这个 AIC 近似描述成精确积分的 Bayesian evidence。

## 明确处理的歧义与限制

* 官方 Python `Uses.__init__(possibleUses={}, actualUses={})` 与原地 `+=` 导致字典跨实例残留。
  同一进程重复调用，甚至 `iterations>1`，可能累积旧 production counts。单次更新在干净进程
  完全一致；本实现按数学语义和 OCaml 路径清零。三轮比较使用三个干净官方进程，未修改 oracle。
* 官方 `sample(maximumDepth)` 在最后层只允许叶子，其截断分布不同于完整 grammar 的 P(p)。
  本实现不使用该 heuristic；通过供给相同 uniform stream、官方足够深度验证真实 ancestral choices。
  资源耗尽是拒绝事件，不重分配概率，不把有限资源下接受的样本谎称无条件精确分布。
* 原 `enumerate` 的 `limit` 仅为输出上限；新 `enumerate_budget/search_tasks` 会真正按
  candidate/state caps 终止。显式 compression version sets 仍可指数增长，尚不应把原始 toy
  跑通视作具备 ARC 或原论文大规模实验的计算性能。
* Grid DSL 现已补齐旧 V1 的全部 24 productions，类型签名及 Haskell 执行语义有对照测试。
  五操作版本仅保留为原始 smoke fixture。搜索预算/停止规则与 recognition 训练步数仍须显式列出，
  不能将不同停止规则下的墙钟时间直接当作同配置性能比较。
* arithmetic oracle 使用仓库内官方二进制，并记录其哈希；没有声称在本机从 OCaml 源码重新构建该二进制。

## 复跑和证据

```powershell
E:\anaconda3\python.exe -m faithful.run_acceptance
```

需要已有 GHC、Python torch/pytest/frozendict、WSL Ubuntu-24.04，以及固定提交的 reference checkout。
该命令重建 Haskell、实际重跑两个官方 OCaml fixture、运行全部 faithful 与旧 V1 tests，生成：

* `faithful/results/junit.xml`：实际测试状态；
* `faithful/results/provenance.json`：提交、官方源码/二进制、实现、输入输出哈希；
* `faithful/results/golden_trace.jsonl`：Haskell 与官方请求/响应；
* `faithful/results/candidate_comparison.json`：候选语义空间差异；
* `faithful/results/*_official.json`, `*_official.log`, `*_ours.json`；
* `faithful/results/ec/history.json`, `recognition_*.pt`：三轮 Grid 运行。

这些证据支持把新实现作为**已通过 tiny-grammar 语义验收的 DreamCoder core 基线**。
在报告实验时仍应列出上述配置和偏差，不能仅凭目录名或 smoke success 宣称完整原论文复现。
