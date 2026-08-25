#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**一枚に畳む。** —— 源のバイトを入れると実行ファイルが出る、ただ一つの .lx。

これまで三段あった:

    21_lex / 22_parse / 32_shape   源のバイト → 規則の形
    31_gen                          規則の形   → 静的 ELF

間を運んでいたのはホスト（Python）で、表を作って次の段へ渡していた。
`33_self.lx` が一段目と二段目を一つにしたので、残っていたのは
**形を生成器の入力の形に写すこと**だけだった —— それが `lib/fold.lx` である。

    lattix.lx = 33_self.lx（形の導出）+ lib/fold.lx（写し）+ 31_gen.lx（生成）

畳んだものが出す実行ファイルは、三段が出したものと **同じ答えを解く**
のでなければならない（升まで一致）。バイトまで同じになるかは別の話で、
**規則の並び順**が違えば番地が動く —— 断片の成層は比較を一律に非単調と
見る（安全側）ので、22_parse の精密な極性解析より層が増えることがある。
バイトの一致も測って出すが、通す条件は **答えの一致**である。
"""
import os, re, stat, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import runtime as RT

W = 78
EX = os.path.join(ROOT, 'examples')
MARK = 'ここから下は表を一つも読まない'


def assemble():
    """三つの断片を一枚にする。**切れ目は源が言う**（畳み目の一行）。"""
    front = open(os.path.join(EX, '33_self.lx'), encoding='utf-8').read()
    # `print` は標準出力を汚す —— 畳んだものが書くのは **ELF だけ** である
    front = "\n".join(l for l in front.splitlines()
                      if not l.startswith('print '))
    glue = open(os.path.join(ROOT, 'lib', 'fold.lx'), encoding='utf-8').read()
    back = open(os.path.join(EX, '31_gen.lx'), encoding='utf-8').read()
    i = back.index(MARK)
    back = back[back.rindex('\n', 0, i) + 1:]
    head = """# **Lattix 一枚。** —— 源のバイトを入れると、静的 ELF が出る。
#
#   標準入力 : `.lx` の生バイト（`table ch` が (位置, 文字) に開く）
#   標準出力 : 静的 ELF（`render out`）
#
# 中身は三つの断片をそのまま繋いだものである ——
#
#   examples/33_self.lx  バイト → 語 → 文 → **規則の形**（構成子は使わない）
#   lib/fold.lx          形を生成器の入力の形に写す（判断は持たない）
#   examples/31_gen.lx   形 → 機械語（番地も飛び先も前置きの鎖が付ける）
#
# 繋ぎ目は `test/fold.py` が張る。**間に Python は一度も現れない。**
# この一枚が自分自身を焼いてバイト一致したとき、C も Python も要らなくなる。

"""
    return head + front + "\n" + glue + "\n" + back


SRC = assemble()
OUT = os.path.join(ROOT, 'lattix.lx')
open(OUT, 'w', encoding='utf-8').write(SRC)

# **名前がぶつかっていないか。** 三つの断片は別々に書かれたので、
# 同じ綴りが別のものを指していたら、黙って混ざる（過去に一度やった）。
names = re.findall(r'(?m)^field (\w+)', SRC)
dup = sorted({n for n in names if names.count(n) > 1})
assert not dup, f"場の名前がぶつかっている: {dup}"

sg = open(os.path.join(ROOT, 'test', 'selfgen.py'), encoding='utf-8').read()
ns = {'__name__': 'notmain', '__file__': os.path.join(ROOT, 'test', 'selfgen.py')}
exec(compile(sg[:sg.index("tmp = tempfile.mkdtemp()")], 'selfgen', 'exec'), ns)

A = """table ch = (0,32)
field big : or bound 256
big[i] <- true for (i,c) in ch if c >= 97
"""
B = """table ch = (0,32)
field cls : max bound 256
cls[i] <- 1 for (i,c) in ch if c >= 97
cls[i] <- 2 for (i,c) in ch if c == 32
field brk : or bound 256
brk[i] <- true for (i,c) in ch if i >= 1 if cls[i] != cls[i-1]
"""
C = """table ch = (0,32)
field num : max bound 256
num[i] <- c - 48 for (i,c) in ch if c >= 48 if c <= 57
field run : max bound 256
run[i] <- num[i] for (i,c) in ch if i >= 1 if num[i] >= 0
run[i] <- run[i-1] * 10 + num[i] for (i,c) in ch if i >= 1 if num[i] >= 0
"""
CASES = [("ガード一つ", A), ("鎖と比較", B), ("桁を積む", C)]

tmp = tempfile.mkdtemp()
print("=" * W)
print("  **一枚に畳む** —— lattix.lx が源のバイトから実行ファイルを書く")
print("=" * W)
print(f"  {'入力':<16}{'源':>5}{'場':>4}{'規則':>4}{'セル':>6}"
      f"   答え一致   バイト")
print("-" * W)

info = RT.build(SRC, only_prints=True)
ok = True
for i, (name, src) in enumerate(CASES):
    data = b"lattix 12 34\n"
    # 三段（ホストが表を運ぶ）
    flds, rules, _n, three_st, _rk = ns['compile_lx'](src, tmp, 600 + i,
                                                      inp=1, data=data)
    three = open(os.path.join(tmp, f"a{600 + i}.out"), 'rb').read()
    # 一枚（間に Python が一度も現れない）
    info['prog'].tables['ch'] = [(k, c) for k, c in enumerate(src.encode())]
    d = RT.write_data(info['prog'], os.path.join(info['dir'], 'data.lxd'),
                      atom=info['atom'])
    r = subprocess.run([info['exe'], d], capture_output=True)
    one = r.stdout
    if r.returncode or one[:4] != b'\x7fELF':
        print(f"  {name:<16}{len(src):>5}   焼けなかった（終了コード "
              f"{r.returncode}）")
        print("      " + r.stderr.decode('utf-8', 'replace')[:300])
        ok = False; continue
    exe1 = os.path.join(tmp, f"one{i}.out")
    open(exe1, 'wb').write(one)
    os.chmod(exe1, os.stat(exe1).st_mode | stat.S_IEXEC)
    _f, _r, _n2, one_st, _rk2 = ns['_readback'](flds, rules, one, exe1, data, {})
    same = one_st == three_st
    ok &= same
    print(f"  {name:<16}{len(src):>5}{len(flds):>4}{len(rules):>4}"
          f"{sum(len(x) for x in one_st.values()):>6}"
          f"   {'✓' if same else '✗'}      {'同じ' if one == three else '違う'}")
    if not same:
        for f in sorted(set(one_st) | set(three_st)):
            if one_st.get(f) != three_st.get(f):
                print(f"      場 {f}: 一枚 {one_st.get(f)} / 三段 {three_st.get(f)}")
print("-" * W)
print("  一致" if ok else "  不一致")
print("  **写しは判断を持たない。** 三段でやっても一枚でやっても、焼けた")
print("  実行ファイルは同じ答えを解く —— 間に Python は一度も現れない。")
print("=" * W)
sys.exit(0 if ok else 1)
