#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**変異で撒く** —— 通る本を一行ずつ壊して、焼いた側が黙って外れないかを見る。

`differ.py` は文法から形を撒く。撒く形は文法が知っている形だけである。
ここでは `accept.py` の **通る本**を種にして、一か所だけ壊す（行を二度・行を消す・
読みの名を替える・束を替える・`not` を足す・数を替える・規則を入れ替える・値に
場を足す・行を動かす・演算子や比較を替える・宣言の名だけ替える・括弧を一つ
消す・広さを縮める・添字をずらす・区間を替える・ガードを足す・`true` と数を入れ替える・
項を入れ替える・二か所壊す・**語を足す・消す・二度書く・`-` を付ける・丸括弧で包む・
演算子を重ねる**）。壊れた本は、答えの定義（lattix.py）が答えるか断るかの
どちらかである。焼いた側に許されるのは:

    答える  → 解釈実行と升まで一致する
    断る    → 終了コード 6（広さ）/ 7（焼けない形。理由つき）/ 5（⊤。答えが ⊤ を含むとき）

これ以外 —— **黙って違う答え**、**落ちる**（segfault）、**解釈実行が断るのに答える** ——
はどれも嘘である。最初に回したとき、125 本のうち 22 本がそうだった
（二度の宣言・規則の無い場・規則の無い源・比較の節の not・集約の二重ループ・
`true` の値・or の式・頭の無い矢印・閉じない括弧・次元の混在・否定と広さの外・
内側の添字の濾し）。

種には `work/t` の本も入れる（表は源に書いてあるので、口から渡す形に直す）。
本を足した日、**壊す前の本が二冊、黙って違う答えを出していた** —— 区間の上端が式の
`z_depint`（`0 .. n[i] - 1` を `n[?]` と読んだ）と、三次元の場の `z_dim2rd`
（三つ目の添字を落とした）。種そのものも、壊す前に一度比べる価値がある。

   使い方:  python3 test/mutate.py [本数] [種]
