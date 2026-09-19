# DreamCoder-lite synthetic benchmark calibration

这是历史 Lite 校准记录。当前 faithful core 的 controlled benchmark 与独立实验
见 `CONTROLLED_BENCHMARK_REPORT.md` 和 `CONTROLLED_EXPERIMENT_REPORT.md`。

本报告对应前一阶段的固定 seed=7 校准；结果不作为新 Haskell core 的 fidelity 验收依据。
完整数据已保存于 `results/calibration/summary.json`。本轮没有依据测试分数重选 benchmark、
latent fragments、模型架构或学习超参数。

## 固定 benchmark 与隔离

`benchmark_private.json` 在 learner 运行前固定，SHA-256：
`342bde58c0018fb3fe224284b3bedc37823f5acc24595a1b19918d7b2aa97cbc`。
共 96 个训练任务、60 个测试任务。训练有 12 个不同 ground-truth programs；
测试有 60 个不同 programs。所有真实 learner Task 删除 ground truth 并使用匿名名称。
隐藏 generator metadata 仅供评估，不进入 Wake、compression 或 recognition inference。

隐藏的四个 unary fragments 为：

* F0 = trim(flipH(input))；
* F1 = invert(translate(input,−1,+1))；
* F2 = transpose(invert(input))；
* F3 = flipV(translate(input,−1,−1))。

训练实例使用 F0/F1 各 12 次、F2/F3 各 36 次。测试分别使用 13/13/14/13 次
（包含 incidental matches）。generator 分别控制：context 深度；窄/宽 typed branching；
fragment reuse frequency。八个 shallow anchors、48 个 context/difficulty 组合、四个 depth-8
tail tasks 在运行前固定，未为了提高 D 的结果重新生成。

训练/测试的 full program、canonical program、32-probe behavior、完整 I/O task、input overlap
均为 0；nontrivial subtree overlap=9，17 个测试程序含共享子树。全部 replay/dream supervision
与 held-out 的 full/canonical/probe overlap 也为 0。Dream 排除固定保留集的标签碰撞，
不会移动测试任务或把其标签提供给 learner。Probe 等价只是有限输入上的判别，不是普遍等价证明。

## 原 benchmark 的问题

原 Wake 的 36 个任务只有 3 个不同程序，全部 depth=2 / size=3。允许压缩的重复
Grid fragments 正好是三个完整程序，各出现 12 次；真正内部、size≥3 的重复片段为 0。
共享的 trim(input) 只有 size=2，未达到该 compressor 的节省条件。单 macro 上限与 tie order
解释了最初为什么仅选出 rotate90(trim(input))，不能把它当成强 abstraction discovery 证据。

旧 600 个 Dreams 展开后 225 个不同程序，170 个 depth=0（28.33%）；depth histogram
为 170/109/71/56/107/65/19/3（depth 0–7）。Dreams 不进入旧 compressor 的学习 corpus。
原 replay 108 项、9 个不同程序，depth2=72、depth3=36；不是新的独立组合分布。
旧 stress 在 depth5–8 的 A 到 N=3000 仍为 0/24，N=10000 为 1/24；旧 D 在 N=3000、10000
均为 1/24。更大预算有帮助，但这些有限结果不能排除预算不足或定位唯一失败原因。

## 分布与学习结果

新训练深度 depth2=32、depth3=64，size3/4/5/6 分别为 16/32/16/32；
有 14 个重复 eligible fragments，其中 6 个 proper internal fragments。
测试 effective depth 为 `{1:8,3:16,4:8,5:16,6:8,8:4}`，不是按原始冗余 wrapper 数量分桶。
详细 AST size、primitive counts、arity、typed-growth 数据见 `diagnostics.json`。
typed syntactic counts 没有 semantic dedup 或 size bound，不能与实际 enumerated candidate 数混用。

Wake 解出 64/96 个训练任务（8 个不同 MAP programs）。旧 compressor 学到 F3，
MDL 256→226，库大小 24→25。Latent precision=1，recall=.25；由于它每次只能加一个 macro，
四个 latent 的 recall ceiling 本来就是 .25。仅供诊断的 GT corpus 压缩也是 F3，MDL448→346；
该诊断结果没有返回 learner。

离线 held-out representation 检查：native exact rewriting 影响 4 个任务、节省 12 tokens；
允许参数化重写时影响 13 个、节省 39；canonical representation 下影响 5 个、节省 15。
这测的是表示容量，**不代表旧 compressor 已经实现这些更一般的重写能力**。

## 固定预算曲线

所有配置使用同一测试集、topK=3、max states=300000、max AST size=33。
复用同一 grammar 的候选流来提取不同预算前缀，测试证明前缀结果与单独原 search 调用一致。
这没有改变旧 enumerator 或 search policy。Timing 不由共享流模拟，JSON 中相关 timing 指标为 null。

| 配置 / solve % | 100 | 300 | 600 | 1000 | 3000 | 10000 |
|---|---:|---:|---:|---:|---:|---:|
| A base uniform | 10.00 | 13.33 | 16.67 | 20.00 | 23.33 | 28.33 |
| B learned library/prior | 11.67 | 20.00 | 23.33 | 23.33 | 26.67 | 33.33 |
| base fitted prior | 6.67 | 13.33 | 16.67 | 16.67 | 18.33 | 26.67 |
| learned library uniform | 8.33 | 16.67 | 21.67 | 26.67 | 36.67 | 41.67 |
| C base + recognition | 13.33 | 21.67 | 25.00 | 28.33 | 35.00 | 41.67 |
| D library + recognition | 21.67 | 28.33 | 28.33 | 33.33 | 38.33 | 43.33 |
| C shuffled tasks | 10.00 | 13.33 | 15.00 | 16.67 | 25.00 | 28.33 |
| D shuffled tasks | 10.00 | 15.00 | 18.33 | 20.00 | 25.00 | 30.00 |

D 的 matched-task guidance 优于固定 derangement；但高预算下 library_uniform 与 C 都到41.67%，
D 为43.33%，不能宣称压倒性优势。这里只运行一个 seed 和一个固定 shuffle，没有统计显著性结论。
难度分层、各 latent/reuse/recipe、first solution、截尾统计、program recovery 和 frontier metrics
均保留于完整 JSON，不能只用 overall solve rate 掩盖失败的深度段。

这个 benchmark 提供浅层、中间过渡与长尾失败的诊断条件；并不因此证明旧实现就是 DreamCoder。
旧实现的算法偏差见 `DREAMCODER_FIDELITY_REPORT.md`；新内核独立的官方 golden 验收见
`FAITHFUL_DREAMCODER_REPORT.md`。
