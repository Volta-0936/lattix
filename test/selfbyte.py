#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**源のバイトを、焼いた実行ファイルが読む。** —— 自己ホストの一段目。

`examples/33_self.lx` は **断片だけ**で書いた字句解析である（構成子も cons も
無い）。それを 21_lex → 32_shape → 31_gen で焼き、**生の .lx を標準入力から
食わせる**。答えは解釈実行と全セル一致しなければならない。

ここで初めて「Lattix で書いた道具が、Lattix の源を読む」——
`lattix` が自分を読む段の、最初の一段である。
"""
import io, os, re, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

W = 76
SELF = os.path.join(ROOT, 'examples', '33_self.lx')

sg = open(os.path.join(ROOT, 'test', 'selfgen.py'), encoding='utf-8').read()
ns = {'__name__': 'notmain', '__file__': os.path.join(ROOT, 'test', 'selfgen.py')}
exec(compile(sg[:sg.index("tmp = tempfile.mkdtemp()")], 'selfgen', 'exec'), ns)

SRC = open(SELF, encoding='utf-8').read()
# 場の並びは **源が決める**。手で写した一覧は、規則を足すたびに嘘になる。
NAMES = re.findall(r'^field\s+(\w+)', SRC, re.M)


def interp(data):
    """同じプログラムを Lattix の意味で解く（＝答えの定義）。"""
    rows = ", ".join(str((i, c)) for i, c in enumerate(data))
    src, n = re.subn(r"table ch = .*?\n", f"table ch = {rows}\n", SRC, count=1)
    assert n == 1, "置き場所の一行が見つからない"
    p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    st, _c, _s = L.run(p, out=io.StringIO())
    return {i: {k: p.fields[nm].observe(v) for k, v in st[nm].items()}
            for i, nm in enumerate(NAMES)}


print("=" * W)
print("  焼いた字句解析器が、**生の .lx** を読む（33_self.lx / 断片だけ）")
print("=" * W)
tmp = tempfile.mkdtemp()
ok = True
SELFSRC = open(SELF, 'rb').read()
# **突き合わせる相手は C バックエンドである。** 三つの場合とも走らせる
# プログラムは同じ 41KB の断片で、違うのは入力のバイト列だけなので、
# 解釈実行の重さ（1300万升・十分以上）は入力の小ささでは減らない ——
# 実際、解釈実行のまま走らせて **メモリを使い切って殺された**。
# C が答えの定義と一致することは test/runtimecheck.py が全例題で
# 見張っている（33_self.lx も含む）。速いのは焼いた側ではなく、
# **答えの受け取り方**を替えたからである（気づき30）。
DATA = [("小さな源", b"field d : min\nd[0] <- 12\n"),
        ("規則のある源", b"table e = (0,1,4)\nfield dist : min\n"
                         b"dist[j] <- dist[i] + w   for (i,j,w) in e\n"),
        ("自分の源", SELFSRC)]
print(f"  {'入力':<14}{'バイト':>7}{'語':>7}{'バイト数':>8}   全セル一致")
print("-" * W)
SELFP = re.sub(r"table ch = .*?\n", "table ch = (0,32)\n", SRC, count=1)
for i_, (name, data) in enumerate(DATA):
    flds, rules, n, store, rank = ns['compile_lx'](SRC, tmp, 800 + i_,
                                                   inp=1, data=data)
    o = ns['cgo']('self3', SELFP, {'ch': [(i, c) for i, c in enumerate(data)]})
    ref = {i: {k: (1 if v is True else v) for k, v in o(nm).items()}
           for i, nm in enumerate(NAMES)}
    store = {f: {k: (1 if v is True else v) for k, v in d.items()}
             for f, d in store.items()}
    ref = {f: d for f, d in ref.items() if d}
    store = {f: d for f, d in store.items() if d}
    same = store == ref
    ok &= same
    tn = store.get(NAMES.index('tnum'), {})
    ntok = max(tn.values(), default=-1)      # 語の数は値であって座標ではない
    print(f"  {name:<14}{len(data):>7}{ntok + 1:>7}{n:>8}   {'✓' if same else '✗'}")
    if not same:
        for f, nm in enumerate(NAMES):
            if store.get(f) != ref.get(f):
                a, b = store.get(f, {}), ref.get(f, {})
                diff = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
                print(f"      {nm}: 機械語 {len(a)} / 解釈 {len(b)} "
                      f"ずれ {sorted(diff)[:6]}")
print("-" * W)
print("  一致" if ok else "  不一致")
print("  **構成子は一つも使っていない** —— 範囲ガード・比較ガード・鎖・")
print("  場の値が座標、それだけで語が切れる。広さは源が宣言する（bound）。")
print("=" * W)
sys.exit(0 if ok else 1)
