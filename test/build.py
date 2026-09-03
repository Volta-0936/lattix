#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**ビルド系が、実ディレクトリで動く。**

make は「規則と順序」を書く言語である。`examples/30_build.lx` には順序が
一行も無い。書いてあるのは依存の半順序 D だけで、**段は D から出てくる**。

ここで見たいのは三つ:

  1. 実ファイルを見て、正しいものだけを作り直すか（手書きの参照実装と突き合わせ）
  2. 段（level）が依存の最長路になっているか —— **ビルドする前に印字される**
  3. 外界との往復が **段数によらず 2 回** であること

3 が make との差である。`make -j8` は 8 を人が推測して渡し、依存は掘りながら
見つける。Lattix は先に全部の段を出すので、資源は **一度で計画を受け取る**。
同じ段のものに順序は無い —— 無いと分かっているから、好きに使ってよい。

ホストは Python で書いてあるが、それは *外界* である（ファイルを読み書きする
のは誰かがやらねばならない）。**判断は一つも Python 側に無い** ——
何が古いか、どの段か、何を作るかは、全部 .lx が決めている。
"""
import io, os, shutil, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

W = 84
SRC = open(os.path.join(ROOT, 'examples', '30_build.lx'), encoding='utf-8').read()

# 実ディレクトリの中身。原本だけが最初から在り、`.out` は作られる。
# **献立（`.in`）もファイルであり、依存の一つである** —— make と同じで、
# 献立が変われば作り直す。
TREE = {
    'base.txt': "BASE\n",
    'util.txt': "UTIL\n",
    'lib.in':   'include "base.txt"\ninclude "util.txt"\nLIB\n',
    'doc.in':   'include "base.txt"\nDOC\n',
    'app.in':   'include "lib.out"\nAPP\n',
    'top.in':   'include "app.out"\ninclude "doc.out"\nTOP\n',
}
MADE = ['lib.out', 'doc.out', 'app.out', 'top.out']
ORDERED = sorted(list(TREE) + MADE)         # 走査順は番号付けに使うだけ


def make_tree(d):
    for n, body in TREE.items():
        open(os.path.join(d, n), 'w', encoding='utf-8').write(body)


def includes(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('include "') and line.endswith('"'):
            out.append(line[9:-1])
    return out


def deps_of(d, name):
    """**依存は中身から出てくる。** `.out` は献立 `.in` と、その include。"""
    if name not in MADE: return []
    rec = name[:-4] + '.in'
    p = os.path.join(d, rec)
    text = open(p, encoding='utf-8').read() if os.path.exists(p) else TREE[rec]
    return [rec] + includes(text)


def bundle(d, name):
    """`.out` を作る = 献立を読み、include を中身で置き換える。実際に書く。"""
    rec = name[:-4] + '.in'
    body = []
    for line in open(os.path.join(d, rec), encoding='utf-8').read().splitlines():
        s = line.strip()
        if s.startswith('include "') and s.endswith('"'):
            body.append(open(os.path.join(d, s[9:-1]), encoding='utf-8').read())
        else:
            body.append(line + "\n")
    open(os.path.join(d, name), 'w', encoding='utf-8').write("".join(body))


def run_build(d):
    """.lx を一度走らせる。ホストは観測と実行だけ、判断はしない。"""
    names = ORDERED
    num = {n: i for i, n in enumerate(names)}
    built, plan, rt, asked = [], [], [], []

    def host(ch, items):
        if ch == 'scan':
            rt.append('scan')
            f = {'nfile': {(): len(names)}, 'mtime': {}, 'ndep': {},
                 'dep': {}, 'made': {}}
            for n in names:
                i = num[n]
                p = os.path.join(d, n)
                # 無いファイルは 0。**時刻は増えるだけ** なので観測は単調である。
                f['mtime'][(i,)] = (int(os.stat(p).st_mtime_ns // 1000)
                                    if os.path.exists(p) else 0)
                ds = deps_of(d, n)
                f['ndep'][(i,)] = len(ds)
                f['made'][(i,)] = 1 if n in MADE else 0
                for j, x in enumerate(ds):
                    f['dep'][(i, j)] = num[x]
            return f
        if ch == 'build':
            rt.append('build')
            asked.extend(items)             # **何を** 作るかは .lx が言う
            return {}
        return {}

    p = L.parse(SRC); L.check(p); depth = L.stratify(p)
    L.io_rounds(p); L.certify(p)
    store, _c, stats = L.run(p, out=io.StringIO(), host=host)
    lv = {names[k[0]]: p.fields['level'].observe(v)
          for k, v in store['level'].items()}
    # **順序は `todo` が言う。** ホストは段で並べるだけで、判断はしない。
    todo = {k[0]: p.fields['todo'].observe(v) for k, v in store['todo'].items()}
    plan = sorted((todo[i], i) for i in asked)
    for _l, i in plan:
        bundle(d, names[i]); built.append(names[i])
    return built, plan, lv, depth, stats, rt


# ── 手書きの参照実装（向きも順序も再帰も自分で書く）──────────────────
def reference(d):
    names = ORDERED
    dep = {n: deps_of(d, n) for n in names}
    mt = {n: (int(os.stat(os.path.join(d, n)).st_mtime_ns // 1000)
              if os.path.exists(os.path.join(d, n)) else 0) for n in names}
    lev, seen = {}, {}
    def level(n):
        if n in seen: return seen[n]
        seen[n] = 0 if not dep[n] else 1 + max(level(x) for x in dep[n])
        return seen[n]
    for n in names: lev[n] = level(n)
    stale = set()
    for n in sorted(names, key=level):
        if n not in MADE: continue
        if mt[n] == 0 or any(mt[n] < mt[x] for x in dep[n]) \
           or any(x in stale for x in dep[n]):
            stale.add(n)
    return stale, lev


def show(label, built, plan, want, lv, rt):
    good = sorted(built) == sorted(want)
    # 段の順を守っているか（同じ段の中の順序は問わない）
    ordered = all(plan[i][0] <= plan[i + 1][0] for i in range(len(plan) - 1))
    good &= ordered
    print(f"  {label:<26} 作った {len(built):>2} 本  往復 {len(rt)} 回   "
          f"{'✓' if good else '✗'}  {' '.join(sorted(built)) or '—'}")
    if not good:
        print(f"      参照 = {sorted(want)}")
    return good


d = tempfile.mkdtemp()
make_tree(d)
print("=" * W)
print("  ビルド系 —— 実ディレクトリを見て、何を作り直すかを決める")
print("=" * W)
print(f"  {d}  に原本 {len(TREE)} 本 → 生成物 {len(MADE)} 本。"
      "依存は **献立の中身から出てくる**")
print("-" * W)
ok = True

want, _lv = reference(d)
built, plan, lv, depth, stats, rt = run_build(d)
ok &= show("① 全部作る", built, plan, want, lv, rt)

lvref = reference(d)[1]
same_lv = lv == lvref
ok &= same_lv
print(f"  {'段（依存の最長路）':<22} " +
      "  ".join(f"{n}={lv[n]}" for n in ORDERED) +
      f"   参照 {'✓' if same_lv else '✗'}")
wide = {}
for n, l in lv.items(): wide[l] = wide.get(l, 0) + 1
print(f"  {'段ごとの幅（＝同時に作れる本数）':<20} " +
      "  ".join(f"段{l}:{wide[l]}本" for l in sorted(wide)) +
      "   ← `-j` を推測しなくてよい")
print(f"  {'逐次深度（規則の段数）':<23} {depth}"
      "     ← **ビルドを一つも走らせる前に印字される**")

want, _ = reference(d)
built, plan, _lv, _d, _s, rt = run_build(d)
ok &= show("② もう一度（何もしない）", built, plan, want, lv, rt)

time.sleep(0.01)
os.utime(os.path.join(d, 'util.txt'))          # 実際に touch する
want, _ = reference(d)
built, plan, _lv, _d, _s, rt = run_build(d)
ok &= show("③ util.txt を touch", built, plan, want, lv, rt)

os.remove(os.path.join(d, 'doc.out'))          # 生成物を消す
want, _ = reference(d)
built, plan, _lv, _d, _s, rt = run_build(d)
ok &= show("④ doc.out を消す", built, plan, want, lv, rt)

# ── 不変条件9: ネイティブでも同じビルドができるか ────────────────────
# 往復は **実行ファイルを呼び直すこと** になる。1回目は走査を求め、
# ホストが観測を書き、2回目が計画を出す。Python は判断を一つもしない。
import runtime as R
d2 = tempfile.mkdtemp(); make_tree(d2)
names = ORDERED; num = {n: i for i, n in enumerate(names)}
info = R.build(SRC)
base = R.write_data(info['prog'], os.path.join(info['dir'], 'base.lxd'))
_s, m1 = R.run(info['exe'], base)                       # 1回目 → EMIT scan
asked = [v for ch, v in m1.get('emit', []) if ch == 'scan']

rows = {'nfile': [(len(names),)], 'mtime': [], 'ndep': [], 'dep': [], 'made': []}
for n in names:
    i = num[n]; p = os.path.join(d2, n)
    rows['mtime'].append((i, int(os.stat(p).st_mtime_ns // 1000)
                          if os.path.exists(p) else 0))
    ds = deps_of(d2, n)
    rows['ndep'].append((i, len(ds)))
    rows['made'].append((i, 1 if n in MADE else 0))
    for j, x in enumerate(ds): rows['dep'].append((i, j, num[x]))
# 観測は **基底データに足す**。密配列の広さは argv[1] で決まるので、
# 外から来る座標はそこに居なければならない（超えれば実行時に落ちる。黙らない）。
obs = os.path.join(info['dir'], 'scan.lxd')
with open(obs, 'w') as fp:
    fp.write(open(base).read())
    for f, rs in rows.items():
        if not rs: continue
        fp.write(f"field {f} {len(rs)} {len(rs[0])}\n")
        for r in rs: fp.write(" ".join(str(x) for x in r) + "\n")
_s2, m2 = R.run(info['exe'], obs)                       # 2回目 → EMIT build
# 順序は `todo` が言う（解釈実行と同じ規則）。ホストは並べるだけ。
ntodo = {k[0]: v for k, v in _s2.get('todo', {}).items()}
njobs = sorted((ntodo[v], v) for ch, v in m2.get('emit', []) if ch == 'build')
for _lv, i in njobs: bundle(d2, names[i])
nat_built = sorted(names[i] for _lv, i in njobs)
want_all = sorted(reference(d)[0] | set())              # ①で作ったのと同じ集合
nat_ok = (asked == [0] and nat_built == sorted(MADE)
          and all(njobs[k][0] <= njobs[k + 1][0] for k in range(len(njobs) - 1))
          and open(os.path.join(d2, 'top.out'), encoding='utf-8').read()
          == "BASE\nUTIL\nLIB\nAPP\nBASE\nDOC\nTOP\n")
ok &= nat_ok
shutil.rmtree(d2, ignore_errors=True)
print("-" * W)
print(f"  ネイティブ（C {info['lines']} 行）でも同じビルド: "
      f"呼び直し 2 回で {len(nat_built)} 本   {'✓' if nat_ok else '✗'}")
print("    —— **参照実装でしか動かない機能は、機能ではない**（不変条件9）")

# 中身が本当に正しいか（連結の結果を見る）
got = open(os.path.join(d, 'top.out'), encoding='utf-8').read()
want_txt = "BASE\nUTIL\nLIB\nAPP\nBASE\nDOC\nTOP\n"
content = got == want_txt
ok &= content
print("-" * W)
print(f"  top.out の中身 {'✓ 一致' if content else '✗ 不一致'}   "
      f"{got.replace(chr(10), '/')}")
shutil.rmtree(d, ignore_errors=True)
print("-" * W)
print("  一致" if ok else "  不一致")
print("  **順序は一行も書いていない。** 段は依存の最長路として出てくる。")
print("  往復は段数によらず 2 回 —— 走査と、計画の受け渡し。")
print("  `make -j` は並列度を人が推測するが、ここでは **幅が印字されている**。")
print("=" * W)
sys.exit(0 if ok else 1)
