"""Differential study: shared version-space compressor vs the pinned OCaml binary.

Corpora use only primitives registered in the reference binary, so the same
grammar and frontiers are given to both implementations. The reference is run
with verbose=true; its log lists, for every rescored candidate in rank order,
the discrete (beam) score, the continuous score and the rewritten frontiers.
All of these are compared with our trace, as are the final library, weights
and rewritten frontiers of every iteration.

    python -m faithful.versionspace.differential generate   # deterministic corpora and reference inputs
    python -m faithful.versionspace.differential official   # needs WSL; saves reference outputs and logs
    python -m faithful.versionspace.differential compare    # reruns ours, writes comparison.json
"""
import gzip
import json
import math
import os
import random
import re
import subprocess
import sys
import time
from ..python.kernel import ROOT, base, arrow, variable, primitive, index, application, abstraction, invented
from ..compression.versionspace import VersionSpaceKernel

OUT = ROOT/'faithful/results/versionspace'
REFERENCE = ROOT/'faithful/reference/ec'
INT, BOOL = base('int'), base('bool')
def lst(t): return {'constructor': 'list', 'arguments': [t]}
T0, T1 = variable(0), variable(1)
def fn(*ts):
    t = ts[-1]
    for a in reversed(ts[:-1]): t = arrow(a, t)
    return t

# Names and types exactly as registered in solvers/program.ml.
PRIMITIVES = {
    '0': INT, '1': INT, '+': fn(INT, INT, INT), '-': fn(INT, INT, INT), '*': fn(INT, INT, INT), 'mod': fn(INT, INT, INT),
    'if': fn(BOOL, T0, T0, T0), 'eq?': fn(INT, INT, BOOL), 'gt?': fn(INT, INT, BOOL), 'is-prime': fn(INT, BOOL),
    'cons': fn(T0, lst(T0), lst(T0)), 'car': fn(lst(T0), T0), 'cdr': fn(lst(T0), lst(T0)), 'empty': lst(T0),
    'map': fn(fn(T0, T1), lst(T0), lst(T1)), 'fold': fn(lst(T0), T1, fn(T0, T1, T1), T1),
    'length': fn(lst(T0), INT), 'range': fn(INT, lst(INT)), 'index': fn(INT, lst(T0), T0),
}
LL, LI = fn(lst(INT), lst(INT)), fn(lst(INT), INT)

def grammar(names=PRIMITIVES, inventions=()):
    productions = [dict(program=primitive(n), type=PRIMITIVES[n], log_weight=0.) for n in names]
    return dict(log_variable=0., productions=productions+[dict(program=p, type=t, log_weight=0.) for p, t in inventions])

def show(p, function=False):
    """solvers/program.ml: string_of_program."""
    if 'index' in p: return '$%d' % p['index']
    if 'abstraction' in p: return '(lambda %s)' % show(p['abstraction'])
    if 'application' in p:
        s = show(p['application'][0], True)+' '+show(p['application'][1])
        return s if function else '('+s+')'
    if 'primitive' in p: return p['primitive']
    return '#'+show(p['invented'])

def parse(source):
    tokens = re.findall(r'\(|\)|#|[^\s()#]+', source)
    def expression(i):
        t = tokens[i]
        if t == '#':
            body, j = expression(i+1)
            return invented(body), j
        if t == '(':
            if tokens[i+1] == 'lambda':
                body, j = expression(i+2)
                assert tokens[j] == ')'
                return abstraction(body), j+1
            f, j = expression(i+1)
            while tokens[j] != ')':
                x, j = expression(j)
                f = application(f, x)
            return f, j+1
        return (index(int(t[1:])) if t[0] == '$' else primitive(t)), i+1
    p, j = expression(0)
    assert j == len(tokens), source
    return p

