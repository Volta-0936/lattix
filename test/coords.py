#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**座標の形を撒く** —— 読みの入れ子（深さ・次数・源・ずれ）を組み合わせ、置き場
（値・式の中・ガード・否定のガード・書き先）に置いて、焼いた側が黙って外れないかを見る。

`differ.py` は束と項とガードの辺を撒き、`mutate.py` は通る本を壊す。どちらも
**座標の入れ子を深く組まない** —— 内側の二次元の読みの次元1 に、また読みを置く形
（`h[g[i, k[i]]]`）はどちらからも出なかった。焼いた側はそこで何も書かず（解釈実行は
123）、`k[0]` にすると落ちていた。座標は「源 × 次元 × 深さ × 置き場」の積なので、
積のまま撒く。

許されるのは mutate.py と同じ:

    答える  → 解釈実行と升まで一致する
    断る    → 終了コード 6（広さ）/ 7（焼けない形。理由つき）

   使い方:  python3 test/coords.py [本数] [種]
"""
import os, re, struct, subprocess, sys, io, random, tempfile, collections, signal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
LATTIX = os.environ.get('LATTIX_EXE', os.path.join(ROOT, 'lattix'))
W = 78

_src = open(os.path.join(ROOT, 'test', 'accept.py'), encoding='utf-8').read()
_ns = {'__name__': 'coords', '__file__': os.path.join(ROOT, 'test', 'accept.py')}
exec(compile(_src[:_src.index("tmp=tempfile.mkdtemp()")], 'accept', 'exec'), _ns)
widths, BOT = _ns['widths'], _ns['BOT']

HEAD = """table ch = (0,32)
field k : max bound 8
field h : max bound 8
field g : max bound 4 4
field o : or bound 8
field x : max bound 16
k[i] <- i + 1   for (i) in 0 .. 3
h[i] <- 7 - i   for (i) in 0 .. 6
g[i,j] <- i + j   for (i) in 0 .. 3 for (j) in 0 .. 3
o[i] <- true   for (i) in 0 .. 2
"""
FIELDS = [('k', 1), ('h', 1), ('g', 2)]


def slot(rnd, depth, vars_):
    """座標の一つ。源は 計数器（ずれ）/ 定数 / 読み（ずれ）。"""
    kinds = ['v', 'v', 'vo', 'c']
    if depth > 0: kinds += ['r', 'r', 'ro']
    k = rnd.choice(kinds)
    v = rnd.choice(vars_)
    if k == 'v': return v
    if k == 'vo': return f"{v}{rnd.choice(['+1', '-1', '+2'])}"
    if k == 'c': return str(rnd.choice([0, 1, 2]))
    r = read(rnd, depth - 1, vars_)
    if k == 'r': return r
    return f"{r} {rnd.choice(['+', '-'])} 1"


def read(rnd, depth, vars_):
    f, ar = rnd.choice(FIELDS)
    return f"{f}[{', '.join(slot(rnd, depth, vars_) for _ in range(ar))}]"


def program(rnd):
    two = rnd.random() < 0.4
    vars_ = ['i', 'j'] if two else ['i']
    loops = "for (i) in 0 .. 4" + (" for (j) in 0 .. 2" if two else "")
    r = read(rnd, rnd.choice([1, 1, 2, 2, 3]), vars_)
    place = rnd.choice(['val', 'val', 'expr', 'guard', 'nguard', 'write', 'write'])
    if place == 'val':    body = f"x[i] <- {r}   {loops}"
    elif place == 'expr': body = f"x[i] <- {r} {rnd.choice(['+ 1', '* 2', '- i'])}   {loops}"
    elif place == 'guard': body = f"x[i] <- 1   {loops} if {r} {rnd.choice(['>=', '==', '<'])} {rnd.choice([1, 2, 3])}"
    elif place == 'nguard': body = f"x[i] <- 1   {loops} if not o[{r}]"
    else:                 body = f"x[{r}] <- 1   {loops}"
    return HEAD + body + "\n", place


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
            if isinstance(v, (set, frozenset)): continue
            if not isinstance(v, int): v = 2147483646
            ref[(f,) + tuple(kk)] = v
    return ref


class _Slow(Exception): pass
def _alarm(*a): raise _Slow()


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    signal.signal(signal.SIGALRM, _alarm)
    tmp = tempfile.mkdtemp(); kinds = collections.Counter(); bad = []; seen = set()
    import atexit, shutil; atexit.register(shutil.rmtree, tmp, True)   # 焼いた物は走り終えたら消す
    print("=" * W)
    print("  **座標の形を撒く** —— 入れ子 × 次数 × 源 × 置き場。焼いた側が黙って外れないか")
    print("=" * W)
    for n in range(N):
        s, place = program(rnd)
        if s in seen: continue
        seen.add(s)
        try:
            signal.alarm(20); ref = answer(s); signal.alarm(0); ok = True
        except _Slow: kinds['解釈実行が遅い（数えない）'] += 1; continue
        except Exception: signal.alarm(0); ok = False
        r = subprocess.run([LATTIX], input=s.encode(), capture_output=True)
        if r.returncode or r.stdout[:4] != b'\x7fELF':
            bad.append((place, s, '焼き手が落ちた %d' % r.returncode)); continue
        exe = os.path.join(tmp, 'c.out'); open(exe, 'wb').write(r.stdout); os.chmod(exe, 0o755)
        try: r2 = subprocess.run([exe], input=b'', capture_output=True, timeout=30)
        except subprocess.TimeoutExpired: bad.append((place, s, '焼いた側が止まらない')); continue
        rc = r2.returncode
        if not ok:
            if rc in (3, 4, 5, 6, 7, 11): kinds['両者が断る'] += 1
            else: bad.append((place, s, '解釈実行は断る / 焼いた側は終了コード %d' % rc))
            continue
        if rc == 7:
            m = re.search(rb'reason ([0-9A-F]): (.{16})\n', r2.stderr)
            if not m: bad.append((place, s, '理由を言わずに 7')); continue
            kinds['焼く側が断る（7 %s）' % m.group(2).decode().strip()] += 1; continue
        if rc == 6: kinds['焼く側が断る（6 広さ）'] += 1; continue
        if rc in (3, 4):
            _o, _lat, _off, _t = widths(s)
            hit = [1 for k, v in ref.items() if not -2**63 <= v < 2**63
                   or (_lat.get(k[0]) == 'min' and v >= 2147483647)
                   or (_lat.get(k[0]) == 'max' and v <= -2147483647)
                   or (_lat.get(k[0]) == 'flat' and v in (2147483646, 2147483647))]
            if hit: kinds['焼く側が断る（%d 値）' % rc] += 1
            else: bad.append((place, s, '答えに無い理由で終了コード %d' % rc))
            continue
        if rc != 0: bad.append((place, s, '終了コード %d %s' % (rc, r2.stderr[:60]))); continue
        order, lat, off, tot = widths(s)
        if len(r2.stdout) != tot:
            bad.append((place, s, '面の大きさ %d != %d' % (len(r2.stdout), tot))); continue
        got = {}
        for f in order:
            o, cells, w1, wb = off[f]; bot = BOT.get(lat[f])
            for i in range(cells):
                v = struct.unpack_from('<q' if wb == 8 else '<B', r2.stdout, o + wb * i)[0]
                if v != bot: got[(f,) + ((i // w1, i % w1) if w1 > 1 else (i,))] = v
        if got == ref: kinds['一致（%s）' % place] += 1
        else:
            dv = [(x, ref.get(x), got.get(x)) for x in sorted(set(got) | set(ref)) if got.get(x) != ref.get(x)][:3]
            bad.append((place, s, '値が違う %s' % dv))
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<40}{v:>6}")
    print("-" * W)
    for place, s, why in bad[:12]:
        print(f"  ✗ {place}: {why}")
        print('      ' + s.strip().split('\n')[-1])
    if bad:
        print(f"  **破れ {len(bad)}** —— 焼いた側が、答えも断りもしない形で外れた。"); sys.exit(1)
    print("  **破れ無し** —— 撒いた座標はすべて、両者が同じ答えを出すか、焼いた側が理由を言って断った。")
