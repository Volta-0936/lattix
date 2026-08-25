#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lattix 検証ハーネス。

  A. 決定性       — 発火順序を完全ランダム化しても結果はビット単位で同一
  B. エンジン非依存 — ナイーブ／ワークリストで同一の答え
  C. 表層構文の無意味性 — 変数名・文順序・行順序を変えても同一の内容アドレス
  D. 最小性       — 導出された層分けが健全（各非単調読みは書き手より後の層）
"""
import io, os, sys, itertools
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix

here = ROOT
TRIALS = 300
FILES = ["01_shortest.lx", "02_strata.lx", "03_time_axis.lx",
         "04_aggregate.lx", "05_pipeline.lx", "08_belnap.lx", "09_upset.lx"]

def load(name):
    src = open(os.path.join(here, "examples", name), encoding="utf-8").read()
    p = lattix.parse(src); lattix.check(p); d = lattix.stratify(p); lattix.io_rounds(p); lattix.certify(p)
    return src, p, d

ok = True
W = 74
print("=" * W)
print(f"  LATTIX v{lattix.VERSION} VERIFICATION")
print("=" * W)

ENGS = ('naive', 'worklist', 'priority', 'adversarial')
print(f"\n[A] 決定性 — {TRIALS} 通りのランダム実行順序 × {len(ENGS)} エンジン")
for name in FILES:
    src, _, _ = load(name)
    digs = set(); n = 0
    for seed in range(TRIALS):
        for eng in ENGS:
            p = lattix.parse(src); lattix.check(p); lattix.stratify(p); lattix.io_rounds(p); lattix.certify(p)
            store, _, _ = lattix.run(p, seed=seed, engine=eng, out=io.StringIO())
            digs.add(lattix.digest(p, store)); n += 1
    good = len(digs) == 1
    ok &= good
    print(f"   {'✓' if good else '✗'} {name:<20} {n:>5} 実行 → "
          f"{len(digs)} 通りの結果   {sorted(digs)[0]}")

print("\n[B] 極性解析による深度削減（答えは不変）")
for name in FILES:
    src = open(os.path.join(here, "examples", name), encoding="utf-8").read()
    ds = {}
    for mode in ('cons', 'poly'):
        try:
            p = lattix.parse(src); lattix.check(p, conservative=(mode == 'cons'))
            ds[mode] = lattix.stratify(p); lattix.io_rounds(p); lattix.certify(p)
            st, _, _ = lattix.run(p, out=io.StringIO())
            ds[mode + 'd'] = lattix.digest(p, st)
        except lattix.LattixError:
            ds[mode] = None; ds[mode + 'd'] = None
    if ds['cons'] is None:
        print(f"   ✓ {name:<20} 深度 v0.2:棄却 → v0.3:{ds['poly']}"
              f"   （Belnap 否定で全域化）")
        continue
    same = ds['consd'] == ds['polyd']
    ok &= same
    arrow = "→" if ds['cons'] != ds['poly'] else "="
    print(f"   {'✓' if same else '✗'} {name:<20} 深度 {ds['cons']} {arrow} {ds['poly']}"
          f"   結果一致: {same}")

print("\n[F] スパン（並列深度）— 証明書の階数の最大値")
for name in FILES:
    src, _, _ = load(name)
    p = lattix.parse(src); lattix.check(p); d = lattix.stratify(p)
    lattix.io_rounds(p); lattix.certify(p)
    st, _, stt = lattix.run(p, out=io.StringIO(), ranks=True, engine='worklist')
    sp = max((r for _k, r in stt['rank'].items()), default=0)
    print(f"   · {name:<20} 層深度 {d}   スパン {sp:>3}   仕事量 {stt['joins']:>6} join")

print("\n[C] 表層構文の無意味性 — 同じ意味／全く違うテキスト")
_, p1, _ = load("05_pipeline.lx")
_, p2, _ = load("06_order_free.lx")
a1 = lattix.canonical(p1)[1]; a2 = lattix.canonical(p2)[1]
good = a1 == a2
ok &= good
print(f"   {'✓' if good else '✗'} 05_pipeline.lx   → {a1}")
print(f"   {'✓' if good else '✗'} 06_order_free.lx → {a2}")
print(f"     （変数名・文の順序・行の順序・可換演算の項順すべて異なる）")

print("\n[D] 成層の健全性 — 全ての非単調読みが書き手より真に後の層にあるか")
for name in FILES:
    _, p, d = load(name)
    writers = {}
    for r in p.rules:
        writers.setdefault(r.target, []).append(r)
    bad = []
    for r in p.rules:
        for f in r.nonmono_reads:
            for w in writers.get(f, ()):
                if w.stratum >= r.stratum:
                    bad.append((r.lineno, f, w.lineno))
        for f in r.mono_reads:
            for w in writers.get(f, ()):
                if w.stratum > r.stratum:
                    bad.append((r.lineno, f, w.lineno))
    ok &= not bad
    print(f"   {'✓' if not bad else '✗'} {name:<20} 深度 {d}, 規則 {len(p.rules)}"
          + ("" if not bad else f"  違反 {bad}"))

print("\n[E] 停止性証明書")
for name in FILES:
    _, p, _ = load(name)
    for f in sorted(p.certificates):
        st, why = p.certificates[f]
        print(f"   {'✓' if st != 'UNPROVEN' else '?'} {name:<20} {f:<20} {st}")

print("\n[G] 領域実行 — 同じ深さの中に順序は無い（v1.7）")
# 領域は半順序である。同じ深さの領域どうしには順序制約が無いのだから、
# その中を撹拌しても答えは変わってはいけない。**言わずに測る。**
import random
REG_TRIALS = 40
for name in FILES:
    src, p0, _ = load(name)
    base, _, _ = lattix.run(p0, out=io.StringIO())
    want = lattix.digest(p0, base)
    digs = set()
    for seed in range(REG_TRIALS):
        p = lattix.parse(src); lattix.check(p); lattix.stratify(p)
        lattix.io_rounds(p); lattix.certify(p)
        st, _, _, _ = lattix.run_regional(p, out=io.StringIO(),
                                          rng=random.Random(seed))
        digs.add(lattix.digest(p, st))
    good = digs == {want}
    ok &= good
    print(f"   {'✓' if good else '✗'} {name:<20} {REG_TRIALS:>5} 通りの領域内順序 → "
          f"{len(digs)} 通りの結果   層ごとの実行と一致: {digs == {want}}")

print("\n" + "=" * W)
print("  すべて通過" if ok else "  失敗あり")
print("=" * W)
sys.exit(0 if ok else 1)
