# -*- coding: utf-8 -*-
"""attest の二段目 —— 実例ごとの出現の座標と読みの規則を、段ごとに書き出す。

段 L の規則は段 L-1 の読みだけを読む（閉路を作らない）。三段（0〜2）まで —— それより深い
読みの鎖は「持たない形」として判定で言う。書き出した .lx が attest そのものであり、
Python は組むときにしか現れない。"""
import os, textwrap
HERE = os.path.dirname(os.path.abspath(__file__))
NI = 131071
def level(L):
    P = 'q%d' % L          # 段の接頭辞
    prev = 'q%d' % (L - 1)
    out = []
    a = out.append
    a(f"# ── 段 {L} の出現（源5 の内側は段 {L - 1}）" if L else "# ── 段 0 の出現（源5 を持たない）")
    for d in (0, 1):
        a(f"field {P}x{d} : max bound {NI + 1} 16            # 次元 {d} の添字（広さの内側のとき）")
        a(f"field {P}i{d} : max bound {NI + 1} 16            # 源2/3 の内側の升")
    a(f"field {P}ot : or bound {NI + 1} 16               # 座標はあるが広さの外（升は ⊥）")
    a(f"field {P}un : or bound {NI + 1} 16               # 座標が無い（内側の読みが ⊥）")
    a(f"field {P}tp : or bound {NI + 1} 16               # 座標に ⊤ を読んだ（attest は持たない）")
    common = f"for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]] if olv[noo[n, j]] == {L}"
    for d in (0, 1):
        sl = f"osd{d}[n, j]"
        dimok = "" if d == 0 else " if nar[n, j] == 2"
        # 源4: 定数
        a(f"{P}x{d}[n, j] <- ccc[{sl}] + spo[{sl}]   {common}{dimok} if csr[{sl}] == 4")
        a(f"      if ccc[{sl}] >= sblo[{sl}] if ccc[{sl}] < sbhi[{sl}]")
        a(f"{P}ot[n, j] <- true   {common}{dimok} if csr[{sl}] == 4")
        a(f"      if ccc[{sl}] < sblo[{sl}]")
        a(f"{P}ot[n, j] <- true   {common}{dimok} if csr[{sl}] == 4")
        a(f"      if ccc[{sl}] >= sbhi[{sl}]")
        # 源1: 計数器 / 源0: 列（値は nvk{d}[n, j] に置いてある）
        for src in (0, 1):
            a(f"{P}x{d}[n, j] <- ncv{d}[n, j] / 4 + spo[{sl}]   {common}{dimok} if csr[{sl}] == {src}")
            a(f"      if ncv{d}[n, j] >= sblo4[{sl}] if ncv{d}[n, j] < sbhi4[{sl}]")
            a(f"{P}ot[n, j] <- true   {common}{dimok} if csr[{sl}] == {src} if ncv{d}[n, j] < sblo4[{sl}]")
            a(f"{P}ot[n, j] <- true   {common}{dimok} if csr[{sl}] == {src} if ncv{d}[n, j] >= sbhi4[{sl}]")
        # 源2/3: 内側の読み（添字は列 / 計数器 + 前置のずれ）
        for src in (2, 3):
            a(f"{P}i{d}[n, j] <- fcb[ccf[{sl}]] + ncv{d}[n, j] / 4 + spr[{sl}]   {common}{dimok} if csr[{sl}] == {src}")
            a(f"      if ncv{d}[n, j] >= sprl4[{sl}] if ncv{d}[n, j] < sprh4[{sl}]")
            a(f"{P}un[n, j] <- true   {common}{dimok} if csr[{sl}] == {src} if ncv{d}[n, j] < sprl4[{sl}]")
            a(f"{P}un[n, j] <- true   {common}{dimok} if csr[{sl}] == {src} if ncv{d}[n, j] >= sprh4[{sl}]")
        a(f"{P}un[n, j] <- true   {common}{dimok} if csr[{sl}] >= 2 if csr[{sl}] <= 3")
        a(f"      if not sp[{P}i{d}[n, j]]")
        a(f"{P}tp[n, j] <- true   {common}{dimok} if csr[{sl}] >= 2 if csr[{sl}] <= 3")
        a(f"      if stop[{P}i{d}[n, j]]")
        a(f"{P}x{d}[n, j] <- sv[{P}i{d}[n, j]] / 4 + spo[{sl}]   {common}{dimok} if csr[{sl}] >= 2 if csr[{sl}] <= 3")
        a(f"      if sv[{P}i{d}[n, j]] >= sblo4[{sl}] if sv[{P}i{d}[n, j]] < sbhi4[{sl}]")
        a(f"{P}ot[n, j] <- true   {common}{dimok} if csr[{sl}] >= 2 if csr[{sl}] <= 3")
        a(f"      if sv[{P}i{d}[n, j]] < sblo4[{sl}]")
        a(f"{P}ot[n, j] <- true   {common}{dimok} if csr[{sl}] >= 2 if csr[{sl}] <= 3")
        a(f"      if sv[{P}i{d}[n, j]] >= sbhi4[{sl}]")
        if L >= 1:
            # 源5: 内側の出現（段 L-1）の読み
            a(f"field {P}j{d} : max bound {NI + 1} 16           # 源5 の内側の出現（規則の中の番号）")
            a(f"{P}j{d}[n, j] <- ccc[{sl}] - nro[n]   {common}{dimok} if csr[{sl}] == 5")
            a(f"{P}un[n, j] <- true   {common}{dimok} if csr[{sl}] == 5 if not {prev}pr[n, {P}j{d}[n, j]]")
            a(f"{P}tp[n, j] <- true   {common}{dimok} if csr[{sl}] == 5 if {prev}tp2[n, {P}j{d}[n, j]]")
            a(f"{P}x{d}[n, j] <- {prev}vl[n, {P}j{d}[n, j]] / 4 + spo[{sl}]   {common}{dimok} if csr[{sl}] == 5")
            a(f"      if {prev}vl[n, {P}j{d}[n, j]] >= sblo4[{sl}] if {prev}vl[n, {P}j{d}[n, j]] < sbhi4[{sl}]")
            a(f"{P}ot[n, j] <- true   {common}{dimok} if csr[{sl}] == 5")
            a(f"      if {prev}vl[n, {P}j{d}[n, j]] < sblo4[{sl}]")
            a(f"{P}ot[n, j] <- true   {common}{dimok} if csr[{sl}] == 5")
            a(f"      if {prev}vl[n, {P}j{d}[n, j]] >= sbhi4[{sl}]")
    # 升と読み
    a(f"field {P}cl : max bound {NI + 1} 16              # 升（通し番号）")
    a(f"{P}cl[n, j] <- nfb[n, j] + {P}x0[n, j]   {common} if nar[n, j] == 1")
    a(f"{P}cl[n, j] <- nfb[n, j] + {P}x0[n, j] * nw1[n, j] + {P}x1[n, j]   {common} if nar[n, j] == 2")
    a(f"field {P}pr : or bound {NI + 1} 16               # 読んだ升は ⊥ でない（⊤ を含む）")
    a(f"{P}pr[n, j] <- true   {common} if sp[{P}cl[n, j]]")
    a(f"field {P}tp2 : or bound {NI + 1} 16              # 読んだ升は ⊤")
    a(f"{P}tp2[n, j] <- true   {common} if stop[{P}cl[n, j]]")
    a(f"field {P}vl : flat bound {NI + 1} 16             # 読んだ値")
    a(f"{P}vl[n, j] <- sv[{P}cl[n, j]]   {common}")
    return "\n".join(out) + "\n"


