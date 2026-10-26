---
documento: "AURA — Master Development Map"
fecha: 2026-09-27
mantenido-por: "APUS-5 (CTO)"
fuente-de-datos: "milestones/mapa-maestro/capacidades.json (82 capacidades con evidencia al 2026-10-22)"
calculo: "python3 herramientas/indice_madurez.py milestones/mapa-maestro/capacidades.json"
regla-de-actualizacion: "Cada semana: cambiar nivel+evidencia en capacidades.json y recalcular. Ningún % se edita a mano."
---

# AURA — Master Development Map

## 1 · Resumen ejecutivo

**AURA hoy es un núcleo conversacional gobernado, con memoria que funciona de verdad, voz real de
ida y vuelta y la primera mano sobre el hogar, esperando un gesto humano.** No es todavía un ser
integrado: tiene los órganos del MVP casi todos construidos (CORE 87,1 %), pero buena parte no está
aún demostrada de extremo a extremo ni en operación sostenida (READY 59,0 %).

| Ámbito | AURA CORE | AURA READY | AURA MATURITY INDEX |
|---|---:|---:|---:|
| **Lanzamiento** (alcance MVP, Bible 2.2) | 87,1 % | 59,0 % | **73,1 %** |
| Horizonte completo (hasta Release 4) | 77,3 % | 46,1 % | **61,7 %** |

*Recalculado el 2026-10-22 con `indice_madurez.calcular` sobre 82 capacidades (antes esta tabla conservaba la línea base
del 2026-09-27: 69,9 % / 57,6 %, que sigue en el registro de evolución). La vista viva es el panel de progreso:
`cd walking-skeleton && python3 -m herramientas.panel_progreso` → `publicado/panel-progreso/index.html`.*

**Advertencia que manda sobre el porcentaje:** el índice mide madurez de CAPACIDADES. La aceptación
formal del MVP exige además sostener los criterios-marco CM1–CM4 en uso real, y **CM1 no es
alcanzable en el hardware de referencia**: la Bible pide P50 ≤ 800 ms en local y AURA mide hoy
**7,4 s** por turno de voz con los modelos cargados (HC-1, Celeron N4020). Es el bloqueo nº 1.

## 2 · El marco formal que este mapa adopta (y por qué no el de 13 etapas)

La hipótesis de etapas del mandato (0 Constitución … 12 Lanzamiento) se contrastó con la Bible. La
Bible tiene su propia estructura y **prevalece** (el propio mandato lo exige):

| Formal | Contenido (Bible 2.2 §3, §5) | Etapas del CEO que caen aquí |
|---|---|---|
| **M1 — Núcleo conversacional** | memoria (1) · voz (2) · multi-LLM (6) | 1 Memoria · 4 Comunicación · parte de 2 Sentidos (oír/hablar) |
| **M2 — Manos digitales** | computador (4) · automatización (5) · notificaciones (9) | 6 Acción · parte de 9 Proactividad |
| **M3 — Presencia** | hogar (7) · avatar (3) · aprendizaje/anticipación (8) | 5 Presencia · 7 Relación · 9 Proactividad |
| **R1 = MVP** | M1+M2+M3, aceptado al sostener CM1–CM4 en una ventana de uso real (2.2 §3.4) | **12 «Lanzamiento»** |
| R2 — El políglota autónomo | modelos, Android, NAS | parte de 2 Sentidos |
| R3 — El guardián | seguridad activa, multiusuario | 3 Identidad · 8 Protección |
| R4 — La presencia total | cámaras y visión, multi-dispositivo | 2 Sentidos (ver) |
| Horizonte PIOS H2/H3 (7.5) | orquestador, PIOS pleno | 10 Autoevolución |

**«Lanzamiento del ser» no es un término de la Bible.** Su equivalente formal es la **aceptación de
R1** en el gate del CEO (2.2 §3.4, §3.5). Tampoco admite la Bible un salto binario «componentes →
ser»: AURA es un PIOS desde su definición (D18) y madura por horizontes (2.1 §5). Este mapa usa el
**umbral de integración** (§14) como hito observable de ese paso, sin llamarlo nacimiento.

**Sobre el calendario:** la Bible mide los hitos «por criterios de salida, no por fechas» (2.2:134).
Las semanas de §16 son una **estimación de esfuerzo** anclada en la velocidad medida; cada semana
termina en un criterio de salida verificable, no en una fecha.

## 3 · Estado actual (2026-09-27) · evidencia de ejecución

- Memoria: «Mi nombre es X» → cambio de tema → «¿Cómo me llamo?» correcto; corrección versionada;
  sobrevive al reinicio `[EJEC]`.
- Voz: micrófono → Whisper → AURA → Piper → altavoz, **por el aire** `[EJEC]`; 7,4 s por turno.
- Hogar: HA instalado (solo localhost), adaptador real con confirmación del efecto; la TV Samsung
  real espera a que alguien pulse «Permitir».
- Gobierno: PARADA armada; Motor Único, permisos, kill switch, audit log veraz; 1205 garantías
  declaradas; mutación en cada incremento.
- Autoevolución: el ciclo funcionó (12 cambios aplicados acreditados) y está **detenido** por PARADA
  desde 2026-09-08.

## 4 · Arquitectura real (lo que corre al ejecutar AURA)

```
micrófono ─► Whisper (USB) ─┐                                  ┌─► Piper precargada ─► altavoz
                            ▼                                  │
        Orquestador: cascada de superficies deterministas ─────┤  (el modelo solo si nada del Core responde)
            │  memoria personal · ventana DR-4 · recuperación M8 · órdenes · aritmética · estado
            ▼
        Motor Único ─► permisos/listas D4 ─► kill switch ─► adaptador ─► verificación ─► audit log
            │                                                    ├─ computador (ficheros)
            │                                                    ├─ Home Assistant (127.0.0.1) ─► TV
            │                                                    └─ QA · auditor · diagnóstico
        Control-plane (fuera del producto): descubrimiento → planificación → ejecución → PARADA
```

## 5–8 · Capacidades por estado, con evidencia

La tabla completa, con ruta, prueba y bloqueo de cada capacidad, es **`capacidades.json`** (82
filas). Resumen por nivel, **calculado del fichero** (`collections.Counter` sobre `nivel`) el 2026-10-22; los ejemplos
son de la línea base y no son exhaustivos:

| Nivel | Nº | Ejemplos |
|---|---:|---|
| 6 Operativa | 18 | Motor Único, permisos, kill switch, memoria personal, DR-4, reglas, audit log |
| 5 Demostrada E2E | 27 | voz bidireccional, micrófono, corrección, reinicio, recuperación M8 |
| 4 Integrada | 11 | HA como hub, encender/apagar verificado, olvido, notificaciones |
| 3 Implementada | 3 | CM2 a 4 semanas, memoria N2, delegación |
| 2 Prototipo | 3 | cámara, presencia, descubrimiento, voz→dispositivo |
| 1 Concepto | 15 | avatar, palabra de activación, anticipación, multiusuario, guardián |
| 0 Inexistente | 5 | barge-in, anomalías, emergencias, conocido/desconocido |

**Bloqueadas por gobierno** (no por técnica): avatar (D33), anticipación (contradicción de
alcance), multiusuario e identidad (R3), visión (R4), voz→dispositivo, privacidad D, autoevolución
(PARADA/ADR-0025), delegación (D22).

## 9–12 · Índices y fórmula

```
core(c)  = min(nivel, 3) / 3          ready(c) = max(nivel − 3, 0) / 3
dimensión = media de sus capacidades   CORE / READY = media de las dimensiones
AURA MATURITY INDEX = (CORE + READY) / 2   (= media de nivel/6)
```

**Pesos:** todas las dimensiones pesan lo mismo. La Bible no jerarquiza sus pilares y un peso
elegido a mano sería un porcentaje subjetivo disfrazado. Lo que la Bible sí define es el
**alcance**, y por eso hay dos ámbitos. La herramienta rechaza cualquier nivel ≥2 sin evidencia
(`herramientas/test_indice_madurez.py`, 7 pruebas).

Índice por dimensión (lanzamiento, **línea base 2026-09-27**; los nombres no tienen correspondencia declarada con las
letras A–Q de `capacidades.json` — decisión pendiente del CEO): Gobierno 91,7 · Acción 90,0 · Voz 72,2 · Identidad del ser 70,8
· Comunicación 70,8 · Memoria 70,4 · Inteligencia 66,7 · Audición 61,1 · Proactividad 61,1 ·
Aprendizaje 61,1 · Presencia 60,0 · **Relación familiar 33,3**.

## 13 · Mapa de dependencias (surgido del código, no de la hipótesis)

```
                 GOBIERNO (Motor Único, permisos, PARADA)   ← ya maduro: todo cuelga de aquí
                        │
      ┌─────────────────┼──────────────────────────┐
   MEMORIA           ACCIÓN                     VOZ (oír + hablar)
      │                 │                          │
      │            HOGAR (HA) ◄── [humano: Permitir]    PALABRA DE ACTIVACIÓN
      │                 │                          │
      └──────► UMBRAL DE INTEGRACIÓN ◄─────────────┘   ◄── [decisión: voz→orden reversible]
                        │
          USO REAL SOSTENIDO (datos) ──► CM2 memoria a 4 semanas
                        │
                 APRENDIZAJE / ANTICIPACIÓN (CM4) ◄── [decisión: alcance]
                        │
                   AVATAR (paralelo) ◄── [decisión D33]
                        │
              ACEPTACIÓN R1 ◄── [bloqueo duro: CM1 en HC-1]
                        │
        R2 políglota ─► R3 guardián + identidad ◄── [decisión B] ─► R4 visión ◄── [decisión A]
```

**Cuello de botella:** el aprendizaje y CM2 dependen de **tiempo de uso real**, que ningún código
acorta. Por eso el uso real tiene que empezar ya, en paralelo, y no al final.

**Paralelizable:** palabra de activación ‖ hogar · instrumentación de CM2 ‖ integración · avatar ‖
aprendizaje · reactivación de la autoevolución (decisión propia) ‖ todo lo anterior.

## 14 · Etapas evolutivas y su Definition of Done (por comportamiento)

