#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
領域ごとの完全性 —— 実測ではなく **証明** にする。

v1.6 は「領域 r まで処理したらそのセルは最終」と *実測* しただけだった。
主張の規律に照らせば、これは主張してよい強さではない。ここで証明にする。

  (0) 祖先閉性 : scope 内のセルへの寄与が読むセルは、すべて scope 内にある
  (A) 安定性   : scope 内のセルについて、どの寄与も吸収済み
  (B) 有基性   : 主張された値はすべて、より小さい階数から導出できる

  (0) ∧ (A) ⟹ lfp|scope ⊑ S|scope   —— 外がどれだけ育っても scope は動かない
  (B)       ⟹ S ⊑ lfp
  ⟹ **S|scope = lfp|scope**

そしてもう一つ、v1.6 で私が間違えていたことを直す。

  凝縮グラフは **半順序** である。v1.6 はそこに位相ソートの pop 順を付けて
  全順序にした。無い制約を発明していた。192 個の領域を一列に並べていたが、
  本当に順序があるのは高さ（最長鎖）ぶんだけである。

半順序の **下方集合（down-set）** 全体は、包含で分配束をなす（Birkhoff 1937）。
つまり「どこまで終わったか」自体が束の要素であり、別々に進んだ二つの実行の合流は
**和集合 = join** である。**完全性の証明書が、答えと同じように合成できる。**

