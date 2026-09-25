# -*- coding: utf-8 -*-
"""**使う側の試験。** `./lattix` に .lx を食わせて焼き、走らせ、
   解釈実行（lattix.py）と升まで比べる。試験用に作られていない .lx を使う。"""
import os, re, struct, subprocess, sys, io, collections, tempfile
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,ROOT)
import lattix as L
LATTIX=os.environ.get("LATTIX_EXE", os.path.join(ROOT,"lattix"))

CASES=[]
def case(name, src, data=b'', rows=None, exit=None, known=False, why=None):
    # why=(行, 理由) —— **焼けないと言うだけでは足りない。どこを直すかを言う。**
    CASES.append((name, src, data, rows, exit, known, why))

case("二乗（計数器 × 計数器）", """table ch = (0,32)
field sq : max bound 16
sq[i] <- i * i   for (i) in 0 .. 9
""")
case("足す（計数器 + 計数器）", """table ch = (0,32)
field d : max bound 16
d[i] <- i + i   for (i) in 0 .. 9
""")
case("定数を掛ける", """table ch = (0,32)
field m : max bound 16
m[i] <- i * 3   for (i) in 0 .. 9
""")
case("鎖（前の升に足す）", """table ch = (0,32)
field s : max bound 16
s[0] <- 0
s[i] <- s[i-1] + 2   for (i) in 1 .. 9
""")
case("最短経路（三列の表）", """table edges = (0,0,0)
field dist : min bound 16
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edges
""", rows=[(0,1,4),(0,2,1),(2,1,2),(1,3,5),(3,4,3)])
case("到達可能性（or）", """table edges = (0,0,0)
field reach : or bound 16
reach[0] <- true
reach[j] <- true   for (i,j,w) in edges if reach[i]
""", rows=[(0,1,1),(1,2,1),(3,4,1)])
case("語を数える（生バイト）", """table ch = (0,32)
field isw : or bound 256
isw[i] <- true   for (i,c) in ch if c >= 97
field brk : or bound 256
brk[i] <- true   for (i,c) in ch if i >= 1 if isw[i] if not isw[i-1]
field n : count bound 4
n[0] <- 1        for (i,c) in ch if brk[i]
""", data=b'the quick brown fox jumps')
case("大文字にする（bit を落とす）", """table ch = (0,32)
field up : max bound 256
up[i] <- c - 32   for (i,c) in ch if c >= 97 if c <= 122
""", data=b'abc xyz')
case("二次元の場", """table ch = (0,32)
field g : max bound 8 8
g[i,j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
""")
case("集約（数える）", """table edges = (0,0,0)
field deg : count bound 16
deg[i] <- 1   for (i,j,w) in edges
""", rows=[(0,1,1),(0,2,1),(1,2,1)])
case("集約（足す）", """table edges = (0,0,0)
field tot : sum bound 16
tot[i] <- w   for (i,j,w) in edges
""", rows=[(0,1,4),(0,2,1),(1,2,7)])
case("場の値が座標", """table edges = (0,0,0)
field ptr : max bound 16
ptr[i] <- j   for (i,j,w) in edges
field val : max bound 16
val[i] <- w   for (i,j,w) in edges
field got : max bound 16
got[i] <- val[ptr[i]]   for (i,j,w) in edges
""", rows=[(0,1,4),(1,2,5),(2,3,6)])
case("否定のガード", """table edges = (0,0,0)
field seen : or bound 16
seen[i] <- true   for (i,j,w) in edges
field miss : or bound 16
miss[j] <- true   for (i,j,w) in edges if not seen[j]
""", rows=[(0,1,1),(1,2,1)])
case("比較（場と場）", """table edges = (0,0,0)
field a : max bound 16
a[i] <- w   for (i,j,w) in edges
field b : max bound 16
b[i] <- j   for (i,j,w) in edges
field big : or bound 16
big[i] <- true   for (i,j,w) in edges if a[i] > b[i]
""", rows=[(0,1,4),(1,2,1),(2,3,9)])
case("割る・余り", """table ch = (0,32)
field h : max bound 16
h[i] <- i / 2   for (i) in 0 .. 9
field r : max bound 16
r[i] <- i % 4   for (i) in 0 .. 9
""")
case("層（前の層が閉じてから）", """table edges = (0,0,0)
field e : or bound 16
e[i] <- true   for (i,j,w) in edges
field none : or bound 4
none[0] <- true   for (i,j,w) in edges if not e[j]
""", rows=[(0,1,1),(1,0,1)])


case("引く（計数器 − 計数器）", """table ch = (0,32)
field d : max bound 16
d[i] <- i - i   for (i) in 0 .. 5
""")
case("列 × 列", """table edges = (0,0,0)
field m : max bound 16
m[i] <- j * w   for (i,j,w) in edges
""", rows=[(0,2,3),(1,4,5)])
case("場 × 場", """table edges = (0,0,0)
field a : max bound 16
a[i] <- j   for (i,j,w) in edges
field b : max bound 16
b[i] <- w   for (i,j,w) in edges
field m : max bound 16
m[i] <- a[i] * b[i]   for (i,j,w) in edges
""", rows=[(0,2,3),(1,4,5)])
case("場 − 場", """table edges = (0,0,0)
field a : max bound 16
a[i] <- j   for (i,j,w) in edges
field b : max bound 16
b[i] <- w   for (i,j,w) in edges
field d : max bound 16
d[i] <- a[i] - b[i]   for (i,j,w) in edges
""", rows=[(0,9,3),(1,8,5)])
case("左からの畳み込み（i * 2 + 1）", """table ch = (0,32)
field f : max bound 16
f[i] <- i * 2 + 1   for (i) in 0 .. 5
""")
case("前の升を読む（f[i-1]）", """table ch = (0,32)
field n : max bound 256
n[i] <- c   for (i,c) in ch
field p : max bound 256
p[i] <- n[i-1] + 1   for (i,c) in ch if i >= 1
""", data=b'abcd')
case("次の升を読む（f[i+1]）", """table ch = (0,32)
field n : max bound 256
n[i] <- c   for (i,c) in ch
field q : max bound 256
q[i] <- n[i+1]   for (i,c) in ch
""", data=b'abcd')
case("入れ子の読みにずれ（f[g[i]+1]）", """table edges = (0,0,0)
field ptr : max bound 16
ptr[i] <- j   for (i,j,w) in edges
field val : max bound 16
val[i] <- w   for (i,j,w) in edges
field got : max bound 16
got[i] <- val[ptr[i] + 1]   for (i,j,w) in edges
""", rows=[(0,1,4),(1,2,5),(2,3,6)])
case("二次元のずれ（f[i,j-1]）", """table ch = (0,32)
field g : max bound 8 8
g[i,0] <- i           for (i) in 0 .. 3
g[i,j] <- g[i,j-1] + 1   for (i) in 0 .. 3 for (j) in 1 .. 3
""")
case("flat（定数伝播）", """table edges = (0,0,0)
field v : flat bound 16
v[i] <- w   for (i,j,w) in edges
""", rows=[(0,1,4),(0,2,4),(1,2,7),(1,3,9)])
case("min の ⊥（届かない升）", """table edges = (0,0,0)
field dist : min bound 16
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edges
""", rows=[(0,1,4),(5,6,1)])
case("ガード六種", """table edges = (0,0,0)
field a : max bound 16
a[i] <- w   for (i,j,w) in edges
field g1 : or bound 16
g1[i] <- true   for (i,j,w) in edges if w == 4
field g2 : or bound 16
g2[i] <- true   for (i,j,w) in edges if w != 4
field g3 : or bound 16
g3[i] <- true   for (i,j,w) in edges if w >= 4
field g4 : or bound 16
g4[i] <- true   for (i,j,w) in edges if w <= 4
field g5 : or bound 16
g5[i] <- true   for (i,j,w) in edges if w > 4
field g6 : or bound 16
g6[i] <- true   for (i,j,w) in edges if w < 4
""", rows=[(0,1,3),(1,2,4),(2,3,5)])
case("区間の上端が場", """table edges = (0,0,0)
field lim : max bound 4
lim[0] <- w   for (i,j,w) in edges
field sq : max bound 32
sq[k] <- k + 100   for (k) in 0 .. lim[0]
""", rows=[(0,0,5)])
# **空の区間は一度も回らない。** 焼いた側のループは do-while だったので
# `for (k) in 1 .. 0` が本体を一度実行していた —— 頭で一度比べて直した。
case("空の区間（一度も回らない）", """table edges = (0,0,0)
field lim : max bound 4
lim[0] <- w   for (i,j,w) in edges
field z : max bound 32
z[k] <- 7   for (k) in 1 .. lim[0]
""", rows=[(0,0,0)])
# **名前は 16 文字まで。** 鍵は 8 文字を二本ぶんしか持てない ——
# 17 文字以上は綴りが違っても同じ鍵になるので、焼かずに言う。
case("長い名前（16文字まで）", """table ch = (0,32)
field abcdefghijklmnoX : max bound 16
field abcdefghijklmnoY : max bound 16
abcdefghijklmnoX[i] <- 1 for (i,c) in ch
abcdefghijklmnoY[i] <- 2 for (i,c) in ch
""", data=b"ab")
case("17文字の名前（焼けない）", """table ch = (0,32)
field abcdefghijklmnopq : max bound 16
abcdefghijklmnopq[i] <- 1 for (i,c) in ch
""", data=b"ab", exit=7, why=(2,1))
# **宣言した上限は、そこまで本当に入らなければ嘘である。**
# 源 262,144 バイトを (位置, 文字) の表に開くと 16 バイト × 262,144 = 4MB 要る。
# 地上に 3.6MB しか無かったとき、228KB を超える源は **黙って壊れていた**
# （出力 23 バイト、終了コード 0）。
#
# **読める量（`rcap` = 524,288）と、位置で引ける量（文字の面）は一つの数である。**
# 長いあいだ面だけが 262,144 で、`rcap` の半分しか無かった。`lattix.lx` が
# 261,918 バイトまで育った日、**自分の源を読めなくなる 226 バイト手前**に居た。
# 面を `rcap` に合わせた（memsz 631 → 1,097 MB、焼きは 2.02 → 2.15 秒）。
# この組が、その二つが同じであることを測る —— 数えて言う（気づき35・44）。
case("520KB の源（宣言の内側）", """table ch = (0,32)
field big : or bound 64
big[i] <- true for (i,c) in ch if c >= 97
""" + "\n".join("# %d ------------------------------------------------------" % i
                for i in range(8400)) + "\n", data=b"abc")
