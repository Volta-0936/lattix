#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lattix — 答えの検査器。コンパイラを信頼しない。

コンパイラは信頼するしかないが検証できない翻訳機械である。
Thompson (1984) の trusting trust、そして GCC/LLVM の誤コンパイルは実在する。
CompCert は「コンパイラを一度証明する」で殴った。Coq とその証明を信じる必要がある。

Lattix は別の道が取れる。**プログラムが仕様そのものだから。**

  Lattix のプログラムは「単調写像」の宣言であり、答えは定義により
  その最小不動点である。最小不動点であることは *局所的に検査できる*。

  (A) 安定性  : どの規則実例の寄与も、答えにすでに吸収されている
                  → 答えは前不動点。ゆえに lfp ⊑ S
  (B) 有基性  : どのセルの値も、*より小さい階数* のセルだけから導出できる
                  → 答えは ⊥ から有限回で到達可能。ゆえに S ⊑ lfp

  (A) ∧ (B)  ⟹  S = lfp

どちらも **規則実例を1回なめるだけ** で済む。不動点計算は要らない。
つまり検査は計算より安い（certifying algorithm; Mehlhorn）。

C/Rust ではこれができない。あちらの「答え」は任意の状態であって、
再計算より安く正しさを確かめる一般的方法が無い。

この検査器は生成された C を一度も見ない。読むのは
  * .lx のソース（仕様）
  * 出てきた答えと階数
