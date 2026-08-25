#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
証明可能な途中答え — 実行が変わりうる最後の次元「どこまでやったか」。

証明書は二つの条件からできていた。分解するとこうなる:

  (B) 有基性 ⟹ S ⊑ lfp  =  SOUND    「書いてあることはすべて真」
  (A) 安定性 ⟹ lfp ⊑ S  =  COMPLETE 「真であることはすべて書いてある」

予算で打ち切った答えは (A) を失うが (B) は保つ。
つまり **健全だが未完** と *証明できる*。新しい機構は要らない。分解しただけ。

これが効くのは、締切のある計算・探索の途中経過・段階的な精緻化である。
「まだ全部ではないが、書いてあることは信じてよい」を機械が保証する。
"""
import io, os, sys, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L, attest as A

def graph(n, m, seed=17):
    r = random.Random(seed); e = set()
    for i in range(1, n): e.add((r.randrange(i), i, r.randint(1, 30)))
    while len(e) < m:
        a, b = r.randrange(n), r.randrange(n)
        if a != b: e.add((a, b, r.randint(1, 30)))
    return sorted(e)

E = graph(300, 2000)
SRC = ("table edges = " + ", ".join(f"({a},{b},{w})" for a, b, w in E) + "\n"
       "field dist : min\ndist[0] <- 0\n"
       "dist[j] <- dist[i] + w   for (i,j,w) in edges\n")

def solve(budget=None):
    p = L.parse(SRC); L.check(p); L.stratify(p); L.io_rounds(p); L.io_rounds(p); L.certify(p)
    # 証明書が非負を示した層では優先度スケジューラが選ばれる。
    # 各座標が初回ポップで確定するので、階数が後から古びない。
    st, _, stats = L.run(p, out=io.StringIO(), budget=budget, ranks=True,
                         engine='auto')
    store = {'dist': {k: p.fields['dist'].observe(v) for k, v in st['dist'].items()}}
    rank = {'dist': {k: r for (f, k), r in stats['rank'].items() if f == 'dist'}}
    return store, rank, stats

full, frank, fstats = solve()
W = 84
print("=" * W)
print("  証明可能な途中答え — 予算を切って止めても『健全』は証明できる")
print(f"  対象: 最短経路 頂点300 / 辺2000。完全解の join = {fstats['joins']:,}")
print("=" * W)
print(f"  {'予算(join)':>11} {'求まった点':>10} {'確定':>6} {'暫定':>6} {'過小評価':>8} "
      f"{'SOUND':>7} {'COMPLETE':>9}")
print("-" * W)
ok = True
for b in [200, 600, 1500, 3000, None]:
    st, rk, stats = solve(b)
    got = len(st['dist'])
    exact = sum(1 for k, v in st['dist'].items() if full['dist'].get(k) == v)
    under = sum(1 for k, v in st['dist'].items() if v < full['dist'].get(k, 0))
    rep = A.attest(SRC, st, rk)
    ok &= rep.sound and under == 0
    print(f"  {str(b or '無制限'):>11} {got:>10} {exact:>6} {got-exact:>6} {under:>8} "
          f"{'✓' if rep.sound else '✗':>7} {'✓' if rep.complete else '✗':>9}")
print("-" * W)
print("  『確定』は真値と一致した点、『暫定』はまだ緩和途中の点。")
print("  重要なのは **過小評価が常に 0** であること。min 束は下から育つので、")
print("  途中の答えは必ず真の距離以上 —— 存在しない近道を主張することが原理的に無い。")
print("  経路探索・計画・見積りでは、これは『安全側に外す』ことの構造的保証である。")
print("  そして SOUND はその保証が *証明されている* ことを意味する。")
print("=" * W)
sys.exit(0 if ok else 1)
