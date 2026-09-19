# -*- coding: utf-8 -*-
"""**「まだ書いていない種類のもの」を機械に書かせる**（気づき21 → 気づき46）。

   断片の文法（束 × 項の種 × ガードの辺）から小さな `.lx` を組み立て、
   `./lattix` で焼いて走らせ、解釈実行と **升まで**比べる。
   通す条件は二つ:

     1. 両方が受け取ったなら **答えが一致する**
     2. 解釈実行が断ったなら **焼いた側も断る**（黙って答えを出さない）

   撒く道具は答えを持っていない —— 二つの実装を突き合わせるだけである。
   手で書いた 53 本（accept.py）では一度も出なかった食い違いが、
   最初の 400 本で 39 本出た（`or` の場に値を書く / `sum` の 0 と ⊥）。

   **撒く文法が言語より狭ければ、狭い所の嘘は永久に生き延びる。**
   `if a[i] + 1 >= 2` は焼けて、走らせると segfault していた。この試験は
   終了コードを見ているので **捕まえられたはずだった** —— 撒いていなかった
   だけである。ここは「通る形」を並べる表であって、いつのまにか
   `accept.py` と同じ病（気づき21: 手で書いた試験は通る形を測っている）に
   なっていた。だから直した形は **必ずここにも撒く**:
   鎖の座標（`f0[f0[f0[i]]]`）、群（`a + b * c`）、辺の式（断るはず）。
"""
import os, re, struct, subprocess, sys, io, collections, tempfile, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
LATTIX = os.path.join(ROOT, "lattix")

def widths(src):
    order=[]; bnd={}; lat={}
    for ln in src.split('\n'):
        m=re.match(r'^field (\w+) : (\w+)(?: bound ([0-9 ]+))?\s*(?:#.*)?$', ln.split('#')[0].strip())
        if m:
            order.append(m.group(1)); lat[m.group(1)]=m.group(2)
            bnd[m.group(1)]=[int(x) for x in (m.group(3) or '64').split()]
    ar=collections.defaultdict(lambda:1)
    for ln in src.split('\n'):
        for m in re.finditer(r'(\w+)\[([^\]]*)\]', ln.split('#')[0]):
            if m.group(1) in bnd: ar[m.group(1)]=max(ar[m.group(1)], 1+m.group(2).count(','))
    # **升の幅は束が言う**（31_gen の `fwb`）—— `or` は一升 1 バイト。
    off={}; o=0
    for f in order:
        b=bnd[f]; w0=b[0]; w1=b[1] if len(b)>1 else w0
        cells=w0*w1 if ar[f]==2 else w0
        wb=1 if lat[f]=='or' else 8
        off[f]=(o,cells,w1 if ar[f]==2 else 1,wb); o+=cells*wb
    return order, lat, off, o

BOT={'min':2147483647,'max':-2147483647,'or':0,'flat':2147483647,'sum':0,'count':0}
LAT0 = ['max','min','or','sum','count']
V0 = ['c','i','c + i','c - i','i * 3','c / 2','c % 4','5','i + 1','c + 1',
      # **群**（積の連なり）。`a + b * c` は長いあいだ焼けなかった ——
      # 直したのだから撒く。撒かない形は、直っていないことにも気づけない。
      'c + i * 2','c * 2 + i','c - i * 2','i * 2 + c * 3']
G0 = ['','   if c >= 97','   if c != 32','   if i >= 2','   if c < 100','   if c == 97',
      # **辺に式**。焼く側は断らねばならない —— 長いあいだ黙って焼いて落ちていた。
      '   if c + 1 >= 98','   if c >= 96 + 1']
