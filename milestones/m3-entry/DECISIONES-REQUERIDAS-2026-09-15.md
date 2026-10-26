---
documento: "Decisiones requeridas surgidas del ciclo de construcción del 2026-09-15"
tipo: "PROPUESTA — no ratificada. Ninguna de estas decisiones está tomada."
fecha: 2026-09-15
mantenido-por: "APUS-5 (CTO)"
decide: "CEO (Mauricio)"
checkpoint: "6dad6af (árbol con cambios sin commitear)"
---

> **ESTADO POSTERIOR — APROBADAS (CEO, 2026-09-15).** Fuente: el mensaje de misión del CEO
> «CONTINUACIÓN DE CONSTRUCCIÓN DE AURA — DECISIONES DR-1 / DR-2 / DR-3 / DR-4 APROBADAS»:
> **DR-1 = A** · **DR-2 = A**, con FORGET sobre identidad/versión concreta y conservando historial ·
> **DR-3 = límite con aviso honesto**, sin subir el timeout · **DR-4 = medir por separado recorte (A)
> y descarte por bloques (B), después la combinación, e implantar solo lo que la medición sostenga**.
> **Laguna de registro:** no existe acta en `decisiones/`; redactarla corresponde al CEO. El contenido de
> abajo se conserva tal como se propuso.

# Decisiones requeridas — ciclo del 2026-09-15

**Este documento no decide nada.** Recoge cuatro decisiones que el ciclo de construcción encontró y **no
pudo tomar**, porque cada una cambia autoridad, perímetro o comportamiento normativo. Cada línea de
trabajo afectada se detuvo solo en ese punto; lo demás se construyó.

Todo lo marcado `[EJEC]` se reprodujo ejecutando AURA con datos aislados (nunca `~/.aura`) y proveedor
mock salvo indicación. Clasificación D47.

---

## DR-1 · La evocación genérica choca con la puerta de ADR-0014

### Problema
Tras declarar hechos que AURA reconoce y lista, una pregunta de evocación **sin atributo** recibe la
respuesta de ausencia. AURA niega tener recuerdos que su propio Core conserva.

### Evidencia reproducible `[EJEC]`
Sesión nueva por variante, tras declarar «me llamo Mauricio» y «mi color favorito es el verde»:

| pregunta | respuesta |
|---|---|
| ¿te acuerdas de lo que te dije antes? | «No tengo ningun recuerdo registrado sobre eso.» |
| ¿te acuerdas de lo que te dije? | ídem |
| ¿recuerdas lo que te conté? | ídem |
| ¿te acuerdas de mi nombre? | ídem |
| ¿qué te dije antes? | ídem |
| ¿de qué hablamos? | ídem |
| ¿te acuerdas de mi color favorito? | pasa al modelo (acierto léxico accidental) |
| ¿recuerdas cómo me llamo? | «Te llamas Mauricio.» (acierto por subcadena accidental) |

**5 de 7 fallan.** Es un defecto de familia, no de una frase.

### Causa `[EJEC]` + `[LECT]`
- La puerta (`core/orchestrator.py`, `if not hits and _es_consulta_de_memoria(text) and not cognicion_general`)
  decide **solo** con `memory.recall`, que es léxico. «¿te acuerdas de lo que te dije antes?» no comparte
  términos con ningún recuerdo → 0 hits → ausencia.
- La puerta **nunca consulta el modelo de usuario**, aunque es el mismo almacén físico.
- El buffer `_dialogue` solo se lee **después** de la puerta, para el prompt del LLM.
- ADR-0014 §1 **se cumple literalmente**: promete qué hacer con cero resultados, no cómo se calculan. El
  propio ADR admite en sus consecuencias que *«la detección por patrones puede no reconocer formulaciones
  inusuales»*; esta, sin embargo, es la formulación más natural posible.

Clasificación: bug de integración entre superficies que no se consultan (dominante) sobre un límite
aceptado de ADR-0014.

### Perímetro tocado
Toda corrección toca algo declarado intocable en `DP-COGNICION-LOCAL-Y-RENDIMIENTO.md` §10 o fuera del §9:
la puerta de ADR-0014, `_es_consulta_de_memoria`, `recall`/`contracts.py`, o la cascada de superficies.

### Alternativas
| | qué | impacto sobre el Core | impacto sobre el LLM | riesgo |
|---|---|---|---|---|
| **A** | Superficie determinista de **evocación de hechos** en la soberanía, junto a `«¿qué sabes de mí?»`: «¿te acuerdas de lo que te dije?» → lo que AURA sabe hoy, desde el Core | responde el Core, 0 llamadas al LLM | ninguno | colisiones con otras superficies (§4.6); decidir si «lo que te dije» son hechos o conversación |
| **B** | La puerta consulta el modelo de usuario antes de afirmar ausencia | toca ADR-0014 | ninguno | mover la garantía 24/24; exige remedir la batería |
| **C** | Evocación **conversacional** leyendo `_dialogue` («¿de qué hablamos?») | responde el Core desde memoria volátil | ninguno | el buffer no sobrevive al reinicio: choca con la regla del CEO de que toda capacidad importante lo haga |
| **D** | Aceptarlo como límite de ADR-0014 | — | — | AURA sigue negando recuerdos que tiene |

