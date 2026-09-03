#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lattix — 束空間の網羅探索 (structure enumeration, not recall)

これまで min / max / set / flat / fourv / sum を選んだのは「想起」だった。
問題の形を見て、知っている代数構造を思い出していた。想起は既知に閉じる。

ここでは想起をやめる。有限束の空間そのものを n ≦ 7 で同型を除いて全列挙し、
各束について Lattix が必要とする性質を機械的に算出する:

  * 単調な非自明対合の有無      → 「否定が層を消費しない」束かどうか
  * 単調述語（上に閉じた部分集合）の個数 → 「層を消費しないガード」の総数
  * 単調自己写像の個数          → 層を消費しない変換の総数（表現力）
  * 高さ                         → Kleene 反復の停止界

そして「否定が自由な最小の束は何か」を、文献ではなく列挙に答えさせる。
"""
from __future__ import annotations
import os, sys, itertools, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from functools import lru_cache

# ==========================================================================
# 1. 有限順序集合の生成（最大元を一つずつ足していく標準的な帰納）
#    任意の n+1 元順序集合は極大元を持つので、これで全同型類が出る。
# ==========================================================================

def down_closed_subsets(n, up):
    """up[i] = i 以上の元のビットマスク。下に閉じた部分集合を全列挙。"""
    out = []
    for m in range(1 << n):
        ok = True
        for i in range(n):
            if m >> i & 1:
                # i が入るなら i 以下の元も全部入っていなければならない
                for j in range(n):
                    if (up[j] >> i & 1) and not (m >> j & 1):
                        ok = False; break
            if not ok: break
        if ok: out.append(m)
    return out


def canonical(n, up):
    """同型判定用の正準形。まず (下方サイズ, 上方サイズ) で分割して
    置換探索を絞る。n ≦ 7 ならこれで十分速い。"""
    down = [0] * n
    for i in range(n):
        for j in range(n):
            if up[j] >> i & 1: down[i] |= 1 << j
    inv = [(bin(down[i]).count('1'), bin(up[i]).count('1')) for i in range(n)]
    groups = {}
    for i in range(n): groups.setdefault(inv[i], []).append(i)
    keys = sorted(groups)
    best = None
    for perms in itertools.product(*[itertools.permutations(groups[k]) for k in keys]):
        img = [0] * n                      # img[old] = new label
        pos = 0
        for grp in perms:
            for old in grp:
                img[old] = pos; pos += 1
        rel = []
        for i in range(n):
            for j in range(n):
                if up[i] >> j & 1: rel.append((img[i], img[j]))
        key = tuple(sorted(rel))
        if best is None or key < best: best = key
    return best


def gen_posets(maxn):
    """naturally labelled posets, deduplicated by canonical form at each level."""
    levels = {1: {canonical(1, [1]): [1]}}
    for n in range(2, maxn + 1):
        cur = {}
        for up in levels[n - 1].values():
            k = n - 1
            for D in down_closed_subsets(k, up):
                nu = [u for u in up]
                # new element k sits strictly above exactly the ideal D
                for i in range(k):
                    if D >> i & 1: nu[i] |= 1 << k
                nu.append(1 << k)
                c = canonical(n, nu)
                if c not in cur: cur[c] = nu
        levels[n] = cur
    return levels


# ==========================================================================
# 2. 束かどうか（最小元があり、任意の2元に上限の最小元が存在する）
# ==========================================================================

def as_lattice(n, up):
    down = [0] * n
    for i in range(n):
        for j in range(n):
            if up[j] >> i & 1: down[i] |= 1 << j
    bots = [i for i in range(n) if bin(down[i]).count('1') == 1]
    if len(bots) != 1: return None
    join = [[None] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            ub = up[i] & up[j]
            if ub == 0: return None
            cands = [k for k in range(n) if ub >> k & 1]
            least = [k for k in cands if all(up[k] >> c & 1 for c in cands)]
            if len(least) != 1: return None
            join[i][j] = least[0]
    return join, up, down, bots[0]


# ==========================================================================
# 3. Lattix が必要とする性質を機械的に算出
# ==========================================================================

def leq(up, a, b): return bool(up[a] >> b & 1)

def monotone(n, up, f):
    return all(not leq(up, a, b) or leq(up, f[a], f[b])
               for a in range(n) for b in range(n))

def involutions(n, up):
    """単調かつ f∘f = id かつ f ≠ id な写像。これが『無料の否定』。"""
    out = []
    for perm in itertools.permutations(range(n)):
        if any(perm[perm[i]] != i for i in range(n)): continue   # not involutive
        if all(perm[i] == i for i in range(n)): continue          # identity
        if monotone(n, up, perm): out.append(perm)
    return out

def up_sets(n, up):
    """単調述語 = 上に閉じた部分集合。⊥ を含まないものが『⊥で偽』な健全ガード。"""
    tot = strict = 0
    for m in range(1 << n):
        ok = all(not (m >> i & 1) or (m & up[i]) == up[i] for i in range(n))
        if ok:
            tot += 1
            if not (m >> _bot_of(n, up) & 1): strict += 1
    return tot, strict

def _bot_of(n, up):
    for i in range(n):
        if all(up[i] >> j & 1 for j in range(n) if True) or \
           all(leq(up, i, j) for j in range(n)): return i
    return 0

def count_monotone_maps(n, up):
    """単調自己写像の総数（層を消費しない変換の表現力）。後戻り探索。"""
    order = sorted(range(n), key=lambda i: bin(up[i]).count('1'), reverse=True)
    below = {i: [j for j in range(n) if leq(up, j, i) and j != i] for i in range(n)}
    above = {i: [j for j in range(n) if leq(up, i, j) and j != i] for i in range(n)}
    f = {}
    cnt = 0
    def rec(idx):
        nonlocal cnt
        if idx == n:
            cnt += 1; return
        x = order[idx]
        for v in range(n):
            ok = True
            for y in below[x]:
                if y in f and not leq(up, f[y], v): ok = False; break
            if ok:
                for y in above[x]:
                    if y in f and not leq(up, v, f[y]): ok = False; break
            if ok:
                f[x] = v; rec(idx + 1); del f[x]
    rec(0)
    return cnt

def height(n, up):
    @lru_cache(None)
    def h(i):
        return 1 + max([h(j) for j in range(n) if j != i and leq(up, i, j)], default=0)
    b = _bot_of(n, up)
    return h(b)

def is_chain(n, up):
    return all(leq(up, i, j) or leq(up, j, i) for i in range(n) for j in range(n))


NAMES = {
    (1,): "自明",
    (2,): "Bool（2値）",
    (3,): "Kleene 3値 / flat(1値)",
}

def name_of(n, up, invs, chain):
    if n == 1: return "trivial"
    if chain and n == 2: return "Bool — 2値論理"
    if chain and n == 3: return "3-chain — flat(値1個) / Kleene 3値"
    if chain: return f"{n}-chain"
    if n == 4 and len(invs) == 1: return "M2 diamond — ★ Belnap 4値 (1977)"
    return ""


# ==========================================================================
# 4. 実行
# ==========================================================================

MAXN = int(sys.argv[1]) if len(sys.argv) > 1 else 7
W = 92
print("=" * W)
print(f"  LATTIX 束空間の網羅探索 — n ≦ {MAXN} の有限束を同型を除いて全列挙")
print("  想起ではなく列挙。「否定が自由な最小の束は何か」を文献ではなく探索に答えさせる。")
print("=" * W)

levels = gen_posets(MAXN)
zoo = []
for n in range(1, MAXN + 1):
    for up in levels[n].values():
        L = as_lattice(n, up)
        if L is None: continue
        join, up_, down, bot = L
        invs = involutions(n, up)
        tot_us, strict_us = up_sets(n, up)
        zoo.append(dict(n=n, up=list(up), join=join, bot=bot, invs=invs,
                        upsets=tot_us, guards=strict_us,
                        maps=count_monotone_maps(n, up),
                        height=height(n, up), chain=is_chain(n, up)))

print(f"\n  n ごとの束の個数（同型類）: "
      + ", ".join(f"n={n}:{sum(1 for z in zoo if z['n']==n)}"
                  for n in range(1, MAXN + 1)))
print(f"  合計 {len(zoo)} 個の束を発見\n")

print(f"  {'n':>2} {'高さ':>4} {'鎖':>3} {'単調自己写像':>12} {'単調述語':>8} "
      f"{'⊥で偽の述語':>11} {'単調対合':>8}  名前 / 意味")
print("-" * W)
for z in sorted(zoo, key=lambda z: (z['n'], -len(z['invs']), -z['maps'])):
    nm = name_of(z['n'], z['up'], z['invs'], z['chain'])
    star = "★" if z['invs'] else " "
    print(f"  {z['n']:>2} {z['height']:>4} {'鎖' if z['chain'] else '—':>3} "
          f"{z['maps']:>12} {z['upsets']:>8} {z['guards']:>11} "
          f"{len(z['invs']):>8}{star} {nm}")

# ---------------------------------------------------------------- findings
print("\n" + "=" * W)
print("  探索が答えたこと")
print("=" * W)

with_inv = [z for z in zoo if z['invs']]
if with_inv:
    m = min(z['n'] for z in with_inv)
    smallest = [z for z in with_inv if z['n'] == m]
    print(f"\n  Q1. 否定が層を消費しない（= 非自明な単調対合を持つ）最小の束は？")
    print(f"      A. n = {m}、そのような束は {len(smallest)} 個。")
    for z in smallest:
        print(f"         join表={z['join']}  対合={z['invs']}")
        print(f"         → これは 4元ダイヤモンド M2。中央の2元が非比較なので入替が順序を保つ。")
        print(f"         → Belnap (1977) の四値論理そのもの。文献からではなく列挙から出た。")
    print(f"      n < {m} の束（鎖のみ）は非自明な単調対合を持たない:")
    print(f"         鎖の順序自己同型は恒等写像しかないから。否定は必ず層を消費する。")

multi = [z for z in zoo if len(z['invs']) >= 2]
if multi:
    m = min(z['n'] for z in multi)
    print(f"\n  Q2. 独立な『無料の否定』を2つ以上持つ最小の束は？")
    print(f"      A. n = {m}、{sum(1 for z in multi if z['n']==m)} 個。")
    for z in [z for z in multi if z['n'] == m][:2]:
        print(f"         対合 {len(z['invs'])} 個: {z['invs']}")
    print(f"      → Ginsberg の bilattice が2つの否定を持つ理由の、構造的な下界。")
else:
    print(f"\n  Q2. n ≦ {MAXN} には独立な対合を2つ持つ束は存在しない。")

best = max(zoo, key=lambda z: (z['guards'] / max(z['n'], 1), z['maps']))
print(f"\n  Q3. 元あたりの『層を消費しないガード』が最大の束は？")
print(f"      A. n={best['n']}, 高さ={best['height']}, ⊥で偽の単調述語={best['guards']} 個"
      f" ({best['guards']/best['n']:.2f}/元)")
print(f"      → 表現力と高さ（停止界）は独立に選べる。設計の自由度がここにある。")

chains = [z for z in zoo if z['chain']]
print(f"\n  Q4. 現行 Lattix の束は空間のどこにいるか？")
print(f"      min/max/flat/sum/count は全て鎖（{len(chains)} 個の鎖を発見）。")
print(f"      鎖は単調対合を持たないので、否定は必ず層を要求する。")
print(f"      fourv だけが非鎖。つまり我々は {len(zoo)} 個中 {len(chains)+1} 個しか使っていない。")
print(f"      残り {len(zoo)-len(chains)-1} 個は未使用の設計空間である。")

json.dump([{k: v for k, v in z.items() if k != 'up'} for z in zoo],
          open(os.path.join(ROOT, 'zoo.json'), 'w'), ensure_ascii=False, indent=1, default=list)
print(f"\n  完全な結果を zoo.json に出力（機械可読）")
print("=" * W)
