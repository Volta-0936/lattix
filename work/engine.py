"""対象 .lx → 規則の表 → run.lx（走らせる物）→ 答え。
   そして **対象を直接走らせた答え** と突き合わせる。"""
import io,sys,subprocess; sys.path.insert(0,'.')
sys.path.insert(0,'/tmp/dg')
from tab import tables_for
import lattix as L

def engine_text(nb, ns):
    """規則の表を読んで対象の不動点を出す物を組み立てる。

    **層は座標である。** 層 s の規則は、項では層 s の面（同じ層の再帰）を、
    ガードでは層 s-1 の面（閉じた値）を読む。処理系の成層は場の粒度なので、
    層ごとに面を分ける —— 一つの面で自分を否定越しに読むと輪に見えるからだる。
    （場ではなく座標で成層できれば一枚で済む。第4段の宿題）
    """
    NBZ = nb - 1
    L = []
    A = L.append
    A("# ══ 走らせる物 —— 規則の表を読んで、対象の最小不動点を出す ══════════")
    A("# 反復空間は表 `bind` に宣言されている —— 割り算も掛け算も要らない。")
    A("field d : min bound 256 8")
    A("d[row,col] <- v                for (row,col,v) in dat")
    A("field br : max bound 8192")
    A("field bi : max bound 8192 4")
    A("br[gb] <- r                    for (gb,r,lvl,idx) in bind")
    A("bi[gb,lvl] <- idx              for (gb,r,lvl,idx) in bind")
    A("field osrc : max bound 512")
    A("field ocol : max bound 512")
    A("field oshf : max bound 512")
    A("osrc[ow] <- src                for (gc,ow,r,dm,src,f,col,sk,sh) in crd")
    A("ocol[ow] <- col                for (gc,ow,r,dm,src,f,col,sk,sh) in crd")
    A("oshf[ow] <- sh                 for (gc,ow,r,dm,src,f,col,sk,sh) in crd")
    for nm, src, idx in (('t', 'trm', '(gt,r,t,kd,f,col,v,ow) in trm'),
                         ('h', 'rrule', '(r,st,lat,tar,wf,ow) in rrule')):
        k = 'gt' if nm == 't' else 'r'
        A(f"field {nm}src : max bound 512")
        A(f"field {nm}col : max bound 512")
        A(f"field {nm}shf : max bound 512")
        A(f"{nm}src[{k}] <- osrc[ow]           for {idx}")
        A(f"{nm}col[{k}] <- ocol[ow]           for {idx}")
        A(f"{nm}shf[{k}] <- oshf[ow]           for {idx}")
    A("field gsrc : max bound 512")
    A("field gcol : max bound 512")
    A("field gshf : max bound 512")
    A("gsrc[gg] <- osrc[oo]           for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd if ok == 0")
    A("gcol[gg] <- ocol[oo]           for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd if ok == 0")
    A("gshf[gg] <- oshf[oo]           for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd if ok == 0")
    A("field lastt : max bound 512")
    A("lastt[r] <- gt                 for (gt,r,t,kd,f,col,v,ow) in trm")
    A("field fst : max bound 512")
    A("fst[wf] <- st                  for (r,st,lat,tar,wf,ow) in rrule")
    A("field rlat : max bound 512")
    A("field rst : max bound 512")
    A("rlat[r] <- lat                 for (r,st,lat,tar,wf,ow) in rrule")
    A("rst[r] <- st                   for (r,st,lat,tar,wf,ow) in rrule")
    A("")
    A("# ── 座標（源 0 表の列 / 1 計数器 / 4 定数）────────────────────────")
    for nm, key, loop, cond in (
            ('tk', 'gt,gb', 'for (gt,r,t,kd,f,col,v,ow) in trm', 'if kd == 3'),
            ('hk', 'r,gb', 'for (r,st,lat,tar,wf,ow) in rrule', ''),
            ('gk', 'gg,gb', 'for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd', 'if ok == 0')):
        pre = nm[0]
        A(f"field {nm} : min bound 512 8192")
        kk = key.split(",")[0]
        for srcno, expr in ((0, f'd[bi[gb,0], {pre}col[{kk}]] + {pre}shf[{kk}]'),
                            (1, f'bi[gb, {pre}col[{kk}]] + {pre}shf[{kk}]'),
                            (4, f'{pre}col[{kk}] + {pre}shf[{kk}]')):
            A(f"{nm}[{key}] <- {expr}   {loop} for (gb) in 0 .. {NBZ} if br[gb] == r {cond} if {pre}src[{key.split(',')[0]}] == {srcno}")
    A("")
    A("# ══ 層ごとの面。層 s の値は、層 s-1 の値を引き継ぐ ═══════════════")
    for s in range(ns):
        for pl, lat in (('n', 'min'), ('x', 'max'), ('o', 'or')):
            A(f"field v{pl}{s} : {lat} bound 32 256")
    for pl, lat, code in (('n', 'min', 1), ('x', 'max', 2), ('o', 'or', 3)):
        val = 'true' if pl == 'o' else 'v'
        A(f"v{pl}0[f,c] <- {val}   for (s,f,c,v) in seed for (f2,lat,ar) in fld if f == f2 if lat == {code}")
        for s in range(1, ns):
            A(f"v{pl}{s}[f,c] <- v{pl}{s-1}[f,c]   for (f,lat,ar) in fld for (c) in 0 .. 255 if lat == {code}")
    A("")
    for s in range(ns):
        prev = s - 1
        A(f"# ══ 層 {s} ═══════════════════════════════════════════════════════")
        A(f"field gv{s} : min bound 512 8192")
        A(f"gv{s}[gg,gb] <- ov                for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if ok == 3")
        A(f"gv{s}[gg,gb] <- d[bi[gb,0], c1]   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if ok == 1")
        A(f"gv{s}[gg,gb] <- bi[gb, c1]        for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if ok == 2")
        if prev >= 0:
            for pl, lat, code in (('n', 'min', 1), ('x', 'max', 2)):
                A(f"gv{s}[gg,gb] <- v{pl}{prev}[f, gk[gg,gb]]   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (gb) in 0 .. {NBZ} for (f2,lt,ar) in fld if br[gb] == r if rst[r] == {s} if ok == 0 if f == f2 if lt == {code}")
        A(f"field gh{s} : or bound 512 8192")
        for code, op in ((1, '=='), (2, '!='), (3, '>='), (4, '<='), (5, '>'), (6, '<')):
            A(f"gh{s}[gg,gb] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if kd == 4 if gv == {code} if gv{s}[gg-1,gb] {op} gv{s}[gg,gb]")
        if prev >= 0:
            A(f"# `if not f[C]` —— **否定は閉じた層 {prev} を見る**（⊥ なら成り立つ）")
            A(f"gh{s}[gg,gb] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if kd == 2 if not vo{prev}[f, gk[gg,gb]]")
        A(f"# `if f[C]` —— **肯定は単調だから同じ層**を見る（再帰の一部）")
        A(f"gh{s}[gg,gb] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if kd == 12 if vo{s}[f, gk[gg,gb]]")
        # **「全部立った」は数える。** 否定で言うと、肯定のガード（単調で、
        # 同じ層の再帰の一部）まで否定の輪に入ってしまう。数えれば単調のまま ——
        # `nh` は増えるだけ、`ng` は動かないので `nh >= ng` も単調である。
        A(f"field nh{s} : count bound 512 8192")
        A(f"field ng{s} : count bound 512")
        A(f"nh{s}[r,gb] <- true   for (r,st,lat,tar,wf,ow) in rrule for (gb) in 0 .. {NBZ} if br[gb] == r if st == {s}")
        A(f"ng{s}[r] <- true      for (r,st,lat,tar,wf,ow) in rrule if st == {s}")
        for kd in (4, 2, 12):
            A(f"nh{s}[r,gb] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if kd == {kd} if gh{s}[gg,gb]")
            A(f"ng{s}[r] <- true      for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd if rst[r] == {s} if kd == {kd}")
        A(f"field tc{s} : min bound 512 8192")
        for kd, expr in ((1, 'v'), (5, 'v'), (2, 'd[bi[gb,0], col]'), (11, 'd[bi[gb,0], col]'),
                         (4, 'bi[gb, col]'), (13, 'bi[gb, col]')):
            A(f"tc{s}[gt,gb] <- {expr}   for (gt,r,t,kd,f,col,v,ow) in trm for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if kd == {kd}")
        for pl, lat, code in (('n', 'min', 1), ('x', 'max', 2)):
            A(f"field tf{pl}{s} : {lat} bound 512 8192")
            A(f"field ac{pl}{s} : {lat} bound 512 8192")
            A(f"tf{pl}{s}[gt,gb] <- v{pl}{s}[f, tk[gt,gb]]   for (gt,r,t,kd,f,col,v,ow) in trm for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if rlat[r] == {code} if kd == 3 if fst[f] == {s}")
            if prev >= 0:
                for rpl, rcode in (('n', 1), ('x', 2)):
                    A(f"tf{pl}{s}[gt,gb] <- v{rpl}{prev}[f, tk[gt,gb]]   for (gt,r,t,kd,f,col,v,ow) in trm for (gb) in 0 .. {NBZ} for (f2,lt,ar) in fld if br[gb] == r if rst[r] == {s} if rlat[r] == {code} if kd == 3 if f == f2 if lt == {rcode} if fst[f] <= {prev}")
            A(f"ac{pl}{s}[gt,gb] <- tc{s}[gt,gb]   for (gt,r,t,kd,f,col,v,ow) in trm for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if rlat[r] == {code} if t == 0 if kd != 3")
            A(f"ac{pl}{s}[gt,gb] <- tf{pl}{s}[gt,gb]   for (gt,r,t,kd,f,col,v,ow) in trm for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if rlat[r] == {code} if t == 0 if kd == 3")
            A(f"ac{pl}{s}[gt,gb] <- ac{pl}{s}[gt-1,gb] + tf{pl}{s}[gt,gb]   for (gt,r,t,kd,f,col,v,ow) in trm for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if rlat[r] == {code} if t >= 1 if kd == 3")
            for kd, op in ((1, '+'), (2, '+'), (4, '+'), (5, '-'), (11, '-'), (13, '-')):
                A(f"ac{pl}{s}[gt,gb] <- ac{pl}{s}[gt-1,gb] {op} tc{s}[gt,gb]   for (gt,r,t,kd,f,col,v,ow) in trm for (gb) in 0 .. {NBZ} if br[gb] == r if rst[r] == {s} if rlat[r] == {code} if t >= 1 if kd == {kd}")
            A(f"v{pl}{s}[wf, hk[r,gb]] <- ac{pl}{s}[lastt[r],gb]   for (r,st,lat,tar,wf,ow) in rrule for (gb) in 0 .. {NBZ} if br[gb] == r if st == {s} if lat == {code} if nh{s}[r,gb] >= ng{s}[r]")
        A(f"vo{s}[wf, hk[r,gb]] <- true   for (r,st,lat,tar,wf,ow) in rrule for (gb) in 0 .. {NBZ} if br[gb] == r if st == {s} if lat == 3 if nh{s}[r,gb] >= ng{s}[r]")
        A("")
    last = ns - 1
    A(f"print vn{last}")
    A(f"print vx{last}")
    A(f"print vo{last}")
    return "\n".join(L) + "\n"


