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


def run_front(path):
    """front.lx を焼いた測定器で走らせ、家の表（dat/spc/ssz）を読み出す。"""
    data = open(path, 'rb').read()
    rows = [(i, c) for i, c in enumerate(data)] + [(len(data), 32)]
    if SLOW:
        src = re.sub(r"table ch = .*?\n",
                     "table ch = " + ", ".join(f"({i},{c})" for i, c in rows) + "\n",
                     SRC, count=1)
        o = ns['go'](src)
    else:
        o = ns['cgo']('front', SRC, {'ch': rows})
    g = lambda f: dict(o(f))
    dat = sorted((k[0], k[1], v) for k, v in g('zdat').items())
    spb, spw, sps = g('zspb'), g('zspw'), g('zsps')
    spc = sorted((sp, j, spb[(sp, j)], spw[(sp, j)], sps[(sp, j)])
                 for (sp, j) in spb)
    ssz = sorted((k[0], v) for k, v in g('zssz').items())
    return dat, spc, ssz


def run_flat(path):
    fl, _ = flatten(path, engine2.close_upto)
    t = fl.tables()
    return (sorted(map(tuple, t['dat'])), sorted(map(tuple, t['spc'])),
            sorted(map(tuple, t['ssz'])), fl)


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
    return sorted(regions.values()), sorted(spaces.values()), leftover


def diff(a, b):
    ra, sa, la = a
    rb, sb, lb = b
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
    'examples/26_reach.lx',
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
            dat2, spc2, ssz2, fl = run_flat(f)
            if fl.nofam:
                skip += 1
                print(f"  {n:<22} —  参照が家にしない: {fl.nofam[0][0][:40]}", flush=True)
                continue
            got = normalize(*run_front(f))
            want = normalize(dat2, spc2, ssz2)
            why = diff(got, want)
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
