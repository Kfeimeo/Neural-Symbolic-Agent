# Phase 3 — Equivalence-Aware Abstraction Discovery：阶段总结

## 结论与完成范围

**现有证据支持“等价表示能增加可用 exposure，但当前实现没有把它转化为额外的 latent recovery 或参数泛化”。这不是全量 Phase 3 的最终结论。**

运行进程已经退出，但“进程结束”不等于“预定实验全部完成”。续跑状态文件停留在等待子集，未产生 `full_study.log`；没有足够证据确定退出原因。本次仅整理已保存结果，没有重启训练、补跑 held-out，或改变冻结预算。

| 实验部分 | 已完成 / 预定 | 可支持的结论 |
|---|---:|---|
| medium 固定-frontier 重压缩 | 36/36 | 3 benchmark seeds × 3 training seeds × 4 arms 的配对诊断 |
| 六轮 EC runs | 4/72 | 仅 seed 101 / medium / training seed 1 的四臂 |
| training-round records | 24/432 | 上述四臂均完成六轮 |
| held-out records | 22/936 | B0/B1 的 library 1–6 轮、recognition 1–5 轮 |

B2/B3 没有 held-out 记录；B0/B1 缺最终轮 recognition 和 shuffle。因此不能比较四臂最终 recognition-guided S(B)，也不能声称 held-out 泛化已经改善。

## 1. 冻结边界与方法范围

benchmark、reuse regimes、recognition 架构及训练流程、Haskell solver/DSL/evaluator、Wake budgets、top-K、六轮 EC、DreamCoder Bayesian MDL objective、inside-outside 和 held-out 协议均保持原实现。Phase 3 使用独立的 frontier/proposal 适配层。

| Arm | 表示与候选生成 | 接受标准 |
|---|---|---|
| B0 | 原始 Full-DC compressor | 原 DreamCoder MDL |
| B1 | RR-normal form → 原 inverse-β compressor | 同上 |
| B2 | E/R 闭包 → 固定 cost 的单一代表 → 原 inverse-β compressor | 同上 |
| B3 | 跨任务 e-class anti-unification → 候选后选择 rewrite witness | 同上 |

RR 包括 identity、双反射、transpose/rotate180/invert involution、零平移、同色 recolor、trim 幂等和四次 rotate90。E 包括几何变换与逐像素操作、border/trim 的交换，以及旋转/翻转/transpose 与平移的坐标改写。平移会裁剪，故没有使用相反平移相消。所有规则来自 DSL 语义；probes 仅用于评估。

RR 按 AST 节点数严格下降；critical overlaps 和局部合流论证见 [EQUATIONS.md](experiments/equivalence_abstraction/EQUATIONS.md)。每次 E 生成 term 后先 RR-normalize，再插入。canonical cost 为 `(AST node count, deterministic serialization)`，不是 Bayesian MDL。

**实现范围必须随结论保留：** B3 是一阶应用体、最多两个 AU 参数的 Babble-style 实现，已有 inventions 保持 opaque。候选产生后按结构改写大小选择 witness，再调用冻结的 Haskell MDL；没有对所有 witness 分配做联合 MDL 全局优化，也没有复现 Babble 的完整 library-selection 算法。规则集不是 DSL 等价关系的完备公理化。

E/R 闭包上限 512 terms，每对 AU 上限 256 patterns，超限直接失败。B2 六轮训练已完成，但事后指标计算先 β 展开 invention，再饱和；其最终 frontier 超过 512-term 上限，所以最终完整 exposure/条件参数指标未取得。这个失败发生在指标计算，而非训练压缩；未提高上限或用截断值替代。

## 2. 固定-frontier 配对诊断：medium reuse

输入是同一组 Phase 2 **最终** frontiers 和 grammar，四臂分别额外压缩最多三次。这是固定输入的额外 Sleep 诊断，不是原始 Wake frontier 重建，也不代替六轮 EC。B0 也获得相同的额外优化机会。

以下为 9 个 `(benchmark seed, training seed)` cells 的均值，共 54 个 active-latent instances。只有 3 个独立 benchmark instances；training seeds 不能当作 9 个独立 benchmark。

