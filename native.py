#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lattix — C バックエンド。

インタプリタが動的である必要はまったく無い。プログラムが与えられた時点で
処理系はすでに全部知っている:

  各場の束      → join は具体的な機械語の演算になる
  各規則の形     → 束縛の走査は静的なループになる
  層            → 相構造は静的になる
  停止性証明書   → スケジューラをコンパイル時に選べる（非負なら二分ヒープ）
  座標の定義域   → 場は密配列になり、辞書もハッシュも消える
  読み取りキー   → 索引がコンパイル時に導出される（最短経路なら隣接リストが出る）

結果はタグ付き値もディスパッチも辞書引きも無い単相の C である。

対応: min max or and flat count sum set（要素領域が小さければビットセット）
未対応は理由付きで Unsupported を投げ、インタプリタに落ちる。
"""
from __future__ import annotations
import os, sys, subprocess, tempfile, itertools, time
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lattix as L

BOT = {'min': "INT64_MAX", 'max': "INT64_MIN", 'or': "0", 'and': "1",
       'flat': "INT64_MIN", 'count': "0", 'sum': "0"}
MAXCELLS = 1 << 24
SETBITS = 4096


# ==========================================================================
# ℤ —— 整数は機械語ではない
# ==========================================================================
# 答えは最小不動点なのだから、**答えが語長に依存してはならない。**
# 64ビットで環に巻くのは、値の意味を機械に明け渡すことである。
#
# 表現は二段: 収まる間はそのまま機械語で持ち、溢れた瞬間に
# **内容で名づけられた値**（帯の中の番号）に化ける。同じ数は必ず同じ語になるので、
# `flat` の等値も min/max の比較も、構成子の内容アドレスも、そのまま効く。
# 小さい数に札を付けない（帯を予約する）のは、**座標が値と同じ語に住んでいる**からで、
# 札を付けると全ての添字算術に外し忘れの穴が開く。
#
# 座標は別である。**座標は有限の資源**（`bound N` や深さ表と同じ）で、
# 大きすぎる数を座標にしようとしたら黙って壊れずにそう言う。
Z_PRELUDE = r"""
#include <stdlib.h>
/* ── ℤ: 小さい間は機械語、溢れたら帯の中の番号 ───────────────────── */
#define ZFIT (((i64)1)<<62)
#define ZBLO (INT64_MIN + 1)
typedef struct { int sg; int n; uint32_t *d; } zbig;   /* d: 2^32 進、下位から */
static zbig *ZB = 0; static long long ZN = 0, ZCAP = 0;
static long long *ZH = 0; static long long ZHC = 0;
/* 引き算は符号なしで。符号付きの溢れは未定義動作で、最適化に消される。 */
#define ZISBIG(w) (((uint64_t)(w) - (uint64_t)ZBLO) < (uint64_t)ZN)
#define ZIDX(w)   ((long long)((uint64_t)(w) - (uint64_t)ZBLO))

static int zmcmp(const uint32_t*a,int an,const uint32_t*b,int bn){
  if(an!=bn) return an<bn?-1:1;
  for(int i=an-1;i>=0;i--) if(a[i]!=b[i]) return a[i]<b[i]?-1:1;
  return 0; }
static int zmadd(const uint32_t*a,int an,const uint32_t*b,int bn,uint32_t*o){
  int n = an>bn?an:bn; uint64_t c=0;
  for(int i=0;i<n;i++){ uint64_t s=c; if(i<an)s+=a[i]; if(i<bn)s+=b[i];
    o[i]=(uint32_t)s; c=s>>32; }
  if(c) o[n++]=(uint32_t)c;
  return n; }
static int zmsub(const uint32_t*a,int an,const uint32_t*b,int bn,uint32_t*o){
  int64_t br=0;                                   /* a >= b が前提 */
  for(int i=0;i<an;i++){ int64_t s=(int64_t)a[i]-br-(i<bn?(int64_t)b[i]:0);
    if(s<0){ s+=((int64_t)1<<32); br=1; } else br=0; o[i]=(uint32_t)s; }
  int n=an; while(n>0 && o[n-1]==0) n--;
  return n; }
static int zmmul(const uint32_t*a,int an,const uint32_t*b,int bn,uint32_t*o){
  for(int i=0;i<an+bn;i++) o[i]=0;
  for(int i=0;i<an;i++){ uint64_t c=0;
    for(int j=0;j<bn;j++){ uint64_t s=(uint64_t)a[i]*b[j]+o[i+j]+c;
      o[i+j]=(uint32_t)s; c=s>>32; }
    o[i+bn]=(uint32_t)c; }
  int n=an+bn; while(n>0 && o[n-1]==0) n--;
  return n; }
/* 二進の筆算。速くはないが正しい。 */
static void zmdiv(const uint32_t*a,int an,const uint32_t*b,int bn,
                  uint32_t*q,int*qn,uint32_t*r,int*rn){
  int rl = bn + 1;
  for(int i=0;i<an;i++) q[i]=0;
  for(int i=0;i<rl;i++) r[i]=0;
  for(long long bit=(long long)an*32-1; bit>=0; bit--){
    uint32_t c = (a[bit>>5]>>(bit&31)) & 1u;
    for(int i=0;i<rl;i++){ uint32_t nc = r[i]>>31; r[i]=(r[i]<<1)|c; c=nc; }
    int rr=rl; while(rr>0 && r[rr-1]==0) rr--;
    if(zmcmp(r,rr,b,bn)>=0){ int nn=zmsub(r,rr,b,bn,r);
      for(int i=nn;i<rl;i++) r[i]=0;
      q[bit>>5] |= 1u<<(bit&31); } }
  int n=an; while(n>0 && q[n-1]==0) n--; *qn=n;
  n=rl; while(n>0 && r[n-1]==0) n--; *rn=n; }

static uint64_t zhash(int sg,const uint32_t*d,int n){
  uint64_t h=1469598103934665603ULL ^ (uint64_t)(sg<0);
  for(int i=0;i<n;i++){ h^=d[i]; h*=1099511628211ULL; }
  return h; }
static i64 zmk(int sg,const uint32_t*d,int n){
  while(n>0 && d[n-1]==0) n--;
  if(n==0) return 0;
  if(n<=2){ uint64_t v=d[0]; if(n==2) v |= ((uint64_t)d[1])<<32;
    if(v <= (uint64_t)ZFIT) return sg<0 ? -(i64)v : (i64)v; }
  if(ZHC==0){ ZHC=1024; ZH=(long long*)malloc(sizeof(long long)*ZHC);
    for(long long i=0;i<ZHC;i++) ZH[i]=-1; }
  uint64_t h=zhash(sg,d,n); long long m=ZHC-1, p=(long long)(h&m);
  while(ZH[p]>=0){ zbig *z=&ZB[ZH[p]];
    if(z->sg==sg && z->n==n && !memcmp(z->d,d,(size_t)n*4)) return ZBLO+ZH[p];
    p=(p+1)&m; }
  if(ZN==ZCAP){ ZCAP=ZCAP?ZCAP*2:64; ZB=(zbig*)realloc(ZB,sizeof(zbig)*(size_t)ZCAP); }
  ZB[ZN].sg=sg; ZB[ZN].n=n;
  ZB[ZN].d=(uint32_t*)malloc((size_t)n*4); memcpy(ZB[ZN].d,d,(size_t)n*4);
  ZH[p]=ZN; ZN++;
  if(ZN*2 > ZHC){                                   /* 表を広げる */
    long long nc=ZHC*2; long long *nh=(long long*)malloc(sizeof(long long)*nc);
    for(long long i=0;i<nc;i++) nh[i]=-1;
    for(long long i=0;i<ZN;i++){ uint64_t hh=zhash(ZB[i].sg,ZB[i].d,ZB[i].n);
      long long q=(long long)(hh&(nc-1)); while(nh[q]>=0) q=(q+1)&(nc-1); nh[q]=i; }
    free(ZH); ZH=nh; ZHC=nc; }
  return ZBLO+ZN-1; }
static void zof(i64 w,int *sg,uint32_t *buf,const uint32_t **d,int *n){
  if(ZISBIG(w)){ zbig *z=&ZB[ZIDX(w)]; *sg=z->sg; *d=z->d; *n=z->n; return; }
  uint64_t v = w<0 ? (uint64_t)(-(w+1))+1 : (uint64_t)w;
  *sg = w<0 ? -1 : 1; buf[0]=(uint32_t)v; buf[1]=(uint32_t)(v>>32);
  *d=buf; *n = buf[1] ? 2 : (buf[0] ? 1 : 0); }
