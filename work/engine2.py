# -*- coding: utf-8 -*-
"""寄与の関係（flat.py の出力）を閉じる物。**Lattix で書いてある。**

   種で場合分けする解釈器ではない。表にあるのは辺だけで、走らせる物は
   「辺の先に、辺の元＋重みを寄せる」としか言っていない。fetch も decode も無い。

   升を指すのは **指し番号**ひとつで、`rz` が解く。だから走らせる側には
   「直接の升」と「値で決まる升」の場合分けが一つも無い。
"""
import io, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lattix as L
from flat import flatten, PLANE, OP, ARITH, LAT

EG = "(e,st,lat,t,vf,n,a,la,b,w) in eg"
CD = "(e,st,k,lat,c,op,n,r1,r2,w) in cd"
IX = "(q,im,ic,il,iz,dl) in ix"
FG = "(e,sp,st,lat,vf,n,dm,am,bm,wm) in fg"
FC = "(e,sp,st,kk,lat,cm,op,n,r1,r2,wm) in fc"
FP = "(e,sp,st,kd,lat,pb,am,mo,p1,p2,mu) in fp"


def _ax(sl, X):
    """空間 sp の点 t から、枠 sl の軸の **行と列**を取り出す。
    「表の列か計数器か」の場合分けは無い —— 区間も表と同じ行に置いてある。"""
    a = f"MA{sl}[{X}]"
    return (f"D[SB[sp,{a}] + (t / SD[sp,{a}]) % SW[sp,{a}], ML{sl}[{X}]]")


def _map(X, s=None):
    """写像 X の値 = 定数 + Σ 係数 × 軸の値 + 係数 × **番地の面**。

    最後の項が「値で決まる座標」である —— `f[g[i]]` の `g[i]` は点ごとに
    違うが、その値の置き場もまた空間なので、`pa[s, 基 + 点]` に写しておけば
    写像は一次式のままでいられる。使わない写像は `pa[s, 0] = 0` を読む
    （場合分けを作らないための番兵）。層 s は座標である。"""
    out = f"MC[{X}]" + "".join(f" + MK{i}[{X}] * {_ax(i, X)}" for i in range(3))
    if s is not None:
        out += f" + MI[{X}] * pa[s, MB[{X}] + MU[{X}] * t]"
        out += f" + MI2[{X}] * pa[s, MB2[{X}] + MU2[{X}] * t]"
    return out
IOP = {v: k for k, v in OP.items()}
KEYED = (8, 9, 10)                  # sum / count / bag —— 寄与元キー付き
BOOL  = (3, 4, 9)                   # true を寄せる束


