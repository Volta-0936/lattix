#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**値の幅を撒く** —— 印の近く・64 ビットの近くを通る鎖を撒いて、焼いた側が黙って
外れないかを見る。

焼いた符号は値を 64 ビットで持ち、「無い」「⊤」を値で見分ける（min・flat の ⊥ は
2147483647、max の ⊥ は -2147483647、flat の ⊤ は 2147483646）。解釈実行は多倍長で、
印も持たない。撒く形は一段の演算の鎖（`x[i] <- x[i-1] * c`）と、その写し・二乗・和 ——
**途中の値が答えに残る**形だけにしてあるので、断りの正しさを答えから決められる:

    答える  → 解釈実行と升まで一致する
    断る    → 終了コード 3（答えに 64 ビットを超える値がある）/
              4（答えに印に届く値がある: min で 2147483647 以上、max で -2147483647 以下、
                 flat で二つの印）/ 7（理由つき）

   使い方:  python3 test/values.py [本数] [種]
"""
import os, re, struct, subprocess, sys, io, random, tempfile, collections, signal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
LATTIX = os.environ.get('LATTIX_EXE', os.path.join(ROOT, 'lattix'))
W = 78

_src = open(os.path.join(ROOT, 'test', 'accept.py'), encoding='utf-8').read()
_ns = {'__name__': 'values', '__file__': os.path.join(ROOT, 'test', 'accept.py')}
exec(compile(_src[:_src.index("tmp=tempfile.mkdtemp()")], 'accept', 'exec'), _ns)
widths, BOT = _ns['widths'], _ns['BOT']

SEEDS = [1, 2, 3, 7, 1000000007, 2147483646, 2147483645, 65535, 4294967]
CONSTS = [1, 2, 3, 10, 256, 65536, 1000003, 2147483647, 2147483646]


def program(rnd):
    lx = rnd.choice(['min', 'max', 'flat'])
    ly = rnd.choice(['min', 'max', 'flat', 'max'])
    op = rnd.choice(['*', '*', '+', '-'])
    c = rnd.choice(CONSTS)
    n = rnd.choice([1, 2, 5, 20, 40, 63, 64, 70])
    seed = rnd.choice(SEEDS)
    lines = ["table ch = (0,32)",
             "field x : %s bound 128" % lx,
             "field y : %s bound 128" % ly,
             "field s : sum bound 4",
             "x[0] <- %d" % seed,
             "x[i] <- x[i-1] %s %d   for (i) in 1 .. %d" % (op, c, n)]
    k = rnd.randrange(5)
    if k == 0: lines.append("y[i] <- x[i]   for (i) in 0 .. %d" % n)
    elif k == 1: lines.append("y[i] <- x[i] * x[i]   for (i) in 0 .. %d" % n)
    elif k == 2: lines.append("y[i] <- x[i] + x[i]   for (i) in 0 .. %d" % n)
    elif k == 3: lines.append("y[i] <- 0 - x[i]   for (i) in 0 .. %d" % n)
    else: lines.append("s[0] <- x[i]   for (i) in 0 .. %d" % n)
    return "\n".join(lines) + "\n"


def answer(s):
    p = L.parse(s); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    p.tables['ch'] = [(0, 32)]
    st, _, _ = L.run(p, out=io.StringIO())
    ref = {}
    for f, d in st.items():
        lat = p.fields[f].name
        for kk, v in d.items():
            if v is True: v = 1
            if v is False: continue
            if isinstance(v, dict): v = sum(v.values()) if lat == 'sum' else len(v)
            if lat == 'sum' and v == 0: continue   # SPEC: ⊥ が 0 の束では 0 は ⊥（打ち消し合った和も）
            if isinstance(v, (set, frozenset)): continue
            if not isinstance(v, int): v = 2147483646
            ref[(f,) + tuple(kk)] = v
    return ref


def reaches(lat, v):
    return ((lat == 'min' and v >= 2147483647) or (lat == 'max' and v <= -2147483647) or
            (lat == 'flat' and v in (2147483646, 2147483647)))


class _Slow(Exception): pass
def _alarm(*a): raise _Slow()


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    signal.signal(signal.SIGALRM, _alarm)
    tmp = tempfile.mkdtemp(); kinds = collections.Counter(); bad = []; seen = set()
    import atexit, shutil; atexit.register(shutil.rmtree, tmp, True)   # 焼いた物は走り終えたら消す
    print("=" * W)
    print("  **値の幅を撒く** —— 印の近く・64 ビットの近く。焼いた側が黙って外れないか")
    print("=" * W)
    for n in range(N):
        s = program(rnd)
        if s in seen: continue
        seen.add(s)
        try:
            signal.alarm(20); ref = answer(s); signal.alarm(0); ok = True
        except _Slow: kinds['解釈実行が遅い（数えない）'] += 1; continue
        except Exception: signal.alarm(0); ok = False
        r = subprocess.run([LATTIX], input=s.encode(), capture_output=True)
        if r.returncode or r.stdout[:4] != b'\x7fELF':
            bad.append((s, '焼き手が落ちた %d' % r.returncode)); continue
        exe = os.path.join(tmp, 'v.out'); open(exe, 'wb').write(r.stdout); os.chmod(exe, 0o755)
        try: r2 = subprocess.run([exe], input=b'', capture_output=True, timeout=30)
        except subprocess.TimeoutExpired: bad.append((s, '焼いた側が止まらない')); continue
        rc = r2.returncode
        if not ok:
            if rc in (3, 4, 5, 6, 7, 11): kinds['両者が断る'] += 1
            else: bad.append((s, '解釈実行は断る / 焼いた側は終了コード %d' % rc))
            continue
        order, lat, off, tot = widths(s)
        if rc == 3:
            if [1 for v in ref.values() if not -2**63 <= v < 2**63]: kinds['64 ビットを超える（3）'] += 1
            else: bad.append((s, '64 ビットに収まる答えで終了コード 3'))
            continue
        if rc == 4:
            if [1 for k, v in ref.items() if reaches(lat.get(k[0]), v)]: kinds['印に届く（4）'] += 1
            else: bad.append((s, '印の無い答えで終了コード 4'))
            continue
        if rc == 7:
            kinds['焼く側が断る（7）'] += 1; continue
        if rc != 0: bad.append((s, '終了コード %d %s' % (rc, r2.stderr[:60]))); continue
        if len(r2.stdout) != tot:
            bad.append((s, '面の大きさ %d != %d' % (len(r2.stdout), tot))); continue
        got = {}
        for f in order:
            o, cells, w1, wb = off[f]; bot = BOT.get(lat[f])
            for i in range(cells):
                v = struct.unpack_from('<q' if wb == 8 else '<B', r2.stdout, o + wb * i)[0]
                if v != bot: got[(f,) + ((i // w1, i % w1) if w1 > 1 else (i,))] = v
        if got == ref: kinds['一致'] += 1
        else:
            dv = [(x, ref.get(x), got.get(x)) for x in sorted(set(got) | set(ref)) if got.get(x) != ref.get(x)][:3]
            bad.append((s, '値が違う %s' % dv))
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<40}{v:>6}")
    print("-" * W)
    for s, why in bad[:10]:
        print(f"  ✗ {why}")
        for l in s.strip().split('\n')[4:]: print('      ' + l)
    if bad:
        print(f"  **破れ {len(bad)}** —— 焼いた側が、答えも断りもしない形で外れた。"); sys.exit(1)
    print("  **破れ無し** —— 撒いた値はすべて、両者が同じ答えを出すか、焼いた側が理由を言って断った。")
