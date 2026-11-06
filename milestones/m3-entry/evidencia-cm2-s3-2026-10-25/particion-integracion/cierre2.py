import ast,os,sys
R=os.getcwd(); T=os.environ['T']
WS=R+'/walking-skeleton'; CP=R+'/entorno/control-plane'
st={}
for l in open(T+'/estado-uall.txt'):
    p=l[3:].rstrip('\n'); p=p.split(' -> ')[-1]; st[p]=l[:2]
def resolve(mod,roots):
    for r in roots:
        p=os.path.join(r,*mod.split('.'))
        if os.path.isfile(p+'.py'): return p+'.py'
        if os.path.isfile(p+'/__init__.py'): return p+'/__init__.py'
def walk(node,eager):
    for ch in ast.iter_child_nodes(node):
        if eager and isinstance(ch,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)): continue
        yield ch; yield from walk(ch,eager)
def deps(path,roots,rootdir,eager):
    t=ast.parse(open(path,encoding='utf8').read())
    rel=os.path.relpath(path,rootdir)[:-3].split('/'); pkg=rel[:-1]
    out=set()
    for n in walk(t,eager):
        ms=[]
        if isinstance(n,ast.Import): ms=[a.name for a in n.names]
        elif isinstance(n,ast.ImportFrom):
            if n.level: b=pkg[:len(pkg)-(n.level-1)]; m='.'.join(b+([n.module] if n.module else []))
            else: m=n.module or ''
            ms=[m]+[m+'.'+a.name for a in n.names]
        for m in ms:
            ps=m.split('.')
            for i in range(1,len(ps)+1):
                f=resolve('.'.join(ps[:i]),roots)
                if f: out.add(f)
    return out
def clos(entries,roots,rootdir,eager_entry_only=False,lazy=True):
    seen=set(); st_=[(e,True) for e in entries]
    while st_:
        f,top=st_.pop()
        if f in seen: continue
        seen.add(f)
        for d in deps(f,roots,rootdir,eager=not lazy): st_.append((d,False))
    return seen
M=WS+'/aura_skeleton/__main__.py'; A=lambda *x:[WS+'/aura_skeleton/'+y for y in x]
procs=[
 ('receptor aura-receptor-nodos.service  [python -m aura_skeleton --receptor-nodos]','WS',[M,WS+'/aura_skeleton/__init__.py']+A('adapters/receptor_nodos.py','core/nodos.py','adapters/detector_hardware.py','bus_nats.py')),
 ('cron CM2 aura-medir-cm2.sh  [python -m aura_skeleton --medir-cm2]','WS',[M,WS+'/aura_skeleton/__init__.py']+A('core/reloj_cm2.py')),
 ('cron despertador despertar-aura.sh -> despertador.py','CP',[CP+'/despertador.py']),
]
res={}
for name,w,e in procs:
    roots,rd=([WS],WS) if w=='WS' else ([CP],CP)
    eg=clos(e,roots,rd,lazy=False); lz=clos(e,roots,rd,lazy=True)
    # eager del entry point, luego lazy transitivo desde los modulos alcanzados eager: aproximacion = lazy total
    print('##',name); 
    print('   cierre completo (incl. imports perezosos):',len(lz),'ficheros | solo eager desde entry (1 nivel de profundidad no recursivo-perezoso):',len(eg))
    for f in sorted(lz):
        r=os.path.relpath(f,R)
        if r in st:
            print('   %s %s%s'%(st[r],r,'' if f in eg else '   [perezoso/transitivo]'))
            res.setdefault(r,set()).add(name.split()[0])
print('\n## UNION (ficheros sin commit que un commit incompleto rompería)')
for r,v in sorted(res.items()): print(st[r],r,'<-',','.join(sorted(v)))
# dinamico
print('\n## import dinamico (importlib/sys.path) detectado: aura_skeleton/adapters/estado_autonomo_cp.py importa por importlib el modulo `observatorio` del plano de control (entorno/control-plane/observatorio.py, MODIFICADO) via sys.path; no aparece en el AST estatico.')
