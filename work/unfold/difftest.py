#!/usr/bin/env python3
"""**部品を開く段（unfold）を定義と突き合わせる。**

    python3 work/unfold/difftest.py <焼いた unfold> [本数] [種]

部品（component / use）を持つ本をランダムに組み、
  (1) 定義で走らせた答え（終了コードと出力）
  (2) unfold で開いた本を定義で走らせた答え
を比べる。unfold が本を書き換えたなら (1) と (2) は同じでなければならない。とくに
**定義が断る本を、開いた本が答えてはいけない**（DANGER —— 焼く道で黙って違う答えになる）。
書き換えなかった本（開けない —— 焼き手が use を断る）は数えるだけ。行の番号: 開いた本の前半は、
元の本と同じ位置に同じ改行を持つ（塊と use の行は空になる）。
"""
import os, random, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import lattix as L

UNF = os.path.abspath(sys.argv[1])
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)

def run_def(path):
    p = subprocess.run([sys.executable, os.path.join(ROOT, 'lattix.py'), path],
                       capture_output=True, text=True, timeout=120, cwd=ROOT)
    return p.returncode, p.stdout

# ── 部品の型紙: (出力, local, 本体の規則, 引数) —— E は辺の表（i,j,w）、N は点の表（v）、S は値 ──
KINDS = [
    ('sssp', [('d', 'min')], [], ['d[S] <- 0', 'd[j] <- d[i] + w for (i,j,w) in E'], ['E', 'S']),
    ('reach', [('h', 'or')], [], ['h[S] <- true', 'h[j] <- true for (i,j,w) in E if h[i]'], ['E', 'S']),
    ('gap', [('o', 'set')], [('seen', 'or')],
     ['seen[S] <- true', 'seen[j] <- true for (i,j,w) in E if seen[i]',
      'o[] <- {v} for (v) in N if not seen[v]'], ['E', 'N', 'S']),
    ('tot', [('c', 'sum')], [], ['c[] <- w for (i,j,w) in E'], ['E']),
    ('cnt', [('c', 'count')], [], ['c[] <- 1 for (v) in N'], ['N']),
    ('mul', [('m', 'max')], [], ['m[i] <- i * S for (i) in 0 .. S'], ['S']),
    ('fl', [('f', 'flat')], [], ['f[i] <- S + i for (i) in 0 .. 3'], ['S']),
    ('two', [('a', 'max'), ('b', 'max')], [('t', 'max')],
     ['t[v] <- v + S for (v) in N', 'a[v] <- t[v] * 2 for (v) in N', 'b[v] <- a[v] + K for (v) in N if not t[v] < 2'],
     ['N', 'S', 'K']),
    ('none', [], [('z', 'max')], ['z[0] <- 1'], []),
]
TRUE_DEPTH = {'sssp': 1, 'reach': 1, 'gap': 2, 'tot': 1, 'cnt': 1, 'mul': 1, 'fl': 1, 'two': 2, 'none': 1}

