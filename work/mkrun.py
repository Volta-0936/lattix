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
           'npa': 1, 'nat': 1}

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
            dim['nat'] = max(dim['nat'], fl.ATOMB + len(fl.atl) + 1)
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


ARITH = (1, 2, 5, 6, 8, 10)


def family_shapes():
    """**家の形は測らずに数え上げる。** 形の空間は文法が宣言している有限集合
    である（気づき46 の論法を engine 自身に適用する）。測量で閉じると、
    測量に現れなかった形の表を食わせたとき **どの規則の門も合わず、
    黙って何も出さない** —— trinity の三面鏡がこれを 21 本まとめて出した。

    閉じた根拠（気づき31。「なぜこれで全部か」を同じ場所に書く）:
      fsh  (束, 形, 数):  形0 定数/間接(全束・数0) / 形1 加算(数の束・数1,2) /
           形2 true・形5 false(or/and/fourv) / 形3 一元の集合(set) /
           形4 写し(全束・数1)
      fcsh (種, 束, 演算子, 数):  種6 軸だけ(演算子6) / 種2 not・種5 bnot・
           種3 生・種4 is(全束) / 種1 閉・種11 生の比較(全束×演算子6×数0..2)
      fpsh (種, 束):  種0 場の写し(全束±。負は生きた面 —— flat は ⊥→v で
           止まり、他の束は定義が単調と認めた読みだけがここに来る。実際に
           育つ途中を二度写す本は点の道でも ⊤ になる) /
           種1 折り込み(写像%法) / 種2 並べ / 種3 法 / 種4 割り /
           種8 pa÷pa / 種9 pa%pa / 種10 pa·pa / 種11 写像÷法(束0)
    点の道の形（vals/cond/ixlat）は今も測量で閉じている —— そちらは
    消える予定の道であり、検査の側（shapes.json）が届かない形を声に出す。"""
    # 束の合法性は定義（lattix.py の check）が言う —— or は true と or の
    # 読みだけ、値の式（形0/1）は数の束だけ。数え上げを文法より粗くすると、
    # 定義が run.lx ごと弾く（一度やった。彼が見つけてくれた）。
    # write() の最後で L.check に通し、粗ければ **声に出して**落ちる。
    fsh = set()
    for lt in ARITH:
        fsh.add((lt, 0, 0)); fsh.add((lt, 1, 1)); fsh.add((lt, 1, 2))
    for lt in PLANE:
        fsh.add((lt, 4, 1))
    fsh.add((9, 0, 0))                  # count は値を数えない（`orders[c] <- v` の形0）
    for lt in (3, 4, 9):
        fsh.add((lt, 2, 0))
    for lt in (4, 6):
        fsh.add((lt, 5, 0))
    fsh.add((6, 2, 0))
    fsh.add((7, 3, 0))                  # 一元の集合 {v}（元は軸の一次式）
    for lt in (1, 2):                   # 向きの逆な束を引く（max ← c − 生きた min）
        fsh.add((lt, 6, 1)); fsh.add((lt, 6, 2))
    # 種1（閉じた/flat の比較）は pa を通るので束が消えている —— 六行で全部。
    # 種11（生きた単調な比較）だけが面に残るが、それは測量に任せる（下の union）。
    fcsh = {(6, 0, op, 0) for op in range(1, 7)} | \
           {(1, 0, op, 0) for op in range(1, 7)}
    # 種11（生きた単調な比較）は束 × 演算子 × 右の直読みの数（0..2）で閉じる。
    # 生きたまま比べられるのは flat.py の fcond が認める束（sum/count/bag 以外）。
    # 測量に任せると本ごとに違う run.lx になる —— それは処理系ではない。
    # 右に生きた直読み（n ≥ 1）を持つ形は run.lx 自身が成層できない
    # （`x >= y` の y は下る向き）—— 定義が刈る。n = 0 だけ数える。
    # 向きも数える: 昇る束（max/or/count）は `>=` `>` だけが単調、下る束
    # （min/and）は `<=` `<`、flat/fourv（LVar）はどの演算子でも読める。
    # flat/fourv の比較は pa を通る種1 なので種11 には来ない。下る束（min/and）は
    # 測量に任せる（コーパスに無い形を増やすと、焼く C が記憶に収まらない —— 8GB で
    # cc1 が落ちた。形は言語の側から数えるが、**焼ける大きさも資源**である）。
    # sum / count も育つ一方なので `>=` `>` は単調（04_aggregate の revenue[c] > 100）
    # 下る束（min）は `<=` `<` が単調（閉じた max と生きた min の比較を反転した形）
    for lt, ops in ((2, (3, 5)), (3, (3, 5)), (8, (3, 5)), (9, (3, 5)), (1, (4, 6))):
        for op in ops:
            fcsh.add((11, lt, op, 0))
    for lt in PLANE:
        if lt == 7:
            # set をガードの主語にする形は測定器（C）が `is` を焼けない。
            # 言語の制限ではないので数え上げから外すだけ —— 本が要れば
            # shapes.json 経由で「run.lx に無い形」と **声に出て**止まる。
            continue
        fcsh.add((2, lt, 0, 0)); fcsh.add((5, lt, 0, 0))
        fcsh.add((3, lt, 0, 0)); fcsh.add((4, lt, 0, 0))
    # 生きた写しは **昇る束だけ**（2 max / 3 or / 5 flat / 6 fourv / 9 count）。
    # 下る束（min / and）や符号の要る束（sum / bag）を生きたまま pa（flat・
    # 昇る文脈）へ写す規則は、run.lx 自身が成層できない —— 定義も同じことを
    # 言っている（下る読みが同層に居られるのは同束の直読み am/bm だけ）。
    fpsh = {(0, lt) for lt in PLANE} | \
           {(0, -lt) for lt in (2, 3, 5, 6, 9)} | \
           {(1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0),
            (8, 0), (9, 0), (10, 0), (11, 0)}
    return fsh, fcsh, fpsh


