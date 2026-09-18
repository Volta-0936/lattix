# -*- coding: utf-8 -*-
"""**一枚の本にする（第A段4）** —— `run.lx` の「表の読み」を、前段が書く
   「場の読み」へ置き換える。

   これまでは二つの不動点が **表**で継いであった:

       源のバイト → front.lx → 家の表（dat/spc/ssz/mp/fg/fc/fp/ate）
                                        ↓ Python が運ぶ
                                     run.lx → 最小不動点

   表を運ぶのは Python である。だから「Lattix だけで走る」には表を消す
   しかない —— **表を場にする**。

   ここで測った言語の事実が三つある（どれも試して分かった）:

   ① **表の読みは疎、場の読みは密。** `for (…) in fg` は行のある物だけを
      なめるが、場は宣言した箱をなめる。だから一枚にするには前段が
      **詰まった番号**を配っていなければならない。幸い前段の番号はもともと
      詰まっている（規則 r・文 s・枠 u）—— `compact`（pipeline.py）が
      要ったのは *機械の配列* が小さい番号しか引けないからで、番号その
      ものは前段のもので足りる。

   ② **⊥ を繰り返しの上限に置くと、繰り返しは空になる。** だから
      「行が無い」は場でもそのまま「火が消える」になる。番兵の層 999 も
      要らない（run.lx 側の `if st != 999` は残しても当たらない）。

   ③ **無いことは `not` では測れない —— 0 も偽だからである。**
      `m[1] <- 0` と書いた升に `not m[1]` は真を返す。既定が 0 の列なら
      それでよい（0 を書くのは無害）が、既定が 0 でない列（fg の am/wm、
      fc の wm）では嘘になる。**在ることを `>= 0` で立て、それを否定する。**

   使い方:
       python3 work/onebook.py examples/02_strata.lx  > /tmp/all.lx
       python3 lattix.py /tmp/all.lx          # ← 表は ch 一枚だけ
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'test'))

# ── 表ごとの「行の形 → 場の読み」────────────────────────────────
#   鍵（e / q / i / u）だけは繰り返しの変数のまま。残りの列は場の読みに
#   なる。fc と fp の sp / st は **規則ごとの値**なので fg と同じ場を読む
#   （参照の組み立て器も `spof[(r,)]` / `st[(r,)]` を写していた）。
PAT = {
    'fp': ("for (e,sp,st,kd,lat,pb,am,mo,p1,p2,mu) in fp",
           "for (e) in 0 .. znr2m[0] for (u) in 0 .. 127 if zfpu[e, u]",
           {'sp': 'Fgsp[e]', 'st': 'Fgst[e]', 'kd': 'Fpkd[e,u]',
            'lat': 'Fplat[e,u]', 'pb': 'Fppb[e,u]', 'am': 'Fpam[e,u]',
            'mo': 'Fpmo[e,u]', 'p1': 'Fpp1[e,u]', 'p2': 'Fpp2[e,u]',
            'mu': 'Fpmu[e,u]'}),
    'fc': ("for (e,sp,st,kk,lat,cm,op,n,r1,r2,wm) in fc",
           "for (e) in 0 .. znr2m[0] for (i) in 0 .. 7 if Fcu[e, i]",
           {'sp': 'Fgsp[e]', 'st': 'Fgst[e]', 'kk': 'Fckk[e,i]',
            'lat': 'Fclat[e,i]', 'cm': 'Fccm[e,i]', 'op': 'Fcop[e,i]',
            'n': 'Fcn[e]', 'r1': 'Fcz[e]', 'r2': 'Fcz[e]',
            'wm': 'Fcwm[e,i]'}),
    'fg': ("for (e,sp,st,lat,vf,n,dm,am,bm,wm) in fg",
           "for (e) in 0 .. znr2m[0] if Fgu[e]",
           {'sp': 'Fgsp[e]', 'st': 'Fgst[e]', 'lat': 'Fglat[e]',
            'vf': 'Fgvf[e]', 'n': 'Fgn[e]', 'dm': 'Fgdm[e]',
            'am': 'Fgam[e]', 'bm': 'Fgbm[e]', 'wm': 'Fgwm[e]'}),
    'cd': ("for (e,st,k,lat,c,op,n,r1,r2,w) in cd",
           "for (e) in 0 .. zNE[0] for (i) in 0 .. 15",
           {'st': 'Cdst[e,i]', 'k': 'Cdk[e,i]', 'lat': 'Cdlat[e,i]',
            'c': 'Cdc[e,i]', 'op': 'Cdop[e,i]', 'n': 'Cdn[e,i]',
            'r1': 'Cdr1[e,i]', 'r2': 'Cdr2[e,i]', 'w': 'Cdw[e,i]'}),
    'eg': ("for (e,st,lat,t,vf,n,a,la,b,w) in eg",
           "for (e) in 0 .. zNE[0]",
           {'st': 'Egst[e]', 'lat': 'Eglat[e]', 't': 'Egt[e]',
            'vf': 'Egvf[e]', 'n': 'Egn[e]', 'a': 'Ega[e]', 'la': 'Egla[e]',
            'b': 'Egb[e]', 'w': 'Egw[e]'}),
    'ix': ("for (q,im,ic,il,iz,dl) in ix",
           "for (q) in 0 .. zNQ[0]",
           {'im': 'Ixm[q]', 'ic': 'Ixc[q]', 'il': 'Ixl[q]',
            'iz': 'Ixz[q]', 'dl': 'Ixd[q]'}),
}
ORDER = ('fp', 'fc', 'fg', 'cd', 'eg', 'ix')     # 長い綴りから当てる
#   **行が在ることを、場では立てて言わねばならない。** 表は「行がある物だけ」を
#   なめるので、存在の判断が繰り返しそのものに入っていた。場は宣言した箱を
#   なめるので、`if Fgu[e]` / `if Fcu[e,i]` / `if zfpu[e,u]` を足さないと、
#   *居ない行* まで数えてしまう —— 門の数 `fq` が 1 のはずが 9 になり、
#   `fn >= fq` が立たず、家の寄与が一つも書かれなかった。

# 前段の場をそのまま読む物（写す必要が無い —— 既定も要らない）
DIRECT = {'D': 'zdat', 'SB': 'zspb', 'SW': 'zspw', 'SD': 'zsps',
          'SZ': 'zssz', 'ok': 'Rok'}

# 写像の列（既定は 0。**0 が真の値でも無害**なので `not` でよい）
MCOL = [('MC', 'zmc'), ('MA0', 'zmj0'), ('ML0', 'zmc0'), ('MK0', 'zmm0'),
        ('MA1', 'zmj1'), ('ML1', 'zmc1'), ('MK1', 'zmm1'),
        ('MA2', 'zmj2'), ('ML2', 'zmc2'), ('MK2', 'zmm2'),
        ('MI', 'zmia'), ('MB', 'zmib'), ('MU', 'zmiu'),
        ('MI2', 'zmia2'), ('MB2', 'zmib2'), ('MU2', 'zmiu2')]


def _cut(src, points=False):
    """run.lx から、この一枚に要らない行を落とす。

    ① **表を写すところ**（`dat`/`spc`/`ssz`/`mp`/`ate`）—— 場を直に読むので
       要らない。
    ② **点の道**（`eg`/`cd`/`ix`）—— 前段はまだ出さない。残すと
       「死んでいるが書いてある」ので、成層器が `rz` の輪を棄却する
       （`for (q) in 0 .. zNQ[0]` は静的な区間ではないから、軸を刻む時計が
       立たない）。**死んでいる規則は、書いてあるだけで成層を壊す。**
       前段が点の道を出すようになったら points=True で戻す。

    落とした結果 **書き手が居なくなった場**は、読む規則ごと落ちる
    （不動点）。どの場が消えるかを手で並べない —— 数えさせる。
    """
    keep = []
    for ln in src.splitlines():
        if re.search(r'\bin (dat|spc|ssz|mp|ate)\b', ln):
            continue
        if not points and re.search(r'\bin (eg|cd|ix)\b', ln):
            continue
        keep.append(ln)
    decl = {m.group(1): i for i, ln in enumerate(keep)
            for m in [re.match(r'field\s+(\w+)', ln)] if m}
    # **橋が書く場を「書き手が居ない」と数えてはいけない。** ここは宣言も
    # 規則も橋の側にある（run.lx からは落とす）—— 参照は生きている。
    hold = {'D', 'SB', 'SW', 'SD', 'SZ', 'AE1', 'AE2'} | {m for m, _ in MCOL}
    drop = set(hold)
    for _round in range(20):
        body = [(i, ln) for i, ln in enumerate(keep)
                if not re.match(r'field\s|#|print\s|\s*$', ln)]
        wr = {re.match(r'(\w+)\[', ln).group(1) for _i, ln in body
              if re.match(r'(\w+)\[', ln)}
        dead = {f for f in decl if f not in wr and f not in hold}
        if not dead:
            break
        drop |= dead
        keep = [ln for i, ln in enumerate(keep)
                if not (re.match(r'field\s+(\w+)', ln)
                        and re.match(r'field\s+(\w+)', ln).group(1) in drop)
                and not any(re.search(r'\b' + f + r'\[', ln) for f in dead)]
        decl = {m.group(1): i for i, ln in enumerate(keep)
                for m in [re.match(r'field\s+(\w+)', ln)] if m}
    return "\n".join(keep)


def fieldize(src):
    """行ごとに、表の読みを場の読みへ置き換える。"""
    out = []
    for ln in src.splitlines():
        for nm in ORDER:
            pat, loop, cols = PAT[nm]
            if pat not in ln:
                continue
            ln = ln.replace(pat, loop)
            # **列は束ねた変数であって、場ではない。** だから `[` が続く綴りは
            # 列ではない —— 面の名前 `vf` と eg の列 `vf` はこれで分かれる
            # （`vf[s-1, …]` を `Egvf[e][s-1, …]` に潰した事故がここから出た）。
            rx = re.compile(r'\b(' + '|'.join(
                sorted(cols, key=len, reverse=True)) + r')\b(?!\s*\[)')
            ln = rx.sub(lambda m: cols[m.group(1)], ln)
            break
        rx2 = re.compile(r'\b(' + '|'.join(
            sorted(DIRECT, key=len, reverse=True)) + r')\b')
        ln = rx2.sub(lambda m: DIRECT[m.group(1)], ln)
        out.append(ln)
    return "\n".join(out)


def _zero(nm, src, key, loop, live=""):
    """既定 0 の列。**0 が真の値でも `max` の上では無害**（0 を重ねるだけ）。"""
    return (f"{nm}[{key}] <- 0        {loop}{live} if not {src}[{key}]\n"
            f"{nm}[{key}] <- {src}[{key}]   {loop}\n")


BRIDGE = """
# ══ 家の表を **場**で言う（第A段4）════════════════════════════════
#   ここから下は「表を運ぶ Python」の置き換えである。参照の組み立て器
#   （test/front.py front_family）がやっていた「列を寄せて既定を埋める」を
#   そのまま Lattix で書いた。番号は前段のものをそのまま使う ——
#   **番号はラベルであって名前ではない**ので、詰め直す理由が無い
#   （機械の配列に入れるときだけ詰める。それは焼く側の仕事である）。

