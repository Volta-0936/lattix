#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lattix v0.2 — a coordinate-lattice program kernel.

    Von Neumann made sequence the substrate.
    Lattix makes it a derived quantity that the compiler minimises.

What changed from v0.1 (Koshi)
------------------------------
* `seal` is GONE from the surface language. Nobody writes ordering any more.
  The compiler derives the provably-minimal stratification (SCC condensation
  + weighted longest path) and reports the sequential depth it achieved.
  Recursion through a non-monotone dependency is now an *impossibility
  report*, not a missing annotation.
* Non-idempotent aggregation recovered: `sum` is a provenance-keyed lattice,
  so + becomes commutative/associative/idempotent again.
* Semi-naive worklist engine driven by a read-key index.
* Termination certificates (lattice height / non-negative recursive delta).
* Content-addressed normal form: program identity is a hash of its meaning,
  not its text. Variable names and statement order are semantically invisible.

No dependencies. Python 3.8+.
"""

from __future__ import annotations
import sys, os, random, argparse, itertools, hashlib, json, time
from collections import defaultdict, deque, Counter

INF = float('inf')
NEGINF = float('-inf')
VERSION = "1.8"


class LattixError(Exception):
    pass


# 内容アドレスは **32ビットに収まる掛け算だけ**で書ける必要がある ——
# 128ビットを持たない機械（と、Lattix 自身）でも計算できるように。
# だから 28 ビットの法を二つ使い、二つの折り込みを並べて一つの番地にする。
#
# **なぜ 28 で、31 ではないのか。** 内容アドレスを座標にする場は、番地の幅
# ぶんの帯を一本ずつ占める。31+31 = 62 ビットだと帯が四本で 2^64 を超え、
# 焼いた側で升の番号が i64 に入らない（⊤ の番兵 INT64_MAX とも衝突する）。
# 28+28 = 56 ビットなら帯は 128 本まで並ぶ。**上限は数えてから書く**（気づき35）。
CTOR_M1 = 268435399             # 2^28 に近い素数
CTOR_M2 = 268435367             # 同上（別の素数）
CTOR_K1 = 1000003
CTOR_K2 = 1000033
CTOR_BITS = 56


def _fold(b, m, k, h=0):
    for x in b:
        h = (h * k + x + 1) % m
    return h


def _enc(a, m, k):
    if isinstance(a, bool):  return 3 * int(a) + 2
    if isinstance(a, str):   return 3 * _fold(a.encode(), m, k) + 1
    if isinstance(a, int):   return 3 * (a % m)
    return 3 * _fold(repr(a).encode(), m, k) + 1


def ctor_id(name, args):
    """構成された値の名前は、それを作った内容そのものである。

    `malloc` も `new` も gensym も「いつ確保したか」に依存する。
    それは von Neumann の時間軸が『新しい値』という言葉に紛れ込んだものだ。
    順序・時間・空間・信頼のどれにも依存しない命名は一つしかない —— 内容アドレス。

    結果として:
      * 同じものを二度作っても同じ名前 → 構成が冪等（join になる）
      * 別マシンで独立に作っても同じ名前 → 合流でプロトコル無しに共有される
      * 検査器が名前を再計算できる      → 構成も証明の対象になる
    これは hash-consing（Ershov 1958）だが、最適化ではなく *構成の定義* である。

    **符号化は整数の算術だけで書けなければならない。** 以前は SHA-256 の
    先頭 56 ビットだった。正準ではあったが、それを計算できるのは SHA-256 を
    持つ実装だけである —— つまり **Lattix 自身には計算できなかった**。
    処理系が自分の言語で書かれることを目指す以上、これは穴である。

    いまは固定の乗数と法による多項式を **二本**（法 2^31-1 と 2^31-99）折り、
    並べて 62 ビットの番地にする。掛け算は 31×31 ビットなので 64 ビットに収まり、
    128 ビット整数を持たない機械でも、Lattix の規則としても書ける。

      h ← 名前のバイトの折り込み
      h ← (h·K + 引数の数 + 1) mod M
      各引数 a:  h ← (h·K + enc(a)) mod M
        enc(整数 v) = 3(v mod M)  enc(文字列 s) = 3·折り込み(s)+1  enc(真偽 b) = 3b+2
      番地 = h1 · M2 + h2
    """
    out = []
    for m, k in ((CTOR_M1, CTOR_K1), (CTOR_M2, CTOR_K2)):
        h = _fold(name.encode(), m, k)
        h = (h * k + len(args) + 1) % m
        for a in args:
            h = (h * k + _enc(a, m, k)) % m
        out.append(h)
    return out[0] * CTOR_M2 + out[1]


# ==========================================================================
# 1. Lattices
# ==========================================================================

class _Top:
    __slots__ = ()
    def __repr__(self): return "TOP"
    def __eq__(self, o): return isinstance(o, _Top)
    def __hash__(self): return hash("LATTIX_TOP")

TOP = _Top()


class _FourV:
    """Belnap (1977) four-valued truth. The lattice is the KNOWLEDGE order

              TOP  (both / contradictory)
             /   \
            T     F
             \   /
              BOT (neither / unknown)

    and the crucial property is that NEGATION IS MONOTONE on it:
        ~BOT=BOT   ~T=F   ~F=T   ~TOP=TOP
    Swapping the two incomparable middle elements preserves the order.
    On two-valued booleans `not` is anti-monotone and therefore costs a
    stratum; here it costs nothing.  Recursion through negation stops being
    ill-posed and simply lands on the Kripke-Kleene / Fitting fixpoint."""
    __slots__ = ('v',)
    def __init__(self, v): self.v = v
    def __repr__(self): return "T4" if self.v else "F4"
    def __eq__(self, o): return isinstance(o, _FourV) and o.v == self.v
    def __hash__(self): return hash(("FOURV", self.v))

FTRUE, FFALSE = _FourV(True), _FourV(False)


def _fnot(v):
    if v is None or isinstance(v, _Top): return v      # BOT and TOP are fixed
    if isinstance(v, _FourV): return FFALSE if v.v else FTRUE
    return FFALSE if v else FTRUE


def _flat_join(a, b):
    if a is None: return b
    if b is None: return a
    if isinstance(a, _Top) or isinstance(b, _Top): return TOP
    return a if a == b else TOP


def _sum_join(a, b):
    # a, b : dict[provenance -> contributed value]
    if not a: return b
    if not b: return a
    out = dict(a)
    for k, v in b.items():
        if k in out and out[k] != v:
            out[k] = TOP
        else:
            out[k] = v
    return out


class Lattice:
    def __init__(self, name, bot, join, *, finite_height, needs_seal=False,
                 observe=None, sense='NONE', geq=None):
        self.name = name
        self.bot = bot
        self.join = join
        # `sense` = how the OBSERVED value moves as the store climbs the
        # lattice.  This is what makes threshold tests cost nothing.
        #   UP     observed value only increases   (max, set, or, sum, count)
        #   DOWN   observed value only decreases   (min, and)
        #   FLAT   incomparable values; every bottom-strict predicate is
        #          monotone because there is no ascending chain to violate
        #   BELNAP monotone under negation too
        self.sense = sense
        self.finite_height = finite_height   # height bounded by input size alone?
        self.needs_seal = needs_seal         # any read is non-monotone?
        self._observe = observe
        # `geq(a, c)` = "a carries at least the information c", i.e. a ⊒ c.
        # zoo.py proved that the monotone predicates on a lattice are exactly
        # its up-sets, and every up-set is a union of principal ones ⊒c.
        # So THIS ONE TEST generates every stratum-free guard, on every
        # lattice.  The whole hand-derived polarity table is its shadow.
        self._geq = geq

    def geq(self, a, c):
        if self._geq is None: return False
        try: return bool(self._geq(a, c))
        except TypeError: return False

    def is_bot(self, v):
        if isinstance(v, _Top): return False
        if isinstance(v, dict):
            if len(v) == 0: return True
            # **⊥ が 0 の束では、0 は ⊥ である。** 寄与が届いていても、
            # 観測される値が 0 なら束の元としては ⊥ と同じものである ——
            # 「届いたか」は履歴であって値ではない。焼いた符号は升に 0 を
            # 置くだけなので二つを区別できず、ここで区別すると
            # **同じ源が二つの答えを持つ**（`s[i] <- i` の i=0）。
            if self.name in ('sum', 'count'):
                try: return self.observe(v) == 0
                except Exception: return False
            return False
        try: return v == self.bot
        except Exception: return False

    def observe(self, v):
        return self._observe(v) if self._observe else v


LATTICES = {
    'min':  Lattice('min',  INF,   lambda a, b: a if a <= b else b,
                    finite_height=False, sense='DOWN', geq=lambda a, c: a <= c),
    'max':  Lattice('max',  NEGINF, lambda a, b: a if a >= b else b,
                    finite_height=False, sense='UP', geq=lambda a, c: a >= c),
    'set':  Lattice('set',  frozenset(), lambda a, b: a | b,
                    finite_height=True, sense='UP', geq=lambda a, c: a >= c),
    'or':   Lattice('or',   False, lambda a, b: bool(a) or bool(b),
                    finite_height=True, sense='UP',
                    geq=lambda a, c: bool(a) >= bool(c)),
    'and':  Lattice('and',  True,  lambda a, b: bool(a) and bool(b),
                    finite_height=True, sense='DOWN',
                    geq=lambda a, c: bool(a) <= bool(c)),
    'flat': Lattice('flat', None,  _flat_join, finite_height=True, sense='FLAT', geq=lambda a, c: isinstance(a, _Top) or (a is not None and a == c)),
    # Belnap: same carrier as flat, but negation is a lattice morphism.
    'fourv': Lattice('fourv', None, _flat_join, finite_height=True, sense='BELNAP', geq=lambda a, c: isinstance(a, _Top) or (a is not None and a == c)),
    # provenance-keyed: contributions are keyed by the rule instance that made
    # them, so re-contributing is idempotent and + becomes a lattice again.
    # `needs_seal` is gone: an aggregate read is monotone exactly when the
    # contributions are certified sign-definite.  See field_senses().
    'sum':  Lattice('sum', {}, _sum_join, finite_height=True,
                    observe=lambda d: TOP if any(isinstance(x, _Top) for x in d.values())
                                      else sum(d.values()), sense='NONE', geq=lambda a, c: a >= c),
    'count': Lattice('count', {}, _sum_join, finite_height=True,
                     observe=lambda d: len(d), sense='UP', geq=lambda a, c: a >= c),
    'bag':  Lattice('bag', {}, _sum_join, finite_height=True,
                    observe=lambda d: tuple(sorted((str(v) for v in d.values()))),
                    sense='NONE'),
}


# ==========================================================================
# 2. Surface syntax  (a transport format; the normal form is the real program)
# ==========================================================================

KEYWORDS = {'table', 'field', 'print', 'for', 'in', 'if',
            'not', 'range', 'min', 'max', 'true', 'false', 'seal', 'is',
            'component', 'end', 'use', 'as', 'depth', 'include', 'local',
            'source', 'emit', 'from', 'io', 'budget', 'constructor', 'bound',
            'render'}
RANGE_CAP = 1 << 22   # 座標の区間の上限。有限の資源であることを宣言する
FIRE_BUDGET = 4000000   # 昇鎖の見張り。構造の限界ではなく暴走の検出
SYMS = ['<-', '<=', '>=', '==', '!=', '..', '[', ']', '(', ')', '{', '}',
        ',', ':', '+', '-', '*', '/', '%', '<', '>', '=']


def tokenize(line, lineno):
    toks, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if c in ' \t\r\n': i += 1; continue
        if c == '#': break
        if c == '"':
            j = line.find('"', i + 1)
            if j < 0: raise LattixError(f"line {lineno}: unterminated string")
            toks.append(('STR', line[i + 1:j])); i = j + 1; continue
        hit = next((s for s in SYMS if line.startswith(s, i)), None)
        if hit:
            toks.append(('SYM', hit)); i += len(hit); continue
        if c.isdigit():
            j = i
            while j < n and line[j].isdigit(): j += 1
            toks.append(('INT', int(line[i:j]))); i = j; continue
        if c.isalpha() or c == '_':
            j = i
            while j < n and (line[j].isalnum() or line[j] == '_'): j += 1
            w = line[i:j]
            toks.append(('KW' if w in KEYWORDS else 'ID', w)); i = j; continue
        raise LattixError(f"line {lineno}: unexpected character {c!r}")
    return toks


class Rule:
    __slots__ = ('target', 'keys', 'value', 'sources', 'guards', 'lineno',
                 'reads', 'mono_reads', 'nonmono_reads', 'id', 'stratum', 'scc')
    def __init__(self, target, keys, value, sources, guards, lineno):
        self.target, self.keys, self.value = target, keys, value
        self.sources, self.guards, self.lineno = sources, guards, lineno
        self.reads = set(); self.mono_reads = set(); self.nonmono_reads = set()
        self.id = None; self.stratum = 0; self.scc = 0
    def __repr__(self):
        return f"<r{self.id} L{self.lineno} -> {self.target}>"


class Parser:
    def __init__(self, toks, lineno, ctors=()):
        self.t, self.i, self.lineno = toks, 0, lineno
        self.ctors = ctors
    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)
    def eat(self, kind=None, val=None):
        if self.i >= len(self.t):
            raise LattixError(f"line {self.lineno}: unexpected end of statement")
        k, v = self.t[self.i]
        if (kind and k != kind) or (val is not None and v != val):
            raise LattixError(f"line {self.lineno}: expected {val or kind}, got {v!r}")
        self.i += 1
        return v
    def at(self, kind, val=None):
        k, v = self.peek()
        return k == kind and (val is None or v == val)
    def done(self):
        return self.i >= len(self.t)

    def expr(self):
        left = self.sum_()
        k, v = self.peek()
        if k == 'KW' and v == 'is':          # a ⊒ c : monotone on EVERY lattice
            self.eat()
            return ('geq', left, self.sum_())
        if k == 'SYM' and v in ('<', '>', '<=', '>=', '==', '!='):
            self.eat()
            return ('cmp', v, left, self.sum_())
        return left

    def sum_(self):
        e = self.term()
        while self.at('SYM', '+') or self.at('SYM', '-'):
            op = self.eat(); e = ('bin', op, e, self.term())
        return e

    def term(self):
        e = self.atom()
        while self.at('SYM', '*') or self.at('SYM', '/') or self.at('SYM', '%'):
            op = self.eat(); e = ('bin', op, e, self.atom())
        return e

    def atom(self):
        k, v = self.peek()
        if k == 'INT': self.eat(); return ('int', v)
        if k == 'STR': self.eat(); return ('str', v)
        if k == 'KW' and v in ('true', 'false'):
            self.eat(); return ('bool', v == 'true')
        if k == 'KW' and v == 'not':
            self.eat(); return ('not', self.atom())
        if k == 'KW' and v in ('min', 'max'):
            self.eat(); self.eat('SYM', '(')
            a = self.expr(); self.eat('SYM', ',')
            b = self.expr(); self.eat('SYM', ')')
            return ('fn', v, a, b)
        if k == 'SYM' and v == '(':
            self.eat(); e = self.expr(); self.eat('SYM', ')'); return e
        if k == 'SYM' and v == '{':
            self.eat(); items = []
            if not self.at('SYM', '}'):
                items.append(self.expr())
                while self.at('SYM', ','):
                    self.eat(); items.append(self.expr())
            self.eat('SYM', '}')
            return ('set', items)
        if k == 'SYM' and v == '-':
            self.eat(); return ('bin', '-', ('int', 0), self.atom())
        if k == 'ID':
            name = self.eat()
            if name in self.ctors and self.at('SYM', '('):
                self.eat(); args = []
                if not self.at('SYM', ')'):
                    args.append(self.expr())
                    while self.at('SYM', ','):
                        self.eat(); args.append(self.expr())
                self.eat('SYM', ')')
                if len(args) != len(self.ctors[name][0]):
                    raise LattixError(f"line {self.lineno}: {name} takes "
                                      f"{len(self.ctors[name][0])} argument(s)")
                return ('ctor', name, args)
            if self.at('SYM', '['):
                self.eat(); idx = []
                if not self.at('SYM', ']'):
                    idx.append(self.expr())
                    while self.at('SYM', ','):
                        self.eat(); idx.append(self.expr())
                self.eat('SYM', ']')
                return ('fref', name, idx)
            return ('var', name)
        raise LattixError(f"line {self.lineno}: cannot parse expression near {v!r}")


class Program:
    def __init__(self):
        self.tables = {}
        self.fields = {}
        self.field_line = {}
        self.field_bound = {}
        self.rules = []
        self.prints = []          # field names, order irrelevant to semantics
        self.renders = []         # 座標順に文字として並べて出す場（下の注を読む）
        self.ctors = {}           # name -> (arg field names, bound)
        self.sources = {}         # field -> channel it is fed from
        self.channels = []        # channels emitted to, in decl order
        self.components = {}      # name -> Component
        self.uses = []            # (name, args, prefix, lineno)
        self.sense = {}
        self.conservative = False
        self.strata = []          # list[list[Rule]] filled by stratify()
        self._axis = {}           # field -> 成層の時計が立つ軸（_axis_unroll が刻む）
        self.critical_path = []
        self.certificates = {}
        self.io = 0
        self.budgets = []      # (kind, limit, lineno)


class Component:
    """A reusable rule set with a DEPTH SIGNATURE.

    A library is only useful if using it does not silently destroy the
    guarantees you came for.  So a component's interface is not just
    "what fields go in and out" but "how much sequential order using me
    costs you".  The compiler verifies the declared depth against the
    component's own stratification, and the caller's depth is recomputed
    over the expanded program -- composition cannot hide order."""
    __slots__ = ('name', 'params', 'outs', 'locals_', 'body', 'decl_depth',
                 'decl_io', 'lineno', 'depth', 'io')
    def __init__(self, name, params, outs, lineno):
        self.name, self.params, self.outs, self.lineno = name, params, outs, lineno
        self.locals_ = {}      # field -> lattice name
        self.body = []         # raw logical lines
        self.decl_depth = None; self.decl_io = None
        self.depth = None; self.io = None


def _subst(e, fmap, vmap):
    k = e[0]
    if k == 'ctor':
        return ('ctor', e[1], [_subst(x, fmap, vmap) for x in e[2]])
    if k == 'var':
        return vmap.get(e[1], e)
    if k == 'fref':
        return ('fref', fmap.get(e[1], e[1]), [_subst(x, fmap, vmap) for x in e[2]])
    if k in ('bin', 'cmp', 'fn'):
        return (k, e[1], _subst(e[2], fmap, vmap), _subst(e[3], fmap, vmap))
    if k == 'geq':
        return ('geq', _subst(e[1], fmap, vmap), _subst(e[2], fmap, vmap))
    if k in ('not', 'bnot'):
        return (k, _subst(e[1], fmap, vmap))
    if k == 'set':
        return ('set', [_subst(x, fmap, vmap) for x in e[1]])
    return e


CONT = ('for ', 'if ', 'for(', 'if(')
# **文が終わっていないなら、行は終わっていない。** 人は読める形に改行する ——
# `table seed =` で改行し、行の途中で括弧を開いたまま次の行へ行く。
# 「コンマで終わったら続き」だけでは、その形が玄関で弾かれていた。
OPEN = ('=', ',', '<-', '+', '-', '*', '/', '%', '(')


def _strip_comment(raw):
    """`#` から行末まで。ただし **文字列の中の `#` は文字である**。"""
    out = []; instr = False; i = 0
    while i < len(raw):
        ch = raw[i]
        if instr:
            out.append(ch)
            if ch == '\\' and i + 1 < len(raw):
                out.append(raw[i + 1]); i += 2; continue
            if ch == '"': instr = False
        else:
            if ch == '#': break
            out.append(ch)
            if ch == '"': instr = True
        i += 1
    return ''.join(out).rstrip()


def _open_parens(code):
    """閉じていない `(` の数（文字列の中は数えない）。"""
    n = 0; instr = False; i = 0
    while i < len(code):
        ch = code[i]
        if instr:
            if ch == '\\': i += 2; continue
            if ch == '"': instr = False
        else:
            if ch == '"': instr = True
            elif ch == '(': n += 1
            elif ch == ')': n -= 1
        i += 1
    return n


def _logical_lines(text):
    """継続行: 文がまだ閉じていない（末尾が `=` `,` `<-` 演算子、または
    括弧が開いたまま）か、次の行が for / if で始まるとき。"""
    pend, start = None, None
    for lineno, raw in enumerate(text.splitlines(), 1):
        code = _strip_comment(raw)
        if not code.strip():
            continue
        t = code.strip()
        if pend is not None and (pend.endswith(OPEN) or _open_parens(pend) > 0
                                 or t.startswith(CONT)):
            pend += " " + t
            continue
        if pend is not None:
            yield start, pend
        pend, start = t, lineno
    if pend is not None:
        yield start, pend


def _lit(p):
    k, v = p.peek()
    if k == 'SYM' and v == '-':          # 表は ℤ を持てる。負の重みは普通にある。
        p.eat(); return -p.eat('INT')
    if k in ('INT', 'STR', 'ID'): return p.eat()
    raise LattixError(f"line {p.lineno}: bad table literal {v!r}")


def _expand_includes(text, base):
    out = []
    for line in text.splitlines():
        t = line.strip()
        if t.startswith('include '):
            path = t.split(None, 1)[1].strip().strip('"')
            p = path if os.path.isabs(path) else os.path.join(base or '.', path)
            if not os.path.exists(p):
                # 取り込み元の場所が分からない呼び出し（テストなど）でも解けるように、
                # 配布の中の決まった場所を順に見る。**探す場所は宣言してある。**
                here = os.path.dirname(os.path.abspath(__file__))
                for d in (here, os.path.join(here, 'examples'),
                          os.path.join(here, 'lib')):
                    if os.path.exists(os.path.join(d, path)):
                        p = os.path.join(d, path); break
            out.append(f"# --- included from {path} ---")
            out.append(_expand_includes(open(p, encoding='utf-8').read(),
                                        os.path.dirname(p)))
        else:
            out.append(line)
    return "\n".join(out)


def parse(text, base=None):
    if 'include ' in text:
        text = _expand_includes(text, base)
    prog = Program()
    cur = None                       # component being collected
    for lineno, raw in _logical_lines(text):
        head = raw.split()[:1]
        if cur is not None:
            if head == ['end']:
                prog.components[cur.name] = cur; cur = None
            else:
                cur.body.append((lineno, raw))
            continue
        if head == ['component']:
            cur = _parse_component_head(raw, lineno); continue
        if head == ['use']:
            prog.uses.append(_parse_use(raw, lineno)); continue
        toks = tokenize(raw, lineno)
        if not toks: continue
        p = Parser(toks, lineno, prog.ctors)
        k, v = p.peek()

        if k == 'KW' and v == 'constructor':
            p.eat(); nm = p.eat('ID'); p.eat('SYM', '(')
            fs = [p.eat('ID')]
            while p.at('SYM', ','):
                p.eat(); fs.append(p.eat('ID'))
            p.eat('SYM', ')')
            bd = 64
            if p.at('KW', 'bound'):
                p.eat(); bd = p.eat('INT')
            prog.ctors[nm] = (fs, bd)
            for f in fs:
                fn = f"{nm}_{f}"
                if fn not in prog.fields:
                    prog.fields[fn] = LATTICES['flat']; prog.field_line[fn] = lineno
            if '_size' not in prog.fields:
                prog.fields['_size'] = LATTICES['max']; prog.field_line['_size'] = lineno
            continue

        if k == 'KW' and v == 'budget':
            p.eat()
            kind = p.eat()
            if kind not in ('depth', 'io', 'top'):
                raise LattixError(f"line {lineno}: budget must be `depth`, `io` "
                                  f"or `top`")
            p.eat('SYM', '<='); prog.budgets.append((kind, p.eat('INT'), lineno))
            continue

        if k == 'KW' and v == 'source':
            # 外界からの入力は「これまでに観測したもの」であり、単調に育つ。
            # だから普通の場と同じ扱いでよい。層0に置かれる — ただしその
            # チャネルへ emit する規則があるなら、それは往復であって層が上がる。
            p.eat(); name = p.eat('ID'); p.eat('SYM', ':'); lat = p.eat()
            if lat not in LATTICES:
                raise LattixError(f"line {lineno}: unknown lattice {lat!r}")
            p.eat('KW', 'from'); ch = p.eat('STR')
            if name in prog.fields:
                raise LattixError(f"line {lineno}: field {name!r} redeclared")
            prog.fields[name] = LATTICES[lat]; prog.field_line[name] = lineno
            prog.sources[name] = ch
            continue

        if k == 'KW' and v == 'emit':
            # 出力は「出したものの集合」という場である。効果はその *差分* を
            # 実体化することなので、何度実行しても、どの順序でも、何レプリカでも
            # 重複しない。exactly-once が構造から出る。
            p.eat(); ch = p.eat('STR')
            fld = 'emit_' + ''.join(c if c.isalnum() else '_' for c in ch)
            if fld not in prog.fields:
                prog.fields[fld] = LATTICES['set']; prog.field_line[fld] = lineno
                prog.channels.append((ch, fld))
            p.eat('SYM', '<-')
            val = p.expr()
            sources, guards = [], []
            while not p.done():
                if p.at('KW', 'for'):
                    sources.append(_for_clause(p, lineno))
                elif p.at('KW', 'if'):
                    p.eat(); guards.append(p.expr())
                else:
                    raise LattixError(f"line {lineno}: expected 'for' or 'if'")
            r = Rule(fld, [], ('set', [val]), sources, guards, lineno)
            r.id = len(prog.rules); prog.rules.append(r)
            continue

        if k == 'KW' and v == 'seal':
            raise LattixError(
                f"line {lineno}: `seal` no longer exists in Lattix v{VERSION}.\n"
                f"    Ordering is derived, not written. Delete this line;\n"
                f"    the compiler will place the barrier at the provably\n"
                f"    earliest sound point and tell you the depth it achieved.")

        if k == 'KW' and v == 'table':
            p.eat(); name = p.eat('ID'); p.eat('SYM', '=')
            if p.at('KW', 'range'):
                p.eat(); p.eat('SYM', '(')
                lo = p.eat('INT'); p.eat('SYM', ','); hi = p.eat('INT'); p.eat('SYM', ')')
                prog.tables[name] = [(x,) for x in range(lo, hi)]
            else:
                rows = []
                while True:
                    p.eat('SYM', '(')
                    row = []
                    if not p.at('SYM', ')'):
                        row.append(_lit(p))
                        while p.at('SYM', ','):
                            p.eat(); row.append(_lit(p))
                    p.eat('SYM', ')')
                    rows.append(tuple(row))
                    if p.at('SYM', ','):
                        p.eat(); continue
                    break
                prog.tables[name] = rows
            continue

        if k == 'KW' and v == 'field':
            p.eat(); name = p.eat('ID'); p.eat('SYM', ':')
            lat = p.eat()
            if lat not in LATTICES:
                raise LattixError(f"line {lineno}: unknown lattice {lat!r} "
                                  f"(have: {', '.join(sorted(LATTICES))})")
            if name in prog.fields:
                raise LattixError(f"line {lineno}: field {name!r} redeclared")
            prog.fields[name] = LATTICES[lat]
            prog.field_line[name] = lineno
            # 座標の広さは **宣言できる**（有限の資源は宣言し、超えたら言う）。
            # 書かなければ処理系が data から決める。焼くときは必ず要る ——
            # 密な配列に落とすとき、広さは実行時ではなく **記述** が言う。
            if p.at('KW') and p.peek()[1] == 'bound':
                p.eat(); b = [int(p.eat('INT'))]
                while p.at('INT'):          # 次元ごとに書ける（`bound 8192 16`）
                    b.append(int(p.eat('INT')))
                prog.field_bound[name] = b[0] if len(b) == 1 else tuple(b)
            continue

        if k == 'KW' and v == 'print':
            p.eat(); prog.prints.append(p.eat('ID')); continue

        # ── render ────────────────────────────────────────────────────
        # 文字列型は要らなかった。**列は座標に住んでいて、時間には住んでいない。**
        # 場 f が (位置) -> 文字コード なら、それを座標順に並べたものが文字列である。
        # 並び順は実行順序ではなく座標が決めるので、これは効果ではなく *描画* である。
        # （これが無いとコード生成の出力が書けない ——「Python から抜ける」の最後の一点）
        if k == 'KW' and v == 'render':
            p.eat(); prog.renders.append(p.eat('ID')); continue

        r = _parse_rule(p, lineno)
        r.id = len(prog.rules)
        prog.rules.append(r)
    if cur is not None:
        raise LattixError(f"component {cur.name!r} is missing `end`")
    _desugar_ctors(prog)
    for u in prog.uses:
        _instantiate(prog, u)
    return prog


def _find_ctors(e, out):
    k = e[0]
    if k == 'ctor':
        out.append(e)
        for x in e[2]: _find_ctors(x, out)
    elif k == 'fref':
        for x in e[2]: _find_ctors(x, out)
    elif k in ('bin', 'cmp', 'fn'):
        _find_ctors(e[2], out); _find_ctors(e[3], out)
    elif k == 'geq':
        _find_ctors(e[1], out); _find_ctors(e[2], out)
    elif k in ('not', 'bnot'):
        _find_ctors(e[1], out)
    elif k == 'set':
        for x in e[1]: _find_ctors(x, out)
    return out


def _desugar_ctors(prog):
    """構成子の出現ごとに、引数場と大きさ場への寄与規則を生成する。

    構成は副作用ではなく寄与である。だから冪等・可換であり、
    成層器も検査器も証明書も、そのまま構成に効く。"""
    extra = []
    for r in list(prog.rules):
        seen = []
        for e in r.keys + [r.value] + r.guards:
            _find_ctors(e, seen)
        for c in seen:
            nm, args = c[1], c[2]
            fs, _bd = prog.ctors[nm]
            for f, a in zip(fs, args):
                extra.append(Rule(f"{nm}_{f}", [c], a, r.sources, r.guards, r.lineno))
            extra.append(Rule('_size', [c], ('int', 1), r.sources, r.guards, r.lineno))
            for a in args:
                # 引数が構成された節点なら深さが伝播する。葉なら _size は ⊥ で
                # 寄与が消えるだけ。だから場合分けが要らない。
                extra.append(Rule('_size', [c],
                                  ('bin', '+', ('fref', '_size', [a]), ('int', 1)),
                                  r.sources, r.guards, r.lineno))
    for e in extra:
        e.id = len(prog.rules); prog.rules.append(e)


def _parse_rule(p, lineno):
    target = p.eat('ID')
    p.eat('SYM', '[')
    keys = []
    if not p.at('SYM', ']'):
        keys.append(p.expr())
        while p.at('SYM', ','):
            p.eat(); keys.append(p.expr())
    p.eat('SYM', ']')
    p.eat('SYM', '<-')
    value = p.expr()
    sources, guards = [], []
    while not p.done():
        if p.at('KW', 'for'):
            # **座標の空間そのものを回す。** 表は地上データだが、区間は *値* で
            # 決まる —— 上端が育てば規則実例が増える。増えるだけなので単調。
            # ノイマンの普遍構成子が「周りの格子」を使ったのと同じで、
            # 供給は列挙されたものではなく **空間** である。
            sources.append(_for_clause(p, lineno))
        elif p.at('KW', 'if'):
            p.eat(); guards.append(p.expr())
        else:
            raise LattixError(f"line {lineno}: expected 'for' or 'if', "
                              f"got {p.peek()[1]!r}")
    return Rule(target, keys, value, sources, guards, lineno)


def _for_clause(p, lineno):
    """`for (v...) in 表` か `for (v) in a .. b`。**一箇所にしか書かない。**
    emit と component が別実装だったので、区間が規則でしか使えなかった。"""
    p.eat(); p.eat('SYM', '(')
    vs = [p.eat('ID')]
    while p.at('SYM', ','):
        p.eat(); vs.append(p.eat('ID'))
    p.eat('SYM', ')'); p.eat('KW', 'in')
    if p.at('ID') and not (p.peek(1)[0] == 'SYM' and p.peek(1)[1] == '..'):
        return (vs, p.eat('ID'))
    if len(vs) != 1:
        raise LattixError(f"line {lineno}: a range binds one variable")
    lo = p.expr(); p.eat('SYM', '..'); hi = p.expr()
    return (vs, ('..', lo, hi))


def _parse_component_head(raw, lineno):
    toks = tokenize(raw, lineno)
    p = Parser(toks, lineno)
    p.eat('KW', 'component')
    name = p.eat('ID')
    p.eat('SYM', '(')
    params = []
    if not p.at('SYM', ')'):
        params.append(p.eat('ID'))
        while p.at('SYM', ','):
            p.eat(); params.append(p.eat('ID'))
    p.eat('SYM', ')')
    outs = []
    if p.at('SYM', '-') or p.at('SYM', '>'):
        while p.at('SYM', '-') or p.at('SYM', '>'):
            p.eat()
        while True:
            f = p.eat('ID'); p.eat('SYM', ':'); lat = p.eat()
            if lat not in LATTICES:
                raise LattixError(f"line {lineno}: unknown lattice {lat!r}")
            outs.append((f, lat))
            if p.at('SYM', ','): p.eat(); continue
            break
    c = Component(name, params, outs, lineno)
    while p.at('KW', 'depth') or p.at('KW', 'io'):
        which = p.eat()
        if which == 'depth': c.decl_depth = p.eat('INT')
        else:                c.decl_io = p.eat('INT')
    return c


def _parse_use(raw, lineno):
    toks = tokenize(raw, lineno)
    p = Parser(toks, lineno)
    p.eat('KW', 'use')
    name = p.eat('ID')
    p.eat('SYM', '(')
    args = []
    if not p.at('SYM', ')'):
        args.append(_use_arg(p))
        while p.at('SYM', ','):
            p.eat(); args.append(_use_arg(p))
    p.eat('SYM', ')')
    p.eat('KW', 'as')
    return (name, args, p.eat('ID'), lineno)


def _use_arg(p):
    k, v = p.peek()
    if k == 'INT': return ('int', p.eat())
    if k == 'STR': return ('str', p.eat())
    return ('name', p.eat('ID'))


def _instantiate(prog, use):
    name, args, pfx, lineno = use
    c = prog.components.get(name)
    if c is None:
        raise LattixError(f"line {lineno}: unknown component {name!r}")
    if len(args) != len(c.params):
        raise LattixError(f"line {lineno}: {name} takes {len(c.params)} "
                          f"parameter(s), got {len(args)}")
    # 1) stratify the component ALONE to obtain its true depth signature
    sub = Program()
    sub.tables = prog.tables
    sub.sources, sub.channels = {}, []
    tmap, vmap = {}, {}
    for pname, (kind, val) in zip(c.params, args):
        if kind == 'name': tmap[pname] = val
        else:              vmap[pname] = (kind, val)
    fmap = {}
    body_rules, body_fields, body_srcs, body_chans = _component_body(c, lineno)
    for f, lat in list(body_fields.items()):
        fmap[f] = f"{pfx}_{f}"
    for f, lat in body_fields.items():
        if fmap[f] in prog.fields:
            raise LattixError(f"line {lineno}: field {fmap[f]!r} already exists")
        prog.fields[fmap[f]] = LATTICES[lat]
        prog.field_line[fmap[f]] = lineno
        sub.fields[f] = LATTICES[lat]
    for ch, fld in body_chans:                 # channels stay global
        if fld not in prog.fields:
            prog.fields[fld] = LATTICES['set']; prog.field_line[fld] = lineno
            prog.channels.append((ch, fld))
        sub.fields.setdefault(fld, LATTICES['set'])
        if (ch, fld) not in sub.channels: sub.channels.append((ch, fld))
    for f, ch in body_srcs.items():
        prog.sources[fmap[f]] = ch
        sub.sources[f] = ch
    for r in body_rules:
        sub.rules.append(_clone(r, {}, tmap, vmap, len(sub.rules)))
    try:
        check(sub); c.depth = stratify(sub); c.io = io_rounds(sub)
    except LattixError as e:
        raise LattixError(f"line {lineno}: component {name!r} does not stratify: {e}")
    if c.decl_io is not None and c.io != c.decl_io:
        raise LattixError(
            f"line {c.lineno}: component {name!r} declares io {c.decl_io} but its "
            f"rules block on the world {c.io} time(s).\n"
            f"    Round-trip count is part of the interface: a library may not "
            f"silently cost its caller more latency than it advertised.")
    if c.decl_depth is not None and c.depth != c.decl_depth:
        raise LattixError(
            f"line {c.lineno}: component {name!r} declares depth {c.decl_depth} "
            f"but its rules stratify to depth {c.depth}.\n"
            f"    A depth signature is part of the interface: a library may not\n"
            f"    silently cost its caller more order than it advertised.")
    # 2) splice the renamed rules into the caller
    for r in body_rules:
        prog.rules.append(_clone(r, fmap, tmap, vmap, len(prog.rules)))


def _component_body(c, lineno):
    """部品の中でも外界を使える。source は部品ごとに名前を付け替えるが、
    チャネルは大域である（同じチャネルへの emit は同じ集合に集まる）。"""
    fields, rules, srcs, chans = {}, [], {}, []
    for ln, raw in c.body:
        toks = tokenize(raw, ln)
        if not toks: continue
        p = Parser(toks, ln)
        k, v = p.peek()
        if k == 'KW' and v in ('field', 'local'):
            p.eat(); f = p.eat('ID'); p.eat('SYM', ':'); lat = p.eat()
            if lat not in LATTICES:
                raise LattixError(f"line {ln}: unknown lattice {lat!r}")
            fields[f] = lat; continue
        if k == 'KW' and v == 'source':
            p.eat(); f = p.eat('ID'); p.eat('SYM', ':'); lat = p.eat()
            if lat not in LATTICES:
                raise LattixError(f"line {ln}: unknown lattice {lat!r}")
            p.eat('KW', 'from'); ch = p.eat('STR')
            fields[f] = lat; srcs[f] = ch; continue
        if k == 'KW' and v == 'emit':
            p.eat(); ch = p.eat('STR')
            fld = 'emit_' + ''.join(x if x.isalnum() else '_' for x in ch)
            chans.append((ch, fld))
            p.eat('SYM', '<-'); val = p.expr()
            ss, gg = [], []
            while not p.done():
                if p.at('KW', 'for'):
                    ss.append(_for_clause(p, ln))
                elif p.at('KW', 'if'):
                    p.eat(); gg.append(p.expr())
                else:
                    raise LattixError(f"line {ln}: expected 'for' or 'if'")
            rules.append(Rule(fld, [], ('set', [val]), ss, gg, ln))
            continue
        rules.append(_parse_rule(p, ln))
    for f, lat in c.outs:
        fields.setdefault(f, lat)
    return rules, fields, srcs, chans


def _clone(r, fmap, tmap, vmap, newid):
    vm = {k: (v[0], v[1]) for k, v in vmap.items()}
    vm = {k: (('int', v[1]) if v[0] == 'int' else ('str', v[1]))
          for k, v in vmap.items()}
    n = Rule(fmap.get(r.target, r.target),
             [_subst(x, fmap, vm) for x in r.keys],
             _subst(r.value, fmap, vm),
             [(vs, tmap.get(src, src) if isinstance(src, str) else src)
              for vs, src in r.sources],
             [_subst(g, fmap, vm) for g in r.guards],
             r.lineno)
    n.id = newid
    return n


# ==========================================================================
# 3. Dependency classification
# ==========================================================================

def _walk(e, fn):
    fn(e)
    k = e[0]
    if k == 'fref':
        for x in e[2]: _walk(x, fn)
    elif k in ('bin', 'cmp', 'fn'):
        _walk(e[2], fn); _walk(e[3], fn)
    elif k == 'geq':
        _walk(e[1], fn); _walk(e[2], fn)
    elif k == 'ctor':
        for x in e[2]: _walk(x, fn)
    elif k in ('not', 'bnot'):
        _walk(e[1], fn)
    elif k == 'set':
        for x in e[1]: _walk(x, fn)


def field_refs(e, out):
    _walk(e, lambda n: out.add(n[1]) if n[0] == 'fref' else None)


FLIP = {'UP': 'DOWN', 'DOWN': 'UP', 'COORD': 'COORD'}


def field_senses(prog):
    """How each field's OBSERVED value moves as the store climbs.

    For aggregates the sense is not a property of the lattice but of the
    program: `sum` only ascends if every contribution is non-negative.  That
    is the *same* sign certificate that licensed Dijkstra scheduling, reused
    here to license threshold tests without a barrier."""
    sense = {}
    contribs = defaultdict(list)
    for r in prog.rules:
        contribs[r.target].append(r)
    for f, lat in prog.fields.items():
        if lat.name in ('sum', 'bag'):
            sense[f] = _sign_sense(prog, contribs.get(f, []))
        else:
            sense[f] = lat.sense
    return sense


def _fires(prog, r):
    """この規則は **一度でも起きるか**。地上で偽と決まるガードだけを見る。
    起きない規則の値の形を問うても意味がない（符号も差分も同じ理屈）。"""
    store = {g: {} for g in prog.fields}
    ground = [g for g in r.guards if not _has_fref(g)]
    if not ground: return True
    try:
        n = 0
        for env in bindings(r, prog, None):
            n += 1
            if n > 200000: return True         # 数えきれない ⇒ 起きるとみなす
            if all(_truthy(ev(g, env, store, prog.fields)) for g in ground):
                return True
    except Exception:
        return True
    return False


def _sign_sense(prog, rules):
    store = {g: {} for g in prog.fields}
    for r in rules:
        refs = set(); field_refs(r.value, refs)
        if refs:
            if not _fires(prog, r): continue    # 起きない寄与に符号は無い
            return 'NONE'                      # value depends on other lattices
        try:
            # 起きない寄与の符号は問わない（`_delta_nonneg` と同じ理由）
            ground = [g for g in r.guards if not _has_fref(g)]
            for env in bindings(r, prog, None):
                if any(not _truthy(ev(g, env, store, prog.fields)) for g in ground):
                    continue
                v = ev(r.value, env, store, prog.fields)
                if not isinstance(v, (int, float)) or v < 0:
                    return 'NONE'
        except Exception:
            return 'NONE'
    return 'UP'


UBOUND = set()      # 前線下界を持てる場（証明書が licence する。下の注を読む）
BOUND = {}          # 実行中の前線下界: 場 -> 未確定セルの最終値の下界
SETTLED = {}        # 場 -> 確定済みのキー集合


SIGNS = None      # いま検査している規則の「負にならない変数」（遅延して数える）


def _nonneg(e, lo):
    """`e` が **lo 以上**だと地上データから証せるか。"""
    if e[0] == 'int': return e[1] >= lo
    if e[0] == 'var' and SIGNS is not None:
        return SIGNS.at_least(e[1], lo)
    return False


class _Signs:
    """規則が回る束縛の上で、各変数が取る最小値。ガードで落ちる束縛は数えない。"""
    def __init__(self, prog, rule):
        self.prog, self.rule, self.lo = prog, rule, None

    CAP = 20000        # 直積を数えるのも資源である。宣言して、超えたら証さない。

    def _rows(self):
        """束縛を数える。源が一つなら表を一度舐めるだけ（打ち切らない）。
        源が二つ以上なら直積になるので、宣言した上限で打ち切って証さない。"""
        r = self.rule
        one = len(r.sources) == 1 and not isinstance(r.sources[0][1], tuple)
        if one:
            vs, src = r.sources[0]
            for row in self.prog.tables.get(src) or []:
                yield dict(zip(vs, row))
            return
        n = 0
        for env in bindings(r, self.prog, None):
            n += 1
            if n > self.CAP: raise TimeoutError()
            yield env

    def at_least(self, name, lo):
        if self.lo is None:
            self.lo = {}; self.any = False
            try:
                store = {g: {} for g in self.prog.fields}
                ground = [g for g in self.rule.guards if not _has_fref(g)]
                for env in self._rows():
                    if any(not _truthy(ev(g, env, store, self.prog.fields))
                           for g in ground):
                        continue
                    self.any = True
                    for k, v in env.items():
                        if not isinstance(v, (int, float)):
                            self.lo[k] = None
                        elif self.lo.get(k, 1 << 62) is not None:
                            self.lo[k] = min(self.lo.get(k, 1 << 62), v)
            except TimeoutError:
                self.lo = {}; self.any = True      # 数えきれない ⇒ 証さない
            except Exception:
                self.lo = {}; self.any = True
        # 一度も起きない規則に符号は無い。空虚に真である。
        if not getattr(self, 'any', True): return True
        v = self.lo.get(name)
        return v is not None and v >= lo


def _flatreq(e, sense, otherwise):
    """flat / fourv の升の読みは単調である（⊥ ⊑ v ⊑ ⊤ の鎖は「育つ」鎖ではない）。
    剰余も、升で割るのも、順序をひっくり返さない —— 動く値ではないからである。"""
    if e[0] == 'fref' and sense.get(e[1]) in ('FLAT', 'BELNAP'):
        return 'UP'
    return otherwise


def classify(e, req, strict, sense, out, detail=None):
    """Mark every field read that sits in a NON-monotone position.

    `req`    the direction this subexpression's value must move for the
             enclosing context to be monotone: UP / DOWN / COORD(=unusable)
    `strict` no `not` has been crossed, so BOT still maps to false

    FLAT / BELNAP cells are LVars: BOT -> v and there they stay.  A read of
    one is therefore monotone wherever it sits -- value, coordinate or
    predicate.  The single escape is TOP, and TOP is a CONFLICT: the answer
    is already reported as ill-posed, so no schedule has to preserve it.
    Negation is the real exception, and it is about BOT, not TOP.

    v0.2 blanket-banned every comparison.  That was correct but crude:
    `dist[v] < k` on a descending lattice and `revenue[c] > k` on an
    ascending one are perfectly monotone and cost no stratum at all."""
    k = e[0]
    if k in ('int', 'str', 'bool', 'var'):
        return
    if k == 'fref':
        # **添字は否定の下でも添字である。** `not f[g[x]]` の `g` は否定されて
        # いない —— 否定されるのは f の値だけである。⊥ の座標は「真に読まれる」
        # ことがなく、ただ寄与を消す。だから `strict` はここで立て直す
        # （`native.botguards` の「添字は否定の下でも要る」と同じ判断）。
        for x in e[2]:
            classify(x, 'COORD', True, sense, out, detail)
        s = sense.get(e[1], 'NONE')
        bad = None
        if req == 'COORD':
            # **flat / fourv の升は LVar である —— 一度決まったら動かない。**
            # ⊥ → v で止まる升の読みは、座標でも述語でも単調である（寄与は
            # 増えるだけで、消えない）。単調でなくなるのは ⊤ を跨ぐときだけで、
            # ⊤ は矛盾であって答えではない —— 処理系がそう報告する。
            # 座標だけ緩めて述語を縛るのは、同じ判断を二つに割ることだった
            # （気づき34: 一度直した判断は、同じ判断を持つ全員を数えてから閉じる）。
            bad = None if (s in ('FLAT', 'BELNAP') and strict) else \
                  "used as a coordinate (its value indexes another field)"
        elif s == 'BELNAP':  bad = None
        elif s == 'FLAT':
            # 否定だけは別である。`not f[…]` は ⊥ で **真**に読まれるので、
            # あとで値が入ると真が偽に変わる。ここは ⊥ の話であって ⊤ の話でない。
            if not strict: bad = "negated, so ⊥ would read as true"
        elif s != req:       bad = f"needs to move {req} here, but a `{s}`-sensed field moves {s}"
        if bad:
            out.add(e[1])
            if detail is not None: detail.append((e[1], bad))
        return
    if k == 'geq':
        # up-set membership: monotone in the tested field on EVERY lattice.
        # The right-hand side must be ground (a moving threshold is not).
        if req == 'UP':
            classify(e[2], 'COORD', strict, sense, out, detail)
            for x in e[1][2]:
                classify(x, 'COORD', strict, sense, out, detail)
        else:
            classify(e[1], 'COORD', strict, sense, out, detail)
            classify(e[2], 'COORD', strict, sense, out, detail)
        return
    if k == 'bnot':                                    # Belnap negation
        classify(e[1], req, strict, sense, out, detail); return
    if k == 'not':
        classify(e[1], FLIP[req], False, sense, out, detail); return
    if k == 'cmp':
        op, a, b = e[1], e[2], e[3]
        # ── 上界による早期解禁 ────────────────────────────────────────
        # `dist[v] > k` は min 束（DOWN）に対する非単調な比較で、いままで層を
        # 一つ食っていた。だが非負デルタの証明書があれば、前線の値 B は
        # **まだ確定していない全セルの最終値の下界** である。つまり B は上界 U で、
        #   B > k  ⟹  そのセルの最終値 > k（真になったら二度と偽にならない）
        # だから待つ必要が無い。**層を消すのは証明書である。**
        # 証明書はスケジューラを選ぶだけのものではなかった。
        if (op in ('>', '>=') and a[0] == 'fref' and b[0] == 'int'
                and a[1] in UBOUND and req != 'COORD' and strict):
            classify(a, 'COORD' if False else 'DOWN', strict, sense, out, detail)
            return
        if op in ('==', '!=') or req == 'COORD':
            classify(a, 'COORD', strict, sense, out, detail)
            classify(b, 'COORD', strict, sense, out, detail); return
        lo = op in ('<', '<=')
        ra, rb = ('DOWN', 'UP') if lo else ('UP', 'DOWN')
        if req == 'DOWN':
            ra, rb = FLIP[ra], FLIP[rb]
        classify(a, ra, strict, sense, out, detail)
        classify(b, rb, strict, sense, out, detail); return
    if k == 'bin':
        op = e[1]
        if op == '+':
            classify(e[2], req, strict, sense, out, detail)
            classify(e[3], req, strict, sense, out, detail)
        elif op == '-':
            classify(e[2], req, strict, sense, out, detail)
            classify(e[3], FLIP[req], strict, sense, out, detail)
        elif op == '*':
            # **符号は宣言されている。** 掛ける相手が literal でなくても、
            # 表の列なら「その規則が回る束縛の上で負にならない」ことを
            # データから証せる。拾い直しではない —— 宣言をそのまま読むだけである。
            if _nonneg(e[3], 0):
                classify(e[2], req, strict, sense, out, detail)
            elif _nonneg(e[2], 0):
                classify(e[3], req, strict, sense, out, detail)
            else:
                classify(e[2], 'COORD', strict, sense, out, detail)
                classify(e[3], 'COORD', strict, sense, out, detail)
        elif op == '/':
            # 正の数で割るのは順序を保つ（切り捨ても保つ）。割る数の符号が
            # 証せるなら、除算も単調である。
            if _nonneg(e[3], 1):
                classify(e[2], req, strict, sense, out, detail)
            else:
                classify(e[2], _flatreq(e[2], sense, 'COORD'), strict, sense, out, detail)
                classify(e[3], _flatreq(e[3], sense, 'COORD'), strict, sense, out, detail)
        else:
            # 剰余は単調でない（`x % 2` は x が育つと行ったり来たりする）——
            # **育つ束の話である。** flat / fourv の升は ⊥ → v → ⊤ としか動かず、
            # 算術は ⊥ 厳密・⊤ 厳密なので、剰余も単調である。
            # （内容アドレスがここに乗る。構成は再帰の中で使える。）
            classify(e[2], _flatreq(e[2], sense, 'COORD'), strict, sense, out, detail)
            classify(e[3], _flatreq(e[3], sense, 'COORD'), strict, sense, out, detail)
        return
    if k == 'fn':                       # min/max monotone in both arguments
        classify(e[2], req, strict, sense, out, detail)
        classify(e[3], req, strict, sense, out, detail); return
    if k == 'set':
        for x in e[1]:
            classify(x, 'COORD', strict, sense, out, detail)
        return
    if k == 'ctor':
        # 構成子の引数は「値」であって「座標」ではない。⊥ が伝播するので、
        # flat 場（一度確定したら動かない）を読む限り単調である。
        # min/max のように後から改善する場を読めば名前が変わってしまうので、
        # そこは sense の不一致として自動的に非単調になる。
        for x in e[2]:
            classify(x, 'UP', strict, sense, out, detail)
        return
    raise LattixError(f"classify: {e!r}")


def conservative_nonmono(e, neg, out):
    """The v0.2 analysis, kept so the polarity analysis can be differentially
    tested against a schedule that is obviously sound."""
    k = e[0]
    if k in ('fref',):
        if neg: out.add(e[1])
        for x in e[2]: conservative_nonmono(x, True, out)
    elif k == 'cmp':
        conservative_nonmono(e[2], True, out); conservative_nonmono(e[3], True, out)
    elif k in ('not', 'bnot'):
        conservative_nonmono(e[1], True, out)
    elif k == 'geq':
        conservative_nonmono(e[1], True, out); conservative_nonmono(e[2], True, out)
    elif k == 'bin':
        if e[1] == '-':
            conservative_nonmono(e[2], neg, out); conservative_nonmono(e[3], True, out)
        else:
            conservative_nonmono(e[2], neg, out); conservative_nonmono(e[3], neg, out)
    elif k == 'fn':
        conservative_nonmono(e[2], neg, out); conservative_nonmono(e[3], neg, out)
    elif k == 'set':
        for x in e[1]: conservative_nonmono(x, neg, out)
    elif k == 'ctor':
        for x in e[2]: conservative_nonmono(x, True, out)


def _expr_lattice(e, prog):
    if e[0] == 'fref': return prog.fields[e[1]].name if e[1] in prog.fields else None
    if e[0] in ('not', 'bnot'): return _expr_lattice(e[1], prog)
    return None


def _annotate(e, prog):
    """Rewrite `not` over a four-valued expression into the monotone `bnot`."""
    k = e[0]
    if k == 'not':
        inner = _annotate(e[1], prog)
        return ('bnot', inner) if _expr_lattice(inner, prog) == 'fourv' else ('not', inner)
    if k == 'bnot': return ('bnot', _annotate(e[1], prog))
    if k == 'geq': return ('geq', _annotate(e[1], prog), _annotate(e[2], prog))
    if k == 'fref': return ('fref', e[1], [_annotate(x, prog) for x in e[2]])
    if k in ('bin', 'cmp', 'fn'):
        return (k, e[1], _annotate(e[2], prog), _annotate(e[3], prog))
    if k == 'set': return ('set', [_annotate(x, prog) for x in e[1]])
    if k == 'ctor': return ('ctor', e[1], [_annotate(x, prog) for x in e[2]])
    return e


def _vars_of(e, out):
    _walk(e, lambda n: out.add(n[1]) if n[0] == 'var' else None)


def check(prog, conservative=False, optimistic=False):
    for r in prog.rules:
        r.keys = [_annotate(x, prog) for x in r.keys]
        r.value = _annotate(r.value, prog)
        r.guards = [_annotate(g, prog) for g in r.guards]
    prog.sense = field_senses(prog)
    prog.conservative = conservative
    for r in prog.rules:
        if r.target not in prog.fields:
            raise LattixError(f"line {r.lineno}: undeclared field {r.target!r}")
        # **`or` の元は {⊥, true} しか無い。** 整数を書くと、この解釈実行は
        # 何も置かず（値が true でないので）、焼いた符号は規則が火を噴いた
        # 時点で 1 を置く —— 同じ源が二つの答えを持つ。だから型として断る。
        # 許すのは `true` と **`or` の場の読み**だけ（⊥ は火を噴かないので一致する）。
        if prog.fields[r.target].name == 'or':
            v = r.value
            ok = (v[0] == 'bool' and v[1] is True)
            if not ok and v[0] == 'fref' and v[1] in prog.fields:
                ok = prog.fields[v[1]].name == 'or'
            if not ok:
                raise LattixError(f"line {r.lineno}: field {r.target!r} is `or`, whose "
                                  f"only elements are ⊥ and true — write `true` "
                                  f"(or read another `or` field), not a value")
        bound = {v for vs, _ in r.sources for v in vs}
        for vs, src in r.sources:
            if isinstance(src, tuple) and src[0] == '..':
                continue
            if src not in prog.tables:
                raise LattixError(f"line {r.lineno}: unknown table {src!r}")
            rows = prog.tables[src]
            ar = len(rows[0]) if rows else len(vs)
            if ar != len(vs):
                raise LattixError(f"line {r.lineno}: table {src!r} has arity {ar}, "
                                  f"pattern binds {len(vs)}")
        refs = set()
        for e in r.keys + [r.value] + r.guards:
            field_refs(e, refs)
        for vs, src in r.sources:            # 区間の端も読みである
            if isinstance(src, tuple) and src[0] == '..':
                field_refs(src[1], refs); field_refs(src[2], refs)
        for f in refs:
            if f not in prog.fields:
                raise LattixError(f"line {r.lineno}: undeclared field {f!r}")
        nm = set()
        if optimistic:
            pass                      # assume every read is monotone (depth 1)
        elif conservative:
            for e in r.keys + [r.value] + r.guards:
                conservative_nonmono(e, False, nm)
            nm |= {f for f in refs if prog.fields[f].name in ('sum', 'count', 'bag')}
        else:
            global SIGNS
            SIGNS = _Signs(prog, r)
            tgt_req = {'DOWN': 'DOWN'}.get(prog.sense.get(r.target), 'UP')
            for e in r.keys:
                classify(e, 'COORD', True, prog.sense, nm)
            classify(r.value, tgt_req, True, prog.sense, nm)
            for g in r.guards:
                classify(g, 'UP', True, prog.sense, nm)
            for vs, src in r.sources:
                # 区間が **縮む** ことがあってはならない。下端は下へ、上端は上へ。
                if isinstance(src, tuple) and src[0] == '..':
                    classify(src[1], 'DOWN', True, prog.sense, nm)
                    classify(src[2], 'UP', True, prog.sense, nm)
        r.reads = refs
        r.nonmono_reads = nm
        r.mono_reads = refs - nm

        used = set()
        for e in r.keys + [r.value] + r.guards:
            _vars_of(e, used)
        free = used - bound
        if free:
            raise LattixError(f"line {r.lineno}: unbound variable(s) "
                              f"{', '.join(sorted(free))} — add a `for` clause")
    for f in prog.prints:
        if f not in prog.fields:
            raise LattixError(f"print: undeclared field {f!r}")


# ==========================================================================
# 4. Stratifier — derives the provably minimal sequential depth
# ==========================================================================

def _tarjan_scc(n, succ):
    index = [None] * n; low = [0] * n; onstk = [False] * n
    stack, comp, counter, out = [], [None] * n, [0], [0]
    for root in range(n):
        if index[root] is not None: continue
        work = [(root, 0)]
        while work:
            v, pi = work[-1]
            if pi == 0:
                index[v] = low[v] = counter[0]; counter[0] += 1
                stack.append(v); onstk[v] = True
            recurse = False
            for i in range(pi, len(succ[v])):
                w = succ[v][i]
                if index[w] is None:
                    work[-1] = (v, i + 1); work.append((w, 0)); recurse = True; break
                elif onstk[w]:
                    low[v] = min(low[v], index[w])
            if recurse: continue
            if low[v] == index[v]:
                while True:
                    w = stack.pop(); onstk[w] = False; comp[w] = out[0]
                    if w == v: break
                out[0] += 1
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
    return comp, out[0]


def dependency_edges(prog):
    """(u, v, w) の一覧。これが成層問題の全入力である。
    lib/stratify.lx はこの表だけを受け取って、同じ答えを出す。"""
    writers = defaultdict(list)
    for r in prog.rules:
        writers[r.target].append(r.id)
    edges = []
    for r in prog.rules:
        for f in r.mono_reads:
            for w in writers.get(f, ()):
                if w != r.id: edges.append((w, r.id, 0))
        for f in r.nonmono_reads:
            for w in writers.get(f, ()):
                edges.append((w, r.id, 1))
        for f in r.reads:
            ch = prog.sources.get(f)
            if ch is None: continue
            for (c2, fld) in prog.channels:
                if c2 != ch: continue
                for w in writers.get(fld, ()):
                    edges.append((w, r.id, 1))
    return edges


def _const_int(e):
    """定数に畳めるなら int、畳めなければ None。"""
    if e[0] == 'int': return e[1]
    if e[0] == 'bin':
        a, b = _const_int(e[2]), _const_int(e[3])
        if a is None or b is None: return None
        try:
            return {'+': a + b, '-': a - b, '*': a * b,
                    '/': a // b, '%': a % b}[e[1]]
        except ZeroDivisionError:
            return None
    return None


def _axis_unroll(prog, ids):
    """**局所成層の決定可能な十分条件 —— 展開そのものが証明である。**

    場の粒度の成層器は、否定が同じ場の *小さい座標* を読む形
    （lvl[s, c] が lvl[s-1, c'] を否定で読む）を輪と見なして棄却する。
    だが座標が静的な区間 `for (s) in lo .. hi` で束ねられているなら、
    s を代入して展開した具体例の集合は **元のプログラムと同一のグラウンド
    集合**であり、展開後のグラフで成層が立てば、それは s に沿った整礎帰納の
    証明である（依存距離が正なら軸を逐次に回してよい —— 多面体の合法性と
    同じ主張）。判断は増やさない: 展開して、同じ成層器にもう一度判定させる。

    展開するのは棄却された SCC の規則だけ。各規則は「目標の座標に現れる、
    静的な区間の変数」を一つ持たねばならない（書き先の時計）。無ければ
    諦めて元の棄却を返す。展開の上限は 65,536 具体例 —— 超えたら声に出す。
    """
    todo = [prog.rules[i] for i in ids]
    plans = []
    total = 0
    axis = {}                      # 場 → 軸の位置（書き先の時計が立つ列）
    for r in todo:
        pick = None
        for vs, src in r.sources:
            if not (len(vs) == 1 and isinstance(src, tuple) and src[0] == '..'):
                continue
            dims = [d for d, k in enumerate(r.keys) if k == ('var', vs[0])]
            if not dims: continue
            lo, hi = _const_int(src[1]), _const_int(src[2])
            if lo is not None and hi is not None and lo <= hi:
                pick = (vs[0], lo, hi, dims[0]); break
        if pick is None: return False
        d0 = axis.setdefault(r.target, pick[3])
        if d0 != pick[3]: return False     # 同じ場に二つの時計は持てない
        total += pick[2] - pick[1] + 1
        plans.append((r, pick))
    # 展開しない書き手が居る場は、その書き手の座標が不明（総当たり）になる。
    # それでも裂く価値はある —— 不明は保守的に全員へ繋ぐだけである。
    for f, d in axis.items():
        prog._axis[f] = d
    if total > 65536:
        raise LattixError(
            f"axis unrolling would create {total} rule instances (cap 65536) —\n"
            f"    the stratification axis range is too wide to elaborate.")
    out = []
    for r in prog.rules:
        plan = next((pl for rr, pl in plans if rr is r), None)
        if plan is None:
            out.append(r); continue
        var, lo, hi, _d = plan
        for v in range(lo, hi + 1):
            vm = {var: ('int', v)}
            srcs = []
            for vs, src in r.sources:
                if len(vs) == 1 and vs[0] == var and isinstance(src, tuple) \
                        and src[0] == '..':
                    continue
                if isinstance(src, tuple) and src[0] == '..':
                    srcs.append((vs, ('..', _subst(src[1], {}, vm),
                                      _subst(src[2], {}, vm))))
                else:
                    srcs.append((vs, src))
            nr = Rule(r.target, [_subst(k, {}, vm) for k in r.keys],
                      _subst(r.value, {}, vm), srcs,
                      [_subst(g, {}, vm) for g in r.guards], r.lineno)
            nr.reads = set(r.reads)
            nr.mono_reads = set(r.mono_reads)
            nr.nonmono_reads = set(r.nonmono_reads)
            out.append(nr)
    prog.rules = out
    for i, r in enumerate(prog.rules): r.id = i
    return True


def stratify(prog):
    """Assign each rule the smallest stratum consistent with soundness.

    edge W --0--> R : R monotonically reads a field W writes (may co-iterate)
    edge W --1--> R : R non-monotonically reads it (must be strictly later)

    Minimal depth = weighted longest path.  A 1-edge inside a cycle means
    recursion through negation: no stratification exists —— unless the cycle
    descends a statically bounded coordinate, in which case unrolling that
    axis elaborates the local stratification (see `_axis_unroll`).
    """
    for _attempt in range(8):
        bad = _stratify_core(prog)
        if bad is None:
            return prog._depth
        ids, err = bad
        if not _axis_unroll(prog, ids):
            raise err
    raise err


def _fref_axis_coords(e, f, d, out):
    """式の中の場 f の読みについて、軸 d の座標（定数）を集める。
    定数でない読みは None（不明＝全員に繋ぐ）。"""
    k = e[0]
    if k == 'fref':
        if e[1] == f:
            out.add(_const_int(e[2][d]) if d < len(e[2]) else None)
        for x in e[2]: _fref_axis_coords(x, f, d, out)
    elif k == 'ctor':
        for x in e[2]: _fref_axis_coords(x, f, d, out)
    elif k in ('bin', 'cmp', 'fn'):
        _fref_axis_coords(e[2], f, d, out); _fref_axis_coords(e[3], f, d, out)
    elif k == 'geq':
        _fref_axis_coords(e[1], f, d, out); _fref_axis_coords(e[2], f, d, out)
    elif k in ('not', 'bnot'):
        _fref_axis_coords(e[1], f, d, out)
    elif k == 'set':
        for x in e[1]: _fref_axis_coords(x, f, d, out)


def _stratify_core(prog):
    n = len(prog.rules)
    writers = defaultdict(list)
    for r in prog.rules:
        writers[r.target].append(r.id)

    # **座標で場を裂く。** 軸を持つ場（_axis_unroll が刻む）は、書き先の
    # 軸座標が定数 c、読みの軸座標が定数 c' で c != c' なら、そのグラウンド
    # 辺は存在しない —— 場の粒度の総当たりから、無い辺を引くだけである。
    # 字面展開の engine が通っていたのは名前が座標を持っていたからで
    # （vf0, vf1, …）、これは同じ判断を名前ではなく数で行う。
    axis = getattr(prog, '_axis', {})
    wc = {}
    for r in prog.rules:
        d = axis.get(r.target)
        wc[r.id] = _const_int(r.keys[d]) if d is not None and d < len(r.keys) \
                   else None

    # **同じ規則の同じ場を、書き手の数だけ歩き直すな。** 座標の集合は
    # (規則, 場) だけで決まる（軸は固定）—— 判断は変わらない。前は
    # 書き手 × 読み手 × 場ぶん歩いていたので、一枚の本（前段 2371 規則 ∪
    # 走らせる物 366 規則）では成層だけで数十分掛かっていた。
    _rc = {}

    def rcoords(r, f):
        d = axis.get(f)
        if d is None: return {None}
        key = (r.id, f)
        hit = _rc.get(key)
        if hit is not None: return hit
        out = set()
        for e in r.keys + [r.value] + r.guards:
            _fref_axis_coords(e, f, d, out)
        for vs, src in r.sources:
            if isinstance(src, tuple) and src[0] == '..':
                _fref_axis_coords(src[1], f, d, out)
                _fref_axis_coords(src[2], f, d, out)
        _rc[key] = out or {None}
        return _rc[key]

    def joined(w, r, f):
        if f not in axis: return True
        rs = rcoords(r, f)
        return None in rs or wc[w] is None or wc[w] in rs

    edges = []          # (u, v, w)
    succ = [[] for _ in range(n)]
    for r in prog.rules:
        for f in r.mono_reads:
            for w in writers.get(f, ()):
                if w != r.id and joined(w, r, f):
                    edges.append((w, r.id, 0)); succ[w].append(r.id)
        for f in r.nonmono_reads:
            for w in writers.get(f, ()):
                # a weight-1 self-loop IS the ill-posed case; keep it
                if joined(w, r, f):
                    edges.append((w, r.id, 1)); succ[w].append(r.id)
        # 外界との往復: そのチャネルへ emit する規則より真に後でなければ、
        # 応答を読むことはできない。これが逐次性の *本当の* 出どころである。
        for f in r.reads:
            ch = prog.sources.get(f)
            if ch is None: continue
            for (c2, fld) in prog.channels:
                if c2 != ch: continue
                for w in writers.get(fld, ()):
                    edges.append((w, r.id, 1)); succ[w].append(r.id)

    comp, ncomp = _tarjan_scc(n, succ)

    for (u, v, w) in edges:
        if w == 1 and comp[u] == comp[v]:
            cyc = sorted({prog.rules[i].target for i in range(n) if comp[i] == comp[u]})
            ids = [i for i in range(n) if comp[i] == comp[u]]
            err = LattixError(
                "unstratifiable program: recursion through a non-monotone "
                "dependency.\n"
                f"    fields in the cycle: {', '.join(cyc)}\n"
                f"    line {prog.rules[v].lineno} asks a question about "
                f"{', '.join(sorted(prog.rules[v].nonmono_reads))} whose answer\n"
                f"    depends on that question. No execution order fixes this —\n"
                f"    it is not a missing barrier, it is an ill-posed program.\n"
                f"    REPAIR: retype {' / '.join(cyc)} to `fourv`. Belnap negation is\n"
                f"    monotone in the knowledge order, so the cycle acquires a least\n"
                f"    fixpoint and the undecided coordinates come back as ⊥.")
            return (ids, err)

    cedges = defaultdict(int)
    for (u, v, w) in edges:
        if comp[u] != comp[v]:
            cedges[(comp[u], comp[v])] = max(cedges[(comp[u], comp[v])], w)

    csucc = defaultdict(list); indeg = defaultdict(int)
    for (a, b), w in cedges.items():
        csucc[a].append((b, w)); indeg[b] += 1
    order, q = [], [c for c in range(ncomp) if indeg[c] == 0]
    while q:
        c = q.pop()
        order.append(c)
        for (b, w) in csucc[c]:
            indeg[b] -= 1
            if indeg[b] == 0: q.append(b)

    lvl = [0] * ncomp; pred = [None] * ncomp
    for c in order:
        for (b, w) in csucc[c]:
            if lvl[c] + w > lvl[b]:
                lvl[b] = lvl[c] + w; pred[b] = c
    depth = max(lvl) + 1 if ncomp else 0

    for r in prog.rules:
        r.stratum = lvl[comp[r.id]]
        r.scc = comp[r.id]
    # 凝縮グラフの位相順。層の *中* でも、SCC は互いに順序を持つ ——
    # 一つの層をまとめて回すと、独立な部分どうしが再発火で干渉する。
    prog.scc_rank = {c: i for i, c in enumerate(order)}
    prog.strata = [[] for _ in range(depth)]
    for r in prog.rules:
        prog.strata[r.stratum].append(r)

    # recover a critical path for the report
    if ncomp:
        end = max(range(ncomp), key=lambda c: lvl[c])
        chain, c = [], end
        while c is not None:
            members = sorted({prog.rules[i].target for i in range(n) if comp[i] == c})
            chain.append("+".join(members))
            c = pred[c]
        prog.critical_path = list(reversed(chain))
    prog._depth = depth
    return None


# ==========================================================================
# 5. Termination certificates
# ==========================================================================

def io_rounds(prog):
    """外界と何回 *ブロックして* 待つか。

    応答を後の層で読むチャネルへの emit だけが数えられる。
    投げっぱなしの emit は遅延に効かないので数えない。
    並列に出せるものは同じ層に入るので、自然に 1 回にまとまる。"""
    emit_at = defaultdict(set)
    fld2ch = {fld: ch for ch, fld in prog.channels}
    for r in prog.rules:
        ch = fld2ch.get(r.target)
        if ch is not None: emit_at[ch].add(r.stratum)
    blocking = set()
    for r in prog.rules:
        for f in r.reads:
            ch = prog.sources.get(f)
            if ch is None: continue
            for s in emit_at.get(ch, ()):
                if s < r.stratum: blocking.add((ch, s))
    prog.io = len(blocking)
    return prog.io


def check_budgets(prog, depth):
    for kind, limit, lineno in prog.budgets:
        got = depth if kind == 'depth' else prog.io
        if got > limit:
            raise LattixError(
                f"line {lineno}: budget {kind} <= {limit} exceeded: this program "
                f"costs {got}.\n"
                f"    critical path : " + " -> ".join(prog.critical_path) + "\n"
                f"    A cost budget is an interface, like a type. Widen it "
                f"deliberately or remove the dependency that caused it.")


def certify(prog):
    """Prove (or fail to prove) that the fixpoint converges."""
    writers = defaultdict(list)
    for r in prog.rules:
        writers[r.target].append(r)
    out = {}
    for f, lat in prog.fields.items():
        if not writers.get(f):
            out[f] = ("VACUOUS", "no contributions")
            continue
        recursive = any(f in r.reads for r in writers[f])
        if lat.finite_height:
            out[f] = ("CERTIFIED", f"{lat.name} lattice: height bounded by input size")
            continue
        if not recursive:
            out[f] = ("CERTIFIED", f"{lat.name} lattice, non-recursive: one pass")
            continue
        # recursive min/max: prove the recursive step cannot descend forever
        ok, why = _delta_nonneg(prog, f, writers[f], lat)
        out[f] = ("CERTIFIED", why) if ok else ("UNPROVEN", why)
    prog.certificates = out
    # 前線下界を持てる場 = min 束 + 再帰デルタ非負（＝ Dijkstra が licence される場）
    prog.bounded = {f for f, (st, why) in out.items()
                    if st == 'CERTIFIED' and prog.fields[f].name == 'min'
                    and any(f in r.reads for r in writers.get(f, ()))}
    return out


def relax(prog):
    """証明書を使って **層をもう一度減らせるか** を試す。

    check → stratify → certify の順は崩せない（証明書は層に依る）。だから
    一度通した後に、証明書が licence する上界を使ってもう一度だけ回す。

    落ちるのは「min 束への `> k`」型のガードで、これは前線の下界 B があれば
    待たずに答えられる。**証明書はスケジューラを選ぶだけのものではなかった。**

    戻り値: (前の深度, 後の深度)。減らなければ元に戻す。"""
    before = len(prog.strata)
    if not getattr(prog, 'bounded', None): return before, before
    global UBOUND
    saved = UBOUND
    UBOUND = set(prog.bounded)
    try:
        check(prog)
        after = stratify(prog)
        io_rounds(prog); certify(prog)
    except LattixError:
        UBOUND = saved
        check(prog); stratify(prog); io_rounds(prog); certify(prog)
        return before, before
    if after >= before:                 # 得が無ければ元の解析に戻す
        UBOUND = saved
        check(prog); stratify(prog); io_rounds(prog); certify(prog)
        return before, before
    prog.relaxed = True                 # 実行系は前線下界を維持する義務を負う
    prog.force_engine = 'priority'      # 下界を維持できるのはこれだけ
    UBOUND = saved
    return before, after


def _has_fref(e):
    s = set(); field_refs(e, s); return bool(s)


def _delta_nonneg(prog, fname, rules, lat):
    """For `f[k] <- f[k'] + delta`, evaluate delta on the ground data and check
    its sign.  For a min-lattice this is exactly 'no negative cycles'."""
    want = "non-negative" if lat.name == 'min' else "non-positive"
    for r in rules:
        if fname not in r.reads:
            continue
        e = r.value
        if not (e[0] == 'bin' and e[1] in ('+', '-')):
            return False, f"recursive contribution is not of the form f[..] {'+'} delta"
        a, b = e[2], e[3]
        sub = set(); field_refs(a, sub)
        if fname not in sub:
            a, b = b, a
            sub = set(); field_refs(a, sub)
            if fname not in sub:
                return False, "recursive reference is not in an additive position"
        d = set(); field_refs(b, d)
        if d:
            return False, "delta itself depends on lattice values"
        store = {g: {} for g in prog.fields}
        # **起きない寄与の符号は問うても意味がない。** 地上で偽と決まるガード
        # （場の読みを含まないガード）で落ちる束縛は、この規則の差分ではない。
        ground = [g for g in r.guards if not _has_fref(g)]
        for env in bindings(r, prog, None):
            if any(not _truthy(ev(g, env, store, prog.fields)) for g in ground):
                continue
            v = ev(b, env, store, prog.fields)
            if e[1] == '-': v = -v
            if lat.name == 'min' and v < 0:
                return False, f"delta can be negative ({v}) — descent may not terminate"
            if lat.name == 'max' and v > 0:
                return False, f"delta can be positive ({v}) — ascent may not terminate"
    return True, (f"recursive delta is {want} on all ground data "
                  f"(no {'negative' if lat.name=='min' else 'positive'} cycle) "
                  f"⇒ Kleene iteration converges")


# ==========================================================================
# 6. Evaluation
# ==========================================================================

def ev(e, env, store, fields):
    k = e[0]
    if k == 'int' or k == 'str' or k == 'bool': return e[1]
    if k == 'var': return env[e[1]]
    if k == 'fref':
        key = tuple(ev(x, env, store, fields) for x in e[2])
        lat = fields[e[1]]
        raw = store[e[1]].get(key, lat.bot)
        # **⊥ の読みは火を噴かない。** min の ⊥ は INF という *値* なので、
        # max の場に書くと ⊥ 由来の巨大な数がそのまま残る（`min` に書く限りは
        # 吸収されるので、何版も気づかなかった）。焼いた符号は ⊥ で次の行へ
        # 飛んでいる —— 定義の方がまた甘かった（気づき27 と同じ穴）。
        # 否定は `_truthy(None)` が偽なので、`not f[…]` は今までどおり発火する。
        if _is_bot(lat, raw): return None
        return lat.observe(raw)
    if k == 'set':
        # **⊥ は要素になれない。** 座標になれないのと同じ理由である ——
        # 「まだ分からないもの」を集合に入れると、観測が単調でなくなる。
        # （外界に問い合わせ中の値が {None} として出ていて、ネイティブと食い違った。）
        return frozenset(v for v in (ev(x, env, store, fields) for x in e[1])
                         if v is not None)
    if k == 'ctor':
        vals = tuple(ev(x, env, store, fields) for x in e[2])
        if any(v is None for v in vals): return None      # ⊥ は伝播する
        if any(isinstance(v, _Top) for v in vals): return TOP   # ⊤ も伝播する
        return ctor_id(e[1], vals)
    if k == 'geq':
        a = e[1]
        if a[0] != 'fref':
            raise LattixError("`is` needs a field reference on the left")
        lat = fields[a[1]]
        v = ev(a, env, store, fields)
        if isinstance(v, _Top): return TOP     # ⊤ は上集合のどれにも属する
        return lat.geq(v, ev(e[2], env, store, fields))
    if k == 'bnot':
        return _fnot(ev(e[1], env, store, fields))
    if k == 'not':
        v = ev(e[1], env, store, fields)
        # `not (f[x] < 6)` は f が ⊥ のときも発火してはならない ——
        # 「⊥ だから偽」を否定すると真になり、あとで値が入ると偽に戻る。
        # ⊥ は否定を跨いで **⊥ のまま**（発火しない）である。
        if v is None and e[1][0] in ('cmp', 'not'): return None
        return not _truthy(v)
    if k == 'fn':
        a = ev(e[2], env, store, fields); b = ev(e[3], env, store, fields)
        if a is None or b is None: return None
        if isinstance(a, _Top) or isinstance(b, _Top): return TOP
        return min(a, b) if e[1] == 'min' else max(a, b)
    if k == 'cmp':
        op = e[1]
        # 上界（前線下界）で早期に答える。まだ確定していないセルの最終値は
        # B 以上だと証明書が言っているので、B を使えば **偽陽性が起きない**。
        # 確定したセルは正確な値で答える。だから答えは待ったときと同じになる。
        if op in ('>', '>=') and e[2][0] == 'fref' and e[3][0] == 'int' \
           and e[2][1] in BOUND:
            f = e[2][1]
            key = tuple(ev(x, env, store, fields) for x in e[2][2])
            if key in SETTLED.get(f, ()):
                a = fields[f].observe(store[f].get(key, fields[f].bot))
            else:
                a = BOUND[f]
            b = e[3][1]
            if isinstance(a, _Top): return TOP     # ⊤ は「少なくとも真」
            if a is None: return False
            # **前線下界が ⊥ なら、比べてはいけない。** 層が終わった時点で
            # 未確定の升は「到達しなかった」＝⊥ であって、INF という *値* では
            # ない。ここで `INF >= 3` を真と答えていたので、⊥ の升にまで
            # 述語が立っていた（SPEC「⊥ は比べられない」に反する）。
            # 走らせる物（Lattix で書いた実装）と突き合わせて出た穴である。
            if a in (INF, NEGINF):
                raw = store[f].get(key, fields[f].bot)
                if _is_bot(fields[f], raw): return None   # ⊥ のまま —— 比べない
                a = fields[f].observe(raw)                # 層が終わっている＝確定値
            return a > b if op == '>' else a >= b
        # **⊥ の読みは火を噴かない。** ⊥ と比べて真になる述語は単調でない ——
        # あとで値が入れば真が偽に変わりうる。項でも肯定ガードでもそうしている
        # のに、比較だけ穴が開いていた。焼いた符号はここで次の行へ飛んでいる
        # （種3/4 の「⊥ は火を噴かない」）。定義と機械語が食い違っていた。
        # 上の前線下界（`relax`）は ⊥ を **まだ確定していない**として扱う別の話で、
        # そちらが先に答える —— だからこの検査はその後ろに置く。
        if _cmp_bot(e[2], env, store, fields) or _cmp_bot(e[3], env, store, fields):
            return None       # **偽ではなく ⊥**。`not` を跨いでも発火しない
        a = ev(e[2], env, store, fields); b = ev(e[3], env, store, fields)
        # **⊤ は「少なくとも真」である。** ⊥ ⊑ v ⊑ ⊤ の鎖の上で述語が単調で
        # あるためには、⊤ での答えが v での答え以上でなければならない ——
        # つまり ⊤ では立つ。⊤ を偽に潰していたから、`f[x] < 4` が
        # 「v で真、⊤ で偽」になり、日程で答えが変わっていた（discover 第2部）。
        # `_truthy(TOP)` が既に真を返していたのに、比較だけが潰していた。
        if isinstance(a, _Top) or isinstance(b, _Top): return TOP
        try:
            return {'<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b,
                    '==': a == b, '!=': a != b}[op]
        except TypeError:
            return False
    if k == 'bin':
        a = ev(e[2], env, store, fields); b = ev(e[3], env, store, fields)
        if a is None or b is None: return None
        if isinstance(a, _Top) or isinstance(b, _Top): return TOP
        op = e[1]
        if isinstance(a, frozenset) or isinstance(b, frozenset):
            if op == '+': return a | b
            if op == '-': return a - b
            raise LattixError(f"bad set operator {op}")
        if a in (INF, NEGINF) or b in (INF, NEGINF):
            if op in ('+', '-', '*'):
                return INF if INF in (a, b) else NEGINF
        if op in ('/', '%'):
            # 零除算は誤りではなく **未定** である。⊥ を返せば寄与が消えるだけで、
            # プログラム全体が落ちない（束の言葉で書けば例外は要らない）。
            if b == 0: return None
            return (a // b) if op == '/' else (a % b)
        return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b}[op]()
    raise LattixError(f"cannot evaluate {e!r}")


def _is_bot(lat, v):
    """その値は束の ⊥ か（検査器の影の束にも効くように緩く見る）。"""
    isb = getattr(lat, 'is_bot', None)
    if isb is not None:
        try: return bool(isb(v))
        except Exception: return False
    try:
        if isinstance(v, (dict, set, frozenset, list)): return len(v) == 0
        return v == lat.bot
    except Exception:
        return False


def _cmp_bot(x, env, store, fields):
    """比較の片側が ⊥ の場の読みか。⊥ なら規則は発火しない。

    検査器は観測値の上の **影の束**（attest.Shim）を渡してくる。⊥ の綴りが
    違うだけで、聞きたいことは同じである —— だから `is_bot` が無ければ
    `bot` と比べる。ここで例外を出したら、検査器が規則を丸ごと落とした。"""
    if x[0] != 'fref': return False
    try:
        lat = fields[x[1]]
        key = tuple(ev(y, env, store, fields) for y in x[2])
        v = store.get(x[1], {}).get(key, lat.bot)
        isb = getattr(lat, 'is_bot', None)
        if isb is not None: return bool(isb(v))
        if isinstance(v, (dict, set, frozenset, list)): return len(v) == 0
        return v == lat.bot
    except Exception:
        return False


def _truthy(v):
    if isinstance(v, _FourV): return v.v          # T -> fire, F -> don't
    if isinstance(v, _Top): return True           # TOP is at least true
    if v is None or v is INF: return False
    if isinstance(v, frozenset): return len(v) > 0
    if isinstance(v, dict): return len(v) > 0
    return bool(v)


def bindings(rule, prog, rng, store=None):
    """規則実例の供給。表の行か、**座標の区間**か。

    区間の端は左から順に、それまでに束縛された変数の下で評価する ——
    だから `for (s) in 0 .. ns[] for (r) in 0 .. nr[s]` が書ける。
    外側の座標が内側の空間の広さを決める。**記述が空間を決める。**"""
    if not rule.sources:
        yield {}; return
    f = store if store is not None else {g: {} for g in prog.fields}

    def rows_for(src, env):
        if isinstance(src, tuple) and src[0] == '..':
            a = ev(src[1], env, f, prog.fields)
            b = ev(src[2], env, f, prog.fields)
            if not isinstance(a, int) or not isinstance(b, int): return []
            if isinstance(a, bool) or isinstance(b, bool): return []
            if b - a > RANGE_CAP:
                raise LattixError(f"line {rule.lineno}: range of {b - a + 1} "
                                  f"coordinates exceeds the cap {RANGE_CAP}")
            return [(i,) for i in range(a, b + 1)]
        return prog.tables[src]

    def walk(i, env):
        if i == len(rule.sources):
            yield dict(env); return
        vs, src = rule.sources[i]
        rows = rows_for(src, env)
        if rng is not None:
            rows = list(rows); rng.shuffle(rows)
        for row in rows:
            for name, val in zip(vs, row): env[name] = val
            yield from walk(i + 1, env)
        for name in vs: env.pop(name, None)

    yield from walk(0, {})


def read_keys(e, env, store, fields, out):
    k = e[0]
    if k == 'fref':
        for x in e[2]: read_keys(x, env, store, fields, out)
        out.add((e[1], tuple(ev(x, env, store, fields) for x in e[2])))
    elif k in ('bin', 'cmp', 'fn'):
        read_keys(e[2], env, store, fields, out); read_keys(e[3], env, store, fields, out)
    elif k == 'geq':
        read_keys(e[1], env, store, fields, out); read_keys(e[2], env, store, fields, out)
    elif k == 'ctor':
        for x in e[2]: read_keys(x, env, store, fields, out)
    elif k in ('not', 'bnot'):
        read_keys(e[1], env, store, fields, out)
    elif k == 'set':
        for x in e[1]: read_keys(x, env, store, fields, out)


def _prov(rule, env):
    return (rule.id,) + tuple(env[v] for v in sorted(env))


def _contribute(r, env, store, prog, stats):
    # **支持は毎回きれいにする。** 途中で消える寄与（ガードが偽、値が ⊥）は
    # 前の実例の `support` を残したまま抜けていて、起きなかった寄与が
    # 階数を下げていた（`_size` の 22_parse で露見）。
    stats['support'] = 0
    lat = prog.fields[r.target]
    for g in r.guards:
        if not _truthy(ev(g, env, store, prog.fields)):
            return False
    val = ev(r.value, env, store, prog.fields)
    # BOT propagates across lattices: reading an undetermined flat field and
    # feeding it to a `min` field must contribute nothing, not crash.  Same for
    # TOP -- contradictory input carries no definite information downstream
    # (the conflict itself is reported at its own field).
    if val is None and lat.name not in ('flat', 'fourv'):
        return False
    if isinstance(val, _FourV) and lat.name not in ('flat', 'fourv'):
        return False
    if lat.name == 'fourv' and isinstance(val, bool):
        val = FTRUE if val else FFALSE
    if lat.name in ('sum', 'count', 'bag'):
        if val is None: return False
        val = {_prov(r, env): val}
    if lat.is_bot(val): return False
    key = tuple(ev(x, env, store, prog.fields) for x in r.keys)
    # 座標がまだ未確定（⊥）なら、そのセルはまだ存在しない。寄与できない。
    # ⊥ も ⊤ も座標ではない。矛盾した情報はセルの名前になれない。
    if any(x is None for x in key): return False
    if any(isinstance(x, _Top) for x in key):
        # **矛盾した値は座標になれない。** 黙って飛ばすと、この寄与が
        # 「起きたか起きなかったか」が日程で変わる（⊤ になる前に間に合えば
        # 起きる）。座標に使う読みを単調だと言えるのは ⊥ → v で止まるあいだ
        # だけなので、そこを越えたら **そう言って止まる**。
        stats.setdefault('topkey', set()).add((r.target, r.lineno))
        return False
    stats['key'] = key          # 実際に書いたキー（構成子だと事前計算とずれる）
    cur = store[r.target].get(key, lat.bot)
    # TOP is the top element of EVERY lattice, so it absorbs.  Without this,
    # a downstream field could keep a transient value that its source later
    # invalidated -- order-dependent, and discover.py caught exactly that.
    if isinstance(val, _Top) or isinstance(cur, _Top):
        new = TOP
    else:
        new = lat.join(cur, val)
    stats['joins'] += 1
    if new != cur:
        store[r.target][key] = new
        # **影**: 平坦なセルは生涯にただ一つの確定値しか持てない（⊥ → a → ⊤）。
        # だから「⊤ になる前の値」は曖昧さなく決まる。それを捨てているから
        # 閉路で押し上げられた ⊤ の証人が最終の答えに残らない。捨てずに置く。
        P = stats.get('pre')
        if P is not None and lat.name in ('flat', 'fourv') \
           and not isinstance(new, _Top):
            P.setdefault((r.target, key), new)
        stats['support'] = 1          # changed
        return True
    # 値は変わらないが、この寄与はいま主張されている値を *支持* している。
    # 階数はここでも更新しないと古びる（正当化した相手が後で改善した場合）。
    #
    # 「吸収された」と「支持している」は違う。min 束で cur=3 のセルに 4 が来ても
    # join は動かないが、4 は 3 の正当化ではない。**等しいときだけ支持である。**
    # 半素朴な実行では読みが動いた実例しか再発火しないのでこの差は表に出なかった。
    # 領域実行が領域内を素朴に舐めた途端に、階数が 3 から 2 へ落ちて証明書が壊れた。
    stats['support'] = 2 if (not lat.is_bot(cur) and new == val) else 0
    return False


# **実例の表は最適化であって、答えではない。**
# worklist / priority / sweep はどれも「規則の実例」を一本ずつ表に置く ——
# 表があるから育った所だけ再訪できる。だが実例が数百万本になると、
# 表そのものが答えより重くなる（升 1300万の断片で 4GB 使って殺された）。
# そのときは表を作らず、毎回数え直す（naive）。**答えは実行に依らない**ので
# 選び直してよい —— 変わるのは時間と空間だけである。
ITEM_CAP = 1500000


class _TooManyItems(Exception):
    """実例の表が上限を超えた。表を持たない日程に切り替える合図。"""


def _cap(items, rule):
    if len(items) > ITEM_CAP:
        raise _TooManyItems(f"{len(items)} instances (line {rule.lineno})")


def run_stratum_naive(rules, prog, store, rng, stats):
    while True:
        changed = False
        order = list(rules)
        if rng is not None: rng.shuffle(order)
        for r in order:
            for env in bindings(r, prog, rng, store):
                stats['key'] = None
                ch = _contribute(r, env, store, prog, stats)
                if not ch and stats.get('support') != 2: continue
                rk = set()
                for e in r.keys + [r.value] + r.guards:
                    read_keys(e, env, store, prog.fields, rk)
                if _bump(stats, prog, rules, r, stats.get('key') or
                         tuple(ev(x, env, store, prog.fields) for x in r.keys),
                         rk, ch, store, env):
                    changed = True
                if ch: changed = True
        stats['rounds'] += 1
        if not changed: break


WTA = ('min', 'max', 'or', 'and', 'flat')   # 勝者総取り: 正当化は一つで足りる

def _bump(stats, prog, rules, r, tgtkey, rk, changed, store=None, env=None):
    """rank(cell) = 1 + max rank of the SAME-STRATUM cells that justify it.

    The rank is written on every CHANGE, so it always names the justification
    that produced the value now in the cell.

    Whether the ranks are *valid at the end* is a property of the scheduler:
    a scheduler that settles each coordinate once (the priority queue, which
    the termination certificate licenses) never invalidates an earlier rank.
    A FIFO worklist may relax a cell after its dependents were ranked, leaving
    a stale rank -- the checker then reports "certificate invalid", not
    "answer wrong".  That is the honest outcome."""
    R = stats.get('rank')
    if R is None: return False
    # 読みは **層を問わず全部** 見る。同層だけを見ると、場が複数の層で書かれるとき
    # 階数が小さく出て、検査器の有基性を通らなくなる（16_lex / 15_parse で露見）。
    # 大きい方へ倒すのは安全側である —— 検査器が要求するのは狭義の減少だけだから。
    # まだ階数の付いていない証人を 0 と読むと、階数が実際より浅く出る。
    # **階数は日程の副産物ではない。** 証人が揃うまで書かずに待つ ——
    # 証人が階数を得れば、この寄与は索引を通ってもう一度撃たれる。
    c = (r.target, tgtkey)
    old = R.get(c)
    m = 0
    for (f, k) in rk:
        if (f, k) in R:
            m = max(m, R[(f, k)])
        elif store is not None and k in store.get(f, ()):
            # 証人はいるが、まだ階数が無い。いま書ける階数は必ず浅すぎる。
            # **古い階数も捨てる** —— それはもう今の値を支えていない。
            # 支持も一緒に捨てる。片方だけ残すと、撤回が古い支持を信じる。
            if old is not None: del R[c]
            if stats.get('just') is not None: stats['just'].pop(c, None)
            return old is not None
    if prog.fields[r.target].name in WTA:
        # 階数は「その値に至る *最短の* 導出の深さ」でなければならない。
        # 最初にできた導出を記録すると、後から見つかる近道が反映されない。
        # つまり階数そのものが最短経路問題である —— 最短経路はいつも幾何にある。
        R[c] = (m + 1) if (changed or old is None) else min(old, m + 1)
    else:
        R[c] = (m + 1) if changed else max(old or 0, m + 1)
    # **証明書は支持を名指している。** 階数を書いたということは、いまの値を
    # 支えている規則実例をここで選んだということである。その実例が読んだセルと
    # 使った表の行を控えておけば、撤回のときに「消えた事実がこの値の *導出に*
    # 使われたか」が直に引ける —— 依存の全閉包を歩かなくてよい。
    # **記述は二度使われる**: 検査のために作った証人が、削除の前線にもなる。
    J = stats.get('just')
    if J is not None and R.get(c) is not None:
        rows = ()
        if env is not None:
            try:
                rows = tuple((tb, tuple(env[v] for v in vs))
                             for vs, tb in r.sources if isinstance(tb, str))
            except KeyError:
                rows = ()
        J[c] = (frozenset(rk), rows)
    # 影の階数は「その確定値に至った導出の深さ」。⊤ になったあとの階数は
    # ⊤ の導出のものなので、**一度だけ**書いて上書きしない。
    P = stats.get('pre')
    if P is not None and c in P and c not in stats['prerank']:
        stats['prerank'][c] = R[c]
    return R[c] != old


def run_stratum_worklist(rules, prog, store, rng, stats):
    """Semi-naive: a rule instance is re-fired only when a key it reads moved.

    区間を持つ規則は **供給そのものが育つ**。だから実例表を一度作って終わりに
    できない —— かといって毎回数え直す（素朴）のは、育っていない分まで数え直す
    ことになる。育った差分だけ足す: これは半素朴を *供給* の側に効かせたもので、
    値について既にやっていることと同じ形である。"""
    stats['here'] = {r.target for r in rules}
    items, index = [], defaultdict(list)
    grow = [r for r in rules
            if any(not isinstance(src, str) for _v, src in r.sources)]
    seen = set()

    def expand(rs):
        """まだ見ていない束縛の実例だけを足す。"""
        fresh = []
        for r in rs:
            for env in bindings(r, prog, rng, store):
                if r in grow:
                    sig = (r.id,) + tuple(sorted(env.items(), key=lambda t: t[0]))
                    if sig in seen: continue
                    seen.add(sig)
                rk = set()
                for e in r.keys + [r.value] + r.guards:
                    read_keys(e, env, store, prog.fields, rk)
                tgt = tuple(ev(x, env, store, prog.fields) for x in r.keys)
                i = len(items)
                items.append((r, dict(env), tgt, rk))
                _cap(items, r)
                for fk in rk:
                    index[fk].append(i)
                fresh.append(i)
        return fresh

    order = expand(rules)
    if rng is not None: rng.shuffle(order)
    # FIFO, not LIFO: a stack turns Bellman-Ford into depth-first thrashing,
    # re-relaxing along non-final prefixes.  A queue keeps the frontier
    # level-ordered (this is exactly SPFA) and is what makes semi-naive pay.
    work = deque(order)
    queued = [True] * len(items)
    while work:
        if rng is not None and len(work) > 1 and rng.random() < 0.5:
            work.rotate(-rng.randrange(len(work)))
        i = work.popleft()
        queued[i] = False
        r, env, tgt, rk = items[i]
        if stats.get('budget') and stats['joins'] >= stats['budget']:
            stats['stopped'] = True; return
        stats['key'] = None
        ch = _contribute(r, env, store, prog, stats)
        # 階数は **実際に書いたキー** に付ける。事前計算した tgt は、キーが
        # 構成子（内容アドレス）のとき ⊥ から作った名前になっていて、
        # 証人が別のセルに書かれていた（`node_sym` の階数 0 の正体）。
        # 構成された値の証人は、その部品の証人である —— 名前さえ合えば分解できている。
        key = stats.get('key') or tgt
        moved = False
        if ch:
            stats['rounds'] += 1
            moved = _bump(stats, prog, rules, r, key, rk, True, store, env)
            if stats['rounds'] > FIRE_BUDGET:
                raise LattixError("fire budget exhausted (ascending chain too long)")
        elif (stats.get('rank') is not None and stats.get('support') == 2
              and prog.fields[r.target].name in WTA):
            # 値は変わらないが、より浅い正当化が見つかった。階数は下がりうる。
            # 単調に減るだけなので必ず止まる。
            moved = _bump(stats, prog, rules, r, key, rk, False, store, env)
        if ch or moved:
            for j in index.get((r.target, tgt), ()):
                if not queued[j]:
                    queued[j] = True; work.append(j)
        if not work and grow:
            # 前線が尽きた。**空間が広がっていないか**を見て、広がっていれば足す。
            more = expand(grow)
            if more:
                queued.extend([False] * (len(items) - len(queued)))
                for j in more:
                    if not queued[j]: queued[j] = True; work.append(j)


def _ubound_guard(e, bnd):
    """このガードは前線下界に依存するか（`f[x] > k` の形で f が下界つき）。"""
    return (e[0] == 'cmp' and e[1] in ('>', '>=') and e[2][0] == 'fref'
            and e[3][0] == 'int' and e[2][1] in bnd)


def run_stratum_priority(rules, prog, store, rng, stats):
    stats['here'] = {r.target for r in rules}
    """Certificate-directed scheduling.

    The termination certificate for a `min` field says its recursive delta is
    non-negative.  That is not merely a proof of convergence -- it is exactly
    the precondition under which a *value-ordered* frontier is monotone, i.e.
    Dijkstra.  So the proof selects the scheduler: pop the pending rule
    instance whose source coordinate currently holds the smallest value, and
    every key settles on its first pop.
    """
    items, index, prio_src = [], defaultdict(list), []
    for r in rules:
        for env in bindings(r, prog, rng, store):
            rk = set()
            for e in r.keys + [r.value] + r.guards:
                read_keys(e, env, store, prog.fields, rk)
            tgt = tuple(ev(x, env, store, prog.fields) for x in r.keys)
            i = len(items)
            items.append((r, env, tgt, rk))
            _cap(items, r)
            prio_src.append(next((k for k in rk if k[0] == r.target), None))
            for fk in rk:
                index[fk].append(i)
    import heapq
    heap, seq = [], itertools.count()
    bestp = [INF] * len(items)          # dedup: only (re)queue on improvement
    def push(i):
        src = prio_src[i]
        if src is None:
            p = NEGINF
        else:
            lat = prog.fields[src[0]]
            p = lat.observe(store[src[0]].get(src[1], lat.bot))
            if p is None or isinstance(p, _Top): p = INF
            if p == INF: return          # source still ⊥: nothing to propagate
        if p >= bestp[i]: return
        bestp[i] = p
        heapq.heappush(heap, (p, next(seq), i))
    order = list(range(len(items)))
    if rng is not None: rng.shuffle(order)
    for i in order: push(i)
    # 前線下界の維持。pop される値は単調非減少なので、いま pop した値は
    # **まだ確定していない全セルの最終値の下界** である。これが一番安い上界 U。
    bnd = {f for f in stats.get('here', ()) if f in getattr(prog, 'bounded', ())}
    # 下界に依存するガードを持つ規則実例。**下界が上がったら真偽が変わりうる**ので、
    # 「読んだセルが動いたら再発火」だけでは足りない。閉包を消費する側の再発火である。
    relaxed_items = [i for i, (r, _e, _t, _k) in enumerate(items)
                     if any(_ubound_guard(g, bnd) for g in r.guards)]
    for f in bnd:
        BOUND[f] = 0 if not store[f] else min(
            [prog.fields[f].observe(v) for v in store[f].values()] or [0])
        SETTLED[f] = set()
    while heap:
        p, _, i = heapq.heappop(heap)
        if p > bestp[i]: continue        # stale entry
        moved = False
        for f in bnd:
            if isinstance(p, (int, float)) and p != NEGINF and p != BOUND.get(f):
                BOUND[f] = p; moved = True
        if moved:
            for q in relaxed_items: push(q)
        bestp[i] = INF
        r, env, tgt, rk = items[i]
        for f in bnd:                    # pop された時点でその座標は確定
            src = prio_src[i]
            if src is not None and src[0] == f: SETTLED[f].add(src[1])
        if stats.get('budget') and stats['joins'] >= stats['budget']:
            stats['stopped'] = True; return
        ch = _contribute(r, env, store, prog, stats)
        if ch:
            stats['rounds'] += 1
            _bump(stats, prog, rules, r, tgt, rk, True, store, env)
            if stats['rounds'] > FIRE_BUDGET:
                raise LattixError("fire budget exhausted (ascending chain too long)")
            for j in index.get((r.target, tgt), ()):
                push(j)
    for f in bnd:
        BOUND[f] = INF      # 層が終われば、未確定のセルは ⊥ = 到達不能 = INF


def _ekey(e):
    """式の正準な文字列。同じ文字列なら同じ環境で同じ値になる。"""
    k = e[0]
    if k in ('int', 'str', 'bool', 'var'): return f"{k}:{e[1]}"
    if k == 'fref': return f"f:{e[1]}({','.join(_ekey(x) for x in e[2])})"
    if k in ('bin', 'cmp', 'fn'): return f"{k}:{e[1]}({_ekey(e[2])},{_ekey(e[3])})"
    if k == 'geq': return f"geq({_ekey(e[1])},{_ekey(e[2])})"
    if k == 'ctor': return f"c:{e[1]}({','.join(_ekey(x) for x in e[2])})"
    if k in ('not', 'bnot'): return f"{k}({_ekey(e[1])})"
    if k == 'set': return "set(" + ",".join(sorted(_ekey(x) for x in e[1])) + ")"
    return repr(e)


def _affine(e):
    """座標の式を **基点 + 定数** に割る。基点は不透明でよい（同じ式なら同じ値）。

    `i` も `tnum[i]` も等しく基点になる。だから鎖は、地の座標に沿っていても
    *計算された* 座標に沿っていても、同じ一つの判定で掃ける。"""
    if e[0] == 'int': return (None, e[1])
    if e[0] == 'bin' and e[1] in ('+', '-'):
        a, b = _affine(e[2]), _affine(e[3])
        if a is None or b is None: return None
        if a[0] is not None and b[0] is not None: return None
        if b[0] is None:
            return (a[0], a[1] + b[1] if e[1] == '+' else a[1] - b[1])
        if e[1] == '-': return None
        return (b[0], a[1] + b[1])
    return (_ekey(e), 0)


def sweep_plan(prog, rules):
    """この SCC は **座標順に一度なめるだけ**で最小不動点に達するか。

    Dijkstra は *値* で並べる。値は実行しないと分からないので、優先度キューが要る。
    だがずれが構文で分かるなら、**座標そのものが細胞グラフの位相順序**である ——
    順序は幾何から只で出てくるので、キューも再発火も要らない。

    条件（規則の形だけで判定できる。データを見ない）:
      * 目標キーはすべて束縛変数の affine（場の読みをキーに使わない）
      * この SCC が書く場の読みは、**ただ一つの座標**で定数ずれ、残りは同一式
      * そのずれの符号が SCC 全体で一致する
      * ずれ 0 の同座標依存（`a[i] <- b[i]`, `b[i] <- a[i-1]`）は非巡回で、
        その位相順が同じ座標の中での発火順になる

    これは Fast Sweeping（Boué–Dupuis 1999 / Zhao 2005）だが、
    ここでは偏微分方程式の特性線ではなく **規則のずれベクトル**から出ている。
    返り値: (座標番号, +1 昇順 / -1 降順, 同座標内の規則順)。無理なら None。"""
    here = {r.target for r in rules}
    ids = {r.id: n for n, r in enumerate(rules)}
    dim = sign = None
    same = [[] for _ in rules]          # 同座標の依存（位相順に並べる辺）

    def settled(e):
        """キーの基点は、この SCC が回っている間 **動かない** ものに限る。"""
        bad = []
        _walk(e, lambda n: bad.append(1) if (
            n[0] == 'ctor' or (n[0] == 'fref' and n[1] in here)) else None)
        return not bad

    for r in rules:
        if not all(settled(k) for k in r.keys): return None
        tk = [_affine(k) for k in r.keys]
        if any(a is None for a in tk): return None
        refs = []
        for e in [r.value] + list(r.guards) + list(r.keys):
            _walk(e, lambda n: refs.append(n) if n[0] == 'fref' else None)
        for n in refs:
            if n[1] not in here: continue
            if not all(settled(x) for x in n[2]): return None
            rk = [_affine(x) for x in n[2]]
            if len(rk) != len(tk) or any(a is None for a in rk): return None
            diff = [(i, b[1] - a[1]) for i, (a, b) in enumerate(zip(tk, rk)) if a != b]
            for i, off in diff:
                a, b = tk[i], rk[i]
                if a[0] is None or b[0] is None or a[0] != b[0]: return None
            if len(diff) > 1: return None
            if not diff:                       # 同じ座標を読む: 位相順で足りる
                for w in rules:
                    if w.target == n[1] and w.id != r.id:
                        same[ids[w.id]].append(ids[r.id])
                continue
            d, off = diff[0]
            if off == 0: return None
            s = 1 if off < 0 else -1
            if dim is None: dim, sign = d, s
            elif (dim, sign) != (d, s): return None
    if dim is None: return None
    # 同座標依存の位相順（巡回していたら一掃では足りない）
    n = len(rules); indeg = [0] * n
    for u in range(n):
        for v in same[u]: indeg[v] += 1
    q = [i for i in range(n) if indeg[i] == 0]; order = []
    while q:
        u = q.pop(); order.append(u)
        for v in same[u]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    if len(order) != n: return None
    rank = [0] * n
    for pos, u in enumerate(order): rank[u] = pos
    return dim, sign, {rules[i].id: rank[i] for i in range(n)}


def run_stratum_sweep(rules, prog, store, rng, stats, plan):
    """座標順の一掃。各セルは一度で確定する（キューも優先度も要らない）。

    掃いたあと **もう一度なめて、何も動かないことを確かめる**。
    証明が正しければ二度目は空振りで終わる。空振りしなければ証明が間違っている
    ので、そのまま収束するまで掃く（答えは正しいままで、記録だけが残る）。"""
    dim, sign, rank = plan
    items = []
    for r in rules:
        for env in bindings(r, prog, rng, store):
            rk = set()
            for e in r.keys + [r.value] + r.guards:
                read_keys(e, env, store, prog.fields, rk)
            tgt = tuple(ev(x, env, store, prog.fields) for x in r.keys)
            c = tgt[dim]
            if not isinstance(c, int) or isinstance(c, bool):
                return False       # 座標が並べられない: 掃けない
            items.append(((c * sign, rank[r.id]), r, env, tgt, rk))
            _cap(items, r)
    items.sort(key=lambda it: it[0])
    passes = 0
    while True:
        passes += 1
        moved = False
        for _k, r, env, tgt, rk in items:
            if stats.get('budget') and stats['joins'] >= stats['budget']:
                stats['stopped'] = True; return
            stats['key'] = None
            if _contribute(r, env, store, prog, stats):
                moved = True
                stats['rounds'] += 1
                if _bump(stats, prog, rules, r, stats.get('key') or tgt, rk, True, store, env):
                    moved = True
        if not moved: break
        if passes > 64:
            raise LattixError("sweep did not converge")
    stats['sweeps'] = stats.get('sweeps', 0) + passes
    if passes > 2: stats['sweep_dirty'] = stats.get('sweep_dirty', 0) + 1
    return True


def _certificate_allows_priority(prog, rules):
    fs = {r.target for r in rules} | {f for r in rules for f in r.reads}
    for f in fs:
        if prog.fields[f].name != 'min':
            return False
        if prog.certificates.get(f, ("UNPROVEN",))[0] != "CERTIFIED":
            return False
    return True


def run_stratum_adversarial(rules, prog, store, rng, stats):
    """Not a production scheduler -- a falsifier.

    It fires guard-bearing rules as early as possible and re-fires depth-first
    (LIFO), which is the worst case for any analysis that wrongly claims a
    read is monotone: a guard gets evaluated while the field it reads is still
    far from its fixpoint.  discover.py runs this alongside random seeds."""
    items, index = [], defaultdict(list)
    stats['here'] = {r.target for r in rules}
    for r in sorted(rules, key=lambda r: (-len(r.guards), r.id)):
        for env in bindings(r, prog, rng, store):
            rk = set()
            for e in r.keys + [r.value] + r.guards:
                read_keys(e, env, store, prog.fields, rk)
            tgt = tuple(ev(x, env, store, prog.fields) for x in r.keys)
            i = len(items); items.append((r, env, tgt, rk))
            for fk in rk: index[fk].append(i)
    work = list(range(len(items)))
    queued = [True] * len(items)
    while work:
        i = work.pop()                      # LIFO: deepest re-propagation
        queued[i] = False
        r, env, tgt, rk = items[i]
        ch = _contribute(r, env, store, prog, stats)
        if ch:
            stats['rounds'] += 1
            _bump(stats, prog, rules, r, tgt, rk, True, store, env)
            if stats['rounds'] > FIRE_BUDGET:
                raise LattixError("fire budget exhausted")
            for j in index.get((r.target, tgt), ()):
                if not queued[j]:
                    queued[j] = True; work.append(j)


ENGINES = {'naive': run_stratum_naive,
           'adversarial': run_stratum_adversarial,
           'worklist': run_stratum_worklist,
           'priority': run_stratum_priority}



def run(prog, seed=None, engine='auto', out=None, budget=None, ranks=False,
        host=None):
    BOUND.clear(); SETTLED.clear()   # 前線下界は実行ごと。大域に持ち越さない
    out = out if out is not None else sys.stdout
    rng = random.Random(seed) if seed is not None else None
    store = {f: {} for f in prog.fields}
    stats = {'joins': 0, 'rounds': 0, 'engines': [], 'budget': budget,
             'stopped': False, 'here': set()}
    if ranks: stats['rank'] = {}; stats['pre'] = {}; stats['prerank'] = {}
    t0 = time.time()
    delivered = stats['delivered'] = {ch: set() for ch, _ in prog.channels}
    stats['roundtrips'] = 0; stats['io_rounds'] = 0
    for si, s in enumerate(prog.strata):
        if not s: continue
        # 層の中を SCC に割り、凝縮グラフの位相順に回す。
        # 層は「協調の回数」を決めるだけで、**その中の順序までは決めていない**。
        groups = defaultdict(list)
        for r in s: groups[r.scc].append(r)
        rank = getattr(prog, 'scc_rank', {})
        for c in sorted(groups, key=lambda c: rank.get(c, c)):
            g = groups[c]
            pick = engine if engine != 'auto' else (
                'priority' if _certificate_allows_priority(prog, g) else 'worklist')
            # 上界で層を落としたなら、実行系は前線下界を維持する義務を負う。
            # それができるのは優先度スケジューラだけなので、選択の余地は無い。
            if getattr(prog, 'relaxed', False): pick = 'priority'
            if pick == 'priority' and not getattr(prog, 'relaxed', False) \
               and not _certificate_allows_priority(prog, g):
                pick = 'worklist'  # the certificate is the licence; no licence, no Dijkstra
            # 区間は **答えが決める供給**である。上端が育てば実例が増えるので、
            # 実例表を一度作って終わりにはできない。毎回数え直す。
            plan = (sweep_plan(prog, g)
                    if pick == 'worklist' and engine == 'auto' else None)
            # **実例が多すぎたら表を捨てる。** 途中まで作った表は寄与を
            # 一つも入れていないので、そのまま数え直す側へ渡してよい。
            try:
                if plan is not None and run_stratum_sweep(g, prog, store, rng,
                                                          stats, plan):
                    stats['engines'].append('sweep')
                else:
                    stats['engines'].append(pick)
                    ENGINES[pick](g, prog, store, rng, stats)
            except _TooManyItems:
                if stats['engines'] and stats['engines'][-1] == pick:
                    stats['engines'].pop()
                stats['engines'].append('naive')
                run_stratum_naive(g, prog, store, rng, stats)
        if host is not None:
            before = stats['roundtrips']
            _flush(prog, store, host, delivered, stats)
            if stats['roundtrips'] > before:
                stats['io_rounds'] = stats.get('io_rounds', 0) + 1
    stats['seconds'] = time.time() - t0

    if prog.ctors and '_size' in store:
        cap = min(b for _fs, b in prog.ctors.values())
        deep = [k for k, v in store['_size'].items() if v > cap]
        if deep:
            raise LattixError(
                f"construction exceeded the declared bound {cap}: "
                f"{len(deep)} node(s) deeper than that.\n"
                f"    A constructor's `bound` is the well-founded measure that makes\n"
                f"    construction terminate. Raise it deliberately, or make the\n"
                f"    recursion structural.")
    # **矛盾した値は座標になれない。** 黙って飛ばすと、その寄与が「起きたか
    # 起きなかったか」が日程で変わる —— discover 第2部が反例を出した。
    # 座標に使う読みを単調と言えるのは ⊥ → v で止まるあいだだけである。
    bad = stats.get('topkey')
    if bad:
        # 構成子が作る補助の場（`_size` / `<構成子>_<場>`）は最後に回す ——
        # 人が書いた場の名前で言うほうが、直す場所に近い。
        aux = {'_size'} | {f"{c}_{x}" for c, (xs, _b) in prog.ctors.items()
                           for x in xs}
        f, ln = sorted(bad, key=lambda t: (t[0] in aux, t[0], t[1]))[0]
        raise LattixError(
            f"line {ln}: a contradictory value was used as a coordinate of `{f}`"
            f" ({len(bad)} rule(s) hit this).\n"
            f"    ⊥ and ⊤ are not coordinates. A cell two rules disagree about\n"
            f"    has no name, so nothing can be filed under it — and whether the\n"
            f"    contribution happened would depend on the schedule.\n"
            f"    REPAIR: make the writers agree, or stop indexing by that value.")
    conflicts = []
    for f, lat in prog.fields.items():
        if lat.name == 'fourv':
            continue          # TOP means "both", a first-class Belnap value
        for k, v in store[f].items():
            if isinstance(lat.observe(v), _Top):
                conflicts.append((f, k))
    # **矛盾した値は座標になれない。**（SPEC「⊥ も ⊤ も座標になれない」）
    # 座標に使う読みが単調なのは、flat の升が ⊥ → v で止まるからである。
    # ⊤ まで行けばその前提が崩れ、寄与が「起きたか起きなかったか」が日程で
    # 変わる。黙って飛ばしていたので、答えが日程に依っていた。**そう言って止まる。**
    # 判定は最後の店だけを見るので、どの日程でも同じことを言う。

    for f in prog.renders:
        # **バイトはバイトである。** 列は座標に住んでいるのだから、
        # 書き出しも文字符号化を通してはならない —— 実行形式を書けなくなる。
        txt = render_text(prog, store, f)
        buf = getattr(out, 'buffer', None)
        if buf is not None and all(ord(c) < 256 for c in txt):
            buf.write(bytes(ord(c) for c in txt)); buf.flush()
        else:
            print(txt, file=out)

    for f in prog.prints:
        lat = prog.fields[f]
        items = sorted(store[f].items(), key=lambda kv: _sortkey(kv[0]))
        if not items:
            print(f"{f}: ⊥ everywhere (no coordinate reached a definite value)",
                  file=out)
        for k, v in items:
            ks = ", ".join(show_val(x, prog, store) for x in k)
            print(f"{f}[{ks}] = {show_val(lat.observe(v), prog, store)}", file=out)
    return store, conflicts, stats


def render_text(prog, store, f):
    """場を座標順に読んで文字列にする。座標が並びを決める —— 実行順序ではない。

    キーは (位置) か (行, 桁) を想定する。どちらも辞書式で並べれば読める順になる。
    値は文字コード（整数）。⊥ の座標は飛ばす。"""
    lat = prog.fields[f]
    out = []
    for k, v in sorted(store[f].items(), key=lambda kv: _sortkey(kv[0])):
        c = lat.observe(v)
        if c is None or isinstance(c, _Top): continue
        try: out.append(chr(int(c)))
        except (TypeError, ValueError): continue
    return "".join(out)


def _flush(prog, store, host, delivered, stats):
    """効果の実体化 = 場の成長の差分を外に出すこと。

    すでに出したものは `delivered` に入っている。だから何度呼ばれても、
    どんな順序でも、何レプリカが合流しても、同じ効果は二度起きない。
    exactly-once を得るために追加の機構は要らない —— 集合が冪等だから。"""
    for ch, fld in prog.channels:
        have = store[fld].get((), frozenset())
        new = [x for x in sorted(have, key=str) if x not in delivered[ch]]
        if not new: continue
        delivered[ch] |= set(new)
        stats['roundtrips'] += 1
        facts = host(ch, new) or {}
        for f, kv in facts.items():
            if f not in prog.fields: continue
            lat = prog.fields[f]
            for k, v in kv.items():
                key = tuple(k) if isinstance(k, (list, tuple)) else (k,)
                cur = store[f].get(key, lat.bot)
                store[f][key] = lat.join(cur, v)


def show_val(v, prog, store, depth=0):
    """**構成した値は、構成した形で見せる。** 内容アドレスは名前であって、
       人に見せるものではない —— `50793508452103897` ではなく
       `because_unary(11, power)` と書く。アクセサ場がそのまま DAG なので、
       住所を引けば構成子と引数が出る（気づき: 記述が二度使われる）。"""
    if depth <= 8 and isinstance(v, int) and not isinstance(v, bool):
        for nm, (fs, _bd) in getattr(prog, 'ctors', {}).items():
            if not fs:
                continue
            first = store.get(f"{nm}_{fs[0]}")
            if first is None or (v,) not in first:
                continue
            args = []
            for a in fs:
                d = store.get(f"{nm}_{a}", {})
                if (v,) not in d:
                    args = None; break
                av = prog.fields[f"{nm}_{a}"].observe(d[(v,)])
                args.append(show_val(av, prog, store, depth + 1))
            if args is not None:
                return f"{nm}({', '.join(args)})"
    return fmt(v)


def _sortkey(t):
    return tuple((0, x, "") if isinstance(x, int) else (1, 0, str(x)) for x in t)


def fmt(v):
    if v is None or v is INF or v is NEGINF: return "⊥"
    if isinstance(v, _Top): return "⊤ CONFLICT"
    if isinstance(v, frozenset):
        return "{" + ", ".join(str(x) for x in sorted(v, key=str)) + "}"
    if isinstance(v, tuple):
        return "[" + ", ".join(str(x) for x in v) + "]"
    if v is True: return "true"
    if v is False: return "⊥"
    return str(v)


def _canon_value(v):
    if isinstance(v, frozenset):
        return "{" + ",".join(sorted(map(repr, v))) + "}"
    if isinstance(v, _FourV): return "T4" if v.v else "F4"
    if isinstance(v, _Top):   return "TOP"
    if isinstance(v, tuple):  return "[" + ",".join(sorted(map(repr, v))) + "]"
    return repr(v)


def digest(prog, store):
    h = hashlib.sha256()
    for f in sorted(store):
        lat = prog.fields[f]
        h.update(f.encode())
        for k in sorted(store[f], key=lambda t: tuple(str(x) for x in t)):
            h.update(repr(k).encode())
            h.update(_canon_value(lat.observe(store[f][k])).encode())
    return h.hexdigest()[:16]


# ==========================================================================
# 7. Content-addressed normal form
# ==========================================================================

def _canon_expr(e, ren):
    k = e[0]
    if k == 'var':
        if e[1] not in ren: ren[e[1]] = f"v{len(ren)}"
        return ren[e[1]]
    if k == 'int': return str(e[1])
    if k == 'str': return json.dumps(e[1])
    if k == 'bool': return "T" if e[1] else "F"
    if k == 'fref': return f"@{e[1]}[{','.join(_canon_expr(x, ren) for x in e[2])}]"
    if k == 'not': return f"(!{_canon_expr(e[1], ren)})"
    if k == 'bnot': return f"(~{_canon_expr(e[1], ren)})"
    if k == 'geq': return f"({_canon_expr(e[1], ren)}⊒{_canon_expr(e[2], ren)})"
    if k == 'set': return "{" + ",".join(sorted(_canon_expr(x, ren) for x in e[1])) + "}"
    if k == 'ctor': return f"{e[1]}<{','.join(_canon_expr(x, ren) for x in e[2])}>"
    if k in ('bin', 'cmp'):
        l, r = _canon_expr(e[2], ren), _canon_expr(e[3], ren)
        if e[1] in ('+', '*', '==', '!='):        # commutative: sort operands
            l, r = sorted((l, r))
        return f"({l}{e[1]}{r})"
    if k == 'fn':
        l, r = sorted((_canon_expr(e[2], ren), _canon_expr(e[3], ren)))
        return f"{e[1]}({l},{r})"
    raise LattixError(f"canon: {e!r}")


def canonical(prog):
    """A normal form that ignores variable names, statement order, rule order,
    operand order of commutative ops, and whitespace.  Two programs with the
    same meaning-by-construction get the same address."""
    lines = []
    for f in sorted(prog.fields):
        lines.append(f"field {f}:{prog.fields[f].name}")
    for t in sorted(prog.tables):
        rows = sorted(prog.tables[t], key=lambda r: tuple(str(x) for x in r))
        lines.append(f"table {t}={json.dumps(rows)}")
    rl = []
    for r in prog.rules:
        ren = {}
        srcs = sorted((src if isinstance(src, str) else
                       "..(" + _canon_expr(src[1], {}) + "," + _canon_expr(src[2], {}) + ")",
                       tuple(vs)) for vs, src in r.sources)
        # 変数の正準名は **束縛点の座標** である。綴りも traversal 順も要らない。
        # de Bruijn（1972）は束縛子を *数えて* 指標にした。座標のある言語では
        # 数える手続きすら要らない —— 束縛点そのものが座標だからである。
        # 同じ表を二度回す規則だけは束縛点で区別できないので、そこは従来通り。
        if len({s for s, _vs in srcs}) == len(srcs):
            for src, vs in srcs:
                for i, v in enumerate(vs): ren[v] = f"b({src},{i})"
        else:
            for src, vs in srcs:
                for v in vs:
                    if v not in ren: ren[v] = f"v{len(ren)}"
        head = f"{r.target}[{','.join(_canon_expr(x, ren) for x in r.keys)}]"
        body = _canon_expr(r.value, ren)
        gs = sorted(_canon_expr(g, ren) for g in r.guards)
        ss = ";".join(f"{src}({','.join(ren[v] for v in vs)})" for src, vs in srcs)
        rl.append(f"{head}<-{body}|{ss}|{','.join(gs)}")
    lines += sorted(rl)
    lines += [f"observe {f}" for f in sorted(set(prog.prints))]
    lines += [f"render {f}" for f in sorted(set(prog.renders))]
    norm = "\n".join(lines)
    return norm, "lx1" + hashlib.sha256(norm.encode()).hexdigest()[:24]



# ==========================================================================
# 7.5  「なぜ」——  答えに理由を尋ねる
# ==========================================================================
# この言語だけができることがある。**どの値にも証人がいる。**
# 階数も、正当化した規則実例も、証明書のために既に全部計算されている。
# 蛇口が無かっただけである。
#
# 三つの問いに答える:
#   値がある  → どの規則がどの束縛で、何を読んで作ったか（導出木）
#   ⊤        → **食い違った二つの寄与**を名指す
#   ⊥        → 書こうとした実例のうち、**どのガードがなぜ偽だったか**
#
# 最後のものが実は一番効く。「なぜ空なのか」はデバッグの第一の問いで、
# printf も breakpoint も無いこの言語では、他に訊く方法が無い。

def _why_contribs(prog, store, f, key):
    """そのセルへ向かった規則実例を全部集める（火を噴かなかったものも）。"""
    out = []
    for r in prog.rules:
        if r.target != f: continue
        for env in bindings(r, prog, None, store):
            try: k = tuple(ev(x, env, store, prog.fields) for x in r.keys)
            except Exception: continue
            if k != key: continue
            bad = None
            for g in r.guards:
                if not _truthy(ev(g, env, store, prog.fields)): bad = g; break
            try: v = None if bad else ev(r.value, env, store, prog.fields)
            except Exception: v = None
            rk = set()
            for e in r.keys + [r.value] + r.guards:
                read_keys(e, env, store, prog.fields, rk)
            out.append((r, env, bad, v, rk))
    return out


def _why_show(prog, e, env):
    """規則の一部を、束縛を当てはめた形で見せる。"""
    def go(x):
        k = x[0]
        if k == 'var': return f"{x[1]}={fmt(env.get(x[1]))}" if x[1] in env else x[1]
        if k == 'int': return str(x[1])
        if k == 'str': return json.dumps(x[1])
        if k == 'bool': return "true" if x[1] else "false"
        if k == 'fref':
            ks = ",".join(str(ev(y, env, {g: {} for g in prog.fields}, prog.fields))
                          if y[0] == 'int' else go(y) for y in x[2])
            return f"{x[1]}[{ks}]"
        if k == 'bin': return f"({go(x[2])} {x[1]} {go(x[3])})"
        if k == 'cmp': return f"({go(x[2])} {x[1]} {go(x[3])})"
        if k == 'not': return f"not {go(x[1])}"
        if k == 'geq': return f"({go(x[1])} is {go(x[2])})"
        if k == 'ctor': return f"{x[1]}({','.join(go(y) for y in x[2])})"
        if k == 'set': return "{" + ",".join(go(y) for y in x[1]) + "}"
        if k == 'fn': return f"{x[1]}({go(x[2])},{go(x[3])})"
        return str(x)
    return go(e)


def why(prog, store, ranks, f, key, out=sys.stdout, indent="", seen=None, budget=40):
    lat = prog.fields[f]
    cur = store[f].get(key, lat.bot)
    val = lat.observe(cur)
    ks = ", ".join(show_val(x, prog, store) for x in key)
    seen = set() if seen is None else seen
    p = lambda s: print(indent + s, file=out)
    p(f"{f}[{ks}] = {show_val(val, prog, store)}")
    if (f, key) in seen or budget <= 0:
        if (f, key) in seen and isinstance(val, _Top):
            # **閉路に戻った。** ループを一周して違う値が戻ってきた、が答えである。
            p("  ↺ 閉路に戻った ——  一周して別の値が戻るので、ここは定数でない")
        else:
            p("  … （既に辿った）" if (f, key) in seen else "  … （深さ打ち切り）")
        return
    seen = seen | {(f, key)}
    cs = _why_contribs(prog, store, f, key)

    if isinstance(val, _Top):
        # ⊤ は **二つの寄与が食い違った**しるし。両方を名指す。
        fired, byv = [], {}
        for r, env, bad, v, rk in cs:
            if bad is not None or v is None: continue
            fired.append((r, env, v, rk))
            byv.setdefault("TOP" if isinstance(v, _Top) else _canon_value(v),
                           (r, env, v, rk))
        picks = list(byv.values())
        if len(picks) >= 2:
            p("  ⊤ ——  食い違った二つの寄与:")
            for r, env, v, rk in picks[:2]:
                p(f"    L{r.lineno}  {_why_show(prog, r.value, env)}  →  {fmt(v)}")
            # ⊤ を運んできた側を辿る（食い違いの源はその先にある）
            for r, env, v, rk in picks[:2]:
                if not isinstance(v, _Top): continue
                for (g, kk) in sorted(rk, key=str):
                    if g in prog.fields and isinstance(
                            prog.fields[g].observe(store[g].get(kk, prog.fields[g].bot)),
                            _Top):
                        why(prog, store, ranks, g, kk, out, indent + "      ",
                            seen, budget - 1)
                        return
            return
        p("  ⊤ ——  上流から伝わってきた（食い違いは別の場所で起きた）")
        for r, env, v, rk in fired:
            for (g, kk) in sorted(rk, key=str):
                if g in prog.fields and isinstance(
                        prog.fields[g].observe(store[g].get(kk, prog.fields[g].bot)),
                        _Top):
                    why(prog, store, ranks, g, kk, out, indent + "    ",
                        seen, budget - 1)
                    return
        return

    if lat.is_bot(cur):
        # **なぜ空なのか。** 火を噴かなかった実例と、その理由を見せる。
        if not cs:
            p("  ⊥ ——  この座標へ向かう規則実例が一つも無い")
            return
        p(f"  ⊥ ——  向かった実例 {len(cs)} 件。止まった理由:")
        for r, env, bad, v, rk in cs[:6]:
            if bad is not None:
                p(f"    L{r.lineno}  ガード `{_why_show(prog, bad, env)}` が偽")
            elif v is None:
                p(f"    L{r.lineno}  本体が ⊥（読んだ場のどれかが未定）")
            else:
                p(f"    L{r.lineno}  値 {fmt(v)} は吸収された")
        return

    # 確定値: **最短の導出**を選ぶ（階数がそれを知っている）
    best, bestk = None, None
    for r, env, bad, v, rk in cs:
        if bad is not None or v is None: continue
        if lat.observe(v) != val: continue      # 正当化は「等しいとき」だけ
        m = max([ranks.get(g, {}).get(kk, 0) for (g, kk) in rk] or [0])
        if best is None or m < bestk: best, bestk = (r, env, v, rk), m
    if best is None:
        p("  （この答えを作った寄与が見つからない —— 証明書が壊れている）"); return
    r, env, v, rk = best
    p(f"  ← L{r.lineno}  {f}[{','.join(_why_show(prog, x, env) for x in r.keys)}]"
      f" <- {_why_show(prog, r.value, env)}")
    for (g, kk) in sorted(rk, key=str):
        if g in prog.fields and kk in store[g] and (g, kk) != (f, key):
            why(prog, store, ranks, g, kk, out, indent + "      ", seen, budget - 1)


def why_query(prog, store, ranks, q, out=sys.stdout):
    """`dist[5]` / `cvin[3,y]` / `f` を読んで答える。"""
    toks = tokenize(q, 0)
    p = Parser(toks, 0, prog.ctors)
    e = p.expr()
    if e[0] == 'var':
        f = e[1]
        if f not in prog.fields: raise LattixError(f"unknown field {f!r}")
        tops = [k for k, v in store[f].items()
                if isinstance(prog.fields[f].observe(v), _Top)]
        ks = tops or sorted(store[f], key=_sortkey)[:1]
        if not ks:
            print(f"{f}: ⊥ everywhere", file=out); return
        for k in ks[:3]: why(prog, store, ranks, f, k, out)
        return
    if e[0] != 'fref':
        raise LattixError("why: 場の参照を書く（例: dist[5]）")
    key = tuple(x[1] for x in e[2])
    if e[1] not in prog.fields: raise LattixError(f"unknown field {e[1]!r}")
    why(prog, store, ranks, e[1], key, out)

# ==========================================================================
# 8. CLI
# ==========================================================================

def report(prog, depth, stats=None, out=sys.stdout):
    n = len(prog.rules)
    W = 68
    p = lambda s="": print(s, file=out)
    p("─" * W)
    p(f"  LATTIX v{VERSION}   —   ordering derived, not written")
    p("─" * W)
    p(f"  rules (a sequential language would totally order these) : {n}")
    p(f"  MINIMAL SEQUENTIAL DEPTH  (proved optimal)              : {depth}")
    if depth:
        p(f"  order-free parallelism  (rules per stratum, mean)       : {n/depth:.1f}")
    p(f"  blocking round trips with the world                     : {prog.io}")
    p(f"  barriers the programmer wrote                           : 0")
    p("─" * W)
    for i, s in enumerate(prog.strata):
        names = "  ∥  ".join(f"{r.target}(L{r.lineno})" for r in sorted(s, key=lambda r: r.lineno))
        p(f"  stratum {i}:  {names}")
    if prog.critical_path:
        p(f"  critical path : " + " ⟶ ".join(prog.critical_path))
    p("─" * W)
    p("  termination certificates")
    for f in sorted(prog.certificates):
        st, why = prog.certificates[f]
        mark = "✓" if st == "CERTIFIED" else ("·" if st == "VACUOUS" else "?")
        p(f"   {mark} {f:<14} {st:<10} {why}")
    if stats:
        p("─" * W)
        p(f"  scheduler chosen by certificate : {', '.join(stats['engines'])}")
        p(f"  joins performed : {stats['joins']}   "
          f"fires : {stats['rounds']}   time : {stats['seconds']*1000:.1f} ms")
    p("─" * W)


def explain(prog, out=sys.stdout):
    p = lambda s="": print(s, file=out)
    p("─" * 68)
    p("  why each surviving barrier survives")
    p("─" * 68)
    p("  field senses (how the observed value moves as the store climbs):")
    for f in sorted(prog.sense):
        p(f"     {f:<20} {prog.sense[f]}")
    any_ = False
    for r in prog.rules:
        det = []
        tgt_req = {'DOWN': 'DOWN'}.get(prog.sense.get(r.target), 'UP')
        nm = set()
        for e in r.keys: classify(e, 'COORD', True, prog.sense, nm, det)
        classify(r.value, tgt_req, True, prog.sense, nm, det)
        for g in r.guards: classify(g, 'UP', True, prog.sense, nm, det)
        if det:
            any_ = True
            p(f"  line {r.lineno}  ({r.target}, stratum {r.stratum}):")
            for f, why in det:
                p(f"     ✗ {f}: {why}")
    if not any_:
        p("  none — every read in this program is monotone. depth is 1 and irreducible.")
    p("─" * 68)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lattix — sequence is a derived quantity")
    ap.add_argument('file')
    ap.add_argument('--plan', action='store_true', help='show the derived schedule')
    ap.add_argument('--json', action='store_true', help='machine-readable plan')
    ap.add_argument('--why', metavar='CELL',
                    help='なぜその値になったのかを訊く（例: dist[5]）')
    ap.add_argument('--canonical', action='store_true', help='print the normal form')
    ap.add_argument('--address', action='store_true', help='print the content address only')
    ap.add_argument('--engine', choices=['auto','worklist','naive','priority','adversarial'], default='auto')
    ap.add_argument('--conservative', action='store_true',
                    help='disable polarity analysis (the v0.2 schedule)')
    ap.add_argument('--span', action='store_true',
                    help='report the parallel span (longest derivation chain)')
    ap.add_argument('--barriers', action='store_true',
                    help='explain every surviving barrier')
    ap.add_argument('--distributable', action='store_true',
                    help='report the CALM verdict for this program')
    ap.add_argument('--shuffle', type=int, default=None, metavar='SEED')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args(argv)

    try:
        src = open(a.file, encoding='utf-8').read()
        prog = parse(src)
        check(prog, conservative=a.conservative)
        depth = stratify(prog)
        io_rounds(prog)
        check_budgets(prog, depth)
        certify(prog)
    except LattixError as e:
        print(f"\n\033[31mlattix: rejected\033[0m\n  {e}\n", file=sys.stderr)
        return 2

    norm, addr = canonical(prog)
    if a.address:
        print(addr); return 0
    if a.canonical:
        print(norm); print(f"\n# address: {addr}"); return 0
    if a.json:
        print(json.dumps({
            "version": VERSION, "address": addr, "rules": len(prog.rules),
            "sequential_depth": depth, "io_rounds": prog.io,
            "strata": [[{"id": r.id, "line": r.lineno, "target": r.target,
                         "mono_reads": sorted(r.mono_reads),
                         "nonmono_reads": sorted(r.nonmono_reads)} for r in s]
                       for s in prog.strata],
            "critical_path": prog.critical_path,
            "certificates": {k: {"status": v[0], "reason": v[1]}
                             for k, v in prog.certificates.items()},
        }, indent=2, ensure_ascii=False))
        return 0

    try:
        store, conflicts, stats = run(prog, seed=a.shuffle, engine=a.engine,
                                      out=(open('/dev/null', 'w')
                                           if (a.quiet or a.why) else None),
                                      ranks=(a.span or bool(a.why)))
    except LattixError as e:
        print(f"\n\033[31mlattix: runtime\033[0m\n  {e}\n", file=sys.stderr)
        return 3

    if a.distributable:
        d = distributability(prog, depth)
        print("─" * 68)
        print(f"  coordination-free (CALM) : "
              f"{'YES' if d['coordination_free'] else 'NO'}")
        print(f"  global barriers required : {d['barriers_required']}")
        print(f"  {d['verdict']}")
        print("─" * 68)
    if a.why:
        R = defaultdict(dict)
        for (f, k), v in (stats.get('rank') or {}).items(): R[f][k] = v
        why_query(prog, store, R, a.why)
        return 0
    if a.barriers:
        explain(prog)
    if a.span:
        R = stats.get('rank', {})
        per = defaultdict(int)
        for (f, k), r in R.items(): per[f] = max(per[f], r)
        span = max(per.values(), default=0)
        print("─" * 68)
        print("  PARALLEL SPAN (longest chain of derivations)")
        print("  層深度が『協調が何回要るか』なら、スパンは『並列にしても何段かかるか』。")
        print("  最適化とは、命令を並べ替えることではなく、この鎖を短くすることである。")
        print("─" * 68)
        for f in sorted(per):
            print(f"    {f:<24} span {per[f]:>6}   cells {len(store[f]):>7}")
        print(f"    {'TOTAL':<24} span {span:>6}   work {stats['joins']:>7} joins")
        print("─" * 68)
    if a.plan:
        report(prog, depth, stats)
        print(f"  address : {addr}")
    if conflicts:
        # **⊤ は誤りではない。束の頂点である。**
        # 曖昧性検出では ⊤ が診断だが、定数伝播では ⊤ が *答え*（定数でない）
        # である。どちらなのかは言語ではなくプログラムが言うこと ——
        # だから既にある契約の語彙で言わせる: `budget top <= 0`。
        lim = min([n for kind, n, _l in prog.budgets if kind == 'top'],
                  default=None)
        bad = lim is not None and len(conflicts) > lim
        tag = "\033[31mbudget top exceeded\033[0m" if bad else "top (⊤) reached"
        print(f"\nlattix: {tag}  —  {len(conflicts)} coordinate(s)", file=sys.stderr)
        for f, k in conflicts[:20]:
            print(f"  {f}[{', '.join(map(str,k))}] joined two different values → ⊤",
                  file=sys.stderr)
        if bad: return 4
    return 0




# ==========================================================================
# 8.5 領域 — 大域バリアを廃す
# ==========================================================================
#
# 逐次深度は *規則* レベルで計算される。だが協調が本当に要るのは *セル* レベルである。
# 「層1は層0の完了を待つ」と言うとき、実際に待つ必要があるのは
# **そのセルの祖先だけ** であって、層0の全部ではない。
#
# 独立な連結成分が k 個あれば、大域バリア1個は **k 個の独立した局所バリア** に分解する。
# 実測で k=16 のとき 27.4 倍の過剰同期だった。
#
# 解き方は v1.5 と同じ形である —— セル依存グラフを SCC 分解して位相順に処理する。
# 違いは、**層をまたいで** 処理すること。SCC の位相順は「祖先が先」を保証するので、
# 非単調な読み（＝そのセルが確定していることの要求）は自動的に満たされる。
# **大域バリアは一度も張らなくてよい。**
#
# そしてこれはストリーミングと同じ機構である。ウォーターマークが時間座標の領域を
# 閉じるのと、SCC の完了が依存グラフの領域を閉じるのは、同じことをしている。

def poset(items, n=None):
    """**D —— 依存の半順序。処理系にこれ一つしか無い。**

    items は [(書き先, [読み先])] のリストで、セルの名前は「番号でも組でも
    ハッシュできれば何でもよい」。解釈実行はセルを (場, 座標) の組で、
    ネイティブは密配列のスロット番号で呼ぶ。**同じ D を見ている。**

    返すもの:
      comp    セル -> 領域番号（SCC）
      level   領域 -> 最長路の深さ。**pop 順ではない**（v1.6 の事故）
      height  max(level)+1  = 避けられない逐次段数
      width   同じ深さにある領域の最大数 = 構造が許す並列度
      lvl     項目 -> 深さ / order 深さ順の項目 / bounds 深さの境目
      preds, succs, cells, cellid

    半順序を全順序に潰さないこと。比較不能な領域には順序制約が *存在しない*。
    """
    cellid, cells = {}, []
    def cid(c):
        if c not in cellid:
            cellid[c] = len(cells); cells.append(c)
        return cellid[c]
    if n is not None:                       # 密スロット（ネイティブ）
        cells = list(range(n)); cellid = {i: i for i in range(n)}
        cid = lambda c: c
    edges = defaultdict(list)
    tg = []
    for tgt, rds in items:
        t = cid(tgt); tg.append(t)
        for c in rds: edges[cid(c)].append(t)
    m = len(cells)
    comp, ncomp = _tarjan_scc(m, [edges.get(i, []) for i in range(m)])
    csucc = defaultdict(set); cpred = defaultdict(set); indeg = defaultdict(int)
    for u, vs in edges.items():
        for v in vs:
            if comp[u] != comp[v] and comp[v] not in csucc[comp[u]]:
                csucc[comp[u]].add(comp[v]); cpred[comp[v]].add(comp[u])
                indeg[comp[v]] += 1
    q = [c for c in range(ncomp) if indeg[c] == 0]
    level = [0] * ncomp; deg = dict(indeg)
    while q:
        c = q.pop()
        for b in csucc.get(c, ()):
            if level[b] < level[c] + 1: level[b] = level[c] + 1
            deg[b] -= 1
            if deg[b] == 0: q.append(b)
    lvl = [level[comp[t]] for t in tg]
    height = (max(lvl) + 1) if lvl else 0
    order = sorted(range(len(items)), key=lambda i: (lvl[i], tg[i]))
    bounds, seen = [0] * (height + 1), 0
    for h in range(height):
        while seen < len(order) and lvl[order[seen]] == h: seen += 1
        bounds[h + 1] = seen
    wide = Counter(level[c] for c in range(ncomp))
    return {'comp': comp, 'ncomp': ncomp, 'level': level, 'lvl': lvl,
            'height': height, 'width': (max(wide.values()) if wide else 0),
            'order': order, 'bounds': bounds, 'preds': cpred, 'succs': csucc,
            'cells': cells, 'cellid': cellid, 'tgt': tg}


def _cell_refs(e, out=None):
    out = [] if out is None else out
    k = e[0]
    if k == 'fref':
        out.append((e[1], e[2]))
        for x in e[2]: _cell_refs(x, out)
    elif k in ('bin', 'cmp', 'fn'):
        _cell_refs(e[2], out); _cell_refs(e[3], out)
    elif k == 'geq':
        _cell_refs(e[1], out); _cell_refs(e[2], out)
    elif k in ('not', 'bnot'):
        _cell_refs(e[1], out)
    elif k in ('set', 'ctor'):
        for x in (e[1] if k == 'set' else e[2]): _cell_refs(x, out)
    return out


def _cell_poset(prog, rng=None):
    """規則実例を並べて D を呼ぶ。D の計算はここには無い（poset が唯一）。"""
    store = {f: {} for f in prog.fields}
    inst = []                       # (rule, env, tgt_cell, read_cells)
    for r in prog.rules:
        for env in bindings(r, prog, rng, store):
            try:
                tgt = (r.target, tuple(ev(x, env, store, prog.fields) for x in r.keys))
            except Exception:
                continue
            rds = set()
            for e in r.keys + [r.value] + r.guards:
                for f, ix in _cell_refs(e):
                    try:
                        rds.add((f, tuple(ev(x, env, store, prog.fields) for x in ix)))
                    except Exception:
                        pass
            inst.append((r, env, tgt, rds))
    P = poset([(t, rds) for (_r, _e, t, rds) in inst])
    # キー式が場を読むなら、セルの名前が実行中に生まれる。事前の分解は *近似* になる。
    exact = not any(_cell_refs(k) for r in prog.rules for k in r.keys)
    P.update(exact=exact, inst=inst,
             cid=lambda c: P['cellid'][c])
    return P


def cell_regions(prog, rng=None):
    """D を *深さごとの束* に落とした形。同じ深さは互いに独立である。"""
    P = _cell_poset(prog, rng)
    order = defaultdict(list)
    for i, h in enumerate(P['lvl']):
        order[h].append(i)
    return P['inst'], order, P['ncomp'], len(P['cells']), P


def region_closure(P, regs):
    """領域集合を **下方集合（down-set）** に閉じる。祖先を全部入れる。

    半順序 P の下方集合の全体は、包含で分配束をなす（Birkhoff 1937）。
    つまり「どこまで終わったか」自体が束の要素であり、
    別々に進んだ二つの実行の合流は **和集合＝join** である。
    完全性の証明書が、答えと同じように合成できる理由がここにある。"""
    out, stack = set(regs), list(regs)
    while stack:
        c = stack.pop()
        for p in P['preds'].get(c, ()):
            if p not in out: out.add(p); stack.append(p)
    return out


def run_regional(prog, out=None, rng=None, upto=None, regions=None, ranks=False):
    """領域ごとに実行する。大域バリアを一度も張らない。

    返り値の `finished` は「各セルが確定した領域番号」で、
    これが **領域ごとの完全性証明** の土台になる:
    領域 r まで処理した時点で、rank ≤ r のセルは *最終値* である。"""
    out = out if out is not None else sys.stdout
    store = {f: {} for f in prog.fields}
    stats = {'joins': 0, 'rounds': 0, 'here': set(prog.fields), 'support': 0,
             'budget': None, 'regions': 0, 'global_barriers': 0}
    if ranks: stats['rank'] = {}; stats['pre'] = {}; stats['prerank'] = {}
    inst, order, ncomp, ncells, P = cell_regions(prog, rng)
    stats.update(poset=P, height=P['height'], width=P['width'], ncomp=ncomp)
    finished = {}
    depths = sorted(order)
    if upto is not None: depths = depths[:upto]
    if regions is not None:
        regions = region_closure(P, regions)     # 祖先を含まない下方集合は無い
        stats['regions_run'] = regions
    def keep(i):
        if regions is None: return True
        r, env, tgt, rds = inst[i]
        return P['comp'][P['cellid'][tgt]] in regions
    stats['exact'] = P['exact']
    sweeps = 0
    while True:
      sweeps += 1
      moved_any = False
      for rk in depths:
        idx = [i for i in order[rk] if keep(i)]
        if not idx: continue
        if rng is not None: rng.shuffle(idx)   # 同じ深さの中に順序は無い
        if sweeps == 1: stats['regions'] += 1
        changed = True
        while changed:                       # 領域内だけ不動点を取る
            changed = False
            moved_any |= False
            for i in idx:
                r, env, tgt, rds = inst[i]
                stats['key'] = None
                ch = _contribute(r, env, store, prog, stats)
                if ch: changed = moved_any = True
                if ranks and stats['key'] is not None:
                    # 階数は *全部の* 読みを見て付ける（層内に限らない）。
                    # 検査器は層内しか要求しないので、これは安全側である。
                    if ch or (stats.get('support') == 2
                              and prog.fields[r.target].name in WTA):
                        live = set()
                        for e in r.keys + [r.value] + r.guards:
                            read_keys(e, env, store, prog.fields, live)
                        _bump(stats, prog, None, r, stats['key'], live, ch, None, env)
        for i in idx:
            finished[inst[i][2]] = rk
      # 分解が正確なら一巡で終わる。**巡目が増えたらそれは近似だったということ。**
      if P['exact'] or not moved_any or sweeps > 64: break
    stats['sweeps'] = sweeps
    return store, stats, finished, ncells


# ==========================================================================
# 9. Session — the same program, run four ways
# ==========================================================================
#
# A batch run, an incremental update, a replicated run, and an arbitrary
# schedule are FOUR DIFFERENT PROGRAMS in Python / Rust / C.  Here they are
# one program, because contributions are joins:
#
#   * adding facts can only grow the store  -> incremental is just "keep going"
#   * joins commute and are idempotent      -> replicas merge with no protocol
#   * no write destroys information         -> no lock, no ownership, no race
#
# The compiler's sequential depth is exactly the CALM boundary:
#   depth == 1  <=>  the program is monotone  <=>  coordination-free.
# That is not a slogan here; `--distributable` prints it.

class Session:
    """A persistent store you can keep adding facts to."""

    def __init__(self, src, engine='auto'):
        self.src = src
        self.prog = parse(src)
        check(self.prog)
        self.depth = stratify(self.prog)
        io_rounds(self.prog)
        certify(self.prog)
        self.engine = engine
        self.store = {f: {} for f in self.prog.fields}
        self.total = {'joins': 0, 'rounds': 0, 'bindings': 0}
        self._items = {}     # stratum -> list[(rule, env, tgt)]
        self._index = {}     # stratum -> {(field,key): [item ids]}
        self._seeded = set()
        self._rank = {}      # (場,キー) -> 階数
        self._just = {}      # (場,キー) -> (読んだセル, 使った表の行) = **支持**

    # -- facts ------------------------------------------------------------
    def add(self, table, rows):
        """Add ground facts. Returns the rows that were genuinely new."""
        if table not in self.prog.tables:
            raise LattixError(f"unknown table {table!r}")
        have = set(self.prog.tables[table])
        new = [tuple(r) for r in rows if tuple(r) not in have]
        self.prog.tables[table].extend(new)
        return new

    # -- retraction -------------------------------------------------------
    def retract(self, table, rows):
        """事実を消す。**追加しかできない世界に「変わる」を入れる。**

        削除は単調ではない。だが構造は既に持っている:

          * どのセルがどのセルから導かれるかは D が知っている（索引がある）
          * **削除後の答えは、削除前の答え以下である**（事実が減れば導かれるものも減る）

        二つ目が効く。削除前の答えがそのまま **上界 U** になる。だから

          1. 消えた事実から前向きに届く範囲を ⊥ に戻す（過剰削除。DRed）
          2. 生き残った支えから育て直す（下界 L が ⊥ から上がる）
          3. **L が U に届いたセルは、そこで確定** —— それ以上は育ちえない

        3 が上界の使いどころである。DRed は「消して、作り直す」までだが、
        上界を持っていれば **作り直しの途中で止められる**。
        """
        if table not in self.prog.tables:
            raise LattixError(f"unknown table {table!r}")
        gone = {tuple(r) for r in rows}
        keep = [r for r in self.prog.tables[table] if tuple(r) not in gone]
        removed = len(self.prog.tables[table]) - len(keep)
        self.prog.tables[table] = keep
        st = {'joins': 0, 'rounds': 0, 'bindings': 0, 'here': set(),
              'support': 0, 'budget': None, 'reset': 0, 'capped': 0}
        if not removed: return st

        upper = {}                      # (場, キー) -> 削除前の値 = 上界 U
        for f, d in self.store.items():
            for k, v in d.items(): upper[(f, k)] = v

        # 1. 過剰削除: 影響が届きうるセルを ⊥ に戻す
        #
        # ここを一度、**依存の全閉包**で歩いていた。「このセルを読みうる規則実例が
        # あるか」で閉じるので、密なグラフでは全体に届き、削減が 1.0× になった。
        # だが消えるかどうかを決めるのは「読みうるか」ではなく
        # **いまの値が何に支えられているか** である。そして支持は既に名指してある ——
        # 階数を書いたとき、処理系はその値を作った実例を一つ選んでいる（`_just`）。
        # 検査のために作った証人が、そのまま削除の前線になる。
        # 支えが無事なセルは触らない。触らなかったセルは、値が変わらないことが
        # **導出が生きているという理由で**言える（削除後 ⊑ 削除前 なので等号）。
        self._items.clear(); self._index.clear()
        J = self._just
        seeds = set()
        # **支持が全セルを覆っていなければ使わない。** 支持の無いセルは前線に
        # 乗らないので、消し忘れが静かに残る。覆っていないなら全閉包へ落ちる ——
        # 遅いのは構わないが、黙って間違えるのは構う（不変条件8）。
        covered = all((f, k) in J for f, d in self.store.items() for k in d)
        if J and covered:
            for c, (_rds, rows) in J.items():
                if any(tb == table and rw in gone for tb, rw in rows):
                    seeds.add(c)
            frontier = {(c, rds) for c, (rds, _rows) in J.items()}
        else:
            # 証人が無い（階数を取っていない実行）。安全側 —— 全閉包に戻す。
            frontier = set()
            for si, rules in enumerate(self.prog.strata):
                for r in rules:
                    for env in bindings(r, self.prog, None):
                        tgt = (r.target, tuple(ev(x, env, self.store,
                                                  self.prog.fields) for x in r.keys))
                        rds = set()
                        for e in r.keys + [r.value] + r.guards:
                            read_keys(e, env, self.store, self.prog.fields, rds)
                        frontier.add((tgt, frozenset(rds)))
            for r in self.prog.rules:
                for row in gone:
                    for vs, src in r.sources:
                        if not isinstance(src, str) or src != table: continue
                        env = dict(zip(vs, row))
                        try:
                            seeds.add((r.target, tuple(ev(x, env, self.store,
                                                          self.prog.fields)
                                                       for x in r.keys)))
                        except Exception: pass
        reach = set(seeds)
        changed = True
        while changed:
            changed = False
            for tgt, rds in frontier:
                if tgt in reach: continue
                if rds & reach: reach.add(tgt); changed = True
        for (f, k) in reach:
            if k in self.store.get(f, {}):
                del self.store[f][k]; st['reset'] += 1

        # 2-3. 育て直す。上界に届いたら、そのセルはもう動かない
        st['upper'] = upper
        for si, rules in enumerate(self.prog.strata):
            if rules: self._run(si, rules, st, None, only=reach)
        st.pop('upper', None)
        return st

    # -- evaluation -------------------------------------------------------
    def solve(self, delta=None):
        """Run to fixpoint.  `delta` maps table -> newly added rows; when it is
        given, only rule instances touching a new fact are generated."""
        st = {'joins': 0, 'rounds': 0, 'bindings': 0, 'here': set(),
              'support': 0, 'budget': None,
              # **証人を捨てない。** 階数と、その階数を書いた実例が読んだもの。
              # 検査のために作るものだが、撤回の前線もこれで引ける。
              'rank': self._rank, 'just': self._just}
        for si, rules in enumerate(self.prog.strata):
            if not rules:
                continue
            if si > 0 and delta is not None:
                # A non-monotone stratum reads a field it does not own, so a
                # growing input can *retract* one of its conclusions.  Only
                # stratum 0 is incrementalisable for free; be honest and
                # recompute the rest.
                for r in rules:
                    self.store[r.target] = {}
                self._items.pop(si, None); self._index.pop(si, None)
            self._run(si, rules, st, delta if si == 0 else None)
        for k in ('joins', 'rounds', 'bindings'):
            self.total[k] = self.total.get(k, 0) + st.get(k, 0)
        return st

    def _run(self, si, rules, st, delta, only=None):
        items = self._items.setdefault(si, [])
        index = self._index.setdefault(si, defaultdict(list))
        seed = []
        gen = _bindings_delta if delta is not None else _bindings_all
        for r in rules:
            for env in gen(r, self.prog, delta):
                rk = set()
                for e in [r.value] + r.guards:
                    read_keys(e, env, self.store, self.prog.fields, rk)
                tgt = tuple(ev(x, env, self.store, self.prog.fields) for x in r.keys)
                i = len(items)
                items.append((r, env, tgt, frozenset(rk)))
                for fk in rk:
                    index[fk].append(i)
                # 撤回のあとは、**影響が届いた範囲に触る実例だけ**を撒く。
                # 全部撒き直すと、削除の仕事量が再計算と同じになる（一度そうなった）。
                if only is None or (r.target, tgt) in only or (rk & only):
                    seed.append(i)
                st['bindings'] += 1
        work = deque(seed)
        queued = set(seed)
        while work:
            i = work.popleft()
            queued.discard(i)
            r, env, tgt, rds = items[i]
            ch = _contribute(r, env, self.store, self.prog, st)
            # **証人をここでも取る。** 取らないと撤回が支持を引けず、
            # 依存の全閉包を歩く羽目になる（それが 1.0× の正体だった）。
            if ch or st.get('support') == 2:
                _bump(st, self.prog, None, r, st.get('key') or tgt,
                      rds, ch, self.store, env)
            if ch:
                st['rounds'] += 1
                for j in index.get((r.target, tgt), ()):
                    if j not in queued:
                        queued.add(j); work.append(j)

    # -- observation ------------------------------------------------------
    def digest(self):
        return digest(self.prog, self.store)

    def show(self, out=None):
        out = out if out is not None else sys.stdout
        for f in self.prog.prints:
            lat = self.prog.fields[f]
            for k, v in sorted(self.store[f].items(), key=lambda kv: _sortkey(kv[0])):
                key = ', '.join(show_val(x, self.prog, self.store) for x in k)
                val = show_val(lat.observe(v), self.prog, self.store)
                print(f"{f}[{key}] = {val}", file=out)


def _bindings_all(rule, prog, _delta):
    yield from bindings(rule, prog, None)


def _bindings_delta(rule, prog, delta):
    """Bindings in which at least one source row is new (Δ(A×B) decomposition).
    Duplicates are possible and harmless -- joins are idempotent."""
    if not rule.sources:
        return
    if any(not isinstance(src, str) for _v, src in rule.sources):
        yield from bindings(rule, prog, None); return
    srcs = [(vs, prog.tables[src], delta.get(src, [])) for vs, src in rule.sources]
    k = len(srcs)
    seen = set()
    for i in range(k):
        if not srcs[i][2]:
            continue
        pools = [srcs[j][2] if j == i else srcs[j][1] for j in range(k)]
        for combo in itertools.product(*pools):
            if combo in seen:
                continue
            seen.add(combo)
            env = {}
            for (vs, _, _), row in zip(srcs, combo):
                for n, v in zip(vs, row):
                    env[n] = v
            yield env


def merge_stores(prog, *stores):
    """Pointwise join.  This is the whole replication protocol.  There is no
    conflict resolution because a join cannot conflict."""
    out = {f: {} for f in prog.fields}
    for s in stores:
        for f, d in s.items():
            lat = prog.fields[f]
            tgt = out[f]
            for k, v in d.items():
                cur = tgt.get(k, lat.bot)
                if isinstance(cur, _Top) or isinstance(v, _Top):
                    tgt[k] = TOP
                else:
                    tgt[k] = lat.join(cur, v)
    return out


def distributability(prog, depth):
    return {
        "sequential_depth": depth,
        "coordination_free": depth == 1,
        "barriers_required": max(depth - 1, 0),
        "verdict": ("monotone: replicas may run independently and merge by join, "
                    "with no coordination protocol (CALM)")
                   if depth == 1 else
                   (f"non-monotone: {depth-1} global barrier(s) required; the "
                    f"critical path is " + " -> ".join(prog.critical_path)),
    }


if __name__ == '__main__':
    sys.exit(main())
