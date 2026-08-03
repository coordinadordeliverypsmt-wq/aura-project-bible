# Checklist de Continuidad — AURA

> **Para quien retome el desarrollo** (persona o agente), después de horas o de semanas, con o sin
> contexto de las conversaciones anteriores.
>
> **Estatus (CEO, 2026-08-02): este documento es la FUENTE DE VERDAD para retomar el trabajo y para
> registrar cualquier vacío detectado durante un incremento.** Si aparece una deuda, un trabajo diferido o
> un hueco, se anota aquí **en el momento**, no al final.
>
> **Y una regla que no se deroga:** fuente de verdad *para retomar* no significa fuente de verdad *sobre
> los hechos*. Esos los tiene el repositorio y se comprueban por ejecución. Este checklist te dice **qué
> verificar**, **en qué orden** y **qué NO es lo que parece**. Si algo de aquí contradice lo que mide un
> comando, **manda el comando** — y entonces el documento está desactualizado y corregirlo es el trabajo.

**Última actualización:** 2026-08-02 · **Estado documentado:** `main` = `origin/main` = `dc58695`
(verifica el hash actual con `git log`; este documento se actualiza en cada cierre, no en cada commit)

---

## 1 · Arranque en frío: seis comandos antes de tocar nada

Ejecútalos **en este orden**. No empieces a trabajar hasta que los seis hayan pasado.

```bash
cd <raíz del repositorio>

# 1. Preflight OBLIGATORIO del entorno (D27/D31). Verifica USB montados, dónde viven los modelos,
#    espacio y swap. Saltárselo produce conclusiones falsas — ver §4.1.
bash entorno/scripts/preflight-check.sh          # debe terminar en ESTADO: APTO
bash entorno/scripts/instalar-hooks.sh           # una vez por clon: activa el bloqueo del Quality Gate

# 2. ¿Dónde está el código?
git log --oneline -3 && git status --porcelain    # árbol debe estar limpio

# 3. ¿Local y remoto coinciden?
git fetch origin && git rev-list --left-right --count main...origin/main   # debe ser "0  0"

# 4. ¿El sistema pasa su propia puerta de calidad?
cd walking-skeleton && ./quality-gate.sh          # debe terminar en PASS

# 5. ¿Qué enciende realmente el arranque de producción?
AURA_DATOS=/tmp/aura-check python3 -m aura_skeleton   # lee el bloque BOOT; Ctrl-D para salir

# 6. ¿Qué quedó pendiente y qué NO está autorizado?
#    -> §3 y §5 de este documento
```

**Si el paso 1 o el 4 fallan, eso es el trabajo.** No se construye nada encima de un entorno o una base
en rojo.

---

## 2 · Dónde está el proyecto ahora

| | |
|---|---|
| Fase | **Construcción de producto.** La fase documental (Bible) está cerrada desde el 2026-07-18 |
| Capacidades de producto cerradas | **4** — N2 Memoria Semántica · Centro de Notificaciones · Modelo de Usuario · Automatización definida por el usuario |
| Quality Gate | PASS **472 passed / 3 skipped** |
| Benchmark permanente | `tests/datos/bateria_memoria.json` — 65 recuerdos, 77 consultas. Cualquier cambio del recuperador debe superarla. Decisión razonada en `milestones/m3-entry/DECISION-RECUPERADOR-N1.md` |
| Alertas de arquitectura abiertas | **0** (las cinco históricas, resueltas) |
| Trabajo en curso | **ninguno** |
| Proceso automatizado | `CLAUDE.md` (protocolo por sesión) · 4 agentes en `.claude/agents/` · hook `pre-push` con bloqueo duro · arnés de mutación (`herramientas/mutar.py`, a demanda) |
| Modo de trabajo | **Orquestado** (CEO, 2026-08-02): el trabajo se reparte entre agentes; una tarea solo se cierra por evidencia, nunca porque un agente diga que terminó |

**Dos numeraciones distintas — no las mezcles** (fuente de confusión ya detectada por el CEO):

- **Incrementos del roadmap** (orden en que se construyeron): 1 N2 · 2 Notificaciones · 3 Modelo de Usuario · 4 Automatización.
- **Capacidades del MVP (acta D2)**: 1 Memoria · 2 Voz · 3 Avatar · 4 Control del computador · 5 Automatización · 6 Multi-modelo · 7 Hogar · 8 Aprendizaje · 9 Notificaciones.

La pregunta *"¿qué falta del MVP?"* solo se responde con la numeración **D2**. La pregunta *"¿qué hemos
construido?"* con la del **roadmap**. Ambas tablas están separadas en
`milestones/m3-entry/ROADMAP-CAPACIDADES-FUNCIONALES.md`.

---

## 3 · Decidido vs. pendiente

### Decidido y vigente (no reabrir sin el CEO)