| Etapa (formal) | DoD — AURA demuestra que… | Estado |
|---|---|---|
| **M1 · Núcleo conversacional** | recuerda, corrige, persiste, recupera, supera reinicio; oye y responde por voz; no inventa | Técnico ✅ · CM1 ❌ · CM2 sin medir |
| **M2 · Manos digitales** | actúa sobre el computador por el Motor Único; automatiza lo que el usuario define; notifica | Técnico ✅ · gate del CEO presentado, sin veredicto |
| **Umbral de integración** | en UNA conversación: persona habla → AURA la oye → recuerda → actúa sobre el hogar → verifica el efecto → recuerda el resultado | Opción C aprobada (CEO 2026-10-04); voz→TV demostrada E2E por el aire (10-04/06); cadena completa en una conversación hablada probada con dobles (2026-10-21); **sin E2E físico de la cadena entera** · el resultado no sobrevive al reinicio (punto D) |
| **M3 · Presencia** | hogar real verificado; avatar; aprende de patrones y anticipa (≥1 acción proactiva valorada/día, ≤20 % falsos positivos) | Hogar 4/6 · avatar 1 · anticipación 1 |
| **Aceptación R1** | CM1–CM4 sostenidos 2 semanas de uso real, medidos por registro automático, veredicto del CEO | Bloqueado por CM1 en HC-1 |
| R2 · R3 · R4 | según 2.2 §5 | Conceptos |

## 16 · Cronograma de evolución (estimación de esfuerzo; cada semana cierra por criterio de salida)

**Base de la estimación:** velocidad medida el 2026-09-27 — en una jornada, la voz pasó de nivel
1–2 a 5, el hogar de 0 a 4 y la memoria corrigió tres defectos, con mutación y auditoría. Se estima
**un bloque vertical por semana** de trabajo. Es estimación, no dato; se recalibra cada semana.

| Semana | Objetivo del ser | Capacidades | Salida esperada (existencia nueva) | Gate |
|---|---|---|---|---|
| **S1** ✅ técnico | **Voz presente** | TTS precargada ✅ · palabra de activación ✅ · voz→dispositivo* · TV E2E* | AURA **acude cuando la llaman por su nombre** ✅ demostrado por el aire | E2E por el aire ✅ + mutación 30/30 ✅ |
| **S2** ✅ técnico | **Primer umbral de integración** | entorno físico ✅ · orden de hogar por el Core ✅ · memoria del resultado ✅ · fallos de red/HA/dispositivo ✅ · voz→acción ✅ (opción C, solo TV sala) · TV real ✅ | AURA **conoce su entorno por voz** ✅ y cierra orden → Motor Único → efecto verificado → recuerdo (✅ TV real por voz humana, 2026-10-04/06) | mutación 72/72 ✅ |
| **S3** ‖ S2 · 🟡 mecanismo | **Memoria en la vida real** | reloj de CM2 ✅ implementado, validado e **iniciado el 2026-10-07** (`cm2.inicio`, seq 1314; el día 28 es **por hecho** — `max(valid_from, inicio)` + 28 d —; con 0 hechos a 2026-10-24, ninguna sonda de día 28 antes del 2026-11-21) · olvido: rutas lógicas cerradas (T11) ✅ · privacidad D* · borrado físico / D-AMP-3* | AURA **mide su propio recuerdo** en uso real | registro CM2 funcionando (⏳ iniciado; gate (D-CM2-1) = ≥20 sondas válidas de día 28 (mínimo provisional, Q5) + «todos los criterios vigentes»; evaluación final del CEO (fase 5); a 2026-10-24: 0 hechos y 0 sondas por D-CM2-1; procedimiento en `PROCEDIMIENTO-INICIO-CM2.md` §7) |
| **S4–S5** | **Aprender y anticipar** | inferencia de patrones (M3.2b) · sugerencias (CM4)* | AURA **propone** algo útil que nadie le pidió | ≥1 sugerencia valorada |
| **S5** ‖ | **Rostro** | avatar Live2D* | AURA **tiene una presencia visible** coherente con su voz | demo + gate M3 |
| **S6** | **Integración y gates** | gates M2 y M3 · regresión completa | AURA opera como **un solo sistema** | gates del CEO |
| **S7–S8** | **Ventana de aceptación R1** | uso real sostenido | CM1–CM4 sostenidos → **aceptación de R1** | gate R1 (CEO) |
| Post-R1 | R2 → R3 → R4 | políglota · guardián + identidad* · visión* | según decisiones A/B | por release |

`*` = depende de una decisión o acción humana (§19); la rama bloqueada no congela las demás.
**S7–S8 no puede cerrarse en HC-1 mientras CM1 siga como está.**

## 17 · Plan diario de S1 y S2

| Día | S1 · Voz presente | S2 · Primer umbral de integración |
|---|---|---|
| Lunes | ✅ TTS precargada (5,9 s → 0,8 s) · medición de palabra de activación | descubrimiento pasivo como proveedor de contexto |
| Martes | palabra de activación en AURA (Vosk, regla de vocativo) | pruebas de dispositivo desconectado, red caída, HA caído |
| Miércoles | escucha continua por segmentos, sin archivar audio | notificaciones de hogar E2E |
| Jueves | pruebas por el aire, falsos positivos, PARADA | cadena completa en una conversación |
| Viernes | mutación · seguridad · Quality Gate · demo | mutación · seguridad · Quality Gate · demo |

Si un día termina antes, se empieza el siguiente bloque.

## 18–19 · Bloqueos y decisiones requeridas

| Bloqueo | Tipo | Impacto | Decisión | Trabajo alternativo |
|---|---|---|---|---|
| CM1 (≤800 ms) inalcanzable en HC-1. Medido E2E el 2026-09-29: camino por defecto P50 32,1 s; mejor vía rápida (espeak + Vosk) P50 995-1070 ms, con corrupción de memoria. iGPU: GPU HANG. OpenVINO CPU: 50 s (`RESULTADO-CM1-HW-ACCEL.md`) | **Decisión** | Impide aceptar R1 y, por dependencia, R2-R4 | Hardware objetivo del despliegue (vía 3). El umbral de CM1 NO se cambia (CEO 2026-09-28) | Agotado en HC-1 con lo autorizado (A, B1-B3, iGPU, TTS alternativa). No repetir sin hipótesis nueva |
| TV sin emparejar | **Acción humana** | Hogar no pasa de nivel 4 | — pulsar «Permitir» + `~/aura-hogar/emparejar-tv.sh` | Todo lo demás |
| Voz → acción reversible sin modelo | Decisión | «Apaga la tele» dicho no llega al dispositivo | ¿Ampliar `ordenes.py` a lista verde reversible? | La acción funciona por el Motor Único |
| Privacidad del contenido retenido (punto D) | Decisión | Retención de ficheros leídos | `DECISION-REQUERIDA-CONTINUIDAD-DE-RESULTADOS.md` | — |
| Visión (A) e identidad (B) | Decisión | R4/R3 | `DECISION-REQUERIDA-PERCEPCION-VISUAL-E-IDENTIDAD.md` | medición hecha |
| Avatar | Decisión (D33) | Capacidad 3 del MVP | Plataforma de despliegue | — |
| Anticipación | Decisión | CM4 | `reglas.py` la declara fuera del MVP; la Bible 2.2 la pone en M3 | captura de señales ya activa |
| Tres LLM frente a D24 | Decisión | Capacidad 6 | Conciliar capacidad 6 con «sin claves de terceros» | — |
| Autoevolución detenida | Decisión | El ciclo no avanza solo | PARADA · ADR-0025 · delegación (6 preguntas) | — |

## 21 · Riesgos

- **Rendimiento de HC-1** (el mayor): CM1 y la experiencia de voz dependen de hardware que la acta
  D-4 prohíbe cambiar.
- **Tiempo de uso real:** CM2 y CM4 exigen semanas de uso que ningún código acorta.
- **Falsos positivos de la palabra de activación:** una AURA que escucha sin ser llamada rompe la
  confianza (medido y mitigado con la regla del vocativo).
- **«Declarado ≠ real»:** en este mismo censo dos agentes inflaron niveles (dieron por retirado un
  HA que sigue en marcha y por accionada una TV que nunca se tocó). Por eso el índice exige evidencia.

## 22–25 · Hitos y condiciones de lanzamiento (aceptación de R1)

AURA se acepta —su «lanzamiento», en lenguaje del mandato— solo cuando, **integrada y en uso
real**, demuestra: recuerda (CM2 ≥90 % a 4 semanas) · conversa en tiempo (CM1) · actúa y verifica
(CM3 ≥95 % en lista verde, 100 % HITL en roja) · anticipa (CM4) · permanece gobernada y segura ·
se mantiene operativa. Los puntos 5–6 del mandato (ver, reconocer) son **R4/R3**, no condiciones del
lanzamiento según la Bible.

## Regla de actualización

Cada viernes: actualizar `capacidades.json` con la evidencia de la semana, recalcular, anotar el
delta del índice y mover las semanas del cronograma según lo medido. Un nivel sube solo con su
evidencia; si baja, se dice.


---

## Registro de actualizaciones

| Fecha | Bloque | Evidencia | Índice lanzamiento | Índice completo |
|---|---|---|---:|---:|
| 2026-09-27 | Línea base del censo | 76 capacidades, 3 censos independientes + medición propia | 69,9 % | 57,6 % |
| 2026-09-27 | **S1 · Voz presente** | TTS precargada (turno de voz 25 s → 7,4 s); palabra de activación por el aire 22/24 con 0 falsos positivos; bucle completo «Oye Aurora» → «¿Sí?» → «¿Cómo me llamo?» → «Te llamas Mauricio»; 30/30 mutantes | **71,7 %** | **58,9 %** |

**Lo que AURA hace desde el bloque S1 que antes no hacía:** está atenta sin que nadie pulse nada, y
cuando alguien dice «Oye Aurora» contesta «¿Sí?», escucha, recuerda y responde por el altavoz.
**Pendiente de S1:** las dos ramas con `*` (TV: pulsar «Permitir»; voz → orden reversible: decisión).
| 2026-09-27 | **S2 · Umbral de integración + entorno** | «¿Qué hay conectado?» por voz y por el aire, descubriendo la red real (router + 2 televisores Samsung + 1 equipo sin identificar); órdenes de hogar interpretadas por el Core con efecto verificado y recordadas sin reejecutar; voz→acción detenida en la frontera; el modelo ya no elige el dispositivo; honestidad del hogar simulado (D-ADP-1) en los dos caminos; 2 ALTOS de seguridad corregidos; 72/72 mutantes | **72,5 %** | **59,4 %** |

**Lo que AURA hace desde el bloque S2 que antes no hacía:** cuando le preguntan «¿qué hay conectado?»,
descubre la red en ese momento y distingue lo que ha **descubierto**, lo que ha **identificado**, lo
que está **integrado** y lo que puede **controlar**; recuerda lo que hizo en casa sin volver a hacerlo;
y ya no deja que el modelo decida qué dispositivo tocar.

