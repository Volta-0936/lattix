/* Lattix — generated once from the PROGRAM. データは実行時に読む。 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
typedef int64_t i64;

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

static long long JOINS=0;
static i64 *T_e; static int N_e, A_e, LO_e;

/* 開番地法のハッシュ表。**密配列が使えないときの一般形。**
   鍵は座標の組（i64 の並び）。値は束の元。 */
typedef struct { i64 *k; i64 *v; char *used; long long cap, n; int ar; } map;
static uint64_t mix(uint64_t x){
  x ^= x>>33; x *= 0xff51afd7ed558ccdULL; x ^= x>>33;
  x *= 0xc4ceb9fe1a85ec53ULL; x ^= x>>33; return x; }
static void mgrow(map *m);
static long long mslot(map *m, const i64 *k){
  uint64_t h = 1469598103934665603ULL;
  for(int i=0;i<m->ar;i++) h = mix(h ^ (uint64_t)k[i]);
  long long i = (long long)(h & (uint64_t)(m->cap-1));
  for(;;){
    if(!m->used[i]) return i;
    int same = 1;
    for(int d=0; d<m->ar; d++) if(m->k[i*m->ar+d] != k[d]) { same = 0; break; }
    if(same) return i;
    i = (i+1) & (m->cap-1);
  } }
static void minit(map *m, int ar, i64 bot){
  m->ar = ar; m->cap = 1024; m->n = 0;
  m->k = (i64*)malloc(sizeof(i64)*(size_t)m->cap*(ar?ar:1));
  m->v = (i64*)malloc(sizeof(i64)*(size_t)m->cap);
  m->used = (char*)calloc((size_t)m->cap, 1); (void)bot; }
static void mgrow(map *m){
  long long oc = m->cap; i64 *ok = m->k, *ov = m->v; char *ou = m->used;
  m->cap *= 2; m->n = 0;
  m->k = (i64*)malloc(sizeof(i64)*(size_t)m->cap*(m->ar?m->ar:1));
  m->v = (i64*)malloc(sizeof(i64)*(size_t)m->cap);
  m->used = (char*)calloc((size_t)m->cap, 1);
  for(long long i=0;i<oc;i++) if(ou[i]){
    long long s = mslot(m, ok + i*m->ar);
    for(int d=0; d<m->ar; d++) m->k[s*m->ar+d] = ok[i*m->ar+d];
    m->v[s] = ov[i]; m->used[s] = 1; m->n++; }
  free(ok); free(ov); free(ou); }
static i64 mget(map *m, const i64 *k, i64 bot){
  long long s = mslot(m, k); return m->used[s] ? m->v[s] : bot; }
static int mput(map *m, const i64 *k, i64 v){
  long long s = mslot(m, k);
  if(!m->used[s]){
    for(int d=0; d<m->ar; d++) m->k[s*m->ar+d] = k[d];
    m->v[s] = v; m->used[s] = 1; m->n++;
    if(m->n*10 >= m->cap*7) mgrow(m);
    return 1; }
  m->v[s] = v; return 0; }

static i64 *F_lvl; static long long SZ_lvl; static int DOM_lvl;
static int DOM_lvl_0;
static int DOM_lvl_1;
static int *K_lvl;   /* 順序の証人（階数）。検査器が読む */
static i64 g_lvl(long long i){ return (i < 0 || i >= SZ_lvl) ? (0) : F_lvl[i]; }
static int r_lvl(long long i){ return (i < 0 || i >= SZ_lvl) ? 0 : K_lvl[i]; }
static int MAXC = 0;
static char SEEDF[4096][64]; static int SEEDA[4096];
static long long SEEDV[4096][8]; static int NSEED = 0;
#define SLACK 3