| Decisión | Dónde consta |
|---|---|
| La fase de **integración NO está abierta**. Agotar las capacidades construibles es condición *necesaria, no suficiente*; el cambio de fase es decisión **explícita** del CEO | `ROADMAP-CAPACIDADES-FUNCIONALES.md` |
| Presupuesto de hardware **cero**; prohibido fabricar entornos para aprobar hitos (D34) | acta de decisiones fundacionales |
| Local-first, open source, **sin claves de terceros** (D24) | ADR-0001, acta |
| El **Core** es la única fuente de verdad sobre los hechos del sistema (ADR-0014) | `adr/0014-*.md` |
| **Producto Demostrable**: cierre en 5 bloques, demostración desde la perspectiva del usuario | `decisiones/2026-07-28-estandar-de-trabajo-producto-demostrable.md` |
| **D47**: evidencia clasificada `[EJEC]/[LECT]/[INFER]/[HIPO]`; la autoridad viene de la evidencia, no del rango | `decisiones/2026-07-28-D47-*.md` |

### Pendiente de decisión del CEO

| Pendiente | Desde | Qué bloquea |
|---|---|---|
| **P1 · Escenario de despliegue** (¿es esta máquina el objetivo?) | 2026-07-21 | 3 de las 5 fases de M3 |
| **Siguiente inversión del proyecto** tras la revisión estratégica | 2026-08-02 | Todo trabajo de construcción nuevo |
| **Mover el artefacto de N2** (opciones B/C del Decision Package) | 2026-08-02 | Nada urgente: el CEO lo aplazó hasta que N2 pueda usarse; hoy P1 la bloquea. Ver §4.3 |
| **`CHANGELOG.md` e `INDICE.md` abandonados** | 2026-08-02 | Nada técnico, pero afirman ser registro del proyecto y llevan 12-15 días desfasados. Detectado durante el incremento de proceso; no se corrigió para no desviarlo |
| **SIGKILL durante una mutación** deja el fichero mutado | 2026-08-02 | Nada: inevitable en Python (SIGKILL no es interceptable). Recuperación: `git checkout -- <fichero>`. SIGINT sí restaura correctamente |
| **Verificador de consistencia** (propuesta NO autorizada) | 2026-08-02 | Nada. Registrada en `decisiones/pendientes-de-evaluacion/`; se reevalúa tras la revisión estratégica |

---

## 4 · Lo que parece hecho y no lo está

> Esta sección existe porque el proyecto ha sufrido **al menos ocho veces** el mismo patrón —declarado
> en un documento, ausente en la realidad—: ALERTA-004, evals de T1, ALERTA-005, captura de señales,
> ADR-0021, plan vs materialización, `D-ADP-1` y el roadmap contradictorio (recuento verificado con
> hashes el 2026-08-02; antes se citaban cuatro). **Léela entera antes de asumir que una capacidad
> "cerrada" funciona.**

### 4.1 · El preflight no es opcional — saltárselo ya produjo un error

En la revisión estratégica del 2026-08-02 se concluyó que *"Ollama no tiene modelos descargados"*
mirando `~/.ollama`. **Era falso:** el store del servicio está enlazado al USB `AURORA_EXT` y contiene
**dos modelos íntegros** (`qwen2.5:3b` y `qwen2.5:0.5b`). El `preflight-check.sh` lo dice en su segunda
línea. **Ejecuta el paso 1 del §1 siempre.**

### 4.2 · N2 (memoria semántica) está cerrada pero NUNCA se materializa

`[EJEC 2026-08-02]` El arranque real registra: `capacidades (estado EFECTIVO): activas=[] degradadas=['memoria']; memoria -> N1`.

Dos razones **independientes**, ninguna es un defecto de código:
1. El perfil de hardware llega **siempre vacío**: el detector real **no existe** (`core/detectores.py`
   contiene solo Protocolos; `_PerfilInyectado` devuelve lo que traiga la configuración).
2. Aunque existiera: esta máquina tiene **3,6 GB de RAM** frente al umbral declarado de **8 GB**.

**Consecuencia:** el usuario de esta máquina usa N1 (léxico). Comprobado que la arquitectura sí funciona
—`ram_mb=16000` → `SemanticMemory`— pero **no en este hardware**.

### 4.3 · RIESGO ACTIVO — el modelo de N2 vive en un directorio temporal

```
~/.aura/models/paraphrase-multilingual-MiniLM-L12-v2/
   model.onnx     -> /home/majo1230/.claude/jobs/<job>/tmp/mlmodel/onnx/model.onnx   (470 MB)
   tokenizer.json -> /home/majo1230/.claude/jobs/<job>/tmp/mlmodel/tokenizer.json     (17 MB)
```

