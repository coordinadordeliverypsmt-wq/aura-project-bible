import os,re,sys,glob,tomllib,ast
T=os.environ['T']; R=os.getcwd()
lines=[l.rstrip('\n') for l in open(T+'/estado-uall.txt')]
st={}
for l in lines:
    p=l[3:]; 
    if ' -> ' in p: p=p.split(' -> ')[-1]
    st[p]=l[:2]
EXC=re.compile(r'(__pycache__|\.pyc$|graphify-out/|kernel\.errors\.txt$|omisiones\.log$|\.pytest_cache|\.ruff_cache|\.control-plane\.lock$|\.supervisor\.lock$|control-plane/(estado\.json|eventos\.jsonl)$)')
EXTRA_EXC={'.claude/ficha-evidencia.md':'efimera por diseno (orquestacion-herramientas.md: se descarta al cerrar el incremento)'}
CP='entorno/control-plane/'; WS='walking-skeleton/'
REC_CP={CP+'planificador.py',CP+'control_plane.py',CP+CP and CP+'motor_autonomia.py',CP+'aura.py',CP+'.gitignore',
        CP+'test_red_reanudacion_tras_caida.py',CP+'mutaciones/reanudacion-tras-caida.toml',
        WS+'mutaciones/motor-autonomia.toml',WS+'mutaciones/f1-orquestador.toml'}
rule={}; why={}
def put(p,c,w=''): rule[p]=c; why[p]=w
for p in st:
    if EXC.search(p): put(p,'X','exclusion obligatoria'); continue
    if p in EXTRA_EXC: put(p,'X',EXTRA_EXC[p]); continue
    b=os.path.basename(p)
    if p in REC_CP: put(p,5,'recuperacion tras caidas'); continue
    if p.startswith(WS+'aura_skeleton/') or p==WS+'architecture_manifest.toml': put(p,1,'nucleo runtime'); continue
    if p in (WS+'tests/unit/test_ruta_red.py',WS+'tests/unit/test_sin_dispositivos_reales.py',WS+'mutaciones/ruta-red.toml',WS+'mutaciones/sin-dispositivos-reales.toml'): put(p,2,'red v2'); continue
    if p.startswith(WS+'tests/'): 
        if re.search(r'test_(arnes_|registro_gate)',b): put(p,3,'arnes/gate')
        elif 'panel_progreso' in b: put(p,7,'panel')
        else: put(p,1,'tests WS')
        continue
    if p in (WS+'herramientas/mutar.py',WS+'herramientas/registro_gate.py',WS+'quality-gate.sh') or re.match(WS+'mutaciones/(arnes-|retiradas/)',p): put(p,3,'arnes/gate'); continue
    if p in (WS+'herramientas/panel_progreso.py',WS+'herramientas/censura_panel.py',WS+'herramientas/procedencia_panel.py','herramientas/indice_madurez.py','herramientas/test_indice_madurez.py','publicado/panel-progreso/index.html'): put(p,7,'panel'); continue
    if p.startswith(WS+'herramientas/'): put(p,6,'herramienta de medicion (evidencia)'); continue
    if p.startswith(WS+'mutaciones/'): put(p,'M','derivar de fichero/pruebas'); continue
    if p.startswith(CP+'mutaciones/'): put(p,'M','derivar'); continue
    if p.startswith(CP): put(p,4,'plano de control'); continue
    if p.startswith('entorno/nodos/') or p in ('entorno/scripts/voz-usb.sh','entorno/scripts/aura-voz.sh'): put(p,1,'toolchain de nodo/voz leida por pruebas de WS'); continue
    if p.startswith('entorno/scripts/') or p.startswith('entorno/'): put(p,7,'operativo (sin asignar en la propuesta)'); continue
    if re.search(r'milestones/m3-entry/evidencia-',p) or p.startswith('milestones/investigacion-externa/'): put(p,6,'evidencia'); continue
    put(p,7,'docs/gobierno')
# --- derivar mutaciones
def commit_of_module(mod_path,base):
    # mod_path relative to base dir ('aura_skeleton/...' or 'x.py')
    for pre in (WS,CP,''):
        q=pre+mod_path
        if q in rule and rule[q]!='M': return rule[q]
    return None
def test_commit(spec,base):
    f=spec.split('::')[0]
    for pre in (base,WS,CP):
        q=pre+f
        if q in rule and rule[q]!='M': return rule[q]
    return None
for p in [q for q in rule if rule[q]=='M']:
    base=WS if p.startswith(WS) else CP
    d=tomllib.load(open(p,'rb')); cs=[]; notes=[]
    for s in d.get('pruebas',[]): 
        c=test_commit(s,base); (cs.append(c) if c else notes.append('prueba?'+s))
    for m in d.get('mutante',[]):
        if 'fichero' in m:
            c=commit_of_module(m['fichero'],base); (cs.append(c) if c else notes.append('fichero?'+m['fichero']))
        for s in m.get('pruebas',[]):
            c=test_commit(s,base); (cs.append(c) if c else notes.append('prueba?'+s))
    cs=[c for c in cs if c!='X']
    rule[p]=max(cs) if cs else 7
    why[p]='derivado max%s %s'%(sorted(set(cs)),';'.join(sorted(set(notes)))[:120])
OV4=['entorno/control-plane/mutaciones/'+x+'.toml' for x in ('barreras-de-gobernanza','blindaje-del-mecanismo','eventos-de-autoridad','kill-switch-cableado','observar-git','presupuesto-y-perimetro')]+['walking-skeleton/mutaciones/'+x+'.toml' for x in ('auditoria-3-y-cuota-11','codigo-muerto-completo','controles-14-y-criterios-22','cp-estado-defectos')]
for p in OV4:
    if p in rule: rule[p]=4; why[p]+=' | override: aplica sobre previos-a-la-aplicacion (etapa 4) -> C4'
# --- tests -> docs / data que referencian (arrastre hacia delante)
tests=[p for p in rule if re.search(r'(/tests/.*\.py|/test_[^/]*\.py)$',p)]
cands=[p for p in rule if p.startswith('entorno/') and rule[p] not in ('X',) and not p.endswith('.py') and not p.startswith(WS+'mutaciones/') and not p.startswith(CP+'mutaciones/')]
cands+= [p for p in rule if p.startswith(('entorno/nodos/','entorno/scripts/','herramientas/')) and p.endswith('.py')]
txt={t:open(t,encoding='utf8',errors='replace').read() for t in tests}
pulls=[]
for p in cands:
    if not p.startswith('entorno/'): continue
    b=os.path.basename(p)
    for t in tests:
        ct=rule[t]
        if ct=='X' or rule[p]<=ct: continue
        if p in txt[t] or (len(b)>=10 and b in txt[t]):
            pulls.append((p,rule[p],ct,t)); rule[p]=ct; why[p]+=' | arrastrado por '+t
with open(T+'/arrastres.txt','w') as f:
    for x in pulls: f.write('%s\t%s->%s\t%s\n'%x)
with open(T+'/asignacion.tsv','w') as f:
    for p in sorted(rule): f.write('%s\t%s\t%s\n'%(p,rule[p],why[p]))
from collections import Counter
print(Counter(str(v) for v in rule.values()))
