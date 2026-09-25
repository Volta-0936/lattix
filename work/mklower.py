#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**下ろしを組む。** —— `lower.lx` = 33_self（前段）+ lib/lower.lx（下ろしの規則）。

    python3 work/mklower.py          # 型紙を種に起こして lib/lower.lx に書き、lower.lx を組む
    ./lattix lower.lx lower          # 焼く
    ./lower prog.lx > prog.low.lx    # 下ろす
    ./lattix prog.low.lx prog        # 焼く

**型紙は読める形で書き、ここで種に起こす**（31_gen の命令の形と同じくデータで持つ）。
`{h:w}` は穴 h（0..3）を w 桁の席に右寄せで置く —— 上の桁の 0 は ⊥ のまま残り、
render が飛ばすので可変長に詰まって出る（⊥ は幅 0 の glue）。これは組む道具であって、
下ろす道には居ない（焼いた `lower` は Python を知らない）。
"""
import os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 型紙の番号は lib/lower.lx の規則が名指しする（番号を動かすときは両方を見る）。
# `{h:w}` は穴 h を w 桁の席に右寄せ、`@` は名前の十六升（宣言の綴り。短ければ残りは ⊥）。
LOOP2 = "\n      for (_k) in 0 .. {1:7} for (_m) in 0 .. {2:7}"
TEMPLATES = [
    (0, " (_r{0:1}) in 0 .. {1:7}"),             # 表のループ → 区間（L, 行数-1）
    (1, "_t{0:2}c{1:2}[_r{2:1}]"),                 # 表の変数 → 列の場の読み（表, 列, L）
    (2, " bound 4096"),                            # 広さの無い一次元の場
    (3, " bound 256 256"),                         # 広さの無い二次元の場
    (4, "0"),                                      # `n[]` → `n[0]`
    (5, "\n_t{0:2}c{1:2}[{2:7}] <- {3:10}"),       # 表の升 → 種（表, 列, 行, 値）
    (6, "\nfield _t{0:2}c{1:2} : flat bound {2:7}"),  # 表の列 → 場（表, 列, 行数）
    (7, " {0:7} .. {1:7}"),                        # `range(a, b)` の表 → 区間 a .. b-1（変数はそのまま）
    # print（一次元）: p, …
    (10, "\nfield _pr{0:2} : max bound {1:7}"),
    (11, "\n_pr{0:2}[_k] <- _k + {1:7}   for (_k) in 0 .. {2:7}"),
    (12, "\n_pv[_pr{0:2}[_k]] <- @[_k] for (_k) in 0 .. {2:6}"),
    (13, "\n_pbs[{0:2}] <- {1:7}\n_pen[{0:2}] <- {2:7}"),
    (14, "\n_Rz[0] <- {2:7}\n_Pz[0] <- {0:2}"),
    (15, "\n_por[{0:2}] <- true"),
    # print（二次元）
    (16, "\nfield _pr{0:2} : max bound {1:7} {2:7}"),
    (17, "\n_pr{0:2}[_k, _m] <- _k * {1:7} + _m + {2:7}"),
    (18, LOOP2),
    (19, "\n_pv[_pr{0:2}[_k, _m]] <- @[_k, _m]"),
    (20, "\n_pk1[_pr{0:2}[_k, _m]] <- _k"),
    (21, "\n_pk2[_pr{0:2}[_k, _m]] <- _m"),
    (22, "\n      if @[_k, _m] == @[_k, _m]"),
    (23, "\n_pd2[{0:2}] <- true"),
    (24, "\n_pnm[{0:2}, {1:2}] <- {2:3}"),         # 名前の字
    (25, "\n_pd0[{0:2}] <- true"),                  # `n[]` の場（座標を書かない）
]
WIDTH = 63                                         # 型紙の升（lx の 1..63）


def cells(text):
    """型紙 → [(字, 穴, 桁)]。字は数、穴は 1 起点（0 は穴でない）、桁は右から。
       名前の升は穴 0・桁 -(k+1)（k 文字目）。"""
    out, i = [], 0
    while i < len(text):
        m = re.match(r'\{(\d):(\d+)\}', text[i:])
        if m:
            h, w = int(m.group(1)), int(m.group(2))
            out += [(None, h + 1, w - 1 - k) for k in range(w)]
            i += m.end()
        elif text[i] == '@':
            out += [(None, 0, -(k + 1)) for k in range(16)]; i += 1
        else:
            out.append((ord(text[i]), 0, 0)); i += 1
    assert len(out) <= WIDTH, (text, len(out))
    return out


def seeds():
    lines = ["# ── 型紙（work/mklower.py が起こす。手で直さない）──"]
    for k, text in TEMPLATES:
        lines.append(f"# {k}: {text!r}")
        for j, (c, h, d) in enumerate(cells(text)):
            if h == 0 and d < 0:
                lines.append(f"tpn[{k}, {j}] <- {-d}")
            elif h == 0:
                lines.append(f"tpc[{k}, {j}] <- {c}")
            else:
                lines.append(f"tph[{k}, {j}] <- {h}")
                lines.append(f"tpd[{k}, {j}] <- {d}")
    # print の機械（下ろした本の末尾に一度だけ置く字の並び）と `table ch`
    eng = open(os.path.join(ROOT, 'work', 'lower', 'engine.lx'), encoding='utf-8').read()
    bt = ": ⊥ everywhere (no coordinate reached a definite value)\n".encode()
    eng += "".join(f"_bt[{i}] <- {b}\n" for i, b in enumerate(bt))
    eng += "table ch = (0,32)\n"
    data = ("\n" + eng).encode()
    assert len(data) <= 8192, len(data)
    lines.append(f"# print の機械（work/lower/engine.lx の {len(data)} バイト）")
    lines += [f"lk[{i}] <- {b}" for i, b in enumerate(data)]
    lines.append("# ── 型紙ここまで ──")
    return "\n".join(lines) + "\n"


def digit_rules():
    """穴 h の d 桁目を置く規則（d = 0 は常に、d ≥ 1 は値がその桁に届くときだけ）と、名前の升。"""
    L = f"for (c) in 0 .. ncz[0] for (j) in 0 .. {WIDTH - 1}"
    out = ["# ── 穴の桁と名前の升（work/mklower.py が起こす。手で直さない）──"]
    for h in range(4):
        for d in range(10):
            p = 10 ** d
            val = f"48 + ch{h}[c] % 10" if d == 0 else f"48 + ch{h}[c] / {p} % 10"
            g = "" if d == 0 else f" if ch{h}[c] >= {p}"
            out.append(f"lx[crow[c], j + 1] <- {val}   {L}\n      if tph[cti[c], j] == {h + 1}"
                       f" if tpd[cti[c], j] == {d}{g}")
    for k in range(16):
        out.append(f"lx[crow[c], j + 1] <- dch[cnd[c], {k}]   {L} if tpn[cti[c], j] == {k + 1}")
    out.append("# ── 穴の桁ここまで ──")
    return "\n".join(out) + "\n"


def splice(src, tag, body):
    a, b = f"# <<{tag}>>\n", f"# <</{tag}>>\n"
    i, j = src.index(a) + len(a), src.index(b)
    return src[:i] + body + src[j:]


if __name__ == '__main__':
    lp = os.path.join(ROOT, 'lib', 'lower.lx')
    low = open(lp, encoding='utf-8').read()
    low = splice(low, 'templates', seeds())
    low = splice(low, 'digits', digit_rules())
    open(lp, 'w', encoding='utf-8').write(low)
    front = open(os.path.join(ROOT, 'examples', '33_self.lx'), encoding='utf-8').read()
    front = "\n".join(l for l in front.splitlines() if not l.startswith('print '))
    # 下ろす源は 262,144 バイトまで（焼き手の 589,824 は焼き手自身を読むための広さ）。
    # 狭くするのは置き場のため —— 前段の面は百九十枚あり、2 GB の手前に収めたい。
    front = front.replace('bound 589824', 'bound 262144')
    head = ("# **下ろす（lower.lx）** —— 自由に書かれた .lx を、焼ける形（SPEC §12）の .lx に書き換える。\n"
            "# 中身は examples/33_self.lx（前段）と lib/lower.lx（下ろしの規則）を繋いだもの。\n"
            "# work/mklower.py が組む。**手で直さない。**\n\n")
    out = head + front + "\n" + low
    names = re.findall(r'(?m)^field (\w+)', out)
    dup = sorted({n for n in names if names.count(n) > 1})
    assert not dup, f"場の名前がぶつかっている: {dup}"
    open(os.path.join(ROOT, 'lower.lx'), 'w', encoding='utf-8').write(out)
    print('lower.lx', len(out.encode()), 'バイト')
