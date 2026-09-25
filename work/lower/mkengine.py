#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**print の機械を起こす**（work/lower/engine.lx を書く。手で直さない）。

行 r は印字する升（集合なら要素）の線形の番号。字は決まった席に置き、⊥ の席は render が飛ばす（幅 0）。
席: 名 0..31 / `[` 32 / 座標0 33..56 / `, ` 57,58 / 座標1 59..82 / `] = ` 83..86 / 値 87..110 / 改行 111。
集合の行は要素ごと: 組の最初の行だけが名と鍵と `{`（87）を書き、ほかは `, `（88,89）、要素 90..113、
組の最後の行が `}`（114）と改行（115）を書く。名は三十二文字まで（下ろしは十七文字以上の場を付け替える）。
"""
import os
# 行で引く場（名, 束, 二次元目の広さ —— 0 なら一次元）。宣言は下ろしが行の数を入れて書く（型紙 70 から）
# 二次元目の広さ: 数ならそれ、"O" なら `_o` の広さ（項が無ければ 116、在れば 87 + TW —— 項の節は `_o` の席で数える）
ROWS = [("_o", "max", "O"), ("_pv", "max", 0), ("_pk1", "max", 0), ("_pk2", "max", 0), ("_pp", "max", 0),
        ("_pab", "max", 0), ("_pq", "max", 0), ("_pe", "max", 0), ("_pgs", "max", 0), ("_gf", "min", 0),
        ("_gl", "max", 0), ("_ph", "or", 0), ("_dk1", "max", 10), ("_dk2", "max", 10), ("_dv0", "max", 10),
        ("_dv1", "max", 10), ("_de", "max", 10),
        # 項の print（行 r の値が項の番地なら、項の字を前順に展開して書く）
        ("_rs", "max", 0), ("_rt", "or", 0), ("_Wn", "max", 0),
        ("_xq0", "max", 0), ("_xs0", "max", 0), ("_xq1", "max", 0), ("_xs1", "max", 0),
        ("_xq2", "max", 0), ("_xs2", "max", 0), ("_xq3", "max", 0), ("_xs3", "max", 0),
        # 項の節（深さ L ごとに別の場 —— 子の位置は親の場所を座標に読んで決まるので、同じ場で回すと
        # 成層できない。深さは 8 までなので、段ごとに場を分ければ輪が消える）。出力は段を合わせた `_VN` / `_VD`
        ("_V0", "flat", "O"), ("_V1", "flat", "O"), ("_V2", "flat", "O"), ("_V3", "flat", "O"), ("_V4", "flat", "O"),
        ("_V5", "flat", "O"), ("_V6", "flat", "O"), ("_V7", "flat", "O"), ("_V8", "flat", "O"),
        ("_VN", "flat", "O"), ("_VD", "flat", "O"), ("_VG", "flat", "O")]
R = "for (r) in 0 .. _Rz[0]"
L = []
L.append("# ── print を _o に下ろす機械（下ろした本の末尾に一度だけ置く。work/lower/mkengine.py が起こす）──")
L.append("# 行 r は印字する升（集合なら要素）の線形の番号。字は決まった席に置き、⊥ の席は render が飛ばす（幅 0）。")
L.append("# 席: 名 0..31 / `[` 32 / 座標0 33..56 / `, ` 57,58 / 座標1 59..82 / `] = ` 83..86 / 値 87..110 / 改行 111。")
L.append("# 集合: 組の最初の行が名・鍵・`{`（87）、ほかは `, `（88,89）、要素 90..113、最後の行が `}`（114）と改行（115）")
# **行で引く場は、下ろしが宣言する**（行の数は print の升の数の和 —— 本ごとに違う。ROWS を見よ）
decl = """field _pbs : max bound 64
field _pen : max bound 64
field _pd2 : or bound 64
field _pd0 : or bound 64
field _pa1 : or bound 64                     # 座標0 は原子
field _pa2 : or bound 64                     # 座標1 は原子
field _pav : or bound 64                     # 値は原子
field _an : max bound 1024 24                # 原子の番号 → 綴り
field _por : or bound 64
field _pn : or bound 64
field _pnm : max bound 64 32
field _Rz : max bound 1
field _Pz : max bound 1
field _bt : max bound 64
field _pst : or bound 64                     # print p は集合
field _pea : or bound 64                     # 集合の要素は原子"""
L += decl.split("\n")
L.append(f"_pp[r] <- p   {R} for (p) in 0 .. _Pz[0] if r > _pbs[p] if r <= _pen[p] if _pv[r] == _pv[r]")
L.append(f"_pn[_pp[r]] <- true   {R}")
L.append(f"_pk1[r] <- r - _pbs[_pp[r]] - 1   {R} if _pp[r] >= 0 if not _pd2[_pp[r]] if not _pd0[_pp[r]] if not _pst[_pp[r]]")
L.append(f"_gf[_pgs[r]] <- r   {R} if _pst[_pp[r]]")
L.append(f"_gl[_pgs[r]] <- r   {R} if _pst[_pp[r]]")
L.append(f"_ph[r] <- true   {R} if _pp[r] >= 0 if not _pst[_pp[r]]")
L.append(f"_ph[r] <- true   {R} if _pst[_pp[r]] if _gf[_pgs[r]] == r")
L.append(f"_o[r, j] <- _pnm[_pp[r], j]   {R} for (j) in 0 .. 31 if _ph[r]")
L.append(f"_o[r, 32] <- 91   {R} if _ph[r]")
def digits(q, src, end, cond):
    """**桁は鎖で出す**（十の規則を並べない）: `q[r, 9]` に値、`q[r, e] = q[r, e+1] / 10`。
    席 end-9+e に `q[r, e] % 10` を置く —— 上の桁の 0 は q が 0 なので書かない（⊥ は幅 0）"""
    L.append(f"{q}[r, 9] <- {src}   {R} {cond}".rstrip())
    L.append(f"{q}[r, e] <- {q}[r, e + 1] / 10   {R} for (e) in 0 .. 8")
    L.append(f"_o[r, e + {end-9}] <- 48 + {q}[r, e] % 10   {R} for (e) in 0 .. 8 if {q}[r, e] >= 1")
    L.append(f"_o[r, {end}] <- 48 + {q}[r, 9] % 10   {R}")
