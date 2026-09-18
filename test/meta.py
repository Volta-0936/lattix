#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**言語自身の法則で試す。** —— 答えを知らなくても嘘は見つかる。

`differ.py` は二つの実装（焼きと解釈実行）を突き合わせる。強いが、
**撒く文法が言語より狭ければ、狭い所の嘘は永久に生き延びる** ——
実際、今日 `if a[i] + 1 >= 2` が焼けて segfault していたのに、
`differ` は「食い違いなし」と言い続けていた。その形を撒いていなかったからである。

ここは別の道を行く。Lattix には **他の言語に無い法則**がある ——

    答えは最小不動点である。だから **規則の順序に依らない**。
    引いてから配っても（中間の場を一枚置いても）答えは同じである。
    宣言を広げても答えは同じである（増えるのは届かない升だけ）。
    読まれない場を足しても答えは同じである（動くのは配置だけ）。

どれも **答えを知らなくても**確かめられる。P と P' を両方焼いて、
同じ升が同じ値なら通る。違えば **必ずどちらかが嘘**である。

法則はどれも「意味は変えず、**配置だけを変える**」形をしている。
今日の難しい誤りは全部そこに居た —— 位置の鎖、飛び先、群の境目、番兵。
神託が要らないので、撒く文法を広げるだけいくらでも深く試せる。

    python3 test/meta.py [本数]