### Exposure

| Arm | syntactic ER@1 | ER@2 | behavioural ER@1 | ER@2 | equivalence-usable ER@1 | ER@2 |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 64.81% | 48.15% | 96.30% | 85.19% | 85.19% | 74.07% |
| B1 | 64.81% | 48.15% | 96.30% | 85.19% | 85.19% | 74.07% |
| B2 | 66.67% | 48.15% | 96.30% | 85.19% | 85.19% | 74.07% |
| B3 | 66.67% | 48.15% | 96.30% | 85.19% | 85.19% | 74.07% |

ER@k 表示 active latent 获得至少 k 个不同训练 task 的支持，不是 frontier 排名。syntactic 使用冻结的 β-normal rewrite 判据；behavioural 是有限 probes 上的子表达式见证；usable 是当前显式 E/R 空间中能够缩短程序的 latent rewrite。三者的搜索空间不同，不保证集合严格嵌套。

B2/B3 的 syntactic ER@1 仅增加 1/54；ER@2 没有提升。虽然完整等价空间的 usable ER@2 为 74.07%，单一 canonical representative 没有把它全部暴露给原 compressor。

### Recovery 与参数泛化

| Arm | exact AST recall | β recall | behavioural precision | recall | F1 | parameterised recall |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 1.85% | 3.70% | 9.47% | 18.52% | 12.37% | 5.56% |
| B1 | 1.85% | 3.70% | 9.47% | 18.52% | 12.37% | 5.56% |
| B2 | 1.85% | 3.70% | 9.39% | 18.52% | 12.28% | 5.56% |
| B3 | 1.85% | 3.70% | 9.16% | 18.52% | 12.08% | 5.56% |

**四臂条件参数恢复率均为 2/20 = 10%。** 参数化 recall 均为 2/36 = 5.56%。条件分母逐 latent 检查多个有效参数值是否真的暴露；generalised recovery 要求参数类型兼容、并通过该 latent 全部有效参数值的 probes。

与原 Phase 2 相比，四臂都在 seed 303 / training seed 1 额外恢复了 F01：behavioural recall 从 9/54 增到 10/54。B0 已取得同样提升，所以它来自共同增加的压缩机会，不能计为 RR/E/AU 的增益。相对于额外压缩 B0，B1/B2/B3 在所有 9 个配对 cells 的 recovered-latent 集合完全相同，没有净增益，也没有被均值掩盖的 latent 得失互换。

新增 invention 中，每臂各有 1 个匹配目标 grid latent；新增 generalised parameter-latent 匹配为 0，新增 specialised/baked-in parameter-latent 匹配也为 0。B2/B3 其余新增 inventions 不匹配本 benchmark 的目标 latent。它们可以是有效的组合抽象，不能因 target precision 较低就称为语义错误；但也不能称为参数恢复。

### Invention 数量与 MDL：必须区分两个比较边界

| Arm | 新 invention 总数 | 最终 invention 数均值 | 转换后压缩局部 ΔMDL 均值 | 原始输入→最终结果总 ΔMDL 均值 |
|---|---:|---:|---:|---:|
| B0 | 1 | 11.667 | +0.127285 | +0.127285 |
| B1 | 1 | 11.667 | +0.127320 | -0.078169 |
| B2 | 4 | 12.000 | +0.576560 | -0.599665 |
| B3 | 4 | 12.000 | +0.643207 | -0.357250 |

正 ΔMDL 表示 MDL 下降、拟合改善。局部列从表示转换后的 corpus 开始计算；总列使用相同边界：原始 corpus 经冻结 inside-outside 拟合得到的 MDL，减去最终 grammar/corpus 的 MDL。原结果字段为 `delta_mdl` 与 `total_delta_mdl`（B0 二者边界相同）。

**此前“B2/B3 提高 MDL 收益”的表述只能指局部 compression gate；总收益并未提高。** 三个表示干预臂的固定-input 总 ΔMDL 均值为负。按 AST cost 选择代表没有保证其在非均匀 grammar 下有更好的 Bayesian MDL；候选通过后续 MDL gate，也不能抵消表示转换已造成的全部代价。

