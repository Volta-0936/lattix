#!/bin/sh
# 走らせる物 vs 参照実装 —— 全部измерь
ok=0; ng=0
for f in work/t/*.lx; do
  out=$(timeout 180 python3 work/engine.py "$f" 2>&1 | tail -1)
  case "$out" in
    *一致) printf "  %-16s ✓\n" "$(basename $f)"; ok=$((ok+1));;
    *) printf "  %-16s ✗  %s\n" "$(basename $f)" "$(timeout 180 python3 work/engine.py "$f" 2>&1 | tail -3 | head -2 | tr '\n' ' ')"; ng=$((ng+1));;
  esac
done
echo "  ---- 一致 $ok / 食い違い $ng"
