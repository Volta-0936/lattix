# expand.s を組んで、31_gen.lx に置く種（四バイトずつ）を起こす —— 作るときの道具。焼き手を組むのに Python は要らない
# （種は 31_gen.lx の源に書いてある。展開器を直したらこれで起こし直して貼る）
import subprocess, struct
subprocess.run(['as', '-o', 'expand.o', 'expand.s'], check=True)
subprocess.run(['objcopy', '-O', 'binary', '-j', '.text', 'expand.o', 'expand.bin'], check=True)
b = open('expand.bin', 'rb').read()
stub = bytes([0x48, 0x89, 0x73, 0xf0, 0xe9, 0, 0, 0, 0, 0xe9, 0, 0, 0, 0])
assert b.endswith(stub); blob = b[:-len(stub)]
assert len(blob) % 4 == 0
ph = {b'\x11\x11\x11\x11': 'RBUF', b'\x22\x22\x22\x22': 'CAP'}
out, patch = [], {}
for k in range(len(blob) // 4):
    w = blob[4*k:4*k+4]
    if w in ph:
        patch[ph[w]] = k; v = 0
    else:
        v = struct.unpack('<i', w)[0]
    out.append(f"xv[{k}] <- {v}")
n = len(blob) // 4
print(f"# {n} 升（{len(blob)} バイト）。RBUF は升 {patch['RBUF']}、CAP は升 {patch['CAP']}")
print("\n".join(out))
open('rows.txt', 'w').write(f"N {n} RBUF {patch['RBUF']} CAP {patch['CAP']}\n" + "\n".join(out) + "\n")