#define ZDEC(w,sg,d,n) uint32_t _b##w[2]; int sg,n; const uint32_t *d; \
                       zof(w,&sg,_b##w,&d,&n);

static i64 z_addsub(i64 a,i64 b,int neg){
  ZDEC(a,sa,da,na) ZDEC(b,sb0,db,nb) int sb = neg ? -sb0 : sb0;
  uint32_t *o=(uint32_t*)malloc((size_t)((na>nb?na:nb)+2)*4); i64 r;
  if(sa==sb){ int n=zmadd(da,na,db,nb,o); r=zmk(sa,o,n); }
  else { int c=zmcmp(da,na,db,nb);
    if(c==0) r=0;
    else if(c>0){ int n=zmsub(da,na,db,nb,o); r=zmk(sa,o,n); }
    else { int n=zmsub(db,nb,da,na,o); r=zmk(sb,o,n); } }
  free(o); return r; }
static i64 z_add(i64 a,i64 b){
  if(!ZISBIG(a)&&!ZISBIG(b)){ i64 r;
    if(!__builtin_add_overflow(a,b,&r) && r<=ZFIT && r>=-ZFIT) return r; }
  return z_addsub(a,b,0); }
static i64 z_sub(i64 a,i64 b){
  if(!ZISBIG(a)&&!ZISBIG(b)){ i64 r;
    if(!__builtin_sub_overflow(a,b,&r) && r<=ZFIT && r>=-ZFIT) return r; }
  return z_addsub(a,b,1); }
static i64 z_mul(i64 a,i64 b){
  if(!ZISBIG(a)&&!ZISBIG(b)){ i64 r;
    if(!__builtin_mul_overflow(a,b,&r) && r<=ZFIT && r>=-ZFIT) return r; }
  ZDEC(a,sa,da,na) ZDEC(b,sb,db,nb)
  if(na==0||nb==0) return 0;
  uint32_t *o=(uint32_t*)malloc((size_t)(na+nb+1)*4);
  int n=zmmul(da,na,db,nb,o); i64 r=zmk(sa*sb,o,n); free(o); return r; }
static int z_cmp(i64 a,i64 b){
  if(!ZISBIG(a)&&!ZISBIG(b)) return a<b?-1:(a>b?1:0);
  ZDEC(a,sa,da,na) ZDEC(b,sb,db,nb)
  if(na==0&&nb==0) return 0;
  if(na==0) return sb>0?-1:1;
  if(nb==0) return sa>0?1:-1;
  if(sa!=sb) return sa<sb?-1:1;
  int c=zmcmp(da,na,db,nb); return sa>0?c:-c; }
/* 除算は **床** で。解釈実行（Python）と同じでなければ答えが二つになる。 */
static i64 z_div(i64 a,i64 b){
  if(b==0) return 0;
  if(!ZISBIG(a)&&!ZISBIG(b)){ i64 q=a/b, r=a%b; if(r!=0 && ((r<0)!=(b<0))) q--; return q; }
  ZDEC(a,sa,da,na) ZDEC(b,sb,db,nb)
  if(nb==0) return 0;
  int _w = (na>nb?na:nb)+2;
  uint32_t *q=(uint32_t*)calloc((size_t)_w,4), *rm=(uint32_t*)calloc((size_t)_w,4);
  int qn,rn; zmdiv(da,na,db,nb,q,&qn,rm,&rn);
  i64 quo=zmk(sa*sb,q,qn); i64 rem=zmk(sa,rm,rn);
  free(q); free(rm);
  if(rem!=0 && sa*sb<0) quo=z_sub(quo,1);
  return quo; }
static i64 z_mod(i64 a,i64 b){
  if(b==0) return 0;
  if(!ZISBIG(a)&&!ZISBIG(b)){ i64 r=a%b; if(r!=0 && ((r<0)!=(b<0))) r+=b; return r; }
  return z_sub(a, z_mul(z_div(a,b), b)); }
static char *zstr(i64 w){
  static char bufs[4][512]; static int bi=0; char *out=bufs[bi=(bi+1)&3];
  if(!ZISBIG(w)){ snprintf(out,512,"%lld",(long long)w); return out; }
  zbig *z=&ZB[ZIDX(w)];
  int n=z->n; uint32_t *t=(uint32_t*)malloc((size_t)n*4);
  memcpy(t,z->d,(size_t)n*4);
  char tmp[4096]; int p=0;
  while(n>0){ uint64_t rem=0;
    for(int i=n-1;i>=0;i--){ uint64_t cur=(rem<<32)|t[i]; t[i]=(uint32_t)(cur/10); rem=cur%10; }
    tmp[p++]=(char)('0'+rem);
    while(n>0 && t[n-1]==0) n--; }
  free(t);
  int o=0; if(z->sg<0) out[o++]='-';
  while(p>0 && o<500) out[o++]=tmp[--p];
  out[o]=0; return out; }
static i64 z_coord(i64 w){
  if(ZISBIG(w)){ fprintf(stderr,"coordinate does not fit a machine word: %s\n", zstr(w)); exit(4); }
  return w; }
/* **どの場のどの添字か**を言う。黙って落ちるのと、落ちて名前を言うのは違う。 */
static i64 z_coordn(i64 w, const char *nm, int ln){
  if(ZISBIG(w)){ fprintf(stderr,
    "coordinate does not fit a machine word: %s  (%s, line %d)\n", zstr(w), nm, ln);
    exit(4); }
  return w; }
"""


class Unsupported(Exception):
    pass


# ==========================================================================
# 1. 静的解析
# ==========================================================================

def bindings_indexed(rule, prog):
    if not rule.sources:
        yield {}, ()
        return
    lists = [(vs, prog.tables[src]) for vs, src in rule.sources]
    for combo in itertools.product(*[range(len(rows)) for _, rows in lists]):
        env = {}
        for (vs, rows), ri in zip(lists, combo):
            for n, v in zip(vs, rows[ri]):
                env[n] = v
        yield env, combo


class Plan:
    def __init__(self, prog):
        self.prog = prog
        self.atom = {}        # atom -> dense code
        self.dom = {}         # field -> [size per dim]
        self.arity = {}
        self.kind = {}        # (field, dim) -> 'int' | 'atom'
        self.setuniv = {}
        self.valkind = {}   # field -> 'atom' if its VALUES are atoms
        self.setkind = {}   # set field -> 'atom' | 'int' (codes collide otherwise)
        self.items = {}       # rule id -> [(env, rowidx)]
        self.slot = {}        # field -> absolute slot base
        self.perm = {}        # （廃止: 配列の置換は成立しない。renumber を読むこと）
        self.recode = None    # 座標の再番号付け: 旧座標 -> 新座標
        self.recols = set()   # 再番号付けする表の列 (表名, 列)
        self.cells = 0

    def recoded(self, v):
        """座標としての符号。再番号付けが有効なら、そちらを返す。"""
        c = self.code(v)
        if self.recode is not None and not isinstance(v, str):
            return self.recode.get(c, c)
        return c

    def code(self, v):
        if isinstance(v, bool): return 1 if v else 0
        if isinstance(v, int): return v
        if v not in self.atom:
            self.atom[v] = len(self.atom)
        return self.atom[v]


def analyse(prog):
    p = Plan(prog)
    if prog.ctors:
        raise Unsupported("constructors produce 56-bit content addresses; the "
                          "native backend needs hash tables instead of dense arrays")
    for r in prog.rules:
        if any(not isinstance(src, str) for _v, src in r.sources):
            raise Unsupported("coordinate ranges (`for (i) in a .. b`) are "
                              "interpreter-only for now")
    if prog.sources or prog.channels:
        raise Unsupported("effects (source/emit) are host-side; native backend "
                          "would need the host protocol linked in")
    if prog.renders:
        raise Unsupported("`render` writes a field as a byte sequence; the native "
                          "backend prints numbers only (invariant 6: never guess)")
    for f, lat in prog.fields.items():
        if lat.name in ('fourv', 'bag'):
            raise Unsupported(f"lattice `{lat.name}` is outside the native fragment")
    for r in prog.rules:
        for k in r.keys:
            s = set(); L.field_refs(k, s)
            if s:
                raise Unsupported(f"line {r.lineno}: key expression reads a field")
        p.items[r.id] = list(bindings_indexed(r, prog))

    # atoms first (so codes are stable), then key domains
    for t, rows in prog.tables.items():
        for row in rows:
            for x in row:
                p.code(x)

    store = {f: {} for f in prog.fields}
    seen = {}
    def note(f, keys):
        ar = len(keys[0]) if keys else 0
        if f in p.arity and p.arity[f] != ar:
            raise Unsupported(f"field {f} used with two arities")
        p.arity[f] = ar
        hi = seen.setdefault(f, [0] * ar)
        for k in keys:
            for d in range(ar):
                raw = k[d]
                kind = 'int' if isinstance(raw, int) and not isinstance(raw, bool) else 'atom'
                prev = p.kind.setdefault((f, d), kind)
                if prev != kind:
                    raise Unsupported(f"field {f} dim {d} mixes integers and atoms")
                c = p.code(raw)
                if c < 0: raise Unsupported(f"field {f}: negative coordinate {c}")
                hi[d] = max(hi[d], c)

    for r in prog.rules:
        ks = [tuple(L.ev(x, env, store, prog.fields) for x in r.keys)
              for env, _ in p.items[r.id]]
        note(r.target, ks or [()])
        for e in [r.value] + r.guards:
            for f, idx in _frefs(e):
                ks2 = [tuple(L.ev(x, env, store, prog.fields) for x in idx)
                       for env, _ in p.items[r.id]]
                note(f, ks2 or [()])

    for f in prog.fields:
        p.arity.setdefault(f, 0); seen.setdefault(f, [])
        p.dom[f] = [d + 1 for d in seen[f]]
        sz = 1
        for d in p.dom[f]: sz *= d
        if sz > MAXCELLS: raise Unsupported(f"field {f} needs {sz} cells")
        p.slot[f] = p.cells; p.cells += sz

    for f, lat in prog.fields.items():
        if lat.name != 'set': continue
        u = {}
        for r in prog.rules:
            if r.target != f: continue
            if r.value[0] != 'set':
                raise Unsupported(f"line {r.lineno}: set field needs a set literal")
            for env, _ in p.items[r.id]:
                for x in r.value[1]:
                    raw = L.ev(x, env, store, prog.fields)
                    kind = 'atom' if isinstance(raw, str) else 'int'
                    prev = p.setkind.setdefault(f, kind)
                    if prev != kind:
                        raise Unsupported(f"set {f} mixes atoms and integers")
                    u.setdefault(p.code(raw), len(u))
        if len(u) > SETBITS: raise Unsupported(f"set universe too large for {f}")
        p.setuniv[f] = u

    # do the field's VALUES carry atoms?  (flat fields holding "done"/"failed")
    for r in prog.rules:
        if prog.fields[r.target].name in ('set', 'sum', 'count', 'or', 'and'):
            continue
        for env, _ in p.items[r.id]:
            try: v = L.ev(r.value, env, store, prog.fields)
            except Exception: continue
            if isinstance(v, str):
                p.valkind[r.target] = 'atom'; p.code(v)

    for r in prog.rules:
        if prog.fields[r.target].name in ('sum', 'count'):
            s = set(); L.field_refs(r.value, s)
            if s: raise Unsupported(f"line {r.lineno}: aggregate contribution reads a field")
    return p


def _frefs(e, out=None):
    out = [] if out is None else out
    k = e[0]
    if k == 'fref':
        out.append((e[1], e[2]))
        for x in e[2]: _frefs(x, out)
    elif k in ('bin', 'cmp', 'fn', 'geq'):
        _frefs(e[2] if k != 'geq' else e[1], out)
        _frefs(e[3] if k != 'geq' else e[2], out)
    elif k in ('not', 'bnot'):
        _frefs(e[1], out)
    elif k == 'set':
        for x in e[1]: _frefs(x, out)
    return out


def flatkey(p, f, k):
    """座標 → 密配列の添字。

    **ここが第三の埋め込みである**（CLAUDE.md §1）。
    時間への埋め込み（スケジューラ）と同じ操作を、記憶に対して行う場所。
    既定は辞書式で、これは C の幾何も D も見ていない —— von Neumann の
    「記憶は整数で番地付けされた一本の線」をそのまま受け入れている。

    p.perm[f] があれば、それは D の深さ順に並べ直した配置である。
    同じ深さのセルが連続に置かれるので、導出の前線が記憶を一直線に舐める。
    答えも仕事量も変わらない。**動くのはキャッシュミスだけ。**"""
    flat, mult = 0, 1
    for d in reversed(range(len(k))):
        flat += p.recoded(k[d]) * mult; mult *= p.dom[f][d]
    return flat


# ==========================================================================
# 2. 式のコード生成
# ==========================================================================

def cexpr(e, r, p, V):
    k = e[0]
    if k == 'int':  return str(e[1])
    if k == 'str':  return str(p.code(e[1]))
    if k == 'bool': return "1" if e[1] else "0"
    if k == 'var':  return V[e[1]]
    if k == 'fref': return f"F_{e[1]}[{cidx(e[1], e[2], r, p, V)}]"
    if k == 'bin':
        fn = {'+': 'z_add', '-': 'z_sub', '*': 'z_mul', '/': 'z_div', '%': 'z_mod'}[e[1]]
        return f"{fn}({cexpr(e[2],r,p,V)}, {cexpr(e[3],r,p,V)})"
    if k == 'cmp':
        # **⊤ は「少なくとも真」である**（SPEC / `lattix.ev`）。⊥ ⊑ v ⊑ ⊤ の鎖の
        # 上で述語が単調であるためには、⊤ で立たなければならない。ここを偽に
        # 潰していたら、定義と機械語がまた食い違う。
        t = _topguards(e[2], r, p, V) + _topguards(e[3], r, p, V)
        c = f"(z_cmp({cexpr(e[2],r,p,V)}, {cexpr(e[3],r,p,V)}) {e[1]} 0)"
        return "(" + " || ".join(t + [c]) + ")" if t else c
    if k == 'not':  return f"(!({cexpr(e[1],r,p,V)}))"
    if k == 'fn':
        a, b = cexpr(e[2], r, p, V), cexpr(e[3], r, p, V)
        return f"(({a}) {'<' if e[1]=='min' else '>'} ({b}) ? ({a}) : ({b}))"
    if k == 'geq':
        fr = e[1]
        if fr[0] != 'fref': raise Unsupported("`is` needs a field on the left")
        lat = p.prog.fields[fr[1]].name
        a = cexpr(fr, r, p, V); c = cexpr(e[2], r, p, V)
        if lat == 'min':                    return f"({a} != INT64_MAX && z_cmp({a},{c}) <= 0)"
        if lat in ('max', 'count', 'sum'):  return f"({a} != INT64_MIN && z_cmp({a},{c}) >= 0)"
        if lat == 'or':                     return f"({a} >= (({c})?1:0))"
        if lat == 'and':                    return f"({a} <= (({c})?1:0))"
        if lat == 'flat':
            return f"({a} == INT64_MAX || ({a} != INT64_MIN && {a} == {c}))"
        raise Unsupported(f"`is` on lattice {lat}")
    raise Unsupported(f"expression node {k}")


def cidx(f, idx, r, p, V):
    if not idx: return "0"
    parts, mult = [], 1
    for d in reversed(range(len(idx))):
        e = idx[d]
        # 索引位置の整数リテラルも座標である。表と同じ番号に揃える。
        x = (str(p.recoded(e[1])) if e[0] == 'int' and p.recode is not None
             else (V[e[1]] if e[0] == 'var' else f"z_coord({cexpr(e, r, p, V)})"))
        parts.append(f"(({x}) * {mult})")
        mult *= p.dom[f][d]
    return " + ".join(reversed(parts))


def _topguards(e, r, p, V):
    """比較の中の **flat の ⊤** を集める。⊤ は「少なくとも真」なので、
    ここが立ったら比較そのものが立つ（`||` で短絡するので算術も踏まない）。"""
    out = []
    def walk(x):
        if not isinstance(x, tuple) or not x: return
        if x[0] == 'fref':
            if p.prog.fields[x[1]].name == 'flat':
                out.append(f"(F_{x[1]}[{cidx(x[1], x[2], r, p, V)}] == INT64_MAX)")
            return                      # 添字の中は座標であって比べられる値ではない
        if x[0] in ('bin', 'fn'): walk(x[2]); walk(x[3])
    walk(e)
    return out


def botguards(e, r, p, V, out, neg=False):
    """⊥ で発火しない読みを集める。**どの束でも** ⊥ は情報の不在である ——
    min の ⊥ は INF という値に見えるだけで、値ではない。
    ただし **否定の下は数えない** —— `not f[…]` は f が ⊥ のときにこそ発火する。"""
    k = e[0]
    if k == 'fref':
        lat = p.prog.fields[e[1]].name
        if lat in BOT and not neg:
            out.add(f"F_{e[1]}[{cidx(e[1], e[2], r, p, V)}] == {BOT[lat]}")
        for x in e[2]: botguards(x, r, p, V, out)      # 添字は否定の下でも要る
    elif k in ('bin', 'cmp', 'fn'):
        botguards(e[2], r, p, V, out, neg); botguards(e[3], r, p, V, out, neg)
    elif k in ('not',):
        botguards(e[1], r, p, V, out, True)
    elif k == 'set':
        for x in e[1]: botguards(x, r, p, V, out, neg)
    # `geq` handles bottom itself


# ==========================================================================
# 3. コード生成
# ==========================================================================

PRELUDE = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
typedef int64_t i64;
@@Z@@
typedef struct { i64 p; int it; } hnode;
typedef struct { hnode *a; int n, cap; } heap;
static void hpush(heap*h,i64 p,int it){
  if(h->n==h->cap){h->cap=h->cap?h->cap*2:1024;
    h->a=(hnode*)realloc(h->a,(size_t)h->cap*sizeof(hnode));}
  int i=h->n++; h->a[i].p=p; h->a[i].it=it;
  while(i>0){int q=(i-1)/2; if(h->a[q].p<=h->a[i].p)break;
    hnode t=h->a[q];h->a[q]=h->a[i];h->a[i]=t; i=q;} }
static int hpop(heap*h,i64*p,int*it){ if(!h->n)return 0;
  *p=h->a[0].p; *it=h->a[0].it; h->a[0]=h->a[--h->n]; int i=0;
  for(;;){int l=2*i+1,rr=l+1,m=i;
    if(l<h->n&&h->a[l].p<h->a[m].p)m=l; if(rr<h->n&&h->a[rr].p<h->a[m].p)m=rr;
    if(m==i)break; hnode t=h->a[m];h->a[m]=h->a[i];h->a[i]=t; i=m;} return 1; }
static long long JOINS=0, FIRES=0, CONFLICTS=0;
/* 束の join は可換・冪等なので、原子的に緩和するだけで並列化できる。
   ロックも所有権も要らない —— 情報を壊す書き込みが存在しないから。 */
static void zpar(void){ fprintf(stderr,
  "parallel atomic join on an unbounded integer is not supported\n"); exit(5); }
static inline int amin(i64 *p, i64 v){
  if(ZISBIG(v)||ZISBIG(*p)) zpar();
  i64 o=__atomic_load_n(p,__ATOMIC_RELAXED);
  while(v<o){ if(__atomic_compare_exchange_n(p,&o,v,1,__ATOMIC_RELAXED,__ATOMIC_RELAXED))
                return 1; }
  return 0; }
static inline int amax(i64 *p, i64 v){
  if(ZISBIG(v)||ZISBIG(*p)) zpar();
  i64 o=__atomic_load_n(p,__ATOMIC_RELAXED);
  while(v>o){ if(__atomic_compare_exchange_n(p,&o,v,1,__ATOMIC_RELAXED,__ATOMIC_RELAXED))
                return 1; }
  return 0; }
/* RANK[cell] = 1 + max rank of the cells that justified it.
   This is the derivation depth, and it is what makes the answer CHECKABLE:
   a value that only supports itself can never get a finite rank. */
static int RANK[%(CELLS)d];
""".replace("@@Z@@", Z_PRELUDE.replace("%", "%%"))


def generate(prog, p, par=False, sweep=False, topo=False, region=False):
    o = []
    e = o.append
    e(PRELUDE % dict(CELLS=max(p.cells,1)))
    for f, u in p.setuniv.items():
        cases = "".join(f"case {k}: return {v};" for k, v in u.items())
        e(f"static inline int setbit_{f}(i64 x){{ switch(x){{ {cases} }} return 0; }}")
    for t, rows in prog.tables.items():
        if not rows: continue
        ar = len(rows[0])
        # 座標として使われる列だけ、新しい番号で焼く。重みのようなデータ列は触らない。
        e(f"static const i64 T_{t}[{len(rows)}][{ar}] = {{"
          + ",".join("{" + ",".join(
              str(p.recoded(x) if (t, c) in p.recols else p.code(x))
              for c, x in enumerate(row)) + "}" for row in rows)
          + "};")
    for f, lat in prog.fields.items():
        sz = max(1, _size(p, f))
        if lat.name == 'set':
            w = max(1, (len(p.setuniv.get(f, {})) + 63) // 64)
            e(f"#define W_{f} {w}")
            e(f"static uint64_t F_{f}[{sz}][{w}];")
        else:
            e(f"static i64 F_{f}[{sz}];")
        e(f"#define SZ_{f} {sz}")

    decls, drivers = [], []
    for si, rules in enumerate(prog.strata):
        if rules:
            d, m = stratum(prog, p, si, rules, par=par, sweep=sweep,
                           topo=topo, region=region)
            decls.append(d); drivers.append(m)
    for d in decls: e(d)

    e("int main(void){")
    e("  struct timespec t0,t1;")
    for f, lat in prog.fields.items():
        if lat.name == 'set':
            e(f"  memset(F_{f},0,sizeof(F_{f}));")
        else:
            e(f"  for(int i=0;i<SZ_{f};i++) F_{f}[i]={BOT[lat.name]};")
    e("  clock_gettime(CLOCK_MONOTONIC,&t0);")
    for m in drivers: e(m)
    e("  clock_gettime(CLOCK_MONOTONIC,&t1);")
    e('  fprintf(stderr,"NATIVE_MS %.4f\\nJOINS %lld\\nFIRES %lld\\nCONFLICTS %lld\\n",'
      '(t1.tv_sec-t0.tv_sec)*1e3+(t1.tv_nsec-t0.tv_nsec)/1e6,JOINS,FIRES,CONFLICTS);')
    for si, rules in enumerate(prog.strata):
        if not rules: continue
        if region:
            e(f'  fprintf(stderr,"REG_HEIGHT %d\\nREG_WIDTH %d\\nREG_PASSES %d\\n",'
              f' REG_HEIGHT_{si}, REG_WIDTH_{si}, REG_PASSES_{si});')
        elif par: e(f'  fprintf(stderr,"BSP_ROUNDS %d\\n", BSP_ROUNDS_{si});')
        if sweep: e(f'  fprintf(stderr,"SWEEP_PASSES %d\\n", SWEEP_PASSES_{si});')
    for f, lat in prog.fields.items():
        ar = p.arity[f]; dims = p.dom[f]
        pm = None
        if p.recode is not None and ar == 1 and p.kind.get((f, 0)) == 'int' \
           and f in getattr(p, 'refields', ()):
            # 座標を付け替えたのだから、印字は元の名前に戻す。
            # **配置は記憶の都合、座標は意味の側にある。**
            inv = {v: k for k, v in p.recode.items()}
            pm = [inv.get(i, i) for i in range(p.dom[f][0])]
        if pm:
            # 配置を変えたのだから、座標に戻すには逆置換が要る。
            # **座標は配置ではない。** 添字は記憶の都合、座標は意味の側にある。
            e(f"  static const int INV_{f}[{len(pm)}]={{"
              + ",".join(map(str, pm)) + "};")
        e(f"  for(int i=0;i<SZ_{f};i++){{")
        if pm: e(f"    int _k=INV_{f}[i];")
        if lat.name == 'set':
            e(f"    int any=0; for(int w=0;w<W_{f};w++) if(F_{f}[i][w]) any=1;")
            e("    if(!any) continue;")
        else:
            e(f"    if(F_{f}[i]=={BOT[lat.name]}) continue;")
        e(f'    printf("{f}");')
        for d in range(ar):
            m = 1
            for q in range(d + 1, ar): m *= dims[q]
            v = "_k" if pm else "i"
            e(f'    printf(" %lld",(long long)(({v}/{m})%{dims[d]}));')
        if lat.name == 'set':
            e(f"    for(int b=0;b<{max(1,len(p.setuniv.get(f,{})))};b++)"
              f" if(F_{f}[i][b>>6]>>(b&63)&1) printf(\" %d\",b);")
            e(f'    printf(" @%d\\n", RANK[i+{p.slot[f]}]);')
        else:
            e('    printf(" = %s", zstr(F_' + f + '[i]));')
            e(f'    printf(" @%d\\n", RANK[i+{p.slot[f]}]);')
        e("  }")
    e("  return 0;}")
    return "\n".join(o)


def _size(p, f):
    sz = 1
    for d in p.dom[f]: sz *= d
    return sz


def stratum(prog, p, si, rules, par=False, sweep=False, topo=False, region=False):
    """Returns (file-scope declarations, in-main driver)."""
    store = {f: {} for f in prog.fields}
    items = []
    for r in rules:
        for env, rows in p.items[r.id]:
            items.append((r, env, rows))
    n = len(items)
    if n == 0:
        return "", ""
    D, M = [], []
    S = f"S{si}"

    D.append(f"static const short {S}_RULE[{n}]={{" +
             ",".join(str(r.id) for r, _, _ in items) + "};")
    maxs = max(len(r.sources) for r in rules)
    for s in range(maxs):
        D.append(f"static const int {S}_R{s}[{n}]={{" +
                 ",".join(str(rows[s] if s < len(rows) else 0)
                          for _, _, rows in items) + "};")
    tgt, absl = [], []
    for r, env, _ in items:
        k = tuple(L.ev(x, env, store, prog.fields) for x in r.keys)
        fk = flatkey(p, r.target, k)
        tgt.append(fk); absl.append(p.slot[r.target] + fk)
    D.append(f"static const int {S}_TGT[{n}]={{" + ",".join(map(str, tgt)) + "};")
    D.append(f"static const int {S}_ABS[{n}]={{" + ",".join(map(str, absl)) + "};")

    idx, selfkey = {}, []
    here = {r.target for r in rules}          # fields owned by THIS stratum
    rds, rdss = [], [0]
    for i, (r, env, _) in enumerate(items):
        rk = set()
        for ex in [r.value] + r.guards:
            for f, ix in _frefs(ex):
                kk = tuple(L.ev(x, env, store, prog.fields) for x in ix)
                rk.add((f, flatkey(p, f, kk)))
        for (f, kk) in rk:
            idx.setdefault(p.slot[f] + kk, []).append(i)
        own = [kk for (f, kk) in rk if f == r.target]
        selfkey.append(own[0] if own else -1)
        for (f, kk) in sorted(rk):
            if f in here: rds.append(p.slot[f] + kk)
        rdss.append(len(rds))
    fl, st = [], []
    for sl in range(p.cells):
        st.append(len(fl)); fl.extend(idx.get(sl, []))
    st.append(len(fl))
    D.append(f"static const int {S}_IX[{max(1,len(fl))}]={{" +
             (",".join(map(str, fl)) if fl else "0") + "};")
    D.append(f"static const int {S}_IXS[{p.cells+1}]={{" + ",".join(map(str, st)) + "};")

    D.append(f"static const int {S}_RDS[{max(1,len(rds))}]={{" +
             (",".join(map(str, rds)) if rds else "0") + "};")
    D.append(f"static const int {S}_RDSS[{n+1}]={{" + ",".join(map(str, rdss)) + "};")
    agg = any(prog.fields[r.target].name in ('sum', 'count') for r in rules)
    if agg:
        D.append(f"static char {S}_done[{n}];")

    # ---- the per-item body, as a real function -------------------------
    F = [f"static int fire_{S}(int IT){{", "  switch({}_RULE[IT]){{".format(S)]
    for r in rules:
        F.append(f"  case {r.id}: {{")
        V = {}
        for s, (vs, src) in enumerate(r.sources):
            for c, v in enumerate(vs):
                V[v] = f"T_{src}[{S}_R{s}[IT]][{c}]"
        bg = set(); botguards(r.value, r, p, V, bg)
        for g in r.guards: botguards(g, r, p, V, bg)
        if bg: F.append(f"    if({' || '.join(sorted(bg))}) return 0;")
        for g in r.guards:
            F.append(f"    if(!({cexpr(g,r,p,V)})) return 0;")
        lat = prog.fields[r.target].name
        T = f"{S}_TGT[IT]"
        if lat == 'set':
            F.append("    { int ch=0; JOINS++;")
            for x in r.value[1]:
                F.append(f"      {{ int b=setbit_{r.target}({cexpr(x,r,p,V)});")
                F.append(f"        if(!(F_{r.target}[{T}][b>>6]>>(b&63)&1)){{"
                         f" F_{r.target}[{T}][b>>6]|=1ULL<<(b&63); ch=1; }} }}")
            F.append("      if(ch){FIRES++; return 1;} return 2; }")
        elif lat in ('sum', 'count'):
            v = "1" if lat == 'count' else f"({cexpr(r.value,r,p,V)})"
            F.append(f"    if({S}_done[IT]) return 0;")
            F.append(f"    {S}_done[IT]=1; JOINS++;"
                     f" F_{r.target}[{T}]=z_add(F_{r.target}[{T}],{v});"
                     f" FIRES++; return 1;")
        elif lat == 'flat':
            F.append(f"    {{ i64 v={cexpr(r.value,r,p,V)}; JOINS++;")
            F.append(f"      if(F_{r.target}[{T}]==INT64_MIN){{ F_{r.target}[{T}]=v;"
                     f" FIRES++; return 1; }}")
            # **矛盾は ⊤ である**（定義がそう言っている）。前の値を握って
            # 黙って続けると、機械語だけが別の束を持つことになる。
            F.append(f"      if(F_{r.target}[{T}]!=v && F_{r.target}[{T}]!=INT64_MAX)"
                     f"{{ CONFLICTS++; F_{r.target}[{T}]=INT64_MAX;"
                     f" FIRES++; return 1; }} return 2; }}")
        else:
            op = {'min': '<', 'max': '>', 'or': '>', 'and': '<'}[lat]
            F.append(f"    {{ i64 v={cexpr(r.value,r,p,V)}; JOINS++;")
            if lat in ('or', 'and'): F.append("      v = v?1:0;")
            if par and lat in ('min', 'max'):
                fn = 'amin' if lat == 'min' else 'amax'
                F.append(f"      if({fn}(&F_{r.target}[{T}], v)) return 1;")
            else:
                cnd = (f"(F_{r.target}[{T}]=={BOT[lat]} || z_cmp(v,F_{r.target}[{T}]) {op} 0)"
                       if lat in ('min', 'max') else f"v {op} F_{r.target}[{T}]")
                F.append(f"      if({cnd}){{ F_{r.target}[{T}]=v;"
                         f" FIRES++; return 1; }}")
            F.append(f"      return F_{r.target}[{T}]=={BOT[lat]} ? 0 : 2; }}")
        F.append("  }")
    F.append("  }")
    F.append("  return 0;")
    F.append("}")
    D.extend(F)

    # ---- the engine ----------------------------------------------------
    D.append(f"#define RK_{S}(J,T,CH) do{{ int _m=0;"
             f" for(int _z={S}_RDSS[J];_z<{S}_RDSS[(J)+1];_z++)"
             f" if(RANK[{S}_RDS[_z]]>_m) _m=RANK[{S}_RDS[_z]];"
             f" if(CH) RANK[T]=_m+1;"
             f" }}while(0)")
    if sweep:
        # ── 幾何的掃引（Fast Sweeping; Zhao 2005）─────────────────────
        # 最短経路は eikonal 方程式である。Dijkstra（= Fast Marching）は
        # 値の順に前線を進めるが、**座標そのものが方向を持つ**ことを使わない。
        #
        # 特性線（最短経路）は座標方向に単調なので、座標順に前進掃引し、
        # 次に後退掃引すれば、格子サイズによらず定数回で収束する。
        # ヒープも前線も索引も要らない。ただの二重ループである。
        #
        # 私はこれを既に測っていた。v1.3 で BSP 1スレッドが rounds=2 で
        # 終わったのは「宣言順が幸運だった」のではなく、**掃引だったから**である。
        if topo:
            order, cyclic, ncomp = cell_order(prog, p, rules, items)
            D.append(f"/* topological order: {ncomp} SCCs, {cyclic} of them cyclic */")
        else:
            order = sorted(range(n), key=lambda i: (selfkey[i], tgt[i]))
        D.append(f"static const int {S}_ORD[{n}]={{" + ",".join(map(str, order)) + "};")
        D.append(f"static int SWEEP_PASSES_{si}=0;")
        M.append(f"  {{ /* stratum {si}: geometric sweep (no heap, no frontier) */")
        M.append(f"    int passes=0, changed=1;")
        M.append(f"    while(changed){{ changed=0; passes++;")
        M.append(f"      /* どのスケジューラも同じ規則で **順序の証人**（階数）を出す。")
        M.append(f"         掃引だけ出していなかったので、掃引の答えは検査にかけられなかった。")
        M.append(f"         生産側と検査側は同じ対象を見ている（CLAUDE.md §1）。 */")
        M.append(f"      if(passes&1){{ for(int q=0;q<{n};q++){{ int IT={S}_ORD[q];")
        M.append(f"        int _r=fire_{S}(IT); int t={S}_ABS[IT];")
        M.append(f"        if(_r) RK_{S}(IT,t,_r==1); if(_r==1) changed=1; }} }}")
        M.append(f"      else {{ for(int q={n}-1;q>=0;q--){{ int IT={S}_ORD[q];")
        M.append(f"        int _r=fire_{S}(IT); int t={S}_ABS[IT];")
        M.append(f"        if(_r) RK_{S}(IT,t,_r==1); if(_r==1) changed=1; }} }} }}")
        M.append(f"    SWEEP_PASSES_{si}=passes; }}")
        return "\n".join(D), "\n".join(M)
    if region:
        # ── 領域実行（v1.9）: 凝縮グラフの深さごとに並列領域を開く ────
        # 大域バリアは張らない。同期は「深さの境目」だけで、そこは
        # **構造が要求する順序** である（祖先が先）。
        # 同じ深さの中は互いに独立なので、スレッドに配ってよい。
        order, bounds, ncomp, height, width = cell_levels(prog, p, rules, items)
        D.append(f"/* regions: {ncomp} SCCs, height {height}, width {width} */")
        D.append(f"static const int {S}_ORD[{max(n,1)}]={{"
                 + ",".join(map(str, order)) + "};")
        D.append(f"static const int {S}_LVL[{height+1}]={{"
                 + ",".join(map(str, bounds)) + "};")
        D.append(f"static int REG_HEIGHT_{si}={height}, REG_WIDTH_{si}={width};")
        D.append(f"static int REG_PASSES_{si}=0;")
        M.append(f"  {{ /* stratum {si}: regional execution over the poset */")
        M.append(f"    /* 深さごとに並列領域を開く。**大域バリアではない** ——")
        M.append(f"       同期するのは深さの境目だけで、そこは構造が要求する順序である。")
        M.append(f"       仕事が薄い深さでは fork/join が仕事より高くつくので、")
        M.append(f"       閾値未満は直列で回す（v1.3 と同じ罠を踏まないため）。 */")
        M.append(f"    int passes=0;")
        M.append(f"    for(int lv=0; lv<{height}; lv++){{")
        M.append(f"      int a={S}_LVL[lv], b={S}_LVL[lv+1]; int changed=1;")
        M.append(f"      while(changed){{ changed=0; passes++;")
        M.append(f"        if(b-a >= 4096){{")
        M.append(f"          _Pragma(\"omp parallel for schedule(guided) reduction(|:changed)\")")
        M.append(f"          for(int q=a;q<b;q++){{ int IT={S}_ORD[q];")
        M.append(f"            int _r=fire_{S}(IT); int t={S}_ABS[IT];")
        M.append(f"            if(_r) RK_{S}(IT,t,_r==1);")
        M.append(f"            if(_r==1) changed=1; }}")
        M.append(f"        }} else {{")
        M.append(f"          for(int q=a;q<b;q++){{ int IT={S}_ORD[q];")
        M.append(f"            int _r=fire_{S}(IT); int t={S}_ABS[IT];")
        M.append(f"            if(_r) RK_{S}(IT,t,_r==1);")
        M.append(f"            if(_r==1) changed=1; }} }} }} }}")
        M.append(f"    REG_PASSES_{si}=passes; }}")
        return "\n".join(D), "\n".join(M)
    if par:
        # BSP: 前線を並列に緩和し、変化したスロットから次の前線を作る。
        # ラウンド数は導出鎖の長さ —— つまり **スパンそのもの** になるはず。
        # これがスパンという指標の唯一の現金化手段であり、反証の場でもある。
        M.append(f"  {{ /* stratum {si}: BSP parallel rounds */")
        M.append(f"    static char dirty[{p.cells}];")
        M.append(f"    int *cur=(int*)malloc(sizeof(int)*{max(n,len(fl))*2+16}),"
                 f" *nxt=(int*)malloc(sizeof(int)*{max(n,len(fl))*2+16});")
        M.append(f"    int ncur={n}, nnxt=0, rounds=0;")
        M.append(f"    for(int i=0;i<{n};i++) cur[i]=i;")
        M.append(f"    while(ncur){{ rounds++;")
        M.append(f"      _Pragma(\"omp parallel for schedule(guided)\")")
        M.append(f"      for(int q=0;q<ncur;q++){{ int IT=cur[q];")
        M.append(f"        if(fire_{S}(IT)==1) dirty[{S}_ABS[IT]]=1; }}")
        M.append(f"      nnxt=0;")
        M.append(f"      /* 前線の再構築は、いま処理した項目の書き先だけを見ればよい。")
        M.append(f"         全セル走査にすると、この直列部分が並列部分を食い潰す")
        M.append(f"         （最初の実装がまさにそれで、2スレッドの方が遅かった）。 */")
        M.append(f"      for(int q=0;q<ncur;q++){{ int sl={S}_ABS[cur[q]];")
        M.append(f"        if(dirty[sl]){{ dirty[sl]=0;")
        M.append(f"          for(int z={S}_IXS[sl];z<{S}_IXS[sl+1];z++) nxt[nnxt++]={S}_IX[z];")
        M.append(f"        }} }}")
        M.append(f"      int *t=cur; cur=nxt; nxt=t; ncur=nnxt; }}")
        M.append(f"    BSP_ROUNDS_{si}=rounds; free(cur); free(nxt); }}")
        D.append(f"static int BSP_ROUNDS_{si}=0;")
        return "\n".join(D), "\n".join(M)
    prio = _priority_ok(prog, rules)
    if prio:
        f0 = rules[0].target
        base = p.slot[f0]
        D.append(f"static const int {S}_RDK[{n}]={{" + ",".join(map(str, selfkey)) + "};")
        M.append(f"  {{ /* stratum {si}: priority queue over READ SLOTS.")
        M.append(f"       The certificate says the recursive delta is non-negative, so a")
        M.append(f"       value-ordered frontier settles each coordinate on first pop.")
        M.append(f"       Keying the heap on the slot rather than on the rule instance is")
        M.append(f"       what turns this from edge-centric relaxation into Dijkstra. */")
        M.append(f"    heap H; H.a=0;H.n=0;H.cap=0; i64 pp; int SL;")
        M.append(f"    #define VAL(S) F_{f0}[(S)-{base}]")
        M.append(f"    for(int i=0;i<{n};i++) if({S}_RDK[i]<0)")
        M.append(f"      {{ int _r=fire_{S}(i); int t={S}_ABS[i];"
                 f" if(_r) RK_{S}(i,t,_r==1);"
                 f" if(_r==1) hpush(&H, VAL(t), t); }}")
        M.append(f"    while(hpop(&H,&pp,&SL)){{")
        M.append(f"      if(pp > VAL(SL)) continue;            /* stale entry */")
        M.append(f"      for(int q={S}_IXS[SL];q<{S}_IXS[SL+1];q++){{ int j={S}_IX[q];")
        M.append(f"        int _r=fire_{S}(j); int t={S}_ABS[j];"
                 f" if(_r) RK_{S}(j,t,_r==1);"
                 f" if(_r==1) hpush(&H, VAL(t), t); }} }}")
        M.append(f"    #undef VAL")
        M.append(f"    free(H.a); }}")
    else:
        M.append("  { /* stratum %d : FIFO worklist over read slots */" % si)
        M.append(f"    static char inq[{p.cells}]; static int wq[{p.cells}+1];")
        M.append(f"    int qn={p.cells}+1, qh=0, qt=0;")
        M.append(f"    for(int i=0;i<{n};i++)")
        M.append(f"      {{ int _r=fire_{S}(i); int t={S}_ABS[i];"
                 f" if(_r) RK_{S}(i,t,_r==1);")
        M.append("        if(_r==1 && !inq[t]){ inq[t]=1; wq[qt]=t; qt=(qt+1)%qn; } }")
        M.append("    while(qh!=qt){ int SL=wq[qh]; qh=(qh+1)%qn; inq[SL]=0;")
        M.append(f"      for(int q={S}_IXS[SL];q<{S}_IXS[SL+1];q++){{ int j={S}_IX[q];")
        M.append(f"        int _r=fire_{S}(j); int t={S}_ABS[j];"
                 f" if(_r) RK_{S}(j,t,_r==1);")
        M.append("          if(_r==1 && !inq[t]){ inq[t]=1; wq[qt]=t; qt=(qt+1)%qn; } } }")
        M.append("  }")
    return "\n".join(D), "\n".join(M)


def cell_slots(prog, p, rules, items):
    """規則実例を「書き先スロット / 読み先スロット」に落とすだけ。

    D の計算はここには無い。**lattix.poset が唯一の実装である**（CLAUDE.md §1）。
    解釈実行はセルを (場, 座標) の組で呼び、ここは密配列のスロット番号で呼ぶ。
    見ているのは同じ D である。"""
    store = {f: {} for f in prog.fields}
    out = []
    for (r, env, _rows) in items:
        tgt = p.slot[r.target] + flatkey(
            p, r.target, tuple(L.ev(x, env, store, prog.fields) for x in r.keys))
        rds, mine = [], None
        for f, ix in _frefs(r.value) + [x for g in r.guards for x in _frefs(g)]:
            sl = p.slot[f] + flatkey(p, f, tuple(L.ev(x, env, store, prog.fields)
                                                 for x in ix))
            rds.append(sl)
            if mine is None or f == r.target: mine = sl
        out.append((tgt, rds, mine if mine is not None else -1))
    return out


def cell_levels(prog, p, rules, items):
    """D を深さごとに束ねる。同じ深さは互いに独立 —— 同時に走らせてよい。"""
    sl = cell_slots(prog, p, rules, items)
    P = L.poset([(t, rds) for (t, rds, _m) in sl], n=p.cells)
    return P['order'], P['bounds'], P['ncomp'], P['height'], P['width']


def cell_order(prog, p, rules, items):
    """掃引のための **線形拡大**。D の線形拡大であればどれでも健全である。

    v1.5 ではここで pop 順の全順序を作っていた。いまは D の深さ（最長路）で
    並べ、同じ深さの中は読みスロット順にする —— 局所性のためである。
    順序の証人としては同じ強さで、掃引のパス数も変わらない。"""
    sl = cell_slots(prog, p, rules, items)
    P = L.poset([(t, rds) for (t, rds, _m) in sl], n=p.cells)
    rd = [m for (_t, _r, m) in sl]
    cyclic = sum(1 for c in range(P['ncomp'])
                 if sum(1 for x in P['comp'] if x == c) > 1)
    order = sorted(range(len(items)), key=lambda i: (P['lvl'][i], rd[i]))
    return order, cyclic, P['ncomp']


def layout(prog, p):
    """記憶への埋め込み —— D の深さ順にセルを並べ直す。

    スケジューラは D を *時間* に埋め込む。これは同じ D を *空間* に埋め込む。
    新しい機構ではない。資源が違うだけである。

    コア数に依存しないので、1 コアの機械でも判定できる:
    答えも join 数も変わらず、変わるのは参照の局所性だけ。"""
    items = [(r, env, rows) for s in prog.strata for r in s
             for env, rows in p.items[r.id]]
    if not items: return 0
    sl = cell_slots(prog, p, None, items)
    P = L.poset([(t, rds) for (t, rds, _m) in sl], n=p.cells)
    # セルの深さ: 書き先はその領域の深さ、読まれるだけのセルも同じ規則で決まる
    depth = [P['level'][P['comp'][i]] for i in range(p.cells)]
    for f in prog.fields:
        base, size = p.slot[f], 1
        for d in p.dom[f]: size *= d
        if size <= 1: continue
        idx = sorted(range(size), key=lambda i: (depth[base + i], i))
        perm = [0] * size
        for new, old in enumerate(idx): perm[old] = new
        p.perm[f] = perm
    return sum(1 for f in p.perm)


def coord_space(prog, p):
    """座標の再番号付けが *安全か* を判定し、対象を返す。

    安全条件はひとつだけ: **座標が不透明であること**。
    座標変数が索引位置に裸でしか現れず、算術も比較もされないこと。

    `i+1` や `i < j` を書いているプログラムは、**座標自身が幾何を持っている**。
    そこに別の番号付けを被せてはいけないし、被せる必要も無い ——
    そういうプログラムでは既に座標順が D を精密化している（掃引が効く）。

    逆に座標が不透明（ただの名前）なら、幾何は無い。**なら D から与えればよい。**

    返す: (再番号付けする表の列の集合, 対象の場の集合) / 不可なら (None, None)
    """
    coordcols, impure, fields = set(), set(), set()
    for r in prog.rules:
        col = {}
        for vs, srcname in r.sources:
            for i, v in enumerate(vs): col[v] = (srcname, i)
        def index_pos(e, f):
            if e[0] == 'var':
                if e[1] in col: coordcols.add(col[e[1]])
                return True
            return e[0] == 'int'
        # 索引位置（書き先のキーと、読み先の添字）
        for e in r.keys:
            if not index_pos(e, r.target): return None, None
        fields.add(r.target)
        for f, ix in _frefs(r.value) + [x for g in r.guards for x in _frefs(g)]:
            fields.add(f)
            for e in ix:
                if not index_pos(e, f): return None, None
        # 索引以外に現れた変数は「データとしても使われている」
        def walk(e):
            k = e[0]
            if k == 'var':
                if e[1] in col: impure.add(col[e[1]])
            elif k in ('bin', 'cmp', 'fn'): walk(e[2]); walk(e[3])
            elif k == 'geq': walk(e[1]); walk(e[2])
            elif k in ('not', 'bnot'): walk(e[1])
            elif k == 'set':
                for x in e[1]: walk(x)
            elif k == 'fref':
                pass                      # 索引は上で見た。ここでは中に入らない
        for e in [r.value] + r.guards: walk(e)
    if coordcols & impure: return None, None
    if any(p.arity[f] != 1 for f in fields): return None, None
    for f in fields:
        if p.kind.get((f, 0)) != 'int': return None, None
    return coordcols, fields


def renumber(prog, p):
    """不透明な座標を、D の深さ順に振り直す。

    配列を置換するのではない。**名前そのものを付け替える。**
    生成 C は添字を座標から算術で作るので、名前が変われば配置も変わる ——
    間接参照はゼロ。埋め込みは記憶ではなく C（座標の空間）の側で行う。
    """
    cols, fields = coord_space(prog, p)
    if not cols: return 0
    items = [(r, env, rows) for st in prog.strata for r in st
             for env, rows in p.items[r.id]]
    if not items: return 0
    sl = cell_slots(prog, p, None, items)
    P = L.poset([(t, rds) for (t, rds, _m) in sl], n=p.cells)
    # 記憶を流れていくのはセルではなく **規則実例** である（辺の列）。
    # だから配置は D の深さではなく、**日程が最初に触る順** に従うべきだ。
    # ここを深さ順にすると、同じ深さの中の並びが実行順とずれて逆効果になる。
    lvl = P['lvl']
    seq = sorted(range(len(sl)), key=lambda i: (lvl[i], sl[i][2]))
    first, k = {}, 0
    for i in seq:
        t, rds, _m = sl[i]
        for c in list(rds) + [t]:
            for f in fields:
                base = p.slot[f]
                if base <= c < base + p.dom[f][0]:
                    v = c - base
                    if v not in first: first[v] = k; k += 1
    depth = {}
    for f in fields:
        for v in range(p.dom[f][0]):
            depth.setdefault(v, first.get(v, 1 << 30))
    order = sorted(depth, key=lambda v: (depth[v], v))
    p.recode = {v: i for i, v in enumerate(order)}
    p.recols = cols
    p.refields = fields
    return len(p.recode)


def dag_stat(prog, p, rules):
    """依存グラフがどれだけ DAG か —— 掃引が効くかどうかの *不変* な指標。

    幾何指標（座標順に沿う寄与の割合）は番号付けに依存していた。
    同じグラフでも番号を撹拌すると 1.00 → 0.50 に落ちる。
    それは「番号付けが位相順序にどれだけ近いか」を測っていたからである。

    DAG 度は **番号付けの取り方に依存しない**。グラフの構造だけで決まる。
    そして位相順序で掃引すれば、番号付けが何であれ DAG 部分は一掃で終わる。

    近似を測るのをやめて、近似される側を測る。"""
    items = [(r, env, rows) for r in rules for env, rows in p.items[r.id]]
    if not items: return 1.0
    store = {f: {} for f in prog.fields}
    succ = defaultdict(list)
    touched = set()
    for (r, env, _rows) in items:
        tgt = p.slot[r.target] + flatkey(
            p, r.target, tuple(L.ev(x, env, store, prog.fields) for x in r.keys))
        touched.add(tgt)
        for f, ix in _frefs(r.value) + [x for g in r.guards for x in _frefs(g)]:
            sl = p.slot[f] + flatkey(p, f, tuple(L.ev(x, env, store, prog.fields)
                                                 for x in ix))
            succ[sl].append(tgt); touched.add(sl)
    comp, ncomp = L._tarjan_scc(p.cells, [succ.get(i, []) for i in range(p.cells)])
    size = defaultdict(int)
    for i in touched: size[comp[i]] += 1
    incyc = sum(v for c, v in size.items() if v > 1)
    return 1.0 - incyc / max(len(touched), 1)


DAG_THRESHOLD = 0.95


def geometry_stat(prog, p, rules):
    """座標の単調性 —— 掃引が効くかどうかの静的な指標。

    最短経路は eikonal 方程式であり、特性線は座標方向に流れる。
    座標の番号付けがその流れに沿っていれば、前進掃引だけでほぼ収束する
    （Fast Sweeping; Zhao 2005）。ヒープも前線も要らない。

    測るのは一つだけ: 寄与の *書き先が読み元より後ろにある* 割合。
    1.0 に近ければ座標順が特性線に沿っている = 掃引が効く。
    0.5 付近なら番号付けが幾何を反映していない = 掃引は効かない。

    非負デルタの証明書が Dijkstra を許可したのと同じ形である ——
    安い静的な測定が、スケジューラを *許可* する。"""
    store = {f: {} for f in prog.fields}
    fwd = tot = 0
    for r in rules:
        if r.target not in r.reads: continue          # 再帰的な規則だけ
        for env, _rows in p.items[r.id]:
            tk = flatkey(p, r.target,
                         tuple(L.ev(x, env, store, prog.fields) for x in r.keys))
            for f, ix in _frefs(r.value) + [x for g in r.guards for x in _frefs(g)]:
                if f != r.target: continue
                rk = flatkey(p, f, tuple(L.ev(x, env, store, prog.fields) for x in ix))
                tot += 1
                if tk > rk: fwd += 1
    return (fwd / tot) if tot else 0.0


SWEEP_THRESHOLD = 0.90


def _priority_ok(prog, rules):
    tg = {r.target for r in rules}
    fs = tg | {f for r in rules for f in r.reads}
    if len(tg) != 1 or fs != tg: return False
    f0 = next(iter(tg))
    return (prog.fields[f0].name == 'min'
            and prog.certificates.get(f0, ("",))[0] == "CERTIFIED")


# ==========================================================================
# 4. ドライバ
# ==========================================================================

def compile_source(src, opt="-O2", keep=None, par=False, threads=None,
                   sweep=None, topo=False, region=False, place=True):
    prog = L.parse(src); L.check(prog)
    depth = L.stratify(prog); L.io_rounds(prog); L.certify(prog)
    plan = analyse(prog)
    geo = max((geometry_stat(prog, plan, s) for s in prog.strata if s), default=0.0)
    dag = min((dag_stat(prog, plan, s) for s in prog.strata if s), default=1.0)
    if place:
        renumber(prog, plan)
    if False:
        # **配列を置換するやり方は成立しない。** 生成 C は添字を座標から
        # *実行時に算術で* 計算する（`F_dist[j]`）。置換表を挟めば、
        # 置換表を引くこと自体がキャッシュミスになり、目的を失う。
        #
        # 記憶への埋め込みは、配置ではなく **座標の付け替え** でなければならない。
        # 座標を D の深さ順に振り直せば、C の添字算術がそのまま新しい配置になる。
        # 間接参照はゼロ。埋め込みは C（座標の空間）の側で行う —— CLAUDE.md §1。
        raise Unsupported("memory embedding must renumber coordinates (C), "
                          "not permute arrays: the generated C computes indices "
                          "arithmetically from coordinates, so an indirection "
                          "table costs the very miss it tries to remove")
    if region:
        # 領域実行は原子的な join が要る（同じ深さの領域は同時に走る）ので par を立てる。
        par, sweep, topo = True, False, False
    if sweep is None:
        # DAG 度が高ければ位相順序で掃引する。番号付けには一切依存しない。
        sweep = topo = (not par) and dag >= DAG_THRESHOLD
    elif topo:
        sweep = True
    csrc = generate(prog, plan, par=par, sweep=sweep, topo=topo, region=region)
    d = keep or tempfile.mkdtemp(prefix="lattix_")
    os.makedirs(d, exist_ok=True)
    cf = os.path.join(d, "prog.c"); ex = os.path.join(d, "prog")
    open(cf, "w").write(csrc)
    cmd = ["gcc", opt, "-march=native", "-w"]
    if par: cmd.append("-fopenmp")
    cmd += ["-o", ex, cf]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise Unsupported("gcc failed:\n" + r.stderr[:2500])
    return dict(prog=prog, plan=plan, exe=ex, csrc=cf, depth=depth,
                lines=len(csrc.splitlines()), geometry=geo, dag=dag,
                sweep=sweep, topo=topo, region=region, place=place)


def run_native(ex, threads=None):
    env = dict(os.environ)
    if threads: env["OMP_NUM_THREADS"] = str(threads)
    t = time.time()
    r = subprocess.run([ex], capture_output=True, text=True, env=env)
    wall = time.time() - t
    if r.returncode:
        raise Unsupported("native run failed")
    meta = {}
    for line in r.stderr.splitlines():
        k, _, v = line.partition(" ")
        if v:
            try: meta[k] = float(v)
            except ValueError: pass
    return r.stdout, meta, wall


def to_store(prog, p, stdout, want_rank=False):
    inv = {v: k for k, v in p.atom.items()}
    def dec(f, d, c):
        return inv[c] if p.kind.get((f, d)) == 'atom' else c
    store = {f: {} for f in prog.fields}
    rank = {f: {} for f in prog.fields}
    for line in stdout.splitlines():
        t = line.split()
        if not t: continue
        rk = 0
        if t[-1].startswith("@"):
            rk = int(t[-1][1:]); t = t[:-1]
        f = t[0]; lat = prog.fields[f]; ar = p.arity[f]
        key = tuple(dec(f, d, int(t[1 + d])) for d in range(ar))
        rest = t[1 + ar:]
        if lat.name == 'set':
            u = {v: k for k, v in p.setuniv[f].items()}
            at = p.setkind.get(f) == 'atom'
            store[f][key] = frozenset((inv[u[int(b)]] if at else u[int(b)])
                                      for b in rest)
            rank[f][key] = rk
        else:
            v = int(rest[-1])
            if lat.name in ('or', 'and'): v = bool(v)
            elif lat.name == 'flat' and v == (1 << 63) - 1: v = L.TOP   # 矛盾
            elif p.valkind.get(f) == 'atom': v = inv.get(v, v)
            store[f][key] = v
            rank[f][key] = rk
    return (store, rank) if want_rank else store


if __name__ == '__main__':
    path = sys.argv[1]
    info = compile_source(open(path).read(), keep=os.path.dirname(os.path.abspath(path)) + "/_gen")
    out, meta, wall = run_native(info['exe'])
    print(out, end="")
    print(f"# native {meta.get('NATIVE_MS',0):.4f} ms   joins {int(meta.get('JOINS',0))}   "
          f"C {info['lines']} lines", file=sys.stderr)
