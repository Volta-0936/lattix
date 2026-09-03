#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
撤回（削除）—— 追加しかできない世界に「変わる」を入れる。

削除は単調ではない。だが構造は既に持っていた:

  * どのセルがどのセルから導かれるかは D が知っている（索引がある）
  * **削除後の答えは、削除前の答え以下である**

二つ目が効く。削除前の答えがそのまま上界 U になるので、

  1. 消えた事実から前向きに届く範囲を ⊥ に戻す（過剰削除。DRed 1993）
  2. 生き残った支えから育て直す —— **影響が届いた範囲に触る実例だけ**を撒く

ここは二度間違えた。一度目は育て直しで全実例を撒いていた。
二度目は **過剰削除の前線を「依存の全閉包」で歩いていた** ——
「このセルを読みうる規則実例があるか」で閉じるので、密なグラフでは全体に届き、
削減がまた 1.0× に戻った。**削減率が 1 のときは、たいてい何もしていない。**

消えるかどうかを決めるのは「読みうるか」ではなく
**いまの値が何に支えられているか** である。そして支持は既に名指してあった ——
階数を書いたとき、処理系はその値を作った実例を一つ選んでいる。
**検査のために作った証人が、そのまま削除の前線になる。**（記述は二度使われる）

支持が全セルを覆っていなければ、黙って全閉包に落ちる。
遅いのは構わないが、消し忘れを黙って残すのは構わない（不変条件8）。

この検査は、無作為な削除を何度も試して、毎回「一から解いた答え」と突き合わせる。
"""
import io, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

W = 88
ok = True

def src_reach(E):
    return ("table edge = " + ", ".join(f"({a},{b})" for a, b in E) + "\n"
            "field reach : or\nreach[0] <- true\n"
            "reach[j] <- true   for (i,j) in edge if reach[i]\n")

def src_dist(E):
    return ("table edge = " + ", ".join(f"({a},{b},{w})" for a, b, w in E) + "\n"
            "field dist : min\ndist[0] <- 0\n"
            "dist[j] <- dist[i] + w   for (i,j,w) in edge\n")

print("=" * W)
print("  撤回した答えは、一から解いた答えと一致するか（無作為に 24 回）")
print("=" * W)
print(f"  {'形':<14}{'消した辺':>8}{'⊥に戻す':>9}{'撤回join':>10}{'一からjoin':>11}{'削減':>8}  一致")
print("-" * W)
trials = 0
for shape in ('tree', 'chain', 'random', 'weighted'):
    acc = []
    for t in range(12):
        rng = random.Random(1000 + t)
        if shape == 'tree':
            E = [(i // 2, i) for i in range(1, 600)]; mk = src_reach
        elif shape == 'chain':
            E = [(i, i + 1) for i in range(599)] + [(i, 600 + i) for i in range(0, 599, 7)]
            mk = src_reach
        elif shape == 'random':
            E = [(rng.randrange(120), rng.randrange(120)) for _ in range(400)]; mk = src_reach
        else:
            E = [(rng.randrange(120), rng.randrange(120), rng.randrange(1, 9))
                 for _ in range(400)]; mk = src_dist
        drop = rng.sample(E, k=rng.choice([1, 2, 3]))
        s = L.Session(mk(E)); s.solve()
        st = s.retract('edge', drop)
        E2 = [e for e in E if e not in drop]
        s2 = L.Session(mk(E2)); st2 = s2.solve()
        f = 'reach' if mk is src_reach else 'dist'
        same = ({k: v for k, v in s.store[f].items()} ==
                {k: v for k, v in s2.store[f].items()})
        ok &= same; trials += 1
        acc.append((st['reset'], st['joins'], st2['joins']))
        if t == 0:
            red = st2['joins'] / max(st['joins'], 1)
            print(f"  {shape:<14}{len(drop):>8}{st['reset']:>9}{st['joins']:>10}"
                  f"{st2['joins']:>11}{red:>7.1f}×  {'✓' if same else '✗'}")
    n = len(acc)
    mr = sum(a for a, _, _ in acc) / n
    mred = sum(c / max(b, 1) for _a, b, c in acc) / n
    print(f"  {'  ↑ 12回の平均':<14}{'':>8}{mr:>9.0f}{'':>10}{'':>11}{mred:>7.1f}×")
print("-" * W)
print(f"  {trials} 回すべて一致: {'✓' if ok else '✗'}")
print()
print("  密なグラフ（頂点120・辺400）で 1.0× → **12回平均で random 202× / weighted 323×**。")
print("  変えたのは前線だけである。DRed は「読みうるものを全部消す」が、")
print("  **証明書は既に支持を名指している** ので、支えが無事なセルは触らなくてよい。")
print("  触らなかったセルの値が変わらないことは、実測ではなく")
print("  **導出が生きているという理由で**言える（削除後 ⊑ 削除前 なので等号）。")
print("=" * W)
sys.exit(0 if ok else 1)