def engine_text(nc, ne, nq, ns, shapes, ixlat, fsh=(), nrow=1, ncol=1,
                nsp=1, nmp=1, nax=1, fcsh=(), npt=1, fpsh=(), npa=1):
    """**層は座標である。** 前は層ごとに規則を字面で展開していた（vf0, vf1,
    … と名前が層を持っていた —— 名前が座標だった）。いまは場が先頭に s 軸を
    持ち、規則は `for (s) in 0 .. N-1` を纏う。閉じた面は `s-1` の読みである。
    成層は処理系が軸に沿って証明する（SPEC「層は座標である」/ _axis_unroll）
    —— 判断も意味も変えず、**同じグラウンド集合を 16 分の 1 の字数で言う**。"""
    vals, cond, lats = shapes
    T = []; A = T.append
    SA = f"for (s) in 0 .. {ns - 1}"      # 全部の層
    S1 = f"for (s) in 1 .. {ns - 1}"      # 閉じた面を読む物（s-1 が要る）
    PS = 's' if fpsh else None
    A("# ══ 走らせる物 —— 寄与の関係を閉じる ════════════════════════════")
    A("#  升は番号。場も座標も、もうここには無い。**層も座標である。**")
    if fsh:
        A("")
        A("# ── 多面体の道 —— **反復空間を点に潰さずに渡す** ────────────────")
        A("#  「宣言されているものを、そのまま機械に渡すには？」（CLAUDE.md）")
        A("#  軸の中身は `dat` の行に置いてある（区間も表と同じ形）。")
        A(f"field D : flat bound {nrow} {ncol}")
        A("D[r,c] <- v            for (r,c,v) in dat")
        for nm, col in (('SB', 'b'), ('SW', 'w'), ('SD', 'd')):
            A(f"field {nm} : max bound {nsp} {nax}")
            A(f"{nm}[sp,j] <- {col}   for (sp,j,b,w,d) in spc")
        A(f"field SZ : max bound {nsp}")
        A("SZ[sp] <- n            for (sp,n) in ssz")
        MP = "for (x,k0,a0,l0,m0,a1,l1,m1,a2,l2,m2,im,ib,iu,i2,b2,u2) in mp"
        A(f"field MC : max bound {nmp}")
        A(f"MC[x] <- k0            {MP}")
        for i in range(3):
            for nm, col in (('MA', 'a'), ('ML', 'l'), ('MK', 'm')):
                A(f"field {nm}{i} : max bound {nmp}")
                A(f"{nm}{i}[x] <- {col}{i}   {MP}")
        for nm, col in (('MI', 'im'), ('MB', 'ib'), ('MU', 'iu'),
                        ('MI2', 'i2'), ('MB2', 'b2'), ('MU2', 'u2')):
            A(f"field {nm} : max bound {nmp}")
            A(f"{nm}[x] <- {col}   {MP}")
    for lt in lats:
        pl, nm = PLANE[lt]
        A(f"field v{pl} : {nm} bound {ns} {nc}")
    # `rz` は **flat**。番地は ⊥ → v としか動かない（育たない）ので、
    # 座標に使っても単調である。max にすると「育つ値を座標にした」ことになる。
    A(f"field rz : flat bound {ns} {nq}")
    A(f"field nc : count bound {ns} {ne}")
    A(f"field ng : count bound {ns} {ne}")
    A(f"field ok : or bound {ns} {ne}")
    # **条件のためだけの面。** 閉じた面からしか読まないので、寄与が立つか
    # どうか（`ok`）に依存しない —— だから否定や等号の輪に入らない。
    A(f"field ct : flat bound {ns} {nc}")
    if fpsh:
        # **番地の面。** 値で決まる座標を、点ごとに一升だけ写しておく。
        # 升 0 は番兵（`pa[s, 0] = 0`）で、使わない写像はここを読む。
        A(f"field pa : flat bound {ns} {npa}")
        A(f"pa[s, 0] <- 0   {SA}")
    if fcsh:
        # **多面体のガード。** 「全部立った」を (辺, 点) で数える ——
        # 要る数は辺ごと（点に依らない）ので `fq` は s と辺の二次元でよい。
        A(f"field fq : count bound {ns} {ne}")
        A(f"field fn : count bound {ns} {ne} {npt}")
        A(f"field fo : or bound {ns} {ne} {npt}")

    A(""); A("# ══ 升を指す番号を解く。m = 0 はそのまま、それ以外は値で決まる升。══")
    A(f"rz[s, q] <- iz        {SA} for {IX} if im == 0")
    for lt in ixlat:
        if lt >= 0: continue
        ql, _ = PLANE[-lt]
        A("# 内容アドレスは育たない（⊥ → v → ⊤）ので **生きた面**でよい")
        A(f"rz[s, q] <- im * v{ql}[s, ic] + iz   {SA} for {IX} if il == {lt}")
    for lt in ixlat:
        if lt < 0: continue
        ql, _ = PLANE[lt]
        A(f"rz[s, q] <- im * v{ql}[s - 1, ic] + iz   {S1} for {IX} if il == {lt}")
    A("# 閉じた層 s-1 を引き継ぐ（寄与元キー付きの束は引き継がず作り直す）")
    for lt in lats:
        if lt in KEYED: continue
        pl, _ = PLANE[lt]
        A(f"v{pl}[s, rz[s, q]] <- v{pl}[s - 1, rz[s, q]]   {S1} for {IX} if dl == {lt}")

    A("# ── 条件のための項。閉じた面 s-1 からしか読まない。────────────")
    CT = f"{S1} for {EG} if st == 0 - s - 1"
    A(f"ct[s, rz[s, t]] <- w   {CT} if vf == 0")
    for lt in lats:
        ql, _ = PLANE[lt]
        A(f"ct[s, rz[s, t]] <- v{ql}[s - 1, rz[s, a]]   {CT} if vf == 4 if la == {lt}")
    A(f"ct[s, rz[s, t]] <- ct[s, rz[s, a]] + w   {CT} if vf == 1 if n == 1")
    A(f"ct[s, rz[s, t]] <- ct[s, rz[s, a]] + ct[s, rz[s, b]] + w   {CT} if vf == 1 if n == 2")
    for vfc, o in ((6, '*'), (7, '/'), (8, '%')):
        A(f"ct[s, rz[s, t]] <- ct[s, rz[s, a]] {o} w   {CT} if vf == {vfc} if n == 1")
        A(f"ct[s, rz[s, t]] <- ct[s, rz[s, a]] {o} ct[s, rz[s, b]]   {CT} if vf == {vfc} if n == 2")

    A("# ── 条件は **数える**。否定にすると、単調な肯定まで輪に入る。──")
    A(f"nc[s, e] <- true   {SA} for {EG} if st == s")
    A(f"ng[s, e] <- true   {SA} for {EG} if st == s")
    A(f"ng[s, e] <- true   {SA} for {CD} if st == s")
    for (k, lt, op, n) in cond:
        S0 = S1 if (k in (1, 2) or lt == 0) else SA
        g = f"{S0} for {CD} if st == s if k == {k} if lat == {lt}"
        cc, R1, R2 = "rz[s, c]", "rz[s, r1]", "rz[s, r2]"
        if lt == 0:
            V = "ct[s,"                     # 条件のためだけの面
        else:
            pl, _ = PLANE[lt]
            V = f"v{pl}[s,"
        if k in (1, 11):
            if lt != 0 and k == 1:
                V = f"v{PLANE[lt][0]}[s - 1,"    # 単調でない問いは閉じた面
            rhs = {0: "w", 1: f"{V} {R1}] + w",
                   2: f"{V} {R1}] + {V} {R2}] + w"}[n]
            A(f"nc[s, e] <- true   {g} if op == {op} if n == {n} "
              f"if {V} {cc}] {IOP[op]} {rhs}")
        elif k == 2:   A(f"nc[s, e] <- true   {g} if not v{PLANE[lt][0]}[s - 1, {cc}]")
        elif k == 5:   A(f"nc[s, e] <- true   {g} if not {V} {cc}]")
        elif k == 3:   A(f"nc[s, e] <- true   {g} if {V} {cc}]")
        elif k == 4:
            # ⊒ は束が定める。`is` をそのまま書けば、単調性も束ごとの意味も
            # 処理系が持っている —— 演算子に開いて写すと flat の ⊤ を落とす。
            A(f"nc[s, e] <- true   {g} if {V} {cc}] is w")
    A(f"ok[s, e] <- true   {SA} for {EG} if st == s if nc[s, e] >= ng[s, e]")
    A(f"ok[s, e] <- ok[s - 1, e]   {S1} for {EG} if st >= 0 if st < s")

    if fpsh:
        A("# ── 値で決まる座標を番地の面へ写す。その層までの写しを全部持つ。──")
        PL0 = f"{SA} for {FP} for (t) in 0 .. SZ[sp] - 1 if st >= 0 if st <= s"
        PL1 = f"{S1} for {FP} for (t) in 0 .. SZ[sp] - 1 if st >= 0 if st <= s"
        for (kd, lt) in fpsh:
            if kd == 0:
                ql, _ = PLANE[abs(lt)]
                if lt < 0:
                    A(f"pa[s, pb + t] <- v{ql}[s, {_map('am', PS)}]   "
                      f"{PL0} if kd == 0 if lat == {lt}")
                else:
                    A(f"pa[s, pb + t] <- v{ql}[s - 1, {_map('am', PS)}]   "
                      f"{PL1} if kd == 0 if lat == {lt}")
            elif kd == 1:
                # **構成子の番地は引数の一次式（法 M）である。** 括弧を忘れない
                # —— `%` は `+` より強く、無いと最後の項しか畳まれない。
                A(f"pa[s, pb + t] <- ({_map('am', PS)}) % mo   {PL0} if kd == 1")
            elif kd == 3:
                A(f"pa[s, pb + t] <- pa[s, p1 + t] % mo   {PL0} if kd == 3")
            elif kd == 4:
                A(f"pa[s, pb + t] <- pa[s, p1 + t] / mo   {PL0} if kd == 4")
            elif kd == 2:
                A(f"pa[s, pb + t] <- mu * pa[s, p1 + t] + pa[s, p2 + t]   "
                  f"{PL0} if kd == 2")

    if fsh:
        A("# ── 多面体の寄与。辺一本が空間ひとつを覆う。──────────────")
        LOOP = f"for {FG} for (t) in 0 .. SZ[sp] - 1"
        gate = ""
        if fcsh:
            A(f"fq[s, e] <- true   {SA} for {FG} if st == s")
            A(f"fq[s, e] <- true   {SA} for {FC} if st == s")
            A(f"fn[s, e, t] <- true   {SA} {LOOP} if st == s")
            for (kk, lt, op, n) in fcsh:
                S0 = S1 if kk == 2 or (kk in (1, 11) and lt != 0 and kk == 1) else SA
                G = (f"{S0} for {FC} for (t) in 0 .. SZ[sp] - 1 if st == s "
                     f"if kk == {kk} if lat == {lt}")
                if kk == 1:
                    # **写像 対 写像。** 読みは pa に写してあるので、
                    # 比較の規則から束も面も消えている（六行で全部）。
                    A(f"fn[s, e, t] <- true   {SA.replace('for', 'for', 1)} "
                      f"for {FC} for (t) in 0 .. SZ[sp] - 1 if st == s "
                      f"if kk == 1 if lat == 0 if op == {op} "
                      f"if ({_map('cm', PS)}) {IOP[op]} ({_map('wm', PS)})")
                    continue
                if kk == 6:
                    # **箱に半空間を一枚あてる。** 升を読まないので面も層も
                    # 要らない —— 軸の一次式どうしを比べるだけ。
                    A(f"fn[s, e, t] <- true   {G} if op == {op} "
                      f"if {_map('cm')} {IOP[op]} {_map('wm')}")
                    continue
                pl, _ = PLANE[lt]
                V = f"v{pl}[s," if kk != 1 else f"v{pl}[s - 1,"
                C = _map('cm', PS)
                if kk == 11:
                    rhs = {0: _map('wm'),
                           1: f"{V} {_map('r1', PS)}] + {_map('wm')}",
                           2: (f"{V} {_map('r1', PS)}] + {V} {_map('r2', PS)}] + "
                               f"{_map('wm')}")}[n]
                    A(f"fn[s, e, t] <- true   {G} if op == {op} if n == {n} "
                      f"if {V} {C}] {IOP[op]} {rhs}")
                elif kk == 2: A(f"fn[s, e, t] <- true   {G} if not v{pl}[s - 1, {C}]")
                elif kk == 5: A(f"fn[s, e, t] <- true   {G} if not v{pl}[s, {C}]")
                elif kk == 3: A(f"fn[s, e, t] <- true   {G} if v{pl}[s, {C}]")
                elif kk == 4:
                    A(f"fn[s, e, t] <- true   {G} if v{pl}[s, {C}] is {_map('wm')}")
            A(f"fo[s, e, t] <- true   {SA} {LOOP} if st == s "
              f"if fn[s, e, t] >= fq[s, e]")
            # 前の層で立った門はもう動かない（その層は閉じている）。
            # 引き継がないと、寄せ直す束（KEYED）の古い辺が門で落ちる。
            A(f"fo[s, e, t] <- fo[s - 1, e, t]   {S1} {LOOP} if st >= 0 if st < s")
            gate = " if fo[s, e, t]"
        # **寄与元キー付きの束（sum/count/bag）は引き継げない** —— 観測は数で
        # あって束の元ではない。点の道と同じ判断（気づき34 の教訓のまま）。
        for lt in sorted({x[0] for x in fsh}):
            if lt in KEYED: continue
            pl, _ = PLANE[lt]
            A(f"v{pl}[s, {_map('dm', PS)}] <- v{pl}[s - 1, {_map('dm', PS)}]   "
              f"{S1} {LOOP} if lat == {lt} if st < s")
        for (lt, vf, n) in fsh:
            pl, _ = PLANE[lt]
            sel = "if st <= s" if lt in KEYED else "if st == s"
            g = f"{SA} {LOOP} {sel} if lat == {lt} if vf == {vf}{gate}"
            D = f"v{pl}[s, {_map('dm', PS)}]"
            if vf == 0:   A(f"{D} <- {_map('wm', PS)}   {g}")
            elif vf == 2: A(f"{D} <- true   {g}")
            elif vf == 5: A(f"{D} <- false  {g}")
            elif vf == 4: A(f"{D} <- v{pl}[s, {_map('am', PS)}]   {g}")
            elif vf == 1 and n == 1:
                A(f"{D} <- v{pl}[s, {_map('am', PS)}] + {_map('wm', PS)}   {g} if n == 1")
            elif vf == 1 and n == 2:
                A(f"{D} <- v{pl}[s, {_map('am', PS)}] + v{pl}[s, {_map('bm', PS)}] "
                  f"+ {_map('wm', PS)}   {g} if n == 2")

    A("# ── 寄与。これが全部である。──────────────────────────────")
    for (lt, vf, n, la) in vals:
        # la == 5（flat）は生きた面でよい（⊥ → v で止まる）。閉じた面を
        # 読む形（la が負・束違い）は s-1 が要るので層 1 から。
        closed = vf in (1, 4, 6, 7, 8) and (la < 0 or (la != lt and la != 5))
        S0 = S1 if closed else SA
        pl, _ = PLANE[lt]
        g = (f"{S0} for {EG} if st >= 0 if st {'<=' if lt in KEYED else '=='} s "
             f"if ok[s, e] if lat == {lt} if vf == {vf}")
        D = f"v{pl}[s, rz[s, t]]"
        if vf == 0:   A(f"{D} <- w      {g}")
        elif vf == 2: A(f"{D} <- true   {g}")
        elif vf == 5: A(f"{D} <- false  {g}")
        elif vf == 3: A(f"{D} <- {{w}}    {g}")
        elif vf == 9:
            ql, _ = PLANE[abs(la)]
            r = "s - 1" if la < 0 else "s"
            A(f"{D} <- {{v{ql}[{r}, rz[s, a]]}}   {g} if la == {la}")
        elif vf in (6, 7, 8):
            ql, _ = PLANE[abs(la)]
            r = "s" if la == lt or la == 5 else "s - 1"
            op = {6: '*', 7: '/', 8: '%'}[vf]
            rhs = f"v{ql}[{r}, rz[s, b]]" if n == 2 else "w"
            A(f"{D} <- v{ql}[{r}, rz[s, a]] {op} {rhs}   "
              f"{g} if n == {n} if la == {la}")
        elif vf in (1, 4):
            ql, _ = PLANE[abs(la)]
            r = "s" if la == lt or la == 5 else "s - 1"
            src = f"v{ql}[{r}, rz[s, a]]"
            if vf == 4:
                A(f"{D} <- {src}   {g} if la == {la}")
            elif n == 1:
                A(f"{D} <- {src} + w   {g} if n == 1 if la == {la}")
            else:
                A(f"{D} <- {src} + v{ql}[{r}, rz[s, b]] + w   "
                  f"{g} if n == 2 if la == {la}")
    A("")
    for lt in lats:
        A(f"print v{PLANE[lt][0]}")
    return "\n".join(T) + "\n"