**Descartado en cualquier caso:** que el LLM decida si un recuerdo existe (ADR-0014 §2).

### Pruebas necesarias para A
Las 7 variantes de arriba como casos positivos; negativos de colisión con olvido, refutación,
automatizaciones y «qué sabes de mí»; proveedor espía con 0 llamadas; `test_frontera_cognitiva.py` 24/24
intacto; mutantes sobre el anclaje de la gramática.

### Recomendación de la cuadrilla
**A**, limitada a evocación de **hechos** con gramática anclada. Deja la puerta intacta, no delega nada al
modelo y tiene la misma forma que una superficie que ya existe. C debería esperar a que exista memoria
conversacional persistente.

---

## DR-2 · «Olvidar» no alcanza al eco episódico (semántica de FORGET, `D-AMP-3`)

### Problema
Cada declaración deja dos entradas: la semántica (versionada) y un eco episódico «usuario dijo: …» sin
marcas. Olvidar retira la primera y **no la segunda**, que sigue llegando al modelo como memoria.

### Evidencia reproducible `[EJEC]` — idéntica en `HEAD` y en el árbol
```
tu> mi color favorito es el verde        AURA> Entendido.
tu> olvida mi color favorito             AURA> Hecho. Ya no lo consideraré parte de lo que sé de ti.
tu> ¿qué sabes de mí?                    AURA> Todavía no sé nada sobre ti.
tu> color favorito                       → llega al modelo con
    [contexto memoria: usuario dijo: mi color favorito es el verde | usuario dijo: olvida mi color favorito]
```
El olvido cumple su promesa en la superficie y no en el contexto. Con un modelo real, el dato olvidado
puede volver a salir por su boca. **Es preexistente**: se reprodujo igual sobre una copia exportada de
`6dad6af`.

### Relación con lo construido hoy
El filtro de contexto de este ciclo (`_da_por_cierto`) retira del prompt las entradas **refutadas y
superseded**, pero no puede alcanzar el eco: no lleva marcas. Y tras corregir el blanco del olvido, la
versión antigua de un atributo **se conserva como historial** después de olvidar la vigente, porque
decidir si el olvido la arrastra es precisamente D-AMP-3.

Nota de contexto: **en `HEAD` el olvido ya destruía historial**, pero por un defecto —borraba la versión
antigua en lugar de la vigente—, no por decisión. Ese defecto se corrigió en este ciclo.

### Un segundo caso, también preexistente, que decide D-AMP-3 por accidente `[EJEC]`
Hallado por la reverificación independiente, reproducido igual sobre `6dad6af`:
```
tu> mi ciudad favorita es Valencia     (v1)
tu> mi ciudad favorita es Sevilla      (v2)
tu> mi ciudad favorita es Valencia     (v3, vigente, texto IDÉNTICO a v1)
tu> ¿qué sabes de mí?
tu> olvida eso                          AURA> Hecho.   → desaparecen v1 Y v3
```
El foco señala una sola entrada, pero la operación del Motor Único borra **por texto**
(`_predicado` en `core/ejecutor_modelo_usuario.py` compara `contiene in content`), así que se lleva
también la versión histórica idéntica. En ese caso límite el olvido **arrastra el historial** sin que
nadie lo haya decidido. Corregirlo exige que `olvidar_informacion_usuario` identifique la entrada por
versión y no por texto: es un cambio del **contrato de la operación** en el Motor Único, y por eso no
se hizo aquí. Queda ligado a esta misma decisión.

### Alternativas
| | qué | riesgo |
|---|---|---|
| **A** | El olvido retira también de la recuperación normal los ecos que contienen literalmente lo olvidado, conservándolos para auditoría | define por primera vez que un eco depende de un hecho |
| **B** | El olvido de un atributo arrastra también su historial (todas las versiones) | decide D-AMP-3 en el sentido «DELETE»; pierde auditoría si no se conserva aparte |
| **C** | Enlazar en el modelo de memoria cada eco con su hecho | cambio del modelo de memoria; es la solución completa y la más cara |
| **D** | Mantenerlo | «olvidar» promete algo que el contexto del modelo no cumple |

### Recomendación de la cuadrilla
Decidir **D-AMP-3** primero (el documento de AMP recomienda coexistencia), y con esa decisión aplicar
**A**: es la que hace verdadera la frase «ya no lo consideraré parte de lo que sé de ti» sin tocar el
modelo de memoria.

---

## DR-3 · La cola larga de generación supera el timeout visible (`D-FC-7`)

### Problema
Algunas respuestas del modelo se alargan lo bastante como para superar el timeout por defecto, y el turno
se pierde tras minutos de espera.

