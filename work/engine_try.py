"""対象 .lx → 規則の表 → run.lx（走らせる物）→ 答え。
   そして **対象を直接走らせた答え** と突き合わせる。"""
import io,sys,subprocess; sys.path.insert(0,'.')
sys.path.insert(0,'/tmp/dg')
from tab import tables_for
import lattix as L

ENGINE = """
# ══ 走らせる物 —— 規則の表を読んで、対象の最小不動点を出す ══════════
# 命令も番地も出さない。**この物の不動点が、対象の不動点である。**

# ── 地上データを場に開く ──────────────────────────────────────────
field d : min bound 256 8
d[row,col] <- v                for (row,col,v) in dat

# ── 記述を引ける形に（所有者・項・規則ごと）──────────────────────
field ocol : max bound 512
ocol[ow] <- col                for (gc,ow,r,dm,src,f,col,sk,sh) in crd
field tcol : max bound 512
tcol[gt] <- ocol[ow]           for (gt,r,t,kd,f,col,v,ow) in trm
field hcol : max bound 512
hcol[r] <- ocol[ow]            for (r,st,lat,tar,wf,ow) in rrule
field lastt : max bound 512
lastt[r] <- gt                 for (gt,r,t,kd,f,col,v,ow) in trm
field rlat : max bound 512
rlat[r] <- lat                 for (r,st,lat,tar,wf,ow) in rrule

# ══ ガード ═════════════════════════════════════════════════════════
# 比較は **辺が二行**（種3 が左、種4 が右で値が演算子）。左は右の一つ前。
field gvn : min bound 512 256
gvn[gg,row] <- ov              for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (row) in 0 .. NROWZ if ok == 3
gvn[gg,row] <- d[row,c1]       for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (row) in 0 .. NROWZ if ok == 1

field ghold : or bound 512 256
ghold[gg,row] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (row) in 0 .. NROWZ if kd == 4 if gv == 1 if gvn[gg-1,row] == gvn[gg,row]
ghold[gg,row] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (row) in 0 .. NROWZ if kd == 4 if gv == 2 if gvn[gg-1,row] != gvn[gg,row]
ghold[gg,row] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (row) in 0 .. NROWZ if kd == 4 if gv == 3 if gvn[gg-1,row] >= gvn[gg,row]
ghold[gg,row] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (row) in 0 .. NROWZ if kd == 4 if gv == 4 if gvn[gg-1,row] <= gvn[gg,row]
ghold[gg,row] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (row) in 0 .. NROWZ if kd == 4 if gv == 5 if gvn[gg-1,row] > gvn[gg,row]
ghold[gg,row] <- true   for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (row) in 0 .. NROWZ if kd == 4 if gv == 6 if gvn[gg-1,row] < gvn[gg,row]

# **成り立たない辺が一つでもあれば、その束縛では火が点かない。**
# 数えるのではなく、立たなかったことを伝える（否定は層を切る）。
field gbad : or bound 512 256
gbad[r,row] <- true     for (gg,r,g,kd,f,c1,gv,ok,ov,oo) in grd for (row) in 0 .. NROWZ if kd == 4 if not ghold[gg,row]

# ══ 対象の場の値 ═══════════════════════════════════════════════════
# **束ごとに面を分ける** —— min の面が育つ max の面を読むと単調でなくなる。
field vmin : min bound 32 256
field vmax : max bound 32 256
field vor  : or  bound 32 256
vmin[f,c] <- v     for (s,f,c,v) in seed for (f2,lat,ar) in fld if f == f2 if lat == 1
vmax[f,c] <- v     for (s,f,c,v) in seed for (f2,lat,ar) in fld if f == f2 if lat == 2
vor[f,c]  <- true  for (s,f,c,v) in seed for (f2,lat,ar) in fld if f == f2 if lat == 3

# ══ 項 ═══════════════════════════════════════════════════════════
# **定数・表の列・計数器の項は、対象の場に依らない。** 別の場に置く ——
# 育つ場を引き算や掛け算の右に置くと単調でなくなる（気づき38）ので、
# 「動かない側」と「育つ側」を混ぜない。
field tcv : min bound 512 256           # 動かない項（定数 / 表の列 / 計数器）
tcv[gt,row] <- v            for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if kd == 1
tcv[gt,row] <- v            for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if kd == 5
tcv[gt,row] <- v            for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if kd == 6
tcv[gt,row] <- v            for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if kd == 7
tcv[gt,row] <- v            for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if kd == 8
tcv[gt,row] <- d[row,col]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if kd == 2
tcv[gt,row] <- d[row,col]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if kd == 11
tcv[gt,row] <- d[row,col]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if kd == 12

# ── min の規則 ────────────────────────────────────────────────────
field tfn : min bound 512 256       # 育つ項（場の読み）
field acn : min bound 512 256       # 左からの畳み
tfn[gt,row] <- vmin[f, d[row,tcol[gt]]]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 1 if kd == 3
acn[gt,row] <- tcv[gt,row]    for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 1 if t == 0 if kd != 3
acn[gt,row] <- tfn[gt,row]     for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 1 if t == 0 if kd == 3
acn[gt,row] <- acn[gt-1,row] + tfn[gt,row]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 1 if t >= 1 if kd == 3
acn[gt,row] <- acn[gt-1,row] + tcv[gt,row]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 1 if t >= 1 if kd == 1
acn[gt,row] <- acn[gt-1,row] + tcv[gt,row]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 1 if t >= 1 if kd == 2
acn[gt,row] <- acn[gt-1,row] + tcv[gt,row]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 1 if t >= 1 if kd == 4
vmin[wf, d[row,hcol[r]]] <- acn[lastt[r],row]
      for (r,st,lat,tar,wf,ow) in rrule for (row) in 0 .. NROWZ if lat == 1 if not gbad[r,row]

# ── max の規則 ────────────────────────────────────────────────────
field tfx : max bound 512 256       # 育つ項（場の読み）
field acx : max bound 512 256       # 左からの畳み
tfx[gt,row] <- vmax[f, d[row,tcol[gt]]]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 2 if kd == 3
acx[gt,row] <- tcv[gt,row]    for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 2 if t == 0 if kd != 3
acx[gt,row] <- tfx[gt,row]     for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 2 if t == 0 if kd == 3
acx[gt,row] <- acx[gt-1,row] + tfx[gt,row]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 2 if t >= 1 if kd == 3
acx[gt,row] <- acx[gt-1,row] + tcv[gt,row]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 2 if t >= 1 if kd == 1
acx[gt,row] <- acx[gt-1,row] + tcv[gt,row]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 2 if t >= 1 if kd == 2
acx[gt,row] <- acx[gt-1,row] + tcv[gt,row]   for (gt,r,t,kd,f,col,v,ow) in trm for (row) in 0 .. NROWZ if rlat[r] == 2 if t >= 1 if kd == 4
vmax[wf, d[row,hcol[r]]] <- acx[lastt[r],row]
      for (r,st,lat,tar,wf,ow) in rrule for (row) in 0 .. NROWZ if lat == 2 if not gbad[r,row]
# ── or の規則（値を見ない。**火が点いたら true**）────────────────
vor[wf, d[row,hcol[r]]] <- true
      for (r,st,lat,tar,wf,ow) in rrule for (row) in 0 .. NROWZ if lat == 3 if not gbad[r,row]

print vmin
print vmax
print vor
"""

