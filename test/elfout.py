#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**C を使わずに実行形式を書く。**

`render` は場を座標順のバイト列として書き出す。つまり Lattix は
ファイルの中身を計算できる。中身が実行形式なら、Lattix は実行形式を書ける。

ここで確かめるのは二つ:
  1. 出てきた 132 バイトが本物の ELF で、**走る**
  2. 終了コードが **計算された答え**である（最短経路長 13）

gcc は一度も呼ばれていない。到達点 —— Python も C も無い Lattix 単体 ——
への一歩目は、「実行形式は答えの実体化である」と言えることである。
"""
import os, subprocess, sys, stat, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = 84

src = os.path.join(ROOT, 'examples', '27_elf.lx')
out = os.path.join(tempfile.mkdtemp(), 'a.out')
with open(out, 'wb') as fp:
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'lattix.py'), src],
                       stdout=fp, stderr=subprocess.PIPE)
blob = open(out, 'rb').read()
os.chmod(out, os.stat(out).st_mode | stat.S_IEXEC)

ok = blob[:4] == b'\x7fELF'
code = subprocess.run([out]).returncode if ok else -1

print("=" * W)
print("  Lattix が実行形式を書く —— C を一度も通さずに")
print("=" * W)
print(f"  出力 {len(blob)} バイト   先頭 {blob[:4]!r}   ELF: {'✓' if ok else '✗'}")
print(f"  走らせた終了コード: {code}   （最短経路 dist[5] = 13 が入っているはず）")
print("-" * W)
good = ok and code == 13 and len(blob) == 132
print("  一致" if good else "  不一致")
print("  `render` は場を **座標順のバイト列** として書き出す。列は座標に住んでいて、")
print("  時間には住んでいない —— だから出力は効果ではなく *描画* であり、")
print("  描かれたものが実行形式なら、それは **答えの実体化** である。")
print("=" * W)
sys.exit(0 if good else 1)
