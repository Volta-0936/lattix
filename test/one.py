#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**一枚の本の通し運転（第A段4）** —— 表を運ぶ Python が居ない。

    源のバイト（table ch）
        → front.lx（前段）→ 家の場 → 橋 → 走らせる物 → 最小不動点

   これまでの三段（test/pipeline.py）は、前段が出した **表**を Python が
   運んで走らせる側に食わせていた。ここでは表そのものが無い ——
   `run.lx` の「表の読み」を「場の読み」に書き換えて、前段と同じ一冊に
   入れてある（work/onebook.py）。**走らせるのは参照実装 lattix.py 一つ**で、
   審判も同じ lattix.py が定義を直に走らせた答えである。

   層の上限は本ごとに測って渡す（`fl.strata()` は観測であって経路ではない）。
   渡す層が足りなければ面が空になる —— 静かに間違えるのではなく見えて違う。

   使い方:  python3 test/one.py [本…]
"""
import os, sys, io, time, signal, glob

os.environ.setdefault('LATTIX_FAMILY_MIN', '1')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))
sys.path.insert(0, os.path.join(ROOT, 'test'))

import lattix as L
import onebook as OB
import engine2
from engine2 import answers
from flat import flatten, PLANE

W = 84
LIMIT = int(os.environ.get("LATTIX_LIMIT", "600"))


def one(path):
    ref, q = answers(path)                       # 審判（定義の解釈実行）
    fl, _ = flatten(path, engine2.close_upto)    # 観測（層の数と升の名前）
    if fl.nofam:
        return 'skip', f"参照が家にしない: {fl.nofam[0][0][:28]}"
    ns = min(48, fl.strata() + 2)
    src, cut = OB.build(path, ns=ns)
    p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    t0 = time.time()
    st, _, _ = L.run(p, out=io.StringIO())
    ms = (time.time() - t0) * 1000
    alarm = {k: v for k, v in st.get('zov', {}).items() if v}
    if alarm:
        return 'diff', f"zov {sorted(alarm)}"
    out = {}
    for lt in fl.shapes()[2]:
        pl = PLANE[lt][0]
        for (sx, c), v in st.get('v' + pl, {}).items():
            if sx != ns - 1 or v is None or v is False:
                continue
            try:
                f, keys = fl.name_of(c)
            except (KeyError, IndexError):
                continue
            out.setdefault(f, {})[keys] = fl.obs(v, f)
    for f in (q.prints or list(q.fields)):
        if dict(ref.get(f, {})) != out.get(f, {}):
            return 'diff', f"{f}（刈った形 {len(cut)}）"
    return 'ok', f"{ms:.0f} ms  層 {ns}  刈った形 {len(cut)}"


if __name__ == '__main__':
    print("=" * W)
    print("  一枚の本 —— 前段も走らせる物も同じ一冊。読む表は `ch` だけ")
    print("=" * W)
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'work/t/*.lx')))

    def bell(sig, fr): raise TimeoutError()
    signal.signal(signal.SIGALRM, bell)
    ok = skip = bad = 0
    for f in files:
        signal.alarm(LIMIT)
        try:
            v, why = one(f)
        except TimeoutError:
            v, why = 'skip', f"{LIMIT}s で切った"
        except Exception as ex:
            v, why = 'diff', f"{type(ex).__name__}: {ex}"[:56]
        finally:
            signal.alarm(0)
        n = os.path.basename(f)
        if v == 'ok': ok += 1; print(f"  {n:<22} ✓  {why}", flush=True)
        elif v == 'skip': skip += 1; print(f"  {n:<22} —  {why}", flush=True)
        else: bad += 1; print(f"  {n:<22} ✗  {why}", flush=True)
    print("-" * W)
    print(f"  一致 {ok} / 未対応 {skip} / 食い違い {bad}")
    print("=" * W)
    sys.exit(1 if bad else 0)
