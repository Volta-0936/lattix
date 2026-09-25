#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attest/attest.lx を組む —— 答えの検査器（.lx）。

    一段目〜四段目   attest/base.lx（手で書いた: 入力を読み分ける・表を場に開く・升・実例を数える）
    出現            attest/occ.py（実例ごとの座標と読み。三段まで）
    ここ            ガード・項・寄与・検査・判定を描く

規則は形が繰り返すので Python で書き出す。書き出した .lx が attest そのものであり、
Python は組むときにしか現れない（焼いたあとは .lx だけ）。

    python3 attest/mkeval.py [実例の数（既定 131072）] [出す先（既定 attest/attest.lx）]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import occ
NI = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get('ATTEST_NI', '131072'))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('ATTEST_OUT', os.path.join(HERE, 'attest.lx'))
src = occ.source(NI)

L = []
a = L.append
N1 = NI
NJ = "for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]]"

a("""
# ══ 出現の段をまとめる（読む側は段を知らない）═══════════════════════════════""")
for f, lat, what in [('opr', 'or', '読んだ升は ⊥ でない（⊤ を含む）'), ('otp', 'or', '読んだ升は ⊤'),
                     ('ocp', 'or', '座標に ⊤ を読んだ'), ('oun', 'or', '座標が無い'), ('oot', 'or', '広さの外'),
                     ('ocl', 'max', '升'), ('ovl', 'flat', '読んだ値')]:
    a(f"field {f} : {lat} bound {N1} 16                # {what}")
for lv in (0, 1, 2):
    c = f"{NJ} if olv[noo[n, j]] == {lv}"
    a(f"opr[n, j] <- true   {c} if q{lv}pr[n, j]")
    a(f"otp[n, j] <- true   {c} if q{lv}tp2[n, j]")
    a(f"ocp[n, j] <- true   {c} if q{lv}tp[n, j]")
    a(f"oun[n, j] <- true   {c} if q{lv}un[n, j]")
    a(f"oot[n, j] <- true   {c} if q{lv}ot[n, j]")
    a(f"ocl[n, j] <- q{lv}cl[n, j]   {c}")
    a(f"ovl[n, j] <- q{lv}vl[n, j]   {c}")
a(f"""# **持たないもの** —— 鎖の四段目より深い出現、座標に ⊤ を読んだ出現。検査したとは言わない
field nuns : or bound {N1}                      # 実例 n は attest が持たない形を含む
nuns[n] <- true   {NJ} if olv[noo[n, j]] >= 3
nuns[n] <- true   {NJ} if ocp[n, j]
nuns[n] <- true   {NJ} if olv[noo[n, j]] >= 1 if nar[n, j] == 3
field rbig : or bound 2048                      # 所有者が 16 を超える規則（検査しない）
rbig[r] <- true   for (r) in 0 .. nrlz[0] if rocn[r] >= 17
""")

# ── ガード ───────────────────────────────────────────────────────────
a(f"""# ══ ガード ═══════════════════════════════════════════════════════════════
# 規則のガードの行は隣り合う（節に沿った鎖）。規則 r の最初の行と数
field rgf : min bound 2048
rgf[gr[g]] <- g   for (g) in 0 .. nggz[0]
field rgl : max bound 2048
rgl[gr[g]] <- g   for (g) in 0 .. nggz[0]
field rgc : max bound 2048
rgc[r] <- 0   for (r) in 0 .. nrlz[0]
rgc[r] <- rgl[r] - rgf[r] + 1   for (r) in 0 .. nrlz[0] if rgl[r] >= 0
field ngc2 : max bound {N1}                     # 実例 n のガードの行の数
ngc2[n] <- rgc[nr[n]]   for (n) in 0 .. ninz[0]
field ngf : max bound {N1}
ngf[n] <- rgf[nr[n]]   for (n) in 0 .. ninz[0] if ngc2[n] >= 1
field ngg2 : max bound {N1} 16                  # 実例 n の k 番目のガードの行
ngg2[n, k] <- ngf[n] + k   for (n) in 0 .. ninz[0] for (k) in 0 .. 15 if k < ngc2[n]
field ngj : max bound {N1} 16                   # その行の読みの出現（規則の中の番号）
ngj[n, k] <- goo[ngg2[n, k]] - nro[n]   for (n) in 0 .. ninz[0] for (k) in 0 .. 15 if k < ngc2[n]
      if gk[ngg2[n, k]] == 9
ngj[n, k] <- goo[ngg2[n, k]] - nro[n]   for (n) in 0 .. ninz[0] for (k) in 0 .. 15 if k < ngc2[n]
      if gk[ngg2[n, k]] == 2
ngj[n, k] <- goo[ngg2[n, k]] - nro[n]   for (n) in 0 .. ninz[0] for (k) in 0 .. 15 if k < ngc2[n]
      if gk[ngg2[n, k]] >= 3 if gk[ngg2[n, k]] <= 4 if gok[ngg2[n, k]] == 0
field gfl : or bound {N1}                       # 実例 n のガードのどれかが立たない
field gbig : or bound 2048                      # ガードの行が 16 を超える規則（検査しない）
gbig[r] <- true   for (r) in 0 .. nrlz[0] if rgc[r] >= 17
""")
GK = f"for (n) in 0 .. ninz[0] for (k) in 0 .. 15 if k < ngc2[n]"
# 読みのガード（9）と not のガード（2）
a(f"gfl[n] <- true   {GK} if gk[ngg2[n, k]] == 9 if oun[n, ngj[n, k]]")
a(f"gfl[n] <- true   {GK} if gk[ngg2[n, k]] == 9 if oot[n, ngj[n, k]]")
a(f"gfl[n] <- true   {GK} if gk[ngg2[n, k]] == 9 if not oun[n, ngj[n, k]] if not oot[n, ngj[n, k]]")
a(f"      if not opr[n, ngj[n, k]]")
a(f"gfl[n] <- true   {GK} if gk[ngg2[n, k]] == 9 if opr[n, ngj[n, k]] if not otp[n, ngj[n, k]]")
a(f"      if ovl[n, ngj[n, k]] == 0")
a(f"gfl[n] <- true   {GK} if gk[ngg2[n, k]] == 2 if oun[n, ngj[n, k]]")
a(f"gfl[n] <- true   {GK} if gk[ngg2[n, k]] == 2 if opr[n, ngj[n, k]] if otp[n, ngj[n, k]]")
a(f"gfl[n] <- true   {GK} if gk[ngg2[n, k]] == 2 if opr[n, ngj[n, k]] if not otp[n, ngj[n, k]]")
a(f"      if ovl[n, ngj[n, k]] != 0")
# 比較の辺の値
a(f"""field gsv : flat bound {N1} 16                  # 比較の辺の値の四倍
field gsm : or bound {N1} 16                    # 比較の辺が無い（読みが ⊥・座標が無い・広さの外）
field gsq : max bound {N1} 16                   # 辺が語の表の列なら、その語""")
S = f"{GK} if gk[ngg2[n, k]] >= 3 if gk[ngg2[n, k]] <= 4"
a(f"gsv[n, k] <- gov[ngg2[n, k]] * 4   {S} if gok[ngg2[n, k]] == 3")
for kk in (0, 1, 2):
    a(f"gsv[n, k] <- nk{kk}[n] * 4   {S} if gok[ngg2[n, k]] == 2 if gc1[ngg2[n, k]] == {kk}")
