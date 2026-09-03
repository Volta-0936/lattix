#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""データフロー解析の一式を、独立に書いた参照実装と突き合わせる。

`examples/29_dataflow.lx` は次を **一つの不動点** として出す:
到達可能性 / 定数伝播 / 到達定義 / 使用前未定義 / 生存変数 / 死んだ代入。

教科書はこれらを別々のアルゴリズムとして書く —— 向き（前向き・後ろ向き）、
束、meet、反復順序、kill の扱い。Lattix 側には **一行も書いていない**。
だから参照実装（下）は、そのぜんぶを手で書く必要がある。差はそこに出る。
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

W = 84
class TOPMARK:
    def __repr__(self): return '⊤'
TOPMARK = TOPMARK()

src = open(os.path.join(ROOT, 'examples', '29_dataflow.lx'), encoding='utf-8').read()
p = L.parse(src); L.check(p); depth = L.stratify(p); L.io_rounds(p); L.certify(p)
store, conflicts, stats = L.run(p, out=io.StringIO(), ranks=True)
obs = lambda f: {k: p.fields[f].observe(v) for k, v in store[f].items()}

# ── 参照実装（手書き。向きも順序も kill も自分で書く）────────────────
prog = {r[0]: r[1:] for r in p.tables['prog']}
VARS = [r[0] for r in p.tables['vars']]
N = max(prog)

succ = {i: set() for i in prog}
for i, (op, d, s1, s2, tg) in prog.items():
    if op not in (4, 6) and i < N: succ[i].add(i + 1)
    if op in (4, 5): succ[i].add(tg)

reach, frontier = {0}, [0]
while frontier:
    i = frontier.pop()
    for j in succ[i]:
        if j not in reach: reach.add(j); frontier.append(j)

defs = {i: (d if op in (1, 2, 3) else None) for i, (op, d, s1, s2, tg) in prog.items()}
uses = {}
for i, (op, d, s1, s2, tg) in prog.items():
    u = set()
    if op in (2, 3, 5): u.add(s1)
    if op == 3: u.add(s2)
    uses[i] = u

# 定数伝播（前向き・meet は「違えば ⊤」）
def meet(x, y):
    if x is None: return y
    if y is None: return x
    if x is TOPMARK or y is TOPMARK or x != y: return TOPMARK
    return x
cin = {i: {v: None for v in VARS} for i in prog}
cout = {i: {v: None for v in VARS} for i in prog}
for _ in range(200):
    ni = {i: {v: None for v in VARS} for i in prog}
    for i in prog:
        if i not in reach: continue
        for j in succ[i]:
            for v in VARS: ni[j][v] = meet(ni[j][v], cout[i][v])
    no = {}
    for i, (op, dv, s1, s2, tg) in prog.items():
        d = dict(ni[i])
        if op == 1: d[dv] = tg
        elif op == 2: d[dv] = ni[i][s1]
        elif op == 3:
            x, y = ni[i][s1], ni[i][s2]
            d[dv] = (TOPMARK if TOPMARK in (x, y)
                     else None if x is None or y is None else x + y)
        no[i] = d
    if (ni, no) == (cin, cout): break
    cin, cout = ni, no

# 到達定義（前向き・kill つき）
rd = {i: set() for i in prog}
for _ in range(200):
    nr = {i: set() for i in prog}
    for i in prog:
        outi = {(v, d) for (v, d) in rd[i] if v != defs[i]}
        if defs[i] is not None: outi.add((defs[i], i))
        for j in succ[i]: nr[j] |= outi
    if nr == rd: break
    rd = nr
undef = {(i, v) for i in prog if i in reach for v in uses[i]
         if not any(w == v for (w, _d) in rd[i])}

# 生存変数（後ろ向き）
live = {i: set() for i in prog}
for _ in range(200):
    nl = {i: set(uses[i]) for i in prog}
    for i in prog:
        for j in succ[i]:
            nl[i] |= {v for v in live[j] if v != defs[i]}
    if nl == live: break
    live = nl
liveafter = {i: set().union(*[live[j] for j in succ[i]]) if succ[i] else set()
             for i in prog}
dead = {i for i in prog if i in reach and defs[i] is not None
        and defs[i] not in liveafter[i]}

# ── 突き合わせ ──────────────────────────────────────────────────────
# 原子は表の中では綴りそのものが座標である
g_reach = {k[0] for k, v in obs('reach').items() if v}
g_undef = {(k[0], k[1]) for k, v in obs('undef').items() if v}
g_dead = {k[0] for k, v in obs('dead').items() if v}
g_unreach = {k[0] for k, v in obs('unreach').items() if v}
g_cout = {(k[0], k[1]): (TOPMARK if isinstance(v, L._Top) else v)
          for k, v in obs('cvout').items()}
w_cout = {(i, v): cout[i][v] for i in prog for v in VARS if cout[i][v] is not None}

rows = [("到達可能性", g_reach, reach),
        ("到達不能",   g_unreach, set(prog) - reach),
        ("定数伝播",   g_cout, w_cout),
        ("使用前未定義", g_undef, undef),
        ("死んだ代入", g_dead, dead)]
print("=" * W)
print("  データフロー解析一式 —— 一つの不動点で、手書きの参照実装と一致するか")
print("=" * W)
print(f"  命令 {len(prog)} 本 / 変数 {len(VARS)} 個 / 逐次深度 {depth} / "
      f"join {stats['joins']}")
print("-" * W)
ok = True
for name, got, want in rows:
    same = got == want
    ok &= same
    n = len(want) if not isinstance(want, dict) else len(want)
    print(f"  {name:<14} {n:>3} 件   {'一致' if same else '不一致'}")
    if not same:
        print(f"      lattix={got}\n      参照  ={want}")
print("-" * W)
print(f"  ⊤ に達した座標 {len(conflicts)} 個 —— **これは誤りではなく答えである**")
print("  （定数でない、の意味。曖昧性検出をしたいプログラムは `budget top <= 0` と書く）")
print("  一致" if ok else "  不一致")
print("=" * W)
sys.exit(0 if ok else 1)
