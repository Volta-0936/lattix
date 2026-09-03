#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**Lattix が読んだ表を、Lattix が機械語に焼く。** —— G4b の前半。

三段とも Lattix である:

    21_lex.lx    バイト列        → トークンの表
    22_parse.lx  トークンの表    → `trow[表, 行, 列]`（地上データ）
    31_gen.lx    その表          → **静的 ELF**

段の間でホストがやるのは、場を表に落として次に渡すことだけである
（`selfparse` と同じ。runtime.py が `field <名> <行数> <次数>` として既に読める形）。
出てきた実行ファイルを走らせた終了コードが、同じ `.lx` を解釈実行した答えと
一致すれば、**入口から出口まで判断は Lattix 側にある**。

まだ手で置いているのは *規則の形*（読み列・書き列・重み列）である。
それを 22_parse の出力から導くのが G4b の後半で、そこまで行けば
「.lx を入れて実行ファイルが出る」が Lattix だけで閉じる。
"""
import io, os, re, stat, struct, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

W = 84


def strip(path):
    return "\n".join(ln for ln in open(path, encoding='utf-8').read().splitlines()
                     if not (ln.startswith('table ch') or ln.startswith('table tok')))


LEX = strip(os.path.join(ROOT, 'examples', '21_lex.lx'))
PAR = strip(os.path.join(ROOT, 'examples', '22_parse.lx'))
GEN = open(os.path.join(ROOT, 'examples', '31_gen.lx'), encoding='utf-8').read()


def go(src, extra=""):
    p = L.parse(src + "\n" + extra)
    L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    store, _, _st = L.run(p, out=io.StringIO())
    return lambda f: {k: p.fields[f].observe(v) for k, v in store[f].items()}


def front(path):
    """21_lex → 22_parse。**両方とも Lattix である。**"""
    codes = list(open(path, 'rb').read()) + [32]
    o = go("table ch = " + ", ".join(f"({i},{c})" for i, c in enumerate(codes)), LEX)
    tk, tc, tc2, tl, ts, ti = (o('tk'), o('tc'), o('tc2'), o('tline'),
                               o('tsym'), o('tint'))
    rows = [(k[0], tk[k], tc[k], tc2.get(k, 0), tl[k],
             ti[k] if tk[k] == 1 else ts[k]) for k in sorted(tk)]
    o2 = go("table tok = " + ", ".join(str(r).replace(" ", "") for r in rows), PAR)
    return o2('trow')


def emit(rows, seeds, tmp, tag):
    sd = ", ".join(f"({k},0,{c},{v})" for k, (c, v) in enumerate(seeds))
    src = GEN
    src, n0 = re.subn(r"table seed  = .*?\n(?=table)", f"table seed  = {sd}\n", src,
                      count=1, flags=re.S)
    assert n0 == 1, "seed 表の差し替えが空振りした"
    lx = os.path.join(tmp, f"g{tag}.lx")
    open(lx, 'w', encoding='utf-8').write(src)
    exe = os.path.join(tmp, f"a{tag}.out")
    with open(exe, 'wb') as fp:
        subprocess.run([sys.executable, os.path.join(ROOT, 'lattix.py'), lx],
                       stdout=fp, stderr=subprocess.PIPE)
    os.chmod(exe, os.stat(exe).st_mode | stat.S_IEXEC)
    blob = open(exe, 'rb').read()
    if blob[:4] != b'\x7fELF': return len(blob), {}
    # **地上データは stdin から。** 行を 8バイト小端で流す。
    ncols = max(c for _i, c, _v in rows) + 1
    byrow = {}
    for i, c, v in rows: byrow.setdefault(i, {})[c] = v
    indata = b"".join(struct.pack("<q", byrow[i].get(c, 0))
                      for i in sorted(byrow) for c in range(ncols))
    r = subprocess.run([exe], input=indata, capture_output=True)
    F = struct.unpack('<64q', r.stdout[:512])
    return len(blob), {(k,): v for k, v in enumerate(F) if v != 2147483647}


SRC = """table edge = (0,1,4), (0,2,1), (2,1,2), (1,3,5), (3,4,3), (4,5,2)
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edge
print dist
"""

tmp = tempfile.mkdtemp()
lxp = os.path.join(tmp, 'src.lx')
open(lxp, 'w', encoding='utf-8').write(SRC)

print("=" * W)
print("  Lattix が読んだ表を、Lattix が機械語に焼く（21 → 22 → 31）")
print("=" * W)

trow = front(lxp)                                  # ← 前段は丸ごと Lattix
# `rn` は文の中の行番号で 1 から始まる。0 起点に均す（**番号の起点も座標である**）。
raw = sorted((k[1], k[2], v) for k, v in trow.items())
base = min(r for r, _c, _v in raw)
edge = [(r - base, c, v) for r, c, v in raw]
ncol = max(c for _r, c, _v in edge) + 1
nrow = max(r for r, _c, _v in edge) + 1
print(f"  21_lex → 22_parse が読んだ表 : {nrow} 行 × {ncol} 列 "
      f"= {len(edge)} セル（`trow`）")

# Python 版の構文解析器が読んだ表と、同じか
pp = L.parse(SRC)
want_rows = [(i, c, v) for i, row in enumerate(pp.tables['edge'])
             for c, v in enumerate(row)]
same_tbl = edge == sorted(want_rows)
print(f"  Python 版の構文解析器と一致 : {'✓' if same_tbl else '✗'}")

n, got = emit(edge, [(0, 0)], tmp, 0)
p2 = L.parse(SRC); L.check(p2); L.stratify(p2); L.io_rounds(p2); L.certify(p2)
st, _c, _s = L.run(p2, out=io.StringIO())
ref = {k: p2.fields['dist'].observe(v) for k, v in st['dist'].items()}
same_ans = got == ref
print("-" * W)
print(f"  31_gen が焼いた実行ファイル : {n} バイト（静的 ELF）")
print(f"  書き出した場                : {len(got)} セル   解釈実行と "
      f"{'一致 ✓' if same_ans else '不一致 ✗'}")
ok = same_tbl and same_ans
print("-" * W)
print("  一致" if ok else "  不一致")
print("  字句・構文・コード生成の三段が Lattix で、間にあるのは表の受け渡しだけ。")
print("  規則の形まで含めた全経路は selfgen が検査する（32_shape が形を導く）。")
print("=" * W)
sys.exit(0 if ok else 1)
