# -*- coding: utf-8 -*-
"""**閉じの器を外す —— pass を座標にする（第A段 A.3）。**

   前段は二つの口を持っていた。`orc`（区間の上端になる閉じた値）と
   `ext`（値で決まる座標の測った広さ）である。どちらも「その本を走らせて
   みないと分からない」ものなので、いままで **C の測定器**（engine2.close_upto）
   が閉じていた。だが走らせる物は既にある —— **run.lx** である。

       一巡目 front（口なし・静かな見積り） → 表 → run.lx → 面
       口 ＝ その面から読む（閉じた値・触れた升の広さ）
       二巡目 front（測った口）            → 表 → run.lx → 答え

   一巡目と二巡目は別の走行ではなく、**同じ不動点の層 0 と層 1** である
   （p は座標であって時間ではない）。ここでは結線を Python が持っているが、
   **閉じの器はもう居ない**。置き場を戻すのも前段自身の置き場の場で行う
   （flat.py の name_of を使わない）。

   使い方:  python3 test/twopass.py [本…]
"""
import os, sys, time, signal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))
sys.path.insert(0, os.path.join(ROOT, 'test'))
os.environ.setdefault('LATTIX_FAMILY_MIN', '1')
# **置き場も前段が言う。** 突き合わせが読む場に、前段の置き場の場を足す
# （flat.py の lay / name_of を使わないための口）。
os.environ['FRONT_EXTRA'] = ','.join(filter(None, [
    os.environ.get('FRONT_EXTRA', ''),
    'zfb,zfna,zfs0,zfs1,zflo0,zflo1,zflo2,zfsz0,zfsz1,zfsz2,zamx,zlatf']))

import front as F
import pipeline as P
import lattix as L
import runtime as R
import baked as B
from engine2 import tbl, answers, Rejected
from flat import PLANE

W = 84
LIMIT = int(os.environ.get("LATTIX_LIMIT", "600"))


