#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
増分を **ネイティブで**。追加のデータファイルを食わせるだけ。

  ./prog base.lxd            答えを出す
  ./prog base.lxd add.lxd    続きをやる（無効化ロジックは一行も無い）

事実の追加はストアを増やすことしかできないので、**増分は「続きをやる」だけ**である。
新しい行だけを撃ち、あとは前線が運ぶ。C にこの変換は書けない ——
「撃ち直しても答えは同じ」は join の冪等性から来る意味の性質だからである。
"""
import os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import runtime as R

W = 84
PROG = ("table edge = (0,1)\n"
        "field reach : or\n"
        "reach[0] <- true\n"
        "reach[j] <- true   for (i,j) in edge if reach[i]\n"
        "print reach\n")

def write(path, rows):
    with open(path, "w") as f:
        f.write(f"edge {len(rows)} 2\n")
        for a, b in rows: f.write(f"{a} {b}\n")

info = R.build(PROG, semi=True)
d = info['dir']
random.seed(3)
n, m = 30000, 150000
E = [(random.randrange(n), random.randrange(n)) for _ in range(m)]
add = [(random.randrange(n), random.randrange(n)) for _ in range(5)]
write(os.path.join(d, "b.lxd"), E)
write(os.path.join(d, "a.lxd"), add)
write(os.path.join(d, "f.lxd"), E + add)

st, meta = R.run(info['exe'], os.path.join(d, "b.lxd"), os.path.join(d, "a.lxd"))
st2, meta2 = R.run(info['exe'], os.path.join(d, "f.lxd"))

print("=" * W)
print(f"  到達可能性 / 頂点 {n} / 辺 {m} → 5 辺を追加")
print("=" * W)
print(f"  {'':<18}{'実時間':>12}{'join':>12}")
print("-" * W)
print(f"  {'バッチ':<18}{meta['NATIVE_MS']:>10.2f}ms{meta['JOINS']:>12.0f}")
print(f"  {'増分（5辺）':<18}{meta['DELTA_MS']:>10.2f}ms{meta['DELTA_JOINS']:>12.0f}")
print(f"  {'一から解き直し':<18}{meta2['NATIVE_MS']:>10.2f}ms{meta2['JOINS']:>12.0f}")
print("-" * W)
same = st == st2
ratio = meta2['JOINS'] / max(meta['DELTA_JOINS'], 1)
print(f"  答え一致: {'✓' if same else '✗'}    仕事量 {ratio:,.0f}× 削減")
print()
print("  無効化ロジックは書いていない。**書けないから書いていない** ——")
print("  情報を壊す書き込みが言語に無いので、無効にすべきものが存在しない。")
print("  正直に: 増分の実時間はファイル読み込みが支配していて、join の削減ほどは縮まない。")
print("  そして **削除（撤回）はまだできない**。追加のみである。")
print("=" * W)
sys.exit(0 if (same and ratio > 100) else 1)
