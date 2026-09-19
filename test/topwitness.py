#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**閉路で押し上げられた ⊤ に、証人を付ける。**

階数の証明書は帰納の半分である —— 「この座標は a *以上* である」を、
より小さい階数のセルから示す。だが定数伝播のループはこうなる:

    pc1 で y=0        cvin[3,y] に 0 が届く
    pc3 で y=y+x      一周して 1 が戻る
    0 ≠ 1             よって cvin[3,y] = ⊤（定数でない）

最終の答えの中には ⊤ しか残っていない。**二つ目の確定値 1 は ⊤ に吸収されて
消えている。** だから「より小さい階数の *答えの中の* セルから導ける」は言えない。
これは余帰納の側 —— 「この座標は a より上でしかありえない」の話である。

証人はどこにいたか。**捨てていただけである。**
平坦束のセルは生涯にただ一つの確定値しか持てない（⊥ → a → ⊤）。
だから「⊤ になる前の値」は曖昧さなく決まる。それを集めた **影の店** は
最小不動点への途中経過で、有基性を見れば S₂ ⊑ lfp が言える。
そして影の中では、同じセルへ **相異なる二つの確定値が届いている**。

影は証明書の一部であり、検査器は処理系を信じない。だからここでは
影を三通りに壊して、**壊した影が通らないこと** も確かめる。
"""
import copy, io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L, attest as A

W = 84


def split(d):
    o = {}
    for (f, k), v in (d or {}).items(): o.setdefault(f, {})[k] = v
    return o


def certify(name, **kw):
    src = open(os.path.join(ROOT, 'examples', name), encoding='utf-8').read()
    p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    store, _c, st = L.run(p, out=io.StringIO(), ranks=True)
    obs = {f: {k: p.fields[f].observe(v) for k, v in d.items()}
           for f, d in store.items()}
    return (src, obs, split(st.get('rank')), split(st.get('pre')),
            split(st.get('prerank')))


print("=" * W)
print("  閉路の ⊤ に証人を付ける —— 影の店（⊤ になる前の確定値）")
print("=" * W)
src, obs, R, PRE, PR = certify('29_dataflow.lx')

bare = A.attest(src, obs, R)                                   # 影なし
full = A.attest(src, obs, R, pre=PRE, prerank=PR)              # 影あり
# 影が無ければ ⊤ は **示せない**（未証明）—— 健全とは言わない。影があれば示せる。
# （前は影なしでも SOUND ✓ と数えていた。恒等 `f <- f` で ⊤ を偽った証明書がそれで通った）
ok = (bare.cyclic_top and not full.cyclic_top and full.top_witness
      and not bare.sound and not bare.ok and bare.complete
      and full.sound and full.complete and full.ok)

print(f"  影の中のセル {sum(len(v) for v in PRE.values()):>4} 個"
      f"（平坦な場が ⊤ になる前に持っていた確定値）")
print("-" * W)
print(f"  影なし   witness {str(bare.top_witness):<26} 未証明 {bare.cyclic_top}")
print(f"  影あり   witness {str(full.top_witness):<26} 未証明 {full.cyclic_top}")
for f, key, vs in full.top_witness:
    print(f"      {f}[{', '.join(map(str, key))}] = ⊤   ←   "
          f"{vs[0]} と {vs[1]} が同じ座標に届く")

# ── 壊した影は通らない ────────────────────────────────────────────────
print("-" * W)
print("  影も証明書である。だから壊して落ちることを確かめる:")
sab = [("影の値を捏造", lambda P, K: P['cvout'].__setitem__((3, 'y'), 99)),
       ("影の階数を 0 に", lambda P, K: K['cvin'].__setitem__((3, 'y'), 0)),
       ("影の階数を巨大に", lambda P, K: K['cvout'].__setitem__((3, 'y'), 999))]
for label, mut in sab:
    P2, K2 = copy.deepcopy(PRE), copy.deepcopy(PR)
    mut(P2, K2)
    r = A.attest(src, obs, R, pre=P2, prerank=K2)
    good = (not r.top_witness) and r.cyclic_top
    ok &= bool(good)
    print(f"    {label:<16} 証人 {'出ない ✓' if good else '出てしまった ✗'}")

# ── 偽の ⊤ は通らない（2026-09-19 に見つけた二つの穴）─────────────────────
# ① 恒等 `f <- f`: 最終の答えでは、1 と ⊤ の寄与だけ —— 本物（f <- f + 1）と同じ形に見える。
#    前は「閉路で押し上げられた ⊤」として健全に数え、ATTESTED と言った。
# ② 下の層の `not z`: 影が下の層まで ⊤ の前の値（0）に戻すと、`not z` が立って存在しない
#    寄与 5 が証人になった（答えは 7）。影は層ごとに組む。
print("-" * W)
print("  偽の ⊤ は通らない:")
forged = [
    ("恒等で ⊤ を偽る", """table ch = (0,32)