class Lay:
    """**前段が出した置き場**（基・下端・広さ・歩幅・次数）。flat.py は見ない。"""
    def __init__(self, g):
        one = lambda n: {k[0]: v for k, v in g(n).items()}
        self.b = one('zfb'); self.ar = one('zfna')
        self.lo = [one(f'zflo{d}') for d in range(3)]
        self.sz = [one(f'zfsz{d}') for d in range(3)]
        self.s = [one('zfs0'), one('zfs1'), {}]
        self.order = sorted((b, f) for f, b in self.b.items())

    def cell(self, f, keys):
        c = self.b[f]
        for d, k in enumerate(keys):
            c += (k - self.lo[d].get(f, 0)) * (self.s[d].get(f, 1) if d < 2 else 1)
        return c

    def name_of(self, c):
        """升 → (場, 座標)。基は場の順位に沿った前置きの鎖なので二分探索。"""
        import bisect
        i = bisect.bisect_right(self.order, (c, 1 << 62)) - 1
        if i < 0: raise KeyError(c)
        b, f = self.order[i]
        off = c - b
        ar = self.ar.get(f, 1)
        if ar == 0: return f, ()
        w = [self.sz[d].get(f, 1) for d in range(ar)]
        st = [self.s[d].get(f, 1) if d < 2 else 1 for d in range(ar)]
        if off >= (w[0] * st[0] if st[0] else 1): raise KeyError(c)
        keys = []
        for d in range(ar):
            k, off = (off // st[d], off % st[d]) if st[d] else (off, 0)
            if k >= w[d]: raise KeyError(c)
            keys.append(k + self.lo[d].get(f, 0))
        return f, tuple(keys)


def machine(info, g, dat, spc, ssz):
    """前段の場から表を組み立て、run.lx（焼いた一枚）に食わせる。"""
    fg, fc, fp, maps = F.front_family(g)
    sszr = {r: v for (r,), v in g('zsszr').items()}
    fg, fc, fp, maps = P.compact(fg, fc, fp, maps, sszr)
    t = {'eg': [], 'cd': [], 'ix': [],
         'dat': [list(r) for r in dat], 'spc': [list(r) for r in spc],
         'ssz': [list(r) for r in ssz],
         'mp': [[m] + list(row) for m, row in sorted(maps.items())],
         'fg': [list(r) for r in fg], 'fc': [list(r) for r in fc],
         'fp': [list(r) for r in fp]}
    zatbv = g('zatb').get((0,))
    t['ate'] = (sorted([zatbv + i, e1, g('zate2')[(i,)]]
                       for (i,), e1 in g('zate1').items()) if zatbv else [])
    for n in B.NAMES:
        if not t[n]:
            t[n] = [{'eg': [0]*10, 'cd': [0, 0, 999, 0, 0, 0, 0, 0, 0, 0],
                     'ix': [0]*6, 'dat': [0]*3, 'spc': [0]*5, 'ssz': [0, 1],
                     'mp': [0]*17, 'fg': [0, 0, 999, 0, 0, 0, 0, 0, 0, 0],
                     'fc': [0, 0, 999, 0, 0, 0, 0, 0, 0, 0, 0],
                     'fp': [0, 0, 999, 0, 0, 0, 0, 0, 0, 0, 0],
                     'ate': [0, 999, 0]}[n]]
    src = B.enginesrc("".join(tbl(n, t[n]) for n in B.NAMES))
    q = L.parse(src)
    d = R.write_data(q, os.path.join(info['dir'], f'data.{os.getpid()}.lxd'))
    got, _m = R.run(info['exe'], d)
    lats = set(r[3] for r in fg if r[2] != 999) | {5}
    return got, lats


def planes(got, lats, lay):
    """機械の面 → {場番号: {座標: 値}}（前段の置き場で戻す）。"""
    out = {}
    for lt in lats:
        if lt not in PLANE: continue
        for (sx, c), v in got.get(f'v{PLANE[lt][0]}', {}).items():
            if sx != B.NS - 1: continue
            try: f, keys = lay.name_of(c)
            except (KeyError, IndexError): continue
            out.setdefault(f, {})[keys] = v
    return out


def measured(seen, dyn, syn, fnum):
    """一巡目の面から口 `ext` を作る —— **触れた升が広さを言う**。"""
    rows = []
    for f, d in sorted(dyn | {(s, d) for s in syn for d in range(3)}):
        i = fnum.get(f)
        if i is None or i not in seen: continue
        ks = [k[d] for k in seen[i] if len(k) > d]
        if not ks: continue
        rows.append((i, d, min(ks), max(ks) - min(ks) + 1))
    return sorted(set(rows))


def closedrows(fl_p, seen, fnum):
    """一巡目の面から口 `orc` を作る —— 区間の上端に出てくる閉じた升。"""
    def frefs(e):
        if not isinstance(e, tuple): return
        if e[0] == 'fref': yield e
        for x in e[1:]:
            if isinstance(x, tuple): yield from frefs(x)
            elif isinstance(x, list):
                for y in x: yield from frefs(y)
    rows = []
    for r in fl_p.rules:
        for _vs, srcx in (r.sources or []):
            if not (isinstance(srcx, tuple) and srcx[0] == '..'): continue
            for e in list(frefs(srcx[1])) + list(frefs(srcx[2])):
                i = fnum.get(e[1])
                if i is None or i not in seen: continue
                keys = tuple(k[1] if k[0] == 'int' else 0 for k in e[2])
                # 添字なしの場（`n[]`）は前段では一次元の升 0 に居る
                v = seen[i].get(keys if keys else (0,))
                if isinstance(v, int): rows.append((i, keys[0] if keys else 0, v))
                if any(k[0] != 'int' for k in e[2]):
                    vs = [w for w in seen[i].values() if isinstance(w, int)]
                    if vs: rows.append((i, 63, max(vs)))
    return sorted(set(rows))


def one(info, path):
    ref, p = answers(path)                    # 審判（定義の解釈実行）
    class Shim: pass
    sh = Shim(); sh.p = p
    fnum, syn = F.frontnum(sh)
    dyn = {(f, d) for f, d in F._dynd(sh)} if hasattr(F, '_dynd') else set()

    t0 = time.time()
    # **巡の数は二ではない —— 広さの鎖の高さである。**
    # 参照（flat.py）は一巡目に 2^62 の仮の帯を敷けるので二巡で足りる。
    # 機械は升の番号に宣言した上限があるので、仮の帯を敷く代わりに
    # **測って広げる**。広さは単調に増えるだけなので、止まるところが不動点。
    # 一巡目の仮の広さ。**測る前に落とさないため**の帯である —— 値で決まる
    # 座標（`form[icount[] + 1]`）は静的な区間算術の外に書くので、静的な広さで
    # 一巡目を走らせると **黙って落ちて**、広さが育たない（不動点が動かない）。
    # 参照は 2^62 の帯を敷けるが、機械の升には宣言した上限があるので
    # 「広いが有限」の帯を敷く（超えたら run.lx の zov が言う）。
    PROV = int(os.environ.get('LATTIX_PROV', 1 << 20))
    ext = sorted({(fnum[f], d, 0, PROV) for f, d in dyn if f in fnum})
    orc, rounds = None, 0
    while True:
        rounds += 1
        dat, spc, ssz, g = F.run_front(path, orc, ext)
        lay = Lay(g)
        got, lats = machine(info, g, dat, spc, ssz)
        seen = planes(got, lats, lay)
        e2 = [(1022, 0, g('zamx').get((0,), 0), 1)] + measured(seen, dyn, syn, fnum)
        o2 = closedrows(p, seen, fnum) or [(0, 0, -1)]
        # 広さは縮めない（測りは join である）
        if ext:
            w = {(f, d): (lo, wd) for f, d, lo, wd in ext}
            for f, d, lo, wd in e2:
                if (f, d) in w:
                    l0, w0 = w[(f, d)]
                    lo2 = min(lo, l0); w[(f, d)] = (lo2, max(lo + wd, l0 + w0) - lo2)
                else: w[(f, d)] = (lo, wd)
            e2 = sorted((f, d, lo, wd) for (f, d), (lo, wd) in w.items())
        if (e2, o2) == (ext, orc) or rounds >= 6:
            out2, lay1 = seen, lay
            break
        ext, orc = e2, o2
    ms = (time.time() - t0) * 1000

    inv = {i: f for f, i in fnum.items()}
    # 原子は番号である（綴りの順）。**審判の側**で綴りに戻す —— 前段が配った
    # 基（zatb）と、記述に現れる綴りの順（参照の parse と同じ判断）で引く。
    from flat import _allatoms
    atb = g('zatb').get((0,))
    atl = _allatoms(p)
    unat = lambda x: (atl[x - atb] if isinstance(x, int) and atb
                      and atb <= x < atb + len(atl) else x)
    obs = {}
    for i, cells in out2.items():
        f = inv.get(i)
        if f is None: continue
        for keys, v in cells.items():
            obs.setdefault(f, {})[tuple(unat(k) for k in keys)] = v
    nv = 0
    for f in (p.prints or list(p.fields)):
        want = {(k if k else (0,)): v for k, v in ref.get(f, {}).items()}
        gotf = obs.get(f, {})
        if set(want) != set(gotf):
            miss = sorted(set(want) - set(gotf))[:2]
            extra = sorted(set(gotf) - set(want))[:2]
            return 'diff', f"{f}: 升が違う 足りない {miss} 余分 {extra}"
        for k, v in want.items():          # 数の升は値まで見る（真偽・原子・⊤ は形が違う）
            if isinstance(v, int) and not isinstance(v, bool):
                nv += 1
                if gotf[k] != v: return 'diff', f"{f}{list(k)}: {gotf[k]} ≠ {v}"
    return 'ok', f"{ms:.0f} ms  {rounds} 巡  口 orc {len(orc or [])} / ext {len(ext or [])} / 数の升 {nv}"


if __name__ == '__main__':
    print("=" * W)
    print("  二巡の通し運転 —— 口は **機械の面**から。閉じの器は居ない")
    print("=" * W)
    info, sec = B.bake(os.path.join(ROOT, 'work', '_baked'))
    print(f"  焼いた: {sec:.0f}s")
    print("-" * W)
    def bell(s, f): raise TimeoutError()
    signal.signal(signal.SIGALRM, bell)
    ok = bad = skip = 0
    for path in sys.argv[1:]:
        n = os.path.basename(path)
        signal.alarm(LIMIT)
        try:
            v, why = one(info, os.path.join(ROOT, path))
        except Rejected as ex: v, why = 'skip', f"参照が断る本: {str(ex)[:40]}"
        except TimeoutError: v, why = 'diff', f"{LIMIT}s で切った"
        except Exception as ex: v, why = 'diff', f"{type(ex).__name__}: {ex}"[:70]
        finally: signal.alarm(0)
        if v == 'ok': ok += 1; print(f"  {n:<22} ✓  {why}", flush=True)
        elif v == 'skip': skip += 1; print(f"  {n:<22} —  {why}", flush=True)
        else: bad += 1; print(f"  {n:<22} ✗  {why}", flush=True)
    print("-" * W)
    print(f"  一致 {ok} / 断る本 {skip} / 食い違い {bad}")
    print("=" * W)
    sys.exit(1 if bad else 0)
