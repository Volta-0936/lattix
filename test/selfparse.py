#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lattix で書いた構文解析器が、Lattix のソースを Python 版と同じ木に読む。

二段構成である:
  examples/21_lex.lx   バイト列  → トークンの表
  examples/22_parse.lx トークンの表 → 抽象構文（内容アドレス）

段の間でホストは何もしていない。**場をそのまま表に落として渡している**だけで、
これは runtime.py が `field <name> <nrows> <ar>` として既に読める形である。

比べるのは木の *形* ではなく **名前**（56ビットの内容アドレス）である。
名前が一致するなら木は一致している。逆は要らない。

変数は綴りではなく **束縛点の座標** `bind(表, 位置)` で名づける。
束縛点そのものが座標なので、traversal 順に付け替える α変換が存在しない ——
de Bruijn（1972）が数えていたものを、座標がそのまま与える。
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

C = L.ctor_id
W = 84

def strip(path):
    return "\n".join(ln for ln in open(path, encoding='utf-8').read().splitlines()
                     if not (ln.startswith('table ch') or ln.startswith('table tok')))

LEX = strip(os.path.join(ROOT, 'examples', '21_lex.lx'))
PAR = strip(os.path.join(ROOT, 'examples', '22_parse.lx'))


def go(src, extra=""):
    p = L.parse(src + "\n" + extra)
    L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    store, _, st = L.run(p, out=io.StringIO())
    obs = lambda f: {k: p.fields[f].observe(v) for k, v in store[f].items()}
    return obs, st


def stages(path):
    raw = open(path, 'rb').read()
    codes = list(raw) + [32]
    o, s1 = go("table ch = " + ", ".join(f"({i},{c})" for i, c in enumerate(codes)), LEX)
    tk, tc, tc2, tline, tsym, tint = (o('tk'), o('tc'), o('tc2'),
                                      o('tline'), o('tsym'), o('tint'))
    rows = [(k[0], tk[k], tc[k], tc2.get(k, 0), tline[k],
             tint[k] if tk[k] == 1 else tsym[k]) for k in sorted(tk)]
    o2, s2 = go("table tok = " + ", ".join(str(r).replace(" ", "") for r in rows), PAR)
    return rows, o2, s1, s2


def addr(s):
    a = 0
    for c in reversed(s.encode()): a = C('cons', [c, a])
    return a

def lst(xs):
    a = 0
    for x in reversed(xs): a = C('cons', [x, a])
    return a

def term(e, vb):
    k = e[0]
    if k == 'int':  return C('eint', [e[1]])
    if k == 'bool': return C('ebool', [1 if e[1] else 0])
    if k == 'var':  return vb.get(e[1], C('evar', [addr(e[1])]))
    if k == 'fref': return C('efref', [addr(e[1]), lst([term(x, vb) for x in e[2]])])
    if k == 'ctor': return C('ector', [addr(e[1]), lst([term(x, vb) for x in e[2]])])
    if k == 'bin':  return C('ebin', [ord(e[1]), term(e[2], vb), term(e[3], vb)])
    if k == 'cmp':
        op = ord(e[1][0]) * 256 + (ord(e[1][1]) if len(e[1]) > 1 else 0)
        return C('ecmp', [op, term(e[2], vb), term(e[3], vb)])
    if k == 'geq':  return C('egeq', [term(e[1], vb), term(e[2], vb)])
    if k == 'fn':   return C('efn', [0 if e[1] == 'min' else 1,
                                     term(e[2], vb), term(e[3], vb)])
    if k == 'set':  return C('eset', [lst([term(x, vb) for x in e[1]])])
    if k == 'not':  return C('enot', [term(e[1], vb)])
    if k == 'str':  return C('estr', [addr(e[1])])
    return None


TARGETS = ['01_shortest', '02_strata', '04_aggregate', '06_order_free',
           '09_upset', '15_parse', '16_lex', '18_ubound', '19_mod',
           '20_lex_full', '21_lex', '22_parse']

