import sys,os
sys.argv=['x','/dev/null','/dev/null']
exec(open(os.path.dirname(os.path.abspath(__file__))+'/cierre.py').read().split("procs={")[0])
st={l[3:].strip().split(' -> ')[-1]:l[:2] for l in open(os.environ['T']+'/estado-uall.txt')}
def show(rel):
    c=closure([R+'/'+rel],[WS] if rel.startswith('walking') else [CP])
    print('##',rel)
    for f in sorted(c):
        r=os.path.relpath(f,R)
        if r in st: print('  ',st[r],r)
for m in sys.stdin.read().split(): show(m)
