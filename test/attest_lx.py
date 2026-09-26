#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**答えの検査器を .lx で** —— attest/attest.lx を焼き、答えと壊した証明書にかける。

attest は二枚の .lx でできている:

    attest/front.lx    源のバイト → 規則の表（焼き手の前段 + 表を語にして描く尻尾）
    attest/attest.lx   [表][証人（値の面 + 階数の面。fd 3）][出した答え（stdout）][プログラムの入力] → 判定

判定は四つ。ATTESTED（答えは源の最小不動点）、REJECTED（最小不動点でない / 示せない /
源に答えが無い —— 見出しが言い分ける）、UNSUPPORTED（attest が持たない形。理由を言う）、
そして入力が attest の入力でない・源が焼けない。

ここでは表の意味の参照実装（attest/ir.py。表だけを読む Python）と判定を突き合わせる。
**許す組は五つだけ:** 両者 ATTESTED、両者 REJECTED、両者 UNSUPPORTED、参照が ATTESTED /
REJECTED で .lx が UNSUPPORTED（.lx の限界 —— 鎖の深さ・値の幅・実例の数）。
.lx が ATTESTED なのに参照がそう言わない組は **嘘** である。落ちる（終了コード 0 以外）のも破れ。

    使い方:  python3 test/attest_lx.py [壊す回数（一件あたり、既定 2）] [撒く本の数（既定 60）] [種]