a(f"gsv[n, k] <- na0[n] * 4   {S} if gok[ngg2[n, k]] == 1 if inpw[0] == 1 if gc1[ngg2[n, k]] == 0")
a(f"gsv[n, k] <- urb[na0[n]] * 4   {S} if gok[ngg2[n, k]] == 1 if inpw[0] == 1 if gc1[ngg2[n, k]] == 1")
a(f"gsq[n, k] <- nq0[n] + gc1[ngg2[n, k]]   {S} if gok[ngg2[n, k]] == 1 if inpw[0] == 8")
a(f"gsv[n, k] <- uwv[gsq[n, k]]   {S} if gok[ngg2[n, k]] == 1 if inpw[0] == 8")
a(f"gsv[n, k] <- ovl[n, ngj[n, k]]   {S} if gok[ngg2[n, k]] == 0 if opr[n, ngj[n, k]] if not otp[n, ngj[n, k]]")
a(f"gsm[n, k] <- true   {S} if gok[ngg2[n, k]] == 0 if not opr[n, ngj[n, k]]")
a(f"gsm[n, k] <- true   {S} if gok[ngg2[n, k]] == 0 if oun[n, ngj[n, k]]")
a(f"gsm[n, k] <- true   {S} if gok[ngg2[n, k]] == 0 if oot[n, ngj[n, k]]")
a(f"nuns[n] <- true   {S} if gok[ngg2[n, k]] == 0 if otp[n, ngj[n, k]]     # ⊤ を比べる")
# 比較: 左の行 k、右の行 k + 1、演算子は右の行の ggv
C = f"for (n) in 0 .. ninz[0] for (k) in 0 .. 15 if k < ngc2[n] if gk[ngg2[n, k]] == 3"
a(f"field gop : max bound {N1} 16                  # 比較の演算子（左の行に置く）")
a(f"gop[n, k] <- ggv[ngg2[n, k] + 1]   {C}")
a(f"gfl[n] <- true   {C} if gsm[n, k]")
a(f"gfl[n] <- true   {C} if gsm[n, k+1]")
for op, neg in [(1, '!='), (2, '=='), (3, '<'), (4, '>'), (5, '<='), (6, '>=')]:
    a(f"gfl[n] <- true   {C} if gop[n, k] == {op} if gsv[n, k] {neg} gsv[n, k+1]")

# ── 項 ─────────────────────────────────────────────────────────────
a(f"""
# ══ 項（群の和）═══════════════════════════════════════════════════════════
field rtf : min bound 2048
rtf[tr[g]] <- g   for (g) in 0 .. ngtz[0]
field rtl : max bound 2048
rtl[tr[g]] <- g   for (g) in 0 .. ngtz[0]
field rtc : max bound 2048
rtc[r] <- 0   for (r) in 0 .. nrlz[0]
rtc[r] <- rtl[r] - rtf[r] + 1   for (r) in 0 .. nrlz[0] if rtl[r] >= 0
field ntc : max bound {N1}                      # 実例 n の項の数
ntc[n] <- rtc[nr[n]]   for (n) in 0 .. ninz[0]
field ntf : max bound {N1}
ntf[n] <- rtf[nr[n]]   for (n) in 0 .. ninz[0] if ntc[n] >= 1
field ntt : max bound {N1} 8                    # 実例 n の t 番目の項の行
ntt[n, t] <- ntf[n] + t   for (n) in 0 .. ninz[0] for (t) in 0 .. 7 if t < ntc[n]
field ntk : max bound {N1} 8                    # その種
ntk[n, t] <- tk[ntt[n, t]]   for (n) in 0 .. ninz[0] for (t) in 0 .. 7 if t < ntc[n]
field ntj : max bound {N1} 8                    # 読みの項の出現（規則の中の番号）
field tpv : flat bound {N1} 8                   # 項の値の四倍
field tab : or bound {N1}                       # 実例 n の読みの項のどれかが無い
field ttp : or bound {N1}                       # 実例 n の読みの項のどれかが ⊤
field tqw : max bound {N1} 8                    # 列の項が語の表なら、その語
# 二のべき（割る・余りの寄せ量）
field pw : max bound 64
pw[0] <- 1
pw[k] <- pw[k-1] * 2   for (k) in 1 .. 62
field tsh : max bound 8192                      # 割る・余りの項の寄せ量
tsh[g] <- k   for (g) in 0 .. ngtz[0] for (k) in 0 .. 62 if tk[g] >= 7 if tk[g] <= 8 if pw[k] == tvl[g]
""")
T = f"for (n) in 0 .. ninz[0] for (t) in 0 .. 7 if t < ntc[n]"
TV = f"{T} if not gfl[n]"      # 値はガードが立つ実例でだけ作る（立たない実例の値は焼いた側も作らない —— 溢れうる）
for kind in (1, 5, 6):
    a(f"tpv[n, t] <- tvl[ntt[n, t]] * 4   {TV} if ntk[n, t] == {kind}")
for kind in (4, 13, 14):
    for kk in (0, 1, 2):
        a(f"tpv[n, t] <- nk{kk}[n] * 4   {TV} if ntk[n, t] == {kind} if tc1[ntt[n, t]] == {kk}")
for kind in (2, 11, 12):
    a(f"tpv[n, t] <- na0[n] * 4   {TV} if ntk[n, t] == {kind} if inpw[0] == 1 if tc1[ntt[n, t]] == 0")
    a(f"tpv[n, t] <- urb[na0[n]] * 4   {TV} if ntk[n, t] == {kind} if inpw[0] == 1 if tc1[ntt[n, t]] == 1")
    a(f"tqw[n, t] <- nq0[n] + tc1[ntt[n, t]]   {T} if ntk[n, t] == {kind} if inpw[0] == 8")
    a(f"tpv[n, t] <- uwv[tqw[n, t]]   {TV} if ntk[n, t] == {kind} if inpw[0] == 8")
for kind in (3, 9, 10):
    a(f"ntj[n, t] <- too[ntt[n, t]] - nro[n]   {T} if ntk[n, t] == {kind}")
R = f"{T} if ntk[n, t] >= 9 if ntk[n, t] <= 10"
for cond in (f"{T} if ntk[n, t] == 3", R):
    a(f"tpv[n, t] <- 4   {cond} if not gfl[n] if opr[n, ntj[n, t]] if nol[n, ntj[n, t]] == 3")
    a(f"tpv[n, t] <- ovl[n, ntj[n, t]]   {cond} if not gfl[n] if opr[n, ntj[n, t]] if not otp[n, ntj[n, t]]")
    a(f"      if nol[n, ntj[n, t]] != 3")
    a(f"tab[n] <- true   {cond} if not opr[n, ntj[n, t]]")
    a(f"tab[n] <- true   {cond} if oun[n, ntj[n, t]]")
    a(f"tab[n] <- true   {cond} if oot[n, ntj[n, t]]")
    a(f"ttp[n] <- true   {cond} if otp[n, ntj[n, t]]")
