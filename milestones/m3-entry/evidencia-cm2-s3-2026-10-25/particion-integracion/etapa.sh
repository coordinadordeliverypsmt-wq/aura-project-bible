#!/bin/bash
# uso: etapa.sh K   (arbol acumulativo 1..K)
K=$1; T=/home/majo1230/.claude/jobs/d6cb894c/tmp/particion
R=/home/majo1230/Documentos/AURA/aura-project-bible/.claude/worktrees/m3-entry
D=$T/arbol-$K; rm -rf "$D"; mkdir -p "$D" $T/home
(cd $R && git archive HEAD) | tar -x -C "$D"
PREV=$R/milestones/m3-entry/evidencia-cm2-s3-2026-10-25/reanudacion-tras-caida/previos-a-la-aplicacion
python3 - "$K" "$D" "$R" "$T" "$PREV" <<'PY'
import sys,shutil,os
K=int(sys.argv[1]);D,R,T,PREV=sys.argv[2:6]
cp='entorno/control-plane/'
prev={cp+'planificador.py':'planificador.py',cp+'control_plane.py':'control_plane.py',cp+'motor_autonomia.py':'motor_autonomia.py',cp+'aura.py':'aura.py'}
n=0
for l in open(T+'/asignacion.tsv'):
    p,c,_=l.rstrip('\n').split('\t',2)
    if c=='X': continue
    c=int(c)
    src=R+'/'+p
    if c<=K: pass
    elif c==5 and K==4 and p in prev: src=PREV+'/'+prev[p]
    else: continue
    dst=D+'/'+p; os.makedirs(os.path.dirname(dst),exist_ok=True)
    shutil.copy2(src,dst); n+=1
if K>=3:
    o=D+'/walking-skeleton/mutaciones/arnes-validador-comandos.toml'
    if os.path.exists(o): os.remove(o)
print('ficheros copiados',n)
PY