# List-processing solutions in the style of the published list domain; several
# tasks carry alternative solutions so that frontiers have more than one entry.
LIST_TASKS = [(LL, s.split(' | ')) for s in '''
(lambda (map (lambda (+ $0 1)) $0)) | (lambda (fold $0 empty (lambda (lambda (cons (+ $1 1) $0)))))
(lambda (map (lambda (+ $0 (+ 1 1))) $0)) | (lambda (map (lambda (+ (+ $0 1) 1)) $0))
(lambda (map (lambda (* $0 $0)) $0))
(lambda (map (lambda (- $0 1)) $0))
(lambda (map (lambda (* $0 (+ 1 1))) $0)) | (lambda (map (lambda (+ $0 $0)) $0))
(lambda (map (lambda (mod $0 (+ 1 1))) $0))
(lambda (map (lambda (if (gt? $0 0) $0 0)) $0))
(lambda (map (lambda (if (eq? $0 0) 1 0)) $0))
(lambda (map (lambda (if (gt? $0 1) (- $0 1) $0)) $0))
(lambda (fold $0 empty (lambda (lambda (if (gt? $1 0) (cons $1 $0) $0)))))
(lambda (fold $0 empty (lambda (lambda (if (eq? (mod $1 (+ 1 1)) 0) (cons $1 $0) $0)))))
(lambda (fold $0 empty (lambda (lambda (if (is-prime $1) (cons $1 $0) $0)))))
(lambda (fold $0 empty (lambda (lambda (if (gt? $1 1) (cons $1 $0) $0)))))
(lambda (fold $0 empty (lambda (lambda (cons $1 (cons $1 $0))))))
(lambda (cons 0 $0))
(lambda (cons 1 (cons 0 $0)))
(lambda (cdr (cdr $0)))
(lambda (cons (car $0) $0))
(lambda (cons (car $0) (cons (car $0) $0)))
(lambda (map (lambda (+ $0 (car $1))) $0))
(lambda (map (lambda (+ $0 (length $1))) $0))
(lambda (map (lambda (* $0 (car $1))) $0))
(lambda (cons (length $0) $0))
(lambda (cons (fold $0 0 (lambda (lambda (+ $1 $0)))) $0))
(lambda (map (lambda (index $0 $1)) (range (length $0))))
(lambda (map (lambda (+ (index $0 $1) $0)) (range (length $0))))
(lambda (range (length $0)))
(lambda (range (car $0)))
(lambda (map (lambda (+ $0 1)) (range (length $0))))
(lambda (map (lambda (* $0 $0)) (range (car $0))))
(lambda (cdr (map (lambda (+ $0 1)) $0))) | (lambda (map (lambda (+ $0 1)) (cdr $0)))
(lambda (map (lambda (+ $0 1)) (map (lambda (* $0 $0)) $0))) | (lambda (map (lambda (+ (* $0 $0) 1)) $0))
(lambda (map (lambda (* $0 $0)) (map (lambda (+ $0 1)) $0)))
(lambda (fold (cdr $0) empty (lambda (lambda (if (gt? $1 0) (cons $1 $0) $0)))))
'''.strip().splitlines()] + [(LI, s.split(' | ')) for s in '''
(lambda (fold $0 0 (lambda (lambda (+ $1 $0)))))
(lambda (fold $0 1 (lambda (lambda (* $1 $0)))))
(lambda (fold $0 0 (lambda (lambda (+ 1 $0))))) | (lambda (length $0))
(lambda (fold $0 0 (lambda (lambda (if (gt? $1 $0) $1 $0)))))
(lambda (length (cdr $0)))
(lambda (+ (car $0) (car (cdr $0))))
(lambda (fold (map (lambda (* $0 $0)) $0) 0 (lambda (lambda (+ $1 $0))))) | (lambda (fold $0 0 (lambda (lambda (+ (* $1 $1) $0)))))
(lambda (index 1 $0)) | (lambda (car (cdr $0)))
(lambda (index (+ 1 1) $0)) | (lambda (car (cdr (cdr $0))))
(lambda (fold $0 0 (lambda (lambda (+ (if (gt? $1 0) 1 0) $0)))))
'''.strip().splitlines()]

def list_corpus():
    return grammar(), [dict(request=r, entries=[dict(program=parse(s), log_likelihood=0.) for s in sources]) for r, sources in LIST_TASKS]

def leaves(p):
    if 'application' in p: return sum(map(leaves, p['application']))
    if 'abstraction' in p: return leaves(p['abstraction'])
    return 1

def uses(p, names):
    if 'application' in p: return any(uses(q, names) for q in p['application'])
    if 'abstraction' in p: return uses(p['abstraction'], names)
    return 'invented' in p and show(p) in names

