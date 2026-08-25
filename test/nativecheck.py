#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成された C の答えが、インタプリタの答えと一致するかを全例題で検証する。"""
import io, os, sys, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L, native as N

def sig(prog, store, observed):
    """Canonical signature. The native store already holds OBSERVED values
    (a sum field is an int, not a provenance map), so do not observe twice."""
    out = []
    for f in sorted(store):
        lat = prog.fields[f]
        for k in sorted(store[f], key=lambda t: tuple(str(x) for x in t)):
            v = store[f][k] if observed else lat.observe(store[f][k])
            out.append(f"{f}{k!r}={L._canon_value(v)}")
    import hashlib
    return hashlib.sha256("\n".join(out).encode()).hexdigest()[:16]

here = ROOT
W = 78
print("=" * W)
print("  NATIVE vs INTERPRETER — 同じ答えを返すか")
print("=" * W)
print(f"  {'例題':<20} {'深度':>4} {'C行数':>6} {'native ms':>10} {'interp ms':>10} "
      f"{'倍率':>7}  一致")
print("-" * W)
ok = True
for path in sorted(glob.glob(os.path.join(here, "examples", "*.lx"))):
    name = os.path.basename(path)
    src = open(path, encoding='utf-8').read()
    try:
        p = L.parse(src); L.check(p); d = L.stratify(p); L.io_rounds(p); L.certify(p)
    except L.LattixError:
        print(f"  {name:<20} {'—':>4}  (interpreter rejects: by design)")
        continue
    st, _, stats = L.run(p, out=io.StringIO())
    gold = sig(p, st, observed=False)
    try:
        info = N.compile_source(src, keep=os.path.join(here, "_gen", name))
    except N.Unsupported as e:
        print(f"  {name:<20} {d:>4}  {'—':>6}  未対応: {str(e).splitlines()[0][:38]}")
        continue
    out, meta, wall = N.run_native(info['exe'])
    nstore = N.to_store(info['prog'], info['plan'], out)
    got = sig(info['prog'], nstore, observed=True)
    same = got == gold
    ok &= same
    ims = stats['seconds'] * 1000
    nms = meta.get('NATIVE_MS', 0)
    print(f"  {name:<20} {d:>4} {info['lines']:>6} {nms:>10.4f} {ims:>10.3f} "
          f"{(ims/nms if nms else 0):>6.0f}×  {'✓' if same else '✗ ' + got + ' vs ' + gold}")
print("=" * W)
print("  すべて一致" if ok else "  不一致あり")
print("=" * W)
sys.exit(0 if ok else 1)
