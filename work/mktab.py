"""対象プログラム → 規則の表（run.lx の入力）。地上データも表にする。"""
import os,sys,tempfile,re; sys.path.insert(0,'.')
sg=open('test/selfgen.py',encoding='utf-8').read()
ns={'__name__':'notmain','__file__':os.path.abspath('test/selfgen.py')}
exec(compile(sg[:sg.index("tmp = tempfile.mkdtemp()")],'selfgen','exec'),ns)
cap={}; orig=ns['_crun']
def fake(key, s, tables, allprints=True):
    if key=='gen': cap['t']=dict(tables); raise SystemExit
    return orig(key, s, tables, allprints)
ns['_crun']=fake
import lattix as L
def tables_for(path):
    src=open(path,encoding='utf-8').read()
    try: ns['compile_lx'](src, tempfile.mkdtemp(), 777)
    except SystemExit: pass
    t=cap['t']
    p=L.parse(src); L.check(p)
    tname=list(p.tables)[0]; rows=p.tables[tname]
    dat=[(i,j,v) for i,row in enumerate(rows) for j,v in enumerate(row)]
    t['dat']=dat; t['nrow']=[(len(rows),)]
    return t
if __name__=='__main__':
    for k,v in tables_for(sys.argv[1]).items(): print(f"{k:6} {v}")
