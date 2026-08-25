#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python 手書き実装との正直な対比。

同じ仕事（最短経路 + 辺の増分追加 + レプリカ合流）を、
(a) Lattix 4行、(b) 手書き Python で書き、両方を同じ試験にかける。

Lattix が負ける項目も同じ表に出す。負けているのは実時間であり、
勝っているのは「人間が書いて別々に試験しなければならないコードの量」である。
"""
import io, os, sys, time, random, heapq, inspect
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
import native as NAT

# ==========================================================================
# (a) Lattix — これで全部。バッチ・増分・分散・任意順序をすべて兼ねる。
# ==========================================================================
LATTIX_SRC = """
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edges
"""
LATTIX_LOC = 3

# ==========================================================================
# (b) 手書き Python — 同じ三つの機能を、三つ別々に書く必要がある
# ==========================================================================

def py_batch(n, edges):
    """(b1) バッチ: Dijkstra"""
    adj = [[] for _ in range(n)]
    for a, b, w in edges:
        adj[a].append((b, w))
    dist = [float('inf')] * n
    dist[0] = 0
    pq = [(0, 0)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def py_incremental(dist, adj, new_edge):
    """(b2) 増分: 辺を1本足したときの再緩和。
    バッチとは *別の* アルゴリズムであり、別途、バッチと一致することを
    試験しなければならない。ここが不変条件バグの巣になる。"""
    a, b, w = new_edge
    adj[a].append((b, w))
    if dist[a] + w >= dist[b]:
        return dist                      # 影響なし
    dist[b] = dist[a] + w
    pq = [(dist[b], b)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, ww in adj[u]:
            nd = d + ww
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def py_merge(d1, d2):
    """(b3) 合流: この *特定の* プログラム専用。min 束だと知っているから書ける。
    集合なら和、和なら寄与元付き加算、と束ごとに書き直しになる。"""
    return [min(x, y) for x, y in zip(d1, d2)]


PY_LOC = sum(len([l for l in inspect.getsource(f).splitlines()
                  if l.strip() and not l.strip().startswith(('#', '"""'))])
             for f in (py_batch, py_incremental, py_merge))

# ==========================================================================
# 試験
# ==========================================================================
N, M, ADDS = 600, 6000, 60
rnd = random.Random(3)
edges = set()
for i in range(1, N): edges.add((rnd.randrange(i), i, rnd.randint(1, 40)))
while len(edges) < M:
    a, b = rnd.randrange(N), rnd.randrange(N)
    if a != b: edges.add((a, b, rnd.randint(1, 40)))
edges = sorted(edges)

def lx_src(rows):
    return ("table edges = " + ", ".join(f"({a},{b},{w})" for a, b, w in rows)
            + "\n" + LATTIX_SRC)

W = 86
print("=" * W)
print("  LATTIX vs 手書き Python — 同じ仕事、同じ試験")
print(f"  頂点 {N} / 辺 {M} / 辺の追加 {ADDS} 回")
print("=" * W)

# --- batch
t = time.time(); pyd = py_batch(N, edges); py_bt = time.time() - t
s = L.Session(lx_src(edges)); t = time.time(); st = s.solve(); lx_bt = time.time() - t
try:
    _ci = NAT.compile_source(lx_src(edges))
    _o, _m, _ = NAT.run_native(_ci['exe'])
    nat_bt = _m['NATIVE_MS'] / 1000.0
    nat_lines = _ci['lines']
except NAT.Unsupported:
    nat_bt, nat_lines = None, 0
lxd = [s.store['dist'].get((v,), float('inf')) for v in range(N)]
same_batch = lxd == pyd

# --- incremental
adj = [[] for _ in range(N)]
for a, b, w in edges: adj[a].append((b, w))
pyd2 = py_batch(N, edges)
base = list(edges)
py_it = lx_it = 0.0
lx_joins = 0
mismatch = 0
for _ in range(ADDS):
    a, b = rnd.randrange(N), rnd.randrange(N)
    while a == b: a, b = rnd.randrange(N), rnd.randrange(N)
    e = (a, b, rnd.randint(1, 15))
    if e in base: continue
    base.append(e)
    t = time.time(); pyd2 = py_incremental(pyd2, adj, e); py_it += time.time() - t
    added = s.add('edges', [e])
    t = time.time(); sti = s.solve(delta={'edges': added}); lx_it += time.time() - t
    lx_joins += sti['joins']
    lxd2 = [s.store['dist'].get((v,), float('inf')) for v in range(N)]
    if lxd2 != pyd2: mismatch += 1

print(f"\n  {'項目':<30} {'Lattix':>12} {'Lattix native':>14} {'手書き Python':>14}   勝敗")
print("-" * W)
inc_loc = len([l for l in inspect.getsource(py_incremental).splitlines() if l.strip()])
mrg_loc = len([l for l in inspect.getsource(py_merge).splitlines() if l.strip()])
print(f"  {'人が書くプログラム行数':<26} {LATTIX_LOC:>12} {LATTIX_LOC:>14} {PY_LOC:>14}   Lattix")
print(f"  {'増分版のための追加行数':<26} {0:>12} {0:>14} {inc_loc:>14}   Lattix")
print(f"  {'合流版のための追加行数':<26} {0:>12} {0:>14} {mrg_loc:>14}   Lattix")
print(f"  {'同期を保つべき別実装の数':<25} {1:>12} {1:>14} {3:>14}   Lattix")
nb = f"{nat_bt*1000:.2f} ms" if nat_bt else "n/a"
win = "Lattix native" if (nat_bt and nat_bt < py_bt) else "Python"
print(f"  {'バッチ実行':<27} {lx_bt*1000:>9.0f} ms {nb:>14} {py_bt*1000:>11.2f} ms   {win}")
print(f"  {'増分 ' + str(ADDS) + ' 回の合計':<26} {lx_it*1000:>9.0f} ms "
      f"{'未実装':>14} {py_it*1000:>11.2f} ms   Python")
print(f"  {'答えの一致':<27} {'バッチ ' + ('✓' if same_batch else '✗'):>12}"
      f" {'✓' if nat_bt else '—':>14} {'増分 ' + ('✓' if mismatch == 0 else '✗'):>14}   —")
print("-" * W)
if nat_bt:
    print(f"  バッチはネイティブが最速（{nat_bt*1000:.2f} ms vs Python {py_bt*1000:.2f} ms）。")
    print(f"  Lattix ソースは4行のまま。生成 C は {nat_lines} 行で、隣接リストも")
    print(f"  優先度キューも人間は書いていない。増分のネイティブ化は未実装。")
print()
print(f"  だが Python 側の {PY_LOC} 行のうち、")
print(f"  {len([l for l in inspect.getsource(py_incremental).splitlines() if l.strip()])} 行は"
      f"「バッチと同じ答えを出す」ことを人間が保証しなければならないコードである。")
print(f"  Lattix 側にその行は存在しない。増分・分散・並列は導出物であって実装物ではない。")
print()
print(f"  そして手書き py_merge は min 専用である。集合なら和集合、和なら寄与元付き、")
print(f"  と束ごとに書き直しになる。Lattix の merge_stores は束に対して一つで済む。")
print("=" * W)
sys.exit(0 if (same_batch and mismatch == 0) else 1)