Son **enlaces al directorio temporal de un job de Claude Code**, que se borra al eliminar el job. Si
desaparecen, la composición captura la excepción y **degrada a N1 en silencio** (una línea de log).

Contradice el principio del CEO —*"la IA es una herramienta de construcción, no una fuente de verdad del
proyecto"*— y la regla D31 —*"nunca se escriben modelos de IA en el disco interno"*, pues deberían vivir
en `AURORA_EXT`.

**Estado (CEO, 2026-08-02):** mover el artefacto **NO está aprobado**; se revisará cuando N2 pueda usarse
realmente (hoy P1 la bloquea). Decision Package en el historial del proyecto. Lo que **sí** se corrigió es
que la degradación ya **no es silenciosa** (ver abajo) y que el manifiesto declara su `source`, de modo que
un artefacto perdido puede **reponerse**, no solo verificarse.

**Ya corregido — la degradación es ruidosa** (2026-08-02, `fix(consistencia)` en el historial): si el plan permite más de lo que se
consigue ensamblar, AURA declara el **estado efectivo**, lo anuncia en el arranque con su motivo y lo
registra en el audit log. Verifícalo así:

```bash
AURA_EMBED_MODEL_DIR=/ruta/inexistente python3 -m aura_skeleton   # debe avisar, no callar
```

### 4.4 · El motor de inferencia NO es viable en esta máquina

`[EJEC 2026-08-02]` Medido con el modelo **más pequeño disponible** (`qwen2.5:0.5b`, ya descargado):

| Caso | Resultado |
|---|---|
| Prompt «Hola», 8 tokens de salida | **25,8 s** (vs presupuesto 1200 ms → **21× por encima**) |
| Prompt real de AURA (543 tokens) | **no completa** — error 500 tras 3 min |

**No es un problema de "falta descargar un modelo pequeño".** Ya está descargado y tampoco sirve. La
restricción es la máquina.

**Por defecto, AURA arranca con `MockProvider`** (`AURA_STACK_REAL` no definida): un clasificador de
5 reglas de palabras clave. Si lees "AURA entiende al usuario", verifica **con qué proveedor**.

### 4.5 · AURA afirma acciones del hogar que no ejecuta

`[EJEC 2026-08-02]` Con Home Assistant ausente:

```
Usuario: Enciende la lámpara del salón
AURA:    Enciendo la lámpara. [accion encender_dispositivo ejecutada]
```

No se encendió nada. El adaptador de hogar es un mock que solo escribe una línea de log, pero el
arranque lo lista entre las **12 operaciones disponibles** (10 reales sobre archivos + 2 simuladas).
La garantía de ALERTA-005 verifica que **el adaptador respondió**, no que **el mundo cambió**.

**Sigue abierto — deuda `D-ADP-1`**, registrada en
`milestones/m3-entry/DEUDA-ADAPTADORES-SIMULADOS.md` (el CEO decidió no abrir incremento: primero
producto). La corrección de consistencia del 2026-08-02 resolvió la inconsistencia en la **capa de capacidades**
(plan vs materialización); esta es la misma clase de problema en la **capa de adaptadores** y todavía no
tiene solución: un adaptador simulado responde `status: ok` igual que uno real.

### 4.6 · Las superficies conversacionales ya interfieren entre sí

`[EJEC 2026-08-02]` Hay **47 patrones literales en 8 grupos**, evaluados en cascada con precedencia
fija en `on_turn`; el árbitro es **el orden en que se escribió el código**. Defectos verificados:

| El usuario dice | AURA responde | Diagnóstico |
|---|---|---|
| «Mis reglas de casa son otras» | lista las automatizaciones | falso positivo |
| «Olvida lo que ha pasado» | «No he encontrado eso para olvidarlo» | superficie equivocada |
| «Olvida esa automatización» | «No he encontrado eso para olvidarlo» | superficie equivocada; la regla sigue activa |
| «Elimina la automatización de copias» | pasa al LLM, sin efecto | hueco sin cubrir |

**Antes de añadir una superficie determinista nueva, comprueba que no colisiona con las 8 existentes.**

### 4.7 · Nadie ha usado AURA

`[EJEC 2026-08-02]` El audit log de producción tiene **8 entradas, todas de arranque**. No hay memoria
persistida ni reglas en `~/.aura`. La captura de señales **funciona** (verificado: 2 señales de 3
turnos), pero **ningún componente las consume** y no hay materia prima acumulada.

Consecuencia: **ninguna decisión de producto puede apoyarse hoy en telemetría de uso real.**

### 4.8 · La equivalencia del índice de memoria estaba verificada solo a escala pequeña

