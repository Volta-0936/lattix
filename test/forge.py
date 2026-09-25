#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**偽物を数え上げる** —— 小さい本のあらゆる答えと階数を、検査器にかける。

検査器の約束は一つ: **ATTESTED なら、答えは最小不動点である。** 突き合わせ（ir と .lx、源で読む
attest.py と表で読む ir）は「互いに同じことを言う」しか測らない —— 同じ考えを写した検査器は、同じ所で
一緒に間違える（⊤ の穴がそうだった）。ここでは約束そのものを測る: 升が数個しか無い本なら、
**あらゆる答え**（値の小さい集合の直積）と **あらゆる階数**を作れる。最小不動点でない答えに、
どれか一つの階数で ATTESTED と言えば、それが嘘である。

    表の上の検査器（attest/ir.py）      —— 答えの全部 × 前不動点になった答えの階数の全部
    源で読み直す検査器（attest.py）      —— 同じ
    .lx の検査器（attest/attest.lx）     —— ir が ATTESTED と言った偽物があれば、それを（遅いので）

本の四割は二次元の場を混ぜる（program2d。升の番号は c1 * 広さ1 + c2 —— 一次元の本だけでは、
検査器が升の番号と座標を取り違えても見えない）。

    使い方:  python3 test/forge.py [本の数（既定 40）] [種]
