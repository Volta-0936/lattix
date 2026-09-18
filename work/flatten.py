#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**断片が読める形へ落とす一枚の写し。** —— 引いてから配る。

`front.lx` は解釈実行に向けて書かれたので、好きなだけ入れ子を書けたし、
ガードの辺に式も書けた。焼ける形（`31_gen.lx` の断片）はもっと狭い。
**狭さは測った**（`test/accept.py` の「断片の際」の組）——

    書き座標   `w[i]` `w[a[i]]`                    …読みは **一段まで**
    値・ガード `a[i]` `a[b[i]]`                    …読みは **二段まで**
    ガードの辺 `a[i]` `i` `3`                      …**式は置けない**

三つ目が一番怖い。`if k <= tlen[t] - 1` は以前 **黙って通って**、
`tlen[t]` の番号を場の番号として読む命令になり segfault した。いまは
断られる（33_self が「知らない種 15」を立て、31_gen がそれを出さない）。
断られるようになったから、こちらで直せる —— 直し方は一つしかない:

    if k <= tlen[t] - 1
      ↓
    field zh1 : max bound <t の定義域>
    zh1[t] <- tlen[t] - 1     for (t,zc) in ch
    if k <= zh1[t]            if zh1[t] >= 0

`>= 0` は ⊥ を落とすため（⊥ の座標では元の規則も撃たない）。同時に
**比較のガードが層を切る**ので、育っている場を座標に使わずに済む（気づき38）。

引く規則には元のガードを付けない。付けなくても値は同じで、消す側の
`>= 0` が ⊥ を落とす。付けると同じ判定を場ごとに何度も回すことになる。

**輪の節はそのまま写す。** 定義域を当てるのではなく、元の規則が回している
ものをそのまま回す —— 推測しない。広さ（bound）だけは、その規則が既に
その変数で引いている場から借りる。