def key(fld, flag, end, cond, q):
    L.append(f"_o[r, j + {end-23}] <- _an[{fld}[r], j]   {R} for (j) in 0 .. 23 if {cond} if {flag}[_pp[r]]")
    digits(q, f"{fld}[r]", end, f"if {cond} if _pp[r] >= 0 if not {flag}[_pp[r]]")
key("_pk1", "_pa1", 56, "_ph[r]", "_dk1")
L.append(f"_o[r, 57] <- 44   {R} if _pd2[_pp[r]]")
L.append(f"_o[r, 58] <- 32   {R} if _pd2[_pp[r]]")
key("_pk2", "_pa2", 82, "_ph[r]", "_dk2")
for j, c in enumerate("] = "):
    L.append(f"_o[r, {83+j}] <- {ord(c)}   {R} if _ph[r]")
V = 87
for j, c in enumerate("true"):
    L.append(f"_o[r, {V+j}] <- {ord(c)}   {R} if _por[_pp[r]]")
L.append(f"_o[r, j + {V}] <- _an[_pv[r], j]   {R} for (j) in 0 .. 23 if _pav[_pp[r]]")
L.append(f"_o[r, {V}] <- 45   {R} if _pv[r] < 0 if _pp[r] >= 0 if not _por[_pp[r]] if not _pav[_pp[r]] if not _pst[_pp[r]]")
L.append(f"_pab[r] <- _pv[r]   {R} if _pv[r] >= 0 if _pp[r] >= 0 if not _por[_pp[r]] if not _pav[_pp[r]] if not _pst[_pp[r]] if not _rt[r]")
L.append(f"_pab[r] <- 0 - _pv[r]   {R} if _pv[r] < 0 if _pp[r] >= 0 if not _por[_pp[r]] if not _pav[_pp[r]] if not _pst[_pp[r]] if not _rt[r]")
L.append(f"# 十九桁は一つの割り算で出せない（10^18 の上は 64 ビットの積が溢れる）ので、下九桁と上に分ける")
L.append(f"_pq[r] <- _pab[r] / 1000000000   {R}")
E = V + 23
# 下九桁は `_pab % 10^9`、上は `_pq`。下の上の桁の 0 は、上が在るときだけ 0 と書く
digits("_dv0", "_pab[r] % 1000000000", E, "")
L.append(f"_o[r, e + {E-9}] <- 48   {R} for (e) in 1 .. 8 if _pq[r] >= 1 if _dv0[r, e] == 0")
digits("_dv1", "_pq[r]", E - 9, "if _pq[r] >= 1")
L.append(f"_o[r, {E+1}] <- 10   {R} if _pp[r] >= 0 if not _pst[_pp[r]] if not _rt[r]")
# 集合の行
S = f"{R} if _pst[_pp[r]]"
L.append(f"_o[r, 87] <- 123   {S} if _gf[_pgs[r]] == r")
L.append(f"_o[r, 88] <- 44   {S} if _gf[_pgs[r]] < r")
L.append(f"_o[r, 89] <- 32   {S} if _gf[_pgs[r]] < r")
L.append(f"_o[r, j + 90] <- _an[_pe[r], j]   {S} for (j) in 0 .. 23 if _pea[_pp[r]]")
digits("_de", "_pe[r]", 113, "if _pst[_pp[r]] if not _pea[_pp[r]]")
L.append(f"_o[r, 114] <- 125   {S} if _gl[_pgs[r]] == r")
L.append(f"_o[r, 115] <- 10   {S} if _gl[_pgs[r]] == r")
L.append("_o[_pbs[p], j] <- _pnm[p, j]   for (p) in 0 .. _Pz[0] for (j) in 0 .. 31 if not _pn[p]")
L.append("_o[_pbs[p], j + 32] <- _bt[j]   for (p) in 0 .. _Pz[0] for (j) in 0 .. 60 if not _pn[p]")
L.append("""# **数の集合は綴りの順に並べる**（解釈実行は `sorted(key=str)`: 10 < 2）。数 y の綴りを
# 十一進四桁の鍵 `_sP[y]` に畳む（桁は 数字+1、綴りの後ろは 0 —— 短い綴りが先に来る）。
# print ごとに、要素の範囲の鍵に印を付け（`_sh`）、鍵の空間を鎖で数えれば（`_sc`）、
# それが綴りの順の番号になる（数え上げの整列。鍵の空間は 11^4 = 14,641 升）
# 桁が一つ多い数の鍵は、最後の桁を落とした数の鍵に、最後の桁を足したもの（前の桁は同じ席に居る）
field _s10 : max bound 10000
_s10[y] <- y / 10   for (y) in 0 .. 9999
field _sP : max bound 10000
_sP[y] <- y * 1331 + 1331   for (y) in 0 .. 9
_sP[y] <- _sP[_s10[y]] + y % 10 * 121 + 121   for (y) in 10 .. 99
_sP[y] <- _sP[_s10[y]] + y % 10 * 11 + 11   for (y) in 100 .. 999
_sP[y] <- _sP[_s10[y]] + y % 10 + 1   for (y) in 1000 .. 9999
field _psi : or bound 64                     # print p は数の集合
field _sh : or bound 64 14641
field _sc : max bound 64 14641
_sc[p, 0] <- 0   for (p) in 0 .. _Pz[0] if _psi[p]
_sc[p, q] <- _sc[p, q - 1] + 1   for (p) in 0 .. _Pz[0] for (q) in 1 .. 14640 if _psi[p] if _sh[p, q - 1]
_sc[p, q] <- _sc[p, q - 1]   for (p) in 0 .. _Pz[0] for (q) in 1 .. 14640 if _psi[p] if not _sh[p, q - 1]""")