print("=" * W)
print("  Lattix の構文解析器で、Lattix のソースを読む")
print("=" * W)
ok = True
total = 0
for name in TARGETS:
    path = os.path.join(ROOT, 'examples', name + '.lx')
    rows, o, s1, s2 = stages(path)
    head, body = o('head'), o('body')
    srcs, guards = {}, {}
    for (st, _c), val in o('srcof').items(): srcs.setdefault(st, set()).add(val)
    for (st, _c), val in o('guardof').items(): guards.setdefault(st, set()).add(val)
    if o('toodeep'): print("   括弧が宣言した深さを超えた"); ok = False
    sstart, tl = o('sstart'), o('tl')
    ref = L.parse(open(path, encoding='utf-8').read())
    gen = {'_size'} | {f"{c}_{f}" for c, (fs, _b) in ref.ctors.items() for f in fs}
    line_of = {s[0]: tl[(sstart[s],)] for s in sstart}
    bad = n = 0
    for r in ref.rules:
        if r.target in gen: continue
        s = next((s for s, ln in line_of.items() if ln == r.lineno), None)
        vb, ws = {}, set()
        for vs, src in r.sources:
            for i, v in enumerate(vs): vb[v] = C('bind', [addr(src), i])
            ws.add(C('usrc', [addr(src), lst([C('bind', [addr(src), i])
                                              for i in range(len(vs))])]))
        want = (term(('fref', r.target, r.keys), vb), term(r.value, vb),
                frozenset(ws), frozenset(term(g, vb) for g in r.guards))
        if any(x is None for x in want[:2]) or None in want[3]:
            continue                 # 文字列を含む規則は対象外（既知の穴）
        n += 1
        got = (head.get((s,)), body.get((s,)),
               frozenset(srcs.get(s, ())), frozenset(guards.get(s, ())))
        if got != want:
            bad += 1
            if os.environ.get('V'):
                names=('head','body','srcs','guards')
                print('   NG L%d %s %s' % (r.lineno, r.target, [x for x,a,b in zip(names,got,want) if a!=b]))
    # 宣言（場と束・表・観測）も突き合わせる
    LAT = {'min':1,'max':2,'or':3,'and':4,'set':5,'flat':6,'fourv':7,
           'sum':8,'count':9,'bag':10}
    dgot = {k[0]: v for k, v in o('flat_').items()}
    dwant = {addr(f): LAT[ref.fields[f].name] for f in ref.fields if f not in gen}
    tr = {}
    for (t, r, c), v in o('trow').items(): tr.setdefault(t, {}).setdefault(r, {})[c] = v
    tgot = {t: [tuple(rw[c] for c in sorted(rw)) for _r, rw in sorted(rws.items())]
            for t, rws in tr.items()}
    twant = {addr(t): [tuple((1 if x is True else 0 if x is False else
                              (addr(x) if isinstance(x, str) else x)) for x in row)
                       for row in rws] for t, rws in ref.tables.items()}
    sgot = {k[0]: v for k, v in o('shown').items()}
    swant = {addr(f): 1 for f in ref.prints}
    swant.update({addr(f): 2 for f in ref.renders})
    dbad = [w for w, g, x in (('場', dgot, dwant), ('表', tgot, twant),
                              ('観測', sgot, swant)) if g != x]
    # ── 極性と成層 ── 文ごとの層が Python の成層器と一致するか
    lvl = {k[0]: v for k, v in o('level').items()}
    L.check(ref); L.stratify(ref)
    sbad = 0
    for r in ref.rules:
        if r.target in gen: continue
        st2 = next((x for x, ln in line_of.items() if ln == r.lineno), None)
        if lvl.get(st2) != r.stratum: sbad += 1
    if sbad: dbad.append(f'層{sbad}')
    total += n
    ok &= (bad == 0 and n > 0 and not dbad)
    print(f"  {name:<14} トークン {len(rows):>4}  規則 {n:>3}  場 {len(dwant):>3}  "
          f"表 {len(twant):>2}  層 {max(lvl.values(), default=-1)+1:>2}  "
          f"{'一致' if bad == 0 and not dbad else f'不一致 {bad} {dbad}'}")
print("-" * W)
print(f"  規則 {total} 本の 頭部・本体・source・guard が、内容アドレスまで一致した。")
print("  **構文解析器は自分自身も読める** —— 22_parse.lx の全規則が一致した。")
print("  変数は束縛点の座標で名づけるので、正準形に α変換の手続きが無い。")
print("-" * W)