# **入れ子は八重まで**（計数器は rcx / r13 / r14 の三本と、四本目からは場の下の升）。
# 前は三重までで、四重目は黙って壊れた符号になっていた（のちに焼かずに言うようにした）。
# 升の計数器を **座標・比較の左右・値・掛ける・上端が場の区間・場の読みの座標** で読む。
case("入れ子 三重（通る）", """table ch = (0,32)
field a : max bound 16
a[k] <- 1   for (k) in 0 .. 1 for (m) in 0 .. 1 for (n) in 0 .. 1
""", data=b"ab")
case("入れ子 四重（通る・升の計数器）", """table ch = (0,32)
field a : max bound 4 4
a[m, p] <- k * 10 + n + p   for (k) in 0 .. 1 for (m) in 0 .. 3 for (n) in 0 .. 2 for (p) in 0 .. 3 if p != n
""", data=b"ab")
case("入れ子 八重（通る・升の計数器）", """table ch = (0,32)
field n : max bound 2
n[0] <- 2
field w : or bound 4 4
w[i, j] <- true   for (i) in 0 .. 3 for (j) in 0 .. 3 if i != j
field a : max bound 4 4
a[g, q] <- q * h + d - f + r   for (b) in 0 .. 1 for (d) in 0 .. 1 for (f) in 0 .. 1 for (g) in 0 .. 3
      for (h) in 0 .. n[0] for (p) in 1 .. 2 for (q) in 0 .. 3 for (r) in 0 .. 1
      if q >= p if r < h if w[g, q] if b == 0
""", data=b"ab")
# **一つの文の束縛は十まで**（鍵で引く —— 前は焼き手の前段が六つ、下ろしの前段が十と、
# 同じ判断を二箇所に別々の上限で持っていた）。表の六列を束ねてから区間を四つ重ねる。
# **依存する区間**（13g）: 上端の添字が外の区間の変数（`for (j) in 0 .. n[i]`）。多面体でいえば箱でなく
# 半空間で切られた反復空間 —— 焼く側は入るたびに上端を読み直し、段ごとの升に置いて比べる。
case("依存する区間（上端が外の変数で引いた場）", """table ch = (0,32)
field n : max bound 4
n[0] <- 2
n[1] <- 0
n[3] <- 5
field t : max bound 4 8
t[i, j] <- i * 10 + j   for (i) in 0 .. 3 for (j) in 0 .. n[i]
field s : sum bound 4
s[i] <- 1   for (i) in 0 .. 0 for (k) in 0 .. 3 for (j) in 1 .. n[k]
""")
case("依存する区間（升の計数器・内側の変数・負の上端）", """table ch = (0,32)
field n : max bound 8
n[0] <- 3
n[1] <- 1
n[2] <- 0 - 2   for (z) in 0 .. 0
n[4] <- 2
field t : max bound 8 8
t[a, j] <- a + b + d + j * 100   for (a) in 0 .. 1 for (b) in 0 .. 1 for (d) in 0 .. 4 for (j) in 0 .. n[d]
field u : max bound 8 8
u[i, j] <- j + k * 10   for (i) in 0 .. 4 for (k) in 0 .. n[i] for (j) in 1 .. n[k]
field w : max bound 8 8
w[p, q] <- a + q   for (a) in 0 .. 1 for (b) in 0 .. 0 for (d) in 0 .. 0 for (p) in 0 .. 4 for (q) in 0 .. n[p]
""")
case("依存する区間の上端が ⊥ / 場の広さの外なら回らない", """table ch = (0,32)
field n : max bound 4
n[1] <- 2
field t : max bound 8 8
t[i, j] <- j + 1   for (i) in 0 .. 6 for (j) in 0 .. n[i]
""")
case("依存する区間の添字が表の変数（言う —— 下ろしが持ち上げる形）", """table ch = (0,32)
field n : max bound 4
n[1] <- 2
field u : max bound 8 8
u[i, j] <- j   for (i,c) in ch for (j) in 0 .. n[i]
""", data=b"ab", exit=7, why=(5,8))
# **下端が場の区間**（13i）: 解釈実行の文法では、`in` の次が名前で `..` が直に続かなければ表の名である。
# だから読みの下端は丸括弧で包む（`(lo[i]) ..`）。名前は `..` が直に続くときだけ下端（`i ..` —— 三角）。
# 評価は下端 → 上端 → 広さ: どちらかが ⊥ なら空、広さが上限を越えたら断る（終了コード 10）。
case("下端が場（丸括弧の読み・裸の外の変数）", """table ch = (0,32)
field lo : max bound 4
field hi : max bound 4
lo[0] <- 1
lo[1] <- 3
lo[2] <- 5
hi[0] <- 2
hi[1] <- 4
hi[3] <- 3
field a : max bound 8
a[j] <- j * 10   for (j) in (lo[0]) .. 4
field t : max bound 4 8
t[i, j] <- i * 10 + j   for (i) in 0 .. 3 for (j) in (lo[i]) .. hi[i]
field u : sum bound 4
u[i] <- j   for (i) in 0 .. 3 for (j) in i .. 3
field v : count bound 4
v[i] <- k   for (i) in 0 .. 3 for (k) in (lo[i]) .. 6
""")
case("下端が場（升の計数器・min の ⊥・sum の 0・負の下端）", """table ch = (0,32)
field m : min bound 8
m[1] <- 2
m[3] <- 0 - 1   for (z) in 0 .. 0
m[4] <- 9
field s : sum bound 8
s[2] <- 3
field r : sum bound 8
r[d] <- j + a + b   for (a) in 0 .. 1 for (b) in 0 .. 1 for (c) in 0 .. 0 for (d) in 0 .. 4 for (j) in (m[d]) .. 2
field q : max bound 8
q[e] <- e + d   for (a) in 0 .. 0 for (b) in 0 .. 0 for (c) in 0 .. 0 for (d) in 0 .. 2 for (e) in d .. 4
field w : max bound 8
w[j] <- j   for (j) in (s[0]) .. 3
w[j] <- j + 100   for (j) in (s[2]) .. 5
""")
case("下端が場で広さが上限を越える（止まって言う）", """table ch = (0,32)
field lo : max bound 2
lo[0] <- 0 - 5000000   for (z) in 0 .. 0
field x : max bound 8
x[j] <- 1   for (j) in (lo[0]) .. 3
""", exit=10)
case("下端が名前で `..` が続かない（定義は表の名と読む —— 言う）", """table ch = (0,32)
field lo : max bound 2
lo[0] <- 1
field x : max bound 8
x[j] <- j   for (j) in lo[0] .. 3
""", exit=7, why=(5,8))
case("丸括弧の下端が式（言う —— 下ろしが持ち上げる形）", """table ch = (0,32)
field x : max bound 8
x[j] <- j   for (i) in 0 .. 2 for (j) in (i + 1) .. 3
""", exit=7, why=(3,8))
case("裸の下端が表の変数（言う —— 下ろしが持ち上げる形）", """table ch = (0,32)
field x : max bound 8
x[j] <- j   for (i,c) in ch for (j) in i .. 3
""", data=b"ab", exit=7, why=(3,8))
case("束縛 十（表の六列 + 区間四つ）", """table t = (0,0,0,0,0,0)
field a : max bound 8 4
a[p, j] <- q + r + s + u + v + i + k + m   for (p,q,r,s,u,v) in t for (i) in 0 .. 1 for (j) in 0 .. 3 for (k) in 0 .. 1 for (m) in 0 .. 2
      if m != k
""", rows=[(0,1,2,3,4,5),(1,0,0,0,0,1),(5,2,2,2,2,2)])
case("束縛 十一（焼けない）", """table t = (0,0,0,0,0,0)
field a : max bound 8 4
a[p, j] <- q + n   for (p,q,r,s,u,v) in t for (i) in 0 .. 1 for (j) in 0 .. 3 for (k) in 0 .. 1 for (m) in 0 .. 2 for (n) in 0 .. 1
""", rows=[(0,1,2,3,4,5)], exit=7, why=(3,8))
case("入れ子 九重（焼けない）", """table ch = (0,32)
field a : max bound 16
a[k] <- 1   for (k) in 0 .. 1 for (m) in 0 .. 1 for (n) in 0 .. 1 for (p) in 0 .. 1 for (q) in 0 .. 1 for (r) in 0 .. 1 for (s) in 0 .. 1 for (u) in 0 .. 1 for (v) in 0 .. 1
""", data=b"ab", exit=7, why=(3,2))
# ══ 断片の際（測った）════════════════════════════════════════════
# **狭さは覚えていられない。** 「入れ子は一段まで」と書いてあった。測ったら
# 一段なのは **書き座標** だけで、値とガードは二段まで入った。さらに調べたら
# 二段なのも生成器の都合ですらなく、**座標の源に「読み」が無かった**だけで、
# 鎖（源5）を開いたら三段も四段も通った。いまの際は
# 「書き座標は三段まで測った / 値・ガードは四段まで測った」である ——
# 上限を数字で書かず、**測った所まで**を試験に置く（気づき33・44）。
# 下の `Z` は共通の前置き（7 行）で、どの組も 8 行目に場、9 行目に規則が来る。
Z = """table ch = (0,32)
field a : max bound 16
a[i] <- 1 for (i,c) in ch
field b : max bound 16
b[i] <- 0 for (i,c) in ch
field p : max bound 16
p[i] <- 0 for (i,c) in ch
"""
case("値の読み 二段（通る）", Z + """field v : max bound 16
v[i] <- a[b[i]] for (i,c) in ch
""", data=b"ab")
case("値の読み 三段（通る）", Z + """field v : max bound 16
v[i] <- a[b[p[i]]] for (i,c) in ch
""", data=b"ab")
case("ガードの読み 二段（通る）", Z + """field v : or bound 16
v[i] <- true for (i,c) in ch if a[b[i]] >= 1
""", data=b"ab")
case("ガードの読み 三段（通る）", Z + """field v : or bound 16
v[i] <- true for (i,c) in ch if a[b[p[i]]] >= 1
""", data=b"ab")
# **書き座標だけは一段である。** 値と同じ二段が書けると思っていた。
case("書き座標の読み 一段（通る）", Z + """field v : or bound 16
v[a[i]] <- true for (i,c) in ch if a[i] >= 0
""", data=b"ab")
case("書き座標の読み 二段（通る）", Z + """field v : or bound 16
v[a[b[i]]] <- true for (i,c) in ch if a[b[i]] >= 0
""", data=b"ab")
case("値の読み 四段（通る）", Z + """field q : max bound 16
q[i] <- 0 for (i,c) in ch
field v : max bound 16
v[i] <- a[b[p[q[i]]]] for (i,c) in ch
""", data=b"ab")
case("書き座標の読み 三段（通る）", Z + """field v : or bound 16
v[a[b[p[i]]]] <- true for (i,c) in ch if a[b[p[i]]] >= 0
""", data=b"ab")
# **どこまで測ったかを置く。** 鎖は一段ずつ内側に開くだけなので原理的な
# 上限は無いが、上限は **超えたときを試すまで上限ではない**（気づき44）——
# 源が実際に使う深さ（front.lx は書き座標 5 / 値 6）まで測って置く。
D5 = """table ch = (0,32)
field a : max bound 16
a[i] <- c   for (i,c) in ch
field b : max bound 16
b[i] <- 3 - i   for (i) in 0 .. 3
field p : max bound 16
p[i] <- 3 - i   for (i) in 0 .. 3
field q : max bound 16
q[i] <- 3 - i   for (i) in 0 .. 3
field r : max bound 16
r[i] <- 3 - i   for (i) in 0 .. 3
field t : max bound 16
t[i] <- 3 - i   for (i) in 0 .. 3
"""
case("値の読み 五段（通る）", D5 + """field v : max bound 16
v[i] <- a[b[p[q[r[i]]]]]   for (i) in 0 .. 3
""", data=b"wxyz")
case("値の読み 六段（通る）", D5 + """field v : max bound 16
v[i] <- a[b[p[q[r[t[i]]]]]]   for (i) in 0 .. 3
""", data=b"wxyz")
case("書き座標 五段（通る）", D5 + """field v : or bound 16
v[b[p[q[r[i]]]]] <- true   for (i) in 0 .. 3 if b[p[q[r[i]]]] >= 0
""", data=b"wxyz")
# 二次元の座標の中でも鎖は開く（次元0 が三段、次元1 は定数）
case("二次元の中 三段（通る）", D5 + """field g : max bound 8 8
g[i,j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
field v : max bound 16
v[i] <- g[b[p[i]], 1]   for (i) in 0 .. 3
""", data=b"wxyz")
# **辺は式ではない。** ここは長いあいだ **黙って壊れた符号**を出していた ——
# 場の番号のつもりで足し算の結果を読み、走らせると segfault した。
# 数え上げでは漏れる（左の手前・右の後ろ・前置き・否定の四通りある）ので、
# いまは「if 節の中の、括弧の外の演算子」を一本で見る。
case("辺に式 左（焼けない）", Z + """field v : or bound 16
v[i] <- true for (i,c) in ch if a[i] + 1 >= 2
""", data=b"ab", exit=7, why=(9, 8))
case("辺に式 右（焼けない）", Z + """field v : or bound 16
v[i] <- true for (i,c) in ch if a[i] >= b[i] + 1
""", data=b"ab", exit=7, why=(9, 8))
case("辺に式 前置き（焼けない）", Z + """field v : or bound 16
v[i] <- true for (i,c) in ch if 1 + a[i] >= 2
""", data=b"ab", exit=7, why=(9, 8))
case("否定の辺に式（焼けない）", Z + """field v : or bound 16
v[i] <- true for (i,c) in ch if not a[i] + 1
""", data=b"ab", exit=7, why=(9, 8))
# **括弧の中のずれは式ではない。** `f[i-1]` は座標の話なので当たらない。
case("座標の中のずれ（通る）", Z + """field v : or bound 16
v[i] <- true for (i,c) in ch if a[i+1] >= 1
""", data=b"ab")
# **二次元の中間の場は引ける。** 深い書き座標を平らにするとき、輪の変数が
# 二つある式はここへ落ちる（`work/flatten.py`）。
case("二次元の中間の場（通る）", Z + """field q : max bound 64 2
q[i,k] <- a[i] + k for (i,c) in ch for (k) in 0 .. 1
field r : or bound 64
r[q[i,k]] <- true for (i,c) in ch for (k) in 0 .. 1 if q[i,k] >= 0
""", data=b"ab")

