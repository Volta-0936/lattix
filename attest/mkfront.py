#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attest/front.lx を組む —— 源のバイトを読み、規則の表を八バイト小端の語の列にして描く。

中身は焼き手の前段そのもの（examples/33_self.lx から print を除いたもの + lib/fold.lx）に、
表を語の列にして描く尻尾（attest/enc.lx）を繋いだだけ。前段を二つ持たない —— 焼き手が
読んだとおりの表を attest が読む（前段の読み違いは attest の外。前段は「読めた語を数える」
ので、読めない語があれば表の頭に断り（行と理由）が載る）。

    python3 attest/mkfront.py [出す先（既定 attest/front.lx）]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
front = open(os.path.join(ROOT, 'examples', '33_self.lx'), encoding='utf-8').read()
front = "\n".join(l for l in front.splitlines() if not l.startswith('print '))
glue = open(os.path.join(ROOT, 'lib', 'fold.lx'), encoding='utf-8').read()
tail = open(os.path.join(HERE, 'enc.lx'), encoding='utf-8').read()
head = ("# attest-front —— 源のバイトを読み、規則の表を八バイト小端の語の列にして描く。\n"
        "#   中身: examples/33_self.lx（print を除く）+ lib/fold.lx + attest/enc.lx\n"
        "#   組み方: python3 attest/mkfront.py（手で直さない）\n\n")
out = head + front + "\n" + glue + "\n" + tail
dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'front.lx')
open(dst, 'w', encoding='utf-8').write(out)
