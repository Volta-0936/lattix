#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**なぜその値になったのか** を訊けるか。

この言語だけができることがある —— どの値にも証人がいる。階数も、正当化した
規則実例も、証明書のために既に全部計算されている。蛇口が無かっただけである。

三つの問いに答えられなければならない:
  値がある → どの規則がどの束縛で作ったか（**最短の**導出木）
  ⊤       → 食い違った二つの寄与を名指し、食い違いの源まで辿る
  ⊥       → 向かった実例のうち、**どのガードがなぜ偽だったか**

三つ目が一番効く。「なぜ空なのか」はデバッグの第一の問いで、
printf も breakpoint も無いこの言語には、他に訊く方法が無い。
"""
import os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = 84


def ask(example, cell):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'lattix.py'),
                        os.path.join(ROOT, 'examples', example), '--why', cell],
                       capture_output=True, text=True)
    return r.stdout


cases = []

# ① 確定値 —— 最短経路の導出が、実際に最短の経路を辿るか
t = ask('01_shortest.lx', 'dist[5]')
cases.append(("値の導出木", 'dist[5]',
              t.splitlines()[0].strip() == "dist[5] = 13"
              and "dist[0] <- 0" in t
              and "dist[2] = 1" in t and "dist[1] = 3" in t, t))

# ② ⊤ —— 食い違った二つの寄与を名指し、閉路まで辿るか
t = ask('29_dataflow.lx', 'cvin[3,y]')
cases.append(("⊤ の二つの証人", 'cvin[3,y]',
              "食い違った二つの寄与" in t and "→  0" in t
              and "閉路に戻った" in t, t))

# ③ ⊥ —— どのガードが偽だったかを、束縛を当てはめて言えるか
t = ask('29_dataflow.lx', 'reach[7]')
cases.append(("⊥ の理由", 'reach[7]',
              "ガード" in t and "succ[i=0,j=7]" in t, t))

# ④ ⊥ —— そもそも向かう実例が無い場合
t = ask('01_shortest.lx', 'dist[9]')
cases.append(("⊥（実例なし）", 'dist[9]',
              "規則実例が一つも無い" in t, t))

print("=" * W)
print("  答えに理由を尋ねる —— 証人は既にいる。蛇口を付けただけ")
print("=" * W)
ok = True
for name, cell, good, out in cases:
    ok &= good
    print(f"  {name:<18} {cell:<14} {'✓' if good else '✗'}")
    if not good:
        print("    ---\n" + "\n".join("    " + l for l in out.splitlines()[:10]))
print("-" * W)
print("  一致" if ok else "  不一致")
print("  `dist[5] = 13` の導出は 0→2→1→3→4→5。**階数が最短の導出を知っている。**")
print("  `reach[7] = ⊥` は「向かった 12 件すべてガードが偽」——")
print("  束縛を当てはめた形（`succ[i=0,j=7]`）で言えるので、次に見る場所が分かる。")
print("=" * W)
sys.exit(0 if ok else 1)
