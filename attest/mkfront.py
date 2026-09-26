#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attest/front.lx を組む —— 源のバイトを読み、規則の表を八バイト小端の語の列にして描く。

中身は焼き手の前段そのもの（examples/33_self.lx + lib/fold.lx）に、
表を語の列にして描く尻尾（attest/enc.lx）を繋いだだけ。前段を二つ持たない —— 焼き手が
読んだとおりの表を attest が読む（前段の読み違いは attest の外。前段は「読めた語を数える」
ので、読めない語があれば表の頭に断り（行と理由）が載る）。

    python3 attest/mkfront.py [出す先（既定 attest/front.lx）]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# **三行の include**（14z）。前は三つを繋いで書いていた —— 焼き手の口が取り込みを開くので、繋ぐのは焼き手の仕事である
# （lattix.lx・lower.lx と同じ）。取り込みは今の場所から探すので、リポジトリの根で焼く
out = ("# attest-front —— 源のバイトを読み、規則の表を八バイト小端の語の列にして描く。\n"
       "#   中身: examples/33_self.lx + lib/fold.lx + attest/enc.lx（焼き手の口が取り込みを開く。リポジトリの根で焼く）\n"
       "#   組み方: python3 attest/mkfront.py（手で直さない）\n"
       'include "examples/33_self.lx"\n'
       'include "lib/fold.lx"\n'
       'include "attest/enc.lx"\n')
dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'front.lx')
open(dst, 'w', encoding='utf-8').write(out)
