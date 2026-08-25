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
        self.top_witness = []   # 影の店で証人が出た ⊤: (f, key, 二つの確定値)
        self.scope = None       # None = 大域。集合なら「そのセルについての主張」
    @property
    def sound(self):
        """(B) 有基性: 主張された値はすべて正当に導出できる  ⟹  S ⊑ lfp
        つまり『書いてあることはすべて真』。途中で打ち切った答えでも成り立つ。"""
        return not (self.grounded or self.extra)
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


def shadow(prog, sh, S, pre, prerank):
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

    返すのは (S₂, R₂, 寄与)。寄与の階数は平坦な読みだけを見る。"""
    FL = {f for f, l in prog.fields.items() if l.name in ('flat', 'fourv')}
    S2 = {f: (dict(pre.get(f, {})) if f in FL else dict(S.get(f, {})))
          for f in prog.fields}
    R2 = {f: dict(prerank.get(f, {})) for f in prog.fields}
    contrib = {}
    for r in prog.rules:
        reads = (_frefs(r.value) + [x for g in r.guards for x in _frefs(g)]
                 + [x for k in r.keys for x in _frefs(k)])
        for env in L.bindings(r, prog, None, S2):
            try:
                if not all(L._truthy(L.ev(g, env, S2, sh)) for g in r.guards):
                    continue
                v = L.ev(r.value, env, S2, sh)
                key = tuple(L.ev(x, env, S2, sh) for x in r.keys)
            except Exception:
                continue
            if v is None or isinstance(v, L._Top): continue
            if any(x is None or isinstance(x, L._Top) for x in key): continue
            if sh[r.target].name == 'fourv' and isinstance(v, bool):
                v = L.FTRUE if v else L.FFALSE
            mr = 0
            for f, ix in reads:
                if f not in FL: continue
                try: kk = tuple(L.ev(x, env, S2, sh) for x in ix)
                except Exception: continue
                mr = max(mr, R2[f].get(kk, 0))
            contrib.setdefault((r.target, key), []).append((v, mr))
    # 影の有基性: どの影の値も、*より小さい影の階数* の影の値から導ける
    for f in FL:
        lat = sh[f]
        for key, a in S2[f].items():
            k = R2[f].get(key, 0)
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
            for env in L.bindings(r, prog, None, S):
                try: writable.add((r.target, tuple(L.ev(x, env, S, sh) for x in r.keys)))
                except Exception: pass

    # 寄与は **層をまたいで集める**。場が複数の層で書かれるとき、
    # 層ごとに有基性を見ると「この層では支えが無い」だけで棄却してしまう。
    # 正当化はどの規則から来てもよい（`brk` が層0と層1の両方で書かれて露見した）。
    all_contrib, all_total, all_here = {}, {}, set()
    _sh = [None]                 # 影の店は ⊤ が出たときだけ作る（遅延）
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
            for env in L.bindings(r, prog, None, S):
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
                # この寄与が読んだ同層セルの最大階数 / 祖先閉性
                mr = 0
                for f, ix in reads_of:
                    try: kk = tuple(L.ev(x, env, S, sh) for x in ix)
                    except Exception: continue
                    if f in here: mr = max(mr, R[f].get(kk, 0))
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
        for f in here:
            lat = sh[f]
            for key, claimed in S[f].items():
                if lat.name in ACCUM:
                    if claimed > total.get((f, key), 0):
                        rep.grounded.append((f, key, claimed, total.get((f, key), 0)))
                    elif claimed < total.get((f, key), 0) and \
                         (scope is None or (f, key) in scope):
                        rep.stability.append((f, key, total.get((f, key), 0), claimed))
                    continue
                if claimed == lat.bot: continue
                if isinstance(claimed, L._Top) and lat.name in ('flat', 'fourv'):
                    # **⊤ は二つの寄与で支えられる。**
                    # 階数の証明書は「より小さい階数のセルから導ける」を要求するが、
                    # ⊤ はしばしば **そのセル自身の過去の値** を通って生じる
                    # （ループを回った定数伝播がまさにそれ）。束の高さが 2 なので
                    # 循環で ⊤ を捏造することはできない —— 相異なる二つの
                    # *確定値* が要り、その各々は自分の階数で支えられている。
                    # だから頂点だけは「値の段」で整礎性を見る。
                    vs = {v for v, _mr in contrib.get((f, key), ())
                          if v != lat.bot and not isinstance(v, L._Top)}
                    tops = [mr for v, mr in contrib.get((f, key), ())
                            if isinstance(v, L._Top)]
                    if len(vs) >= 2 or (tops and min(tops) < R[f].get(key, 0)):
                        continue
                    if vs and tops and pre is not None:
                        # **影に訊く。** 最終の答えでは片方の確定値が ⊤ に
                        # 吸収されているが、⊤ になる前の店には残っている。
                        if _sh[0] is None:
                            _sh[0] = shadow(prog, sh, S, pre, prerank or {})
                        _S2, _R2, c2 = _sh[0]
                        if c2 is not None:
                            w = {v for v, _ in c2.get((f, key), ())}
                            if len(w) >= 2:
                                rep.top_witness.append((f, key, sorted(w, key=repr)[:2]))
                                continue
                    if vs and tops:
                        # **閉路で押し上げられた ⊤。**
                        # 定数伝播のループがこれである: 最初 0 が入り、一周して
                        # 1 が戻り、⊤ になる。答えは最小不動点で正しいが、
                        # *最終の答えの中に* well-founded な証人が残っていない ——
                        # 二つ目の確定値（1）は ⊤ に吸収されて消えている。
                        # 階数の証明書は帰納の半分であって、これは余帰納の側である
                        # （上界 `U` の話。GUIDE の穴を読むこと）。
                        # 破れではないので violation にはしないが、**黙らない**。
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
                if not lat.leq(claimed, acc):
                    rep.grounded.append((f, key, claimed, acc))
        # 集約で申告漏れ（寄与はあるのに答えに無い）= 完全性の破れ
        for (f, key), tot in total.items():
            if key not in S[f] and tot and (scope is None or (f, key) in scope):
                rep.stability.append((f, key, tot, "missing"))

    return rep


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
    else:
        print("REJECTED")
        for v in rep.stability[:5]: print("  not stable  :", v)
        for v in rep.grounded[:5]:  print("  not grounded:", v)
        for v in rep.extra[:5]:     print("  extra       :", v)
    sys.exit(0 if rep.ok else 1)
