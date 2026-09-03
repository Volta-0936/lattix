#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lattix: 評価器の実測比較。停止性証明書がスケジューラを選ぶ。"""
import os, sys, io, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix

def rand_graph(n, m, seed=1):
    r = random.Random(seed); e = set()
    for i in range(1, n): e.add((r.randrange(i), i, r.randint(1, 40)))
    while len(e) < m:
        a, b = r.randrange(n), r.randrange(n)
        if a != b: e.add((a, b, r.randint(1, 40)))
    return e

def grid(k, seed=2):
    r = random.Random(seed); e = set(); ix = lambda x, y: x * k + y
    for x in range(k):
        for y in range(k):
            if x + 1 < k: e.add((ix(x, y), ix(x + 1, y), r.randint(1, 40)))
            if y + 1 < k: e.add((ix(x, y), ix(x, y + 1), r.randint(1, 40)))
            if x + 1 < k and y + 1 < k: e.add((ix(x + 1, y + 1), ix(x, y), r.randint(1, 40)))
    return e

def source(e):
    rows = ", ".join(f"({a},{b},{w})" for a, b, w in sorted(e))
    return (f"table edges = {rows}\nfield dist : min\n"
            f"dist[0] <- 0\ndist[j] <- dist[i] + w for (i,j,w) in edges\n")

CASES = [("random  n=300",   rand_graph(300, 2400)),
         ("random  n=1000",  rand_graph(1000, 12000)),
         ("grid    40×40",   grid(40)),
         ("grid    70×70",   grid(70))]

W = 84
print("=" * W)
print("  LATTIX ENGINE BENCHMARK — 同一プログラム、同一答え、3つの実行戦略")
print("  『停止性証明書は事実の証明ではなく、スケジューラの選択子である』")
print("=" * W)
print(f"  {'graph':<16} {'|E|':>6} | {'naive':>9} {'worklist':>9} {'priority':>9}"
      f" | {'vs naive':>9} {'agree':>6}")
print("-" * W)
allok = True
for label, e in CASES:
    res = {}
    for eng in ('naive', 'worklist', 'priority'):
        p = lattix.parse(source(e)); lattix.check(p)
        lattix.stratify(p); lattix.io_rounds(p); lattix.certify(p)
        st, _, s = lattix.run(p, engine=eng, out=io.StringIO())
        res[eng] = (s['joins'], lattix.digest(p, st))
    agree = len({d for _, d in res.values()}) == 1
    allok &= agree
    n_, w_, p_ = res['naive'][0], res['worklist'][0], res['priority'][0]
    print(f"  {label:<16} {len(e):>6} | {n_:>9,} {w_:>9,} {p_:>9,}"
          f" | {n_/p_:>8.1f}× {'✓' if agree else '✗':>6}")
print("=" * W)
print("  数値は join 回数（機械非依存の仕事量）。全戦略で結果ハッシュ一致。")
print("  priority は min束かつ再帰デルタ非負が *証明された* 層でのみ選ばれる。")
print("=" * W)
sys.exit(0 if allok else 1)
