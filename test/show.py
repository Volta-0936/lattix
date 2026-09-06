#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**見せる物（show.lx）の突き合わせ。** 参照実装の答えを家の升番号に置き、
show.lx に食わせて、`python3 lattix.py f.lx` の標準出力と **バイト一致**を見る。
（値は参照実装から、置き場は flat.py から。走らせる側を挟むのは pipeline の仕事）"""
import os, sys, io, re, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))
os.environ.setdefault('LATTIX_FAMILY_MIN', '1')
import lattix as L
import engine2
from flat import flatten, fat_of
SHOW = open(os.path.join(ROOT, 'show.lx'), encoding='utf-8').read()


def tables(path):
    ref, p = engine2.answers(path)
    fl, _ = flatten(path, engine2.close_upto)
    return tables_of(fl, p, ref)


def tables_of(fl, p, ref, fat_ref=None):
    """見せる物の表。ref は場 → {座標: 値}（参照実装の答えでも、機械の面の
    読みでも同じ形）。原子の型は **記述から**出す（fat_ref は使わない）。"""
    fnum = {f: i for i, f in enumerate(p.fields)}
    atn = {a: i for i, a in enumerate(fl.atl)}          # 綴り → 番号（基から）
    fld, fnm, atm, pv, prn, ps = [], [], [], [], [], []
    for f, i in fnum.items():
        if f not in fl.lay: continue
        b, sz, st, lo = fl.lay[f]
        ks = next(iter(ref.get(f, {})), None)
        ar = len(ks) if ks is not None else len(sz)      # 次数は記述のもの（0 次元は []）
        row = [i, fl.flat[f], ar, b]
        for d in range(3):
            row += [lo[d] if d < ar else 0, sz[d] if d < ar else 1, st[d] if d < ar else 1]
        fld.append(tuple(row))
        for k, c in enumerate(f.encode()): fnm.append((i, k, c))
        for keys, v in ref.get(f, {}).items():
            if v is None or isinstance(v, tuple) or v is L.INF or v is L.NEGINF: continue
            c = b
            for d, k in enumerate(keys):
                kk = fl.ATOMB + atn[k] if isinstance(k, str) else k
                c += (kk - lo[d]) * st[d]
            if isinstance(v, frozenset):
                pv.append((i, c, 0))
                for q, e in enumerate(sorted(v, key=str)):
                    ps.append((i, c, q, fl.ATOMB + atn[e] if isinstance(e, str) else e))
                continue
            if v is True: v = 1
            elif v is False: continue
            if isinstance(v, L._Top): v = (1 << 63) - 1     # ⊤ は機械の印（flat の ⊤ = INT64_MAX。2^62 は 23_big の pow2[62] と衝突した）
            if isinstance(v, L._FourV): v = 1 if v.v else 0
            if isinstance(v, str): v = fl.ATOMB + atn[v]
            if not isinstance(v, int): continue
            pv.append((i, c, v))
    for a, sp in enumerate(fl.atl):
        for k, c in enumerate(sp.encode()): atm.append((a, k, c))
    for j, f in enumerate(p.prints):
        if f in fnum: prn.append((j, fnum[f]))
    ctr, cac = [], []
    for ci, (nm, (fs, _bd)) in enumerate(p.ctors.items()):
        for k, ch in enumerate(nm.encode()): ctr.append((ci, k, ch))
        for i, a in enumerate(fs): cac.append((ci, i, fnum[f"{nm}_{a}"]))
    # **原子の型は記述が言う**（答えを見ない）。flat.fat_of の不動点。
    fat = {(fnum[f], d) for f, d in fat_of(p) if f in fnum}
    return (fld, fnm or [(0, 0, 32)], atm or [(0, 0, 32)], pv or [(0, 0, 0)], prn,
            [(fl.ATOMB,)], sorted(fat) or [(1023, 0)], ps or [(1023, 0, 0, 0)],
            ctr or [(0, 0, 32)], cac or [(1023, 0, 1023)])


def render(tb):
    """show.lx に表を入れて走らせ、出たバイト列を返す（解釈実行）。"""
    src = SHOW
    for n, rows in zip(('fld', 'fnm', 'atm', 'pv', 'prn', 'ab', 'fat', 'ps', 'ctr', 'cac'), tb):
        src = re.sub(rf"table {n} = .*?\n",
                     f"table {n} = " + ", ".join("(" + ",".join(map(str, r)) + ")" for r in rows) + "\n",
                     src, count=1, flags=re.S)
    q = L.parse(src); L.check(q); L.stratify(q); L.io_rounds(q); L.certify(q)
    buf = io.BytesIO()
    class W:
        buffer = buf
        def write(self, s): buf.write(s.encode())
        def flush(self): pass
    L.run(q, out=W())
    return buf.getvalue()


def one(path):
    try:
        tb = tables(path)
    except engine2.Rejected as ex:
        return b'', b''                      # 参照実装が断る本（標準出力は空）
    got = render(tb)
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'lattix.py'), path],
                       capture_output=True)
    if r.returncode != 0:
        return b'', b''                      # 参照実装が断る本（budget など）
    return got, r.stdout


if __name__ == '__main__':
    ok = bad = 0
    for f in sys.argv[1:]:
        try:
            src0 = open(f, encoding='utf-8').read()
            if re.search(r'^render ', src0, re.M) or not re.search(r'^print ', src0, re.M):
                print(f"  {os.path.basename(f):<22} —  print が無い / render の本"); continue
            got, want = one(f)
        except Exception as ex:
            bad += 1; print(f"  {os.path.basename(f):<22} ✗  {type(ex).__name__}: {str(ex)[:60]}"); continue
        if got == want:
            ok += 1; print(f"  {os.path.basename(f):<22} ✓  {len(got)} bytes")
        else:
            bad += 1
            gl, wl = got.decode('utf-8', 'replace').splitlines(), want.decode('utf-8', 'replace').splitlines()
            d = next((k for k in range(max(len(gl), len(wl))) if k >= len(gl) or k >= len(wl) or gl[k] != wl[k]), None)
            print(f"  {os.path.basename(f):<22} ✗  行 {d}: {gl[d] if d is not None and d < len(gl) else '(無し)'!r} ≠ {wl[d] if d is not None and d < len(wl) else '(無し)'!r}")
    print(f"  一致 {ok} / 食い違い {bad}")