"""
import os, sys, struct, subprocess, tempfile, random, itertools, collections, shutil, atexit, re, io
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'attest')); sys.path.insert(0, ROOT)
import ir as A
import attest as ATT
import lattix as LX
W = 78
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
LATTIX = os.environ.get('LATTIX_EXE', os.path.join(ROOT, 'lattix'))
tmp = tempfile.mkdtemp(); atexit.register(shutil.rmtree, tmp, True)
FRONT = os.path.join(tmp, 'attest-front'); EV = os.path.join(tmp, 'attest')
for lx, exe in [('front.lx', FRONT), ('attest.lx', EV)]:
    subprocess.run([LATTIX, os.path.join(ROOT, 'attest', lx), exe], check=True, capture_output=True)
    os.chmod(exe, 0o755)

LATS = ['max', 'min', 'flat', 'flat', 'or', 'sum', 'count']


def program():
    """場は二つか三つ、升は一つか二つ。規則は種・写し・一つ足す・ガード。非単調な読み（not・比較）は
    自分より前の場からだけ —— そうしないと大半が成層できずに断られる"""
    nf = rnd.randint(2, 3)
    F = [('f%d' % k, rnd.choice(LATS), rnd.choice([1, 1, 2])) for k in range(nf)]
    L = ["table ch = (0,32)"] + ["field %s : %s bound %d" % f for f in F]
    for _ in range(rnd.randint(1, 3)):             # 種
        n, lat, b = rnd.choice(F)
        L.append("%s[%d] <- %s" % (n, rnd.randrange(b), 'true' if lat == 'or' else rnd.randint(0, 2)))
    for _ in range(rnd.randint(2, 4)):             # 規則
        h = rnd.randrange(nf); n, lat, b = F[h]
        z = "z"
        src = rnd.choice(F)                        # 読む場（単調な読みはどこからでも）
        low = F[:h]
        if lat == 'or':
            val = 'true'
        elif lat == 'count':
            val = '1'
        else:
            k = rnd.random()
            nonor = [x for x in F if x[1] not in ('or',)]
            if k < 0.25: val = str(rnd.randint(0, 2))
            elif src[1] == 'or': val = str(rnd.randint(0, 2))
            elif k < 0.5: val = "%s[%s]" % (src[0], z)
            elif k < 0.65: val = "%s[%s] + 1" % (src[0], z)
            elif k < 0.75: val = "%s[%s] - 1" % (src[0], z)
            elif k < 0.85: val = "%s[%s] * 2" % (src[0], z)
            elif nonor:
                # **座標に読みを置く**（f[g[z]]）—— g の値が広さの外なら読みは ⊥
                ix = rnd.choice(nonor)
                val = "%s[%s[%s]]" % (src[0], ix[0], z)
            else: val = "%s[%s]" % (src[0], z)
        g = ""
        r = rnd.random()
        if r < 0.3:
            gs = rnd.choice(F)
            g = " if %s[%s]" % (gs[0], z)
        elif r < 0.45 and low:
            gs = rnd.choice(low)
            g = " if not %s[%s]" % (gs[0], z)
        elif r < 0.6 and low:
            gs = rnd.choice([x for x in low if x[1] != 'or'] or low)
            if gs[1] != 'or': g = " if %s[%s] %s %d" % (gs[0], z, rnd.choice(['>', '<', '==']), rnd.randint(0, 2))
        elif r < 0.7 and len([x for x in low if x[1] != 'or']) >= 1:
            # 二つの場を比べる（下の層どうし、または自分と下の層）
            a1 = rnd.choice([x for x in low if x[1] != 'or'])
            a2 = rnd.choice([x for x in low if x[1] != 'or'])
            g = " if %s[%s] %s %s[%s]" % (a1[0], z, rnd.choice(['<', '>=', '!=']), a2[0], z)
        hb = min(b, src[2]) if val.startswith(src[0]) else b
        if b == 2 and rnd.random() < 0.2 and lat != 'or' and src[2] == 2 and val.startswith(src[0] + '[z]'):
            # 鎖: 次の升へ写す（f[z+1] <- g[z]）
            L.append("%s[z+1] <- %s   for (z) in 0 .. 0%s" % (n, val, g))
        else:
            L.append("%s[z] <- %s   for (z) in 0 .. %d%s" % (n, val, hb - 1, g))
    return "\n".join(L) + "\n"


def program2d():
    """**二次元の場を混ぜる**（升の番号は c1 * 広さ1 + c2）。読みは書き先の束縛で引く —— 一次元の場は
    [z] か [w]、二次元の場は [z, w]（書き先が一次元なら [z, 0]）。検査器が升の番号と座標を取り違えれば
    （一次元の本だけでは見えない）、ここで出る"""
    nf = rnd.randint(2, 3)
    F = []
    for k in range(nf):
        lat = rnd.choice(LATS)
        b = (rnd.choice([1, 2]), rnd.choice([1, 2])) if rnd.random() < 0.5 else (rnd.choice([1, 2]),)
        F.append(('f%d' % k, lat, b))
    if not any(len(b) == 2 for _n, _l, b in F):
        n0, l0, b0 = F[0]; F[0] = (n0, l0, (b0[0], 2))
    L = ["table ch = (0,32)"] + ["field %s : %s bound %s" % (n, lat, " ".join(map(str, b)))
                                for n, lat, b in F]
    for _ in range(rnd.randint(1, 3)):             # 種
        n, lat, b = rnd.choice(F)
        # 種の座標は `,` の後ろに空白を置く（前は焼き手の前段が `f[0, 1] <- 2` を理由 8 で断っていた ——
        # 空白を跨いで引くように直した。test/spaces.py）
        L.append("%s[%s] <- %s" % (n, ", ".join(str(rnd.randrange(x)) for x in b),
                                   'true' if lat == 'or' else rnd.randint(0, 2)))

    def rd(m, tb):
        n, _l, bm = m
        if len(bm) == 2: return "%s[z, %s]" % (n, "w" if len(tb) == 2 else "0")
        return "%s[%s]" % (n, rnd.choice(["z", "w"]) if len(tb) == 2 else "z")
    for _ in range(rnd.randint(2, 4)):             # 規則
        h = rnd.randrange(nf); n, lat, b = F[h]
        src = rnd.choice(F); low = F[:h]
        if lat == 'or': val = 'true'
        elif lat == 'count': val = '1'
        else:
            k = rnd.random()
            if k < 0.25 or src[1] == 'or': val = str(rnd.randint(0, 2))
            elif k < 0.5: val = rd(src, b)
            elif k < 0.65: val = rd(src, b) + " + 1"
            elif k < 0.8: val = rd(src, b) + " - 1"
            else: val = rd(src, b) + " * 2"
        g = ""
        r = rnd.random()
        if r < 0.3: g = " if " + rd(rnd.choice(F), b)
        elif r < 0.45 and low: g = " if not " + rd(rnd.choice(low), b)
        elif r < 0.6 and [x for x in low if x[1] != 'or']:
            gs = rnd.choice([x for x in low if x[1] != 'or'])
            g = " if %s %s %d" % (rd(gs, b), rnd.choice(['>', '<', '==']), rnd.randint(0, 2))
        loops, key = "for (z) in 0 .. %d" % (b[0] - 1), "z"
        if len(b) == 2: loops += " for (w) in 0 .. %d" % (b[1] - 1); key = "z, w"
        L.append("%s[%s] <- %s   %s%s" % (n, key, val, loops, g))
    return "\n".join(L) + "\n"


def make(src):
    p = os.path.join(tmp, 's.lx'); open(p, 'w').write(src)
    prog, tab, wit = os.path.join(tmp, 'prog'), os.path.join(tmp, 'tab'), os.path.join(tmp, 'w')
    for f in (prog, tab, wit):
        if os.path.exists(f): os.remove(f)
    subprocess.run([LATTIX, p, prog], capture_output=True)
    subprocess.run([FRONT, p, tab], capture_output=True)
    if not os.path.exists(prog) or not os.path.exists(tab): return None
    os.chmod(prog, 0o755)
    try:
        r = subprocess.run(['sh', '-c', 'exec 3>"$1"; shift; exec "$@"', 'sh', wit, prog], input=b'',
                           capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0: return None
    return open(tab, 'rb').read(), open(wit, 'rb').read()


DOM = {'max': [None, 0, 1, 2, 3], 'min': [None, 0, 1, 2, 3], 'flat': [None, 0, 1, 2, 'T'], 'or': [None, 1],
       'sum': [None, 1, 2, 3], 'count': [None, 1, 2]}
# 弱順序（同順を許す並べ方）を階数 1, 2, … で: 使う段が 0..m-1 と途切れない割り当て
WEAK = {n: [tuple(x + 1 for x in t) for t in itertools.product(range(n), repeat=n)
            if set(t) == set(range(max(t) + 1))] if n else [()] for n in range(0, 7)}


def encode(lay, vals, ranks):
    """{(f, c): 値}（None は ⊥、'T' は flat の ⊤）と {(f, c): 階数} を面にする"""
    vt = sum(L['cells'] * L['wb'] for L in lay); kt = sum(L['cells'] * 4 for L in lay)
    V = bytearray(vt); K = bytearray(kt)
    for f, L in enumerate(lay):
        for c in range(L['cells']):
            v = vals.get((f, c))
            if v is None: v = A.BOT[L['lat']]
            elif v == 'T': v = A.TOPV
            if L['wb'] == 1: V[L['vo'] + c] = v
            else: struct.pack_into('<q', V, L['vo'] + 8 * c, v)
            struct.pack_into('<i', K, L['ko'] + 4 * c, ranks.get((f, c), 0))
    return bytes(V), bytes(K)


def src_ok(src, names, lay, vals, ranks):
    store, rank = {}, {}
    for f, L in enumerate(lay):
        d, k = {}, {}
        if L['ar'] == 3: key = lambda c, w1=L['w1'], w2=L['w2']: (c // (w1 * w2), c // w2 % w1, c % w2)
        elif L['ar'] == 2: key = lambda c, w=L['w1']: (c // w, c % w)
        else: key = lambda c: (c,)
        for c in range(L['cells']):
            v = vals.get((f, c))
            if v is None: continue
            d[key(c)] = True if L['lat'] == 'or' else (LX.TOP if v == 'T' else v)
            if ranks.get((f, c)): k[key(c)] = ranks[(f, c)]
        store[names[f]] = d; rank[names[f]] = k
    try: return ATT.attest(src, store, rank).ok
    except Exception: return False


print("=" * W)
print("  **偽物を数え上げる** —— 小さい本のあらゆる答えと階数を、検査器にかける")
print("=" * W)
tally = collections.Counter(); lies = []; seen = set(); nprog = 0
for _ in range(N * 4):
    if nprog >= N: break
    s = program2d() if rnd.random() < 0.4 else program()
    if s in seen: continue
    seen.add(s)
    got = make(s)
    if got is None: tally['焼けない・断る本'] += 1; continue
    tab, wit = got
    T = A.Tables(tab); lay, vt, kt = T.layout()
    cells = [(f, c) for f, L in enumerate(lay) for c in range(L['cells'])]
    if len(cells) > 5: tally['升が多い本（数えない）'] += 1; continue
    names = re.findall(r'(?m)^field (\w+)', s)
    _, S0, K0 = A.decode(T, wit[:vt], wit[vt:vt + kt])
    lfp = {(f, c): ('T' if (lay[f]['lat'] == 'flat' and v == A.TOPV) else (1 if lay[f]['lat'] == 'or' else v))
           for f in S0 for c, v in S0[f].items()}
    nprog += 1
    for combo in itertools.product(*[DOM[lay[f]['lat']] for f, c in cells]):
        vals = {cells[i]: v for i, v in enumerate(combo) if v is not None}
        if vals == lfp: continue
        # 前不動点でない答えは、どの階数でも通らない（安定性は階数を見ない）
        V, K = encode(lay, vals, {x: 1 for x in vals})
        rep = A.check(tab, V, K, b'')
        # 参照が持たない形（⊤ の支え）は階数しだいで持てる形になりうる —— 飛ばさずに階数を全部試す
        if rep.get('verdict') != 'unsupported' and (rep.get('stability') or rep.get('outside')):
            tally['前不動点でない'] += 1; continue
        tally['前不動点（最小でない）か、階数で決まる'] += 1
        present = sorted(vals)
        # 階数は比べられるだけ（mr < k）なので、効くのは **升の弱順序**（同順を許す並べ方）だけ。
        # 弱順序を全部試せば、階数を全部試したのと同じ（五升で 541 通り）
        for rk in WEAK[len(present)]:
            ranks = dict(zip(present, rk))
            V, K = encode(lay, vals, ranks)
            v1 = A.check(tab, V, K, b'')['verdict']
            v0 = src_ok(s, names, lay, vals, ranks)
            tally['試した階数'] += 1
            if v1 == 'attested' or v0:
                v2 = None
                if v1 == 'attested':
                    open(os.path.join(tmp, 'in'), 'wb').write(tab + V + K + V)
                    r = subprocess.run([EV, os.path.join(tmp, 'in')], capture_output=True)
                    v2 = r.stdout.split(b'\n')[0].decode(errors='replace')
                lies.append((s, vals, ranks, lfp, v1, v0, v2))
                break
print(f"  数えた本 {nprog} 本")
for k, v in sorted(tally.items()): print(f"    {k:<40}{v:>10}")
print("-" * W)
for s, vals, ranks, lfp, v1, v0, v2 in lies[:6]:
    print("  嘘:", "ir=" + v1, "attest.py=" + ('ok' if v0 else 'no'), "lx=" + str(v2))
    print("   ", s.replace('\n', ' | ')[:200])
    print("    偽の答え", vals, "階数", ranks, "最小不動点", lfp)
ok = not lies
print("-" * W)
print("  **嘘 0** —— 最小不動点でない答えは、どの階数でも ATTESTED にならなかった" if ok
      else f"  **嘘 {len(lies)}**")
print("=" * W)
sys.exit(0 if ok else 1)