# **項は八つまで。** 九つ目は隣の文の枠を踏んで、答えが黙って変わっていた。
case("項 八つ（通る）", """table ch = (0,32)
field a : max bound 16
a[i] <- 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1   for (i,c) in ch
""", data=b"ab")
case("項 九つ（焼けない）", """table ch = (0,32)
field a : max bound 16
a[i] <- 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1   for (i,c) in ch
""", data=b"ab", exit=7, why=(3,3))
# **二のべきでない除数。** 前は `c / 3` は寄せ量が出ずに割り算が消え、`c % 3` は
# `and rax,2` になって別の答えを出していた —— どちらも黙って。いまは idiv で割り、
# 床（Python の `//` と `%`）に寄せる。焼けないのは 0・負・即値の外の除数だけ。
case("割る・余り（二のべき）", """table ch = (0,32)
field q : max bound 8
q[i] <- c / 4   for (i,c) in ch
field r : max bound 8
r[i] <- c % 8   for (i,c) in ch
""", data=b"ab")
case("三で割る（通る）", """table ch = (0,32)
field q : max bound 8
q[i] <- c / 3   for (i,c) in ch
""", data=b"ab")
case("三で割った余り（通る）", """table ch = (0,32)
field r : max bound 8
r[i] <- c % 3   for (i,c) in ch
""", data=b"ab")
case("負を割る・余り（床へ寄せる）", """table ch = (0,32)
field q : max bound 8
q[i] <- - c / 7   for (i,c) in ch
field r : max bound 8
r[i] <- - c % 7   for (i,c) in ch
field s : max bound 8
s[i] <- c * 1000003 / 10 % 10   for (i,c) in ch
""", data=b"az!")
case("零で割る（焼けない）", """table ch = (0,32)
field q : max bound 8
q[i] <- c / 0   for (i,c) in ch
""", data=b"ab", exit=7, why=(3,5))
case("零の法（焼けない）", """table ch = (0,32)
field r : max bound 8
r[i] <- c % 0   for (i,c) in ch
""", data=b"ab", exit=7, why=(3,5))
# **行と理由は対でなければ意味が無い。** 別々の min で選ぶと、行は一方の
# 最小・理由は他方の最小になって、**指した行にその理由が無い**ことが起きる。
# 一つの鍵（行 * 16 + 理由）に畳んであるので、二つ誤りを置いて確かめる。
case("二つの誤り（先が出る）", """table ch = (0,32)
field abcdefghijklmnopq : max bound 16
abcdefghijklmnopq[i] <- 1 for (i,c) in ch
field q : max bound 8
q[i] <- c / 0   for (i,c) in ch
""", data=b"ab", exit=7, why=(2,1))
# **`or` の元は ⊥ と true しか無い。** 値を書くと解釈実行は何も置かず
# （値が true でない）、焼いた符号は規則が火を噴いた時点で 1 を置く ——
# 同じ源が二つの答えを持っていた。型の誤りとして断る。
case("or に値を書く（焼けない）", """table ch = (0,32)
field f : or bound 16
f[i] <- c % 4   for (i,c) in ch
""", data=b"ab", exit=7, why=(3,9))
case("or の場を読む（通る）", """table ch = (0,32)
field a : or bound 16
a[i] <- true   for (i,c) in ch if c >= 97
field b : or bound 16
b[i] <- a[i]   for (i,c) in ch
""", data=b"ab")
# **⊥ が 0 の束では、0 は ⊥ である。** `s[0]` は寄与が届いていても値は 0 ——
# 焼いた符号は升が 0 なので ⊥ と見る。解釈実行も同じに見なければならない。
case("sum の 0 は ⊥", """table ch = (0,32)
field s : sum bound 16
s[i] <- i   for (i,c) in ch
field g : max bound 16
g[i] <- 7   for (i) in 0 .. 5 if s[i] <= 3
""", data=b"hello Ldx")
case("二つの誤り（逆順）", """table ch = (0,32)
field q : max bound 8
q[i] <- c / 0   for (i,c) in ch
field abcdefghijklmnopq : max bound 16
abcdefghijklmnopq[i] <- 1 for (i,c) in ch
""", data=b"ab", exit=7, why=(3,5))
# **`/` と `%` は場の読みには種が付いていなかった。** 付いていないのに素の
# 「場の読み」に落ちるので、`a[i] / a[i-1]` が **足し算**になっていた
# （97/98 が 195）—— 解釈実行は 1 と言う。同じ源が二つの答えを持っていた。
case("場で割る（焼けない）", """table ch = (0,32)
field a : max bound 8
a[i] <- c   for (i,c) in ch
field b : max bound 8
b[i] <- a[i] / a[i-1]   for (i,c) in ch if i >= 1
""", data=b"ab", exit=7, why=(5,8))
case("場で余り（焼けない）", """table ch = (0,32)
field a : max bound 8
a[i] <- c   for (i,c) in ch
field b : max bound 8
b[i] <- a[i] % a[i-1]   for (i,c) in ch if i >= 1
""", data=b"ab", exit=7, why=(5,8))
# 引く・掛けるは通る（種9/10）——「通る一つ隣」を対で置く
case("場を引く・掛ける（通る）", """table ch = (0,32)
field a : max bound 8
a[i] <- c   for (i,c) in ch
field b : max bound 8
b[i] <- a[i] * a[i-1]   for (i,c) in ch if i >= 1
field d : max bound 8
d[i] <- a[i] - a[i-1]   for (i,c) in ch if i >= 1
""", data=b"ab")
# **知らない文を黙って読み飛ばしてはいけない。** `constructor` も `include` も
# `use` も `budget` も素通ししていて、焼けた実行ファイルは segfault していた。
case("知らない文（焼けない）", """table ch = (0,32)
constructor cons(h,t) bound 256
field a : max bound 8
a[i] <- c   for (i,c) in ch
""", data=b"ab", exit=7, why=(2,8))
case("辺に足し算（焼けない）", """table edges = (0,0,0)
field n : max bound 16
n[0] <- 3
field f : or bound 16
f[i] <- true   for (i,j,w) in edges if i + 1 == n[0]
""", rows=[(0,1,1)], exit=7, why=(5,8))
# **足した後に掛ける形は焼かない。** 焼いた符号は左から畳み（`(1+2)*3 = 9`）、
# **足してから掛ける形は焼ける。** 長いあいだ「焼けない」の例だった ——
# 焼いた符号が `rax` を累算器にした左畳みで、`1 + 2 * 3` が 9 になり、
# 解釈実行の 7 と食い違ったからである。黙って違う答えを出すよりはと
# 断っていた（理由7）。いまは項が **群** に分かれ、和は場の下の升に
# 溜まるので、どちらも 7 を出す。断りは消した。
case("足してから掛ける（通る）", """table edges = (0,0,0)
field a : max bound 16
a[i] <- j + w * 3   for (i,j,w) in edges
""", rows=[(0,1,2)])
P = """table ch = (0,32)
field a : max bound 16
a[i] <- 2 + i   for (i) in 0 .. 3
field b : max bound 16
b[i] <- 3 + i   for (i) in 0 .. 3
field c : max bound 16
c[i] <- 5 - i   for (i) in 0 .. 3
"""
case("群 a + b * c", P + """field v : max bound 16
v[i] <- a[i] + b[i] * c[i]   for (i) in 0 .. 3
""", data=b"ab")
case("群 a * b + c * a", P + """field v : max bound 16
v[i] <- a[i] * b[i] + c[i] * a[i]   for (i) in 0 .. 3
""", data=b"ab")
case("群 a - b * c（群の符号）", P + """field v : max bound 16
v[i] <- a[i] - b[i] * c[i]   for (i) in 0 .. 3
""", data=b"ab")
case("群 a + b * 4 + c", P + """field v : max bound 16
v[i] <- a[i] + b[i] * 4 + c[i]   for (i) in 0 .. 3
""", data=b"ab")
case("群 a + i * 2（計数器）", P + """field v : max bound 16
v[i] <- a[i] + i * 2   for (i) in 0 .. 3
""", data=b"ab")
case("群 a + b / 2（割る）", P + """field v : max bound 16
v[i] <- a[i] + b[i] / 2   for (i) in 0 .. 3
""", data=b"ab")
case("変数で割る（焼けない）", """table edges = (0,0,0)
field q : max bound 16
q[i] <- j / w   for (i,j,w) in edges
""", rows=[(0,4,2)], exit=7, why=(3,8))
# **三段は焼ける。** 長いあいだ「焼けない」の例だった —— 座標の源が
# 「列・計数器・場の値・定数」の四つだと思い込んでいて、添字が **読み** の
# ときに源が出ず、黙って座標が消えていたからである。鎖（源5）は
# `f[g[i,j]]` のために既に在ったので、条件を広げるだけで N 段まで届いた。
case("三段の読み（通る）", """table edges = (0,0,0)
field a : max bound 16
a[i] <- j   for (i,j,w) in edges
field c : max bound 16
c[i] <- a[a[a[i]]]   for (i,j,w) in edges
""", rows=[(0,1,1),(1,2,1)])
case("表が二つ（焼けない）", """table a = (0,0)
table b = (0,0,0)
field f : max bound 16
f[i] <- c   for (i,c) in a
""", data=b'xy', exit=7, why=(0,6))
# ══ 座標の濾し（`test/meta.py` が見つけた穴。直した）════════════════
# **座標は読むまえに広さで濾す。** 濾しは在ったのに `cdhf == 1`（ずれが
# あるとき）にしか出なかった —— 検査が「座標」という **概念**ではなく
# 「ずれ」という **機能**に紐づいていたからである（気づき34 の裏面）。
# 漏れると解釈実行と食い違う。黙って:
#
#   解釈実行   b: ⊥ everywhere   （100 番の升は a に無い）
#   焼いた側   b[0] = 0          ← **隣の場の升を読んで、その数を答えにした**
#
# 鎖にすると読んだごみが次の座標になって segfault した。三つとも置く。
case("座標が広さを超える（場の値）", """table ch = (0,32)
field big : max bound 8
big[i] <- 100   for (i,c) in ch if i <= 2
field a : max bound 8
a[i] <- 7   for (i) in 0 .. 7
field b : max bound 8
b[i] <- a[big[i]]   for (i,c) in ch if i <= 2
""", data=b'abc')
case("座標が広さを超える（表の列）", """table ch = (0,32)
field a : max bound 8
a[i] <- 7   for (i) in 0 .. 7
field b : max bound 8
b[i] <- a[c]   for (i,c) in ch
""", data=b'abc')
# 鎖の途中の輪も濾す（内側の所有者でも **次元0 は座標として完成している**）
case("鎖の途中がはみ出す", """table ch = (0,32)
field f0 : max bound 64
f0[i] <- c % 8   for (i,c) in ch
field f1 : sum bound 64
f1[f0[i]] <- f0[i] * 2 + f0[i] * 3   for (i,c) in ch   if f0[i] >= 2
field f2 : count bound 64
f2[i] <- f0[f1[f1[i]]]   for (i,c) in ch   if f1[f1[i]] >= 1
""", data=b'lattix meta test 42')