ストリーミングのウォーターマークは、この半順序が *鎖* である特別な場合にすぎない。
"""
import io, os, sys, copy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
import attest as A

W = 92
ok = True

def comps(k, per=6):
    e = []; n = 0
    for _ in range(k):
        for i in range(per - 1): e.append((n + i, n + i + 1))
        n += per
    return e, n

def src(E, n):
    return ("table edge = " + ", ".join(f"({a},{b})" for a, b in E) + "\n"
            "table node = " + ", ".join(f"({i})" for i in range(n)) + "\n"
            "field seen : or\n"
            "seen[i] <- true            for (i,j) in edge\n"
            "seen[j] <- true            for (i,j) in edge if seen[i]\n"
            "field far : or\n"
            "far[v] <- true             for (v) in node if not seen[v]\n")

def load(s):
    p = L.parse(s); L.check(p); d = L.stratify(p); L.io_rounds(p); L.certify(p)
    return p, d

def obs(p, st):
    return {f: {k: p.fields[f].observe(v) for k, v in d.items()} for f, d in st.items()}

def ranks_of(stats):
    R = {}
    for (f, k), v in (stats.get('rank') or {}).items(): R.setdefault(f, {})[k] = v
    return R

# ==========================================================================
print("=" * W)
print("  1. 領域は全順序ではない —— v1.6 は無い制約を発明していた")
print("=" * W)
print(f"  {'成分数':>6} {'セル':>6} {'領域(SCC)':>10} | {'v1.6 逐次段数':>13} "
      f"{'真の高さ':>8} {'幅(同時に走れる)':>16}")
print("-" * W)
for k in (1, 2, 4, 8, 16):
    E, n = comps(k); S = src(E, n)
    p, d = load(S)
    st, stt, fin, nc = L.run_regional(p, out=io.StringIO())
    print(f"  {k:>6} {nc:>6} {stt['ncomp']:>10} | {stt['ncomp']:>13} "
          f"{stt['height']:>8} {stt['width']:>16}")
print("-" * W)
print("  高さは成分数によらず一定、幅だけが伸びる。これが正しい形である。")
print("  v1.6 の『領域数』は逐次段数ではなかった。**私が並べただけだった。**")

# ==========================================================================
print("\n" + "=" * W)
print("  2. 途中で止めた実行に、証明書が出る")
print("=" * W)
K = 16
E, n = comps(K); S = src(E, n)
p_full, _ = load(S)
full, _, _ = L.run(p_full, out=io.StringIO())
FULL = obs(p_full, full)

p0, _ = load(S)
_, s0, _, ncells = L.run_regional(p0, out=io.StringIO())
H = s0['height']
print(f"  成分 {K} 個 / 頂点 {n} / セル {ncells} / 領域 {s0['ncomp']} / 高さ {H}")
print(f"\n  {'深さまで':>8} {'確定セル':>9} {'祖先閉性':>9} {'安定(scope内)':>13} "
      f"{'有基性':>8} {'完全性':>9} {'最終値と一致':>13}")
print("-" * W)
for upto in range(1, H + 1):
    p, _ = load(S)
    st, stt, fin, _ = L.run_regional(p, out=io.StringIO(), upto=upto, ranks=True)
    done = set(fin)
    rep = A.attest(S, obs(p, st), ranks_of(stt), scope=done)
    O = obs(p, st)
    agree = sum(1 for (f, kk) in done if FULL[f].get(kk) == O[f].get(kk))
    good = rep.sound and rep.complete and agree == len(done)
    ok &= good
    print(f"  {upto:>8} {len(done):>9} {'✓' if not rep.closure else '✗':>9} "
          f"{'✓' if not rep.stability else '✗':>13} {'✓' if not rep.grounded else '✗':>8} "
          f"{'✓ COMPLETE' if rep.complete and rep.sound else '✗':>9} "
          f"{agree}/{len(done):<8}")
print("-" * W)
print("  検査器は『最終値と一致』の列を見ていない。完全解を持っていないからである。")
print("  それでも **その scope については COMPLETE** と言える。それが証明の意味である。")

# ==========================================================================
print("\n" + "=" * W)
print("  3. 空振りしていないことの確認（証明書は嘘を拒む）")
print("=" * W)
p, _ = load(S)
st, stt, fin, _ = L.run_regional(p, out=io.StringIO(), upto=H - 1, ranks=True)
done = set(fin); O = obs(p, st); R = ranks_of(stt)
base = A.attest(S, O, R, scope=done)
print(f"  正しい scope（{len(done)} セル）        : "
      f"{'✓ COMPLETE' if base.complete and base.sound else '✗'}")

# (a) まだ値が育っていないセルを scope に足す → 安定性が落ちる
#     （深く進んだ実行では「未完了だが既に最終値」のセルもある。それを
#      COMPLETE と言うのは *正しい*。だから浅い実行で試す。）
p1, _ = load(S)
st1, stt1, fin1, _ = L.run_regional(p1, out=io.StringIO(), upto=1, ranks=True)
O1, R1, done1 = obs(p1, st1), ranks_of(stt1), set(fin1)
# **並べてから選ぶ。** 集合のまま [:1] を取っていたので、Python のハッシュ順で
# 被害者が変わり、20回に2回だけ落ちる試験になっていた。
# その揺らぎのおかげで検査器の穴（ガードが偽の実例を見ていなかった）が出た。
young = sorted(c for c in ({(f, k) for f in FULL for k in FULL[f]} - done1)
               if FULL[c[0]].get(c[1]) != O1[c[0]].get(c[1]))[:1]
rep = A.attest(S, O1, R1, scope=done1 | set(young))
hit = bool(rep.closure or rep.stability)
ok &= hit
print(f"  育ちきっていないセルを1つ足す     : "
      f"{'✓ 棄却' if hit else '✗ 見逃し'}   （閉性 {len(rep.closure)} / 安定 {len(rep.stability)}）")

# (b) 証明済みのセルの値を壊す → 安定性か有基性が落ちる
bad = copy.deepcopy(O); target = None
for f, k in sorted(done):
    if O[f].get(k) is True:
        bad[f][k] = False; target = (f, k); break
rep2 = A.attest(S, bad, R, scope=done)
hit2 = not (rep2.sound and rep2.complete)
ok &= hit2
print(f"  確定セル {str(target):<22}を反転 : "
      f"{'✓ 棄却' if hit2 else '✗ 見逃し'}   （安定 {len(rep2.stability)} / 有基 {len(rep2.grounded)}）")

# (a2) 祖先を1つ scope から外す → 祖先閉性そのものが落ちる
victim = ('seen', (0,))          # 鎖の根。scope 内の誰かが必ずこれを読む
rep1b = A.attest(S, O, R, scope=done - {victim})
hitb = bool(rep1b.closure)
ok &= hitb
print(f"  祖先を1つ scope から外す          : "
      f"{'✓ 棄却' if hitb else '✗ 見逃し'}   （閉性 {len(rep1b.closure)}）")

# (c) 階数を1つ壊す → 有基性が落ちる。
#     基底規則からも導ける セルでは階数1は正当なので、**再帰的にしか支えの無い**
#     セル（＝階数が最大のもの）を選ぶ。ここを雑にやると「捕捉した」と誤読する。
badR = {f: dict(d) for f, d in R.items()}
deep = max(sorted(done), key=lambda c: R.get(c[0], {}).get(c[1], 0))
badR[deep[0]][deep[1]] = 1
rep3 = A.attest(S, O, badR, scope=done)
hit3 = not rep3.sound
ok &= hit3
print(f"  階数を浅くする {str(deep):<16}   : "
      f"{'✓ 棄却' if hit3 else '✗ 見逃し'}   （{R[deep[0]][deep[1]]} → 1、有基 {len(rep3.grounded)}）")

# ==========================================================================
print("\n" + "=" * W)
print("  4. 証明書が合成する —— 下方集合の join（Birkhoff 1937）")
print("=" * W)
p, _ = load(S)
inst, order, ncomp, ncells, P = L.cell_regions(p)
half = n // 2
regA = {P['comp'][P['cellid'][c]] for c in P['cells'] if c[1] and c[1][0] < half}
regB = {P['comp'][P['cellid'][c]] for c in P['cells'] if c[1] and c[1][0] >= half}
dA, dB = L.region_closure(P, regA), L.region_closure(P, regB)

pa, _ = load(S)
sA, stA, finA, _ = L.run_regional(pa, out=io.StringIO(), regions=regA, ranks=True)
pb, _ = load(S)
sB, stB, finB, _ = L.run_regional(pb, out=io.StringIO(), regions=regB, ranks=True)

repA = A.attest(S, obs(pa, sA), ranks_of(stA), scope=set(finA))
repB = A.attest(S, obs(pb, sB), ranks_of(stB), scope=set(finB))

# 合流は join。ロックも合意も要らない —— 答えのときと同じ理由で。
merged = {f: dict(d) for f, d in sA.items()}
for f, d in sB.items():
    lat = pa.fields[f]
    for k, v in d.items():
        merged[f][k] = lat.join(merged[f][k], v) if k in merged[f] else v
Rm = ranks_of(stA)
for f, d in ranks_of(stB).items():
    for k, v in d.items():
        Rm.setdefault(f, {})
        Rm[f][k] = min(Rm[f][k], v) if k in Rm[f] else v
scope_m = set(finA) | set(finB)
repM = A.attest(S, obs(pa, merged), Rm, scope=scope_m)

closed = L.region_closure(P, dA | dB) == (dA | dB)
M = obs(pa, merged)
agree = sum(1 for (f, kk) in scope_m if FULL[f].get(kk) == M[f].get(kk))
good = repA.complete and repB.complete and repM.complete and repM.sound \
       and closed and agree == len(scope_m)
ok &= good
print(f"  機械A  領域 {len(dA):>3} / セル {len(finA):>3}   "
      f"{'✓ COMPLETE(A)' if repA.complete and repA.sound else '✗'}")
print(f"  機械B  領域 {len(dB):>3} / セル {len(finB):>3}   "
      f"{'✓ COMPLETE(B)' if repB.complete and repB.sound else '✗'}")
print(f"  合流   領域 {len(dA | dB):>3} / セル {len(scope_m):>3}   "
      f"{'✓ COMPLETE(A∪B)' if repM.complete and repM.sound else '✗'}"
      f"   下方集合のまま: {'✓' if closed else '✗'}   最終値と一致 {agree}/{len(scope_m)}")
print("-" * W)
print("  合流に使ったのは join だけである。証明書を作り直してもいない —— **足しただけ**。")
print("  「どこまで終わったか」が束の要素だから、進捗が答えと同じ規則で合成する。")
print("  ウォーターマークはこの半順序が *鎖* の場合にすぎない。時間軸は一次元だから。")
print("=" * W)
sys.exit(0 if ok else 1)