# ── 原子の剰余（ate）。行の番号は原子の基から始まる ──────────────
field AE1 : flat bound 71454279745205302
field AE2 : flat bound 71454279745205302
AE1[zatb[0] + i] <- zate1[i]   for (i) in 0 .. 63
AE2[zatb[0] + i] <- zate2[i]   for (i) in 0 .. 63

# ── fg: 規則ごとに一行。**在ることは `zfgst >= 0` が言う** ─────────
field Fgu : or bound 4096
Fgu[e] <- true         for (e) in 0 .. znr2m[0] if zfgst[e] >= 0
field Fgst : max bound 4096
Fgst[e] <- zfgst[e]    for (e) in 0 .. znr2m[0]
field Fgsp : max bound 4096
Fgsp[e] <- zspof[e]    for (e) in 0 .. znr2m[0] if Fgu[e]
field Fglat : max bound 4096
Fglat[e] <- zfglat[e]  for (e) in 0 .. znr2m[0]
field Fgdm : max bound 4096
Fgdm[e] <- e * 128     for (e) in 0 .. znr2m[0] if Fgu[e]
"""


def bridge():
    T = [BRIDGE]
    A = T.append
    NR = "for (e) in 0 .. znr2m[0]"
    A("field Fgvf : max bound 4096")
    A(_zero('Fgvf', 'zfgvf', 'e', NR, " if Fgu[e]").rstrip())
    A("field Fgn : max bound 4096")
    A(_zero('Fgn', 'zfgns', 'e', NR, " if Fgu[e]").rstrip())
    # ── 既定が 0 でない列 —— **在ることを立ててから否定する** ───────
    A("# **0 も偽である**ので、既定が 0 でない列は `not` では埋められない。")
    A("field Fgamu : or bound 4096")
    A(f"Fgamu[e] <- true      {NR} if zfgam[e] >= 0")
    A("field Fgam : max bound 4096")
    A(f"Fgam[e] <- e * 128 + 1   {NR} if Fgu[e] if zhasa[e] if not Fgamu[e]")
    A(f"Fgam[e] <- e * 128 + 4   {NR} if Fgu[e] if not zhasa[e] if not Fgamu[e]")
    A(f"Fgam[e] <- zfgam[e]      {NR} if Fgamu[e]")
    A("field Fgwmu : or bound 4096")
    A(f"Fgwmu[e] <- true      {NR} if zwm[e] >= 0")
    A("field Fgwm : max bound 4096")
    A(f"Fgwm[e] <- e * 128 + 4   {NR} if Fgu[e] if not Fgwmu[e]")
    A(f"Fgwm[e] <- zwm[e]        {NR} if Fgwmu[e]")
    A("field Fgbm : max bound 4096")
    A(f"Fgbm[e] <- e * 128 + 2   {NR} if Fgu[e] if Fgn[e] == 2")
    A(f"Fgbm[e] <- e * 128 + 4   {NR} if Fgu[e] if Fgn[e] <= 1")
    A("")
    A("# ── fc: 文 s の門を、**規則の番号へ写す**（zrn が写す）─────────")
    A("#   参照の組み立て器も `zrnm.get((s,))` が None の文を捨てていた ——")
    A("#   ここでは `if zrn[s] >= 0` がその判断である。")
    S = "for (s) in 0 .. nstz[0] for (i) in 0 .. 7 if zrn[s] >= 0"
    A("field Fcu : or bound 4096 8")
    A(f"Fcu[zrn[s], i] <- true    {S} if zfck[s, i] >= 0")
    for nm, src in (('Fckk', 'zfck'), ('Fccm', 'zfcam')):
        A(f"field {nm} : max bound 4096 8")
        A(f"{nm}[zrn[s], i] <- {src}[s, i]   {S}")
    for nm, src in (('Fclat', 'zfclt'), ('Fcop', 'zfcop')):
        A(f"field {nm} : max bound 4096 8")
        A(f"{nm}[zrn[s], i] <- 0        {S} if zfck[s, i] >= 0 if not {src}[s, i]")
        A(f"{nm}[zrn[s], i] <- {src}[s, i]   {S}")
    A("field Fcz : max bound 4096            # 門の r1 / r2 は零の写像")
    A(f"Fcz[e] <- e * 128 + 4     {NR} if Fgu[e]")
    A("field Fcn : max bound 4096            # 門の n は必ず 0")
    A(f"Fcn[e] <- 0               {NR} if Fgu[e]")
    A("field Fcwmu : or bound 4096 8")
    A(f"Fcwmu[zrn[s], i] <- true  {S} if zfcwm[s, i] >= 0")
    A("field Fcwm : max bound 4096 8")
    A(f"Fcwm[zrn[s], i] <- zrn[s] * 128 + 4   {S} if zfck[s, i] >= 0 "
      f"if not Fcwmu[zrn[s], i]")
    A(f"Fcwm[zrn[s], i] <- zfcwm[s, i]        {S}")
    A("")
    A("# ── fp: 枠（規則 r・枠番号 u）。前段がもう詰めて番号を配っている ──")
    U = "for (e) in 0 .. znr2m[0] for (u) in 0 .. 127"
    for nm, src in (('Fplat', 'zfplt'), ('Fppb', 'zfpb'), ('Fpam', 'zfpam')):
        A(f"field {nm} : max bound 4096 128")
        A(f"{nm}[e, u] <- {src}[e, u]   {U}")
    for nm, src in (('Fpkd', 'zfpk'), ('Fpmo', 'zfpmo'), ('Fpp1', 'zfpsr'),
                    ('Fpp2', 'zfps2'), ('Fpmu', 'zfpx')):
        A(f"field {nm} : max bound 4096 128")
        A(f"{nm}[e, u] <- 0        {U} if zfpu[e, u] if not {src}[e, u]")
        A(f"{nm}[e, u] <- {src}[e, u]   {U}")
    A("")
    A("# ── 写像の列。**使っている写像だけ**（zmu）。既定は 0 ───────────")
    M = ("for (r) in 0 .. znr2m[0] for (k) in 0 .. 127 "
         "if zmu[r * 128 + k]")
    for nm, src in MCOL:
        A(f"field {nm} : max bound 524288")
        A(f"{nm}[r * 128 + k] <- 0        {M} if not {src}[r * 128 + k]")
        A(f"{nm}[r * 128 + k] <- {src}[r * 128 + k]   {M}")
    return "\n".join(T) + "\n"


def prune(head, eng, say=print):
    """**形を刈る判断を、場の形でもう一度やる。**

    表の形（run.lx）が成層できたのは、番兵の表（層 999 の一行）が
    「この規則は一度も起きない」と *地上で* 言えたからである
    （`_fires` → `_sign_sense` が `sum` の符号を UP のままにする）。
    場になるとその一行が無いので、`sum` の面は符号不明（NONE）になり、
    門の輪 `fn → fo → vm → fn` が非単調として棄却される。

    **同じ判断が二箇所にある**（気づき34）—— mkrun.write も同じ刈りを
    している。ここでも同じことをする: 断られた行を落とし、落とした形を
    一つずつ声に出す。数え上げた形であって測った形ではないので、
    たいていは誰も使っていない。
    """
    import lattix as _L
    #  刈った行は **消さずに註へ変える** —— 行番号が動くと、処理系が言う
    #  「line N」が次の回で別の行を指す（一度それで同じ行を二度刈って
    #  止まった）。番号はラベルであって名前ではないが、**ラベルは動かして
    #  よいものではない**。
    lines = eng.splitlines()
    off, out = head.count("\n"), []
    for _round in range(60):
        body = "\n".join(lines)
        try:
            q = _L.parse(head + body); _L.check(q); _L.stratify(q)
            return body, out
        except _L.LattixError as ex:
            m = re.search(r'line (\d+)', str(ex))
            if not m:
                raise
            ln = int(m.group(1)) - 1 - off
            if ln < 0 or ln >= len(lines) or lines[ln].startswith('#'):
                raise
            #  **刈った物は、字面ではなく形で言う。** 頭を 80 字切っても
            #  どの形かは分からない —— 判断はガードに書いてある。
            shp = re.findall(r'if (?:F\w+\[[^\]]*\]|\w+) == -?\d+', lines[ln])
            who = lines[ln].split('[')[0]
            out.append(f"{who}: {' '.join(shp)}")
            say(f"  刈った: {who:<4} {' '.join(shp)}")
            lines[ln] = '# 刈った（場の形では単調でない）: ' + lines[ln][:60]
    raise SystemExit("刈っても閉じない —— 数え上げの根拠が破れている")



# ══ 見せる物（show.lx）を一枚に入れる ══════════════════════════════
#   show.lx が食う表は十枚あるが、**中身はもう前段が持っている** ——
#   置き場（fld）は zlatf / zfna / zfb / zflo* / zfsz* / zfs*、名前（fnm）は
#   文字の流れ、print の並び（prn）は zprn、原子の基（ab）は zatb、
#   原子の型（fat）は zfat。答え（pv）だけが **機械の面**から来る。
#
#   `pv` は疎（値のある升だけ）だが場は密なので、**宣言した升を全部なめる**
#   （`for (f) for (c) in 0 .. fvz[f]`）。そして「升に値があるか」は
#   `not` では測れない（0 も偽）——**`>= 0` と `<= 0` の二本**で言う。
#   ⊥ ではどちらも立たないので、これが「在る」の正しい測り方である。
SHOWPAT = {
    'prn': ("for (i, f) in prn", "for (i) in 0 .. znpz[0]", {'f': 'zprn[i]'}),
    # `pv` は疎（値のある升だけ）。場では **宣言した升を全部なめて**、
    # 「値がある」は `has` が言う。見せる物は同じ表を二つの綴りで読んで
    # いるので（`(f,c,v)` と `(fg,g,vg)`）、二本とも置き換える。
    'pv': ("for (f, c, v) in pv",
           "for (f) in 0 .. zNF[0] for (pc) in 0 .. fvz[f] if has[fbase[f] + pc]",
           {'c': '(fbase[f] + pc)', 'v': 'val[fbase[f] + pc]'}),
    'pv2': ("for (fg, g, vg) in pv",
            "for (fg) in 0 .. zNF[0] for (pc) in 0 .. fvz[fg] if has[fbase[fg] + pc]",
            {'g': '(fbase[fg] + pc)', 'vg': 'val[fbase[fg] + pc]'}),
}
#   この段（第一の刈り）が見ない物 —— 原子・構成子・集合。
#   これらを使う本はまだ一枚にできない（front 側の綴りの表がまだ要る）。
#   **集合（ps）だけは、まだ場にできない。** 面に置かれた集合から元を
#   取り出す言葉が Lattix に無いからである（作れるが、数えられない）。
#   機械は arena に整列して置くので番号で引けるが、それは面の外の構造で
#   あって、規則からは見えない。ここは言語の穴として数えておく。
SHOWCUT = ('fld', 'fnm', 'atm', 'ab', 'fat', 'ps', 'ctr', 'cac')
#   前段と綴りがぶつかる三つ（`farr` / `nch` / `neg`）。**名前は座標である**
#   ので、同じ綴りは同じ場になってしまう —— 見せる物の側を改名する。
SHOWREN = {'farr': 'Sfarr', 'nch': 'Snch', 'neg': 'Sneg'}
#   数の面（束の番号 → 面の綴り）。集合 7 / bag 10 / fourv 6 は第一の刈りの外。
NUMLAT = [(1, 'vn'), (2, 'vx'), (5, 'vf'), (8, 'vm'), (9, 'vc')]
BOOLLAT = [(3, 'vo'), (4, 'va')]


def _consts(src):
    """show.lx の中の **字面の表**（topc / emp）を種の場に直す。
    プログラムに依らない定数なので、表である理由が無い。"""
    out, rules = src, []
    for nm in ('topc', 'emp'):
        m = re.search(rf"^table {nm} = (.*)$", out, re.M)
        if not m:
            continue
        rows = re.findall(r"\((\d+),(\d+)\)", m.group(1))
        rules.append(f"field z{nm} : max bound {len(rows) + 1}")
        rules += [f"z{nm}[{k}] <- {c}" for k, c in rows]
        out = out.replace(m.group(0), "")
        out = out.replace(f"for (k, c) in {nm}",
                          f"for (k) in 0 .. {len(rows) - 1}")
        out = re.sub(rf"<- c (for \(t\) in 0 \.\. nitz\[0\] for \(k\) in 0 \.\. {len(rows)-1})",
                     rf"<- z{nm}[k] \1", out)
    return "\n".join(rules) + "\n" + out


def _ren(src):
    """前段とぶつかる綴りを改名する。"""
    rx = re.compile(r'\b(' + '|'.join(SHOWREN) + r')\b')
    return rx.sub(lambda m: SHOWREN[m.group(1)], src)


def _logical(src):
    """**規則は行ではない。** 続きの行（空白で始まる行）は前の規則の一部で
    ある。行で切ると規則が割れる —— `isset` の `for (…) in pv` だけ落として
    `if item[t] == c` を残し、`c` が宙に浮いた事故がここから出た。"""
    out = []
    for ln in src.splitlines():
        if out and ln[:1].isspace() and ln.strip():
            out[-1] += " " + ln.strip()
        else:
            out.append(ln)
    return out


def _cutshow(src):
    """見せる物から、**表を読む規則だけ**を落とす。

    宣言は残す。**書き手の消えた場は、読んでも正しい** —— `if not isnv[t]`
    は書き手が居なければ真であり、それがこの段の意味そのものである
    （構成子の値は無い）。書き手が消えたからといって読む規則まで落とすと、
    `num[t,3] <- ival[t] … if not isnv[t]` が道連れになって **値が一つも
    出なくなる**（`d[0] = ` だけが出た事故がここから出た）。
    """
    return "\n".join(ln for ln in _logical(src)
                     if not re.match(r'table\s', ln)
                     and not re.search(r'\bin (' + '|'.join(SHOWCUT) + r')\b', ln))


def showbridge(last):
    """前段の場と機械の面から、見せる物の場を埋める。last = 最後の層。"""
    T = []
    A = T.append
    NF = "for (f) in 0 .. zNF[0]"
    A("# ══ 見せる物の表を **場**で言う ════════════════════════════════")
    A("field zNF : max bound 1                 # 場の数 − 1（合成の場も込み）")
    A("zNF[z] <- znf2[0] - 1 for (z) in 0 .. 0")
    A("field zfu : or bound 1024               # 場 f は在る（束がある）")
    A(f"zfu[f] <- true {NF} if zlatf[f] >= 1")
    A(f"flat_[f] <- zlatf[f]    {NF} if zfu[f]")
    A("# 次数は記述のもの（添字なしの場は 0 次）")
    A(f"farr[f] <- zfna[f]      {NF} if zfu[f] if not zfna0[f]")
    A(f"farr[f] <- 0            {NF} if zfu[f] if zfna0[f]")
    A(f"fbase[f] <- zfb[f]      {NF} if zfu[f]")
    for d, (lo, sz) in enumerate((('zflo0', 'zfsz0'), ('zflo1', 'zfsz1'),
                                  ('zflo2', 'zfsz2'))):
        A(f"flo[f, {d}] <- {lo}[f]   {NF} if zfu[f] if farr[f] >= {d + 1}")
        A(f"flo[f, {d}] <- 0         {NF} if zfu[f] if farr[f] <= {d}")
        A(f"fsz[f, {d}] <- {sz}[f]   {NF} if zfu[f] if farr[f] >= {d + 1}")
        A(f"fsz[f, {d}] <- 1         {NF} if zfu[f] if farr[f] <= {d}")
    for d, st in enumerate(('zfs0', 'zfs1')):
        A(f"fst[f, {d}] <- {st}[f]   {NF} if zfu[f] if farr[f] >= {d + 1}")
        A(f"fst[f, {d}] <- 1         {NF} if zfu[f] if farr[f] <= {d}")
    A(f"fst[f, 2] <- 1           {NF} if zfu[f]")
    A(f"fvol[f] <- fsz[f, 0] * fst[f, 0]   {NF} if zfu[f]")
    A(f"flast[f] <- fbase[f] + fvol[f] - 1 {NF} if zfu[f]")
    A(f"fvz[f] <- fvol[f] - 1              {NF} if zfu[f]")
    A("# 名前の綴りは **文字の流れから**（dch は 16 文字しか持っていない）")
    A("fnl[dcof[i] - 1] <- cpos[i] + 1 for (i,c) in ch if isdcl[tnum[i]]")
    A("fnc[dcof[i] - 1, cpos[i]] <- c for (i,c) in ch if isdcl[tnum[i]]")
    A("      if cpos[i] <= 31")
    A("atb[z] <- zatb[0] for (z) in 0 .. 0")
    A("# 合成の場（構成子の引数場）の名前は前段がもう綴っている（zach）")
    A(f"fnl[f] <- p + 1   {NF} for (p) in 0 .. 23 if zach[f, p] >= 1")
    A(f"fnc[f, p] <- zach[f, p]   {NF} for (p) in 0 .. 23 if zach[f, p] >= 1")
    A("# ── 原子の綴り。番号は `zatct - zatb`（順位）である ──────────────")
    A("#   綴りのトークンに引用符は入っていない（`tag(alpha, 0)` が")
    A("#   `tag(lpha, 0)` と出て分かった —— 頭を一字落としていた）。")
    A("atl[zatct[tnum[i]] - zatb[0]] <- cpos[i] + 1 for (i,c) in ch")
    A("      if zatct[tnum[i]] >= zatb[0]")
    A("atc[zatct[tnum[i]] - zatb[0], cpos[i]] <- c for (i,c) in ch")
    A("      if zatct[tnum[i]] >= zatb[0] if cpos[i] <= 31")
    A("# ── 構成子の名前と引数場 ──────────────────────────────────────")
    A("nctz[z] <- zncdm[0] for (z) in 0 .. 0")
    A("ctnl[c] <- p + 1 for (c) in 0 .. zncdm[0] for (p) in 0 .. 31")
    A("      if tch[zcdt[c], p] >= 1")
    A("ctnc[c, p] <- tch[zcdt[c], p] for (c) in 0 .. zncdm[0] for (p) in 0 .. 31")
    A("ctar[c] <- zcar[c] for (c) in 0 .. zncdm[0]")
    A("ctaf[c, k] <- zafn[c, k] for (c) in 0 .. zncdm[0] for (k) in 0 .. 7")
    A("ctf0[c] <- zafn[c, 0] for (c) in 0 .. zncdm[0]")
    A("fatm[f, d] <- zfat[f, d] for (f) in 0 .. zNF[0] for (d) in 0 .. 3")
    A("")
    A("# ── 答えは機械の面から。**在ることは `>= 0` と `<= 0` の二本で言う** ──")
    C = f"{NF} for (c) in 0 .. fvz[f] if zfu[f]"
    for lt, pl in NUMLAT:
        A(f"val[fbase[f] + c] <- {pl}[{last}, fbase[f] + c]   {C} if flat_[f] == {lt}")
        A(f"has[fbase[f] + c] <- true   {C} if flat_[f] == {lt}"
          f" if {pl}[{last}, fbase[f] + c] >= 0")
        A(f"has[fbase[f] + c] <- true   {C} if flat_[f] == {lt}"
          f" if {pl}[{last}, fbase[f] + c] <= 0")
    for lt, pl in BOOLLAT:
        A(f"val[fbase[f] + c] <- 1      {C} if flat_[f] == {lt}"
          f" if {pl}[{last}, fbase[f] + c]")
        A(f"has[fbase[f] + c] <- true   {C} if flat_[f] == {lt}"
          f" if {pl}[{last}, fbase[f] + c]")
    return "\n".join(T) + "\n"



def _args(txt, i):
    """`f[` の直後 i から、深さ 0 のコンマで割った引数と `]` の位置を返す。"""
    d, out, st = 1, [], i
    while i < len(txt):
        c = txt[i]
        if c == '[':
            d += 1
        elif c == ']':
            d -= 1
            if d == 0:
                out.append(txt[st:i]); return out, i
        elif c == ',' and d == 1:
            out.append(txt[st:i]); st = i + 1
        i += 1
    return None, None


def fold3(src, say=lambda *a: None):
    """**三次元以上の場を二次元に畳む。**

    焼く物（31_gen）は二次元までしか座標を持たない。だが三次元の場は
    「後ろの軸の広さ」を掛けて足せば二次元になる —— 座標の意味は変わらず、
    **升の数も変わらない**（積は同じ）。宣言した広さを読んで畳むので、
    上限を新しく書くことはしない。

    `f[a, b, c]`（bound A B C）→ `f[a, (b) * C + (c)]`（bound A (B*C)）。
    """
    bnd = {}
    #   宣言の後ろには註が付く（見せる物は手書きである）—— `$` で留めると
    #   `field dgt : max bound 65536 64 41   # …` が当たらない。
    for m in re.finditer(r'^field\s+(\w+)\s*:\s*(\w+)\s+bound\s+([0-9]+(?:\s+[0-9]+)*)',
                         src, re.M):
        b = m.group(3).split()
        if len(b) >= 3:
            bnd[m.group(1)] = [int(x) for x in b]
    if not bnd:
        return src
    for f, b in sorted(bnd.items()):
        say(f"  畳んだ: {f} {len(b)} 次 → 2 次（{' × '.join(map(str, b[1:]))}）")
    out, i = [], 0
    rx = re.compile(r'\b(' + '|'.join(sorted(bnd, key=len, reverse=True)) + r')\[')
    while True:
        m = rx.search(src, i)
        if not m:
            out.append(src[i:]); break
        f = m.group(1)
        args, end = _args(src, m.end())
        if args is None or len(args) != len(bnd[f]):
            out.append(src[i:m.end()]); i = m.end(); continue
        w = bnd[f][1:]
        acc = f"({args[1].strip()})"
        for k in range(2, len(args)):
            acc = f"({acc} * {w[k-1]} + ({args[k].strip()}))"
        out.append(src[i:m.start()])
        out.append(f"{f}[{args[0].strip()}, {acc}]")
        i = end + 1
    src = "".join(out)
    # 宣言も畳む（**升の数は変わらない** —— 積が同じだから）
    def decl(m):
        b = [int(x) for x in m.group(3).split()]
        if len(b) < 3:
            return m.group(0)
        n = 1
        for x in b[1:]:
            n *= x
        return f"field {m.group(1)} : {m.group(2)} bound {b[0]} {n}"
    return re.sub(r'^field\s+(\w+)\s*:\s*(\w+)\s+bound\s+([0-9]+(?:\s+[0-9]+)*)',
                  decl, src, flags=re.M)



#   断片（31_gen）が持つ束は六つ —— min / max / or / flat / sum / count。
#   持たないのは `and` / `fourv` / `set` / `bag` の四つで、一枚の本ではその面が
#   **一つずつ**しか無い（`va` / `v4` / `vs` / `vb`）。その束を使わない本では
#   面は死んでいるので、落としても答えは変わらない —— 使う本は焼けない、と
#   **声に出して**断る側に回る（黙って違う答えを出すよりよい）。
TRIM = ('va', 'v4', 'vs', 'vb')


def trim(src, say=lambda *a: None):
    """断片に無い束の面を落とす。"""
    rx = re.compile(r'\b(' + '|'.join(TRIM) + r')\[')
    out, n = [], 0
    for ln in src.splitlines():
        m = re.match(r'field\s+(\w+)', ln)
        if m and m.group(1) in TRIM:
            n += 1; continue
        if rx.search(ln):
            n += 1; continue
        out.append(ln)
    say(f"  断片の外の束を落とした: {n} 行（{' / '.join(TRIM)}）")
    return "\n".join(out)



def cells(src, nc, say=lambda *a: None):
    """**面の箱を、要るだけにする。**

    `run.lx` は面を `bound 48 437671048959211563` と宣言している —— 内容番地が
    座標だからで、これは *測った* 値である（コーパス全体の上限）。だが一枚の
    本では **番地は法で畳んである**（`zamw`）ので、升の番号は前段の置き場の
    大きさで収まる。密配列で焼くには、この箱を要るだけに詰めるしかない
    （4.4×10^17 升は敷けない —— 焼いた物は segfault した）。
    """
    n = 0
    out = []
    for ln in src.splitlines():
        m = re.match(r'(field v\w+ : \w+ bound )(\d+) (\d+)$', ln)
        if m and int(m.group(3)) > nc:
            ln = f"{m.group(1)}{m.group(2)} {nc}"; n += 1
        out.append(ln)
    say(f"  面の箱を {nc} 升にした（{n} 面）")
    return "\n".join(out)


def build(book, prints=True, points=False, say=lambda *a: None,
          ns=None, show=False, fold=False, six=False, oneport=False,
          nc=None):
    """all.lx を組む —— 表は `ch` 一枚だけ。"""
    import front as F
    data = open(book, 'rb').read()
    if b'include ' in data:
        import lattix
        data = lattix._expand_includes(
            data.decode('utf-8'), os.path.dirname(book)).encode('utf-8')
    rows = [(i, c) for i, c in enumerate(data)] + [(len(data), 32)]
    src = re.sub(r"table ch = .*?\n",
                 "table ch = " + ", ".join(f"({i},{c})" for i, c in rows) + "\n",
                 F.SRC, count=1)
    if oneport:
        # **焼いた実行ファイルが読める表は、標準入力の一つだけ**である。
        # 口（orc / ext）は番兵一行のまま残っていたので落とす —— 口が要る本は
        # そもそも一枚で走らないので、落として困る本は無い。
        keep, n = [], 0
        for ln in src.splitlines():
            if re.match(r'table (orc|ext) ', ln) or re.search(r'\bin (orc|ext)\b', ln):
                n += 1; continue
            keep.append(ln)
        src = "\n".join(keep)
        say(f"  口の表を落とした: {n} 行（読む表は `ch` 一枚になった）")
    run = open(os.path.join(ROOT, 'run.lx'), encoding='utf-8').read()
    eng = fieldize(_cut(run, points=points))
    if ns is not None:
        # **層の上限を下げて測る。** 小さい本は層をほとんど使わないので、
        # 診断の輪はこれで十倍速くなる（答えは変わらない —— 足りなければ
        # 面が空になるので、静かに間違えるのではなく **見えて**間違える）。
        eng = re.sub(r'\b(0|1) \.\. 47\b', lambda m: f"{m.group(1)} .. {ns - 1}", eng)
    if not prints:
        eng = "\n".join(l for l in eng.splitlines() if not l.startswith('print '))
    if show:
        # 見せる物を継ぐときは、面を print するのではなく **字面を出す**。
        eng = "\n".join(l for l in eng.splitlines()
                        if not l.startswith('print '))
        sh = open(os.path.join(ROOT, 'show.lx'), encoding='utf-8').read()
        sh = fieldize2(_cutshow(_ren(_consts(sh))))
        eng = eng + "\n" + _ren(showbridge((ns or 48) - 1)) + "\n" + sh
    head = src + "\n" + bridge() + "\n"
    eng, cut = prune(head, eng, say)
    if nc:
        eng = cells(eng, nc, say)
    if six:
        eng = trim(eng, say)
    if fold:
        eng = fold3(eng, say)
    return head + eng + "\n", cut


def fieldize2(src):
    """見せる物の `prn` の読みを場の読みへ（run.lx と同じ機械的な置き換え）。"""
    out = []
    for ln in src.splitlines():
        for nm, (pat, loop, cols) in SHOWPAT.items():
            if pat not in ln:
                continue
            ln = ln.replace(pat, loop)
            rx = re.compile(r'\b(' + '|'.join(cols) + r')\b(?!\s*\[)')
            ln = rx.sub(lambda m: cols[m.group(1)], ln)
        out.append(ln)
    return "\n".join(out)


if __name__ == '__main__':
    os.environ.setdefault('LATTIX_FAMILY_MIN', '1')
    bk = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work/t/a_min.lx')
    txt, cut = build(bk, say=lambda m: print(m, file=sys.stderr))
    sys.stdout.write(txt)