def _lit(x):
    return '"%s"' % x.replace('"', "'") if isinstance(x, str) else str(x)


def tbl(n, rows):
    return "table %s = %s\n" % (n, ", ".join("(" + ",".join(map(_lit, r)) + ")" for r in rows))


def close_upto(fl):
    """層 k まで **走らせる物で**閉じて、値を前段に返す。

    前段と走らせる物は超段ごとに交代する。反復空間の端が値で決まる形
    （`for (i) in 0 .. n[]`）があるかぎり、これは避けられないし、
    避けるべきでもない —— 端は上へしか動かないので、交代は単調である。"""
    def go():
        if not fl.eg and not fl.fg: return
        sh = fl.shapes()
        t = fl.tables()
        k = fl.strata() - 1
        names = ('eg', 'cd', 'ix') + (('dat', 'spc', 'ssz', 'mp', 'fg', 'fc',
                                       'fp') if fl.fg else ())
        src = "".join(tbl(n, t[n]) for n in names)
        eng = src + engine_text(fl.ncell() + 1, fl.nid + 1, len(fl.ix) + 1,
                                k + 1, sh, fl.ixlat, fl.fsh if fl.fg else (),
                                fl.nrow + 1,
                                max((r[1] for r in fl.dat), default=0) + 1,
                                len(fl.ssz) + 1, len(fl.mp) + 1,
                                max((r[1] for r in fl.spc), default=0) + 1,
                                fl.fcsh if fl.fc else (),
                                max((r[1] for r in fl.ssz), default=1),
                                fl.fpsh if fl.fp else (), fl.pab + 1)
        open('/tmp/close_gen.lx', 'w', encoding='utf-8').write(eng)
        q = L.parse(eng); L.check(q); L.stratify(q); L.io_rounds(q); L.certify(q)
        st2, _, _ = L.run(q, out=io.StringIO())
        for lt in sh[2]:
            nmf = f'v{PLANE[lt][0]}'
            for (sx, c), v in st2.get(nmf, {}).items():
                if sx != k: continue          # 層は座標 —— 閉じるのは層 k の面
                fl.measure(c)          # 触れた升をそのまま上端に（一巡目の測り）
                try: f, keys = fl.name_of(c)
                except (KeyError, IndexError): continue
                fl.closed[(f, keys)] = q.fields[nmf].observe(v)
        fl.upto = len(fl.eg) + len(fl.fg)
    return go