def build(path):
    t = tables_for(path)
    nrow = t['nrow'][0][0]
    def tbl(n, data):
        return "table %s = %s\n" % (n, ", ".join("(" + ",".join(map(str,r)) + ")" for r in data))
    src = "".join(tbl(n, t[n]) for n in ['fld','seed','rrule','trm','crd','lop','grd','dat'])
    return src + ENGINE.replace('NROWZ', str(nrow-1)), t

def answers(path):
    """対象を直接走らせた答え（場名 → {座標: 値}）"""
    src = open(path,encoding='utf-8').read()
    p=L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    st,_,_=L.run(p, out=io.StringIO())
    return {f:{k:p.fields[f].observe(v) for k,v in d.items()} for f,d in st.items()}, p

if __name__=='__main__':
    path=sys.argv[1]
    eng,t = build(path)
    open('/tmp/dg/run_gen.lx','w',encoding='utf-8').write(eng)
    ref,p = answers(path)
    q=L.parse(eng); L.check(q); L.stratify(q); L.io_rounds(q); L.certify(q)
    st2,_,_=L.run(q, out=io.StringIO())
    names=[f for f in p.fields]
    got={}
    for plane in ['vmin','vmax','vor']:
        for (f,c),v in st2.get(plane,{}).items():
            got.setdefault(names[f],{})[(c,)] = (True if plane=='vor' else v)
    ok=True
    for f in p.prints or names:
        a={k:v for k,v in ref.get(f,{}).items()}
        b=got.get(f,{})
        if a!=b: ok=False; print(f"  ✗ {f}\n    対象: {a}\n    走らせる物: {b}")
        else: print(f"  ✓ {f}: {a}")
    print("  一致" if ok else "  食い違い")