"""
import io, os, sys, struct, subprocess, tempfile, random, collections, shutil, atexit
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'attest')); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'test'))
import ir as A
import re
import attest as ATT        # 源を lattix.py の構文で読み直す検査器（前段を共有しない）
import lattix as LX
W = 78
NTRIAL = int(sys.argv[1]) if len(sys.argv) > 1 else 2
NPROG = int(sys.argv[2]) if len(sys.argv) > 2 else 60
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1
LATTIX = os.environ.get('LATTIX_EXE', os.path.join(ROOT, 'lattix'))
tmp = tempfile.mkdtemp(); atexit.register(shutil.rmtree, tmp, True)

print("=" * W)
print("  **答えの検査器を .lx で** —— attest/attest.lx を焼き、答えと壊した証明書にかける")
print("=" * W)

# ── 組んだ .lx が生成器と一致するか（手で直していないか）──────────────────────
for gen, lx, args in [('mkfront.py', 'front.lx', []), ('mkeval.py', 'attest.lx', ['131072'])]:
    out = os.path.join(tmp, lx)
    subprocess.run([sys.executable, os.path.join(ROOT, 'attest', gen)] + args + [out], check=True, capture_output=True)
    same = open(out, 'rb').read() == open(os.path.join(ROOT, 'attest', lx), 'rb').read()
    print(f"  {'attest/' + lx + ' は ' + gen + ' の出力と同じ':<52}{'✓' if same else '✗（組み直すこと）'}")
    if not same: sys.exit(1)

# ── 焼く ──────────────────────────────────────────────────────────────
FRONT, EV = os.path.join(tmp, 'attest-front'), os.path.join(tmp, 'attest')
for lx, exe in [('front.lx', FRONT), ('attest.lx', EV)]:
    r = subprocess.run([LATTIX, os.path.join(ROOT, 'attest', lx), exe], cwd=ROOT, capture_output=True)
    os.chmod(exe, 0o755)
    probe = subprocess.run([exe], input=b'', capture_output=True)
    ok = r.returncode == 0 and b'cannot bake' not in probe.stderr
    print(f"  {'焼いた ' + lx:<52}{'✓' if ok else '✗ ' + probe.stderr[:60].decode(errors='replace')}")
    if not ok: sys.exit(1)


def make(src, data):
    """源を焼いて走らせ、証人（fd 3 = 値の面 + 階数の面）と出した答え（stdout）を取る。表は attest-front で作る。"""
    p = os.path.join(tmp, 's.lx'); open(p, 'w', encoding='utf-8').write(src)
    prog, tab, wit = os.path.join(tmp, 'prog'), os.path.join(tmp, 'tab'), os.path.join(tmp, 'w.bin')
    for f in (prog, tab, wit):
        if os.path.exists(f): os.remove(f)
    subprocess.run([LATTIX, p, prog], capture_output=True)
    subprocess.run([FRONT, p, tab], capture_output=True)
    if not os.path.exists(prog) or not os.path.exists(tab): return None
    os.chmod(prog, 0o755)
    try:
        r = subprocess.run(['sh', '-c', 'exec 3>"$1"; shift; exec "$@"', 'sh', wit, prog], input=data,
                           capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0: return None
    return open(tab, 'rb').read(), r.stdout, open(wit, 'rb').read()


WORD = {'ATTESTED': 'attested', 'REJECTED': 'rejected', 'UNSUPPORTED': 'unsupported'}
def verdict(blob):
    p = os.path.join(tmp, 'in'); open(p, 'wb').write(blob)
    r = subprocess.run([EV, p], capture_output=True)
    if r.returncode != 0: return 'rc%d' % r.returncode, r.stderr[:80]
    first = r.stdout.split(b'\n')[0].decode(errors='replace')
    for w, v in WORD.items():
        if first.startswith('attest: ' + w): return v, r.stdout.decode(errors='replace')
    return 'other', r.stdout.decode(errors='replace')


ALLOWED = {('attested', 'attested'), ('rejected', 'rejected'), ('unsupported', 'unsupported'),
           ('attested', 'unsupported'), ('rejected', 'unsupported')}
tally = collections.Counter(); bad = []; why_uns = collections.Counter()
rnd = random.Random(SEED)


def corrupt(tab, vals0, ranks0):
    """一か所だけ壊す: 値を動かす・消す・足す・flat を ⊤ にする・階数を下げる"""
    lay, _, _ = A.Tables(tab).layout()
    lay = [L for L in lay if L['cells']]
    if not lay: return None
    for _ in range(20):
        Lf = rnd.choice(lay); c = rnd.randrange(Lf['cells'])
        kind = rnd.choice(['bump', 'drop', 'add', 'top', 'rank0', 'rank1', 'rankhi'])
        vals, ranks = bytearray(vals0), bytearray(ranks0)
        bot = A.BOT[Lf['lat']]; off = Lf['vo'] + Lf['wb'] * c
        cur = vals[off] if Lf['wb'] == 1 else struct.unpack_from('<q', vals, off)[0]
        rk = struct.unpack_from('<i', ranks, Lf['ko'] + 4 * c)[0]
        if kind == 'bump' and cur != bot:
            nv = (1 - cur) if Lf['wb'] == 1 else cur + rnd.choice([1, -1, 7])
            if not -2**63 <= nv < 2**63: nv = cur - 1      # 数の場の ⊤ の印（機械の整数の端。14v）から外へは出ない
        elif kind == 'drop' and cur != bot:
            nv = bot
        elif kind == 'add' and cur == bot:
            nv = 1 if Lf['wb'] == 1 else rnd.choice([1, 5, -3])
            struct.pack_into('<i', ranks, Lf['ko'] + 4 * c, rnd.choice([1, 2, 5]))
        elif kind == 'top' and Lf['lat'] == 'flat' and cur != A.TOPV:
            nv = A.TOPV
            struct.pack_into('<i', ranks, Lf['ko'] + 4 * c, rnd.choice([1, 2, 5]))
        elif kind in ('rank0', 'rank1') and rk > 0:
            nv = cur
            struct.pack_into('<i', ranks, Lf['ko'] + 4 * c, 0 if kind == 'rank0' else rk - 1)
        elif kind == 'rankhi' and rk > 0:
            # 2^31 を越える階数: 符号つきに読めば負、符号なしなら大きい。三つの検査器が同じ読みか
            nv = cur
            struct.pack_into('<I', ranks, Lf['ko'] + 4 * c, rnd.choice([0x80000000, 0xFFFFFFFF]))
        else:
            continue
        if Lf['wb'] == 1: vals[off] = nv
        else: struct.pack_into('<q', vals, off, nv)
        return kind, bytes(vals), bytes(ranks)
    return None


_NUMTOP = {}
def numtop(src2):
    """定義の答えが min / max / sum の場に ⊤ を持つか（源ごとに一度だけ解く）"""
    if src2 not in _NUMTOP:
        try:
            p = LX.parse(src2); LX.check(p); LX.stratify(p); LX.io_rounds(p); LX.certify(p)
            st, _, _ = LX.run(p, out=io.StringIO())
            _NUMTOP[src2] = any(p.fields[f].name in ('min', 'max', 'sum')
                                and isinstance(p.fields[f].observe(v), LX._Top)
                                for f, d in st.items() for v in d.values())
        except Exception:
            _NUMTOP[src2] = False
    return _NUMTOP[src2]


def src_verdict(src, tab, vals, ranks, data):
    """attest.py（源を lattix.py の構文で読み直す）の判定。**前段を共有しない** —— 表を作った前段が
    源を読み違えていれば、表の上の判定（ir と .lx）と食い違う。"""
    try:
        T = A.Tables(tab); lay, S, K = A.decode(T, vals, ranks)
        names = re.findall(r'(?m)^field (\w+)', src)
        store, rank = {}, {}
        for f, Lf in enumerate(lay):
            # 升の番号 → 座標（三次元は (c0 * 広さ1 + c1) * 広さ2 + c2 の畳みを戻す）
            if Lf['ar'] == 3: key = lambda c, w1=Lf['w1'], w2=Lf['w2']: (c // (w1 * w2), c // w2 % w1, c % w2)
            elif Lf['ar'] == 2: key = lambda c, w=Lf['w1']: (c // w, c % w)
            else: key = lambda c: (c,)
            d = {}
            for c, v in S[f].items():
                if Lf['lat'] == 'or': v = True
                elif Lf['lat'] == 'flat' and v == A.TOPV: v = LX.TOP
                d[key(c)] = v
            store[names[f]] = d
            rank[names[f]] = {key(c): r for c, r in K[f].items()}
        rows = A.rows_of(T, data)
        lit = ", ".join("(" + ",".join(str(x) for x in r) + ")" for r in rows) if rows else "(0,32)"
        src2 = re.sub(r'(?m)^table (\w+) = .*$', lambda m: 'table %s = %s' % (m.group(1), lit), src, count=1)
        # **数の場の ⊤ は、まだ源の上で示せない**（14v）。焼いた本は ⊤ を min / max / sum へも運び、升には
        # 束の順の端（0x7fff…ffff / 0x8000…0000）を置く —— 面の上では正しい 0x7fff…ffff と見分けが付かない。
        # 表の上の二つ（ir と attest.lx）は「±2^60 を越える値」として UNSUPPORTED と言う。源で読み直す側も
        # 同じ所で言う: 定義の答えが数の場に ⊤ を持つ本は判定しない（持たない本の端の値は、ただの数）
        if numtop(src2): return 'unsupported'
        return 'attested' if ATT.attest(src2, store, rank).ok else 'rejected'
    except Exception as e:
        return 'py-error'


src_tally = collections.Counter(); src_bad = []; src_gran = collections.Counter()
RANKONLY = ('rank0', 'rank1', 'rankhi')      # 値は正直な答えのまま、階数だけを変えたもの


def check(label, tab, vals, ranks, data, out=None, src=None):
    """out は出した答え（既定は値の面そのもの —— 場の面をそのまま出す本の stdout）"""
    try: v1 = A.check(tab, vals, ranks, data)['verdict']
    except Exception as e: v1 = 'ir-error'
    if src is not None:
        v0 = src_verdict(src, tab, vals, ranks, data)
        src_tally[(v0, v1)] += 1
        # 表の上で ATTESTED なら源の上でも、源の上で ATTESTED なら表の上でも（UNSUPPORTED は除く）。
        # ただし **階数だけを変えた** 証明書で、源の上だけが ATTESTED と言うのは食い違いではない ——
        # 値は正直な答え（最小不動点）のままなので、どちらの判定も嘘ではなく、階数を比べる読みの粒度が
        # 違うだけである（attest.py は強連結成分で比べ、表の上は前段の層で比べる。成分は層より細かい）。
        # 逆向き（表の上だけが ATTESTED）は、前段の層が成分を割っている —— 破れとして数える
        kind = label.split(':')[1] if ':' in label else label
        if (v1 == 'attested') != (v0 == 'attested') and v1 != 'unsupported':
            if kind in RANKONLY and v0 == 'attested' and v1 == 'rejected':
                src_gran[kind] += 1
            else:
                src_bad.append((label, v0, v1, src[:200]))
    v2, info = verdict(tab + vals + ranks + (vals if out is None else out) + data)
    tally[(label, v1, v2)] += 1
    if v2 == 'unsupported' and isinstance(info, str):
        for line in info.splitlines()[2:]:
            if line.startswith('  a ') or line.startswith('  more'): why_uns[line.strip()[:60]] += 1
    if (v1, v2) not in ALLOWED:
        bad.append((label, v1, v2, info))
    return v1, v2


def planes(tab, wit):
    lay, vt, kt = A.Tables(tab).layout()
    return wit[:vt], wit[vt:vt + kt]


RCAP = 983040        # 焼いた本が標準入力から読める上限（31_gen の rcap）—— attest.lx もこれ以上は読めない
too_big = []


def run(label, src, data, ntrial):
    got = make(src, data)
    if got is None: return False
    tab, out, wit = got
    # **attest.lx の読み口より大きい証明書は、attest の限界として数える**（14 で 8 MB の場を持つ accept の本を
    # 足した日、attest.lx が「入力が大きすぎる」（終了コード 6）と正しく断り、それを破れと数えていた）
    if len(tab) + 2 * len(wit) + len(data) > RCAP:
        too_big.append((label, len(tab) + 2 * len(wit) + len(data))); return False
    vals0, ranks0 = planes(tab, wit)
    check(label + ':元', tab, vals0, ranks0, data, out, src=src)   # 元は、本が実際に出した stdout で
    for _ in range(ntrial):
        c = corrupt(tab, vals0, ranks0)
        if c is None: continue
        kind, vals, ranks = c
        check(label + ':' + kind, tab, vals, ranks, data, src=src)
    return True


# ── accept の答える本 ─────────────────────────────────────────────────
_src = open(os.path.join(ROOT, 'test', 'accept.py'), encoding='utf-8').read()
_ns = {'__name__': 'x', '__file__': os.path.join(ROOT, 'test', 'accept.py')}
exec(compile(_src[:_src.index("tmp=tempfile.mkdtemp()")], 'accept', 'exec'), _ns)
n_acc = 0
for name, src, data, rows, xexit, known, why in _ns['CASES']:
    if xexit is not None or known or 'render ' in src: continue
    inp = data if rows is None else b''.join(struct.pack('<' + 'q' * len(t), *t) for t in rows)
    n_acc += run('accept', src, inp, NTRIAL)

# ── 偽物（2026-09-19 に見つけた穴。.lx と ir と attest.py の三つとも通らないこと）──────────
FORGE = [
    ("恒等で ⊤ を偽る（最小不動点は 1）", """table ch = (0,32)