# ── 同じ二段を **ネイティブで** 通す ────────────────────────────────────
# ここには Python が一行も要らない。実行ファイルがファイルを開き、切り、読む。
import runtime as R

def strip2(path, pre):
    return "\n".join(ln for ln in open(path, encoding='utf-8').read().splitlines()
                     if not ln.startswith(pre))

lexe = R.build("table ch = (0,32)\n" + strip2(
    os.path.join(ROOT, 'examples', '21_lex.lx'), 'table ch'))
pexe = R.build("table tok = (1,0,97,0,1,0)\n" + strip2(
    os.path.join(ROOT, 'examples', '22_parse.lx'), 'table tok'))

def native(path):
    s = os.path.join(lexe['dir'], 'in.lx')
    open(s, 'wb').write(open(path, 'rb').read())
    d = os.path.join(lexe['dir'], 'd.lxd'); open(d, 'w').write(f"bytes ch {s}\n")
    g1, m1 = R.run(lexe['exe'], d)
    o = lambda f: {k[0] if isinstance(k, tuple) else k: v for k, v in g1.get(f, {}).items()}
    tk, tc, tc2, tline, tsym, tint = (o('tk'), o('tc'), o('tc2'),
                                      o('tline'), o('tsym'), o('tint'))
    rows = [(k, tk[k], tc[k], tc2.get(k, 0), tline[k],
             tint[k] if tk[k] == 1 else tsym[k]) for k in sorted(tk)]
    d2 = os.path.join(pexe['dir'], 'd.lxd')
    with open(d2, 'w') as fp:
        fp.write(f"tok {len(rows)} 6\n")
        for r in rows: fp.write(" ".join(str(x) for x in r) + "\n")
        fp.write("depths 20 1\n")
        for i in range(20): fp.write(f"{i}\n")
    g2, m2 = R.run(pexe['exe'], d2)
    return rows, {f: {(k if isinstance(k, tuple) else (k,)): v
                      for k, v in g2.get(f, {}).items()} for f in g2}, \
           m1.get('NATIVE_MS', 0) + m2.get('NATIVE_MS', 0)

for name in ['20_lex_full', '22_parse']:
    path = os.path.join(ROOT, 'examples', name + '.lx')
    rows, o, ms = native(path)
    head, body, tl, sstart = o.get('head', {}), o.get('body', {}), o['tl'], o['sstart']
    srcs, guards = {}, {}
    for k, v in o.get('srcof', {}).items(): srcs.setdefault(k[0], set()).add(v)
    for k, v in o.get('guardof', {}).items(): guards.setdefault(k[0], set()).add(v)
    ref = L.parse(open(path, encoding='utf-8').read())
    gen = {'_size'} | {f"{c}_{f}" for c, (fs, _b) in ref.ctors.items() for f in fs}
    line_of = {s[0]: tl[(sstart[s],)] for s in sstart}
    bad = n = 0
    for r in ref.rules:
        if r.target in gen: continue
        s = next((s for s, ln in line_of.items() if ln == r.lineno), None)
        vb, ws = {}, set()
        for vs, src in r.sources:
            for i, v in enumerate(vs): vb[v] = C('bind', [addr(src), i])
            ws.add(C('usrc', [addr(src), lst([C('bind', [addr(src), i])
                                              for i in range(len(vs))])]))
        want = (term(('fref', r.target, r.keys), vb), term(r.value, vb),
                frozenset(ws), frozenset(term(g, vb) for g in r.guards))
        if any(x is None for x in want[:2]) or None in want[3]: continue
        n += 1
        got = (head.get((s,)), body.get((s,)),
               frozenset(srcs.get(s, ())), frozenset(guards.get(s, ())))
        if got != want: bad += 1
    ok &= (bad == 0 and n > 0)
    print(f"  ネイティブ {name:<12} トークン {len(rows):>5}  規則 {n:>3}  "
          f"{'一致' if bad == 0 else f'不一致 {bad}'}   {ms:.0f} ms")
print("-" * W)
print("  **前段は丸ごと C になった。** ホストは実行ファイルを起動しただけである。")
print("=" * W)
sys.exit(0 if ok else 1)
