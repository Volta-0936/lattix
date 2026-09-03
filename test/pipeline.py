# -*- coding: utf-8 -*-
"""**二段の通し運転 —— front.lx の表を、そのまま run.lx に食わせて走らせる。**

   これまで front.lx の表は flat.py と突き合わせるだけだった（test/front.py）。
   ここでは flat.py を **表の経路から外す**:

       源のバイト → front.lx（焼いた Lattix） → 家の表
                                   ↓
                    run.lx（焼いた Lattix） → 最小不動点 → 答え

   Python が持つのは結線（表を運ぶ）と審判（lattix.py の解釈実行と比べる）
   だけである。flat.py は升の名前を戻す観測にだけ使う —— 表そのものは
   一行も作らない。**これが §0 の最終形の初めての通し運転である。**

   使い方:  python3 test/pipeline.py [本…]     （省略時は front.py の BOOKS）
"""
import os, sys, time, signal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))
sys.path.insert(0, os.path.join(ROOT, 'test'))

import front as F                       # 組み立て器と BOOKS を借りる
import lattix as L
import runtime as R
import engine2
from engine2 import tbl, answers
from flat import flatten, PLANE
import baked as B

W = 84
BIG = 10 ** 9
LIMIT = 420


def compact(fg, fc, fp, maps, sszr):
    """組み立て器が合成規則の枠に配った仮の番地（BIG+…）を、機械の
    bound に収まる実番地へ詰め直す。famnorm はラベル自由だが機械は
    配列で引く —— 番地は npa、写像の番号は nmp の中でなければならない。"""
    top = 1
    for r in fp:
        if r[5] < BIG: top = max(top, r[5] + 1)
    for m, row in maps.items():
        if m < BIG:
            for k in (11, 14):
                if row[k] and row[k] < BIG: top = max(top, row[k] + 1)
    bmap = {}
    for r in fp:                        # 出現順に、規則の点数ぶんの帯を取る
        if r[5] >= BIG and r[5] not in bmap:
            n = max(1, sszr.get(r[0], 1))
            bmap[r[5]] = top; top += n
    fix = lambda b: bmap.get(b, b)
    fp2 = [r[:5] + (fix(r[5]), r[6], r[7], fix(r[8]), fix(r[9]), r[10])
           for r in fp]
    mtop = max((m for m in maps if m < BIG), default=0) + 1
    mmap = {}
    for m in sorted(maps):
        if m >= BIG:
            mmap[m] = mtop; mtop += 1
    maps2 = {}
    for m, row in maps.items():
        row = list(row)
        row[11] = fix(row[11]); row[14] = fix(row[14])
        maps2[mmap.get(m, m)] = tuple(row)
    fixm = lambda m: mmap.get(m, m)
    fg2 = [r[:6] + (fixm(r[6]), fixm(r[7]), fixm(r[8]), fixm(r[9])) for r in fg]
    fc2 = [r[:5] + (fixm(r[5]), r[6], r[7], fixm(r[8]), fixm(r[9]),
                    fixm(r[10])) for r in fc]
    return fg2, fc2, fp2, maps2


def one(info, path):
    ref, p = answers(path)                       # 審判（定義の解釈実行）
    fl, _ = flatten(path, engine2.close_upto)    # 観測（升の名前と口の写し）
    if fl.nofam: return 'skip', f"参照が家にしない: {fl.nofam[0][0][:30]}"
    dat, spc, ssz, g = F.run_front(path, F.oracle(fl), F.extrows(fl))
    fg, fc, fp, maps = F.front_family(g)
    sszr = {r: v for (r,), v in g('zsszr').items()}
    fg, fc, fp, maps = compact(fg, fc, fp, maps, sszr)
    t = {'eg': [], 'cd': [], 'ix': [],
         'dat': [list(r) for r in dat],
         'spc': [list(r) for r in spc],
         'ssz': [list(r) for r in ssz],
         'mp': [[m] + list(row) for m, row in sorted(maps.items())],
         'fg': [list(r) for r in fg],
         'fc': [list(r) for r in fc],
         'fp': [list(r) for r in fp]}
    zatbv = g('zatb').get((0,))
    t['ate'] = (sorted([zatbv + i, e1, g('zate2')[(i,)]]
                       for (i,), e1 in g('zate1').items()) if zatbv else [])
    for n in B.NAMES:
        if not t[n]:                             # 空の表は番兵一行
            t[n] = [{'eg': [0]*10, 'cd': [0, 0, 999, 0, 0, 0, 0, 0, 0, 0],
                     'ix': [0]*6, 'dat': [0]*3, 'spc': [0]*5, 'ssz': [0, 1],
                     'mp': [0]*17, 'fg': [0, 0, 999, 0, 0, 0, 0, 0, 0, 0],
                     'fc': [0, 0, 999, 0, 0, 0, 0, 0, 0, 0, 0],
                     'fp': [0, 0, 999, 0, 0, 0, 0, 0, 0, 0, 0],
                     'ate': [0, 999, 0]}[n]]
    src = B.enginesrc("".join(tbl(n, t[n]) for n in B.NAMES))
    q = L.parse(src)
    d = R.write_data(q, os.path.join(info['dir'], 'data.lxd'))
    t0 = time.time(); got, _meta = R.run(info['exe'], d)
    ms = (time.time() - t0) * 1000
    out = {}
    for lt in set(r[3] for r in fg if r[2] != 999) | {5}:
        if lt not in PLANE: continue
        pl = PLANE[lt][0]
        for (sx, c), v in got.get(f'v{pl}', {}).items():
            if sx != B.NS - 1: continue
            try: f, keys = fl.name_of(c)
            except (KeyError, IndexError): continue
            out.setdefault(f, {})[keys] = fl.obs(v, f)
    for f in (p.prints or list(p.fields)):
        if dict(ref.get(f, {})) != out.get(f, {}):
            return 'diff', f
    return 'ok', f"{ms:.0f} ms"


if __name__ == '__main__':
    print("=" * W)
    print("  二段の通し運転 —— front.lx の表を run.lx が走らせる（表の経路に Python は居ない）")
    print("=" * W)
    info, sec = B.bake(os.path.join(ROOT, 'work', '_baked'))
    print(f"  焼いた: {sec:.0f}s   {os.path.getsize(info['exe']):,} バイト")
    print("-" * W)
    files = sys.argv[1:] or [os.path.join(ROOT, b) for b in F.BOOKS]
    def bell(sig, fr): raise TimeoutError()
    signal.signal(signal.SIGALRM, bell)
    ok = skip = bad = 0
    for f in files:
        signal.alarm(LIMIT)
        try:
            v, why = one(info, f)
        except TimeoutError: v, why = 'skip', f"{LIMIT}s で切った"
        except Exception as ex: v, why = 'diff', f"{type(ex).__name__}: {ex}"[:58]
        finally: signal.alarm(0)
        n = os.path.basename(f)
        if v == 'ok': ok += 1; print(f"  {n:<22} ✓  {why}", flush=True)
        elif v == 'skip': skip += 1; print(f"  {n:<22} —  {why}", flush=True)
        else: bad += 1; print(f"  {n:<22} ✗  {why}", flush=True)
    print("-" * W)
    print(f"  一致 {ok} / 未対応 {skip} / 食い違い {bad}")
    print("  **前段も走らせる側も Lattix である。** Python は結線と審判だけになった。")
    print("=" * W)
    sys.exit(1 if bad else 0)
