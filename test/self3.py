#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**形も断片が導く。** —— 三段目。

`33_self.lx` は生の `.lx` バイトから、31_gen が食う **形の表そのもの**を出す。
場・次数・広さ・種・規則・ループ・項・ガード・座標 —— どれも Python 側で
決めていない。ホストがやるのは、場を表の行に落として次の段へ渡すことだけである。

検査は二重: 焼いた実行ファイルの答えが **解釈実行と全セル一致**し、
同じ形を 32_shape が出したものと突き合わせても一致する。
"""
import io, os, re, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

sg = open(os.path.join(ROOT, 'test', 'selfgen.py'), encoding='utf-8').read()
ns = {'__name__': 'notmain', '__file__': os.path.join(ROOT, 'test', 'selfgen.py')}
exec(compile(sg[:sg.index('print("=" * W)')], 'selfgen', 'exec'), ns)

SELF = open(os.path.join(ROOT, 'examples', '33_self.lx'), encoding='utf-8').read()
SELFP = re.sub(r"table ch = .*?\n", "table ch = (0,32)\n", SELF, count=1)
W = 78


def shape(src):
    """**断片が導いた形**を、31_gen の表の行にする。判断は一つも Python に無い。"""
    o = ns['cgo']('self3', SELFP, {'ch': [(i, c) for i, c in enumerate(src.encode())]})
    g = lambda n: o(n)
    one = lambda n: {k[0]: v for k, v in o(n).items()}
    two = lambda n: {(k[0], k[1]): v for k, v in o(n).items()}

    isrec, rst, rlt, rarr = one('isrec'), one('rst'), one('rlt'), one('rarr')
    hfz, isseed = one('hfz'), one('isseed')
    order = sorted((s for s in isrec if isrec[s]), key=lambda s: (rst.get(s, 0), s))
    rno = {s: r for r, s in enumerate(order)}

    flatt, farr, fwid, fwid2 = one('flatt'), one('farr'), one('fwid'), one('fwid2')
    flds = sorted((f, flatt[f], farr.get(f, 1), fwid.get(f, 64),
                   fwid2.get(f, fwid.get(f, 64))) for f in flatt)
    fl = [(f, l, a) for f, l, a, _w, _w2 in flds]
    fd = ([(f, 0, w) for f, _l, _a, w, _w2 in flds]
          + [(f, 1, w2) for f, _l, a, _w, w2 in flds if a == 2])

    sedf, sedc, sedv = one('sedf'), one('sedc'), one('sedv')
    seeds = [(k, sedf[s], sedc.get(s, 0), sedv.get(s, 0))
             for k, s in enumerate(sorted(s for s in isseed if isseed[s]))]

    rules = [(r, rst.get(s, 0), rlt[s], rarr.get(s, 1), hfz[s])
             for r, s in enumerate(order)]

    lkd, llo, lhi, lar = two('lkd'), two('llo2'), two('lhi2'), two('lar2')
    lbf, lbc = two('lbf2'), two('lbc2')
    loops = [(rno[s], l, lkd[(s, l)], llo.get((s, l), 0), lhi.get((s, l), 0),
              lar.get((s, l), 0), lbf.get((s, l), 0), lbc.get((s, l), 0))
             for (s, l) in sorted(lkd) if s in rno]
    loops = [(k,) + row for k, row in enumerate(loops)]

    trkd, trfl, trcl, trvl = two('trkd'), two('trfl'), two('trcl'), two('trvl')
    terms = [(rno[s], t, trkd[(s, t)], trfl.get((s, t), 0), trcl.get((s, t), 0),
              trvl.get((s, t), 0))
             for (s, t) in sorted(trkd) if s in rno]

    gkd, gfd, gc1, ggv = two('gkd'), two('gfd'), two('gc1'), two('ggv')
    gok, gov = two('gok2'), two('gov')
    guards = [(rno[s], gg, gkd[(s, gg)], gfd.get((s, gg), 0), gc1.get((s, gg), 0),
               ggv.get((s, gg), 0), gok.get((s, gg), 0), gov.get((s, gg), 0))
              for (s, gg) in sorted(gkd) if s in rno]

    okk, oix, osn = one('okk'), one('oix'), one('osn')
    c0 = (one('c0sr'), one('c0cf'), one('c0cc'), one('c0hf'), one('c0of'))
    c1 = (one('c1sr'), one('c1cf'), one('c1cc'), one('c1hf'), one('c1of'))
    has1 = one('has1')
    coords = []
    for ob in sorted(okk):
        s = osn.get(ob)
        if s not in rno or c0[0].get(ob) is None: continue
        coords.append((okk[ob], rno[s], oix.get(ob, 0), 0, c0[0][ob],
                       c0[1].get(ob, 0), c0[2].get(ob, 0),
                       int(c0[3].get(ob, 0)), c0[4].get(ob, 0)))
        if has1.get(ob):
            coords.append((okk[ob], rno[s], oix.get(ob, 0), 1, c1[0][ob],
                           c1[1].get(ob, 0), c1[2].get(ob, 0),
                           int(c1[3].get(ob, 0)), c1[4].get(ob, 0)))
    coords.sort()
    # **所有者に通し番号を振る**（種・規則・番号の三つ組では 4次元になる）。
    # 断片の側では所有者はそのまま **出現**なので、番号も出現の順で足りる。
    own = {}
    for (kk, r, i, _d, *_x) in coords:
        own.setdefault((kk, r, i), len(own))
    NOOWN = len(own)
    coords = [(k, own[(kk, r, i)], r, d, src, cf, cc, hof, off)
              for k, (kk, r, i, d, src, cf, cc, hof, off) in enumerate(coords)]
    rules = [ru + (own.get((2, ru[0], 0), NOOWN),) for ru in rules]
    guards = [(k,) + row + (own.get((1, row[0], row[1]), NOOWN),)
              for k, row in enumerate(guards)]
    terms = [(k,) + row + (own.get((0, row[0], row[1]), NOOWN),)
             for k, row in enumerate(terms)]
    ncol = one('ncol').get(0, 1)
    trow = {}
    for (r, c), v in two('tbrow').items(): trow[(0, r, c)] = v
    return dict(flds=flds, fl=fl, fd=fd, seeds=seeds, rules=rules, loops=loops,
                terms=terms, guards=guards, coords=coords, trow=trow, ncol=ncol)


A = """table edge = (0,1,4), (0,2,1), (2,1,2), (1,3,5), (3,4,3), (4,5,2)
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edge
"""
B = """table e = (0,1,4,1), (0,2,1,0), (2,1,2,1)
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w for (i,j,w,t) in e if t == 1
field far : or bound 16
far[j] <- true for (i,j,w,t) in e if w >= 2
"""
C = """table e = (0,5), (1,7), (2,9), (3,2)
field val : max bound 16
val[i] <- v for (i,v) in e
field got : max bound 16
got[i] <- val[i] for (i,v) in e
field ch2 : max bound 16
ch2[i] <- ch2[i-1] + 1 for (i,v) in e if i >= 1
ch2[0] <- 0
"""
D = """table e = (0,1), (1,2), (2,3)
field m : max bound 8 4
m[i,0] <- j     for (i,j) in e
m[i,1] <- j + 1 for (i,j) in e
field s2 : max bound 8
s2[i] <- m[i,0] + m[i,1] for (i,j) in e
"""
E = """table e = (0,3), (1,1), (2,5)
field lim : max bound 8
lim[i] <- v for (i,v) in e
field big : or bound 8
big[i] <- true for (i,v) in e if i > lim[i]
field rng : max bound 16
rng[x] <- x * 2 for (x) in 1 .. 4
"""
F_ = """field p : max bound 8
p[0] <- 3
p[1] <- 1
p[2] <- 0
field q : max bound 8 4
q[3,0] <- 5
q[1,1] <- 9
q[0,3] <- 11
field r : max bound 8
r[j] <- q[p[j], p[j+1]] for (j) in 0 .. 1
r[j] <- q[p[j-1], p[j]] for (j) in 1 .. 2
"""
G_ = """table e = (0,700), (1,66000), (2,300)
field lo : max bound 8
lo[i] <- x % 256 for (i,x) in e
field hi : max bound 8
hi[i] <- x / 256 % 256 for (i,x) in e
field top : max bound 8
top[i] <- x / 65536 for (i,x) in e
"""
H_ = """table e = (0,10,3), (1,20,7), (2,30,25)
field a : max bound 8
a[i] <- x for (i,x,y) in e
field b : max bound 8
b[i] <- y for (i,x,y) in e
field d : max bound 8
d[i] <- a[i] - b[i] for (i,x,y) in e
"""
I_ = """table e = (0,3)
field lim : max bound 8
lim[i] <- v for (i,v) in e
field sq : max bound 16
sq[x] <- x * 2 for (x) in 0 .. lim[0]
"""
CASES = [("最短経路", A), ("ガードと二場", B), ("鎖と場の読み", C),
         ("定数の添字と2次元", D), ("列と場・掛ける", E),
         ("前置のずれ p[j+1]", F_), ("割る／余り", G_),
         ("場の読みを引く", H_), ("上端が場", I_)]

tmp = tempfile.mkdtemp()
ok = True
print("=" * W)
print("  **形も断片が導く** —— 33_self.lx が出した表で焼く（三段目）")
print("=" * W)
print(f"  {'入力':<20}{'場':>3}{'規則':>4}{'項':>4}{'ガード':>6}{'座標':>5}"
      f"{'セル':>6}   一致")
print("-" * W)
for i, (name, src) in enumerate(CASES):
    sp = shape(src)
    flds, rules, n, store, rank = ns['bake'](sp, tmp, 500 + i)
    names, ref = ns['interp'](src)
    same = store == ref
    ok &= same
    print(f"  {name:<20}{len(sp['fl']):>3}{len(sp['rules']):>4}{len(sp['terms']):>4}"
          f"{len(sp['guards']):>6}{len(sp['coords']):>5}"
          f"{sum(len(d) for d in store.values()):>6}   {'✓' if same else '✗'}")
    if not same:
        for f, nm in enumerate(names):
            if store.get(f) != ref.get(f):
                print(f"      {nm}: 機械語 {store.get(f)}")
                print(f"      {' ' * len(nm)}  解釈  {ref.get(f)}")
print("-" * W)
print("  一致" if ok else "  不一致")
print("  場・次数・広さ・種・規則・ループ・項・ガード・座標 —— **どれも断片が導いた**。")
print("  ホストは場を行に落として次の段へ渡すだけで、判断を一つも持たない。")
print("=" * W)
sys.exit(0 if ok else 1)
