#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**本を撒く** —— 場・種・規則を何本も組み合わせた本を丸ごと撒く。

`differ.py` は二規則の型に項とガードを入れ替えて撒く。`mutate.py` は通る本を一か所
壊す。`coords.py` は座標、`values.py` は値の幅を撒く。どれも **規則どうしの絡み**
（層・否定・集約・二次元・場で決まる区間・種・鎖）を深く組まない。ここでは束も
次数も読みもガードも区間も混ぜた本を丸ごと作り、解釈実行と升まで比べる。

    答える  → 解釈実行と升まで一致する
    断る    → 終了コード 2〜10（答えの側に理由があるもの）・7（理由つき）

   使い方:  python3 test/progs.py [本数] [種]
"""
import os, re, struct, subprocess, sys, io, random, tempfile, collections, signal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
LATTIX = os.environ.get('LATTIX_EXE', os.path.join(ROOT, 'lattix'))
W = 78

_src = open(os.path.join(ROOT, 'test', 'accept.py'), encoding='utf-8').read()
_ns = {'__name__': 'progs', '__file__': os.path.join(ROOT, 'test', 'accept.py')}
exec(compile(_src[:_src.index("tmp=tempfile.mkdtemp()")], 'accept', 'exec'), _ns)
widths, BOT = _ns['widths'], _ns['BOT']

LATS = ['min', 'max', 'max', 'or', 'flat', 'sum', 'count']


def program(rnd):
    """場は f0, f1, … の順に並べ、**非単調な読み**（not・比較・区間の上端）は自分より
    前の場からだけ取る —— そうしないと大半が「成層できない」で両者に断られ、撒く意味が
    薄くなる（単調な読みは自分を含めてどこからでも取る。鎖が組める）。"""
    nf = rnd.randint(3, 5)
    F = []
    for k in range(nf):
        lat = rnd.choice(LATS)
        two = rnd.random() < 0.25
        F.append(('f%d' % k, lat, two))
    lines = ["table ch = (0,32)"]
    for n, lat, two in F:
        lines.append("field %s : %s bound %s" % (n, lat, "8 8" if two else "16"))

    def coord1(v):
        return rnd.choice([v, v, '%s+1' % v, '%s-1' % v])

    def read(vs, pool, depth=1):
        """読み一つ（1D か 2D）。pool から選ぶ"""
        pool = [x for x in pool if x[1] != 'or'] or pool
        if not pool: return str(rnd.randint(0, 9))
        n, lat, two = rnd.choice(pool)
        if two:
            return "%s[%s, %s]" % (n, coord1(rnd.choice(vs)), coord1(rnd.choice(vs)))
        if depth > 0 and rnd.random() < 0.2:
            return "%s[%s]" % (n, read(vs, pool, depth - 1))
        return "%s[%s]" % (n, coord1(rnd.choice(vs)))

    def value(vs, cols, lat, h):
        mono = [x for x in F if x[1] in ('min', 'max', 'flat') and (x[1] == lat or F.index(x) < h)]
        if lat == 'or':
            ors = [x for x in F[:h + 1] if x[1] == 'or' and not x[2]]
            if ors and rnd.random() < 0.4:
                return "%s[%s]" % (rnd.choice(ors)[0], rnd.choice(vs))
            return "true"
        atoms = [rnd.choice(vs), str(rnd.randint(0, 9))] + cols
        if mono: atoms.append(read(vs, mono))
        a = rnd.choice(atoms)
        if lat in ('min', 'max') and mono and rnd.random() < 0.3:
            return "%s %s 1" % (read(vs, mono), '+' if lat == 'max' else '-')   # 鎖
        k = rnd.random()
        if k < 0.30: return a
        # **値の式の形も撒く。** 撒く道具はどれも「項 演算子 項」までしか作らず、先頭の `-`
        # （群0 の符号が消えていた）・丸括弧・演算子の重なり（黙って読み飛ばしていた）・
        # 2^32 以上の法（`and` の即値が符号拡張で -1 になっていた）を一度も作らなかった。
        if k < 0.40:                    # 先頭の -
            b, c = rnd.choice(atoms), rnd.choice(atoms)
            return rnd.choice(["-%s" % a, "-%s %s %s" % (a, rnd.choice(['+', '-', '*']), b),
                               "-%s * %s + %s" % (a, b, c)])
        if k < 0.46:                    # 焼く側が知らない形 —— 断るか、一致するか
            b = rnd.choice(atoms)
            return rnd.choice(["(%s %s %s)" % (a, rnd.choice(['+', '-']), b), "-(%s)" % a,
                               "%s - -%s" % (a, b), "%s * -%s" % (a, b), "%s + (%s)" % (a, b)])
        if k < 0.54:                    # 大きい二のべき
            return "%s %s %d" % (a, rnd.choice(['/', '%']), 2 ** rnd.choice([31, 32, 33, 40, 62]))
        if k < 0.66:                    # 長い鎖（群の境目と優先順位）
            e = a
            for _ in range(rnd.randint(2, 4)):
                e += " %s %s" % (rnd.choice(['+', '-', '*', '*']), rnd.choice(atoms))
            return e
        op = rnd.choice(['+', '-', '*', '/ 2', '% 4'])
        if op in ('/ 2', '% 4'): return "%s %s" % (a, op)
        return "%s %s %s" % (a, op, rnd.choice(atoms))

    def guard(vs, cols, h):
        low = F[:h]
        ors = [x for x in low if x[1] == 'or' and not x[2]]
        g = []
        for _ in range(rnd.choice([0, 0, 1, 1, 2])):
            k = rnd.random()
            if k < 0.3 and ors:
                n = rnd.choice(ors)[0]
                g.append(("if not %s[%s]" if rnd.random() < 0.5 else "if %s[%s]") % (n, rnd.choice(vs)))
            elif k < 0.6 or not low:
                g.append("if %s %s %d" % (rnd.choice(vs + cols), rnd.choice(['<', '>=', '==', '!=']), rnd.randint(0, 6)))
            else:
                g.append("if %s %s %s" % (read(vs, low, 0), rnd.choice(['<', '>=', '<=']),
                                          rnd.choice([str(rnd.randint(0, 9)), read(vs, low, 0)])))
        return ("   " + " ".join(g)) if g else ""

    # 種（一次元の場だけ）
    for _ in range(rnd.randint(0, 2)):
        one = [x for x in F if not x[2]]
        if not one: break
        n, lat, two = rnd.choice(one)
        v = "true" if lat == 'or' else str(rnd.randint(1, 9))
        if lat == 'count': v = "1"
        lines.append("%s[%d] <- %s" % (n, rnd.randint(0, 7), v))
    # 規則
    for _ in range(rnd.randint(2, 5)):
        h = rnd.randrange(nf)
        n, lat, two = F[h]
        agg = lat in ('sum', 'count')
        k = rnd.random()
        bn = [x for x in F[:h] if x[1] in ('max', 'min') and not x[2]]
        if k < 0.4:
            loops = "for (i,c) in ch"; vs = ['i']; cols = ['c']
        elif k < 0.7 or (agg and k < 0.85):
            loops = "for (i) in 0 .. %d" % rnd.randint(1, 6); vs = ['i']; cols = []
        elif k < 0.85:
            loops = "for (i) in 0 .. 3 for (j) in 0 .. 3"; vs = ['i', 'j']; cols = []
        elif bn:
            loops = "for (i) in 0 .. %s[0]" % rnd.choice(bn)[0]; vs = ['i']; cols = []
        else:
            loops = "for (i) in 0 .. 3"; vs = ['i']; cols = []
        if two:
            head = "%s[%s, %s]" % (n, rnd.choice(vs), vs[-1])
        else:
            head = "%s[%s]" % (n, rnd.choice([vs[0], coord1(vs[0])]))
        if len(vs) == 2 and not two:
            head = "%s[%s]" % (n, vs[0]) if False else head
        lines.append("%s <- %s   %s%s" % (head, value(vs, cols, lat, h), loops, guard(vs, cols, h)))
    return "\n".join(lines) + "\n"


def answer(s, data):
    p = L.parse(s); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    p.tables['ch'] = [(i, c) for i, c in enumerate(data)] if data else [(0, 32)]
    st, _, _ = L.run(p, out=io.StringIO())
    ref, top = {}, False
    for f, d in st.items():
        lat = p.fields[f].name
        for kk, v in d.items():
            if v is True: v = 1
            if v is False: continue
            if isinstance(v, dict):
                if any(isinstance(x, L._Top) for x in v.values()): top = True; v = 2147483646
                else: v = sum(v.values()) if lat == 'sum' else len(v)
            if isinstance(v, (set, frozenset)): continue
            if not isinstance(v, int): v = 2147483646; top = True
            ref[(f,) + tuple(kk)] = v
    return ref, top


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
    import atexit, shutil; atexit.register(shutil.rmtree, tmp, True)
    data = b'ab1 cd23'
    print("=" * W)
    print("  **本を撒く** —— 場・種・規則を組み合わせた本を丸ごと。焼いた側が黙って外れないか")
    print("=" * W)
    for n in range(N):
        s = program(rnd)
        if s in seen: continue
        seen.add(s)
        why = ''
        try:
            signal.alarm(20); ref, top = answer(s, data); signal.alarm(0); ok = True
        except _Slow: kinds['解釈実行が遅い（数えない）'] += 1; continue
        except Exception as ex: signal.alarm(0); ok = False; why = str(ex)
        r = subprocess.run([LATTIX], input=s.encode(), capture_output=True)
        if r.returncode or r.stdout[:4] != b'\x7fELF':
            bad.append((s, '焼き手が落ちた %d' % r.returncode)); continue
        exe = os.path.join(tmp, 'p.out'); open(exe, 'wb').write(r.stdout); os.chmod(exe, 0o755)
        try: r2 = subprocess.run([exe], input=data, capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            # **昇鎖が止まらない本**（`f[i] <- f[i] + 1`）には最小不動点が無い。解釈実行は
            # 変化の回数の見張り（400 万回）で止めて断る。焼いた側は見張りを持たず回り続ける
            # —— 嘘ではない（答えを出さない）が、止まらない。両者が「答えない」なら数えるだけ。
            if not ok and ('fire budget' in why or 'did not converge' in why):
                kinds['昇鎖が止まらない（両者とも答えない）'] += 1
            else: bad.append((s, '焼いた側が止まらない'))
            continue
        rc = r2.returncode
        if not ok:
            if rc in (2, 3, 4, 5, 6, 7, 10): kinds['両者が断る'] += 1
            else: bad.append((s, '解釈実行は断る / 焼いた側は終了コード %d' % rc))
            continue
        order, lat, off, tot = widths(s)
        if rc == 7:
            if not re.search(rb'reason ([0-9A-F]): (.{16})\n', r2.stderr): bad.append((s, '理由を言わずに 7'))
            else: kinds['焼く側が断る（7）'] += 1
            continue
        if rc == 6: kinds['焼く側が断る（6）'] += 1; continue
        if rc == 5:
            if top: kinds['両者 ⊤（5）'] += 1
            else: bad.append((s, '⊤ の無い答えで終了コード 5'))
            continue
        if rc == 4:
            if [1 for k, v in ref.items() if reaches(lat.get(k[0]), v)]: kinds['印に届く（4）'] += 1
            else: bad.append((s, '印の無い答えで終了コード 4'))
            continue
        if rc == 3:
            if [1 for v in ref.values() if not -2**63 <= v < 2**63]: kinds['64 ビットを超える（3）'] += 1
            else: bad.append((s, '64 ビットに収まる答えで終了コード 3'))
            continue
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
    for s, why in bad[:8]:
        print(f"  ✗ {why}")
        for l in s.strip().split('\n')[1:]: print('      ' + l)
    if bad:
        print(f"  **破れ {len(bad)}** —— 焼いた側が、答えも断りもしない形で外れた。"); sys.exit(1)
    print("  **破れ無し** —— 撒いた本はすべて、両者が同じ答えを出すか、焼いた側が理由を言って断った。")