# ══ 否定のガードの下の ⊥ —— **神託の側が間違っていた** ══════════════
# `if not g[f[i]]` で `f[i]` が ⊥ のとき、撃つか撃たないか。
# 焼いた側と C 測定器は **撃たない**、解釈実行だけが **撃つ**だった。
# 二対一だが多数決ではない —— **意図が四箇所に書いてあった**:
#   `lattix.classify`   「添字は否定の下でも添字である。⊥ の座標は真に読まれる
#                        ことがなく、ただ寄与を消す」（成層はこの上に立つ）
#   `native.botguards`  「添字は否定の下でも要る」
#   C 測定器・焼いた符号 そう実装している
# 解釈実行の評価器（`ev`）だけが、座標の不在を「その升は ⊥」にすり替え、
# `not` がそれを真に裏返していた。すぐ下に同じ形の先例（`not (f[x] < 6)` は
# ⊥ のとき撃たない）があったのに、座標の場合だけ塞がれていなかった。
# 評価器を直した。この組は、三つの実装が同じ答えを出すことを測る。
case("否定の下の ⊥（撃たない）", """table ch = (0,32)
field f0 : sum bound 16
f0[i] <- 5   for (i,c) in ch   if c >= 97
field g0 : or bound 16
g0[i] <- true   for (i,c) in ch if c >= 100
field f1 : count bound 256
f1[i] <- i   for (i) in 1 .. 6   if not g0[f0[i]]
""", data=b'hello Ldx')

# ══ 向きの食い違い（成層の四つ目）══════════════════════════════════
# 焼く側の成層は **位置**しか見ていなかった（`not` の直後・比較の節・添字の中）。
# 答えの定義は **向き**も見る —— 読む場の動く向きと、読む位置が要る向きが
# 食い違えば、書き手が途中で持っていた値を読み手が取り消せない。同じ層で
# 読むと、同じ表を回る規則が一つのループに畳まれて **途中の値を掴む**。
# 以下の五つは、直す前の焼き手がどれも **黙って違う答え**を出していた
# （`test/meta.py` が一つ目を撒いて出し、残りは位置ごとに作って確かめた）。
case("count の読み × min", """table ch = (0,32)
field f0 : max bound 64
f0[i] <- c % 8   for (i,c) in ch
field f1 : count bound 64
f1[f0[i]] <- 1   for (i,c) in ch
field f2 : min bound 64
f2[f0[i]] <- f1[i]   for (i,c) in ch
""", data=b'aabbcc')
case("count を引いて max へ", """table ch = (0,32)
field k : max bound 64
k[i] <- c % 4   for (i,c) in ch
field b : count bound 64
b[k[i]] <- 1   for (i,c) in ch
field t : max bound 64
t[k[i]] <- 100 - b[k[i]]   for (i,c) in ch
""", data=b'abcdefghijklmnopqrstuvwxyz')
case("育つ max を min が読む", """table ch = (0,32)
field k : max bound 64
k[i] <- c % 4   for (i,c) in ch
field mx : max bound 64
mx[k[i]] <- c   for (i,c) in ch
field m : min bound 64
m[k[i]] <- mx[k[i]]   for (i,c) in ch
""", data=b'abcdefghijklmnopqrstuvwxyz')
case("素のガードが min を読む", """table ch = (0,32)
field k : max bound 64
k[i] <- c % 4   for (i,c) in ch
field mn : min bound 64
mn[k[i]] <- c - 97   for (i,c) in ch
field x : max bound 64
x[k[i]] <- 1   for (i,c) in ch if mn[k[i]]
""", data=b'ea')
case("証の無い掛け算（負が育つ）", """table ch = (0,32)
field k : max bound 64
k[i] <- c % 4   for (i,c) in ch
field a : max bound 64
a[k[i]] <- c - 100   for (i,c) in ch
field t : max bound 64
t[k[i]] <- a[k[i]] * a[k[i]]   for (i,c) in ch
""", data=b'Z[\\]^_`abc')

# ── 書き先の側の向き ────────────────────────────────────────────
# 向きは読む側だけのものではない。max / min の join は途中の値を呑み込むが、
# flat は呑めない（3 のあとの 5 は ⊤）、sum も呑めない（同じ寄与の値が
# 変われば ⊤ —— 焼いた側では ⊤ ですらなく **小さい和**になっていた）。
# 答えの定義（`classify`）も flat の書き先に「上へ」を要求していたので、
# これは二つの実装に同じ形で空いていた穴である。解釈実行は依存の順に
# 解くので最後の値を読んで正しかった —— 分析ではなく順序が救っていた。
case("flat が育つ max を読む", """table ch = (0,32)
field k : max bound 64
k[i] <- c % 4   for (i,c) in ch
field mx : max bound 64
mx[k[i]] <- c   for (i,c) in ch
field g : flat bound 64
g[k[i]] <- mx[k[i]]   for (i,c) in ch
""", data=b'abcdefghijklmnopqrstuvwxyz')
case("sum が育つ max を足す", """table ch = (0,32)
field k : max bound 64
k[i] <- c % 4   for (i,c) in ch
field mx : max bound 64
mx[k[i]] <- c   for (i,c) in ch
field sm : sum bound 64
sm[k[i]] <- mx[k[i]]   for (i,c) in ch
""", data=b'abcdefghijklmnopqrstuvwxyz')

# **成層できない源は焼かない。** `alive[i] <- true ... if not alive[i]` は、問いの
# 答えがその問い自身に依る（解釈実行は「成層できない」と断る）。前段は層が
# 上がり続けて 127 に届いたこと（`toodeep`）を数えていたのに、**誰も読んで
# いなかった** —— 焼いた側は黙って答えを出していた。いまは理由 7 で言う。
case("成層できない（言う）", """table ch = (0,32)
field alive : or bound 64
alive[i] <- true   for (i,c) in ch if not alive[i]
""", data=b"ab", exit=7, why=(3,7))
case("向きの閉路（言う）", """table ch = (0,32)
field a : min bound 8
field b : max bound 8
a[0] <- 5
b[i] <- a[i]   for (i) in 0 .. 3
a[i] <- b[i] - 1   for (i) in 0 .. 3
""", data=b"ab", exit=7, why=(5,7))

# **焼けない束は宣言の行で言う。** fourv の `not` は Belnap の否定で単調なのに、
# 断片はそれを否定として数えて層が上がり続け、「成層できない」と言っていた
# （断るのは正しいが、理由が嘘）。宣言の行で「焼けない形」と言う。
case("焼けない束（言う）", """table ch = (0,32)
field liar : fourv bound 8
liar[i] <- true   for (i,c) in ch
liar[i] <- not liar[i]   for (i,c) in ch
""", data=b"ab", exit=7, why=(2,8))

# **⊤ の規律**（13e）。SPEC は「⊤ は少なくとも真」（比較は ⊤ で立つ）、「⊤ は座標になれない」、
# 算術は ⊤ 厳密と言う。焼いた符号は長いあいだこの規律を持たず、⊤ の印 0x7ffffffe を
# **ただの数**として読んでいた —— `if g[0] < 5` で解釈実行は立ち、焼いた側は立たなかった。
# そのあいだは ⊤ を作る所で止まって言っていた（終了コード 5）。いまは規律を焼く:
#   比較は ⊤ で立つ（⊥ とは比べられない）/ flat へ書く算術は ⊤ 厳密 / 数の場へ読めば止まる。
case("⊤ で比較は立つ", """table ch = (0,32)
field g : flat bound 4
g[0] <- 1   for (i,c) in ch if c == 97
g[0] <- 2   for (i,c) in ch if c == 98
field x : max bound 4
x[0] <- 1   for (i) in 0 .. 0 if g[0] < 5
""", data=b"ab")
case("⊤ で比較は立つ（左右・両辺・⊥ とは立たない）", """table ch = (0,32)
field f : flat bound 4
f[0] <- 1
f[0] <- 2
f[1] <- 5
f[3] <- 7
field g : flat bound 4
g[0] <- 3
g[0] <- 4
g[1] <- 5
field c : or bound 4
c[i] <- true   for (i) in 0 .. 3 if f[i] < 3
field d : or bound 4
d[i] <- true   for (i) in 0 .. 3 if f[i] >= 3
field e : or bound 4
e[i] <- true   for (i) in 0 .. 3 if 4 < f[i]
field k : or bound 4
k[i] <- true   for (i) in 0 .. 3 if f[i] == g[i]
field q : or bound 4
q[i] <- true   for (i) in 0 .. 3 if f[i] != g[i]
field u : or bound 4
u[i] <- true   for (i) in 0 .. 3 if i <= f[i]
""")
case("⊤ は flat へ書く算術で ⊤（⊥ なら撃たない）", """table ch = (0,32)
field f : flat bound 4
f[0] <- 1
f[0] <- 2
f[1] <- 5
f[2] <- 9
field b : flat bound 4
b[0] <- 10
b[1] <- 20
b[3] <- 30
field g : flat bound 4
g[i] <- f[i] * 3 + b[i] - 1   for (i) in 0 .. 3
field h : flat bound 4
h[i] <- b[i] - f[i] * f[i]   for (i) in 0 .. 3
field w : flat bound 4
w[i] <- g[i] / 2 + 1   for (i) in 0 .. 3
""")
case("⊤ を数の場へ読む（言う）", """table ch = (0,32)
field f : flat bound 4
f[0] <- 1
f[0] <- 2
field m : max bound 4
m[i] <- f[i] + 1   for (i) in 0 .. 3
""", exit=5)
case("同じ値なら ⊤ にならない", """table ch = (0,32)
field g : flat bound 4
g[0] <- 1   for (i,c) in ch if c == 97
g[0] <- 1   for (i,c) in ch if c == 98
field x : max bound 4
x[0] <- 1   for (i) in 0 .. 0 if g[0] < 5
""", data=b"ab")

