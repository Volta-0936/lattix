# 展開器（expand.s）を定義の _expand_includes と突き合わせる: ランダムな取り込みの木を作り、台（mkharness.py が組む
# `harness`）と定義の字を比べる。定義の「lattix.py の居場所」は台の「今の場所」に揃える（t/ に置いたことにする）
#   python3 mkharness.py && as -o harness.o harness.s && ld -o harness harness.o && python3 difftest.py
import os, random, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE))); import lattix as L
os.makedirs(os.path.join(HERE, 't'), exist_ok=True)
L.__file__ = os.path.join(HERE, 't', 'lattix.py')
R = random.Random(8)
os.chdir(os.path.join(HERE, 't'))
for d in ('sub','examples','lib','sub/sub','sub/examples','sub/lib','examples/sub','lib/sub'): os.makedirs(d, exist_ok=True)
def norm(t):
    ls = [l.strip() for l in t.split('\n')]
    while ls and ls[-1] == '': ls.pop()
    return ls
def mk(path, depth):
    lines = []
    for i in range(R.randint(0, 6)):
        c = R.random()
        if c < 0.25 and depth < 3:
            sub = f"f{R.randint(0,40)}.lx"
            where = R.choice(['', 'sub/', 'examples/', 'lib/'])
            tgt_dir = where
            name = sub
            # file location relative to cwd: sometimes relative to including dir
            if where in ('examples/', 'lib/'):
                full = where + name; ref = name
            elif where == 'sub/':
                full = 'sub/' + name; ref = 'sub/' + name
            else:
                full = name; ref = name
            mk(full, depth + 1)
            lead = R.choice(['', ' ', '\t', '  '])
            q = R.choice(['"%s"', '%s', '"%s" ', '""%s""'])
            lines.append(lead + 'include ' + R.choice(['', ' ']) + (q % ref))
        elif c < 0.3:
            lines.append(R.choice(['include', 'include   ', '# include "zz"', 'includes x', 'xinclude "a"']))
        else:
            lines.append(f"line{depth}_{i} " + R.choice(['', 'x <- 1', '(a,', '']))
    txt = '\n'.join(lines) + R.choice(['', '\n', '\n\n', '\r\n'])
    open(path, 'w').write(txt)
bad = 0
for n in range(600):
    for f in os.listdir('.'):
        pass
    mk('main.lx', 0)
    src = open('main.lx').read()
    try:
        want = L._expand_includes(src, None) if 'include ' in src else src
        wok = True
    except Exception as e:
        wok = False
    r = subprocess.run([os.path.join(HERE, 'harness'), 'main.lx'], capture_output=True)
    got = r.stdout.decode('latin-1')
    if not wok:
        if r.returncode == 0: bad += 1; print('SILENT-ACCEPT', n, r.stderr[:80])
        continue
    if r.returncode != 0 or got.replace('\r\n','\n').rstrip('\n') != want.replace('\r\n','\n').rstrip('\n'):
        bad += 1; print('DIFF', n, r.returncode, r.stderr[:80]); print(repr(want[:300])); print(repr(got[:300])); break
print('bad', bad)