def planted_corpus(k, seed, tasks, names, latents=4, alternatives=.3, likelihoods=False, keep_latents=0, sizes=(6, 20)):
    """Programs sampled around hidden latent functions, then inlined.

    The learner sees base-language programs only (except `keep_latents`
    inventions deliberately left in the library, to exercise inlining)."""
    rng = random.Random(seed)
    g0 = grammar(names)
    def draw(g, request, fuel):
        try: return k.call('sample', grammar=g, request=request, uniforms=[rng.random() for _ in range(fuel)])['program']
        except ValueError: return None
    hidden = []
    latent_requests = [fn(INT, INT), fn(INT, INT, INT), LL, LI, fn(INT, lst(INT), lst(INT)), fn(fn(INT, INT), lst(INT), lst(INT))]
    def bound(p, depth=0):
        if 'application' in p: return bound(p['application'][0], depth) | bound(p['application'][1], depth)
        if 'abstraction' in p: return bound(p['abstraction'], depth+1)
        return {p['index']-depth} if 'index' in p and p['index'] >= depth else set()
    def parameters(p):
        n = 0
        while 'abstraction' in p: p, n = p['abstraction'], n+1
        return {i-n for i in bound(p, 0)} == set(range(-n, 0))
    while len(hidden) < latents:
        request = rng.choice(latent_requests)
        body = draw(g0, request, 16)
        # A latent must use each of its parameters and be new.
        if body is None or not 4 <= leaves(body) <= 9 or not parameters(body) or any(show(body) == show(h['invented']) for h, _ in hidden): continue
        hidden.append((invented(body), k.call('infer', grammar=g0, program=invented(body))['type']))
    g1 = grammar(names, hidden)
    g1['log_variable'] = 1.5
    for pr in g1['productions'][len(names):]: pr['log_weight'] = 1.5
    kept = hidden[:keep_latents]
    learner = grammar(names, kept)
    inline_names = {show(p) for p, _ in hidden[keep_latents:]}
    def expand(p):
        # Inline every hidden latent the learner is not given; kept ones stay opaque.
        if not uses(p, inline_names): return p
        marker = {}
        def strip(q):
            if 'application' in q: return application(*map(strip, q['application']))
            if 'abstraction' in q: return abstraction(strip(q['abstraction']))
            if 'invented' in q and show(q) not in inline_names:
                marker['__kept%d' % len(marker)] = q
                return primitive('__kept%d' % (len(marker)-1))
            return q
        def restore(q):
            if 'application' in q: return application(*map(restore, q['application']))
            if 'abstraction' in q: return abstraction(restore(q['abstraction']))
            return marker.get(q.get('primitive'), q)
        return restore(k.call('beta', program=strip(p))['program'])
    def solution(request):
        for _ in range(400):
            p = draw(g1, request, 30)
            if p is None or not uses(p, {show(h) for h, _ in hidden}): continue
            q = expand(p)
            if not sizes[0] <= leaves(q) <= sizes[1] or show(q) in seen: continue
            try: k.call('score', grammar=learner, request=request, program=q)
            except ValueError: continue
            seen.add(show(q))
            return q
    frontiers, seen = [], set()
    requests = [LL, LL, LI, fn(INT, INT), fn(INT, lst(INT), lst(INT))]
    while len(frontiers) < tasks:
        request = rng.choice(requests)
        programs = []
        for _ in range(1 + (rng.random() < alternatives) + (rng.random() < alternatives/2)):
            p = solution(request)
            if p is not None and all(show(p) != show(q) for q in programs): programs.append(p)
        if programs:
            frontiers.append(dict(request=request, entries=[dict(program=p,
                log_likelihood=round(-rng.random(), 3) if likelihoods and i else 0.) for i, p in enumerate(programs)]))
    return learner, frontiers

ARITHMETIC = ['0', '1', '+', '-', '*', 'mod', 'if', 'eq?', 'gt?', 'is-prime']
FIRST_ORDER = ARITHMETIC+['cons', 'car', 'cdr', 'empty', 'length', 'range', 'index']

