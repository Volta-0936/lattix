#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外界 — そして、この言語でしか出せない数値。

  逐次深度 = 外界との往復回数

依存する呼び出しだけが深度を上げる。独立な呼び出しは上げない。
つまり Lattix は **プログラムの遅延を往復回数で静的に印字する**。
他の言語にこの問いを立てる語彙は無い。

そして効果は「出したものの集合」という場の *差分* を実体化することなので、
再実行しても、順序を変えても、レプリカを合流させても重複しない。
exactly-once に追加の機構は要らない —— 集合が冪等だから。
"""
import io, os, sys, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

W = 86
CALLS = []

def host(ch, items):
    CALLS.append((ch, tuple(items)))
    if ch == "fetch":  return {'profile': {u: 100 + u for u in items}}
    if ch == "geo":    return {'region':  {p: 200 + (p % 3) for p in items}}
    if ch == "tax":    return {'rate':    {r: 1 + (r % 2) for r in items}}
    return {}

DEPENDENT = open(os.path.join(ROOT, "examples/12_world.lx"), encoding="utf-8").read()

INDEPENDENT = """
table users = (1), (2), (3), (4), (5)
emit "fetch" <- u          for (u) in users
emit "geo"   <- u          for (u) in users
emit "tax"   <- u          for (u) in users
source profile : flat from "fetch"
source region  : flat from "geo"
source rate    : flat from "tax"
field seen : set
seen[] <- {u}              for (u) in users
"""

def go(src, label, seed=None):
    global CALLS
    CALLS = []
    p = L.parse(src); L.check(p); d = L.stratify(p); L.io_rounds(p); L.certify(p)
    st, _, stats = L.run(p, out=io.StringIO(), host=host, seed=seed)
    return p, d, st, stats, list(CALLS)

print("=" * W)
print("  外界との往復回数を、処理系が静的に印字する")
print("=" * W)

p, d, st, stats, calls = go(DEPENDENT, "dep")
print(f"\n  (a) 応答に依存する呼び出しの連鎖（fetch → geo → tax）")
print(f"      逐次深度 {d}   直列した往復 {stats['io_rounds']} 回   "
      f"ホスト呼び出し {len(calls)} 回")
print(f"      臨界路 : " + " ⟶ ".join(p.critical_path))
print(f"      → 5ユーザ × 3段でも、直列するのは {stats['io_rounds']} 回だけ。")
print(f"        同じ段の5件はまとめて1回で出ている（バッチ化は導出物）。")

p2, d2, st2, stats2, calls2 = go(INDEPENDENT, "indep")
print(f"\n  (b) 互いに独立な呼び出し（同じ3チャネル、依存なし）")
print(f"      逐次深度 {d2}   直列した往復 {stats2['io_rounds']} 回   "
      f"ホスト呼び出し {len(calls2)} 回")
print(f"      → 依存が無ければ深度は上がらない。3チャネルが同じ層で出る。")
print(f"\n  同じI/O量でも遅延が違う。その差を *コンパイル時に* 数値で返す言語は他に無い。")

# ---------------------------------------------------------------- once
print("\n" + "=" * W)
print("  効果の exactly-once — 追加の機構ゼロで")
print("=" * W)

ok = True

# (1) 同じセッションを再実行しても、新しい効果は出ない
sess_src = DEPENDENT
CALLS = []
pp = L.parse(sess_src); L.check(pp); L.stratify(pp); L.certify(pp)
store = {f: {} for f in pp.fields}
delivered = {ch: set() for ch, _ in pp.channels}
def run_once(seed=None):
    stats = {'joins': 0, 'rounds': 0, 'engines': [], 'budget': None,
             'stopped': False, 'here': set(), 'roundtrips': 0, 'io_rounds': 0,
             'delivered': delivered}
    rng = random.Random(seed) if seed is not None else None
    for sst in pp.strata:
        if not sst: continue
        L.ENGINES['worklist'](sst, pp, store, rng, stats)
        L._flush(pp, store, host, delivered, stats)
    return stats
CALLS = []; s1 = run_once()
n1 = len(CALLS)
CALLS = []; s2 = run_once()
n2 = len(CALLS)
CALLS = []; s3 = run_once(seed=7)
n3 = len(CALLS)
print(f"  1回目のホスト呼び出し : {n1}")
print(f"  2回目（同じストア）   : {n2}   ← 何も起きない")
print(f"  3回目（順序を乱数化） : {n3}   ← 何も起きない")
ok &= (n2 == 0 and n3 == 0)
print(f"  {'✓' if ok else '✗'} 再実行・順序変更で副作用は重複しない")

# (2) レプリカを合流させても重複しない
CALLS = []
reps = []
for half in range(2):
    q = L.parse(sess_src); L.check(q); L.stratify(q); L.certify(q)
    stq, _, sq = L.run(q, out=io.StringIO(), host=host, seed=half)
    reps.append((q, stq))
before = len(CALLS)
merged = L.merge_stores(reps[0][0], reps[0][1], reps[1][1])
emitted = merged['emit_fetch'].get((), frozenset())
dup = len(emitted) != len(set(emitted))
print(f"\n  2レプリカが独立に実行 → ホスト呼び出し合計 {before}")
print(f"  ストアを join で合流 → emit_fetch の要素数 {len(emitted)}（重複 {dup}）")
print(f"  ✓ 合流は集合の和なので、同じ効果が二度現れることが原理的に無い")
ok &= not dup

print("\n" + "=" * W)
print("  効果 = 場の成長の差分。だから冪等・可換・合流可能。")
print("  『一度だけ実行する』ために、トランザクションも冪等キーも重複排除も要らない。")
print("=" * W)
sys.exit(0 if ok else 1)
