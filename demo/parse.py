#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lattix で書いた構文解析器 —— 値の構成の実証。

`malloc` も `new` も gensym も使わない。構成された節点の名前は
**それを作った内容そのもの** である。だから:

  * 同じ部分木は自動的に共有される（hash-consing が構成の定義になる）
  * 別マシンで独立に解析しても同じ名前 → 合流でプロトコル無しに共有
  * 曖昧性は flat 束の ⊤ として自動検出される
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

here = ROOT
BASE = open(os.path.join(here, "examples", "15_parse.lx"), encoding="utf-8").read()

def program(tokens):
    w = ", ".join(f'({i},"{t}")' for i, t in enumerate(tokens))
    ix = ", ".join(f"({i})" for i in range(len(tokens) + 1))
    out = []
    for line in BASE.splitlines():
        t = line.strip()
        if t.startswith('table word'):  out.append(f"table word = {w}"); continue
        if t.startswith('table idx'):   out.append(f"table idx  = {ix}"); continue
        if t.startswith('(5,"with")') or t.startswith('(0),(1)'): continue
        out.append(line)
    return "\n".join(out)

def run(tokens):
    src = program(tokens)
    p = L.parse(src); L.check(p); d = L.stratify(p); L.io_rounds(p); L.certify(p)
    st, conf, stats = L.run(p, out=io.StringIO())
    return p, st, d, stats, conf

def show(st, nid, depth=0):
    if isinstance(nid, L._Top): return "  " * depth + "⊤ AMBIGUOUS"
    lf = st['leaf_sym'].get((nid,))
    if lf is not None:
        pos = st['leaf_pos'].get((nid,))
        return "  " * depth + f"{lf}@{pos}"
    sym = st['node_sym'].get((nid,))
    if sym is None: return "  " * depth + f"?{nid}"
    l = st['node_left'].get((nid,)); r = st['node_right'].get((nid,))
    return ("  " * depth + f"{sym}\n" + show(st, l, depth + 1) + "\n"
            + show(st, r, depth + 1))

W = 80
print("=" * W)
print("  Lattix で書いた CYK 構文解析器 —— 値の構成")
print("=" * W)

S1 = ["the", "cat", "saw", "the", "mat"]
p, st, d, stats, conf = run(S1)
n = len(S1)
root = st['tree'].get((0, n, "S"))
print(f"\n  (1) 「{' '.join(S1)}」   深度 {d}  規則 {len(p.rules)}  join {stats['joins']:,}")
print(f"      構成された節点 {len(st['_size'])} 個   最大深さ {max(st['_size'].values())}")
print(f"      解析木:")
for line in show(st, root).splitlines(): print("        " + line)

S2 = ["the", "cat", "saw", "the", "mat", "with", "the", "telescope"]
# **曖昧な文は ⊤ を作り、⊤ は名前になれない。** 部分木が二通りある升は
# `flat` の ⊤ に落ちる。その升を `node(…)` の引数にすると、構成された値の
# 名前が ⊤ になり、⊤ は座標ではない —— 処理系はそこで止まる。
# 「⊤ になる前に間に合った寄与だけ残る」を許すと、答えが日程で変わるからである
# （`test/discover.py` 第2部が反例を出した）。**曖昧性は、そう言って止まる。**
amb = False
try:
    p2, st2, d2, stats2, conf2 = run(S2)
except L.LattixError as ex:
    amb = True; why = str(ex).splitlines()[0]
print(f"\n  (2) 「{' '.join(S2)}」")
if amb:
    print(f"      {why}")
    print(f"      → PP の係り先が二通りある。**曖昧性が束の ⊤ として自動検出された。**")
    print(f"        文法解析器に曖昧性検出コードを書いていない。flat 束がそう定義されている。")
    print(f"        ⊤ の部分木は名前を持てないので、半分だけ組み上がった木も残らない。")
else:
    print(f"      S[0,{len(S2)}] = {st2['tree'].get((0, len(S2), 'S'))}  （曖昧でなかった）")

# ---- 構造共有 ----------------------------------------------------------
print("\n" + "-" * W)
print("  構造共有 — 同じ部分木は同じ名前を持つ")
subtrees = {}
for (nid,), sym in st['node_sym'].items():
    subtrees.setdefault(sym, []).append(nid)
tot = len(st['_size'])
print(f"      文(1) で構成された相異なる節点 : {tot}")
print(f"      「the cat」のような部分木は、どの解釈からでも同じ id になる。")

# ---- 分散: 別々に解析して合流 -------------------------------------------
print("\n" + "-" * W)
print("  分散 — 二つのレプリカが独立に解析し、join で合流する")
pa, sta, *_ = run(S1)
pb, stb, *_ = run(S1)
merged = L.merge_stores(pa, sta, stb)
same = all(merged[f] == sta[f] for f in sta)
print(f"      レプリカA の節点 {len(sta['_size'])}  レプリカB の節点 {len(stb['_size'])}")
print(f"      合流後の節点 {len(merged['_size'])}   （重複ゼロ: {same}）")
print(f"      → 内容アドレスなので、別々に作った同じ構造が *自動的に* 同一物になる。")
print(f"        アドレスも世代番号も UUID も使っていないので、突き合わせが要らない。")

print("\n" + "=" * W)
print("  『新しい値』を『いつ確保したか』で名付けるのは von Neumann のバイアスである。")
print("  順序・時間・空間・信頼のどれにも依存しない命名は、内容アドレスしかない。")
print("=" * W)
sys.exit(0 if (root is not None and amb and same) else 1)
