# -*- coding: utf-8 -*-
"""**配る一枚**を作る。

   走らせる物はプログラムごとに違ってはいけない。違うなら、それは
   コンパイラであって処理系ではない。だから形の一覧を **言語の側**から取り、
   層の数に上限を宣言して、`run.lx` を一枚だけ書く。

   プログラムから出るのは表（`eg` / `cd` / `ix`）だけであり、
   その表は `include "run.lx"` の一行を持つ `.lx` になる。
"""
import sys, os, glob
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from flat import flatten, PLANE, LAT
import engine2

LIMIT = 400                  # 一本にかける上限（形を集めるだけなので十分）
NS = 16                      # 層の上限（宣言する。超えたら断る）
# 升の番号の上限は **測って**宣言する（`survey` が数える）。
# 「上限を大きく書くのは、上限を測らないことの言い換えである」（CLAUDE.md）。


# **形を集めるだけ**なので、大きすぎて時間の掛かる物は外してよい ——
# 同じ形は他の本にも出ている（31/32 は 33_self・28_asm と同じ道具立て）。
HEAVY = ('31_gen.lx', '32_shape.lx')


def corpus():
    fs = sorted(glob.glob(os.path.join(ROOT, 'work/t/*.lx'))) + \
         sorted(glob.glob(os.path.join(ROOT, 'examples/*.lx')))
    return [f for f in fs if os.path.basename(f) not in HEAVY]


def survey():
    """いまの言語が出しうる形を、コーパス全体から集める。"""
    import signal, time
    vals, cond, lats, ixl, ns, nc, ne, nq = set(), set(), set(), set(), 1, 1, 1, 1
    # 多面体の道の形と、その資源（行・列・空間・写像・軸・点）も **測る**
    fsh, fcsh, fpsh = set(), set(), set()
    dim = {'nrow': 1, 'ncol': 1, 'nsp': 1, 'nmp': 1, 'nax': 1, 'npt': 1,
           'npa': 1}

    def bell(sig, fr): raise TimeoutError()
    signal.signal(signal.SIGALRM, bell)
    for f in corpus():
        t0 = time.time(); signal.alarm(LIMIT)
        try:
            fl, _p = flatten(f, engine2.close_upto)
            v, c, l = fl.shapes()
            vals |= set(v); cond |= set(c); lats |= set(l); ixl |= set(fl.ixlat)
            ns = max(ns, fl.strata())
            nc = max(nc, fl.ncell() + 1)
            ne = max(ne, fl.nid + 1)
            nq = max(nq, len(fl.ix) + 1)
            fsh |= set(fl.fsh); fcsh |= set(fl.fcsh); fpsh |= set(fl.fpsh)
            dim['nrow'] = max(dim['nrow'], fl.nrow + 1)
            dim['ncol'] = max(dim['ncol'],
                              max((r[1] for r in fl.dat), default=0) + 1)
            dim['nsp'] = max(dim['nsp'], len(fl.ssz) + 1)
            dim['nmp'] = max(dim['nmp'], len(fl.mp) + 1)
            dim['nax'] = max(dim['nax'],
                             max((r[1] for r in fl.spc), default=0) + 1)
            dim['npt'] = max(dim['npt'], max((r[1] for r in fl.ssz), default=1))
            dim['npa'] = max(dim['npa'], fl.pab + 1)
            note = f"形 {len(v)}+{len(fl.fsh)}  層 {fl.strata()}  升 {fl.ncell()+1}"
        except TimeoutError:
            note = f"—— {LIMIT}s で切った"
        except Exception as ex:
            note = f"—— {type(ex).__name__}: {str(ex)[:44]}"
        finally:
            signal.alarm(0)
        print(f"  {os.path.basename(f):<22} {time.time()-t0:5.1f}s  {note}", flush=True)
    return (sorted(vals), sorted(cond), sorted(lats), sorted(ixl), ns, nc, ne, nq,
            sorted(fsh), sorted(fcsh), sorted(fpsh), dim)


def write(path):
    (vals, cond, lats, ixl, ns, nc, ne, nq, fsh, fcsh, fpsh, dim) = survey()
    if ns > NS:
        raise SystemExit(f"層が {ns} —— 宣言した上限 {NS} を超えた")
    lats = sorted(set(lats) | set(LAT.values()) & set(PLANE))
    body = engine2.engine_text(nc, ne, nq, NS, (vals, cond, lats), ixl,
                               fsh, dim['nrow'], dim['ncol'], dim['nsp'],
                               dim['nmp'], dim['nax'], fcsh, dim['npt'],
                               fpsh, dim['npa'])
    head = ("# ══ run.lx —— 走らせる物。**これ一枚で全部のプログラムが走る** ══\n"
            "#\n"
            "#   入れる物: 表 `eg`（寄与の辺）/ `cd`（条件）/ `ix`（升を指す番号）\n"
            f"#   層の上限: {NS}   升の番号の上限: {nc}（**測った**値）\n"
            f"#     大きいのは、内容アドレスを座標にする場があるからである ——\n"
            f"#     こちらが大きく書いたのではなく、content address がそう宣言している。\n"
            f"#     焼くときは、その場だけが hash 表に落ちる（他は密配列）。\n"
            f"#   辺の上限: {ne}   指し番号の上限: {nq}\n"
            "#\n"
            "#   プログラムごとに変わるのは **表だけ**である。\n"
            f"#   規則の数 {body.count(chr(10))} 行は、言語の形の数であって\n"
            "#   プログラムの大きさではない。\n\n")
    open(path, 'w', encoding='utf-8').write(head + body)
    return len(vals), len(cond), len(lats), ns, body.count("\n"), nc


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'run.lx')
    nv, ncd, nl, ns, nline, nc = write(out)
    print(f"{out}  形 {nv} / 条件 {ncd} / 束 {nl} / 見た層 {ns} / 升 {nc:,} / {nline} 行")
