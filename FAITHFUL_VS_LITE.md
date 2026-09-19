# DreamCoder core 与 DreamCoder-lite

旧 V1 保留在 `dreamcoder/`，新实现位于 `faithful/`。两者独立运行，不通过 monkey patch
将旧搜索器包装成 Haskell，也不让新内核调用官方 solver 完成实际学习。

| 项目 | 旧 DreamCoder-lite | 新 core |
|---|---|---|
| Symbolic stack | Python | Haskell；Python 通过 versioned JSON 调用 |
| Language | `$input` + monomorphic first-order tree | de Bruijn λ calculus、多态、application、invention、β reduction |
| Probability | 全局 primitive softmax，input 免费 | request/environment 合法集合上的 conditional normalization，含变量质量 |
| Recognition context | task-conditioned unigram | root / variable-parent / primitive-argument bigram，类型与环境条件归一化 |
| Generative prior | guided search score 与 prior 混用 | 明确分离，候选重新按 G 评分 |
| Frontier | 有限多候选容器，但学习依赖 MAP | log evidence、posterior weights、expected sufficient statistics |
| Grammar update | MAP count + smoothing | official-style expected actual / possible update |
| Compression | exact subtree，单 input parameter，单个 macro | inverse β、内部表达式参数化、多参数、library objective、多个 invention、层级定义 |
| Dreams | 独立的 depth-capped heuristic sampler | 与 typed P(p) 一致的 ancestral draws，显式记录资源拒绝 |
| Replay | uniform repeated labels | BO 使用整个 frontier；KL posterior sampling |
| Recognition loss | primitive histogram CE | typed full-program BO / KL NLL |
| EC | 单轮实验为主 | 持久 library/frontier，重复 Wake/Compress/Dream/Train |
| Fidelity evidence | 自身单元测试、合成任务成绩 | 固定官方提交 live oracle、Haskell 数值对照、OCaml compression golden |
| Grid DSL | 24 productions | 已补齐同类型与语义的 24 productions；五操作版本仅保留作 smoke fixture |
| Search engineering | best-first，明确 node/state budgets | toy 入口使用 uniform-cost agenda，有真实 candidate/state caps；旧 exhaustive 接口保留作 golden oracle 比较 |

本阶段不依据 held-out performance 改 synthetic distribution，也不接 Stitch、ARC-3、RL、LLM。
fidelity fixtures 可含程序标签；真实 learner Task 仅含 I/O、request 和名字，没有 ground-truth 字段。

完整通过范围、官方差异和复跑命令见 `FAITHFUL_DREAMCODER_REPORT.md`。

2026-09-18：原始 36/24 toy 的 faithful 八组实验已实际运行，见 `FAITHFUL_TOY_REPORT.md`。