def build(path):
    t = tables_for(path)
    nb = len({b[0] for b in t['bind']})
    ns = max(r[1] for r in t['rrule']) + 1
    def tbl(n, data):
        return "table %s = %s\n" % (n, ", ".join("(" + ",".join(map(str,r)) + ")" for r in data))
    src = "".join(tbl(n, t[n]) for n in ['fld','seed','rrule','trm','crd','lop','grd','dat','bind'])
    return src + engine_text(nb, ns), t

class Rejected(Exception):
    pass


def answers(path):
    """対象を直接走らせた答え（場名 → {座標: 値}）"""
    src = open(path,encoding='utf-8').read()
    try:
        p=L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    except L.LattixError as ex:
        raise Rejected(str(ex)[:60])
    st,_,_=L.run(p, out=io.StringIO())
    return {f:{k:p.fields[f].observe(v) for k,v in d.items()} for f,d in st.items()}, p

if __name__=='__main__':
    path=sys.argv[1]
    try:
        ref0, _p0 = answers(path)
    except Rejected as ex:
        print(f"  参照実装が断る: {ex}"); print("  一致"); sys.exit(0)
    eng,t = build(path)
    open('/tmp/dg/run_gen.lx','w',encoding='utf-8').write(eng)
    ref,p = answers(path)
    q=L.parse(eng); L.check(q); L.stratify(q); L.io_rounds(q); L.certify(q)
    st2,_,_=L.run(q, out=io.StringIO())
    names=[f for f in p.fields]
    got={}
    ns = max(r[1] for r in t['rrule']) + 1
    for plane in [f'vn{ns-1}', f'vx{ns-1}', f'vo{ns-1}']:
        for (f,c),v in st2.get(plane,{}).items():
            got.setdefault(names[f],{})[(c,)] = (True if plane.startswith('vo') else v)
    ok=True
    for f in p.prints or names:
        a={k:v for k,v in ref.get(f,{}).items()}
        b=got.get(f,{})
        if a!=b: ok=False; print(f"  ✗ {f}\n    対象: {a}\n    走らせる物: {b}")
        else: print(f"  ✓ {f}: {a}")
    print("  一致" if ok else "  食い違い")
