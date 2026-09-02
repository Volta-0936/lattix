#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lattix — データを *実行時に読む* C バックエンド。Python から離れるための最初の一段。

`native.py` は地上データを静的配列に焼く。速いが、**データが変わるたびに Python が要る**
（50万辺で約20秒）。「実行に Python は要らない」と言えなかった理由はここにあった。

ここが生成するのは **プログラムだけを焼いた C** である。規則は表の行に対するループになり、
表は実行時にファイルから読む。同じ実行ファイルが、別のデータで何度でも走る。

  gcc -O2 prog.c -o prog     一度だけ
  ./prog data.lxd            以後、Python は一度も通らない

対応する断片（それ以外は Unsupported を投げる。黙って間違えない）:
  * 束: min / max / or / and
  * 座標: 整数のみ、深さは任意
  * 規則: 表からの束縛、算術、比較、`not`、場の参照
  * 外界: `emit` は出した集合の *差分* を `EMIT <ch> <値>` として書き出す。
    `source` はデータファイルの `field <名> <行数> <次数+1>` から読む。
    **往復は実行ファイルを呼び直すこと** —— 逐次深度がその回数である。
  * スケジューラ: 証明書が licence すれば **二分ヒープ（Dijkstra）**、
    そうでなければ **半素朴**（変化したセルから引ける索引を起動時に作る）。

半素朴評価は gcc には *原理的に* できない変換である。「同じ規則を全部の行に
撃ち直しても答えは変わらないが、変化したセルに繋がる行だけ撃てば足りる」——
これは join が冪等・単調であることから来る *意味の* 性質で、C の意味論には無い。
**どの規則がどのセルに触るかを、こちらはコンパイル時に全部知っている。**

