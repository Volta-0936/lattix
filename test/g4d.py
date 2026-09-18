#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**自分を焼いて、バイトまで同じ。** —— これだけが終わりの条件（G4d）。

    E0 = C で焼いた起動用（lattix.lx を C 経由で実行できる形にしたもの）
    L1 = E0(lattix.lx)      ← これが配る `lattix`（静的 ELF、依存なし）
    L2 = L1(lattix.lx)      ← `lattix` が自分自身を焼いた

`L1 == L2` なら、**C も Python も要らない**。ここから先、`lattix` は
自分で自分を作り続けられる —— 起動用はもう二度と要らない（気づき: 自立とは
「同じものを作れること」であって「速いこと」ではない）。

念のため、焼けた `lattix` が **小さい .lx を実行ファイルに焼けること**も
見る（自分を焼けても他人を焼けないのでは、道具ではない）。
"""
import hashlib, os, stat, subprocess, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import runtime as RT

W = 78
SRC = open(os.path.join(ROOT, 'lattix.lx'), encoding='utf-8').read()
RAW = open(os.path.join(ROOT, 'lattix.lx'), 'rb').read()
A = """table ch = (0,32)
field big : or bound 256
big[i] <- true for (i,c) in ch if c >= 97
"""

print("=" * W)
print("  **自分を焼いてバイト一致**（G4d）—— 起動用はここで役目を終える")
print("=" * W)
t = time.time()
E0 = RT.build(SRC, only_prints=True)
print(f"  {'起動用を C で焼く':<28}{time.time()-t:>6.1f} 秒", flush=True)

E0['prog'].tables['ch'] = [(i, c) for i, c in enumerate(RAW)]
d = RT.write_data(E0['prog'], os.path.join(E0['dir'], 'data.lxd'), atom=E0['atom'])
t = time.time()
r = subprocess.run([E0['exe'], d], capture_output=True)
ok = r.returncode == 0 and r.stdout[:4] == b'\x7fELF'
print(f"  {'L1 = 起動用(lattix.lx)':<28}{time.time()-t:>6.1f} 秒  {len(r.stdout)} バイト", flush=True)
if not ok:
    print("  焼けなかった:", r.stderr.decode('utf-8', 'replace')[:300]); sys.exit(1)
tmp = tempfile.mkdtemp()
L1 = os.path.join(tmp, 'lattix')
open(L1, 'wb').write(r.stdout); os.chmod(L1, os.stat(L1).st_mode | stat.S_IEXEC)

t = time.time()
r2 = subprocess.run([L1], input=RAW, capture_output=True)
print(f"  {'L2 = L1(lattix.lx)':<28}{time.time()-t:>6.1f} 秒  {len(r2.stdout)} バイト", flush=True)
h1 = hashlib.sha256(r.stdout).hexdigest()
h2 = hashlib.sha256(r2.stdout).hexdigest()
print(f"  L1 {h1[:40]}")
print(f"  L2 {h2[:40]}")
same = h1 == h2

# **他人も焼ける**か（道具として使えるか）
r3 = subprocess.run([L1], input=A.encode(), capture_output=True)
exe = os.path.join(tmp, 'a.out')
open(exe, 'wb').write(r3.stdout); os.chmod(exe, os.stat(exe).st_mode | stat.S_IEXEC)
r4 = subprocess.run([exe], input=b'lattix 12 34\n', capture_output=True)
# **升の幅は束が言う**（31_gen の `fwb`）—— `A` の `big` は `or` なので
# 一升 1 バイト。8 バイトで読むと隣の升まで一つの数として読んでしまう。
cells = list(r4.stdout[:6]) if len(r4.stdout) >= 6 else []
works = r3.stdout[:4] == b'\x7fELF' and cells == [1] * 6
print(f"  {'小さい .lx も焼ける':<28}{'✓' if works else '✗'}  "
      f"（{len(r3.stdout)} バイトの実行ファイル、答え {cells[:6]}）")
# **通ったら置く。** `lattix` は `lattix.lx` の像であって、手で作るものではない。
if same and works:
    dst = os.path.join(ROOT, 'lattix')
    # 走っている実行ファイルは上書きできない（Text file busy）—— 置き換える
    tmpdst = dst + '.new'
    open(tmpdst, 'wb').write(r.stdout)
    os.chmod(tmpdst, os.stat(tmpdst).st_mode | stat.S_IEXEC)
    os.replace(tmpdst, dst)
    print(f"  {'置いた':<28}{os.path.relpath(dst, ROOT)}")

print("-" * W)
print("  **バイト一致**" if same else f"  一致しない（違うバイトの数 "
      f"{sum(1 for x, y in zip(r.stdout, r2.stdout) if x != y)}）")
print("  焼けた lattix は、自分自身をもう一度焼いて **同じバイト列**を出す。")
print("  ここから先は起動用が要らない —— .lx を入れれば .lx だけで回る。")
print("=" * W)
sys.exit(0 if (same and works) else 1)
