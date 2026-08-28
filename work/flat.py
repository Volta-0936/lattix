# -*- coding: utf-8 -*-
"""対象 `.lx` → **寄与の関係**（升と升のあいだの辺）。

   Lattix のプログラムの実体は「規則・項・ガード」ではない ——
   **どの升がどの升から寄与を受けるか** であり、答えはその閉包である。
   どのループがどの升に触るかは宣言されているので、関係は *数え上げられる*。
   だから走らせる側は「解釈」を一つもしない。座標も一つも計算しない。

     eg の層が **負**（-1-s）なら「層 s の *条件のための項*」である。
     それは閉じた面からしか読まないので、寄与が立つかどうか（`ok`）に依存しない。
     だから否定の輪に入らない —— `ct` という別の面に住む。

     ix  (指し番号, m, 升, 束, o, 束)
            束が **負**なら「その升は生きた面（同じ層）から読む」の合図。
            内容アドレスは ⊥ → v → ⊤ としか動かないので、これが要る。
            **升を指す番号**。辺も条件も、升を直接には持たない。
              m = 0 なら「そのまま o 番の升」    —— 地上で決まる升
              m ≠ 0 なら「m × v[ic 番の升] + o」—— 値で決まる升
                        （ic は *升の番号*。地上で決まっていなければならない）
            走らせる側は `rz[指し番号]` と書くだけでよく、
            **直接と間接の場合分けが一つも要らない**。
     eg  (辺, 層, 束, 先, 形, 数, a, la, b, w)
            la が **負**なら「源は閉じた面（層 s-1）から読む」の合図。
            形 0  値そのもの（列 w：数・文字列・構成子の番地）
            形 1  Σ源 + w        （算術）
            形 2  true
            形 3  {w}            （集合の一元）
            形 4  源の写し       v[先] <- v[a]
            形 5  false
            形 6  v[a] * w   形 7  v[a] / w   形 8  v[a] % w   形 9  {v[a]}
                  —— 掛け・割り・剰余は **中間の升に開く**。
                  一つの寄与を辺の連なりにするので、走らせる側は
                  「三項の式」を知らなくてよい。中間の升は同じ束に置く。
     cd  (辺, 層, 種, 束, 升, 演算子, 数, r1, r2, w)   辺が生きる条件
            種 1 は **閉じた面**（層 s-1）を見る。ただし問いが単調なら ——
            比べる場が同じ層で書かれているなら —— 生きた面でよい。層は
            単調でない問いのためだけに在る。種 5 は Belnap の否定（単調）。
            **条件も辺と同じ形をしている** —— 左の升と、右の Σ升+w を比べる。
            種 1  v[升] ⋈ v[r1] + v[r2] + w  …… 閉じた面 s-1
            種 2  not f[升]                  …… 閉じた面 s-1
            種 3  f[升]                      …… 生きた面 s（単調な再帰の一部）
            種 4  f[升] is w                 …… 生きた面 s（⊒ はどの束でも単調）

   **升は番号である。** 場と座標の組をここで一つの番号に写しておく。
   走らせる側は場を知らない。だから面は一次元で、規則は数えるほどしかない。
"""
import sys, os, itertools
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lattix as L

LAT = {'min': 1, 'max': 2, 'or': 3, 'and': 4, 'flat': 5, 'fourv': 6,
       'set': 7, 'sum': 8, 'count': 9, 'bag': 10}
PLANE = {1: ('n', 'min'), 2: ('x', 'max'), 3: ('o', 'or'), 4: ('a', 'and'),
         5: ('f', 'flat'), 6: ('4', 'fourv'), 7: ('s', 'set'),
         8: ('m', 'sum'), 9: ('c', 'count'), 10: ('b', 'bag')}
ARITH = (1, 2, 5, 6, 8, 10)         # 値が数として足せる束
FAMILY = True     # 多面体の道（反復空間を点に潰さずに渡す）
ARITH_MAX = 1 << 24   # 一軸の広さがこれを超えたら、密には並べない
ARITH_SPACE = 1 << 32 # 場ぜんたいの広さの上限（同上）
FAMILY_MIN = 512  # **この言語の最適化は「証明」ではなく「選択」である**（CLAUDE.md）。
                  # 小さい空間は点に展開したほうが速い（層の数だけ寄せ直すから）。
                  # 大きい空間だけ、多面体のまま渡す —— 表が爆発するのはそこだけ。
PAD = 64          # 座標は ℤ にある。負の側の余白。
ATOMB0 = 1 << 62  # 一巡目の原子の置き場（**測るための仮の上**）。
                  # 二巡目では「数えたものをそのまま上端にする」（CLAUDE.md）。
OP  = {'==': 1, '!=': 2, '>=': 3, '<=': 4, '>': 5, '<': 6}


class _NoFam(Exception):
    """多面体（空間と写像）では書けない —— 理由を一つ持つ。

    **断る口は一つにする。** 前は途中の `return False` が七つあり、そのうち
    二つ（源が密でない・原子を値にした）は既に作った番地の写し `fp` と枠 `pab`
    を戻さずに帰っていた。戻さないと、点に展開した規則のために番地の面が
    育ち続ける —— 誰も読まない升を毎周まわすことになる。
    同じ判断（作りかけを捨てる）を七箇所に書けば、直るのは一箇所である
    （気づき34）。"""

    def __init__(self, why):
        super().__init__(why); self.why = why


