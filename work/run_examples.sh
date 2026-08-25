#!/bin/sh
ok=0; ng=0; sk=0
for f in examples/*.lx; do
  raw=$(timeout 300 python3 work/engine.py "$f" 2>&1); out=$(echo "$raw" | tail -3 | tr '\n' ' '); last=$(echo "$raw" | tail -1)
  case "$last" in
    *一致) printf "  %-22s ✓\n" "$(basename $f)"; ok=$((ok+1));;
    *NotImplement*) printf "  %-22s —  %s\n" "$(basename $f)" "$(echo "$out" | sed 's/.*NotImplementedError: //' | cut -c1-52)"; sk=$((sk+1));;
    *) printf "  %-22s ✗  %s\n" "$(basename $f)" "$(echo "$out" | cut -c1-64)"; ng=$((ng+1));;
  esac
done
echo "  ---- 一致 $ok / 未対応 $sk / 食い違い $ng"