# ══ 項（構成子）═══════════════════════════════════════════════════════════
# 値は解釈実行と同じ番地（`ctor_id`: 二本の多項式を法 M1・M2 で折り、番地 = h1·M2 + h2 < 2^56）。
# 下ろしは、構成子の出現 ×（引数が使うループ）の反復ごとに **場所 g** を置き、構成子と引数を書く
# （`_sk[g]` / 数 `_sv[g, i]` / 原子 `_sva[g, i]`）。番地は場所の記録から機械が出す。
M1, K1, M2, K2 = 268435399, 1000003, 268435367, 1000033
P = [65521, 65519, 65497, 65479]
G = "for (g) in 0 .. _Sz[0]"
GI = f"{G} for (i) in 0 .. 3"
L.append("""field _Sz : max bound 1                      # 最後の場所の番号
field _sk : flat bound 16384                 # 場所 g の構成子
field _sv : flat bound 16384 4               # 場所 g の i 番目の引数（数・項の番地）
field _sva : flat bound 16384 4              # 場所 g の i 番目の引数（原子の番号）
field _kn : max bound 64                     # 構成子 k の引数の数
field _kb1 : max bound 64                    # 構成子 k の名と引数の数を折り込んだ種（一本目）
field _kb2 : max bound 64                    # （二本目）
field _knm : max bound 64 16                 # 構成子 k の名
field _knl : max bound 64                    # その長さ
field _sn : flat bound 16384                 # 場所 g の引数の数""")
L.append(f"_sn[g] <- _kn[_sk[g]]   {G}")
L.append("""# 原子の綴りの折り込み（`_enc(str) = 3·fold(綴り) + 1`）
field _anl : max bound 1024
_anl[a] <- j + 1   for (a) in 0 .. 1023 for (j) in 0 .. 23 if _an[a, j] >= 1""")
for ln, (m, k) in enumerate([(M1, K1), (M2, K2)], 1):
    # 折り込みの鎖は **flat**（升は一度しか決まらない）。`%` は向きを持たないので、max の場で自分を
    # 読む鎖にすると成層できない —— flat の読みは動かないので鎖になれる
    L.append(f"field _af{ln} : flat bound 1024 25")
    L.append(f"field _ag{ln} : flat bound 1024 24")
    L.append(f"_af{ln}[a, 0] <- 0   for (a) in 0 .. 1023 if _anl[a] >= 1")
    L.append(f"_ag{ln}[a, j] <- _af{ln}[a, j] * {k} + _an[a, j] + 1   for (a) in 0 .. 1023 for (j) in 0 .. 23")
    L.append(f"_af{ln}[a, j + 1] <- _ag{ln}[a, j] % {m}   for (a) in 0 .. 1023 for (j) in 0 .. 23")
    L.append(f"field _afh{ln} : max bound 1024")
    L.append(f"_afh{ln}[a] <- _af{ln}[a, _anl[a]]   for (a) in 0 .. 1023")
    L.append(f"field _se{ln} : flat bound 16384 4         # 引数の符号化（数 3(v mod M) / 原子 3·fold + 1）")
    L.append(f"_se{ln}[g, i] <- _sv[g, i] % {m} * 3   {GI}")
    L.append(f"_se{ln}[g, i] <- _afh{ln}[_sva[g, i]] * 3 + 1   {GI}")
    L.append(f"field _sh{ln} : flat bound 16384 5         # 引数 i までを折り込んだもの（flat —— 上を見よ）")
    L.append(f"field _su{ln} : flat bound 16384 4")
    L.append(f"_sh{ln}[g, 0] <- _kb{ln}[_sk[g]]   {G}")
    L.append(f"_su{ln}[g, i] <- _sh{ln}[g, i] * {k} + _se{ln}[g, i]   {GI} if i < _sn[g]")
    L.append(f"_sh{ln}[g, i + 1] <- _su{ln}[g, i] % {m}   {GI} if i < _sn[g]")