class Flatten:
    def __init__(self, prog, extent=None, atomb=None):
        self.p = prog
        self.flat = {}
        for f, lt in prog.fields.items():
            if lt.name not in LAT:
                raise NotImplementedError(f"束 `{lt.name}` はまだ")
            self.flat[f] = LAT[lt.name]
        self.fstr = {}                      # 場 → 書かれる層（最大）
        for r in prog.rules:
            st = getattr(r, 'stratum', 0) or 0
            self.fstr[r.target] = max(self.fstr.get(r.target, 0), st)
        self.cid = {}                       # (場, 座標) → 升番号
        self.rev = []                       # 升番号 → (場, 座標)
        self.eg, self.cd, self.ix = [], [], []
        self.ref = {}                       # (m, ic, il, o, dl) → 指し番号
        # **反復空間の端が値で決まることがある**（`for (i) in 0 .. n[]`）。
        # 端は上へしか動けないと宣言されている（`classify(…,'UP')`）ので、
        # その場は必ず前の層で閉じている。だから前段と走らせる物は
        # **超段ごとに交代する** —— これは BSP の構造そのものである。
        self.closer = None                  # 層 k まで閉じる（engine2 が入れる）
        self.closed = {}                    # (場, 座標) → 閉じた値
        self.upto = -1                      # どこまで（辺の数）閉じてあるか
        self.ntmp = 0                       # 中間の升の数
        self.nid = 0                        # 辺の通し番号（中間の辺も同じ列に並ぶ）
        self.atn, self.atl = {}, []         # 原子 → 番号 / 番号 → 原子
        self.gvhit = False                  # 区間の端が場の読みだったか
        self.noclose = False                # 閉じ直さずに読む（層ごとに一度）
        self.gst = -1                       # どの層で閉じたか
        # ── 多面体の道 —— **反復空間を点に潰さずに渡す** ────────────────
        # 「宣言されているものを、そのまま機械に渡すには？」（CLAUDE.md）
        # 規則が「表と区間の直積を回り、座標が軸の一次式で書ける」形なら、
        # 点に展開せず、空間と写像のまま渡す。辺の数が規則の数に戻る。
        self.dat, self.reg, self.rng = [], {}, {}   # 軸の中身と、列ごとの上下
        self.atomcol = set()                # 原子が入っている列（値には使えない）
        self.nrow = 1                       # 行 0 は「ゼロの行」（使わない枠用）
        self.spc, self.spn, self.ssz = [], {}, []
        self.mp, self.mpn = [], {}
        self.fg = []
        self.nofam = []                     # 断った規則と、その理由（数えるため）
        self.fc = []                        # 多面体のガード（辺ごと）
        self.fp = []                        # 番地の面への写し（間接の座標）
        self.pab = 1                        # 番地の面の次の枠（0 は番兵）
        # **値から決まる座標を持つ場は、番号が算術でなければならない。**
        #
        # 広さは `bound` が宣言している。書いていないときは —— **測る**。
        # 「上限を大きく書くのは、上限を測らないことの言い換えである」（CLAUDE.md）。
        # だから一巡目は仮の広さで数え上げ、そこで **実際に使われた座標**を
        # 記録し、二巡目でその測った値をそのまま上端にする。
        # 構成子の番地を座標にする場は測っても大きい —— それは content address が
        # そう宣言しているのであって、こちらが大きく書いたのではない。
        # **升の番号づけは一つでよい。** 値で決まる座標を持つ場だけを算術に
        # していたが、測るようにした以上、全部を算術で並べても広さは締まる。
        # （原子も構成子の番地も、番号として同じ段に載る。）
        need = _needs_arith(prog)           # 値で決まる座標を持つ場（算術が要る）
        if extent is None:
            self.ar = set(prog.fields)      # 一巡目は全部を仮の算術で測る
        else:
            # **表現は測った広さが決める。** 密に並べられる場は算術に、
            # 内容アドレスで番地が飛ぶ場は内容で名づける（＝hash 表の側）。
            self.ar = set(need)
            for f in prog.fields:
                if f in need or f in prog.field_bound: self.ar.add(f); continue
                w, ok = 1, True
                for i in range(_arity(prog, f)):
                    a, z = extent.get((f, i), (0, 0))
                    if z - a + 1 > ARITH_MAX: ok = False; break
                    w *= z - a + 1
                if ok and w <= ARITH_SPACE: self.ar.add(f)
        self.atn, self.atl = {}, []
        for a in _allatoms(prog):           # **綴りの順**に番号を配る
            self.atn[a] = len(self.atl); self.atl.append(a)
        self.seen = {}                      # (場, 軸) → (下, 上)  ← 測った値
        self.ATOMB = ATOMB0 if atomb is None else atomb
        self.lay, self.nk, base = {}, {}, 0
        for f in sorted(self.ar):
            ar = _arity(prog, f); self.nk[f] = ar
            b = prog.field_bound.get(f)
            sz, lo = [], []
            for i in range(ar):
                if b is not None:
                    w = (b[i] if isinstance(b, tuple) and i < len(b)
                         else (b if not isinstance(b, tuple) else b[-1]))
                    lo.append(-PAD); sz.append(w + PAD)
                elif extent is not None and (f, i) in extent:
                    a, z = extent[(f, i)]        # 数えたものをそのまま上端に
                    lo.append(a); sz.append(z - a + 1)
                elif extent is not None:
                    lo.append(0); sz.append(1)   # 一度も使われなかった軸
                else:
                    lo.append(-PAD); sz.append(ATOMB0 * 2)   # 一巡目の仮
            sz = sz or [1]; lo = lo or [0]
            st, n = [], 1
            for x in reversed(sz): st.insert(0, n); n *= x
            self.lay[f] = (base, sz, st, lo); base += n
        self.nbase = base

    # ── 多面体: 軸の中身 / 空間 / 写像 ───────────────────────────────
    def region(self, src, st=0):
        """軸の中身を `dat` の連続した行に置く。**区間も表も同じ形**にする ——
        走らせる側に「表の列か計数器か」の場合分けを作らないため。

        区間の端は **閉じた層の値でよい**（`for (i) in 0 .. n[]`）。端は上へしか
        動けないと宣言されているので、前の層で必ず閉じている —— `bindings` が
        点に展開するときに使っているのと同じ `gval` を、ここでも使う。
        これが無いと「端が場の読み」の規則は一本残らず点に潰れていた。"""
        key = src if isinstance(src, str) else repr(src)
        if key in self.reg: return self.reg[key]
        if isinstance(src, str):
            rows = self.p.tables[src]
            nc = max((len(r) for r in rows), default=1)
            base = self.nrow
            for i, row in enumerate(rows):
                for c in range(nc):
                    v = row[c] if c < len(row) else 0
                    if isinstance(v, int) and not isinstance(v, bool):
                        self.dat.append((base + i, c, v))
                    else:
                        # 原子は **番号**で置く。座標には使えるが、値には使えない
                        # （値として渡すと答えが番号になってしまう）。
                        self.atomcol.add((base, c))
                        self.dat.append((base + i, c, self.atom(v)))
            self.nrow += len(rows)
            self.reg[key] = (base, len(rows), nc)
            for c in range(nc):
                xs = [self.dat[k][2] for k in range(len(self.dat) - len(rows) * nc,
                                                   len(self.dat)) if self.dat[k][1] == c]
                self.rng[(base, c)] = (min(xs), max(xs)) if xs else (0, 0)
        else:
            lo, hi = self.gval(src[1], st, {}), self.gval(src[2], st, {})
            if not isinstance(lo, int) or not isinstance(hi, int):
                raise NotImplementedError("多面体にできない区間")
            if hi - lo + 1 > (1 << 20):
                raise NotImplementedError("多面体にできない区間")
            base = self.nrow
            for i in range(hi - lo + 1):
                self.dat.append((base + i, 0, lo + i))
            self.nrow += hi - lo + 1
            self.reg[key] = (base, hi - lo + 1, 1)
            self.rng[(base, 0)] = (lo, hi)
        return self.reg[key]

    def space(self, r, st=0):
        """反復空間 = 軸の直積。点 t から x_j = (t / 歩幅_j) mod 幅_j。"""
        axes = []
        for vs, src in r.sources:
            if isinstance(src, tuple) and src[0] != '..':
                raise NotImplementedError("多面体にできない源")
            axes.append(self.region(src, st))
        key = tuple((b, w) for b, w, _c in axes)
        if key in self.spn: return self.spn[key], axes
        sp = len(self.spn); self.spn[key] = sp
        stp, n = [], 1
        for _b, w, _c in reversed(axes): stp.insert(0, n); n *= w
        for j, (b, w, _c) in enumerate(axes):
            self.spc.append((sp, j, b, w, stp[j]))
        self.ssz.append((sp, n))
        return sp, axes

    def slots(self, r):
        """変数 → (軸, 列)。"""
        out = {}
        for j, (vs, _src) in enumerate(r.sources):
            for c, v in enumerate(vs): out[v] = (j, c)
        return out

    def affine(self, e, sl, env=None):
        """式 → (定数, [(軸, 列, 係数)])。一次でなければ断る。"""
        k = e[0]
        if k == 'int': return e[1], []
        if k == 'var':
            if e[1] not in sl: raise NotImplementedError("軸に無い変数")
            j, c = sl[e[1]]; return 0, [(j, c, 1)]
        if k == 'bin' and e[1] in '+-':
            c1, s1 = self.affine(e[2], sl); c2, s2 = self.affine(e[3], sl)
            if e[1] == '-':
                c2 = -c2; s2 = [(j, c, -m) for j, c, m in s2]
            return c1 + c2, s1 + s2
        if k == 'bin' and e[1] == '*':
            for a, b in ((e[2], e[3]), (e[3], e[2])):
                g = self.val(b, {})
                if isinstance(g, int) and not isinstance(g, bool):
                    c1, s1 = self.affine(a, sl)
                    return c1 * g, [(j, c, m * g) for j, c, m in s1]
        raise NotImplementedError(f"一次式でない: {e}")

    def mapof(self, const, slots, axes, ind=(0, 0, 0)):
        """写像を一つ登録する。枠は三つまで（余りはゼロの行を指す）。

        `ind = (係数, 番地面の基, 使うか)` は **値で決まる座標**の項である ——
            値 = 定数 + Σ 係数·軸 + 係数_i · pa[基 + 使うか × 点]
        使わないときは (0, 0, 0) で、`pa[0] = 0` を読んで 0 を足す。
        場合分けを作らないために、番兵の升を一つ置いてある（`pa[0]`）。"""
        if len(slots) > 3: raise NotImplementedError("枠が三つを超える")
        row = [const]
        for j, c, m in slots: row += [j, c, m]
        while len(row) < 10: row += [0, 0, 0]
        row += list(ind)
        key = tuple(row)
        if key in self.mpn: return self.mpn[key]
        x = len(self.mp); self.mpn[key] = x
        self.mp.append(tuple([x] + row))
        return x

    # ── 値で決まる座標を、多面体のまま渡す ──────────────────────────
    # `f[g[i]]` の `g[i]` は点ごとに違う値だが、**その値の置き場もまた空間**
    # である（点 t につき一升）。だから番地の面 `pa` に一枚写しておけば、
    # 写像は「定数 + Σ 係数·軸 + 係数·pa[基 + t]」の一次式のままでいられる。
    # 深い入れ子は、この写しを重ねるだけで届く（`pa` を `pa` から作る）。
    def pslot(self, n):
        """番地の面に、点 n 個ぶんの枠を一つ取る（基は 1 以上 —— 0 は番兵）。"""
        b = self.pab; self.pab += max(1, n); return b

    def pcell(self, e, sl, axes, st, sp, npt):
        """座標の式 → (定数, 軸の枠, 間接の項)。一次に収まらない読みは
        `pa` に写して一次に戻す。**間接の項は一つまで**（写像が一行だから）。"""
        try:
            c, ss = self.affine(e, sl)
            return c, ss, (0, 0, 0)
        except NotImplementedError:
            pass
        # `A + m·g[…]` の形に分ける（`g[…]` はちょうど一つ）
        fl = list(_tops(e))
        if len(fl) != 1 or not _addok(e):
            raise NotImplementedError(f"多面体にできない座標: {e}")
        g = fl[0]
        c, ss = self.affine(_strip(e, [g]), sl)
        m = _coef(e, g)
        am = self.pmapcell(g[1], g[2], sl, axes, st, sp, npt)
        lt = self.flat[g[1]]
        if self.fstr.get(g[1], 0) >= st:
            # まだ閉じていない場を番地にできるのは、⊥ → v で止まる升だけ
            if lt != 5:
                raise NotImplementedError(f"`{g[1]}` は同じ層で育つので番地にできない")
            lt = -lt                      # 生きた面から読む合図（`ix` と同じ）
        b = self.pslot(npt)
        self.fp.append((self.newid(), sp, st, lt, b, am))
        return c, ss, (m, b, 1)

    def pmapcell(self, f, kexprs, sl, axes, st, sp, npt):
        """場 f の升を指す **写像**。座標が値で決まっていてもよい。"""
        base, sz, stp, lo = self.lay[f]
        const, slots, ind = base, [], (0, 0, 0)
        for i, ke in enumerate(kexprs):
            c, ss, iv = self.pcell(ke, sl, axes, st, sp, npt)
            if iv[2]:
                if ind[2]:
                    raise NotImplementedError("一つの写像に間接の項が二つ")
                ind = (iv[0] * stp[i], iv[1], 1)
            a = z = c
            for j, col, m in ss:
                b0, _w, _nc = axes[j]
                x0, x1 = self.rng.get((b0, col), (0, 0))
                a += m * x0 if m > 0 else m * x1
                z += m * x1 if m > 0 else m * x0
            if not iv[2]:
                q0, q1 = self.seen.get((f, i), (a, z))
                self.seen[(f, i)] = (min(q0, a), max(q1, z))
            const += (c - lo[i]) * stp[i]
            slots += [(j, col, m * stp[i]) for j, col, m in ss]
        return self.mapof(const, slots, axes, ind)

    # ── 多面体のガード —— 条件も **写像**で書ける ────────────────────
    def fcond(self, q, sl, axes, st, sp, npt):
        """ガード一本を `fc` の一行にする。できなければ断る（NotImplementedError）。

        `cd` との違いは升の番号を写像で持つことだけである —— 種も演算子も同じ。
        「宣言されているものを、そのまま機械に渡すには？」（CLAUDE.md）"""
        zero = self.mapof(0, [], axes)
        if q[0] == 'cmp':
            op, a, b = q[1], q[2], q[3]
            if a[0] != 'fref':
                if b[0] != 'fref':
                    raise NotImplementedError("多面体のガード: 両辺が升でない")
                op, a, b = self.FLIP[op], b, a
            fl = [a[1]] + [x[1] for x in _frefs(b)]
            lt = self.flat[a[1]]
            if any(self.flat[f] != lt for f in fl):
                raise NotImplementedError("多面体のガードで束が混ざる")
            if not _addok(b):
                raise NotImplementedError("多面体のガードの右辺")
            rb = list(_frefs(b))
            if len(rb) > 2:
                raise NotImplementedError("多面体のガードの右辺が三つ以上の升")
            k = 1 if all(self.fstr.get(f, -1) >= st for f in fl) else 0
            if k and lt in (8, 9, 10): k = 0
            if not k and st == 0:
                raise NotImplementedError("層 0 で閉じた値を問うている")
            cm = self.pmapcell(a[1], a[2], sl, axes, st, sp, npt)
            rm = [self.pmapcell(x[1], x[2], sl, axes, st, sp, npt)
                  for x in rb] + [zero, zero]
            c, ss = self.affine(_strip(b, rb), sl)
            return (sp, st, 1 + 10 * k, lt, cm, OP[op], len(rb),
                    rm[0], rm[1], self.mapof(c, ss, axes))
        if q[0] == 'geq' and q[1][0] == 'fref':
            bv = self.val(q[2], {})
            if not isinstance(bv, int) or isinstance(bv, bool):
                raise NotImplementedError("多面体の `is` の右辺")
            return (sp, st, 4, self.flat[q[1][1]],
                    self.pmapcell(q[1][1], q[1][2], sl, axes, st, sp, npt), 0, 0,
                    zero, zero, self.mapof(bv, [], axes))
        if q[0] == 'bnot' and q[1][0] == 'fref':
            e = q[1]
            return (sp, st, 5, self.flat[e[1]],
                    self.pmapcell(e[1], e[2], sl, axes, st, sp, npt),
                    0, 0, zero, zero, zero)
        if q[0] == 'not' and q[1][0] == 'fref':
            e = q[1]
            if st == 0: raise NotImplementedError("層 0 で否定を問うている")
            return (sp, st, 2, self.flat[e[1]],
                    self.pmapcell(e[1], e[2], sl, axes, st, sp, npt),
                    0, 0, zero, zero, zero)
        if q[0] == 'fref':
            return (sp, st, 3, self.flat[q[1]],
                    self.pmapcell(q[1], q[2], sl, axes, st, sp, npt),
                    0, 0, zero, zero, zero)
        raise NotImplementedError(f"多面体のガードの形: {q}")

    def family(self, r, st, lat):
        """規則を **空間と写像のまま**渡せるならそうする。できなければ False。

        断る口はここ一つである。作りかけの番地の写し（`fp`）と枠（`pab`）は
        必ず戻す。断った理由は数えられる形で残す（`nofam`）—— 広げる前に
        数えるため（PLAN §5-6）。`mp` / `spc` は鍵で共有される溜めなので
        戻さない（同じ写像を次の規則が引き当てる）。"""
        fp0, pab0 = list(self.fp), self.pab
        try:
            return self._family(r, st, lat)
        except _NoFam as ex:
            why = ex.why
        except NotImplementedError as ex:
            why = str(ex) or 'NotImplementedError'
        except KeyError as ex:
            why = f'KeyError {ex}'
        self.fp[:] = fp0; self.pab = pab0
        self.nofam.append((why, r.target, getattr(r, 'id', -1), st))
        return False

    def _family(self, r, st, lat):
        if not r.sources: raise _NoFam('源が無い')
        if r.target not in self.lay: raise _NoFam('書き先が密でない')
        e = r.value
        if e[0] == 'bool':
            vf, srcs = (2 if e[1] else 5), []
        elif e[0] == 'fref':
            vf, srcs = 4, [e]
        else:
            vf, srcs = None, []
            fl = [x for x in _frefs(e)]
            if fl and lat not in ARITH: raise _NoFam('数でない束に読みがある')
            if not _addok(e): raise _NoFam('値が足し算の形でない')
            vf = 1 if fl else 0
            srcs = fl
        if len(srcs) > 2: raise _NoFam('読みが三つ以上')
        if any(self.flat[x[1]] != lat for x in srcs): raise _NoFam('読みで束が混ざる')
        sp, axes = self.space(r, st)
        n = 1
        for _b, w, _c in axes: n *= w
        # **これは断りではなく選択である**（小さい空間は点に展開したほうが速い）。
        # 数えるときに、書けない物と混ぜてはいけない。
        if n < FAMILY_MIN: raise _NoFam('※空間が小さい（選択）')
        sl = self.slots(r)
        if any(x[1] not in self.lay for x in srcs): raise _NoFam('読む場が密でない')
        dm = self.pmapcell(r.target, r.keys, sl, axes, st, sp, n)
        am = bm = self.mapof(0, [], axes)
        if srcs:
            am = self.pmapcell(srcs[0][1], srcs[0][2], sl, axes, st, sp, n)
            if len(srcs) == 2:
                bm = self.pmapcell(srcs[1][1], srcs[1][2], sl, axes, st, sp, n)
        if vf in (0, 1):
            rest = _strip(e, srcs)
            c, ss = self.affine(rest, sl)
            for j, col, _m in ss:
                if (axes[j][0], col) in self.atomcol:
                    raise _NoFam('原子を値にしている')
            wm = self.mapof(c, ss, axes)
        else:
            wm = self.mapof(0, [], axes)
        # **ガードも写像で書ける。** 「全部立った」は (辺, 点) で数える ——
        # 升の数は変わらないが、表が規則の数に戻る（PLAN 6.8-2）。
        fcr = [self.fcond(q, sl, axes, st, sp, n) for q in r.guards]
        eid = self.newid()
        self.fg.append((eid, sp, st, lat, vf, len(srcs), dm, am, bm, wm))
        for row in fcr:
            self.fc.append((eid,) + row)
        return True

    # ── 升の番号づけ ─────────────────────────────────────────────────
    def cell(self, f, keys):
        if f in self.lay:
            return self.at(f, keys)
        k = (f, tuple(keys))
        c = self.cid.get(k)
        if c is None:
            c = self.nbase + len(self.rev); self.cid[k] = c; self.rev.append(k)
        return c

    def at(self, f, keys):
        """算術の番号 —— 基点 + Σ (座標 − 下端) × 歩幅。

        広さは宣言が言う。宣言が無ければ、一巡目に **測った**値が言う。"""
        base, sz, st, lo = self.lay[f]
        n = base
        for i, k in enumerate(keys):
            if not isinstance(k, int) or isinstance(k, bool):
                k = self.atom(k)          # 原子も番号である。上の段に置くだけ
            a, z = self.seen.get((f, i), (k, k))
            self.seen[(f, i)] = (min(a, k), max(z, k))
            k -= lo[i]
            if k < 0:
                raise NotImplementedError(f"`{f}` の座標が余白 {PAD} より小さい")
            if k >= sz[i]:
                raise NotImplementedError(f"`{f}` の座標 {k} が宣言された広さ {sz[i]} の外 —— "
                                          f"`field {f} : … bound …` を広げてくれ")
            n += k * st[i]
        return n

    def q(self, m, ic, il, o, dl):
        """升を指す番号を一つ作る（同じ指し方は同じ番号）。"""
        k = (m, ic, il, o, dl)
        x = self.ref.get(k)
        if x is None:
            x = len(self.ix); self.ref[k] = x
            self.ix.append((x, m, ic, il, o, dl))
        return x

    def axes(self, c):
        """升番号 → (場, 生の座標)。**測る**ためだけに使う（原子は番号のまま）。"""
        if c >= self.nbase: return None, ()
        for f, (base, sz, st, lo) in self.lay.items():
            n = 1
            for x in sz: n *= x
            if base <= c < base + n:
                k, r = [], c - base
                for i, s in enumerate(st):
                    k.append(r // s + lo[i]); r %= s
                return f, k
        return None, ()

    def measure(self, c):
        """走らせて **実際に触れた升**を、そのまま上端にする（CLAUDE.md）。"""
        f, k = self.axes(c)
        if f is None: return
        for i, x in enumerate(k):
            a, z = self.seen.get((f, i), (x, x))
            self.seen[(f, i)] = (min(a, x), max(z, x))

    def name_of(self, c):
        """升番号 → (場, 座標)。答えを見せるときに要る。"""
        if c >= self.nbase:
            return self.rev[c - self.nbase]
        for f, (base, sz, st, lo) in self.lay.items():
            n = 1
            for x in sz: n *= x
            if base <= c < base + n:
                k, r = [], c - base
                for i, s in enumerate(st):
                    if i >= self.nk.get(f, len(st)): break
                    x = r // s + lo[i]; r %= s
                    if x >= self.ATOMB:
                        i2 = x - self.ATOMB
                        if i2 >= len(self.atl): raise KeyError(c)
                        x = self.atl[i2]
                    k.append(x)
                return f, tuple(k)
        raise KeyError(c)

    # ── 座標の式 → **升を指す番号** ─────────────────────────────────
    def cref(self, f, kexprs, env, st=None):
        """地上で決まっても値で決まっても、返るのは指し番号ひとつである。

        軸が二つ以上あっても、読む升が **一つ**なら一次式にまとまる ——
        `out[owner[i], i - owner[i]]` は `base + st1*i + (st0-st1)*owner[i]`。
        まとまらないなら、座標そのものを **丸ごと升に作る**。作れば一次式である。
        """
        lat = self.flat[f]
        vals, terms, hard = [], [], []
        for i, k in enumerate(kexprs):
            v = self.val(k, env)
            if v is not None:
                vals.append(v); continue
            vals.append(0)
            try:
                m, c, o, lt = self.linear(k, env)
                terms.append((i, m, c, lt)); vals[-1] = o
            except NotImplementedError:
                hard.append((i, k)); terms.append(None)
        if not terms:
            return self.q(0, 0, 0, self.cell(f, vals), lat)
        if f not in self.lay:
            raise NotImplementedError(f"`{f}` の座標が値で決まるのに広さが分からない")
        if st is None:
            raise NotImplementedError("層が分からない座標")
        base, sz, stp, _lo = self.lay[f]
        good = [t for t in terms if t is not None]
        if not hard and len({t[2] for t in good}) == 1:
            off = self.at(f, vals)
            im = sum(stp[i] * m for i, m, _c, _l in good)
            _i, _m, c, lt = good[0]
            return self.q(im, c, lt, off, lat)
        # **座標そのものを一つの升に作る。** 内容アドレスも、升が二つ以上の
        # 一次式も、これで一様に扱える。作った升は ⊥ → v としか動かない。
        e = ('int', self.at(f, vals))
        for i, k in enumerate(kexprs):
            t = terms[i] if i < len(terms) else None
            if self.val(k, env) is not None: continue
            if t is not None:
                m, c, o, lt = t
                e = ('bin', '+', e, ('bin', '*', ('fref', '#c', [('int', c)]),
                                     ('int', stp[i] * m)))
            else:
                e = ('bin', '+', e, ('bin', '*', k, ('int', stp[i])))
        q, _lt = self.vexpr(e, env, 5, st)
        return self.q(1, self.cellof(q), -5, 0, lat)

    def linear(self, e, env, sign=1):
        """`m * v[升] + o` の形に分ける。升の読みはちょうど一つ。"""
        k = e[0]
        if k == 'bin' and e[1] in '+-':
            s2 = sign if e[1] == '+' else -sign
            g = self.val(e[3], env)
            if g is not None:
                m, c, o, lt = self.linear(e[2], env, sign)
                return m, c, o + s2 * g, lt
            g = self.val(e[2], env)
            if g is not None:
                m, c, o, lt = self.linear(e[3], env, s2)
                return m, c, o + sign * g, lt
            raise NotImplementedError("座標に升の読みが二つ")
        if k == 'bin' and e[1] == '*':
            g = self.val(e[3], env)
            if g is None:
                g = self.val(e[2], env); e = ('bin', '*', e[3], e[2])
            if g is None: raise NotImplementedError(f"座標の形: {e}")
            m, c, o, lt = self.linear(e[2], env, sign)
            return m * g, c, o * g, lt
        if k == 'fref':
            # 座標を決める升は **地上で分かっていなければならない** ——
            # そうでないと「番号を解く物が番号を解く物を読む」輪になる。
            keys = []
            for x in e[2]:
                v = self.val(x, env)
                if v is None:
                    raise NotImplementedError("座標の中の座標が値で決まる形はまだ")
                keys.append(v)
            return sign, self.cell(e[1], keys), 0, self.flat[e[1]]
        if k == 'ctor':
            raise NotImplementedError("座標が構成子（丸ごと升に作る）")
        raise NotImplementedError(f"座標の形: {e}")

    # ── 束縛のもとで式を地上の値に落とす（できなければ None）────────
    def val(self, e, env):
        k = e[0]
        if k == 'int':  return e[1]
        if k == 'str':  return e[1]
        if k == 'bool': return e[1]
        if k == 'var':  return env[e[1]]
        if k == 'ctor':
            vs = [self.val(x, env) for x in e[2]]
            if any(v is None for v in vs): return None
            return L.ctor_id(e[1], tuple(vs))
        if k == 'fn':
            a, b = self.val(e[2], env), self.val(e[3], env)
            if a is None or b is None: return None
            return min(a, b) if e[1] == 'min' else max(a, b)
        if k == 'bin':
            a, b = self.val(e[2], env), self.val(e[3], env)
            if a is None or b is None: return None
            if isinstance(a, str) or isinstance(b, str): return None
            return {'+': a+b, '-': a-b, '*': a*b,
                    '/': a//b if b else None, '%': a%b if b else None}[e[1]]
        return None

    def keys_of(self, keys, env):
        out = []
        for k in keys:
            v = self.val(k, env)
            if v is None: raise NotImplementedError(f"座標が束縛で決まらない: {k}")
            out.append(v)
        return out

    # ── 値の式を「読む升たち＋重み」に分ける ─────────────────────────
    MOP = {'*': 6, '/': 7, '%': 8}

    def newid(self):
        i = self.nid; self.nid += 1; return i

    def tmp(self, lat):
        """中間の升。一つの寄与にしか使われないので、束は何でも矛盾しない ——
        先と同じ束に置けば、読みが単調のままになる。"""
        self.ntmp += 1
        return self.q(0, 0, 0, self.cell('#', (self.ntmp,)), lat)

    def atom(self, v):
        """文字列などの原子に番号を与える。**内容アドレスの上の段**に置くので、
        数の座標とも構成子の番地とも混ざらない。

        番号は **綴りの順**に配ってある（`_allatoms` が先に全部集めている）ので、
        番号の大小がそのまま綴りの大小である —— `min` / `max` / 比較が、
        文字列のままのときと同じ答えを出す。走らせる側は文字列を一度も見ない。"""
        i = self.atn.get(v)
        if i is None:
            i = len(self.atl); self.atn[v] = i; self.atl.append(v)
        return self.ATOMB + i

    def obs(self, v):
        """面の値 → 見せる値。原子の番号を綴りに戻す。"""
        if isinstance(v, frozenset):
            return frozenset(self.obs(x) for x in v)
        if isinstance(v, int) and not isinstance(v, bool) and v >= self.ATOMB:
            i = v - self.ATOMB
            if i < len(self.atl): return self.atl[i]
        return v

    def ctcell(self):
        self.ntmp += 1
        return self.q(0, 0, 0, self.cell('#', (self.ntmp,)), 5)

    def ctexpr(self, e, env, st):
        """**条件のためだけの項。** 閉じた面からしか読まないので、寄与が立つか
        どうかに依存しない —— だから `not` や `==` の輪に入らない。
        束が混ざっていても、ここに写せば一つの面で比べられる。"""
        if st <= 0:
            raise NotImplementedError("層 0 で閉じた値から項を作れない")
        S = -1 - st
        if e[0] == 'fref':
            q = self.cref(e[1], e[2], env, st)
            t = self.ctcell()
            self.eg.append((self.newid(), S, 0, t, 4, 1, q, self.flat[e[1]], 0, 0))
            return t
        if e[0] == 'bin' and e[1] in ('+', '-', '*', '/', '%'):
            vf = 1 if e[1] in '+-' else self.MOP[e[1]]
            a = self.ctexpr(e[2], env, st)
            v = self.val(e[3], env)
            t = self.ctcell()
            if v is not None and not isinstance(v, str):
                if e[1] == '-': v = -v
                self.eg.append((self.newid(), S, 0, t, vf, 1, a, 0, 0, v))
            else:
                if e[1] == '-':
                    raise NotImplementedError("条件の項で升を引く形はまだ")
                b = self.ctexpr(e[3], env, st)
                self.eg.append((self.newid(), S, 0, t, vf, 2, a, 0, b, 0))
            return t
        if e[0] == 'ctor':
            raise NotImplementedError("条件の項に構成子")
        v = self.val(e, env)
        if isinstance(v, str): v = self.atom(v)   # **原子は番号で渡す**
        if v is None:
            raise NotImplementedError(f"条件の項: {e}")
        t = self.ctcell()
        self.eg.append((self.newid(), S, 0, t, 0, 0, 0, 0, 0, v))
        return t

    def tolat(self, srcs, lat, st):
        """束の違う源を、先と同じ束の升に写す。**閉じた面から写す**ので、
        「育つ値を別の束で読む」ことにはならない。"""
        out = []
        for l, q in srcs:
            if l == lat:
                out.append((l, q)); continue
            if st <= 0:
                raise NotImplementedError("層 0 で他の束を読んでいる")
            t = self.tmp(lat)
            self.eg.append((self.newid(), st, lat, t, 4, 1, q, -l, 0, 0))
            out.append((lat, t))
        return out

    def cellof(self, q):
        """指し番号 → 升番号（地上で決まる指し方のときだけ）。"""
        row = self.ix[q]
        if row[1] != 0: raise NotImplementedError("座標の中の座標が値で決まる形はまだ")
        return row[4]

    def enc(self, v, m, k):
        """内容アドレスの引数の符号化（`lattix._enc` と同じ定義）。"""
        return L._enc(v, m, k)

    def ctor(self, e, env, lat, st):
        """構成子 → 辺の連なり。**内容アドレスは整数の算術だけで書ける** ——
        だから走らせる側に新しい仕掛けが一つも要らない。

            h ← (h·K + enc(引数)) mod M     を法二本ぶん
            番地 = h1·M2 + h2

        地上で決まる引数は前段で畳む。升の値である引数だけが辺になる。
        掛け算が 31×31 ビットに収まるので、128 ビット整数が要らない。"""
        nm, args = e[1], e[2]
        parts = []
        for m, k in ((L.CTOR_M1, L.CTOR_K1), (L.CTOR_M2, L.CTOR_K2)):
            h = L._fold(nm.encode(), m, k)
            h = (h * k + len(args) + 1) % m
            cur = None                                # h を持つ升（None なら定数）
            for a in args:
                v = self.val(a, env)
                if v is not None and cur is None:
                    h = (h * k + L._enc(v, m, k)) % m
                    continue
                if cur is None:                       # 定数をいったん升に置く
                    cur = self.tmp(lat)
                    self.eg.append((self.newid(), st, lat, cur, 0, 0, 0, 0, 0, h))
                t1 = self.tmp(lat)                    # h · K
                self.eg.append((self.newid(), st, lat, t1, 6, 1, cur, lat, 0, k))
                t2 = self.tmp(lat)
                if v is not None:                     # h·K + enc(定数)
                    self.eg.append((self.newid(), st, lat, t2, 1, 1, t1, lat, 0,
                                    L._enc(v, m, k)))
                else:
                    q, ql = self.vexpr(a, env, lat, st)
                    t0 = self.tmp(lat)                # v mod M
                    self.eg.append((self.newid(), st, lat, t0, 8, 1, q, ql, 0, m))
                    t3 = self.tmp(lat)                # enc(値) = 3(v mod M)
                    self.eg.append((self.newid(), st, lat, t3, 6, 1, t0, lat, 0, 3))
                    self.eg.append((self.newid(), st, lat, t2, 1, 2, t1, lat, t3, 0))
                cur = self.tmp(lat)                   # mod M
                self.eg.append((self.newid(), st, lat, cur, 8, 1, t2, lat, 0, m))
            if cur is None:
                cur = self.tmp(lat)
                self.eg.append((self.newid(), st, lat, cur, 0, 0, 0, 0, 0, h))
            parts.append(cur)
        h1, h2 = parts                                # 番地 = h1·M2 + h2
        t = self.tmp(lat)
        self.eg.append((self.newid(), st, lat, t, 6, 1, h1, lat, 0, L.CTOR_M2))
        u = self.tmp(lat)
        self.eg.append((self.newid(), st, lat, u, 1, 2, t, lat, h2, 0))
        return u, lat

    def vexpr(self, e, env, lat, st):
        """値の式 → (その値を持つ升の指し番号, その升の束)。層 st で作る。

        剰余と「升で割る」は単調でないので、**引数が閉じていなければならない**。
        だから一段下の層で作る。処理系の成層がその層を用意している ——
        非単調な読みは必ず真に後ろに置かれているからである。
        """
        if e[0] == 'fref':
            if e[1] == '#c':                    # 既に番号が分かっている升
                return self.q(0, 0, 0, e[2][0][1], lat), lat
            return self.cref(e[1], e[2], env, st), self.flat[e[1]]
        if e[0] == 'ctor':
            return self.ctor(e, env, lat, st)
        if e[0] == 'bin' and e[1] in self.MOP:
            g = self.val(e[3], env)
            ground = g is not None and not isinstance(g, str)
            # 単調でない段は **閉じた面**から読む。負を掛ける／負で割るのも
            # 順序を裏返すので同じ扱いにする（`la` に負を書いて合図する）。
            # こうすると、走らせる側の各規則が見る `w` の符号が一定になり、
            # 「宣言されたデータから符号を証す」道が通る。
            # flat / fourv の升は ⊥ → v → ⊤ としか動かないので、剰余も単調。
            hard = (e[1] == '%' and lat not in (5, 6)) or not ground
            if ground and isinstance(g, int):
                if lat not in (5, 6):
                    if e[1] == '*' and g < 0: hard = True
                    if e[1] == '/' and g <= 0: hard = True
            sub = st - 1 if hard else st
            if sub < 0:
                raise NotImplementedError(f"層 0 で `{e[1]}` を畳む形はまだ")
            a, la = self.vexpr(e[2], env, lat, sub)
            t = self.tmp(lat)
            if ground:
                self.eg.append((self.newid(), st, lat, t, self.MOP[e[1]], 1,
                                a, -la if hard else la, 0, g))
            else:
                b, _lb = self.vexpr(e[3], env, lat, sub)
                self.eg.append((self.newid(), st, lat, t, self.MOP[e[1]], 2,
                                a, -la, b, 0))
            return t, lat
        if e[0] == 'bin' and e[1] in '+-':
            srcs, w = self.split(e, env, 1, lat, st)
            if any(l != lat for l, _q in srcs) and len(srcs) > 1:
                srcs = self.tolat(srcs, lat, st)
            # **三つ以上の升を足すなら、二つずつ畳む。** 辺は二項でよい。
            while len(srcs) > 2:
                (l1, q1), (l2, q2) = srcs[0], srcs[1]
                if l1 != l2:
                    raise NotImplementedError("二つの升を足す寄与で束が混ざる形はまだ")
                t = self.tmp(lat)
                self.eg.append((self.newid(), st, lat, t, 1, 2, q1, l1, q2, 0))
                srcs = [(lat, t)] + srcs[2:]
            c = [q for _l, q in srcs] + [0, 0]
            la = srcs[0][0] if srcs else lat
            if len(srcs) == 2 and srcs[1][0] != la:
                raise NotImplementedError("二つの升を足す寄与で束が混ざる形はまだ")
            t = self.tmp(lat)
            self.eg.append((self.newid(), st, lat, t, 1, len(srcs),
                            c[0], la, c[1], w))
            return t, lat
        v = self.val(e, env)
        if v is not None and not isinstance(v, str):
            t = self.tmp(lat)
            self.eg.append((self.newid(), st, lat, t, 0, 0, 0, 0, 0, v))
            return t, lat
        raise NotImplementedError(f"値の形: {e}")

    def split(self, e, env, sign=1, lat=None, st=0):
        k = e[0]
        if k == 'bin' and e[1] in '+-':
            s1, c1 = self.split(e[2], env, sign, lat, st)
            s2, c2 = self.split(e[3], env, sign if e[1] == '+' else -sign, lat, st)
            return s1 + s2, c1 + c2
        if k == 'fref':
            q = self.cref(e[1], e[2], env, st)
            if sign == 1:
                return [(self.flat[e[1]], q)], 0
            # 引くのは「−1 を掛ける」ことである。中間の升に開けば形が増えない。
            lt = lat if lat is not None else self.flat[e[1]]
            t = self.tmp(lt)
            # 負を掛けるのは単調でない ⇒ **閉じた面**から読む
            self.eg.append((self.newid(), st, lt, t, 6, 1, q,
                            -self.flat[e[1]], 0, -1))
            return [(lt, t)], 0
        v = self.val(e, env)
        if isinstance(v, str) and sign == 1:
            return [], self.atom(v)      # **原子は番号で渡す**（文字列は渡さない）
        if v is not None and not isinstance(v, str):
            return [], sign * v
        if lat is None or sign != 1:
            raise NotImplementedError(f"値の形: {e}")
        q, lt = self.vexpr(e, env, lat, st)
        return [(lt, q)], 0

    # ── ガードを「地上で決まるもの」と「升を読むもの」に分ける ───────
    FLIP = {'==': '==', '!=': '!=', '>=': '<=', '<=': '>=', '>': '<', '<': '>'}

    def _est(self, r):
        """反復空間の大きさの **見積り**（閉じ直さずに分かるぶんだけ）。
        分からない端は「大きい」と見る —— 端が場の読みなら、たいてい大きい。"""
        n = 1
        for _vs, src in r.sources:
            if isinstance(src, tuple) and src[0] == '..':
                lo, hi = self.val(src[1], {}), self.val(src[2], {})
                if lo is None or hi is None: return 1 << 30
                n *= max(0, hi - lo + 1)
            else:
                n *= len(self.p.tables.get(src, ()))
        return n

    def settled(self, q, st):
        """その問いは **閉じた層だけで決まる**か（層 s-1 以下の場しか読まない）。"""
        fs = [x[1] for x in _frefs(q)]
        if not fs or st == 0: return False
        if any(self.fstr.get(f, 1 << 30) >= st for f in fs): return False
        return not _hasctor(q)

    def gguard(self, q, env, st):
        """**閉じた層だけで決まる問いは、表に載せない。**

        層 s の規則が層 s-1 以下の場だけを問うているなら、その答えは
        いま既に確定している（超段は交代している —— `close_upto`）。
        載せれば、走らせる側が点ごとに同じことをもう一度数えるだけである。
        真偽が決まらない（形が分からない）ときは None を返し、
        いままでどおり `cd` の行にする。"""
        def truthy(v):
            if v is None: return False
            if isinstance(v, L._Top): return True   # ⊤ は「少なくとも真」
            if isinstance(v, frozenset): return len(v) > 0
            return bool(v)

        k = q[0]
        if k == 'cmp':
            a = self.gval(q[2], st, env); b = self.gval(q[3], st, env)
            if isinstance(a, L._Top) or isinstance(b, L._Top): return True
            if a is None or b is None: return False   # ⊥ は火を噴かない
            try:
                return {'==': a == b, '!=': a != b, '>=': a >= b,
                        '<=': a <= b, '>': a > b, '<': a < b}[q[1]]
            except TypeError:
                return None
        if k == 'fref':
            return truthy(self.gval(q, st, env))
        if k == 'not' and q[1][0] == 'fref':
            return not truthy(self.gval(q[1], st, env))
        if k == 'geq' and q[1][0] == 'fref':
            v = self.gval(q[1], st, env); c = self.val(q[2], env)
            if v is None or c is None: return False
            if isinstance(v, L._Top): return True
            try: return bool(self.p.fields[q[1][1]].geq(v, c))
            except Exception: return None
        return None

    def cond(self, q, env, eid, st):
        if q[0] == 'cmp':
            op, a, b = q[1], q[2], q[3]
            av, bv = self.val(a, env), self.val(b, env)
            if av is not None and bv is not None:            # 地上で決まる
                return {'==': av == bv, '!=': av != bv, '>=': av >= bv,
                        '<=': av <= bv, '>': av > bv, '<': av < bv}[op]
            if av is not None:                               # 左に升を置く
                op, a, b = self.FLIP[op], b, a
            fl = [x[1] for x in _frefs(a)] + [x[1] for x in _frefs(b)]
            if not fl:
                raise NotImplementedError(f"ガードの辺: {q}")
            lat = self.flat[fl[0]]
            mixed = any(self.flat[f] != lat for f in fl)
            # **層は単調でない問いのためだけに在る。** 比べる相手がみな同じ層で
            # 書かれているなら、閉じた面ではなく生きた面を見てよい。
            k = 1 if all(self.fstr.get(f, -1) >= st for f in fl) else 0
            # **寄与元キー付きの束（sum/count/bag）を生きた面で比べない。**
            # 観測は寄与が集まるほど動くので、符号が証せない限り単調でない ——
            # 走らせる物は表を見て符号を証せない（どの本の表も同じ規則を通る）。
            if k and lat in (8, 9, 10):
                k = 0
            if not k and st == 0:
                raise NotImplementedError("層 0 で閉じた値を問うている")
            simple = (a[0] == 'fref') and not mixed
            if simple:
                try:
                    tst = st if k else st - 1
                    cl = self.cref(a[1], a[2], env, tst)
                    srcs, w = self.split(b, env, 1, lat, tst)
                    if len(srcs) > 2:
                        raise NotImplementedError("条件の右が三つ以上の升を読む形")
                    if any(l != lat for l, _c in srcs):
                        raise NotImplementedError("条件で束が混ざる")
                    rc = [c for _l, c in srcs] + [0, 0]
                    self.cd.append((eid, st, 1 + 10 * k, lat, cl,
                                    OP[op], len(srcs), rc[0], rc[1], w))
                    return True
                except NotImplementedError:
                    pass
            # 素直に比べられないなら、両辺を **条件のための面**に写して比べる。
            cl = self.ctexpr(a, env, st)
            cr = self.ctexpr(b, env, st)
            self.cd.append((eid, st, 1, 0, cl, OP[op], 1, cr, 0, 0))
            return True
        if q[0] == 'geq' and q[1][0] == 'fref':
            bv = self.val(q[2], env)
            if bv is None: raise NotImplementedError(f"`is` の右辺: {q[2]}")
            if isinstance(bv, str): bv = self.atom(bv)
            if isinstance(bv, bool): bv = 1 if bv else 0
            # ⊒ は **どの束でも単調** —— だから層を要求しない。生きた面を見る。
            self.cd.append((eid, st, 4, self.flat[q[1][1]],
                            self.cref(q[1][1], q[1][2], env, st),
                            0, 0, 0, 0, bv))
            return True
        if q[0] == 'bnot' and q[1][0] == 'fref':
            e = q[1]                                    # Belnap の否定は単調
            self.cd.append((eid, st, 5, self.flat[e[1]],
                            self.cref(e[1], e[2], env, st), 0, 0, 0, 0, 0))
            return True
        if q[0] == 'not' and q[1][0] == 'fref':
            e = q[1]
            if st == 0: raise NotImplementedError("層 0 で否定を問うている")
            self.cd.append((eid, st, 2, self.flat[e[1]],
                            self.cref(e[1], e[2], env, st), 0, 0, 0, 0, 0))
            return True
        if q[0] == 'fref':
            self.cd.append((eid, st, 3, self.flat[q[1]],
                            self.cref(q[1], q[2], env, st), 0, 0, 0, 0, 0))
            return True
        raise NotImplementedError(f"ガードの形: {q}")

    # ── 反復空間を数え上げる ─────────────────────────────────────────
    def gval(self, e, st, env):
        """区間の端だけが使ってよい評価 —— **閉じた層の値**を見に行く。

        規則の値やガードはここを通らない。通せば関係を先に解いてしまい、
        「宣言をそのまま渡す」ではなくなる。端だけは反復空間そのものなので、
        数え上げる前に知っていなければならない。"""
        try:
            v = self.val(e, env)
        except KeyError:
            return None
        if v is not None: return v
        if e[0] == 'bin' and e[1] in '+-*/%':
            a, b = self.gval(e[2], st, env), self.gval(e[3], st, env)
            if a is None or b is None: return None
            return {'+': a+b, '-': a-b, '*': a*b,
                    '/': a//b if b else None, '%': a%b if b else None}[e[1]]
        if e[0] == 'fn':
            a, b = self.gval(e[2], st, env), self.gval(e[3], st, env)
            if a is None or b is None: return None
            return min(a, b) if e[1] == 'min' else max(a, b)
        if e[0] == 'fref':
            keys = []
            for x in e[2]:
                k = self.gval(x, st, env)
                if k is None: return None
                keys.append(k)
            # **いまここまで数え上げた関係**を閉じる。位相順に処理しているので、
            # 端を決める場はもう関係の中に入っている。
            # 一度知った端は動かない（その SCC はもう閉じている）ので、
            # 分からないときだけ閉じ直す —— でないと規則ごとに走らせ直しになる。
            k = (e[1], tuple(keys))
            self.gvhit = True
            v = self.closed.get(k)
            if v is None and self.closer is not None and not self.noclose \
                    and self.upto != len(self.eg) + len(self.fg):
                self.closer(); v = self.closed.get(k)
            return v
        return None

    def bindings(self, r):
        """反復空間を数え上げる。**内側の端が外側の束縛で決まってよい**
        （`for (i) in … for (j) in 0 .. ndep[i] - 1`）ので、入れ子で回す。"""
        st = getattr(r, 'stratum', 0) or 0

        def rec(i, env):
            if i == len(r.sources):
                yield dict(env); return
            vs, src = r.sources[i]
            if isinstance(src, tuple) and src[0] == '..':
                self.gvhit = False
                lo = self.gval(src[1], st, env); hi = self.gval(src[2], st, env)
                if lo is None or hi is None:
                    if not self.gvhit:
                        raise NotImplementedError("区間の端が定数でない形はまだ")
                    return          # 端が ⊥ ⇒ 反復空間は空（参照実装と同じ）
                for x in range(lo, hi + 1):
                    env[vs[0]] = x
                    for e2 in rec(i + 1, env): yield e2
            else:
                for row in self.p.tables[src]:
                    for k, v in zip(vs, row): env[k] = v
                    for e2 in rec(i + 1, env): yield e2

        for e in rec(0, {}): yield e

    # ── 値の式 → (形, 源のリスト, 重み) を一つ以上 ───────────────────
    def forms(self, r, env, lat, st):
        e = r.value
        if e[0] == 'bool':
            return [(2 if e[1] else 5, [], 0)]
        if e[0] == 'set':
            out = []
            for x in e[1]:
                v = self.val(x, env)
                if v is not None:
                    out.append((3, [], self.atom(v) if isinstance(v, str) else v))
                    continue
                q, ql = self.vexpr(x, env, self.flat[x[1]] if x[0] == 'fref'
                                   else lat, st)
                out.append((9, [(ql, q)], 0))     # {升の値}
            return out
        if e[0] == 'fref':
            return [(4, [(self.flat[e[1]], self.cref(e[1], e[2], env, st))], 0)]
        v = self.val(e, env)
        if v is not None:
            # **走らせる側は文字列を一度も見ない。** 原子は番号にして渡す
            # （番号の大小＝綴りの大小なので、比較も min/max も答えが変わらない）。
            return [(0, [], self.atom(v) if isinstance(v, str) else v)]
        if lat not in ARITH:
            raise NotImplementedError(f"束 {lat} に算術の値: {e}")
        srcs, w = self.split(e, env, 1, lat, st)
        while len(srcs) > 2 or (len(srcs) == 2 and
                                (srcs[0][0] != lat or srcs[1][0] != lat)):
            if srcs[0][0] != lat or srcs[1][0] != lat:
                srcs = self.tolat(srcs, lat, st)
            if len(srcs) <= 2: break
            t = self.tmp(lat)
            self.eg.append((self.newid(), st, lat, t, 1, 2,
                            srcs[0][1], lat, srcs[1][1], 0))
            srcs = [(lat, t)] + srcs[2:]
        return [(1, srcs, w)]

    def run(self):
        # **層の中も順序がある。** 層は協調の回数を決めるだけで、その中の
        # 順序は凝縮グラフの位相順である。反復空間の端を決める場は、
        # 端を使う規則より前の SCC に居るので、そこまで閉じれば数え上げられる。
        rank = getattr(self.p, 'scc_rank', {})
        for r in sorted(self.p.rules,
                        key=lambda r: (getattr(r, 'stratum', 0) or 0,
                                       rank.get(r.scc, r.scc), r.id)):
            f = r.target
            st = getattr(r, 'stratum', 0) or 0
            lat = self.flat[f]
            if FAMILY and self.family(r, st, lat): continue
            # **閉じた層だけで決まる問いは、規則ごとに一度だけ閉じて答える。**
            # 実例ごとに閉じ直したら、それは関係を数え上げる代わりに
            # 関係を何度も解くことになる（気づき35 の裏面）。
            sg = [i for i, q in enumerate(r.guards) if self.settled(q, st)]
            # **閉じ直す価値があるのは、点が多いときだけである。**
            # 小さい空間のために関係を解き直したら、それは節約ではない。
            if sg and self.gst != st and self._est(r) < FAMILY_MIN: sg = []
            # **閉じるのは層ごとに一度**。層 st の辺をいくら足しても、
            # 層 st-1 以下の値は動かない（そこはもう閉じている）。
            if sg and self.closer is not None and self.gst != st:
                if self.upto != len(self.eg) + len(self.fg): self.closer()
                self.gst = st
            for env in (self.bindings(r) if r.sources else [{}]):
                if sg:
                    self.noclose = True
                    try:
                        g0 = {i: self.gguard(r.guards[i], env, st) for i in sg}
                    finally:
                        self.noclose = False
                    if any(x is False for x in g0.values()): continue
                    rest = [q for i, q in enumerate(r.guards)
                            if g0.get(i, None) is None]
                else:
                    rest = r.guards
                eid = self.newid()
                if not all(self.cond(q, env, eid, st) for q in rest):
                    self.cd[:] = [c for c in self.cd if c[0] != eid]
                    continue
                dst = self.cref(f, r.keys, env, st)
                first = True
                for vf, srcs, w in self.forms(r, env, lat, st):
                    if len(srcs) > 2:
                        raise NotImplementedError("一つの寄与が三つ以上の升を読む形はまだ")
                    lats = [l for l, _c in srcs]
                    if len(srcs) == 2 and (lats[0] != lat or lats[1] != lat):
                        raise NotImplementedError("二つの升を足す寄与で束が混ざる形はまだ")
                    if any(l != lat for l in lats) and st == 0:
                        raise NotImplementedError("層 0 で他の束を読んでいる")
                    cells = [c for _l, c in srcs] + [0, 0]
                    lats = lats + [0, 0]
                    e2 = eid if first else self.newid()      # 集合は元ごとに一辺
                    if not first:
                        for c in [c for c in self.cd if c[0] == eid]:
                            self.cd.append((e2,) + c[1:])
                    first = False
                    self.eg.append((e2, st, lat, dst, vf, len(srcs),
                                    cells[0], lats[0], cells[1], w))
        return self

    # ── 走らせる側に渡す表 ───────────────────────────────────────────
    def tables(self):
        t = {'eg': self.eg, 'cd': self.cd, 'ix': self.ix,
             'dat': self.dat, 'spc': self.spc, 'ssz': self.ssz,
             'mp': self.mp, 'fg': self.fg, 'fc': self.fc, 'fp': self.fp}
        if not self.dat: self.dat.append((0, 0, 0))
        for k, ar in (('eg', 10), ('cd', 10), ('ix', 6),
                      ('dat', 3), ('spc', 5), ('ssz', 2), ('mp', 14),
                      ('fg', 10), ('fc', 11), ('fp', 6)):
            if not t[k]:
                row = [0] * ar; row[1] = 999        # どの層にも当たらない番兵
                if k in ('ix', 'dat', 'spc', 'mp'): row = [0] * ar
                if k == 'ssz': row = [0, 1]
                if k == 'fg': row = [0, 0, 999, 0, 0, 0, 0, 0, 0, 0]
                if k == 'fc': row = [0, 0, 999, 0, 0, 0, 0, 0, 0, 0, 0]
                if k == 'fp': row = [0, 0, 999, 0, 0, 0]
                t[k] = [tuple(row)]
        return t

    def strata(self):
        return max([e[1] for e in self.eg] + [g[2] for g in self.fg] + [0]) + 1

    # ── この関係に **実際に現れる形**。走らせる物はこれだけ持てばよい ──
    def shapes(self):
        # **層は形の一部ではない。** どの層にも同じ形が現れうるので、
        # 走らせる物は層ごとに同じ規則を持つ（配る一枚にするための性質）。
        vals = sorted({(e[2], e[4], e[5], e[7]) for e in self.eg if e[1] >= 0})
        self.fsh = sorted({(g[3], g[4], g[5]) for g in self.fg})   # 束,形,数
        self.fcsh = sorted({(c[3], c[4], c[6], c[7]) for c in self.fc})  # 種,束,演算子,数
        self.fpsh = sorted({r[3] for r in self.fp})                # 番地の面の源の束
        cond = sorted({(c[2], c[3], c[5], c[6]) for c in self.cd})   # 種,束,演算子,数
        self.ixlat = sorted({r[3] for r in self.ix if r[1] != 0})
        lats = sorted({r[5] for r in self.ix} | {abs(e[2]) for e in self.eg}
                      | {abs(l) for l in self.ixlat} | {g[3] for g in self.fg} | {5})
        return vals, cond, [l for l in lats if l in PLANE]

    def ncell(self):
        n = self.nbase + len(self.rev)
        for _q, m, _ic, _il, o, _dl in self.ix:
            n = max(n, o + 1)
        return n


def _addok(e):
    """場の読みが **足し算の枝にだけ**あるか。掛け算や割り算の中にあると、
    「Σ源 + 重み」に分けられない（`pow2[n-1] * 2` はそれ）。"""
    if not isinstance(e, tuple) or not e: return True
    if e[0] == 'fref': return True
    if e[0] == 'bin' and e[1] == '+': return _addok(e[2]) and _addok(e[3])
    if e[0] == 'bin' and e[1] == '-':
        return _addok(e[2]) and not any(True for _ in _frefs(e[3]))
    return not any(True for _ in _frefs(e))


def _tops(e):
    """**加法の骨組みの上にある読み**だけを返す（添字の中には降りない）。
    `match[owt[i]] + 1` の頂上は `match[…]` ひとつである —— 内側の `owt` は
    座標であって、この式の項ではない（気づき28）。"""
    if not isinstance(e, tuple) or not e: return
    if e[0] == 'fref':
        yield e; return
    if e[0] == 'bin' and e[1] in ('+', '-', '*'):
        for x in (e[2], e[3]):
            for y in _tops(x): yield y


def _coef(e, g, sign=1):
    """加法の枝にある `g` の係数（`3 * g[i]` なら 3、`x - g[i]` なら -1）。"""
    if e is g: return sign
    if isinstance(e, tuple) and e and e[0] == 'bin':
        if e[1] == '+':
            return _coef(e[2], g, sign) or _coef(e[3], g, sign)
        if e[1] == '-':
            return _coef(e[2], g, sign) or _coef(e[3], g, -sign)
        if e[1] == '*':
            for a, b in ((e[2], e[3]), (e[3], e[2])):
                if isinstance(b, tuple) and b and b[0] == 'int':
                    c = _coef(a, g, sign)
                    if c: return c * b[1]
    return 0


def _strip(e, srcs):
    """式から場の読みを 0 に置き換える（残りが重みの一次式になる）。"""
    if e in srcs: return ('int', 0)
    if isinstance(e, tuple) and e and e[0] == 'bin':
        return (e[0], e[1], _strip(e[2], srcs), _strip(e[3], srcs))
    if isinstance(e, tuple) and e and e[0] == 'fref':
        return ('int', 0)
    return e


def _arity(prog, f):
    n = 0
    for r in prog.rules:
        if r.target == f: n = max(n, len(r.keys))
        for e in r.keys + [r.value] + r.guards:
            for x in _frefs(e):
                if x[1] == f: n = max(n, len(x[2]))
    return n


def _frefs(e):
    if isinstance(e, (list, tuple)):
        if e and e[0] == 'fref': yield e
        for x in e:
            if isinstance(x, (list, tuple)):
                for y in _frefs(x): yield y


def _hasctor(e):
    if isinstance(e, (list, tuple)):
        if e and e[0] == 'ctor': return True
        return any(_hasctor(x) for x in e if isinstance(x, (list, tuple)))
    return False


def _allatoms(prog):
    """プログラムに現れる原子（文字列）を、**綴りの順**にすべて集める。
    走らせる側に渡す表に文字列を一つも入れないための下ごしらえである ——
    前段が Lattix になったとき、そこで文字列を持てないのと同じ理由。"""
    out = set()
    def walk(e):
        if not isinstance(e, tuple) or not e: return
        if e[0] == 'str': out.add(e[1]); return
        for x in e[1:]:
            if isinstance(x, tuple): walk(x)
            elif isinstance(x, list):
                for y in x: walk(y)
    for rows in prog.tables.values():
        for row in rows:
            for x in row:
                if isinstance(x, str): out.add(x)
    for r in prog.rules:
        for e in list(r.keys) + [r.value] + list(r.guards): walk(e)
    return sorted(out)


def _needs_arith(prog):
    """座標に場の読みが現れる場は、番号が **算術**でなければならない。"""
    need = set()
    for r in prog.rules:
        for k in r.keys:
            if any(True for _ in _frefs(k)):
                need.add(r.target)
        for e in r.keys + [r.value] + r.guards:
            for x in _frefs(e):
                for k in x[2]:
                    if any(True for _ in _frefs(k)):
                        need.add(x[1])
    return need


def flatten(path, closer=None):
    """**二巡する。** 一巡目は仮の広さで数え上げて、実際に使われた座標を測る。
    二巡目は測った値をそのまま上端にする —— 大きく書けば測らずに済むが、
    それは「上限を測らないことの言い換え」である（CLAUDE.md）。"""
    src = open(path, encoding='utf-8').read()

    def once(extent=None, atomb=None):
        p = L.parse(src, base=os.path.dirname(os.path.abspath(path)))
        L.check(p); L.stratify(p)
        fl = Flatten(p, extent, atomb)
        if closer is not None: fl.closer = closer(fl)
        return fl.run(), p

    fl, _p = once()
    if fl.closer is not None:
        fl.upto = -1
        try: fl.closer()          # 一度走らせて、触れた升を全部数える
        except Exception: pass
    # 一巡目で測った上端のうち、原子は仮の置き場（ATOMB0）に載っている。
    # 二巡目では原子を「数の上端のすぐ上」に置き直すので、測った値も translate する。
    num = [z for (f, i), (a, z) in fl.seen.items() if z < ATOMB0]
    nb = (max(num) + 1) if num else 1
    ext = {}
    for k, (a, z) in fl.seen.items():
        ext[k] = (a - ATOMB0 + nb if a >= ATOMB0 else a,
                  z - ATOMB0 + nb if z >= ATOMB0 else z)
    return once(ext, nb)


if __name__ == '__main__':
    fl, p = flatten(sys.argv[1])
    for k, v in fl.tables().items():
        print(f"{k:3} {v[:5]}{' …' if len(v) > 5 else ''}  （{len(v)} 行）")
    print("層", fl.strata(), " 升", fl.ncell(), " 指し番号", len(fl.ix))
    v, c, l = fl.shapes()
    print("形", v); print("条件", c); print("束", l)