# 群の鎖 —— **項ごとに場を分ける**（gv0 … gv7）。値の大きさを比べて溢れを避けるので、一つの場の中で
# t-1 から t へ鎖を張ると「閉路の中の比較」になって成層できない。項は八つまで（理由 3）。
# 値の幅: 四倍の値は [-2^62, 2^62) に置く。二つの足し算は溢れない（[-2^63, 2^63) に収まる）ので、
# 足してから幅を見る。掛け算は先に桁の数（ビットの長さ）を足して見る —— 溢れる掛け算は作らない。
# 幅を越える実例には vbig の印を付けて値を置かない（判定は「持てない値」と言う）。
a(f"""field tlead : or bound {N1} 8                  # 群の先頭（掛ける・割る・余りでない）
tlead[n, t] <- true   {T} if ntk[n, t] <= 5
tlead[n, t] <- true   {T} if ntk[n, t] == 9
tlead[n, t] <- true   {T} if ntk[n, t] == 11
tlead[n, t] <- true   {T} if ntk[n, t] == 13
field tneg : or bound {N1} 8                    # 引く項（群の符号）
tneg[n, t] <- true   {T} if ntk[n, t] == 5
tneg[n, t] <- true   {T} if ntk[n, t] == 9
tneg[n, t] <- true   {T} if ntk[n, t] == 11
tneg[n, t] <- true   {T} if ntk[n, t] == 13
field tmg : or bound {N1} 8                     # 掛ける・割る・余りの項（群は前を引き継ぐ）
tmg[n, t] <- true   {T} if t >= 1 if not tlead[n, t]
field tmul : or bound {N1} 8                    # 掛ける項
tmul[n, t] <- true   {T} if ntk[n, t] == 6
tmul[n, t] <- true   {T} if ntk[n, t] == 10
tmul[n, t] <- true   {T} if ntk[n, t] == 12
tmul[n, t] <- true   {T} if ntk[n, t] == 14
field tb : max bound {N1} 8                     # 割る・余りの寄せ量
tb[n, t] <- tsh[ntt[n, t]]   {T} if ntk[n, t] >= 7 if ntk[n, t] <= 8
field tpw : max bound {N1} 8                    # 2^寄せ量
tpw[n, t] <- pw[tb[n, t]]   {T} if ntk[n, t] >= 7 if ntk[n, t] <= 8
field tb0 : max bound {N1} 8                    # 寄せ量の六つの桁
tb0[n, t] <- tb[n, t] % 2   {T} if ntk[n, t] >= 7 if ntk[n, t] <= 8
field tb1 : max bound {N1} 8
tb1[n, t] <- tb[n, t] / 2 % 2   {T} if ntk[n, t] >= 7 if ntk[n, t] <= 8
field tb2 : max bound {N1} 8
tb2[n, t] <- tb[n, t] / 4 % 2   {T} if ntk[n, t] >= 7 if ntk[n, t] <= 8
field tb3 : max bound {N1} 8
tb3[n, t] <- tb[n, t] / 8 % 2   {T} if ntk[n, t] >= 7 if ntk[n, t] <= 8
field tb4 : max bound {N1} 8
tb4[n, t] <- tb[n, t] / 16 % 2   {T} if ntk[n, t] >= 7 if ntk[n, t] <= 8
field tb5 : max bound {N1} 8
tb5[n, t] <- tb[n, t] / 32 % 2   {T} if ntk[n, t] >= 7 if ntk[n, t] <= 8
field npw : min bound 64                        # -2^k
npw[k] <- 0 - pw[k]   for (k) in 0 .. 62
field vbig : or bound {N1}                      # 実例 n の値が attest の幅の外
# 掛ける項の値のビットの長さ（|値| < 2^長さ）
field lbt : max bound {N1} 8
lbt[n, t] <- 0   {T} if tmul[n, t] if tpv[n, t] == 0
lbt[n, t] <- k + 1   for (n) in 0 .. ninz[0] for (t) in 0 .. 7 for (k) in 0 .. 62 if t < ntc[n] if tmul[n, t]
      if tpv[n, t] >= pw[k]
lbt[n, t] <- k + 1   for (n) in 0 .. ninz[0] for (t) in 0 .. 7 for (k) in 0 .. 62 if t < ntc[n] if tmul[n, t]
      if tpv[n, t] <= npw[k]
""")
DIVS = [2, 4, 16, 256, 65536, 4294967296]
for t in range(8):
    Nt = f"for (n) in 0 .. ninz[0] if ntc[n] >= {t + 1}"
    a(f"# ── 項 {t}")
    a(f"field gv{t} : flat bound {N1}                    # 群の値の四倍（項 {t} までの積）")
    a(f"field gs{t} : max bound {N1}                     # 群の符号（1 / -1）")
    a(f"field ga{t} : flat bound {N1}                    # 項 {t} の群より前の群の和")
    if t == 0:
        # 最初の項: 単項の `-` は最初の項に掛かる
        a(f"gv0[n] <- tpv[n, 0]   {Nt} if not tneg[n, 0]")
        a(f"gv0[n] <- 0 - tpv[n, 0]   {Nt} if tneg[n, 0]")
        a(f"gs0[n] <- 1   {Nt}")
        a(f"ga0[n] <- 0   {Nt}")
    else:
        p = t - 1
        # 群の先頭: 前の群を和に足す（足してから幅を見る）
        a(f"field gar{t} : flat bound {N1}                   # 足したまま（幅を見る前）")
        a(f"gv{t}[n] <- tpv[n, {t}]   {Nt} if tlead[n, {t}]")
        a(f"gs{t}[n] <- 1   {Nt} if tlead[n, {t}] if not tneg[n, {t}]")
        a(f"gs{t}[n] <- 0 - 1   {Nt} if tlead[n, {t}] if tneg[n, {t}]")
        a(f"gar{t}[n] <- ga{p}[n] + gs{p}[n] * gv{p}[n]   {Nt} if tlead[n, {t}]")
        a(f"ga{t}[n] <- gar{t}[n]   {Nt} if tlead[n, {t}] if gar{t}[n] >= npw[62] if gar{t}[n] < pw[62]")
        a(f"vbig[n] <- true   {Nt} if tlead[n, {t}] if gar{t}[n] < npw[62]")
        a(f"vbig[n] <- true   {Nt} if tlead[n, {t}] if gar{t}[n] >= pw[62]")
        # 掛ける・割る・余り: 群は前を引き継ぐ
        a(f"gs{t}[n] <- gs{p}[n]   {Nt} if tmg[n, {t}]")
        a(f"ga{t}[n] <- ga{p}[n]   {Nt} if tmg[n, {t}]")
        # 掛ける: |gv / 4| < 2^(lbg - 2)、|tpv| < 2^lbt。和が 64 以下なら積は 2^62 未満
        a(f"field lbs{t} : max bound {N1}")
        a(f"lbs{t}[n] <- lbg{p}[n] + lbt[n, {t}]   {Nt} if tmul[n, {t}]")
        a(f"gv{t}[n] <- gv{p}[n] / 4 * tpv[n, {t}]   {Nt} if tmul[n, {t}] if lbs{t}[n] <= 64")
        a(f"vbig[n] <- true   {Nt} if tmul[n, {t}] if lbs{t}[n] >= 65")
        # 割る 2^k: 寄せ量の六つの桁で段ずつ（四倍の値 4a を 2^(m+2) で割ると床(a / 2^m)。4 を掛けて戻す）
        D = f"{Nt} if ntk[n, {t}] >= 7 if ntk[n, {t}] <= 8"
        for i in range(6):
            a(f"field dv{t}{i} : flat bound {N1}")
            prev = f"gv{p}[n]" if i == 0 else f"dv{t}{i - 1}[n]"
            a(f"dv{t}{i}[n] <- {prev} / {DIVS[i] * 4} * 4   {D} if tb{i}[n, {t}] == 1")
            a(f"dv{t}{i}[n] <- {prev}   {D} if tb{i}[n, {t}] == 0")
        a(f"gv{t}[n] <- dv{t}5[n]   {Nt} if ntk[n, {t}] == 7")
        # 余り 2^k: 4a - 4 床(a / 2^k) 2^k。k が 61 以上で a が負なら答え（2^k に近い）は幅の外
        a(f"gv{t}[n] <- gv{p}[n] - dv{t}5[n] * tpw[n, {t}]   {Nt} if ntk[n, {t}] == 8 if tb[n, {t}] <= 60")
        a(f"gv{t}[n] <- gv{p}[n] - dv{t}5[n] * tpw[n, {t}]   {Nt} if ntk[n, {t}] == 8 if tb[n, {t}] >= 61")
        a(f"      if gv{p}[n] >= 0")
        a(f"vbig[n] <- true   {Nt} if ntk[n, {t}] == 8 if tb[n, {t}] >= 61 if gv{p}[n] < 0")
    if t <= 6:
        # 次の項が掛ける項なら、この群の値のビットの長さが要る
        Nn = f"for (n) in 0 .. ninz[0] if ntc[n] >= {t + 2}"
        a(f"field lbg{t} : max bound {N1}")
        a(f"lbg{t}[n] <- 0   {Nn} if tmul[n, {t + 1}] if gv{t}[n] == 0")
        Nk = f"for (n) in 0 .. ninz[0] for (k) in 0 .. 62 if ntc[n] >= {t + 2}"
        a(f"lbg{t}[n] <- k + 1   {Nk} if tmul[n, {t + 1}] if gv{t}[n] >= pw[k]")
        a(f"lbg{t}[n] <- k + 1   {Nk} if tmul[n, {t + 1}] if gv{t}[n] <= npw[k]")
