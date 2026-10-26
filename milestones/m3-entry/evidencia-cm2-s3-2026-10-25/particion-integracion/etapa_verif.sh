#!/bin/bash
K=$1; T=/home/majo1230/.claude/jobs/d6cb894c/tmp/particion; D=$T/arbol-$K
export PYTHONDONTWRITEBYTECODE=1 PYTHONUSERBASE=/home/majo1230/.local HOME=$T/home AURA_CONTROL_PLANE= AURA_RED=
echo "=== ETAPA $K  $(date -Is)"; $T/etapa.sh $K
echo "--- (0) imports internos sin resolver (AST, lazy incluidos)"; python3 $T/verifica.py $D
echo "--- (a1) receptor/CM2: import aura_skeleton.__main__ (cwd=walking-skeleton)"
( cd $D/walking-skeleton && python3 -c "
import importlib,aura_skeleton.__main__ as m, importlib.util as u
for x in ('aura_skeleton.core.reloj_cm2','aura_skeleton.adapters.receptor_nodos','aura_skeleton.core.nodos'):
    print(x, 'OK' if u.find_spec(x) else 'AUSENTE')
src=open(m.__file__).read()
print('flag --receptor-nodos en __main__:', '--receptor-nodos' in src, '| --medir-cm2:', '--medir-cm2' in src)
" ; echo "rc=$?" )
echo "--- (a2) despertador: import despertador (cwd=control-plane)"
( cd $D/entorno/control-plane && python3 -c "
import despertador, aura, control_plane, orquestador
print('despertador importado OK; verificador/aislamiento:', __import__('importlib.util').util.find_spec('verificador') is not None, __import__('importlib.util').util.find_spec('aislamiento') is not None)" ; echo "rc=$?" )
for sub in walking-skeleton entorno/control-plane; do
  echo "--- (b) pytest --collect-only $sub"
  ( cd $D/$sub && python3 -m pytest --collect-only -q -p no:cacheprovider > $T/colecta-$K-$(basename $sub).txt 2>&1; echo "rc=$?" )
  python3 - $T/colecta-$K-$(basename $sub).txt <<'PY'
import sys,re
L=open(sys.argv[1],errors='replace').read().splitlines()
tot=0;fi=0;err=[l for l in L if l.startswith('ERROR') or 'Error' in l[:60] and l.startswith('E ')]
for l in L:
    m=re.match(r'^(\S+\.py): (\d+)$',l)
    if m: tot+=int(m.group(2)); fi+=1
    m=re.match(r'^(\d+) tests? collected',l)
    if m: tot=int(m.group(1))
    m=re.search(r'(\d+) errors?',l)
print('  recogidos:',tot,'| ficheros con tests (modo -q):',fi,'| lineas ERROR:',len([l for l in L if l.startswith('ERROR')]))
for l in L:
    if l.startswith('ERROR') or l.startswith('E   '): print('  ',l[:200])
print('  ultima linea:',L[-1][:160] if L else '')
PY
done