## 3. 六轮 EC：单个配对 cell

以下仅为 seed 101 / medium / training seed 1，不能推广到全部 reuse regimes 或独立 seeds。累计总 ΔMDL 按每轮“原始输入→最终输出”的一致边界累加，包含实际表示变换影响。不同臂后续 frontiers 已随学习发生变化，所以它是各自轨迹的累计量，不是对共同最终 corpus 的打分。

| Arm | training solve | inventions | behavioural P / R / F1 | parameter recall | 累计总 ΔMDL |
|---|---:|---:|---|---:|---:|
| B0 | 21/56 (37.50%) | 12 | 8.33% / 16.67% / 11.11% | 25.00% | +33.783214 |
| B1 | 21/56 (37.50%) | 12 | 8.33% / 16.67% / 11.11% | 25.00% | +30.522940 |
| B2 | 21/56 (37.50%) | 14 | 0.00% / 0.00% / 0.00% | 0.00% | +20.373581 |
| B3 | 20/56 (35.71%) | 13 | 7.69% / 16.67% / 10.53% | 25.00% | +24.875523 |

B0/B1/B3 均恢复 F04，B2 没有恢复目标 latent。B3 相对于 B2 在这个 cell 中保留了 recovery，但未超过 B0，且少解出一个训练任务。这支持继续检查 canonical representation 的信息损失，不能证明 e-class AU 普遍必要。

| Arm | syntactic ER@1 / ER@2 | behavioural ER@1 / ER@2 | usable ER@1 / ER@2 |
|---|---|---|---|
| B0 | 50.00% / 50.00% | 83.33% / 83.33% | 66.67% / 66.67% |
| B1 | 50.00% / 33.33% | 100.00% / 66.67% | 66.67% / 50.00% |
| B2 | 完整 exposure 汇总未取得 | 完整 exposure 汇总未取得 | 闭包超过 512；未测 |
| B3 | 50.00% / 33.33% | 83.33% / 83.33% | 83.33% / 66.67% |

B2 的 recovery 与 parameter recall 是独立计算的，不依赖饱和，因此表中的 0 是实测值；其失败的 exposure 项不是 0。

## 4. 已完成的 held-out S(B) 与首解排名

最终第六轮仅有 B0/B1 的 **library-only** 评估。每臂 30 个 held-out tasks；未解出任务保留为 rank > 10000，不填成 10000。

| Arm | S(100) | S(300) | S(1000) | S(3000) | S(10000) | 首解 rank 均值 / 中位数（仅 solved） |
|---|---:|---:|---:|---:|---:|---|
| B0 | 0.00% | 0.00% | 6.67% | 10.00% | 20.00% | 3151.33 / 2593.50 |
| B1 | 0.00% | 0.00% | 6.67% | 13.33% | 20.00% | 3369.50 / 2346.50 |

两臂 S(10000) 都为 20%；较低预算曲线有差异。solved-only rank 只描述已解子集，不能替代完整 solve curve。逐任务 rank 和全部 22 条中间轮次曲线保存在 `completed_evidence.json`，包括未解的 null；没有用第五轮 recognition 结果替代缺失的第六轮结果。

## 5. 五个主要问题的回答

1. **单纯 RR-normalization 是否提高 abstraction recovery？** 当前证据没有显示提高：9 个固定-input 配对 cells 的 recovered sets、参数恢复率均与 B0 相同；单个六轮 cell 也同为 1/6 recall。总 ΔMDL 反而低于 B0。

2. **R+E canonicalization 是否缩小 behavioural→syntactic gap？** 当前 cost-defined B2 只增加了一个 ER@1 latent-instance，ER@2 保持 26/54；没有缩小 ER@2 gap。完整 E/R 空间提供更多 usable exposure，但这不等于单一 canonical representative 已使原 compressor 可用。

3. **B2 是否足够，还是必须 B3？** 不能判定 B2 充分，也不能判定 B3 必要。固定-input 中二者新增 invention 数相同、recovery 相同；单个六轮 cell 中 B3 recall 高于 B2，但不高于 B0。B2/B3 held-out 缺失、样本不足，且 B3 的参数/一阶范围和 witness heuristic 会限制这个比较。

