import tomllib,os,sys,glob
T=os.environ['T']
def check(D):
    bad={}
    for tp in glob.glob(D+'/walking-skeleton/mutaciones/*.toml')+glob.glob(D+'/entorno/control-plane/mutaciones/*.toml'):
        base=D+'/walking-skeleton' if '/walking-skeleton/' in tp else D+'/entorno/control-plane'
        try: d=tomllib.load(open(tp,'rb'))
        except Exception as e: bad[tp]=['TOML?'+str(e)[:40]]; continue
        for m in d.get('mutante',[]):
            f=m.get('fichero'); b=m.get('buscar')
            if not f or b is None: continue
            cands=[os.path.normpath(base+'/'+f),os.path.normpath(D+'/entorno/control-plane/'+f),os.path.normpath(D+'/walking-skeleton/'+f)]
            p=next((c for c in cands if os.path.isfile(c)),None)
            if not p: bad.setdefault(tp,[]).append(m.get('id','?')+':fichero-ausente:'+f); continue
            n=open(p,encoding='utf8',errors='replace').read().count(b)
            if n!=1: bad.setdefault(tp,[]).append(m.get('id','?')+':%d'%n)
    return bad
for k in range(1,8):
    D=T+'/arbol-%d'%k; bad=check(D)
    print('ETAPA',k,'tomls con mutantes NO aplicables (buscar != 1 ocurrencia o fichero ausente):',len(bad))
    for t,l in sorted(bad.items()): print('   ',os.path.relpath(t,D),len(l),l[:4])
