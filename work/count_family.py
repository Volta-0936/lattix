# -*- coding: utf-8 -*-
"""**広げる前に数える**（PLAN §5-6 / 第4段 4.1）。

   多面体の道（空間と写像のまま渡す）で書けなかった規則を、**理由ごとに数える**。
   前段（`front.lx`）が何を作らなければならないかは、この数え上げが決める ——
   作ってから足りないと気づいて戻す、を繰り返さないために。

   数えるときに二つを混ぜない:
     ※ が付く行は **選択**（書けるが、点に展開したほうが速いと決めた）
     付かない行は **書けない**（いまの写像の言葉では言えない）

   使い方:  python3 work/count_family.py [本の名前 …]
"""
import sys, os, glob, signal, time, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import flat, engine2

LIMIT = int(os.environ.get('LIMIT', '240'))
HEAVY = ('31_gen.lx', '32_shape.lx')


def corpus(argv):
    if argv: return argv
    fs = sorted(glob.glob(os.path.join(ROOT, 'work/t/*.lx'))) + \
         sorted(glob.glob(os.path.join(ROOT, 'examples/*.lx')))
    return [f for f in fs if os.path.basename(f) not in HEAVY]


def bell(sig, fr): raise TimeoutError()


def main(argv):
    signal.signal(signal.SIGALRM, bell)
    why = collections.Counter()          # 理由 → 規則の本数
    byfile = collections.Counter()       # 本 → 断られた規則の本数
    fam = pts = 0
    W = 78
    print("=" * W)
    print("  多面体で書けなかった規則を、理由ごとに数える")
    print("=" * W)
    print(f"  {'本':<24}{'家':>5}{'点':>6}   断った理由（多い順）")
    print("-" * W)
    for f in corpus(argv):
        b = os.path.basename(f)
        signal.alarm(LIMIT)
        t0 = time.time()
        try:
            fl, _p = flat.flatten(f, engine2.close_upto)
            n_fam, n_no = len(fl.fg), len(fl.nofam)
            fam += n_fam; pts += n_no
            top = collections.Counter(w for w, _t, _i, _s in fl.nofam)
            for k, v in top.items(): why[k] += v
            byfile[b] = n_no
            head = "  ".join(f"{k}×{v}" for k, v in top.most_common(3))
            print(f"  {b:<24}{n_fam:>5}{n_no:>6}   {head}")
        except TimeoutError:
            print(f"  {b:<24}{'—':>5}{'—':>6}   {LIMIT}s で切った")
        except Exception as ex:
            print(f"  {b:<24}{'—':>5}{'—':>6}   {type(ex).__name__}: {str(ex)[:40]}")
        finally:
            signal.alarm(0)
    print("-" * W)
    print(f"  家として渡せた規則 {fam} / 点に落ちた規則 {pts}")
    print()
    print("  断った理由（※ は選択であって、書けないわけではない）")
    print("-" * W)
    for k, v in why.most_common():
        print(f"    {v:>6}  {k}")
    print("=" * W)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