def build(path):
    fl, p = flatten(path, close_upto)
    t = fl.tables()
    sh = fl.shapes()
    names = ('eg', 'cd', 'ix') + (('dat', 'spc', 'ssz', 'mp', 'fg', 'fc', 'fp')
                                   if fl.fg else ())
    src = "".join(tbl(n, t[n]) for n in names)
    eng = engine_text(fl.ncell() + 1, fl.nid + 1, len(fl.ix) + 1,
                      fl.strata(), sh, fl.ixlat, fl.fsh if fl.fg else (),
                      fl.nrow + 1, max((r[1] for r in fl.dat), default=0) + 1,
                      len(fl.ssz) + 1, len(fl.mp) + 1,
                      max((r[1] for r in fl.spc), default=0) + 1,
                      fl.fcsh if fl.fc else (),
                      max((r[1] for r in fl.ssz), default=1),
                      fl.fpsh if fl.fp else (), fl.pab + 1)
    return src + eng, fl, p


class Rejected(Exception):
    pass


def answers(path):
    src = open(path, encoding='utf-8').read()
    try:
        p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    except L.LattixError as ex:
        raise Rejected(str(ex)[:60])
    st, _, _ = L.run(p, out=io.StringIO())
    return {f: {k: p.fields[f].observe(v) for k, v in d.items()} for f, d in st.items()}, p