L.append("field _sid : flat bound 16384                # 場所 g の番地（項の引数が項なら、番地の鎖は再帰する —— 升は一度だけ決まる flat なので回れる）")
L.append(f"_sid[g] <- _sh1[g, _sn[g]] * {M2} + _sh2[g, _sn[g]]   {G}")
L.append("""# **番地 → 場所の引き: 多段の桶の最小。** 段 L ごとに `_cbL[番地 % P_L]` に場所の最小を置く（min —— 置く順に
# 依らない）。桶の最小の番地が自分の番地と同じなら解けた。違えば（別の番地が同じ桶に居た）解けていない場所
# だけで次の段の桶を作る。四段で残ったものは詰めた一覧を線形に見る。同じ番地の場所は同じ中身なので、
# どの場所を引いても答えは同じ —— 引く側は段ごとに「桶の最小の番地 == 探す番地」を見るだけでよい""")
prev = []
for lv, pr in enumerate(P):
    cond = "".join(f" if not _ck{j}[g]" for j in prev)
    L.append(f"field _cq{lv} : max bound 16384")
    L.append(f"_cq{lv}[g] <- _sid[g] % {pr}   {G} if _sid[g] >= 0{cond}")
    L.append(f"field _cb{lv} : min bound {pr}")
    L.append(f"_cb{lv}[_cq{lv}[g]] <- g   {G}")
    L.append(f"field _cr{lv} : max bound 16384")
    L.append(f"_cr{lv}[g] <- _cb{lv}[_cq{lv}[g]]   {G}")
    L.append(f"field _ck{lv} : or bound 16384")
    L.append(f"_ck{lv}[g] <- true   {G} if _sid[_cr{lv}[g]] == _sid[g]")
    prev.append(lv)
