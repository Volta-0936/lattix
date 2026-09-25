#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**口を打つ** —— 焼いた実行ファイルの入口と出口を、撒く道具が作らない形で打つ。

撒く道具（accept / differ / meta / mutate / coords / values）は **源**を撒く。入力の
大きさ、読めない入力、閉じた出す先は撒かれない。ここで打つのは、黙ると嘘になる所だけ:

    置き場ちょうど → 答える / 一バイト多い → 6        （前は黙って切った）
    詰め直しの置き場より大きい render → 答える          （前は segfault）
    ディレクトリを読む → 8                              （前は空の入力として答えた）
    語の列が行の途中で切れる → 8 / 割り切れる → 答える  （前は 0 で埋めた一行）
    出す先が /dev/full → 9 / 開けない出す先 → 9          （前は 0）
    証人の fd 3 が閉じている → 0 / fd 3 が /dev/full → 9
    読み手が先に閉じた大きい答え → 0 以外                 （前は 0）

   使い方:  python3 test/mouths.py
"""
import os, struct, subprocess, sys, tempfile, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATTIX = os.environ.get('LATTIX_EXE', os.path.join(ROOT, 'lattix'))
W = 78
tmp = tempfile.mkdtemp()
import atexit; atexit.register(shutil.rmtree, tmp, True)


def bake(name, src):
    r = subprocess.run([LATTIX], input=src.encode(), capture_output=True)
    assert r.returncode == 0 and r.stdout[:4] == b'\x7fELF', (name, r.returncode)
    exe = os.path.join(tmp, name); open(exe, 'wb').write(r.stdout); os.chmod(exe, 0o755)
    return exe


CNT = bake('cnt', "table ch = (0,32)\nfield n : count bound 4\nn[0] <- 1   for (i,c) in ch\n")
ROWS = bake('rows', "table e = (0,0,0)\nfield n : count bound 4\nfield s : sum bound 4\n"
                    "n[0] <- 1   for (i,j,w) in e\ns[0] <- w   for (i,j,w) in e\n")
BIG = bake('big', "table ch = (0,32)\nfield x : max bound 262144\nx[i] <- i   for (i) in 0 .. 262143\n")
WIDE = bake('wide', "table ch = (0,32)\nfield o : max bound 2000000\no[i] <- 65   for (i) in 0 .. 1999999\nrender o\n")

CAP = 983040      # 生バイトの置き場（rcap）


def run(exe, inp=b'', args=(), stdout=None, fd3=None, shell=None):
    if shell:
        r = subprocess.run(['sh', '-c', shell], capture_output=True)
        return r.returncode, r.stdout
    kw = {}
    if fd3 is not None:
        kw['pass_fds'] = (3,)
    r = subprocess.run([exe, *args], input=inp, stdout=stdout or subprocess.PIPE,
                       stderr=subprocess.PIPE, **kw)
    return r.returncode, (r.stdout if stdout is None else b'')


def n0(out): return struct.unpack_from('<q', out, 0)[0] if len(out) >= 8 else None


cases = []
def case(name, got, want):
    cases.append((name, got, want, got == want))


rc, out = run(CNT, b'a' * CAP); case('置き場ちょうど（答える）', (rc, n0(out)), (0, CAP))
rc, out = run(CNT, b'a' * (CAP + 1)); case('一バイト多い（6）', rc, 6)
rc, out = run(CNT, b''); case('空の入力（答える）', (rc, n0(out)), (0, 0))
rc, out = run(WIDE); case('二百万升を描く（答える）', (rc, len(out), set(out)), (0, 2000000, {65}))
# 表を回さない本は標準入力を読まない（前は端末で起こすと入力を待って止まった）。開いたままの管で測る
rc, out = run(None, shell=f'sleep 2 | timeout 1 {WIDE} > /dev/null'); case('表を回さない本は入力を待たない（答える）', rc, 0)
rc, out = run(CNT, args=(tmp,)); case('ディレクトリを読む（8）', rc, 8)
rc, out = run(CNT, args=(os.path.join(tmp, 'nope'),)); case('無い源（8）', rc, 8)
row = struct.pack('<qqq', 1, 2, 5)
rc, out = run(ROWS, row * 3); case('語の列が割り切れる（答える）', (rc, n0(out)), (0, 3))
rc, out = run(ROWS, row * 3 + b'\x01' * 7); case('語の列が行の途中で切れる（8）', rc, 8)
with open('/dev/full', 'wb') as full:
    rc, _ = run(BIG, stdout=full); case('出す先が /dev/full（9）', rc, 9)
rc, _ = run(BIG, args=('/dev/null', '/proc/nope/x')); case('開けない出す先（9）', rc, 9)
rc, _ = run(CNT, b'ab', shell='exec 3>&-; exec %s < /dev/null > /dev/null' % CNT)
case('証人の fd 3 が閉じている（0）', rc, 0)
rc, _ = run(CNT, shell='exec 3>/dev/full; exec %s < /dev/null > /dev/null' % CNT)
case('証人の fd 3 が /dev/full（9）', rc, 9)
# **箱を越えた書きは、どの場かを名で言う**（14w。前は場の番号を四バイトで続けていた —— 人には読めない）
SMALL = bake('small', "table ch = (0,32)\nfield other : max bound 8\nfield small : max bound 4\n"
                      "other[i] <- i   for (i) in 0 .. 7\nsmall[i] <- other[i] * 2   for (i) in 0 .. 7\n")
r = subprocess.run([SMALL], input=b'a', capture_output=True)
case('箱を越えた書きは場を名で言う（6）', (r.returncode, r.stderr.split(b'\n')[1].split()), (6, [b'field', b'1', b'small']))
r = subprocess.run([CNT], input=b'a' * (CAP + 1), capture_output=True)
case('置き場を越えた入力は表と言う（6）', (r.returncode, r.stderr.split(b'\n')[1].strip()), (6, b'the input table'))
# **焼き手の箱を越えた本は、焼き手自身が箱の名を言う**（14w。場 2,048 本 —— 前段の宣言の綴りの箱）。前は写しの
# 見張り（capf）が「箱が足りない」と言い、写しが古いと箱に入る本まで断った
src2048 = "table ch = (0,32)\n" + "".join(f"field f{i} : max bound 2\n" for i in range(2048)) + "f0[i] <- i   for (i) in 0 .. 1\n"
r = subprocess.run([LATTIX], input=src2048.encode(), capture_output=True)
nm = r.stderr.split(b'\n')[1].split() if r.stderr.count(b'\n') >= 2 else []
case('焼き手の箱を越えた本は箱の名を言う（6）', (r.returncode, nm[:1], len(nm)), (6, [b'field'], 3))
p = subprocess.Popen([BIG], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
p.stdout.read(1); p.stdout.close(); rc = p.wait()
case('読み手が先に閉じた大きい答え（0 以外）', rc != 0, True)

print("=" * W); print("  **口を打つ** —— 入口と出口を、撒く道具が作らない形で"); print("=" * W)
for name, got, want, ok in cases:
    print(f"  {name:<34}{str(got):>18}   {'✓' if ok else '✗ 待った ' + str(want)}")
print("-" * W)
bad = [c for c in cases if not c[3]]
if bad:
    print(f"  **破れ {len(bad)}**"); sys.exit(1)
print(f"  **{len(cases)} / {len(cases)}** —— 口は黙らない。")