### Evidencia `[EJEC]` — Ollama real, `qwen2.5:0.5b`, máquina sana
Campaña de 18 turnos cognitivos con preguntas distintas y el prefijo de caché controlado
(`milestones/m3-entry/evidencia-cognicion-local/`):
- **2 de 18** generaron ≥ 199 tokens.
- Uno duró **189,1 s**. `OllamaProvider.DEFAULT_TIMEOUT_S = 180`.
- Mediana del turno: 35–46 s según la variante del prompt.

### Por qué no se aplicó ninguna solución
Cada opción cambia lo que recibe el usuario:
| | qué | lo que recibe el usuario |
|---|---|---|
| **A** | `num_predict` + reparar el JSON en la última frase completa | una respuesta cortada, marcada como no verificada |
| **B** | `num_predict` + mensaje honesto de corte | un aviso en ~70 s en vez de un timeout en 180 s |
| **C** | Subir el timeout por defecto | la respuesta completa, con una peor espera más larga |
| **D** | No cambiar nada y medir primero con conversaciones multiturno reales | lo de hoy |

Sin tratamiento, `num_predict` a secas es peor que nada: el JSON truncado cae en el texto de fallback
*«No entendí bien; ¿puedes reformularlo?»*, que es falso —el modelo entendió y se extendió—.

### Recomendación de la cuadrilla
**Decidir junto con DR-4, y después B.** n = 18 con 2 colas es poca muestra para fijar un tope. La
ingesta multiturno ya se midió (DR-4) y es la otra causa, mayor y estructural, de superar el timeout: un
tope de generación sin resolver la ventana no evitaría los turnos de ~188 s desde el octavo.

---

## DR-4 · La ventana deslizante del diálogo rompe la caché desde el turno 8

### Problema
En una conversación que llega al modelo, a partir del octavo turno cada turno re-ingiere el buffer de
diálogo completo y supera el timeout por defecto.

### Evidencia `[EJEC]` — orquestador real, Ollama real, máquina sana
`milestones/m3-entry/evidencia-cognicion-local/campana-3-multiturno/multiturno-2.json`:
- T1–T7: ingesta **6,5–38,7 s** aunque el prompt crece de 132 a 1564 caracteres (la caché de prefijo
  cubre todo menos el último intercambio).
- **T8: 144,8 s de ingesta, 187,8 s de turno**, con un prompt más corto que el de T7.
- Causa: `_DIALOG_N = 6` y el descarte del turno más antiguo cambia el **principio** del buffer, lo que
  invalida la caché de todo lo que va detrás. Se predijo por la estructura del prompt antes de medirlo.

### Por qué no se aplicó
Cada alternativa cambia **cuánta conversación recuerda AURA**, que es comportamiento de producto, y
ninguna elimina el pico por completo:

| | qué | memoria conversacional | latencia |
|---|---|---|---|
| **A** | Descartar por bloques: al superar 6, conservar 3 | entre 3 y 6 turnos, en vez de siempre 6 | pico ~100 s + generación, solo cada 4 turnos |
| **B** | Ventana más corta (p. ej. 3) | siempre 3 turnos | picos menores, en cada turno desde el 5.º |
| **C** | Recortar en el buffer las respuestas previas de AURA (van íntegras y son lo más largo) | mismos turnos, menos texto de cada uno | menos tokens; el pico sigue existiendo |
| **D** | Mantener la ventana y resolver el pico con DR-3 (timeout/tope) | siempre 6 turnos | cada turno desde el 8.º, ~145 s de ingesta |

### Relación con otras decisiones
Se combina con **DR-3**: el timeout de 180 s lo superan tanto la cola larga de generación como este pico
de ingesta. Conviene decidirlas juntas.

### Pruebas necesarias para cualquier opción
Hoy **ninguna prueba ni mutante protege el tamaño ni la política de la ventana** (verificado por búsqueda
en `tests/` y `mutaciones/`). Una propiedad determinista y medible sin LLM: *el prompt del turno n empieza
por el prefijo del turno n−1 salvo en los turnos de corte*. Más la repetición de esta campaña con 10–12
turnos antes y después.

### Recomendación de la cuadrilla
**C + A**: recortar las respuestas previas de AURA en el buffer ataca el volumen sin perder turnos, y el
descarte por bloques reduce la frecuencia del pico. Medir ambas por separado antes de combinarlas.

---

## Lo que NO es una decisión nueva y no se incluye aquí

- **Voz.** La decisión sigue siendo la de `DECISION-REQUERIDA-VOZ-NO-DISPONIBLE.md` (ABIERTA, opciones
  A–D). Dos hechos nuevos para quien la tome, ver el informe del ciclo: la voz Piper **sí existe**, pero
  en el USB `AURORA_EXT`, que **tras el reinicio del 2026-09-15 no está conectado**; y el modelo de Whisper
  tampoco está en caché local. Reconectar el USB es acción humana, no decisión.
- **VAL-M1…M5, EDF-M4/M5, SB-M10, P-019, modelo por defecto, ampliación de zona**: ya elevadas antes.
- **Acta de `D-AMP-1 = B`**: la aprobación no tiene artefacto en `decisiones/`; es una laguna de
  registro, no una decisión por tomar.