L.append("field _cu : or bound 16384                  # 四段で解けなかった場所")
L.append(f"_cu[g] <- true   {G} if _sid[g] >= 0" + "".join(f" if not _ck{j}[g]" for j in prev))
L.append("""field _cuc : max bound 16384                # 場所 g までの解けなかった場所の数（鎖）
_cuc[0] <- 0   for (z) in 0 .. 0 if _Sz[0] >= 0 if not _cu[0]
_cuc[0] <- 1   for (z) in 0 .. 0 if _cu[0]
_cuc[g] <- _cuc[g - 1] + 1   for (g) in 1 .. _Sz[0] if _cu[g]
_cuc[g] <- _cuc[g - 1]   for (g) in 1 .. _Sz[0] if not _cu[g]
field _cul : max bound 16384                # 解けなかった場所の一覧
_cul[_cuc[g] - 1] <- g   for (g) in 0 .. _Sz[0] if _cu[g]
field _cuz : max bound 1
_cuz[z] <- _cuc[g] - 1   for (g) in 0 .. _Sz[0] for (z) in 0 .. 0""")
def lookup(out, x, ctx_loops, ctx_guard, keyed, pre, bound2=None):
    """値 x の場所を out に（見つからなければ ⊥）。keyed は out の座標の書き方、pre は仮の場の接頭辞"""
    for lv, pr in enumerate(P):
        q, sx = f"{pre}q{lv}", f"{pre}s{lv}"
        if bound2 is not None:
            L.append(f"field {q} : max bound 16384 {bound2}")
            L.append(f"field {sx} : max bound 16384 {bound2}")
        L.append(f"{q}[{keyed}] <- {x} % {pr}   {ctx_loops}{ctx_guard} if {x} >= 0")
        L.append(f"{sx}[{keyed}] <- _cb{lv}[{q}[{keyed}]]   {ctx_loops}")
        L.append(f"{out}[{keyed}] <- {sx}[{keyed}]   {ctx_loops} if _sid[{sx}[{keyed}]] == {x}")
    L.append(f"{out}[{keyed}] <- _cul[u]   {ctx_loops} for (u) in 0 .. _cuz[0] if _sid[_cul[u]] == {x}")
