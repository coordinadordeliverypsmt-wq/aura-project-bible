import ast,os,sys,re
D=sys.argv[1]
miss=[]
for base,pkg in ((D+'/walking-skeleton','aura_skeleton'),):
    for dp,dn,fn in os.walk(base+'/'+pkg):
        for f in fn:
            if not f.endswith('.py'): continue
            p=dp+'/'+f
            try: t=ast.parse(open(p,encoding='utf8').read())
            except SyntaxError as e: miss.append(('SYNTAX',p,str(e))); continue
            rel=os.path.relpath(p,base)[:-3].split('/')
            pk=rel[:-1]
            for n in ast.walk(t):
                mods=[]
                if isinstance(n,ast.ImportFrom):
                    if n.level: b=pk[:len(pk)-(n.level-1)]; m='.'.join(b+([n.module] if n.module else []))
                    else: m=n.module or ''
                    mods=[(m,[a.name for a in n.names])]
                elif isinstance(n,ast.Import): mods=[(a.name,[]) for a in n.names]
                for m,names in mods:
                    if not m.startswith(pkg) and m!=pkg: continue
                    q=base+'/'+m.replace('.','/')
                    ok=os.path.isfile(q+'.py') or os.path.isfile(q+'/__init__.py')
                    if not ok: miss.append(('FALTA',os.path.relpath(p,D),m)); continue
                    if os.path.isdir(q):
                        for a in names:
                            if a=='*' : continue
                            if not (os.path.isfile(q+'/'+a+'.py') or os.path.isdir(q+'/'+a)):
                                pass # puede ser nombre dentro de __init__
for m in miss: print(*m)
print('imports internos sin resolver:',len(miss))
# --- control-plane: imports de modulos hermanos presentes en el worktree vivo pero ausentes en el arbol
R='/home/majo1230/Documentos/AURA/aura-project-bible/.claude/worktrees/m3-entry/entorno/control-plane'
vivos={f[:-3] for f in os.listdir(R) if f.endswith('.py')}
cm=[]
cpd=D+'/entorno/control-plane'
for f in sorted(os.listdir(cpd)):
    if not f.endswith('.py'): continue
    try: t=ast.parse(open(cpd+'/'+f,encoding='utf8').read())
    except SyntaxError as e: cm.append((f,'SYNTAX')); continue
    for n in ast.walk(t):
        ms=[]
        if isinstance(n,ast.Import): ms=[a.name.split('.')[0] for a in n.names]
        elif isinstance(n,ast.ImportFrom) and not n.level and n.module: ms=[n.module.split('.')[0]]
        for m in ms:
            if m in vivos and not os.path.isfile(cpd+'/'+m+'.py'): cm.append((f,m))
for f,m in sorted(set(cm)): print('FALTA-CP',f,'importa',m)
print('imports CP sin resolver:',len(set(cm)))
