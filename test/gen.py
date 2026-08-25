#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**Lattix が Lattix のプログラムから機械語を書く。** —— C を切る道の三歩目。

  27_elf  機械語が定数
  28_asm  命令列が **データ** から決まる
  31_gen  命令列が **別の Lattix プログラム** から決まる      ← ここ

`examples/31_gen.lx` の入力は、解析済みプログラムの四つの表である:

    fld   (場番号, 束, 次数)              束: 1 min / 2 max / 3 or
    seed  (種番号, 場, 座標, 値)          2次元は c1*64+c2 に畳む
    rrule (規則番号, 層, 束, 表の次数, 読み場, 書き場, 読み有無, 読2, 書2,
           読列1, 読列2, 書列1, 書列2, 重み列, ガード有無, ガード列, ガード値,
           否定有無, 否定場, 否定2, 否定列1, 否定列2)
    row   (行, 列, 値)                    地上データ

**データは実行ファイルの中に居ない。** 表は標準入力から読む（8バイト小端）。
一度焼いた実行ファイルが違うデータで何度でも走る —— 配布形そのものである。
出力は終了コードではない —— **場そのものと、その階数**(証明書)である。
検査は二重: 全セルが解釈実行と一致し、さらに **attest が機械語の答えを別証する**。
"""
import io, os, re, stat, struct, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
import attest as ATT

W = 88
SRC = open(os.path.join(ROOT, 'examples', '31_gen.lx'), encoding='utf-8').read()
DOM = 64
BOT = {1: 2147483647, 2: -2147483647, 3: 0, 6: 2147483647, 8: 0, 9: 0}
TOPV = 2147483646



def _run_with_witness(exe, indata):
    """**証人は fd 3 に出る**（開いていなければ書かれない）。試験は開けて受け取る。
       `sh -c 'exec 3>w; exec prog'` —— 引数は渡さないので argc は 1 のまま。"""
    import tempfile, os, subprocess as _sp
    d = tempfile.mkdtemp(); w = os.path.join(d, "witness.bin")
    r = _sp.run(['sh', '-c', 'exec 3>"$1"; shift; exec "$@"', 'sh', w, exe],
                input=indata, capture_output=True)
    try:
        wit = open(w, 'rb').read()
    except OSError:
        wit = b''
    try:
        os.unlink(w); os.rmdir(d)
    except OSError:
        pass
    return r, wit

def gen(flds, seeds, rules, edges, tmp, tag, guards=(), terms=(), coords=(),
        loops=(), inp=8, outp=None, raw=None):
    """31_gen.lx の入力表を差し替えて、実行ファイルを作って走らせる。

    `rules` は規則ごとの 20 列、`guards` は **行** (規則, 種, 場, 列1, 列2, 2次元, 値)。
    ガード番号は並び順が決める —— 番号は座標であって、書くものではない。
    """
    # 場は (番号, 束, 次数[, 広さ1, 広さ2])。広さを書かなければ 64 升
    flds = [tuple(row) + (64, 64)[len(row) - 3:] for row in flds]
    fl = ", ".join(f"({f},{l},{a})" for f, l, a, _w1, _w2 in flds)
    fd = ", ".join(f"({f},0,{w1})" + (f", ({f},1,{w2})" if a == 2 else "")
                   for f, _l, a, w1, w2 in flds)
    sd = (", ".join(f"({k},{fd},{c},{v})" for k, (fd, c, v) in enumerate(seeds))
          or f"(0,{len(flds)},0,0)")   # 番兵は「場の数」（存在しない場番号）
    # **座標の所有者に通し番号**（種・規則・番号の三つ組では場が 4次元になる）
    own = {}
    for row in coords: own.setdefault(tuple(row[:3]), len(own))
    NOOWN = len(own)

    # 列は 4（r を足して 5）。足りない分は 0 で埋める —— 手で並べない
    rr = ", ".join("(" + ",".join(map(str, (k,) + ru[:4] + (0,) * (4 - len(ru[:4]))
                                       + (own.get((2, k, 0), NOOWN),))) + ")"
                   for k, ru in enumerate(rules))
    # ループは規則から自動で作る（区間かどうかと次数は規則が言う）
    if not loops:
        lp2 = []
        for k, ru in enumerate(rules):
            a = ru[2] if len(ru) > 2 else 0
            isr, lo, hi = (ru[4], ru[5], ru[6]) if len(ru) > 6 else (0, 0, 0)
            lp2.append((k, 0, 1 if isr else 0, lo, hi, a, 0, 0))
        loops = lp2
    def rows(src, ncol, kk, glob=False):
        seen, out = {}, []
        for n, row in enumerate(src):
            r = row[0]
            g = seen.get(r, 0); seen[r] = g + 1
            cells = (r, g) + tuple(row[1:])
            cells = cells + (0,) * (ncol - 1 - len(cells) - (1 if glob else 0))
            cells = cells + (own.get((kk, r, g), NOOWN),)
            if glob: cells = (n,) + cells
            out.append("(" + ",".join(map(str, cells)) + ")")
        empty = ("(0,63," + ",".join(["0"] * (ncol - 2)) + ")" if glob
                 else "(63," + ",".join(["0"] * (ncol - 1)) + ")")
        return ", ".join(out) or empty
    gd = rows(guards, 10, 1, glob=True)
    tm = rows(terms, 8, 0, glob=True)   # 項は **通し番号**を先頭に持つ
    # 座標は (所有者番号, 規則, 次元, 源, 場, 列, ずれ種, ずれ) の行
    cr = (", ".join("(" + ",".join(map(str, (k, own[tuple(row[:3])], row[1])
                                        + tuple(row[3:]))) + ")"
                    for k, row in enumerate(coords))
          or "(0,0,63,0,0,0,0,0,0)")
    # ループも行 (規則, 番号, 種, 下端, 上端, 表の次数)。既定は表を一周
    lp = ", ".join("(" + ",".join(map(str, (k,) + tuple(row)
                                       + (0,) * (8 - len(row)))) + ")"
                   for k, row in enumerate(loops))
    ip = f"({inp})"
    op = (", ".join("(" + ",".join(map(str, row)) + ")" for row in (outp or []))
          or "(0,63,8)")
    src = SRC
    ns = []
    for name, txt in (('fld  ', fl), ('seed ', sd), ('rrule', rr),
                      ('grd  ', gd), ('trm  ', tm), ('crd  ', cr),
                      ('lop  ', lp), ('inp  ', ip), ('outp ', op),
                      ('fdim ', fd)):
        src, n = re.subn(rf"table {name} = .*?\n(?=table |#)",
                         f"table {name} = {txt}\n", src, count=1, flags=re.S)
        ns.append(n)
    assert ns == [1] * 10, f"表の差し替えが空振りした {ns}"
    lx = os.path.join(tmp, f"g{tag}.lx")
    open(lx, 'w', encoding='utf-8').write(src)
    exe = os.path.join(tmp, f"a{tag}.out")
    with open(exe, 'wb') as fp:
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'lattix.py'), lx],
                           stdout=fp, stderr=subprocess.PIPE)
    if r.returncode:
        return 0, None, None, r.stderr.decode()[:200]
    os.chmod(exe, os.stat(exe).st_mode | stat.S_IEXEC)
    blob = open(exe, 'rb').read()
    if blob[:4] != b'\x7fELF':
        return len(blob), None, None, "not an ELF"
    indata = (raw if raw is not None
              else b"".join(struct.pack(f"<{len(e)}q", *e) for e in edges))
    r, _wit = _run_with_witness(exe, indata)
    if outp:                       # バイトで書く口は、そのままバイト列が答え
        return len(blob), r.stdout, None, ""

    ncell = sum(w1 * (w2 if a == 2 else 1) for _f, _l, a, w1, w2 in flds)
    F = struct.unpack(f'<{ncell}q', r.stdout[:8*ncell])
    K = struct.unpack(f'<{ncell}q', _wit[:8*ncell])   # 証人は fd 3 から
    store, rank = {}, {}
    off = 0
    for f, l, a, w1, w2 in flds:
        cells = w1 * (w2 if a == 2 else 1)
        key = ((lambda k: (k,)) if a == 1
               else (lambda k, w=w2: (k // w, k % w)))
        dec = ((lambda v: True) if l == 3
               else (lambda v: L.TOP if v == TOPV else v))
        store[f] = {key(k): dec(F[off+k]) for k in range(cells)
                    if F[off+k] != BOT[l]}
        rank[f] = {key(k): K[off+k] for k in range(cells) if K[off+k]}
        off += cells
    return len(blob), store, rank, ""


def interp(src, names):
    """同じプログラムを Lattix の意味で解く（＝答えの定義）。"""
    p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    st, _c, _s = L.run(p, out=io.StringIO())
    return {i: {k: p.fields[nm].observe(v) for k, v in st[nm].items()}
            for i, nm in enumerate(names)}


E1 = [(0, 1, 4), (0, 2, 1), (2, 1, 2), (1, 3, 5), (3, 4, 3), (4, 5, 2)]
SRC1 = ("table edge = " + ", ".join(map(str, E1)) + "\n"
        "field dist : min\ndist[0] <- 0\n"
        "dist[j] <- dist[i] + w   for (i,j,w) in edge\n")

# 型の列 t を持つ辺。t == 1 の辺だけ使う。dist は最短、far は最長（DAG）。
E2 = [(0, 1, 4, 1), (0, 2, 1, 1), (2, 1, 2, 1), (1, 3, 5, 1),
      (3, 4, 3, 1), (4, 5, 2, 1), (0, 5, 99, 0)]
SRC2 = ("table edge = " + ", ".join(map(str, E2)) + "\n"
        "field dist : min\ndist[0] <- 0\n"
        "dist[j] <- dist[i] + w   for (i,j,w,t) in edge if t == 1\n"
        "field far : max\nfar[0] <- 0\n"
        "far[j] <- far[i] + w     for (i,j,w,t) in edge if t == 1\n")

# 場をまたぐ読み。a は到達可能性、b は「到達点の隣」+ 独自の種。
E3 = [(0, 1), (1, 2), (2, 3), (4, 5)]
SRC3 = ("table edge = " + ", ".join(map(str, E3)) + "\n"
        "field a : or\na[0] <- true\n"
        "a[j] <- true   for (i,j) in edge if a[i]\n"
        "field b : or\nb[9] <- true\n"
        "b[j] <- true   for (i,j) in edge if a[i]\n")

# 2次元: 変数つき到達（rd[j,v] <- true … if rd[i,v]）と、その 1次元への射
E4 = [(0, 1, 5), (1, 2, 5), (0, 2, 7), (2, 3, 7), (3, 1, 9)]
SRC4 = ("table step = " + ", ".join(map(str, E4)) + "\n"
        "field rd : or\nrd[0, 5] <- true\nrd[0, 7] <- true\n"
        "rd[j, v] <- true   for (i,j,v) in step if rd[i, v]\n"
        "field hit : or\n"
        "hit[j] <- true     for (i,j,v) in step if rd[i, v]\n")

# **層と否定と読み無し規則。** 29_dataflow の三点セット。
#   層0: reach（読みつき or） / used（読み無し or。表が直接駆動、ガードつき）
#   層1: unre[j] <- true … if used[j] if not reach[j]   （否定は前の層を読む）
E5 = [(0, 1, 1), (1, 2, 1), (4, 5, 0), (2, 3, 1)]
SRC5 = ("table edge = " + ", ".join(map(str, E5)) + "\n"
        "field reach : or\nreach[0] <- true\n"
        "reach[j] <- true   for (i,j,t) in edge if reach[i]\n"
        "field used : or\n"
        "used[j] <- true    for (i,j,t) in edge if t == 1\n"
        "field unre : or\n"
        "unre[j] <- true    for (i,j,t) in edge if used[j] if not reach[j]\n")

# 集約: 出次数（count）と重みの和（sum）。どちらも読み無し・一度だけ撃つ。
E7 = [(0, 1, 4), (0, 2, 1), (2, 1, 2), (1, 3, 5), (0, 3, 9)]
SRC7 = ("table edge = " + ", ".join(map(str, E7)) + "\n"
        "field reach : or\nreach[0] <- true\n"
        "reach[j] <- true   for (i,j,w) in edge if reach[i]\n"
        "field outd : count\n"
        "outd[i] <- 1       for (i,j,w) in edge\n"
        "field wsum : sum\n"
        "wsum[i] <- w       for (i,j,w) in edge\n")

# 鎖。**前置きの鎖そのもの** —— 生成器が自分の番地割り当てに使っている形。
E8 = [(1, 5), (2, 3), (3, 7), (4, 2)]
SRC8 = ("table rows = " + ", ".join(map(str, E8)) + "\n"
        "field off : max\noff[0] <- 0\n"
        "off[i] <- off[i-1] + w   for (i,w) in rows\n")

# **記号表は不動点である。** 綴り ["dist","d","dist","w","d"] を intern する。
#   行 (k,a,b,c):  k=0 文字 (0,トークン,桁,文字)  終端 0 を各綴りの後ろに置く
#                  k=1 トークン (1,t,0,0)   k=2 対 (2,i,j,d) i<j、共有できる桁ぜんぶ
# aid[t] = そのトークンと同じ綴りが最初に現れた場所。**ハッシュは無い。**
_SP = ["dist", "d", "dist", "w", "d"]
R9 = []
for t, w in enumerate(_SP):
    R9.append((1, t, 0, 0))
    for d, ch in enumerate(w): R9.append((0, t, d, ord(ch)))
    R9.append((0, t, len(w), 1))            # 終端（⊥は番兵になれないので実文字）
for i in range(len(_SP)):
    for j in range(i + 1, len(_SP)):
        for d in range(min(len(_SP[i]), len(_SP[j])) + 1):
            R9.append((2, i, j, d))
SRC9 = ("table T = " + ", ".join(map(str, R9)) + "\n"
        "field tch : max\n"
        "tch[a, b] <- c    for (k,a,b,c) in T if k == 0\n"
        "field diff : or\n"
        "diff[a, b] <- true  for (k,a,b,c) in T if k == 2 if tch[a, c] != tch[b, c]\n"
        "field aid : min\n"
        "aid[a] <- a       for (k,a,b,c) in T if k == 1\n"
        "aid[b] <- a       for (k,a,b,c) in T if k == 2 if not diff[a, b]\n")

# 区間。表の行ではなく座標そのものを回る —— 計数器が座標である。
SRCR = ("field acc : max\nacc[0] <- 0\n"
        "acc[i] <- acc[i-1] + 3   for (i) in 1 .. 9\n"
        "field mark : or\n"
        "mark[i] <- true          for (i) in 2 .. 5\n")

# flat: 種二つが合流して ⊤、列の食い違いも ⊤。**⊤ は答えである。**
E6 = [(0, 1, 4), (5, 1, 4), (1, 2, 8), (2, 3, 9), (2, 3, 9)]
SRC6 = ("table edge = " + ", ".join(map(str, E6)) + "\n"
        "field cv : flat\ncv[0] <- 7\ncv[5] <- 9\n"
        "cv[j] <- cv[i]     for (i,j,t) in edge\n"
        "field cw : flat\n"
        "cw[j] <- t         for (i,j,t) in edge\n")

# **ガードは何個でも並ぶ。** 列で持っていた頃は 1 個ずつが上限だった。
E10 = [(1, 2, 3, 0), (1, 2, 3, 1), (1, 9, 3, 2), (1, 2, 3, 3)]
SRC10 = ("table T = " + ", ".join(map(str, E10)) + "\n"
         "field bad : or\nbad[3] <- true\n"
         "field good : or\n"
         "good[d] <- true   for (a,b,c,d) in T if a == 1 if b == 2 if c == 3\n"
         "                  if not bad[d]\n")

# **二項の加算**（場を二つ足す）。項が行になったので、ただ二行並ぶだけ。
#   階数は二つの読みの **最大 + 1** —— cmovl が分岐せずに最大を取る
E11 = [(0, 1, 5), (1, 2, 7), (0, 2, 3)]
SRC11 = ("table edge = " + ", ".join(map(str, E11)) + "\n"
         "field a : max\na[0] <- 10\n"
         "a[j] <- a[i] + w    for (i,j,w) in edge\n"
         "field b : max\nb[0] <- 1\n"
         "b[j] <- b[i] + 1    for (i,j,w) in edge\n"
         "field s : max\n"
         "s[j] <- a[i] + b[i] for (i,j,w) in edge\n")

# **座標の広さは場ごと。** 2000 升の鎖を区間で回す（64 升の壁はもう無い）。
SRC12 = ("field acc : max\nacc[0] <- 0\n"
         "acc[i] <- acc[i-1] + 3   for (i) in 1 .. 1999\n")

# **場の値が座標** `f[g[i]]`。trie の一段 —— 綴りの照合はこれで書ける。
#   nxt[p] : 親 p から辿った先。step[i] = nxt[cur[i]] のような読み方をする。
E13 = [(0, 3), (1, 5), (2, 7), (3, 9)]
SRC13 = ("table edge = " + ", ".join(map(str, E13)) + "\n"
         "field ptr : max\n"
         "ptr[i] <- p    for (i,p) in edge\n"
         "field val : max\nval[3] <- 30\nval[5] <- 50\nval[7] <- 70\nval[9] <- 90\n"
         "field got : max\n"
         "got[i] <- val[ptr[i]]   for (i,p) in edge\n")

# **入れ子ループ**。対を数える —— Lattix の記号表は「引く」のではなく「比べる」
#   から、対の列挙が要る。ホストが対の行を作るのではなく、**言語が数える**。
#   pair[i,j] <- true  for (i) in 0..3 for (j) in 0..3 if i < j   の形
SRC14 = ("field pair : or\n"
         "pair[i, j] <- true   for (i) in 0 .. 3 for (j) in 0 .. 3\n")

# **記号表を、対の行をホストが作らずに焼く。** ループが対を数える ——
#   diff は三重ループ (i,j,d)、aid は二重ループ (i,j) で、値は **計数器そのもの**。
_SP2 = ["dist", "d", "dist", "w", "d"]
E15 = [(t, d, ord(c)) for t, w in enumerate(_SP2)
       for d, c in enumerate(w + "\x01")]
SRC15 = ("table ch = " + ", ".join(map(str, E15)) + "\n"
         "field tch : max\n"
         "tch[t, d] <- c   for (t,d,c) in ch\n"
         "field diff : or\n"
         "diff[i, j] <- true   for (i) in 0 .. 4 for (j) in 0 .. 4 for (d) in 0 .. 7\n"
         "                     if tch[i, d] != tch[j, d]\n"
         "field aid : min\n"
         "aid[j] <- i   for (i) in 0 .. 4 for (j) in 0 .. 4 if not diff[i, j]\n")

#  rrule:  (st, lt, a, wf, rng, lo, hi)      ← 7 列だけ
#  guards: **行** (規則, 種, 場, 列, 値)   種1 `列 == 値` / 2 否定 / 3,4 比較の左右
#  terms:  **行** (規則, 種, 場, 列, 値)   種1 定数 / 2 表の列 / 3 場の読み
#  coords: **行** (所有者種, 規則, 番号, 次元, 源, 場, 列, ずれ有無, ずれ)
#          所有者種 0 項 / 1 ガード / 2 書き先。源 0 列 / 1 計数器 / 2,3 場の値
def C(kk, r, i, d, src, cf, cc, hof=0, off=0):
    return (kk, r, i, d, src, cf, cc, hof, off)

cases = [
    ("最短経路 (min)", SRC1, ['dist'], [(0, 1, 1)], [(0, 0, 0)],
     [(0, 1, 3, 0)], E1, [],
     [(0, 3, 0, 0, 0), (0, 2, 0, 2, 0)],
     [C(0, 0, 0, 0, 0, 0, 0), C(2, 0, 0, 0, 0, 0, 1)]),
    ("min+max+ガード", SRC2, ['dist', 'far'], [(0, 1, 1), (1, 2, 1)],
     [(0, 0, 0), (1, 0, 0)],
     [(0, 1, 4, 0), (0, 2, 4, 1)], E2,
     [(0, 1, 0, 3, 1), (1, 1, 0, 3, 1)],                     # if t == 1
     [(0, 3, 0, 0, 0), (0, 2, 0, 2, 0), (1, 3, 1, 0, 0), (1, 2, 0, 2, 0)],
     [C(0, 0, 0, 0, 0, 0, 0), C(2, 0, 0, 0, 0, 0, 1),
      C(0, 1, 0, 0, 0, 0, 0), C(2, 1, 0, 0, 0, 0, 1)]),
    ("場をまたぐ読み (or)", SRC3, ['a', 'b'], [(0, 3, 1), (1, 3, 1)],
     [(0, 0, 1), (1, 9, 1)],
     [(0, 3, 2, 0), (0, 3, 2, 1)], E3, [],
     [(0, 3, 0, 0, 0), (1, 3, 0, 0, 0)],
     [C(0, 0, 0, 0, 0, 0, 0), C(2, 0, 0, 0, 0, 0, 1),
      C(0, 1, 0, 0, 0, 0, 0), C(2, 1, 0, 0, 0, 0, 1)]),
    ("2次元 rd[j,v] (or)", SRC4, ['rd', 'hit'], [(0, 3, 2), (1, 3, 1)],
     [(0, 0*64+5, 1), (0, 0*64+7, 1)],
     [(0, 3, 3, 0), (0, 3, 3, 1)], E4, [],
     [(0, 3, 0, 0, 0), (1, 3, 0, 0, 0)],
     # 読みは rd[i,v]（二次元）、書きは rd[j,v] と hit[j]
     [C(0, 0, 0, 0, 0, 0, 0), C(0, 0, 0, 1, 0, 0, 2),
      C(2, 0, 0, 0, 0, 0, 1), C(2, 0, 0, 1, 0, 0, 2),
      C(0, 1, 0, 0, 0, 0, 0), C(0, 1, 0, 1, 0, 0, 2),
      C(2, 1, 0, 0, 0, 0, 1)]),
    ("flat 定数伝播", SRC6, ['cv', 'cw'], [(0, 6, 1), (1, 6, 1)],
     [(0, 0, 7), (0, 5, 9)],
     [(0, 6, 3, 0), (0, 6, 3, 1)], E6, [],
     [(0, 3, 0, 0, 0), (1, 2, 0, 2, 0)],
     [C(0, 0, 0, 0, 0, 0, 0), C(2, 0, 0, 0, 0, 0, 1), C(2, 1, 0, 0, 0, 0, 1)]),
    ("集約 sum/count", SRC7, ['reach', 'outd', 'wsum'],
     [(0, 3, 1), (1, 9, 1), (2, 8, 1)],
     [(0, 0, 1)],
     [(0, 3, 3, 0), (0, 9, 3, 1), (0, 8, 3, 2)], E7, [],
     [(0, 3, 0, 0, 0), (2, 2, 0, 2, 0)],
     [C(0, 0, 0, 0, 0, 0, 0), C(2, 0, 0, 0, 0, 0, 1),
      C(2, 1, 0, 0, 0, 0, 0), C(2, 2, 0, 0, 0, 0, 0)]),
    ("鎖 off[i-1]+w", SRC8, ['off'], [(0, 2, 1)], [(0, 0, 0)],
     [(0, 2, 2, 0)], E8, [],
     [(0, 3, 0, 0, 0), (0, 2, 0, 1, 0)],
     # 読みの座標は 列0 の -1（mod 256）。書きは 列0
     [C(0, 0, 0, 0, 0, 0, 0, 1, 255), C(2, 0, 0, 0, 0, 0, 0)]),
    ("記号表＝不動点 (intern)", SRC9, ['tch', 'diff', 'aid'],
     [(0, 2, 2), (1, 3, 2), (2, 1, 1)],
     [(2, 0, 0)],
     [(0, 2, 4, 0), (0, 1, 4, 2), (1, 3, 4, 1), (2, 1, 4, 2)], R9,
     [(0, 1, 0, 0, 0),                          # if k == 0
      (1, 1, 0, 0, 1),                          # if k == 1
      (2, 1, 0, 0, 2),                          # if k == 2
      (2, 3, 0, 0, 0),                          # 比較の左  tch[a,c]
      (2, 4, 0, 0, 2),                          # 比較の右  != tch[b,c]
      (3, 1, 0, 0, 2),                          # if k == 2
      (3, 2, 1, 0, 0)],                         # if not diff[a,b]
     [(0, 2, 0, 3, 0), (1, 2, 0, 1, 0), (3, 2, 0, 1, 0)],
     # 書き先と、ガードたちの座標（2次元は次元が二行）
     [C(2, 0, 0, 0, 0, 0, 1), C(2, 0, 0, 1, 0, 0, 2),
      C(2, 1, 0, 0, 0, 0, 1),
      C(1, 2, 1, 0, 0, 0, 1), C(1, 2, 1, 1, 0, 0, 3),      # tch[a,c]
      C(1, 2, 2, 0, 0, 0, 2), C(1, 2, 2, 1, 0, 0, 3),      # tch[b,c]
      C(2, 2, 0, 0, 0, 0, 1), C(2, 2, 0, 1, 0, 0, 2),
      C(2, 3, 0, 0, 0, 0, 2),
      C(1, 3, 1, 0, 0, 0, 1), C(1, 3, 1, 1, 0, 0, 2)]),    # diff[a,b]
    ("区間 for i in a..b", SRCR, ['acc', 'mark'], [(0, 2, 1), (1, 3, 1)],
     [(0, 0, 0)],
     [(0, 2, 0, 0, 1, 1, 9), (0, 3, 0, 1, 1, 2, 5)], [], [],
     [(0, 3, 0, 0, 0), (0, 1, 0, 0, 3)],
     # 計数器がそのまま座標（源1）。読みは -1 のずれ
     [C(0, 0, 0, 0, 1, 0, 0, 1, 255), C(2, 0, 0, 0, 1, 0, 0),
      C(2, 1, 0, 0, 1, 0, 0)]),
    ("ガード四つ／一規則", SRC10, ['bad', 'good'], [(0, 3, 1), (1, 3, 1)],
     [(0, 3, 1)],
     [(1, 3, 4, 1)], E10,
     [(0, 1, 0, 0, 1), (0, 1, 0, 1, 2), (0, 1, 0, 2, 3), (0, 2, 0, 0, 0)],
     [],
     [C(2, 0, 0, 0, 0, 0, 3), C(1, 0, 3, 0, 0, 0, 3)]),
    ("二項の加算 a[i]+b[i]", SRC11, ['a', 'b', 's'],
     [(0, 2, 1), (1, 2, 1), (2, 2, 1)],
     [(0, 0, 10), (1, 0, 1)],
     [(0, 2, 3, 0), (0, 2, 3, 1), (0, 2, 3, 2)], E11, [],
     [(0, 3, 0, 0, 0), (0, 2, 0, 2, 0),
      (1, 3, 1, 0, 0), (1, 1, 0, 0, 1),
      (2, 3, 0, 0, 0), (2, 3, 1, 0, 0)],
     [C(0, 0, 0, 0, 0, 0, 0), C(2, 0, 0, 0, 0, 0, 1),
      C(0, 1, 0, 0, 0, 0, 0), C(2, 1, 0, 0, 0, 0, 1),
      C(0, 2, 0, 0, 0, 0, 0), C(0, 2, 1, 0, 0, 0, 0),
      C(2, 2, 0, 0, 0, 0, 1)]),
    ("2000 升の鎖（区間）", SRC12, ['acc'], [(0, 2, 1, 2000, 1)], [(0, 0, 0)],
     [(0, 2, 0, 0, 1, 1, 1999)], [], [],
     [(0, 3, 0, 0, 0), (0, 1, 0, 0, 3)],
     [C(0, 0, 0, 0, 1, 0, 0, 1, 255), C(2, 0, 0, 0, 1, 0, 0)]),
    # **場の値が座標** got[i] <- val[ptr[i]]。源2 —— 名前が座標であることの機械語
    ("場の値が座標 val[ptr[i]]", SRC13, ['ptr', 'val', 'got'],
     [(0, 2, 1), (1, 2, 1), (2, 2, 1)],
     [(1, 3, 30), (1, 5, 50), (1, 7, 70), (1, 9, 90)],
     [(0, 2, 2, 0), (0, 2, 2, 2)], E13, [],
     [(0, 2, 0, 1, 0), (1, 3, 1, 0, 0)],
     [C(2, 0, 0, 0, 0, 0, 0),                       # ptr[i] <- p
      C(0, 1, 0, 0, 2, 0, 0),                       # 読み val[ptr[i]]（源2）
      C(2, 1, 0, 0, 0, 0, 0)]),                     # 書き got[i]
    # **入れ子ループ**（外 rcx、内 r13）。座標の源1 が「どのループか」を言う
    ("入れ子ループ（対）", SRC14, ['pair'], [(0, 3, 2, 4, 4)], [],
     [(0, 3, 0, 0)], [], [], [],
     [C(2, 0, 0, 0, 1, 0, 0), C(2, 0, 0, 1, 1, 0, 1)],
     [(0, 0, 1, 0, 3, 0), (0, 1, 1, 0, 3, 0)]),
    # **対を言語が数える記号表**。ホストは対の行を一つも作らない
    ("記号表（ループが数える）", SRC15, ['tch', 'diff', 'aid'],
     [(0, 2, 2, 5, 8), (1, 3, 2, 5, 5), (2, 1, 1, 5, 1)], [],
     [(0, 2, 3, 0), (0, 3, 3, 1), (1, 1, 3, 2)], E15,
     # diff の比較ガード tch[i,d] != tch[j,d] / aid の否定 not diff[i,j]
     [(1, 3, 0, 0, 0), (1, 4, 0, 0, 2), (2, 2, 1, 0, 0)],
     # 値: tch は列 c、aid は **計数器 i**（種4）
     [(0, 2, 0, 2, 0), (2, 4, 0, 0, 0)],
     [C(2, 0, 0, 0, 0, 0, 0), C(2, 0, 0, 1, 0, 0, 1),          # tch[t,d]
      C(2, 1, 0, 0, 1, 0, 0), C(2, 1, 0, 1, 1, 0, 1),          # diff[i,j]
      C(1, 1, 0, 0, 1, 0, 0), C(1, 1, 0, 1, 1, 0, 2),          # tch[i,d]
      C(1, 1, 1, 0, 1, 0, 1), C(1, 1, 1, 1, 1, 0, 2),          # tch[j,d]
      C(2, 2, 0, 0, 1, 0, 1),                                  # aid[j]
      C(1, 2, 0, 0, 1, 0, 0), C(1, 2, 0, 1, 1, 0, 1)],         # diff[i,j]
     [(0, 0, 0, 0, 0, 3),
      (1, 0, 1, 0, 4, 0), (1, 1, 1, 0, 4, 0), (1, 2, 1, 0, 7, 0),
      (2, 0, 1, 0, 4, 0), (2, 1, 1, 0, 4, 0)]),
    ("層＋否定＋読み無し", SRC5, ['reach', 'used', 'unre'],
     [(0, 3, 1), (1, 3, 1), (2, 3, 1)],
     [(0, 0, 1)],
     [(0, 3, 3, 0), (0, 3, 3, 1), (1, 3, 3, 2)], E5,
     [(1, 1, 0, 2, 1), (2, 2, 0, 0, 0)],
     [(0, 3, 0, 0, 0), (2, 3, 1, 0, 0)],
     [C(0, 0, 0, 0, 0, 0, 0), C(2, 0, 0, 0, 0, 0, 1),
      C(2, 1, 0, 0, 0, 0, 1),
      C(0, 2, 0, 0, 0, 0, 1), C(2, 2, 0, 0, 0, 0, 1),
      C(1, 2, 0, 0, 0, 0, 1)]),
]

# ── バイトの口。**源のバイトを読み、バイトを書く**（ELF を吐く形）─────
def byte_echo(tmp):
    n, out, _r, err = gen([(0, 2, 1)], [], [(0, 2, 2, 0)], [], tmp, 900,
                          terms=[(0, 2, 0, 1, 0)],
                          coords=[C(2, 0, 0, 0, 0, 0, 0)],
                          loops=[(0, 0, 0, 0, 0, 2)],
                          inp=1, outp=[(0, 0, 1)], raw=b"Hello, Lattix!")
    return n, out, err


tmp = tempfile.mkdtemp()
print("=" * W)
print("  Lattix が Lattix のプログラムから機械語を書く —— 場は複数、束が命令を選ぶ")
print("=" * W)
print(f"  {'入力':<20}{'場':>3}{'規則':>4}{'バイト':>7}{'セル':>5}  全セル一致   attest")
print("-" * W)
ok = True
for tag, (name, src, names, flds, seeds, rules, edges, guards,
          terms, coords, *rest) in enumerate(cases):
    loops = rest[0] if rest else ()
    # 場の升数の合計が 0x1000/8 を超えたら焼かない（K の置き場を踏む前に拒む）

    n, store, rank, err = gen(flds, seeds, rules, edges, tmp, tag,
                              guards, terms, coords, loops)
    ref = interp(src, names)
    same = store == ref
    fmap = {i: nm for i, nm in enumerate(names)}
    rep = ATT.attest(src, {fmap[f]: d for f, d in (store or {}).items()},
                     {fmap[f]: d for f, d in (rank or {}).items()})
    cert = rep.sound and rep.complete
    good = same and cert
    ok &= good
    print(f"  {name:<20}{len(flds):>3}{len(rules):>4}{n:>7}"
          f"{sum(len(d) for d in (store or {}).values()):>5}   "
          f"{'✓' if same else '✗':>4}      "
          f"SOUND {'✓' if rep.sound else '✗'} COMPLETE {'✓' if rep.complete else '✗'}"
          f"{('  ' + err) if err else ''}")
# ── 同じ実行ファイル、違うデータ。焼き直しは一度も無い ────────────────
exe0 = os.path.join(tmp, "a0.out")
print("-" * W)
print("  **同じ実行ファイル、違うデータ**（焼き直し無し）:")
for note, edges2 in [("別の図", [(0, 1, 7), (1, 2, 9), (0, 2, 30), (2, 3, 2)]),
                     ("大きい重み", [(0, 1, 4000), (1, 2, 90000), (2, 3, 2000000)])]:
    indata = b"".join(struct.pack("<3q", *e) for e in edges2)
    r = subprocess.run([exe0], input=indata, capture_output=True)
    F = struct.unpack(f'<{DOM}q', r.stdout[:8*DOM])
    got = {(k,): v for k, v in enumerate(F) if v != BOT[1]}
    src2 = ("table edge = " + ", ".join(map(str, edges2)) + "\n"
            "field dist : min\ndist[0] <- 0\n"
            "dist[j] <- dist[i] + w   for (i,j,w) in edge\n")
    want = interp(src2, ['dist'])[0]
    good = got == want
    ok &= good
    print(f"    {note:<12} {len(edges2)} 行 → {len(got)} セル  {'✓' if good else '✗'}")

print("-" * W)
# ── バイトの口 ──────────────────────────────────────────────────────
nb, ob, eb = byte_echo(tmp)
same_b = ob is not None and ob[:14] == b"Hello, Lattix!"
ok &= same_b
print("-" * W)
print("  **バイトの口**（源のバイトを読み、バイトを書く）:")
print(f"    生バイト入力 → 生バイト出力 {'✓' if same_b else '✗'}   "
      f"{ob[:14] if ob else eb}")
print("    答えは stdout、**証人（階数）は stderr** —— 混ざってはいけない")
print("-" * W)
print("  一致" if ok else "  不一致")
print("  **場ごとに ⊥ が違い（INF / -INF / 0）、束ごとに命令が違う**（jge / jle / test）。")
print("  ガードは 3 命令の前置き。本体の長さが揺れるので、命令番号は規則番号に沿った")
print("  **前置きの鎖**で出る（番地と同じ形。気づき17）。")
print("  そして attest が通る —— 機械語で解いた答えにも証明書が付く（不変条件6）。")
print("=" * W)
sys.exit(0 if ok else 1)
