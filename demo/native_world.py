#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外界を、ネイティブで。**往復は実行ファイルを呼び直すことである。**

  ./prog data.lxd                 → EMIT lookup 1 / 2 / 3
  （ホストが答える）
  ./prog data.lxd answers.lxd     → 答えを食べて続きを解く

逐次深度（外界との往復回数）は「何回呼び直すか」そのものになる。
効果は場の成長の *差分* なので、再実行しても順序を変えても重複しない ——
exactly-once はプロトコルではなく構造から出る。
"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L, runtime as R

W = 84
SRC = ("table ks = (1), (2), (3)\n"
       'emit "lookup" <- k          for (k) in ks\n'
       "source info : min from \"lookup\"\n"
       "field out : min\n"
       "out[k] <- info[k] + 1       for (k) in ks\n"
       "print out\n")

def host(ch, values):
    """外界の答え。ここでは 10 倍して返す。"""
    return {ch: {v: v * 10 for v in values}}

print("=" * W)
print("  外界との往復を、実行ファイルの呼び直しで")
print("=" * W)
info = R.build(SRC)
d = info['dir']
data = R.write_data(info['prog'], os.path.join(d, "base.lxd"))

store, meta = R.run(info['exe'], data)
emitted = meta.get('emit', [])
print(f"  1回目: EMIT {emitted}")

ans = host('lookup', [v for _ch, v in emitted])['lookup']
apath = os.path.join(d, "answer.lxd")
with open(apath, "w") as f:
    f.write(f"field info {len(ans)} 2\n")
    for k, v in sorted(ans.items()):
        f.write(f"{k} {v}\n")
store2, meta2 = R.run(info['exe'], data, apath)
print(f"  2回目: out = {dict(sorted(store2.get('out', {}).items()))}")

# 解釈実行（ホストつき）と突き合わせる
p = L.parse(SRC); L.check(p); L.stratify(p); rounds = L.io_rounds(p); L.certify(p)
def h(ch, new):
    return {'info': {(v,): v * 10 for v in new}}
ref, _c, st = L.run(p, out=io.StringIO(), host=h)
A = {k: p.fields['out'].observe(v) for k, v in ref['out'].items()}
B = store2.get('out', {})
same = A == B
print(f"  解釈実行（ホストつき）: {dict(sorted(A.items()))}")
print("-" * W)
print(f"  一致: {'✓' if same else '✗'}   処理系が宣言した往復回数: {rounds}")
print("  効果は集合の成長の差分。**同じ答えを二度出さないための仕掛けは書いていない。**")
print("=" * W)
sys.exit(0 if same else 1)
