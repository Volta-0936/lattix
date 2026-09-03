#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lattix で書いた字句解析器を、**ネイティブで**、実ファイルに当てる。

`demo/bootstrap.py` は Python がバイトを運んでいた。ここでは運ばない ——
実行ファイルが `bytes ch <path>` で自分でファイルを開く。

この検査は「大きな入力は測定器である」ことの記録でもある。
小さな例（9文字）では通っていたのに、実ファイル（207文字）で 117 トークン中
12 個が ⊤ に落ちた。原因は ⊥ 検査が **構成子の引数の中に降りていなかった**こと。
`cons(c, text[i+1])` の `text[i+1]` が ⊥ のまま名前になり、
あとから本物の名前が来て flat が衝突していた。
"""
import io, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L, runtime as R

W = 84
# **完全版の字句解析器**（コメントと文字列を自分で飛ばす）を、生のソースに当てる。
# ホストは前処理を一切しない。バイト列をそのまま渡すだけ。
body = "\n".join(ln for ln in open(os.path.join(ROOT, 'examples', '20_lex_full.lx'),
                                   encoding='utf-8').read().splitlines()
                 if not ln.startswith('table ch'))
rawb = open(os.path.join(ROOT, 'examples', '01_shortest.lx'), 'rb').read()
text = rawb.decode('utf-8')

info = R.build("table ch = (0,32)\n" + body)
src_path = os.path.join(info['dir'], "input.lx")
open(src_path, "wb").write(rawb)
data = os.path.join(info['dir'], "lex.lxd")
open(data, "w").write(f"bytes ch {src_path}\n")
got, meta = R.run(info['exe'], data)

codes = list(rawb) + [32]     # **バイト列**。ネイティブが読むものと同じにする
tbl = "table ch = " + ", ".join(f"({i},{c})" for i, c in enumerate(codes))
p = L.parse(tbl + "\n" + body); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
ref, _, _ = L.run(p, out=io.StringIO())
A = {k: p.fields['token'].observe(v) for k, v in ref['token'].items()}
B = got.get('token', {})
TOP = (1 << 63) - 1
same = A == B
tops = sum(1 for v in B.values() if v == TOP)

print("=" * W)
print("  Lattix の字句解析器を、ネイティブで実ファイルに当てる")
print("=" * W)
print(f"  入力 {len(rawb)} バイト（コメント・文字列そのまま） / トークン {len(B)} 個 / ⊤ {tops}")
print(f"  解釈実行と一致: {'✓' if same else '✗'}   ({meta.get('NATIVE_MS', 0):.2f} ms)")
print("-" * W)
print("  ホストがやったのは実行ファイルを起動したことだけ。**前処理はゼロ。**")
print("  ファイルを開いたのも、コメントと文字列を飛ばしたのも、切ったのも、")
print("  名前を付けたのも Lattix 側である。")
print("  コメントは単調な鎖（否定も剰余も要らない）、文字列は引用符の **偶奇** ——")
print("  最後まで足りなかった言語機能は、剰余ひとつだった。")
print("=" * W)
sys.exit(0 if (same and tops == 0) else 1)