だけである。コンパイラがどれだけ壊れていても、答えが違えば落ちる。
"""
from __future__ import annotations
import os, sys, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lattix as L

# 観測値のまま扱うための束の影（observe を恒等にした版）
OBS_BOT = {'min': float('inf'), 'max': float('-inf'), 'set': frozenset(),
           'or': False, 'and': True, 'flat': None, 'sum': 0, 'count': 0,
           'fourv': None}      # Belnap の ⊥（不明）。四値は元から束なので影は本物に委ねる
ACCUM = ('sum', 'count')          # 寄与元付き集約: 直接和で検査する
IDEM = ('min', 'max', 'set', 'or', 'and', 'flat', 'fourv')


class _ObsProg:
    """区間の端も観測値の上で読む。`L.bindings` は端を `prog.fields`（本物の束）で観測するので、
    観測値の店（sum / count は整数）を渡すと本物の observe が袋を待って落ちていた ——
    `(s[2]) .. 5` の下端（13i の試験で出た。上端 `.. s[0]` でも同じ）。場の束だけを影に差し替える。"""
    def __init__(self, prog, sh): self._p, self.fields = prog, sh
    def __getattr__(self, k): return getattr(self._p, k)


class Shim:
    """観測値の上で動く束。ev() に渡すためだけのもの。"""
    def __init__(self, lat):
        self.name = lat.name
        self.bot = OBS_BOT[lat.name]
        self._geq = lat._geq
        self.sense = lat.sense
        self._lat = lat
    def observe(self, v): return v
    def geq(self, a, c):
        if self._geq is None: return False
        try: return bool(self._geq(a, c))
        except TypeError: return False
    def join(self, a, b):
        n = self.name
        if n == 'fourv':
            # Belnap 四値は知識の順序の束そのもの。⊥ ⊑ T,F ⊑ ⊤。
            # ここだけ本物の束に委ねる —— 影を作る意味が無いから。
            return self._lat.join(a, b)
        if n == 'min': return min(a, b)
        if n == 'max': return max(a, b)
        if n == 'set': return a | b
        if n == 'or':  return bool(a) or bool(b)
        if n == 'and': return bool(a) and bool(b)
        if n == 'flat':
            if a is None: return b
            if b is None: return a
            return a if a == b else L.TOP
        return a + b
    def leq(self, a, b):
        """a ⊑ b ?"""
        return self.join(a, b) == b


class Report:
    def __init__(self):
        self.instances = 0
        self.stability = []     # violations
        self.grounded = []
        self.extra = []
        self.closure = []       # 領域検査でのみ使う: 祖先が scope の外にある
        self.cyclic_top = []    # 閉路で押し上げられた ⊤（影でも証人が出なかったもの）
        self.unproven = []      # 小さい階数から来ない寄与に支えられた集約（示せない）
        self.top_witness = []   # 影の店で証人が出た ⊤: (f, key, 二つの確定値)
        self.scope = None       # None = 大域。集合なら「そのセルについての主張」
    @property
    def sound(self):
        """(B) 有基性: 主張された値はすべて正当に導出できる  ⟹  S ⊑ lfp
        つまり『書いてあることはすべて真』。途中で打ち切った答えでも成り立つ。

        **閉路でしか支えられない ⊤（cyclic_top）は、導出を示していない。** 最終の答えだけ
        では本物（f <- f + 1 で 1 と 2 が届いた ⊤）と偽物（恒等 f <- f で 1 しか来ないのに
        ⊤ と書いたもの）を見分けられない。前はこれを「破れではない」として健全に数え、
        恒等の偽物に ATTESTED と言っていた（2026-09-19 に測って直した）。"""
        return not (self.grounded or self.extra or self.cyclic_top or self.unproven)
    @property
    def complete(self):
        """(A) 安定性: どの寄与も吸収済み  ⟹  lfp ⊑ S
        つまり『真であることはすべて書いてある』。
        scope があるときは **その集合の上でだけ** の主張である。
        成立には祖先閉性 (closure) も要る —— 祖先がまだ育つなら
        いま吸収されていることは最小不動点での吸収を意味しない。"""
        return not (self.stability or self.closure)
    @property
    def ok(self):
        return self.sound and self.complete


def shadow(prog, sh, S, pre, prerank, R=None):
    """**影の店** —— 平坦な場が ⊤ になる *前* に持っていた確定値だけの店。

    平坦束のセルは生涯にただ一つの確定値しか持てない（⊥ → a → ⊤）。
    だから「⊤ になる前の値」は曖昧さなく決まる。それだけを集めた店 S₂ は
    最小不動点への **途中経過** であり、有基性を見れば S₂ ⊑ lfp が言える。

    そして ⊤ の証人は、そこにいる ——
    **同じセルへ相異なる二つの確定値が届く。** 最終の答えでは片方が ⊤ に
    吸収されて消えているが、影には残っている。階数は帰納の半分（下から）で、
    これが余帰納の側（上から）である: 「この座標は a より上でしかありえない」。

    非平坦な場は最終の答えのまま使う。それは既に (A)(B) で lfp と証明済みなので
    公理として置ける —— 影の帰納は **平坦なセルの上だけ** で well-founded。

    返すのは (S₂, R₂, 寄与)。

    **影は層ごとに組む**（2026-09-19 に直した）。前は下の層の平坦な場まで ⊤ の前の値に
    戻していた —— 下の層は、上の層が走るときには確定している。`if not z[q]` は z の ⊤ を
    見て立たないのに、影では z の前の値 0 を見て立ち、存在しない寄与 5 を証人にした
    （x = 7 の答えを x = ⊤ と偽った証明書が通った）。いまは、規則 r の層で書かれる平坦な
    場だけを ⊤ の前の値（と、⊤ にならなかった確定値）に戻し、それ以外は最終の答えを読む。
    寄与の階数は同じ層の読み（平坦な場は影の階数、それ以外は最終の階数）を見る。"""
    FL = {f for f, l in prog.fields.items() if l.name in ('flat', 'fourv')}
    R = R or {}
    S2 = {f: {} for f in FL}
    R2 = {f: {} for f in FL}
    contrib = {}
    AX = _axioms(prog)                    # 種だけの場は下の層と同じ（_axioms）
    for si, rules in enumerate(prog.strata):
        if not rules: continue
        here = {r.target for r in rules} - AX
        St, Rt = {}, {}
        for f in prog.fields:
            if f in FL and f in here:
                d = {k: v for k, v in S.get(f, {}).items()
                     if v is not None and not isinstance(v, L._Top)}
                rk = {k: R.get(f, {}).get(k, 0) for k in d}
                d.update(pre.get(f, {})); rk.update(prerank.get(f, {}))
                St[f], Rt[f] = d, rk
                S2[f].update(d); R2[f].update(rk)
            else:
                St[f], Rt[f] = dict(S.get(f, {})), dict(R.get(f, {}))
        for r in rules:
            reads = (_frefs(r.value) + [x for g in r.guards for x in _frefs(g)]
                     + [x for k in r.keys for x in _frefs(k)])
            for env in L.bindings(r, _ObsProg(prog, sh), None, St):
                try:
                    if not all(L._truthy(L.ev(g, env, St, sh)) for g in r.guards):
                        continue
                    v = L.ev(r.value, env, St, sh)
                    key = tuple(L.ev(x, env, St, sh) for x in r.keys)
                except Exception:
                    continue
                if v is None or isinstance(v, L._Top): continue
                if any(x is None or isinstance(x, L._Top) for x in key): continue
                if sh[r.target].name == 'fourv' and isinstance(v, bool):
                    v = L.FTRUE if v else L.FFALSE
                mr = 0
                for f, ix in reads:
                    if f not in here: continue          # 下の層は確定している
                    try: kk = tuple(L.ev(x, env, St, sh) for x in ix)
                    except Exception: continue
                    mr = max(mr, Rt[f].get(kk, 0))
                contrib.setdefault((r.target, key), []).append((v, mr))
    # 影の有基性: どの影の値（⊤ になる前の値）も、*より小さい影の階数* の影の値から導ける
    # （⊤ にならなかった確定値は最終の答えの (B) で示してある）
    for f in FL:
        lat = sh[f]
        for key, a in (pre.get(f) or {}).items():
            k = (prerank.get(f) or {}).get(key, 0)
            if k <= 0: return None, None, None
            acc = lat.bot
            for v, mr in contrib.get((f, key), ()):
                if mr < k: acc = lat.join(acc, v)
            if not lat.leq(a, acc): return None, None, None
    return S2, R2, contrib


def attest(src, store, rank, verbose=False, scope=None, pre=None, prerank=None):
    """store/rank は観測値。生成物がどう作られたかは一切参照しない。

    scope=None なら大域の検査（従来どおり）。
    scope に **セルの集合** を渡すと *領域ごとの完全性* を検査する:

      (0) 祖先閉性 : scope 内のセルへの寄与が読むセルは、すべて scope 内にある
      (A) 安定性   : scope 内のセルについて、どの寄与も吸収済み
      (B) 有基性   : 主張された値はすべて（大域で）正当に導出できる

      (0) ∧ (A)  ⟹  lfp|scope ⊑ S|scope     —— 外がどれだけ育っても scope は動かない
      (B)        ⟹  S ⊑ lfp
      三つ合わせて **S|scope = lfp|scope**。途中で止めた実行でも言える。

    ここが v1.6 で実測しか無かったところである。証明にした。"""
    prog = L.parse(src); L.check(prog); L.stratify(prog); L.io_rounds(prog); L.certify(prog)
    sh = {f: Shim(lat) for f, lat in prog.fields.items()}
    rep = Report(); rep.scope = scope

    S = {f: dict(store.get(f, {})) for f in prog.fields}
    R = {f: dict(rank.get(f, {})) for f in prog.fields}

    # 書かれうるセル（＝どれかの規則実例の書き先）。ここに無いセルは永遠に ⊥ なので
    # 祖先閉性の対象外である。scope 検査のときだけ要る。
    writable = None
    if scope is not None:
        writable = set()
        for r in prog.rules:
            for env in L.bindings(r, _ObsProg(prog, sh), None, S):
                try: writable.add((r.target, tuple(L.ev(x, env, S, sh) for x in r.keys)))
                except Exception: pass

    # 寄与は **層をまたいで集める**。場が複数の層で書かれるとき、
    # 層ごとに有基性を見ると「この層では支えが無い」だけで棄却してしまう。
    # 正当化はどの規則から来てもよい（`brk` が層0と層1の両方で書かれて露見した）。
    all_contrib, all_total, all_here = {}, {}, set()
    _sh = [None]                 # 影の店は ⊤ が出たときだけ作る（遅延）
    # 階数を比べる読みは **書き先と同じ強連結成分の場** の読みだけ（_sccs）
    SCC = _sccs(prog)
    for si, rules in enumerate(prog.strata):
        if not rules: continue
        here = {r.target for r in rules}
        all_here |= here
        # --- 収集: 各セルへの寄与と、その寄与が読んだ同層セルの階数 ---
        contrib = {}          # (field,key) -> list of (value, maxreadrank)
        total = {}            # 集約用
        for r in rules:
            lat = sh[r.target]
            reads_of = (_frefs(r.value) + [x for g in r.guards for x in _frefs(g)]
                        + [x for k in r.keys for x in _frefs(k)])
            for env in L.bindings(r, _ObsProg(prog, sh), None, S):
                rep.instances += 1
                # ── 祖先閉性はガードより先に見る ──────────────────────
                # いま偽のガードは、祖先が育てば真になりうる。**まだ火を噴いて
                # いない規則実例こそ、scope の外に依存が漏れている証拠である。**
                # ここをガードの後ろに置いていたため、「静かなセル」を scope に
                # 入れても検査が通ってしまった（demo/certified.py が 20 回に 2 回
                # 落ちて露見。ハッシュ順の揺らぎが被害者の選び方を変えていた）。
                if scope is not None:
                    try: tk = (r.target, tuple(L.ev(x, env, S, sh) for x in r.keys))
                    except Exception: tk = None
                    if tk is not None and tk in scope:
                        for f, ix in reads_of:
                            try: kk = tuple(L.ev(x, env, S, sh) for x in ix)
                            except Exception: continue
                            if (f, kk) in writable and (f, kk) not in scope:
                                rep.closure.append((tk, (f, kk)))
                try:
                    if not all(L._truthy(L.ev(g, env, S, sh)) for g in r.guards):
                        continue
                    v = L.ev(r.value, env, S, sh)
                except Exception:
                    continue
                # 真偽値を四値へ正規化する（処理系の `_contribute` と同じ規則）。
                # ここを揃えないと、同じ寄与が別の値に見えて安定性が破れる。
                if lat.name == 'set' and isinstance(v, frozenset):
                    v = frozenset(x for x in v if x is not None)   # ⊥ は要素になれない
                    if not v: continue
                if lat.name == 'fourv' and isinstance(v, bool):
                    v = L.FTRUE if v else L.FFALSE
                if v is None and lat.name not in ('flat', 'fourv'): continue
                if lat.name in IDEM and v == lat.bot: continue
                key = tuple(L.ev(x, env, S, sh) for x in r.keys)
                # この寄与が読んだ、書き先と同じ成分のセルの最大階数
                mr = 0
                for f, ix in reads_of:
                    if SCC.get(f) != SCC.get(r.target): continue
                    try: kk = tuple(L.ev(x, env, S, sh) for x in ix)
                    except Exception: continue
                    mr = max(mr, R[f].get(kk, 0))
                contrib.setdefault((r.target, key), []).append((v, mr))
                if lat.name in ACCUM:
                    total[(r.target, key)] = total.get((r.target, key), 0) + \
                        (1 if lat.name == 'count' else v)

        # --- (A) 安定性 ---------------------------------------------------
        for (f, key), cs in contrib.items():
            lat = sh[f]
            if lat.name in ACCUM: continue        # 集約は下で直接比較
            if scope is not None and (f, key) not in scope: continue
            claimed = S[f].get(key, lat.bot)
            for v, _ in cs:
                if not lat.leq(v, claimed):
                    rep.stability.append((f, key, v, claimed))
                    break

        for k, v in contrib.items(): all_contrib.setdefault(k, []).extend(v)
        for k, v in total.items(): all_total[k] = all_total.get(k, 0) + v

    if True:
        here, contrib, total = all_here, all_contrib, all_total
        # --- (B) 有基性 ---------------------------------------------------
        # 「主張された値は、より小さい階数のセルだけから *導出できる*」。
        # 等号ではなく S[c] ⊑ acc である。等号にすると、途中で止めた答え
        # （まだ緩和しきっていない距離）まで棄却してしまう。
        # 完全性 (A) と合わせれば結局 S[c] = acc になる。
        # **規則の無い場も見る。** 前は規則が書く場（here）だけを見ていた —— 規則も種も無い場に
        # 値を書いた証明書は、その升が一度も調べられずに通った（`a` に規則が無いのに a[2] = 5、
        # それを読む v[2] = 10 と書くと ATTESTED。最小不動点では a も v も ⊥。2026-09-19 に
        # 前段を共有しない二つの検査器を突き合わせて見つけた）。寄与の無い升の値は支えが無い。
        for f in prog.fields:
            lat = sh[f]
            for key, claimed in S[f].items():
                if lat.name in ACCUM:
                    if claimed > total.get((f, key), 0):
                        rep.grounded.append((f, key, claimed, total.get((f, key), 0)))
                    elif claimed < total.get((f, key), 0) and \
                         (scope is None or (f, key) in scope):
                        rep.stability.append((f, key, total.get((f, key), 0), claimed))
                    # 在る升の階数は 1 以上（集約でも。階数 0 は「一度も導かれていない」）
                    elif R[f].get(key, 0) <= 0:
                        rep.grounded.append((f, key, claimed, "rank 0 (unjustified)"))
                    # **集約の寄与にも階数の規律が要る。** `c <- 1 if c`（count）に c = 1 と書くと、
                    # その 1 が寄与を立て、寄与が 1 を作る（最小不動点は ⊥）。和の一致だけ見ていた間は
                    # ATTESTED と言った（2026-09-20、偽物を数え上げて見つけた）。小さい階数から来ない
                    # 寄与に支えられた集約は **示せない**（unproven —— SOUND に数えない）
                    elif any(mr >= R[f].get(key, 0) for _v, mr in contrib.get((f, key), ())):
                        rep.unproven.append((f, key))
                    continue
                if claimed == lat.bot: continue
                if isinstance(claimed, L._Top) and lat.name in ('flat', 'fourv'):
                    # **⊤ は二つの寄与で支えられる。**
                    # 階数の証明書は「より小さい階数のセルから導ける」を要求するが、
                    # ⊤ はしばしば **そのセル自身の過去の値** を通って生じる
                    # （ループを回った定数伝播がまさにそれ）。
                    # 前はここに「束の高さが 2 なので循環で ⊤ を捏造することはできない」と
                    # 書き、二つの確定値を階数を問わずに数えていた。**捏造できた。**
                    # **違う二つの値も、より小さい階数の読みから来ていなければならない。**
                    # 前は階数を問わなかった —— `w <- 7 if x` と `x <- w` の閉路で、x = ⊤ と w = 7 を
                    # 偽った証明書が通った（x の ⊤ を w の 7 が支え、w の 7 を「⊤ は真」が支える。
                    # 最小不動点は x = 0、w = ⊥）。flat の値からの比較・ガードは単調なので（⊥ は偽、
                    # ⊤ は真）、閉路の中に置ける —— 階数の規律を外してよい所は無い（2026-09-19）
                    kx = R[f].get(key, 0)
                    vs = {v for v, _mr in contrib.get((f, key), ())
                          if v != lat.bot and not isinstance(v, L._Top) and _mr < kx}
                    tops = [mr for v, mr in contrib.get((f, key), ())
                            if isinstance(v, L._Top)]
                    if len(vs) >= 2 or (tops and min(tops) < kx):
                        continue
                    vs_any = {v for v, _mr in contrib.get((f, key), ())
                              if v != lat.bot and not isinstance(v, L._Top)}
                    if (vs_any and tops or len(vs_any) >= 2) and pre is not None:
                        # **影に訊く。** 最終の答えでは片方の確定値が ⊤ に
                        # 吸収されているが、⊤ になる前の店には残っている。
                        if _sh[0] is None:
                            _sh[0] = shadow(prog, sh, S, pre, prerank or {}, R)
                        _S2, _R2, c2 = _sh[0]
                        if c2 is not None:
                            w = {v for v, _m in c2.get((f, key), ()) if _m < kx}
                            if len(w) >= 2:
                                rep.top_witness.append((f, key, sorted(w, key=repr)[:2]))
                                continue
                    if vs_any and tops or len(vs_any) >= 2:
                        # **閉路で押し上げられた ⊤。**
                        # 定数伝播のループがこれである: 最初 0 が入り、一周して
                        # 1 が戻り、⊤ になる。答えは最小不動点で正しいが、
                        # *最終の答えの中に* well-founded な証人が残っていない ——
                        # 二つ目の確定値（1）は ⊤ に吸収されて消えている。
                        # 階数の証明書は帰納の半分であって、これは余帰納の側である
                        # （上界 `U` の話。GUIDE の穴を読むこと）。
                        # 最終の答えだけでは本物と偽物（恒等 f <- f で ⊤ と書いたもの）を
                        # 見分けられない。**示せないので健全に数えない**（Report.sound）。
                        rep.cyclic_top.append((f, key))
                        continue
                    rep.grounded.append((f, key, claimed, "⊤ without two witnesses"))
                    continue
                k = R[f].get(key, 0)
                if k <= 0:
                    rep.grounded.append((f, key, claimed, "rank 0 (unjustified)"))
                    continue
                acc = lat.bot
                for v, mr in contrib.get((f, key), ()):
                    if mr < k:
                        acc = lat.join(acc, v)
                if not lat.leq(claimed, acc) and pre is not None:
                    # **⊤ の前の値に訊く。** `w <- 7 if x` の w は、x が ⊤ になる前の値を読んで
                    # 立った。最終の答えでは x は ⊤（階数は w より大きい）なので、w の支えが見えない。
                    # 影（同じ層の平坦な場を ⊤ の前の値に戻した店）の寄与を、同じ階数の規律で足す
                    # —— 影の値も階数で支えられているので、帰納は一つの整列の上で閉じる。
                    if _sh[0] is None:
                        _sh[0] = shadow(prog, sh, S, pre, prerank or {}, R)
                    _S2, _R2, c2 = _sh[0]
                    if c2 is not None:
                        for v, mr in c2.get((f, key), ()):
                            if mr < k:
                                acc = lat.join(acc, v)
                if not lat.leq(claimed, acc):
                    rep.grounded.append((f, key, claimed, acc))
        # 集約で申告漏れ（寄与はあるのに答えに無い）= 完全性の破れ
        for (f, key), tot in total.items():
            if key not in S[f] and tot and (scope is None or (f, key) in scope):
                rep.stability.append((f, key, tot, "missing"))

    return rep


def _axioms(prog):
    """**種だけの場** —— 書く規則がどれも `for` を持たず、場を一つも読まない（定数の升に定数を置く）場。

    焼き手の前段は `for` の無い矢印の文を種として規則の表から外し、層に数えない（`for` の無い文が
    場を読むか定数でない値を持てば、理由 8 で断る）。種の升は何にも寄りかからずに決まるので、
    読む側から見れば **下の層と同じ** —— 読みの階数に数えない。焼いた本の階数もそう数えている
    （種は 1、種を読んで立つ和も 1）。前は lattix.py の成層が種の場を読む側と同じ層に入れ、
    正直な証明書を「示せない」と言っていた（2026-09-20、撒いた本で表の上の参照と食い違って見つけた）。
    種の升そのものは、他の升と同じく (A) と (B) で確かめる。
    （いまは影の店で使う。本の検査は強連結成分で比べる —— _sccs。種だけの場はひとりで一つの成分）"""
    oks = {}
    for r in prog.rules:
        reads = (_frefs(r.value) + [x for g in r.guards for x in _frefs(g)]
                 + [x for k in r.keys for x in _frefs(k)])
        oks.setdefault(r.target, []).append(not r.sources and not reads)
    return {f for f, xs in oks.items() if all(xs)}


def _sccs(prog):
    """場の依存の **強連結成分**（場 → 成分の番号）。辺は「規則が読む場 → 規則が書く場」。

    有基性の帰納に要るのは「支えの読みが、先に示したセルである」ことだけである。先の成分の場は
    （同じ層でも）書き先に寄りかからないので、その升は階数を問わずに先に示せる —— 帰納の順は
    （成分の位相順, 階数）の辞書順でよく、階数を比べる読みは **同じ成分の場** の読みだけになる。
    前は lattix.py の層で比べていた。層は単調な読みを一つの層にまとめるので、`c <- 1 if h[i] >= 2`
    （c は count、h は同じ層の max）の正直な証明書を示せなかった —— 焼いた本は集約の階数を 1 に
    置く（印が数えるので深さを持たない）ので、同じ層の h の階数 1 が c の支えに数えられて、集約の
    階数の規律（2026-09-20）に掛かった。成分なら c は h と別で、c が自分を読むとき（`c <- 1 if c`）
    だけ規律が要る。種だけの場（_axioms）は読みを持たないので、ひとりで一つの成分になる。"""
    succ = {f: set() for f in prog.fields}
    for r in prog.rules:
        for x in (_frefs(r.value) + [x for g in r.guards for x in _frefs(g)]
                  + [x for k in r.keys for x in _frefs(k)]):
            succ.setdefault(x[0], set()).add(r.target)
            succ.setdefault(r.target, set())
    # Tarjan（反復）
    index, low, onst, comp = {}, {}, set(), {}
    st, n, c = [], 0, 0
    for root in sorted(succ):
        if root in index: continue
        work = [(root, iter(sorted(succ[root])))]
        index[root] = low[root] = n; n += 1; st.append(root); onst.add(root)
        while work:
            v, it = work[-1]
            w = next(it, None)
            if w is not None:
                if w not in index:
                    index[w] = low[w] = n; n += 1; st.append(w); onst.add(w)
                    work.append((w, iter(sorted(succ[w]))))
                elif w in onst:
                    low[v] = min(low[v], index[w])
                continue
            work.pop()
            if work: low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                while True:
                    w = st.pop(); onst.discard(w); comp[w] = c
                    if w == v: break
                c += 1
    return comp


def _frefs(e, out=None):
    out = [] if out is None else out
    k = e[0]
    if k == 'fref':
        out.append((e[1], e[2]))
        for x in e[2]: _frefs(x, out)
    elif k in ('bin', 'cmp', 'fn'):
        _frefs(e[2], out); _frefs(e[3], out)
    elif k == 'geq':
        _frefs(e[1], out); _frefs(e[2], out)
    elif k in ('not', 'bnot'):
        _frefs(e[1], out)
    elif k == 'set':
        for x in e[1]: _frefs(x, out)
    return out


# --------------------------------------------------------------------------
if __name__ == '__main__':
    import native as N, io
    path = sys.argv[1]
    src = open(path, encoding='utf-8').read()
    info = N.compile_source(src)
    out, meta, _ = N.run_native(info['exe'])
    store, rank = N.to_store(info['prog'], info['plan'], out, want_rank=True)
    rep = attest(src, store, rank)
    solver_joins = int(meta.get('JOINS', 0))
    print(f"instances examined : {rep.instances}   (solver joins: {solver_joins})")
    if rep.ok:
        print("ATTESTED: SOUND ✓  COMPLETE ✓   = the least fixpoint of the program.")
        print("          the C compiler was not trusted, examined, or executed by this checker.")
    elif rep.sound:
        print("PARTIAL : SOUND ✓  COMPLETE ✗   every claimed fact is true, some are missing.")
    elif (rep.cyclic_top or rep.unproven) and not (rep.grounded or rep.extra or rep.stability):
        print("UNPROVEN: a flat ⊤ supported only by a cycle, or an aggregate supported by reads")
        print("          of its own stratum at an equal or higher rank — the final answer alone")
        print("          cannot tell these from forgeries.")
        for v in rep.cyclic_top[:5]: print("  unproven ⊤  :", v)
        for v in rep.unproven[:5]:   print("  unproven agg:", v)
    else:
        print("REJECTED")
        for v in rep.stability[:5]: print("  not stable  :", v)
        for v in rep.grounded[:5]:  print("  not grounded:", v)
        for v in rep.extra[:5]:     print("  extra       :", v)
    sys.exit(0 if rep.ok else 1)
