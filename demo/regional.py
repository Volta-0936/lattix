#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
領域バリア —— 大域同期を廃す。

逐次深度は *規則* レベルで計算される。だが協調が本当に要るのは *セル* レベルである。
「層1は層0の完了を待つ」と言うとき、実際に待つ必要があるのは
**そのセルの祖先だけ** であって、層0の全部ではない。

独立な連結成分が k 個あれば、大域バリア1個は k 個の独立した局所バリアに分解する。

解き方は v1.5 と同じ形である —— セル依存グラフを SCC 分解して位相順に処理する。
違いは **層をまたいで** 処理すること。SCC の位相順は「祖先が先」を保証するので、
非単調な読み（そのセルが確定していることの要求）は自動的に満たされる。

そしてこれはストリーミングと同じ機構である。ウォーターマークが時間座標の領域を
閉じるのと、SCC の完了が依存グラフの領域を閉じるのは、同じことをしている。
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

W = 92

def comps(k, per=6):
    """k 個の互いに素な連結成分（各成分は長さ per の鎖）+ 到達しない点"""
    e = []; n = 0
    for _ in range(k):
        for i in range(per - 1): e.append((n + i, n + i + 1))
        n += per
    return e, n

def src(E, n):
    return ("table edge = " + ", ".join(f"({a},{b})" for a, b in E) + "\n"
            "table node = " + ", ".join(f"({i})" for i in range(n)) + "\n"
            "field seen : or\n"
            "seen[i] <- true            for (i,j) in edge\n"
            "seen[j] <- true            for (i,j) in edge if seen[i]\n"
            "field far : or\n"
            "far[v] <- true             for (v) in node if not seen[v]\n")

def load(s):
    p = L.parse(s); L.check(p); d = L.stratify(p); L.io_rounds(p); L.certify(p)
    return p, d

print("=" * W)
print("  規則レベルの深度は、協調を過大に報告している")
print("=" * W)
print(f"  {'成分数':>6} {'頂点':>6} | {'規則深度':>8} {'大域バリア':>10} | {'領域数':>7} "
      f"{'高さ':>5} {'幅':>5} {'大域バリア':>10} | {'答え一致':>9}")
print("-" * W)
ok = True
for k in (1, 2, 4, 8, 16):
    E, n = comps(k)
    S = src(E, n)
    p, d = load(S)
    a, _, sa = L.run(p, out=io.StringIO())
    p2, _ = load(S)
    b, sb, fin, ncells = L.run_regional(p2, out=io.StringIO())
    same = all(p.fields[f].observe(a[f].get(kk)) == p2.fields[f].observe(b[f].get(kk))
               for f in a for kk in set(a[f]) | set(b[f]))
    ok &= same
    print(f"  {k:>6} {n:>6} | {d:>8} {1:>10} | {sb['ncomp']:>7} "
          f"{sb['height']:>5} {sb['width']:>5} {sb['global_barriers']:>10} | "
          f"{'✓' if same else '✗':>9}")
print("-" * W)
print("  規則レベルは「大域バリアが1つ要る」と言う。セルレベルの真実は")
print("  「独立な局所バリアが成分数ぶん要る」であって、**大域バリアは一度も要らない**。")
print("  領域は *半順序* である（v1.7 で直した）。順序があるのは高さぶんだけで、")
print("  幅は同時に走れる領域の数である。成分を増やしても高さは伸びない。")

# ---- 領域ごとの完全性 ---------------------------------------------------
print("\n" + "=" * W)
print("  領域ごとの完全性 —— 途中で「この部分はもう最終です」と言える")
print("=" * W)
K = 16
E, n = comps(K)
S = src(E, n)
p, d = load(S)
full, _, _ = L.run(p, out=io.StringIO())
p2, _ = load(S)
store, st, fin, ncells = L.run_regional(p2, out=io.StringIO())
R = st['height']
print(f"  成分 {K} 個 / 頂点 {n} / セル {ncells} / 領域 {st['ncomp']} / 高さ {R}")
print(f"\n  {'処理した深さ':>12} {'確定したセル':>12} {'そのうち最終値':>14} {'完全性':>8}")
print("-" * W)
for frac in (0.125, 0.25, 0.5, 0.75, 1.0):
    upto = max(1, int(R * frac))
    done = [c for c, r in fin.items() if r < upto]
    exact = sum(1 for (f, kk) in done
                if p.fields[f].observe(full[f].get(kk)) ==
                   p2.fields[f].observe(store[f].get(kk)))
    good = (exact == len(done))
    ok &= good
    print(f"  {upto:>7}/{R:<4} {len(done):>12} {exact:>14} {'✓ 完全' if good else '✗':>8}")
print("-" * W)
print("  **深さ r まで処理した時点で、そこまでのセルは既に最終値である。**")
print("  v1.7 でこれは実測ではなく **証明** になった → demo/certified.py")
print("  これは『途中答え』ではない。その領域については COMPLETE と言える。")
print("  v0.8 の SOUND/COMPLETE は大域の話だった。ここでは *領域ごと* に言える。")

print("\n" + "=" * W)
print("  正直に: 対価は仕事量である")
print("=" * W)
E, n = comps(16); S = src(E, n)
p, _ = load(S); _, _, sa = L.run(p, out=io.StringIO())
p2, _ = load(S); _, sb, _, _ = L.run_regional(p2, out=io.StringIO())
print(f"  層ごとの実行   join {sa['joins']:>6}   大域バリア 1")
print(f"  領域ごとの実行 join {sb['joins']:>6}   大域バリア 0   （{sb['joins']/sa['joins']:.1f}×）")
print(f"  領域ごとに『変化なし』を確認するパスが要るぶん増える。")
print(f"  1コアで速くしたいなら層ごとでよい。**分散・ストリーミングでは領域ごとが要る。**")
print("=" * W)
sys.exit(0 if ok else 1)