def write(path, fromjson=None):
    if fromjson:
        # 測量は済んでいる（work/shapes.json）—— 形の数え上げだけ更新して書き直す
        import json as _json
        sh = _json.load(open(fromjson))
        tt = lambda xs: [tuple(x) if isinstance(x, list) else (x,) for x in xs]
        vals, cond, ixl = set(tt(sh['vals'])), set(tt(sh['cond'])), set(sh['ixlat'])
        lats = {x[0] for x in vals if x[0] in PLANE} | {x[0] for x in tt(sh['fsh']) if x[0] in PLANE}
        fsh, fcsh, fpsh = set(tt(sh['fsh'])), set(tt(sh['fcsh'])), set(tt(sh['fpsh']))
        dim, nc, ne, nq, ns = sh['dim'], sh['nc'], sh['ne'], sh['nq'], NS
    else:
        (vals, cond, lats, ixl, ns, nc, ne, nq, fsh, fcsh, fpsh, dim) = survey()
    if ns > NS:
        raise SystemExit(f"層が {ns} —— 宣言した上限 {NS} を超えた")
    efsh, efcsh, efpsh = family_shapes()
    # 数え上げ ∪ 測量（種11 のような「面に残る形」は測量が言う）
    fsh = sorted(efsh | set(fsh))
    fcsh = sorted(efcsh | set(fcsh))
    fpsh = sorted(efpsh | set(fpsh))
    lats = sorted(set(lats) | set(LAT.values()) & set(PLANE))
    body = engine2.engine_text(nc, ne, nq, NS, (vals, cond, lats), ixl,
                               fsh, dim['nrow'], dim['ncol'], dim['nsp'],
                               dim['nmp'], dim['nax'], fcsh, dim['npt'],
                               fpsh, dim['npa'], dim['nat'])
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
    # **書く前に定義へ通し、定義に刈らせる。** 数え上げは文法の上限であり、
    # どの形が意味を持つか（or に値は書けない・min の生ガードは輪を閉じる）は
    # 定義（check / stratify）が言う。弾かれた行から形を読み取り、落として
    # 書き直す —— 黙って落とすのではなく、刈った形を一つずつ声に出す。
    import re as _re
    import lattix as _L
    pad = {'eg': [0]*10, 'cd': [0,0,999,0,0,0,0,0,0,0], 'ix': [0]*6,
           'dat': [0]*3, 'spc': [0]*5, 'ssz': [0,1], 'mp': [0]*17,
           'fg': [0,0,999,0,0,0,0,0,0,0], 'fc': [0,0,999,0,0,0,0,0,0,0,0],
           'fp': [0,0,999,0,0,0,0,0,0,0,0], 'ate': [0,0,0]}
    dummy = "".join("table %s = (%s)\n" % (n, ",".join(map(str, r)))
                    for n, r in pad.items())
    for _round in range(200):
        src = dummy + head + body
        try:
            q = _L.parse(src); _L.check(q); _L.stratify(q)
            break
        except _L.LattixError as ex:
            m = _re.search(r'line (\d+)', str(ex))
            if not m: raise
            ln = src.split('\n')[int(m.group(1)) - 1]
            mc = _re.search(r'in fc .*if kk == (\d+) if lat == (-?\d+)'
                            r'(?:.*if op == (\d+))?', ln)
            mg = _re.search(r'in fg .*if lat == (-?\d+) if vf == (\d+)'
                            r'(?:.*if n == (\d+))?', ln)
            if mc:
                kk, lt = int(mc.group(1)), int(mc.group(2))
                op = int(mc.group(3)) if mc.group(3) else None
                drop = {t for t in fcsh if t[0] == kk and t[1] == lt
                        and (op is None or t[2] == op)}
            elif mg:
                lt, vf = int(mg.group(1)), int(mg.group(2))
                drop = {t for t in fsh if t[0] == lt and t[1] == vf}
            else:
                raise
            if not drop: raise
            for t in sorted(drop):
                print(f"  刈った: {t}  —— {str(ex).splitlines()[0][:60]}",
                      flush=True)
            fcsh = sorted(set(fcsh) - drop); fsh = sorted(set(fsh) - drop)
            body = engine2.engine_text(nc, ne, nq, NS, (vals, cond, lats), ixl,
                                       fsh, dim['nrow'], dim['ncol'],
                                       dim['nsp'], dim['nmp'], dim['nax'],
                                       fcsh, dim['npt'], fpsh, dim['npa'], dim['nat'])
    else:
        raise SystemExit("刈っても閉じない —— 数え上げの根拠が破れている")
    # 検査の側が「run.lx に無い形」を声に出せるように、**刈ったあとの**
    # 一覧を書き残す（刈る前に書くと、持っていない形を持っていると嘘をつく）。
    import json
    json.dump({'vals': sorted(vals), 'cond': sorted(cond), 'ixlat': sorted(ixl),
               'fsh': [list(t) for t in fsh], 'fcsh': [list(t) for t in fcsh],
               'fpsh': [list(t) for t in fpsh], 'dim': dim,
               'nc': nc, 'ne': ne, 'nq': nq},
              open(os.path.join(HERE, 'shapes.json'), 'w'))
    open(path, 'w', encoding='utf-8').write(head + body)
    return len(vals), len(cond), len(lats), ns, body.count("\n"), nc


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'run.lx')
    fj = os.path.join(ROOT, 'work', 'shapes.json') if os.environ.get('LATTIX_FROMJSON') else None
    nv, ncd, nl, ns, nline, nc = write(out, fromjson=fj)
    print(f"{out}  形 {nv} / 条件 {ncd} / 束 {nl} / 見た層 {ns} / 升 {nc:,} / {nline} 行")