# ══ 変異で撒いて出た穴（`test/mutate.py`）══════════════════════════
# 通る本を一行ずつ壊して焼くと、焼いた側が **落ちる**か **黙って違う答え**を出す
# 形が十一出た。どれも解釈実行は答えるか断るかのどちらかで、焼いた側だけが外れた。
case("同じ名前を二度宣言（言う）", """table ch = (0,32)
field a : max bound 4
a[0] <- 5
field a : min bound 4
a[0] <- 3
""", data=b"ab", exit=7, why=(4,10))
case("規則の無い場を先に宣言", """table ch = (0,32)
field a : max bound 16
field b : max bound 16
b[i] <- 3 + i   for (i) in 0 .. 3
field v : max bound 16
v[i] <- a[i] + b[i]   for (i) in 0 .. 3
field w : max bound 16
w[i] <- b[i]   for (i) in 0 .. 3
""")
case("規則が一本も無い", """table ch = (0,32)
field t : max bound 16
t[0] <- 1
""")
case("場が一つも無い", """table ch = (0,32)
""")
case("print に宣言の無い名（言う）", """table ch = (0,32)
print x
""", data=b"ab", exit=7, why=(2,4))
case("比較の節の not（言う）", """table ch = (0,32)
field a : max bound 16
a[i] <- c   for (i,c) in ch
field big : or bound 16
big[i] <- true   for (i,c) in ch if not a[i] > 97
""", data=b"ab", exit=7, why=(5,8))
# **二重以上のループの集約**（13f）。一度だけ数える印は外側の行でしか引いていないので、前は断っていた。
# 読む場を下の層に閉じれば（前段が集約の読みで層を切る）規則は一度しか回らず、印は要らない。
case("集約に二重のループ（count・表と区間）", """table ch = (0,32)
field a : count bound 4
a[0] <- 1   for (i,c) in ch for (k) in 0 .. 2
""", data=b"ab")
case("集約に三重のループ（読む場は同じ源の規則）", """table ch = (0,32)
field w : max bound 4 4
w[i, j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
field c : count bound 4
c[i] <- 1   for (i) in 0 .. 3 for (j) in 0 .. 3 if w[i, j] >= 3
field s : sum bound 4
s[i] <- w[i, j] * k   for (i) in 0 .. 3 for (j) in 0 .. 3 for (k) in 1 .. 2
field m : max bound 4
m[i] <- s[i] + c[i]   for (i) in 0 .. 3
""")
# **区間の集約の印**（14）。印は `[rcx + 変位]` で、表なら rcx は地上の行を指すが、区間では rcx が
# 計数器の値なので、番地は「変位 + i」—— どこでもない所だった。場が 4〜12 MB の本では場の升を印と読み、
# count が 10 でなく 0 になった（黙って違う答え）。印を「計数器 - 下端」のビットにした。
case("区間の集約の印（大きい場と並んでも数える）", """table ch = (0,32)
field big : max bound 1000000
big[i] <- 7   for (i) in 0 .. 999999
field c : count bound 1
c[0] <- i   for (i) in 0 .. 9
field s : sum bound 1
s[0] <- i   for (i) in 3 .. 12
""")
case("区間の集約の印（同じ層の読みで何周も回る・下端が 0 でない）", """table ch = (0,32)
field nx : max bound 64
nx[i] <- i + 1   for (i) in 5 .. 40
field reach : or bound 64
reach[5] <- true
reach[j] <- true   for (i) in 5 .. 40 for (j) in 0 .. 63 if reach[i] if nx[i] == j
field c : count bound 1
c[0] <- v   for (v) in 5 .. 50 if reach[v]
field s : sum bound 1
s[0] <- v   for (v) in 3 .. 60 if reach[v]
field n : max bound 1
n[0] <- 44
field u : sum bound 1
u[0] <- v   for (v) in 0 .. n[0] if reach[v]
""")
case("区間の集約で下端が場（印は 計数器 - 下端の升）", """table ch = (0,32)
field lo : max bound 1
lo[0] <- 2
field nx : max bound 64
nx[i] <- i + 1   for (i) in 3 .. 30
field reach : or bound 64
reach[3] <- true
reach[j] <- true   for (i) in 3 .. 30 for (j) in 0 .. 40 if reach[i] if nx[i] == j
field c : count bound 1
c[0] <- v   for (v) in (lo[0]) .. 25 if reach[v]
field s : sum bound 1
s[0] <- v   for (v) in (lo[0]) .. 25 if reach[v]
""")
case("区間の集約の下端の場が同じ層で動く（言う —— 印の番号がずれる）", """table ch = (0,32)
field nx : max bound 16
nx[i] <- i + 1   for (i) in 0 .. 9
field r : or bound 16
r[0] <- true
r[j] <- true   for (i) in 0 .. 9 for (j) in 0 .. 15 if r[i] if nx[i] == j
field lo : min bound 1
lo[0] <- 9
lo[0] <- 4   for (z) in 0 .. 0 if r[5]
field c : count bound 1
c[0] <- v   for (v) in (lo[0]) .. 12 if r[v]
""", exit=7, why=(11,8))
case("集約に二重のループで、自分を読み返す（言う）", """table ch = (0,32)
field c : count bound 4
c[0] <- 1
c[i] <- 1   for (i) in 1 .. 3 for (j) in 0 .. 1 if c[j] >= 1
""", exit=7, why=(4,7))
case("true は 1（max）", """table ch = (0,32)
field x : max bound 4
x[i] <- true   for (i) in 0 .. 2
field y : max bound 4
y[i] <- true + 1   for (i) in 0 .. 2
""")
case("or に true と読みを足す（言う）", """table ch = (0,32)
field e : or bound 4
e[i] <- true   for (i) in 0 .. 2
field n : or bound 4
n[i] <- true + e[i]   for (i) in 0 .. 2
""", data=b"ab", exit=7, why=(5,9))
case("頭の無い矢印（言う）", """table ch = (0,32)
field r : max bound 16
ri] <- i   for (i) in 0 .. 9
""", data=b"ab", exit=7, why=(3,8))
case("閉じない括弧（言う）", """table ch = (0,32)
field h : max bound 16
h[i <- i   for (i) in 0 .. 9
field r : max bound 16
r[i] <- 1   for (i) in 0 .. 3
""", data=b"ab", exit=7, why=(3,8))
case("一次元と二次元を混ぜる（言う）", """table ch = (0,32)
field q : max bound 8 2
q[i] <- 0   for (i) in 0 .. 3
q[i,k] <- i + k   for (i) in 0 .. 3 for (k) in 0 .. 1
""", data=b"ab", exit=7, why=(3,8))
case("否定 × 広さの外（立つ）", """table ch = (0,32)
field isw : or bound 256
isw[i] <- true   for (i,c) in ch if c >= 97
field brk : or bound 256
brk[i] <- true   for (i,c) in ch if i >= 0 if isw[i] if not isw[i-1]
""", data=b"the quick brown fox")
case("内側の添字が広さの外（⊥）", """table ch = (0,32)
field g : max bound 4
g[k] <- 1   for (k) in 0 .. 3
field f : max bound 64
f[k] <- 7   for (k) in 0 .. 63
field x : max bound 64
x[i] <- f[g[i]]   for (i,c) in ch
field y : max bound 64
y[i] <- f[g[i] + 2]   for (i,c) in ch
field z : or bound 64
z[i] <- true   for (i,c) in ch if not f[g[i]]
""", data=b"the quick brown fox")

case("not は ⊥ で立つ（flat / max / min）", """table ch = (0,32)
field sf : flat bound 16
sf[i] <- 1   for (i,c) in ch if c >= 98
field sm : max bound 16
sm[i] <- 1   for (i,c) in ch if c >= 98
field sn : min bound 16
sn[i] <- 1   for (i,c) in ch if c >= 98
field v : max bound 16
v[i] <- c - 98   for (i,c) in ch
field mf : or bound 16
mf[i] <- true   for (i,c) in ch if not sf[i]
field mm : or bound 16
mm[i] <- true   for (i,c) in ch if not sm[i]
field mn : or bound 16
mn[i] <- true   for (i,c) in ch if not sn[i]
field m0 : or bound 16
m0[i] <- true   for (i,c) in ch if not v[i]
""", data=b"abc")
case("種が広さの外（言う）", """table ch = (0,32)
field r : max bound 4
r[5] <- 7
field s : max bound 4
s[0] <- 1
""", data=b"ab", exit=7, why=(3,11))
case("種が式（言う）", """table ch = (0,32)
field t : max bound 16
t[0] <- 1 + 2
""", data=b"ab", exit=7, why=(3,8))
case("or の種が 1（言う）", """table ch = (0,32)
field t : or bound 16
t[0] <- 1
""", data=b"ab", exit=7, why=(3,9))
case("区間の上端が式（言う）", """table ch = (0,32)
field n : max bound 4
n[0] <- 3
field t : max bound 8
t[j] <- j   for (j) in 0 .. n[0] - 1
""", data=b"ab", exit=7, why=(5,8))
case("三次元の場（広さ三つ・種・内側の読み）", """table ch = (0,32)
field w : max bound 3 2 4
w[i, j, k] <- i * 100 + j * 10 + k   for (i) in 0 .. 2 for (j) in 0 .. 1 for (k) in 0 .. 3
field g : flat bound 3 3 3
g[1, 2, 0] <- 7
field a : flat bound 4
a[0] <- 1
a[1] <- 2
field t : max bound 8
t[k] <- w[a[k], k, a[k] + 1] + 1   for (k) in 0 .. 1
""", data=b"ab")
case("四次元の場（言う）", """table ch = (0,32)
field w : max bound 2 2 2
w[i, j, k, 0] <- i + j + k   for (i) in 0 .. 1 for (j) in 0 .. 1 for (k) in 0 .. 1
""", data=b"ab", exit=7, why=(3,8))

case("count の種は 1", """table ch = (0,32)
field d : count bound 16
d[0] <- 0
d[2] <- 5
d[i] <- 1   for (i,c) in ch
""", data=b"abc")
case("種の座標が式（言う）", """table ch = (0,32)
field d : min bound 16
d[0+1] <- 0
""", data=b"ab", exit=7, why=(3,8))
case("大きい数（言う）", """table ch = (0,32)
field x : max bound 4
x[i] <- i + 3000000000   for (i) in 0 .. 2
""", data=b"ab", exit=7, why=(3,12))
case("大きい割る数（通る）", """table ch = (0,32)
field x : max bound 4
x[i] <- i * 429496730 / 4294967296   for (i) in 0 .. 2
""")
# ══ 値が ⊥ / ⊤ の印と重なる（言う）══════════════════════════════════════
# 焼いた符号は「無い」を値で見分ける —— min と flat の ⊥ は 2147483647、max は -2147483647、
# flat の ⊤ は 2147483646。その値そのものを答えに持つ升は ⊥（や ⊤）に見える。
# 「INT_MAX を無限大に使う」書き方でそのまま踏む。解釈実行は数として持つ。
# 規則の値は join の手前で見張り（終了コード 4）、種は焼く前に断る（理由 D）。
case("min に 2147483647（言う）", """table ch = (0,32)
field x : min bound 4
x[i] <- 2147483647   for (i) in 0 .. 2
""", exit=4)
case("足して印に届く（言う）", """table ch = (0,32)
field y : max bound 4
field x : min bound 4
y[0] <- 2147483646
x[i] <- y[0] + 1   for (i) in 0 .. 2
""", exit=4)
case("flat に 2147483646（言う）", """table ch = (0,32)
field g : flat bound 4
g[i] <- 2147483646   for (i) in 0 .. 1
""", exit=4)
case("max に -2147483647（言う）", """table ch = (0,32)
field y : max bound 4
y[i] <- 0 - 2147483647   for (i) in 0 .. 1
""", exit=4)
case("min ← max の写し（言う）", """table ch = (0,32)
field y : max bound 4
field x : min bound 4
y[0] <- 2147483647
x[i] <- y[0]   for (i) in 0 .. 0
""", exit=4)
case("flat ← min の写し（言う）", """table ch = (0,32)
field y : min bound 4
field g : flat bound 4
y[0] <- 2147483646
g[i] <- y[0]   for (i) in 0 .. 0
""", exit=4)
case("min の種が印（言う）", """table ch = (0,32)
field x : min bound 4
x[0] <- 2147483647
""", data=b"ab", exit=7, why=(3,13))
case("flat の種が ⊤ の印（言う）", """table ch = (0,32)
field g : flat bound 4
g[0] <- 2147483646
""", data=b"ab", exit=7, why=(3,13))
case("flat の写しは ⊤ を運ぶ", """table ch = (0,32)
field g : flat bound 4
g[0] <- 1   for (i,c) in ch if c == 97
g[0] <- 2   for (i,c) in ch if c == 98
field y : flat bound 4
y[0] <- g[0]   for (i) in 0 .. 0
""", data=b"ab")
case("印の隣は通る", """table ch = (0,32)
field x : min bound 4
field y : max bound 4
x[i] <- 2147483646   for (i) in 0 .. 1
y[i] <- 0 - 2147483646   for (i) in 0 .. 1
y[2] <- 2147483647
""")

