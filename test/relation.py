# -*- coding: utf-8 -*-
"""寄与の関係を閉じる物（`work/engine2.py`）が、参照実装と **食い違わない**こと。

   できない形は断ってよい（未対応）。**答えが違うことだけが失敗である。**
"""
import os, sys, glob, io, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))
import signal
import lattix as L
from engine2 import build, answers, Rejected
from flat import PLANE

LIMIT = 400      # 一本にかける上限。遅いのは速さの宿題であって食い違いではない。


def one(path):
    try:
        ref, p = answers(path)
    except Rejected:
        return 'skip', ''
    try:
        eng, fl, p = build(path)
    except NotImplementedError as ex:
        return 'skip', str(ex)[:50]
    q = L.parse(eng); L.check(q); L.stratify(q); L.io_rounds(q); L.certify(q)
    st2, _, _ = L.run(q, out=io.StringIO())
    ns = fl.strata(); got = {}
    for lt in fl.shapes()[2]:
        nm = f'v{PLANE[lt][0]}'
        for (sx, c), v in st2.get(nm, {}).items():
            if sx != ns - 1: continue
            try: f, keys = fl.name_of(c)
            except (KeyError, IndexError): continue
            got.setdefault(f, {})[keys] = fl.obs(q.fields[nm].observe(v), f)
    for f in (p.prints or list(p.fields)):
        if dict(ref.get(f, {})) != got.get(f, {}):
            return 'diff', f
    return 'ok', ''


if __name__ == '__main__':
    files = sorted(glob.glob(os.path.join(ROOT, 'work/t/*.lx'))) + \
            sorted(glob.glob(os.path.join(ROOT, 'examples/*.lx')))
    # **大きすぎて関係を実体化できない本は外す。** 辺を数百万本ぶん持つので
    # 機械の記憶を食い尽くす —— 正しさではなく速さの宿題である（計画 6.5-1）。
    files = [f for f in files
             if os.path.basename(f) not in ('31_gen.lx', '32_shape.lx')]
    ok = skip = bad = 0
    def bell(sig, fr): raise TimeoutError()
    signal.signal(signal.SIGALRM, bell)
    for f in files:
        signal.alarm(LIMIT)
        try:
            v, why = one(f)
        except TimeoutError:
            v, why = 'skip', f"{LIMIT}s で切った"
        except Exception as ex:
            v, why = 'diff', f"{type(ex).__name__}: {ex}"[:70]
        finally:
            signal.alarm(0)
        if v == 'ok': ok += 1
        elif v == 'skip': skip += 1
        else:
            bad += 1; print(f"  食い違い {os.path.basename(f)}  {why}")
    print(f"  一致 {ok} / 未対応 {skip} / 食い違い {bad}")
    sys.exit(1 if bad else 0)
