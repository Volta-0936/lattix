# -*- coding: utf-8 -*-
"""**三面鏡 —— 彼自身にバグを探させる。**

   Lattix の主張は「答えは実行に依らない」。同じ規則の表は、点に展開しても
   （eg/cd/ix）、空間と写像のまま渡しても（fg/fc/fp）、**同じ最小不動点**を
   持たなければならない。二つの符号化は互いの検査器であり、定義（解釈実行）が
   審判である —— 三面のどれかが割れたら、それが最小の証人つきのバグである。

   今週の穴は一つ残らずこの形で見つかった（sum の層またぎ・pa の継ぎ目・
   cref の行の形・層 0 の flat 読み）。だから撒く: 文法が言う形の空間
   （束 × 源 × 座標 × 値 × ガード × 層）から小さな本を組み立て、

     定義   = lattix.py（解釈実行）
     点の道 = FAMILY_MIN 大 で表を作り、焼いた一枚に食わせる
     家の道 = FAMILY_MIN 1  で表を作り、同じ焼いた一枚に食わせる

   を升まで突き合わせる。焼いた一枚は一つ（表は入力であって答えではない）。
   割れた本は work/_trinity/ に残す —— 縮めるのは人の仕事ではなく、
   種を減らして撒き直せばよい。

   使い方:  python3 test/trinity.py [本数=200] [種=0]
"""
import sys, os, io, random, signal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))
import lattix as L
import runtime as R
import flat as F
import engine2
from engine2 import tbl, answers, Rejected
from baked import enginesrc, bake, coverage, NAMES, NS

BIG = 10 ** 9
LATS = ['min', 'max', 'or', 'sum', 'count', 'flat']


def gen(rng):
    """層で組み立てる —— 生成の時点で成層が立つようにし、歩留まりを上げる。
    形の空間: 束 × (表|区間) × (直接|間接 1..2 の座標) × (定数|一次|読み|
    混束の読み|鎖|構成子) × (軸ガード|場ガード|not|is)。"""
    n = rng.randint(3, 6)
    rows = [(i, rng.randint(0, 9), rng.randint(1, 5)) for i in range(n)]
    src = ["table t = " + ", ".join(f"({a},{b},{c})" for a, b, c in rows)]
    W = 16
    flds = []                                     # (名前, 束, 層)

    def field(lat, st, dims=1):
        f = f"f{len(flds)}"
        src.append(f"field {f} : {lat} bound {W}" + (" 96" if dims == 2 else ""))
        flds.append((f, lat, st, dims)); return f

    # 層 0 —— 表から書く。flat を二枚置いて座標・引数の供給にする
    g0 = field('flat', 0); src.append(f"{g0}[i] <- v          for (i,v,w) in t")
    g1 = field('flat', 0); src.append(f"{g1}[i] <- w          for (i,v,w) in t")
    lat = rng.choice(LATS)
    a0 = field(lat, 0)
    val = rng.choice([f"v + {rng.randint(0,9)}", "v * 2", "w",
                      f"{g0}[i] + 1" if lat in ('min','max','sum','flat') else "v",
                      "true" if lat == 'or' else "v"])
    gd = rng.choice(["", f" if i >= {rng.randint(0,2)}", " if v != 3",
                     f" if {g0}[i] >= 1"])
    src.append(f"{a0}[i] <- {val}   for (i,v,w) in t{gd}")

    # 否定の壁 —— 層 1 を作る
    b0 = field('or', 0)
    src.append(f"{b0}[i] <- true   for (i,v,w) in t if i >= {n - 2}")
    lat1 = rng.choice(LATS)
    c0 = field(lat1, 1)
    kind = rng.randrange(5)
    if kind == 0:                                  # 混束の読み（閉じた面）
        v1 = f"{a0}[i] + 10" if lat1 in ('min','max','sum','flat') else "true" \
             if lat1 == 'or' else "v"
    elif kind == 1:                                # 鎖
        v1 = f"{g0}[i] * {rng.choice([2,3])} % {rng.choice([4,8])}" \
             if lat1 in ('min','max','sum','count','flat') else "v"
    elif kind == 2 and lat1 == 'flat':             # 構成子（引数は場の読み）
        src[0:0] = ["constructor pr(x, y) bound 64"]
        v1 = f"pr({g0}[i], {g1}[i])"
    else:
        v1 = "v" if lat1 not in ('or',) else "true"
    src.append(f"{c0}[i] <- {v1}   for (i,v,w) in t if not {b0}[i]")

    # 書き先の座標が値で決まる（間接 1..2）
    d0 = field('max', 1, dims=rng.choice([1, 2]))
    _, _, _, dims = flds[-1]
    key = f"{g0}[i]" if dims == 1 else f"{g0}[i], {g1}[i]"
    src.append(f"{d0}[{key}] <- i + 1   for (i,v,w) in t if not {b0}[i]")

    for f, _l, _s, _d in flds:
        src.append(f"print {f}")
    return "\n".join(src) + "\n"