case("min に印を越える値（言う）", """table ch = (0,32)
field m : min bound 4
m[i] <- 2147483647 + i   for (i) in 1 .. 2
""", exit=4)
case("max に印を下回る値（言う）", """table ch = (0,32)
field y : max bound 4
y[i] <- 0 - 2147483647 - i   for (i) in 1 .. 2
""", exit=4)
case("flat は印の外の大きい値を持つ", """table ch = (0,32)
field g : flat bound 4
g[i] <- 2147483647 + i   for (i) in 1 .. 2
""")

# ══ 昇鎖が終わらない（言う）════════════════════════════════════════════════
# 最小不動点が無い（f[0] は 1, 2, 3, … と上がり続ける）。前は焼いた側が回り続けた（答えないが
# 断りもしない）。周回が上限（16,777,216）を越えたら止まって言う（終了コード 11）。
case("昇鎖が終わらない（言う）", """table ch = (0,32)
field f : max bound 4
f[0] <- 1
f[z] <- f[z] + 1   for (z) in 0 .. 0
""", exit=11)

# ══ 描く値はバイト（言う）════════════════════════════════════════════════
# 前は下位の八ビットだけを書いた —— 300 が 44、-1 が 255 になった（解釈実行は 300 を
# 文字として持ち、負は飛ばす）。0..255 の外で止まる（終了コード 2）。
case("描く値が 255 を超える（言う）", """table ch = (0,32)
field out : max bound 8
out[i] <- i * 100   for (i) in 0 .. 4
render out
""", exit=2)
case("描く値が負（言う）", """table ch = (0,32)
field out : max bound 8
out[i] <- 0 - i   for (i) in 0 .. 3
render out
""", exit=2)

# **render は書いた順に全部描く**（解釈実行と同じ）。前は二つ目を理由 8 で断っていた
# （その前は場の番号の大きい方だけを黙って描いていた）。同じ場を二度描くのも、⊥ を 0 に
# 置いた大きい場（xor で読む）も、並びの通りに出る。九つ目からは断る。
case("render が二つ（書いた順）", """table ch = (0,32)
field a : max bound 4
field b : max bound 4
a[i] <- 65   for (i) in 0 .. 1
b[i] <- 66   for (i) in 0 .. 1
render b
render a
""")
case("render が三つ（同じ場を二度・大きい min）", """table ch = (0,32)
field a : max bound 4
field b : min bound 70000
a[i] <- 65 + i   for (i) in 0 .. 3
b[i] <- 120 - i  for (i) in 0 .. 2
b[69999] <- 10
render b
render a
render b
""")
case("render が九つ（言う）", """table ch = (0,32)
field a : max bound 4
a[0] <- 65
render a
render a
render a
render a
render a
render a
render a
render a
render a
""", exit=7, why=(12,8))

# ══ 同じ升の種は join する（test/progs.py が撒いて出した）════════════════
# 種は升に値を直に置くので、後の種が前の種を上書きしていた —— min の 7 と 9 が 9、
# flat の 1 と 2 が 2（解釈実行は ⊤）、count の二つが一つ、sum の二つが後の値。
case("同じ升の種（六つの束）", """table ch = (0,32)
field m : min bound 4
field x : max bound 4
field g : flat bound 4
field s : sum bound 4
field c : count bound 4
m[1] <- 7
m[1] <- 9
x[1] <- 3
x[1] <- 8
x[1] <- 5
g[1] <- 3
g[1] <- 3
g[2] <- 1
g[2] <- 2
s[1] <- 5
s[1] <- 6
s[1] <- 5
c[1] <- 1
c[1] <- 1
c[2] <- 1
""")
case("同じ升の種が ⊤ を作り、数として読まれる（言う）", """table ch = (0,32)
field g : flat bound 4
field y : max bound 4
g[2] <- 1
g[2] <- 2
y[i] <- g[i] + 1   for (i) in 0 .. 3
""", exit=5)

# ══ 区間の上端（上端が ⊥ なら回らない・広さは言語の上限まで）══════════════
# 上端が min / flat の ⊥（2147483647）を数として読んで二十億回まわり segfault した。
# sum / count の ⊥（0）では `0 .. 0` を一度回して答えを一つ多くした。解釈実行は回さない。
case("上端が ⊥ の区間（min）は回らない", """table ch = (0,32)
field n : min bound 4
field x : count bound 4
x[0] <- 1   for (i) in 0 .. n[0]
""")
case("上端が ⊥ の区間（count）は回らない", """table ch = (0,32)
field n : count bound 4
field x : count bound 4
x[0] <- 1   for (i) in 0 .. n[0]
""")
case("上端が場の区間（min）", """table ch = (0,32)
field n : min bound 4
field x : count bound 4
n[0] <- 10
x[0] <- 1   for (i) in 3 .. n[0]
""")
# 区間の広さは言語の上限（RANGE_CAP = 4,194,304）まで。解釈実行は超えた区間を断る。
case("数の区間が上限より広い（言う）", """table ch = (0,32)
field n : count bound 4
n[0] <- 1   for (i) in 0 .. 5000000
""", exit=7, why=(3,15))
case("場の区間が上限より広い（言う）", """table ch = (0,32)
field n : max bound 4
field x : count bound 4
n[0] <- 5000000
x[0] <- 1   for (i) in 0 .. n[0]
""", exit=10)
# **面ごとに 2 GB まで**（14）。値の面 F は rbx から、階数の面 K は r10 から引くので、上限は面ごと。
case("階数の面が 2 GB を超える（値の面は超えない —— 言う）", """table ch = (0,32)
field x : or bound 40000 40000
x[i,j] <- true   for (i) in 0 .. 2 for (j) in 0 .. 1
""", exit=7, why=(0,14))
case("値の面が 2 GB を超える（言う）", """table ch = (0,32)
field x : or bound 50000 50000
field y : max bound 4
y[i] <- i + 1   for (i) in 0 .. 3
x[i,j] <- true   for (i) in 0 .. 2 for (j) in 0 .. 1
""", exit=7, why=(0,14))

