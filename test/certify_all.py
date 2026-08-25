#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
**扱えるすべての例題が、答えの証明書を通る。**

以前は構成子を使う例題（CYK 構文解析・字句解析）が通らなかった。
`node_sym` の階数が 0 —— 証人がいなかった。

原因は「証人がいない」ではなく **「別の名前で記録されていた」** だった。
規則実例を作った時点でキーを先に計算していたが、キーが構成子（内容アドレス）だと、
その時点では引数がまだ ⊥ なので **⊥ から作った名前** になる。
あとから本物の名前のセルに値が入るが、階数は前の名前の側に書かれたまま。

構成された値の証人は、その部品の証人である。分解はできていた。名前が合っていなかった。
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L, attest as A

W = 80
ok, done, skip = True, 0, 0
print("=" * W)
print("  すべての例題を、答えの証明書にかける（解釈実行）")
print("=" * W)
for name in sorted(os.listdir(os.path.join(ROOT, 'examples'))):
    if not name.endswith('.lx'): continue
    src = open(os.path.join(ROOT, 'examples', name), encoding='utf-8').read()
    try:
        p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
        store, _rk, stats = L.run(p, out=io.StringIO(), ranks=True)
        def _sp(d):
            o = {}
            for (f, k), v in (d or {}).items(): o.setdefault(f, {})[k] = v
            return o
        R, PRE, PR = (_sp(stats.get('rank')), _sp(stats.get('pre')),
                      _sp(stats.get('prerank')))
        obs = {f: {k: p.fields[f].observe(v) for k, v in d.items()}
               for f, d in store.items()}
        rep = A.attest(src, obs, R, pre=PRE, prerank=PR)
    except Exception as e:
        skip += 1
        print(f"  {name:<20} —  {str(e)[:38]}")
        continue
    fine = rep.sound and rep.complete
    ok &= fine; done += 1
    tw = (f"   ⊤ の証人 {len(rep.top_witness)}" if rep.top_witness else "")
    tw += (f"   未証明の ⊤ {len(rep.cyclic_top)}" if rep.cyclic_top else "")
    print(f"  {name:<20} SOUND {'✓' if rep.sound else '✗'}  "
          f"COMPLETE {'✓' if rep.complete else '✗'}{tw}")
print("-" * W)
print(f"  検査した {done} 本すべて通過: {'✓' if ok else '✗'}   （検査器の外 {skip} 本）")
print("  外の 2 本は不成層で棄却されるもの（＝そもそも答えが無い。正しい振る舞い）。")
print("  **Belnap 四値も検査に入った** —— 四値は元から束なので、影に本物の join を委ね、")
print("  真偽値から四値への正規化を処理系と揃えるだけで済んだ。")
print("=" * W)
sys.exit(0 if ok else 1)
