#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**焼く側の層は、答えの定義の層を守るか。** —— 成層の突き合わせ。

焼く側（`examples/33_self.lx`）は源のトークンだけを見て文に層を振る。
答えの定義（`lattix.classify`）は式の木を見て、読みごとに単調か否かを言う。
二つは別の道具で書かれているので、**同じことを言っているか**は測るしかない。

守るべきことは二つだけである:
    非単調な読み   読み手の層 > 書き手の層（書き終わってから読む）
    単調な読み     読み手の層 ≥ 書き手の層
焼く側の層が余分に深いのは構わない（答えは変わらない）。**足りないのが嘘**で、
足りないと、同じ表を回る規則が一つのループに畳まれて途中の値を掴む。

測り方: 断片に探針を足して焼き（文 s の層を一バイトで描く）、源を食わせる。
探針が描いた層は **焼く側が実際に使う層そのもの**である —— 写しの模型ではない。
解釈実行の規則とは、頭の行で対にする（取り込んだ規則は行が合わないので数えない）。

   使い方:  python3 test/strat.py [源…]
"""
import os, re, subprocess, sys, glob, tempfile, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
LATTIX = os.environ.get("LATTIX_EXE", os.path.join(ROOT, "lattix"))
W = 78

# ── 探針: 断片の層を文ごとに一バイト（32 は規則でない文）──────────────
front = open(os.path.join(ROOT, 'examples', '33_self.lx'), encoding='utf-8').read()
front = "\n".join(l for l in front.splitlines() if not l.startswith('print '))
front += """

field lvout : max bound 4096
lvout[s] <- 32 for (s) in 0 .. nstz[0]
lvout[s] <- level[s] + 48 for (s) in 0 .. nstz[0] if hasr[s]
render lvout
"""
tmp = tempfile.mkdtemp()
probe = os.path.join(tmp, 'probe')
r = subprocess.run([LATTIX], input=front.encode(), capture_output=True)
if r.returncode or r.stdout[:4] != b'\x7fELF':
    print("探針が焼けなかった:", r.stderr[:200]); sys.exit(2)
open(probe, 'wb').write(r.stdout); os.chmod(probe, 0o755)


def statements(raw):
    """断片と同じ切り方で文を数える: 行頭の語が文の頭（`for` / `if` は続き）。
    文 0 は源の頭 —— 最初の行が文なら、それが文 0 である。"""
    heads = []          # 文番号 → (行, 書き先の名前 or None)
    lines = raw.decode('utf-8', 'replace').split('\n')
    first = True
    for ln, text in enumerate(lines, 1):
        if not text or text[0] in ' \t\r#':
            first = False if text and text[0] != '#' else first
            continue
        w = re.match(r'[A-Za-z0-9_]+', text)
        if w and w.group(0) in ('for', 'if'): continue
        m = re.match(r'(\w+)\[', text)
        if first and ln == 1:
            heads.append((ln, m.group(1) if m else None))
        else:
            if not heads: heads.append((0, None))      # 源の頭（注釈など）
            heads.append((ln, m.group(1) if m else None))
        first = False
    return heads


def refs_of(r):
    out = set()
    for e in r.keys + [r.value] + r.guards: L.field_refs(e, out)
    for vs, src in r.sources:
        if isinstance(src, tuple) and src[0] == '..':
            L.field_refs(src[1], out); L.field_refs(src[2], out)
    return out


def check(path):
    raw = open(path, 'rb').read()
    r = subprocess.run([probe], input=raw, capture_output=True)
    if r.returncode:
        return None, f"探針が止まった rc={r.returncode}"
    lv = r.stdout
    # **層 127 は「深すぎる」**（`toodeep`）—— 焼く側はそこで断る。断るのは嘘ではない。
    deep = any(b != 32 and b - 48 >= 127 for b in lv)
    try:
        p = L.parse(raw.decode('utf-8')); L.check(p)
    except Exception as ex:
        return None, f"解釈実行が読まない: {str(ex)[:40]}"
    try:
        L.stratify(p)
    except Exception as ex:
        # 答えの定義が「成層できない」と言うなら、焼く側も断っていなければならない
        if deep: return None, "両者が断る（成層できない）"
        return (0, [(0, '—', '—', 0, 0, '成層できないのに焼く側が層を振った')], 0), None
    if deep:
        return None, "焼く側が断る（層が深すぎる）"
    heads = statements(raw)
    stmt_of_line = {ln: s for s, (ln, h) in enumerate(heads)}
    writers = collections.defaultdict(list)
    for s, (ln, h) in enumerate(heads):
        if h: writers[h].append(s)
    lines = raw.decode('utf-8').split('\n')
    lvl = lambda s: None if s >= len(lv) or lv[s] == 32 else lv[s] - 48
    n, bad = 0, []
    for rr in p.rules:
        if rr.lineno > len(lines) or not lines[rr.lineno - 1].startswith(rr.target + '['):
            continue                                   # 取り込んだ規則（行が合わない）
        s = stmt_of_line.get(rr.lineno)
        if s is None or lvl(s) is None: continue
        for f in refs_of(rr):
            for w in writers.get(f, []):
                if lvl(w) is None: continue
                n += 1
                nm = f in rr.nonmono_reads
                if (lvl(s) <= lvl(w)) if nm else (lvl(s) < lvl(w)):
                    bad.append((rr.lineno, rr.target, f, lvl(s), lvl(w), '非単調' if nm else '単調'))
    return (n, bad, max((b - 48 for b in lv if b != 32), default=-1) + 1), None


if __name__ == '__main__':
    files = sys.argv[1:] or (sorted(glob.glob(os.path.join(ROOT, 'examples', '*.lx'))) +
                             sorted(glob.glob(os.path.join(ROOT, 'work', 't', '*.lx'))) +
                             [os.path.join(ROOT, 'lattix.lx')])
    print("=" * W)
    print("  **焼く側の層は、答えの定義の層を守るか** —— 探針が描いた層で測る")
    print("=" * W)
    print(f"  {'源':<26}{'読みの辺':>8}{'破れ':>6}{'層':>5}")
    print("-" * W)
    tot, broken, skipped = 0, 0, 0
    for path in files:
        res, why = check(path)
        name = os.path.basename(path)
        if res is None:
            skipped += 1
            print(f"  {name:<26}{'':>8}{'':>6}{'':>5}   —  {why}"); continue
        n, bad, depth = res
        tot += n; broken += len(bad)
        print(f"  {name:<26}{n:>8}{len(bad):>6}{depth:>5}   {'✓' if not bad else '✗'}")
        for b in bad[:3]:
            print(f"      行 {b[0]}: {b[1]} が {b[2]} を読む（{b[5]}）—— 層 {b[3]} / 書き手 {b[4]}")
    print("-" * W)
    print(f"  読みの辺 {tot}  破れ {broken}  測れなかった源 {skipped}")
    if broken:
        print("  **破れがある** —— 焼く側は、書き終わる前の値を読む。")
        sys.exit(1)
    print("  **破れ無し** —— 焼く側の層は、答えの定義が要る順序をすべて守る。")
