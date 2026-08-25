# -*- coding: utf-8 -*-
"""対象 `.lx` → 規則の表（整数だけ）。**第2段で `front.lx` に置き換わる仮の物。**

   符号は `examples/33_self.lx` に合わせる（測って決めた）:
     fld   (場, 束, 次数)                束 1 min / 2 max / 3 or
     seed  (番号, 場, 座標, 値)
     rrule (規則, 層, 束, 表の次数, 書き場, 書き先の所有者)
     lop   (通し, 規則, 段, 種, 下端, 上端, 次数, 上端の場, 上端の座標)  種 0 表
     trm   (通し, 規則, 項番号, 種, 場, 列, 値, 所有者)
             種 1 定数 / 2 表の列 / 3 場 / 4 計数器
             種 5 -定数 / 6 *定数 / 7 /定数 / 8 %定数 / 9 -場 / 10 *場
     grd   (通し, 規則, 番号, 種, 場, 列1, 値, 辺の種, 定数, 所有者)
             種 1 `列 == 値` / 2 `not f[C]` / 3 比較の左辺 / 4 比較の右辺（値=演算子）
             演算子 1 == / 2 != / 3 >= / 4 <= / 5 > / 6 <
             辺の種 0 場の読み / 1 表の列 / 2 計数器 / 3 定数
     crd   (通し, 所有者, 規則, 次元, 源, 場, 列, ずれ種, ずれ)
             源 0 表の列 / 1 計数器 / 2 列で引いた場 / 3 計数器で引いた場 / 4 定数
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lattix as L

# **走らせる物が解ける束だけを通す。** 解けない束を黙って空で返すのは
# 「黙って間違える」ことである（`03_time_axis` の flat で一度やった）。
LAT = {'min': 1, 'max': 2, 'or': 3}
OP  = {'==': 1, '!=': 2, '>=': 3, '<=': 4, '>': 5, '<': 6}


class Build:
    def __init__(self, prog):
        self.p = prog
        self.fno = {f: i for i, f in enumerate(prog.fields)}
        self.tno = {t: i for i, t in enumerate(prog.tables)}
        self.fld, self.seed, self.rrule = [], [], []
        self.lop, self.trm, self.grd, self.crd = [], [], [], []
        self.fdim, self.dat = [], []
        self.own = 0

    # ── 座標を一つ置く（所有者を一つ消費する）──────────────────────
    def coord(self, r, keys, cols, ctr):
        ow = self.own; self.own += 1
        for d, k in enumerate(keys):
            sh = 0
            if k[0] == 'bin' and k[1] in '+-' and k[3][0] == 'int':
                sh = k[3][1] if k[1] == '+' else -k[3][1]
                k = k[2]                       # **ずれは座標の性質**（気づき: 番地は座標）
            kk, val = k[0], k
            if kk == 'var' and val[1] in cols:
                self.crd.append((len(self.crd), ow, r, d, 0, 0, cols[val[1]], 1, sh))
            elif kk == 'var' and val[1] in ctr:
                self.crd.append((len(self.crd), ow, r, d, 1, 0, ctr[val[1]], 1, sh))
            elif kk == 'int':
                self.crd.append((len(self.crd), ow, r, d, 4, 0, val[1], 1, sh))
            elif kk == 'fref':
                inner = val[2][0]
                src = 2 if (inner[0] == 'var' and inner[1] in cols) else 3
                col = cols.get(inner[1], ctr.get(inner[1], 0)) if inner[0] == 'var' else 0
                self.crd.append((len(self.crd), ow, r, d,
                                 src, self.fno[val[1]], col, 1, sh))
            else:
                raise NotImplementedError(f"座標の形: {k}")
        return ow

    # ── 値の項へ平らにする（左からの畳み）────────────────────────
    def terms(self, e, out):
        if e[0] == 'bin' and e[1] in '+-*/%':
            self.terms(e[2], out); out.append((e[1], e[3]))
        else:
            out.append((None, e))

    def term_row(self, r, t, op, e, cols, ctr):
        if op == '+': op = None          # 足すのが既定（種 2/3/4 がそれ）
        kind, fld, col, val, ow = None, 0, 0, 0, 0
        if e[0] == 'int':
            if op in ('*','/','%'):
                raise NotImplementedError(
                    "育つ値にデータを掛ける/割る形は、走らせる物がまだ畳めない"
                    "（符号の証明書が要る）")
            kind = {None: 1, '-': 5}[op]; val = e[1]
        elif e[0] == 'var' and e[1] in cols:
            if op == '*': raise NotImplementedError("列を掛ける形はまだ")
            kind = {None: 2, '-': 11}[op]; col = cols[e[1]]
        elif e[0] == 'var' and e[1] in ctr:
            if op == '*': raise NotImplementedError("計数器を掛ける形はまだ")
            kind = {None: 4, '-': 13}[op]; col = ctr[e[1]]
        elif e[0] == 'fref':
            if op in ('-','*'): raise NotImplementedError("場を引く/掛ける形はまだ")
            kind = 3; fld = self.fno[e[1]]
            ow = self.coord(r, e[2], cols, ctr)
        elif e[0] == 'bool':
            kind = 1; val = 1
        else:
            raise NotImplementedError(f"項の形: {e} 演算 {op}")
        self.trm.append((len(self.trm), r, t, kind, fld, col, val, ow))

    # ── ガード ────────────────────────────────────────────────────
    def edge(self, r, g, kind, e, cols, ctr, opv):
        """比較の辺を一行置く。種 3 が左、4 が右（値が演算子）。"""
        if e[0] == 'int':
            self.grd.append((len(self.grd), r, g, kind, 0, 0, opv, 3, e[1], 0))
        elif e[0] == 'var' and e[1] in cols:
            self.grd.append((len(self.grd), r, g, kind, 0, cols[e[1]], opv, 1, 0, 0))
        elif e[0] == 'var' and e[1] in ctr:
            self.grd.append((len(self.grd), r, g, kind, 0, ctr[e[1]], opv, 2, 0, 0))
        elif e[0] == 'fref':
            ow = self.coord(r, e[2], cols, ctr)
            self.grd.append((len(self.grd), r, g, kind, self.fno[e[1]], 0, opv, 0, 0, ow))
        else:
            raise NotImplementedError(f"ガードの辺: {e}")

    def guards(self, r, gl, cols, ctr):
        g = 0
        for q in gl:
            if q[0] == 'cmp':
                self.edge(r, g, 3, q[2], cols, ctr, 0); g += 1
                self.edge(r, g, 4, q[3], cols, ctr, OP[q[1]]); g += 1
            elif q[0] == 'not' and q[1][0] == 'fref':
                e = q[1]
                ow = self.coord(r, e[2], cols, ctr)
                self.grd.append((len(self.grd), r, g, 2, self.fno[e[1]], 0, 0, 0, 0, ow)); g += 1
            elif q[0] == 'fref':
                # `if f[C]` = 「f[C] が ⊥ でない」。比較の左辺だけを置く形で表す
                ow = self.coord(r, q[2], cols, ctr)
                self.grd.append((len(self.grd), r, g, 12, self.fno[q[1]], 0, 0, 0, 0, ow)); g += 1
            else:
                raise NotImplementedError(f"ガードの形: {q}")

    # ── 全体 ──────────────────────────────────────────────────────
    def run(self):
        for f, lat in self.p.fields.items():
            if lat.name not in LAT:
                raise NotImplementedError(f"束 `{lat.name}` はまだ解けない（場 {f}）")
            ar = 1
            for r in self.p.rules:
                if r.target == f: ar = max(ar, len(r.keys))
            self.fld.append((self.fno[f], LAT[lat.name], ar))
            w = 64
            self.fdim.append((self.fno[f], 0, w))
            if ar == 2: self.fdim.append((self.fno[f], 1, w))
        # **表が二つ以上でも、行に通し番号を振れば走らせる側は変わらない。**
        self.base = {}
        n = 0
        for t, rows in self.p.tables.items():
            self.base[t] = n
            for i, row in enumerate(rows):
                for j, v in enumerate(row):
                    self.dat.append((n + i, j, v))
            n += len(rows)
        self.bind = []
        rn = 0
        for r in self.p.rules:
            if not r.sources:                      # 種
                if r.keys and r.keys[0][0] != 'int':
                    raise NotImplementedError(f"種の座標が定数でない: {r.keys}")
                if r.value[0] not in ('int', 'bool'):
                    raise NotImplementedError(f"種の値の形: {r.value}")
                self.seed.append((len(self.seed), self.fno[r.target],
                                  r.keys[0][1] if r.keys else 0,
                                  r.value[1] if r.value[0] != 'bool' else 1))
                continue
            cols, ctr, spaces, arity = {}, {}, [], 0
            for lvl, (vs, src) in enumerate(r.sources):
                if isinstance(src, tuple) and src[0] == '..':
                    lo, hi = src[1], src[2]
                    if lo[0] != 'int' or hi[0] != 'int':
                        raise NotImplementedError("上端/下端が定数でない区間はまだ")
                    ctr[vs[0]] = lvl
                    spaces.append(range(lo[1], hi[1] + 1))
                    self.lop.append((len(self.lop), rn, lvl, 1, lo[1], hi[1], 1, 0, 0))
                else:
                    if cols: raise NotImplementedError("表のループが二つある形はまだ")
                    cols = {v: i for i, v in enumerate(vs)}
                    arity = len(vs)
                    b = self.base[src]
                    spaces.append(range(b, b + len(self.p.tables[src])))
                    self.lop.append((len(self.lop), rn, lvl, 0, 0, 0, len(vs), 0, 0))
            lat = LAT[self.p.fields[r.target].name]
            st = getattr(r, 'stratum', 0) or 0
            # **反復空間はここで数え上げる。** 多面体は宣言されている ——
            # 束縛に通し番号を振って表で渡せば、走らせる側は割り算も掛け算も要らない。
            import itertools as _it
            for combo in _it.product(*spaces):
                gb = len({b[0] for b in self.bind})
                for lvl, idx in enumerate(combo):
                    self.bind.append((gb, rn, lvl, idx))
            ts = []; self.terms(r.value, ts)
            for t, (op, e) in enumerate(ts):
                self.term_row(rn, t, op, e, cols, ctr)
            self.guards(rn, r.guards, cols, ctr)
            hw = self.coord(rn, r.keys, cols, ctr)
            self.rrule.append((rn, st, lat, arity, self.fno[r.target], hw))
            rn += 1
        return self

    # **空の表は書けない。** 存在しない規則番号／場番号を持つ一行を置く ——
    # 番兵は「無い」を値で言う（⊥ ではなく、届かない座標で言う）。
    def sentinel(self, t):
        NR, NF = 4095, len(self.fno)
        for name, arity, at, val in (('seed', 4, 1, NF), ('rrule', 6, 0, NR),
                                     ('trm', 8, 1, NR), ('crd', 9, 2, NR),
                                     ('lop', 9, 1, NR), ('grd', 10, 1, NR),
                                     ('bind', 4, 1, NR), ('dat', 3, 0, 0),
                                     ('fld', 3, 0, NF)):
            if not t[name]:
                row = [0] * arity; row[at] = val
                t[name] = [tuple(row)]
        return t

    def tables(self):
        return self.sentinel({'fld': self.fld, 'seed': self.seed, 'rrule': self.rrule,
                'trm': self.trm, 'crd': self.crd, 'lop': self.lop,
                'grd': self.grd, 'fdim': self.fdim, 'dat': self.dat,
                'bind': self.bind,
                'nrow': [(len(self.dat),)]})


def tables_for(path):
    p = L.parse(open(path, encoding='utf-8').read()); L.check(p); L.stratify(p)
    return Build(p).run().tables()


if __name__ == '__main__':
    for k, v in tables_for(sys.argv[1]).items():
        print(f"{k:6} {v}")