L.append("# 行 r の値の場所（値が項の番地なら）")
lookup("_rs", "_pv[r]", R, " if _Sz[0] >= 0 if _pp[r] >= 0", "r", "_x")
L.append(f"_rt[r] <- true   {R} if _rs[r] >= 0")
L.append("# 場所 g の i 番目の引数が項なら、その場所（子）")
L.append("field _cs : max bound 16384 4")
lookup("_cs", "_sv[g, i]", GI, "", "g, i", "_y", bound2=4)
L.append("field _ct : or bound 16384 4                # 引数は項")
L.append(f"_ct[g, i] <- true   {GI} if _cs[g, i] >= 0")
# ── 項の字の並べ方（固定の枠 —— ⊥ の升は幅 0 なので、枠の余りは詰まって消える）──
NW, IW, AW = 16, 20, 24
L.append(f"""# **項の字は固定の枠で並べる**（名 {NW} / 数 {IW} / 原子 {AW} / 子の項は子の枠）。⊥ の升は render が飛ばすので、
# 枠の余りは詰まって消える —— 長さを数えなくてよい。深さ d（0..8）の節の枠の広さ `_W[g, d]`、
# 引数 i の枠の始まり `_Oi[g, d]`（名 + `(` の後ろ、前の枠 + `, `）。深さ 9 の子は番地の数字（show_val と同じ）。
# 引数は三つまで
field _W : max bound 16384 9
field _Wm : max bound 16384 9                # 広さ - 1（`)` の位置）""")
GD = f"{G} for (d) in 0 .. 8"
for i in range(3):
    L.append(f"field _O{i} : max bound 16384 9")
    L.append(f"field _Oe{i} : max bound 16384 9          # 数の枠の終わり（右寄せの桁の一の位）")
    L.append(f"field _aw{i} : max bound 16384 9")
    L.append(f"_aw{i}[g, d] <- {IW}   {GD} if _sv[g, {i}] == _sv[g, {i}] if not _ct[g, {i}]")
    L.append(f"_aw{i}[g, d] <- {AW}   {GD} if _sva[g, {i}] >= 0")
    L.append(f"_aw{i}[g, d] <- {IW}   {GD} if _ct[g, {i}] if d == 8")
    L.append(f"_aw{i}[g, d] <- _W[_cs[g, {i}], d + 1]   {GD} if d < 8")
L.append(f"_O0[g, d] <- {NW + 1}   {GD} if _sn[g] >= 1")
for i in range(1, 3):
    L.append(f"_O{i}[g, d] <- _O{i-1}[g, d] + _aw{i-1}[g, d] + 2   {GD} if _sn[g] > {i}")
for i in range(3):
    L.append(f"_Oe{i}[g, d] <- _O{i}[g, d] + {IW - 1}   {GD}")
L.append(f"_W[g, d] <- {NW + 2}   {GD} if _sn[g] == 0")
for n in range(1, 4):
    L.append(f"_W[g, d] <- _O{n-1}[g, d] + _aw{n-1}[g, d] + 1   {GD} if _sn[g] == {n}")
L.append(f"_Wm[g, d] <- _W[g, d] - 1   {GD}")
L.append(f"""# **桁は場所ごとの鎖**（行ごとに十九の規則を並べない）: 場所 g の引数 i の大きさを `_dq[4g+i, e]` に
# 10^e で割ったものとして置き、項の字の数の枠は、その番号の桁を右寄せで写すだけ
field _q4 : max bound 16384 4
_q4[g, i] <- g * 4 + i   {GI}
field _Sq : max bound 1
_Sq[z] <- _Sz[0] * 4 + 3   for (z) in 0 .. 0
field _dq : max bound 65536 20
_dq[_q4[g, i], 0] <- _sv[g, i]   {GI} if _sv[g, i] >= 0
_dq[_q4[g, i], 0] <- 0 - _sv[g, i]   {GI} if _sv[g, i] < 0
_dq[x, e + 1] <- _dq[x, e] / 10   for (x) in 0 .. _Sq[0] for (e) in 0 .. 18""")
L.append(f"""# (場所, 深さ) を一本の番号 9g + d に畳んだ写し（焼き手の内側の二次元の読みは、次元1 に読みを置けない）
field _q9 : max bound 16384 9
_q9[g, d] <- g * 9 + d   {GD}
field _Wm1 : max bound 147456
_Wm1[_q9[g, d]] <- _Wm[g, d]   {GD}""")
for i in range(3):
    L.append(f"field _O{i}1 : max bound 147456")
    L.append(f"_O{i}1[_q9[g, d]] <- _O{i}[g, d]   {GD}")
    L.append(f"field _Oe{i}1 : max bound 147456")
    L.append(f"_Oe{i}1[_q9[g, d]] <- _Oe{i}[g, d]   {GD}")