`[VERIF 2026-08-03]` `memory.py` afirmaba que el índice invertido daba un resultado **«idéntico»** al
barrido completo, y que estaba **«verificado»**. Lo estaba — pero solo por debajo de
`_UMBRAL_UBICUO = 256`, el único régimen que la batería oficial (65 recuerdos) **puede** ejercitar.
Por encima, la equivalencia se rompe: un recuerdo con cobertura suficiente puede no llegar a
puntuarse nunca (`D-M-1`, `milestones/m3-entry/DEUDA-N1-RECUPERADOR.md`, con contraejemplo
reproducible).

La lección no es el defecto —heredado de MA.2a, no introducido por el incremento de cobertura— sino
**cómo se coló**: una prueba en verde cuyo dominio no alcanza la condición que la afirmación cubría.
Un verde solo demuestra lo que la prueba **puede** ejercitar.

`test_el_recall_sigue_siendo_correcto_con_volumen` sigue en verde con `D-M-1` activo: su recuerdo-aguja
tiene términos exclusivos. **No es un control de este escenario**, aunque su nombre lo sugiera.

---

## 5 · Qué NO está autorizado

1. **Abrir la fase de integración.** Decisión explícita del CEO (2026-08-02).
2. **Iniciar cualquier incremento nuevo** sin decisión posterior a la revisión estratégica.
3. **Abrir frentes fuera del plan** aprobado.
4. **Fabricar entornos** para aprobar hitos (D34) ni adoptar claves de terceros (D24).
5. **Recortar capacidades del MVP**: exige nueva acta del CEO (D2 es rango 1).

---

## 6 · Cómo se trabaja aquí

**El protocolo vive en [`CLAUDE.md`](CLAUDE.md), no aquí.** Allí están el ciclo de todo incremento
(RED → GREEN → mutación → Quality Gate → auditoría → cierre), el flujo de integración con sus comandos
exactos, los trailers obligatorios, las reglas que no se negocian y el **reparto obligatorio de
orquestación** (quién hace qué; el que implementa nunca audita su propio trabajo).

**Por qué no se repite en este documento:** dos copias del mismo texto se desincronizan, y este proyecto
ya ha pagado ocho veces el precio de que un documento afirme algo que no es cierto. Cada contenido tiene
un solo dueño: **el protocolo es de `CLAUDE.md`; el estado del proyecto, las decisiones vigentes y las
trampas son de este checklist.**

### Deuda registrada — leer antes de tocar lo relacionado

| Documento | Cubre |
|---|---|
| `milestones/m3-entry/DEUDA-N2-MEMORIA-SEMANTICA.md` | acoplamiento a `_items`, re-embebido en arranque (305 ms/recuerdo), fragilidad ante `restore()`, y **`D-N2-5`: con N2 activa, «olvida esto» lanza `AttributeError`** |
| `milestones/m3-entry/DEUDA-AUTOMATIZACION.md` | 8 partidas; reconocedor de un solo patrón, sin semántica transaccional |
| `milestones/m3-entry/DEUDA-CAPTURA-DE-SENALES.md` | brecha histórica de instrumentación |
| `milestones/m3-entry/DEUDA-ADAPTADORES-SIMULADOS.md` | `D-ADP-1`: un adaptador simulado responde `ok` igual que uno real |
| `milestones/m3-entry/DEUDA-N1-RECUPERADOR.md` | 6 partidas. **`D-M-2` es CRÍTICA: el eco `usuario dijo:` del propio turno desactiva ADR-0014 al repetir una pregunta.** Además: recall a 0,000 con coletillas de cortesía, recuerdo largo como atractor de FP, refutados que siguen llegando al LLM, y `D-M-1` (régimen ubicuo) |
| `milestones/m3-entry/DP-D-M-1-RECUPERACION-EXACTA.md` | Decision Package **APROBADO como documento** (CEO, 2026-08-03). Recomienda `A′` (prefijo con cota, α=1 como elección de diseño). **La implementación NO está autorizada: el CEO la supeditó a resolver antes `D-M-2`** |

## 7 · Cómo se mantiene este checklist

**Actualizarlo es parte del cierre de cada incremento, igual que los cinco bloques.** Un incremento no
está cerrado si este documento quedó desactualizado.

En cada cierre, revisar y corregir:

1. **§2** — hash, Quality Gate, capacidades cerradas, trabajo en curso.
2. **§3** — mover a "decidido" lo que el CEO haya decidido; añadir lo que quede pendiente.
3. **§4** — **la sección más importante.** Añadir toda trampa nueva descubierta; **borrar** las que se
   hayan corregido de verdad (con el commit que lo demuestra). Una trampa resuelta que sigue listada
   hace perder tiempo; una trampa real ausente hace perder el proyecto.
4. **§5** — actualizar autorizaciones y prohibiciones vigentes.
5. **§6** — solo si cambió el protocolo o apareció deuda nueva registrada.

Si al actualizarlo descubres que algo de §4 **ya no es cierto**, verifícalo por ejecución antes de
borrarlo, y cita el commit en el cierre del incremento.
