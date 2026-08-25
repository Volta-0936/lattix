#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自己適用 — Lattix の中核解析を Lattix で書き、Python 実装と突き合わせる。

成層（どの規則がどの層に入るか、そもそも成層できるか）は、
この言語の一番深いところにある解析である。それが束の上の不動点で書ける。

Python 版: Tarjan の SCC + 縮約 DAG + トポロジカル順、約 60 行の命令型コード。
Lattix 版: 6 行。しかも並列・増分・分散・検査可能。

両者が全例題で一致するかを測る。
"""
import io, os, sys, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

here = ROOT
STRAT = open(os.path.join(here, "lib", "stratify.lx"), encoding="utf-8").read()

def analyse_with_lattix(edges, nrules):
    dep = ", ".join(f"({u},{v},{w})" for u, v, w in edges) or "(0,0,0)"
    node = ", ".join(f"({i})" for i in range(nrules)) or "(0)"
    src = (STRAT + f"\ntable dep = {dep}\ntable node = {node}\n"
           "use stratifier(dep, node) as s\n")
    p = L.parse(src); L.check(p); d = L.stratify(p); L.io_rounds(p); L.certify(p)
    st, _, stats = L.run(p, out=io.StringIO(), ranks=True, engine='worklist')
    bad = bool(st['s_unstratifiable'].get((), False))
    lev = {k[0]: v for k, v in st['s_level'].items()}
    return bad, lev, d, stats, (p, st, stats)

W = 88
print("=" * W)
print("  自己適用 — Lattix の成層器を Lattix で書き、Python 実装と突き合わせる")
print("  Python 版 60行（Tarjan+縮約+トポロジカル）  vs  Lattix 版 6行")
print("=" * W)
print(f"  {'例題':<22} {'規則':>4} {'辺':>4} | {'Python 深度':>11} {'Lattix 深度':>11}"
      f" {'層割当':>8} | {'不成層':>7}")
print("-" * W)

ok = True
for path in sorted(glob.glob(os.path.join(here, "examples", "*.lx"))):
    name = os.path.basename(path)
    src = open(path, encoding="utf-8").read()
    try:
        p = L.parse(src, base=here); L.check(p)
    except L.LattixError as e:
        print(f"  {name:<22} (front end rejects: {str(e).splitlines()[0][:40]})")
        continue
    edges = L.dependency_edges(p)
    n = len(p.rules)
    if n > 200:
        # Lattix で書いた成層器は推移閉包なので辺の数に二乗で効く。
        # **黙って飛ばさない**: 何を測っていないかを書いて飛ばす。
        print(f"  {name:<22} {n:>4} {len(edges):>4} | 規模のため未測定"
              f"（Lattix 版成層器は推移閉包＝辺に二乗）")
        continue
    try:
        pd = L.stratify(p); pbad = False
        pylev = {r.id: r.stratum for r in p.rules}
    except L.LattixError:
        pd, pbad, pylev = None, True, {}
    bad, lev, _, _, prov = analyse_with_lattix(edges, n)
    if pbad:
        agree = bad
        print(f"  {name:<22} {n:>4} {len(edges):>4} | {'棄却':>11} "
              f"{('棄却' if bad else '通過'):>11} {'—':>8} | {'✓' if agree else '✗':>7}")
        ok &= agree
        continue
    lxd = (max(lev.values()) + 1) if lev else 0
    same_assign = all(lev.get(i, 0) == pylev.get(i, 0) for i in range(n))
    agree = (lxd == pd) and same_assign and not bad
    ok &= agree
    print(f"  {name:<22} {n:>4} {len(edges):>4} | {pd:>11} {lxd:>11}"
          f" {('一致' if same_assign else '不一致'):>8} | {'✓' if agree else '✗':>7}")

# --- 最後の環: 成層器の答えそのものを、検査器にかける -------------------
import attest as A
print("-" * W)
print("  そして成層器の *答えそのもの* を検査器にかける")
sample = sorted(glob.glob(os.path.join(here, "examples", "*.lx")))[0]
p0 = L.parse(open(sample, encoding="utf-8").read(), base=here); L.check(p0)
e0 = L.dependency_edges(p0)
dep = ", ".join(f"({u},{v},{w})" for u, v, w in e0) or "(0,0,0)"
node = ", ".join(f"({i})" for i in range(len(p0.rules))) or "(0)"
ssrc = (STRAT + f"\ntable dep = {dep}\ntable node = {node}\n"
        "use stratifier(dep, node) as s\n")
pp = L.parse(ssrc); L.check(pp); L.stratify(pp); L.io_rounds(pp); L.certify(pp)
sst, _, sstats = L.run(pp, out=io.StringIO(), ranks=True)
store = {f: {k: pp.fields[f].observe(v) for k, v in d.items()}
         for f, d in sst.items()}
rank = {f: {} for f in pp.fields}
for (f, k), r in sstats['rank'].items(): rank[f][k] = r
rep = A.attest(ssrc, store, rank)
print(f"   {'✓' if rep.sound else '✗'} SOUND {'✓' if rep.sound else '✗'}   "
      f"COMPLETE {'✓' if rep.complete else '✗'}   "
      f"（規則実例 {rep.instances} 個を1パス）")
print("   → コンパイラの中核解析の答えが、コンパイラを信頼せずに検証できる。")
ok &= rep.sound

print("-" * W)
print("  すべて一致" if ok else "  不一致あり")
print("=" * W)
print("  Lattix 版の成層器はそれ自体が Lattix プログラムなので:")
print("   * 決定性・増分・分散・証明書つき検査 —— 全部そのまま効く")
print("   * 深度署名を持つ部品として `use` できる")
print("   * つまりコンパイラの中核解析が、言語の保証の内側に入った")
print("=" * W)
sys.exit(0 if ok else 1)
