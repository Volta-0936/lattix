#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**前段を Lattix にする（第2段）の突き合わせ。**

    33_self.lx + lib/fold.lx + front.lx   源のバイト → 家の表
    work/flat.py                           同じ源     → 家の表（参照）

二つが出す dat / spc / ssz を比べる。番号づけ（軸・空間の並び）は
どちらも自由なラベルなので、**中身で正規化してから**比べる ——
軸はその中身（行の集合）が名前で、空間はその軸の列が名前である。
ラベルが違って中身が同じなら一致、中身が違えば食い違いである。

走らせ方: C の測定器で一度焼き、本ごとに表（ch）だけ差し替える
（selfgen.cgo と同じ。焼き直すのは front.lx を書き換えたときだけ）。
LATTIX_SLOW=1 で解釈実行に切り替え（遅いが、途中の場が見える）。
"""
import os, re, sys, glob

os.environ.setdefault('LATTIX_FAMILY_MIN', '1')     # 参照側も家を強制する
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))

import engine2
from flat import flatten

W = 84
SLOW = os.environ.get('LATTIX_SLOW') == '1'

# selfgen の cgo（焼いて表を差し替える）をそのまま借りる
sg = open(os.path.join(ROOT, 'test', 'selfgen.py'), encoding='utf-8').read()
ns = {'__name__': 'notmain', '__file__': os.path.join(ROOT, 'test', 'selfgen.py')}
exec(compile(sg[:sg.index("tmp = tempfile.mkdtemp()")], 'selfgen', 'exec'), ns)


def assemble():
    self_ = open(os.path.join(ROOT, 'examples', '33_self.lx'), encoding='utf-8').read()
    self_ = "\n".join(l for l in self_.splitlines() if not l.startswith('print '))
    fold = open(os.path.join(ROOT, 'lib', 'fold.lx'), encoding='utf-8').read()
    front = open(os.path.join(ROOT, 'front.lx'), encoding='utf-8').read()
    front = "\n".join(l for l in front.splitlines() if not l.startswith('print '))
    src = self_ + "\n" + fold + "\n" + front
    return re.sub(r"table ch = .*?\n", "table ch = (0,32)\n", src, count=1)


SRC = assemble()


def _dynd(fl):
    """値で決まる座標を持つ (場, 次元) —— 広さは走らせて測るしかないので、
    測った置き場を口（ext）から渡す（BSP の継ぎ目。orc と同じ判断）。"""
    from flat import _frefs
    dyn = set()
    def keyd(f, keys):
        for d, k in enumerate(keys):
            if isinstance(k, tuple) and any(True for _ in _frefs(k)):
                dyn.add((f, d))
            walk(k)
    def walk(e):
        if not isinstance(e, tuple) or not e: return
        if e[0] == 'fref':
            keyd(e[1], e[2]); return
        for x in e[1:]:
            if isinstance(x, tuple): walk(x)
            elif isinstance(x, list):
                for y in x: walk(y)
    for r in fl.p.rules:
        keyd(r.target, r.keys)
        # 座標に升の読みが一つでもあれば、その規則は一巡目を **点で測る**
        # （flat.py の measuring の門と同じ判断）。点で測った広さは静的な
        # 区間算術では出ない —— 書き先の **全次元**を口から渡す。
        if any(isinstance(k, tuple) and any(True for _ in _frefs(k))
               for k in r.keys):
            for d in range(len(r.keys)):
                dyn.add((r.target, d))
        walk(r.value)
        for q in r.guards: walk(q)
        for _vs, srcx in (r.sources or []):
            if isinstance(srcx, tuple): walk(srcx)
    return dyn


def frontnum(fl):
    """前段の場番号: 宣言された場、_size、構成子の宣言順に引数場
    （参照実装は構成子の行で引数場を先に番号づける —— 口はこちらの番号で話す）。"""
    named = list(fl.p.fields)
    syn = {'_size'} | {f"{nm}_{f}" for nm, (fs, _bd) in fl.p.ctors.items()
                       for f in fs}
    decl = [f for f in named if f not in syn]
    fnum = {f: i for i, f in enumerate(decl)}
    nf0 = len(decl)
    fnum['_size'] = nf0
    base = nf0 + 1
    for nm, (fs, _bd) in fl.p.ctors.items():
        for k, f in enumerate(fs):
            fnum[f"{nm}_{f}"] = base + k
        base += len(fs)
    return fnum, syn


def extrows(fl):
    """合成の場（_size と 引数場）の測った置き場を、走らせた側の口として渡す。"""
    fnum, syn = frontnum(fl)
    rows = [(1022, 0, fl.ATOMB - 1, 1)]      # 数の上端の印（原子の基 − 1）
    for f in syn:
        if f not in fl.lay: continue
        b, sz, st, lo = fl.lay[f]
        for d in range(len(sz)):
            rows.append((fnum[f], d, lo[d], sz[d]))
    for f, d in sorted(_dynd(fl)):           # 値で決まる座標の次元も口から
        if f not in fl.lay or f not in fnum or f in syn: continue
        b, sz, st, lo = fl.lay[f]
        if d < len(sz):
            rows.append((fnum[f], d, lo[d], sz[d]))
    return sorted(set(rows))


def oracle(fl):
    """区間の上端に出てくる閉じた升（場, 座標, 値）。走らせた側の口の写し。"""
    def frefs(e):
        if not isinstance(e, tuple): return
        if e[0] == 'fref':
            yield e
        for x in e[1:]:
            if isinstance(x, tuple): yield from frefs(x)
            elif isinstance(x, list):
                for y in x: yield from frefs(y)
    fnum, _syn = frontnum(fl)
    rows = []
    for r in fl.p.rules:
        for _vs, srcx in (r.sources or []):
            if isinstance(srcx, tuple) and srcx[0] == '..':
                for e in list(frefs(srcx[1])) + list(frefs(srcx[2])):
                    keys = tuple(k[1] if k[0] == 'int' else 0 for k in e[2])
                    v = fl.closed.get((e[1], keys))
                    if v is not None:
                        rows.append((fnum[e[1]], keys[0] if keys else 0, int(v)))
                    if any(k[0] != 'int' for k in e[2]):
                        # 依存する区間の端 —— 場の **最大**を座標 63 で渡す
                        # （flat の _bmax と同じ判断: 閉じたどの面からでも）
                        vs = [w for (f, _k), w in getattr(fl, 'closedany', {}).items()
                              if f == e[1] and isinstance(w, int)]
                        vs += [w for (f, _k), w in fl.closed.items()
                               if f == e[1] and isinstance(w, int) and not isinstance(w, bool)]
                        if vs: rows.append((fnum[e[1]], 63, max(vs)))
    return sorted(set(rows)) or [(0, 0, -1)]


def run_front(path, orc=None, ext=None):
    """front.lx を焼いた測定器で走らせ、家の表を読み出す。"""
    data = open(path, 'rb').read()
    if b'include ' in data:
        # include は字面の取り込み（lattix.py の parse と同じ前処理）——
        # 前段が読むのは取り込んだ後の本文。配る側もこの一枚を渡す。
        import lattix
        data = lattix._expand_includes(data.decode('utf-8'),
                                       os.path.dirname(path)).encode('utf-8')
    rows = [(i, c) for i, c in enumerate(data)] + [(len(data), 32)]
    orc = orc or [(0, 0, -1)]
    ext = ext or [(0, 0, 0, 0)]
    if SLOW:
        src = re.sub(r"table ch = .*?\n",
                     "table ch = " + ", ".join(f"({i},{c})" for i, c in rows) + "\n",
                     SRC, count=1)
        src = re.sub(r"table orc = .*?\n",
                     "table orc = " + ", ".join(str(r) for r in orc) + "\n",
                     src, count=1)
        src = re.sub(r"table ext = .*?\n",
                     "table ext = " + ", ".join(str(r) for r in ext) + "\n",
                     src, count=1)
        o = ns['go'](src)
    else:
        o = ns['cgo']('front', SRC, {'ch': rows, 'orc': orc, 'ext': ext})
    g = lambda f: dict(o(f))
    dat = sorted((k[0], k[1], v) for k, v in g('zdat').items())
    spb, spw, sps = g('zspb'), g('zspw'), g('zsps')
    spc = sorted((sp, j, spb[(sp, j)], spw[(sp, j)], sps[(sp, j)])
                 for (sp, j) in spb)
    ssz = sorted((k[0], v) for k, v in g('zssz').items())
    return dat, spc, ssz, g


def front_family(g):
    """front.lx の場から fg/fc/fp/写像 を組み立てる（0 は居ない部品の埋め草）。"""
    zmu = g('zmu')
    c = {n: g(n) for n in ('zmc', 'zmn', 'zmj0', 'zmc0', 'zmm0', 'zmj1', 'zmc1',
                           'zmm1', 'zmj2', 'zmc2', 'zmm2', 'zmia', 'zmib',
                           'zmiu', 'zmia2', 'zmib2', 'zmiu2')}
    maps = {}
    for (m,) in zmu:
        v = lambda n: c[n].get((m,), 0)
        maps[m] = (v('zmc'), v('zmj0'), v('zmc0'), v('zmm0'),
                   v('zmj1'), v('zmc1'), v('zmm1'), v('zmj2'), v('zmc2'),
                   v('zmm2'), v('zmia'), v('zmib'), v('zmiu'),
                   v('zmia2'), v('zmib2'), v('zmiu2'))
    st, lat, vf, nsv = g('zfgst'), g('zfglat'), g('zfgvf'), g('zfgns')
    spof, sszr = g('zspof'), g('zsszr')
    hasa = g('zhasa')
    fg = []
    for (r,) in st:
        n = nsv.get((r,), 0)
        zero = r * 128 + 4
        am = r * 128 + 1 if hasa.get((r,)) else zero
        am = g('zfgam').get((r,), am)
        bm = r * 128 + 2 if n == 2 else zero
        wm = g('zwm').get((r,), zero)
        fg.append((r, spof[(r,)], st[(r,)], lat[(r,)], vf.get((r,), 0), n,
                   r * 128, am, bm, wm))
    zfck, zfclt, zfcam, zfcop, zfcwm = (g('zfck'), g('zfclt'), g('zfcam'),
                                        g('zfcop'), g('zfcwm'))
    zrnm = g('zrn')
    fc = []
    for (s, i), k in zfck.items():
        r = zrnm.get((s,))
        if r is None: continue
        zero = r * 128 + 4
        fc.append((r, spof[(r,)], st[(r,)], k, zfclt.get((s, i), 0),
                   zfcam[(s, i)], zfcop.get((s, i), 0), 0, zero, zero,
                   zfcwm.get((s, i), zero)))
    zfpu, zfplt, zfpb, zfpam = g('zfpu'), g('zfplt'), g('zfpb'), g('zfpam')
    zfpk, zfpmo, zfpsr = g('zfpk'), g('zfpmo'), g('zfpsr')
    zfps2, zfpx = g('zfps2'), g('zfpx')
    fp = []
    for (r, u) in zfpu:
        fp.append((0, spof[(r,)], st[(r,)], zfpk.get((r, u), 0),
                   zfplt[(r, u)], zfpb[(r, u)], zfpam[(r, u)],
                   zfpmo.get((r, u), 0), zfpsr.get((r, u), 0),
                   zfps2.get((r, u), 0), zfpx.get((r, u), 0)))
    # 合成規則は host のガードを継ぐ（写像は内容で共有される）——
    # ただし種1 の読みの枠は **合成規則の層で閉じ方を見直す**。_size は
    # 書き手の最大層へ持ち上がるので、host では生きていた読み（負の束）が
    # 合成の層では閉じている（正の束）。flat.py は合成規則の fcond を
    # その層で引き直すのと同じ判断である。
    zsyrr = g('zsyrr')
    zrs = {r: s for (s,), r in zrnm.items()}
    zglfd, zgcfd, zgch = g('zglfd'), g('zgcfd'), g('zgch')
    zgflfd = g('zgflfd')
    zlatf, zfws = g('zlatf'), g('zfws')
    BIG = 10 ** 9
    hostfc = {}
    for row in fc: hostfc.setdefault(row[0], []).append(row)
    for (rp,), rh in zsyrr.items():
        sh = zrs.get(rh)
        for row in hostfc.get(rh, []):
            row2 = (rp, spof[(rp,)], st[(rp,)]) + row[3:]
            cam = row[5]
            i = (cam % 128 - 8) // 3
            if (row[3] == 1 and sh is not None and 0 <= i < 8
                    and (rh, 32 + i) in zfpu):
                ch = zgch.get((sh, i))
                fd = (zgcfd.get((sh, i)) if ch else
                      zglfd.get((sh, i), zgflfd.get((sh, i))))
                if fd is not None:
                    lat = zlatf[(fd,)]
                    lt = lat if zfws.get((fd,), 0) <= st[(rp,)] - 1 else -lat
                    b32 = BIG + rp * 64 + 32 + i
                    fp.append((0, spof[(rp,)], st[(rp,)], 0, lt, b32,
                               zfpam[(rh, 32 + i)], 0, 0, 0, 0))
                    tb = b32
                    if ch and (rh, 56 + i) in zfpu:
                        tb = BIG + rp * 64 + 56 + i
                        fp.append((0, spof[(rp,)], st[(rp,)], 3, 0, tb,
                                   rh * 128 + 4, zfpmo[(rh, 56 + i)],
                                   b32, 0, 0))
                    mn = BIG + rp * 128 + cam % 128
                    mia = maps[cam][10]
                    maps[mn] = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, mia, tb, 1,
                                0, 0, 0)
                    row2 = row2[:5] + (mn,) + row2[6:]
            fc.append(row2)
    return fg, fc, fp, maps


def run_flat(path):
    fl, _ = flatten(path, engine2.close_upto)
    t = fl.tables()
    live = lambda rs: [tuple(r) for r in rs if len(r) > 2 and r[2] != 999]
    fg = [tuple(r) for r in t['fg'] if len(r) == 10]
    maps = {r[0]: tuple(r[1:]) for r in t['mp']}
    ate = sorted(tuple(r) for r in t['ate'] if r[1] != 999)
    return (sorted(map(tuple, t['dat'])), sorted(map(tuple, t['spc'])),
            sorted(map(tuple, t['ssz'])), fl,
            fg, live(t['fc']), live(t['fp']), maps, ate)


def paexp(b, maps, fpbyb, depth):
    fpr = fpbyb.get(b)
    if fpr is None: return ('?', b)
    if depth > 8: return ('deep',)
    if fpr[3] in (3, 4):
        return (fpr[3], fpr[7], paexp(fpr[8], maps, fpbyb, depth + 1))
    if fpr[3] == 2:
        return (2, paexp(fpr[8], maps, fpbyb, depth + 1),
                paexp(fpr[9], maps, fpbyb, depth + 1), fpr[10])
    if fpr[3] == 7:
        return (7, fpr[7], paexp(fpr[8], maps, fpbyb, depth + 1),
                paexp(fpr[9], maps, fpbyb, depth + 1), fpr[10])
    return (fpr[3], fpr[4], mapexp(fpr[6], maps, fpbyb, depth + 1))


def mapexp(mid, maps, fpbyb, depth=0):
    """写像の番号 → 中身（間接は番地の面の写しを再帰で開く）。"""
    if depth > 4: return ('deep',)
    row = maps[mid]
    const, slots = row[0], {}
    for k in range(3):
        j, c, m = row[1 + 3 * k], row[2 + 3 * k], row[3 + 3 * k]
        if m: slots[(j, c)] = slots.get((j, c), 0) + m
    slots = tuple(sorted((jc, m) for jc, m in slots.items() if m))
    inds = []
    for base in (10, 13):
        ia, ib, iu = row[base], row[base + 1], row[base + 2]
        if iu:
            inds.append((ia, paexp(ib, maps, fpbyb, depth)))
    return (const, slots, tuple(sorted(inds)))


def famnorm(fg, fc, fp, maps, spmap):
    """規則を中身で名づけ直す —— eid・写像番号・面の基はラベルである。"""
    fpbyb = {r[5]: r for r in fp}
    fcby = {}
    for r in fc: fcby.setdefault(r[0], []).append(r)
    out = []
    for row in fg:
        eid, sp, st, lat, vf, nsc = row[0], row[1], row[2], row[3], row[4], row[5]
        ex = lambda m: mapexp(m, maps, fpbyb)
        gs = sorted((q[3], q[4], ex(q[5]), q[6], q[7], ex(q[8]), ex(q[9]),
                     ex(q[10])) for q in fcby.get(eid, []))
        out.append((spmap.get(sp), st, lat, vf, nsc, ex(row[6]), ex(row[7]),
                    ex(row[8]), ex(row[9]), tuple(gs)))
    # 面の写しの「多重度」は比べない —— flat は規則ごとに写しを作り直し、
    # front は内容の同じ写しを共有することがある（どちらも答えは同じ）。
    loosefp = sorted(set(paexp(r[5], maps, fpbyb, 0) for r in fp))
    return sorted(out), loosefp


def normalize(dat, spc, ssz):
    """軸を中身で、空間を軸の列で名づけ直す。"""
    byrow = {}
    for r, c, v in dat: byrow.setdefault(r, []).append((c, v))
    regions = {}                                   # base -> (w, 中身の鍵)
    for sp, j, base, w, step in spc:
        if base not in regions:
            rows = []
            for r in range(base, base + w):
                rows.append(tuple(sorted(byrow.get(r, []))))
            regions[base] = (w, tuple(rows))
    used = set()
    for base, (w, _k) in regions.items():
        used.update(range(base, base + w))
    leftover = sorted((r, c, v) for r, c, v in dat if r not in used)
    spaces = {}                                    # sp -> 正規の鍵
    sz = dict(ssz)
    for sp in {r[0] for r in spc}:
        axes = sorted((j, regions[base][1], w, step)
                      for s2, j, base, w, step in spc if s2 == sp)
        spaces[sp] = (tuple(axes), sz.get(sp))
    return sorted(regions.values()), sorted(spaces.values()), leftover, spaces


def diff(a, b):
    ra, sa, la = a[:3]
    rb, sb, lb = b[:3]
    if ra != rb:
        for x, y in zip(ra, rb):
            if x != y: return f"軸: {str(x)[:38]} ≠ {str(y)[:38]}"
        return f"軸の数 {len(ra)} ≠ {len(rb)}"
    if sa != sb:
        for x, y in zip(sa, sb):
            if x != y: return f"空間: {str(x)[:36]} ≠ {str(y)[:36]}"
        return f"空間の数 {len(sa)} ≠ {len(sb)}"
    if la != lb: return f"余りの dat {len(la)} ≠ {len(lb)}"
    return None


BOOKS = [
    'work/t/a_min.lx', 'work/t/b_3term.lx', 'work/t/c_ge.lx', 'work/t/d_eq.lx',
    'work/t/e_ne.lx', 'work/t/f_two.lx', 'work/t/g_sub.lx', 'work/t/k_max.lx',
    'work/t/l_or.lx', 'work/t/m_orguard.lx', 'work/t/n_range.lx',
    'work/t/o_ctr.lx', 'work/t/p_nest.lx', 'work/t/q_ctrguard.lx',
    'work/t/r_fguard.lx', 'work/t/s_not.lx', 'work/t/u_cross.lx',
    'examples/01_shortest.lx', 'examples/03_time_axis.lx',
    'examples/26_reach.lx', 'examples/22_parse.lx',
    'work/t/x_sumstrata.lx', 'work/t/y_paseam.lx',
    'examples/08_belnap.lx', 'examples/18_ubound.lx', 'examples/27_elf.lx',
    'work/t/z_mixlat.lx', 'work/t/z_twoind.lx', 'work/t/v_poly.lx',
    'work/t/z_chain.lx', 'work/t/z_nestwm.lx', 'work/t/z_twoctor.lx',
    'examples/16_lex.lx', 'work/t/z_atomarg.lx', 'examples/35_noema.lx',
    'examples/20_lex_full.lx', 'examples/21_lex.lx',
    'examples/29_dataflow.lx', 'examples/17_render.lx', 'work/t/w_indir.lx',
    'examples/15_parse.lx', 'examples/19_mod.lx', 'examples/23_big.lx',
    'examples/34_decimal.lx', 'examples/02_strata.lx', 'examples/05_pipeline.lx',
    'examples/06_order_free.lx', 'examples/09_upset.lx',
    'examples/28_asm.lx', 'work/t/z_depint.lx', 'work/t/z_unit0.lx',
    'work/t/z_accread.lx', 'work/t/z_dim2rd.lx', 'examples/25_eval.lx',
]

if __name__ == '__main__':
    files = sys.argv[1:] or [os.path.join(ROOT, b) for b in BOOKS]
    print("=" * W)
    print("  前段の突き合わせ —— front.lx の家の表 と flat.py の家の表（dat/spc/ssz）")
    print("=" * W)
    ok = bad = skip = 0
    for f in files:
        n = os.path.basename(f)
        try:
            dat2, spc2, ssz2, fl, ffg, ffc, ffp, fmaps, fate = run_flat(f)
            if fl.nofam:
                skip += 1
                print(f"  {n:<22} —  参照が家にしない: {fl.nofam[0][0][:40]}", flush=True)
                continue
            dat1, spc1, ssz1, g = run_front(f, oracle(fl), extrows(fl))
            got = normalize(dat1, spc1, ssz1)
            want = normalize(dat2, spc2, ssz2)
            why = diff(got, want)
            if why is None:
                zatbv = g('zatb').get((0,))
                gate = sorted((zatbv + i, e1, g('zate2')[(i,)])
                              for (i,), e1 in g('zate1').items()) if zatbv else []
                if gate != fate:
                    why = f"ate: {str(gate)[:40]} ≠ {str(fate)[:40]}"
            if why is None:
                gfg, gfc, gfp, gmaps = front_family(g)
                a = famnorm(gfg, gfc, gfp, gmaps, got[3])
                b = famnorm(ffg, ffc, ffp, fmaps, want[3])
                if a != b:
                    fa, fb = a[0], b[0]
                    why = "fg/fc/fp: "
                    for x, y in zip(fa, fb):
                        if x != y:
                            why += f"{str(x)[:60]} ≠ {str(y)[:60]}"; break
                    else:
                        why += (f"規則の数 {len(fa)} ≠ {len(fb)}" if len(fa) != len(fb)
                                else f"面 {str(a[1])[:40]} ≠ {str(b[1])[:40]}")
        except Exception as ex:
            bad += 1
            print(f"  {n:<22} ✗  {type(ex).__name__}: {str(ex)[:52]}", flush=True)
            continue
        if why is None:
            ok += 1; print(f"  {n:<22} ✓", flush=True)
        else:
            bad += 1; print(f"  {n:<22} ✗  {why}", flush=True)
    print("-" * W)
    print(f"  一致 {ok} / 食い違い {bad} / 参照が家にしない {skip}")
    print("=" * W)
    sys.exit(1 if bad else 0)
