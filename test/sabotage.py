#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
検査器を信用しないための試験 — 故意に壊して、捕まえられるかを測る。

第1部  生成された C に変異を注入して再コンパイルする（誤コンパイルの模擬）。
       答えが実際に変わった変異のうち、検査器が何割を捕まえるか。
第2部  攻撃者が答えと階数の *両方* を自由に捏造できる場合。
       階数は信頼しない。信頼するのは検査器の算術だけ。
"""
import os, re, sys, io, random, subprocess, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L, native as N, attest as A

W = 90

# ==========================================================================
# 対象プログラム
# ==========================================================================
def graph(n, m, seed=11):
    r = random.Random(seed); e = set()
    for i in range(1, n): e.add((r.randrange(i), i, r.randint(1, 30)))
    while len(e) < m:
        a, b = r.randrange(n), r.randrange(n)
        if a != b: e.add((a, b, r.randint(1, 30)))
    return sorted(e)

EDGES = graph(120, 600)
SRC = ("table edges = " + ", ".join(f"({a},{b},{w})" for a, b, w in EDGES) + "\n"
       "field dist : min\n"
       "dist[0] <- 0\n"
       "dist[j] <- dist[i] + w   for (i,j,w) in edges\n")

# ==========================================================================
# 第1部 — C への変異注入
# ==========================================================================
MUTATIONS = [
    ("比較演算子の反転",        r"if\(v < F_dist", "if(v <= F_dist", 1),
    ("加算を減算に",            r"\+ T_edges\[S0_R0\[IT\]\]\[2\]\)",
                                "- T_edges[S0_R0[IT]][2])", 1),
    ("重みを1ずらす",           r"T_edges\[S0_R0\[IT\]\]\[2\]\)",
                                "T_edges[S0_R0[IT]][2] + 1)", 1),
    ("⊥ガードの削除",           r"if\(F_dist\[.*?\] == INT64_MAX\) return 0;\n", "", 1),
    ("初期値を汚染",            r"F_dist\[i\]=INT64_MAX;", "F_dist[i]=(i==7?99:INT64_MAX);", 1),
    ("伝播の欠落 (lost wakeup)", r"FIRES\+\+; return 1;", "FIRES++; return 0;", 1),
    ("索引の切り詰め",          r"for\(int q=S0_IXS\[SL\];q<S0_IXS\[SL\+1\];q\+\+\)",
                                "for(int q=S0_IXS[SL];q<S0_IXS[SL+1]-1;q++)", 1),
    ("stale判定の反転",         r"if\(pp > VAL\(SL\)\) continue;", "if(pp < VAL(SL)) continue;", 1),
    ("ヒープ比較の反転",        r"if\(h->a\[q\]\.p<=h->a\[i\]\.p\)break;",
                                "if(h->a[q].p>=h->a[i].p)break;", 1),
    ("地上データの改竄",        r"\{(\d+),(\d+),(\d+)\},\{", None, 1),
    ("キー計算のずれ",          r"S0_TGT\[IT\]\]", "S0_TGT[IT]+1]", 1),
    ("階数の捏造(小)",          r"if\(_m\+1>RANK\[T\]\) RANK\[T\]=_m\+1;", "RANK[T]=1;", 1),
]

def truth(src):
    p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.io_rounds(p); L.certify(p)
    st, _, _ = L.run(p, out=io.StringIO())
    return {k: p.fields['dist'].observe(v) for k, v in st['dist'].items()}

def build_run(csrc, d):
    cf, ex = os.path.join(d, "m.c"), os.path.join(d, "m")
    open(cf, "w").write(csrc)
    r = subprocess.run(["gcc", "-O2", "-w", "-o", ex, cf], capture_output=True, text=True)
    if r.returncode: return None
    try:
        rr = subprocess.run([ex], capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    return rr.stdout

print("=" * W)
print("  第1部 — 生成された C に誤コンパイルを注入し、検査器が捕まえるかを測る")
print(f"  対象: 最短経路 頂点120 / 辺600。検査器は C を一度も見ない。")
print("=" * W)

info = N.compile_source(SRC)
BASE_C = open(info['csrc']).read()
GOLD = truth(SRC)
out0, _, _ = N.run_native(info['exe'])
st0, rk0 = N.to_store(info['prog'], info['plan'], out0, want_rank=True)
assert st0['dist'] == GOLD, "baseline mismatch"
rep0 = A.attest(SRC, st0, rk0)
print(f"\n  無傷のバイナリ: 答えは正しく、検査器は "
      f"{'ATTESTED' if rep0.ok else 'REJECTED(!!)'}  "
      f"（規則実例 {rep0.instances} 個を1パス）\n")

print(f"  {'注入した誤り':<24} {'答えは':<10} {'検査器':<12} 判定")
print("-" * W)
d = tempfile.mkdtemp(prefix="sab_")
caught = wrong = benign = certbad = 0
for name, pat, rep, _n in MUTATIONS:
    if rep is None:
        m = re.search(pat, BASE_C, re.M)
        if not m: print(f"  {name:<24} (パターン不一致)"); continue
        mut = BASE_C[:m.start()] + "{%d,%d,%d},{" % (int(m.group(1)), int(m.group(2)),
                                                     int(m.group(3)) + 5) + BASE_C[m.end():]
    else:
        mut, k = re.subn(pat, rep, BASE_C, count=1, flags=re.M)
        if k == 0: print(f"  {name:<24} (パターン不一致)"); continue
    out = build_run(mut, d)
    if out is None:
        print(f"  {name:<24} {'コンパイル失敗':<10} {'—':<12} （そもそも通らない）"); continue
    if out == "TIMEOUT":
        print(f"  {name:<24} {'停止せず':<10} {'—':<12} ✓ 実行時に露見"); wrong += 1; caught += 1; continue
    try:
        st, rk = N.to_store(info['prog'], info['plan'], out, want_rank=True)
    except Exception:
        print(f"  {name:<24} {'出力破損':<10} {'—':<12} ✓ 実行時に露見"); wrong += 1; caught += 1; continue
    bad = (st['dist'] != GOLD)
    r = A.attest(SRC, st, rk)
    if bad: wrong += 1
    elif r.ok: benign += 1
    else: certbad += 1
    if bad and not r.ok: caught += 1
    verdict = ("✓ 捕捉" if (bad and not r.ok) else
               ("✗ 見逃し" if bad else
                ("(答えは無傷)" if r.ok else "証明書が無効 → 再証明を要求")))
    print(f"  {name:<24} {'変わった' if bad else '変わらず':<10} "
          f"{'REJECTED' if not r.ok else 'ATTESTED':<12} {verdict}")

print("-" * W)
print(f"  答えが実際に変わった変異: {wrong} 件   検査器が捕捉: {caught} 件"
      f"   捕捉率 {100*caught/max(wrong,1):.0f}%")
print(f"  答えが変わらなかった変異: {benign} 件 → すべて ATTESTED（誤警報ゼロ）")
print(f"  答えは正しいが証明書が壊れた変異: {certbad} 件 → 棄却。")
print(f"    これは誤警報ではない。検査器の契約は「(答え, 証明書) の対を検査する」であって")
print(f"    「答えを当てる」ではない。壊れた証明書は再証明を要求するのが正しい。")

# ==========================================================================
# 第2部 — 答えも階数も攻撃者が捏造する場合
# ==========================================================================
print("\n" + "=" * W)
print("  第2部 — 攻撃者が答えと階数の *両方* を捏造できる場合")
print("  階数は信頼しない。整数が整列していることだけを使う。")
print("=" * W)

def forge(label, src, store, rank, should):
    r = A.attest(src, store, rank)
    got = "ATTESTED" if r.ok else "REJECTED"
    ok = (got == should)
    print(f"  {label:<44} → {got:<10} {'✓' if ok else '✗ 期待は ' + should}")
    return ok

allok = True
# (a) 値をひとつだけ小さく捏造（min 束では上に行く = 情報を増やす方向）
st = {'dist': dict(st0['dist'])}; rk = {'dist': dict(rk0['dist'])}
st['dist'][(9,)] = 0
allok &= forge("距離をひとつ 0 に捏造（安定性は保つ）", SRC, st, rk, "REJECTED")

# (b) 同時に階数も大きく捏造して正当化を狙う
rk2 = {'dist': dict(rk0['dist'])}; rk2['dist'][(9,)] = 10**6
allok &= forge("上に加えて階数を 10^6 に水増し", SRC, st, rk2, "REJECTED")

# (c) 全セルの階数を同一の巨大値にして順序を潰す
rk3 = {'dist': {k: 10**6 for k in st0['dist']}}
allok &= forge("全セルの階数を同一値にして整列を潰す", SRC, st0, rk3, "REJECTED")

# (d) 循環支持: p ⇐ q, q ⇐ p。最小不動点は空。両方 true と主張する。
CIRC = "table u = (0)\nfield p : or\nfield q : or\np[0] <- true for (x) in u if q[0]\nq[0] <- true for (x) in u if p[0]\n"
allok &= forge("循環支持で true を主張（真の答えは空）", CIRC,
               {'p': {(0,): True}, 'q': {(0,): True}},
               {'p': {(0,): 5}, 'q': {(0,): 3}}, "REJECTED")
allok &= forge("循環支持 + 階数を同一値に", CIRC,
               {'p': {(0,): True}, 'q': {(0,): True}},
               {'p': {(0,): 9}, 'q': {(0,): 9}}, "REJECTED")
allok &= forge("正しい答え（空）", CIRC, {'p': {}, 'q': {}}, {'p': {}, 'q': {}}, "ATTESTED")

# (e) 収束前の答え（伝播不足）
part = {'dist': {k: v for k, v in st0['dist'].items() if k[0] < 40}}
partr = {'dist': {k: v for k, v in rk0['dist'].items() if k[0] < 40}}
allok &= forge("途中で打ち切った答え（安定性が破れる）", SRC, part, partr, "REJECTED")

print("=" * W)
print("  階数は untrusted data である。攻撃者が自由に選んでよい。")
print("  それでも通らないのは、正当化が階数について *狭義に* 減少しなければならず、")
print("  整数が整列しているので循環が組めないからである。")
print("  信頼すべきは検査器の算術だけ。C コンパイラは信頼も検査もしていない。")
print("=" * W)
sys.exit(0 if (allok and caught == wrong) else 1)