"""
import os, re, struct, subprocess, sys, io, random, tempfile, collections, signal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
LATTIX = os.environ.get('LATTIX_EXE', os.path.join(ROOT, 'lattix'))
W = 78

# 種は `accept.py` の「通る本」（答えを比べる組）。試験の本体は走らせない。
_src = open(os.path.join(ROOT, 'test', 'accept.py'), encoding='utf-8').read()
_ns = {'__name__': 'mutate', '__file__': os.path.join(ROOT, 'test', 'accept.py')}
exec(compile(_src[:_src.index("tmp=tempfile.mkdtemp()")], 'accept', 'exec'), _ns)
# 既知の穴の組は種にしない（壊すと同じ穴を踏む —— 測られているものを数え直さない）
SEEDS = [c for c in _ns['CASES'] if c[4] is None and not c[5] and 'render ' not in c[1]]
widths, BOT = _ns['widths'], _ns['BOT']


def _book_seeds():
    """`work/t` の本も種にする。表は源に書いてあるので、それを口から渡す形に直す
    （二列は生バイト、三列以上は 8 バイト小端の列）。"""
    import glob
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, 'work', 't', '*.lx'))):
        src = open(path, encoding='utf-8').read()
        if 'render ' in src or 'use ' in src or 'include ' in src: continue
        try: p = L.parse(src)
        except Exception: continue
        if len(p.tables) != 1: continue
        (tn, rows), = p.tables.items()
        if not rows: continue
        if any(not isinstance(x, int) for r in rows for x in r): continue
        if len(rows[0]) == 2:
            if [r[0] for r in rows] != list(range(len(rows))): continue
            if any(not (0 <= r[1] <= 255) for r in rows): continue
            out.append((os.path.basename(path), src, bytes(r[1] for r in rows), None, None, False, None))
        else:
            out.append((os.path.basename(path), src, b'', [tuple(r) for r in rows], None, False, None))
    return out


SEEDS += _book_seeds()
LATS = ['min', 'max', 'or', 'flat', 'sum', 'count']


def mutate(s, rnd):
    lines = s.split('\n'); k = rnd.randrange(26)
    fl = re.findall(r'(?m)^field (\w+)', s)
    idx = [i for i, l in enumerate(lines) if l.strip()]
    if not idx: return None
    i = rnd.choice(idx)
    if k == 0: lines.insert(i, lines[i])                                  # 行を二度
    elif k == 1:                                                         # 行を消す
        if lines[i].startswith('table'): return None
        del lines[i]
    elif k == 2 and len(fl) >= 2:                                        # 読みの名を替える
        a, b = rnd.sample(fl, 2)
        occ = [m.start() for m in re.finditer(r'\b%s\[' % a, s)]
        if not occ: return None
        p = rnd.choice(occ); return s[:p] + b + s[p + len(a):]
    elif k == 3:                                                         # 束を替える
        m = [j for j, l in enumerate(lines) if l.startswith('field ')]
        if not m: return None
        j = rnd.choice(m); lines[j] = re.sub(r': (\w+)', ': ' + rnd.choice(LATS), lines[j], count=1)
    elif k == 4:                                                         # ガードに not
        m = [j for j, l in enumerate(lines) if ' if ' in l and ' if not ' not in l]
        if not m: return None
        j = rnd.choice(m); lines[j] = lines[j].replace(' if ', ' if not ', 1)
    elif k == 5:                                                         # 数を替える
        nums = list(re.finditer(r'(?<![\w\[])(\d+)(?![\w])', lines[i]))
        if not nums or lines[i].startswith('table'): return None
        mm = rnd.choice(nums); v = int(mm.group(1))
        nv = rnd.choice([0, 1, 2, v + 1, max(0, v - 1), v * 2, 255])
        lines[i] = lines[i][:mm.start()] + str(nv) + lines[i][mm.end():]
    elif k == 6:                                                         # 規則を入れ替える
        r = [j for j, l in enumerate(lines) if '<-' in l]
        if len(r) < 2: return None
        a, b = rnd.sample(r, 2); lines[a], lines[b] = lines[b], lines[a]
    elif k == 7:                                                         # 値に場を足す・引く・掛ける
        r = [j for j, l in enumerate(lines) if '<-' in l and ' for ' in l]
        if not r or not fl: return None
        j = rnd.choice(r); f = rnd.choice(fl); op = rnd.choice(['+', '-', '*'])
        v = re.search(r'for \((\w+)', lines[j])
        if not v: return None
        lines[j] = re.sub(r'<- (.*?)(\s+for )',
                          lambda m_: '<- %s %s %s[%s]%s' % (m_.group(1), op, f, v.group(1), m_.group(2)),
                          lines[j], count=1)
    elif k == 8:                                                         # 行を動かす
        if len(idx) < 3: return None
        j = rnd.choice(idx); l = lines.pop(i); lines.insert(min(j, len(lines)), l)
    elif k == 9:                                                         # 演算子を替える
        ops = list(re.finditer(r' ([+\-*/%]) ', lines[i]))
        if not ops: return None
        mm = rnd.choice(ops)
        lines[i] = lines[i][:mm.start(1)] + rnd.choice('+-*/%') + lines[i][mm.end(1):]
    elif k == 10:                                                        # 比較を替える
        ops = list(re.finditer(r' (==|!=|>=|<=|>|<) ', lines[i]))
        if not ops: return None
        mm = rnd.choice(ops)
        lines[i] = lines[i][:mm.start(1)] + rnd.choice(['==', '!=', '>=', '<=', '>', '<']) + lines[i][mm.end(1):]
    elif k == 11:                                                        # 宣言の名だけ替える
        m = [j for j, l in enumerate(lines) if l.startswith('field ')]
        if not m: return None
        j = rnd.choice(m); lines[j] = re.sub(r'^field (\w+)', r'field \1x', lines[j])
    elif k == 12:                                                        # 括弧を一つ消す
        ps = [q for q, ch in enumerate(lines[i]) if ch in '[]()']
        if not ps: return None
        q = rnd.choice(ps); lines[i] = lines[i][:q] + lines[i][q + 1:]
    elif k == 13:                                                        # 広さを縮める
        m = [j for j, l in enumerate(lines) if l.startswith('field ') and 'bound' in l]
        if not m: return None
        j = rnd.choice(m)
        lines[j] = re.sub(r'bound (\d+)', lambda mm: 'bound %d' % max(1, int(mm.group(1)) // 4), lines[j], count=1)
    elif k == 14:                                                        # 添字をずらす
        m = list(re.finditer(r'\[(\w+)\]', lines[i]))
        if not m: return None
        mm = rnd.choice(m); d = rnd.choice(['+1', '-1', '+2', '-3'])
        lines[i] = lines[i][:mm.start()] + '[%s%s]' % (mm.group(1), d) + lines[i][mm.end():]
    elif k == 15:                                                        # 区間を替える
        m = list(re.finditer(r'in (\d+) \.\. (\d+)', lines[i]))
        if not m: return None
        mm = rnd.choice(m)
        lo, hi = rnd.choice([(0, 0), (3, 1), (0, 200), (1, 1), (0, 63), (2, 5)])
        lines[i] = lines[i][:mm.start()] + 'in %d .. %d' % (lo, hi) + lines[i][mm.end():]
    elif k == 16:                                                        # ガードを足す
        r = [j for j, l in enumerate(lines) if '<-' in l and ' for ' in l]
        if not r or not fl: return None
        j = rnd.choice(r); f = rnd.choice(fl)
        v = re.search(r'for \((\w+)', lines[j])
        if not v: return None
        g = rnd.choice(['if %s[%s]', 'if not %s[%s]', 'if %s[%s] >= 1', 'if %s[%s] == 0', 'if %s[%s] < 3'])
        lines[j] = lines[j] + '   ' + g % (f, v.group(1))
    elif k == 17:                                                        # true と数を入れ替える
        if 'true' in lines[i]: lines[i] = lines[i].replace('true', rnd.choice(['1', '0', '2']), 1)
        else:
            m = list(re.finditer(r'<- (\d+)', lines[i]))
            if not m: return None
            mm = m[0]; lines[i] = lines[i][:mm.start()] + '<- true' + lines[i][mm.end():]
    elif k == 18:                                                        # 項を入れ替える
        m = re.search(r'<- (\S+) ([+\-*]) (\S+)(\s)', lines[i])
        if not m: return None
        lines[i] = lines[i][:m.start()] + '<- %s %s %s%s' % (m.group(3), m.group(2), m.group(1), m.group(4)) + lines[i][m.end():]
    elif k == 19:                                                        # 二か所壊す
        a = mutate(s, rnd)
        return mutate(a, rnd) if a else None
    elif k >= 20:                                                        # **字句を撒く**
        # 上の十九の壊し方は、どれも行か正規表現の単位で、**語の並び**そのものは壊さない。
        # 焼く側の前段は知らない語を黙って読み飛ばしていた（丸括弧・演算子の重なり・
        # 座標の `i*2`・ガードの `not not`・for の後ろの語）—— 語を一つ足す・消す・
        # 二度書く・先頭に `-` を付ける・丸括弧で包む・演算子を重ねる。
        r = [j for j, l in enumerate(lines) if '<-' in l]
        if not r: return None
        j = rnd.choice(r)
        toks = re.findall(r'\w+|[^\w\s]|\s+', lines[j])
        pos = [q for q, t in enumerate(toks) if not t.isspace()]
        if not pos: return None
        q = rnd.choice(pos); kk = k - 20
        if kk == 0:                                                      # 語を一つ足す
            toks.insert(q, ' %s ' % rnd.choice(['-', '+', '*', '/', '%', '(', ')', ',', '3',
                                                'not', 'i', '..', '=', '<', '>', 'true', '[', ']']))
        elif kk == 1: toks.insert(q, toks[q])                            # 二度書く
        elif kk == 2: del toks[q]                                        # 消す
        elif kk == 3:                                                    # 先頭に `-`
            w = [x for x in pos if re.match(r'\w', toks[x])]
            if not w: return None
            toks.insert(rnd.choice(w), '-')
        elif kk == 4:                                                    # 丸括弧で包む
            w = [x for x in pos if re.match(r'\w', toks[x])]
            if not w: return None
            a = rnd.choice(w); b = min(len(toks) - 1, a + rnd.randint(0, 4))
            toks.insert(b + 1, ')'); toks.insert(a, '(')
        elif kk == 5:                                                    # 演算子を重ねる
            w = [x for x in pos if toks[x] in '+-*/%']
            if not w: return None
            toks.insert(rnd.choice(w) + 1, ' %s' % rnd.choice(['-', '+', '*']))
        lines[j] = ''.join(toks)
    else: return None
    return '\n'.join(lines)


def answer(s, data, rows):
    """答えの定義。⊤ を含むかも返す。"""
    p = L.parse(s); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    t = [t for t in p.tables][0]
    p.tables[t] = ([(i, c) for i, c in enumerate(data)] if data else [(0, 32)]) if rows is None else list(rows)
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


class _Slow(Exception): pass
def _alarm(*a): raise _Slow()


if __name__ == '__main__':
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 20260919)
    signal.signal(signal.SIGALRM, _alarm)
    tmp = tempfile.mkdtemp(); kinds = collections.Counter(); bad = []
    import atexit, shutil; atexit.register(shutil.rmtree, tmp, True)   # 焼いた物は走り終えたら消す
    print("=" * W)
    print("  **変異で撒く** —— 通る本を一か所だけ壊し、焼いた側が黙って外れないか")
    print("=" * W)
    for n in range(N):
        name, s0, data, rows, _x, _k, _w = rnd.choice(SEEDS)
        s = mutate(s0, rnd)
        if not s or s == s0: continue
        inp = data if rows is None else b''.join(struct.pack('<' + 'q' * len(t), *t) for t in rows)
        why = ''
        try:
            signal.alarm(20); ref, top = answer(s, data, rows); signal.alarm(0); ok = True
        except _Slow: kinds['解釈実行が遅い（数えない）'] += 1; continue
        except Exception as ex: signal.alarm(0); ok = False; why = str(ex)
        r = subprocess.run([LATTIX], input=s.encode(), capture_output=True)
        if r.returncode or r.stdout[:4] != b'\x7fELF':
            bad.append((name, s, '焼き手が落ちた %d' % r.returncode)); continue
        exe = os.path.join(tmp, 'm.out'); open(exe, 'wb').write(r.stdout); os.chmod(exe, 0o755)
        try: r2 = subprocess.run([exe], input=inp, capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            # **昇鎖が止まらない本**（`a[i] <- a[i] + i * 2`）には最小不動点が無い。解釈実行は
            # 変化の回数の見張りで止めて断り、焼いた側は見張りを持たず回り続ける（progs.py と同じ
            # 数え方）。答えは出さないので嘘ではないが、**断りでもない** —— 数えて見せる。
            if not ok and ('fire budget' in why or 'did not converge' in why):
                kinds['昇鎖が止まらない（両者とも答えない）'] += 1
            else: bad.append((name, s, '焼いた側が止まらない'))
            continue
        rc = r2.returncode
        if not ok:
            if rc == 0: bad.append((name, s, '解釈実行は断るのに、焼いた側は答えた'))
            elif rc in (3, 4, 5, 6, 7): kinds['両者が断る'] += 1
            else: bad.append((name, s, '解釈実行は断る / 焼いた側は終了コード %d' % rc))
            continue
        if rc in (6, 7): kinds['焼く側が断る（%d）' % rc] += 1; continue
        if rc == 5:
            if top: kinds['両者 ⊤（焼く側は 5 で言う）'] += 1
            else: bad.append((name, s, '⊤ の無い答えで終了コード 5'))
            continue
        if rc == 4:                              # 値が印と重なった —— 答えに印と同じ値があるはず
            _o, _lat, _off, _t = widths(s)
            hit = [1 for k, v in ref.items() if (_lat.get(k[0]) == 'min' and v >= 2147483647)
                   or (_lat.get(k[0]) == 'max' and v <= -2147483647)
                   or (_lat.get(k[0]) == 'flat' and v in (2147483646, 2147483647))]
            if hit: kinds['値が印に届く（焼く側は 4 で言う）'] += 1
            else: bad.append((name, s, '印の無い答えで終了コード 4'))
            continue
        if rc == 3:                              # 値が 64 ビットに収まらない —— 答えにそういう値があるはず
            if [1 for v in ref.values() if not -2**63 <= v < 2**63]:
                kinds['64 ビットを超える（焼く側は 3 で言う）'] += 1
            else: bad.append((name, s, '64 ビットに収まる答えで終了コード 3'))
            continue
        if rc != 0: bad.append((name, s, '終了コード %d %s' % (rc, r2.stderr[:60]))); continue
        order, lat, off, tot = widths(s)
        if len(r2.stdout) != tot:
            bad.append((name, s, '面の大きさ %d != %d' % (len(r2.stdout), tot))); continue
        got = {}
        for f in order:
            o, cells, w1, wb = off[f]; bot = BOT.get(lat[f])
            if bot is None: continue
            for i in range(cells):
                v = struct.unpack_from('<q' if wb == 8 else '<B', r2.stdout, o + wb * i)[0]
                if v != bot: got[(f,) + ((i // w1, i % w1) if w1 > 1 else (i,))] = v
        if got == ref: kinds['一致'] += 1
        else:
            dv = [(x, ref.get(x), got.get(x)) for x in sorted(set(got) | set(ref)) if got.get(x) != ref.get(x)][:3]
            bad.append((name, s, '値が違う %s' % dv))
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<34}{v:>6}")
    print("-" * W)
    for name, s, why in bad[:10]:
        print(f"  ✗ {name}: {why}")
        for l in s.split('\n'): print('      ' + l)
    if bad:
        print(f"  **破れ {len(bad)}** —— 焼いた側が、答えも断りもしない形で外れた。"); sys.exit(1)
    print("  **破れ無し** —— 壊した本はすべて、両者が同じ答えを出すか、焼いた側が理由を言って断った。")