def gen():
    prog = []
    tables = {'g1': '(0,1,3), (1,2,2), (0,2,7), (2,3,1)', 'g2': '(0,3,5), (3,1,1)',
              'v1': '(0), (1), (2), (3), (4)', 'v2': '(1), (3)'}
    etabs, ntabs = ['g1', 'g2'], ['v1', 'v2']
    lines = ['# 撒いた部品の本']
    for t, rows in tables.items():
        lines.append(f'table {t} = {rows}')
    comps = []
    ncomp = rng.randint(1, 3)
    for ci in range(ncomp):
        k = rng.choice(KINDS)
        name = rng.choice(['lib', 'go', 'part', 'sssp', 'q', k[0]])
        outs, locs, body, params = k[1], k[2], list(k[3]), list(k[4])
        pnames = {p: rng.choice({'E': ['edges', 'e', 'E'], 'N': ['nodes', 'n', 'N'],
                                 'S': ['src', 's', 'x'], 'K': ['k', 'kk']}[p]) for p in params}
        if len(set(pnames.values())) < len(pnames):
            pnames = {p: p.lower() + str(i) for i, p in enumerate(params)}
        bl = []
        for r in body:
            for p, nm in pnames.items():
                import re
                r = re.sub(r'\b' + p + r'\b', nm, r)
            bl.append(r)
        mut = rng.random()
        if mut < 0.06 and bl:      # 外の場を読む
            bl[-1] += ' if best[0] >= 0'
        elif mut < 0.10 and 'S' in pnames:   # 値の引数を表に
            bl.append(f'{outs[0][0] if outs else "z"}[0] <- 1 for (y) in {pnames["S"]}' if outs else 'z[1] <- 1')
        elif mut < 0.14 and 'S' in pnames:   # 束縛に値の引数
            bl.append(f'{(outs or locs)[0][0]}[0] <- {pnames["S"]} for ({pnames["S"]}) in 0 .. 2')
        elif mut < 0.17:           # 文字列
            bl.append(f'{(outs or locs)[0][0]}[0] <- "a"')
        elif mut < 0.20:           # 知らない場
            bl.append('ghost[0] <- 1')
        elif mut < 0.23:           # 構成子らしい呼び出し
            bl.append(f'{(outs or locs)[0][0]}[0] <- foo(1)')
        elif mut < 0.26 and 'E' in pnames:   # 表の引数を値に
            bl.append(f'{(outs or locs)[0][0]}[0] <- {pnames["E"]}')
        elif mut < 0.28:
            bl.append('print ' + (outs or locs)[0][0])
        elif mut < 0.30:
            bl.append(f'emit "ch" <- 1')
        sig = ''
        r = rng.random()
        if r < 0.5:
            sig = f'  depth {rng.choice([TRUE_DEPTH[k[0]], TRUE_DEPTH[k[0]] + 1, max(1, TRUE_DEPTH[k[0]] - 1), 3])}'
        elif r < 0.6:
            sig = f'  depth {TRUE_DEPTH[k[0]]}  io 0'
        outs_s = (' -> ' + ', '.join(f'{f} : {l}' for f, l in outs)) if outs else ''
        head = f'component {name}({", ".join(pnames[p] for p in params)}){outs_s}{sig}'
        h = rng.random()
        if h < 0.03: head = head.replace('(', ' (', 1)
        elif h < 0.05: head += ' junk'
        elif h < 0.07 and outs: head = head.replace('->', '->>')
        elif h < 0.08: head = head.replace(')', '', 1)
        cl = [head] + [f'  local {f} : {l}' for f, l in locs] + ['  ' + x for x in bl]
        if rng.random() > 0.03: cl.append('end')
        comps.append((name, k, params, pnames, outs, cl))
    # use の文
    uses = []
    prefixes = []
    for ui in range(rng.randint(1, 3)):
        name, k, params, pnames, outs, cl = rng.choice(comps)
        if rng.random() < 0.05: name = 'nothere'
        args = []
        for p in params:
            if p == 'E': a = rng.choice(etabs)
            elif p == 'N': a = rng.choice(ntabs)
            else: a = str(rng.choice([0, 1, 2, 3]))
            if rng.random() < 0.05: a = rng.choice(['g1', '2'])
            args.append(a)
        if rng.random() < 0.04 and args: args = args[:-1]
        if rng.random() < 0.03: args.append('1')
        pf = rng.choice(['a', 'b', 'p1', 'road', 'x_y']) if rng.random() < 0.97 else '_u'
        prefixes.append((pf, outs))
        uses.append(f'use {name}({", ".join(args)}) as {pf}')
    # 並べる: 部品と use の順を混ぜる
    blocks = [c[5] for c in comps]
    items = [('c', b) for b in blocks] + [('u', u) for u in uses]
    rng.shuffle(items)
    if rng.random() < 0.3:
        lines.append('field best : min')
        lines.append('best[0] <- 5')
    for kind, it in items:
        if kind == 'c': lines.extend(it)
        else: lines.append(it)
        if rng.random() < 0.3: lines.append('# 注釈 use x() as y')
    for pf, outs in prefixes:
        for f, l in outs:
            lines.append(f'print {pf}_{f}')
    if rng.random() < 0.3: lines.append('print best')
    if rng.random() < 0.05: lines.append('end')
    return '\n'.join(lines) + '\n'

stats = {'SAME': 0, 'REFUSE-UNOPENED': 0, 'ANSWER-UNOPENED': 0, 'BOTH-REFUSE': 0, 'CONSERVATIVE': 0, 'DANGER': 0, 'LINES': 0}
tmp = tempfile.mkdtemp()
for n in range(N):
    src = gen()
    f = os.path.join(tmp, f'u{n}.lx'); open(f, 'w').write(src)
    o = os.path.join(tmp, f'u{n}.u.lx')
    subprocess.run([UNF, f, o], cwd=ROOT, check=False, capture_output=True)
    got = open(o, encoding='utf-8', errors='replace').read()
    rc0, out0 = run_def(f)
    if got == src:
        stats['ANSWER-UNOPENED' if rc0 == 0 else 'REFUSE-UNOPENED'] += 1
        continue
    # 行: 元の行数ぶんは、元の行が残るか空になる
    ol, ul = src.split('\n'), got.split('\n')
    okl = all(ul[i] == ol[i] or ul[i].strip() == '' for i in range(len(ol) - 1))
    if not okl:
        stats['LINES'] += 1; print('LINES', f)
    rc1, out1 = run_def(o)
    if rc0 == 0 and rc1 == 0:
        if out0 == out1: stats['SAME'] += 1
        else: stats['DANGER'] += 1; print('DANGER (answer)', f)
    elif rc0 != 0 and rc1 != 0: stats['BOTH-REFUSE'] += 1
    elif rc0 == 0: stats['CONSERVATIVE'] += 1; print('CONSERVATIVE', f)
    else: stats['DANGER'] += 1; print('DANGER (refused by definition, answered after unfold)', f)
print(stats, 'tmp', tmp)
