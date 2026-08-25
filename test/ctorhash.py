#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容アドレスを **C 側でも計算できる** ことを確かめる。

「同じ内容なら同じ名前」は、処理系の実装言語に依存してはいけない主張である。
以前は SHA-256 の先頭 56 ビットだった。正準ではあったが、それを計算できるのは
SHA-256 を持つ実装だけである —— つまり **Lattix 自身には計算できなかった**。
いまは固定の乗数と法による多項式なので、`*` と `+` と `%` があれば書ける。
C からも同じ 61 ビットが出るはずだ —— **はずだ、で済ませない。**

ここが一致していることが、ハッシュ表バックエンド（構成子・疎な座標）の前提になる。
"""
import hashlib, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lattix as L

C = r"""
#include <stdio.h>
#include <stdint.h>
#include <string.h>
/* Lattix の内容アドレス —— **31ビットの法を二本**。128ビット整数が要らない。 */
#define LXM1 268435399ULL
#define LXM2 268435367ULL
#define LXK1 1000003ULL
#define LXK2 1000033ULL
static uint64_t lxfold(const char*p, size_t n, uint64_t m, uint64_t k){
  uint64_t h=0; for(size_t i=0;i<n;i++) h=(h*k+(uint64_t)(unsigned char)p[i]+1)%m;
  return h; }
static uint64_t one(const char*name, const int64_t*iv, int n, uint64_t m, uint64_t k){
  uint64_t h = lxfold(name, strlen(name), m, k);
  h = (h*k + (uint64_t)n + 1) % m;
  for(int j=0;j<n;j++){ int64_t t=iv[j]%(int64_t)m; if(t<0) t+=(int64_t)m;
    h = (h*k + 3*(uint64_t)t) % m; }
  return h; }
static uint64_t ctor_id(const char*name, const int64_t*iv, int n){
  return one(name,iv,n,LXM1,LXK1)*LXM2 + one(name,iv,n,LXM2,LXK2); }
int main(void){ int64_t a[2]={12345,-7};
  printf("%llu\n",(unsigned long long)ctor_id("node",a,2));
  int64_t b[1]={0}; printf("%llu\n",(unsigned long long)ctor_id("leaf",b,1));
  return 0; }
"""
import tempfile
d = tempfile.mkdtemp(prefix="lattix_hash_")
open(os.path.join(d, "sha.c"), "w").write(C)
subprocess.run(["gcc", "-O2", "-w", "-o", os.path.join(d, "sha"),
                os.path.join(d, "sha.c")], check=True)
out = subprocess.run([os.path.join(d, "sha")], capture_output=True, text=True).stdout.split()
want = [str(L.ctor_id("node", (12345, -7))), str(L.ctor_id("leaf", (0,)))]
print("=" * 72)
print("  内容アドレス: Python と C が同じ値を出すか")
print("=" * 72)
for a, b in zip(want, out):
    print(f"  Python {a:>20}   C {b:>20}   {'✓' if a == b else '✗'}")
print("-" * 72)
print("  一致しなければ、別マシンでの構造共有も、検査器の再計算も成り立たない。")
print("=" * 72)
sys.exit(0 if out == want else 1)
