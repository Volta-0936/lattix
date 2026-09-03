# -*- coding: utf-8 -*-
"""**層は座標である（局所成層の決定可能な十分条件）。**

   場の粒度の成層器は、否定が同じ場の小さい座標を読む形
   （lvl[s,c] が lvl[s-1,c'] を否定で読む）を輪と見なして棄却してきた。
   だが s が静的な区間なら、代入して展開した具体例の集合は元と同一の
   グラウンド集合であり、座標で場を裂いたグラフで成層が立てば、
   それは s に沿った整礎帰納の証明である —— 依存距離が正なら軸を
   逐次に回してよい（多面体の合法性と同じ主張）。

   検べること:
     1. 圧縮形（for (s) in 1..3 + s-1 の否定読み）が受かり、答えが
        手で計算した完全モデルと一致する
     2. C の測定器（runtime.py）も同じ答えを出す
     3. 真に病んだ形（表の上の自己否定・座標が定数にならない読み）は
        今までどおり棄却される —— 広げたのは証明できる形だけ
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

GOOD = """\
table e = (0,1), (1,2), (2,3)
field lvl : or bound 4 8
lvl[0, i] <- true       for (i,j) in e
lvl[s, j] <- true       for (s) in 1 .. 3 for (i,j) in e if lvl[s-1, i] if not lvl[s-1, j]
print lvl
"""
WANT = {(0, 0): True, (0, 1): True, (0, 2): True, (1, 3): True}

BAD_TABLE = """\
table node = (0), (1)
field alive : or bound 4
alive[n] <- true    for (n) in node if not alive[n]
print alive
"""
BAD_COORD = """\
table e = (0,1), (1,0)
field g : flat bound 8
g[i] <- j           for (i,j) in e
field lvl : or bound 4 8
lvl[0, i] <- true   for (i,j) in e
lvl[s, j] <- true   for (s) in 1 .. 3 for (i,j) in e if not lvl[g[i], j]
print lvl
"""


def main():
    W = 74
    print("=" * W)
    print("  層は座標である —— 展開が証明、座標が場を裂く")
    print("=" * W)
    p = L.parse(GOOD); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    st, _, _ = L.run(p, out=io.StringIO())
    got = dict(st.get('lvl', {}))
    assert got == WANT, (got, WANT)
    print(f"  受かる形: 解釈実行が完全モデルと一致 ({len(got)} 升) ✓")
    print(f"  展開後の規則 {len(p.rules)} 本 / 層 {len(p.strata)}")

    import runtime as R
    info = R.build(GOOD, keep=os.path.join(ROOT, 'work', '_axtest'))
    q = L.parse(GOOD)
    d = R.write_data(q, os.path.join(ROOT, 'work', '_axtest', 'data.lxd'))
    gotc, _ = R.run(info['exe'], d)
    assert dict(gotc.get('lvl', {})) == WANT, gotc.get('lvl')
    print("  C の測定器も同じ答え ✓")

    for name, src in (('表の上の自己否定', BAD_TABLE),
                      ('座標が定数にならない否定読み', BAD_COORD)):
        try:
            p = L.parse(src); L.check(p); L.stratify(p)
        except L.LattixError:
            print(f"  断る形: {name} → 棄却 ✓")
        else:
            print(f"  ✗ {name} が通ってしまった"); return 1
    print("=" * W)
    return 0


if __name__ == '__main__':
    sys.exit(main())
