#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**この `.lx` は断片に入るか。** —— 焼く前に測る一枚。

`./lattix` は入らない形を **断る**（黙って壊れた符号は出さない）が、
断りは一つしか言わない（`badk` は max なので、一番大きい行番号が勝つ）。
直すには全部の場所が要る。だからここで数える。

測るのは四つ。どれも `test/accept.py` の組で測った際である ——

    書き座標の読みの段数     測ったのは 5 段まで
    値・ガードの読みの段数   測ったのは 6 段まで
    ガードの辺の式           置けない（`if k <= tlen[t] - 1` は断られる）
    足してから掛ける形       `a + b * c` は焼くと `(a+b)*c`（断られる）

使い方:  python3 work/fits.py front.lx run.lx …
"""
import re, sys

IDN = r'[A-Za-z_][A-Za-z_0-9]*'
WMAX, VMAX = 5, 6          # **測った所まで**（気づき44。超えるなら先に測る）


def match_bracket(s, i):
    d = 0
    for j in range(i, len(s)):
        if s[j] == '[': d += 1
        elif s[j] == ']':
            d -= 1
            if d == 0: return j
    return -1


def logical_rules(src):
    """継続行を畳んで論理規則にする。(開始行, 本文) の列。"""
    out = []; cur = None; ln0 = 0
    for i, l in enumerate(src.splitlines(), 1):
        s = l.split('#')[0].strip()
        if cur is not None and (s.startswith('for ') or s.startswith('if ')):
            cur += ' ' + s; continue
        if cur is not None: out.append((ln0, cur)); cur = None
        if '<-' in s: cur = s; ln0 = i
    if cur is not None: out.append((ln0, cur))
    return out


def depth(s):
    """読みの段数（`v` は 0、`h[v]` は 1、`g[h[v]]` は 2）"""
    best = 0; i = 0
    while i < len(s):
        m = re.compile(IDN + r'\s*\[').match(s, i)
        if m:
            j = match_bracket(s, m.end() - 1)
            if j < 0: break
            best = max(best, 1 + depth(s[m.end():j])); i = m.end()
        else:
            i += 1
    return best


def outside(s):
    """括弧の中を `@` に潰す（深さ0 だけを見るため）"""
    out = []; i = 0
    while i < len(s):
        if s[i] in '[(':
            d = 0; j = i
            while j < len(s):
                if s[j] in '[(': d += 1
                elif s[j] in '])':
                    d -= 1
                    if d == 0: break
                j += 1
            if j >= len(s): break
            out.append('@'); i = j + 1
        else:
            out.append(s[i]); i += 1
    return ''.join(out)


def parts(body):
    t = re.split(r'\s+(?=for\s|if\s)', body.strip())
    return t[0], t[1:]


def check(path):
    src = open(path, encoding='utf-8').read()
    hit = {'W': [], 'V': [], 'G': [], 'E': [], 'M': []}
    for ln, rule in logical_rules(src):
        if '<-' not in rule: continue
        head, body = rule.split('<-', 1)
        m = re.match(IDN + r'\[', head.strip())
        if m:
            h = head.strip(); j = match_bracket(h, m.end() - 1)
            if j > 0 and depth(h[m.end():j]) > WMAX:
                hit['W'].append((ln, rule))
        val, cls = parts(body)
        if depth(val) > VMAX: hit['V'].append((ln, rule))
        for c in cls:
            if not c.startswith('if'): continue
            if depth(c) > VMAX: hit['G'].append((ln, rule))
            if re.search(r'[+\-*/%]', outside(c[2:])): hit['E'].append((ln, c.strip()))
        # 足してから掛ける（焼いた符号は左から畳む）
        o = outside(val); add = False
        for ch in o:
            if ch in '+-': add = True
            elif ch in '*/%' and add: hit['M'].append((ln, rule)); break
    name = path.split('/')[-1]
    tot = sum(len(v) for v in hit.values())
    print('%-24s %s' % (name, '断片の中' if tot == 0 else '外に %d 箇所' % tot))
    for k, why in (('W', '書き座標が %d 段より深い' % WMAX),
                   ('V', '値が %d 段より深い' % VMAX),
                   ('G', 'ガードが %d 段より深い' % VMAX),
                   ('E', 'ガードの辺が式'),
                   ('M', '足してから掛ける')):
        if hit[k]:
            print('   %-22s %4d 本   例 %d: %s' % (why, len(hit[k]), hit[k][0][0],
                                                  str(hit[k][0][1])[:70]))
    return tot


if __name__ == '__main__':
    n = 0
    for p in sys.argv[1:] or ['/root/repo/front.lx']:
        n += check(p)
    sys.exit(1 if n else 0)