# ══ 値の式の先頭の `-`（群0 の符号）══════════════════════════════════════
# 引く項は「引く命令」ではなく **群の符号**になったが、群0 の符号には置き場が無かった ——
# `-5` が 5、`-b[0] + 10` が 13、`-2 * b[0]` が 6、min / sum / flat でも同じ（全部黙って）。
case("先頭の -（六つの形）", """table ch = (0,32)
field b : max bound 4
field a : max bound 8
field m : min bound 4
field s : sum bound 4
field f : flat bound 4
b[0] <- 3
a[n] <- -5   for (n) in 0 .. 0
a[n] <- -b[0] + 10   for (n) in 1 .. 1
a[n] <- -2 * b[0]   for (n) in 2 .. 2
a[n] <- -b[0] - 1   for (n) in 3 .. 3
a[n] <- -n   for (n) in 4 .. 4
a[n] <- -b[0] * 2 + 7   for (n) in 5 .. 5
m[n] <- -5   for (n) in 0 .. 0
s[n] <- -5   for (n) in 0 .. 0
f[n] <- -b[0]   for (n) in 0 .. 0
""")
# ══ 焼く側が知らない値の形は言う（理由 8）══════════════════════════════════
# 丸括弧の中は深さ 1 で項にならず 0、`b - -1` の前の `-` と `b * -1` の `*` は黙って
# 落ちて b - 1 になっていた（解釈実行は b + 1 / -b / -b）。
for _nm, _v in [("丸括弧", "(0 - b[n])"), ("丸括弧の前の -", "-(b[n])"),
                ("演算子の後ろの -", "b[n] - -1"), ("掛けるの後ろの -", "b[n] * -1"),
                ("終わりの演算子", "b[n] +"), ("先頭の *", "* b[n]"), ("項が並ぶ", "b[n] b[n]")]:
    case("値の形: " + _nm + "（言う）", """table ch = (0,32)
field b : max bound 4
field c : max bound 4
b[0] <- 3
c[n] <- %s   for (n) in 0 .. 0
""" % _v, exit=7, why=(5, 8))
# ══ 大きい二のべきで割る・余りを取る ══════════════════════════════════════
# `and rax, imm32` の即値は符号拡張されるので、2^32 以上の法は -1（全部の桁）になり、
# 余りを取らずに素通しした（`c % 4294967296` が c のまま）。二のべきの表は 2^36 で
# 止まっていて、2^40 で割る源を「二のべきでない除数」と嘘の理由で断っていた。
case("大きい二のべき（割る・余り）", """table ch = (0,32)
field a : max bound 2
field c : flat bound 2
field r : flat bound 8
a[0] <- 2000000000
c[i] <- a[i] * 8 + 5   for (i) in 0 .. 0
r[i] <- c[0] % 2147483648   for (i) in 0 .. 0
r[i] <- c[0] % 4294967296   for (i) in 1 .. 1
r[i] <- c[0] % 8589934592   for (i) in 2 .. 2
r[i] <- c[0] / 4294967296   for (i) in 3 .. 3
r[i] <- c[0] / 1099511627776   for (i) in 4 .. 4
r[i] <- c[0] % 4611686018427387904   for (i) in 5 .. 5
r[i] <- 0 - c[0] % 4294967296   for (i) in 6 .. 6
r[i] <- c[0] % 1099511627776 - c[0] / 1099511627776   for (i) in 7 .. 7
""")
case("大きい二のべき（負の数）", """table ch = (0,32)
field a : max bound 2
field c : flat bound 2
field r : flat bound 4
a[0] <- 2000000000
c[i] <- 0 - a[i] * 8 - 5   for (i) in 0 .. 0
r[i] <- c[0] % 4294967296   for (i) in 0 .. 0
r[i] <- c[0] / 4294967296   for (i) in 1 .. 1
r[i] <- c[0] % 1099511627776   for (i) in 2 .. 2
r[i] <- c[0] / 4611686018427387904   for (i) in 3 .. 3
""")
# ══ 64 ビットに収まらない数（理由 C）══════════════════════════════════════
# 前は焼き手自身が桁を積む所で溢れ、終了コード 3 で止まって行を言えなかった。
case("2^63 で割る（言う）", """table ch = (0,32)
field a : max bound 2
field b : max bound 2
a[0] <- 5
b[i] <- a[i] / 9223372036854775808   for (i) in 0 .. 0
""", exit=7, why=(5, 12))
case("二十桁の種（言う）", """table ch = (0,32)
field a : max bound 2
a[0] <- 99999999999999999999
""", exit=7, why=(3, 12))
case("2^63 - 1 で割る（即値に入らない。言う）", """table ch = (0,32)
field a : max bound 2
field b : max bound 2
a[0] <- 5
b[i] <- a[i] / 9223372036854775807   for (i) in 0 .. 0
""", exit=7, why=(5, 5))
# ══ 単項の `-` は最初の項に掛かる ═══════════════════════════════════════
# 解釈実行の単項の `-` は `*` `/` `%` より強い: `- i % 4` は (-i) % 4、`-i / 2` は (-i) / 2。
case("単項の - の強さ", """table ch = (0,32)
field r : flat bound 16
field q : flat bound 16
field b : max bound 4
b[0] <- 7
r[i] <- - i % 4   for (i) in 0 .. 9
q[i] <- -i / 2   for (i) in 0 .. 5
q[i] <- -b[0] % 4 * 2 - 1   for (i) in 6 .. 6
""")
# ══ 座標の語を数える（理由 8）════════════════════════════════════════════
# 座標は次元ごとに「添字一つ ± 数」しか持たないのに、残りの語を黙って読み飛ばしていた。
for _nm, _co in [("掛ける", "i*2"), ("前に数", "2*i"), ("割る", "i/2"), ("余り", "i%2"),
                 ("変数を足す", "i+i"), ("ずれ二つ", "i-1+1"), ("数 + 変数", "1+i"),
                 ("読みを足す", "i+b[0]"), ("読みを掛ける", "b[i]*2")]:
    case("座標の形: " + _nm + "（言う）", """table ch = (0,32)
field b : max bound 16
field c : max bound 16
b[0] <- 1
c[n] <- 10 + n   for (n) in 0 .. 3
field a : max bound 16
a[i] <- c[%s]   for (i) in 0 .. 3
""" % _co, exit=7, why=(7, 8))
# ══ 座標のずれは -128 から +127 まで ═══════════════════════════════════════
# ずれは `add r9, imm8` の一バイト（符号つき）。前は「255 まで」を通していて、`c[i+200]` は
# c[i-56] を読んで黙って ⊥、`c[i-200]` は c[i+56] を読んで **違う数**を答えた。
case("座標のずれの境（通る）", """table ch = (0,32)
field c : max bound 512
c[n] <- n   for (n) in 0 .. 511
field a : max bound 512
a[i] <- c[i-128] + c[i+127]   for (i) in 200 .. 203
""")
for _nm, _co in [("+128", "i+128"), ("+200", "i+200"), ("-129", "i-129"), ("-200", "i-200")]:
    case("座標のずれ " + _nm + "（言う）", """table ch = (0,32)
field c : max bound 512
c[n] <- n   for (n) in 0 .. 511
field a : max bound 512
a[i] <- c[%s]   for (i) in 200 .. 203
""" % _co, exit=7, why=(5, 8))
case("座標の形: 読みのずれと空白（通る）", """table ch = (0,32)
field b : max bound 16
field c : max bound 16
b[i] <- i + 1   for (i) in 0 .. 3
c[n] <- 10 + n   for (n) in 0 .. 4
field a : max bound 16
a[i] <- c[b[i]-1] + c[i + 1]   for (i) in 0 .. 3
""")
# ══ ガードの語を数える（理由 8）══════════════════════════════════════════
# `if not not x` は答えが裏返り、`if b > 2 3` / `if b = 2` / `if b <> 2` / `if x x` / `if b > 1 > 0` は
# 解釈実行が構文で断るのに、焼いた側は答えた。
for _nm, _g in [("not が二つ", "if not not x[n]"), ("後ろに数", "if b[n] > 2 3"), ("= 一つ", "if b[n] = 2"),
                ("<>", "if b[n] <> 2"), ("読みが二つ", "if x[n] x[n]"), ("比較が二つ", "if b[n] > 1 > 0")]:
    case("ガードの形: " + _nm + "（言う）", """table ch = (0,32)
field b : max bound 8
field x : or bound 8
field c : max bound 8
b[0] <- 1
x[1] <- true
c[n] <- 5   for (n) in 0 .. 3 %s
""" % _g, exit=7, why=(7, 8))
# ══ for 節・頭・種の語を数える（理由 8）══════════════════════════════════
for _nm, _f in [("後ろに数", "for (n) in 0 .. 3 4"), ("区間が二つ", "for (n) in 0 .. 3 .. 5"),
                ("区間に変数二つ", "for (n, m) in 0 .. 3"), ("下端が読み", "for (n) in b[0] .. 3"),
                ("in が二つ", "for (n) in 0 .. 3 in 5"), ("括弧の中に空白の並び", "for (n c) in ch"),
                ("括弧で包んだ表", "for (n,c) in (ch)"), ("無い表", "for (n,c) in xyz"),
                ("表の名が無い", "for (n,c) in"), ("上端の添字にずれ", "for (n) in 0 .. b[0+1]"),
                ("for の無い in", "(n) in 0 .. 3")]:
    case("for の形: " + _nm + "（言う）", """table ch = (0,32)
field b : max bound 8
field c : max bound 300
b[0] <- 1
c[n] <- 5   %s
""" % _f, exit=7, why=(5, 8))
# ══ 表の for の束ねる数と、表の幅 ═════════════════════════════════════════
# 束ねる数が列の数と違うと、焼いた側はそれを行の幅にして行を読み違えた（解釈実行は断る）。
# 16 列の表は行の幅 128 が一バイトのずれで負に化け、前へ歩いた。
case("束ねる数が列より少ない（言う）", """table t = (0,0,0,0,0,0)
field a : max bound 64
a[c0] <- c1   for (c0,c1) in t
""", rows=[(0,1,2,3,4,5),(1,11,12,13,14,15)], exit=7, why=(3, 8))
case("束ねる数が列より多い（言う）", """table t = (0,0,0)
field a : max bound 64
a[c0] <- c1   for (c0,c1,c2,c3) in t
""", rows=[(0,1,2),(1,11,12)], exit=7, why=(3, 8))
case("十五列の表（通る）", """table t = (0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
field a : max bound 64
a[c0] <- c1   for (c0,c1,c2,c3,c4,c5,c6,c7,c8,c9,ca,cb,cc,cd,ce) in t
""", rows=[tuple([r] + [100*r + k for k in range(1, 15)]) for r in range(3)])
case("十六列の表（言う）", """table t = (0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
field a : max bound 64
a[c0] <- c1   for (c0,c1,c2,c3,c4,c5,c6,c7,c8,c9,ca,cb,cc,cd,ce,cf) in t
""", rows=[tuple([r] + [100*r + k for k in range(1, 16)]) for r in range(3)], exit=7, why=(1, 8))
case("頭の余分な語（言う）", """table ch = (0,32)
field b : max bound 8
b[i]  not <- 0   for (i) in 0 .. 3
""", exit=7, why=(3, 8))
case("種の値が二語（言う）", """table ch = (0,32)
field s : max bound 16
s[0] <- 3 0
""", exit=7, why=(3, 8))
case("値の無い規則（言う）", """table ch = (0,32)
field brk : or bound 256
brk[i] <-    for (i,c) in ch if i >= 0
""", exit=7, why=(3, 8))

# ══ 入力の口（言う）═════════════════════════════════════════════════════
# 置き場（生バイトなら 983,040 バイト）を超える入力を **黙って切っていた**（数えると
# 983040 で止まった）。語の列が行の途中で切れていると、0 で埋めた一行として読んでいた。
# ちょうどは終了コードだけ見る（解釈実行に百万行は重い）。切られていないことは、
# 一つ多い入力が 6 で止まることで測る。
case("入力が置き場ちょうど（通る）", """table ch = (0,32)
field n : count bound 4
n[0] <- 1   for (i,c) in ch
""", data=b"a" * 983040, exit=0)
case("入力が置き場を超える（言う）", """table ch = (0,32)
field n : count bound 4
n[0] <- 1   for (i,c) in ch
""", data=b"a" * 983041, exit=6)
case("行の途中で切れる（言う）", """table edges = (0,0,0)
field n : count bound 4
n[0] <- 1   for (i,j,w) in edges
""", data=b"\x01" * 24 + b"\x07" * 6, exit=8)

# ══ 64 ビットの溢れ（言う）═════════════════════════════════════════════
# 解釈実行は多倍長で持つ。焼いた符号は 64 ビットで持ち、掛け算・足し引き・sum の join の
# 直後に溢れ（OF）を見て止まる（終了コード 3・場の番号つき）。途中の値が溢れても止まる。
case("掛けて溢れる（言う）", """table ch = (0,32)
field x : max bound 64
x[0] <- 1
x[i] <- x[i-1] * 3   for (i) in 1 .. 50
""", exit=3)
case("足して溢れる（言う）", """table ch = (0,32)
field x : max bound 64
field y : max bound 4
x[0] <- 1
x[i] <- x[i-1] * 2   for (i) in 1 .. 62
y[0] <- x[62] + x[62]   for (i) in 0 .. 0
""", exit=3)
case("sum が溢れる（言う）", """table ch = (0,32)
field x : max bound 64
field s : sum bound 4
x[0] <- 1
x[i] <- x[i-1] * 2   for (i) in 1 .. 62
s[0] <- x[62]   for (i) in 0 .. 1
""", exit=3)
case("途中で溢れる（言う）", """table ch = (0,32)
field x : max bound 64
field y : max bound 4
x[0] <- 1
x[i] <- x[i-1] * 2   for (i) in 1 .. 62
y[i] <- x[62] * 2 / 4   for (i) in 0 .. 0
""", exit=3)
case("2^62 まで（通る）", """table ch = (0,32)
field x : max bound 64
x[0] <- 1
x[i] <- x[i-1] * 2   for (i) in 1 .. 62
""")
case("溢れない掛け算（通る）", """table ch = (0,32)
field x : max bound 64
field y : max bound 64
x[0] <- 1
x[i] <- x[i-1] * 2   for (i) in 1 .. 61
y[i] <- x[61] * i   for (i) in 0 .. 3
""")

# ══ 座標の入れ子（test/coords.py が撒いて出した）══════════════════════════
# 内側の二次元の読みの次元1 は、畳む前にその次元の広さで濾す（前は次の行の升を読んだ）。
case("内側の次元1 を濾す", """table ch = (0,32)
field k : max bound 8
field h : max bound 8
field g : max bound 4 4
field x : max bound 16
k[i] <- i + 1   for (i) in 0 .. 3
h[i] <- 7 - i   for (i) in 0 .. 6
g[i,j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
x[j] <- h[g[i, j]]   for (i) in 1 .. 1 for (j) in 0 .. 6
""")
case("内側の次元1 のずれ", """table ch = (0,32)
field k : max bound 8
field h : max bound 8
field g : max bound 4 4
field x : max bound 16
k[i] <- i + 1   for (i) in 0 .. 3
h[i] <- 7 - i   for (i) in 0 .. 6
g[i,j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
x[i] <- k[g[i+2, i+1]]   for (i) in 0 .. 4
""")
case("内側が二次元なら後置は外のもの", """table ch = (0,32)
field k : max bound 8
field h : max bound 8
field g : max bound 4 4
field x : max bound 16
k[i] <- i + 1   for (i) in 0 .. 3
h[i] <- 7 - i   for (i) in 0 .. 6
g[i,j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
x[i] <- g[g[j+1, j] - 1, j] + 1   for (i) in 0 .. 4 for (j) in 0 .. 2
""")
case("内側の次元1 に読み（言う）", """table ch = (0,32)
field k : max bound 8
field h : max bound 8
field g : max bound 4 4
field x : max bound 16
k[i] <- i + 1   for (i) in 0 .. 3
h[i] <- 7 - i   for (i) in 0 .. 6
g[i,j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
x[i] <- h[g[i, k[i]]]   for (i) in 0 .. 2
""", exit=7, why=(9,8))
case("内側の次元1 に定数の読み（言う）", """table ch = (0,32)
field k : max bound 8
field h : max bound 8
field g : max bound 4 4
field x : max bound 16
k[i] <- i + 1   for (i) in 0 .. 3
h[i] <- 7 - i   for (i) in 0 .. 6
g[i,j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
x[i] <- h[g[i, k[0]]]   for (i) in 2 .. 2
""", exit=7, why=(9,8))
case("前置と後置のずれ（言う）", """table ch = (0,32)
field k : max bound 8
field h : max bound 8
field g : max bound 4 4
field x : max bound 16
k[i] <- i + 1   for (i) in 0 .. 3
h[i] <- 7 - i   for (i) in 0 .. 6
g[i,j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
x[i] <- k[k[i+1] - 1]   for (i) in 0 .. 4
""", exit=7, why=(9,8))