これは書き換えの道具であって、走るときには居ない。
"""
import re, sys, collections

IDN = r'[A-Za-z_][A-Za-z_0-9]*'


# ══ 字面を割る ════════════════════════════════════════════════════
def match_bracket(s, i):
    """s[i] == '[' のとき、対応する ']' の位置"""
    d = 0
    for j in range(i, len(s)):
        if s[j] == '[': d += 1
        elif s[j] == ']':
            d -= 1
            if d == 0: return j
    return -1


def logical_rules(src):
    """継続行を畳んで論理規則にする。(開始行, 行数, 本文) の列を返す。"""
    lines = src.split('\n')
    out = []; cur = None
    for i, l in enumerate(lines):
        s = l.split('#')[0].strip()
        if not s:
            if cur: out.append(cur); cur = None
            continue
        if '<-' in s:
            if cur: out.append(cur)
            cur = [i, 1, s]
        elif cur and (s.startswith('for ') or s.startswith('if ')):
            cur[1] += 1; cur[2] += ' ' + s
        else:
            if cur: out.append(cur); cur = None
    if cur: out.append(cur)
    return lines, out


def decls(src):
    """場の名 → (束, [広さ…])"""
    d = {}
    for m in re.finditer(r'(?m)^field (' + IDN + r') : (\w+)(?: bound ([0-9 ]+))?', src):
        d[m.group(1)] = (m.group(2), (m.group(3) or '64').split())
    return d


def split_head(body):
    """`f[IX] <- rest` を (名, 添字, 残り) に"""
    m = re.match(r'(' + IDN + r')\[', body)
    if not m: return None
    i = m.end() - 1
    j = match_bracket(body, i)
    if j < 0: return None
    rest = body[j+1:].lstrip()
    if not rest.startswith('<-'): return None
    return m.group(1), body[i+1:j], rest[2:].strip()


def clauses(rest):
    """値と、for / if の節に割る"""
    parts = re.split(r'\s+(?=for\s|if\s)', rest.strip())
    return parts[0], parts[1:]


def loop_clauses(cls):
    return [c for c in cls if c.startswith('for ')]


def loop_vars(cls):
    vs = []
    for c in loop_clauses(cls):
        m = re.match(r'for \(([^)]*)\)', c)
        if not m: continue
        for v in m.group(1).split(','):
            v = v.strip()
            if v: vs.append(v)
    return vs


def top_commas(s):
    """括弧の外のコンマで割る"""
    out = []; d = 0; last = 0
    for i, ch in enumerate(s):
        if ch == '[': d += 1
        elif ch == ']': d -= 1
        elif ch == ',' and d == 0:
            out.append(s[last:i]); last = i + 1
    out.append(s[last:])
    return [x.strip() for x in out]


def depth(s):
    """読みの最大段数（`v` は 0、`h[v]` は 1、`g[h[v]]` は 2）"""
    best = 0; i = 0
    while i < len(s):
        m = re.compile(IDN + r'\s*\[').match(s, i)
        if m:
            j = match_bracket(s, m.end() - 1)
            if j < 0: break
            best = max(best, 1 + depth(s[m.end():j]))
            i = m.end()
        else:
            i += 1
    return best


def strip_brackets(s):
    """`[...]` の中を落とす（深さ0だけを見るため）"""
    out = []; i = 0
    while i < len(s):
        if s[i] == '[':
            j = match_bracket(s, i)
            if j < 0: break
            out.append('@'); i = j + 1
        else:
            out.append(s[i]); i += 1
    return ''.join(out)


def split_cmp(g):
    """`A op B` を (A, op, B) に割る。**割るのは括弧の外の比較だけ**。"""
    d = 0; i = 0
    while i < len(g):
        ch = g[i]
        if ch == '[': d += 1
        elif ch == ']': d -= 1
        elif d == 0:
            for op in ('==', '!=', '<=', '>='):
                if g.startswith(op, i):
                    return g[:i].strip(), op, g[i+2:].strip()
            if ch in '<>':
                return g[:i].strip(), ch, g[i+1:].strip()
        i += 1
    return None


def has_op(expr):
    """括弧の外に `+ - * / %` があるか"""
    return re.search(r'[+\-*/%]', strip_brackets(expr)) is not None


# ══ 広さを借りる ══════════════════════════════════════════════════
def bound_for(var, body, dec):
    """輪の変数 v の広さを、同じ規則の中で `X[… v …]` と引いている場から借りる。
       **推測しない** —— その規則が既に使っている広さをそのまま使う。"""
    for m in re.finditer(r'(' + IDN + r')\s*\[', body):
        nm = m.group(1)
        if nm not in dec: continue
        j = match_bracket(body, m.end() - 1)
        if j < 0: continue
        for k, part in enumerate(top_commas(body[m.end():j])):
            if part == var:
                bs = dec[nm][1]
                if k < len(bs): return bs[k]
    return None


# ══ 引いてから配る ════════════════════════════════════════════════
class Hoist:
    """一つの源に対する引き出し。同じ式は一枚で済ませる。"""

    def __init__(self, dec, prefix):
        self.dec = dec; self.prefix = prefix
        self.shared = {}          # (式, 輪の文) → (場の名, 変数列)
        self.order = []           # (置く行, 場の名, 広さ列, 変数列, 式, 輪の文)
        self.n = 0
        self.refused = []

    def pull(self, expr, vs, loops, body, at):
        """式 expr を場に引き、`zh[v…]` という読みを返す。できなければ None。"""
        # **負の字面は値にならない。** `-9` は `0 - 9` と書けば項の列になる
        # （引き算は左から畳むので、後ろに続く項があっても意味は変わらない）。
        expr = expr.strip()
        if expr.startswith('-'): expr = '0 - ' + expr[1:].strip()
        used = [v for v in vs
                if re.search(r'(?<![A-Za-z0-9_])' + re.escape(v) + r'(?![A-Za-z0-9_])', expr)]
        seen = []
        for v in used:
            if v not in seen: seen.append(v)
        used = seen
        if not used:
            # **輪に依らない式は一升に引く。** `if zsof[o] <= 0 - 1` や
            # `if Fplat[e,u] == -9` の辺がこれである —— 定数の座標で引けば
            # 辺になる（`if f[C]` は断片が読める形）。
            bs = ['1']; loops = 'for (z) in 0 .. 0'; used = ['z']; ref = '0'
        else:
            bs = [bound_for(v, body, self.dec) for v in used]
            if any(b is None for b in bs): return None
            ref = None
        key = (expr, loops)
        got = self.shared.get(key)
        if got is None:
            self.n += 1
            nm = '%s%d' % (self.prefix, self.n)
            self.shared[key] = (nm, used, ref)
            self.order.append((at, nm, bs, used, expr, loops))
            got = (nm, used, ref)
        ix = got[2] if got[2] is not None else ', '.join(got[1])
        return '%s[%s]' % (got[0], ix)

    def decl_lines(self):
        ins = collections.defaultdict(list)
        for at, nm, bs, used, expr, loops in self.order:
            ins[at].append('field %s : max bound %s   # 引いてから配る'
                           % (nm, ' '.join(bs)))
            ins[at].append('%s[%s] <- %s %s' % (nm, ', '.join(used), expr, loops))
        return ins


def innermost_over(expr, vs, limit):
    """段数が limit を超える式の中の、**一番内側の深すぎる読み**を一つ返す。
       返り値は (開始, 終わり, 部分式)。無ければ None。"""
    best = None
    i = 0
    stack = []
    while i < len(expr):
        m = re.compile(IDN + r'\s*\[').match(expr, i)
        if m:
            j = match_bracket(expr, m.end() - 1)
            if j < 0: break
            sub = expr[m.start():j+1]
            d = depth(sub)
            if d >= 2:
                inner = innermost_over(expr[m.end():j], vs, limit)
                if inner is not None:
                    a, b, e = inner
                    return (m.end() + a, m.end() + b, e)
                cand = (m.start(), j+1, sub)
                if best is None or (cand[1]-cand[0]) < (best[1]-best[0]):
                    best = cand
            i = m.end()
        else:
            i += 1
    return best


def flatten(src, prefix='zh', ctx='', wlimit=1, vlimit=2):
    """三つの狭さへ落とす。書き換えた源と数えを返す。"""
    lines, rules = logical_rules(src)
    dec = decls((ctx + '\n' + src) if ctx else src)
    H = Hoist(dec, prefix)
    nw = nv = ng = 0
    refused = []
    for start, span, body in rules:
        h = split_head(body)
        if not h: continue
        nm, ix, rest = h
        val, cls = clauses(rest)
        vs = loop_vars(cls)
        loops = ' '.join(loop_clauses(cls))
        if not loops: continue
        add = []          # 書き座標に使った引き（⊥ を落とす）
        changed = False

        # ── ① 書き座標: 読みは一段まで ──────────────────────────
        newix = ix
        while depth(newix) > wlimit:
            cand = innermost_over(newix, vs, wlimit)
            if cand is None: cand = (0, len(newix), newix)
            a, b, e = cand
            rd = H.pull(e, vs, loops, body, start)
            if rd is None: break
            newix = newix[:a] + rd + newix[b:]
            add.append(rd); changed = True
        if depth(newix) > wlimit:
            refused.append((start+1, 'w', body[:110])); continue
        if newix != ix: nw += 1

        # ── ② 値: 読みは二段まで ────────────────────────────────
        newval = val
        while depth(newval) > vlimit:
            cand = innermost_over(newval, vs, vlimit)
            if cand is None: break
            a, b, e = cand
            rd = H.pull(e, vs, loops, body, start)
            if rd is None: break
            newval = newval[:a] + rd + newval[b:]
            changed = True
        if depth(newval) > vlimit:
            refused.append((start+1, 'v', body[:110])); continue
        if newval != val: nv += 1

        # ── ③ ガード: 読みは二段まで、辺に式は置けない ──────────
        newcls = []; gfix = False
        for c in cls:
            if not c.startswith('if'):
                newcls.append(c); continue
            g = c[2:].strip()
            neg = g.startswith('not ')
            if neg: g = g[4:].strip()
            sp = split_cmp(g)
            es = [sp[0], sp[2]] if sp else [g]
            newes = []; ok = True
            for e in es:
                ne = e
                while depth(ne) > vlimit:
                    cand = innermost_over(ne, vs, vlimit)
                    if cand is None: ok = False; break
                    x, y, sub = cand
                    rd = H.pull(sub, vs, loops, body, start)
                    if rd is None: ok = False; break
                    ne = ne[:x] + rd + ne[y:]
                if not ok: break
                if has_op(ne):
                    rd = H.pull(ne, vs, loops, body, start)
                    if rd is None: ok = False; break
                    ne = rd
                newes.append(ne)
            if not ok:
                refused.append((start+1, 'g', body[:110])); newcls = None; break
            ng2 = ('if %s %s %s' % (newes[0], sp[1], newes[1])) if sp else \
                  ('if %s%s' % ('not ' if neg else '', newes[0]))
            if ng2 != c: gfix = True; changed = True
            newcls.append(ng2)
        if newcls is None: continue
        if gfix: ng += 1

        if not changed: continue
        # **`>= 0` を付けるのは書き座標に引いたものだけ。** 値やガードに
        # 付けると意味が変わる —— `if not a[b[p[i]]]` は中が ⊥ のとき
        # **撃つ**のであって、撃たないのではない（⊥ は 0 ではない）。
        # 座標では要る: 書き座標の ⊥ は 0 に落ちて 0 番の升を汚すから。
        guard = ''.join(' if %s >= 0' % rd for rd in dict.fromkeys(add))
        lines[start] = '%s[%s] <- %s %s%s' % (nm, newix, newval, ' '.join(newcls), guard)
        for k in range(1, span): lines[start+k] = None

    ins = H.decl_lines()
    out = []
    for i, l in enumerate(lines):
        if i in ins: out.extend(ins[i])
        if l is not None: out.append(l)
    return '\n'.join(out), dict(w=nw, v=nv, g=ng, fields=H.n, refused=refused)


if __name__ == '__main__':
    p = sys.argv[1] if len(sys.argv) > 1 else '/root/repo/front.lx'
    src = open(p, encoding='utf-8').read()
    ctx = ''
    for q in ('/root/repo/examples/33_self.lx', '/root/repo/lib/fold.lx'):
        try: ctx += open(q, encoding='utf-8').read() + '\n'
        except OSError: pass
    pre = '-p' in sys.argv and sys.argv[sys.argv.index('-p')+1] or 'zh'
    new, st = flatten(src, prefix=pre, ctx=ctx)
    if '-w' in sys.argv:
        open(p, 'w', encoding='utf-8').write(new)
        print('書いた:', p)
    print('書き座標 %d / 値 %d / ガード %d 本を平らに、場 %d 枚'
          % (st['w'], st['v'], st['g'], st['fields']))
    if st['refused']:
        print('引けなかった %d 本:' % len(st['refused']))
        for ln, k, b in st['refused'][:20]:
            print('  %6d %s  %s' % (ln, k, b))
