#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**証人の階数が溢れたとき、黙らないか** —— 焼いた本の階数は符号なしの 32 ビットである。

階数を 2^32 近くまで積むには四十億段の導出が要る。待たずに測る: 焼いた本の **種の階数**
（`mov dword [r10+d32], 1`）を 0xFFFFFFF8 に書き換え、十升の鎖（f[i+1] <- f[i] + 1）を走らせる。

    期待: 0xFFFFFFF8, …, 0xFFFFFFFF, 0, 1 —— 0xFFFFFFFF までは順序どおり、その次は 0 に戻る
          （在る升の階数 0 は「導出を与えていない」）。値は変わらない。
          attest は REJECTED（示せない）と言い、階数 0 の升があると注を添える。

前は符号つきで溜めていた（cmovl と 64 ビットの add）。2^31 を越えた階数を読む側が負と見て、
**小さい階数（1）を黙って書いた** —— 順序が壊れているのに、升の階数は尤もらしく見えた。

    使い方:  python3 test/rankwrap.py
"""
import os, sys, struct, subprocess, tempfile, shutil, atexit
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATTIX = os.environ.get('LATTIX_EXE', os.path.join(ROOT, 'lattix'))
W = 78
tmp = tempfile.mkdtemp(); atexit.register(shutil.rmtree, tmp, True)
SRC = """table ch = (0,32)
field f : max bound 10
f[0] <- 1
f[i+1] <- f[i] + 1   for (i) in 0 .. 8
"""


def bake(src_path, out):
    subprocess.run([LATTIX, src_path, out], check=True, capture_output=True)
    os.chmod(out, 0o755)


print("=" * W)
print("  **証人の階数が溢れたとき、黙らないか** —— 種の階数を 2^32 の手前に書き換えて走らせる")
print("=" * W)
sp = os.path.join(tmp, 'chain.lx'); open(sp, 'w').write(SRC)
exe = os.path.join(tmp, 'chain'); bake(sp, exe)
b = bytearray(open(exe, 'rb').read())
hits = [i for i in range(len(b) - 11)
        if b[i:i + 3] == b'\x41\xc7\x82' and b[i + 7:i + 11] == b'\x01\x00\x00\x00']
ok = len(hits) == 1
print(f"  {'種の階数を書く命令（mov dword [r10+d32], 1）が一つ':<52}{'✓' if ok else '✗ ' + str(len(hits))}")
if not ok: sys.exit(1)
struct.pack_into('<I', b, hits[0] + 7, 0xFFFFFFF8)
open(exe, 'wb').write(bytes(b))
wit = os.path.join(tmp, 'w.bin')
r = subprocess.run(['sh', '-c', 'exec 3>"$1"; shift; exec "$@"', 'sh', wit, exe], input=b'', capture_output=True)
w = open(wit, 'rb').read()
vals = struct.unpack('<10q', w[:80]); ranks = struct.unpack('<10I', w[80:120])
want_v = tuple(range(1, 11))
want_k = tuple([0xFFFFFFF8 + i for i in range(8)] + [0, 1])
ok_v = r.returncode == 0 and vals == want_v
ok_k = ranks == want_k
print(f"  {'値は変わらない（1 … 10）':<52}{'✓' if ok_v else '✗ ' + str(vals)}")
print(f"  {'階数は 0xFFFFFFFF まで順に、その次は 0':<52}{'✓' if ok_k else '✗ ' + str([hex(x) for x in ranks])}")

# attest（.lx）にかける: REJECTED（示せない）と、階数 0 の注
front, ev = os.path.join(tmp, 'front'), os.path.join(tmp, 'attest')
bake(os.path.join(ROOT, 'attest', 'front.lx'), front)
bake(os.path.join(ROOT, 'attest', 'attest.lx'), ev)
tab = os.path.join(tmp, 'tab')
subprocess.run([front, sp, tab], check=True, capture_output=True)
inp = os.path.join(tmp, 'in')
open(inp, 'wb').write(open(tab, 'rb').read() + w + r.stdout)
a = subprocess.run([ev, inp], capture_output=True)
out = a.stdout.decode(errors='replace')
ok_a = (a.returncode == 0 and out.startswith('attest: REJECTED -- not proven')
        and 'cell          8' in out and 'a present cell with rank 0' in out)
print(f"  {'attest: REJECTED（示せない）、升 8、階数 0 の注':<52}{'✓' if ok_a else '✗'}")
if not ok_a: print(out)
ok = ok_v and ok_k and ok_a
print("-" * W)
print("  **黙らない** —— 0xFFFFFFFF までは順序を保ち、越えたら階数 0（導出を与えていない）を書く。"
      if ok else "  **破れ**")
print("=" * W)
sys.exit(0 if ok else 1)