def source(ni):
    """一段目〜二段目の .lx（base.lx + 出現）。ni は attest が持つ実例の数。"""
    global NI
    NI = ni - 1
    head = f"""
    # ── 実例ごとの所有者（規則の中の番号 j）─────────────────────────────
    field nro : max bound {NI + 1}                    # 実例 n の規則の最初の所有者
    nro[n] <- rof[nr[n]]   for (n) in 0 .. ninz[0]
    field nrc : max bound {NI + 1}                    # その所有者の数（16 を超える規則は検査しない）
    nrc[n] <- rocn[nr[n]]   for (n) in 0 .. ninz[0]
    field noo : max bound {NI + 1} 16                 # 実例 n の j 番目の所有者
    noo[n, j] <- nro[n] + j   for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n]
    field nof : max bound {NI + 1} 16                 # その場
    nof[n, j] <- ofd[noo[n, j]]   for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]]
    field nol : max bound {NI + 1} 16                 # その束（二段の読みの次元1 に読みを置けないので名前を置く）
    nol[n, j] <- flt[nof[n, j]]   for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]]
    field nar : max bound {NI + 1} 16                 # その次数
    nar[n, j] <- far[nof[n, j]]   for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]]
    field nfb : max bound {NI + 1} 16                 # その場の最初の升
    nfb[n, j] <- fcb[nof[n, j]]   for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]]
    field nw1 : max bound {NI + 1} 16                 # その場の次元1 の広さ
    nw1[n, j] <- fw1[nof[n, j]]   for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]]
    field osd0 : max bound {NI + 1} 16                # 次元 0 のスロット
    osd0[n, j] <- osl[noo[n, j], 0]   for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]]
    field osd1 : max bound {NI + 1} 16                # 次元 1 のスロット
    osd1[n, j] <- osl[noo[n, j], 1]   for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]]
          if nar[n, j] == 2
    # スロットの静かな数: 後置 / 前置のずれ、広さの内側になる基の値の範囲
    field spo : max bound 8192                   # 後置のずれ（無ければ 0）
    spo[g] <- 0   for (g) in 0 .. ngcz[0] if chf[g] != 1
    spo[g] <- cof[g]   for (g) in 0 .. ngcz[0] if chf[g] == 1
    field spr : max bound 8192                   # 前置のずれ（源2/3 の内側の添字に足す）
    spr[g] <- 0   for (g) in 0 .. ngcz[0] if chf[g] != 2
    spr[g] <- cof[g]   for (g) in 0 .. ngcz[0] if chf[g] == 2
    field swd : max bound 8192                   # その次元の広さ
    swd[g] <- fw0[ofd[cso[g]]]   for (g) in 0 .. ngcz[0] if csd[g] == 0
    swd[g] <- fw1[ofd[cso[g]]]   for (g) in 0 .. ngcz[0] if csd[g] == 1
    field sblo : max bound 8192                  # 基の値がこれ以上なら
    sblo[g] <- 0 - spo[g]   for (g) in 0 .. ngcz[0]
    field sbhi : max bound 8192                  # これ未満なら広さの内側
    sbhi[g] <- swd[g] - spo[g]   for (g) in 0 .. ngcz[0]
    field sprl : max bound 8192                  # 源2/3 の内側の添字の範囲（前置のずれ込み）
    sprl[g] <- 0 - spr[g]   for (g) in 0 .. ngcz[0]
    field sprh : max bound 8192
    sprh[g] <- fw0[ccf[g]] - spr[g]   for (g) in 0 .. ngcz[0] if csr[g] >= 2 if csr[g] <= 3
    # 基の値は四倍して持つので、境も四倍して比べる
    field sblo4 : max bound 8192
    sblo4[g] <- sblo[g] * 4   for (g) in 0 .. ngcz[0]
    field sbhi4 : max bound 8192
    sbhi4[g] <- sbhi[g] * 4   for (g) in 0 .. ngcz[0]
    field sprl4 : max bound 8192
    sprl4[g] <- sprl[g] * 4   for (g) in 0 .. ngcz[0]
    field sprh4 : max bound 8192
    sprh4[g] <- sprh[g] * 4   for (g) in 0 .. ngcz[0] if csr[g] >= 2 if csr[g] <= 3
    # 実例 n の j 番目の所有者の次元 d の「列 / 計数器」の値（源0〜3 の基）
    field uip : max bound 983040                 # 生バイトの表の行 r のバイトの位置
    uip[r] <- r + iB[0]   for (r) in 0 .. 983039 if inpw[0] == 1 if r < nrw[0]
    field urb : max bound 983040                 # そのバイト
    urb[r] <- by[uip[r]]   for (r) in 0 .. 983039 if inpw[0] == 1 if r < nrw[0]
    # 語の表: 語 q（行 * 列の数 + 列）の値の四倍。|v| < 2^60 の外は持てないので、印を付けて判定で言う
    field nwq : max bound 1                      # 行に収まる語の数
    nwq[z] <- nrw[z] * ncol[z]   for (z) in 0 .. 0 if inpw[z] == 8
    field uwp : max bound 131072                 # 語 q の位置（バイト）
    uwp[q] <- q * 8 + iB[0]   for (q) in 0 .. 131071 if inpw[0] == 8 if q < nwq[0]
    field uwl : max bound 131072                 # 下の 32 ビット
    uwl[q] <- h32[uwp[q]]   for (q) in 0 .. 131071 if inpw[0] == 8 if q < nwq[0]
    field uwh : max bound 131072                 # 上の 32 ビット（符号なし）
    uwh[q] <- h32[uwp[q] + 4]   for (q) in 0 .. 131071 if inpw[0] == 8 if q < nwq[0]
    field uwun : or bound 131072                 # attest が持てない語
    uwun[q] <- true   for (q) in 0 .. 131071 if inpw[0] == 8 if q < nwq[0] if uwh[q] >= 268435456 if uwh[q] < k31[2]
    field uwsh : max bound 131072                # 上の 32 ビット（符号つき。持てる語だけ）
    uwsh[q] <- uwh[q]   for (q) in 0 .. 131071 if inpw[0] == 8 if q < nwq[0] if not uwun[q] if uwh[q] <= 2147483647
    uwsh[q] <- uwh[q] - 65536 * 65536   for (q) in 0 .. 131071 if inpw[0] == 8 if q < nwq[0] if not uwun[q]
          if uwh[q] > k31[1]
    field uwv : flat bound 131072                # 語 q の値の四倍
    uwv[q] <- uwl[q] * 4 + uwsh[q] * 65536 * 65536 * 4   for (q) in 0 .. 131071 if inpw[0] == 8 if q < nwq[0]
          if not uwun[q]
    field nq0 : max bound 131072                 # 実例 n の行の最初の語
    nq0[n] <- na0[n] * ncol[0]   for (n) in 0 .. ninz[0] if inpw[0] == 8
    """
    cols = ""
    for d in (0, 1):
        sl = f"osd{d}[n, j]"
        dimok = "" if d == 0 else " if nar[n, j] == 2"
        cc = f"for (n) in 0 .. ninz[0] for (j) in 0 .. 15 if j < nrc[n] if ohas[noo[n, j]]{dimok}"
        cols += f"field ncv{d} : flat bound {NI + 1} 16        # 次元 {d} の基の四倍（列 / 計数器。列の値は任意）\n"
        cols += f"field nqw{d} : max bound {NI + 1} 16         # 語の表の列の語\n"
        cols += f"nqw{d}[n, j] <- nq0[n] + ccc[{sl}]   {cc} if inpw[0] == 8 if csr[{sl}] == 0\n"
        cols += f"nqw{d}[n, j] <- nq0[n] + ccc[{sl}]   {cc} if inpw[0] == 8 if csr[{sl}] == 2\n"
        cols += f"ncv{d}[n, j] <- uwv[nqw{d}[n, j]]   {cc} if inpw[0] == 8 if csr[{sl}] == 0\n"
        cols += f"ncv{d}[n, j] <- uwv[nqw{d}[n, j]]   {cc} if inpw[0] == 8 if csr[{sl}] == 2\n"
        for k in (0, 1, 2):
            cols += f"ncv{d}[n, j] <- nk{k}[n] * 4   {cc} if csr[{sl}] == 1 if ccc[{sl}] == {k}\n"
            cols += f"ncv{d}[n, j] <- nk{k}[n] * 4   {cc} if csr[{sl}] == 3 if ccc[{sl}] == {k}\n"
        # 列: 生バイトなら 0 列目は行の番号、1 列目はバイト。語の表なら語
        cols += f"ncv{d}[n, j] <- na0[n] * 4   {cc} if csr[{sl}] == 0 if ccc[{sl}] == 0 if inpw[0] == 1\n"
        cols += f"ncv{d}[n, j] <- na0[n] * 4   {cc} if csr[{sl}] == 2 if ccc[{sl}] == 0 if inpw[0] == 1\n"
        cols += f"ncv{d}[n, j] <- urb[na0[n]] * 4   {cc} if csr[{sl}] == 0 if ccc[{sl}] == 1 if inpw[0] == 1\n"
        cols += f"ncv{d}[n, j] <- urb[na0[n]] * 4   {cc} if csr[{sl}] == 2 if ccc[{sl}] == 1 if inpw[0] == 1\n"
    src = open(os.path.join(HERE, 'base.lx'), encoding='utf-8').read()
    src = src.replace('if nin2[z] <= 262144', 'if nin2[z] <= %d' % (NI + 1)).replace('NIMAX', str(NI + 1))
    return src + textwrap.dedent(head) + cols + level(0) + level(1) + level(2)