field f : flat bound 4
f[0] <- 1
f[z] <- f[z]   for (z) in 0 .. 0
""", {'f': (0, A.TOPV, 1)}),
    ("「⊤ は真」の閉路で ⊤ と 7 を偽る（最小不動点は x = 0、w = ⊥）", """table ch = (0,32)
field x : flat bound 1
field w : flat bound 1
x[z] <- 0   for (z) in 0 .. 0
x[z] <- w[z]   for (z) in 0 .. 0
w[z] <- 7   for (z) in 0 .. 0 if x[z]
""", {'x': (0, A.TOPV, 1), 'w': (0, 7, 2)}),
    # attest.py は規則の無い場を一度も調べていなかった（前段を共有しない二つを突き合わせて見つけた）
    ("規則の無い場に値を書く（最小不動点は a も v も ⊥）", """table ch = (0,32)
field a : max bound 16
field b : max bound 16
b[i] <- 3 + i   for (i) in 0 .. 3
field v : max bound 16
v[i] <- a[i] + b[i]   for (i) in 0 .. 3
""", {'a': (2, 5, 1), 'v': (2, 10, 3)}),
    # 集約が自分を読む輪: 和の一致だけ見ていた間は三つとも通した（偽物を数え上げて見つけた）
    ("集約が自分を支える（`c <- 1 if c` に c = 1。最小不動点は ⊥）", """table ch = (0,32)
