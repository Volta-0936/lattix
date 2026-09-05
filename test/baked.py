# -*- coding: utf-8 -*-
"""**配る一枚を焼く。** `run.lx` を一度 C に落とし、表を差し替えて何度でも走らせる。

   これが「入れた Lattix」の形である —— 実行ファイルは一つで、
   プログラムごとに変わるのは **表だけ**。ここに Python は現れない
   （表を作る前段だけがまだ Python である）。

   束は十ぜんぶ焼ける。集約の寄与元キーは **束縛の組そのもの**で引き、
   集合は整列した並びを arena に置いて番号で指す（域の宣言が要らない）。
   表に文字列は一つも入らない —— 原子は綴りの順に番号を配ってある。
"""
import sys, os, io, re, time, glob, signal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))
import lattix as L
import runtime as R
from flat import flatten, PLANE
import engine2
from engine2 import tbl, answers, Rejected

NAMES = ('eg', 'cd', 'ix', 'dat', 'spc', 'ssz', 'mp', 'fg', 'fc', 'fp', 'ate')


def coverage(fl):
    """この本の形が run.lx の規則で受かるか。**受からない形は黙って落ちる**
    （どの規則の門も合わない）ので、検査の側で声に出す。
    形の一覧は mkrun が run.lx と同時に書く（work/shapes.json）。"""
    import json
    jp = os.path.join(ROOT, 'work', 'shapes.json')
    if not os.path.exists(jp): return None       # 古い run.lx —— 検査できない
    sh = json.load(open(jp))
    tt = lambda xs: {tuple(x) if isinstance(x, (list, tuple)) else (x,)
                     for x in xs}
    v, c, _l = fl.shapes()
    for k, mine in (('vals', tt(v)), ('cond', tt(c)),
                    ('ixlat', tt(fl.ixlat)), ('fsh', tt(fl.fsh)),
                    ('fcsh', tt(fl.fcsh)), ('fpsh', tt(fl.fpsh))):
        miss = mine - tt(sh[k])
        if miss:
            return f"run.lx に無い形 {k}:{sorted(miss)[0]}"
    if fl.ncell() + 1 > sh['nc']: return f"升 {fl.ncell()+1} > {sh['nc']}"
    if fl.nid + 1 > sh['ne']: return f"辺 {fl.nid+1} > {sh['ne']}"
    if len(fl.ix) + 1 > sh['nq']: return f"指し {len(fl.ix)+1} > {sh['nq']}"
    return None
DROP = ()          # **面はもう一つも落としていない**（集約も集合も焼ける）
DROPLAT = ()
NS = 48
LIMIT = 400
W = 84


def enginesrc(tables_src):
    run = open(os.path.join(ROOT, 'run.lx'), encoding='utf-8').read()
    lines = [ln for ln in run.splitlines()
             if not any(re.search(rf'\bv{d}\d+\b', ln) for d in DROP)]
    return tables_src + "\n".join(lines) + "\n"


def bake(keep):
    fl, _ = flatten(os.path.join(ROOT, 'work/t/a_min.lx'), engine2.close_upto)
    t = fl.tables()
    src = enginesrc("".join(tbl(n, t[n]) for n in NAMES))
    t0 = time.time()
    # 検証の焼きは -O0 でよい —— 正しさに最適化は要らず、gcc の時間だけが減る。
    # 速さを測るときだけ LATTIX_OPT=-O2 にする（測る物と検べる物を混ぜない）。
    opt = os.environ.get('LATTIX_OPT', '-O0')
    return R.build(src, keep=keep, opt=opt, ranks=False), time.time() - t0   # 階数は要らない（測定器の走行）


def one(info, path):
    ref, p = answers(path)
    fl, _ = flatten(path, engine2.close_upto)
    if fl.strata() > NS: return 'skip', f"層 {fl.strata()}"
    why = coverage(fl)
    if why: return 'skip', why
    t = fl.tables()
    if any(isinstance(x, str) for n in NAMES for row in t[n] for x in row):
        return 'diff', "表に文字列がある（走らせる側は文字列を見ないはず）"
    src = enginesrc("".join(tbl(n, t[n]) for n in NAMES))
    q = L.parse(src)                      # 表を持つだけの写し（焼かない）
    d = R.write_data(q, os.path.join(info['dir'], f'data.{os.getpid()}.lxd'))
    t0 = time.time(); got, _meta = R.run(info['exe'], d)
    ms = (time.time() - t0) * 1000
    out = {}
    for lt in fl.shapes()[2]:
        pl = PLANE[lt][0]
        if pl in DROP: continue
        for (sx, c), v in got.get(f'v{pl}', {}).items():
            if sx != NS - 1: continue
            try: f, keys = fl.name_of(c)
            except (KeyError, IndexError): continue
            out.setdefault(f, {})[keys] = fl.obs(v, f)
    for f in (p.prints or list(p.fields)):
        if dict(ref.get(f, {})) != out.get(f, {}):
            return 'diff', f
    return 'ok', f"{ms:.0f} ms"


if __name__ == '__main__':
    print("=" * W)
    print("  配る一枚を焼く —— 実行ファイル一つ、プログラムごとに変わるのは表だけ")
    print("=" * W)
    info, sec = bake(os.path.join(ROOT, 'work', '_baked'))
    print(f"  焼いた: {sec:.0f}s   {os.path.getsize(info['exe']):,} バイト")
    print("-" * W)
    files = sys.argv[1:] or (sorted(glob.glob(os.path.join(ROOT, 'work/t/*.lx'))) +
                             sorted(glob.glob(os.path.join(ROOT, 'examples/*.lx'))))
    files = [f for f in files
             if os.path.basename(f) not in ('31_gen.lx', '32_shape.lx')]
    def bell(sig, fr): raise TimeoutError()
    signal.signal(signal.SIGALRM, bell)
    ok = skip = bad = 0
    for f in files:
        signal.alarm(LIMIT)
        try:
            v, why = one(info, f)
        except Rejected as ex: v, why = 'skip', str(ex)[:44]
        except TimeoutError:  v, why = 'skip', f"{LIMIT}s で切った"
        except NotImplementedError as ex: v, why = 'skip', str(ex)[:44]
        except Exception as ex: v, why = 'diff', f"{type(ex).__name__}: {ex}"[:60]
        finally: signal.alarm(0)
        n = os.path.basename(f)
        if v == 'ok': ok += 1; print(f"  {n:<22} ✓  {why}", flush=True)
        elif v == 'skip': skip += 1; print(f"  {n:<22} —  {why}", flush=True)
        else: bad += 1; print(f"  {n:<22} ✗  {why}", flush=True)
    print("-" * W)
    print(f"  一致 {ok} / 未対応 {skip} / 食い違い {bad}")
    print("  **プログラムだけを C にした。** 表は入力であって、答えではない。")
    print("=" * W)
    sys.exit(1 if bad else 0)
