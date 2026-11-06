import sys,os
sys.argv=['x','/dev/null','/dev/null']
exec(open(os.environ['T']+'/cierre.py').read().split("procs={")[0])
st={l[3:].strip().split(' -> ')[-1]:l[:2] for l in open(os.environ['T']+'/estado-uall.txt')}
files=[f for f in st if f.startswith('walking-skeleton/aura_skeleton/') and f.endswith('.py')]
for f in sorted(files):
    deps=[os.path.relpath(d,R) for d in imports(R+'/'+f,[WS],None) if os.path.relpath(d,R)!=f]
    dd=[d.replace('walking-skeleton/aura_skeleton/','') for d in deps if d in st]
    print(st[f],f.replace('walking-skeleton/aura_skeleton/',''),'->',' '.join(sorted(dd)))
