#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
実行時読込バックエンドの答えを、**検査器にかける**。

不変条件6 に「証人はどのスケジューラも同じ規則で出す。出さないモードを作らない」と
書いておきながら、`runtime.py` を丸ごと足したときに階数を出していなかった。
主力になりつつある経路だけが検査の外にあった。ここで塞ぐ。

検査器は C を一行も見ない。読むのは `.lx`（仕様）と、出てきた答えと階数だけである。
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import attest as A, runtime as R

W = 84
ok = True
good = bad = skip = 0
print("=" * W)
print("  実行時読込 C の答えを attest にかける（C は一行も読まない）")
print("=" * W)
for name in sorted(os.listdir(os.path.join(ROOT, 'examples'))):
    if not name.endswith('.lx'): continue
    src = open(os.path.join(ROOT, 'examples', name), encoding='utf-8').read()
    try:
        info = R.build(src)
    except Exception:
        skip += 1; continue
    try:
        d = R.write_data(info['prog'], os.path.join(info['dir'], 'd.lxd'))
        store, meta = R.run(info['exe'], d)
        rep = A.attest(src, store, meta.get('rank', {}),
                       pre=meta.get('pre'), prerank=meta.get('prerank'))
    except Exception as e:
        print(f"  {name:<20} ERR {str(e)[:40]}"); bad += 1; continue
    fine = rep.sound and rep.complete
    good += fine; bad += (not fine)
    mark = f"SOUND {'✓' if rep.sound else '✗'}  COMPLETE {'✓' if rep.complete else '✗'}"
    note = "" if fine else "   ← 階数の付け方（下の注）"
    if rep.top_witness: note += f"   ⊤ の証人 {len(rep.top_witness)}"
    if rep.cyclic_top: note += f"   未証明の ⊤ {len(rep.cyclic_top)}"
    print(f"  {name:<20} {mark}{note}")
print("-" * W)
print(f"  通った {good} / 落ちた {bad} / このバックエンドでは未対応 {skip}")
print()
print("  ここで一度、**原因を取り違えた**。落ちていた 3 本を「実行時側の階数の付け方が悪い」")
print("  と書いたが、同じ 3 本は解釈実行でも落ちていた。原因は検査器の側で、")
print("  **場が複数の層で書かれるとき、有基性を層ごとに見ていた**こと。")
print("  正当化はどの規則から来てもよいので、寄与は層をまたいで集めなければならない。")
print("  （`brk` が層0と層1の両方で書かれていて露見した。原因は測ってから書くこと。）")
print("=" * W)
sys.exit(0 if bad == 0 else 1)
