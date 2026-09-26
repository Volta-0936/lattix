#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**型紙を種に起こす。** —— 型紙・print の機械・塊の帯を種にして lib/lower.lx の印の間に書く。

    python3 work/mklower.py          # 型紙を変えたときだけ（lib/lower.lx の種が源として残る）
    ./lattix lower.lx lower          # 焼く —— lower.lx は三行の include（33_self・fold・lower）。Python は要らない
    ./lower prog.lx > prog.low.lx    # 下ろす
    ./lattix prog.low.lx prog        # 焼く

**型紙は読める形で書き、ここで種に起こす**（31_gen の命令の形と同じくデータで持つ）。
`{h:w}` は穴 h（0..3）を w 桁の席に右寄せで置く —— 上の桁の 0 は ⊥ のまま残り、
render が飛ばすので可変長に詰まって出る（⊥ は幅 0 の glue）。これは組む道具であって、
下ろす道には居ない（焼いた `lower` は Python を知らない）。
"""
import os, re, runpy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 型紙の番号は lib/lower.lx の規則が名指しする（番号を動かすときは両方を見る）。
# `{h:w}` は穴 h を w 桁の席に右寄せ、`@` は名前の十六升（宣言の綴り。短ければ残りは ⊥）。
LOOP2 = "\n      for (_k) in 0 .. {1:7} for (_m) in 0 .. {2:7}"
TEMPLATES = [
    (0, " (_r{0:1}) in 0 .. {1:7}"),             # 表のループ → 区間（L, 行数-1）
    (1, "_t{0:2}c{1:2}[_r{2:1}]"),                 # 表の変数 → 列の場の読み（表, 列, L）
    (2, " bound {0:7}"),                           # 広さの無い一次元の場（推した広さ）
    (3, " bound {0:7} {1:7}"),                     # 広さの無い二次元の場
    (4, "0"),                                      # `n[]` → `n[0]`
    (5, "\n_t{0:2}c{1:2}[{2:7}] <- {3:10}"),       # 表の升 → 種（表, 列, 行, 値）
    (6, "\nfield _t{0:2}c{1:2} : flat bound {2:7}"),  # 表の列 → 場（表, 列, 行数）
    (7, " {0:7} .. {1:7}"),                        # `range(a, b)` の表 → 区間 a .. b-1（変数はそのまま）
    (8, " for (_z) in 0 .. 0"),                    # 焼ける種の形でない種 → 一点の規則
    (9, "{0:7}"),                                  # 規則の中の文字列 → 綴りの順の番号
    # print（一次元）: p, …
    (10, "\nfield _pr{0:2} : max bound {1:7}"),
    (11, "\n_pr{0:2}[_k] <- _k + {1:7}   for (_k) in 0 .. {2:7}"),
    (12, "\n_pv[_pr{0:2}[_k]] <- @[_k] for (_k) in 0 .. {2:6}"),
    (13, "\n_pbs[{0:2}] <- {1:7}\n_pen[{0:2}] <- {2:7}"),
    (14, "\n_Rz[0] <- {2:7}\n_Pz[0] <- {0:2}"),
    (15, "\n_por[{0:2}] <- true"),
    # print（二次元）
    (16, "\nfield _pr{0:2} : max bound {1:7} {2:7}"),
    (17, "\n_pr{0:2}[_k, _m] <- _k * {1:7} + _m + {2:7}"),
    (18, LOOP2),
    (19, "\n_pv[_pr{0:2}[_k, _m]] <- @[_k, _m]"),
    (20, "\n_pk1[_pr{0:2}[_k, _m]] <- _k - _psh1[{0:2}]"),   # ずらしを引く（14k）
    (21, "\n_pk2[_pr{0:2}[_k, _m]] <- _m - _psh2[{0:2}]"),
    (22, "\n      if @[_k, _m] == @[_k, _m]"),
    (23, "\n_pd2[{0:2}] <- true"),
    (24, "\n_pnm[{0:2}, {1:2}] <- {2:3}"),         # 名前の字
    (25, "\n_pd0[{0:2}] <- true"),                  # `n[]` の場（座標を書かない）
    (26, "\n_pa1[{0:2}] <- true"),                  # 座標0 は原子（綴りで書く）
    (27, "\n_pa2[{0:2}] <- true"),                  # 座標1 は原子
    (28, "\n_pav[{0:2}] <- true"),                  # 値は原子
    (29, "\n_an[{0:4}, {1:2}] <- {2:3}"),           # 原子の綴り（番号, 何バイト目, バイト）
    # ANF: 区間 [ta, tb] に名前 `_g<ta>` を置く。`%` はトークンの綴り（束縛の変数名、八文字）
    (30, "\n_g{0:6}[_r{1:1}"),                      # 塊の頭 A（表のループ / 区間のループ / 一点）
    (31, "\n_g{0:6}[%"),
    (32, "\n_g{0:6}[_z"),
    (33, "] <- "),                                   # 塊の頭 B（ループ一つ / 二つ目が表 / 区間）
    (34, ", _r{1:1}] <- "),
    (35, ", %] <- "),
    (36, " for (_r{0:1}) in 0 .. {1:7}"),           # 塊のループの節
    (37, " for (%) in {0:7} .. {1:7}"),
    (38, " for (%) in {0:7} .. @[{1:7}]"),
    (39, " for (_z) in 0 .. 0"),
    (40, "\nfield _g{0:6} : flat bound {1:7}"),     # 塊の宣言
    (41, "\nfield _g{0:6} : flat bound {1:7} {2:7}"),
    (42, "_g{0:6}[_r{1:1}"),                         # 本文の参照 A / B
    (43, "_g{0:6}[%"),
    (44, "_g{0:6}[_z"),
    (45, "]"),
    (46, ", _r{1:1}]"),
    (47, ", %]"),
    # 集合: 宣言 / 書き先の要素 / 値
    (48, "or bound {0:7}"),                             # 鍵の無い集合 → 一次元の or
    (49, "or bound {0:7} {1:7}"),                       # 鍵が一つの集合 → 二次元の or
    (50, "%"),                                          # 要素が区間の変数（`s[]` の中に）
    (51, ", _t{0:2}c{1:2}[_r{2:1}]]"),                  # `s[k]` の後ろに要素（表の変数）
    (52, ", %]"),                                       #                    （区間の変数）
    (53, ", {0:7}]"),                                   #                    （数・文字列）
    (54, "true"),                                       # 値 `{e}` → `true`
    # 集合の print: 行の番号（数の要素は綴りの順 `_sc`）・要素・組の頭・印
    (55, "\n_pr{0:2}[_k] <- _sc[{0:2}, _sP[_k]] + {1:7}"),
    (56, "\n      for (_k) in 0 .. {2:7}"),
    (57, "\n_pr{0:2}[_k, _m] <- _k * {1:7} + _sc[{0:2}, _sP[_m]] + {2:7}"),
    (58, "\n_pe[_pr{0:2}[_k]] <- _k   for (_k) in 0 .. {2:6}"),
    (59, "\n_pgs[_pr{0:2}[_k]] <- {1:7}   for (_k) in 0 .. {2:6}"),
    (60, "\n_pe[_pr{0:2}[_k, _m]] <- _m"),
    (61, "\n_pgs[_pr{0:2}[_k, _m]] <- _k * {1:7} + {2:7}"),
    (62, "\n_pst[{0:2}] <- true"),
    (63, "\n_pea[{0:2}] <- true"),
    (64, "\n_psi[{0:2}] <- true"),
    (65, "\n_sh[{0:2}, _sP[_k]] <- true   for (_k) in 0 .. {2:6}"),
    # `is`
    (66, "<="),
    (67, ">="),
    (68, "=="),
    (69, "@"),                                          # 十七文字以上の場の名前 → `_f<宣言の番号>`
    # 構成子の引数の塊の頭: 出現ごとの場 `_c<A>[場所, i]`（原子は `_ca<A>` —— 原子の符号化は表を
    # 原子の番号で引く＝座標の読みなので、折り込みの鎖と同じ場に置くと自分を座標に読む輪になる）。
    # 穴 0 = 出現の名のトークン、穴 2 = 引数の番号
    (116, "\n_c{0:6}[_st{0:6}[_r{1:1}"), (117, "\n_c{0:6}[_st{0:6}[%"), (118, "\n_c{0:6}[_st{0:6}[_z"),
    (119, "\n_ca{0:6}[_st{0:6}[_r{1:1}"), (120, "\n_ca{0:6}[_st{0:6}[%"), (121, "\n_ca{0:6}[_st{0:6}[_z"),
    (122, "], {2:1}] <- "), (123, ", _r{1:1}], {2:1}] <- "), (124, ", %], {2:1}] <- "),
    # 構成子の出現の本文の参照 `_c<A>[_st<A>[鍵], 30]`（列 30 が番地）
    (125, "_c{0:6}[_st{0:6}[_r{1:1}"), (126, "_c{0:6}[_st{0:6}[%"), (127, "_c{0:6}[_st{0:6}[_z"),
    (128, "], 30]"), (129, ", _r{1:1}], 30]"), (130, ", %], 30]"),
    # 出現の帯
    (131, "\nfield _st{0:6} : max bound {1:7}"),
    (132, "\nfield _st{0:6} : max bound {1:7} {2:7}"),
    (133, "\n_st{0:6}[_x] <- _x + {1:7}   for (_x) in 0 .. {2:7}"),
    (134, "\n_st{0:6}[_x, _y] <- _x * {1:7} + _y + {2:7}"),
    (135, "\n      for (_x) in 0 .. {0:7} for (_y) in 0 .. {1:7}"),
    (136, "\n_sk[_z] <- {0:2}   for (_z) in {1:7} .. {2:7}"),
    # 構成子の宣言の種
    (137, "\n_kn[{0:2}] <- {1:2}"),
    (138, "\n_knl[{0:2}] <- {1:2}"),
    (139, "\n_knm[{0:2}, {1:2}] <- {2:3}"),
    (140, "\n_Sz[0] <- {0:7}"),
    (141, "\n_TWz[0] <- 1023"),
    # 鍵が一つの参照（一行）
    (142, "_g{0:6}[_r{1:1}]"), (143, "_g{0:6}[%]"), (144, "_g{0:6}[_z]"),
    (145, "_c{0:6}[_st{0:6}[_r{1:1}], 30]"), (146, "_c{0:6}[_st{0:6}[%], 30]"), (147, "_c{0:6}[_st{0:6}[_z], 30]"),
    (148, " bound {0:7} {1:7} {2:7}"),                  # 広さの無い三次元の場
    (149, "_unlowered"),                                # 下ろせない print（焼き手に利用者の行で断らせる）
    # flat の場の print の ⊤（13e）。比較は ⊤ で立つ —— `< 0` と `>= 0` の両方が立つのは ⊤ の升だけ。
    # 値の写しは ⊤ の行を避ける（避けずに数の場へ読めば、焼いた側は読む前に止まって言う）
    (150, " if not _ptp[_pr{0:2}[_k]]"),                           # 一次元: 値の写しの後ろ
    (151, "\n_ptp[_pr{0:2}[_k]] <- true for (_k) in 0 .. {2:6}"),   # 一次元: ⊤ の行
    (152, " if @[_k] < 0 if @[_k] >= 0"),
    (153, " if not _ptp[_pr{0:2}[_k, _m]]"),                       # 二次元: 値の写しの輪の後ろ
    (154, "\n_ptp[_pr{0:2}[_k, _m]] <- true"),                     # 二次元: ⊤ の行（+ 輪 18）
    (155, " if @[_k, _m] < 0"),
    (156, " if @[_k, _m] >= 0"),
    (157, "_g{0:6}[0]"),                                               # ループに依らない上端の参照（13g）
    (158, "field"),                                                    # `source` → `field`（13h）
    (159, "_e{0:6}[0]"),                                               # `emit "ch"` → 誰も読まない場の頭
    # budget top（14t）: flat の場ごとに ⊤ の升を数え、越えたら終了コードの升に 4（192〜198。句を 200 からへ動かした）
    (192, "\n_tpc[0] <- 1 for (_k) in 0 .. {1:7} if @"),
    (193, "[_k] < 0 if @[_k] >= 0"),
    (194, "\nfield _exit : sum bound 1\nfield _tpc : count bound 1"),
    (195, "\n_exit[0] <- 4 for (_z) in 0 .. 0 if _tpc[0] > {0:7}"),
    (196, "\n_tpc[0] <- 1 for (_k) in 0 .. {1:7} for (_m) in 0 .. {2:7}"),
    (197, " if @[_k, _m] < 0"),
    (198, " if @[_k, _m] >= 0"),
    (199, " (_r{0:1}) in 0 .. {1:7} if _t{2:2}c0[_r{0:1}] == _t{2:2}c0[_r{0:1}]"),   # 型紙 0 + 重なった行を持つ表の「一列目が在る」（14t）
    # min / max の関数（14u）: `,` と `)` を替えて、二つの実例が引数を一つずつ置く（どちらの実例も両方を読む）
    (200, " * _md + "),
    (201, " * _mc for (_mc) in 0 .. 1 for (_md) in 0 .. 1 if _mc != _md"),
    # 束のある塊（14u）: 書き先へ単調に流れる値の中の塊は書き先の束、関数の塊は関数の束
    (202, "\nfield _g{0:6} : min bound {1:7}"),
    (203, "\nfield _g{0:6} : min bound {1:7} {2:7}"),
    (204, "\nfield _g{0:6} : max bound {1:7}"),
    (205, "\nfield _g{0:6} : max bound {1:7} {2:7}"),
    # 要素が負の集合（14x）: 要素の次元の原点を k ずらす（k は 127 まで —— 焼き手の座標のずれは符号つき一バイト）。
    # print は要素の座標 c ごとに要素の大きさ |c - k| を場 `_py<p>` に置き、負なら `_sPn`（負の数の鍵）、非負なら
    # `_sP` で引く。焼き手の座標の内側の読みは裸の計数器しか持てない（`_sP[_k - k]` は理由 8）ので、引き算は値に置く
    (206, "\nfield _py{0:2} : max bound {2:7}"),
    (207, "\n_py{0:2}[_k] <- {3:3} - _k   for (_k) in 0 .. {2:6}"),
    (208, "\n_py{0:2}[_k] <- _k - {3:3}   for (_k) in {3:3} .. {2:6}"),
    (209, "\n_pe[_pr{0:2}[_k]] <- _k - {3:4}   for (_k) in 0 .. {2:6}"),
    (210, "\n_pr{0:2}[_k] <- _sc[{0:2}, _sPn[_py{0:2}[_k]]] + {1:7}"),
    (211, "\n_pr{0:2}[_k] <- _sc[{0:2}, _sP[_py{0:2}[_k]]] + {1:7}"),
    (212, "\n      for (_k) in {3:3} .. {2:7}"),
    (213, "\n_sh[{0:2}, _sPn[_py{0:2}[_k]]] <- true   for (_k) in 0 .. {2:6}"),
    (214, "\n_sh[{0:2}, _sP[_py{0:2}[_k]]] <- true   for (_k) in {3:3} .. {2:6}"),
    #   print 二次元（鍵が一つの集合 —— 要素は次元1）
    (215, "\n_pr{0:2}[_k, _m] <- _k*{1:5} + _sc[{0:2}, _sPn[_py{0:2}[_m]]] + {2:7}"),
    (216, "\n_pr{0:2}[_k, _m] <- _k*{1:5} + _sc[{0:2}, _sP[_py{0:2}[_m]]] + {2:7}"),
    (217, "\n      for (_k) in 0 .. {1:7} for (_m) in {3:3} .. {2:7}"),
    (218, "\n_pe[_pr{0:2}[_k, _m]] <- _m - {3:4}"),
    #   書き先の要素（表の変数・区間の変数）に k を足す（数の要素は穴の値に足す）
    (219, "_t{0:2}c{1:2}[_r{2:1}] + {3:3}"),
    (220, "% + {3:3}"),
    (221, ", _t{0:2}c{1:2}[_r{2:1}] + {3:3}]"),
    (222, ", % + {3:3}]"),
    (111, "\nfield _e{0:6} : flat bound 1"),                           # （192 からは句の番号 —— MACRO0）
    # 裸の下端の参照（13i）。`in _g[i] .. n` は解釈実行が表の名と読むので丸括弧で包む
    (112, "(_g{0:6}[_r{1:1}])"), (113, "(_g{0:6}[%])"), (114, "(_g{0:6}[_z])"), (115, "(_g{0:6}[0])"),
    # fourv → or の旗二つ（14b）。場に次元を一つ足す: `x[e, 0]` が T の旗、`x[e, 1]` が F の旗。
    # 160 からの番号は 14b で空けた（句の番号の始まりを 160 → 192 に）
    (160, " 2"),                                                       # 書いた広さの後ろに旗の次元
    (161, ", _r9] for (_r9) in 0 .. 1"),                               # 写し: 読みの `]` → 旗ごと
    (162, ", _r9] for (_r9) in 0 .. 1 for (_z) in 0 .. 0"),            #       種を規則にした文（型紙 8 に勝つ）
    (163, ", _fsw[_r9]] for (_r9) in 0 .. 1"),                         # 否定の写し: 旗を入れ替える
    (164, ", _fsw[_r9]] for (_r9) in 0 .. 1 for (_z) in 0 .. 0"),
    (165, ", {0:7}] for (_z) in 0 .. 0"),                              # ガードの `]`（種を規則にした文。53 に勝つ）
    (166, "\n_pv[_pr{0:2}[_k]] <- {1:4} for (_k) in 0 .. {2:6}"),      # print 一次元: 値は原子 T4 / F4 の番号
    (167, " if @[_k, {0:1}]"),                                         #               その旗
    (168, "\n_pv[_pr{0:2}[_k, _m]] <- {1:4}"),                         # print 二次元（+ 輪 18）
    (169, " if @[_k, _m, {0:1}]"),
    (170, "\nfield _fsw : flat bound 2\n_fsw[0] <- 1\n_fsw[1] <- 0"),   # 旗を入れ替える表（一度だけ）
    (171, "\n      if _pv[_pr{0:2}[_k, _m]] >= 0"),                     # print 二次元の座標の行: 値のある行（22 に勝つ）
    # 負の座標（14c）: 次元0 を持ち上げた塊の値の後ろに ` + k`（ループの節 36〜39 の頭に付けた形。max で勝つ）
    (172, " + {3:3} for (_r{0:1}) in 0 .. {1:7}"),
    (173, " + {3:3} for (%) in {0:7} .. {1:7}"),
    (174, " + {3:3} for (%) in {0:7} .. @[{1:7}]"),
    (175, " + {3:3} for (_z) in 0 .. 0"),
    # アクセサ（14d）: `c_f[e]` → 持ち上げた塊の値 `_sv[_ag, j] if _sad[_ag] == e for (_ag) in 0 .. _Sz[0] if _sk[_ag] == k`
    # （場所を **比べて** 引く —— flat の比較は単調なので、項を作る再帰の中でも層が要らない）
    (176, "_sv[_ag, {0:1}] if _sad[_ag] == "),                       # `[` の後ろ（名と `[` は消える）
    (177, " for (_ag) in 0 .. _Sz[0] if _sk[_ag] == {0:2}"),          # `]` の後ろ（`]` は消える）
    (178, "_ssz[_ag] if _sad[_ag] == "),                              # `_size[e]`
    (179, " for (_ag) in 0 .. _Sz[0]"),
    (180, "\nfield _ssz : max bound 16384"),                            # 場所 g の項の大きさ（一度だけ）
    (181, "\n_ssz[g] <- 1 for (g) in 0 .. _Sz[0] if _sad[g] >= 0"),
    (182, "\n_ssz[g] <- _ssz[h] + 1 for (g) in 0 .. _Sz[0]"),
    (183, " for (h) in 0 .. _Sz[0] for (i) in 0 .. 3"),
    (184, " if _sv[g, i] == _sad[h]"),
    (185, "\n_t{0:2}c{1:2}[{2:7}] <- -{3:10}"),   # 表の升が負の数 → 種（5 の裏。桁の穴は負を書けない。焼き手は `-` 数 の種を持てる）
    (186, "\n_psh1[{0:2}] <- {1:7}"),                 # print p の座標0 のずらし（14k。原点をずらした場を印字する）
    (187, "\n_psh2[{0:2}] <- {1:7}"),                 # 座標1 のずらし
    (188, "{0:7} if % >= {1:7}"),                   # 軸の規則の区間を揃える（14l）: 上端 + 元の下端のガード
    (189, "{0:7} if % <= {2:7}"),                   #   上端を広げたとき: 新しい上端 + 元の上端のガード
    (190, "{0:7} if % >= {1:7} if % <= {2:7}"),     #   両方
]

# ── 出現ごとの塊（型紙の塊）──────────────────────────────────────────────
# **項の値は、自分の引数だけの純な函数である**（解釈実行の `ctor_id` と同じ）。値を全部の出現が
# 共有する場（`_sv` → `_sid`）に通すと、場の粒度の成層では **どの出現もどの出現にも依る** ことになり、
# 22_parse は偽の非単調な輪で断られた。だから値の道は出現ごとの場 `_c<A>`（flat、列が役割）に閉じ、
# 共有の表（`_sv` / `_sva`）へは **写すだけ**（print と番地の引きが読む —— 解釈実行の `c_f` の場と同じ位置）。
# 列: 0〜2 数の引数（原子の引数は `_ca<A>` の 0〜2）/ 8〜10・12〜14 引数の符号化（二本）/ 16〜19・20〜23 折り込み /
#     24〜26・27〜29 折り込みの途中 / 30 番地 / 31 共有の表の場所の番号
# 穴: 0 出現（名のトークン）/ 1 帯の幅 - 1 / 2 帯の幅 / 3 帯の基 / 4 構成子 / 5 16 + 引数の数 / 6 20 + 引数の数
# 塊は下ろしが出現ごとに一行（`lb[出現の密な番号, 升]`）に刷る —— 型紙の実例の枠（位置ごとに八つ）に
# 収まらない長さなので、帯を別に持つ（型紙の帯と同じ符号: 字 / 128 + 16 穴 + 桁）。
_L = "   for (x) in 0 .. {1:7} for (i) in 0 .. 2"
_M1, _K1, _M2, _K2 = 268435399, 1000003, 268435367, 1000033
BLOCK = "".join([
    "\nfield _c{0:6} : flat bound {2:7} 32",
    "\nfield _ca{0:6} : flat bound {2:7} 4",
    "\n_c{0:6}[x, 31] <- x + {3:7}   for (x) in 0 .. {1:7}",
    f"\n_c{{0:6}}[x, i + 8] <- _c{{0:6}}[x, i] % {_M1} * 3{_L}",
    f"\n_c{{0:6}}[x, i + 8] <- _afh1[_ca{{0:6}}[x, i]] * 3 + 1{_L}",
    f"\n_c{{0:6}}[x, i + 12] <- _c{{0:6}}[x, i] % {_M2} * 3{_L}",
    f"\n_c{{0:6}}[x, i + 12] <- _afh2[_ca{{0:6}}[x, i]] * 3 + 1{_L}",
    "\n_c{0:6}[x, 16] <- _kb1[{4:2}]   for (x) in 0 .. {1:7}",
    "\n_c{0:6}[x, 20] <- _kb2[{4:2}]   for (x) in 0 .. {1:7}",
    f"\n_c{{0:6}}[x, i + 24] <- _c{{0:6}}[x, i + 16] * {_K1} + _c{{0:6}}[x, i + 8]{_L}",
    f"\n_c{{0:6}}[x, i + 17] <- _c{{0:6}}[x, i + 24] % {_M1}{_L}",
    f"\n_c{{0:6}}[x, i + 27] <- _c{{0:6}}[x, i + 20] * {_K2} + _c{{0:6}}[x, i + 12]{_L}",
    f"\n_c{{0:6}}[x, i + 21] <- _c{{0:6}}[x, i + 27] % {_M2}{_L}",
    f"\n_c{{0:6}}[x, 30] <- _c{{0:6}}[x, {{5:2}}] * {_M2} + _c{{0:6}}[x, {{6:2}}]   for (x) in 0 .. {{1:7}}",
    f"\n_sv[_c{{0:6}}[x, 31], i] <- _c{{0:6}}[x, i]{_L}",
    f"\n_sva[_c{{0:6}}[x, 31], i] <- _ca{{0:6}}[x, i]{_L}",
    "\n_sad[_c{0:6}[x, 31]] <- _c{0:6}[x, 30]   for (x) in 0 .. {1:7}",
])
BLOCK_HOLES = 7


def block_strip():
    """塊の型紙を帯に（字 / 128 + 16 穴 + 桁）。三バイトずつ種に"""
    b = bytearray()
    i = 0
    while i < len(BLOCK):
        m = re.match(r'\{(\d):(\d+)\}', BLOCK[i:])
        if m:
            h, w = int(m.group(1)), int(m.group(2))
            assert h < BLOCK_HOLES and w <= 10
            b += bytes(128 + 16 * h + (w - 1 - k) for k in range(w))
            i += m.end()
        else:
            c = ord(BLOCK[i]); assert c == 10 or 32 <= c <= 126
            b.append(c); i += 1
    b += b"\0" * (-len(b) % 3)
    lines = [f"# 出現ごとの塊の帯（{len(b)} バイトを三バイトずつ）"]
    lines += [f"bt[{i}] <- {b[3*i] + 256 * b[3*i+1] + 65536 * b[3*i+2]}" for i in range(len(b) // 3)]
    lines.append(f"btz[0] <- {len(b) // 3 - 1}")
    # 穴 h の d 桁目の字（d = 0 は常に、d ≥ 1 は値がその桁に届くときだけ）
    widths = {}
    for m in re.finditer(r'\{(\d):(\d+)\}', BLOCK):
        widths[int(m.group(1))] = max(widths.get(int(m.group(1)), 0), int(m.group(2)))
    for h in range(BLOCK_HOLES):
        for d in range(widths[h]):
            p = 10 ** d
            val = f"48 + kbv{h}[a] % 10" if d == 0 else f"48 + kbv{h}[a] / {p} % 10"
            g = "" if d == 0 else f" if kbv{h}[a] >= {p}"
            lines.append(f"bdig[a, {128 + 16 * h + d}] <- {val}   for (a) in 0 .. kaz[0]{g}")
    return "\n".join(lines) + "\n"
# print の機械の、行で引く場の宣言（型紙 70 から。穴 0 = 行の数）
ENGINE_ROWS = runpy.run_path(os.path.join(ROOT, 'work', 'lower', 'mkengine.py'))['ROWS']
for _i, (_nm, _lat, _w) in enumerate(ENGINE_ROWS):
    _tail = "" if _w == 0 else (" {1:4}" if isinstance(_w, str) else f" {_w}")
    TEMPLATES.append((70 + _i, f"\nfield {_nm} : {_lat} bound {{0:7}}" + _tail))
assert 70 + len(ENGINE_ROWS) <= 128


def rows_rules():
    """行で引く場の宣言の実例（源の字に居ない番号 0.. に八つずつ）。穴 0 = 行の数（lrz）、
    穴 1 = 二次元目の広さ（"O" は `_o` の広さ lcw、"T" は項の字の広さ ltw）"""
    out = ["# ── 行で引く場の宣言の実例（work/mklower.py が起こす。手で直さない）──"]
    for i, (nm, lat, w) in enumerate(ENGINE_ROWS):
        n, e = divmod(i, 8)
        out.append(f"iti[{n}, {e}] <- {70 + i}")
        out.append(f"ih0[{n}, {e}] <- {'lrzv' if w == 'V' else 'lrz'}[0]   for (z) in 0 .. 0")
        if w == "V":
            out.append(f"ih1[{n}, {e}] <- lcwv[0]   for (z) in 0 .. 0")
        elif w == "O":
            out.append(f"ih1[{n}, {e}] <- lcw[0]   for (z) in 0 .. 0")
        elif w == "T":
            out.append(f"ih1[{n}, {e}] <- ltw[0]   for (z) in 0 .. 0")
    out.append("# ── 行で引く場の宣言ここまで ──")
    return "\n".join(out) + "\n"
WIDTH = 63                                         # 型紙の升（lx の 1..63）


def cells(text):
    """型紙 → [(字, 穴, 桁)]。字は数、穴は 1 起点（0 は穴でない）、桁は右から。
       名前の升は穴 0・桁 -(k+1)（k 文字目）。"""
    out, i = [], 0
    while i < len(text):
        m = re.match(r'\{(\d):(\d+)\}', text[i:])
        if m:
            h, w = int(m.group(1)), int(m.group(2))
            out += [(None, h + 1, w - 1 - k) for k in range(w)]
            i += m.end()
        elif text[i] == '@':
            out += [(None, 0, -(k + 1)) for k in range(16)]; i += 1
        elif text[i] == '%':
            out += [(None, 0, -(k + 101)) for k in range(8)]; i += 1
        else:
            out.append((ord(text[i]), 0, 0)); i += 1
    assert len(out) <= WIDTH, (text, len(out))
    return out


MACRO0 = 224                                        # 句の型紙の番号の始まり（句のバイト 128 + m → 型紙 224 + m。14b で 160 → 192、14t で 192 → 200、14u で 200 → 224 —— lib/lower.lx の `+ 96` と一緒に動かす。句は 90 まで、tpc は 320）
# **型紙の番号は句の手前まで。** 160 に型紙を足した日、句 160 が黙って上書きして型紙が消えた（13h）
assert all(k < MACRO0 for k, _ in TEMPLATES), [k for k, _ in TEMPLATES if k >= MACRO0]
assert len({k for k, _ in TEMPLATES}) == len(TEMPLATES), "型紙の番号がぶつかっている"


def compress(text, limit=90):
    """**機械の字を句で畳む。** よく出る句（`for (r) in 0 .. _Rz[0]` は百十七回）を一バイト（128 + m）に
    置き換える。句の字は型紙の帯に MACRO0 + m 番の型紙として入れる —— 開くのは型紙を開く規則そのもので、
    句のバイト p は `ex[p, k] = tpc[p のバイト + 64, k]`（⊥ は幅 0 なので、句の長さを数えずに並ぶ）。
    貪欲に選ぶ（節約 = 回数 × (長さ - 1) - 長さ）。結果は機械の字が同じ限り同じなので、控えに取る。"""
    import hashlib, json
    key = hashlib.sha256(text.encode()).hexdigest()
    cache = os.path.join(ROOT, 'work', 'lower', 'engine.pack.json')
    if os.path.exists(cache):
        c = json.load(open(cache))
        if c.get('key') == key:
            return c['seq'], c['macros']
    from collections import Counter
    seq, macros = list(text), []
    while len(macros) < limit:
        best = None
        for L in range(4, 41):
            cnt = Counter(''.join(seq[i:i + L]) for i in range(len(seq) - L + 1)
                          if all(isinstance(x, str) for x in seq[i:i + L]))
            for w, k in cnt.items():
                sv = k * (L - 1) - L
                if best is None or sv > best[0]:
                    best = (sv, w)
        if not best or best[0] <= 10:
            break
        w, m = best[1], len(macros)
        macros.append(w)
        out, i = [], 0
        while i < len(seq):
            if all(isinstance(x, str) for x in seq[i:i + len(w)]) and ''.join(seq[i:i + len(w)]) == w:
                out.append(m); i += len(w)
            else:
                out.append(seq[i]); i += 1
        seq = out
    json.dump({'key': key, 'seq': seq, 'macros': macros}, open(cache, 'w'))
    return seq, macros


def seeds():
    """型紙と print の機械を **帯に畳んで** 種にする。種の数は焼き手の文の面（8,192）に効く ——
    升ごとに一文だった型紙（二千文）と、三バイトずつの機械（二千文）が下ろしの文の三分の二を占めていた。
    - 型紙の帯: 升ごとに一バイト（字 = そのまま / 穴 h の d 桁目 = 128 + 16(h-1) + d /
      名の k 文字目 = 191 + k / 綴りの k 文字目 = 207 + k）、型紙の終わりに 0。三バイトずつ一つの種に。
    - 機械の帯: 字は七ビット（注釈を落とせば ASCII だけ）なので四バイトずつ一つの種に（28 ビット）。
    帯を開くのは下ろしの規則（lib/lower.lx の「帯を開く」）。"""
    lines = ["# ── 型紙と機械の帯（work/mklower.py が起こす。手で直さない）──"]
    blob = bytearray()
    # 機械の字（注釈と詰め物を落とし、句で畳む）。句は型紙 128 + m
    runpy.run_path(os.path.join(ROOT, 'work', 'lower', 'mkengine.py'), run_name='__main__')
    eng = open(os.path.join(ROOT, 'work', 'lower', 'engine.lx'), encoding='utf-8').read()
    bt = ": ⊥ everywhere (no coordinate reached a definite value)\n".encode()
    eng += "".join(f"_bt[{i}] <- {b}\n" for i, b in enumerate(bt))
    eng += "table ch = (0,32)\n"
    eng = "\n".join(re.sub(r' +', ' ', re.sub(r'\s+#.*$', '', l)) for l in eng.split("\n")
                    if not l.startswith('#'))
    seq, macros = compress("\n" + eng)
    ids = {k: text for k, text in TEMPLATES}
    for m, w in enumerate(macros):
        ids[MACRO0 + m] = w
    for k in range(max(ids) + 1):
        if k >= MACRO0:                               # 句: 字をそのまま（型紙の書き方で読まない）
            lines.append(f"# {k}: 句 {ids[k]!r}")
            assert len(ids[k]) <= 48 and all(ord(x) == 10 or 32 <= ord(x) <= 126 for x in ids[k])
            blob += ids[k].encode()
        elif k in ids:
            lines.append(f"# {k}: {ids[k]!r}")
            for (c, h, d) in cells(ids[k]):
                if h == 0 and d <= -101:
                    blob.append(207 + (-d - 100))
                elif h == 0 and d < 0:
                    blob.append(191 + (-d))
                elif h == 0:
                    assert c == 10 or 32 <= c <= 126, (k, c)
                    blob.append(c)
                else:
                    assert 1 <= h <= 4 and 0 <= d <= 15, (k, h, d)
                    blob.append(128 + 16 * (h - 1) + d)
        blob.append(0)
    blob += b"\0" * (-len(blob) % 3)
    lines.append(f"# 型紙の帯（{len(blob)} バイトを三バイトずつ）")
    lines += [f"tv[{i}] <- {blob[3*i] + 256 * blob[3*i+1] + 65536 * blob[3*i+2]}" for i in range(len(blob) // 3)]
    lines.append(f"tvz[0] <- {len(blob) // 3 - 1}")
    # print の機械: 字は 0..127、句は 128 + m。三バイトずつ種に畳む
    data = bytes((ord(x) if isinstance(x, str) else 128 + x) for x in seq)
    assert all(isinstance(x, int) or ord(x) < 128 for x in seq)
    data += b" " * (-len(data) % 3)
    assert len(data) <= 3 * 4096, len(data)
    lines.append(f"# print の機械（work/lower/engine.lx を句 {len(macros)} で畳んだ {len(data)} バイトを三バイトずつ）")
    lines += [f"lk[{i}] <- {data[3*i] + 256 * data[3*i+1] + 65536 * data[3*i+2]}" for i in range(len(data) // 3)]
    lines.append(f"lkz[0] <- {len(data) // 3 - 1}")
    lines.append("# ── 帯ここまで ──")
    return "\n".join(lines) + "\n"


def digit_rules():
    """穴 h の d 桁目を置く規則（d = 0 は常に、d ≥ 1 は値がその桁に届くときだけ）と、名前の升。"""
    L = f"for (c) in 0 .. ncz[0] for (j) in 0 .. {WIDTH - 1}"
    out = ["# ── 穴の桁と名前の升（work/mklower.py が起こす。手で直さない）──"]
    for h in range(4):
        for d in range(10):
            p = 10 ** d
            val = f"48 + ch{h}[c] % 10" if d == 0 else f"48 + ch{h}[c] / {p} % 10"
            g = "" if d == 0 else f" if ch{h}[c] >= {p}"
            out.append(f"lx[crow[c], j + 1] <- {val}   {L}\n      if tph[cti[c], j] == {h + 1}"
                       f" if tpd[cti[c], j] == {d}{g}")
    for k in range(16):
        out.append(f"lx[crow[c], j + 1] <- lnw[cnd[c], {k}]   {L} if tpn[cti[c], j] == {k + 1}")
    for k in range(8):
        out.append(f"lx[crow[c], j + 1] <- tch[cnm[c], {k}]   {L} if tpm[cti[c], j] == {k + 1}")
    out.append("# ── 穴の桁ここまで ──")
    return "\n".join(out) + "\n"


def splice(src, tag, body):
    a, b = f"# <<{tag}>>\n", f"# <</{tag}>>\n"
    i, j = src.index(a) + len(a), src.index(b)
    return src[:i] + body + src[j:]


if __name__ == '__main__':
    lp = os.path.join(ROOT, 'lib', 'lower.lx')
    low = open(lp, encoding='utf-8').read()
    low = splice(low, 'templates', seeds())
    low = splice(low, 'digits', digit_rules())
    low = splice(low, 'rows', rows_rules())
    low = splice(low, 'blocks', block_strip())
    open(lp, 'w', encoding='utf-8').write(low)
    # **lower.lx は組まない**（14z）。前は前段（33_self）と焼き手の写し（fold）の広さを狭めて（589,824 → 262,144 ほか）
    # 繋いでいた —— 置き場が全部で 2 GB の縁に居た頃の工夫である。14 で置き場が面ごとに 2 GB になったので、狭めずに
    # 取り込んでも入る（焼いて確かめた。下ろした字は examples と work/t の 208 本でバイトまで同じ、手間も同じ）。
    # だから lower.lx は三行の include で、焼き手が口で開く（lattix.lx と同じ）
    print('lib/lower.lx', len(low.encode()), 'バイト')
