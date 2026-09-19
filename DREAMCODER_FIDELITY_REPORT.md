# DreamCoder Fidelity Audit

**结论：当前 V1 可以称为 DreamCoder-inspired 最小 Explore–Compress 系统，不能称为原始 DreamCoder 核心算法的 faithful reproduction。** 执行流程相似、机制可运行，不等于概率模型、学习目标与抽象搜索一致。

审计日期：2026-09-17。规范参考为 Ellis 等人的 [PLDI 2021 论文](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf)（§2–4、Fig.3、Eq.1–4）及作者 [ellisk42/ec 官方仓库](https://github.com/ellisk42/ec)。官方代码引用的是本次读取的 `master`，不是声称固定于 2021 的某个 commit；不同后端和开关也不应混为唯一实现。未复制或依赖官方代码。

分类中：E=纯工程简化；S=在声明的受限子问题内保持语义；A=可能实质改变学习或搜索行为；B=实现 bug。`SIMPLIFIED` 不自动意味着属于 E/S。

## 逐项对照

| 项目 | 标记 | 类别 | 当前 V1 与参考实现的差异 |
|---|---|---|---|
| Grid domain / 可执行 DSL | FAITHFUL | S | 以领域 primitives 和 I/O 定义合成问题符合通用框架；换成 Grid 本身不是 fidelity 缺陷。 |
| Typed DSL / 类型系统 | MATERIALLY DIFFERENT | A | 只有单态一阶函数签名及唯一自由输入。没有类型变量、统一、lambda、绑定环境、高阶参数和通用 β-reduction。官方具有这些表示能力，直接影响可发现抽象的空间。[type.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/type.py)、[program.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/program.py) |
| Probabilistic grammar | MATERIALLY DIFFERENT | A | V1 对所有 primitive 一次性 softmax；官方 `buildCandidates` 根据当前请求类型和变量环境筛选并局部归一化，且显式建模变量选择。[grammar.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/grammar.py) |
| Program prior | MATERIALLY DIFFERENT | A | V1 是全局 primitive log probability 求和，输入变量代价为零；不是官方类型/作用域条件生成过程的程序概率。公式差异见下文。 |
| Wake enumerative search | SIMPLIFIED | E/S | V1 的类型孔优先队列确实按自己的代价枚举；Python、固定候选预算、K=3 相对官方的后端、时间预算等是工程/实验选择。但枚举器正确不证明其 prior 与官方相同。[enumeration.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/enumeration.py) |
| 确定性 I/O likelihood | FAITHFUL | S | 在确定性领域，满足全部 I/O 时 likelihood=1，否则为0，是合理的限定；无需为 fidelity 强行加入噪声任务。 |
| Bayesian library objective | MISSING | A | 没有实现论文对任务程序求和、联合库/权重 prior 和参数积分/近似的目标；V1 用独立的 AST token 节省启发式选择宏。[论文 Eq.1–4](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf) |
| Frontier / top-K | SIMPLIFIED | S/A | 保存 K 个合法且按当前分数排序的程序真实有效；没有归一化 posterior、marginal likelihood 或以 posterior 权重进入后续更新。官方 Frontier 支持这些操作。[frontier.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/frontier.py) |
| Search guidance 与 posterior 分离 | MATERIALLY DIFFERENT | A | V1 将 task-specific grammar 同时当作枚举分数和解的 `log_prior`。官方在 recognition 搜索之后用 generative grammar 重新打分，再合并 frontiers。V1 的 guided top-K 不能直接称为 generative-posterior top-K。[dreamcoder.py: sleep_recognition](https://github.com/ellisk42/ec/blob/master/dreamcoder/dreamcoder.py#L606) |
| Grammar 参数更新 | MATERIALLY DIFFERENT | A | V1 是重写后 MAP 程序的计数加1平滑；不含类型可用性分母、变量计数和 frontier posterior weighting，而且没有新宏时 compressor 直接返回旧 grammar。官方提供 inside–outside 及不同 restricted-frontier 更新配置，不能简单等同于全局频次统计。[grammar.py: insideOutside](https://github.com/ellisk42/ec/blob/master/dreamcoder/grammar.py#L391)、[fragmentGrammar.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/fragmentGrammar.py) |
| Library learning / compression | MATERIALLY DIFFERENT | A | 一次只选一个重复的原样子树，以整个 `$input` 为唯一参数。不会在其他参数位置引入变量，也不搜索 β-equivalent refactorings；`F(h(x))` 的结构不会自动归并成 `F(x)` 模式。官方压缩接口与版本空间/refactoring 目标更广。[compression.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/compression.py)、[论文 §3](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf) |
| MDL | MATERIALLY DIFFERENT | A | V1 最小化“语料 AST token + 定义 AST token + 每宏1”，并非论文的 library prior、program likelihood、权重 prior 与 AIC 项的联合优化。108→100 的算术正确，不能因此认为目标一致。 |
| Dream / Helmholtz | SIMPLIFIED | S/A | 先采样程序再执行生成任务的来源机制成立；官方也允许 sampling，**缺少 Helmholtz enumeration 本身不是必然缺陷**。但 V1 深度截断及输入终止权重0.35的 sampler 与其零变量代价 search score 不匹配。[dreaming.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/dreaming.py)、[recognition.py: train](https://github.com/ellisk42/ec/blob/master/dreamcoder/recognition.py#L760) |
| Replay | SIMPLIFIED | S/A | 来源确为 Wake 解；V1 等权加入所有 frontier 程序再重复5次，不保留 posterior 权重。来源忠实，训练分布处理不同。 |
| Recognition encoder | SIMPLIFIED | E/A | MLP 本身不是违规；但 Grid 的方向/颜色对应矩阵是很强的手工特征，实验不能外推成从像素学到一般程序结构。 |
| Recognition 训练目标 | MATERIALLY DIFFERENT | A | V1 学习长度归一化且平滑的 primitive 频次交叉熵，不是 typed program likelihood、frontier KL 或 bias-optimal/MAP 目标。官方代码分别有 `frontierKL` 和 `frontierBiasOptimal`。[recognition.py](https://github.com/ellisk42/ec/blob/master/dreamcoder/recognition.py#L714) |
| Recognition-conditioned grammar | MATERIALLY DIFFERENT | A | V1 的 task conditioning 真实存在；但其“contextual”仅指条件于任务，没有 parent primitive / argument-position context，是 unigram guidance。论文重点模型包含这种 AST bigram context。另有 V1 固定90/10 prior mixture。[官方 contextual 实现](https://github.com/ellisk42/ec/blob/master/dreamcoder/recognition.py)、[论文 §4](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf) |
| 完整一次 EC / Wake–Sleep | SIMPLIFIED | S | Wake→压缩→Dream/Replay→训练→guided Wake 实际完整运行；这是一次循环的机制实现。阶段调度不完全等同于官方 driver，但单次调度差异不是首要问题。 |
| 多轮 bootstrap / 深层库 | MISSING | A | 当前入口不提供跨多轮的库累积、frontier 重评分/重写、持续再训练闭环。可以调用多个基础组件不等于已经实现并验证多轮 driver。[官方 ecIterator / consolidate](https://github.com/ellisk42/ec/blob/master/dreamcoder/dreamcoder.py) |

## 关键公式与具体影响

V1 的分数为：

\[
\log\widetilde P(p)=\sum_f c_f(p)\log\operatorname{softmax}(w)_f,
\qquad \log\widetilde P(\$input)=0.
\]

仅输入程序的质量就是1，再加上任何合法非输入程序的正质量，总和已超过1。这可以作为有界搜索的未归一化 ranking score，但不能直接当成归一化生成模型的程序概率。Color 常量也支付全词表的代价，而不是在当前合法 Color choices 中的条件选择代价。

官方 `buildCandidates` / `likelihoodSummary` 对每一步的合法候选集合计算归一化项，并处理作用域内变量。因此简单的“primitive 使用次数相同”不保证官方 prior 相同；V1 在忽略类型上下文后会改变长度、常量和组合的相对搜索难度。这是概率模型差异，不应在本轮偷偷替换为另一套搜索目标。

论文层面的 Bayesian 目标为：

\[
J(\mathcal L,\theta)=P(\mathcal L,\theta)
\prod_t\sum_p P(t\mid p)P(p\mid\mathcal L,\theta).
\]

有限 frontier 近似保留了对多个程序的求和。V1 的 top-K 容器存在，但压缩通常只取每个任务的一个 MAP 程序，且优化的是 token saving；二者不是同一个优化问题。[论文 §2.4](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf)

V1 recognition 目标实际为：

\[
L_{V1}=-\sum_f\frac{c_f(p)+0.015}{|p|_{primitive}+0.015V}\log q_f(t).
\]

它压缩了顺序、类型机会及 AST 上下文，并对不同长度程序重新加权。即使去掉平滑，也不能一般等同于完整程序的负 log likelihood。保持网络不变而更换目标仍会实质改变算法，故本轮只审计，不修改。

## Bug 与本轮改动边界

新发现并修复：压缩器按“已有学习定义个数”命名 `learned_i`，若基础 domain 已有同名 primitive，会覆盖它。现在选择尚未占用的名字，并增加回归测试。默认 Grid 没有名称冲突，所以这一修复不改变本轮训练或搜索结果。

上一阶段已修复的 Dream 最后一次尝试边界、已有库定义 MDL 成本、raw/expanded recovery 与首解截尾问题仍保留。这里没有把“未复现论文目标”伪装成普通 bug 后大改实现。

`search.py`、`grammar.py`、`recognition.py` 与上一阶段存档的 SHA-256 一致。新增曲线仪器复用**原枚举器的相同前缀**；含分支、成功、失败、状态截断的回归测试证明每档预算的 frontier、节点数、展开状态和停止原因与逐次独立调用原 `search` 相同。它不改变候选顺序或评分，不把共享运行的时间包装成独立任务耗时。

## 阻止 faithful reproduction 结论的优先级

1. **概率模型与 Bayesian 目标不同**：global token score、零变量代价、缺少 typed conditional normalizers 及联合 objective；guided frontier 又未与 generative posterior 分开。
2. **抽象发现空间与目标过窄**：exact-subtree、单输入参数、每轮最多一个宏、无 β-refactoring 或一般参数化；token MDL 不能替代论文的库学习目标。
3. **Recognition objective 与 grammar family 不同**：频次分类 + task-conditioned unigram 无法复现 MAP/bigram 对语法对称性的学习。
4. **Grammar/replay 估计简化**：计数、等权 replay、输入采样与搜索分数不一致，形成另一种训练分布。
5. **缺少多轮闭环与较丰富的类型/程序表示**：限制可形成的层级库与可迁移程序族。

本轮 controlled benchmark 只能检验这些现有组件在可控复用结构上的表现，不能以更好的 A/B/C/D 数字替代 fidelity 证明；也没有原算法的受控实现对照，不能把每一分性能损失精确归因于某项差异。
