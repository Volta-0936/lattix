#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
実行時読込バックエンドが、解釈実行と同じ答えを出すか。

`runtime.py` は **プログラムだけ** を C にする。表は実行ファイルが読む。
だから一度コンパイルした実行ファイルが、別のデータで何度でも走る ——
**そこに Python は一度も現れない。**
"""
import io, os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L, native as N, runtime as R

W = 84
ok = True
print("=" * W)
print("  実行時読込 C  対  解釈実行")
print("=" * W)
print(f"  {'例題':<24} {'C 行数':>7} {'ラウンド':>8} {'一致':>6}")
print("-" * W)
for name in sorted(os.listdir(os.path.join(ROOT, 'examples'))):
    if not name.endswith('.lx'): continue
    src = open(os.path.join(ROOT, 'examples', name), encoding='utf-8').read()
    try:
        info = R.build(src)
    except Exception as ex:
        print(f"  {name:<24} {'—':>7} {'—':>8}   未対応: {str(ex)[:34]}")
        continue
    d = R.write_data(info['prog'], os.path.join(info['dir'], 'data.lxd'))
    got, meta = R.run(info['exe'], d)
    p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    ref, _, _ = L.run(p, out=io.StringIO())
    same = True
    # **`print` と書いた場だけを比べていた。** 生成器（31_gen）は `render` しか
    # 持たないので、比べるものが一つも無く、C の答えは一度も検査されていなかった
    # —— 通っていたのではなく、何も見ていなかった。全部の場を比べる。
    for f in p.fields:
        # `0 in (None, False)` は Python では真。ここで一度騙された ——
        # **食い違いを見たら、まず自分の測り方を疑う。**
        lat = p.fields[f]
        a = {}
        for k, v in ref[f].items():
            o = lat.observe(v)
            if o is None or (lat.name in ('or', 'and') and not o): continue
            a[k] = o
        b = {k: (bool(v) if p.fields[f].name in ('or', 'and') else v)
             for k, v in got.get(f, {}).items()}
        a = {k: (bool(v) if p.fields[f].name in ('or', 'and') else v) for k, v in a.items()}
        if a != b: same = False
    ok &= same
    print(f"  {name:<24} {info['lines']:>7} {int(meta.get('ROUNDS',0)):>8} "
          f"{'✓' if same else '✗':>6}")
print("-" * W)
print("  未対応は Unsupported を投げて落ちる。**黙って間違えない**（不変条件8）。")
print("=" * W)
sys.exit(0 if ok else 1)
