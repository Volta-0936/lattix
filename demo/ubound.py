#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上界 U —— 下界しか持っていなかった処理系に、もう一方を持たせる。

いままで処理系は「いま何が導かれたか」＝下界 L しか計算していなかった。
対になるのは「これ以上どこまで行きうるか」＝上界 U で、
**L = U になった座標が確定した座標**である。

一番安い U は、非負デルタの証明書が licence する **前線の値 B** である。
Dijkstra が pop する値は単調非減少なので、いま pop した値は
まだ確定していない全セルの最終値の下界になる。

これで何が起きるか: min 束への `> k` という非単調な比較が、
**層を消費しなくなる**。証明書はスケジューラを選ぶだけのものではなかった。
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

W = 88
ok = True
src = open(os.path.join(ROOT, 'examples', '18_ubound.lx'), encoding='utf-8').read()

def load():
    p = L.parse(src); L.check(p); d = L.stratify(p); L.io_rounds(p); L.certify(p)
    return p, d

print("=" * W)
print("  上界で層を落とす")
print("=" * W)
base, d0 = load()
s0, _, st0 = L.run(base, out=io.StringIO())
rel, _ = load()
b, a = L.relax(rel)
s1, _, st1 = L.run(rel, out=io.StringIO())

print(f"  緩和なし : 逐次深度 {b}   層 {[[r.target for r in s] for s in base.strata]}")
print(f"  緩和あり : 逐次深度 {a}   層 {[[r.target for r in s] for s in rel.strata]}")
print(f"  使われたスケジューラ: {st1['engines']}  （下界を維持できるのはこれだけ）")
print(f"\n  答え far = {sorted(k for k, v in s1['far'].items() if v)}")
same = s0 == s1
ok &= same and a < b
print(f"  緩和前と完全一致: {'✓' if same else '✗'}")

print("\n" + "-" * W)
print("  発火順序を撹拌しても同じか（下界は順序に依存してはいけない）")
n = 0
for seed in range(40):
    r, _ = load(); L.relax(r)
    s, _, _ = L.run(r, seed=seed, out=io.StringIO())
    n += (s == s0)
ok &= (n == 40)
print(f"  {n}/40 が緩和前と一致  {'✓' if n == 40 else '✗'}")

print("\n" + "-" * W)
print("  一度これで間違えた（記録）")
print("  緩和したのに worklist に落ちていて、答えは *たまたま* 合っていた。")
print("  下界を維持できない実行系では、途中の暫定値で `> k` が偽陽性を出す。")
print("  **上界を使う緩和は、それを維持する義務とセットでしか成立しない。**")
print("=" * W)
sys.exit(0 if ok else 1)