V1 = ['f0[i]','f0[i] + 1','f0[i] - i','f0[i] * 2','f0[i] / 4','f0[i] % 8','i',
      'f0[i] + f0[i]','f0[i+1]','f0[i-1]',
      # 場と場の算術 —— `/` と `%` はここに穴が空いていた（足し算になっていた）
      'f0[i] - f0[i-1]','f0[i] * f0[i-1]','f0[i] / f0[i-1]','f0[i] % f0[i-1]',
      # **鎖の座標**（座標の源に「読み」が無くて三段目が落ちていた）
      'f0[f0[i]]','f0[f0[f0[i]]]','f0[f0[i]] + 1','f0[f0[i-1]]',
      # **群**（`a + b * c` は `(a+b)*c` になっていた）
      'f0[i] + f0[i-1] * 2','f0[i] * 2 + f0[i-1] * 3','f0[i] - f0[i-1] * 2',
      'i * 2 + f0[i]','f0[i] + i * 3 + 1','f0[i] * 2 + i']
G1 = ['','   if f0[i] >= 5','   if i >= 1','   if not g0[i]','   if f0[i] != f0[i+1]',
      '   if f0[i] <= 90',
      # **鎖の座標をガードに**
      '   if f0[f0[i]] >= 3','   if not g0[f0[i]]','   if f0[f0[f0[i]]] >= 1',
      # **辺に式**（断るはず。`if a[i] + 1 >= 2` は焼けて segfault していた）
      '   if f0[i] + 1 >= 5','   if f0[i] >= f0[i-1] + 1','   if 1 + f0[i] >= 5',
      '   if not f0[i] + 1','   if f0[i] * 2 >= 4']
# **書き先の座標も種類がある。** 手で書いた試験も撒いた 150 本も
# `f[i]` しか置いていなかった —— 座標の種類を撒いていなかったから、
# 「二次元の読みを座標に置くと何も書かない」穴が生き延びた（気づき48）。
HD = ['f1[i]', 'f1[i+1]', 'f1[i-1]', 'f1[f0[i]]', 'f1[f0[f0[i]]]', 'f1[f0[i] + 1]']

def mk(l0,v0,g0,l1,v1,g1,hd='f1[i]'):
    return ("table ch = (0,32)\n"
            f"field f0 : {l0} bound 16\n"
            f"f0[i] <- {v0}   for (i,c) in ch{g0}\n"
            "field g0 : or bound 16\n"
            "g0[i] <- true   for (i,c) in ch if c >= 100\n"
            f"field f1 : {l1} bound 256\n"
            f"{hd} <- {v1}   for (i) in 1 .. 6{g1}\n")

W=76
N = int(sys.argv[1]) if len(sys.argv)>1 else 150
random.seed(7)
combos=[(a,b,c,d,e,f,h) for a in LAT0 for b in V0 for c in G0
                        for d in LAT0 for e in V1 for f in G1 for h in HD]
random.shuffle(combos); combos=combos[:N]