static void load_into(const char *path, int append){
  FILE *fp = fopen(path, "r");
  if(!fp){ fprintf(stderr, "cannot open %s\n", path); exit(2); }
  char name[128]; int nrows, ar;
  for(;;){
    if(fscanf(fp, "%127s", name) != 1) break;
    i64 *buf = 0;
    if(!strcmp(name, "field")){
      /* `field <名> <行数> <次数+1>` —— 外から与える場（source）。
         最後の列が値、前の列が座標。join で入れるので順序も重複も関係ない。 */
      char fld[128]; int nr, aw;
      if(fscanf(fp, "%127s %d %d", fld, &nr, &aw) != 3) break;
      for(int k2=0;k2<nr;k2++){
        long long tmp[8]; 
        for(int c2=0;c2<aw;c2++){
          long long v2; if(fscanf(fp, "%lld", &v2) != 1){ fprintf(stderr,"bad data\n"); exit(2); }
          /* **座標の広さを決めるのは座標だけである。** 最後の列は値であって
             座標ではない。値まで数えていたので、mtime のような大きな数を
             source で渡すと領域が壊れた（int への切り詰めで size 1 になる）。 */
          tmp[c2]=v2; if(c2 + 1 < aw && v2 > MAXC) MAXC=(int)v2; }
        if(NSEED < 4096){ strncpy(SEEDF[NSEED], fld, 63);
          SEEDA[NSEED] = aw; for(int c2=0;c2<aw;c2++) SEEDV[NSEED][c2]=tmp[c2]; NSEED++; }
      }
      continue;
    }
    if(!strcmp(name, "bytes")){
      /* `bytes <表> <パス>` —— ファイルの中身を (位置, 文字コード) の表として読む。
         **列は座標に住んでいる。** ホストにバイトを運ばせる必要が無くなる。 */
      char tbl[128], path[1024];
      if(fscanf(fp, "%127s %1023s", tbl, path) != 2) break;
      FILE *bf = fopen(path, "rb");
      if(!bf){ fprintf(stderr, "cannot open file\n"); exit(2); }
      long cap = 1024, len = 0; unsigned char *raw = (unsigned char*)malloc((size_t)cap);
      int ch2;
      while((ch2 = fgetc(bf)) != EOF){
        if(len == cap){ cap *= 2; raw = (unsigned char*)realloc(raw, (size_t)cap); }
        raw[len++] = (unsigned char)ch2; }
      fclose(bf);
      nrows = (int)len + 1; ar = 2;                 /* 末尾に番兵の空白 */
      buf = (i64*)malloc(sizeof(i64)*(size_t)nrows*2);
      for(long k=0;k<len;k++){ buf[k*2]=k; buf[k*2+1]=raw[k];
        if((int)k > MAXC) MAXC=(int)k; if((int)raw[k] > MAXC) MAXC=(int)raw[k]; }
      buf[len*2]=len; buf[len*2+1]=32; if((int)len > MAXC) MAXC=(int)len;
      free(raw);
      strcpy(name, tbl);
      nrows = nrows; ar = 2;
    }
    else {
      if(fscanf(fp, "%d %d", &nrows, &ar) != 2) break;
      buf = (i64*)malloc(sizeof(i64) * (size_t)nrows * ar);
      for(long long k=0; k<(long long)nrows*ar; k++){
        long long v; if(fscanf(fp, "%lld", &v) != 1){ fprintf(stderr,"bad data\n"); exit(2);}
        buf[k] = v; if(v > MAXC) MAXC = (int)v; }
    }
    {
    if(!strcmp(name, "e")) {
      if(append && T_e) {
        T_e = (i64*)realloc(T_e, sizeof(i64)*(size_t)(N_e+nrows)*ar);
        memcpy(T_e + (long long)N_e*ar, buf, sizeof(i64)*(size_t)nrows*ar);
        LO_e = N_e; N_e += nrows; free(buf);
      } else { T_e=buf; N_e=nrows; A_e=ar; LO_e=0; }
      continue; }
    }
  }
  fclose(fp);
}
static void load(const char *p){ load_into(p, 0); }

static long long BASE_lvl;
static int SEMI_ON = 0;
static int *WQ; static long long WH, WT, WCAP; static char *INQ;
static void wpush(long long c){ if(INQ[c]) return; INQ[c]=1;
  WQ[WT]=(int)c; WT=(WT+1)%WCAP; }