def cases(k):
    """name -> (grammar, frontiers, reference options)."""
    result = {}
    def add(name, corpus, **options):
        g, fs = corpus
        result[name] = dict(grammar=g, frontiers=fs, options=dict(dict(arity=3, iterations=3, top_k=2, top_i=300, beam_size=1000000,
            pseudo_counts=30., aic=1., structure_penalty=1.5, inline=True), **options))
    # Defaults above follow the reference's list-domain script (arity 3, topK 2,
    # pseudocounts 30) except the structure penalty, which that script sets to 1.
    add('list_arity3', list_corpus(), iterations=2, top_i=40)
    add('list_arity2', list_corpus(), arity=2, iterations=4)
    add('list_arity1', list_corpus(), arity=1, iterations=4, top_k=5)
    add('list_cheap_library', list_corpus(), arity=2, iterations=6, structure_penalty=.2, pseudo_counts=1.)
    add('list_top1', list_corpus(), arity=2, top_k=1, iterations=3)
    add('list_narrow_rescoring', list_corpus(), arity=2, top_i=12, iterations=3)
    add('list_narrow_beam', list_corpus(), arity=2, beam_size=6, iterations=2)
    add('list_no_inline', list_corpus(), arity=2, inline=False, iterations=4, structure_penalty=.2)
    # Runs that end because no candidate improves the objective, not by the iteration bound.
    add('list_until_rejected', list_corpus(), arity=1, iterations=30, top_k=5)
    add('list_nothing_to_learn', list_corpus(), arity=1, iterations=30, top_k=5, structure_penalty=4., aic=3.)
    # The reference needs many minutes to rescore 300 candidates on these corpora, hence
    # the smaller top_i beyond seed 0. Its arity-3 run on 30 tasks of up to 20 leaves
    # reached 14 GB and was stopped, hence the shorter arithmetic programs.
    for seed in range(3):
        add('planted_arith_%d' % seed, planted_corpus(k, seed, 20, ARITHMETIC, latents=3, sizes=(5, 10)), arity=3, structure_penalty=.5, top_i=40, iterations=2)
    for seed in range(3):
        add('planted_first_order_%d' % seed, planted_corpus(k, 100+seed, 40, FIRST_ORDER, latents=4), arity=2, structure_penalty=.5, top_i=60 if seed else 300)
    for seed in range(3):
        add('planted_list_%d' % seed, planted_corpus(k, 200+seed, 40, list(PRIMITIVES), latents=5), arity=2, structure_penalty=.5, top_i=60 if seed else 300)
    for seed in range(2):
        add('planted_weighted_%d' % seed, planted_corpus(k, 300+seed, 36, list(PRIMITIVES), latents=4, alternatives=.9, likelihoods=True),
            arity=2, top_k=3, structure_penalty=.5, pseudo_counts=1., top_i=60 if seed else 300)
    for seed in range(3):
        add('planted_inlining_%d' % seed, planted_corpus(k, 400+seed, 36, list(PRIMITIVES), latents=5, keep_latents=2), arity=2, structure_penalty=.5, top_i=60 if seed else 300)
    add('planted_large_0', planted_corpus(k, 500, 100, list(PRIMITIVES), latents=8), arity=2, structure_penalty=1., iterations=2, top_i=30)
    return result

def official_input(case):
    g, o = case['grammar'], case['options']
    return dict(DSL=dict(logVariable=g['log_variable'], productions=[dict(expression=show(p['program']), logProbability=p['log_weight']) for p in g['productions']]),
        frontiers=[dict(request=f['request'], programs=[dict(program=show(e['program']), logLikelihood=e['log_likelihood']) for e in f['entries']]) for f in case['frontiers']],
        arity=o['arity'], topK=o['top_k'], topI=o['top_i'], bs=o['beam_size'], CPUs=1, iterations=o['iterations'], aic=o['aic'],
        pseudoCounts=o['pseudo_counts'], structurePenalty=o['structure_penalty'], inline=o['inline'], verbose=True)

def linux(path): return '/mnt/'+str(path)[0].lower()+str(path)[2:].replace('\\', '/')

def run_official(names):
    # One WSL session for the batch; the binary and reference checkout are not modified.
    # The loop lives in a script file because wsl.exe re-expands its command line.
    # A verbose multi-iteration run writes checkpoints to ./compressionMessages.
    lines = ['mkdir -p /tmp/vsdiff/compressionMessages && cd /tmp/vsdiff || exit 1', 'for n in %s; do' % ' '.join(names), '  s=$(date +%s.%N)',
        '  timeout 3600 "%s/compression" "%s/$n.input.json" > "%s/$n.official.json" 2> "%s/$n.official.log"' % (linux(REFERENCE), *[linux(OUT)]*3),
        '  echo "$? $s $(date +%%s.%%N)" > "%s/$n.official.status"' % linux(OUT), 'done', '']
    script = OUT/('run_official_%d.sh' % os.getpid())
    script.write_bytes('\n'.join(lines).encode())
    subprocess.run(['wsl', '-d', 'Ubuntu-24.04', '--', 'sh', linux(script)], check=True)
    script.unlink()
    for n in names:
        # Verbose logs are large and repetitive; they are kept compressed.
        log = OUT/f'{n}.official.log'
        with gzip.GzipFile(OUT/f'{n}.official.log.gz', 'wb', mtime=0) as f: f.write(log.read_bytes())
        log.unlink()