def faces(path, info, ddir):
    out = []
    for fm in (BIG, 1):
        F.FAMILY_MIN = fm
        fl, _ = F.flatten(path, engine2.close_upto)
        if fl.strata() > NS: raise NotImplementedError(f"層 {fl.strata()}")
        why = coverage(fl)
        if why: raise NotImplementedError(why)
        t = fl.tables()
        if any(isinstance(x, str) for nm in NAMES for row in t[nm] for x in row):
            raise NotImplementedError("表に文字列")
        srcT = "".join(tbl(nm, t[nm]) for nm in NAMES)
        q = L.parse(enginesrc(srcT))
        d = R.write_data(q, os.path.join(ddir, 'data.lxd'))
        got, _ = R.run(info['exe'], d)
        ans = {}
        for lt in fl.shapes()[2]:
            pl = F.PLANE[lt][0]
            for (c,), v in got.get(f'v{pl}{NS-1}', {}).items():
                try: f, keys = fl.name_of(c)
                except (KeyError, IndexError): continue
                ans.setdefault(f, {})[keys] = fl.obs(v)
        out.append((f"{'点' if fm == BIG else '家'}", ans, len(fl.fg), len(fl.eg)))
    return out


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    rng = random.Random(seed)
    ddir = os.path.join(ROOT, 'work', '_trinity'); os.makedirs(ddir, exist_ok=True)
    info, sec = bake(os.path.join(ROOT, 'work', '_baked'))
    print(f"  焼いた一枚: {sec:.0f}s（表を差し替えて三面ぶん回す）")
    def bell(s, f): raise TimeoutError()
    signal.signal(signal.SIGALRM, bell)
    ok = skip = bad = 0
    for k in range(count):
        srcbook = gen(rng)
        path = os.path.join(ddir, 'book.lx')
        open(path, 'w', encoding='utf-8').write(srcbook)
        signal.alarm(90)
        try:
            ref, p = answers(path)
            fs = faces(path, info, ddir)
            names = p.prints or list(p.fields)
            why = None
            real = set(p.fields)          # 作業用の升（'#' など）は符号化ごとの
            for tag, ans, nfg, neg in fs: # 中間物 —— 比べるのは本物の場だけ
                for f in names:
                    if dict(ref.get(f, {})) != ans.get(f, {}):
                        why = f"{tag} の {f} が定義と違う"; break
                if why: break
            if why is None and len(fs) == 2:
                a0 = {f: v for f, v in fs[0][1].items() if f in real}
                a1 = {f: v for f, v in fs[1][1].items() if f in real}
                if a0 != a1:
                    why = "点と家が互いに違う"
            if why:
                bad += 1
                keep = os.path.join(ddir, f'bad_{seed}_{k}.lx')
                open(keep, 'w', encoding='utf-8').write(srcbook)
                print(f"  ✗ {k}: {why}  → {os.path.relpath(keep, ROOT)}")
            else:
                ok += 1
        except (Rejected, NotImplementedError, R.N.Unsupported):
            skip += 1
        except TimeoutError:
            skip += 1
        except Exception as ex:
            bad += 1
            keep = os.path.join(ddir, f'bad_{seed}_{k}.lx')
            open(keep, 'w', encoding='utf-8').write(srcbook)
            print(f"  ✗ {k}: {type(ex).__name__}: {str(ex)[:60]}  → {os.path.relpath(keep, ROOT)}")
        finally:
            signal.alarm(0)
    print(f"  三面一致 {ok} / 撒けない {skip} / 割れた {bad}")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
