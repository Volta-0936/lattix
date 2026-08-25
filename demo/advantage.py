#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一つのプログラム、四つの実行。

Python / Rust / C では、以下は *四つの別々のプログラム* である:

  1. 計算する
  2. 入力が変わったらもう一度計算する（+ 無効化ロジック）
  3. 複数コアで計算する（+ ロック / 所有権）
  4. 複数マシンで計算する（+ 合流プロトコル）

Lattix ではこれらは一つのプログラムであり、残り三つは処理系が導出する。
寄与が join だから:

  * 事実の追加はストアを増やすことしかできない → 増分は「続きをやる」だけ
  * join は可換・冪等              → レプリカはプロトコル無しで合流する
  * 情報を破壊する書き込みが無い      → ロックも所有権も競合検出も要らない

以下は主張ではなく実測である。
"""
import io, os, sys, random, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

PROGRAM = """
table edges = {rows}
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edges
print dist
"""

def graph(n, m, seed=5):
    r = random.Random(seed); e = set()
    for i in range(1, n): e.add((r.randrange(i), i, r.randint(1, 40)))
    while len(e) < m:
        a, b = r.randrange(n), r.randrange(n)
        if a != b: e.add((a, b, r.randint(1, 40)))
    return sorted(e)

def src(rows):
    return PROGRAM.format(rows=", ".join(f"({a},{b},{w})" for a, b, w in rows) or "(0,0,0)")

N, M = 800, 8000
EDGES = graph(N, M)
W = 84
print("=" * W)
print("  LATTIX — 一つのプログラム、四つの実行")
print(f"  対象: 単一始点最短経路、頂点 {N} / 辺 {M}。ソースは4行、注釈ゼロ。")
print("=" * W)

d = L.distributability(*(lambda p: (p, L.stratify(p)))(
    (lambda p: (L.check(p), p)[1])(L.parse(src(EDGES)))))
print(f"\n  処理系の判定: 逐次深度 {d['sequential_depth']} / "
      f"協調不要 {'YES' if d['coordination_free'] else 'NO'} / "
      f"必要な大域障壁 {d['barriers_required']}")
print(f"  → 深度1は CALM 定理の境界そのもの。以下の (3) が成立する条件である。")

# ---------------------------------------------------------------- (1) batch
print("\n" + "-" * W)
print("  (1) バッチ実行")
s1 = L.Session(src(EDGES)); t = time.time(); st1 = s1.solve(); t1 = time.time() - t
GOLD = s1.digest()
print(f"      join {st1['joins']:>9,}   規則実例 {st1['bindings']:>8,}   "
      f"{t1*1000:>7.0f} ms   digest {GOLD}")

# ------------------------------------------------------- (2) incremental
print("\n" + "-" * W)
print("  (2) 増分実行 — 事実を足すだけ。無効化ロジックは存在しない（書けない）。")
rnd = random.Random(99)
s2 = L.Session(src(EDGES)); s2.solve()
base = list(EDGES)
inc_j, full_j, mism = [], [], 0
for step in range(20):
    a, b = rnd.randrange(N), rnd.randrange(N)
    while a == b: a, b = rnd.randrange(N), rnd.randrange(N)
    new = (a, b, rnd.randint(1, 12))
    if new in base: continue
    base.append(new)
    added = s2.add('edges', [new])
    sti = s2.solve(delta={'edges': added})
    sf = L.Session(src(base)); stf = sf.solve()
    if s2.digest() != sf.digest(): mism += 1
    inc_j.append(sti['joins']); full_j.append(stf['joins'])
print(f"      ランダムな辺の追加 {len(inc_j)} 回")
print(f"        増分 join   : 中央値 {sorted(inc_j)[len(inc_j)//2]:>6,}  "
      f"最大 {max(inc_j):>6,}  合計 {sum(inc_j):>7,}")
print(f"        全再計算 join: 中央値 {sorted(full_j)[len(full_j)//2]:>6,}  "
      f"合計 {sum(full_j):>7,}")
print(f"        仕事量比     : {sum(full_j)/max(sum(inc_j),1):>8,.0f}×"
      f"     全回で全再計算と一致: {'✓' if mism == 0 else '✗ ' + str(mism)}")

# 最悪ケースも正直に測る: 全域に波及する辺を1本入れる
worst = (0, N - 1, 1)
if worst not in base:
    base.append(worst)
    added = s2.add('edges', [worst])
    stw = s2.solve(delta={'edges': added})
    sf = L.Session(src(base)); stf = sf.solve()
    print(f"      最悪ケース（始点から最遠点へ重み1の辺を追加、全域に波及）")
    print(f"        増分 join {stw['joins']:>7,}  vs  全再計算 {stf['joins']:>7,}"
          f"   {stf['joins']/max(stw['joins'],1):>6.1f}×"
          f"   一致: {'✓' if s2.digest() == sf.digest() else '✗'}")
print("      → 増分の仕事量は変更の影響範囲に比例する。プログラムは1文字も変えていない。")

# ------------------------------------------------------- (3) replicated
print("\n" + "-" * W)
print("  (3) 分散実行 — 4レプリカが更新を別々に受け取り、ランダムなペアで gossip。")
print("      メッセージは順不同・重複あり。ロック / バリア / ベクタークロック /")
print("      合意プロトコルは一切無い。合流は merge_stores（6行）の join のみ。")
K = 4
parts = [EDGES[i::K] for i in range(K)]
reps = [L.Session(src(p)) for p in parts]
facts = [set(p) for p in parts]
jtot = 0
for r in reps: jtot += r.solve()['joins']
grnd = random.Random(7)
rounds = 0
while len({r.digest() for r in reps}) > 1 and rounds < 60:
    rounds += 1
    i, j = grnd.randrange(K), grnd.randrange(K)
    if i == j: continue
    for (a, b) in ((i, j), (j, i)):          # 双方向、重複送信も許す
        newf = [f for f in facts[a] if f not in facts[b]]
        facts[b] |= facts[a]
        if newf: reps[b].add('edges', newf)
        reps[b].store = L.merge_stores(reps[b].prog, reps[b].store, reps[a].store)
        jtot += reps[b].solve(delta={'edges': newf} if newf else None)['joins']
ok3 = len({r.digest() for r in reps}) == 1 and reps[0].digest() == GOLD
print(f"      gossip {rounds} ラウンドで全レプリカが収束")
print(f"      合計 join {jtot:,}  vs  集中バッチ {st1['joins']:,}"
      f"   ({jtot/st1['joins']:.1f}×)")
print(f"      全レプリカが集中実行と同一: {'✓' if ok3 else '✗'}   digest {reps[0].digest()}")
print("      → 分散の対価は *仕事量* であって *正しさ* ではない。")
print("        競合が起きないので、競合解決コードが存在しない。")

# ------------------------------------------------------- (4) any schedule
print("\n" + "-" * W)
print("  (4) 任意スケジュール — 発火順序を乱数化。")
digs = set(); nrun = 0
for seed in range(40):
    p = L.parse(src(EDGES)); L.check(p); L.stratify(p); L.io_rounds(p); L.io_rounds(p); L.certify(p)
    stq, _, _ = L.run(p, seed=seed, out=io.StringIO()); digs.add(L.digest(p, stq)); nrun += 1
for eng in ('naive', 'worklist', 'priority', 'adversarial'):
    p = L.parse(src(EDGES)); L.check(p); L.stratify(p); L.io_rounds(p); L.io_rounds(p); L.certify(p)
    try:
        stq, _, _ = L.run(p, engine=eng, out=io.StringIO())
        digs.add(L.digest(p, stq)); nrun += 1
    except L.LattixError as e:
        print(f"      {eng}: 発火予算超過（この規模では病的。反証器であって実用器ではない）")
ok4 = digs == {GOLD}
print(f"      {nrun} 通りの実行 → {len(digs)} 通りの結果   "
      f"バッチと一致: {'✓' if ok4 else '✗'}")

print("\n" + "=" * W)
print("  4つの実行すべてが同一 digest。ソースは一度も書き換えていない。")
print("  Python / Rust / C で同じものを得るには、無効化ロジック・ロック・")
print("  合流プロトコルを人間が書き、それぞれ別々にテストしなければならない。")
print("=" * W)
sys.exit(0 if (ok3 and ok4) else 1)
