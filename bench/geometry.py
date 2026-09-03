#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最適化の定義が違う —— 仕事量とスパンの幾何。

逐次言語の最適化は「命令を減らす」ことである。時間軸が一本しかないから。
Lattix には二つの深さがある:

    層深度 (depth)  外界と、非単調な問いのために、何回 *協調* が要るか
    スパン (span)   完全に並列化しても、導出鎖が何段あるか

そして **スパンは証明書の階数そのもの** である。
答えの正しさを証明するために作った数が、そのまま並列時間の *上界* になっていた。
（v1.3 で訂正: スパンは上界であって実測値ではない。実時間はコア数と幾何が決める。）

最適化とは、命令の並べ替えではなく **導出の幾何を変えて鎖を短くすること** である。
熱帯半環（min-plus）の言葉で言えば、一歩の大きさを変えることだ。
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

here = ROOT
TROP = open(os.path.join(here, "lib", "tropical.lx"), encoding="utf-8").read()

def chain(n):
    """直径 n-1 の鎖。最悪の幾何。"""
    return [(i, i + 1) for i in range(n - 1)]

def build(n, comp):
    e = ", ".join(f"({a},{b})" for a, b in chain(n))
    nd = ", ".join(f"({i})" for i in range(n))
    return (TROP + f"\ntable edge = {e}\ntable node = {nd}\n"
            f"use {comp}(edge, node) as x\n")

def measure(n, comp):
    src = build(n, comp)
    p = L.parse(src); L.check(p); d = L.stratify(p); L.io_rounds(p); L.certify(p)
    st, _, stats = L.run(p, out=io.StringIO(), ranks=True, engine='worklist')
    span = max((r for (f, k), r in stats['rank'].items()), default=0)
    cells = len(st['x_r'])
    return d, span, stats['joins'], cells, st['x_r']

W = 84
print("=" * W)
print("  仕事量とスパンの幾何 —— 同じ答え、違う導出の形")
print("  対象: 長さ n の鎖グラフの推移閉包（最悪の直径）")
print("=" * W)
print(f"  {'n':>4} | {'線形 work':>10} {'span':>6} | {'二乗化 work':>12} {'span':>6}"
      f" | {'span 短縮':>9} {'work 増':>8} {'一致':>5}")
print("-" * W)

ok = True
rows = []
for n in (8, 12, 16, 24, 32):
    d1, s1, w1, c1, r1 = measure(n, "reach_linear")
    d2, s2, w2, c2, r2 = measure(n, "reach_double")
    same = (r1 == r2)
    ok &= same
    rows.append((n, s1, s2))
    print(f"  {n:>4} | {w1:>10,} {s1:>6} | {w2:>12,} {s2:>6}"
          f" | {s1/max(s2,1):>8.1f}× {w2/max(w1,1):>7.1f}× {'✓' if same else '✗':>5}")

print("-" * W)
import math
print(f"  線形のスパンは n に比例し、二乗化のスパンは log n に比例する:")
for n, s1, s2 in rows:
    print(f"    n={n:>3}   線形 span {s1:>3} (≈n)    二乗化 span {s2:>3} "
          f"(≈log2 n = {math.log2(n):.1f})")
print("-" * W)
print("  答えは一文字も違わない。変わったのは *歩幅* だけである。")
print("  逐次機械で測れば二乗化は遅い。並列機械では、スパンが実時間の *上界* を決める。")
print("  『速い』の定義が実行形態に依存するのに、逐次言語はその軸を持っていない。")
print("=" * W)
print("  そしてこの二つの数は、どちらも処理系が印字する:")
print("    層深度  = 協調の回数     （CALM 境界、外界との往復）")
print("    スパン  = 並列時間の上界 （証明書の階数の最大値。実測値ではない）")
print("  最適化とは、この二つを下げることであって、命令を減らすことではない。")
print("=" * W)
sys.exit(0 if ok else 1)