a(f"""# 実例 n の値: 最後の項の群を和に足す（足してから幅を見る）
field nvr : flat bound {N1}""")
for t in range(8):
    a(f"nvr[n] <- ga{t}[n] + gs{t}[n] * gv{t}[n]   for (n) in 0 .. ninz[0] if ntc[n] == {t + 1}")
a(f"""field nval : flat bound {N1}                    # 実例 n の値の四倍（項が無ければ `or` の true）
nval[n] <- nvr[n]   for (n) in 0 .. ninz[0] if ntc[n] >= 1 if nvr[n] >= npw[62] if nvr[n] < pw[62]
vbig[n] <- true   for (n) in 0 .. ninz[0] if ntc[n] >= 1 if nvr[n] < npw[62]
vbig[n] <- true   for (n) in 0 .. ninz[0] if ntc[n] >= 1 if nvr[n] >= pw[62]
nval[n] <- 4   for (n) in 0 .. ninz[0] if ntc[n] == 0
""")

# ── 寄与 ───────────────────────────────────────────────────────────
a(f"""
# ══ 寄与（ガードが立ち、値があり、書き先の升が広さの内側）══════════════════════
field nhj : max bound {N1}                      # 書き先の出現（規則の中の番号）
nhj[n] <- roo[nr[n]] - nro[n]   for (n) in 0 .. ninz[0]
field nst : max bound {N1}                      # 実例 n の層
nst[n] <- rst[nr[n]]   for (n) in 0 .. ninz[0]
field nwf : max bound {N1}                      # 書き先の場
nwf[n] <- rwf[nr[n]]   for (n) in 0 .. ninz[0]
field nlt : max bound {N1}                      # 書き先の束
nlt[n] <- flt[nwf[n]]   for (n) in 0 .. ninz[0]
field fire : or bound {N1}                      # 実例 n は寄与する
fire[n] <- true   for (n) in 0 .. ninz[0] if not gfl[n] if not tab[n] if not oun[n, nhj[n]]
      if not oot[n, nhj[n]] if not nuns[n]
field nout : or bound {N1}                      # 書き先が広さの外（焼いた側は終了コード 6 で止まるはず）
nout[n] <- true   for (n) in 0 .. ninz[0] if not gfl[n] if not tab[n] if oot[n, nhj[n]] if not nuns[n]
field ncel : max bound {N1}                     # 書き先の升
ncel[n] <- ocl[n, nhj[n]]   for (n) in 0 .. ninz[0] if fire[n]
field ntop : or bound {N1}                      # 寄与は ⊤
ntop[n] <- true   for (n) in 0 .. ninz[0] if fire[n] if ttp[n]
nuns[n] <- true   for (n) in 0 .. ninz[0] if ttp[n] if not gfl[n] if nlt[n] != 6      # flat でない場への ⊤
field cval : flat bound {N1}                    # 寄与の値の四倍（or と count は 1）
cval[n] <- nval[n]   for (n) in 0 .. ninz[0] if fire[n] if not ttp[n] if nlt[n] != 3 if nlt[n] != 9
cval[n] <- 4   for (n) in 0 .. ninz[0] if fire[n] if nlt[n] == 3
cval[n] <- 4   for (n) in 0 .. ninz[0] if fire[n] if nlt[n] == 9
# min / max の升への寄与は、値そのものを束の場に置いて比べる。印を越える寄与（min で 2147483647 から
# 上、max で -2147483647 から下）は焼いた側も持てない（終了コード 4 で止まる）—— 持てない値と言う
field nbig : or bound {N1}
nbig[n] <- true   for (n) in 0 .. ninz[0] if fire[n] if nlt[n] == 1 if cval[n] >= k31[3]
nbig[n] <- true   for (n) in 0 .. ninz[0] if fire[n] if nlt[n] == 2 if cval[n] <= k4n[0]
# 同じ層の読みの階数の最大（書き先の升そのものは読みではない）
field wst : or bound 256 128                    # 場 f は層 s で書かれる
wst[rwf[r], rst[r]] <- true   for (r) in 0 .. nrlz[0]
field nmr : max bound {N1}
nmr[n] <- 0   for (n) in 0 .. ninz[0]
nmr[n] <- sk[ocl[n, j]]   {NJ} if j != nhj[n] if opr[n, j] if wst[nof[n, j], nst[n]]
""")
for lv in (0, 1, 2):
    for d in (0, 1):
        a(f"nmr[n] <- sk[q{lv}i{d}[n, j]]   {NJ} if olv[noo[n, j]] == {lv} if sp[q{lv}i{d}[n, j]]")
        a(f"      if wst[ccf[osd{d}[n, j]], nst[n]]")

# ── 種 ─────────────────────────────────────────────────────────────
a(f"""
# ══ 種（寄与は階数 0 の読みから）═══════════════════════════════════════════
field aS : max bound 4096
aS[s] <- sb[z] + s * 3   for (z) in 1 .. 1 for (s) in 0 .. nsdz[0]
field sdf : max bound 4096
sdf[s] <- wd[aS[s]]   for (s) in 0 .. nsdz[0]
field sdc : max bound 4096
sdc[s] <- wd[aS[s] + 1]   for (s) in 0 .. nsdz[0]
field sdv : max bound 4096
sdv[s] <- wd[aS[s] + 2]   for (s) in 0 .. nsdz[0]
field scel : max bound 4096
scel[s] <- fcb[sdf[s]] + sdc[s]   for (s) in 0 .. nsdz[0]
field slt : max bound 4096
slt[s] <- flt[sdf[s]]   for (s) in 0 .. nsdz[0]
field sval : flat bound 4096                    # 種の値の四倍（count は 1、or は 1）
sval[s] <- sdv[s] * 4   for (s) in 0 .. nsdz[0] if slt[s] != 9 if slt[s] != 3
sval[s] <- 4   for (s) in 0 .. nsdz[0] if slt[s] == 9
sval[s] <- 4   for (s) in 0 .. nsdz[0] if slt[s] == 3
""")