field c : count bound 1
c[z] <- 1   for (z) in 0 .. 0 if c[z]
""", {'c': (0, 1, 1)}),
]
print("-" * W)
for label, src, forge in FORGE:
    got = make(src, b'')
    tab, _out, wit = got
    vals, ranks = planes(tab, wit)
    lay, _, _ = A.Tables(tab).layout()
    names = [l.split(':')[0].split()[1] for l in src.splitlines() if l.startswith('field ')]
    vals, ranks = bytearray(vals), bytearray(ranks)
    for f, (c, v, rk) in forge.items():
        Lf = lay[names.index(f)]
        struct.pack_into('<q', vals, Lf['vo'] + 8 * c, v); struct.pack_into('<i', ranks, Lf['ko'] + 4 * c, rk)
    v1, v2 = check('偽物', tab, bytes(vals), bytes(ranks), b'')
    v0 = src_verdict(src, tab, bytes(vals), bytes(ranks), b'')
    good = v2 != 'attested' and v1 != 'attested' and v0 != 'attested'
    if not good: bad.append(('偽物', v1, v2, label + ' attest.py=' + v0))
    print(f"  {label:<58}{'通らない ✓' if good else '通った ✗'}")

# ── 正直な証明書（三つとも ATTESTED と言うこと）────────────────────────────────
# 種だけの場（f0）は焼き手の前段では層に入らないが、lattix.py の成層では読む和（f2）と同じ層に
# 入る。前は attest.py が種の階数 1 を和の支えの読みに数え、和の階数 1 を「示せない」と言った
# （2026-09-20、撒いた本で見つけた。焼いた本は種を下の層と同じに数えて階数を付ける）
HONEST = [
    ("種だけの場を読む和（種は下の層）", """table ch = (0,32)
