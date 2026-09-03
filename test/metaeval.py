#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lattix で書いたメタ評価器が、Lattix のプログラムを走らせる。

段は二つしかない:
  examples/21_lex.lx    バイト列 → トークンの表
  examples/25_eval.lx   トークンの表 → **答え**（22_parse.lx を include している）

ホストがやるのは場を表に落とすことだけである。木も、記号表も、作らない。
項の DAG は評価器と同じプログラムの中で生きていて、構成子のアクセサ場
（`ebin_l` / `efref_args` / `cons_head` …）がそのまま DAG である。
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

W = 84
EX = os.path.join(ROOT, 'examples')


def strip(path, *pre):
    # include を先に展開してから差し替える —— 取り込んだ側の `table tok`
    # （置き場所だけの一行）が残っていると、こちらの表を上書きしてしまう。
    text = L._expand_includes(open(path, encoding='utf-8').read(), EX)
    return "\n".join(ln for ln in text.splitlines() if not ln.startswith(pre))


def go(src, extra=""):
    p = L.parse(src + "\n" + extra, base=EX)
    L.check(p); d = L.stratify(p); L.io_rounds(p); L.certify(p)
    st, _, stats = L.run(p, out=io.StringIO())
    return p, st, d, stats


def tokens(target):
    raw = open(target, 'rb').read()
    codes = list(raw) + [32]
    p, st, _d, _s = go("table ch = " + ", ".join(f"({i},{c})" for i, c in enumerate(codes)),
                       strip(os.path.join(EX, '21_lex.lx'), 'table ch'))
    o = lambda f: {k[0]: p.fields[f].observe(v) for k, v in st[f].items()}
    tk, tc, tc2, tline, tsym, tint = (o('tk'), o('tc'), o('tc2'),
                                      o('tline'), o('tsym'), o('tint'))
    return [(k, tk[k], tc[k], tc2.get(k, 0), tline[k],
             tint[k] if tk[k] == 1 else tsym[k]) for k in sorted(tk)]


def addr(s):
    a = 0
    for c in reversed(s.encode()): a = L.ctor_id('cons', [c, a])
    return a


def main(target):
    rows = tokens(target)
    tbl = "table tok = " + ", ".join(str(r).replace(" ", "") for r in rows)
    p, st, d, stats = go(tbl, strip(os.path.join(EX, '25_eval.lx'), 'table tok'))
    got = {k: p.fields['val'].observe(v) for k, v in st['val'].items()}
    got.update({k: True for k, v in st['valb'].items()
                if p.fields['valb'].observe(v)})

    ref = L.parse(open(target, encoding='utf-8').read())
    L.check(ref); L.stratify(ref); L.io_rounds(ref); L.certify(ref)
    rst, _, _ = L.run(ref, out=io.StringIO())
    want = {}
    for f in ref.fields:
        for k, v in rst[f].items():
            ov = ref.fields[f].observe(v)
            if ov is None: continue
            want[(addr(f),) + k] = ov
    same = got == want

    print("=" * W)
    print("  Lattix で書いたメタ評価器が、Lattix のプログラムを走らせる")
    print("=" * W)
    print(f"  対象: {os.path.basename(target)}   トークン {len(rows)}   "
          f"メタ側の逐次深度 {d}   join {stats['joins']}")
    show = lambda d: sorted((k[1], v) for k, v in d.items())
    print(f"  メタ評価器の答え: {show(got)}")
    print(f"  解釈実行の答え  : {show(want)}")
    print("-" * W)
    print("  一致" if same else "  不一致")
    print("  段は二つ。ホストは場を表に落としただけで、木も記号表も作っていない。")
    print("  **記述は二度使われる** —— 値として評価される経路と、座標として")
    print("  評価される経路。混ぜると『値が座標になる』＝非単調で、処理系が棄却する。")
    print("=" * W)
    return 0 if same else 1


if __name__ == '__main__':
    if len(sys.argv) > 1:
        sys.exit(main(sys.argv[1]))
    bad = 0
    for name in ('01_shortest', '26_reach'):
        bad |= main(os.path.join(EX, name + '.lx'))
    sys.exit(bad)
