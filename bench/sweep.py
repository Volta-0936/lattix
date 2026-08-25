#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
掃引の順序を「座標」から「依存グラフの位相順序」へ。

v1.4 で座標順の掃引（Fast Sweeping）を入れ、幾何指標で許可した。
だが幾何指標が測っていたのは **「いまの番号付けが位相順序にどれだけ近いか」** だった。
人間の手法（逆ポストオーダ、Cuthill–McKee、空間充填曲線）は全部その近似である。

近似する必要はない。**依存グラフの位相順序は直接計算できる。**

  1. セル依存グラフを作る（読みセル → 書きセル）
  2. SCC に分解する
  3. SCC を位相順に並べて掃引する

DAG 部分は一掃で終わる。反復が要るのは SCC の中だけ。
そして **番号付けに一切依存しない。**
"""
import os, sys, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import native as N

W = 100
r = random.Random(4)

def grid(k):
    e = []; ix = lambda x, y: x * k + y
    for x in range(k):
        for y in range(k):
            if x + 1 < k: e.append((ix(x, y), ix(x + 1, y), r.randint(1, 20)))
            if y + 1 < k: e.append((ix(x, y), ix(x, y + 1), r.randint(1, 20)))
    return e

def randg(n, m):
    e = set()
    for i in range(1, n): e.add((r.randrange(i), i, r.randint(1, 40)))
    while len(e) < m:
        a, b = r.randrange(n), r.randrange(n)
        if a != b: e.add((a, b, r.randint(1, 40)))
    return sorted(e)

def src(E, s0):
    return ("table edges = " + ", ".join(f"({a},{b},{w})" for a, b, w in E) + "\n"
            f"field dist : min\ndist[{s0}] <- 0\n"
            "dist[j] <- dist[i] + w   for (i,j,w) in edges\n")

def vals(o):
    d = {}
    for l in o.splitlines():
        t = l.split()
        if t and t[0] == 'dist': d[int(t[1])] = int(t[3])
    return d

def best(ex, k=3):
    b = None
    for _ in range(k):
        o, m, _ = N.run_native(ex)
        if b is None or m['NATIVE_MS'] < b[1]['NATIVE_MS']: b = (o, m)
    return b

print("=" * W)
print("  掃引の順序 —— 座標順 vs 依存グラフの位相順序")
print("=" * W)

K = 140
E = grid(K); NV = K * K
perm = list(range(NV)); r.shuffle(perm)
SH = [(perm[a], perm[b], w) for a, b, w in E]
RG = randg(NV, 200000)

print(f"  {'形':<22} {'幾何指標':>8} {'DAG度':>7} | {'Dijkstra':>9} |"
      f" {'座標掃引':>9} {'pass':>5} | {'位相掃引':>9} {'pass':>5} | {'一致':>5}")
print("-" * W)
ok = True
rows = []
for nm, ed, s0 in [(f"格子 {K}×{K}", E, 0),
                   ("同じ格子・番号を撹拌", SH, perm[0]),
                   (f"ランダムグラフ n={NV:,}", RG, 0)]:
    S = src(ed, s0)
    a = N.compile_source(S, sweep=False); oa, ma = best(a['exe'])
    b = N.compile_source(S, sweep=True, topo=False); ob, mb = best(b['exe'])
    c = N.compile_source(S, sweep=True, topo=True);  oc, mc = best(c['exe'])
    same = vals(oa) == vals(ob) == vals(oc); ok &= same
    rows.append((nm, a['geometry'], a['dag'], mb, mc))
    print(f"  {nm:<22} {a['geometry']:>8.2f} {a['dag']:>7.2f} | {ma['NATIVE_MS']:>9.2f} |"
          f" {mb['NATIVE_MS']:>9.2f} {int(mb.get('SWEEP_PASSES',0)):>5} |"
          f" {mc['NATIVE_MS']:>9.2f} {int(mc.get('SWEEP_PASSES',0)):>5} |"
          f" {'✓' if same else '✗':>5}")
print("-" * W)
g0, g1 = rows[0], rows[1]
print(f"  番号を撹拌したとき:")
print(f"    幾何指標  {g0[1]:.2f} → {g1[1]:.2f}   **番号付けに依存する**")
print(f"    DAG 度    {g0[2]:.2f} → {g1[2]:.2f}   **依存しない（同じグラフだから）**")
print(f"    座標掃引  {g0[3]['NATIVE_MS']:.2f} → {g1[3]['NATIVE_MS']:.2f} ms "
      f"（{int(g0[3].get('SWEEP_PASSES',0))} → {int(g1[3].get('SWEEP_PASSES',0))} パス）  崩壊する")
print(f"    位相掃引  {g0[4]['NATIVE_MS']:.2f} → {g1[4]['NATIVE_MS']:.2f} ms "
      f"（{int(g0[4].get('SWEEP_PASSES',0))} → {int(g1[4].get('SWEEP_PASSES',0))} パス）  変わらない")
print(f"    → 撹拌格子で {g1[3]['NATIVE_MS']/g1[4]['NATIVE_MS']:.0f} 倍の差。")

print("\n" + "=" * W)
print("  スケジューラの自動選択（DAG 度で決める）")
print("=" * W)
for nm, ed, s0 in [(f"格子 {K}×{K}", E, 0), ("同じ格子・番号を撹拌", SH, perm[0]),
                   (f"ランダムグラフ n={NV:,}", RG, 0)]:
    i = N.compile_source(src(ed, s0)); o, m = best(i['exe'])
    pick = "位相掃引" if i['topo'] else ("座標掃引" if i['sweep'] else "ヒープ(Dijkstra)")
    print(f"  {nm:<24} DAG度 {i['dag']:>5.2f} → {pick:<16} {m['NATIVE_MS']:>8.2f} ms")
print("-" * W)
print("  DAG 度 = 依存グラフのセルのうち、非自明な SCC に属さない割合。")
print("  1.00 なら純粋な DAG → 位相順に一掃で終わる（反復ゼロ）。")
print("  0.00 なら全体が一つの SCC → 掃引では減らせない。ヒープに落とす。")
print()
print("  **幾何指標は引退した。** 番号付けの偶然を測っていたにすぎない。")
print("  近似を測るのをやめて、近似される側を計算した。")
print("=" * W)
print("  四つのスケジューラは、四つの構造に対応している:")
print("    依存グラフが DAG        → 位相順の一掃      （反復ゼロ）")
print("    再帰デルタが非負        → 値順の前線        （Dijkstra）")
print("    座標が特性線に沿う      → 座標順の掃引      （番号付け頼み・保険）")
print("    どれも言えない          → FIFO ワークリスト （安全側）")
print("=" * W)
sys.exit(0 if ok else 1)