"""
import collections, io, os, random, re, struct, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'work'))
import lattix as L
from flatten import flatten
LATTIX = os.environ.get("LATTIX_EXE", os.path.join(ROOT, "lattix"))
BOT = {'min': 2147483647, 'max': -2147483647, 'or': 0,
       'flat': 2147483647, 'sum': 0, 'count': 0}


# ══ 升を読む（accept.py と同じ置き場の勘定）════════════════════════
def match_bracket(s, i):
    d = 0
    for j in range(i, len(s)):
        if s[j] == '[': d += 1
        elif s[j] == ']':
            d -= 1
            if d == 0: return j
    return -1


def widths(src):
    order = []; bnd = {}; lat = {}
    for ln in src.split('\n'):
        m = re.match(r'^field (\w+) : (\w+)(?: bound ([0-9 ]+))?\s*(?:#.*)?$',
                     ln.split('#')[0].strip())
        if m:
            order.append(m.group(1)); lat[m.group(1)] = m.group(2)
            bnd[m.group(1)] = [int(x) for x in (m.group(3) or '64').split()]
    ar = collections.defaultdict(lambda: 1)
    for ln in src.split('\n'):
        ln = ln.split('#')[0]
        for m in re.finditer(r'(\w+)\[', ln):
            if m.group(1) not in bnd: continue
            j = match_bracket(ln, m.end() - 1)
            if j < 0: continue
            ix = ln[m.end():j]; d = 0; nd = 1
            for ch in ix:
                if ch == '[': d += 1
                elif ch == ']': d -= 1
                elif ch == ',' and d == 0: nd += 1
            ar[m.group(1)] = max(ar[m.group(1)], nd)
    off = {}; o = 0
    for f in order:
        b = bnd[f]; w0 = b[0]; w1 = b[1] if len(b) > 1 else w0
        cells = w0 * w1 if ar[f] == 2 else w0
        wb = 1 if lat[f] == 'or' else 8
        off[f] = (o, cells, w1 if ar[f] == 2 else 1, wb); o += cells * wb
    return order, lat, off, o


def cells(src, data):
    """焼いて走らせて升を返す。焼けなければ ('断り', 理由)。"""
    r = subprocess.run([LATTIX], input=src.encode(), capture_output=True)
    if r.returncode or r.stdout[:4] != b'\x7fELF':
        return ('断り', 'bake %d' % r.returncode)
    d = tempfile.mkdtemp(); exe = os.path.join(d, 'a.out')
    open(exe, 'wb').write(r.stdout); os.chmod(exe, 0o755)
    r2 = subprocess.run([exe], input=data, capture_output=True)
    if r2.returncode != 0:
        return ('断り', 'run %d %s' % (r2.returncode, r2.stderr[:40]))
    order, lat, off, tot = widths(src)
    if len(order) == 0 or len(r2.stdout) != tot:
        return ('断り', '置き場 %d != %d' % (len(r2.stdout), tot))
    got = {}
    for f in order:
        o, n, w1, wb = off[f]; bot = BOT[lat[f]]
        for i in range(n):
            v = struct.unpack_from('<q' if wb == 8 else '<B', r2.stdout, o + wb * i)[0]
            if v != bot:
                got[(f,) + ((i // w1, i % w1) if w1 > 1 else (i,))] = v
    return got


# ══ 法則（意味は変えず、配置だけを変える）══════════════════════════
def logical(src):
    """(種, 本文) の列。種は 'table' / 'field' / 'rule' / 'out' / 'blank'"""
    out = []; lines = src.split('\n'); i = 0
    while i < len(lines):
        l = lines[i]; s = l.split('#')[0].strip()
        if not s: out.append(('blank', l)); i += 1; continue
        if s.startswith('table '): out.append(('table', l)); i += 1; continue
        if s.startswith('field '): out.append(('field', l)); i += 1; continue
        if s.startswith('render ') or s.startswith('print '):
            out.append(('out', l)); i += 1; continue
        if '<-' in s:
            body = [l]; i += 1
            while i < len(lines):
                t = lines[i].split('#')[0].strip()
                if t.startswith('for ') or t.startswith('if '):
                    body.append(lines[i]); i += 1
                else: break
            out.append(('rule', '\n'.join(body))); continue
        out.append(('blank', l)); i += 1
    return out


def law_order(src, rnd):
    """① **順序**。最小不動点は規則の並びに依らない。"""
    parts = logical(src)
    rules = [p[1] for p in parts if p[0] == 'rule']
    if len(rules) < 2: return None
    perm = rules[:]; rnd.shuffle(perm)
    if perm == rules: return None
    it = iter(perm); out = []
    for k, v in parts:
        out.append(next(it) if k == 'rule' else v)
    return '\n'.join(out)


def law_flat(src):
    """② **平ら**。引いてから配っても答えは同じ（中間の場が一枚増えるだけ）。"""
    new, st = flatten(src, prefix='zm', wlimit=1, vlimit=2)
    if new == src: return None
    return new


def law_wide(src):
    """③ **広げ**。宣言を広げても答えは同じ（増えるのは届かない升だけ）。"""
    def w(m):
        return 'bound ' + ' '.join(str(int(x) * 2) for x in m.group(1).split())
    new = re.sub(r'bound ([0-9]+(?: [0-9]+)*)', w, src)
    return None if new == src else new


def law_dead(src, rnd):
    """④ **死んだ場**。誰も読まない場を足しても答えは同じ（動くのは配置だけ）。"""
    parts = logical(src)
    add = ("field zdead : max bound 8\n"
           "zdead[k] <- k * 2   for (k) in 0 .. 3\n")
    out = []; put = False
    for k, v in parts:
        if k == 'out' and not put: out.append(add.rstrip()); put = True
        out.append(v)
    if not put: out.append(add.rstrip())
    return '\n'.join(out)


# ══ 撒く（**新しく出来るようになった所**を厚く）═════════════════════
LATS = ['max', 'min', 'or', 'sum', 'count']


def gen(rnd):
    """深い座標・群（積の連なり）・引く群 —— 今日広がった所を狙って撒く。"""
    nf = rnd.randint(2, 4)
    src = ["table ch = (0,32)"]
    names = ['f%d' % k for k in range(nf)]
    src.append("field f0 : max bound 64")
    src.append("f0[i] <- c % 8   for (i,c) in ch")
    for k in range(1, nf):
        lat = rnd.choice(LATS)
        src.append("field f%d : %s bound 64" % (k, lat))
        prev = names[:k]
        # 値: 群を混ぜる（a * b + c、a - b * c、深い座標）
        def rd(depth):
            f = rnd.choice(prev)
            ix = 'i'
            for _ in range(depth):
                ix = '%s[%s]' % (rnd.choice(prev), ix)
            return '%s[%s]' % (f, ix)
        shape = rnd.randint(0, 6)
        if shape == 0:   v = '%s + %s * 2' % (rd(0), rd(0))
        elif shape == 1: v = '%s * 3 + %s' % (rd(0), rd(0))
        elif shape == 2: v = '%s - %s * 2' % (rd(0), rd(0))
        elif shape == 3: v = '%s + %s' % (rd(1), rd(0))
        elif shape == 4: v = '%s' % rd(2)
        elif shape == 5: v = '%s * 2 + %s * 3' % (rd(0), rd(0))
        else:            v = '%s + i * 2' % rd(0)
        if lat == 'or': v = 'true'
        g = rnd.choice(['', '   if %s >= 2' % rd(0), '   if c >= 97',
                        '   if %s != %s' % (rd(0), rd(0)),
                        '   if %s >= 1' % rd(1)])
        hd = rnd.choice(['f%d[i]' % k, 'f%d[i+1]' % k, 'f%d[%s]' % (k, rd(0))])
        if 'f%d[' % k in hd and '[i]' not in hd and '[i+1]' not in hd:
            g += '   if %s >= 0' % rd(0)
        src.append("%s <- %s   for (i,c) in ch%s" % (hd, v, g))
    return '\n'.join(src) + '\n'


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    rnd = random.Random(20260918)
    data = b'lattix meta test 42'
    W = 78
    print("=" * W)
    print("  **言語自身の法則で試す** —— 意味は変えず、配置だけを変える")
    print("=" * W)
    made = ok = skipped = 0
    broke = collections.Counter(); bad = []
    for _ in range(n):
        src = gen(rnd)
        base = cells(src, data)
        if isinstance(base, tuple): skipped += 1; continue
        made += 1
        for name, mk in (('順序', lambda s: law_order(s, rnd)),
                         ('平ら', law_flat),
                         ('広げ', law_wide),
                         ('死んだ場', lambda s: law_dead(s, rnd))):
            alt = mk(src)
            if alt is None: continue
            got = cells(alt, data)
            if isinstance(got, tuple):
                broke[name + '→焼けない'] += 1
                if len(bad) < 6: bad.append((name, got[1], src, alt))
                continue
            keys = set(k for k in got if not k[0].startswith('zm')
                       and not k[0].startswith('zdead'))
            if {k: got[k] for k in keys} != base:
                broke[name] += 1
                if len(bad) < 6: bad.append((name, '答えが違う', src, alt))
            else:
                ok += 1
    print("  撒いた %d 本（焼けた %d / 焼けない %d）、法則の試し %d 回"
          % (n, made, skipped, ok + sum(broke.values())))
    print("-" * W)
    if not broke:
        print("  **破れ無し** —— どの法則も、配置を変えても同じ答えを出した。")
    else:
        for k, v in sorted(broke.items()): print("  %-16s 破れ %d" % (k, v))
        for name, why, a, b in bad:
            print("\n  ── %s: %s ──" % (name, why))
            print("  もと:\n" + "\n".join("    " + x for x in a.strip().split('\n')))
            print("  後:\n" + "\n".join("    " + x for x in b.strip().split('\n')[:14]))
    print("=" * W)
    return 1 if broke else 0


if __name__ == '__main__':
    sys.exit(main())
