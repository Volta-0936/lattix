#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attest の **表の上の** 参照実装 —— attest-eval（.lx）を書く前に、表の意味を測る。

attest.py は源を lattix.py の構文で読み直して検査する。ここは焼き手の前段が出した
**規則の表**（attest-front の語の列）を読み、表の意味だけで同じ検査をする:

  (A) 安定性  : どの規則実例の寄与も、答えにすでに吸収されている
  (B) 有基性  : どのセルの値も、より小さい階数のセルだけから導出できる

表の意味（座標の源・項の種・ガードの種・束）を取り違えていれば、attest.py と判定が
食い違う。食い違わないことを測ってから、同じ意味を .lx で書く。
"""
import struct

LAT = {1: 'min', 2: 'max', 3: 'or', 6: 'flat', 8: 'sum', 9: 'count'}
BOT = {'min': 2147483647, 'max': -2147483647, 'or': 0, 'flat': 2147483647, 'sum': 0, 'count': 0}
TOPV = 2147483646
MISS = -2147483646            # 表の「無い値」


class Tables:
    def __init__(self, blob):
        w = struct.unpack('<%dq' % (len(blob) // 8), blob[:len(blob) // 8 * 8])
        if len(w) < 16 or w[0] != 20260923:
            raise ValueError('not an attest-front table')
        self.hdr = w[:16]
        nfl, nsd, nrl, ngl, ngg, ngt, ngc = w[1:8]
        self.inpw, self.outf, self.outw, self.badk, self.ncol = w[9], w[10], w[11], w[12], w[13]
        p = 16
        def rows(n, k):
            nonlocal p
            out = [w[p + i * k: p + i * k + k] for i in range(n)]
            p += n * k
            return out
        self.F = rows(nfl, 5); self.S = rows(nsd, 3); self.R = rows(nrl, 6)
        self.L = rows(ngl, 8); self.G = rows(ngg, 9); self.T = rows(ngt, 7); self.C = rows(ngc, 8)

    # ── 場の置き場（値の面と階数の面）
    def layout(self):
        lay = []; vo = 0; ko = 0
        for lat, ar, w0, w1, w2 in self.F:
            w1 = w1 if ar >= 2 else 1
            w2 = w2 if ar == 3 else 1
            cells = w0 * w1 * w2
            wb = 1 if lat == 3 else 8
            lay.append(dict(lat=LAT.get(lat, '?%d' % lat), ar=ar, w0=w0, w1=w1, w2=w2,
                            cells=cells, wb=wb, vo=vo, ko=ko))
            vo += cells * wb; ko += cells * 4
        return lay, vo, ko


def decode(tab, vals, ranks):
    """密な面 → {場: {升: 値}}, {場: {升: 階数}}（⊥ の升は持たない）"""
    lay, vt, kt = tab.layout()
    if len(vals) < vt or len(ranks) < kt:
        raise ValueError('certificate too short (%d/%d, %d/%d)' % (len(vals), vt, len(ranks), kt))
    S, K = {}, {}
    for f, L in enumerate(lay):
        bot = BOT.get(L['lat'])
        d, k = {}, {}
        for c in range(L['cells']):
            if L['wb'] == 1: v = vals[L['vo'] + c]
            else: v = struct.unpack_from('<q', vals, L['vo'] + 8 * c)[0]
            # 階数は **符号なし** の 32 ビット（.lx の attest と同じ読み。階数は順序でしかないので、
            # 2^31 を越えても順序は保たれる —— 符号つきに読むと、そこで順序が裏返る）
            r = struct.unpack_from('<I', ranks, L['ko'] + 4 * c)[0]
            if v != bot: d[c] = v
            if r: k[c] = r
        S[f], K[f] = d, k
    return lay, S, K


def rows_of(tab, data):
    """表の行。二列は (位置, バイト)、三列以上は 8 バイト小端の語の列"""
    if tab.inpw == 1:
        return [(i, b) for i, b in enumerate(data)]
    n = tab.ncol
    ws = struct.unpack('<%dq' % (len(data) // 8), data[:len(data) // 8 * 8])
    return [tuple(ws[i:i + n]) for i in range(0, len(ws) - n + 1, n)]


def s8(v):
    """ずれは一バイト（mod 256）。符号つきに戻す"""
    v %= 256
    return v - 256 if v >= 128 else v


class Checker:
    def __init__(self, tab, lay, S, K, rows):
        self.t, self.lay, self.S, self.K, self.rows = tab, lay, S, K, rows
        self.slots = {}                       # 所有者 → {次元: 行}
        for o, r, d, src, cf, cc, hf, of in tab.C:
            self.slots.setdefault(o, {})[d] = (src, cf, cc, hf, of)
        self.loops = {}; self.guards = {}; self.terms = {}
        for row in tab.L: self.loops.setdefault(row[0], []).append(row)
        for row in tab.G: self.guards.setdefault(row[0], []).append(row)
        for row in tab.T: self.terms.setdefault(row[0], []).append(row)
        for d in (self.loops, self.guards, self.terms):
            for k in d: d[k].sort(key=lambda x: x[1])
        self.ofield = {}                      # 所有者 → 読む場（項・ガード・内側の出現）
        for row in tab.T:
            if row[2] in (3, 9, 10): self.ofield[row[6]] = row[3]
        for row in tab.G:
            if row[2] in (2, 9) or (row[2] in (3, 4) and row[6] == 0): self.ofield[row[8]] = row[3]
        for o, r, d, src, cf, cc, hf, of in tab.C:
            if src == 5: self.ofield[cc] = cf

    # ── 読み: 場 f の升 c（⊥ なら None）
    def rd(self, f, c):
        return self.S[f].get(c)

    def rank(self, f, c):
        return self.K[f].get(c, 0)

    # ── 所有者 o の座標。升の番号、OUT（座標はあるが広さの外 —— 升は ⊥）、None（座標が無い ——
    # 内側の読みが ⊥。解釈実行は座標の不在を「その升は ⊥」にすり替えない）
    def coord(self, o, f, env, reads):
        L = self.lay[f]
        sl = self.slots.get(o, {})
        ds = []
        for d in range(L['ar'] if L['ar'] in (1, 2, 3) else 1):
            if d not in sl: return None
            src, cf, cc, hf, of = sl[d]
            off = s8(of)
            if src == 4: x = cc
            elif src == 0: x = env['row'][cc]
            elif src == 1: x = env['k'][cc]
            elif src in (2, 3):
                ix = env['row'][cc] if src == 2 else env['k'][cc]
                if hf == 2: ix += off
                c2 = self.cell1(cf, ix)
                if c2 is None: return None             # 内側の升が広さの外 → 内側の読みは ⊥
                v = self.rd(cf, c2)
                reads.append((cf, c2))
                if v is None: return None
                if self.lay[cf]['lat'] == 'flat' and v == TOPV: raise Unsupported('⊤ を座標にした')
                x = v
            elif src == 5:
                c2 = self.coord(cc, cf, env, reads)
                if c2 is None or c2 is OUT: return None
                v = self.rd(cf, c2)
                reads.append((cf, c2))
                if v is None: return None
                if self.lay[cf]['lat'] == 'flat' and v == TOPV: raise Unsupported('⊤ を座標にした')
                x = v
            else: raise ValueError('coord source %d' % src)
            if hf == 1 or (hf != 0 and src in (0, 1, 4)): x += off
            ds.append(x)
        w = [L['w0'], L['w1'], L['w2']]
        for d, x in enumerate(ds):
            if not 0 <= x < w[d]: return OUT
        c = 0
        for d, x in enumerate(ds): c = c * w[d] + x
        return c

    def cell1(self, f, x):
        L = self.lay[f]
        if L['ar'] >= 2 or not 0 <= x < L['w0']: return None
        return x

    # ── 規則 r の実例を回す
    def instances(self, r):
        loops = self.loops.get(r, [])
        def rec(i, env):
            if i == len(loops):
                yield env; return
            _r, li, kind, lo, hi, ar, bf, bc = loops[i]
            if kind == 0:
                for row in self.rows:
                    yield from rec(i + 1, dict(env, row=row))
            else:
                if kind == 2:
                    h = self.rd(bf, bc)
                    if h is None: return
                elif kind == 3:                      # 上端の添字が外の計数器（bc はそのループの番号）
                    h = self.rd(bf, env['k'][bc])
                    if h is None: return
                else: h = hi
                for x in range(lo, h + 1):
                    k = list(env['k']); k[li] = x
                    yield from rec(i + 1, dict(env, k=tuple(k)))
        yield from rec(0, dict(row=(), k=(0,) * 8))      # 計数器は八本まで（焼き手の入れ子の上限）

    def guard_ok(self, r, env, reads):
        gs = self.guards.get(r, [])
        i = 0
        while i < len(gs):
            _r, gi, kind, f, c1, gv, ok, ov, oo = gs[i]
            if kind in (2, 9):
                c = self.coord(oo, f, env, reads)
                if c is None: return False                  # 座標が無い —— not も撃たない
                v = None if c is OUT else self.rd(f, c)
                if c is not OUT: reads.append((f, c))
                truthy = v is not None and v != 0           # ⊥ と 0 は偽。⊤ は真（少なくとも真）
                if (kind == 9) != truthy: return False
                i += 1; continue
            if kind == 3:
                rt = gs[i + 1]
                a = self.side(gs[i], env, reads); b = self.side(rt, env, reads)
                if a is None or b is None: return False
                op = rt[5]
                res = {1: a == b, 2: a != b, 3: a >= b, 4: a <= b, 5: a > b, 6: a < b}[op]
                if not res: return False
                i += 2; continue
            raise ValueError('guard kind %d' % kind)
        return True

    def side(self, g, env, reads):
        _r, gi, kind, f, c1, gv, ok, ov, oo = g
        if ok == 3: return ov
        if ok == 1: return env['row'][c1]
        if ok == 2: return env['k'][c1]
        c = self.coord(oo, f, env, reads)
        if c is None or c is OUT: return None
        reads.append((f, c))
        v = self.rd(f, c)
        if v is not None and self.lay[f]['lat'] == 'flat' and v == TOPV:
            raise Unsupported('⊤ を比べるガード（規則 %d）' % g[0])
        if v is not None and self.lay[f]['lat'] == 'or': v = 1
        return v

    def value(self, r, env, reads):
        ts = self.terms.get(r, [])
        if not ts: return 1                     # `or` の `true`
        total = 0; cur = None; sign = 1; first = True
        def operand(t):
            _r, ti, kind, f, c1, v, oo = t
            if kind in (1, 5, 6, 7, 8): return v
            if kind in (2, 11, 12): return env['row'][c1]
            if kind in (4, 13, 14): return env['k'][c1]
            if kind in (3, 9, 10):
                c = self.coord(oo, f, env, reads)
                if c is None or c is OUT: return None
                reads.append((f, c))
                x = self.rd(f, c)
                if x is None: return None
                if self.lay[f]['lat'] == 'flat' and x == TOPV:
                    raise TopRead()
                if self.lay[f]['lat'] == 'or': x = 1
                return x
            raise ValueError('term kind %d' % kind)
        try:
            xs = [operand(t) for t in ts]
        except TopRead:
            # 算術は ⊤ 厳密（SPEC）。素の写し（項一つ）はそのまま ⊤ を運ぶ
            return TOP
        if any(x is None for x in xs): return None
        for t, x in zip(ts, xs):
            kind = t[2]
            if kind in (6, 10, 12, 14): cur = cur * x
            elif kind == 7: cur = cur // x
            elif kind == 8: cur = cur % x
            else:
                if cur is not None: total += sign * cur
                neg = kind in (5, 9, 11, 13)
                if first and neg: cur, sign = -x, 1      # 単項の `-` は最初の項に掛かる
                else: cur, sign = x, (-1 if neg else 1)
                first = False
        total += sign * cur
        return total

    def run(self):
        t = self.t
        lat_of = {f: L['lat'] for f, L in enumerate(self.lay)}
        stratum = {r: row[0] for r, row in enumerate(t.R)}
        writers = {}                           # 層 → 書かれる場
        for r, row in enumerate(t.R): writers.setdefault(row[0], set()).add(row[3])
        contrib = {}                           # (場, 升) → [(値, 同じ層の読みの階数の最大)]
        total = {}
        rep = dict(instances=0, stability=[], grounded=[], cyclic_top=[], outside=[])
        # 種: 寄与は階数 0 の読みから
        for f, c, v in t.S:
            lt = lat_of[f]
            if lt == 'count': v = 1
            contrib.setdefault((f, c), []).append((v, 0, False))
            if lt in ('sum', 'count'): total[(f, c)] = total.get((f, c), 0) + v
        for r, row in enumerate(t.R):
            st, rl, ar, wf, oo, line = row
            here = writers[st]
            for env in self.instances(r):
                rep['instances'] += 1
                reads = []
                if not self.guard_ok(r, env, reads): continue
                v = self.value(r, env, reads)
                if v is None: continue
                c = self.coord(oo, wf, env, reads)
                if c is None: continue                       # 座標が無い —— 書かない
                if c is OUT:
                    rep['outside'].append((r, line, env.get('k'), env.get('row')))
                    continue
                if v is TOP:
                    if lat_of[wf] != 'flat': raise Unsupported('⊤ が flat でない場へ（規則 %d）' % r)
                    v = TOPV
                lt = lat_of[wf]
                if lt == 'or': v = 1
                if lt == 'count': v = 1
                mr = max([self.rank(f, cc) for f, cc in reads if f in here] or [0])
                # 同じ層の flat の ⊤ を読んだ寄与（⊤ の前の値を読んだ時の寄与は最終の答えから見えない）
                rt = any(f in here and lat_of[f] == 'flat' and self.S[f].get(cc) == TOPV for f, cc in reads)
                contrib.setdefault((wf, c), []).append((v, mr, rt))
                if lt in ('sum', 'count'): total[(wf, c)] = total.get((wf, c), 0) + v
        # (A) 安定性（冪等の束）と (B) 有基性
        for (f, c), cs in contrib.items():
            lt = lat_of[f]
            if lt in ('sum', 'count'): continue
            claimed = self.S[f].get(c)
            for v, _, _rt in cs:
                if not leq(lt, v, claimed):
                    rep['stability'].append((f, c, v, claimed)); break
        for f, L in enumerate(self.lay):
            lt = L['lat']
            for c, claimed in self.S[f].items():
                if lt in ('sum', 'count'):
                    tt = total.get((f, c), 0)
                    if claimed > tt: rep['grounded'].append((f, c, claimed, tt))
                    elif claimed < tt: rep['stability'].append((f, c, tt, claimed))
                    # 在る升の階数は 1 以上（集約でも。階数 0 は「一度も導かれていない」）
                    elif self.rank(f, c) <= 0: rep['grounded'].append((f, c, claimed, 'rank 0'))
                    # **集約の寄与にも階数の規律が要る。** 集約が同じ層の升を（単調に）読むと、寄与が
                    # 答えそのものに支えられる輪が組める —— `c <- 1 if c`（count）に c = 1 と書くと、
                    # その 1 が寄与を立て、寄与が 1 を作る（最小不動点は ⊥）。和の一致だけ見ていた
                    # 間は通った（2026-09-20、偽物を数え上げて見つけた）。小さい階数から来ない寄与は示せない
                    elif any(mr >= self.rank(f, c) for _v, mr, _rt in contrib.get((f, c), ())):
                        raise Unsupported('集約が同じ層の、階数の小さくない読みに支えられている（場 %d 升 %d）' % (f, c))
                    continue
                cs = contrib.get((f, c), [])
                if lt == 'flat' and claimed == TOPV:
                    k = self.rank(f, c)
                    # 違う二つの値も、階数の小さい寄与から数える（閉路の「⊤ は真」で互いを支える偽物がある）
                    vs = {v for v, mr, _rt in cs if v != TOPV and mr < k}
                    tops = [mr for v, mr, _rt in cs if v == TOPV]
                    if len(vs) >= 2 or (tops and min(tops) < k): continue
                    # 階数を問わなければ支えがある ⊤ は、最終の答えだけでは本物と偽物（恒等の f <- f で
                    # 1 しか来ないのに ⊤ と書いたもの）を見分けられない —— 検査したとは言わない
                    vs_any = {v for v, _mr, _rt in cs if v != TOPV}
                    if len(vs_any) >= 2 or tops:
                        raise Unsupported('閉路でしか支えられない ⊤（場 %d 升 %d）' % (f, c))
                    rep['grounded'].append((f, c, claimed, '⊤ without two witnesses')); continue
                k = self.rank(f, c)
                if k <= 0:
                    rep['grounded'].append((f, c, claimed, 'rank 0')); continue
                acc = None
                for v, mr, _rt in cs:
                    if mr < k: acc = join(lt, acc, v)
                if not leq(lt, claimed, acc):
                    if any(_rt for _v, _mr, _rt in cs):
                        raise Unsupported('⊤ の前の値が要る（場 %d 升 %d）' % (f, c))
                    rep['grounded'].append((f, c, claimed, acc))
        for (f, c), tt in total.items():
            if c not in self.S[f] and tt:
                rep['stability'].append((f, c, tt, 'missing'))
        return rep


class Unsupported(Exception): pass
class TopRead(Exception): pass
OUT = object()                 # 座標はあるが広さの外（升は ⊥）
TOP = object()                 # 値の ⊤（flat の 2147483646 の読み）。数の 2147483646 とは別


def join(lt, a, b):
    if a is None: return b
    if b is None: return a
    if lt == 'min': return min(a, b)
    if lt in ('max', 'or'): return max(a, b)
    if lt == 'flat': return a if a == b else TOPV
    raise ValueError(lt)


def leq(lt, a, b):
    """a ⊑ b（None は ⊥）"""
    if a is None: return True
    if b is None: return False
    return join(lt, a, b) == b


def check(tab_blob, vals, ranks, data):
    tab = Tables(tab_blob)
    if tab.badk != -1:
        return dict(verdict='unbakeable', badk=tab.badk)
    lay, S, K = decode(tab, vals, ranks)
    ck = Checker(tab, lay, S, K, rows_of(tab, data))
    try: rep = ck.run()
    except Unsupported as e: return dict(verdict='unsupported', why=str(e))
    ok = not (rep['stability'] or rep['grounded'] or rep['outside'])
    rep['verdict'] = 'attested' if ok else 'rejected'
    return rep
