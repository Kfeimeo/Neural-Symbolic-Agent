"""Render an honest status/report from completed evidence; never fill missing cells."""
from pathlib import Path
import json
import statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent


def fmt(x):
    return '未定义' if x is None else f'{x:.4f}'


def main():
    evidence_path = OUT/'completed_evidence.json'
    if evidence_path.exists():
        evidence = json.loads(evidence_path.read_text(encoding='utf8'))
        coverage = evidence['coverage']
        if (len(list((OUT/'runs').rglob('round_*.json.gz'))) == coverage['training_round_records']
                and len(list((OUT/'evaluation').rglob('*.json.gz'))) == coverage['held_out_records']):
            from results.equivalence_abstraction.write_completed_report import render
            render(evidence)
            return
    analysis = json.loads((OUT/'analysis.json').read_text()) if (OUT/'analysis.json').exists() else None
    summary = json.loads((OUT/'replay_summary.json').read_text()) if (OUT/'replay_summary.json').exists() else None
    complete = analysis is not None and analysis['complete']
    lines = ['# Phase 3 — Equivalence-Aware Abstraction Discovery', '',
             f'**状态：{"全量指标已生成，结论需结合下表审阅" if complete else "实验未完成；以下仅列已完成证据"}。**', '',
             '## 冻结边界与实现', '',
             '- Phase 1/2 benchmark、reuse regimes、Haskell solver/DSL/evaluator、recognition、Wake budgets、top-K、六轮 EC、MDL、inside-outside 和 held-out 代码均复用。',
             '- B0 原压缩器；B1 RR-normalization 后原压缩器；B2 E/R 闭包的固定 cost 最小代表后原压缩器；B3 在 e-class 对上反统一，再用原 Haskell MDL gate。',
             '- 规则的代数依据、RR 终止性和 critical-overlap/confluence 分析见 [EQUATIONS.md](experiments/equivalence_abstraction/EQUATIONS.md)。有限 probes 只用于评估，不用于生成 equation。',
             '- B3 当前为一阶应用体、最多两个 AU 参数；保留 invention 为 opaque atom。候选生成后按结构改写大小选 witness，再由原 MDL 接受/拒绝；不是对所有 witness 分配做联合 MDL 全局最优化。',
             '- 显式 E/R 闭包上限 512、每对 AU 上限 256；超限使该 cell 失败，不报告为完整饱和。',
             '- Windows checkout 的 24 个 JSON 曾有 CRLF 差异；已恢复为与冻结 SHA-256 完全一致的字节，并加入 LF 属性。冻结 manifest 未改。', '',
             '## 已完成的配对重压缩诊断', '',
             '诊断输入是 Phase 2 保存的最终 frontiers 和 grammar。四臂都额外运行最多三次 compression；这不是重新执行六轮 EC，也不是原始 Wake frontier 的重建。B0 同样执行额外压缩，用于控制额外优化机会。', '']
    if summary:
        lines += [f"完成 {sum(r['cells'] for r in summary['arms'].values())}/36 个 medium-reuse 诊断：3 个独立 benchmark instances × 3 training seeds × 4 arms。训练 seeds 不当作 9 个独立 benchmark。", '',
                  '| Arm | 新 invention 总数 | 平均额外 ΔMDL | behavioural precision | recall | F1 | parameter recall |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for arm, r in summary['arms'].items():
            b = r['behavioural_recovery']
            lines.append(f"| {arm} | {r['new_inventions_total']} | {fmt(r['extra_delta_mdl_mean'])} | {fmt(b['precision'])} | {fmt(b['recall'])} | {fmt(b['f1'])} | {fmt(r['parameterised_latent_recall'])} |")
        lines += ['', '| Arm | syntactic ER@1 / ER@2 | behavioural ER@1 / ER@2 | usable ER@1 / ER@2 | P(param recovery ∣ multiple values) |',
                  '|---|---|---|---|---|']
        for arm, r in summary['arms'].items():
            cells = [' / '.join(fmt(r['er'][kind][f'ER@{n}']) for n in (1, 2)) for kind in ('syntactic', 'behavioural', 'equivalence_usable')]
            c = r['conditional_parametric_recovery']
            lines.append(f"| {arm} | {' | '.join(cells)} | {c['numerator']}/{c['denominator']} = {fmt(c['probability'])} |")
        lines += ['', '每个 latent 的多个参数值均分别检测；保留 specialised invention 的参数匹配见证。generalised recovery 要求参数类型兼容并通过全部有效参数值的独立 probes。空条件分母为 null。', '',
                  '这些指标描述压缩后的 persistent frontiers；ER 的分母是 active latents，支持数按不同训练 task 计算，ER@1/2 不是 frontier rank。']
    else:
        lines += ['36 个压缩诊断已写入 replay/ 时，replay_metrics/ 的语义与参数评估仍可能进行中；未完成汇总时不填数值。']
    lines += ['', '## 六轮 EC 与 held-out', '']
    if analysis:
        lines += [f"已汇总 {analysis['observed_training_cells']}/{analysis['expected_training_cells']} 个 training-round cells；当前缺少 {len(analysis['missing'])} 条 training/evaluation 记录。", '',
                  '[analysis.json](results/equivalence_abstraction/analysis.json) 保留训练解题率、累计 compression ΔMDL、invention count、各 ER、参数恢复、held-out S(B) 和逐任务首解排名。未运行的 held-out 结果不替换为训练结果。']
        final = [r for r in analysis['cells'] if r['regime'] == 'medium' and r['iteration'] == 6]
        if final:
            lines += ['', '已完成的 medium 最终轮次（未配齐的 arms 不构成完整配对比较）：', '',
                      '| Arm | 完成 runs / 9 | training solve | recall | param recall | cumulative ΔMDL |',
                      '|---|---:|---:|---:|---:|---:|']
            for arm in ('B0', 'B1', 'B2', 'B3'):
                rs = [r for r in final if r['arm'] == arm]
                if not rs:
                    continue
                avg = lambda fn: statistics.mean(fn(r) for r in rs)
                lines.append(f"| {arm} | {len(rs)} | {fmt(avg(lambda r:r['training_solve_rate']))} | "
                             f"{fmt(avg(lambda r:r['behavioural_recovery']['recall']))} | "
                             f"{fmt(avg(lambda r:r['parameterised_latent_recall']))} | {fmt(avg(lambda r:r['cumulative_delta_mdl']))} |")
            for mode in ('library', 'recognition', 'shuffle'):
                lines += ['', f'已完成的 {mode} held-out S(B)：', '',
                          '| Arm | runs | S(100) | S(300) | S(1000) | S(3000) | S(10000) |', '|---|---:|---:|---:|---:|---:|---:|']
                for arm in ('B0', 'B1', 'B2', 'B3'):
                    rs = [r for r in final if r['arm'] == arm and mode in r['held_out']]
                    if rs:
                        scores = [fmt(statistics.mean(r['held_out'][mode]['curve'][str(b)] for r in rs)) for b in (100, 300, 1000, 3000, 10000)]
                        lines.append(f"| {arm} | {len(rs)} | {' | '.join(scores)} |")
    else:
        lines += ['尚无完整汇总。']
    lines += ['', '## 五个主要问题', '',
              '1. **RR 是否提高 recovery？** 先比较同输入诊断中的 B1−B0，再检验完整六轮配对结果；单个 seed 的训练 solve 差异不足以回答。',
              '2. **R+E canonicalization 是否缩小 exposure gap？** 报告 syntactic/behavioural/usable ER 的配对变化。usable ER 提升只是可改写性的证据，不自动等于 invention recovery。',
              '3. **B2 是否足够、是否必须 B3？** 需比较 recovery、参数恢复及 held-out 曲线，并审阅 B3 的候选和 witness-selection 限制；新增 invention/ΔMDL 不能单独证明充分性或必要性。',
              '4. **是否提高 parameter generalisation？** 使用 parameterised latent recall 和条件恢复率，单列 baked-in 匹配；不能只比较 invention 数量。',
              '5. **medium 剩余 gap 有多少来自 syntactic/equational variation？** 固定 frontier 诊断能隔离表示/提案变化；完整 EC 的后续 frontiers 会随 library/recognition 反馈改变，其 gap closure 仅作描述，不能直接称为因果归因比例。', '',
              '全量配对实验完成前，以上问题保持未定，不宣称 equality-aware abstraction 已提高 recovery 或 held-out solve rate。', '',
              '## 验证与复现', '',
              '验证文件：[validation_tests.xml](results/equivalence_abstraction/validation_tests.xml)。测试覆盖规则语义、RR overlaps、参数反统一、MDL gate、B0 parity 和既有 Phase 1/2 回归。', '',
              '运行方法见 [Phase 3 README](experiments/equivalence_abstraction/README.md)。protocol.json 锁定源码 hashes，代码变更必须使用新的结果目录。', '',
              'Babble-style e-class AU 的参考是 [Cao et al., POPL 2023](https://arxiv.org/abs/2212.04596)；本实现保留 DreamCoder 的 objective，不采用 Babble 的 library-selection objective。', '']
    if complete:
        groups = {arm: [r for r in analysis['cells'] if r['regime'] == 'medium' and r['iteration'] == 6 and r['arm'] == arm]
                  for arm in ('B0', 'B1', 'B2', 'B3')}
        def avg(arm, fn):
            return statistics.mean(fn(r) for r in groups[arm])
        recall = lambda r: r['behavioural_recovery']['recall']
        param = lambda r: r['parameterised_latent_recall']
        syn = lambda r: r['er']['syntactic']['ER@2']
        beh = lambda r: r['er']['behavioural']['ER@2']
        answers = {
            '1': f"Medium 平均 recovery：B0={avg('B0', recall):.4f}，B1={avg('B1', recall):.4f}；RR 差值={avg('B1', recall)-avg('B0', recall):+.4f}。这是本预算下的观察差异，不宣称统计显著。",
            '2': f"Medium behavioural−syntactic ER@2 gap：B0={avg('B0',beh)-avg('B0',syn):.4f}，B2={avg('B2',beh)-avg('B2',syn):.4f}。完整 EC 比较包含后续搜索反馈；固定输入结果另见诊断表。",
            '3': f"B3−B2 recovery 差值={avg('B3',recall)-avg('B2',recall):+.4f}。结合上表 held-out 曲线判断实际收益；这不能证明完整 e-class 在所有任务中必要或 B2 普遍充分。",
            '4': f"参数化 latent recall：B0={avg('B0',param):.4f}，B1={avg('B1',param):.4f}，B2={avg('B2',param):.4f}，B3={avg('B3',param):.4f}。条件恢复率与 specialised 见证单列，不以数量代替泛化。",
            '5': '完整 EC 的 gap closure 不是纯 syntactic variation 的因果比例。下面给出固定 frontier、固定额外压缩预算下能够被表示/提案干预恢复的基线 gap 份额；仅作为本规则集和候选范围下的操作性下界。',
        }
        attribution = {}
        replay_rows = {}
        for p in (OUT/'replay_metrics').glob('*.json.gz'):
            import gzip
            with gzip.open(p, 'rt', encoding='utf8') as stream:
                r = json.load(stream)
            replay_rows[r['seed'], r['training_seed'], r['arm']] = r['metrics']
        for arm in ('B1', 'B2', 'B3'):
            numerator = denominator = 0
            for (seed, ts, label), b in replay_rows.items():
                if label != 'B0' or (seed, ts, arm) not in replay_rows:
                    continue
                recovered0 = set(b['recovery']['metrics']['behavioral']['recovered_latents'])
                gap = {fid for fid, s in b['behavioural'].items() if s['count'] >= 2} - recovered0
                recovered = set(replay_rows[seed, ts, arm]['recovery']['metrics']['behavioral']['recovered_latents'])
                numerator += len(gap & recovered)
                denominator += len(gap)
            attribution[arm] = {'recovered_gap_instances': numerator, 'baseline_gap_instances': denominator,
                                'fraction': numerator/denominator if denominator else None}
        lines += ['## 全量完成后的数值回答', ''] + [f'{i}. {answer}' for i, answer in answers.items()]
        lines += ['', '固定 frontier gap 份额：`' + json.dumps(attribution, ensure_ascii=False) + '`', '']
        (OUT/'report_answers.json').write_text(json.dumps({'answers': answers, 'fixed_frontier_attribution': attribution}, ensure_ascii=False, indent=2), encoding='utf8')
    (ROOT/'PHASE3_REPORT.md').write_text('\n'.join(lines), encoding='utf8')


if __name__ == '__main__':
    main()