tmp=tempfile.mkdtemp(); data=b'hello Ldx'
import atexit, shutil; atexit.register(shutil.rmtree, tmp, True)   # 焼いた物は走り終えたら消す
ran=refused=rejected=0; bad=[]
print("="*W)
print("  **文法から撒いて突き合わせる** —— 解釈実行と焼いた符号を升まで")
print("="*W)
for k,c in enumerate(combos):
    src=mk(*c)
    try:
        p=L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
        p.tables['ch']=[(i,ch) for i,ch in enumerate(data)]
        ref_raw,_,_=L.run(p, out=io.StringIO())
    except Exception:
        # **解釈実行が断るものは、焼いた側も断らねばならない**
        rejected+=1
        rr=subprocess.run([LATTIX], input=src.encode(), capture_output=True)
        if rr.returncode==0 and rr.stdout[:4]==b'\x7fELF':
            e2=os.path.join(tmp,f"x{k}.out"); open(e2,'wb').write(rr.stdout); os.chmod(e2,0o755)
            q=subprocess.run([e2], input=data, capture_output=True)
            if q.returncode==0: bad.append((src,'解釈実行は断るのに焼いた側は答えを出した'))
        continue
    r=subprocess.run([LATTIX], input=src.encode(), capture_output=True)
    if r.returncode or r.stdout[:4]!=b'\x7fELF':
        bad.append((src,'焼けなかった')); continue
    exe=os.path.join(tmp,f"s{k}.out"); open(exe,'wb').write(r.stdout); os.chmod(exe,0o755)
    r2=subprocess.run([exe], input=data, capture_output=True)
    # **終了コード 6 は嘘ではない。** 「宣言した広さがこの入力に足りない」と
    # 言っている（解釈実行は宣言の広さを見ないので答えを出す）。限界を
    # 名指しで言うのは断りであって、食い違いではない。
    if r2.returncode==6:
        refused+=1; continue
    # **終了コード 5 は「⊤ に達した」と言っている**（焼いた符号は ⊤ の規律を持たない
    # ので、⊤ を作る所で止まる）。断りとして数えてよいのは、答えの定義の側も ⊤ を
    # 含むときだけである —— ⊤ の無い答えで 5 が出たら、それは嘘の断りである。
    if r2.returncode==5:
        tops=[1 for d in ref_raw.values() for v in d.values()
              if isinstance(v, L._Top) or (isinstance(v, dict) and any(isinstance(x, L._Top) for x in v.values()))]
        if tops: refused+=1; continue
        bad.append((src,'⊤ の無い答えで終了コード 5')); continue
    # **終了コード 4 は「値が ⊥ / ⊤ の印と重なった」と言っている。** 断りとして数えて
    # よいのは、答えの定義の側に印と同じ値があるときだけ（捨てられた値で止まることも
    # ありうるが、そのときはここで食い違いとして見えるので、見てから決める）。
    if r2.returncode==4:
        latn={f:p.fields[f].name for f in ref_raw}
        hit=[1 for f,d in ref_raw.items() for v in d.values()
             if isinstance(v,int) and not isinstance(v,bool) and (
                (latn[f] in ('min','flat') and v==2147483647) or
                (latn[f]=='max' and v==-2147483647) or
                (latn[f]=='flat' and v==2147483646))]
        if hit: refused+=1; continue
        bad.append((src,'印の無い答えで終了コード 4')); continue
    if r2.returncode==7:
        refused+=1
        if not re.search(rb'reason ([0-9A-F]): (.{16})\n', r2.stderr):
            bad.append((src,'理由を言わずに 7'))
        continue
    if r2.returncode!=0:
        bad.append((src,f'終了コード {r2.returncode}')); continue
    order,lat,off,tot=widths(src)
    if len(r2.stdout)!=tot:
        bad.append((src,f'面の大きさ {len(r2.stdout)} != {tot}')); continue
    got={}
    for f in order:
        o,cells,w1,wb=off[f]; bot=BOT[lat[f]]
        for i in range(cells):
            v=struct.unpack_from('<q' if wb==8 else '<B',r2.stdout,o+wb*i)[0]
            if v!=bot:
                key=(i//w1,i%w1) if w1>1 else (i,)
                got[(f,)+key]=v
    ref={}
    for f,d in ref_raw.items():
        latf=p.fields[f].name
        for kk,v in d.items():
            if v is True: v=1
            if v is False: continue
            if isinstance(v, dict): v = sum(v.values()) if latf=='sum' else len(v)
            if isinstance(v, (set, frozenset)): continue
            if not isinstance(v, int): v = 2147483646
            ref[(f,)+tuple(kk)]=v
    if got!=ref:
        og=sorted(set(got)-set(ref))[:2]; orr=sorted(set(ref)-set(got))[:2]
        dv=[x for x in sorted(set(got)&set(ref)) if got[x]!=ref[x]][:2]
        bad.append((src,f'焼のみ{og} 解釈のみ{orr} 値違い{[(x,ref[x],got[x]) for x in dv]}'))
        continue
    ran+=1
print(f"  組み立て {len(combos)}   解釈実行が断った {rejected}   "
      f"焼いて比べた {ran}   焼く側が断った {refused}")
print("-"*W)
if bad:
    print(f"  **食い違い {len(bad)} 本**")
    for src,why in bad[:8]:
        print("  "+"-"*60); print("  "+why)
        for ln in src.strip().split("\n"): print("    "+ln)
    print("="*W); sys.exit(1)
print("  **食い違いなし** —— 撒いた形はすべて、両者が同じ答えを出すか、両者が断った。")
print("  手で書いた試験は「通る形」を測っている（気づき21）。撒く方は形を選ばない。")
print("="*W)