def reference(name):
    """(output JSON, verbose log, exit status and wall-clock seconds) of a saved reference run."""
    status = (OUT/f'{name}.official.status').read_text().split()
    with gzip.open(OUT/f'{name}.official.log.gz', 'rt', encoding='utf8') as f: log = f.read()
    return json.loads((OUT/f'{name}.official.json').read_text(encoding='utf8')), log, int(status[0]), float(status[2])-float(status[1])

def parse_log(text):
    """Per compression step: candidate count, initial score and rescored candidates in rank order."""
    steps, trial = [], None
    for line in text.splitlines():
        m = re.match(r'Got (\d+) candidates\.', line)
        if m:
            steps.append(dict(candidate_count=int(m.group(1)), trials=[])); trial = None; continue
        if not steps: continue
        step = steps[-1]
        m = re.match(r'Initial score: (\S+)', line)
        if m: step['before'] = float(m.group(1)); continue
        m = re.match(r'Invention (.+) : .+$', line)
        if m:
            trial = dict(invented=m.group(1), programs=[]); step['trials'].append(trial); continue
        m = re.match(r'Improved score to (\S+) ', line)
        if m: step['after'] = float(m.group(1)); trial = None; continue
        if line.startswith('No improvement possible'): step['rejected'] = True; trial = None; continue
        if trial is None: continue
        m = re.match(r'Discrete score (\S+)', line)
        if m: trial['discrete'] = float(m.group(1)); continue
        m = re.match(r'\tContinuous score (\S+)', line)
        if m: trial['continuous'] = float(m.group(1)); continue
        m = re.match(r'(-?[0-9.]+|-?inf)\t(.+)$', line)
        if m: trial['programs'].append(m.group(2))
    return steps

def our_steps(result):
    steps = []
    for h in result['history']+([result['final_step']] if result['final_step'] else []):
        trials = []
        for t in h.get('trace', []):
            name = show(t['invented'])
            # The reference prints only the frontiers that mention the invention.
            shown = [[show(e['program']) for e in f['entries']] for f in t['frontiers']]
            # Non-finite numbers arrive as null: an unreachable discrete cost, a rejected continuous score.
            trials.append(dict(invented=name, discrete=math.inf if t['discrete'] is None else t['discrete'],
                continuous=-math.inf if t['continuous'] is None else t['continuous'],
                programs=[s for f in shown if any(name in s for s in f) for s in f]))
        step = dict(candidate_count=h['candidate_count'], trials=trials, before=h.get('before'))
        if 'after' in h: step['after'] = h['after']
        else: step['rejected'] = True
        steps.append(step)
    return steps

def close(a, b, tolerance=2e-6):
    return a == b or (a is not None and b is not None and abs(a-b) <= tolerance)