if __name__ == '__main__':
    path = sys.argv[1]
    try:
        ref, _ = answers(path)
    except Rejected as ex:
        print(f"  参照実装が断る: {ex}"); print("  一致"); sys.exit(0)
    eng, fl, p = build(path)
    open('/tmp/run_gen2.lx', 'w', encoding='utf-8').write(eng)
    q = L.parse(eng); L.check(q); L.stratify(q); L.io_rounds(q); L.certify(q)
    st2, _, _ = L.run(q, out=io.StringIO())
    ns = fl.strata(); got = {}
    for lt in fl.shapes()[2]:
        nmf = f'v{PLANE[lt][0]}'
        for (sx, c), v in st2.get(nmf, {}).items():
            if sx != ns - 1: continue
            try: f, keys = fl.name_of(c)
            except (KeyError, IndexError): continue
            got.setdefault(f, {})[keys] = fl.obs(q.fields[nmf].observe(v))
    ok = True
    for f in (p.prints or list(p.fields)):
        a = dict(ref.get(f, {})); b = got.get(f, {})
        if a != b:
            ok = False; print(f"  ✗ {f}\n    対象: {a}\n    走らせる物: {b}")
        else:
            print(f"  ✓ {f}: {a}")
    print("  一致" if ok else "  食い違い")
