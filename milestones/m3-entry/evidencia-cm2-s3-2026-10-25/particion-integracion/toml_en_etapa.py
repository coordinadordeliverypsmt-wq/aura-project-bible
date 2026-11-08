import tomllib,os,sys,glob
T=os.environ['T']; R=os.getcwd()
rule={l.split('\t')[0]:l.split('\t')[1] for l in open(T+'/asignacion.tsv')}
def ap(tp_live,D):
    base=(D+'/walking-skeleton') if '/walking-skeleton/' in tp_live else D+'/entorno/control-plane'
    d=tomllib.load(open(tp_live,'rb')); bad=[]
    for m in d.get('mutante',[]):
        f=m.get('fichero'); b=m.get('buscar')
        if not f or b is None: continue
        cands=[os.path.normpath(c) for c in (base+'/'+f,D+'/entorno/control-plane/'+f,D+'/walking-skeleton/'+f)]
        p=next((c for c in cands if os.path.isfile(c)),None)
        if not p: bad.append(m.get('id')+':ausente'); continue
        if open(p,encoding='utf8',errors='replace').read().count(b)!=1: bad.append(m.get('id'))
    return bad
rows=[]
for tp,c in rule.items():
    if not tp.endswith('.toml') or '/mutaciones/' not in tp or c=='X': continue
    live=R+'/'+tp
    res=[]
    for k in range(1,8): res.append(len(ap(live,T+'/arbol-%d'%k)))
    first=next((k for k in range(1,8) if res[k-1]==res[6]),7)
    print('%-70s asig=%s aplicabilidad_por_etapa(no aplican)=%s primera_etapa_equiv_a_7=%d'%(tp,c,res,first))