**Bloqueos que quedan de S2:**
- **TV real:** pulsar «Permitir» en la TV y ejecutar `~/aura-hogar/emparejar-tv.sh`. Hay además una
  **segunda TV** (Samsung 6 Series 55") que emparejar si se quiere.
- **Voz → acción:** el camino completo está construido y probado; la ejecución real por voz está
  detenida por diseño hasta la decisión del CEO (llave `voz_actua_en_hogar`, apagada).
- **Transcripción por el aire de «Apaga la tele»:** con voz sintética se oye «Para la tene». Hay que
  medirlo con voz humana real antes de concluir.
- **Latencia (CM1):** `AURA_WHISPER_MODEL=tiny` transcribe ~2,2× más rápido con algo menos de
  precisión; el turno sigue muy por encima de 800 ms en HC-1.
| 2026-09-27 | **Cierre S2 · integración física** | TV sala real emparejada («Permitir» pulsado por la persona) y actuada por AURA por la vía autorizada (texto, M1): on→off y off→on releídos en HA; «¿qué hiciste?» recupera la acción física sin reejecutarla; dato personal sobrevive a cambio de tema y reinicio; inventario real: .29 «controlable»; 6 defectos encontrados con el mundo real y 1 MEDIO de la auditoría independiente, corregidos; 36/36 mutantes S2 + 10/10 M8 + 31/31 campaña + 14/14 voz | **72,9 %** | **59,7 %** |

**EFECTO FÍSICO DEMOSTRADO `[EJEC]` (2026-09-27, TV sala Samsung UN43RU7100FXZA, 192.168.20.29):**
- `apaga la tele` → «Hecho: apagué … Estaba «on» y ahora está «off»; lo he comprobado.» (1,2 s; 8,6 s; 10,1 s).
- `enciende la tele` → off→on confirmado (5,2 s; 9,2 s). Un intento con espera de 5 s se contó con
  honestidad como «no cambió» → la espera de confirmación pasa a 15 s (sale en cuanto cambia).
- Estado releído en Home Assistant tras cada orden; la TV quedó apagada, como estaba.

**CAMINO TÉCNICO PREPARADO (sin efecto físico, por diseño):**
- Voz → intención → propuesta → «sí» → frontera → bloqueo. La llave `voz_actua_en_hogar` sigue
  **apagada**. *El camino técnico está construido; la ejecución física por voz requiere decisión
  explícita del CEO.*
- Por el aire (voz **sintética**, no humana), con HA y TV reales: la TV no se movió. Hallazgo para la
  decisión: ante audio confuso Whisper **fabrica frases de su vocabulario** («Sí.» → «¿Qué hiciste?»);
  con órdenes en el `initial_prompt` podría fabricar una orden no dicha. Condición previa a la llave.

**Defectos encontrados por el uso real y corregidos (RED → GREEN → mutante):**
«¿qué hiciste?» contestaba el historial del ciclo (P-018) en vez de la acción recién hecha (S2-M24/25/33);
el inventario no casaba «[TV] X» con «X (MODELO)» de HA ni prefería `media_player` a `remote`, y olvidaba la
TV al apagarse (S2-M26..29); un timeout de HA se contaba como «fallo del sistema de archivos» (S2-M30/31);
espera de 5 s insuficiente para una TV despertada por red (S2-M32); eco de Whisper «X? X?» (S2-M34/35); auditoría independiente (MEDIO): una conexión rechazada al enviar la orden también se llamaba «sistema de archivos» (S2-M36);
`emparejar-tv.sh` esperaba 90 s aunque el emparejamiento ya estuviera hecho.

**Estado al cierre de S2:**
| | |
|---|---|
| Terminado | Hogar real por texto con efecto verificado; recuperación de la acción; entorno con 4 niveles contra la red real |
| Parcial | Voz humana real sin medir en este cierre (solo síntesis, con la máquina cargada: turnos de 21–314 s, no representativos) |
| Bloqueado | Latencia CM1 ≤800 ms en HC-1 (acta D-4) |
| Decisión CEO | Llave voz→acción; persistencia de resultados tras reinicio (tras reiniciar, «¿qué hiciste?» responde el historial del ciclo); segunda TV (.20) |
| Siguiente hito | Prueba con voz humana real («Oye Aurora» / «¿Qué hay conectado?» / «¿Qué te dije antes?» / «Apaga la tele» solo como reconocimiento) y vocabulario de Whisper sin órdenes antes de proponer la llave |
| 2026-09-27 | **S2 · Mapa vivo + endurecimiento** | Diagnóstico `[EJEC]` del entorno (la pérdida está en el descubrimiento pasivo, no en el inventario); nivel CARACTERIZADO, capacidades y superficies de presencia; clasificación honesta (la PS5 ya no es «altavoz»); vocabulario de voz sin órdenes ni confirmaciones; credencial/caída de HA nombradas; 115/115 mutantes en 5 catálogos | **72,9 %** | **59,7 %** |

**Lo que AURA hace desde este bloque:** a «¿Qué hay conectado?» responde también **dónde puede estar hoy**
(este equipo: escuchar y hablar), qué superficies son **solo posibles** (TV: hablar y mostrar, sin integrar ni
autorizar) y **cómo mira y qué no puede ver**. Niveles sin cambio: la evidencia nueva corrige y hace honesto
lo existente; no añade capacidad.

**Decisión CEO abierta (entorno):** para ver lo que no se anuncia (DVR .80, PS5 .36, cámara .110, iOS .93…)
hay que elegir método: registro manual, descubrimiento propio de Home Assistant o lista de clientes del router.
| 2026-09-27 | **Capa de conocimiento del entorno** | Fuentes = evidencia (no verdad); estados DESCUBIERTO→IDENTIFICADO→CARACTERIZADO→INTEGRADO→AUTORIZADO→CONTROLABLE→EFECTO_VERIFICADO; el efecto real del Motor realimenta el conocimiento; conflictos entre fuentes marcados sin adivinar; router y Bluetooth como fuentes preparadas-pero-bloqueadas, declaradas; demo real | **72,9 %** | **59,7 %** |

**Lo que AURA hace desde este bloque:** trata cada fuente (ARP, mDNS, SSDP, HA, equipo local; mañana router
o Bluetooth) como **evidencia** y fusiona; sube a **EFECTO_VERIFICADO** solo cuando el Motor comprobó un
efecto real (no por descubrir); **marca conflictos** en vez de elegir; y **declara las fuentes que aún no
aporta** para que su silencio no se lea como «la casa está vacía». Los 11 equipos reales son casos de
prueba, no inventario. Índice sin cambio: esta capa hace honesto y robusto lo existente, no añade nivel.

**Fuentes:** activas = ARP, mDNS, SSDP, Home Assistant, equipo local. Preparadas-pero-bloqueadas =
**router** (no_autorizada: daría los clientes DHCP si el CEO inicia sesión) y **Bluetooth** (bloqueada por
software; rfkill). El descubrimiento **activo** de red queda como decisión CEO: no se implementó.
| 2026-09-27 | **Vía de integración por dispositivo** | Para cada equipo no integrado, AURA dice la vía legítima y qué falta (resolución de fallos), sin sondear ni romper pairing; visión, frames, control de consola y voz→acción quedan declarados tras sus fronteras | **72,9 %** | **59,7 %** |

**Lo que AURA hace desde este bloque:** ante «¿Qué hay conectado?» ya no solo lista; para lo que aún no
controla dice **cómo se conectaría legítimamente y qué falta** (emparejar la TV, credencial+visión para
cámara/DVR, servicio de control para la consola, o «método desconocido» para lo que solo responde a ARP).
Índice sin cambio: es conocimiento honesto, no capacidad física nueva; visión y voz→acción siguen tras
sus fronteras de gobierno.
| 2026-09-27 | **Percepción visual — primera grada** | Acta CEO ratifica la Decisión A; AURA recibe un FRAME real de su cámara local por su propio código (640×480, persona=None, identidad=None, 0 ficheros); detección e identidad quedan como frontera de DISEÑO elevada por ALERTA-002 | **72,9 %** | **60,1 %** |

**Lo que AURA hace desde este bloque:** con la cámara local puede **recibir un frame** y decirlo con honestidad
(«frame ambiental 640×480; no detecto personas ni identifico»). Es la grada 1-4 del acta (cámara→…→frame),
procesada local, sin guardar imagen. El índice completo sube (visión R4: nivel 1→3 por evidencia real).
**Detención en frontera:** detección de personas e identidad chocan con ALERTA-002 (sin perfiles de terceros)
y con la retención (§10 del acta); su representación es una decisión de diseño que se documentará y elevará
antes de implementarse. Cámaras de red y DVR: REQUIERE CREDENCIAL del propietario.
| 2026-09-27 | **Cámaras/DVR por RTSP — adaptador listo** | Adaptador RTSP que enchufa en el puerto de percepción (secreto nunca filtrado, sin almacenar, libera por captura), probado con abridor inyectado; .110 y .80 REACHABLE pero el stream exige credencial del propietario; persona/identidad = frontera de diseño | **72,9 %** | **60,1 %** |

**Lo que AURA tiene desde este bloque:** el camino para recibir un frame de una cámara de red o del DVR
está construido y probado (`camara_rtsp.py`, 5/5 mutantes) sobre el mismo puerto que la cámara local. **No
hay frame real de red todavía**: `.110` (RTSP TAS-Tech) y `.80` (RTSP H264DVR) responden, pero DESCRIBE/PLAY
exige usuario/contraseña del propietario — bloqueo `REQUIERE CREDENCIAL`, no técnico. Detección de persona e
identidad siguen como frontera de diseño (ALERTA-002 / retención). TV .20 CONGELADA: no se tocó.
| 2026-09-28 | **Política por superficie + DVR autenticado** | Corrección CEO: la seguridad de cámara pasa de bloqueo GLOBAL a política POR CANAL (deny-by-default, evento≠persona≠identidad); PercepcionVisual no captura si la superficie no está autorizada; DVR .80 autenticado por RTSP y 8 canales enumerados SIN decodificar imagen | **73,0 %** | **60,3 %** |

**Lo que AURA tiene desde este bloque:** una **política por superficie** (`politica_superficie.py`): cada
canal del DVR es una superficie con zona/propósito y permisos separados (visual/persistencia/identidad/
acción); lo no autorizado se deniega y la percepción **ni toca la cámara**. Un canal privado ya NO bloquea
los exteriores (mutante PS-M5 lo garantiza). El DVR .80 **autenticó** por RTSP y expone **8 canales** (SDP,
sin imagen). **Falta para capturar un frame exterior:** que el propietario declare qué canal es exterior vs
privado, para que la política autorice esa superficie; la identidad biométrica sigue como frontera aparte.
| 2026-09-28 | **FRAME → OBSERVACIÓN (conectada)** | DP aprobado (Alt B/bajo demanda/imagen-cero) e implementado: la percepción deja de ser una isla — una `LecturaVisual` se vuelve `Observacion` consumible por el orchestrator, efímera, gobernada por política; «¿qué ves en la cámara local?» responde con evidencia real 640×480, sin persona/identidad/evento/imagen; 6/6 mutantes | **73,0 %** | **60,8 %** |

**Lo que AURA hace desde este bloque:** por primera vez la percepción visual **entra al sistema**: a
«¿qué ves en la cámara X?» AURA captura un frame **bajo demanda** de una superficie autorizada y responde
con una observación honesta (fuente + dimensiones; «no interpreto contenido ni identifico a nadie»), sin
guardar imagen, sin memoria, sin evento. Antes el frame se descartaba en `obs.log`. Índice completo sube
(visión R4: 3→5 por comportamiento demostrado E2E). Gradas siguientes (evento/persona/identidad) siguen
cerradas, cada una con su propio DP.

### 2026-09-29 · CM1 bloque iGPU + TTS alternativa — CM1 NO ALCANZADO (medido E2E)

**Evidencia:** `milestones/m3-entry/RESULTADO-CM1-HW-ACCEL.md` + `evidencia-cm1-hw/`. Se midió de fin de habla a inicio de
la respuesta hablada, por el aire, con AURA real.

**Resultados:**
- Camino por defecto: P50 **32,1 s**. El «7,4 s» de §3 era de otras condiciones y queda superado por esta medición.
- Mejor vía rápida (espeak + Vosk): P50 995-1070 ms, con 0 respuestas correctas y corrupción de memoria; se retiró.
- iGPU UHD 600: GPU HANG. OpenVINO CPU: 50 s (solo SSE4.2).
- Queda en el producto: espeak-ng como motor **opcional** (el defecto es Piper) y dos flags de latencia de audio que quitan
  ~2 s de búfer.

**Índice:** no cambia ningún nivel. Voz sigue en 5 por comportamiento E2E; CM1 sigue ❌.

**Cadena bloqueada:** CM1 → aceptación R1 → R2 → R3 → R4, por la decisión de hardware (vía 3), no autorizada.

### 2026-09-29 · AURA conoce su sobre de hardware (DetectorHardware real, ADR-0021/0020)

**Qué cambió:** hasta hoy, el Capability Manager decidía con un perfil VACÍO (`ram_mb=0`). Ahora AURA **mide** su propio equipo
al arrancar: RAM, núcleos, ISA (AVX/AVX2…), GPU, disco y carga. Lo declara en `--verificar` y en el audit log, y el Manager decide
sobre eso. En HC-1 la memoria sigue en N1, ahora **por medición** (3719 MB < 8000). En un equipo con ≥ 8 GB **ampliaría sola** a N2
(probado con un detector simulado; no hay equipo real para medirlo).

**Evidencia:**
- `adapters/detector_hardware.py`;
- auditoría independiente APROBADO CON OBSERVACIONES, con todas corregidas;
- mutación 17/17;
- Quality Gate con delta 0 (2641 passed; los 2 fallos son previos).

**Índice:** lanzamiento 73,0 → **73,2 %** · completo 60,8 → **60,9 %** (dimensión A: 70,8 → 73,3).

**Siguiente puerta:** `milestones/m3-entry/DP-CAPACIDADES-POR-HARDWARE.md`, que pide al CEO las decisiones D46 para que voz y
razonamiento también se adapten al sobre.

### 2026-10-06 · Cierre del bloque «latencia + robustez voz → acción física» (S2, rama voz→acción)

**Evidencia:** `milestones/m3-entry/evidencia-latencia-voz/RESULTADO-LATENCIA-Y-MODELO.md` (§7, cierre) +
`e2e-latencia-2026-10-06.jsonl` + `evidencia-voz-accion/e2e-fisico-2026-10-04.jsonl`.

**Qué cambió:**
- **Voz→TV demostrado por el aire con voz humana.** DP-VOZ-ACCION opción C:
  - 2026-10-04: encendido y apagado de la TV de la sala;
  - 2026-10-06: apagado medido.
  - El bloqueo de S2 «voz → acción» queda resuelto.
- **Latencia** (turnos «apaga» comparables, de «¿Sí?» a la respuesta):
  - orden: 16,1 → 12,3 s;
  - confirmación: 19,3 → 12,3 s (−36 %).
- **Mejoras que explican el ahorro:**
  - captura con fin de habla;
  - «¿Sí?» cacheado: 1,1 → 0,55 s;
  - precarga de los modelos de voz;
  - nombre humano en la respuesta («la TV de la sala»): la síntesis baja de 5,2 a 1,5 s.
- **Robustez:** 5 casos sin prueba propia en el camino hablado ahora la tienen; cada uno con mutante de control (VR-M1..M4 4/4 + VE-M5). Son: «sí» sin propuesta, TV
  inexistente, TV `unavailable`, PARADA previa y turno vacío.
- **Modelo:** se mantiene qwen2.5:0.5b. qwen2.5:1.5b se evaluó (más lento, el doble de RAM, fabrica acciones) y **se
  eliminó** (986 MB).

**Niveles e índice:**
- La capacidad «Orden por voz → dispositivo sin pasar por el modelo» sube de **4 a 5** (demostrada E2E).
- Índice de lanzamiento: 73,2 → **73,3 %**. Índice completo: 60,9 → **61,0 %**.

**CM1 sigue ❌ (bloqueo nº 1, sin cambios):** P50 de fin de habla a respuesta ≈ **7,9 s** frente a ≤ 800 ms. El cuello de
botella es ahora el STT (Whisper base ≈ 5,5 s por turno en HC-1). Mejorar no es cumplir; el umbral no se cambia.

**Siguiente bloque según §16:** S3 · «Memoria en la vida real» (reloj de CM2), que espera la decisión del CEO en
`milestones/m3-entry/DP-S3-RELOJ-CM2.md` §7.

### 2026-10-07 · S3: mecanismo listo, medición NO iniciada

- **Implementado y validado `[EJEC]`:**
  - reloj de CM2 (`core/reloj_cm2.py`), con origen efectivo `max(valid_from, inicio)`;
  - puerta ADR-0014 por vigencia;
  - T11 y T11b: un turno de soberanía no deja eco ni captura señales.
- **Calidad:**
  - mutación: 4/4 (puerta), 4/4 (olvido) y 32/32 (reloj);
  - Quality Gate PASS: 3230 passed, 1 skipped, 17 xfailed.
- **Preparado y no activado:** `PROCEDIMIENTO-INICIO-CM2.md`. El inicio y la ventana de 4 semanas naturales esperan la
  orden del CEO.
- **Bloqueado por decisión formal** (`CONTRATO-OLVIDO-Y-RETENCION.md` v2, §5 y §2):
  - borrado físico (Bible 5.5 §3 frente a ADR-0023, G-6 y G-7);
  - D-N2-5 (G-1 + gate del CEO; parche en `propuestas/`);
  - T8 `restore`;
  - T13, ventana de diálogo (DR-4: privacidad no decidida).
- **Siguiente actividad del §16:** iniciar la medición de S3 cuando el CEO lo ordene.
- **Corrección 2026-10-07 (Director):** la línea anterior decía «En paralelo, S4–S5 (M3.2b)» como rama sin decisión.
  **Era falso.** M3.2b está **congelado por el CEO**: acta fundacional del 2026-07-21, §1 («hasta disponer de entorno
  doméstico y datos reales suficientes»), con §2/D34 (no construir infraestructura no validable) y D39. Datos reales
  medidos `[EJEC]` (agregados, sin contenido): 11 hechos declarados, **0 preferencias observadas**, actividad en 2 días
  (septiembre). La condición no se cumple; levantar la congelación es decisión del CEO.

### 2026-10-18 · Sincronización con el estado real (sin cambiar el orden del §16)

- **Cerrados después del 2026-10-07 y no reflejados aún en el mapa** (evidencia en `CHECKPOINT-CONTINUIDAD.md`):
  D-AMP-2 Memory Context Builder (10-11, acta `decisiones/2026-10-11-D-AMP-2-aprobacion-construccion.md`) · M3.2a
  exportar (10-11, VERIFICADO) · D-M-1 A′ recuperación exacta (10-12, QG PASS) · avisos de NODO-01 R1 (10-18,
  `milestones/m3-entry/CIERRE-AVISOS-NODO-01-R1.md`, QG PASS 3290, mutación 12/12). NODO-01 v1 (10-04,
  `RESULTADO-NODO-01.md`) tampoco figura. **No se recalculan índices ni niveles** de `capacidades.json` en esta
  entrada (la regla exige evidencia por nivel; queda pendiente del recálculo semanal).
- **S3 — corrección de estado `[EJEC]`:** el reloj de CM2 **está iniciado** (1 evento `cm2.inicio`, 2026-10-07T22:46:52Z;
  CHECKPOINT ~8574-8603, «autorización operativa delegada»). La línea «medición NO iniciada» de la entrada anterior
  quedó desfasada.
- **S3 — la medición no está corriendo `[EJEC]`:** **0 eventos `cm2.sonda`** en el audit log. Las sondas (días 7, 14 y
  28; `core/reloj_cm2.py:47`) solo se ejecutan con `python -m aura_skeleton --medir-cm2`, que «debe lanzarse en cada
  ventana; no hay proceso residente» (`PROCEDIMIENTO-INICIO-CM2.md:49-50`); no hay cron que lo haga. Día 7 vencido
  (10-14), día 14 el 10-21, ventana de día 28 del 11-04 al 11-11. **Gate de S3 («registro CM2 funcionando») NO cumplido.**
- **Gobierno:** el inicio de CM2 se registró como «autorización operativa delegada»; el mismo día el CHECKPOINT
  (~8296-8365) exigía orden explícita del CEO → pendiente de ratificación por el CEO (el inicio es irreversible).
- Siguiente actividad del §16 sin cambios: **S3**. Paralelo permitido sin decisión: ninguno (S4–S5 congelado; S5 `*`).

### 2026-10-18 (tarde) · S3: inicio de CM2 ratificado · medición automatizada · población vacía

- Ratificación del CEO del inicio del 2026-10-07 (`decisiones/2026-10-18-acta-ratificacion-inicio-cm2.md`).
- **Corrección de la entrada anterior:** no había sondas vencidas. La población de CM2 está vacía (0 `cm2.hecho_registrado`):
  los hechos de septiembre son anteriores al mecanismo y no se ha declarado ninguno desde el inicio.
- `--medir-cm2` ejecutado (exit 0, sin escrituras) y **cron diario de usuario** instalado (21:30; idempotente, sin solape,
  aplaza si AURA principal vivo). Gate S3: mecanismo listo; **sin datos** hasta que haya hechos declarados en uso real.
- Orden del §16 sin cambios; niveles de `capacidades.json` sin recalcular.

### 2026-10-18 (noche) · S3: primer ciclo automático observado · política de población D-CM2-1

- Cron diario ejecutado a las 21:30 (exit 0): **ejecución sin datos** (0 hechos elegibles, 0 sondas). No es medición válida.
- Política de población del CEO: `decisiones/2026-10-18-D-CM2-1-politica-poblacion-espontanea.md` — solo hechos
  espontáneos del uso real; sin siembra ni importación de históricos.
- Gate S3 abierto: necesita uso real con hechos declarados y ≥20 sondas válidas de día 28. Orden del §16 sin cambios.

### 2026-10-21/22 · Umbral en una conversación hablada · ecosistema doméstico: volumen y silencio · voz por el modelo cerrada

- **Punto del cronograma:** §16 tiene S1-S2 técnicos cerrados, S3 en espera de uso real, S4-S5 congelado (M3.2b) y S5
  pendiente de decisión (D33). El trabajo de esta entrada cierra huecos del **umbral de integración** (§14) y abre el
  **ecosistema doméstico** por acta del CEO (`decisiones/2026-10-22-acta-ecosistema-domestico.md`, D23). El orden del §16
  no cambia.
- **Umbral en UNA conversación hablada `[EJEC]` (dobles):** recordar lo declarado → «apaga la tele» → «sí» → efecto
  releído → «¿qué hiciste?» y «¿apagaste la tele?» recuperan lo ocurrido sin reejecutar. Defecto corregido: «¿apagaste la
  tele?» por voz respondía «no entendí la orden». Evidencia: `tests/integration/test_umbral_una_conversacion_voz.py` (15),
  mutación 5/5, QG PASS 3305.
- **Volumen y silencio de la TV:** 4 capacidades verdes y reversibles, con el atributo releído antes y después. No se
  envía nada si la TV está apagada o el valor no es legible; «ya estaba…» cuando no cambia nada; «la tele de la sala» se
  resuelve por el nombre humano ya fijado. Por voz siguen fuera de la opción C (decisión pendiente, acta §5). Mutación
  17/17 y re-mutación de los TOML afectados 107/107. QG PASS 3392.
  - **Real `[EJEC]` contra el HA de la casa, TV apagadas:** «sube el volumen de la tele de la sala» → «está apagada», 0
    servicios enviados; «sube el volumen» → nombra las 2 TV y pregunta cuál. **El efecto positivo real está PENDIENTE**
    (TV encendida y lectura de `volume_level` legible).
- **Seguridad, defecto anterior a esta entrada cerrado `[EJEC]`:** una frase HABLADA sin activación que la gramática no
  reconocía bajaba al modelo, y el Motor apagaba la TV sin propuesta ni «sí» (opción C esquivada). Ahora, por voz, el modelo
  nunca actúa en casa: `tests/integration/test_voz_no_actua_por_el_modelo.py`, mutante M17.
- **Inventario real (solo lectura):** HA 2026.2.3 con `samsungtv` ×2 (`supported_features` 24509: volumen, silencio,
  fuente, reproducción). Con las TV apagadas no se exponen atributos de volumen ni de contenido. PS5: 0 respuestas DDP
  (búsqueda dirigida de PlayStation, puertos 9302 y 987) a la 00:5x; no es concluyente. No hay cámaras, móviles ni relojes
  en HA. «Declarado ≠ real» corregido en `MAPA-ECOSISTEMA-FISICO.md:48`.
- **Niveles e índice** (`herramientas/indice_madurez.py`): nueva capacidad «Volumen y silencio de la TV con verificación
  del efecto» en **nivel 4** (integrada, sin E2E positivo real). Lanzamiento 73,3 → **73,2 %** (Core 87,1 · Ready 59,2);
  horizonte completo **61,0 %**. Los demás niveles no cambian: M8 y la orden por voz solo ganan evidencia.
- **Siguiente:** demostrar el volumen en real con la TV de la sala encendida y una persona presente; consulta de estado
  «¿qué está poniendo la tele?» (`source`, `app_name` y `media_title`, si HA los expone con la TV encendida); descubrimiento
  ampliado con `red_local` (mDNS/SSDP) para el inventario.

### 2026-10-22 (mañana) · Consulta del estado de la TV contra el HA real · inventario observado · autonomía sin PC: bloqueo de hardware

- **Misión A (volumen real):** las dos TV estaban **apagadas** a las 06:16 (HA `off`; la de la sala desde el 20-10). No se
  encendieron. El efecto positivo real del volumen sigue **PENDIENTE**.
- **Misión C, subpaso hecho — consulta del estado de la TV (solo lectura, sin modelo ni Motor):** «¿está encendida /
  apagada la tele de la sala?», «¿a qué volumen está?», «¿qué está poniendo?».
  - Respuesta: lo que HA da se dice como observado, con su fuente y la hora local de `last_changed`; lo que falta, como
    desconocido. Con la TV apagada no se da ningún valor viejo.
  - Privacidad: el título no se dice por voz ni se audita.
  - PARADA echada: se responde, avisando.
  - **Real `[EJEC]`:** «No: la TV de la sala está apagada (según Home Assistant, desde las 17:38 del 20-10)»; con la TV
    apagada, el volumen y el contenido salen como «no lo sé»; si no se dice cuál, pregunta cuál. 3 lecturas y 0 acciones.
  - Calidad: mutación 16/16, QG PASS 3433.
  - **Defectos corregidos por ECC:** el «Sí/No» contradecía «¿está apagada?» (ALTO); las pruebas de la hora dependían de la
    zona de la máquina (MEDIO); faltaba cubrir `playing`, `paused`, `idle` y `standby`.
- **Misión B, inventario:** ver `milestones/m3-entry/MAPA-ECOSISTEMA-FISICO.md` §6.
  - Confirmados: el router, las 2 TV (por HA) y el DVR .80, que responde y no se toca.
  - Sin respuesta a las 06:16: teléfonos, cámara .110, ULooka y la PS5 (DDP). No es concluyente.
  - Relojes y auriculares: no visibles por IP. Bluetooth está bloqueado por software en este equipo y la nube la excluye D24.
- **Autonomía sin el PC `[EJEC]`:** Home Assistant escucha solo en 127.0.0.1 de HC-1, y NATS y el receptor de nodos también
  corren en HC-1. Sin el PC no hay hogar. NODO-01 (Atom N450, 32 bits, 986 MB) no alcanza para alojarlos. **Bloqueo de
  hardware:** hace falta un nodo de 64 bits siempre encendido (decisión del CEO). No se declara ninguna independencia.
- **Niveles e índice:** nueva «Consulta del estado de la TV» en **nivel 4** (el camino real solo con la TV apagada; nivel 5
  al leerla encendida). Lanzamiento **73,1 %** (Core 87,1 · Ready 59,0); horizonte completo **61,0 %**.
- **Siguiente:** con la TV de la sala encendida y una persona presente, una sola sesión cierra dos capacidades a nivel 5:
  (1) leer el estado real (volumen, fuente, aplicación); (2) subir y luego bajar el volumen para dejarlo como estaba.

### 2026-10-22 (mañana, 2) · Cámara por la vía de la decisión A · descubrimiento ONVIF/DDP · errores de hogar en lenguaje humano

- **TV:** sigue apagada; el volumen positivo real continúa **PENDIENTE**, sin forzarlo.
- **Cámara .110 (decisión A, acta 2026-09-27; DP de percepción multimodal APROBADO E IMPLEMENTADO desde el 28-09):** la
  integración YA existía (`CamaraPyAV`/`AudioRTSP` + `PercepcionBajoDemanda` + política de superficie deny-by-default).
  - **06:5x** no respondía, ni siquiera por ARP. **07:12** volvió y la encontró el descubrimiento nuevo de AURA: ONVIF, con
    una identidad cuyo sufijo es su MAC, y RTSP 554 abierto. Estado: **accesible**.
  - **No se capturó ningún frame:** hacen falta la activación del propietario (`AURA_CAMARA_RTSP`, superficie «interior»;
    ningún lanzador la define) y su presencia (criterio E2E del DP §21). La identificación de personas sigue sin autorizarse
    (decisión B).
- **Avance funcional:**
  - (1) `red_local` produce por fin `tipo_declarado`/`identidad`, que el Core ya consumía y nadie alimentaba:
    WS-Discovery/ONVIF (cámaras) y DDP (PlayStation), dirigidos, sin seguir URL, sin el juego en curso, solo de la LAN
    privada y con tope global. AURA encuentra una cámara aunque cambie de IP.
  - (2) Los errores de hogar se dicen sin nombres técnicos («No he podido subir el volumen: … está apagada»).
  - (3) Inventario: una declaración UDP que contradice el tipo ya deducido se marca como conflicto y no pisa nada.
- **Corrección de «declarado ≠ real» a la baja:** «Captura de cámara» estaba en nivel 2 («fuera de AURA»); la hace AURA
  desde el 27-09 → nivel **5**, solo la cámara local.
- **Calidad:** mutación del descubrimiento 17/17, semana 2 66/66. ECC: code-reviewer APROBAR; security-reviewer, APTO tras
  cerrar un ALTO (envenenamiento) y dos MEDIO (inundación, hilos). Queda una limitación MEDIA documentada (primera ronda de
  fusión). QG PASS 3459.
- **Índice:** lanzamiento **73,1 %** (sin cambio); horizonte completo **61,7 %** (+0,7, solo por la corrección de nivel).
- **Siguiente:** con el propietario presente, activar `AURA_CAMARA_RTSP` para la .110 y preguntar «¿qué ves en la cámara?»
  (observación ambiental, efímera, sin persona). Volumen real cuando haya TV encendida. Opcional: enriquecer ONVIF con
  `GetDeviceInformation` en la misma IP y cerrar la limitación de la primera ronda.

### 2026-10-22 (tarde) · Fusión del inventario independiente del orden · etiqueta ≠ control · cámara sin nombre

- **Limitación MEDIA de la primera ronda: CERRADA.**
  - **Causa raíz** (`core/entorno.py` `_fusionar`): la última declaración ganaba sobre el tipo deducido (y la identidad, al
    revés: ganaba la primera), el nombre del declarante pisaba el anterior y dentro de la ronda no existía la noción de
    conflicto. Era dependiente del orden.
  - **Corrección** (diseño aprobado por arquitecto-evaluador): agrupar por IP, juntar primero las fuentes no declarativas,
    deducir el tipo y después evaluar las declaraciones (ONVIF, DDP; UDP sin autenticar). Si contradicen al deducido o
    entre sí (tipo o identidad), es conflicto y no se adopta nada. Ahora es independiente del orden.
  - **Misma regla dentro de la ronda y entre rondas.** La PS5 que solo anuncia Spotify sigue identificándose por su DDP.
- **Etiqueta ≠ control:** un nombre que solo llega por una declaración UDP no casa con una entidad de HA. Antes, un
  impostor en una IP silenciosa podía hacer que `describir` dijera «lo controlo» (INV-9, security-reviewer).
- **Comprobado `[EJEC]`:** el inventario NO se persiste y ninguna acción resuelve por su nombre. La severidad era MEDIA
  (etiqueta y voz) y ya está cerrada.
- **«¿Qué ves en la cámara?» sin nombre:** antes caía en «No tengo ningún recuerdo». Ahora pregunta cuál y enumera solo las
  cámaras AUTORIZADAS, sin capturar. `[EJEC]` en la composición real: «¿Qué cámara? Puedo mirar: «local»».
- **Cámara .110:** en línea (RTSP abierto a las 10:19). **Sin captura:** sigue faltando la activación con el propietario
  presente. Procedimiento exacto en `milestones/m3-entry/MAPA-ECOSISTEMA-FISICO.md` §6.2.
- **Calidad:** mutación de la fusión 12/12, cámara sin nombre 6/6 y descubrimiento 17/17 (re-ejecutado). QG PASS 3487.
  ECC: arquitecto ENCAJA; security-reviewer, limitación CERRADA y APTO; code-reviewer, APROBAR CON CAMBIOS (2 MEDIO
  corregidos).
- **Observaciones, no deuda:**
  - Un conflicto no se borra hasta reiniciar (DoS de etiqueta, solo texto).
  - Una IP solo-ARP adopta la primera declaración.
  - «¿Qué oyes en la cámara?» y «¿hay movimiento?» sin nombre tienen el mismo hueco.
  - La superficie de red se llama «camara»: darle un nombre propio es configuración del propietario.
- **Niveles e índice:** sin cambios (lanzamiento 73,1 %, horizonte 61,7 %): es un endurecimiento sin capacidad nueva.
- **Siguiente:**
  - (1) Con el propietario presente: la primera captura de la .110 (§6.2). Con una TV encendida: el volumen real.
  - (2) Trabajo autónomo: el mismo arreglo para audio y evento sin nombre (~1-2 h); enriquecer ONVIF con
    `GetDeviceInformation` en la misma IP, sin autenticación (~2-4 h).

### 2026-10-22 (mediodía) · Inventario contrastado con el propietario · la .110 es un dormitorio (elevado) · ONVIF GetDeviceInformation endurecido

- **Inventario** (`MAPA-ECOSISTEMA-FISICO.md` §7-§9): las 7 capturas del propietario se tratan como pistas y se contrastan
  con la red `[EJEC]`. **No se registran secretos:**
  - una captura muestra la contraseña Wi-Fi del extensor;
  - otra, una app con usuario `admin` y contraseña vacía por defecto (posiblemente el DVR; AURA no la prueba; riesgo que
    se comunica al propietario).
- **Privacidad (elevado al CEO):** la .110 se llama «habitacion» (dormitorio). La composición la registra como zona
  «interior», que no está en la lista válida, y existe una autorización del 28-09 dada sin saber que es un dormitorio.
  `DECISION-REQUERIDA-ZONA-CAMARA-110-DORMITORIO.md`; recomendación A (privada = bloqueada salvo acta por canal). El
  procedimiento de captura queda RETIRADO. Hoy el riesgo no está activo (ningún lanzador define `AURA_CAMARA_RTSP`).
- **Avance:** `GetDeviceInformation` ONVIF en la misma IP y sin credenciales. `[EJEC]` La .110 queda identificada por tres
  vías: identidad ONVIF = MAC, ARP = MAC y EYEPLUS/EYEPLUS_DEV/**3.5.1.1108**, que coincide con la captura del propietario.
- **Seguridad** (security-reviewer, APTO tras tres correcciones):
  - el DVR queda excluido explícitamente (`AURA_RED_NO_TOCAR`);
  - anti-SSRF reforzado: IP privada que no sea propia, loopback ni link-local; puertos ONVIF cerrados; sin proxy;
  - el enriquecimiento corre en paralelo con plazo total y nunca se pierde la fuente.
- **Calidad:**
  - Mutación `onvif-informacion` 24/24 (O10 se retiró por equivalente, con su motivo escrito) y
    `descubrimiento-onvif-ddp` 17/17, re-anclados.
  - QG PASS 3512.
- **Autonomía sin PC:** `PROPUESTA-AUTONOMIA-SIN-PC.md` (3 opciones; se recomienda un nodo de 64 bits por fases). Es una
  decisión del propietario.
- **Teléfonos y reloj:** las vías reales están documentadas (app oficial de HA en la LAN; Garmin solo por nube o por un
  puente BLE en Android, con datos de salud) y ninguna está probada.
- **Índice:** sin cambios.
- **Siguiente:**
  - (1) Decisiones del CEO: zona de la .110, nodo de 64 bits, app de HA en un teléfono.
  - (2) Trabajo autónomo: «preguntar cuál» para audio y evento sin nombre (~1-2 h).
  - (3) Con TV encendida: el volumen real.

### 2026-10-22 (tarde) · Rectificación del CEO: todas las cámaras son integrables; la zona es METADATO

- **Decisión:** `decisiones/2026-10-22-acta-camaras-zona-como-metadato.md`. Resuelve
  `DECISION-REQUERIDA-ZONA-CAMARA-110-DORMITORIO.md` y **rectifica** dos entradas anteriores de este registro: la de
  «mediodía» (recomendación A, «privada = bloqueada», y «decisión del CEO: zona de la .110») y la del §331-336 («que el
  propietario declare exterior frente a privado para autorizar»).
- `[EJEC]` Ningún código denegaba por zona: `_permite` solo mira la autorización. La restricción del dormitorio vivía en
  un docstring y en los documentos (declarado ≠ real). Las pruebas nuevas (zona como metadato) lo fijan: ninguna zona
  cambia ningún permiso.
- **Corregido en el código:**
  - la composición ya no se inventa la zona «interior»;
  - el propietario NOMBRA la cámara de red (`AURA_CAMARA_NOMBRE`, saneado y sin poder suplantar a «local») y declara su
    zona como etiqueta (`AURA_CAMARA_ZONA`).
- **Nuevo:**
  - «¿qué oyes en la cámara?» y «¿hay movimiento en la cámara?» sin nombre preguntan cuál y enumeran solo las cámaras
    autorizadas para esa modalidad, sin capturar;
  - el texto dice «puedo intentar», porque la política no comprueba la conexión;
  - sin imagen, la respuesta es «No recibí imagen» y no «No detecté movimiento».
- **Cámara .110:**
  - `[EJEC]` está en línea, con identidad ONVIF (EYEPLUS, firmware 3.5.1.1108), y RTSP `DESCRIBE` responde 200 SIN
    credencial con solo vídeo H264. **No se capturó ningún fotograma.**
  - Para capturar falta que el propietario la active (procedimiento en `MAPA-ECOSISTEMA-FISICO.md` §10).
  - Constancias para el propietario en el acta: rastro de presencia en el audit, terceros en el dormitorio, y RTSP
    abierto sin contraseña en la LAN.
- **Calidad:** mutación `zona-como-metadato` 13/13 y `camara-sin-nombre` 6/6 (re-anclada). QG PASS 3560.
  - security-reviewer: APTO.
  - auditor-consistencia: código alineado; documentos rectificados con esta entrada y con notas en el MAPA y en
    `capacidades.json`.
- **Índice:** sin cambios.
- **Siguiente:** la primera captura de la .110 cuando la active el propietario; el volumen real con la TV encendida; las
  decisiones pendientes (nodo de 64 bits, app de HA, Garmin, retención de los eventos de movimiento).

### 2026-10-22 (noche) · AURA Progress Dashboard

- **Nuevo (herramienta de proceso, no capacidad del producto; fuera de `capacidades.json` por D23):** panel HTML
  estático generado de las fuentes reales. Documentación: `PANEL-DE-PROGRESO.md` (esta carpeta).
- **Rectificado en este mapa:** la tabla del resumen ejecutivo y el recuento por nivel de §5–8 conservaban la línea base
  del 2026-09-27 (69,9 % / 57,6 %, 76 filas). Recalculados con `indice_madurez.calcular` sobre 82 capacidades:
  lanzamiento **73,1 %**, horizonte **61,7 %**; niveles 0:5 · 1:15 · 2:3 · 3:3 · 4:11 · 5:27 · 6:18.
- **Índice:** sin cambios (el panel lo importa; ningún porcentaje se editó a mano).
- **Pendiente del CEO:** nombres para las dimensiones A–Q (no existe mapeo en el repositorio; el panel muestra letras).

### 2026-10-22 (noche, 2) · Veredicto de hogar veraz + panel con procedencia + investigación externa

- **Hogar (dimensión I; niveles SIN cambios, solo evidencia):** la verificación de encender y apagar usa los conjuntos de
  estados de `hogar.py` según la operación (`playing`, `standby`…). Con `unavailable`/`unknown` no se envía nada. Un
  HTTP 4xx/5xx se distingue de «no respondió». El estado asumido de HA no verifica. Toda respuesta nombra a Home
  Assistant como fuente y nunca afirma un efecto físico. Mutación `veredicto-hogar.toml` 24/24. QG PASS 3790.
  Pendiente físico: qué estados reporta la samsungtv real.
- **Panel:** procedencia derivada de la evidencia (`[EJEC]` / solo pruebas / desconocida / sin evidencia). Recuento
  real: 28/14/35/5, y 22 capacidades de nivel ≥ 5 sin ejecución real declarada. El gate de otro commit no se presenta
  como vigente. Consulta privada documentada (`file://` o `127.0.0.1`).
- **Dimensiones A–Q:** propuesta fundamentada `PROPUESTA-NOMBRES-DIMENSIONES.md`, pendiente del CEO (no aplicada).
- **Investigación externa:** `milestones/investigacion-externa/INDICE.md` (IE-000…IE-015). Adoptado solo el concepto de
  estado asumido (IE-002).
- **Índice:** sin cambios (73,1 % / 61,7 %).

### 2026-10-22 (noche, 3) · Verificación física real: TV de la sala y PS5

- **TV de la sala:** «enciende la tele de la sala» por la cadena completa de AURA contra HA real. `off`→`on` releído en
  10,6 s; respuesta «Home Assistant ve la TV de la sala encendida». **PHYSICAL_EFFECT_VERIFIED por estado de HA** (sin
  inspección visual). La TV real reporta `on`, no `playing`. Evidencia: `milestones/m3-entry/evidencia-tv-real-2026-10-22/`.
- **PS5:** despierta (DDP `200 Ok`), solo lectura. AURA no conserva despierta/reposo: capacidad pendiente de decisión
  (D23, IE-005).
- **Niveles e índice sin cambios** (73,1 % / 61,7 %). QG PASS 3790 (19:08).

### 2026-10-22 (noche, 4) · Estado operativo de la PS5 por DDP (D23 / IE-005)

- AURA observa y conserva despierta/en reposo con la hora de lectura (`red_local.observacion_ddp`, `core/entorno`).
  Un error de comunicación nunca se convierte en reposo, y la última lectura válida no se borra. Las contradicciones
  no se adoptan, y el texto dice «lectura, no verificación física». No se envían órdenes: solo `SRCH`.
- Seguridad APTO (MEDIO corregido; BAJO preexistente registrado: el texto de conflicto muestra el host-id). Mutación
  16/16; QG PASS 3811.
- Evidencia: despierta, real; en reposo, **solo simulado**. Niveles e índice sin cambios (73,1 % / 61,7 %).

### 2026-10-22 (noche, 5) · Investigación: DVR «Amtech», evolución de agentes, cámaras (IE-016…IE-031)

- 16 fichas nuevas y una síntesis: `milestones/investigacion-externa/SINTESIS-2026-10-22-DVR-AGENTES-CAMARAS.md`. Nada
  instalado; sin contacto con el DVR.
- DVR `.80`: hipótesis de trabajo **Xiongmai/XMEye (DVRIP)**. El OUI de su MAC es Cisco-Linksys: la MAC no lo
  identifica. Siguiente: el propietario lee modelo, versión y marca en la pantalla del DVR.
- Brecha real `[LECT]`: `autoconstruccion.ejecutar` verifica el candidato **en el árbol vivo** y sin instantánea en
  disco. Patrón IE-028 (copia desechable) propuesto; requiere DP.
- **Niveles e índice sin cambios** (ideas, no evidencia). QG PASS 3811 (21:08).

### 2026-10-22 (noche, 6) · DP: candidato aislado en la autoconstrucción

- Brecha confirmada `[EJEC]` sobre una copia:
  - `autoconstruccion.ejecutar` escribe el candidato en el fichero vivo (L632) y lo verifica con `pytest cwd=raiz`;
  - un SIGKILL durante la verificación deja el candidato, sin respaldo ni evento.
- DP `milestones/m3-entry/DP-CANDIDATO-AISLADO-AUTOCONSTRUCCION.md`: alternativa A (copia temporal + promoción
  atómica + diario) y 10 pruebas planificadas. **Requiere acta del CEO** (toca `autoconstruccion.py` y `review.py`,
  ambos en `_INTOCABLES`).
- **Sin cambios de código**; niveles e índice sin cambios.

### 2026-10-22 (noche, 7) · Candidato aislado en la autoconstrucción: IMPLEMENTADO (alternativa A aprobada)

- `autoconstruccion.ejecutar` ya no escribe el candidato en el árbol vivo antes de aprobarlo:
  - copia temporal → verificación en la copia → promoción atómica bajo cerrojo, con precondición de hashes y diario
    0600 fuera del repo;
  - recuperación validada e idempotente; bloqueo si algo es ambiguo.
- Brecha original cerrada [EJEC]: el vivo intacto durante la verificación y tras SIGKILL.
- Batería del anillo: 1290 passed. Mutación: 38/38 nuevos + 44 + 233 existentes, sin supervivientes. QG PASS 3811.
- Límites declarados: verificador sin parámetros = `verificacion_aislada: False`; ejecución sin confinar. Detalle en DP
  §11.
- Niveles e índice sin cambios.

### 2026-10-25 · Cierre de la misión de aislamiento + corrección de la fila S3

- **Fila S3 del §16 corregida:** decía «no iniciado» y CM2 se inició el 2026-10-07 (CHECKPOINT ~L8583, `cm2.inicio`
  seq 1314). El día 28 del reloj es el 2026-11-04. La tasa solo existe con ≥20 sondas de día 28 sobre hechos
  espontáneos: a 21-10 había 0 (D-CM2-1).
- **Misión de aislamiento del anillo cerrada:**
  - verificación de candidatos en una copia confinada en modo estricto, seguridad APTO;
  - vía sin raíz retirada;
  - QG PASS 3811.
  Es infraestructura del anillo de autoconstrucción y **no cambia el orden del §16**.
- **Estado del cronograma:** S1-S2 cerrados; S3 en espera de uso real (CM2); S4-S5 **congelado** (M3.2b, acta
  2026-07-21); S5 pendiente de D33.
- **Índice:** sin cambios.

### 2026-10-25 (b) · Preparación del gate S3: corrección de la fecha del hito y cobertura del cableado CM2

- **Corrección de la entrada anterior** (se conserva tal cual). «El día 28 del reloj es el 2026-11-04» **no es la fecha
  del gate**: el día 28 se cuenta por hecho, `max(valid_from, inicio)` + 28 d. Ya se había corregido el 2026-10-18 (ficha,
  entrada (r)) y la entrada (q) lo reintrodujo.
- **Cota inferior:** con población 0 en la medición del 2026-10-24 `[EJEC]`, ninguna sonda de día 28 puede existir antes
  del **2026-11-21**. El 2026-11-04 se espera «sin datos suficientes».
- **Fila S3 del §16 corregida** también en el criterio: la «revisión humana» no es condición literal del gate. Es requisito para afirmar fabricación y forma parte de la evaluación del CEO (auditoría de consistencia de hoy). El criterio, la sonda válida y el procedimiento de observación están en
  `milestones/m3-entry/PROCEDIMIENTO-INICIO-CM2.md` §7.
- **Cobertura del cableado:**
  - Hueco medido: el mutante C1 (la composición audita en otro fichero) sobrevivía a todas las pruebas.
  - Cerrado con 3 pruebas `test_produccion_*` en `walking-skeleton/tests/integration/test_reloj_cm2_integracion.py`.
  - Batería `walking-skeleton/mutaciones/cm2-cableado-produccion.toml`: **4/4**.
  - Sin cambios en el código de producción.
- **Índice y orden del §16:** sin cambios.

### 2026-10-25 (c) · Segunda auditoría CM2/S3 y aislamiento de dispositivos en la batería

- **Segunda auditoría de consistencia:** CONFORME. D1-D3 están corregidas y las 5 observaciones menores, resueltas
  (CHECKPOINT (s)).
- **Tabla de clasificación normativa** (PROCEDIMIENTO §7.1.1):
  - el umbral de 20 es **normativo**, por D-CM2-1;
  - la tolerancia de 7 días es un parámetro **sin decisión explícita**, una ambigüedad abierta que espera decisión del CEO.
- **Defecto de la batería (seguridad), corregido:**
  - Con `AURA_HA_URL`/`AURA_HA_TOKEN` en el shell, las pruebas de composición contactaban el Home Assistant heredado:
    1 conexión medida.
  - Corregido con la fixture `_sin_dispositivos_reales` en `walking-skeleton/tests/conftest.py` y la prueba
    `tests/unit/test_sin_dispositivos_reales.py`.
  - Mutación `mutaciones/sin-dispositivos-reales.toml`: 3/3.
- **Migración del cron:** la propuesta de §7.6 queda endurecida (escritura atómica, `AURA_DATOS` de tmp obligatorio,
  comprobación de `WS`). **No ejecutada:** pendiente de autorización.
- **Orden del §16 e índice:** sin cambios. S3 sigue abierto.

### 2026-10-25 (d) · Aislamiento de la batería cerrado: datos, stack y servicios reales

- **Defecto medido:** dentro de la batería, `Configuracion()` valía `~/.aura`, es decir, los **datos reales**. Además, un
  `AURA_STACK_REAL=1` del shell encendía el stack real, y dos pruebas de voz consultaban el **Ollama real** del equipo.
- **Correcciones:**
  - fixture `_sin_datos_ni_stack_reales` en `walking-skeleton/tests/conftest.py`;
  - catálogo de Ollama falso y contado en `tests/integration/test_voz_degrada_con_honestidad.py`;
  - pruebas en `tests/unit/test_sin_dispositivos_reales.py`.
- **Verificación:**
  - barrido completo con shell hostil: 0 conexiones al hogar y centinela de `AURA_DATOS` vacío;
  - traza de `connect()`: solo queda la sonda deliberada de `tests/e2e/test_real_stack.py`;
  - mutación `mutaciones/sin-dispositivos-reales.toml`: **7/7**.
- **Pendiente de autorización (código de producción):** `__main__._ruta_red` trata `AURA_RED=""` como `~/.aura-red`.
  Es latente.
- **Orden del §16:** sin cambios. **S3 sigue abierto:** un PASS de software no es la aprobación de S3.

### 2026-10-25 (e) · `_ruta_red`: batería corregida; cambio de producción especificado y validado (pendiente)

- **Defecto:** `__main__._ruta_red` trata `AURA_RED=""` como ausente y cae en `~/.aura-red`, con la credencial y la PKI
  reales. Dentro de la batería resolvía el directorio real.
- **Corregido en la batería:**
  - fixture `_sin_red_real_por_defecto`;
  - guardia estática para los subprocesos;
  - `walking-skeleton/tests/unit/test_ruta_red.py`;
  - mutación 9/9.
- **Producción sin cambiar:**
  - Propuesta en `milestones/m3-entry/evidencia-cm2-s3-2026-10-25/PROPUESTA-ruta-red.diff`: `""` pasa a ser «sin red».
  - Especificada con dos pruebas `xfail(strict)` y validada en una copia: 2 XPASS y 290 passed.
  - Revisiones de código y de seguridad: APTO.
  - **Pendiente de autorización del CEO.**
- **Riesgo operativo nuevo:** tres procesos de producción ejecutan código del worktree `m3-entry`: el cron de CM2, el
  despertador y el servicio receptor (PROCEDIMIENTO §7.6, ampliación (u)).
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-25 (f) · Procesos de producción frente al worktree: medidos; propuesta de aislamiento (pendiente)

- **Medido en solo lectura:**
  - el receptor carga 67 módulos del worktree, 2 de ellos mutados hoy en el sitio, sin que se reiniciara;
  - el despertador importa código antes de comprobar PARADA;
  - 32 mutantes tocan módulos del despertador;
  - el historial está íntegro (3684 eventos) y no hay contenido anómalo.
- **El despertador no se puede congelar sin una decisión de arquitectura:** sus datos y PARADA van con el código.
- **Mutar sobre una copia** (`--raiz`) queda **validado**: 4/4, y el árbol vivo conserva sha y mtime.
- **Propuesta:** `milestones/m3-entry/PROPUESTA-AISLAMIENTO-PROCESOS-PRODUCCION.md` (A, B, C, D, E). Revisión de
  seguridad: APTO con condiciones, ya incorporadas. **Pendiente de autorización.**
- **`_ruta_red`:** el diff aplica limpio y no tiene cambios ajenos. Sigue pendiente de autorización.
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-25 (g) · El arnés de mutación ya no escribe en el árbol del proyecto (regla 6)

- **Riesgo cerrado:** las baterías mutaban en el sitio código que cargan el receptor de nodos (credencial real) y el
  despertador. Ahora `walking-skeleton/herramientas/mutar.py` muta **una copia aislada** fuera del proyecto. El
  comando no cambia y la regla de `CLAUDE.md` §2 sigue vigente.
- **Además:**
  - contención de `fichero` dentro de la copia;
  - limpieza de copias huérfanas;
  - degradación sin git;
  - retirada de la escritura del diario, que ya era código muerto (AL-M4 y AL-M5 en `mutaciones/retiradas/`).
- **Verificación:**
  - mutación del propio arnés: 11/11, 18/18 y 4/4;
  - baterías reales sin tocar el árbol vivo: 429 `.py` con el mismo sha y mtime;
  - suites completas dentro de una copia: `walking-skeleton` 3836 passed; control-plane con 2 pruebas atadas a la
    ruta real, que nadie usa salvo `contencion-del-ambito`, ajustada y ahora 1/1;
  - revisiones de código y de seguridad, dos rondas: APTO.
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-25 (h) · Cierre documental de la regla 6 y `_ruta_red` validada en copia (no aplicada)

- **`CLAUDE.md` §2 actualizado** (autorizado): el arnés muta copias aisladas y ya no hace falta `git checkout`. La regla
  «NADA en paralelo» se conserva, con el motivo vigente.
- **Docstring de `orquestador.mutacion_en_curso` corregido** (autorizado): solo texto; AST sin docstrings idéntico.
- **`_ruta_red`:** diff final `milestones/m3-entry/evidencia-cm2-s3-2026-10-25/PROPUESTA-ruta-red-v2.diff`, que
  sustituye a la v1.
  - Validado en una copia: suite con parche 3840 passed; mutación `ruta-red` 6/6 y `sin-dispositivos-reales` 9/9.
  - Revisiones de código y de seguridad: APTO.
  - **No aplicado:** pendiente de autorización.
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-26 (i) · QG ambiental diagnosticado; prueba mDNS corregida; `_ruta_red` v2 validada con la suite completa (no aplicada)

- **Fallo mDNS del QG de (x), causa confirmada.**
  - Hechos: el 25-10 hubo un cambio de punto de acceso Wi-Fi a las 22:04-22:07, y después Avahi registró «Host name
    conflict» y anunció `<hostname>-3.local`.
  - **Defecto de premisa de la prueba:** suponía que el nombre anunciado es `hostname + ".local"`.
  - Corregido preguntando a Avahi por D-Bus. Dos mutantes del resolutor siguen detectados (2/2).
- **El otro fallo, `TimeoutExpired`, no se reproduce:** 7 de 7 pasan, en unos 0,3 s, sin llamadas de red (`strace`).
  - **Causa no confirmada.** Hipótesis: un parón del sistema por presión de memoria o de E/S.
- **`_ruta_red` v2, el diff exacto:** suite completa en una copia, 3842 passed / 3 skipped / 17 xfailed (rc=0);
  mutación 6/6 y 9/9; revisiones APTO. **No aplicado.**
- **Observación de producto:**
  - `desplegar-nodo.sh` configura los nodos con `$(hostname).local`, que tras el renombre no se anuncia.
  - NODO-01 sigue ONLINE gracias al servidor de respaldo por IP.
  - Se promueve a deuda si un nodo queda OFFLINE por ese motivo.
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-26 (j) · `_ruta_red` aplicado; primer ciclo autónomo completo demostrado en aislamiento; defecto de reanudación hallado

- **Hito A:** `_ruta_red` v2 **aplicado** al árbol vivo (autorizado), idéntico a la copia validada. Pruebas 14,
  regresión 299 y mutación 6/6.
- **Hito B:** el arnés es el único mutador. La autoconstrucción escribe por diseño, tras autorización, review y PARADA.
  La documentación de §2 ya está alineada.
- **Hito C, demostrado en un sandbox fuera del repositorio**, por la cadena real (`motor_autonomia.trabajar`):
  descubrir, planificar, review, ejecución en copia, **verificación independiente confinada** (pytest bajo Landlock y
  seccomp), promoción y log íntegro. El historial real queda intacto.
- **Hito D, parcial:**
  - la continuidad funciona: el ciclo 2 no repite la tarea;
  - **la reanudación tras un SIGKILL falla**: la tarea queda «planificada sin resultado» para siempre y la cola dice
    «agotada». El fichero queda intacto. Es un defecto de `planificador.elegible`; su arreglo exige decidir el esquema
    de eventos (DP).
- **Hito E: no existe.** `DP-NODO-01` excluye la ejecución remota; los nodos solo emiten latidos. Requiere DP y acta.
- **Instantánea de CM2 y del receptor:** validada en una copia; su activación sigue pendiente de una ventana segura.
  **`pytest-of-majo1230/`:** retirada tras verificación.
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-26 (k) · Recuperación tras caídas propuesta (DP + prototipo validado, NO aplicado); delegación a nodos en DP

- **Defecto del Hito D, con su causa confirmada.** Una tarea interrumpida por SIGKILL quedaba atascada para siempre
  (`planificador.elegible`).
- **`DP-RECUPERACION-TRAS-CAIDAS`, opción C:**
  - identidad del ejecutor y 11 estados;
  - comprobar y añadir bajo cerrojo: sin duplicados ni dos ejecutores;
  - sin migración.
- **Prototipo validado en copia:**
  - 1405 pruebas en la suite;
  - mutación 16/16;
  - dos revisiones independientes y el arquitecto, todos con condiciones;
  - SIGKILL → reanudada → completada → la segunda ejecución hace 0.
- **Sigue pendiente de la decisión del CEO.**
- **`DP-DELEGACION-NODOS`:** la delegación no existe y choca con `DP-NODO-01`. Pide una decisión para ampliar ese DP.
- **Producción intacta:** PARADA armada, ciclo autónomo real inactivo y sin commit.
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-26 (l) · Recuperación tras caídas aplicada al worktree (QG PASS, sin commit)

- **`DP-RECUPERACION-TRAS-CAIDAS`, opción C:** todas las condiciones cerradas o clasificadas (§10.3).
- **Nuevo contrato:**
  - **un supervisor por log**;
  - recuperar antes de planificar;
  - las agotadas, observables con su evento;
  - API pública `registrar_evento_si`, que niega los eventos gobernados;
  - `completada` monótona;
  - identidad del ejecutor robusta (`hidepid`, rango de pid).
- **Evidencia:**
  - en copia: 1429 pruebas y mutación 29/29;
  - 3 revisiones independientes, la última APTO;
  - **QG en vivo PASS: 3842.**
- **Los 2 fallos «base» eran de entorno** (rutas absolutas): pasan en la ruta real.
- **Límite conocido:** una promoción recuperada queda `resultado_ambiguo` hasta que se apruebe un DP de
  `autoconstruccion`.
- **Delegación a nodos:** enmienda de `DP-NODO-01` redactada y **no aplicada**.
- **Producción:** PARADA armada; el ciclo real no ha ejecutado el cambio.
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-26 (m) · Integración preparada y verificada; DP de correlación en la autoconstrucción

- **Partición en 7 commits verificada etapa por etapa:** imports y colección limpios, y la etapa final igual al
  worktree.
- **Auditoría independiente:** resueltas sus reservas, incluida una GRAVE (el borrado del rename).
- **Sin commits:** a la espera de la decisión del CEO.
- **`DP-AUTOCONSTRUCCION-CORRELACION-Y-RECUPERACION`:** correlación estable tarea→cambio y recuperación con la
  verificación publicada. Cierra `resultado_ambiguo` cuando se apruebe. Evaluado ENCAJA CON CONDICIONES, incorporadas.
- **Delegación a nodos:** criterios de aceptación y prerrequisitos definidos; `DP-NODO-01` intacto.
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-26 (n) · Integración ejecutada en la rama de trabajo (7 commits, sin merge)

- **Commits:** `ac64b9c`, `81a0d57`, `646a9ce`, `7c4af11`, `9f13935`, `9f238d6` y `bf13a47` sobre `6dad6af`.
- **Validación:** cada instantánea por separado, sin fallos nuevos. La final con **QG PASS 3842**, preflight APTO y
  control-plane en vivo 1433/0.
- **Auditoría:** independiente, CONSISTENTE. Registros reales no integrados.
- **Sin merge a main ni push:** pendiente de autorización.
- **DP de `autoconstruccion`:** diseño completo y revisado, sin implementar.
- **Delegación:** propuesta con requisitos de seguridad. `DP-NODO-01` intacto.
- **Orden del §16:** sin cambios. **S3 sigue abierto.**

### 2026-10-26 (o) · Investigación externa IE-032 (Coucou) e IE-033 (KORUS): sin cambio de cronograma

- **Coucou:** prototipo aislado futuro, solo con acta; no en el equipo real.
- **KORUS:** descartado.
- **Orden del §16 sin cambios:** no se crea ningún hito nuevo ni ninguna línea de robótica. **S3 sigue abierto.**

### 2026-10-26 (p) · Base de conocimiento de ingeniería (IE-034..IE-043) y consolidación de diseños, sin cambio de cronograma

- **Base y procedimiento:** 10 fichas nuevas con SHA fijado, auditoría de evidencia APTO, y el procedimiento
  «defecto difícil» (la base orienta y no autoriza).
- **Hallazgos sobre AURA:**
  - **Deuda `D-LOG-1`** (cola del log sin ancla, confirmada ejecutando en copia).
  - HAL-034-1: brecha de defensa en profundidad, MEDIA.
- **DP sin implementar:**
  - `autoconstruccion`, con la cobertura D1-D3 completa;
  - delegación, con STRIDE formal y 5 ALTOS abiertos.
- **Integración:** 7 commits verificados documentalmente, sin merge.
- **Orden del §16 sin cambios. S3 sigue abierto.**