スケジューラの選択（掃引・ヒープ・領域）はまだ焼き込み側にしかない。
**構造の解析はコンパイル時、データは実行時** という分け方が正しいので、
索引と日程を実行時に組み立てるのが次の段になる。
"""
from __future__ import annotations
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lattix as L
import native as N
from collections import defaultdict

BOT = {'min': "INT64_MAX", 'max': "INT64_MIN", 'or': "0", 'and': "1",
       'flat': "INT64_MIN", 'fourv': "INT64_MIN", 'sum': "0", 'count': "0",
       'bag': "0"}
# **fourv は flat である** —— 値が二つ（F=1 / T=2）しか無く、否定が
# 二つを入れ替えるだけの flat 束である。⊥ も ⊤ も同じ約束で置ける。
F4, T4 = "1", "2"
CMP = {'min': "<", 'max': ">", 'or': ">", 'and': "<"}
TOPV = "INT64_MAX"          # flat の ⊤（矛盾）
SCALAR = ('min', 'max', 'or', 'and', 'flat', 'fourv')
AGG = ('sum', 'count', 'bag')


def analyse(prog):
    """実行時モードで扱える形か確かめ、場ごとの次数を返す。"""

    for f, lat in prog.fields.items():
        if lat.name not in BOT and lat.name != 'set':
            raise N.Unsupported(f"lattice `{lat.name}` is outside the runtime fragment")
    # 集約は寄与元キーで冪等になっている。実行時側では **一度しか撃たない印**
    # （FIRED ビット）でそれを実体化する。値が場を読むなら形が変わるので拒む。
    for r in prog.rules:
        if prog.fields[r.target].name == 'set' and r.value[0] not in ('set', 'fref'):
            raise N.Unsupported("set field needs a set literal or a set field")
    arity = {}
    for r in prog.rules:
        for k in r.keys:
            if k[0] not in ('var', 'int', 'bin', 'fref', 'ctor'):
                raise N.Unsupported("key expression outside the runtime fragment")
        arity.setdefault(r.target, len(r.keys))
        if arity[r.target] != len(r.keys):
            raise N.Unsupported(f"field {r.target} used with two arities")
        # **読みは区間の端にも居る。** `for (j) in 0 .. ndep[i] - 1` の `ndep` を
        # 数え落としていたので、次数 1 の場が次数 0 と見なされ、外から来た行が
        # 全部同じセルに積まれた —— 落ちずに *違う答え* が出た（不変条件8 の破れ）。
        # 読みを数える場所は、キー・値・ガード・**区間の端** の四つである。
        reads = (N._frefs(r.value) + [x for g in r.guards for x in N._frefs(g)]
                 + [x for k in r.keys for x in N._frefs(k)]
                 + [x for _v, sc in r.sources if not isinstance(sc, str)
                    for e in (sc[1], sc[2]) for x in N._frefs(e)])
        for f, ix in reads:
            arity.setdefault(f, len(ix))
            if arity[f] != len(ix):
                raise N.Unsupported(f"field {f} used with two arities")
    for f in prog.fields: arity.setdefault(f, 0)
    return arity


def dense_ok(prog, arity):
    """密配列で足りるか。**足りるときだけ許される配置**であって、一般形ではない。

    座標集合が閉じて箱に入ると *証明できた* ときは密配列（添字が算術で出る）。
    構成子があると座標は実行中に生まれるので、証明できない。そのときはハッシュ表。
    """
    if prog.ctors: return False
    at = atoms(prog)
    def code(x):
        if isinstance(x, bool): return 1 if x else 0
        if isinstance(x, str): return at[x]
        return int(x)
    span = 1 + slack(prog)
    for rows in prog.tables.values():
        for row in rows:
            for x in row: span = max(span, code(x) + 1)
    # **宣言した広さは、いま手元にある表より優先する。** 実行時読込では
    # 表があとから差し替わるので、いまのデータで箱を測ったら、次のデータで
    # 箱からはみ出す（`bound` と実際に空けた場所が食い違う —— 気づき44）。
    for f, b in prog.field_bound.items():
        w = max(b) if isinstance(b, tuple) else b
        span = max(span, w + 1)
        if span > 8_000_000: return False
    for f, ar in arity.items():
        if span ** max(ar, 1) > 8_000_000: return False
    return True


def valkinds(prog):
    """場の *値* が真偽か原子か整数か。C は整数しか見ないので、戻すときに要る。"""
    colkind = {}
    for t, rows in prog.tables.items():
        for row in rows:
            for i, x in enumerate(row):
                k = 'atom' if isinstance(x, str) else 'int'
                if colkind.setdefault((t, i), k) != k:
                    # **原子と整数は C では同じ整数空間に住んでいる。**
                    # 混ざった列は戻すときに区別できない（原子の 0 番と距離の 0）。
                    # 黙って違う答えを出すより、そう言って落ちる（不変条件8）。
                    raise N.Unsupported(
                        f"table {t!r} column {i} mixes atoms and integers; "
                        f"the native representation cannot tell them apart")
    out = {}
    for f, lat in prog.fields.items():
        out[f] = ('bool' if lat.name in ('or', 'and')
                  else 'fourv' if lat.name == 'fourv' else 'int')
    for r in prog.rules:
        lat = prog.fields[r.target].name
        if lat in ('or', 'and', 'set', 'fourv'): continue
        e = r.value
        if e[0] == 'str': out[r.target] = 'atom'
        elif e[0] == 'var':
            for vs, src in r.sources:
                if not isinstance(src, str): continue      # 区間の座標は整数
                if e[1] in vs and colkind.get((src, vs.index(e[1]))) == 'atom':
                    out[r.target] = 'atom'
    return out


def kinds(prog):
    """座標と集合要素が「整数」か「原子」かを、場ごとに決める。

    C の側は整数しか見ない。だから **戻すときにどちらだったかを知る必要がある**。
    ここを混ぜると、距離の 0 が原子の 0 番に化ける（実際に化けた）。"""
    colkind = {}
    for t, rows in prog.tables.items():
        for row in rows:
            for i, x in enumerate(row):
                k = 'atom' if isinstance(x, str) else 'int'
                if colkind.setdefault((t, i), k) != k:
                    # **原子と整数は C では同じ整数空間に住んでいる。**
                    # 混ざった列は戻すときに区別できない（原子の 0 番と距離の 0）。
                    # 黙って違う答えを出すより、そう言って落ちる（不変条件8）。
                    raise N.Unsupported(
                        f"table {t!r} column {i} mixes atoms and integers; "
                        f"the native representation cannot tell them apart")
    key, elem = {}, {}
    def kind_of(e, r):
        if e[0] == 'str': return 'atom'
        if e[0] in ('int', 'bin'): return 'int'
        if e[0] == 'var':
            for vs, src in r.sources:
                if not isinstance(src, str): continue      # 区間の座標は整数
                if e[1] in vs: return colkind.get((src, vs.index(e[1])), 'int')
        return 'int'
    for r in prog.rules:
        for d, e in enumerate(r.keys):
            k = kind_of(e, r)
            if k == 'atom': key[(r.target, d)] = 'atom'
            key.setdefault((r.target, d), 'int')
        if prog.fields[r.target].name == 'set' and r.value[0] == 'set':
            for x in r.value[1]:
                if kind_of(x, r) == 'atom': elem[r.target] = 'atom'
            elem.setdefault(r.target, 'int')
    # **写しは要素の種別も写す。** `f[x] <- g[y]` の f の要素は g の要素である。
    for _ in range(len(prog.rules) + 1):
        moved = False
        for r in prog.rules:
            if prog.fields[r.target].name != 'set': continue
            if r.value[0] != 'fref': continue
            src = elem.get(r.value[1])
            if src == 'atom' and elem.get(r.target) != 'atom':
                elem[r.target] = 'atom'; moved = True
            elem.setdefault(r.target, 'int')
        if not moved: break
    return key, elem


def ctor_kinds(prog):
    """構成子の引数ごとに、原子か整数かを決める。

    **内容アドレスは「意味」で計算しなければならない。** C の中で原子は整数の符号だが、
    符号は機械の都合であって意味ではない。符号で hash すると、
    「別マシンで独立に作っても同じ名前」が壊れる（実際に木の葉の名前が食い違った）。
    だから原子の引数は、名前のバイト列で符号化する。"""
    colkind = {}
    for t, rows in prog.tables.items():
        for row in rows:
            for i, x in enumerate(row):
                k = 'atom' if isinstance(x, str) else 'int'
                if colkind.setdefault((t, i), k) != k:
                    # **原子と整数は C では同じ整数空間に住んでいる。**
                    # 混ざった列は戻すときに区別できない（原子の 0 番と距離の 0）。
                    # 黙って違う答えを出すより、そう言って落ちる（不変条件8）。
                    raise N.Unsupported(
                        f"table {t!r} column {i} mixes atoms and integers; "
                        f"the native representation cannot tell them apart")
    out = {}
    def kind_of(e, r):
        if e[0] == 'str': return 'atom'
        if e[0] == 'var':
            for vs, src in r.sources:
                if not isinstance(src, str): continue      # 区間の座標は整数
                if e[1] in vs: return colkind.get((src, vs.index(e[1])), 'int')
        return 'int'
    for r in prog.rules:
        cs = []
        for e in r.keys + [r.value] + r.guards: N.L.__dict__  # noqa
        for e in r.keys + [r.value] + r.guards:
            _collect_ctors(e, cs)
        for c in cs:
            ks = out.setdefault(c[1], [None] * len(c[2]))
            for i, a in enumerate(c[2]):
                k = kind_of(a, r)
                if ks[i] is None: ks[i] = k
                elif ks[i] != k:
                    raise N.Unsupported(f"constructor {c[1]} arg {i} mixes atoms and integers")
    return {k: ['int' if x is None else x for x in v] for k, v in out.items()}


def _collect_ctors(e, out):
    k = e[0]
    if k == 'ctor':
        out.append(e)
        for x in e[2]: _collect_ctors(x, out)
    elif k == 'fref':
        for x in e[2]: _collect_ctors(x, out)
    elif k in ('bin', 'cmp', 'fn'): _collect_ctors(e[2], out); _collect_ctors(e[3], out)
    elif k == 'geq': _collect_ctors(e[1], out); _collect_ctors(e[2], out)
    elif k in ('not', 'bnot'): _collect_ctors(e[1], out)
    elif k == 'set':
        for x in e[1]: _collect_ctors(x, out)
    return out


def slack(prog):
    """キー式に現れる定数のずれ（`fib[t+1]` の +1）。密配列の余白になる。

    座標は本来いくらでも増える。密配列にする以上どこかで区切るしかないので、
    **プログラムから読み取れるぶんだけ**余白を取り、超えたら実行時に落とす。
    黙って壊れるより落ちる方がよい（不変条件8）。"""
    sl = 0
    def walk(e):
        nonlocal sl
        if e[0] == 'int':                      # 座標位置の定数そのもの
            sl = max(sl, abs(e[1]))
        elif e[0] == 'bin' and e[1] == '+':
            for x in (e[2], e[3]):
                if x[0] == 'int': sl = max(sl, abs(x[1]))
            walk(e[2]); walk(e[3])
        elif e[0] in ('bin', 'cmp', 'fn'): walk(e[2]); walk(e[3])
    for r in prog.rules:
        for e in r.keys: walk(e)
        for f, ix in N._frefs(r.value) + [x for g in r.guards for x in N._frefs(g)]:
            for e in ix: walk(e)
    return sl


def atoms(prog):
    """原子（文字列）に整数の符号を割り当てる。**C は文字列を一度も見ない。**

    符号はプログラムとデータの両方から集めて、決まった順に振る。
    データファイルの側で既に符号化しておくので、実行ファイルは整数しか読まない。
    座標の空間 C を、機械の側の語彙（整数）へ移す写像である。"""
    seen = set()
    def walk(e):
        k = e[0]
        if k == 'str': seen.add(e[1])
        elif k in ('bin', 'cmp', 'fn'): walk(e[2]); walk(e[3])
        elif k == 'geq': walk(e[1]); walk(e[2])
        elif k in ('not', 'bnot'): walk(e[1])
        elif k == 'set':
            for x in e[1]: walk(x)
        elif k == 'fref':
            for x in e[2]: walk(x)
    for r in prog.rules:
        for e in r.keys + [r.value] + r.guards: walk(e)
    for t, rows in prog.tables.items():
        for row in rows:
            for x in row:
                if isinstance(x, str): seen.add(x)
    return {v: i for i, v in enumerate(sorted(seen))}


def dijkstra_shape(prog):
    """`f[k] <- f[k'] + w` の形（自分自身を一つだけ読む min 場）か。

    形が合っていて、かつ再帰デルタが非負だと証明されているなら、
    値順の前線＝ Dijkstra が使える。**証明書が licence する。**
    返す: (場, 再帰規則, 基底規則) / 合わなければ None
    """
    mins = [f for f, lat in prog.fields.items() if lat.name == 'min']
    if len(prog.fields) != 1 or len(mins) != 1: return None
    if any(not isinstance(sc, str) for r in prog.rules for _v, sc in r.sources):
        return None
    f = mins[0]
    if prog.certificates.get(f, ('UNPROVEN',))[0] != 'CERTIFIED': return None
    rec, base = [], []
    for r in prog.rules:
        rd = N._frefs(r.value) + [x for g in r.guards for x in N._frefs(g)]
        if not rd: base.append(r); continue
        if len(rd) != 1 or rd[0][0] != f: return None
        if len(rd[0][1]) != 1 or rd[0][1][0][0] != 'var': return None
        if len(r.keys) != 1 or r.keys[0][0] != 'var': return None
        if len(r.sources) != 1: return None
        rec.append(r)
    if len(rec) != 1: return None
    return f, rec[0], base


def cidx(f, idx, ar, V, line=0):
    """添字。次数は実行時に決まるので、大きさは変数で持つ。"""
    if not idx: return "0"
    parts = []
    for d in range(len(idx)):
        e = idx[d]
        x = {'var': lambda: V[e[1]], 'int': lambda: str(e[1])}.get(e[0])
        # 座標は有限の資源である。大きすぎる数を座標にしたら、そう言って止まる。
        # **どの場のどの行か**まで言う（名前を言わない停止は事故の隠れ場所）。
        x = (f"({x()})" if x else
             f'z_coordn({cexpr(e, V)}, "{f}[{d}]", {line})')
        parts.append(f"({x})")
    out = parts[0]
    for d in range(1, len(parts)):
        # **次元ごとに広さが違う。** 一つの DOM で畳むと `bound 16384 16` が
        # 16384×16384 になり、只の場が 2GB になって OOM で殺された。
        out = f"(({out}) * DOM_{f}_{d} + ({parts[d]}))"
    return out


ATOM = {}           # 原子 -> 符号（build が設定する）
DENSE = True        # 密配列で足りるか（足りないならハッシュ表）
ONLY_PRINTS = False # 場を全部出すか、`print` と書いたものだけか
KINDS = ({}, {})    # (座標の種別, 集合要素の種別)
VKINDS = {}         # 場 -> 値の種別
PROG = None         # いま生成しているプログラム（束の名前を引くため）


def _topguards(e, V, ar=None):
    """比較の中の **flat の ⊤** を集める。⊤ は「少なくとも真」なので、
    ここが立ったら比較そのものが立つ（`||` で短絡するので算術も踏まない）。"""
    out = []
    def walk(x):
        if not isinstance(x, tuple) or not x: return
        if x[0] == 'fref':
            if PROG.fields[x[1]].name == 'flat':
                out.append(f"({cexpr(x, V, ar)} == INT64_MAX)")
            return                      # 添字の中は座標であって比べられる値ではない
        if x[0] in ('bin', 'fn'): walk(x[2]); walk(x[3])
    walk(e)
    return out


def _isfourv(e):
    """その式は既に **fourv の値**か（1/2/⊥/⊤ の符号を持っているか）。"""
    if not isinstance(e, tuple) or not e: return False
    if e[0] == 'fref': return PROG.fields[e[1]].name == 'fourv'
    if e[0] == 'bnot': return _isfourv(e[1])
    return False


def _fv(e, lat, V, ar=None):
    """fourv の場に書く値。真偽の式（比較・true/false・`not`）は F=1 / T=2 に
    符号化する —— 解釈実行の `val = FTRUE if val else FFALSE` と同じ判断。"""
    x = cexpr(e, V, ar)
    if lat != 'fourv' or _isfourv(e): return x
    return f"(({x}) ? (i64){T4} : (i64){F4})"


def cexpr(e, V, ar=None):
    k = e[0]
    if k == 'int':  return str(e[1])
    if k == 'str':  return str(ATOM[e[1]])
    if k == 'bool': return "1" if e[1] else "0"
    if k == 'var':  return V[e[1]]
    if k == 'fref':
        f = e[1]
        # **範囲の外は ⊥ である。** 素の添字だと `off[-1]` が配列の手前を読む ——
        # 解釈実行では ⊥ で寄与が消えるところが、C では他人のメモリになる。
        # 黙って違う答えを出す壊れ方で、いちばん質が悪い。
        if DENSE:
            if PROG.fields[f].name == 'set':
                return f"F_{f}[{cidx(f, e[2], ar, V)}]"
            return f"g_{f}({cidx(f, e[2], ar, V)})"

        args = ", ".join(cexpr(x, V, ar) for x in e[2]) or ""
        return f"mget_{f}({args})"
    if k == 'set':
        # **集合は arena の並びの番号**（非密の道）。域の宣言が要らない。
        if DENSE: raise N.Unsupported("set literal needs the dense backend here")
        n = len(e[1])
        if n == 0: return "0"
        xs = ", ".join(f"(i64)({cexpr(x, V, ar)})" for x in e[1])
        return f"({{ i64 _se[{n}] = {{{xs}}}; (i64)smk(_se, {n}); }})"
    if k == 'ctor':
        # 構成された値の名前は内容そのもの（56ビット）。実行時に計算する。
        return f"ctor_{e[1]}(" + ", ".join(cexpr(x, V, ar) for x in e[2]) + ")"
    if k == 'bin':
        fn = {'+': 'z_add', '-': 'z_sub', '*': 'z_mul', '/': 'z_div', '%': 'z_mod'}[e[1]]
        return f"{fn}({cexpr(e[2],V,ar)}, {cexpr(e[3],V,ar)})"
    if k == 'cmp':
        # **⊤ は「少なくとも真」である**（`lattix.ev` と同じ定義）。
        t = _topguards(e[2], V, ar) + _topguards(e[3], V, ar)
        c = f"(z_cmp({cexpr(e[2],V,ar)}, {cexpr(e[3],V,ar)}) {e[1]} 0)"
        return "(" + " || ".join(t + [c]) + ")" if t else c
    if k == 'not':  return f"(!({cexpr(e[1],V,ar)}))"
    if k == 'bnot':
        # **Belnap の否定は単調である** —— T と F を入れ替えるだけで、
        # ⊥ と ⊤ は動かない。だから層を一つも食わない。
        x = cexpr(e[1], V, ar)
        return f"({x} == {F4} ? (i64){T4} : ({x} == {T4} ? (i64){F4} : {x}))"
    if k == 'geq':
        # `x is c`（上方集合の判定）。あらゆる束で単調なので層を消費しない。
        fr = e[1]
        if fr[0] != 'fref': raise N.Unsupported("`is` needs a field on the left")
        lat = PROG.fields[fr[1]].name
        x = cexpr(fr, V, ar); c = cexpr(e[2], V, ar)
        if lat == 'min':   return f"({x} != INT64_MAX && z_cmp({x}, {c}) <= 0)"
        if lat == 'max':   return f"({x} != INT64_MIN && z_cmp({x}, {c}) >= 0)"
        if lat == 'or':    return f"({x} >= (({c})?1:0))"
        if lat == 'and':   return f"({x} <= (({c})?1:0))"
        if lat == 'flat':
            return f"({x} == INT64_MAX || ({x} != INT64_MIN && {x} == {c}))"
        if lat == 'fourv':
            return f"({x} == INT64_MAX || ({x} != INT64_MIN && {x} == (({c})?{T4}:{F4})))"
        if lat in AGG:     return f"(z_cmp({x}, {c}) >= 0)"
        raise N.Unsupported(f"`is` on lattice {lat}")
    raise N.Unsupported(f"expression node {k} outside the runtime fragment")



SHA_PRELUDE = r"""
#include <stdio.h>
#include <stdint.h>
#include <string.h>
/* SHA-256（公開仕様。ここは *信頼しない* 側のコードである） */
typedef struct { uint32_t h[8]; uint64_t n; uint8_t b[64]; size_t l; } sha;
static const uint32_t K[64]={
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
#define R(x,n) (((x)>>(n))|((x)<<(32-(n))))
static void blk(sha*s,const uint8_t*p){uint32_t w[64],a,b,c,d,e,f,g,h,t1,t2;int i;
 for(i=0;i<16;i++)w[i]=(p[i*4]<<24)|(p[i*4+1]<<16)|(p[i*4+2]<<8)|p[i*4+3];
 for(;i<64;i++){uint32_t s0=R(w[i-15],7)^R(w[i-15],18)^(w[i-15]>>3),s1=R(w[i-2],17)^R(w[i-2],19)^(w[i-2]>>10);
  w[i]=w[i-16]+s0+w[i-7]+s1;}
 a=s->h[0];b=s->h[1];c=s->h[2];d=s->h[3];e=s->h[4];f=s->h[5];g=s->h[6];h=s->h[7];
 for(i=0;i<64;i++){uint32_t S1=R(e,6)^R(e,11)^R(e,25),ch=(e&f)^((~e)&g);
  t1=h+S1+ch+K[i]+w[i];uint32_t S0=R(a,2)^R(a,13)^R(a,22),mj=(a&b)^(a&c)^(b&c);t2=S0+mj;
  h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;}
 s->h[0]+=a;s->h[1]+=b;s->h[2]+=c;s->h[3]+=d;s->h[4]+=e;s->h[5]+=f;s->h[6]+=g;s->h[7]+=h;}
static void shai(sha*s){s->h[0]=0x6a09e667;s->h[1]=0xbb67ae85;s->h[2]=0x3c6ef372;s->h[3]=0xa54ff53a;
 s->h[4]=0x510e527f;s->h[5]=0x9b05688c;s->h[6]=0x1f83d9ab;s->h[7]=0x5be0cd19;s->n=0;s->l=0;}
static void shau(sha*s,const uint8_t*p,size_t n){s->n+=n;
 while(n){size_t k=64-s->l; if(k>n)k=n; memcpy(s->b+s->l,p,k); s->l+=k;p+=k;n-=k;
  if(s->l==64){blk(s,s->b);s->l=0;}}}
static void shaf(sha*s,uint8_t*o){uint64_t bits=s->n*8;uint8_t pad=0x80;shau(s,&pad,1);
 uint8_t z=0; while(s->l!=56) shau(s,&z,1);
 uint8_t t[8]; for(int i=0;i<8;i++) t[i]=(uint8_t)(bits>>(56-8*i)); shau(s,t,8);
 for(int i=0;i<8;i++){o[i*4]=s->h[i]>>24;o[i*4+1]=s->h[i]>>16;o[i*4+2]=s->h[i]>>8;o[i*4+3]=s->h[i];}}

/* Lattix の内容アドレス —— **31ビットの法を二本**。128ビット整数が要らない。
     h ← (h·K + enc) mod M     を名前・引数の数・各引数について
     番地 = h1·M2 + h2                                              */
#define LXM1 268435399ULL
#define LXM2 268435367ULL
#define LXK1 1000003ULL
#define LXK2 1000033ULL
static uint64_t lxfold(const char*p, size_t n, uint64_t m, uint64_t k){
  uint64_t h=0; for(size_t i=0;i<n;i++) h=(h*k+(uint64_t)(unsigned char)p[i]+1)%m;
  return h; }
static uint64_t lxenc(int64_t v, const char*nm, int big, const void*bp,
                      uint64_t m, uint64_t k){
  if(nm) return 3*lxfold(nm, strlen(nm), m, k) + 1;
  if(big){ const zbig *zz=(const zbig*)bp; uint64_t r=0;
    for(int j=zz->n-1;j>=0;j--) r=(r*(4294967296ULL%m)+(uint64_t)zz->d[j])%m;
    if(zz->sg<0) r=(m-r)%m;
    return 3*r; }
  int64_t t=v%(int64_t)m; if(t<0) t+=(int64_t)m;
  return 3*(uint64_t)t; }
static uint64_t ctor_one(const char*name, const int64_t*iv, const int*kind, int n,
                         uint64_t m, uint64_t k){
  uint64_t h = lxfold(name, strlen(name), m, k);
  h = (h*k + (uint64_t)n + 1) % m;
  for(int j=0;j<n;j++){
    const char *nm = (kind[j] && iv[j] >= 0 && iv[j] < NATOMS) ? ATOMS[iv[j]] : 0;
    int big = (!nm) && ZISBIG(iv[j]);
    h = (h*k + lxenc(iv[j], nm, big, big ? (const void*)&ZB[ZIDX(iv[j])] : 0, m, k)) % m; }
  return h; }
static uint64_t ctor_id(const char*name, const int64_t*iv, const int*kind, int n){
  return ctor_one(name,iv,kind,n,LXM1,LXK1)*LXM2 + ctor_one(name,iv,kind,n,LXM2,LXK2); }

"""

HASH_PRELUDE = r"""
/* 開番地法のハッシュ表。**密配列が使えないときの一般形。**
   鍵は座標の組（i64 の並び）。値は束の元。 */
typedef struct { i64 *k; i64 *v; char *used; long long cap, n; int ar; } map;
static uint64_t mix(uint64_t x){
  x ^= x>>33; x *= 0xff51afd7ed558ccdULL; x ^= x>>33;
  x *= 0xc4ceb9fe1a85ec53ULL; x ^= x>>33; return x; }
static void mgrow(map *m);
static long long mslot(map *m, const i64 *k){
  uint64_t h = 1469598103934665603ULL;
  for(int i=0;i<m->ar;i++) h = mix(h ^ (uint64_t)k[i]);
  long long i = (long long)(h & (uint64_t)(m->cap-1));
  for(;;){
    if(!m->used[i]) return i;
    int same = 1;
    for(int d=0; d<m->ar; d++) if(m->k[i*m->ar+d] != k[d]) { same = 0; break; }
    if(same) return i;
    i = (i+1) & (m->cap-1);
  } }
static void minit(map *m, int ar, i64 bot){
  m->ar = ar; m->cap = 1024; m->n = 0;
  m->k = (i64*)malloc(sizeof(i64)*(size_t)m->cap*(ar?ar:1));
  m->v = (i64*)malloc(sizeof(i64)*(size_t)m->cap);
  m->used = (char*)calloc((size_t)m->cap, 1); (void)bot; }
static void mgrow(map *m){
  long long oc = m->cap; i64 *ok = m->k, *ov = m->v; char *ou = m->used;
  m->cap *= 2; m->n = 0;
  m->k = (i64*)malloc(sizeof(i64)*(size_t)m->cap*(m->ar?m->ar:1));
  m->v = (i64*)malloc(sizeof(i64)*(size_t)m->cap);
  m->used = (char*)calloc((size_t)m->cap, 1);
  for(long long i=0;i<oc;i++) if(ou[i]){
    long long s = mslot(m, ok + i*m->ar);
    for(int d=0; d<m->ar; d++) m->k[s*m->ar+d] = ok[i*m->ar+d];
    m->v[s] = ov[i]; m->used[s] = 1; m->n++; }
  free(ok); free(ov); free(ou); }
static i64 mget(map *m, const i64 *k, i64 bot){
  long long s = mslot(m, k); return m->used[s] ? m->v[s] : bot; }
static int mput(map *m, const i64 *k, i64 v){
  long long s = mslot(m, k);
  if(!m->used[s]){
    for(int d=0; d<m->ar; d++) m->k[s*m->ar+d] = k[d];
    m->v[s] = v; m->used[s] = 1; m->n++;
    if(m->n*10 >= m->cap*7) mgrow(m);
    return 1; }
  m->v[s] = v; return 0; }
"""

SET_PRELUDE = r"""
/* 集合は **整列した並び**を arena に置き、升にはその番号を入れる。
   番号 0 は空集合（⊥ そのもの）。合流は併合で、写しは番号を共有するだけ。
   要素の域を宣言しなくてよいのが密なビット集合との違いである ——
   走らせる物の面に入る要素は升の値なので、域が先に分からない。 */
static i64 *SARN; static long long SARN_N = 1, SARN_CAP = 0;
static long long sput(const i64 *e, long long n){
  if(n == 0) return 0;
  if(SARN_N + n + 1 > SARN_CAP){
    long long c = SARN_CAP ? SARN_CAP*2 : 4096;
    while(c < SARN_N + n + 1) c *= 2;
    SARN = (i64*)realloc(SARN, sizeof(i64)*(size_t)c); SARN_CAP = c; }
  long long at = SARN_N; SARN[at] = n;
  for(long long i=0;i<n;i++) SARN[at+1+i] = e[i];
  SARN_N = at + n + 1; return at; }
static long long slen(long long s){ return s ? (long long)SARN[s] : 0; }
static long long sunion(long long a, long long b){
  long long na = slen(a), nb = slen(b);
  if(!nb) return a;
  if(!na) return b;
  i64 *t = (i64*)malloc(sizeof(i64)*(size_t)(na+nb));
  const i64 *ea = SARN + a + 1, *eb = SARN + b + 1;
  long long i=0,j=0,k=0;
  while(i<na && j<nb){
    if(ea[i] < eb[j]) t[k++] = ea[i++];
    else if(ea[i] > eb[j]) t[k++] = eb[j++];
    else { t[k++] = ea[i++]; j++; } }
  while(i<na) t[k++] = ea[i++];
  while(j<nb) t[k++] = eb[j++];
  if(k == na){ free(t); return a; }         /* b ⊆ a —— 何も動かない */
  long long r = sput(t, k); free(t); return r; }
static long long sadd(long long a, i64 x){   /* 重複を残す差し込み（bag）*/
  long long na = slen(a);
  i64 *t = (i64*)malloc(sizeof(i64)*(size_t)(na+1));
  const i64 *ea = a ? SARN + a + 1 : 0;
  long long i=0,k=0;
  while(i<na && ea[i] <= x) t[k++] = ea[i++];
  t[k++] = x;
  while(i<na) t[k++] = ea[i++];
  long long r = sput(t, k); free(t); return r; }
static int scmp_(const void*x,const void*y){
  i64 a=*(const i64*)x,b=*(const i64*)y; return a<b?-1:(a>b?1:0); }
static long long smk(const i64 *e, long long n){
  i64 *t = (i64*)malloc(sizeof(i64)*(size_t)n);
  memcpy(t, e, sizeof(i64)*(size_t)n);
  qsort(t, (size_t)n, sizeof(i64), scmp_);
  long long k=0; for(long long i=0;i<n;i++) if(!k || t[k-1]!=t[i]) t[k++]=t[i];
  long long r = sput(t, k); free(t); return r; }
"""


SEMI = False        # 半素朴で回すか（前線を積む）
SEMI_STRATA = set() # そのうち半素朴で回せる層
FUSED = {}          # 座標順に融合して一掃する層 -> [(scc, 表)]
LATS = {}           # 実行ファイル -> 場の束（run は build の残り香に頼らない）
CTX = {}            # 実行ファイル -> (原子表, 座標の種別, 値の種別)
                    # **焼いた道具を取っておいて何度も走らせる**ときに要る ——
                    # 別のプログラムを焼いたあとで古い実行ファイルを走らせると、
                    # 大域変数の残り香で復号が食い違う（束だけ直してあった）。
ALLOW_SEMI = True   # 比較のために切れるようにしておく（既定は入り）


def PUSH(f):
    return f"if(SEMI_ON) wpush(BASE_{f} + _t);" if SEMI else ""


def frefs_all(e, out=None):
    """場の読みを集める。**構成子の引数の中にも入る。**

    `native._frefs` は 'ctor' に降りない（焼き込み側は構成子を扱わないので気づかなかった）。
    そのせいで `cons(c, text[i+1])` の中の読みが ⊥ 検査から漏れ、
    ⊥ から作った名前と本物の名前の二つが同じ flat セルに入って ⊤ に落ちていた。
    実データ 207 文字で 117 トークン中 12 個が ⊤ になり、そこで見つかった。
    **小さな例では出ない。大きな入力は測定器である。**"""
    out = [] if out is None else out
    k = e[0]
    if k == 'fref':
        out.append((e[1], e[2]))
        for x in e[2]: frefs_all(x, out)
    elif k == 'ctor':
        for x in e[2]: frefs_all(x, out)
    elif k in ('bin', 'cmp', 'fn'): frefs_all(e[2], out); frefs_all(e[3], out)
    elif k == 'geq': frefs_all(e[1], out); frefs_all(e[2], out)
    elif k in ('not', 'bnot'): frefs_all(e[1], out)
    elif k == 'set':
        for x in e[1]: frefs_all(x, out)
    return out


def frefs_pos(e, out=None):
    """否定の下を除いた場の読み（添字の中も数える）。"""
    if out is None: out = []
    k = e[0]
    if k == 'fref':
        out.append((e[1], e[2]))
        for x in e[2]: frefs_pos(x, out)
    elif k == 'ctor':
        for x in e[2]: frefs_pos(x, out)
    elif k in ('bin', 'cmp', 'fn'):
        frefs_pos(e[2], out); frefs_pos(e[3], out)
    elif k == 'geq':
        pass                       # `is` は ⊥ を自分で見る
    elif k == 'set':
        for x in e[1]: frefs_pos(x, out)
    return out


def cmpfrefs(e, out=None):
    """比較 `cmp` の中に現れる場の読み（束を問わない）。"""
    if out is None: out = []
    k = e[0]
    if k == 'cmp':
        for x in (e[2], e[3]):
            if x[0] == 'fref': out.append((x[1], x[2]))
        cmpfrefs(e[2], out); cmpfrefs(e[3], out)
    elif k in ('bin', 'fn'):
        cmpfrefs(e[2], out); cmpfrefs(e[3], out)
    elif k in ('not', 'bnot'):
        cmpfrefs(e[1], out)
    elif k == 'fref':
        for x in e[2]: cmpfrefs(x, out)
    return out


def ctruth(e, prog, V, arity):
    """ガードの真偽。**束ごとに ⊥ の読み方が違う。**

    `if tree[i,j,B]` は「その座標が定まっているか」であって、
    i64 の値がゼロでないかではない。flat の ⊥ は INT64_MIN で、
    C の目には真に見える —— そのまま撃つと構成子が ⊥ から無限に木を生やす。
    （実際に無限ループした。束を忘れた瞬間に、答えではなく停止性が壊れる。）"""
    if e[0] == 'fref':
        lat = prog.fields[e[1]].name
        x = cexpr(e, V, arity.get(e[1]))
        if lat == 'fourv':
            # **⊤ は「少なくとも真」**（`lattix._truthy`）
            return f"({x} == {T4} || {x} == {TOPV})"
        if lat in ('min', 'max', 'flat'): return f"({x} != {BOT[lat]})"
        if lat in ('or', 'and'):          return f"({x} != 0)"
        return f"({x} != 0)"
    if e[0] == 'not':
        return f"(!{ctruth(e[1], prog, V, arity)})"
    if e[0] == 'bnot':
        # **Belnap の否定を「値がゼロでない」で読んではいけない。**
        # ~⊥ = ⊥（撃たない）/ ~F = T（撃つ）/ ~T = F（撃たない）/ ~⊤ = ⊤（撃つ）。
        # ⊥ は INT64_MIN なので、C の目にはそのまま真に見える（flat と同じ穴）。
        x = cexpr(e[1], V, arity.get(e[1][1]) if e[1][0] == 'fref' else None)
        return f"({x} == {F4} || {x} == {TOPV})"
    return f"({cexpr(e, V)})"


def fuse_plan(prog, g):
    """この SCC を **座標順の一掃**に融合できるか。

    融合とは、規則ごとに表を回すのをやめて、**行を外側・規則を内側**にすること。
    鎖 `f[i] <- f[i-1]` を規則ごとに回すと、一本目が一掃したあと二本目が値を上げ、
    また一本目が要る —— 掃く回数が入力に比例する。行を外側にすれば一度で済む。

    返り値: (表, 掃く列, 符号, 規則の順) か None。"""
    plan = L.sweep_plan(prog, g)
    if plan is None: return None
    # 源0 が共有の表であればよい。二本目以降の源（`for (d) in 0 .. 15` の区間や
    # 別の表）は行の内側のループになる —— 鎖の座標は源0 の列なので、行を
    # 外側にすれば内側の直積は一行ぶんまとめて閉じる。区間の端がこの SCC の
    # 場を読む形だけは並べられない（端が一掃の途中で育つ）。
    here = {r.target for r in g}
    for r in g:
        if not r.sources or not isinstance(r.sources[0][1], str): return None
        for _v, sc in r.sources[1:]:
            if isinstance(sc, str): continue
            bad = []
            for e in (sc[1], sc[2]):
                L._walk(e, lambda n: bad.append(1)
                        if n[0] == 'fref' and n[1] in here else None)
            if bad: return None
    dim, sign, rank = plan
    src = col = None
    for r in g:
        if not r.sources: return None
        if src is None: src = r.sources[0][1]
        elif r.sources[0][1] != src: return None
        base = L._affine(r.keys[dim])
        if base is None or base[0] is None: return None
        # 基点は源0の列そのもの（場の読みが混ざったら行から並べられない）
        v = base[0][4:] if base[0].startswith('var:') else None
        if v is None or v not in r.sources[0][0]: return None
        c = list(r.sources[0][0]).index(v)
        if col is None: col = c
        elif col != c: return None
    return (src, col, sign, rank)


def _aggvars(r):
    """集約の寄与元キー = **束縛の組そのもの**（`lattix._prov` と同じ同値）。
    源が二つ以上あるとき、最初の源だけで番号を作っていたので、一つの行に
    つき一度しか撃たなかった —— 区間の点ぶんの寄与が丸ごと落ちていた
    （表と区間が同じ規則に並ぶまで露見しない。気づき34 の九度目）。"""
    return [v for vs, _src in r.sources for v in vs]


def agg_idx(r, a, ind, V):
    """寄与元キーの配列を出して、その名前を返す。"""
    vs = _aggvars(r)
    nm = f"_fk{r.id}"
    body = ", ".join(f"(i64)({V[v]})" for v in vs) or "0"
    a(f"{ind}i64 {nm}[{max(len(vs), 1)}] = {{{body}}};")
    return nm


def emit_rule(a, prog, r, arity, indexed=None, push=False, only_new=False, row0=None):
    """一本の規則を、表の行に対するループとして出す。

    `indexed` が与えられたら、全行ではなく **その索引から引いた行だけ** を回す。
    それが半素朴評価で、`push` は変化したセルを次の前線へ積むかどうか。"""
    V, ind = {}, "  "
    # ループを一つも開かない規則（地の事実、あるいは融合で外側を借りた規則）でも
    # ガードと ⊥ 検査は `continue` で書かれている。**囲いが要る。**
    nloops = 0 if indexed is not None else len(r.sources) - (0 if row0 is None else 1)
    wrap = nloops <= 0 and indexed is None
    if wrap:
        a(f"{ind}do{{"); ind += "  "
    if indexed is not None:
        pi = indexed
        src = r.sources[0][1]; vs = r.sources[0][0]
        a(f"{ind}for(int _q=IXS_{r.id}_{pi}[_c]; _q<IXS_{r.id}_{pi}[_c+1]; _q++){{")
        a(f"{ind}  int _r0 = IXL_{r.id}_{pi}[_q];")
        for ci, v in enumerate(vs):
            V[v] = f"T_{src}[(long long)_r0*A_{src}+{ci}]"
        ind += "  "
    else:
      for si, (vs, src) in enumerate(r.sources):
        if si == 0 and row0 is not None:
            # 源0の行は外側の一掃が決めている（融合）
            for ci, v in enumerate(vs):
                V[v] = f"T_{src}[(long long){row0}*A_{src}+{ci}]"
            continue
        if not isinstance(src, str):
            # **座標の空間そのものを回す。** 端は値なので毎回読み直す ——
            # 上端が育てば実例が増える（増えるだけなので単調）。
            # 宣言はループの中に置く: 同じ層の規則どうしで名前が衝突しない。
            lo_e, hi_e = cexpr(src[1], V, None), cexpr(src[2], V, None)
            g = (f"({lo_e}) != INT64_MIN && ({lo_e}) != INT64_MAX && "
                 f"({hi_e}) != INT64_MIN && ({hi_e}) != INT64_MAX")
            a(f"{ind}for(i64 _rv{si}={lo_e}; {g} && _rv{si}<=({hi_e}); _rv{si}++){{")
            V[vs[0]] = f"_rv{si}"
            ind += "  "
            continue
        lo = f"LO_{src}" if only_new and si == 0 else "0"
        a(f"{ind}for(int _r{si}={lo}; _r{si}<N_{src}; _r{si}++){{")
        for ci, v in enumerate(vs):
            V[v] = f"T_{src}[(long long)_r{si}*A_{src}+{ci}]"
        ind += "  "
    lat = prog.fields[r.target].name
    for g in r.guards:
        a(f"{ind}if(!{ctruth(g, prog, V, arity)}) continue;")
    # ⊥ は伝播する。未定の場を読んだ寄与は起きない（解釈実行と同じ規則）。
    # flat を外していたので、⊥ から構成子が木を生やして止まらなくなった。
    # **⊥ の読みは火を噴かない**（どの束でも）。ただし **否定の下は別** ——
    # `not f[…]` は f が ⊥ のときにこそ発火する。だから否定を跨がずに集める。
    for f, ix in frefs_pos(r.value) + [x for g in r.guards for x in frefs_pos(g)]:
        if prog.fields[f].name in BOT:
            a(f"{ind}if({cexpr(('fref', f, ix), V, arity[f])} == {BOT[prog.fields[f].name]}) continue;")
    # **比較の中の読みは、どの束でも ⊥ で発火しない。** or/sum/count の ⊥ は
    # 0 という普通の数に見えるが、比べれば同じ穴に落ちる（気づき27）。
    # 巻き上げて continue にする —— `not (f[x] < 6)` の外側に出す必要がある。
    for g in list(r.guards) + [r.value]:
        for f, ix in cmpfrefs(g):
            clat = prog.fields[f].name      # **join の束を潰さない**（また踏んだ）
            if clat not in ('min', 'max', 'flat', 'fourv') and clat in BOT:
                a(f"{ind}if({cexpr(('fref', f, ix), V, arity[f])} == {BOT[clat]}) continue;")
    # 順序の証人: この寄与が読んだセルの階数の最大
    rk = frefs_all(r.value) + [x for g in r.guards for x in frefs_all(g)] \
         + [x for e in r.keys for x in frefs_all(e)]
    a(f"{ind}int _rk{r.id} = 0;")
    for f, ix in rk:
        if DENSE:
            a(f"{ind}if(r_{f}({cidx(f, ix, arity[f], V)}) > _rk{r.id})"
              f" _rk{r.id} = r_{f}({cidx(f, ix, arity[f], V)});")
        else:
            args = ", ".join(cexpr(x, V, arity.get(f)) for x in ix)
            a(f"{ind}if(rget_{f}({args}) > _rk{r.id}) _rk{r.id} = (int)rget_{f}({args});")
    for e in r.keys:
        for f, ix in frefs_all(e):
            klat = prog.fields[f].name        # **join の束と取り違えない**
            if klat in ('min', 'max', 'flat', 'fourv'):
                # ⊥ も ⊤ も座標になれない（不変条件2）。⊥ は寄与が消えるだけ、
                # **⊤ は誤りである** —— 矛盾した升には名前が無い（定義と同じ）。
                a(f"{ind}if({cexpr(('fref', f, ix), V, arity[f])} == {BOT[klat]}) continue;")
                if klat in ('flat', 'fourv'):
                    a(f'{ind}if({cexpr(("fref", f, ix), V, arity[f])} == INT64_MAX)'
                      f'{{ fprintf(stderr, "a contradictory value was used as a '
                      f'coordinate: {f}\\n"); exit(7); }}')
    if not DENSE:
        ks = ", ".join(cexpr(e, V) for e in r.keys)
        lat = prog.fields[r.target].name
        if lat == 'set':
            # **集合も arena の並びで焼ける。** 合流は併合、写しは番号の共有。
            a(f"{ind}{{ JOINS++;")
            a(f"{ind}  i64 _sv = {cexpr(r.value, V)};")
            a(f"{ind}  if(mjoin_{r.target}({ks}{',' if ks else ''} _sv)){{ changed = 1;")
            a(f"{ind}    rset_{r.target}({ks}{',' if ks else ''} _rk{r.id} + 1); }} }}")
            for _ in (r.sources[1:] if row0 is not None else r.sources):
                ind = ind[:-2]; a(f"{ind}}}")
            if wrap: ind = ind[:-2]; a(f"{ind}}}while(0);")
            return
        if lat in AGG:
            idx = agg_idx(r, a, ind, V)
            a(f"{ind}if(!mget(&FIRED_{r.id}, {idx}, 0)){{ mput(&FIRED_{r.id}, {idx}, 1);")
            v = "1" if lat == 'count' else cexpr(r.value, V)
            a(f"{ind}  mput(&FVAL_{r.id}, {idx}, {v});")
            a(f"{ind}  JOINS++; if(mjoin_{r.target}({ks}{',' if ks else ''} {v}))"
              f" changed = 1; }}")
            a(f"{ind}else if(mget(&FVAL_{r.id}, {idx}, 0) != ({v})){{")
            a(f"{ind}  if(mtop_{r.target}({ks})) changed = 1; }}")
        else:
            a(f"{ind}{{ JOINS++;")
            a(f"{ind}  i64 _nv = {_fv(r.value, lat, V)};")
            a(f"{ind}  if(mjoin_{r.target}({ks}{',' if ks else ''} _nv)){{ changed = 1;")
            a(f"{ind}    rset_{r.target}({ks}{',' if ks else ''} _rk{r.id} + 1); }}")
            a(f"{ind}  else if(mget_{r.target}({ks}) == _nv && "
              f"(rget_{r.target}({ks}) == 0 || _rk{r.id} + 1 < rget_{r.target}({ks})))")
            a(f"{ind}    rset_{r.target}({ks}{',' if ks else ''} _rk{r.id} + 1); }}")
        for _ in (r.sources[1:] if row0 is not None else r.sources):
            ind = ind[:-2]; a(f"{ind}}}")
        if wrap: ind = ind[:-2]; a(f"{ind}}}while(0);")
        return
    key = cidx(r.target, r.keys, arity[r.target], V, r.lineno)
    # **どの場のどの座標か**を言う。黙って落ちるのと、落ちて名前を言うのは違う。
    chk = (f'{ind}  if(_t < 0 || _t >= SZ_{r.target}) {{ fprintf(stderr,'
           f' "coordinate out of range: {r.target}[%lld] (line {r.lineno},'
           f' size %lld)\\n", (long long)_t, (long long)SZ_{r.target}); exit(4); }}')
    if lat == 'set':
        if r.value[0] != 'set':
            raise N.Unsupported("set field needs a set literal (dense backend)")
        a(f"{ind}{{ long long _t = {key}; JOINS++;"); a(chk)
        for x in r.value[1]:
            a(f"{ind}  {{ i64 _b = z_coord({cexpr(x, V)});")
            # **集合の要素も座標である。** 箱の外を書けば黙って壊れる ——
            # 実際に壊れた（emit の値が域を超えて、効果が静かに消えた）。
            a(f'{ind}    if(_b < 0 || _b >= DOM_{r.target}) {{ fprintf(stderr,'
              f' "set element out of range: {r.target} <- %lld (line {r.lineno},'
              f' domain %d)\\n", (long long)_b, DOM_{r.target}); exit(6); }}')
            a(f"{ind}    i64 *_w = &F_{r.target}[_t*WD_{r.target} + (_b>>6)];")
            a(f"{ind}    i64 _m = ((i64)1)<<(_b&63);")
            a(f"{ind}    if(!(*_w & _m)){{ *_w |= _m; changed = 1;"
              f" if(_rk{r.id} + 1 > K_{r.target}[_t]) K_{r.target}[_t] = _rk{r.id} + 1; "
              + PUSH(r.target) + " } }")

        a(f"{ind}}}")
    elif lat in AGG:
        # 一度だけ撃つ = 寄与元キーつき集約。何度なめても答えは同じになる。
        idx = agg_idx(r, a, ind, V)
        a(f"{ind}{{ long long _t = {key}; JOINS++;"); a(chk)
        v = "1" if lat == 'count' else cexpr(r.value, V)
        a(f"{ind}  i64 _av = {v};")
        a(f"{ind}  if(!mget(&FIRED_{r.id}, {idx}, 0)){{ mput(&FIRED_{r.id}, {idx}, 1);")
        a(f"{ind}    mput(&FVAL_{r.id}, {idx}, _av);")
        a(f"{ind}    if(F_{r.target}[_t] != {TOPV}) F_{r.target}[_t] ="
          f" z_add(F_{r.target}[_t], _av); changed = 1;"
          f" if(_rk{r.id} + 1 > K_{r.target}[_t]) K_{r.target}[_t] = _rk{r.id} + 1; "
          + PUSH(r.target) + " }")
        # **同じ寄与元が別の値を置いたら ⊤ である**（`lattix._sum_join` と同じ）。
        a(f"{ind}  else if(mget(&FVAL_{r.id}, {idx}, 0) != _av"
          f" && F_{r.target}[_t] != {TOPV}){{ F_{r.target}[_t] = {TOPV};"
          f" changed = 1; " + PUSH(r.target) + " } }")
    elif lat in ('flat', 'fourv'):
        a(f"{ind}{{ i64 _v = {_fv(r.value, lat, V)}; long long _t = {key}; JOINS++;"); a(chk)
        a(f"{ind}  i64 _c = F_{r.target}[_t];")
        # **影**: 平坦なセルは生涯にただ一つの確定値しか持てない。
        # ⊤ になった瞬間にそれは消えるので、消える前にここで控える ——
        # 閉路で押し上げられた ⊤ の証人は、この値である。
        pre = (f" P_{r.target}[_t] = _v; PK_{r.target}[_t] = _rk{r.id} + 1;"
               if DENSE else "")
        a(f"{ind}  if(_c == {BOT[lat]}){{ F_{r.target}[_t] = _v; changed = 1;"
          f" K_{r.target}[_t] = _rk{r.id} + 1;{pre} " + PUSH(r.target) + " }")
        a(f"{ind}  else if(_c != _v && _c != {TOPV}){{ F_{r.target}[_t] = {TOPV}; changed = 1; " + PUSH(r.target) + " } }")
    else:
        a(f"{ind}{{ i64 _v = {cexpr(r.value, V)}; long long _t = {key}; JOINS++;"); a(chk)
        cnd = (f"(F_{r.target}[_t] == {BOT[lat]} || z_cmp(_v, F_{r.target}[_t]) {CMP[lat]} 0)"
               if lat in ('min', 'max') else f"_v {CMP[lat]} F_{r.target}[_t]")
        a(f"{ind}  if({cnd}){{ F_{r.target}[_t] = _v; changed = 1;")
        a(f"{ind}    K_{r.target}[_t] = _rk{r.id} + 1; {PUSH(r.target)} }}")
        a(f"{ind}  else if(_v == F_{r.target}[_t] && _rk{r.id} + 1 < K_{r.target}[_t])")
        a(f"{ind}    K_{r.target}[_t] = _rk{r.id} + 1;   /* 支持は「等しいとき」だけ */")
        a(f"{ind}}}")
    outer = [0] if indexed is not None else (r.sources[1:] if row0 is not None
                                             else r.sources)
    for _ in outer:
        ind = ind[:-2]; a(f"{ind}}}")
    if wrap: ind = ind[:-2]; a(f"{ind}}}while(0);")


def generate(prog, arity):
    e = []
    a = e.append
    try: shape = dijkstra_shape(prog)
    except Exception: shape = None
    a("/* Lattix — generated once from the PROGRAM. データは実行時に読む。 */")
    a("#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <stdint.h>\n#include <time.h>")
    a("typedef int64_t i64;")
    a(N.Z_PRELUDE)
    a("static long long JOINS=0;")
    for t in prog.tables:
        a(f"static i64 *T_{t}; static int N_{t}, A_{t}, LO_{t};")
    # **hash 表はいつでも要る。** 密配列の道でも、集約の「一度だけ撃つ」印は
    # 実例（束縛の組）で引くので、番号の箱では足りない。
    a(HASH_PRELUDE)
    if any(l.name in ('set', 'bag') for l in prog.fields.values()):
        a(SET_PRELUDE)
    if not DENSE:
        inv = {v: k for k, v in ATOM.items()}
        if prog.ctors:
            names = ",".join('"' + inv[i].replace('"', '\\"') + '"'
                             for i in range(len(inv))) or '""'
            a(f"static const char *ATOMS[] = {{{names}}};")
            a(f"static const int NATOMS = {len(inv)};")
            a(SHA_PRELUDE)
        ck = ctor_kinds(prog)
        for nm, (fs, _bd) in prog.ctors.items():
            n = len(fs)
            kinds_ = ck.get(nm, ['int'] * n)
            args = ", ".join(f"i64 a{i}" for i in range(n))
            arr = ", ".join(f"a{i}" for i in range(n))
            mask = ",".join("1" if kinds_[i] == 'atom' else "0" for i in range(n))
            a(f"static i64 ctor_{nm}({args}){{ i64 _a[{n}] = {{{arr}}};")
            a(f"  static const int _k[{n}] = {{{mask}}};")
            a(f'  return (i64)ctor_id("{nm}", _a, _k, {n}); }}')
    for f in prog.renders:
        if not DENSE:
            ar_ = max(arity[f], 1)
            a(f"static long long *RK_{f};")
            a(f"static int rcmp_{f}(const void *pa, const void *pb){{")
            a(f"  long long x = *(const long long*)pa, y = *(const long long*)pb;")
            a(f"  for(int d=0; d<{ar_}; d++){{")
            a(f"    long long u = RK_{f}[x*{ar_}+d], v = RK_{f}[y*{ar_}+d];")
            a(f"    if(u != v) return u < v ? -1 : 1; }}")
            a(f"  return 0; }}")
    for f in prog.fields:
        if DENSE:
            a(f"static i64 *F_{f}; static long long SZ_{f}; static int DOM_{f};")
            for _d in range(max(arity.get(f, 1), 1)):
                a(f"static int DOM_{f}_{_d};")
            a(f"static int *K_{f};   /* 順序の証人（階数）。検査器が読む */")
            if prog.fields[f].name in ('flat', 'fourv'):
                a(f"static i64 *P_{f}; static int *PK_{f};   /* 影と、その階数 */")
            if prog.fields[f].name != 'set':    # 集合はビット集合。走査で読む
                bot = BOT[prog.fields[f].name]
                a(f"static i64 g_{f}(long long i){{ return (i < 0 || i >= SZ_{f})"
                  f" ? ({bot}) : F_{f}[i]; }}")
            a(f"static int r_{f}(long long i){{ return (i < 0 || i >= SZ_{f})"
              f" ? 0 : K_{f}[i]; }}")
        else:
            ar = arity[f]; lat = prog.fields[f].name
            a(f"static map M_{f}; static map R_{f};   /* 値と階数 */")
            args = ", ".join(f"i64 k{i}" for i in range(ar))
            arr = ", ".join(f"k{i}" for i in range(ar)) or "0"
            a(f"static i64 mget_{f}({args}){{ i64 _k[{max(ar,1)}] = {{{arr}}};")
            a(f"  return mget(&M_{f}, _k, {BOT.get(lat, '0')}); }}")
            a(f"static i64 rget_{f}({args}){{ i64 _k[{max(ar,1)}] = {{{arr}}};")
            a(f"  return mget(&R_{f}, _k, 0); }}")
            a(f"static void rset_{f}({args}{',' if ar else ''} i64 v){{ i64 _k[{max(ar,1)}] = {{{arr}}};")
            a(f"  mput(&R_{f}, _k, v); }}")
            a(f"static int mjoin_{f}({args}{',' if ar else ''} i64 v){{ i64 _k[{max(ar,1)}] = {{{arr}}};")
            if lat in ('min', 'max'):
                op = '<' if lat == 'min' else '>'
                a(f"  i64 c = mget(&M_{f}, _k, {BOT[lat]});")
                a(f"  if(c == {BOT[lat]} || z_cmp(v, c) {op} 0)"
                  f"{{ mput(&M_{f}, _k, v); return 1; }} return 0; }}")
            elif lat in ('or', 'and'):
                op = '>' if lat == 'or' else '<'
                a(f"  i64 c = mget(&M_{f}, _k, {BOT[lat]});")
                a(f"  if(v {op} c){{ mput(&M_{f}, _k, v); return 1; }} return 0; }}")
            elif lat in ('flat', 'fourv'):
                a(f"  i64 c = mget(&M_{f}, _k, {BOT[lat]});")
                a(f"  if(c == {BOT[lat]}){{ mput(&M_{f}, _k, v); return 1; }}")
                a(f"  if(c != v && c != {TOPV}){{ mput(&M_{f}, _k, {TOPV}); return 1; }}")
                a("  return 0; }")
            elif lat == 'set':
                a(f"  long long c = (long long)mget(&M_{f}, _k, 0);")
                a(f"  long long u = sunion(c, (long long)v);")
                a(f"  if(u != c){{ mput(&M_{f}, _k, (i64)u); return 1; }} return 0; }}")
            elif lat == 'bag':
                # **袋は重複を残す並び**（観測は綴りの整列）。⊤ は矛盾の印。
                a(f"  i64 c = mget(&M_{f}, _k, 0);")
                a(f"  if(c == {TOPV}) return 0;")
                a(f"  mput(&M_{f}, _k, (i64)sadd((long long)c, v)); return 1; }}")
                a(f"static int mtop_{f}({args}){{ i64 _k[{max(ar,1)}] = {{{arr}}};")
                a(f"  if(mget(&M_{f}, _k, 0) == {TOPV}) return 0;")
                a(f"  mput(&M_{f}, _k, {TOPV}); return 1; }}")
            else:      # sum / count
                a(f"  i64 c = mget(&M_{f}, _k, 0);")
                a(f"  if(c == {TOPV}) return 0;")
                a(f"  mput(&M_{f}, _k, z_add(c, v)); return 1; }}")
                a(f"static int mtop_{f}({args}){{ i64 _k[{max(ar,1)}] = {{{arr}}};")
                a(f"  if(mget(&M_{f}, _k, 0) == {TOPV}) return 0;")
                a(f"  mput(&M_{f}, _k, {TOPV}); return 1; }}")
        if prog.fields[f].name == 'set':
            a(f"static int WD_{f};   /* 一セルあたりのワード数（要素領域はビット集合） */")
    for r in prog.rules:
        if prog.fields[r.target].name in AGG:
            a(f"static map FIRED_{r.id};  /* 寄与元キーの実体化: 一度しか撃たない */")
            a(f"static map FVAL_{r.id};   /* その寄与が置いた値（変われば ⊤）*/")
    a("static int MAXC = 0;")
    # 外から与えられた場の行は、場の確保が済むまで保管する（座標領域がまだ決まらない）
    a("static char SEEDF[4096][64]; static int SEEDA[4096];")
    a("static long long SEEDV[4096][8]; static int NSEED = 0;")
    a(f"#define SLACK {slack(prog)}")
    # ---- データ読み込み --------------------------------------------------
    a("""
static void load_into(const char *path, int append){
  FILE *fp = fopen(path, "r");
  if(!fp){ fprintf(stderr, "cannot open %s\\n", path); exit(2); }
  char name[128]; int nrows, ar;
  for(;;){
    if(fscanf(fp, "%127s", name) != 1) break;
    i64 *buf = 0;
    if(!strcmp(name, "field")){
      /* `field <名> <行数> <次数+1>` —— 外から与える場（source）。
         最後の列が値、前の列が座標。join で入れるので順序も重複も関係ない。 */
      char fld[128]; int nr, aw;
      if(fscanf(fp, "%127s %d %d", fld, &nr, &aw) != 3) break;
      for(int k2=0;k2<nr;k2++){
        long long tmp[8]; 
        for(int c2=0;c2<aw;c2++){
          long long v2; if(fscanf(fp, "%lld", &v2) != 1){ fprintf(stderr,"bad data\\n"); exit(2); }
          /* **座標の広さを決めるのは座標だけである。** 最後の列は値であって
             座標ではない。値まで数えていたので、mtime のような大きな数を
             source で渡すと領域が壊れた（int への切り詰めで size 1 になる）。 */
          tmp[c2]=v2; if(c2 + 1 < aw && v2 > MAXC) MAXC=(int)v2; }
        if(NSEED < 4096){ strncpy(SEEDF[NSEED], fld, 63);
          SEEDA[NSEED] = aw; for(int c2=0;c2<aw;c2++) SEEDV[NSEED][c2]=tmp[c2]; NSEED++; }
      }
      continue;
    }
    if(!strcmp(name, "bytes")){
      /* `bytes <表> <パス>` —— ファイルの中身を (位置, 文字コード) の表として読む。
         **列は座標に住んでいる。** ホストにバイトを運ばせる必要が無くなる。 */
      char tbl[128], path[1024];
      if(fscanf(fp, "%127s %1023s", tbl, path) != 2) break;
      FILE *bf = fopen(path, "rb");
      if(!bf){ fprintf(stderr, "cannot open file\\n"); exit(2); }
      long cap = 1024, len = 0; unsigned char *raw = (unsigned char*)malloc((size_t)cap);
      int ch2;
      while((ch2 = fgetc(bf)) != EOF){
        if(len == cap){ cap *= 2; raw = (unsigned char*)realloc(raw, (size_t)cap); }
        raw[len++] = (unsigned char)ch2; }
      fclose(bf);
      nrows = (int)len + 1; ar = 2;                 /* 末尾に番兵の空白 */
      buf = (i64*)malloc(sizeof(i64)*(size_t)nrows*2);
      for(long k=0;k<len;k++){ buf[k*2]=k; buf[k*2+1]=raw[k];
        if((int)k > MAXC) MAXC=(int)k; if((int)raw[k] > MAXC) MAXC=(int)raw[k]; }
      buf[len*2]=len; buf[len*2+1]=32; if((int)len > MAXC) MAXC=(int)len;
      free(raw);
      strcpy(name, tbl);
      nrows = nrows; ar = 2;
    }
    else {
      if(fscanf(fp, "%d %d", &nrows, &ar) != 2) break;
      buf = (i64*)malloc(sizeof(i64) * (size_t)nrows * ar);
      for(long long k=0; k<(long long)nrows*ar; k++){
        long long v; if(fscanf(fp, "%lld", &v) != 1){ fprintf(stderr,"bad data\\n"); exit(2);}
        buf[k] = v; if(v > MAXC) MAXC = (int)v; }
    }
    {""")
    for t in prog.tables:
        a(f'    if(!strcmp(name, "{t}")) {{')
        a(f"      if(append && T_{t}) {{")
        a(f"        T_{t} = (i64*)realloc(T_{t}, sizeof(i64)*(size_t)(N_{t}+nrows)*ar);")
        a(f"        memcpy(T_{t} + (long long)N_{t}*ar, buf, sizeof(i64)*(size_t)nrows*ar);")
        a(f"        LO_{t} = N_{t}; N_{t} += nrows; free(buf);")
        a(f"      }} else {{ T_{t}=buf; N_{t}=nrows; A_{t}=ar; LO_{t}=0; }}")
        a("      continue; }")
    a("""    }
  }
  fclose(fp);
}
static void load(const char *p){ load_into(p, 0); }
""")
    # 半素朴の下地は、規則の発行より前に宣言しておく（規則の中から積むので）
    global SEMI, SEMI_STRATA
    SEMI_STRATA = set()
    SEMI = ALLOW_SEMI and DENSE and not shape and any(
        N._frefs(r.value) + [x for g in r.guards for x in N._frefs(g)]
        for rules in prog.strata for r in rules)
    if SEMI:
        for si, rules in enumerate(prog.strata):
            ok = True
            for r in rules:
                rd = N._frefs(r.value) + [x for g in r.guards for x in N._frefs(g)]
                if rd and len(r.sources) != 1: ok = False
                if any(not isinstance(sc, str) for _v, sc in r.sources): ok = False
            if ok and rules: SEMI_STRATA.add(si)
        SEMI = bool(SEMI_STRATA)
    if SEMI:
        for f in prog.fields:
            a(f"static long long BASE_{f};")
        a("static int SEMI_ON = 0;")
        a("static int *WQ; static long long WH, WT, WCAP; static char *INQ;")
        a("static void wpush(long long c){ if(INQ[c]) return; INQ[c]=1;")
        a("  WQ[WT]=(int)c; WT=(WT+1)%WCAP; }")

    # ---- 半素朴（変化したセルから規則の行を引く） --------------------------
    # **C には書けない変換。** 「全部の行を撃ち直しても答えは同じだが、
    # 変化したセルに繋がる行だけで足りる」は join の冪等性・単調性から来る
    # 意味の性質であって、C の意味論には存在しない。
    # 索引の中身は実行時のデータで決まるが、**何を索引すべきかは規則が決めている**。
    semi = SEMI
    if semi:
        for si, rules in enumerate(prog.strata):
            ok = True
            for r in rules:
                rd = N._frefs(r.value) + [x for g in r.guards for x in N._frefs(g)]
                if rd and len(r.sources) != 1: ok = False
                if any(not isinstance(sc, str) for _v, sc in r.sources): ok = False
            if ok and rules: SEMI_STRATA.add(si)
        semi = bool(SEMI_STRATA)
    if semi:
        for si, rules in enumerate(prog.strata):
            for r in rules:
                reads = N._frefs(r.value) + [x for g in r.guards for x in N._frefs(g)]
                if not reads: continue
                if any(not isinstance(sc, str) for _v, sc in r.sources): continue
                for pi, (f, ix) in enumerate(reads):
                    a(f"static int *IXS_{r.id}_{pi}, *IXL_{r.id}_{pi};")
        a("static void build_semi(void){")
        for si, rules in enumerate(prog.strata):
            for r in rules:
                reads = N._frefs(r.value) + [x for g in r.guards for x in N._frefs(g)]
                if not reads or not r.sources: continue
                if any(not isinstance(sc, str) for _v, sc in r.sources): continue
                src = r.sources[0][1]
                V = {v: f"T_{src}[(long long)_r*A_{src}+{i}]"
                     for i, v in enumerate(r.sources[0][0])}
                if len(r.sources) > 1:      # 多重ループの規則は索引しない（正しさ優先）
                    continue
                for pi, (f, ix) in enumerate(reads):
                    try: cell = cidx(f, ix, arity[f], V)
                    except Exception: continue
                    a(f"  {{ IXS_{r.id}_{pi} = (int*)calloc((size_t)SZ_{f}+2, sizeof(int));")
                    # **索引を作る側にも境界検査が要る。** 鎖の端（`f[i-1]` の
                    # i=0）は範囲の外＝⊥ で、寄与しない行である。値の読みには
                    # 検査を入れてあったのに、索引の counting sort は素の添字を
                    # 使っていた —— `at[-1]` が配列の手前を書いていた（二度目）。
                    a(f"    for(int _r=0;_r<N_{src};_r++) {{ long long _c={cell};"
                      f" if(_c<0||_c>=SZ_{f}) continue; IXS_{r.id}_{pi}[_c+1]++; }}")
                    a(f"    for(long long i=0;i<SZ_{f}+1;i++) IXS_{r.id}_{pi}[i+1]+=IXS_{r.id}_{pi}[i];")
                    a(f"    IXL_{r.id}_{pi} = (int*)malloc(sizeof(int)*(size_t)N_{src});")
                    a(f"    int *at=(int*)malloc(sizeof(int)*((size_t)SZ_{f}+2));")
                    a(f"    memcpy(at, IXS_{r.id}_{pi}, sizeof(int)*((size_t)SZ_{f}+2));")
                    a(f"    for(int _r=0;_r<N_{src};_r++) {{ long long _c={cell};"
                      f" if(_c<0||_c>=SZ_{f}) continue;"
                      f" IXL_{r.id}_{pi}[at[_c]++] = _r; }}")
                    a("    free(at); }")
        a("}")

    # ---- 規則の発火（層ごと。閉包を消費する順序は構造が決めている） --------
    # 非単調な読み（否定・集約）は、相手の層が **閉じてから** でなければ撃てない。
    # 全部を一つのループで回すと、育ちきる前の値で否定が真になり、集合が汚れる。
    # （実際にそれで `tc[0,3]` を取りこぼした。層は飾りではない。）
    for si, rules in enumerate(prog.strata):
        # **一つの関数に全規則を書くと cc1 が記憶で死ぬ**（3,800 規則の
        # run.lx で 24 万行の C になり、-O0 でも OOM）。規則の塊ごとに
        # 関数へ割る —— 意味は変わらない（changed の OR を積むだけ）。
        parts, buf = [], []
        ba = buf.append
        for r in rules:
            emit_rule(ba, prog, r, arity)
            if len(buf) > 4000:
                parts.append(buf); buf = []; ba = buf.append
        if buf: parts.append(buf)
        for pi, chunk in enumerate(parts):
            a(f"static int sweep{si}_{pi}(void){{ int changed=0;")
            for ln in chunk: a(ln)
            a("  return changed; }")
        a(f"static int sweep{si}(void){{ int changed=0;")
        for pi in range(len(parts)):
            a(f"  changed |= sweep{si}_{pi}();")
        a("  return changed; }")

    # ---- 層の中を SCC に割り、位相順に。融合できる SCC は座標順に一掃する ----
    # 層は協調の *回数* を決めるだけで、その中の順序までは決めていない。
    # SCC を凝縮して位相順に回せば、各 SCC は一度不動点にすればもう戻らない。
    # さらに再帰読みのずれが一定符号なら、**行を外側・規則を内側**にした
    # 一掃が一度で終わる。順序を決めるのは値ではなく座標なので、キューが要らない。
    FUSED.clear()
    for si, rules in enumerate(prog.strata):
        if not rules: continue
        groups = defaultdict(list)
        for r in rules: groups[r.scc].append(r)
        order = sorted(groups, key=lambda c: getattr(prog, 'scc_rank', {}).get(c, c))
        plans = {}
        for c in order:
            try: plans[c] = fuse_plan(prog, groups[c])
            except Exception: plans[c] = None
        if not any(plans.values()): continue
        FUSED[si] = []
        for c in order:
            p = plans[c]
            if p is None: continue
            src, col, sign, _rank = p
            gid = f"{si}_{c}"
            FUSED[si].append((c, src))
            a(f"static int *ORD_{gid}; static i64 *SK_{gid};")
            a(f"static int cmp_{gid}(const void*_a,const void*_b){{")
            a(f"  i64 x=SK_{gid}[*(const int*)_a], y=SK_{gid}[*(const int*)_b];")
            a("  return x<y?-1:(x>y?1:0); }")
            a(f"static void ord_{gid}(void){{")
            a(f"  ORD_{gid}=(int*)malloc(sizeof(int)*(size_t)N_{src});")
            a(f"  SK_{gid}=(i64*)malloc(sizeof(i64)*(size_t)N_{src});")
            a(f"  for(int _r=0;_r<N_{src};_r++){{ ORD_{gid}[_r]=_r;")
            a(f"    SK_{gid}[_r] = ({sign}) * T_{src}[(long long)_r*A_{src}+{col}]; }}")
            a(f"  qsort(ORD_{gid}, (size_t)N_{src}, sizeof(int), cmp_{gid}); }}")
        a(f"static int sweepF{si}(void){{ int _any=0;")
        for c in order:
            g = sorted(groups[c], key=lambda r: (plans[c][3][r.id] if plans[c] else 0))
            gid = f"{si}_{c}"
            a("  { int changed; do{ changed=0;")
            if plans[c]:
                src = plans[c][0]
                a(f"    for(int _o=0;_o<N_{src};_o++){{ int _r0 = ORD_{gid}[_o];")
                # `continue`（ガードと ⊥ 検査）は **その規則だけ**を飛ばす。
                # 外側が共有のループになるので、emit_rule 側が囲いを出す。
                for r in g:
                    emit_rule(a, prog, r, arity, row0="_r0")
                a("    }")
            else:
                for r in g: emit_rule(a, prog, r, arity)
            a("    if(changed) _any=1; }while(changed); }")
        a("  return _any; }")
    if SEMI:
        # **増分は「続きをやる」だけである。** 新しい行だけを撃って前線を回す。
        # 無効化も再計算も要らない —— 事実の追加はストアを増やすことしかできない。
        for si, rules in enumerate(prog.strata):
            a(f"static int sweepN{si}(void){{ int changed=0;")
            for r in rules:
                emit_rule(a, prog, r, arity, only_new=True)
            a("  return changed; }")

    if semi:
        # 層ごとの半素朴駆動。種を撒いてから、変化したセルだけを引く。
        for si, rules in enumerate(prog.strata):
            if not rules or si not in SEMI_STRATA: continue
            a(f"static void drain{si}(void){{")
            a("  int changed = 0; (void)changed;")
            a("  while(WH != WT){ long long _c0 = WQ[WH]; WH = (WH+1) % WCAP; INQ[_c0] = 0;")
            for r in rules:
                reads = N._frefs(r.value) + [x for g in r.guards for x in N._frefs(g)]
                if not reads or len(r.sources) != 1: continue
                for pi, (f, _ix) in enumerate(reads):
                    a(f"    if(_c0 >= BASE_{f} && _c0 < BASE_{f} + SZ_{f}){{")
                    a(f"      long long _c = _c0 - BASE_{f};")
                    emit_rule(a, prog, r, arity, indexed=pi, push=True)
                    a("    }")
            a("  } }")
            a(f"static void semi{si}(void){{ sweep{si}(); drain{si}(); }}")

    # ---- 索引つきヒープ（証明書が licence したときだけ） ------------------
    if shape:
        f, rec, base = shape
        src = rec.sources[0][1]; vs = rec.sources[0][0]
        ri = vs.index(N._frefs(rec.value)[0][1][0][1])      # 読む座標の列
        ti = vs.index(rec.keys[0][1])                        # 書く座標の列
        V = {v: f"T_{src}[(long long)_r*A_{src}+{i}]" for i, v in enumerate(vs)}
        a(f"""
/* 索引（CSR）は **起動時に** 作る。構造の解析はコンパイル時、データは実行時。
   証明書（再帰デルタ非負）が値順の前線を licence するので、ここは Dijkstra。 */
static int *IXS, *IX;
static void build_index(void){{
  IXS = (int*)calloc((size_t)DOM_{f}+2, sizeof(int));
  for(int _r=0;_r<N_{src};_r++) IXS[(int)({V[vs[ri]]})+1]++;
  for(int i=0;i<DOM_{f}+1;i++) IXS[i+1]+=IXS[i];
  IX = (int*)malloc(sizeof(int)*(size_t)N_{src});
  int *at=(int*)malloc(sizeof(int)*((size_t)DOM_{f}+2));
  memcpy(at, IXS, sizeof(int)*((size_t)DOM_{f}+2));
  for(int _r=0;_r<N_{src};_r++) IX[at[(int)({V[vs[ri]]})]++] = _r;
  free(at);
}}
typedef struct {{ i64 p; int c; }} hn;
static hn *H; static int HN, HC;
static void hpush(i64 p, int c){{
  if(HN==HC){{ HC=HC?HC*2:1024; H=(hn*)realloc(H,(size_t)HC*sizeof(hn)); }}
  int i=HN++; H[i].p=p; H[i].c=c;
  while(i>0){{ int q=(i-1)/2; if(H[q].p<=H[i].p) break; hn t=H[q];H[q]=H[i];H[i]=t; i=q; }}
}}
static int hpop(i64 *p, int *c){{
  if(!HN) return 0; *p=H[0].p; *c=H[0].c; H[0]=H[--HN];
  int i=0; for(;;){{ int l=2*i+1,r2=l+1,m=i;
    if(l<HN&&H[l].p<H[m].p) m=l; if(r2<HN&&H[r2].p<H[m].p) m=r2;
    if(m==i) break; hn t=H[m];H[m]=H[i];H[i]=t; i=m; }}
  return 1;
}}
static void solve_heap(void){{
  build_index();
  for(long long i=0;i<SZ_{f};i++) if(F_{f}[i]!={BOT['min']}) hpush(F_{f}[i],(int)i);
  i64 p; int c;
  while(hpop(&p,&c)){{
    if(p > F_{f}[c]) continue;                  /* 古い項目 */
    for(int q=IXS[c]; q<IXS[c+1]; q++){{
      int _r = IX[q];
      i64 _v = {cexpr(rec.value, V)}; JOINS++;
      long long _t = (long long)({V[vs[ti]]});
      if(_v < F_{f}[_t]){{ F_{f}[_t] = _v; hpush(_v,(int)_t); }}
    }}
  }}
}}""")
        a("#define HAVE_HEAP 1")
    # ---- 外から与えられた場の行を入れる（source） --------------------------
    # 外から来た行を join する（source の実体化）。増分でも呼ぶので関数にする。
    a("static void seed_more(int _from){")
    a("  for(int _s=_from;_s<NSEED;_s++){")
    for f in prog.fields:
        ar = arity[f]; lat = prog.fields[f].name
        if lat == 'set': continue
        if DENSE:
            idx = "0"
            for d in range(ar):
                idx = f"(({idx}) * DOM_{f}_{d} + (long long)SEEDV[_s][{d}])" if d else f"(long long)SEEDV[_s][0]"
            a(f'    if(!strcmp(SEEDF[_s], "{f}")){{ long long _t = {idx if ar else "0"};')
            a(f"      i64 _v = (i64)SEEDV[_s][{max(ar,0)}];")
            if lat in ('min', 'max', 'or', 'and'):
                cnd2 = (f"(F_{f}[_t] == {BOT[lat]} || z_cmp(_v, F_{f}[_t]) {CMP[lat]} 0)"
                        if lat in ('min', 'max') else f"_v {CMP[lat]} F_{f}[_t]")
                a(f"      if({cnd2}) {{ F_{f}[_t] = _v; K_{f}[_t] = 1; }}")
            elif lat in ('flat', 'fourv'):
                a(f"      if(F_{f}[_t] == {BOT[lat]}) {{ F_{f}[_t] = _v; K_{f}[_t] = 1; }}")
                a(f"      else if(F_{f}[_t] != _v) F_{f}[_t] = {TOPV};")
            else:
                a(f"      F_{f}[_t] += _v; K_{f}[_t] = 1;")
            a("      continue; }")
        else:
            ks = ", ".join(f"(i64)SEEDV[_s][{d}]" for d in range(ar))
            a(f'    if(!strcmp(SEEDF[_s], "{f}")){{')
            a(f"      if(mjoin_{f}({ks}{',' if ks else ''} (i64)SEEDV[_s][{max(ar,0)}]))")
            a(f"        rset_{f}({ks}{',' if ks else ''} 1);")
            a("      continue; }")
    a("  }")
    a("}")

    # ---- main ------------------------------------------------------------
    a("""
int main(int argc, char **argv){
  if(argc < 2){ fprintf(stderr, "usage: %s data.lxd\\n", argv[0]); return 2; }
  load(argv[1]);
  int D = MAXC + 1 + SLACK;""")
    for f in prog.fields:
        ar = arity[f]
        if not DENSE:
            a(f"  minit(&M_{f}, {max(ar,1)}, 0); minit(&R_{f}, {max(ar,1)}, 0);")
            continue
        # 宣言された広さ（`field f : max bound N`）があれば、それが下限である。
        # **有限の資源は宣言し、超えたら言う** —— data から推した広さより
        # 記述が言う広さが大きいなら、記述に従う（区間はデータに現れない）。
        b = prog.field_bound.get(f)
        bs = list(b) if isinstance(b, tuple) else ([b] if b else [])
        bd = bs[0] if bs else None
        a(f"  DOM_{f} = D; SZ_{f} = 1;")
        if bd: a(f"  if(DOM_{f} < {bd}) DOM_{f} = {bd};")
        for _d in range(max(ar, 1)):
            w = bs[_d] if _d < len(bs) else None
            # **宣言があるなら、それが広さである**（データから推した D ではない）。
            # max を取っていたので `bound 1024 256` が 32768×32768 になり、
            # 只の場が 8GB を要求して落ちた。焼いた ELF は宣言どおりに取る ——
            # 二つの実装が同じ広さを取らなければ、同じ答えにならない。
            a(f"  DOM_{f}_{_d} = {w};" if w else f"  DOM_{f}_{_d} = D;")
        for _d in range(ar): a(f"  SZ_{f} *= DOM_{f}_{_d};")
        if ar == 0: a(f"  SZ_{f} = 1;")
        if prog.fields[f].name == 'set':
            a(f"  WD_{f} = (D + 63) / 64;")
            a(f"  F_{f} = (i64*)calloc((size_t)SZ_{f}*WD_{f}, sizeof(i64));")
            a(f"  K_{f} = (int*)calloc((size_t)SZ_{f}, sizeof(int));")
        else:
            a(f"  F_{f} = (i64*)malloc(sizeof(i64)*(size_t)SZ_{f});")
            a(f"  for(long long i=0;i<SZ_{f};i++) F_{f}[i] = {BOT[prog.fields[f].name]};")
            a(f"  K_{f} = (int*)calloc((size_t)SZ_{f}, sizeof(int));")
            if prog.fields[f].name in ('flat', 'fourv'):
                a(f"  P_{f} = (i64*)malloc(sizeof(i64)*(size_t)SZ_{f});")
                a(f"  for(long long i=0;i<SZ_{f};i++) P_{f}[i] = {BOT[prog.fields[f].name]};")
                a(f"  PK_{f} = (int*)calloc((size_t)SZ_{f}, sizeof(int));")
    for r in prog.rules:
        if prog.fields[r.target].name in AGG:
            a(f"  minit(&FIRED_{r.id}, {max(len(_aggvars(r)), 1)}, 0);")
            a(f"  minit(&FVAL_{r.id}, {max(len(_aggvars(r)), 1)}, 0);")
    if SEMI:
        tot = " + ".join(f"SZ_{f}" for f in prog.fields) or "1"
        off = "0"
        for f in prog.fields:
            a(f"  BASE_{f} = {off};")
            off = f"BASE_{f} + SZ_{f}"
        a(f"  WCAP = ({tot}) + 2;")
        a("  WQ = (int*)malloc(sizeof(int)*(size_t)WCAP);")
        a("  INQ = (char*)calloc((size_t)WCAP, 1); WH = WT = 0; SEMI_ON = 1;")
        a("  build_semi();")
    a("  seed_more(0);")
    a("  struct timespec t0,t1; clock_gettime(CLOCK_MONOTONIC,&t0);")
    a("  int rounds = 0;")
    for si, rules in enumerate(prog.strata):
        if not rules: continue
        if si == 0 and shape:
            # 証明書が値順の前線を licence した層は、ヒープで一掃する
            a(f"  sweep{si}();  solve_heap();")
        elif si in FUSED:
            for (_c, src) in FUSED[si]: a(f"  ord_{si}_{_c}();")
            a(f"  sweepF{si}();")
        elif si in SEMI_STRATA:
            a(f"  semi{si}();")
        else:
            a(f"  while(sweep{si}()) {{ rounds++;")
            a('    if(rounds > 100000000) { fprintf(stderr,"no fixpoint\\n"); return 3; } }')
    a("""  clock_gettime(CLOCK_MONOTONIC,&t1);
  fprintf(stderr, "NATIVE_MS %.4f\\nJOINS %lld\\nROUNDS %d\\n",
          (t1.tv_sec-t0.tv_sec)*1e3+(t1.tv_nsec-t0.tv_nsec)/1e6, JOINS, rounds);""")
    if SEMI:
        # **増分は「続きをやる」だけ。** 追加のファイルを食い、新しい行だけ撃って前線を回す。
        # 無効化ロジックは一行も無い —— 事実の追加はストアを増やすことしかできないから。
        a("  for(int _f=2; _f<argc; _f++){")
        a("    long long j0 = JOINS; clock_gettime(CLOCK_MONOTONIC,&t0);")
        a("    int _ns0 = NSEED;")
        a("    load_into(argv[_f], 1);")
        a("    build_semi();")
        a("    if(NSEED > _ns0) seed_more(_ns0);   /* 外から来た場の行を入れる */")
        for si, rules in enumerate(prog.strata):
            if not rules: continue
            # 種まきは **新しい行だけ**。あとは前線が運ぶ。ここが増分の全部である。
            # ただし外から場が来た（source）ときは、どの行が動いたか分からないので
            # その層を一度だけ通しで回す。往復は元々ブロッキングな境界である。
            a(f"    sweepN{si}();")
            a(f"    if(NSEED > _ns0) {{ while(sweep{si}()) {{ }} }}")
            if si in SEMI_STRATA: a(f"    drain{si}();")
            else: a(f"    while(sweep{si}()) {{ }}")
        a("    clock_gettime(CLOCK_MONOTONIC,&t1);")
        a('    fprintf(stderr, "DELTA_MS %.4f\\nDELTA_JOINS %lld\\n",')
        a("      (t1.tv_sec-t0.tv_sec)*1e3+(t1.tv_nsec-t0.tv_nsec)/1e6, JOINS - j0);")
        a("  }")
    # 既定では **検査器のために全部の場を出す**。`only_prints` を立てると
    # `print` と書いた場だけになる —— render だけのプログラム（生成器）を
    # 走らせるときは、標準出力に混ぜ物があってはならない。
    for f in (prog.prints if ONLY_PRINTS else prog.fields):
        ar = arity[f]; lat = prog.fields[f].name
        if not DENSE:
            a(f"  for(long long i=0;i<M_{f}.cap;i++){{ if(!M_{f}.used[i]) continue;")
            a(f"    if(M_{f}.v[i] == {BOT.get(lat, '0')}) continue;")
            a(f'    printf("{f}");')
            for d in range(ar):
                a(f'    printf(" %lld", (long long)M_{f}.k[i*{max(ar,1)}+{d}]);')
            args = ", ".join(f"M_{f}.k[i*{max(ar,1)}+{d}]" for d in range(ar))
            if lat in ('set', 'bag'):
                a(f'    printf(" :");')
                a(f"    {{ long long _s = (long long)M_{f}.v[i];")
                a(f"      for(long long _b=0;_b<slen(_s);_b++)"
                  f" printf(\" %lld\", (long long)SARN[_s+1+_b]); }}")
                a(f'    printf(" @%lld\\n", (long long)rget_{f}({args})); }}')
                continue
            a(f'    printf(" = %s @%lld\\n", zstr(M_{f}.v[i]), (long long)rget_{f}({args})); }}')
            continue
        a(f"  for(long long i=0;i<SZ_{f};i++){{")
        if lat == 'set':
            a(f"    int _any=0; for(int w=0;w<WD_{f};w++) if(F_{f}[i*WD_{f}+w]) _any=1;")
            a("    if(!_any) continue;")
        else:
            a(f"    if(F_{f}[i]=={BOT[lat]}) continue;")
        a(f'    printf("{f}");')
        for d in range(ar):
            # 次元 d の刻み幅は「後ろの次元の積」。割り算で書いていて、
            # 整数除算で 0 になり SIGFPE で落ちた（多次元を印字して初めて出た）。
            div = " * ".join(["1"] + [f"DOM_{f}_{e}" for e in range(d + 1, ar)])
            a(f'    printf(" %lld", (long long)((i / ({div})) % DOM_{f}_{d}));')
        if lat == 'set':
            a(f'    printf(" :");')
            a(f"    for(int b=0;b<DOM_{f};b++)")
            a(f"      if(F_{f}[i*WD_{f}+(b>>6)]>>(b&63)&1) printf(\" %d\", b);")
            a(f'    printf(" @%d\\n", K_{f}[i]); }}')
        else:
            a(f'    printf(" = %s @%d\\n", zstr(F_{f}[i]), K_{f}[i]); }}')
        # **影を出す。** 平坦なセルが ⊤ になる前に持っていた確定値。
        # 名前を `~f` にして本体と混ぜない —— 影は答えではなく、証明書である。
        if DENSE and lat in ('flat', 'fourv'):
            a(f"  for(long long i=0;i<SZ_{f};i++){{")
            a(f"    if(P_{f}[i]=={BOT[lat]}) continue;")
            a(f'    printf("~{f}");')
            for d in range(ar):
                div = " * ".join(["1"] + [f"DOM_{f}_{e}" for e in range(d + 1, ar)])
                a(f'    printf(" %lld", (long long)((i / ({div})) % DOM_{f}_{d}));')
            a(f'    printf(" = %s @%d\\n", zstr(P_{f}[i]), PK_{f}[i]); }}')
    for ch, fld in prog.channels:
        # **効果は場の成長の差分である。** すでに出したビットは覚えておき、
        # 新しく立ったものだけを書く。だから再実行でも順序を変えても重複しない。
        a(f"  {{ static char _seen_{fld}[{'1'}];  (void)_seen_{fld};")
        a(f"    for(int b=0;b<DOM_{fld};b++)")
        a(f"      if(F_{fld}[0*WD_{fld}+(b>>6)]>>(b&63)&1)")
        a(f'        fprintf(stderr, "EMIT {ch} %d\\n", b); }}')
    for f in prog.renders:
        if not DENSE:
            # **座標順に並べるだけ**。以前はここが泡立ち法で、13万升の列を
            # 書き出すのに 37 秒かかっていた（不動点そのものは 50 ミリ秒）。
            # 遅いのは答えではなく、答えの出し方だった。
            ar_ = max(arity[f], 1)
            a(f"  {{ long long _n = M_{f}.n; long long *_o = (long long*)malloc(sizeof(long long)*(size_t)(_n?_n:1));")
            a(f"    long long _m = 0;")
            a(f"    for(long long i=0;i<M_{f}.cap;i++) if(M_{f}.used[i]) _o[_m++] = i;")
            a(f"    RK_{f} = M_{f}.k;")
            a(f"    qsort(_o, (size_t)_m, sizeof(long long), rcmp_{f});")
            a(f"    for(long long x=0;x<_m;x++){{ i64 _c = M_{f}.v[_o[x]];")
            a(f"      if(_c == {BOT[prog.fields[f].name]} || _c == {TOPV}) continue;")
            a("      putchar((int)z_coord(_c)); }")
            a('  }')
            continue
        # 列は座標に住んでいる。座標順に舐めて putchar するだけでよい。
        lat = prog.fields[f].name
        a(f"  for(long long i=0;i<SZ_{f};i++){{ i64 _c = F_{f}[i];")
        a(f"    if(_c == {BOT[lat]} || _c == {TOPV}) continue;")
        a("    putchar((int)z_coord(_c)); }")
        # **改行を足してはいけない。** render はバイト列であって行ではない ——
        # 解釈実行は足していない。足した瞬間に「同じ答え」でなくなる。
    a("  return 0; }")
    return "\n".join(e)


def write_data(prog, path, atom=None):
    """地上データを、実行ファイルが読む形で書き出す（原子は符号化する）。"""
    at = ATOM if atom is None else atom
    def code(x):
        if isinstance(x, bool): return 1 if x else 0
        if isinstance(x, str): return at[x]
        return int(x)
    with open(path, "w") as fp:
        for t, rows in prog.tables.items():
            ar = len(rows[0]) if rows else 0
            fp.write(f"{t} {len(rows)} {ar}\n")
            for row in rows:
                fp.write(" ".join(str(code(x)) for x in row) + "\n")
    return path


def build(src, keep=None, opt="-O2", semi=True, only_prints=False):
    """プログラムだけを C にする。データは触らない。"""
    global ATOM
    prog = L.parse(src); L.check(prog); L.stratify(prog)
    L.io_rounds(prog); L.certify(prog)
    arity = analyse(prog)
    ATOM = atoms(prog)
    global PROG, KINDS, DENSE
    global VKINDS
    PROG = prog; KINDS = kinds(prog); DENSE = dense_ok(prog, arity)
    VKINDS = valkinds(prog)
    global ALLOW_SEMI; ALLOW_SEMI = semi
    global ONLY_PRINTS; ONLY_PRINTS = only_prints
    csrc = generate(prog, arity)
    _lats = {f: lat.name for f, lat in prog.fields.items()}
    d = keep or tempfile.mkdtemp(prefix="lattix_rt_")
    os.makedirs(d, exist_ok=True)
    cf, ex = os.path.join(d, "prog.c"), os.path.join(d, "prog")
    # **同じ C を二度焼かない。** keep で置き場を指定すれば、道具は残る ——
    # プログラムが同じなら（表が違っても）実行ファイルは同じものでよい。
    same = (os.path.exists(ex) and os.path.exists(cf)
            and open(cf, encoding='utf-8').read() == csrc)
    if not same:
        open(cf, "w").write(csrc)
        # **C が同じなら実行ファイルも同じ** —— 置き場（keep）が違っても焼き直さない。
        # 閉じの測定器は表ごとに置き場を変えるが、C は表に依らず同一だった
        # （10MB の C を 2 分ずつ、同じものを何十回も焼いていた）。内容で引く。
        import hashlib, shutil
        h = hashlib.sha1((opt + "\n" + csrc).encode('utf-8')).hexdigest()[:16]
        cdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '_gen', 'ccache', h)
        cex = os.path.join(cdir, 'prog')
        if os.path.exists(cex):
            shutil.copy2(cex, ex)
        else:
            # 大きな生成 C（数十万行）で cc1 が記憶で死ぬ —— GC を強制する。
            # 意味は変わらず、時間が少し増えるだけ（正しさの焼きには十分）。
            r = subprocess.run(["gcc", opt, "-w",
                                "--param", "ggc-min-expand=10",
                                "--param", "ggc-min-heapsize=32768",
                                "-o", ex, cf],
                               capture_output=True, text=True)
            if r.returncode: raise N.Unsupported("gcc failed:\n" + r.stderr[:2000])
            try:
                os.makedirs(cdir, exist_ok=True)
                tmp = cex + f'.{os.getpid()}'
                shutil.copy2(ex, tmp); os.replace(tmp, cex)
            except OSError:
                pass
    LATS[ex] = _lats
    CTX[ex] = (dict(ATOM), KINDS, VKINDS)
    return dict(prog=prog, exe=ex, csrc=cf, arity=arity, atom=dict(ATOM),
                lines=len(csrc.splitlines()), dir=d)


def run(exe, datafile, *deltas):
    # render は **バイト列** を書く（実行形式でもよい）。だから文字として読まない。
    r = subprocess.run([exe, datafile, *deltas], capture_output=True)
    r = type(r)(r.args, r.returncode,
                r.stdout.decode('utf-8', 'replace'),
                r.stderr.decode('utf-8', 'replace'))
    if r.returncode: raise N.Unsupported("runtime run failed:\n" + r.stderr[:500])
    meta, deltalog, emits = {}, [], []
    for line in r.stderr.splitlines():
        if line.startswith("EMIT "):
            _, ch, val = line.split(None, 2)
            emits.append((ch, int(val))); continue
        k, _, v = line.partition(" ")
        if v:
            try:
                x = float(v)
                if k.startswith("DELTA_"): deltalog.append((k, x))
                meta[k] = x
            except ValueError: pass
    meta['deltas'] = deltalog
    _atom, _kinds, _vkinds = CTX.get(exe, (ATOM, KINDS, VKINDS))
    inv = {v: k for k, v in _atom.items()}
    kkey, kelem = _kinds
    # **build の残り香に頼らない。** 直前に別のプログラムを焼いていたら、
    # 場の名前が食い違って落ちる（実際に落ちた）。焼いたときの束を引く。
    lats = LATS.get(exe, {})
    def dec(x, k):
        return inv.get(x, x) if k == 'atom' else x
    store, ranks = {}, {}
    pre, prerank = {}, {}
    for line in r.stdout.splitlines():
        t = line.split()
        if len(t) < 2: continue
        f = t[0]
        # `~f` は **影** —— 答えではなく ⊤ の証人。別の店に入れる。
        if f.startswith('~'):
            f = f[1:]
            if '=' not in t: continue
            c = t.index('=')
            key = tuple(dec(int(x), kkey.get((f, d), 'int'))
                        for d, x in enumerate(t[1:c]))
            v = int(t[c + 1])
            vk = _vkinds.get(f, 'int')
            if vk == 'bool': v = bool(v)
            elif vk == 'atom': v = inv.get(v, v)
            pre.setdefault(f, {})[key] = v
            if len(t) > c + 2 and t[c + 2].startswith('@'):
                prerank.setdefault(f, {})[key] = int(t[c + 2][1:])
            continue
        if ':' in t:                       # 集合: f k... : e e e
            c = t.index(':')
            key = tuple(dec(int(x), kkey.get((f, d), 'int'))
                        for d, x in enumerate(t[1:c]))
            elems = t[c + 1:]
            if elems and elems[-1].startswith('@'):
                ranks.setdefault(f, {})[key] = int(elems[-1][1:]); elems = elems[:-1]
            xs = [dec(int(x), kelem.get(f, 'int')) for x in elems]
            store.setdefault(f, {})[key] = (
                tuple(sorted(str(v) for v in xs))
                if lats.get(f) == 'bag' else frozenset(xs))
        elif '=' in t:
            c = t.index('=')
            key = tuple(dec(int(x), kkey.get((f, d), 'int'))
                        for d, x in enumerate(t[1:c]))
            v = int(t[c + 1])
            vk = _vkinds.get(f, 'int')
            # **⊤ を戻し忘れていた。** ⊤ を誤りだと思っていた間は誰も戻さなかった。
            if (lats.get(f) in ('flat', 'fourv', 'sum', 'count', 'bag')
                    and v == (1 << 63) - 1):
                v = L.TOP
            elif vk == 'fourv': v = L.FTRUE if v == 2 else L.FFALSE
            elif vk == 'bool': v = bool(v)
            elif vk == 'atom': v = inv.get(v, v)
            store.setdefault(f, {})[key] = v
            if len(t) > c + 2 and t[c + 2].startswith('@'):
                ranks.setdefault(f, {})[key] = int(t[c + 2][1:])
    meta['rank'] = ranks; meta['pre'] = pre; meta['prerank'] = prerank
    inv2 = inv
    ke = kelem
    meta['emit'] = [(ch, inv2.get(v, v) if ke.get('emit_' + ch) == 'atom' else v)
                    for ch, v in emits]
    return store, meta


if __name__ == '__main__':
    path = sys.argv[1]
    info = build(open(path, encoding='utf-8').read())
    data = write_data(info['prog'], os.path.join(info['dir'], "data.lxd"))
    store, meta = run(info['exe'], data)
    for f in info['prog'].prints:
        for k in sorted(store.get(f, {})):
            print(f"{f}[{', '.join(map(str, k))}] = {store[f][k]}")
    print(f"# {info['lines']} 行の C / データは実行時に読んだ / "
          f"{meta.get('NATIVE_MS', 0):.3f} ms", file=sys.stderr)
