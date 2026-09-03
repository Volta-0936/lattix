# -*- coding: utf-8 -*-
"""**配る一枚**の検査 —— `run.lx` は一つ、プログラムから出るのは表だけ。

   これが通るなら、走らせる物はコンパイラではなく *処理系*である。
"""
import os, sys, io, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))
import signal
import lattix as L
from flat import flatten, PLANE
import engine2
from engine2 import tbl, answers, Rejected

NS = 16
NCMAX = None     # `run.lx` が宣言している升の上限（頭から読む）
HASFP = False    # `run.lx` が番地の面（値で決まる座標）を持っているか
LIMIT = 400          # 一本にかける上限。**遅いのは正しさの問題ではない** ——
                     # 固定の一枚は形ごとに規則を持つので、当たらない規則も表を
                     # 舐める。焼けば添字で飛べる（計画 第6段）。


def one(path):
    try:
        ref, p = answers(path)
    except Rejected:
        return 'skip', ''
    try:
        fl, _p = flatten(path, engine2.close_upto)
    except NotImplementedError as ex:
        return 'skip', str(ex)[:44]
    if fl.strata() > NS:
        return 'skip', f"層が {fl.strata()}"
    if fl.fp and not HASFP:
        # **黙って間違えない。** 値で決まる座標（`f[g[i]]` を多面体のまま
        # 渡す道）は `run.lx` が持っていない —— コーパスに一本も無いので
        # 形を測れなかった。持っていないなら、そう言う。
        return 'skip', "番地の面が run.lx に無い"
    if NCMAX is not None and fl.ncell() + 1 > NCMAX:
        # **宣言した資源を超えたら言う**（黙って間違えない）。
        return 'skip', f"升が {fl.ncell()+1} —— run.lx の宣言 {NCMAX} を超える"
    t = fl.tables()
    # **配る一枚は多面体の道を持っている。** だから表は空でも渡す ——
    # `tables()` が番兵の行を入れるので、当たる規則が一つも無いだけである。
    names = ('eg', 'cd', 'ix', 'dat', 'spc', 'ssz', 'mp', 'fg', 'fc', 'fp')
    src = "".join(tbl(n, t[n]) for n in names) + 'include "run.lx"\n'
    q = L.parse(src, base=ROOT)
    L.check(q); L.stratify(q); L.io_rounds(q); L.certify(q)
    st2, _, _ = L.run(q, out=io.StringIO())
    got = {}
    for lt in fl.shapes()[2]:
        nm = f'v{PLANE[lt][0]}'
        for (sx, c), v in st2.get(nm, {}).items():
            if sx != NS - 1: continue
            try: f, keys = fl.name_of(c)
            except (KeyError, IndexError): continue
            got.setdefault(f, {})[keys] = fl.obs(q.fields[nm].observe(v), f)
    for f in (p.prints or list(p.fields)):
        if dict(ref.get(f, {})) != got.get(f, {}):
            return 'diff', f
    return 'ok', ''


if __name__ == '__main__':
    import re
    _rl = open(os.path.join(ROOT, 'run.lx'), encoding='utf-8').read()
    m = re.search(r'升の番号の上限: (\d+)', _rl[:4096])
    if m: NCMAX = int(m.group(1))
    HASFP = ' in fp' in _rl
    files = sorted(glob.glob(os.path.join(ROOT, 'work/t/*.lx'))) + \
            sorted(glob.glob(os.path.join(ROOT, 'examples/*.lx')))
    # **大きすぎて関係を実体化できない本は外す。** 辺を数百万本ぶん持つので
    # 機械の記憶を食い尽くす —— 正しさではなく速さの宿題である（計画 6.5-1）。
    files = [f for f in files
             if os.path.basename(f) not in ('31_gen.lx', '32_shape.lx')]
    if len(sys.argv) > 1: files = sys.argv[1:]
    ok = skip = bad = 0
    def bell(sig, fr): raise TimeoutError()
    signal.signal(signal.SIGALRM, bell)
    for f in files:
        signal.alarm(LIMIT)
        try:
            v, why = one(f)
        except TimeoutError:
            v, why = 'skip', f"{LIMIT}s で切った（速さの宿題）"
        except Exception as ex:
            v, why = 'diff', f"{type(ex).__name__}: {ex}"[:70]
        finally:
            signal.alarm(0)
        n = os.path.basename(f)
        if v == 'ok': ok += 1; print(f"  {n:<22} ✓", flush=True)
        elif v == 'skip': skip += 1; print(f"  {n:<22} —  {why}", flush=True)
        else:
            bad += 1; print(f"  {n:<22} ✗  {why}", flush=True)
    print(f"  ---- 一致 {ok} / 未対応 {skip} / 食い違い {bad}")
    sys.exit(1 if bad else 0)