def compare(ours, official, log):
    """Every difference is listed; an empty list means agreement on all the reference reports."""
    differences = []
    a, b = our_steps(ours), parse_log(log)
    if len(a) != len(b): differences.append(dict(kind='step_count', ours=len(a), official=len(b)))
    for n, (x, y) in enumerate(zip(a, b)):
        where = dict(step=n)
        if x['candidate_count'] != y['candidate_count']:
            differences.append(dict(where, kind='candidate_count', ours=x['candidate_count'], official=y['candidate_count']))
        if y['candidate_count'] and not close(x['before'], y.get('before')):
            differences.append(dict(where, kind='initial_score', ours=x['before'], official=y.get('before')))
        if bool(x.get('rejected')) != bool(y.get('rejected')) and y['candidate_count']:
            differences.append(dict(where, kind='acceptance', ours=not x.get('rejected'), official=not y.get('rejected')))
        if 'after' in x and 'after' in y and not close(x['after'], y['after']):
            differences.append(dict(where, kind='accepted_score', ours=x['after'], official=y['after']))
        if [t['invented'] for t in x['trials']] != [t['invented'] for t in y['trials']]:
            same_set = sorted((t['invented'], round(t['discrete'], 6)) for t in x['trials']) == sorted((t['invented'], round(t['discrete'], 6)) for t in y['trials'])
            differences.append(dict(where, kind='rank_order_within_ties' if same_set else 'ranked_candidates',
                ours=[t['invented'] for t in x['trials']][:5], official=[t['invented'] for t in y['trials']][:5]))
        # Distinct sources can close to the same invention, so trials are aligned by occurrence.
        theirs = {}
        for t in y['trials']: theirs.setdefault(t['invented'], []).append(t)
        for t in x['trials']:
            u = theirs.get(t['invented']) and theirs[t['invented']].pop(0)
            if not u: continue
            for key in ('discrete', 'continuous'):
                if not close(t[key], u[key]):
                    differences.append(dict(where, kind=key+'_score', invented=t['invented'], ours=t[key], official=u[key]))
            if t['programs'] != u['programs']:
                differences.append(dict(where, kind='candidate_rewrite', invented=t['invented'],
                    ours=[p for p in t['programs'] if p not in u['programs']][:3], official=[p for p in u['programs'] if p not in t['programs']][:3]))
    theirs = {p['expression']: p['logProbability'] for p in official['DSL']['productions']}
    mine = {show(p['program']): p['log_weight'] for p in ours['grammar']['productions']}
    if set(mine) != set(theirs):
        differences.append(dict(kind='library', ours=sorted(set(mine)-set(theirs)), official=sorted(set(theirs)-set(mine))))
    else:
        worst = max([abs(mine[n]-theirs[n]) for n in mine]+[abs(ours['grammar']['log_variable']-official['DSL']['logVariable'])])
        if worst > 1e-9: differences.append(dict(kind='weights', max_abs_difference=worst))
    rewritten = [[show(e['program']) for e in f['entries']] for f in ours['frontiers']]
    reference = [[e['program'] for e in f['programs']] for f in official['frontiers']]
    if rewritten != reference:
        bad = [(x, y) for x, y in zip(rewritten, reference) if x != y]
        differences.append(dict(kind='final_frontiers', count=len(bad), ours=bad[0][0], official=bad[0][1]))
    return differences

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mode, only = sys.argv[1], sys.argv[2:]
    names = [p.name[:-len('.case.json')] for p in sorted(OUT.glob('*.case.json'))]
    if mode == 'official':
        return run_official([n for n in names if not only or n in only])
    with VersionSpaceKernel() as k:
        if mode == 'generate':
            for name, case in cases(k).items():
                (OUT/f'{name}.case.json').write_text(json.dumps(case), encoding='utf8')
                (OUT/f'{name}.input.json').write_text(json.dumps(official_input(case)), encoding='utf8')
            return
        # Naming corpora reruns only those and updates their rows of the saved report.
        path = OUT/'comparison.json'
        report = json.loads(path.read_text(encoding='utf8')) if only and path.exists() else {}
        for name in names:
            if only and name not in only: continue
            case = json.loads((OUT/f'{name}.case.json').read_text(encoding='utf8'))
            official, log, _, seconds = reference(name)
            start = time.time()
            # The reference likelihood isolates the version-space algorithm from the
            # OCaml/Python difference in polymorphic normalisers (see ReferenceLikelihood.hs).
            ours = k.call('vs_compress', grammar=case['grammar'], frontiers=case['frontiers'], trace=True, likelihood='ocaml', **case['options'])
            elapsed = time.time()-start
            differences = compare(ours, official, log)
            steps = ours['history']+([ours['final_step']] if ours['final_step'] else [])
            report[name] = dict(options=case['options'], frontiers=len(case['frontiers']), programs=sum(len(f['entries']) for f in case['frontiers']),
                steps=len(steps), inventions=[show(h['invented']) for h in ours['history']],
                candidates=[h['candidate_count'] for h in steps], rescored=sum(h['evaluated'] for h in steps),
                version_table_size=[h['version_table_size'] for h in steps],
                largest_log_version_size=max([x for h in steps for x in h['log_version_sizes']], default=0),
                seconds_ours=round(elapsed, 2), seconds_official=round(seconds, 2),
                differences=differences)
            print(name, 'steps', len(steps), 'candidates', report[name]['candidates'], 'ours %.1fs official %.1fs' % (elapsed, report[name]['seconds_official']),
                  'IDENTICAL' if not differences else sorted({d['kind'] for d in differences}), flush=True)
        path.write_text(json.dumps({name: report[name] for name in names if name in report}, indent=1), encoding='utf8')

if __name__ == '__main__': main()
