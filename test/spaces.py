#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**角括弧のまわりの空白** —— 空白を置いても置かなくても、同じ本である。

解釈実行（lattix.py）は語を読むときに空白を捨てる。焼き手の前段は空白も語として数え、
出現の `[` を「名前の一つ後ろ」、添字を「二つ後ろ」と **数で** 引いていた。だから
`f[ i ]`・`g[ 1 ] <- 5`・`q[0, 1] <- 3`・`n[ 0 ]` を理由 8、`f [i]` を理由 4（宣言の無い場 —— 嘘の
理由）で断っていた（2026-09-20）。いまは空白を跨いで引く（`prevw` / `nextw`）。

ここでは同じ本を **空白の置き方だけ変えて** 何通りも焼き、どれも

    空白の無い書き方と同じバイトを出し、解釈実行と升まで一致する

ことを測る。焼けない形（`g[i * 2]` など）は、空白を置いても同じ理由で断ること。

    使い方:  python3 test/spaces.py
"""
import os, sys, io, struct, subprocess, tempfile, shutil, atexit
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
LATTIX = os.environ.get('LATTIX_EXE', os.path.join(ROOT, 'lattix'))
W = 78
tmp = tempfile.mkdtemp(); atexit.register(shutil.rmtree, tmp, True)
DATA = b'ab1 cd23'

HEAD = """table ch = (0,32)
field g : max bound 4
field h : max bound 4
field n : max bound 2
field f : max bound 8
"""
Q = "field q : max bound 2 3\n"          # 二次元の場は、二次元で使う本にだけ置く（使われ方が次数を決める）

# (名前, [書き方…]) —— 最初の書き方が空白の無いもの。後ろはどれも同じ本の、空白の置き方の違い
CASES = [
    ("一次元の種", ["g[1] <- 5\nf[i] <- g[i]   for (i) in 0 .. 3\n",
                   "g[ 1 ] <- 5\nf[i] <- g[i]   for (i) in 0 .. 3\n",
                   "g [1] <- 5\nf[i] <- g[i]   for (i) in 0 .. 3\n",
                   "g [ 1 ] <- 5\nf[i] <- g[i]   for (i) in 0 .. 3\n"]),
    ("二次元の種", ["q[0,1] <- 3\nq[1,2] <- 4\nf[i] <- q[1, i]   for (i) in 0 .. 2\n",
                   "q[0, 1] <- 3\nq[1, 2] <- 4\nf[i] <- q[1, i]   for (i) in 0 .. 2\n",
                   "q[0 ,1] <- 3\nq[1 ,2] <- 4\nf[i] <- q[1, i]   for (i) in 0 .. 2\n",
                   "q[ 0 , 1 ] <- 3\nq [ 1 , 2 ] <- 4\nf[i] <- q[1, i]   for (i) in 0 .. 2\n"]),
    ("書き先", ["f[i] <- i + 1   for (i) in 0 .. 3\n",
                "f[ i ] <- i + 1   for (i) in 0 .. 3\n",
                "f [i] <- i + 1   for (i) in 0 .. 3\n",
                "f [ i ] <- i + 1   for (i) in 0 .. 3\n"]),
    ("二次元の書き先", ["q[i,j] <- i * 10 + j   for (i) in 0 .. 1 for (j) in 0 .. 2\n",
                      "q[ i , j ] <- i * 10 + j   for (i) in 0 .. 1 for (j) in 0 .. 2\n",
                      "q [i, j] <- i * 10 + j   for (i) in 0 .. 1 for (j) in 0 .. 2\n"]),
    ("値の読み", ["g[2] <- 7\nf[i] <- g[i] + 1   for (i) in 0 .. 3\n",
                  "g[2] <- 7\nf[i] <- g[ i ] + 1   for (i) in 0 .. 3\n",
                  "g[2] <- 7\nf[i] <- g [i] + 1   for (i) in 0 .. 3\n",
                  "g[2] <- 7\nf[i] <- g [ i ] + 1   for (i) in 0 .. 3\n"]),
    ("ずれ", ["g[2] <- 7\nf[i] <- g[i+1]   for (i) in 0 .. 2\n",
              "g[2] <- 7\nf[i] <- g[ i+1 ]   for (i) in 0 .. 2\n",
              "g[2] <- 7\nf[i] <- g[ i + 1 ]   for (i) in 0 .. 2\n",
              "g[2] <- 7\nf[i] <- g [i + 1]   for (i) in 0 .. 2\n"]),
    ("書き先のずれ", ["g[2] <- 7\nf[i+1] <- g[i]   for (i) in 0 .. 3\n",
                     "g[2] <- 7\nf[ i + 1 ] <- g[i]   for (i) in 0 .. 3\n",
                     "g[2] <- 7\nf [i+1] <- g[i]   for (i) in 0 .. 3\n"]),
    ("入れ子の読み", ["g[1] <- 2\nh[2] <- 9\nf[i] <- h[g[i]]   for (i) in 0 .. 3\n",
                     "g[1] <- 2\nh[2] <- 9\nf[i] <- h[ g[ i ] ]   for (i) in 0 .. 3\n",
                     "g[1] <- 2\nh[2] <- 9\nf[i] <- h [g [i]]   for (i) in 0 .. 3\n"]),
    ("入れ子の前置のずれ", ["g[1] <- 2\nh[2] <- 9\nf[i] <- h[g[i+1]]   for (i) in 0 .. 2\n",
                         "g[1] <- 2\nh[2] <- 9\nf[i] <- h[ g[ i + 1 ] ]   for (i) in 0 .. 2\n"]),
    ("ガードの読み", ["g[1] <- 1\nf[i] <- 3   for (i) in 0 .. 3 if g[i]\n",
                     "g[1] <- 1\nf[i] <- 3   for (i) in 0 .. 3 if g[ i ]\n",
                     "g[1] <- 1\nf[i] <- 3   for (i) in 0 .. 3 if g [i]\n"]),
    ("否定のガード", ["g[1] <- 1\nf[i] <- 3   for (i) in 0 .. 3 if not g[i]\n",
                     "g[1] <- 1\nf[i] <- 3   for (i) in 0 .. 3 if not g[ i ]\n",
                     "g[1] <- 1\nf[i] <- 3   for (i) in 0 .. 3 if not g [i]\n"]),
    ("比べるガード", ["g[1] <- 5\ng[2] <- 1\nh[i] <- 3   for (i) in 0 .. 3\nf[i] <- 1   for (i) in 0 .. 3 if g[i] >= h[i]\n",
                     "g[1] <- 5\ng[2] <- 1\nh[i] <- 3   for (i) in 0 .. 3\nf[i] <- 1   for (i) in 0 .. 3 if g[ i ] >= h[ i ]\n",
                     "g[1] <- 5\ng[2] <- 1\nh[i] <- 3   for (i) in 0 .. 3\nf[i] <- 1   for (i) in 0 .. 3 if g [i] >= h [i]\n"]),
    ("定数と比べる", ["g[1] <- 5\nf[i] <- 1   for (i) in 0 .. 3 if g[i] > 2\n",
                     "g[1] <- 5\nf[i] <- 1   for (i) in 0 .. 3 if g[ i ] > 2\n",
                     "g[1] <- 5\nf[i] <- 1   for (i) in 0 .. 3 if 2 < g [ i ]\n"]),
    ("区間の上端", ["n[0] <- 2\nf[i] <- 7   for (i) in 0 .. n[0]\n",
                   "n[0] <- 2\nf[i] <- 7   for (i) in 0 .. n[ 0 ]\n",
                   "n[0] <- 2\nf[i] <- 7   for (i) in 0 .. n [0]\n",
                   "n[ 0 ] <- 2\nf[i] <- 7   for (i) in 0 .. n [ 0 ]\n"]),
    ("表の行", ["f[i] <- c   for (i,c) in ch\n",
                "f[ i ] <- c   for ( i , c ) in ch\n",
                "f [i] <- c   for (i,c) in ch\n"]),
    ("二次元の読み", ["q[1,2] <- 8\nf[i] <- q[1,i] + 1   for (i) in 0 .. 2\n",
                     "q[1,2] <- 8\nf[i] <- q[ 1 , i ] + 1   for (i) in 0 .. 2\n",
                     "q[1,2] <- 8\nf[i] <- q [1, i] + 1   for (i) in 0 .. 2\n"]),
]
# 焼けない形は、空白を置いても同じ理由で断る（理由 8 —— 座標の中の式）
REFUSE = [
    ("座標の中の掛け算", ["f[i] <- g[i*2]   for (i) in 0 .. 3\n",
                         "f[i] <- g[ i * 2 ]   for (i) in 0 .. 3\n"]),
    ("数の前のずれ", ["f[i] <- g[1+i]   for (i) in 0 .. 3\n",
                     "f[i] <- g[ 1 + i ]   for (i) in 0 .. 3\n"]),
]


def bake(src):
    p = os.path.join(tmp, 's.lx'); open(p, 'w', encoding='utf-8').write(src)
    exe = os.path.join(tmp, 'p')
    if os.path.exists(exe): os.remove(exe)
    subprocess.run([LATTIX, p, exe], capture_output=True)
    os.chmod(exe, 0o755)
    r = subprocess.run(['sh', '-c', 'exec 3>/dev/null; exec "$1"', 'sh', exe], input=DATA, capture_output=True)
    if r.returncode: return ('rc', r.returncode, r.stderr.split(b'\n')[0].decode(errors='replace'))
    return ('ok', r.stdout)


def interp(src):
    p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    p.tables['ch'] = [(i, c) for i, c in enumerate(DATA)]
    st, _, _ = L.run(p, out=io.StringIO())
    return p, st


def cells(p, st, out):
    """焼いた答え（場の面）と解釈実行の升を突き合わせる"""
    off = 0; bad = []
    for name, lat in p.fields.items():
        dims = {'g': [4], 'h': [4], 'n': [2], 'f': [8], 'q': [2, 3]}[name]
        n = dims[0] * (dims[1] if len(dims) == 2 else 1)
        for c in range(n):
            v = struct.unpack_from('<q', out, off + 8 * c)[0]
            key = (c,) if len(dims) == 1 else (c // dims[1], c % dims[1])
            ref = st.get(name, {}).get(key)
            if ref is None: ref = -2147483647
            if v != ref: bad.append((name, key, v, ref))
        off += 8 * n
    return bad


print("=" * W)
print("  **角括弧のまわりの空白** —— 置き方だけ違う同じ本を焼き、同じバイトと解釈実行の答えを見る")
print("=" * W)
ok = True; nsrc = 0
for label, forms in CASES:
    base = None; line = []
    for k, body in enumerate(forms):
        src = HEAD + (Q if ('q[' in body or 'q [' in body) else '') + body
        got = bake(src); nsrc += 1
        if got[0] != 'ok':
            line.append('✗ 断った %s' % (got[2][:40],)); ok = False; continue
        p, st = interp(src)
        bad = cells(p, st, got[1])
        if bad:
            line.append('✗ 解釈実行と違う %s' % (bad[:2],)); ok = False; continue
        if base is None: base = got[1]
        elif got[1] != base:
            line.append('✗ 空白の無い書き方と違うバイト'); ok = False; continue
        line.append('✓')
    print(f"  {label:<18}{' '.join(line)}")
for label, forms in REFUSE:
    why = set()
    for body in forms:
        got = bake(HEAD + body); nsrc += 1
        why.add(got[2] if got[0] == 'rc' else 'answered')
    same = len(why) == 1 and 'reason 8' in next(iter(why))
    ok = ok and same
    print(f"  {label:<18}{'同じ理由で断る ✓' if same else '✗ ' + str(why)}")
print("-" * W)
print(f"  焼いた本 {nsrc} 本")
print("  **空白は答えを変えない** —— どの置き方も同じバイト、解釈実行と升まで一致。" if ok else "  **破れ**")
print("=" * W)
sys.exit(0 if ok else 1)
