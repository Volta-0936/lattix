# -*- coding: utf-8 -*-
"""**内容アドレスは、引数の一次式である（法 M）。**

   hash-consing と多面体モデルは、同じ算術である ——
   これは主張ではなく、`ctor_id` の定義から出る恒等式である。

   `ctor_id` は Horner の折り込みで

     h ← (h·K + 引数の数 + 1) mod M      （名前と引数の数だけで決まる定数）
     各引数 a:  h ← (h·K + enc(a)) mod M
     番地 = h1 · M2 + h2

   と書かれている。mod は環の準同型なので展開できて、引数が整数なら

     h_M = C(名前, 引数の数) + Σ_i (3 · K^(n-1-i)) · a_i    (mod M)

   **係数は定数**である（引数にも点にも依らない）。だから構成子の番地は
   軸の一次式であり、いまの写像の言葉に足りないのは **法**（mod）と
   **二本目の間接の項**だけである —— 新しい概念は一つも要らない。

   この恒等式が壊れたら、多面体の道は構成子に届かなくなる。
   だから試験にする（`_enc` の形を変えたら、ここが先に落ちる）。
"""
import os, sys, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

M1, M2, K1, K2 = L.CTOR_M1, L.CTOR_M2, L.CTOR_K1, L.CTOR_K2


def const(name, n, m, k):
    """名前と引数の数だけで決まる定数（引数に依らない）。"""
    c = (L._fold(name.encode(), m, k) * k + n + 1) % m
    return (c * pow(k, n, m)) % m


def coeff(i, n, m, k):
    """i 番目の引数の係数。enc(整数 v) = 3(v mod M) なので 3·K^(n-1-i)。"""
    return (3 * pow(k, n - 1 - i, m)) % m


def fold_affine(name, args, m, k):
    s = const(name, len(args), m, k)
    for i, a in enumerate(args):
        s = (s + coeff(i, len(args), m, k) * (a % m)) % m
    return s


def addr_affine(name, args):
    return fold_affine(name, args, M1, K1) * M2 + fold_affine(name, args, M2, K2)


def main():
    W = 74
    print("=" * W)
    print("  内容アドレスは引数の一次式である（法 M）—— 多面体の道が構成子に届く根拠")
    print("=" * W)
    rng = random.Random(20260828)
    ok = bad = 0
    for name, n in (('cons', 2), ('node', 3), ('leaf', 2), ('evar', 1),
                    ('because_binary', 3), ('ebool', 1), ('x', 4)):
        for _ in range(300):
            args = tuple(rng.randrange(0, 1 << 40) for _ in range(n))
            if L.ctor_id(name, args) == addr_affine(name, args): ok += 1
            else:
                bad += 1
                if bad <= 3: print(f"  差 {name}{args}")
    print(f"  ctor_id == 一次式 mod M      一致 {ok} / 違う {bad}")

    # 係数が本当に定数であること（引数を 1 動かすと、決まった量だけ動く）
    for name, n, i in (('cons', 2, 0), ('cons', 2, 1), ('node', 3, 1)):
        want = coeff(i, n, M1, K1)
        got = set()
        for base in (0, 1, 7, 12345, 999999, (1 << 39)):
            a = [11, 22, 33][:n]; a[i] = base
            b = list(a); b[i] = base + 1
            got.add((fold_affine(name, b, M1, K1) - fold_affine(name, a, M1, K1)) % M1)
        assert got == {want}, (name, i, got, want)
        print(f"  {name} の第 {i} 引数の係数（法 M1）  {want}   定数 ✓")

    # 引数が場の読みでも同じ —— そのときの値は番地の面に写せばよい（fp と同じ形）
    print()
    print("  つまり構成子の番地は「定数 + Σ 係数·引数」であり、")
    print("  写像の言葉に足りないのは **法** と **二本目の間接の項**だけである。")
    print("=" * W)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
