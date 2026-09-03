#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**Lattix が x86-64 を組む。** —— C を切る道の二歩目。

27_elf は機械語が定数だった。ここでは違う:

  * 命令の並びは **データが決める**（数が一つ増えれば `add` が一つ増える）
  * 各命令の番地は **命令番号に沿った鎖**（offset[i] = offset[i-1] + len[i-1]）
  * ELF の大きさは、出来上がった機械語の長さから計算される

だから同じ .lx にデータを差し替えると、**長さの違う実行ファイル**が出てくる。
それを走らせて、終了コードが総和になっていることを確かめる ——
足しているのは Lattix ではなく、**Lattix が書いた機械語**である。
"""
import os, re, subprocess, sys, stat, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = 84
SRC = open(os.path.join(ROOT, 'examples', '28_asm.lx'), encoding='utf-8').read()


def build(nums, tmp):
    rows = ", ".join(f"({i},{v})" for i, v in enumerate(nums))
    src = re.sub(r"^table nums = .*$", f"table nums = {rows}", SRC, count=1,
                 flags=re.M)
    lx = os.path.join(tmp, 'p.lx'); open(lx, 'w', encoding='utf-8').write(src)
    exe = os.path.join(tmp, 'a.out')
    with open(exe, 'wb') as fp:
        subprocess.run([sys.executable, os.path.join(ROOT, 'lattix.py'), lx],
                       stdout=fp, stderr=subprocess.PIPE)
    os.chmod(exe, os.stat(exe).st_mode | stat.S_IEXEC)
    blob = open(exe, 'rb').read()
    code = subprocess.run([exe]).returncode if blob[:4] == b'\x7fELF' else -1
    return len(blob), code


tmp = tempfile.mkdtemp()
cases = [([7, 13, 5, 100], 125), ([1, 2], 3), ([10, 20, 30, 40, 50, 6], 156)]
print("=" * W)
print("  Lattix が x86-64 を組む —— 命令列も番地もデータから決まる")
print("=" * W)
ok = True
for nums, want in cases:
    n, code = build(nums, tmp)
    good = (code == want)
    ok &= good
    print(f"  nums={str(nums):<28} 実行ファイル {n:>4} バイト   "
          f"終了コード {code:>3}  期待 {want:>3}  {'✓' if good else '✗'}")
print("-" * W)
print("  一致" if ok else "  不一致")
print("  番地割り当ては時間の中の手続きに見えるが、**命令番号という座標に沿った鎖**である。")
print("  だから逐次実行は要らない —— 座標順に一度なめれば決まる。")
print("  足しているのは Lattix ではない。**Lattix が書いた機械語**である。")
print("=" * W)
sys.exit(0 if ok else 1)