# ── 検査 ───────────────────────────────────────────────────────────
a(f"""
# ══ 検査 ════════════════════════════════════════════════════════════════
# (A) 安定性: どの寄与も吸収されている。(B) 有基性: どの値も、より小さい階数の寄与から導ける。
# 束ごとに寄与を束ねる場を置く（min は min の場で、max は max の場で —— 印の範囲が揃う）
field cmn : min bound 262144                    # min の升への寄与の最小
field gmn : min bound 262144                    # そのうち階数が小さいもの
field cmx : max bound 262144
field gmx : max bound 262144
field cor : or bound 262144                     # or の升に寄与がある
field gor : or bound 262144
field csm : sum bound 262144                    # sum / count の寄与の和
field chs : or bound 262144                     # 升に寄与がある（束によらない）
field ctp : or bound 262144                     # flat の升に ⊤ の寄与
field gtp : or bound 262144                     # そのうち階数が小さいもの
field fvn : min bound 262144                    # flat の升の最初の寄与（実例の番号。種は -1 - 種）
field fdif : or bound 262144                    # flat の升に、最初と違う値の寄与
field fgeq : or bound 262144                    # flat の升に、答えと同じ値の、階数の小さい寄与
field fneq : or bound 262144                    # flat の升に、答えと違う値の寄与
field fgn : min bound 262144                    # flat の升の、階数の小さい最初の寄与（種は -1 - 種）
field gdif : or bound 262144                    # flat の升に、それと違う値の、階数の小さい寄与
field cnt : or bound 262144                     # 升に、同じ層の ⊤ を読んだ寄与がある
field ggp : or bound 262144                     # 升に階数の小さい寄与がある（束によらない）
""")
I = f"for (n) in 0 .. ninz[0] if fire[n]"
a(f"cmn[ncel[n]] <- cval[n] / 4   {I} if nlt[n] == 1 if cval[n] < k31[3]")
a(f"gmn[ncel[n]] <- cval[n] / 4   {I} if nlt[n] == 1 if cval[n] < k31[3] if nmr[n] < sk[ncel[n]]")
a(f"cmx[ncel[n]] <- cval[n] / 4   {I} if nlt[n] == 2 if cval[n] > k4n[0]")
a(f"gmx[ncel[n]] <- cval[n] / 4   {I} if nlt[n] == 2 if cval[n] > k4n[0] if nmr[n] < sk[ncel[n]]")
a(f"cor[ncel[n]] <- true   {I} if nlt[n] == 3")
a(f"gor[ncel[n]] <- true   {I} if nlt[n] == 3 if nmr[n] < sk[ncel[n]]")
a(f"csm[ncel[n]] <- cval[n]   {I} if nlt[n] >= 8")
# **集約の寄与にも階数の規律が要る。** `c <- 1 if c`（count）に c = 1 と書くと、その 1 が寄与を立て、
# 寄与が 1 を作る（最小不動点は ⊥）。和の一致だけ見ていた間は ATTESTED と言った（2026-09-20、偽物を
# 数え上げて見つけた）。小さい階数から来ない寄与に支えられた集約は示せない（UNSUPPORTED）。
# 階数 0 の在る升は、どの束でも (B) の破れとして下（vgh）で言う
a("field agr : or bound 262144                    # 集約の升に、階数の小さくない読みの寄与がある")
a(f"agr[ncel[n]] <- true   {I} if nlt[n] >= 8 if nmr[n] >= sk[ncel[n]] if sk[ncel[n]] >= 1")
a(f"chs[ncel[n]] <- true   {I}")
a(f"ggp[ncel[n]] <- true   {I} if nmr[n] < sk[ncel[n]]")
a(f"ctp[ncel[n]] <- true   {I} if nlt[n] == 6 if ntop[n]")
a(f"gtp[ncel[n]] <- true   {I} if nlt[n] == 6 if ntop[n] if nmr[n] < sk[ncel[n]]")
a(f"fvn[ncel[n]] <- n   {I} if nlt[n] == 6 if not ntop[n]")
a(f"fgn[ncel[n]] <- n   {I} if nlt[n] == 6 if not ntop[n] if nmr[n] < sk[ncel[n]]")
Sd = "for (s) in 0 .. nsdz[0]"
a(f"cmn[scel[s]] <- sdv[s]   {Sd} if slt[s] == 1")
a(f"gmn[scel[s]] <- sdv[s]   {Sd} if slt[s] == 1 if sk[scel[s]] >= 1")
a(f"cmx[scel[s]] <- sdv[s]   {Sd} if slt[s] == 2")
a(f"gmx[scel[s]] <- sdv[s]   {Sd} if slt[s] == 2 if sk[scel[s]] >= 1")
a(f"cor[scel[s]] <- true   {Sd} if slt[s] == 3")
a(f"gor[scel[s]] <- true   {Sd} if slt[s] == 3 if sk[scel[s]] >= 1")
a(f"csm[scel[s]] <- sval[s]   {Sd} if slt[s] >= 8")
a(f"chs[scel[s]] <- true   {Sd}")
a(f"ggp[scel[s]] <- true   {Sd} if sk[scel[s]] >= 1")
a(f"fvn[scel[s]] <- 0 - 1 - s   {Sd} if slt[s] == 6")
a(f"fgn[scel[s]] <- 0 - 1 - s   {Sd} if slt[s] == 6 if sk[scel[s]] >= 1")
a(f"""# flat の最初の寄与の値（実例か種か）
field fv1 : flat bound 262144
fv1[c] <- cval[fvn[c]]   for (c) in 0 .. nclz[0] if fvn[c] >= 0
field fvs : max bound 262144                    # 最初が種ならその番号
fvs[c] <- 0 - 1 - fvn[c]   for (c) in 0 .. nclz[0] if fvn[c] < 0
fv1[c] <- sval[fvs[c]]   for (c) in 0 .. nclz[0] if fvn[c] < 0
fdif[ncel[n]] <- true   {I} if nlt[n] == 6 if not ntop[n] if cval[n] != fv1[ncel[n]]
fdif[scel[s]] <- true   {Sd} if slt[s] == 6 if sval[s] != fv1[scel[s]]
fgeq[ncel[n]] <- true   {I} if nlt[n] == 6 if not ntop[n] if cval[n] == sv[ncel[n]] if nmr[n] < sk[ncel[n]]
fgeq[scel[s]] <- true   {Sd} if slt[s] == 6 if sval[s] == sv[scel[s]] if sk[scel[s]] >= 1
fneq[ncel[n]] <- true   {I} if nlt[n] == 6 if not ntop[n] if cval[n] != sv[ncel[n]]
fneq[scel[s]] <- true   {Sd} if slt[s] == 6 if sval[s] != sv[scel[s]]
# 階数の小さい寄与だけで数えた「違う二つの値」（⊤ を支えてよいのはこちらだけ）
field fg1 : flat bound 262144
fg1[c] <- cval[fgn[c]]   for (c) in 0 .. nclz[0] if fgn[c] >= 0
field fgs : max bound 262144
fgs[c] <- 0 - 1 - fgn[c]   for (c) in 0 .. nclz[0] if fgn[c] < 0
fg1[c] <- sval[fgs[c]]   for (c) in 0 .. nclz[0] if fgn[c] < 0
gdif[ncel[n]] <- true   {I} if nlt[n] == 6 if not ntop[n] if nmr[n] < sk[ncel[n]] if cval[n] != fg1[ncel[n]]
gdif[scel[s]] <- true   {Sd} if slt[s] == 6 if sk[scel[s]] >= 1 if sval[s] != fg1[scel[s]]
# 同じ層の flat の ⊤ を読んだ寄与（その ⊤ の前の値を読んだ時の寄与が、最終の答えからは見えない）
field nrt : or bound {N1}
nrt[n] <- true   {NJ} if j != nhj[n] if otp[n, j] if wst[nof[n, j], nst[n]]
cnt[ncel[n]] <- true   {I} if nrt[n]
""")
C = "for (c) in 0 .. nclz[0]"
a(f"""# 破れ（升ごと）
field vst : or bound 262144                     # (A) 吸収されていない寄与
field vgr : or bound 262144                     # (B) 導けない値
# min: 答え ≤ どの寄与も（答えが無いのに寄与があるのも破れ）。有基: 小さい階数の寄与の最小 ≤ 答え
vst[c] <- true   {C} if glt[c] == 1 if chs[c] if not sp[c]
vst[c] <- true   {C} if glt[c] == 1 if chs[c] if sp[c] if svn[c] > cmn[c]
vgr[c] <- true   {C} if glt[c] == 1 if sp[c] if not ggp[c]
vgr[c] <- true   {C} if glt[c] == 1 if sp[c] if gmn[c] > svn[c]
vst[c] <- true   {C} if glt[c] == 2 if chs[c] if not sp[c]
vst[c] <- true   {C} if glt[c] == 2 if chs[c] if sp[c] if svx[c] < cmx[c]
vgr[c] <- true   {C} if glt[c] == 2 if sp[c] if not ggp[c]
vgr[c] <- true   {C} if glt[c] == 2 if sp[c] if gmx[c] < svx[c]
vst[c] <- true   {C} if glt[c] == 3 if cor[c] if not sp[c]
vgr[c] <- true   {C} if glt[c] == 3 if sp[c] if not gor[c]
# sum / count: 和がそのまま答え
vst[c] <- true   {C} if glt[c] >= 8 if csm[c] if not sp[c]
vst[c] <- true   {C} if glt[c] >= 8 if sp[c] if csm[c] != sv[c]
vgr[c] <- true   {C} if glt[c] >= 8 if sp[c] if not csm[c]
# flat: ⊤ でない答えは、違う値の寄与も ⊤ の寄与も持たず、同じ値の小さい階数の寄与を持つ
vst[c] <- true   {C} if glt[c] == 6 if chs[c] if not sp[c]
vst[c] <- true   {C} if glt[c] == 6 if sp[c] if not stop[c] if fneq[c]
vst[c] <- true   {C} if glt[c] == 6 if sp[c] if not stop[c] if ctp[c]
vgr[c] <- true   {C} if glt[c] == 6 if sp[c] if not stop[c] if not fgeq[c]
# flat の ⊤ は、違う二つの値の寄与か、小さい階数の ⊤ の寄与で支えられる（違う二つの値は階数を問わない
# —— 閉路の中では flat の ⊤ は値の中でしか読めず（ガード・比較・not は成層で断られる）、値は ⊤ に
# 厳密なので、⊤ でない寄与が ⊤ に支えられることは無い）。値が一つと、同じか大きい階数の ⊤ の寄与
# しか無いものは **閉路で押し上げられた ⊤** —— 最終の答えだけでは本物（f <- f + 1 で 1 と 2）と
# 偽物（f <- f の恒等で、1 しか来ないのに ⊤ と書いたもの）を見分けられない。**検査したとは言わない。**
# （前は「破れではない」として通していた —— 恒等の偽物を ATTESTED と言った。2026-09-19 に測って直した）
# **違う二つの値も、階数の小さい寄与から数える。** 前は階数を問わなかった —— `w <- 7 if x` と
# `x <- w` の閉路で、x = ⊤ と w = 7 を偽った証明書が通った（x の ⊤ を w の 7 が支え、w の 7 を
# 「⊤ は真」が支える。最小不動点は x = 0、w = ⊥）。flat の値からのガードは単調なので（⊥ は偽、
# ⊤ は真）閉路の中に置ける —— 階数の規律を外してよい所は無い。
field ctop : or bound 262144
ctop[c] <- true   {C} if glt[c] == 6 if stop[c] if not gdif[c] if not gtp[c] if fdif[c]
ctop[c] <- true   {C} if glt[c] == 6 if stop[c] if not gdif[c] if not gtp[c] if ctp[c]
vgr[c] <- true   {C} if glt[c] == 6 if stop[c] if not gdif[c] if not gtp[c] if not fdif[c] if not ctp[c]
# 支えの無い値のうち、同じ層の ⊤ を読んだ寄与を持つものは「⊤ の前の値」が要る（最終の答えだけでは
# 示せないが、偽とも言えない）。持たないものだけを破れと言う
field vgh : or bound 262144
vgh[c] <- true   {C} if vgr[c] if not cnt[c]
vgh[c] <- true   {C} if glt[c] <= 6 if sp[c] if sk[c] == 0      # 階数 0 は前の値でも支えられない
# 階数 0 の答え。**在る升の階数は 1 以上 —— 集約でも。** 前は sum / count を除いていたので、種だけの
# 和の升を階数 0 にした証明書を、表の上の参照（寄与の読みの階数 0 が升の階数 0 を下回らない）と違って
# 通していた（2026-09-20、撒いた本の階数を 0 にして見つけた。値は正しいので嘘ではないが、証明書としては
# 何も示していない）
vgr[c] <- true   {C} if glt[c] <= 6 if sp[c] if sk[c] == 0
vgh[c] <- true   {C} if glt[c] >= 8 if sp[c] if sk[c] == 0
""")
src += "\n".join(L) + "\n"
open(OUT, 'w', encoding='utf-8').write(src)