TW = 1024
X = 87 + TW
L.append(f"""# **足し算の表**（焼き手の座標は「読み ± 定数」だけ —— 和は表を読めば読みになる。読みは次元0 に置く）
field _AA : max bound {X} {X}               # x + y
_AA[x, y] <- x + y   for (x) in 0 .. _TWx[0] for (y) in 0 .. _TWx[0]
field _AM : max bound {X} 24                # x - e
_AM[x, e] <- x - e   for (x) in 0 .. _TWx[0] for (e) in 0 .. 23 if x >= e
field _TWz : max bound 1                    # 項の字の広さ - 1（下ろしが置く。項が無ければ ⊥）
field _TWx : max bound 1                    # 項の字の最後の席（87 + 広さ - 1）
_TWx[z] <- _TWz[0] + 87   for (z) in 0 .. 0""")
RP = f"{R} for (p) in 87 .. _TWx[0]"
L.append(f"_V0[r, 87] <- _rs[r]   {R}")
L.append(f"_Wn[r] <- _W[_rs[r], 0] + 87   {R}")
for lv in range(9):
    V = f"_V{lv}[r, p]"
    L.append(f"_VN[r, p] <- {V}   {RP}")
    L.append(f"_VD[r, p] <- {lv}   {RP} if {V} >= 0")
    if lv < 8:
        for i in range(3):
            L.append(f"_V{lv+1}[r, _AA[_O{i}[{V}, {lv}], p]] <- _cs[{V}, {i}]   {RP}")
L.append(f"_VG[r, p] <- _VN[r, p] * 9 + _VD[r, p]   {RP}")
g_, d_, q_ = "_VN[r, p]", "_VD[r, p]", "_VG[r, p]"
L.append(f"_o[r, _AA[j, p]] <- _knm[_sk[{g_}], j]   {RP} for (j) in 0 .. 15")
L.append(f"_o[r, _AA[_knl[_sk[{g_}]], p]] <- 40   {RP}")
L.append(f"_o[r, _AA[_Wm1[{q_}], p]] <- 41   {RP}")
for i in range(3):
    st = f"_AA[_O{i}1[{q_}], p]"
    en = f"_AA[_Oe{i}1[{q_}], p]"
    if i >= 1:
        L.append(f"_o[r, _AM[{st}, 2]] <- 44   {RP} if _sn[{g_}] > {i}")
        L.append(f"_o[r, _AM[{st}, 1]] <- 32   {RP} if _sn[{g_}] > {i}")
    L.append(f"_o[r, _AA[{st}, j]] <- _an[_sva[{g_}, {i}], j]   {RP} for (j) in 0 .. 23")
    # 数の引数（項でない）か、深さ 8 の節の項の引数（番地の数字）
    for cond in [f"if not _ct[{g_}, {i}]", f"if _ct[{g_}, {i}] if {d_} == 8"]:
        L.append(f"_o[r, _AM[{en}, e]] <- 48 + _dq[_q4[{g_}, {i}], e] % 10   {RP} for (e) in 1 .. 19 {cond} if _dq[_q4[{g_}, {i}], e] >= 1")
        L.append(f"_o[r, {en}] <- 48 + _dq[_q4[{g_}, {i}], 0] % 10   {RP} {cond}")
    L.append(f"_o[r, {st}] <- 45   {RP} if _sv[{g_}, {i}] < 0")
L.append(f"_o[r, _Wn[r]] <- 10   {R} if _rt[r]")
L.append('render _o')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.lx"), "w", encoding="utf-8").write("\n".join(L) + "\n")
