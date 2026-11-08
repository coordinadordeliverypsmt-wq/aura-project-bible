import ast,sys,os,collections
R=os.getcwd()
WS=R+'/walking-skeleton'; CP=R+'/entorno/control-plane'
def resolve(mod,roots):
    for r in roots:
        p=os.path.join(r,*mod.split('.'))
        if os.path.isfile(p+'.py'): return p+'.py'
        if os.path.isfile(p+'/__init__.py'): return p+'/__init__.py'
    return None
def imports(path,roots,pkgbase):
    t=ast.parse(open(path,encoding='utf8').read())
    out=set()
    # package of this file
    rel=os.path.relpath(path,roots[0]).replace('/','.')[:-3]
    parts=rel.split('.')
    pkg=parts[:-1] if parts[-1]!='__init__' else parts[:-1]
    for n in ast.walk(t):
        if isinstance(n,ast.Import):
            for a in n.names: out.add(a.name)
        elif isinstance(n,ast.ImportFrom):
            if n.level:
                base=pkg[:len(pkg)-(n.level-1)]
                m='.'.join(base+([n.module] if n.module else []))
            else: m=n.module or ''
            out.add(m)
            for a in n.names: out.add(m+'.'+a.name)
    res=set()
    for m in out:
        # include all parent packages too
        ps=m.split('.')
        for i in range(1,len(ps)+1):
            f=resolve('.'.join(ps[:i]),roots)
            if f and (i==len(ps) or True): res.add(f)
    return res
def closure(entries,roots):
    seen=set(); st=list(entries)
    while st:
        f=st.pop()
        if f in seen or f is None: continue
        seen.add(f)
        st+=list(imports(f,roots,None))
    return seen
procs={
 'receptor+cm2 (python -m aura_skeleton)':([WS+'/aura_skeleton/__main__.py',WS+'/aura_skeleton/__init__.py'],[WS]),
 'despertador (despertador.py)':([CP+'/despertador.py'],[CP]),
}
st={}
for l in open(sys.argv[1]):
    st[l[3:].strip().split(' -> ')[-1]]=l[:2]
allc={}
for name,(e,roots) in procs.items():
    c=closure(e,roots)
    print('##',name,'closure size',len(c))
    for f in sorted(c):
        r=os.path.relpath(f,R)
        s=st.get(r)
        if s: print(s,r); allc.setdefault(r,[]).append(name.split()[0])
open(sys.argv[2],'w').write('\n'.join(f'{k}\t{",".join(v)}' for k,v in sorted(allc.items())))