field f : flat bound 4
f[0] <- 1
f[z] <- f[z]   for (z) in 0 .. 0
""", {'f': {(0,): L.TOP}}, {'f': {(0,): 1}}, {'f': {(0,): 1}}, {'f': {(0,): 1}}),
    ("下の層の not を影で立てる", """table ch = (0,32)
field z : flat bound 1
field x : flat bound 1
z[0] <- 0
z[0] <- 1
x[q] <- 5   for (q) in 0 .. 0 if not z[q]
x[q] <- 7   for (q) in 0 .. 0
x[q] <- x[q]   for (q) in 0 .. 0
""", {'z': {(0,): L.TOP}, 'x': {(0,): L.TOP}}, {'z': {(0,): 1}, 'x': {(0,): 2}},
     {'z': {(0,): 0}, 'x': {(0,): 7}}, {'z': {(0,): 1}, 'x': {(0,): 1}}),
]
for label, fsrc, fS, fR, fP, fK in forged:
    r0 = A.attest(fsrc, fS, fR)
    r1 = A.attest(fsrc, fS, fR, pre=fP, prerank=fK)
    good = (not r0.ok) and (not r1.ok)
    ok &= good
    print(f"    {label:<22} 影なし {'通らない ✓' if not r0.ok else '通った ✗'}   "
          f"影あり {'通らない ✓' if not r1.ok else '通った ✗'}")

# ── ⊤ の無いプログラムでは影は何も主張しない ──────────────────────────
src2, obs2, R2, PRE2, PR2 = certify('01_shortest.lx')
r2 = A.attest(src2, obs2, R2, pre=PRE2, prerank=PR2)
clean = r2.ok and not r2.top_witness and not r2.cyclic_top
ok &= clean
print(f"    {'⊤ の無い例題':<16} 証人 {'出ない ✓' if clean else '✗'}"
      f"   (01_shortest: SOUND {'✓' if r2.sound else '✗'}"
      f" COMPLETE {'✓' if r2.complete else '✗'})")

# ── 不変条件9: 参照実装でしか動かない機能は、機能ではない ────────────────
print("-" * W)
import runtime as R
info = R.build(open(os.path.join(ROOT, 'examples', '29_dataflow.lx'),
                    encoding='utf-8').read())
nstore, nmeta = R.run(info['exe'], R.write_data(info['prog'],
                                               os.path.join(info['dir'], 'd.lxd')))
nrep = A.attest(src, nstore, nmeta.get('rank', {}),
                pre=nmeta.get('pre'), prerank=nmeta.get('prerank'))
same = (sorted(map(repr, nrep.top_witness)) == sorted(map(repr, full.top_witness))
        and not nrep.cyclic_top and nrep.ok)
ok &= same
np = sum(len(v) for v in (nmeta.get('pre') or {}).values())
print(f"  ネイティブ（C）も同じ影を出す: セル {np} 個   証人 {nrep.top_witness}")
print(f"    解釈実行と一致 {'✓' if same else '✗'}"
      "   —— **参照実装でしか動かない機能は、機能ではない**（不変条件9）")

print("-" * W)
print("  一致" if ok else "  不一致")
print("  階数は下から（帰納）。影は上から（余帰納）。**⊤ は上界の証人で支えられる。**")
print("  証人は新しく計算したものではない —— 実行がすでに持っていて、捨てていた。")
print("=" * W)
sys.exit(0 if ok else 1)
