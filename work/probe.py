"""ガードの形ごとに grd 表を出す —— **符号は読むのではなく測る。**"""
import sys,os; sys.path.insert(0,'.'); sys.path.insert(0,'work')
from mktab import tables_for
CASES = {
 "列 >= 定数":   "d[j] <- d[i] + w   for (i,j,w) in e if w >= 2",
 "列 != 定数":   "d[j] <- d[i] + w   for (i,j,w) in e if w != 2",
 "列 == 定数":   "d[j] <- d[i] + w   for (i,j,w) in e if w == 2",
 "列 < 定数":    "d[j] <- d[i] + w   for (i,j,w) in e if w < 2",
 "場 >= 定数":   "d[j] <- d[i] + w   for (i,j,w) in e if d[i] >= 1",
 "not 場":       "d[j] <- d[i] + w   for (i,j,w) in e if not g[i]",
 "場 != 場":     "d[j] <- d[i] + w   for (i,j,w) in e if d[i] != d[j]",
 "列 == 列":     "d[j] <- d[i] + w   for (i,j,w) in e if i == j",
}
HEAD = "table e = (0,1,4), (0,2,1), (2,1,2), (1,3,5)\nfield g : or bound 8\ng[0] <- true\nfield d : min bound 8\nd[0] <- 0\n"
for name, rule in CASES.items():
    p = "/tmp/dg/pr.lx"
    open(p,'w').write(HEAD + rule + "\nprint d\n")
    try:
        t = tables_for(p)
        print(f"  {name:<12} grd={t['grd']}")
    except Exception as ex:
        print(f"  {name:<12} 断られた: {str(ex)[:60]}")
