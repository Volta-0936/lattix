#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**広い焼き手を二段で作る。** —— 面だけを広げた中継ぎ。

一枚の本（前段 + run.lx）は 52 万バイトあって、既定の面（源 262,144 / 像
524,288）に入らない。**bound の付け替えは規則を増やさない**ので、
`HEAD` の源に広さだけ当てた中継ぎを一枚置けば、いまの焼き手で焼ける:

    lattix → _bigbuf（rcap だけ広い）→ _wide（面が全部広い）

使い方:  RCAP=983040 TOTAL=1048576 CHARS=589824 OUT=/tmp python3 work/mkwide.py

像の大きさは焼き手自身の `rcap + 65536` までである（`pcap` の見張り）ので、
TOTAL を上げるときは RCAP も一緒に上げる。
"""
import os, re, subprocess, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RCAP=int(os.environ.get("RCAP",589824)); TOTAL=int(os.environ.get("TOTAL",655360)); CHARS=int(os.environ.get("CHARS",589824))
OUT=os.environ.get('OUT', '/tmp')
src=open(ROOT+'/lattix.lx',encoding='utf-8').read()

def bake(exe, text, out):
    r=subprocess.run([exe], input=text.encode(), capture_output=True)
    if r.returncode or r.stdout[:4]!=b'\x7fELF':
        print('焼けなかった', exe, r.returncode, r.stderr[:200]); sys.exit(1)
    open(out,'wb').write(r.stdout)
    os.chmod(out, 0o755)
    print('  %-10s %d バイト' % (out.split('/')[-1], len(r.stdout)))

# 一段目: rcap だけ広げる
s1=src.replace('rcap[0] <- 524288', 'rcap[0] <- %d'%RCAP)
assert s1!=src
bake(ROOT+'/lattix', s1, OUT+'/_bigbuf')

# 二段目: 面を全部広げる
s2=src
# **一度に写す。** 順に置換すると 1024→4096→16384 と二度当たる。
# そして `bound 4096` が行末のときに当たらなかった（`'bound 4096 '` と
# 末尾の空白で書いていた）—— 一つだけ狭いまま残り、本が入らなかった。
MAP={262144:CHARS, 1024:4096, 2048:8192, 4096:16384, 8192:131072,
     65536:262144, 512:4096, 128:1024, 524288:TOTAL}
def widen(m):
    return 'bound ' + ' '.join(str(MAP.get(int(x), int(x))) for x in m.group(1).split())
s2=re.sub(r'bound ([0-9]+(?: [0-9]+)*)', widen, s2)
s2=s2.replace('capf[0] <- 1024','capf[0] <- 4096')
s2=s2.replace('capr[0] <- 4096','capr[0] <- 16384')
s2=s2.replace('capw[0] <- 8192','capw[0] <- 131072')
s2=s2.replace('caps[0] <- 4096','caps[0] <- 16384')
s2=s2.replace('capi[0] <- 262144','capi[0] <- 524288')
s2=s2.replace('total[0] <- 524288','total[0] <- %d'%TOTAL)
s2=s2.replace('rcap[0] <- 524288','rcap[0] <- %d'%RCAP)
s2=re.sub(r'(?m)^out\[[0-9]+\] <- 0', 'out[%d] <- 0'%(TOTAL-1), s2)
s2=re.sub(r'(?m)^out\[524287\] <- 0', 'out[%d] <- 0'%(TOTAL-1), s2)
open(OUT+'/_wide.lx','w',encoding='utf-8').write(s2)
bake(OUT+'/_bigbuf', s2, OUT+'/_wide')
