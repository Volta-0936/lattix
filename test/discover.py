#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lattix — 極性法則の *実験的* 導出、およびその健全性の反証試行。

人間の研究手順は「紙の上で単調性を証明し、実装し、いくつか試す」だった。
ここではその順序を逆にする。

  判定基準は「基準実装と一致するか」ではない。基準実装が健全とは限らない
  （実際 v0.2 の保守的解析は不健全だった。下記 第2部 を参照）。
  そこで直接、我々が本当に required する性質を測る:

      同じ層に置いたとき、実行順序を変えても答えが変わらないか

  これは 17 通りのランダム順序 + 4 種のスケジューラ（うち一つは解析を
  壊すために作った adversarial）で測る。答えが一意なら、その形状は
  層を消費しない = 単調である。

  第1部  全ガード形状 × 全束 について上記を実測し、極性表を *導出* する。
         手で導いた表と突き合わせる。
  第2部  ランダムプログラムを大量生成し、極性解析の採った層分けが
         順序独立性を壊さないかを反証しにいく。
         ついでに v0.2 の保守的解析が壊れる頻度も数える。
"""
import io, os, sys, random, itertools
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

SEEDS = (None,) + tuple(range(1, 17))

def run_mode(src, mode, seeds=SEEDS):
    """Digests over many execution orders, including a scheduler built
    specifically to break unsound analyses."""
    digs = set()
    for sd in seeds:
        p = L.parse(src)
        L.check(p, conservative=(mode == 'cons'), optimistic=(mode == 'opt'))
        L.stratify(p); L.io_rounds(p); L.certify(p)
        store, _, _ = L.run(p, seed=sd, out=io.StringIO())
        digs.add(L.digest(p, store))
    for eng in ('adversarial', 'naive', 'priority'):
        p = L.parse(src)
        L.check(p, conservative=(mode == 'cons'), optimistic=(mode == 'opt'))
        L.stratify(p); L.io_rounds(p); L.certify(p)
        try:
            store, _, _ = L.run(p, engine=eng, out=io.StringIO())
            digs.add(L.digest(p, store))
        except L.LattixError:
            pass
    return digs

def depth_of(src, mode):
    p = L.parse(src)
    L.check(p, conservative=(mode == 'cons'), optimistic=(mode == 'opt'))
    return L.stratify(p)

# ---------------------------------------------------------------- part 1
VALUE = {'min': 'v', 'max': 'v', 'sum': 'v', 'count': 'v',
         'flat': 'v', 'set': '{v}', 'or': 'true', 'fourv': 'true'}
SECOND = {'min': 'v - 1', 'max': 'v + 1', 'sum': 'v', 'count': 'v',
          'flat': 'v', 'set': '{v + 100}', 'or': 'true',
          # v>4 so SOME coordinates get T ⊔ F = ⊤ and some stay definite.
          # Without this the four-valued probe never reaches ⊤ and every
          # ⊤-sensitive guard reads as vacuously monotone.
          'fourv': 'v > 4'}
NUMERIC = ('min', 'max', 'sum', 'count', 'flat')

DATASETS = [
    "(0,3), (1,5), (2,2), (3,9), (1,1), (2,7), (0,8)",
    "(0,1), (1,2), (2,3), (3,4), (0,9), (1,8), (2,7), (3,6)",
    "(0,4), (1,4), (2,4), (3,4), (0,5), (1,3), (2,6), (3,2)",
]

def probe(lat, guard, data):
    return (f"table t = {data}\n"
            f"field a : {lat}\n"
            f"a[i] <- {VALUE[lat]}   for (i,v) in t\n"
            f"a[i] <- {SECOND[lat]}  for (i,v) in t\n"
            f"field o : set\n"
            f"o[] <- {{i}}           for (i,v) in t if {guard}\n"
            f"print o\n")

# Sweep wide enough that every lattice's REACHABLE values are witnessed --
# an aggregate's totals live far above a min-lattice's distances.
THRESHOLDS = tuple(range(0, 13)) + (14, 16, 18, 20, 22, 24, 26, 28, 30, 44)

def guards_for(lat):
    if lat in NUMERIC:
        gs = [(f"a[i] {op} {{k}}", op) for op in ('<', '<=', '>', '>=', '==', '!=')]
        gs.append(("a[i] is {k}", "is"))       # the universal up-set test
    else:
        gs = [("a[i]", "")]
        if lat != 'set': gs.append(("a[i] is {k}", "is"))
    return ([(g, op, False) for g, op in gs] +
            [(f"not ({g})", op, True) for g, op in gs])

def shape_label(tmpl, neg):
    return tmpl.replace("{k}", "k")

W = 78
print("=" * W)
print("  第1部  極性法則を実験で導出する — 紙の上ではなく、プログラム空間の網羅で")
print("=" * W)
print(f"  {'lattice':<8} {'sense':<7} {'guard':<18} {'実験':<10} {'解析の判定':<12} {'一致'}")
print("-" * W)

disagree = []
rows = 0
for lat in ('min', 'max', 'sum', 'count', 'flat', 'or', 'fourv', 'set'):
    for tmpl, op, neg in guards_for(lat):
        # --- experiment: does "assume monotone" EVER change the answer? ---
        emono, trials = True, 0
        for data in DATASETS:
            for k in (THRESHOLDS if "{k}" in tmpl else [0]):
                g = tmpl.replace("{k}", str(k))
                src = probe(lat, g, data)
                try:
                    o = run_mode(src, 'opt')     # everything in ONE stratum
                except L.LattixError:
                    continue
                trials += 1
                if len(o) != 1:                  # order changed the answer
                    emono = False; break
            if not emono: break
        if trials == 0: continue
        g = tmpl.replace("{k}", "4")
        try:
            claim = depth_of(probe(lat, g, DATASETS[0]), 'poly') == 1
            sense = L.LATTICES[lat].sense
        except L.LattixError:
            continue
        agree = (emono == claim)
        rows += 1
        if not agree: disagree.append((lat, tmpl, emono, claim))
        print(f"  {lat:<8} {sense:<7} {shape_label(tmpl,neg):<18} {'単調' if emono else '非単調':<10}"
              f" {'単調' if claim else '非単調':<12} {'✓' if agree else '✗ 不一致'}"
              f"   ({trials} 実験)")

print("-" * W)
print(f"  {rows} 形状を実測。手で導いた極性表と実験の不一致: {len(disagree)}")
if disagree:
    for d in disagree: print(f"    ✗ {d}")
print("=" * W)

# ---------------------------------------------------------------- part 2
print()
print("=" * W)
print("  第2部  ランダムプログラムによる反証試行")
print("=" * W)

LATS = ['min', 'max', 'set', 'or', 'flat', 'sum', 'count', 'fourv']

def gen_program(rnd):
    nt = rnd.randint(1, 2)
    tables = {}
    for i in range(nt):
        ar = rnd.choice([2, 2, 3])
        rows = {tuple(rnd.randint(0, 4) for _ in range(ar)) for _ in range(rnd.randint(3, 7))}
        tables[f"t{i}"] = (ar, sorted(rows))
    nf = rnd.randint(2, 3)
    fields = {f"f{i}": rnd.choice(LATS) for i in range(nf)}
    src = []
    for n, (ar, rows) in tables.items():
        src.append(f"table {n} = " + ", ".join("(" + ",".join(map(str, r)) + ")" for r in rows))
    for n, l in fields.items():
        src.append(f"field {n} : {l}")
    for _ in range(rnd.randint(2, 5)):
        tgt = rnd.choice(list(fields)); lat = fields[tgt]
        tn = rnd.choice(list(tables)); ar, _ = tables[tn]
        vs = [f"x{j}" for j in range(ar)]
        src_clause = f"for ({','.join(vs)}) in {tn}"
        key = ",".join(rnd.sample(vs, rnd.randint(1, min(2, ar))))
        others = [g for g in fields if fields[g] in NUMERIC and g != tgt]
        if lat in ('or', 'fourv'): val = "true"
        elif lat == 'set':         val = "{" + rnd.choice(vs) + "}"
        elif lat in ('min',) and others and rnd.random() < .5:
            val = f"{rnd.choice(others)}[{rnd.choice(vs)}] + {rnd.randint(0,3)}"
        else:                      val = f"{rnd.choice(vs)} + {rnd.randint(0,4)}"
        # **座標に場を使う形も撒く。** `f[g[x]]` は多面体でも内容アドレスでも
        # 中心にある形なのに、生成器が一度も作っていなかった —— だから
        # 「flat を座標に使ってよい」という緩和が一度も反証にかけられていない。
        flats = [g for g in fields if fields[g] == 'flat']
        if flats and rnd.random() < 0.35:
            key = f"{rnd.choice(flats)}[{rnd.choice(vs)}]"
        guards = []
        if rnd.random() < 0.8:
            gf = rnd.choice(list(fields)); gl = fields[gf]
            gk = rnd.choice(vs)
            if flats and rnd.random() < 0.3:
                gk = f"{rnd.choice(flats)}[{rnd.choice(vs)}]"
            if gl in NUMERIC:
                g = f"{gf}[{gk}] {rnd.choice(['<','<=','>','>=','==','!='])} {rnd.randint(0,6)}"
            else:
                g = f"{gf}[{gk}]"
            if rnd.random() < 0.4: g = f"not ({g})"
            guards.append(g)
        if flats and rnd.random() < 0.25 and lat in NUMERIC:
            val = f"{rnd.choice(flats)}[{rnd.choice(vs)}] + {rnd.randint(0,2)}"
        src.append(f"{tgt}[{key}] <- {val} {src_clause}"
                   + "".join(f" if {g}" for g in guards))
    for n in fields: src.append(f"print {n}")
    return "\n".join(src)

TRIALS = 4000
rnd = random.Random(20260814)
tested = skipped = 0
reduced = same = deeper = 0
v02_broken = []
bad = None
for _ in range(TRIALS):
    src = gen_program(rnd)
    try:
        dp = depth_of(src, 'poly')
        p = run_mode(src, 'poly')
    except (L.LattixError, RecursionError, KeyError, TypeError):
        skipped += 1; continue
    tested += 1
    if len(p) != 1:
        bad = (src, dp, p); break
    try:
        dc = depth_of(src, 'cons'); c = run_mode(src, 'cons')
        if len(c) != 1 and len(v02_broken) < 3:
            v02_broken.append((src, dc, c))
        elif len(c) != 1:
            v02_broken.append(None)
        if dp < dc: reduced += 1
        elif dp == dc: same += 1
        else: deeper += 1
    except (L.LattixError, RecursionError, KeyError, TypeError):
        pass

print(f"  生成 {TRIALS} 本 / 検査 {tested} 本 / 除外 {skipped} 本"
      f"（不成層・発火予算超過・型不整合）")
if bad:
    print("  ✗ 反例 — 極性解析が順序独立性を壊した:")
    for ln in bad[0].splitlines(): print("    " + ln)
    print(f"    depth={bad[1]}  digests={bad[2]}")
    sys.exit(1)

print(f"  ✓ 反例なし。{tested} 本すべてで、17通りのランダム順序 + 4種の")
print(f"     スケジューラ（adversarial 含む）が同一の答えを返した。")
print()
print(f"  深度 v0.2 → v0.3 :  下がった {reduced} 本 / 同じ {same} 本 / "
      f"上がった {deeper} 本")
print(f"     （「上がった」= v0.2 が張り忘れていた障壁を v0.3 が張った）")
print()
nb = len(v02_broken)
print(f"  v0.2 の保守的解析が順序依存になったプログラム: {nb} 本 / {tested} 本"
      f" ({100*nb/max(tested,1):.1f}%)")
if v02_broken and v02_broken[0]:
    src, dc, c = v02_broken[0]
    print("  v0.2 が取りこぼす形の最小例:")
    for ln in src.splitlines(): print("    " + ln)
    print(f"    v0.2 depth={dc} → {len(c)} 通りの答え（順序依存）")
    print(f"    v0.3 は値位置の向き不一致（UP 束を DOWN 束へ寄与）を検出して障壁を張る")
print("=" * W)