4. **是否提高 parameter generalisation，而不只是生成更多 specialised inventions？** 没有：四臂 parameter recall 同为 5.56%，条件恢复率同为 10%；没有新增目标参数 latent 的 generalised 或 specialised 匹配。更多 inventions 主要没有对齐目标 latent，不能作为参数泛化的证据。

5. **medium recovery gap 有多少可归因于 syntactic/equational variation？** 必须区分 exposure 可达性与实际 recovery：

   - 原 Phase 2 corpus 中有 20 个 `(seed, training seed, latent)` 实例满足 behavioural ER@2 但不满足 syntactic ER@2。当前 E/R 空间能让其中 **12/20 = 60%** 变为 usable。这是规则集内的表示可达性证据。
   - 不能用均值 `(74.07−48.15)/(85.19−48.15)=70%` 替代逐实例核对：usable 集合中还有 2 个实例没有原 behavioural-subexpression 见证，两个判据并非严格嵌套。
   - 原 Phase 2 有 **37** 个 behavioural ER@2 已暴露但未恢复的 latent-instances，其中 **29/37** 在等价空间中 usable。四臂都因额外压缩恢复其中相同的 1 个，B1/B2/B3 相对额外压缩 B0 的新增恢复为 **0**。剩余 36 个没有被等价干预进一步恢复。
   - 因而可以报告“60% 的该 exposure mismatch 可在当前理论中消除”，但不能报告“60% 的 recovery gap 已由语法变体解释或解决”。当前实际 equality-specific recovery gain 是 0；规则与候选不完备，也不能反推语法等价变化毫无作用。

## 6. 验证、局限与后续工作

- 32 项测试通过，覆盖 RR overlaps、矩形网格语义、参数反统一、MDL gate 和既有 Phase 1/2 回归。B0 六轮的 grammar、frontiers、Wake 首解排名均与保存的 Phase 2 一致。
- 三个 benchmark 的冻结 hashes 已重新核验。Windows CRLF 差异恢复成原冻结 LF 字节，manifest 未变。
- 实际使用 py312 / PyTorch 2.12.1+cu132，但继承 Phase 2 显式 CPU recognition 配置；CUDA 未用于本批实验。Haskell Wake/压缩仍为 CPU。
- behavioural 和参数恢复均为独立有限 probes 的见证，不是任意输入上的等价证明；所有 rewrite equations 另由 DSL 语义支持。
- 当前只有一个六轮配对 cell 和部分 held-out，不能报告总体显著性、全部 regimes 对比，或一般性的 B2/B3 优劣。
- 后续先补齐四臂最终 held-out 及其余冻结 cells；若要提高 512 cap、改变 AU 范围或 witness 选择，须另建协议版本，不能混入当前冻结结果。
- 在设计修订前，应优先审计表示转换造成的总 MDL 损失，以及已 usable 却未被提案/选择的 latent；不能仅以增加 invention 数作为成功判据。

## 7. 可核查产物

- [完成范围与全部已完成证据](results/equivalence_abstraction/completed_evidence.json)
- [配对诊断汇总](results/equivalence_abstraction/replay_summary.json)
- [逐 latent 的 gap、得失与新增 invention 分类](results/equivalence_abstraction/report_diagnostics.json)
- [冻结协议与源码 hashes](results/equivalence_abstraction/protocol.json)
- [B0 六轮 parity 与测试记录](results/equivalence_abstraction/validation.json)
- [规则证明和实现限制](experiments/equivalence_abstraction/EQUATIONS.md)

`analysis.json` 是早期、不完整的流水线快照；本报告以 `completed_evidence.json` 为最新整理依据。复现当前阶段总结：

```powershell
$env:PYTHONPATH = 'E:\dev\AI\ARC-AGI-3\faithful\vendor'
& 'E:\anaconda3\envs\py312\python.exe' -m results.equivalence_abstraction.summarize_completed
& 'E:\anaconda3\envs\py312\python.exe' -m results.equivalence_abstraction.write_completed_report
```

以上命令只整理现有结果，不启动训练或 held-out 搜索。
