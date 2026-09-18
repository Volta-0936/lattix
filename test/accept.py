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
# （出力 23 バイト、終了コード 0）。260KB の源が通ることを試験に置く。
case("260KB の源（宣言の内側）", """table ch = (0,32)
field big : or bound 64
big[i] <- true for (i,c) in ch if c >= 97
""" + "\n".join("# %d ------------------------------------------------------" % i
                for i in range(4200)) + "\n", data=b"abc")
# **入れ子は三重まで**（計数器は rcx / r13 / r14 の三本）。四重目は
# 黙って壊れた符号になっていた —— いまは焼かずに言う。
case("入れ子 三重（通る）", """table ch = (0,32)
field a : max bound 16
a[k] <- 1   for (k) in 0 .. 1 for (m) in 0 .. 1 for (n) in 0 .. 1
""", data=b"ab")
case("入れ子 四重（焼けない）", """table ch = (0,32)
field a : max bound 16
a[k] <- 1   for (k) in 0 .. 1 for (m) in 0 .. 1 for (n) in 0 .. 1 for (p) in 0 .. 1
""", data=b"ab", exit=7, why=(3,2))
# **項は八つまで。** 九つ目は隣の文の枠を踏んで、答えが黙って変わっていた。
case("項 八つ（通る）", """table ch = (0,32)
field a : max bound 16
a[i] <- 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1   for (i,c) in ch
""", data=b"ab")
case("項 九つ（焼けない）", """table ch = (0,32)
field a : max bound 16
a[i] <- 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1   for (i,c) in ch
""", data=b"ab", exit=7, why=(3,3))
# **二のべきでない除数は焼けない。** `c / 3` は寄せ量が出ずに割り算が消え、
# `c % 3` は `and rax,2` になって別の答えを出していた —— どちらも黙って。
case("割る・余り（二のべき）", """table ch = (0,32)
field q : max bound 8
q[i] <- c / 4   for (i,c) in ch
field r : max bound 8
r[i] <- c % 8   for (i,c) in ch
""", data=b"ab")
case("三で割る（焼けない）", """table ch = (0,32)
field q : max bound 8
q[i] <- c / 3   for (i,c) in ch
""", data=b"ab", exit=7, why=(3,5))
case("三で割った余り（焼けない）", """table ch = (0,32)
field r : max bound 8
r[i] <- c % 3   for (i,c) in ch
""", data=b"ab", exit=7, why=(3,5))
# **行と理由は対でなければ意味が無い。** 別々の min で選ぶと、行は一方の
# 最小・理由は他方の最小になって、**指した行にその理由が無い**ことが起きる。
# 一つの鍵（行 * 16 + 理由）に畳んであるので、二つ誤りを置いて確かめる。
case("二つの誤り（先が出る）", """table ch = (0,32)
field abcdefghijklmnopq : max bound 16
abcdefghijklmnopq[i] <- 1 for (i,c) in ch
field q : max bound 8
q[i] <- c / 3   for (i,c) in ch
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
q[i] <- c / 3   for (i,c) in ch
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
# 解釈実行は掛け算を先にする（`1+2*3 = 7`）—— 同じ言葉が二つの答えを
# 持っていた。黙って違う答えを出すくらいなら言う（終了コード 7）。
case("足してから掛ける（焼けない）", """table edges = (0,0,0)
field a : max bound 16
a[i] <- j + w * 3   for (i,j,w) in edges
""", rows=[(0,1,2)], exit=7, why=(3,7))
case("変数で割る（焼けない）", """table edges = (0,0,0)
field q : max bound 16
q[i] <- j / w   for (i,j,w) in edges
""", rows=[(0,4,2)], exit=7, why=(3,8))
case("三段の読み（焼けない）", """table edges = (0,0,0)
field a : max bound 16
a[i] <- j   for (i,j,w) in edges
field c : max bound 16
c[i] <- a[a[a[i]]]   for (i,j,w) in edges
""", rows=[(0,1,1),(1,2,1)], exit=7, why=(5,8))
case("表が二つ（焼けない）", """table a = (0,0)
table b = (0,0,0)
field f : max bound 16
f[i] <- c   for (i,c) in a
""", data=b'xy', exit=7, why=(0,6))
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
    ar=collections.defaultdict(lambda:1)
    for ln in src.split('\n'):
        for m in re.finditer(r'(\w+)\[([^\]]*)\]', ln.split('#')[0]):
            if m.group(1) in bnd: ar[m.group(1)]=max(ar[m.group(1)], 1+m.group(2).count(','))
    # **升の幅は束が言う**（31_gen の `fwb` と同じ規則）—— `or` は 0 か 1 しか
    # 取らないので一升 1 バイト。
    off={}; o=0
    for f in order:
        b=bnd[f]; w0=b[0]; w1=b[1] if len(b)>1 else w0
        cells=w0*w1 if ar[f]==2 else w0
        wb=1 if lat[f]=='or' else 8
        off[f]=(o,cells,w1 if ar[f]==2 else 1,wb); o+=cells*wb
    return order, lat, off, o

BOT={'min':2147483647,'max':-2147483647,'or':0,'flat':2147483647,'sum':0,'count':0}
tmp=tempfile.mkdtemp()
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
            m = re.search(rb'lattix: cannot bake - line (\d{6}) reason (\d): (.{16})\n', r2.stderr)
            got = (int(m.group(1)), int(m.group(2))) if m else None
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
        want=L.render_text(p, st, p.renders[0]).encode('latin-1','replace')
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
                key=(i//w1,i%w1) if w1>1 else (i,)
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
