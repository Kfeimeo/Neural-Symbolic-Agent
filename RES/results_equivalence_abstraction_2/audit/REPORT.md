# Phase 3：同步后的 5 参数版本

2026-09-23 审计。数据目录：`RES/results_equivalence_abstraction_2`。

协议内 egraph.py 源码哈希精确匹配当前 `max_parameters=5` 文件；其他来源文件也均可匹配本地内容（允许 LF/CRLF 差异）。协议的 `max_au_parameters: 2` 和两参数 scope 描述仍是旧的硬编码元数据，不能作为本批实际源码配置。本次不改写原始协议。相比上一批，B3 结果确实改变。

medium 覆盖完整：36 个运行、216 个训练轮次、468 份评估。预期文件无缺失，JSON 可读取，评估身份字段一致；全部保存的 solve curves 与逐任务 first_solution_nodes 重新计数一致。没有重新运行训练或语义评估。zero/low/high 未包含在这批数据中。

第六轮结果，每组 9 次运行宏平均：

| 指标 | B0 | B1 | B2 | B3（5 参数） |
|---|---:|---:|---:|---:|
| Syntactic ER@1 | 64.81% | 61.11% | 68.52% | 72.22% |
| Syntactic ER@2 | 48.15% | 38.89% | 53.70% | 55.56% |
| Behavioural precision | 8.74% | 9.29% | 6.09% | 7.50% |
| Behavioural recall | 16.67% | 18.52% | 12.96% | 16.67% |
| Behavioural F1 | 11.31% | 12.18% | 8.18% | 10.16% |
| Parameterised latent recall | 5.56% | 8.33% | 2.78% | 5.56% |
| Invention count | 11.56 | 12.44 | 13.22 | 13.44 |
| 累计 raw-frontier → final ΔMDL | 37.99 | 35.76 | 28.51 | 33.82 |
| Training solve rate | 41.87% | 40.28% | 42.86% | 42.86% |
| Library S(10000) | 36.07% | 33.84% | 33.87% | 34.52% |
| Recognition S(10000) | 38.77% | 37.65% | 35.79% | 35.71% |
| Shuffle S(10000) | 36.08% | 35.36% | 34.24% | 33.04% |

ΔMDL 累加每轮 total_delta_mdl，缺该字段时使用 delta_mdl；不同 EC 轨迹的 corpus 不同，不是固定输入上的配对压缩收益。行为恢复是冻结 probes 上的指标，不是语义证明。

与上次已审计的 B3 两参数汇总比较（旧目录已被同步替换，以下旧值来自上次审计记录）：

| 指标 | B3 两参数 | B3 五参数 |
|---|---:|---:|
| 行为恢复 | 8/54 = 14.81% | 9/54 = 16.67% |
| 参数化恢复 | 1/36 = 2.78% | 2/36 = 5.56% |
| Syntactic ER@2 | 51.85% | 55.56% |
| Invention count | 13.22 | 13.44 |
| 累计 ΔMDL | 30.66 | 33.82 |
| Library S(10000) | 32.27% | 34.52% |
| Recognition S(10000) | 37.24% | 35.71% |

恢复集合中新增的是 seed=303、training_seed=3 的 F04；其余最终恢复集合与上次审计记录一致。B0/B1/B2 的汇总与上次一致。五参数 B3 的行为恢复及参数恢复均追平 B0，仍未超过 B1；precision、F1、最大预算 held-out solve rate 均低于 B0。扩大 AU 参数上限有局部恢复收益，但尚无整体泛化提升证据，未做统计显著性检验。

新 B3 recognition 曲线 S(B)：100→3.45%，300→6.50%，1000→13.35%，3000→22.44%，10000→35.71%。完整三模式曲线和每个运行的已解决任务 first-solution rank 均值/中位数见 saved_evidence.json；未解任务不能当作 rank=10000。

研究问题的当前结论：RR normalization 有小幅描述性恢复改善；B2/B3 syntactic ER@2 高于 B0；B3 五参数恢复高于 B2，但尚不能证明完整 e-class AU 的必要性或泛化优势。behavioural ER、equivalence-usable ER、multiple-parameter-exposure 条件恢复率及 specialised invention 匹配尚缺，无法量化 behavioural/syntactic gap closure 或将恢复差异因果归因于 equational variation。

复现保存数据审计：`python scripts/audit_phase3_results.py RES/results_equivalence_abstraction_2`。本报告与 saved_evidence.json 均为本次新生成的分析产物。
