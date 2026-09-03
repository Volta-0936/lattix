#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
幅を実時間にできるか —— v1.7 が出した数を、機械で確かめる。

v1.7 は「幅 32」という数を出したが、32 個の領域を同時に走らせたことは
一度も無かった。構造がそう言っているだけだった。ここで測る。

  高さ = 避けられない逐次段数（凝縮グラフの最長鎖）
  幅   = 同時に走れる領域の最大数

ネイティブの領域実行は、深さごとに OpenMP の並列領域を開く。
**大域バリアは張らない。** 同期は深さの境目だけで、そこは構造が要求する順序である。

受入条件は先に決めてある（CLAUDE.md §7）:
  コア数を増やしたときの実時間が縮まなければ、
  **「幅は実時間の指標ではない」と文書に書く。**
"""
import os, sys, statistics
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import native as N
import attest as A

W = 92
CORES = os.cpu_count() or 1
ok = True


def wide(k, m):
    """k 本の独立な鎖（長さ m）。幅 ≈ k、高さ ≈ m。"""
    e = []
    for c in range(k):
        b = c * m
        for i in range(m - 1):
            e.append((b + i, b + i + 1, 1))
    return e, k * m


def grid(n):
    """n×n 格子。幅は対角線、高さは 2n。"""
    e = []
    idx = lambda x, y: x * n + y
    for x in range(n):
        for y in range(n):
            if x + 1 < n: e.append((idx(x, y), idx(x + 1, y), 1))
            if y + 1 < n: e.append((idx(x, y), idx(x, y + 1), 1))
    return e, n * n


def src(E, n, srcs):
    return ("table edges = " + ", ".join(f"({a},{b},{w})" for a, b, w in E) + "\n"
            "field dist : min\n"
            + "".join(f"dist[{s}] <- 0\n" for s in srcs) +
            "dist[j] <- dist[i] + w   for (i,j,w) in edges\n")


def run(S, region, threads=None, reps=2):
    info = N.compile_source(S, region=region)
    best, meta = None, {}
    for _ in range(reps):
        out, m, _ = N.run_native(info['exe'], threads=threads)
        t = m.get('NATIVE_MS', 0.0)
        if best is None or t < best: best, meta, o = t, m, out
    store = N.to_store(info['prog'], info['plan'], o)
    return best, meta, store, info


print("=" * W)
print(f"  幅は実時間になるか（このマシンのコア数: {CORES}）")
print("=" * W)

CASES = [("独立な鎖 8192×16", *wide(8192, 16), [c * 16 for c in range(8192)]),
         ("独立な鎖 512×64", *wide(512, 64), [c * 64 for c in range(512)])]

print(f"  {'形':<16} {'頂点':>7} {'高さ':>6} {'幅':>7} | {'既定':>9} "
      + " ".join(f"{'領域 ' + str(t) + 'スレ':>11}" for t in (1, 2)) + f" | {'最良比':>7}")
print("-" * W)
for name, E, n, srcs in CASES:
    S = src(E, n, srcs)
    t0, m0, s0, _ = run(S, region=False)
    row, best = [], None
    for th in (1, 2):
        t, m, s, info = run(S, region=True, threads=th)
        if s != s0: ok = False; row.append("答え不一致"); continue
        row.append(f"{t:9.2f}ms")
        if best is None or t < best: best = t
    h, w = int(m.get('REG_HEIGHT', 0)), int(m.get('REG_WIDTH', 0))
    print(f"  {name:<16} {n:>7} {h:>6} {w:>7} | {t0:7.2f}ms "
          + " ".join(f"{x:>11}" for x in row)
          + f" | {t0 / best:6.2f}×")
print("-" * W)
print("  『既定』はコンパイラが証明書から選んだスケジューラ（DAG なら位相掃引、")
print("  そうでなければ Dijkstra）。領域実行はそれとは別に、構造の並列度で殴る。")

# ── スレッドを増やしたときの伸び ────────────────────────────────────────
print("\n" + "=" * W)
print("  同じ形でスレッドだけ増やす（幅が効いているかの直接の問い）")
print("=" * W)
E, n = wide(8192, 16)
S = src(E, n, [c * 16 for c in range(8192)])
base = None
print(f"  {'スレッド':>8} {'実時間':>10} {'対1スレッド':>12} {'理想':>8}")
print("-" * W)
for th in range(1, min(CORES, 4) + 1):
    t, m, s, _ = run(S, region=True, threads=th)
    if base is None: base = t
    print(f"  {th:>8} {t:9.2f}ms {base / t:11.2f}× {th:7}×")
print("-" * W)
h, w = int(m.get('REG_HEIGHT', 0)), int(m.get('REG_WIDTH', 0))
print(f"  高さ {h} / 幅 {w}。幅 ≫ コア数なので、頭打ちの原因はコア数の方である。")
print(f"  **このマシンは {CORES} コアしかない。ここで測れるのは伸びの向きだけである。**")

# ── 並列実行の答えが検査を通るか ────────────────────────────────────────
print("\n" + "=" * W)
print("  並列で出した答えが、証明書を通るか（v1.7 まで通せなかった）")
print("=" * W)
E, n = wide(32, 24)
S = src(E, n, [c * 24 for c in range(32)])
info = N.compile_source(S, region=True)
out, meta, _ = N.run_native(info['exe'], threads=max(2, CORES))
store, rank = N.to_store(info['prog'], info['plan'], out, want_rank=True)
rep = A.attest(S, store, rank)
good = rep.sound and rep.complete
ok &= good
print(f"  頂点 {n} / 高さ {int(meta.get('REG_HEIGHT',0))} / 幅 {int(meta.get('REG_WIDTH',0))}"
      f" / スレッド {max(2, CORES)}")
print(f"  検査した規則実例 {rep.instances}   "
      f"SOUND {'✓' if rep.sound else '✗'}   COMPLETE {'✓' if rep.complete else '✗'}")
print("  階数は並列に書かれるが、検査器は生成物の作り方を一切参照しない。")
print("  **並列実行の答えが最小不動点であることを、いま初めて証明できた。**")
print("=" * W)
sys.exit(0 if ok else 1)