# ══ 判定を描く ════════════════════════════════════════════════════════════
# 行 k は out の [100k, 100k + 100) に置く。描かない行の升は ⊥ のまま（render は ⊥ を飛ばす）。
# 数は十桁の右寄せ（上の桁の 0 は空白）。十で割るのは逆数を掛けて 2^32 で割る（x < 2^30 で正確）。
R = []
r = R.append
r("""
# ══ 判定 ══════════════════════════════════════════════════════════════════
field nvst : count bound 1                      # (A) の破れの升の数
nvst[0] <- 1   for (c) in 0 .. nclz[0] if vst[c]
field nvgr : count bound 1                      # (B) の破れの升の数
nvgr[0] <- 1   for (c) in 0 .. nclz[0] if vgh[c]
field nvot : count bound 1                      # 広さの外へ書く実例の数
nvot[0] <- 1   for (n) in 0 .. ninz[0] if nout[n]
field ncto : count bound 1                      # 閉路で押し上げられた ⊤
ncto[0] <- 1   for (c) in 0 .. nclz[0] if ctop[c]
field bad1 : or bound 1                         # 破れがある
bad1[0] <- true   for (c) in 0 .. nclz[0] if vst[c]
bad1[0] <- true   for (c) in 0 .. nclz[0] if vgh[c]
bad1[0] <- true   for (n) in 0 .. ninz[0] if nout[n]
field rja : or bound 1                          # (A) の破れがある
rja[0] <- true   for (c) in 0 .. nclz[0] if vst[c]
field rjo : or bound 1                          # 広さの外へ書く実例がある
rjo[0] <- true   for (n) in 0 .. ninz[0] if nout[n]
field rjb : or bound 1                          # (B) の破れがある
rjb[0] <- true   for (c) in 0 .. nclz[0] if vgh[c]
field vfst : min bound 1                        # 最初の破れの升
vfst[0] <- c   for (c) in 0 .. nclz[0] if vst[c]
vfst[0] <- c   for (c) in 0 .. nclz[0] if vgh[c]
# 持たないもの（どれか一つでもあれば、検査したとは言わない）
field un1 : or bound 8
un1[0] <- true   for (n) in 0 .. ninz[0] if nuns[n]                 # 鎖が深い・⊤ を座標や比較に使う
un1[0] <- true   for (g) in 0 .. nglz[0] if ltop[g]                 # 区間の上端が ⊤
un1[1] <- true   for (c) in 0 .. nclz[0] if sunv[c]                 # 持てない値
un1[1] <- true   for (c) in 0 .. nclz[0] if sbig[c]
un1[1] <- true   for (n) in 0 .. ninz[0] if nbig[n]
un1[1] <- true   for (n) in 0 .. ninz[0] if vbig[n]
un1[1] <- true   for (q) in 0 .. 131071 if uwun[q]
un1[2] <- true   for (r) in 0 .. nrlz[0] if rbig[r]                 # 読みやガードが 16 を超える規則
un1[2] <- true   for (r) in 0 .. nrlz[0] if gbig[r]
field ninx : max bound 1
ninx[z] <- nin2[z]   for (z) in 0 .. 0
un1[3] <- true   for (z) in 0 .. 0 if ninx[z] > NIV                   # 実例が多すぎる
un1[3] <- true   for (g) in 0 .. nglz[0] if lwid[g]                 # 区間が言語の上限より広い
un1[3] <- true   for (g) in 0 .. nglz[0] if li[g] >= 3              # 四重以上のループ（枠は三つ）
un1[3] <- true   for (g) in 0 .. nglz[0] if lk[g] == 3              # 上端が外の変数で引いた場の区間
un1[4] <- true   for (c) in 0 .. nclz[0] if ctop[c]                 # 閉路でしか支えられない ⊤
un1[5] <- true   for (c) in 0 .. nclz[0] if vgr[c] if cnt[c] if sk[c] >= 1   # ⊤ の前の値が要る
un1[6] <- true   for (c) in 0 .. nclz[0] if agr[c] if sp[c]        # 階数の小さくない寄与の集約
# 二のべきでない除数（焼き手は 09-23 から idiv で割る。attest の割り算は寄せ量の鎖で、二のべきしか
# 持たない —— 黙って値を作らずに「支えが無い」と読むより、持たないと言う）と、描く場が二つ以上
# （attest が描き直すのは最初の描く場だけ）
field tspw : or bound 8192                      # 項 g の除数は二のべき
tspw[g] <- true   for (g) in 0 .. ngtz[0] for (k) in 0 .. 62 if tk[g] >= 7 if tk[g] <= 8 if pw[k] == tvl[g]
un1[7] <- true   for (g) in 0 .. ngtz[0] if tk[g] >= 7 if tk[g] <= 8 if not tspw[g]
un1[7] <- true   for (z) in 0 .. 0 if hd[14] >= 2
field anyun : or bound 1
anyun[0] <- true   for (k) in 0 .. 7 if un1[k]
field okhd : or bound 1                         # 表の印がある
okhd[0] <- true   for (z) in 0 .. 0 if hd[0] == 20260923
field okin : or bound 1                         # 入力は attest の入力（表の印があり、値と階数の面が欠けていない）
okin[0] <- true   for (z) in 0 .. 0 if hd[0] == 20260923 if nin[z] >= 0 if not wbd[0]
# 面が欠けていると、読めない位置の升は ⊥ の印と比べられずに「在る升」になり、階数も読めない —— 判定せずに
# 入力でないと言う（前は「示せない（余計な値か、違う階数）」と偽の理由で REJECTED にしていた）。
# 表の頭か表の中に持てない語（-2147483646 より下）があるときも、表を読み違えるので判定しない（wbd）
field okbk : or bound 1                         # 源は焼ける（前段が断っていない）
okbk[0] <- true   for (z) in 0 .. 0 if badk[0] < 0
# 在る升の階数 0 は「導出を与えていない」。偽った階数か、焼いた本の階数が 2^32 - 1 を越えて 0 に
# 戻ったもの（焼いた本は階数を符号なし 32 ビットで溜め、0xFFFFFFFF の次は 0）。どちらでも示せない
field rk0 : or bound 1
rk0[0] <- true   for (c) in 0 .. nclz[0] if sp[c] if sk[c] == 0
""".replace("NIV", str(NI)))
# 描く数: 0 実例 / 1 升 / 2 (A) / 3 (B) / 4 外 / 5 最初の場 / 6 最初の升 / 7 閉路の ⊤ / 8 断りの行 / 9 断りの理由 / 10 入力のバイト数 / 11 出した答えの違うバイト
r("""field pn : max bound 16                         # 描く数
pn[0] <- 0
pn[z] <- ninx[0]   for (z) in 0 .. 0
pn[1] <- 0
pn[z] <- ncl[0]   for (z) in 1 .. 1
pn[2] <- 0
pn[z] <- nvst[0]   for (z) in 2 .. 2
pn[3] <- 0
pn[z] <- nvgr[0]   for (z) in 3 .. 3
pn[4] <- 0
pn[z] <- nvot[0]   for (z) in 4 .. 4
field vfg : max bound 2                         # 最初の破れの場と、場の中の升（定数で引いた場は座標にならない）
vfg[z] <- gf[vfst[z]]   for (z) in 0 .. 0
vfg[w] <- gc[vfst[z]]   for (z) in 0 .. 0 for (w) in 1 .. 1
pn[z] <- vfg[0]   for (z) in 5 .. 5
pn[z] <- vfg[1]   for (z) in 6 .. 6
pn[7] <- 0
pn[z] <- ncto[0]   for (z) in 7 .. 7
pn[z] <- badk[0] / 16   for (z) in 8 .. 8 if badk[0] >= 0
pn[z] <- badk[0] % 16   for (z) in 9 .. 9 if badk[0] >= 0
pn[10] <- 0
pn[z] <- nin[0]   for (z) in 10 .. 10 if nin[0] >= 0         # プログラムの入力のバイト数（何を確かめたかを言う）
pn[11] <- 0
pn[z] <- ofb[0]   for (z) in 11 .. 11 if obad[0]              # 出した答えの最初に違うバイト
field pq : max bound 16 11                      # 十で i 回割った商
pq[k, 0] <- pn[k]   for (k) in 0 .. 15
pq[k, i] <- pq[k, i-1] * 429496730 / 4294967296   for (k) in 0 .. 15 for (i) in 1 .. 10
field pd : max bound 16 11                      # i 桁目の数字
pd[k, i] <- pq[k, i] - pq[k, i+1] * 10   for (k) in 0 .. 15 for (i) in 0 .. 9
field pc : max bound 16 11                      # i 桁目の文字（上の桁の 0 は空白）
pc[k, i] <- pd[k, i] + 48   for (k) in 0 .. 15 for (i) in 0 .. 9 if pq[k, i] >= 1
pc[k, i] <- 48   for (k) in 0 .. 15 for (i) in 0 .. 0 if pq[k, i] == 0
pc[k, i] <- 32   for (k) in 0 .. 15 for (i) in 1 .. 9 if pq[k, i] == 0
field out : max bound 1300
""")
# 描く行の種類ごとに一つの印（dw）を立て、文字ごとの規則はその印だけを見る —— 文字ごとに条件を
# 全部書くと、焼き手のガードの面（8,192 行）を越える（2026-09-19 に越えた）
FLAGS = {}
r("field dw : or bound 32                          # 描く行の種類")
def flag(cond):
    if cond not in FLAGS:
        k = len(FLAGS); FLAGS[cond] = k
        r(f"dw[z] <- true   for (z) in {k} .. {k}{cond}")
    return FLAGS[cond]
