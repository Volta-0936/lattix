#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**print の機械を起こす**（work/lower/engine.lx を書く。手で直さない）。

行 r は印字する升（集合なら要素）の線形の番号。字は決まった席に置き、⊥ の席は render が飛ばす（幅 0）。
席: 名 0..31 / `[` 32 / 座標0 33..56 / `, ` 57,58 / 座標1 59..82 / `] = ` 83..86 / 値 87..110 / 改行 111。
集合の行は要素ごと: 組の最初の行だけが名と鍵と `{`（87）を書き、ほかは `, `（88,89）、要素 90..113、
組の最後の行が `}`（114）と改行（115）を書く。名は三十二文字まで（下ろしは十七文字以上の場を付け替える）。
"""
import os
R = "for (r) in 0 .. _Rz[0]"
L = []
L.append("# ── print を _o に下ろす機械（下ろした本の末尾に一度だけ置く。work/lower/mkengine.py が起こす）──")
L.append("# 行 r は印字する升（集合なら要素）の線形の番号。字は決まった席に置き、⊥ の席は render が飛ばす（幅 0）。")
L.append("# 席: 名 0..31 / `[` 32 / 座標0 33..56 / `, ` 57,58 / 座標1 59..82 / `] = ` 83..86 / 値 87..110 / 改行 111。")
L.append("# 集合: 組の最初の行が名・鍵・`{`（87）、ほかは `, `（88,89）、要素 90..113、最後の行が `}`（114）と改行（115）")
decl = """field _o : max bound 65536 116
field _pv : max bound 65536
field _pk1 : max bound 65536
field _pk2 : max bound 65536
field _pp : max bound 65536
field _pab : max bound 65536
field _pq : max bound 65536
field _pbs : max bound 64
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
field _pea : or bound 64                     # 集合の要素は原子
field _pe : max bound 65536                  # 行 r の要素
field _pgs : max bound 65536                 # 行 r の組（同じ鍵の集合）の頭の行
field _gf : min bound 65536                  # 組の最初の要素の行
field _gl : max bound 65536                  # 組の最後の要素の行
field _ph : or bound 65536                   # 行 r は名と鍵を書く"""
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
    L.append(f"field {q} : max bound 65536 10")
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
L.append(f"_pab[r] <- _pv[r]   {R} if _pv[r] >= 0 if _pp[r] >= 0 if not _por[_pp[r]] if not _pav[_pp[r]] if not _pst[_pp[r]]")
L.append(f"_pab[r] <- 0 - _pv[r]   {R} if _pv[r] < 0 if _pp[r] >= 0 if not _por[_pp[r]] if not _pav[_pp[r]] if not _pst[_pp[r]]")
L.append(f"# 十九桁は一つの割り算で出せない（10^18 の上は 64 ビットの積が溢れる）ので、下九桁と上に分ける")
L.append(f"_pq[r] <- _pab[r] / 1000000000   {R}")
E = V + 23
# 下九桁は `_pab % 10^9`、上は `_pq`。下の上の桁の 0 は、上が在るときだけ 0 と書く
digits("_dv0", "_pab[r] % 1000000000", E, "")
L.append(f"_o[r, e + {E-9}] <- 48   {R} for (e) in 1 .. 8 if _pq[r] >= 1 if _dv0[r, e] == 0")
digits("_dv1", "_pq[r]", E - 9, "if _pq[r] >= 1")
L.append(f"_o[r, {E+1}] <- 10   {R} if _pp[r] >= 0 if not _pst[_pp[r]]")
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
L.append("render _o")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.lx"), "w", encoding="utf-8").write("\n".join(L) + "\n")
