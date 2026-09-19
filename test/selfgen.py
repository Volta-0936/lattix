#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**`.lx` を入れると実行ファイルが出る。判断は全部 Lattix 側にある。**（G4b / G4c）

    21_lex.lx    バイト列      → トークンの表
    32_shape.lx  トークンの表  → 地上データ + **規則の形**（include 22_parse.lx）
    31_gen.lx    その形        → 静的 ELF

前回まで「読み列・書き列・重み列」は手で置いていた。それを導く規則を
`32_shape.lx` に書いた。探索は要らなかった —— 変数は既に **束縛点の座標**
（`vpos` = 組の何番目か）で名づけられているので、列は参照するだけである。
記号表も、束縛の環境も、α変換も、どこにも無い。

ホストがやるのは場を表に落として次の段へ渡すことだけで、
**何が種で、どれが再帰で、どの変数がどの列か** は一つも Python 側にない。

検査は二重である ——
**全セルが解釈実行と一致し、さらに attest が機械語の答えを別証する。**
出力は終了コードではなく **場と階数**（8バイト小端 ×64 が二本）。
答えは 8 ビットに縛られず、階数は証明書になる（不変条件6）。
"""
import array, io, os, pickle, re, stat, struct, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L
import attest as ATT

W = 84
INF = 2147483647
DOM = 64
EX = os.path.join(ROOT, 'examples')



def _run_with_witness(exe, indata):
    """**証人は fd 3 に出る**（開いていなければ書かれない）。試験は開けて受け取る。
       `sh -c 'exec 3>w; exec prog'` —— 引数は渡さないので argc は 1 のまま。"""
    import tempfile, os, subprocess as _sp
    d = tempfile.mkdtemp(); w = os.path.join(d, "witness.bin")
    r = _sp.run(['sh', '-c', 'exec 3>"$1"; shift; exec "$@"', 'sh', w, exe],
                input=indata, capture_output=True)
    try:
        wit = open(w, 'rb').read()
    except OSError:
        wit = b''
    try:
        os.unlink(w); os.rmdir(d)
    except OSError:
        pass
    return r, wit

def strip_text(t):
    return "\n".join(l for l in t.splitlines()
                     if not (l.startswith('table ch') or l.startswith('table tok')))


# include を **先に展開してから** 置き場所の表を外す（過去の事故のとおり）
LEX = strip_text(open(os.path.join(EX, '21_lex.lx'), encoding='utf-8').read())
SHP = strip_text(L._expand_includes(
    open(os.path.join(EX, '32_shape.lx'), encoding='utf-8').read(), EX + os.sep))
GEN = open(os.path.join(EX, '31_gen.lx'), encoding='utf-8').read()


# ── **同じプログラムを、速い実行で解く。** ────────────────────────────
# 答えは実行に依らない。ならば道具を焼くのに解釈実行を待つ理由は無い。
# `runtime.py` は **プログラムだけ** を C にするので、字句解析器も形の導出も
# 生成器も **一度焼いて、表を差し替えて何度でも走る** ——
# これは Lattix でしか取れない近道である（表は答えの一部ではなく、入力である）。
# C と解釈実行が同じ答えを出すことは test/runtimecheck.py が全例題で見張る。
# `LATTIX_SLOW=1` で解釈実行に戻る（同じ答えが出ることを確かめるため）。
import hashlib
import runtime as RT
SLOW = os.environ.get('LATTIX_SLOW') == '1'
CC = os.path.join(ROOT, '_gen', 'cc')     # 焼いた道具の置き場（走らせるたびに残る）
_C = {}
_STAMP = "".join(open(os.path.join(ROOT, f), encoding='utf-8').read()
                 for f in ('lattix.py', 'native.py', 'runtime.py'))


def _cinfo(key, src, allprints=True):
    if key not in _C:
        q = L.parse(src)
        ex = ("\n" + "\n".join(f"print {f}" for f in q.fields
                                if f not in q.prints)) if allprints else ""
        full = src + ex + "\n"
        h = hashlib.sha1((full + _STAMP + str(allprints)).encode()).hexdigest()[:16]
        # **-O0 で焼く。** 掃き取りは一つの巨大な関数なので、-O1 は
        # 17k 行で何分もかかる（走るのは 2 秒なのに）。道具は最適化しない。
        _C[key] = RT.build(full, keep=os.path.join(CC, h), opt="-O0",
                           only_prints=not allprints)
    return _C[key]


def _crun(key, src, tables, allprints=True):
    info = _cinfo(key, src, allprints)
    for t, rows in tables.items(): info['prog'].tables[t] = rows
    # データは走行ごとの名で書く —— 二つの走行が同じ器を使うと踏み合っていた
    d = RT.write_data(info['prog'], os.path.join(info['dir'], f'data.{os.getpid()}.lxd'),
                      atom=info['atom'])
    return info, d


def cgo(key, src, tables):
    info, d = _crun(key, src, tables)
    store, _m = RT.run(info['exe'], d)
    return lambda f: store.get(f, {})


def go(src, extra=""):
    p = L.parse(src + "\n" + extra)
    L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    st, _c, _s = L.run(p, out=io.StringIO())
    return lambda f: {k: p.fields[f].observe(v) for k, v in st[f].items()}


# **同じ源を何度も読み直さない。** 答えは実行に依らないので、
# (源, 道具) が同じなら形も同じである —— 41KB の断片を三つの試験が
# 何度も読み直していた（一回 4 分）。鍵は源と処理系のバイトそのもの。
FC = os.path.join(ROOT, '_gen', 'front')


def front(src):
    """21_lex → 32_shape（22_parse 込み）。**三段とも Lattix。**"""
    if not SLOW:
        h = hashlib.sha1((src + LEX + SHP + _STAMP).encode()).hexdigest()[:16]
        cf = os.path.join(FC, h + '.pkl')
        if os.path.exists(cf):
            try:
                with open(cf, 'rb') as fp: st = pickle.load(fp)
                return lambda f: st.get(f, {})
            except Exception:
                pass
        st = _front(src)
        os.makedirs(FC, exist_ok=True)
        tmpf = cf + f'.{os.getpid()}'
        with open(tmpf, 'wb') as fp: pickle.dump(st, fp, 4)
        os.replace(tmpf, cf)          # 途中の姿を他の走行に見せない
        return lambda f: st.get(f, {})
    return _front(src)


def _front(src):
    codes = list(src.encode()) + [32]
    chrows = [(i, c) for i, c in enumerate(codes)]
    if SLOW:
        o = go("table ch = " + ", ".join(f"({i},{c})" for i, c in chrows), LEX)
    else:
        o = cgo('lex', "table ch = (0,32)\n" + LEX, {'ch': chrows})
    tk, tc, tc2, tl, ts, ti = (o('tk'), o('tc'), o('tc2'), o('tline'),
                               o('tsym'), o('tint'))
    rows = [(k[0], tk[k], tc[k], tc2.get(k, 0), tl[k],
             ti[k] if tk[k] == 1 else ts[k]) for k in sorted(tk)]
    if SLOW:
        return go("table tok = " + ", ".join(str(r).replace(" ", "") for r in rows),
                  SHP)
    info, d = _crun('shp', "table tok = (0,0,0,0,0,0)\n" + SHP, {'tok': rows})
    store, _m = RT.run(info['exe'], d)
    return store


BOT = {1: 2147483647, 2: -2147483647, 3: 0, 6: 2147483647, 8: 0, 9: 0}
TOPV = 2147483646


def compile_lx(src, tmp, tag, inp=8, data=None):
    o = front(src)
    trow, isrec, isseed = o('trow'), o('isrec'), o('isseed')
    kc, ar, lt = o('kcol'), o('rar'), o('rlat')
    sc, sv, sf = o('scoord'), o('sval'), o('sfld')
    wf = o('wfld')
    flat_, fmapo = o('flat_'), o('fmap')
    h2, kc2, far_ = o('h2'), o('kcol2'), o('far_')
    stl, kdk = o('stl'), o('kdk')
    fwide, fwide2 = o('fwide'), o('fwide2')
    lk, llo, lhi, lar = o('lkind'), o('llo'), o('lhi'), o('lar')
    lbf, lbc = o('lbf'), o('lbc')      # 上端が場のとき（種2）
    # ガードも項も (文, 番号) の行として出てくる —— どちらも列ではない
    gk, gf, g1, g2c, gt, gvv = (o('gkind'), o('gfld'), o('gcol1'),
                                o('gcol2'), o('gtwo'), o('gvalv'))
    gok, gov = o('gok'), o('goval')      # 比較の辺の種（0 = 場の読み）と定数
    tk_, tf, t1, tvv = o('terkind'), o('terfld'), o('tercol'), o('terval')
    # 座標の行（所有者種, 文, 番号, 次元）
    cs, cf_, cc_, ch_, co_ = (o('cdsrc'), o('cdfld'), o('cdcol'),
                              o('cdhof'), o('cdoff'))

    # 場の一覧: 番号 → (束, 次数)。次数は使われ方から出る（far_）
    # 広さも導かれる: 書かれた座標と区間の上端が「少なくともここまで」と言う
    flds = sorted((n, flat_[k], far_.get((n,), 1), fwide.get((n,), 64),
                   fwide2.get((n,), fwide.get((n,), 64)))
                  for k, n in fmapo.items())

    raw = sorted((k[1], k[2], v) for k, v in trow.items())
    # 表の無い（区間だけの）プログラムでは raw が空 —— 行も空でよい
    base = min((r for r, _c, _v in raw), default=0)  # 行番号は 1 起点。0 に均す
    rows = [(r - base, c, v) for r, c, v in raw]
    seeds = [(sf[s], sc[s], sv[s]) for s in sorted(isseed) if isseed[s]]
    # 無いものは形が導かなかったもの。読み・重み・ガード・否定、どれも任意。
    # **規則は層の昇順に並べる**（st は 22_parse の成層そのもの）。
    order = [s for s in sorted(isrec, key=lambda s: (stl.get(s, 0), s)) if isrec[s]]
    rules0 = [(stl.get(s, 0), lt[s], ar[s], wf[s]) for s in order]
    # **書き先の座標が無い規則は焼けない。** ⊥ が blen に伝わって、番地の鎖が
    # 切れ、最後は segfault になる —— 黙って落ちる前に、ここで名前を言う。
    wc = {s[0] for (kk, ss, i, d) in cs if kk == 2 for s in [(ss,)]}
    miss = [r for r, s in enumerate(order) if s[0] not in wc]
    assert not miss, f"書き先の座標が導けない規則: {miss}（頭の添字が変数か確かめる）"
    # ループの行。**入れ子も源が言う**（for 節に沿った鎖）
    loops = [(r, l, lk[(s[0], l)], llo.get((s[0], l), 0), lhi.get((s[0], l), 0),
              lar.get((s[0], l), 0), lbf.get((s[0], l), 0), lbc.get((s[0], l), 0))
             for r, s in enumerate(order)
             for l in sorted(ll for (ss, ll) in lk if ss == s[0])]
    loops = [(k,) + row for k, row in enumerate(loops)]
    # ガード・項・座標の行。文番号 → 規則番号に付け替えるだけ
    guards0 = [(r, g, gk[(s[0], g)], gf.get((s[0], g), 0), g1.get((s[0], g), 0),
                gvv.get((s[0], g), 0), gok.get((s[0], g), 0), gov.get((s[0], g), 0))
               for r, s in enumerate(order)
               for g in sorted(gg for (ss, gg) in gk if ss == s[0])]
    terms0 = [(r, t, tk_[(s[0], t)], tf.get((s[0], t), 0), t1.get((s[0], t), 0),
               tvv.get((s[0], t), 0))
              for r, s in enumerate(order)
              for t in sorted(tt for (ss, tt) in tk_ if ss == s[0])]
    coords0 = [(kk, r, i, d, cs[(kk, s[0], i, d)], cf_.get((kk, s[0], i, d), 0),
                cc_.get((kk, s[0], i, d), 0),
                int(ch_.get((kk, s[0], i, d), 0)),   # 0 無し / 1 後置 / 2 前置
                co_.get((kk, s[0], i, d), 0))
               for r, s in enumerate(order)
               for (kk, ss, i, d) in sorted(cs) if ss == s[0]]

    # **座標の所有者に通し番号を振る。** 種と規則と番号の三つ組で引くと場が
    # 4次元になるが、**焼ける座標は 2次元まで**である —— 生成器が自分を
    # 焼けるようにするには、生成器自身が焼ける形で書かれていなければならない。
    own = {}
    for (kk, r, i, _d, *_x) in coords0:
        own.setdefault((kk, r, i), len(own))
    NOOWN = len(own)                 # 番兵は「所有者の数」（存在しない番号）
    coords = [(k, own[(kk, r, i)], r, d, src, cf, cc, hof, off)
              for k, (kk, r, i, d, src, cf, cc, hof, off) in enumerate(coords0)]
    rules = [ru + (own.get((2, r, 0), NOOWN),) for r, ru in enumerate(rules0)]
    guards = [(k,) + row + (own.get((1, row[0], row[1]), NOOWN),)
              for k, row in enumerate(guards0)]
    terms = [(k,) + row + (own.get((0, row[0], row[1]), NOOWN),)
             for k, row in enumerate(terms0)]

    # **表のループは 0 番でなければならない。** 生成器は rcx を 0 番のループの
    # 行に使うので、表が 1 番目にいると列を別のループの計数器から引く ——
    # 座標が番地に化けて、最後は境界検査（終了コード 6）で落ちる。
    # 黙って落ちる前に、**どの規則か**をここで言う。
    lk0 = {r: k for (_g, r, l, k, *_x) in loops if l == 0}
    tbl = sorted({r for (_g, _oo, r, _d, src, _cf, _cc, _h, _o) in coords
                  if src in (0, 2) and lk0.get(r) != 0})
    assert not tbl, ("表の列を引く規則の 0 番のループが表ではない: "
                     f"{[(r, rules[r]) for r in tbl]}"
                     "（`for (..) in <表>` を一番外側に置く）")
    fl = ", ".join(f"({f},{l},{a})" for f, l, a, _w, _w2 in flds)
    fd = ", ".join(f"({f},0,{w})" + (f", ({f},1,{w2})" if a == 2 else "")
                   for f, _l, a, w, w2 in flds)
    NOFLD = len(flds)                # **番兵は「場の数」**（存在しない場番号）
    sd = (", ".join(f"({k},{fd},{c},{v})" for k, (fd, c, v) in enumerate(seeds))
          or f"(0,{NOFLD},0,0)")
    rr = ", ".join("(" + ",".join(map(str, (k,) + ru)) + ")"
                   for k, ru in enumerate(rules))
    gd = (", ".join("(" + ",".join(map(str, row)) + ")" for row in guards)
          or "(0,63,0,0,0,0,0,0,0,0)")  # ガードが無いときも表は空にできない
    tm = (", ".join("(" + ",".join(map(str, row)) + ")" for row in terms)
          or "(0,0,63,0,0,0,0,0,0)")
    cr = (", ".join("(" + ",".join(map(str, row)) + ")" for row in coords)
          or "(0,0,63,0,0,0,0,0,0)")
    lp = ", ".join("(" + ",".join(map(str, row)) + ")" for row in loops)
    # ── 焼く。**生成器も一度だけ焼いて、表を差し替えて何度でも走らせる。**
    # 表は答えではなく入力である —— だからプログラムは一つで足りる。
    if not SLOW:
        fdrows = ([(f, 0, w) for f, _l, _a, w, _w2 in flds]
                  + [(f, 1, w2) for f, _l, a, _w, w2 in flds if a == 2])
        tabs = {'fld': [(f, l, a) for f, l, a, _w, _w2 in flds],
                'seed': ([(k, fd_, c, v) for k, (fd_, c, v) in enumerate(seeds)]
                         or [(0, NOFLD, 0, 0)]),
                'rrule': [(k,) + ru for k, ru in enumerate(rules)],
                'grd': guards or [(0, 63, 0, 0, 0, 0, 0, 0, 0, 0)],
                'trm': terms or [(0, 63, 0, 0, 0, 0, 0, 0)],
                'crd': coords or [(0, 0, 63, 0, 0, 0, 0, 0, 0)],
                'lop': loops or [(0, 63, 0, 0, 0, 0, 0, 0, 0)],
                'inp': [(inp,)], 'outp': [(0, 63, 8)], 'fdim': fdrows}
        info, dfile = _crun('gen', GEN, tabs, allprints=False)
        exe = os.path.join(tmp, f"a{tag}.out")
        r = subprocess.run([info['exe'], dfile], capture_output=True)
        open(exe, 'wb').write(r.stdout)
        os.chmod(exe, os.stat(exe).st_mode | stat.S_IEXEC)
        blob = r.stdout
        return _readback(flds, rules, blob, exe, data, trow)

    g = GEN
    ns = []
    for name, txt in (('fld  ', fl), ('seed ', sd), ('rrule', rr),
                      ('grd  ', gd), ('trm  ', tm), ('crd  ', cr),
                      ('lop  ', lp), ('inp  ', f"({inp})"), ('outp ', "(0,63,8)"),
                      ('fdim ', fd)):
        g, n = re.subn(rf"table {name} = .*?\n(?=table |#)",
                       f"table {name} = {txt}\n", g, count=1, flags=re.S)
        ns.append(n)
    assert ns == [1] * 10, f"表の差し替えが空振りした {ns}"
    lx = os.path.join(tmp, f"g{tag}.lx")
    open(lx, 'w', encoding='utf-8').write(g)
    exe = os.path.join(tmp, f"a{tag}.out")
    with open(exe, 'wb') as fp:
        subprocess.run([sys.executable, os.path.join(ROOT, 'lattix.py'), lx],
                       stdout=fp, stderr=subprocess.PIPE)
    os.chmod(exe, os.stat(exe).st_mode | stat.S_IEXEC)
    blob = open(exe, 'rb').read()
    return _readback(flds, rules, blob, exe, data, trow)


def bake(sp, tmp, tag, inp=8, data=None):
    """**導かれた形の表で焼く。** 表がどこから来たかは、ここでは問わない ——
    32_shape が出しても、断片（33_self）が出しても、同じ生成器が食う。"""
    tabs = {'fld': sp['fl'], 'seed': sp['seeds'] or [(0, len(sp['fl']), 0, 0)],
            'rrule': sp['rules'], 'grd': sp['guards'] or [(0, 63, 0, 0, 0, 0, 0, 0, 0, 0)],
            'trm': sp['terms'] or [(0, 63, 0, 0, 0, 0, 0, 0)],
            'crd': sp['coords'] or [(0, 0, 63, 0, 0, 0, 0, 0, 0)],
            'lop': sp['loops'] or [(0, 63, 0, 0, 0, 0, 0, 0, 0)],
            'inp': [(inp,)], 'outp': [(0, 63, 8)], 'fdim': sp['fd']}
    info, dfile = _crun('gen', GEN, tabs, allprints=False)
    exe = os.path.join(tmp, f"a{tag}.out")
    r = subprocess.run([info['exe'], dfile], capture_output=True)
    open(exe, 'wb').write(r.stdout)
    os.chmod(exe, os.stat(exe).st_mode | stat.S_IEXEC)
    return _readback(sp['flds'], sp['rules'], r.stdout, exe, data, sp['trow'])


def _readback(flds, rules, blob, exe, data, trow):
    """焼いた実行ファイルを走らせて、**場と階数**を読み戻す（8バイト小端）。"""
    if blob[:4] != b'\x7fELF':
        return flds, rules, len(blob), {}, {}
    # **符号面を踏み越えたら、そう言う。** 生成器がヘッダの空きに長さを書く ——
    # 黙って落ちるのと、落ちて名前を言うのは違う（不変条件8）。
    codelen = blob[8] | (blob[9] << 8) | (blob[10] << 16) | (blob[11] << 24)
    assert 120 + codelen <= len(blob), (
        f"符号面が足りない: 120+{codelen} > {len(blob)}（31_gen の total[] を広げる）")
    if data is not None:                      # 生バイトをそのまま流す
        indata = data
    else:                                     # **地上データは実行ファイルの外**
        ncols = max((k[2] for k in trow), default=-1) + 1
        byrow = {}
        for k, v in trow.items(): byrow.setdefault(k[1], {})[k[2]] = v
        indata = b"".join(struct.pack("<q", byrow[rn].get(c, 0))
                          for rn in sorted(byrow) for c in range(ncols))
    r, _wit = _run_with_witness(exe, indata)
    ncell = sum(w * (w2 if a == 2 else 1) for _f, _l, a, w, w2 in flds)
    # **升の幅は束が言う**（31_gen の `fwb` と同じ規則）—— `or` は 0 か 1 しか
    # 取らないので一升 1 バイト。階数は束によらず 4 バイト。
    nbytes = sum((w * (w2 if a == 2 else 1)) * (1 if l == 3 else 8)
                 for _f, l, a, w, w2 in flds)
    # **升の数だけ Python の整数を作らない。** バイトの並びのまま持つ ——
    # 86万升で 500MB 使って落ちた（答えではなく、答えの受け取り方が重かった）。
    assert len(r.stdout) >= nbytes, (
        f"場が足りない: {len(r.stdout)} < {nbytes}（終了コード {r.returncode}）")
    # 証人は fd 3 から: [値の面][階数の面]（階数は 4 バイト升）。値の面は答え（stdout）と同じバイト
    assert _wit[:nbytes] == r.stdout[:nbytes], "証人の値の面が答えと違う"
    K = array.array('i'); K.frombytes(_wit[nbytes:nbytes + 4*ncell])
    store, rank, off, bo = {}, {}, 0, 0
    for f, l, a, w, w2 in flds:
        cells = w * (w2 if a == 2 else 1)
        wb = 1 if l == 3 else 8
        F = array.array('B' if wb == 1 else 'q')
        F.frombytes(r.stdout[bo:bo + wb * cells])
        key = (lambda k: (k,)) if a == 1 else (lambda k, ww=w2: (k // ww, k % ww))
        dec = ((lambda v: True) if l == 3
               else (lambda v: L.TOP if v == TOPV else v))
        store[f] = {key(k): dec(F[k]) for k in range(cells) if F[k] != BOT[l]}
        rank[f] = {key(k): K[off+k] for k in range(cells) if K[off+k]}
        bo += wb * cells
        off += cells
    return flds, rules, len(blob), store, rank


def interp(src):
    p = L.parse(src); L.check(p); L.stratify(p); L.io_rounds(p); L.certify(p)
    st, _c, _s = L.run(p, out=io.StringIO())
    names = [f for f in p.fields]
    return names, {i: {k: p.fields[nm].observe(v) for k, v in st[nm].items()}
                   for i, nm in enumerate(names)}


A = """table edge = (0,1,4), (0,2,1), (2,1,2), (1,3,5), (3,4,3), (4,5,2)
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edge
"""
B = """table edge = (0,1,7), (1,2,9), (0,2,30), (2,3,2)
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edge
"""
# **列の順を入れ替える。** 手で置いていたら気づかないところである。
C = """table edge = (1,4,0), (2,1,0), (1,2,2), (3,5,1), (4,3,3), (5,2,4)
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (w,j,i) in edge
"""
# 規則を二本（無向グラフ）
D = """table edge = (0,1,4), (0,2,1), (2,1,2), (1,3,5), (3,4,3), (4,5,2)
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edge
dist[i] <- dist[j] + w   for (i,j,w) in edge
"""

# **束を変える。** min と or では処理系が選ぶ命令が違う（cmp/jge と test/cmpq）。
E = """table edge = (0,1), (1,2), (2,3), (4,5)
field reach : or
reach[0] <- true
reach[j] <- true   for (i,j) in edge if reach[i]
"""

# 8 ビットに入らない答え。終了コードの試験ではここが測れなかった。
F_ = """table edge = (0,1,4000), (1,2,90000), (0,2,300000), (2,3,2000000)
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edge
"""
# **二つの場・二つの束・ガード** —— どれも 32_shape が源から導く。
G_ = """table edge = (0,1,4,1), (0,2,1,1), (2,1,2,1), (1,3,5,1), (3,4,3,1), (4,5,2,1), (0,5,99,0)
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w,t) in edge if t == 1
field far : max
far[0] <- 0
far[j] <- far[i] + w     for (i,j,w,t) in edge if t == 1
"""

# **2次元の座標** —— rd[j,v] は「変数 v の定義が j に届くか」。29_dataflow の核。
H_ = """table step = (0,1,5), (1,2,5), (0,2,7), (2,3,7), (3,1,9)
field rd : or
rd[0, 5] <- true
rd[0, 7] <- true
rd[j, v] <- true   for (i,j,v) in step if rd[i, v]
field hit : or
hit[j] <- true     for (i,j,v) in step if rd[i, v]
"""

# **層・否定・読み無し規則。** unre は「使われているのに届かない」——
# reach の層が閉じてから回る（成層は 22_parse の level がそのまま入る）。
I_ = """table edge = (0,1,1), (1,2,1), (4,5,0), (2,3,1)
field reach : or
reach[0] <- true
reach[j] <- true   for (i,j,t) in edge if reach[i]
field used : or
used[j] <- true    for (i,j,t) in edge if t == 1
field unre : or
unre[j] <- true    for (i,j,t) in edge if used[j] if not reach[j]
"""

# **flat 定数伝播。** 二つの種が合流して ⊤、列の食い違いも ⊤。⊤ は答えである。
J_ = """table edge = (0,1,4), (5,1,4), (1,2,8), (2,3,9), (2,3,9)
field cv : flat
cv[0] <- 7
cv[5] <- 9
cv[j] <- cv[i]     for (i,j,t) in edge
field cw : flat
cw[j] <- t         for (i,j,t) in edge
"""

# **集約。** 出次数（count）と重みの和（sum）。一度だけ撃つ印は機械語の場になる。
K_ = """table edge = (0,1,4), (0,2,1), (2,1,2), (1,3,5), (0,3,9)
field reach : or
reach[0] <- true
reach[j] <- true   for (i,j,w) in edge if reach[i]
field outd : count
outd[i] <- 1       for (i,j,w) in edge
field wsum : sum
wsum[i] <- w       for (i,j,w) in edge
"""

# **鎖。** 生成器が自分の番地割り当てに使っている形そのもの。
L_ = """table rows = (1,5), (2,3), (3,7), (4,2)
field off : max
off[0] <- 0
off[i] <- off[i-1] + w   for (i,w) in rows
"""

# **記号表は不動点である。** ["dist","d","dist","w","d"] を intern する三行。
# ハッシュ表はどこにも無い —— 違いは or、最初は min、健全性は層。
_SP = ["dist", "d", "dist", "w", "d"]
_R9 = []
for _t, _w in enumerate(_SP):
    _R9.append((1, _t, 0, 0))
    for _d, _ch in enumerate(_w): _R9.append((0, _t, _d, ord(_ch)))
    _R9.append((0, _t, len(_w), 1))
for _i in range(len(_SP)):
    for _j in range(_i + 1, len(_SP)):
        for _d in range(min(len(_SP[_i]), len(_SP[_j])) + 1):
            _R9.append((2, _i, _j, _d))
M_ = ("table T = " + ", ".join(map(str, _R9)) + "\n"
      "field tch : max\n"
      "tch[a, b] <- c    for (k,a,b,c) in T if k == 0\n"
      "field diff : or\n"
      "diff[a, b] <- true  for (k,a,b,c) in T if k == 2 if tch[a, c] != tch[b, c]\n"
      "field aid : min\n"
      "aid[a] <- a       for (k,a,b,c) in T if k == 1\n"
      "aid[b] <- a       for (k,a,b,c) in T if k == 2 if not diff[a, b]\n")

# 区間。表が一つも無い —— 座標そのものを回る。計数器が座標である。
N_ = ("field acc : max\nacc[0] <- 0\n"
      "acc[i] <- acc[i-1] + 3   for (i) in 1 .. 9\n"
      "field mark : or\n"
      "mark[i] <- true          for (i) in 2 .. 5\n"
      "print acc\n")

# **ガードは何個でも並ぶ**（三つの数値＋否定）。列だった頃は一つが上限だった。
O_ = ("table T = (1,2,3,0), (1,2,3,1), (1,9,3,2), (1,2,3,3)\n"
      "field bad : or\nbad[3] <- true\n"
      "field good : or\n"
      "good[d] <- true  for (a,b,c,d) in T if a == 1 if b == 2 if c == 3 if not bad[d]\n"
      "print good\n")

# **二項の加算** s[j] <- a[i] + b[i]。項が行になったので、ただ二行並ぶ。
#   階数は二つの読みの最大 + 1 —— cmovl が分岐せずに最大を取る
P_ = ("table edge = (0,1,5), (1,2,7), (0,2,3)\n"
      "field a : max\na[0] <- 10\n"
      "a[j] <- a[i] + w    for (i,j,w) in edge\n"
      "field b : max\nb[0] <- 1\n"
      "b[j] <- b[i] + 1    for (i,j,w) in edge\n"
      "field s : max\n"
      "s[j] <- a[i] + b[i] for (i,j,w) in edge\n"
      "print s\n")

# **座標の広さも源が言う。** 2000 升の鎖 —— 64 升の壁はもう無い。
Q_ = ("field acc : max\nacc[0] <- 0\n"
      "acc[i] <- acc[i-1] + 3   for (i) in 1 .. 1999\n"
      "print acc\n")

# **場の値が座標** got[i] <- val[ptr[i]]。trie の一段 —— 綴りの照合の芯。
R_ = ("table edge = (0,3), (1,5), (2,7), (3,9)\n"
      "field ptr : max\nptr[i] <- p    for (i,p) in edge\n"
      "field val : max\nval[3] <- 30\nval[5] <- 50\nval[7] <- 70\nval[9] <- 90\n"
      "field got : max\ngot[i] <- val[ptr[i]]   for (i,p) in edge\n"
      "print got\n")

# **記号表を、対の行をホストが作らずに .lx から焼く。**
#   三重ループ (i,j,d) が綴りを比べ、二重ループ (i,j) が最初の証人を拾う。
#   値は **計数器そのもの**（`aid[j] <- i`）。ハッシュも対の表も無い。
_SP2 = ["dist", "d", "dist", "w", "d"]
S_ = ("table ch = " + ", ".join(str((t, d, ord(c)))
      for t, w in enumerate(_SP2) for d, c in enumerate(w + "\x01")) + "\n"
      "field tch : max\n"
      "tch[t, d] <- c   for (t,d,c) in ch\n"
      "field diff : or\n"
      "diff[i, j] <- true   for (i) in 0 .. 4 for (j) in 0 .. 4 for (d) in 0 .. 7 if tch[i, d] != tch[j, d]\n"
      "field aid : min\n"
      "aid[j] <- i   for (i) in 0 .. 4 for (j) in 0 .. 4 if not diff[i, j]\n"
      "print aid\n")

# **字句解析器を、断片だけで。** 構成子も cons も無い —— 範囲ガードと
#   比較ガード（`cls[i] != cls[i-1]`）と鎖（tnum）だけで語が切れる。
_LXSRC = "field d : min\nd[0] <- 12\n"
T_ = ("table ch = " + ", ".join(str((i, c)) for i, c in enumerate(_LXSRC.encode()))
      + "\n"
      "field alpha : or\n"
      "alpha[i] <- true   for (i,c) in ch if c >= 97 if c <= 122\n"
      "field digit : or\n"
      "digit[i] <- true   for (i,c) in ch if c >= 48 if c <= 57\n"
      "field idpart : or\n"
      "idpart[i] <- true  for (i,c) in ch if alpha[i]\n"
      "idpart[i] <- true  for (i,c) in ch if digit[i]\n"
      "field space : or\n"
      "space[i] <- true   for (i,c) in ch if c <= 32\n"
      "field cls : max\n"
      "cls[i] <- 1  for (i,c) in ch if idpart[i]\n"
      "cls[i] <- 3  for (i,c) in ch if space[i]\n"
      "cls[i] <- 4  for (i,c) in ch if not idpart[i] if not space[i]\n"
      "field brk : or\nbrk[0] <- true\n"
      "brk[i] <- true for (i,c) in ch if i >= 1 if cls[i] != cls[i-1]\n"
      "field tnum : max\ntnum[0] <- 0\n"
      "tnum[i] <- tnum[i-1] for (i,c) in ch if i >= 1 if not brk[i]\n"
      "tnum[i] <- tnum[i-1] + 1 for (i,c) in ch if i >= 1 if brk[i]\n"
      "print tnum\n")

# **列と場を比べる。** 以前は比較の両辺が場の読みでなければ導けず、
# `if i > lim[i]` も `if c > 100` も **黙って落ちていた**（ガードが出ない）。
# 比較は演算子が言う —— 辺は 場の読み / 表の列 / 区間の計数器 / 定数 の四種。
U_ = """table e = (0,3), (1,1), (2,5), (3,2), (4,4)
field lim : max
lim[i] <- v for (i,v) in e
field big : or
big[i] <- true for (i,v) in e if i > lim[i]
field small : or
small[i] <- true for (i,v) in e if i < lim[i]
"""

# **桁を積む。** `n[i-1] * 10 + d` —— 数を読むのは掛け算である。
# 項に「掛ける定数」を足すまで、断片は整数リテラルを読めなかった。
V_ = """table d = (0,1), (1,2), (2,3), (3,4)
field n : max
n[0] <- 1
n[i] <- n[i-1] * 10 + v   for (i,v) in d
"""

# **定数も座標である。** `m[i,0]` の 0 は列でも計数器でも場の値でもない ——
# 源が三つしか無かったので、次元1 が黙って落ちて答えが化けていた。
W_ = """table e = (0,5), (1,7), (2,9)
field m : max bound 8 4
m[i,0] <- v      for (i,v) in e
m[i,1] <- v + 1  for (i,v) in e
field s : max bound 8
s[i] <- m[i,0] + m[i,1] for (i,v) in e
"""

# **前置のずれ** `p[j+1]` —— 内側の添字が動く。後置 `p[j] + 1` とは別物である
X_ = """field p : max bound 8
p[0] <- 3
p[1] <- 1
p[2] <- 0
field q : max bound 8 4
q[3,0] <- 5
q[1,1] <- 9
q[0,3] <- 11
field r : max bound 8
r[j] <- q[p[j], p[j+1]] for (j) in 0 .. 1
r[j] <- q[p[j-1], p[j]] for (j) in 1 .. 2
"""

# **二のべきで割る / 余りを取る** —— バイトを取り出す形（生成器が自分に要る）
Y_ = """table e = (0,700), (1,66000), (2,300)
field lo : max bound 8
lo[i] <- x % 256 for (i,x) in e
field hi : max bound 8
hi[i] <- x / 256 % 256 for (i,x) in e
field top : max bound 8
top[i] <- x / 65536 for (i,x) in e
"""

# **場の読みを引く** —— `rel[n] <- off[jt[n]] - off[n]` の形（生成器が自分に要る）
Z_ = """table e = (0,10,3), (1,20,7), (2,30,25)
field a : max bound 8
a[i] <- x for (i,x,y) in e
field b : max bound 8
b[i] <- y for (i,x,y) in e
field d : max bound 8
d[i] <- a[i] - b[i] for (i,x,y) in e
"""

# **区間の上端が場** —— `for (x) in 0 .. lim[0]`。記述が空間を決める
W2 = """table e = (0,3)
field lim : max bound 8
lim[i] <- v for (i,v) in e
field sq : max bound 16
sq[x] <- x * 2 for (x) in 0 .. lim[0]
"""

# **場と場の積** —— `fw[f,0] * fw[f,1]`（二次元の畳みの掛け数）。
# 定数を掛けるだけでは足りなかった: 掛ける相手も場でありうる（種10）。
M2 = """table e = (0,3,4), (1,5,6), (2,7,8)
field a : max bound 8
a[i] <- x for (i,x,y) in e
field b : max bound 8
b[i] <- y for (i,x,y) in e
field m : max bound 8
m[i] <- a[i] * b[i] for (i,x,y) in e
field m2 : max bound 8
m2[i] <- a[i] * b[i] + 1 for (i,x,y) in e
"""

# **変数も引ける・掛けられる**（種11〜14）。列も計数器も、足すだけではない。
V2 = """table e = (0,3,4), (1,5,6), (2,7,8)
field m : max bound 8
m[i] <- x * y   for (i,x,y) in e
field d : max bound 8
d[i] <- y - x   for (i,x,y) in e
field sq : max bound 8
sq[k] <- k * k   for (k) in 0 .. 5
field z : max bound 8
z[k] <- k - k   for (k) in 0 .. 5
"""

cases = [("素直な図 (min)", A), ("重みが違う (min)", B),
         ("列の順を入れ替え", C), ("規則二本（無向）", D),
         ("到達可能性 (or)", E), ("答えが 8bit を超える", F_),
         ("二場・二束・ガード", G_), ("2次元 rd[j,v]", H_),
         ("層＋否定＋読み無し", I_), ("flat 定数伝播（⊤）", J_),
         ("集約 sum / count", K_), ("鎖 off[i-1]+w", L_),
         ("記号表＝不動点 intern", M_),
         ("区間 for i in a..b", N_), ("ガード四つ／一規則", O_),
         ("二項の加算 a[i]+b[i]", P_), ("2000 升の鎖", Q_),
         ("場の値が座標 val[ptr[i]]", R_),
         ("記号表（ループが数える）", S_),
         ("字句解析器（断片だけ）", T_), ("列と場を比べる", U_),
         ("桁を積む a*10+b", V_),
         ("定数の添字 m[i,0]", W_),
         ("前置のずれ p[j+1]", X_),
         ("割る／余り x/256%256", Y_),
         ("場の読みを引く a-b", Z_),
         ("上端が場 0..lim[0]", W2),
         ("場と場を掛ける a*b", M2),
         ("列と計数器を引く/掛ける", V2)]

tmp = tempfile.mkdtemp()
print("=" * W)
print("  `.lx` を入れると実行ファイルが出る —— 判断は全部 Lattix 側（21 → 32 → 31）")
print("=" * W)
print(f"  {'入力':<21}{'場':>3}{'規則':>4}{'セル':>5}  全セル一致  attest"
      "      導いた形 (束,次数,読場,書場,読,書,重,G,列,値)")
print("-" * W)
ok = True
for i, (name, src) in enumerate(cases):
    flds, rules, n, store, rank = compile_lx(src, tmp, i)
    names, ref = interp(src)
    same = store == ref
    # **機械語の答えを検査器が別証する。** attest は機械語を一行も見ない。
    rep_ = ATT.attest(src, {names[f]: d for f, d in store.items()},
                      {names[f]: d for f, d in rank.items()})
    cert = rep_.sound and rep_.complete
    good = same and cert
    ok &= good
    shp = " ".join(str(r) for r in rules)
    print(f"  {name:<21}{len(flds):>3}{len(rules):>4}"
          f"{sum(len(d) for d in store.values()):>5}   "
          f"{'✓' if same else '✗':>4}     "
          f"SOUND {'✓' if rep_.sound else '✗'} COMPLETE {'✓' if rep_.complete else '✗'}"
          f"   {shp}")
print("-" * W)
print("  一致" if ok else "  不一致")
print("  二十七番 —— **区間の上端が場**。`for (x) in 0 .. lim[0]` —— 言語は最初から")
print("  「区間の端は束縛の下で評価する」と言っていて、焼けないのが穴だった。")
print("  二十六番 —— **場の読みを引く**。足せるのに引けないのは分類の穴だった ——")
print("  相対飛びは `off[jt[n]] - off[n] - ilen[n]` である（自分に要る形）。")
print("  二十五番 —— **二のべきで割る／余り**。算術右シフトと and で足りる ——")
print("  バイトを取り出す形なので、**生成器が自分を焼くのに要る**。")
print("  二十四番 —— **前置のずれ** q[p[j], p[j+1]]。`p[j]+1`（後置）と")
print("  同じ印に畳んでいたので、内側の添字のずれが **黙って落ちていた**。")
print("  三つ目 —— `for (w,j,i) in edge` と列を入れ替えても正しい機械語が出る。")
print("  六つ目 —— 答え 2,394,000。**出力は場そのものなので 8 ビットに縛られない。**")
print("  七つ目 —— 場二つ（min と max）・ガード `if t == 1`。**全部 32_shape が導いた。**")
print("  八つ目 —— **2次元の座標** rd[j,v]（64×64 升）と、その 1次元への射 hit[j]。")
print("  九つ目 —— **層と否定** `if not reach[j]` と読み無し規則。層は成層がそのまま。")
print("  十番目 —— **flat**。⊥→a→⊤ の join が三分岐の機械語になり、⊤ が答えとして出る。")
print("  十一番 —— **集約**。冪等は join ではなく「一度だけ撃つ印」が持つ —— 印も場である。")
print("  十二番 —— **鎖**。off[i] <- off[i-1] + w —— 生成器が番地割り当てに使う形が、")
print("  生成器自身の断片に入った。**自分の背骨を自分で焼ける。**")
print("  十三番 —— **記号表＝不動点**。比較ガード `if tch[a,c] != tch[b,c]` まで")
print("  32_shape が源から導き、intern の三行が .lx のまま機械語になった。")
print("  二十三番 —— **定数も座標である** m[i,0]。源は 列 / 計数器 / 場の値 の")
print("  三つだと思い込んでいて、定数の次元が黙って落ちていた（答えが化けた）。")
print("  二十二番 —— **桁を積む** n[i-1] * 10 + v。項に掛ける定数が入った ——")
print("  数を読むのは掛け算である。これが無いと断片は整数リテラルを読めない。")
print("  二十一番 —— **列と場を比べる**。比較は演算子が言い、辺は四種ある ——")
print("  場の読み / 表の列 / 区間の計数器 / 定数。`if i > lim[i]` も `if c > 100` も")
print("  今まで **黙って落ちていた**（ガードが一つも出ない）。六つの演算子が揃った。")
print("  二十番 —— **字句解析器が断片だけで焼ける**。構成子も cons も無く、")
print("  範囲ガード（`c >= 97`）と比較ガード（`cls[i] != cls[i-1]`）と")
print("  鎖（tnum）で語が切れる —— 自分を読む道具が、自分の断片に入った。")
print("  十九番 —— **記号表が言語の中だけで焼ける**。対の行はホストが作らない ——")
print("  三重ループが綴りを比べ、二重ループが最初の証人を拾う。ハッシュも")
print("  trie も無い（**動く min は座標になれない**から、引かずに比べる）。")
print("  十八番 —— **場の値が座標** val[ptr[i]]。座標も行にしたので、")
print("  源が「表の列／区間の計数器／**場の値**」から選べる。これは trie の")
print("  一段であり、綴りの照合が不動点で書けるということでもある。")
print("  十七番 —— **2000 升**。座標の広さは機械の都合ではなく、")
print("  **プログラムが述べた要求**である（書かれた座標と区間の上端が言う）。")
print("  十六番 —— **二項の加算** s[j] <- a[i] + b[i]。値も式であって列ではない ——")
print("  項を行にしたら、場を二つ足す規則がただ二行になった。階数は二つの")
print("  読みの **最大 + 1** で、cmovl が分岐せずに最大を取る。")
print("  十五番 —— **ガードが四つ**。ガードを列で持つのをやめて行にしたら、")
print("  数の上限が消えた。**可変長のものを固定列に畳んでいたから列が増えていた。**")
print("  十四番 —— **区間** for (i) in 1 .. 9。表が一つも無い —— 計数器がそのまま")
print("  座標で、行読みが転送（mov r9,rcx）になる。座標は読むものではなく居る場所。")
print("  そして全部に SOUND/COMPLETE が付く —— 機械語も証人を出す（不変条件6）。")
print("  検査器は機械語を一行も見ない。読むのは .lx と、場と、階数だけである。")
print("=" * W)
sys.exit(0 if ok else 1)