def text(line, col, s, cond):
    k = flag(cond)
    for i, ch in enumerate(s.encode('ascii')):
        r(f"out[z] <- {ch}   for (z) in {100 * line + col + i} .. {100 * line + col + i} if dw[{k}]")
def num(line, col, n, cond):
    # 十桁、上の桁から
    k = flag(cond)
    for i in range(10):
        pos = 100 * line + col + i
        r(f"out[z] <- pc[{n}, {9 - i}]   for (z) in {pos} .. {pos} if dw[{k}]")
def nl(line, cond):
    k = flag(cond)
    r(f"out[z] <- 10   for (z) in {100 * line + 99} .. {100 * line + 99} if dw[{k}]")
ATT = " if okin[0] if okbk[0] if not anyun[0] if not bad1[0] if not obad[0]"
REJ = " if okin[0] if okbk[0] if not anyun[0] if bad1[0]"
REJX = " if okin[0] if okbk[0] if not anyun[0] if not bad1[0] if obad[0]"   # 証人は正しいが、出した答えが違う
# 見出しは **言えることだけを言う**。(A) の破れは「最小不動点でない」（答えは前不動点でさえない）。
# (B) の破れは「示せない」（余計な値か、違う階数か —— 最終の答えだけでは分からない）。広さの外へ
# 書く実例は、(A) も (B) も通ったとき（答えが最小不動点まで来ている）にだけ「源に答えが無い」と言う
REJA = REJ + " if rja[0]"                       # (A) の破れ —— 答えは最小不動点でない
REJB = REJ + " if not rja[0] if rjb[0]"         # (B) の破れ —— 余計な値か、違う階数
REJO = REJ + " if not rja[0] if not rjb[0]"     # 広さの外へ書く —— 源に答えが無い
UNS = " if okin[0] if okbk[0] if anyun[0]"
OK2 = " if okin[0] if okbk[0]"
NOTIN = " if not okhd[0]"
WBAD = " if okhd[0] if wbd[0]"                    # 表の語が持てない（前段はそんな語を出さない）
SHORT = " if okhd[0] if okbk[0] if not okin[0] if not wbd[0]"
UNBK = " if okhd[0] if not okbk[0] if not wbd[0]"  # 源が焼けないなら、答えの面は無くてよい
text(0, 0, "attest: ATTESTED -- the answer is the least fixed point of the source", ATT)
text(0, 0, "attest: REJECTED -- the answer is NOT the least fixed point", REJA)
text(0, 0, "attest: REJECTED -- a rule writes outside its field's bound: the source has no answer", REJO)
text(0, 0, "attest: REJECTED -- not proven: a value is not grounded (an extra fact, or a wrong rank)", REJB)
text(0, 0, "attest: REJECTED -- the output is not the answer that was checked", REJX)
text(0, 0, "attest: UNSUPPORTED -- attest cannot check this answer", UNS)
text(0, 0, "attest: NOT AN ATTEST INPUT (no table header)", NOTIN)
text(0, 0, "attest: NOT AN ATTEST INPUT (the answer and the ranks are shorter than the table says)", SHORT)
text(0, 0, "attest: NOT AN ATTEST INPUT (a table word below -2147483646)", WBAD)
text(0, 0, "attest: THE SOURCE CANNOT BE BAKED -- line ", UNBK)
num(0, 44, 8, UNBK)
text(0, 54, " reason ", UNBK)
num(0, 62, 9, UNBK)
nl(0, OK2); nl(0, NOTIN); nl(0, SHORT); nl(0, UNBK); nl(0, WBAD)
text(1, 0, "  rule instances ", OK2)
num(1, 17, 0, OK2)
text(1, 27, "   cells ", OK2)
num(1, 36, 1, OK2)
text(1, 46, "   input bytes ", OK2)
num(1, 61, 10, OK2)
nl(1, OK2)
text(2, 0, "  not stable ", REJ)
num(2, 13, 2, REJ)
text(2, 23, "   not grounded ", REJ)
num(2, 39, 3, REJ)
text(2, 49, "   writes outside ", REJ)
num(2, 67, 4, REJ)
nl(2, REJ)
FST = REJ + " if vfst[0] >= 0"
text(3, 0, "  first: field ", FST)
num(3, 15, 5, FST)
text(3, 25, "   cell ", FST)
num(3, 33, 6, FST)
nl(3, FST)
for line, k, s in [(4, 0, "  a chain of reads deeper than 3, or top read in a coordinate or comparison"),
                   (5, 1, "  a value beyond +-2^60, or past the mark of its min / max field"),
                   (6, 2, "  a rule with more than 16 reads or 16 guard rows"),
                   (7, 3, "  more rule instances than attest holds, a range over 4194304, 4+ loops, or a dependent range"),
                   (8, 4, "  a flat top that only a cycle supports (it needs the value before top)")]:
    text(line, 0, s, UNS + f" if un1[{k}]")
    nl(line, UNS + f" if un1[{k}]")