case("広さを超える（言う）", """table ch = (0,32)
field s : max bound 4
s[i] <- i   for (i) in 0 .. 9
""", exit=6)


case("render（大文字にして出す）", """table ch = (0,32)
field out : min bound 4096
out[i] <- c        for (i,c) in ch
out[i] <- c - 32   for (i,c) in ch if c >= 97 if c <= 122
render out
""", data=b'hello lattix 2026')
# **十進で出す。** 二のべきでしか割れないが、逆数を掛けて 2^32 で寄せれば
# 桁は出る（`examples/34_decimal.lx`）。焼いた符号と解釈実行がバイトで合う。
case("十進で出す（逆数を掛ける）", """table ch = (0,32)
field tri : max bound 16
tri[0] <- 0
tri[i] <- tri[i-1] + i               for (i) in 1 .. 15
field hun : max bound 16
hun[i] <- tri[i] * 42949673 / 4294967296    for (i) in 0 .. 15
field ten : max bound 16
ten[i] <- tri[i] * 429496730 / 4294967296   for (i) in 0 .. 15
field h10 : max bound 16
h10[i] <- hun[i] * 10                for (i) in 0 .. 15
field t10 : max bound 16
t10[i] <- ten[i] * 10                for (i) in 0 .. 15
field pos : max bound 16
pos[i] <- i * 4                      for (i) in 0 .. 15
field out : max bound 64
out[pos[i]]     <- hun[i] + 48       for (i) in 0 .. 15
out[pos[i] + 1] <- ten[i] - h10[i] + 48   for (i) in 0 .. 15
out[pos[i] + 2] <- tri[i] - t10[i] + 48   for (i) in 0 .. 15
out[pos[i] + 3] <- 10                for (i) in 0 .. 15
render out
""", data=b'x')
case("render（穴のある場）", """table ch = (0,32)
field out : min bound 4096
out[i] <- c        for (i,c) in ch if c != 32
render out
""", data=b'a b c d')


case(".lx ですらない（言う）", """this is not a lattix program at all
""", exit=7, why=(0,6))
case("途中で切れている（言う）", """table ch = (0,32)
field f : max bound 8
f[i] <- c for (i,c) in
""", exit=7, why=(3,8))
case("宣言の無い場を読む（言う）", """table ch = (0,32)
field f : max bound 8
f[i] <- g[i] for (i,c) in ch
""", exit=7, why=(3,4))

W=76
def widths(src):
    order=[]; bnd={}; lat={}
    for ln in src.split('\n'):
        m=re.match(r'^field (\w+) : (\w+)(?: bound ([0-9 ]+))?\s*(?:#.*)?$', ln.split('#')[0].strip())
        if m:
            order.append(m.group(1)); lat[m.group(1)]=m.group(2)
            bnd[m.group(1)]=[int(x) for x in (m.group(3) or '64').split()]
    # **括弧は regex で数えられない。** `[^\]]*` は最初の `]` で止まるので、
    # `r[q[i,k]]` の添字を `q[i,k` と読み、`r` を二次元だと言っていた ——
    # 置き場の総和が合わず、生成器の側が悪いように見えた。括弧は **数える**。
    ar=collections.defaultdict(lambda:1)
    for ln in src.split('\n'):
        ln=ln.split('#')[0]
        for m in re.finditer(r'(\w+)\[', ln):
            if m.group(1) not in bnd: continue
            d=0; j=m.end()-1; k=j
            while k < len(ln):
                if ln[k]=='[': d+=1
                elif ln[k]==']':
                    d-=1
                    if d==0: break
                k+=1
            ix=ln[j+1:k]
            nd=1
            d=0
            for ch in ix:
                if ch=='[': d+=1
                elif ch==']': d-=1
                elif ch==',' and d==0: nd+=1
            ar[m.group(1)]=max(ar[m.group(1)], nd)
    # **升の幅は束が言う**（31_gen の `fwb` と同じ規則）—— `or` は 0 か 1 しか
    # 取らないので一升 1 バイト。
    off={}; o=0
    for f in order:
        b=bnd[f]; w0=b[0]; w1=b[1] if len(b)>1 else w0; w2=b[2] if len(b)>2 else w0
        # 三次元は (広さ1, 広さ2) の組で持つ（書かない次元の広さは次元0 と同じ —— 前段の fwid2 / fwid3）
        if ar[f]==3: cells=w0*w1*w2; kw=(w1,w2)
        elif ar[f]==2: cells=w0*w1; kw=w1
        else: cells=w0; kw=1
        wb=1 if lat[f]=='or' else 8
        off[f]=(o,cells,kw,wb); o+=cells*wb
    return order, lat, off, o

def cellkey(i, w1):
    """升の通し番号 → 座標（w1 は広さ1、三次元なら (広さ1, 広さ2)）"""
    if isinstance(w1, tuple): return (i // (w1[0] * w1[1]), (i // w1[1]) % w1[0], i % w1[1])
    return (i // w1, i % w1) if w1 > 1 else (i,)

BOT={'min':2147483647,'max':-2147483647,'or':0,'flat':2147483647,'sum':0,'count':0}
tmp=tempfile.mkdtemp()
import atexit, shutil; atexit.register(shutil.rmtree, tmp, True)   # 焼いた物は走り終えたら消す
print("="*W); print("  **使う側の試験** —— ./lattix で焼いて走らせ、解釈実行と升まで比べる"); print("="*W)
print(f"  {'例':<26}{'焼き':>6}{'升':>6}   一致"); print("-"*W)
bad=[]
for k,(name,src,data,rows,xexit,known,why) in enumerate(CASES):
    exe=os.path.join(tmp,f"a{k}.out")
    r=subprocess.run([LATTIX], input=src.encode(), capture_output=True)
    if r.returncode or r.stdout[:4]!=b'\x7fELF':
        print(f"  {name:<26}焼けなかった rc={r.returncode}"); bad.append((name,'焼けない')); continue
    open(exe,'wb').write(r.stdout); os.chmod(exe,0o755)
    inp = data if rows is None else b''.join(struct.pack('<'+'q'*len(t),*t) for t in rows)
    r2=subprocess.run([exe], input=inp, capture_output=True)
    if xexit is not None:                    # **黙って間違えない**（言うはず）
        good = (r2.returncode == xexit); note = f"終了コード {r2.returncode}"
        if why is not None:                  # **どこを直すか**まで言うはず
            m = re.search(rb'lattix: cannot bake - line (\d{6}) reason ([0-9A-F]): (.{16})\n', r2.stderr)
            got = (int(m.group(1)), int(m.group(2), 16)) if m else None
            note = f"{got[0]:06d}:{got[1]} {m.group(3).decode().strip()}" if got else "知らせ無し"
            good = good and (got == why)
        print(f"  {name:<26}{len(src):>6}{'':>6}   {'✓' if good else '✗'}  （{note}）")
        if not good: bad.append((name, note))
        continue
    if 'render ' in src:                     # **バイトを比べる**（升ではない）
        try:
            p=L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
        except Exception as ex:
            print(f"  {name:<26}解釈実行が受け取らない: {str(ex)[:40]}")
            bad.append((name,'試験の側の誤り')); continue
        tname=[t for t in p.tables][0]
        p.tables[tname]=[(i,c) for i,c in enumerate(inp)] if rows is None else list(rows)
        st,_,_=L.run(p, out=io.StringIO())
        want=b''.join(L.render_text(p, st, f).encode('latin-1','replace') for f in p.renders)
        good = (r2.stdout == want)
        print(f"  {name:<26}{len(src):>6}{len(want):>6}   {'✓' if good else '✗'}")
        if not good: bad.append((name, f"出た {r2.stdout[:24]!r} / 待った {want[:24]!r}"))
        continue
    order, lat, off, tot = widths(src)
    plane=r2.stdout
    if len(plane)!=tot:
        print(f"  {name:<26}升の並びが合わない（{len(plane)} != {tot}）"); bad.append((name,'置き場')); continue
    got={}
    for f in order:
        o,cells,w1,wb=off[f]; bot=BOT[lat[f]]
        for i in range(cells):
            v=struct.unpack_from('<q' if wb==8 else '<B',plane,o+wb*i)[0]
            if v!=bot:
                key=cellkey(i,w1)
                got[(f,)+key]=v
    # 解釈実行（表は同じデータを行にして渡す）
    try:
        p=L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    except Exception as ex:
        print(f"  {name:<26}解釈実行が受け取らない: {str(ex)[:40]}")
        bad.append((name, '試験の側の誤り')); continue
    tname=[t for t in p.tables][0]
    if rows is None: p.tables[tname]=[(i,c) for i,c in enumerate(inp)] if inp else [(0,32)]
    else: p.tables[tname]=list(rows)
    ref_raw,_,_=L.run(p, out=io.StringIO())
    ref={}
    for f,d in ref_raw.items():
        latf=p.fields[f].name
        for kk,v in d.items():
            if v is True: v=1
            if v is False: continue
            if isinstance(v, dict):        # sum / count は寄与の袋で持っている
                v = sum(v.values()) if latf=='sum' else len(v)
                if latf == 'sum' and v == 0: continue   # SPEC: ⊥ が 0 の束では 0 は ⊥（打ち消し合った和も）
            if isinstance(v, (set, frozenset)): continue
            if not isinstance(v, int): v = 2147483646     # flat の ⊤
            ref[(f,)+tuple(kk)]=v
    same = got==ref
    if not same and known:
        print(f"  {name:<26}{len(src):>6}{len(got):>6}   —  （既知の穴）"); continue
    if not same:
        og=sorted(set(got)-set(ref))[:2]; orr=sorted(set(ref)-set(got))[:2]
        dv=[x for x in sorted(set(got)&set(ref)) if got[x]!=ref[x]][:2]
        bad.append((name, f"焼のみ{og} 解釈のみ{orr} 値違い{[(x,ref[x],got[x]) for x in dv]}"))
    print(f"  {name:<26}{len(src):>6}{len(got):>6}   {'✓' if same else '✗'}")
print("-"*W)
for n,d in bad: print(f"  ✗ {n}: {d}")
print(f"  {len(CASES)-len(bad)} / {len(CASES)} 一致")
if bad: sys.exit(1)     # 外れがあれば終了コードでも言う（組の試験は rc しか見ない。気づき29）