field f0 : sum bound 16
field f1 : flat bound 16
field f2 : sum bound 16
f0[1] <- 3
f0[4] <- 8
f2[i] <- 5 * i   for (i,c) in ch   if f0[i-1] >= 8
f1[i] <- f1[j+1]   for (i) in 0 .. 3 for (j) in 0 .. 3   if f0[i] <= f0[j]
""", b'ab1 cd23'),
    # attest は入力ぜんぶの語の上の 32 ビットを符号つきにしていた —— プログラムの入力に 01 00 00 80 が
    # 語の上半分に並ぶと -2147483647（max の ⊥ の印）になり、正直な証明書で attest が終了コード 4 で
    # 止まった（2026-09-20、階数を 2^31 より上にした証明書で見つけた）。四つのずれを全部並べる
    ("プログラムの入力に 01 00 00 80 が並ぶ", """table ch = (0,32)
field n : max bound 1
n[z] <- p   for (p,c) in ch for (z) in 0 .. 0
""", b''.join(b'a' * k + b'\x01\x00\x00\x80' * 3 for k in range(4))),
]
for label, src, data in HONEST:
    got = make(src, data)
    tab, out, wit = got
    vals, ranks = planes(tab, wit)
    v1, v2 = check('正直', tab, vals, ranks, data, out)
    v0 = src_verdict(src, tab, vals, ranks, data)
    good = v0 == v1 == v2 == 'attested'
    if not good: bad.append(('正直', v1, v2, label + ' attest.py=' + v0))
    print(f"  {label:<58}{'三つとも通る ✓' if good else '通らない ✗ ' + v0 + '/' + v1 + '/' + v2}")

# ── 撒いた本（test/progs.py の組み方）────────────────────────────────────
import progs as P
prnd = random.Random(SEED + 7); n_prog = 0; seen = set()
for _ in range(NPROG):
    s = P.program(prnd)
    if s in seen: continue
    seen.add(s)
    n_prog += run('progs', s, b'ab1 cd23', NTRIAL)

# ── 描く本（render）と、出した答えを一バイト変えたもの ───────────────────────────
# 証人に値の面が入ったので、答えを fd 1 に描く本も確かめられる。出した答えは証人の値から
# 描き直して比べる —— 使う人が見るのは stdout である
n_rnd = 0; out_ok = True; out_seen = 0
for name, src, data, rows, xexit, known, why in _ns['CASES']:
    if xexit is not None or known or 'render ' not in src: continue
    inp = data if rows is None else b''.join(struct.pack('<' + 'q' * len(t), *t) for t in rows)
    got = make(src, inp)
    if got is None: continue
    tab, out, wit = got
    vals, ranks = planes(tab, wit)
    v1, v2 = check('render:元', tab, vals, ranks, inp, out)
    n_rnd += 1
    if out:
        bad_out = bytearray(out); bad_out[len(out) // 2] ^= 1
        v, info = verdict(tab + vals + ranks + bytes(bad_out) + inp)
        out_seen += 1
        if v2 == 'attested' and not (v == 'rejected' and 'the output is not the answer' in info):
            out_ok = False; bad.append(('render:出した答えを変えた', v2, v, info))
# 場の面をそのまま出す本でも、出した答えだけを変えれば言う
got = make(FORGE[0][1], b'')
tab, out, wit = got
vals, ranks = planes(tab, wit)
bad_out = bytearray(out); bad_out[0] ^= 1
v, info4 = verdict(tab + vals + ranks + bytes(bad_out))
dump_ok = v == 'rejected' and 'the output is not the answer' in info4 and 'at byte          0' in info4

# ── 入力でないもの・焼けない源 ─────────────────────────────────────────────
v, info = verdict(b'hello, this is not a table')
junk_ok = v == 'other' and info.startswith('attest: NOT AN ATTEST INPUT')
p = os.path.join(tmp, 'u.lx'); open(p, 'w').write("table ch = (0,32)\nfield f : max bound 4\nf[i] <- g[i]   for (i,c) in ch\n")
subprocess.run([FRONT, p, os.path.join(tmp, 'ut')], capture_output=True)
v, info2 = verdict(open(os.path.join(tmp, 'ut'), 'rb').read())
unbk_ok = v == 'other' and info2.startswith('attest: THE SOURCE CANNOT BE BAKED -- line          3 reason          4')

# 面が欠けた入力: 欠けた升は「値の無い在る升」に見え、値を比べる検査が黙って飛ぶ —— 入力でないと言う
got = make(FORGE[0][1], b'')
v, info3 = verdict(got[0] + got[2][:len(got[2]) // 2])
short_ok = v == 'other' and info3.startswith('attest: NOT AN ATTEST INPUT (the answer and the ranks are shorter')

# 表の中に持てない語（-2147483646 より下。-2147483647 は attest の max の場の ⊥ の印そのもの）:
# 前は印に当たって終了コード 4 で止まりえた。表を読み違えるので判定せずに、入力でないと言う
wbad_ok, info5 = True, ''
for wv in (-2147483647, -(1 << 62)):
    tb = bytearray(got[0]); struct.pack_into('<q', tb, 8 * 17, wv)
    v, info5 = verdict(bytes(tb) + got[2] + got[1])
    wbad_ok = wbad_ok and v == 'other' and info5.startswith('attest: NOT AN ATTEST INPUT (a table word below')

print("-" * W)
groups = collections.Counter()
for (label, v1, v2), n in tally.items():
    groups[(label.split(':')[1] if ':' in label else label, v1, v2)] += n
print(f"  {'種類':<10}{'参照（ir）':<14}{'attest.lx':<14}{'件数':>6}")
for (k, v1, v2), n in sorted(groups.items(), key=str):
    mark = '' if (v1, v2) in ALLOWED else '  ← 破れ'
    print(f"  {k:<10}{v1:<14}{v2:<14}{n:>6}{mark}")
print("-" * W)
print(f"  答えた本: accept {n_acc} 本、撒いた本 {n_prog} 本（一件あたり {NTRIAL} 回壊す）")
if too_big: print(f"  attest の読み口（{RCAP} バイト）より大きい証明書の本 {len(too_big)} 本は数えない（最大 {max(b for _, b in too_big)} バイト）")
if why_uns:
    print("  UNSUPPORTED の理由（.lx の限界）:")
    for w, n in why_uns.most_common(): print(f"    {n:>4}  {w}")
print(f"  {'attest の入力でないもの':<52}{'言う ✓' if junk_ok else '✗'}")
print(f"  {'焼けない源（行 3、理由 4）':<52}{'言う ✓' if unbk_ok else '✗ ' + info2[:40]}")
print(f"  {'答えと階数の面が欠けた入力':<52}{'言う ✓' if short_ok else '✗ ' + info3[:40]}")
print(f"  {'表の中に持てない語（-2147483647 と -2^62）':<52}{'言う ✓' if wbad_ok else '✗ ' + str(info5)[:40]}")
print(f"  {'描く本 ' + str(n_rnd) + ' 本、出した答えを変えた ' + str(out_seen) + ' 本':<52}{'言う ✓' if out_ok else '✗'}")
print(f"  {'場の面を出す本の、出した答えだけを変えた':<52}{'言う ✓' if dump_ok else '✗ ' + info4[:60]}")
print("  源で読み直す検査器（attest.py）と表の上の参照（ir）:", dict(sorted(src_tally.items())))
print(f"  {'階数だけ変えた証明書で、源の上だけが示せた（粒度の違い）':<52}{sum(src_gran.values())}")
print(f"  {'前段を共有しない検査器と、表の上の判定の食い違い':<52}{len(src_bad)}")
for b in src_bad[:4]: print("  食い違い:", b[0], b[1], b[2], b[3].replace('\n', ' | ')[:120])
for b in bad[:8]: print("  破れ:", b[0], b[1], b[2], str(b[3])[:160].replace('\n', ' | '))
ok = not bad and not src_bad and junk_ok and unbk_ok and short_ok and wbad_ok and out_ok and dump_ok
print("-" * W)
if ok:
    print("  **破れ無し** —— attest.lx は、参照が ATTESTED と言わない証明書に一度も ATTESTED と")
    print("  言わず、落ちなかった。限界（鎖の深さ・値の幅・実例の数・閉路の ⊤）は UNSUPPORTED で言う。")
else:
    print(f"  **破れ {len(bad)}**")
print("=" * W)
sys.exit(0 if ok else 1)