static int *IXS_1_0, *IXL_1_0;
static int *IXS_1_1, *IXL_1_1;
static int *IXS_2_0, *IXL_2_0;
static int *IXS_2_1, *IXL_2_1;
static int *IXS_3_0, *IXL_3_0;
static int *IXS_3_1, *IXL_3_1;
static void build_semi(void){
  { IXS_1_0 = (int*)calloc((size_t)SZ_lvl+2, sizeof(int));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+0])))); if(_c<0||_c>=SZ_lvl) continue; IXS_1_0[_c+1]++; }
    for(long long i=0;i<SZ_lvl+1;i++) IXS_1_0[i+1]+=IXS_1_0[i];
    IXL_1_0 = (int*)malloc(sizeof(int)*(size_t)N_e);
    int *at=(int*)malloc(sizeof(int)*((size_t)SZ_lvl+2));
    memcpy(at, IXS_1_0, sizeof(int)*((size_t)SZ_lvl+2));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+0])))); if(_c<0||_c>=SZ_lvl) continue; IXL_1_0[at[_c]++] = _r; }
    free(at); }
  { IXS_1_1 = (int*)calloc((size_t)SZ_lvl+2, sizeof(int));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+1])))); if(_c<0||_c>=SZ_lvl) continue; IXS_1_1[_c+1]++; }
    for(long long i=0;i<SZ_lvl+1;i++) IXS_1_1[i+1]+=IXS_1_1[i];
    IXL_1_1 = (int*)malloc(sizeof(int)*(size_t)N_e);
    int *at=(int*)malloc(sizeof(int)*((size_t)SZ_lvl+2));
    memcpy(at, IXS_1_1, sizeof(int)*((size_t)SZ_lvl+2));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+1])))); if(_c<0||_c>=SZ_lvl) continue; IXL_1_1[at[_c]++] = _r; }
    free(at); }
  { IXS_2_0 = (int*)calloc((size_t)SZ_lvl+2, sizeof(int));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+0])))); if(_c<0||_c>=SZ_lvl) continue; IXS_2_0[_c+1]++; }
    for(long long i=0;i<SZ_lvl+1;i++) IXS_2_0[i+1]+=IXS_2_0[i];
    IXL_2_0 = (int*)malloc(sizeof(int)*(size_t)N_e);
    int *at=(int*)malloc(sizeof(int)*((size_t)SZ_lvl+2));
    memcpy(at, IXS_2_0, sizeof(int)*((size_t)SZ_lvl+2));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+0])))); if(_c<0||_c>=SZ_lvl) continue; IXL_2_0[at[_c]++] = _r; }
    free(at); }
  { IXS_2_1 = (int*)calloc((size_t)SZ_lvl+2, sizeof(int));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+1])))); if(_c<0||_c>=SZ_lvl) continue; IXS_2_1[_c+1]++; }
    for(long long i=0;i<SZ_lvl+1;i++) IXS_2_1[i+1]+=IXS_2_1[i];
    IXL_2_1 = (int*)malloc(sizeof(int)*(size_t)N_e);
    int *at=(int*)malloc(sizeof(int)*((size_t)SZ_lvl+2));
    memcpy(at, IXS_2_1, sizeof(int)*((size_t)SZ_lvl+2));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+1])))); if(_c<0||_c>=SZ_lvl) continue; IXL_2_1[at[_c]++] = _r; }
    free(at); }
  { IXS_3_0 = (int*)calloc((size_t)SZ_lvl+2, sizeof(int));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+0])))); if(_c<0||_c>=SZ_lvl) continue; IXS_3_0[_c+1]++; }
    for(long long i=0;i<SZ_lvl+1;i++) IXS_3_0[i+1]+=IXS_3_0[i];
    IXL_3_0 = (int*)malloc(sizeof(int)*(size_t)N_e);
    int *at=(int*)malloc(sizeof(int)*((size_t)SZ_lvl+2));
    memcpy(at, IXS_3_0, sizeof(int)*((size_t)SZ_lvl+2));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+0])))); if(_c<0||_c>=SZ_lvl) continue; IXL_3_0[at[_c]++] = _r; }
    free(at); }
  { IXS_3_1 = (int*)calloc((size_t)SZ_lvl+2, sizeof(int));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+1])))); if(_c<0||_c>=SZ_lvl) continue; IXS_3_1[_c+1]++; }
    for(long long i=0;i<SZ_lvl+1;i++) IXS_3_1[i+1]+=IXS_3_1[i];
    IXL_3_1 = (int*)malloc(sizeof(int)*(size_t)N_e);
    int *at=(int*)malloc(sizeof(int)*((size_t)SZ_lvl+2));
    memcpy(at, IXS_3_1, sizeof(int)*((size_t)SZ_lvl+2));
    for(int _r=0;_r<N_e;_r++) { long long _c=(((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r*A_e+1])))); if(_c<0||_c>=SZ_lvl) continue; IXL_3_1[at[_c]++] = _r; }
    free(at); }
}
static int sweep0_0(void){ int changed=0;
  for(int _r0=0; _r0<N_e; _r0++){
    int _rk0 = 0;
    { i64 _v = 1; long long _t = ((((0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 3, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk0 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk0 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk0 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
  return changed; }
static int sweep0(void){ int changed=0;
  changed |= sweep0_0();
  return changed; }
static int sweep1_0(void){ int changed=0;
  for(int _r0=0; _r0<N_e; _r0++){
    if(!(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk1 = 0;
    if(r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk1) _rk1 = r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk1) _rk1 = r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((1))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk1 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk1 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk1 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
  return changed; }
static int sweep1(void){ int changed=0;
  changed |= sweep1_0();
  return changed; }
static int sweep2_0(void){ int changed=0;
  for(int _r0=0; _r0<N_e; _r0++){
    if(!(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk2 = 0;
    if(r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk2) _rk2 = r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk2) _rk2 = r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((2))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk2 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk2 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk2 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
  return changed; }
static int sweep2(void){ int changed=0;
  changed |= sweep2_0();
  return changed; }
static int sweep3_0(void){ int changed=0;
  for(int _r0=0; _r0<N_e; _r0++){
    if(!(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk3 = 0;
    if(r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk3) _rk3 = r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk3) _rk3 = r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((3))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk3 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk3 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk3 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
  return changed; }
static int sweep3(void){ int changed=0;
  changed |= sweep3_0();
  return changed; }
static int sweepN0(void){ int changed=0;
  for(int _r0=LO_e; _r0<N_e; _r0++){
    int _rk0 = 0;
    { i64 _v = 1; long long _t = ((((0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 3, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk0 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk0 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk0 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
  return changed; }
static int sweepN1(void){ int changed=0;
  for(int _r0=LO_e; _r0<N_e; _r0++){
    if(!(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk1 = 0;
    if(r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk1) _rk1 = r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk1) _rk1 = r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((1))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk1 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk1 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk1 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
  return changed; }
static int sweepN2(void){ int changed=0;
  for(int _r0=LO_e; _r0<N_e; _r0++){
    if(!(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk2 = 0;
    if(r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk2) _rk2 = r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk2) _rk2 = r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((2))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk2 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk2 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk2 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
  return changed; }
static int sweepN3(void){ int changed=0;
  for(int _r0=LO_e; _r0<N_e; _r0++){
    if(!(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk3 = 0;
    if(r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk3) _rk3 = r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk3) _rk3 = r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((3))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk3 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk3 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk3 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
  return changed; }
static void drain0(void){
  int changed = 0; (void)changed;
  while(WH != WT){ long long _c0 = WQ[WH]; WH = (WH+1) % WCAP; INQ[_c0] = 0;
  } }
static void semi0(void){ sweep0(); drain0(); }
static void drain1(void){
  int changed = 0; (void)changed;
  while(WH != WT){ long long _c0 = WQ[WH]; WH = (WH+1) % WCAP; INQ[_c0] = 0;
    if(_c0 >= BASE_lvl && _c0 < BASE_lvl + SZ_lvl){
      long long _c = _c0 - BASE_lvl;
  for(int _q=IXS_1_0[_c]; _q<IXS_1_0[_c+1]; _q++){
    int _r0 = IXL_1_0[_q];
    if(!(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk1 = 0;
    if(r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk1) _rk1 = r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk1) _rk1 = r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((1))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk1 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk1 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk1 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
    }
    if(_c0 >= BASE_lvl && _c0 < BASE_lvl + SZ_lvl){
      long long _c = _c0 - BASE_lvl;
  for(int _q=IXS_1_1[_c]; _q<IXS_1_1[_c+1]; _q++){
    int _r0 = IXL_1_1[_q];
    if(!(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk1 = 0;
    if(r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk1) _rk1 = r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk1) _rk1 = r_lvl((((z_coordn(z_sub(1, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((1))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk1 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk1 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk1 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
    }
  } }
static void semi1(void){ sweep1(); drain1(); }
static void drain2(void){
  int changed = 0; (void)changed;
  while(WH != WT){ long long _c0 = WQ[WH]; WH = (WH+1) % WCAP; INQ[_c0] = 0;
    if(_c0 >= BASE_lvl && _c0 < BASE_lvl + SZ_lvl){
      long long _c = _c0 - BASE_lvl;
  for(int _q=IXS_2_0[_c]; _q<IXS_2_0[_c+1]; _q++){
    int _r0 = IXL_2_0[_q];
    if(!(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk2 = 0;
    if(r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk2) _rk2 = r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk2) _rk2 = r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((2))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk2 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk2 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk2 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
    }
    if(_c0 >= BASE_lvl && _c0 < BASE_lvl + SZ_lvl){
      long long _c = _c0 - BASE_lvl;
  for(int _q=IXS_2_1[_c]; _q<IXS_2_1[_c+1]; _q++){
    int _r0 = IXL_2_1[_q];
    if(!(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk2 = 0;
    if(r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk2) _rk2 = r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk2) _rk2 = r_lvl((((z_coordn(z_sub(2, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((2))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk2 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk2 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk2 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
    }
  } }
static void semi2(void){ sweep2(); drain2(); }
static void drain3(void){
  int changed = 0; (void)changed;
  while(WH != WT){ long long _c0 = WQ[WH]; WH = (WH+1) % WCAP; INQ[_c0] = 0;
    if(_c0 >= BASE_lvl && _c0 < BASE_lvl + SZ_lvl){
      long long _c = _c0 - BASE_lvl;
  for(int _q=IXS_3_0[_c]; _q<IXS_3_0[_c+1]; _q++){
    int _r0 = IXL_3_0[_q];
    if(!(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk3 = 0;
    if(r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk3) _rk3 = r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk3) _rk3 = r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((3))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk3 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk3 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk3 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
    }
    if(_c0 >= BASE_lvl && _c0 < BASE_lvl + SZ_lvl){
      long long _c = _c0 - BASE_lvl;
  for(int _q=IXS_3_1[_c]; _q<IXS_3_1[_c+1]; _q++){
    int _r0 = IXL_3_1[_q];
    if(!(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) != 0)) continue;
    if(!(!(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) != 0))) continue;
    if(g_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) == 0) continue;
    int _rk3 = 0;
    if(r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0]))))) > _rk3) _rk3 = r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+0])))));
    if(r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1]))))) > _rk3) _rk3 = r_lvl((((z_coordn(z_sub(3, 1), "lvl[0]", 0))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))));
    { i64 _v = 1; long long _t = ((((3))) * DOM_lvl_1 + (((T_e[(long long)_r0*A_e+1])))); JOINS++;
      if(_t < 0 || _t >= SZ_lvl) { fprintf(stderr, "coordinate out of range: lvl[%lld] (line 4, size %lld)\n", (long long)_t, (long long)SZ_lvl); exit(4); }
      if(_v > F_lvl[_t]){ F_lvl[_t] = _v; changed = 1;
        K_lvl[_t] = _rk3 + 1; if(SEMI_ON) wpush(BASE_lvl + _t); }
      else if(_v == F_lvl[_t] && _rk3 + 1 < K_lvl[_t])
        K_lvl[_t] = _rk3 + 1;   /* 支持は「等しいとき」だけ */
    }
  }
    }
  } }
static void semi3(void){ sweep3(); drain3(); }
static void seed_more(int _from){
  for(int _s=_from;_s<NSEED;_s++){
    if(!strcmp(SEEDF[_s], "lvl")){ long long _t = (((long long)SEEDV[_s][0]) * DOM_lvl_1 + (long long)SEEDV[_s][1]);
      i64 _v = (i64)SEEDV[_s][2];
      if(_v > F_lvl[_t]) { F_lvl[_t] = _v; K_lvl[_t] = 1; }
      continue; }
  }
}

int main(int argc, char **argv){
  if(argc < 2){ fprintf(stderr, "usage: %s data.lxd\n", argv[0]); return 2; }
  load(argv[1]);
  int D = MAXC + 1 + SLACK;
  DOM_lvl = D; SZ_lvl = 1;
  if(DOM_lvl < 4) DOM_lvl = 4;
  DOM_lvl_0 = 4;
  DOM_lvl_1 = 8;
  SZ_lvl *= DOM_lvl_0;
  SZ_lvl *= DOM_lvl_1;
  F_lvl = (i64*)malloc(sizeof(i64)*(size_t)SZ_lvl);
  for(long long i=0;i<SZ_lvl;i++) F_lvl[i] = 0;
  K_lvl = (int*)calloc((size_t)SZ_lvl, sizeof(int));
  BASE_lvl = 0;
  WCAP = (SZ_lvl) + 2;
  WQ = (int*)malloc(sizeof(int)*(size_t)WCAP);
  INQ = (char*)calloc((size_t)WCAP, 1); WH = WT = 0; SEMI_ON = 1;
  build_semi();
  seed_more(0);
  struct timespec t0,t1; clock_gettime(CLOCK_MONOTONIC,&t0);
  int rounds = 0;
  semi0();
  semi1();
  semi2();
  semi3();
  clock_gettime(CLOCK_MONOTONIC,&t1);
  fprintf(stderr, "NATIVE_MS %.4f\nJOINS %lld\nROUNDS %d\n",
          (t1.tv_sec-t0.tv_sec)*1e3+(t1.tv_nsec-t0.tv_nsec)/1e6, JOINS, rounds);
  for(int _f=2; _f<argc; _f++){
    long long j0 = JOINS; clock_gettime(CLOCK_MONOTONIC,&t0);
    int _ns0 = NSEED;
    load_into(argv[_f], 1);
    build_semi();
    if(NSEED > _ns0) seed_more(_ns0);   /* 外から来た場の行を入れる */
    sweepN0();
    if(NSEED > _ns0) { while(sweep0()) { } }
    drain0();
    sweepN1();
    if(NSEED > _ns0) { while(sweep1()) { } }
    drain1();
    sweepN2();
    if(NSEED > _ns0) { while(sweep2()) { } }
    drain2();
    sweepN3();
    if(NSEED > _ns0) { while(sweep3()) { } }
    drain3();
    clock_gettime(CLOCK_MONOTONIC,&t1);
    fprintf(stderr, "DELTA_MS %.4f\nDELTA_JOINS %lld\n",
      (t1.tv_sec-t0.tv_sec)*1e3+(t1.tv_nsec-t0.tv_nsec)/1e6, JOINS - j0);
  }
  for(long long i=0;i<SZ_lvl;i++){
    if(F_lvl[i]==0) continue;
    printf("lvl");
    printf(" %lld", (long long)((i / (1 * DOM_lvl_1)) % DOM_lvl_0));
    printf(" %lld", (long long)((i / (1)) % DOM_lvl_1));
    printf(" = %s @%d\n", zstr(F_lvl[i]), K_lvl[i]); }
  return 0; }