text(9, 0, "  a value that needs what a flat field held before it became top", UNS + " if un1[5]")
nl(9, UNS + " if un1[5]")
# 行 4〜8 は UNSUPPORTED の理由の行。REJECTED のときは空いているので、階数 0 の注をここに置く
text(4, 0, "  a present cell with rank 0: no derivation given (a forged rank, or one past 2^32 - 1)",
     REJ + " if rk0[0]")
nl(4, REJ + " if rk0[0]")
MISS = REJA + " if not rjb[0] if not rjo[0]"
text(9, 0, "  every value is grounded, so facts are missing: the answer is below it", MISS)
nl(9, MISS)
text(11, 0, "  an aggregate supported by reads of its own stratum at an equal or higher rank", UNS + " if un1[6]")
nl(11, UNS + " if un1[6]")
text(12, 0, "  a divisor that is not a power of two, or more than one render", UNS + " if un1[7]")
nl(12, UNS + " if un1[7]")
OBAD = OK2 + " if obad[0]"
text(10, 0, "  the output differs from the answer in the witness at byte ", OBAD)
num(10, 61, 11, OBAD)
nl(10, OBAD)
r("render out")
src = open(OUT, encoding='utf-8').read() + "\n".join(R) + "\n"
open(OUT, 'w', encoding='utf-8').write(src)
print(OUT, len(src.splitlines()))
