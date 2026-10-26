---
documento: "Decision Package — S3 · Reloj automático de CM2 (memoria en la vida real)"
tipo: "DECISION PACKAGE — BORRADOR. NO APROBADO. Prepara la decisión; no la toma."
fecha: 2026-10-04
revision: "2026-10-06 — v2 (corrección documental), v3 (revisión final) y v4 (cierre: hechos frente a inferencias), autorizadas por el CEO (§9). No cambia el estado: sigue sin aprobar."
autor: "APUS-5 (CTO)"
estado: "DECISION_REQUIRED"
origen: "Mapa maestro §16 (S3 ‖ S2: «reloj de CM2 automático · privacidad D* · olvido D-AMP-3*» → salida «registro CM2 funcionando») y §13 («instrumentación de CM2» es paralelizable). CHECKPOINT 2026-10-04 (post NODO-01) y 2026-10-06 (cierre de S2)."
---

# DP — S3 · Reloj automático de CM2

`[LECT]` leído en el repositorio · `[EJEC]` medido ejecutando · `[INFER]` deducido · `[HIPO]` no verificado.
**PROPUESTA** = texto del CTO pendiente de aprobación; no es una regla vigente.
Rutas de código relativas a `walking-skeleton/`; rutas de documentos relativas a la raíz del repositorio.

## 1. Por qué es el siguiente incremento (y no otro)

- **S2 está cerrado.** La rama voz→acción física quedó cerrada el 2026-10-06 (CHECKPOINT, entrada «BLOQUE CERRADO»). El mapa §16
  nombra S3 como el siguiente bloque.
- **CM1 no bloquea S3 según los documentos oficiales `[LECT]`.**
  - CM1 sigue **incumplido**: P50 ≈ 7,9 s frente a ≤ 800 ms, medido el 2026-10-06 `[EJEC]`
    (`milestones/m3-entry/evidencia-latencia-voz/e2e-latencia-2026-10-06.jsonl`; `RESULTADO-LATENCIA-Y-MODELO.md` §7.4. El P50
    medido es 7,17 s hasta el corte; sumar los 0,7 s de la ventana de silencio es `[INFER]`).
  - El mapa §13 pone el «bloqueo duro: CM1 en HC-1» sobre **ACEPTACIÓN R1** (`milestones/mapa-maestro/AURA_MASTER_DEVELOPMENT_MAP.md:135`),
    no sobre CM2 (`:129`), y declara «instrumentación de CM2 ‖ integración» paralelizable (`:143`).
  - El mapa §16 programa S3 en paralelo a S2 (`:167`): «la rama bloqueada no congela las demás» (`:174`).
  - **Acotación:** el mismo mapa dice que «**S7–S8 no puede cerrarse en HC-1 mientras CM1 siga como está**» (`:175`). S3 puede
    acumular datos de CM2, pero **R1 no puede aceptarse** mientras CM1 siga incumplido.
- **R1 está BLOQUEADO por CM1 en HC-1** (mapa §18-19). R2, R3 y R4 dependen de R1. L4 sigue DIFERIDO a R4.
- **Rama de hardware:** su puerta es `DP-CAPACIDADES-POR-HARDWARE.md` §7, que sigue en DECISION_REQUIRED.
- **Mapa §13:** el cuello de botella de R1 es el **tiempo de uso real**: «CM2 y CM4 exigen semanas de uso que ningún código
  acorta… el uso real tiene que empezar ya, en paralelo».
- **S3 es la única pieza de la ruta a R1 que no espera una decisión de hardware** `[INFER]`, por lectura del mapa §16-19. Cada semana sin el reloj es una semana de uso
  real que no cuenta para CM2.
- **Contrapeso:** mientras CM1 bloquee R1 sin fecha, aplazar S3 no retrasa la aceptación de R1 `[INFER]`.

**Qué no hay [LECT, revisado 2026-10-06]:**
- no hay ningún Decision Package de CM2 anterior a este;
- no hay código de CM2: `grep -i cm2` en `aura_skeleton/` y `herramientas/` da 0 resultados, y el flag `--medir-cm2` **no
  existe**;
- `capacidades.json` lo confirma: «CM2 exige medición en uso real (Bible 2.5) **nunca realizada**», nivel 3.

Por CLAUDE.md §2 («nada se construye sin DP aprobado»), este documento es el paso correcto.

## 2. Qué exige CM2 (Bible 2.5 §5.2)

Fuente: `docs/libro-02-vision-y-producto/2.5-requisitos-atributos-calidad.md:107-114` (v1.1.0, aprobado 2026-07-18). La marca
† del original indica umbral **propuesto**.

| Criterio | Valor (texto de 2.5) |
|---|---|
| Ventana | «recuperar temas de al menos **4 semanas** atrás sin re-explicación †» |
| Tasa de recuperación | «≥ **90%** † de los temas **marcados como relevantes** en el set de evaluación» |
| Umbral de fracaso | «> **10%** † de turnos que **exigen** re-explicar contexto ya vivido cuenta como fracaso de producto» |
| Fidelidad | «cero fabricación de recuerdos (la memoria distingue lo recordado de lo inferido)» |

**Cómo se mide, según la Bible** `[LECT]`:
- **2.5 §6** (`:148-154`):
  - «evidencia por registro automático… audit log y telemetría local»;
  - «sets de evaluación… derivados de los escenarios de 2.3»;
  - «el veredicto lo emite el CEO»;
  - la zona intermedia la adjudica el CEO;
  - la instrumentación y el protocolo «se ejecutan en 7.2».
- **2.2 §3.2 y §3.4** (`docs/libro-02-vision-y-producto/2.2-alcance-mvp-roadmap-releases.md:79-97`):
  - «la prueba de memoria exige por definición **semanas de calendario**»;
  - ventana de aceptación de R1 «propuesta: 2 semanas»;
  - el incumplimiento reinicia la ventana de ese criterio.
- **2.3 E-01** (`docs/libro-02-vision-y-producto/2.3-usuario-escenarios-prioritarios.md:174`): «tasa de recuperación de temas;
  tasa de re-explicación».
- **7.2** (`docs/libro-07-ingenieria-operacion-evolucion/7.2-estrategia-pruebas-evals.md:38`): «recall y no-fabricación de memoria
  (2.5 §5.2)… **LLM-as-judge + evaluación humana**». 7.2 **no contiene un protocolo de CM2** (no aparece el término).

**No existe definición oficial** de «tema relevante», «re-explicación», «recuperación» ni «fabricación». Las del §5.2 de este
DP son **PROPUESTAS**; su aprobación es la pregunta 5 del §7.

El reloj debe producir las cifras **solo, desde el registro automático** (mapa §22-25: «medidos por registro automático»),
sin que nadie las calcule a mano.

## 3. Qué existe y qué se reutilizaría (no se crea arquitectura paralela)

Hay que distinguir lo que **existe** de lo que **garantiza**. Reutilizar algo no hereda garantías que no tiene.

- **`MemoryStore`** (`aura_skeleton/contracts.py:95`, con `write`:103 y `recall`:104) `[LECT]`.
  - `recall` solo excluye los kinds de `KINDS_NO_RECUPERABLES = {HISTORICO}` (`contracts.py:52`), con prueba y mutantes
    (`mutaciones/historico-no-recuperable.toml` H-M1..M6).
  - **`recall` NO filtra los hechos refutados, superseded ni retirados.** Ese filtro vive en el Core:
    `_da_por_cierto` (`aura_skeleton/core/orchestrator.py:516-528`) solo depura el contexto que recibe el modelo.
  - **Residuo declarado:** el eco episódico «usuario dijo: …» de una versión antigua no lleva marca y sigue llegando
    (`orchestrator.py:2057-2064`; medido en `tests/integration/test_contexto_de_memoria_vigente.py:137`,
    `test_MEDIDO_NO_DESEADO_…`).
  - **Consecuencia para el reloj:** una sonda que llame a `recall` directamente contaría como «recuperado» un hecho ya
    retirado.
  - **`recall` es léxico y no depende del tiempo** (`aura_skeleton/modules/memory.py:164-215`). La edad de un hecho solo
    influye a través de lo que cambia a su alrededor: la memoria crece y otras entradas compiten por los primeros k
    resultados (§5.3).
- **Hechos declarados** (`ClaseSenal.HECHO_DECLARADO`, `aura_skeleton/conectores/conversacion.py:228`; candados A/B):
  - Su recuperación en un turno está probada y protegida por mutantes (`mutaciones/hechos-declarados.toml` H1-H10;
    `tests/integration/test_hechos_declarados.py::test_P8`, persistencia entre dos procesos, sin mutante que la ataque).
  - **No** hay ninguna prueba de recuperación con edad (7/14/28 días), ni reloj inyectado. **No existe evidencia longitudinal**
    de la memoria de AURA: ninguna medición con la ventana mínima de 4 semanas.
- **Qué se guarda de una conversación** (`orchestrator.py:3134-3158`, `intencion.destino_de_memoria`) `[LECT]`:
  - una declaración, como `episodica` («usuario dijo: …»), recuperable;
  - una orden pura, como `HISTORICO`, que no vuelve en `recall`;
  - **una pregunta, un turno social o uno incierto no se almacenan** (`:3141-3143`).
- **Batería de memoria** (`tests/datos/bateria_memoria.json`, `tests/integration/test_bateria_memoria.py`) `[LECT]`:
  - 65 recuerdos y 77 consultas, de las que 53 esperan recuerdo; incluye paráfrasis y sinónimos.
  - Mide recall@3 ≥ **0,63** (`RECALL_MINIMO`), 0 falsos positivos puros y ≤ 2 adversariales conocidos, sobre
    `PersistentMemory.recall`.
  - **No es un set de CM2**: su umbral no es el 90 %, sus recuerdos no tienen edad y no son «temas marcados como relevantes».
- **«24/24» es frontera cognitiva, no fidelidad de memoria (corrección de esta revisión).**
  - **Qué es:** las 24 consultas de la batería **sin** recuerdo esperado reciben la ausencia determinista de ADR-0014 sin
    llamar al LLM (`tests/unit/test_frontera_cognitiva.py:100-102`, `tests/unit/test_frontera_referente.py:9`).
  - **Cuándo vale:** solo **con la memoria vacía**. Con el corpus sembrado se midió **19/24**, con 5 fugas
    (`milestones/m3-entry/DEUDA-ADR0014-MEMORIA-VACIA.md`, 2026-08-09).
  - **Qué no mide:** si un hecho declarado se recupera ni si se fabrica un recuerdo con el tiempo. **No se reutiliza como
    evidencia de la fidelidad de CM2.**
- **Pruebas de abstención honesta** («No tengo ningún recuerdo registrado sobre eso», `tests/unit/test_historial_consultable.py`;
  `test_hechos_declarados.py::H10`, `P11`).
  - Prueban que no se inventa **ante la ausencia**.
  - **No existe ningún contador `fabricado`** que el reloj pueda reutilizar.
- **Historial y audit log** (`adr/0023-el-historial-es-la-unica-fuente-de-verdad.md`, accepted 2026-08-03) `[LECT]`.
  - El audit log es uno de los componentes del historial (`ADR-0023:49`; `aura_skeleton/observability.py:98-175`):
    append + `fsync` y **sellado por segmentos**.
  - Retirar se expresa con una **lápida** anexada, nunca reescribiendo (`ADR-0023:65`).
  - Una proyección «debe poder eliminarse por completo y regenerarse desde el historial» (`:82`).
  - **Consecuencia:** el resultado de cada sonda sería una observación que entra en el historial; la tasa de CM2, una
    proyección regenerable desde esos eventos, sin repetir las sondas.
  - **Rotación (corregido en esta revisión):**
    - Al superar 5 MB, el fichero activo se **sella** (se renombra a un segmento inmutable con `sha256` en un manifiesto) y se
      abre otro vacío. «**Nada se elimina** — la rotación no borra registros» (`observability.py:110-115, 136-160`).
    - ADR-0023:115 lo registra así: el fichero activo «decrece», pero el contenido «sobrevive íntegro en el segmento».
    - **No hay pérdida de eventos.** El reloj tendría que leer **segmentos + activo** (`leer_audit_desde`,
      `observability.py:219`), no solo el fichero activo.
    - En el código no existe ningún mecanismo que borre segmentos, así que la conservación de 28 días se cumpliría por diseño
      salvo intervención manual `[INFER, sin ejecutar]`. Una prueba al construir debería verificarlo.
  - **Qué contenido llega al audit log (corregido en v3, `[LECT]`):**
    - La traza de bajo nivel `MEM write` (`modules/memory.py:162`) no se audita.
    - Pero **toda declaración** pasa por el Motor Único (`registrar_informacion_usuario`) y su ejecutor audita el **texto
      íntegro**: «registrada sobre '…': {contenido!r}» (`core/ejecutor_modelo_usuario.py:282-288`).
    - Olvidar y refutar auditan también la lista de textos afectados (`:299-306`, `:314-320`).
    - Lo mismo los ecos retirados (`:176`).
    - **El texto de un hecho está en el audit log inmutable desde que se declara** (§4.1).
- **Dos paradas distintas (aclaración de v3, `[LECT]`).** El repositorio llama «PARADA» a dos cosas:
  - **(a) PARADA del control-plane** (`entorno/control-plane/PARADA`). Detiene el ciclo autónomo. **Está armada.**
  - **(b) Kill switch de AURA en ejecución** (`<AURA_DATOS>/KILL`, `aura_skeleton/composicion.py:369-375`;
    `_sistema_detenido`, `core/orchestrator.py:2205-2214`). Es la «`PARADA`» de ADR-0024. El 2026-10-06 `~/.aura/KILL` no
    existía: **no está armado**.
  - **Consecuencia:** si (b) estuviera armado, toda declaración que pasa por el Motor Único (`registrar_informacion_usuario`,
    clase `soberania` con kill switch, `core/permissions.py:96-101`) se bloquearía. Solo quedaría el eco pasivo, y la opción A
    **no registraría hechos nuevos** que medir (`core/almacen_senales.py:38-41`: «con el kill switch armado son cero»).
  - El reloj de A depende, por tanto, de que (b) no esté armado durante el uso real. (a) no le afecta, salvo que el reloj se
    apoyara en el ciclo autónomo, que es justo lo que este DP descarta.
- **Kill switch (b) y escritura** (ADR-0024) (`adr/0024-alcance-del-kill-switch-y-escritura-pasiva.md`, accepted 2026-09-09) `[LECT]`:
  - «`PARADA` detiene la ejecución, no la conversación».
  - La escritura pasiva es una whitelist cerrada: `KINDS_PASIVOS = {episodica, historico}` (`contracts.py:71`).
  - «Un `kind` nuevo queda bloqueado con `PARADA` armada hasta que alguien lo declare».
  - «Esta decisión NO autoriza `memory.write` fuera del motor».
  - **Consecuencia:** el reloj no puede escribir en memoria un kind nuevo.
  - **Eventos de auditoría:** ADR-0024 no los regula; el Core ya audita con PARADA armada (`orchestrator.py:3155`). Que estén
    **permitidos** con el kill switch (b) armado es una lectura del silencio de ADR-0024 `[INFER]`; falta la prueba.
- **Ciclo autónomo** (`entorno/scripts/despertar-aura.sh`, cron cada 30 min, `motor_ciclo`). **PARADA (a) del control-plane está armada.** El reloj
  **no puede depender del ciclo autónomo**.

## 4. La pregunta que bloquea: ¿qué es un «tema relevante» y quién lo marca?

Bible 2.5 habla de «temas marcados como relevantes», pero **ningún documento dice quién los marca ni qué se guarda para
medirlos** `[LECT]`.

**Privacidad y retención: qué está decidido y qué no (corregido en esta revisión)** `[LECT]`:
- **Decisión D.** Es la «D» de `milestones/m3-entry/DECISION-REQUERIDA-CONTINUIDAD-DE-RESULTADOS.md` (2026-09-21, «PROPUESTA —
  no ratificada»): «**¿Qué contenido está prohibido retener?** … El caso concreto y medido es `leer_archivo`» (`:106-110`).
  - Trata del contenido de los **resultados de ejecución**, no de los temas de conversación, y **sigue sin decidirse**.
  - El mapa la vincula a S3 («privacidad D*», `:167`; «Privacidad del contenido retenido (punto D)», `:196`).
  - Su relación con la opción B es **por analogía**: B crearía una retención nueva, y decidir sobre ella es una decisión de
    privacidad. Si la cubre D o necesita una propia es una pregunta del CEO (§7, pregunta 1).
- **No existe una prohibición expresa** de almacenar conversaciones o transcripciones. La versión anterior de este DP la
  citaba como «regla vigente» sin fuente. Lo que sí existe:
  - **D-M-7** (`decisiones/2026-09-09-D-M-7-aprobacion-opcion-A.md:30`): «Eje 2 conservador: ante duda, **no almacenar**.
    El fallo seguro es perder recall, nunca fabricar». Es una política de clasificación para la memoria.
  - **Bible 2.4:117** (`docs/libro-02-vision-y-producto/2.4-personalidad-etica-limites.md`): «Sin retención por defecto»,
    referida a datos de **terceros**.
  - **Acta fundacional D23** (`decisiones/2026-07-17-acta-decisiones-fundacionales.md:163-165`): autoriza un **Módulo de
    Captura de Conocimiento** que procesa conversaciones «**siempre con autorización expresa del usuario**».
  - **Hoy AURA guarda** lo descrito en el §3; el audio se borra tras cada turno.
- **Olvido.** **D-AMP-3** (FORGET vs DELETE) **no está firmada** (§4.1).

| Opción | Qué es el set de evaluación | Qué se guarda de más | Mide CM2 tal como lo define 2.5 | Riesgo |
|---|---|---|---|---|
| **A · Hechos declarados** | Lo que el usuario **declara explícitamente** («recuerda que…»). Ya se guarda hoy | Métricas: id del hecho, fecha de declaración, resultado de cada sonda. **Contenido nuevo: ninguno, salvo que la consulta independiente lo exija** (pregunta 5) | **Parcialmente** (§5.3): mide recuperación y fidelidad de lo declarado; **no** mide temas conversacionales no declarados | Bajo. Puede sobreestimar CM2 frente a temas implícitos. Depende de la pregunta 5 |
| **B · Marcado explícito por el usuario** | El usuario dice «esto es importante» sobre un tema de la conversación | Un **resumen del tema** marcado: contenido nuevo, con retención | **Sí** en el set; la circularidad del oráculo (§5.2) también le afecta `[INFER]` | Medio: crea un archivo de temas. Exige antes una decisión de retención (D u otra propia, a decidir por el CEO) |
| **C · Detección automática de temas** | AURA infiere qué fue relevante | Resúmenes inferidos de conversaciones | Sí, pero el LLM juzgaría relevancia, cuando ADR-0014 y DP-COGNICION §6 le quitan esa autoridad (8/12 medido) | Alto: viola la frontera cognitiva. **El CTO propone descartarla; decide el CEO** |
| **D · Aplazar** | — | — | No | El tiempo de uso real sigue sin contar para CM2. **Contrapeso:** mientras CM1 bloquee R1, aplazar no retrasa la aceptación de R1 `[INFER]` |

**Re-explicación (umbral > 10 %):**
- Detectarla sin LLM exige una heurística, que no está definida (§5.2).
- Con A solo se puede observar la re-declaración de hechos ya declarados.
- Para temas no declarados necesita B.

### 4.1 D-AMP-3 · FORGET vs DELETE (incorporada en la revisión del 2026-10-06: el mapa la incluye en S3 y el DP original la omitía)

**Estado `[LECT]`: NO firmada.**
- `milestones/m3-entry/AMP-AURA-DECISIONES.md` (2026-09-10, «Requiere aprobación del CEO») la formula para firma.
- `DECISION-REQUERIDA-CONTINUIDAD-DE-RESULTADOS.md:226` (2026-09-21) dice que «sigue sin firmar».
- El código la cita como pendiente: `aura_skeleton/core/modelo_usuario.py:202`, `aura_skeleton/core/orchestrator.py:2236` y
  `tests/integration/test_soberania_respeta_vigencia.py:21-24`.
- La línea «APROBAR ahora… D-AMP-3 = A» (`AMP-AURA-DECISIONES.md:243`) **es una recomendación, no una firma**.

**Opciones documentadas** (`AMP-AURA-DECISIONES.md:83-113`):
- **A · coexistencia** (recomendada por el CTO en septiembre):
  - `refutar` (INVALIDATE) y `borrar` (**DELETE destructivo**) se mantienen, y se añade **`FORGET`** como tercer verbo: el
    valor fuera y una lápida.
  - Regla dura: «el borrado destructivo no puede ser nunca el modo por defecto de una operación automática».
- **B · sustituir `borrar` por `FORGET`:** todo borrado deja lápida. El documento la rechaza por «reducir la soberanía del
  usuario en nombre de la auditoría».

#### 4.1.1 Cuatro comportamientos distintos, y lo que hace hoy el código `[LECT]`

La decisión mezcla cuatro cosas que **no son equivalentes**:

| # | Comportamiento | Qué hace hoy AURA | Fuente |
|---|---|---|---|
| 1 | **Retirar de la recuperación operativa** | **Hecho olvidado:** la lápida lo oculta en la proyección (`_proyectar`), no vuelve en `recall` y sobrevive al reinicio. La clave de proyección es `(user_id, kind, content)` (`memory.py:120-135`): dos versiones con texto idéntico se funden al recargar, y la lápida de una oculta las dos (caso v1/v3 de `DECISIONES-REQUERIDAS-2026-09-15.md:117-131`); el «olvido por versión» no sobreviviría al reinicio en ese caso `[INFER, sin ejecutar]`. **Eco episódico** («usuario dijo: …»): se marca `retirada` y `_da_por_cierto` lo saca del contexto del modelo, pero **no de los `hits` de `recall`** (la puerta de ADR-0014 decide con `hits`) | `modules/memory.py:124-135, 217-237`; `core/ejecutor_modelo_usuario.py:157-178`; `core/orchestrator.py:516-528, 2057-2064` |
| 2 | **Registrar que ocurrió el olvido** | Audit de la memoria «olvidadas N entrada(s)», sin contenido. Audit del ejecutor «olvidadas N entrada(s) sobre '…': [textos]», **con** contenido. Línea de lápida en el JSONL. Audit «retirados N eco(s)… [textos]» | `memory.py:234, 236`; `ejecutor_modelo_usuario.py:173-178, 299-306` |
| 3 | **Conservar el contenido olvidado** | **Sí, en cuatro sitios:** (a) la línea original del JSONL (append-only); (b) la lápida, copia íntegra `{**baja, _LAPIDA: True}`; (c) los ecos marcados, que contienen el texto literal; (d) **el audit log**, inmutable, por tres vías: la **declaración** («registrada… {contenido!r}», `ejecutor_modelo_usuario.py:282-288`), el **olvido o la refutación** («… {afectadas!r}», `:299-306`, `:314-320`) y los **ecos retirados** (`:176`). Es coherente con una garantía aprobada `[INFER]`: G-6, «toda mutación es reconstruible desde el audit log» (`DP-D-M-8-MOTOR-UNICO-DE-MUTACIONES.md:193`, APROBADO por el CEO el 2026-08-17), con prueba que lo exige (`tests/unit/test_g7_lapida_append_only.py::test_g7_el_audit_sigue_identificando_QUE_y_SOBRE_QUIEN`: «tiene alergia a la penicilina» debe aparecer en el audit) | `memory.py:157-162, 234, 253-255`; `ejecutor_modelo_usuario.py:176, 282-288, 299-306, 314-320`; `observability.py:98-115` |
| 4 | **Eliminar físicamente el contenido** | **No existe**, aunque la Bible 5.5 §3 lo exige («elimina el dato y su rastro en índices y backups»). «La purga física NO se implementa». El audit log no tiene ninguna vía de borrado en el código, aunque su docstring cita «el borrado solo existe a petición del usuario (Bible 5.5)». `backup()` y `restore()` reescribirían el fichero activo desde la proyección, pero **no tienen llamadores en producción**, y un backup anterior al olvido conservaría el texto | `memory.py:232, 287-355`; `observability.py:112-114` |

**Conclusiones:**
- Hoy **no existe ningún borrado destructivo**. Para `borrar`, el sistema se parece a la política B (todo borrado deja lápida),
  antes de la firma. Pero no es B: B supone «valor fuera», y hoy el valor se conserva, en el caso (d) dentro de un registro
  forense inmutable.
- `AMP-AURA-DECISIONES.md:90` describe `borrar` como «reescribe el almacén», y el docstring de `borrar`
  (`modelo_usuario.py:117-121`) dice lo mismo, igual que el de `olvidar` («se reescribe el fichero», `memory.py:218-221`). **Las
  tres descripciones están desfasadas.** Desde G-7, `borrar` → Motor Único
  (`olvidar_informacion_usuario`, `modelo_usuario.py:116-127`) → `memoria.olvidar` → lápida.

#### 4.1.2 Qué decidió DR-2 = A y qué no

**DR-2 = A NO es la política A de D-AMP-3.** DR-2 (CEO, 2026-09-15) es otra pregunta, con sus propias opciones A-D
(`milestones/m3-entry/DECISIONES-REQUERIDAS-2026-09-15.md:90-139`), titulada «"Olvidar" no alcanza al eco episódico (semántica
de FORGET, `D-AMP-3`)».
- **Única constancia escrita:** una cita del mensaje de misión del CEO dentro del propio documento (`:11-14`), «**DR-2 = A**,
  con FORGET sobre identidad/versión concreta y conservando historial». No hay acta en `decisiones/`, y el documento lo
  reconoce como «laguna de registro».
- **Qué es la A de DR-2** (`:136`): «El olvido retira también de la recuperación normal los ecos que contienen literalmente lo
  olvidado, **conservándolos para auditoría**».

**Qué significa «conservando historial» según el propio documento (`[INFER]`: la frase del CEO solo consta citada en `:11-14`; esta lectura sale del texto del documento, no de un acta).** En DR-2, «historial» son las **versiones anteriores de
un atributo**: «la versión antigua de un atributo **se conserva como historial** después de olvidar la vigente, porque decidir
si el olvido la arrastra es precisamente D-AMP-3» (`:111-113`). La opción B de DR-2, «el olvido de un atributo arrastra
también su historial (todas las versiones)», es la que se rechazó.

| Cuestión | ¿La decide DR-2 = A? |
|---|---|
| Olvidar la versión vigente no arrastra las anteriores | **Sí, según la lectura `[INFER]` de arriba**: «conservando historial» = las otras versiones |
| FORGET actúa sobre una identidad/versión concreta, no por texto | **Sí** |
| Los ecos que contienen lo olvidado se retiran de la recuperación normal | **Sí** (en la práctica, del contexto del modelo; no de los `hits`, §4.1.1) |
| Los ecos se **conservan para auditoría**, con su texto | **Sí, de forma expresa** («conservándolos para auditoría») |
| El **valor del propio hecho olvidado** se conserva (línea original y lápida) | **No lo dice.** Pendiente |
| El texto olvidado se escribe en el **audit log inmutable** | **DR-2 no lo dice.** Es coherente con **G-6** (DP-D-M-8, aprobado el 2026-08-17) tal como lo interpreta la prueba G-7; que G-6 lo **exija** es `[INFER]`, porque DP-D-M-8:193 solo dice «antes/después». Ninguna decisión ha ponderado G-6 frente al «valor fuera» de FORGET. Pendiente |
| `borrar` destructivo existe (política A) o se sustituye por FORGET (política B) | **No.** El documento recomendaba «decidir D-AMP-3 primero» (`:141-142`) |

#### 4.1.3 Asunto de privacidad para el CEO (no se resuelve aquí; no se toca código)

- Cuando el usuario pide «olvida X», AURA deja de usarlo, pero **el texto de X sigue en disco**: en la memoria (línea original,
  lápida y ecos) y **en el audit log inmutable**, donde está **desde que se declaró**, también dentro de los **segmentos sellados**
  (`sha256` en un manifiesto) que la rotación nunca borra. Ese log no tiene vía de borrado.
- La respuesta al usuario («Hecho. Ya no lo consideraré parte de lo que sé de ti», DR-2 `:99`) es exacta sobre el
  comportamiento 1, pero **no** sobre los comportamientos 3 y 4.
- **Hay una tensión entre dos fuentes, y ninguna decisión la ha resuelto:**
  - **G-6** (aprobada): toda mutación tiene que poder reconstruirse desde el audit log. Interpretado así por la prueba
    `test_g7_el_audit_sigue_identificando_QUE_y_SOBRE_QUIEN`, eso conserva qué se olvidó. Que G-6 **exija** el valor, y no
    solo la identidad, es una lectura `[INFER]`: DP-D-M-8:193 dice «reconstrucción del antes/después».
  - **«Valor fuera»:** tanto la A como la B de D-AMP-3 atribuyen esa propiedad a FORGET. Si G-6 exige el valor (`[INFER]`, ver arriba),
    no podría cumplirse en el audit log.
- **Contradicción documental entre fuentes aprobadas (hallazgo del 2026-10-06, `[LECT]`):**
  - **Bible 5.5 §3** «Derecho al olvido: borrado verificable» (`docs/libro-05-seguridad-y-confianza/5.5-privacidad-soberania-datos.md:40-42`,
    v1.0.0, «Aprobado» el 2026-07-18 por el CTO con delegación D22) exige: «Una solicitud de borrado **elimina el dato y su
    rastro en índices y backups**; el borrado es **verificable** (el usuario obtiene constancia)».
  - **G-6** (DP-D-M-8, aprobado por el CEO el 2026-08-17) y **ADR-0023** (append-only, lápidas) llevan al comportamiento
    actual, que **conserva** el dato.
  - El código sigue G-6 y ADR-0023 y **no cumple 5.5 §3**. Ningún ADR ni DP aprobado las reconcilia. La única referencia, `milestones/m3-entry/MA.3-diseno-rotacion-audit-log.md:20, 82` (PROPUESTA, sin aprobar), cita «la purga a petición del usuario (Bible 5.5)» como si existiera, y no existe.
  - **Precedencia** (`docs/libro-01-gobernanza-y-metodo/1.1-constitucion-roles-autoridad.md` §3, `:62-83`):
    - El orden es: actas (`decisiones/`) > constitución > ADR `accepted` > capítulo de la Bible «Aprobado» > guías.
    - Los DP **no figuran** en esa jerarquía.
    - Entre rangos distintos prevalece el mayor; a igual rango, la aprobación del CEO más reciente (§3.2.1-2). `1.2:92`: si un
      ADR choca con un capítulo, «prevalece el ADR y el capítulo se corrige».
  - **Fuentes en juego:**
    - **Acta D1** (`decisiones/2026-07-17-acta-decisiones-fundacionales.md:44-47`, rango 1): datos «siempre bajo control del
      usuario».
    - **Acta del estándar de producto** (`decisiones/2026-07-28-estandar-de-trabajo-producto-demostrable.md:148-151`, rango 1):
      olvidar está terminado cuando el usuario puede «comprobar tras un reinicio que realmente fue olvidado». Admite tanto
      «fuera de la recuperación» como «fuera del disco» `[INFER]`.
    - **ADR-0017 §4** (accepted 2026-07-21, rango 3): el modelo del usuario debe poder «borrarse — total o selectivamente».
    - **ADR-0023** (accepted 2026-08-03, rango 3): append-only, retirar «nunca reescribiendo».
    - **Bible 5.5 §3** (rango 4): la cita de arriba.
    - **G-6**: en un DP aprobado por el CEO, sin rango normativo explícito.
  - **Lectura de rangos `[INFER]`:** ADR-0023 (rango 3) prevalecería sobre 5.5 §3 (rango 4) en lo que decide, que es el
    append-only. Que la lápida y el audit **conserven el valor** no lo decide ADR-0023, sino la implementación de G-6. Y ADR-0017
    (rango 3) apunta en sentido contrario.
  - **Este DP no resuelve la contradicción.** La registra como pendiente visible para el gate del CEO (1.1 §3.2.3).
    `decisiones/pendientes.md` **no se ha modificado** en esta misión: anotarla allí exige autorización.
- Si el comportamiento actual es aceptable, y en qué medida, es una decisión de soberanía del CEO (pregunta 4 y punto separado
  del §7). Este DP no propone cambiar G-6 ni la Bible.

**Relación con CM2:**
- D-AMP-3 es una **decisión global de soberanía**, no de medición. Se incluye porque el mapa la pone en S3, pero **no debería
  decidirse por conveniencia métrica**.
- Con el código actual, refutar y olvidar dejan rastro, así que el reloj **puede identificar los retirados sin depender de
  D-AMP-3**. Cómo cuentan en la tasa es una pregunta de medición (pregunta 5).
- Si se aprobara un borrado destructivo real, el reloj perdería esa identificación, salvo que conservara un id propio. Ese id
  sería un rastro de lo que el usuario pidió borrar.

## 5. Cómo funcionaría con la opción A (para que la decisión sea concreta) — PROPUESTA, nada construido

### 5.1 Mecánica

- **Sonda.** A los 7, 14 y 28 días de cada hecho declarado, el reloj consulta la memoria y registra
  `{hecho_id, edad_dias, resultado}` sin el texto del hecho.
- **Punto de entrada: sin decidir.** Hay dos candidatos `[LECT]` y ninguno es neutral:
  - **(i) Turno completo** (`handle_utterance`), con una consulta formulada como pregunta.
    - A favor: es la ruta real del usuario e incluye el filtro de vigencia del Core.
    - Una pregunta no se almacena en memoria (`orchestrator.py:3141-3143`).
    - En contra: entra en la ventana de diálogo en RAM y en el audit log como un turno más, y puede llegar al LLM si el Core no
      responde. Habría que marcarla como sonda.
  - **(ii) Subfunción del Core** (`recall` + `_da_por_cierto`).
    - A favor: es determinista.
    - En contra: no es «la ruta del usuario», hereda el residuo del eco episódico (§3) y exige justificar que no se crea un
      componente que ya tiene equivalente.
  - En ningún caso basta una llamada cruda a `MemoryStore.recall` (§3).
- **Consulta independiente** (requisito previo de A, no un detalle):
  - La consulta **no puede construirse con el texto almacenado**, porque acertaría siempre: sería una prueba decorativa.
  - Las vías posibles son la pregunta típica por ese atributo («¿cómo me llamo?»), que solo existe para hechos con atributo
    reconocido, o una paráfrasis fijada al declarar el hecho. La paráfrasis **es contenido nuevo retenido**, en tensión con
    el «ningún contenido nuevo» de A.
  - Generarla sin LLM no está resuelto. Si la pregunta 5 se encarga a 7.2, **A no puede construirse hasta entonces**
    (dependencia 1 → 5).
- **Calendario:** se deriva del historial (ADR-0023), para que sobreviva al reinicio. Nada vive solo en memoria de proceso.
- **Cuándo corre** (separado en dos, pregunta 2 del §7):
  - **(2a) Bajo demanda,** con `python -m aura_skeleton --medir-cm2`. El flag **no existe**: habría que construirlo. Es una
    medición explícita y no usa el ciclo autónomo.
  - **(2b) Al cierre de sesión.** **No hay punto de integración.**
    - `CentroNotificaciones.cerrar_sesion` (`aura_skeleton/core/notificaciones.py:92`) existe, pero en producción **no lo llama
      nadie**: solo `demo_capacidad_m2.py:232` y `tests/unit/test_notificaciones.py:96-114`.
    - Lo confirman un grep sobre `walking-skeleton/` y el grafo de Graphify (`~/.graphify/aura/graphify-out/graph.json`,
      construido en `6dad6af`): el nodo no tiene llamadores de producción.
    - `__main__.py` solo tiene Ctrl-D/EOF/KeyboardInterrupt y un `finally` por turno.
    - Hay que **crear** un enganche de fin de sesión: es un componente nuevo y pasa por la regla de demostrar antes que no
      existe equivalente.
- **Paradas (a) y (b):**
  - La sonda solo lee y emite un evento de auditoría; no ejecuta acciones del Motor Único. ADR-0024 no lo prohíbe; que lo permita es `[INFER]` (§3).
  - **No puede usar `memory.write`.**
  - **Falta probar** que la lectura funciona con el kill switch (b) armado, y también con la PARADA (a) armada, por el punto de entrada elegido y que el evento no contiene
    texto.
- **Informe:** `--medir-cm2` imprimiría:
  - la tasa a ≥ 28 días y el número de hechos en ventana;
  - los retirados, tratados según la pregunta 5;
  - las fabricaciones y las re-explicaciones detectadas, según las definiciones que se aprueben.
- **Honestidad (INV-9):** hasta que un hecho cumpla 28 días, y mientras no haya un mínimo de hechos, CM2 es **«sin datos
  suficientes»**, nunca «90 %».

### 5.2 Definiciones operativas — PROPUESTAS, pendientes de aprobación (pregunta 5 del §7)

Ninguna tiene definición oficial (§2). El reloj no puede medir sin ellas.

| Término | PROPUESTA | Límite / consecuencia |
|---|---|---|
| **Hecho en evaluación** | Un hecho declarado (`HECHO_DECLARADO`) con su **fecha de origen**: la primera declaración de esa identidad. Una re-declaración crea una versión nueva, pero no reinicia la fecha | Si la fecha se reiniciara, los hechos que el usuario repite no llegarían nunca a 28 días (sesgo de supervivencia). Solo cubre lo declarado (opción A) |
| **Recuperación correcta** | El punto de entrada elegido devuelve, para la consulta independiente, el valor **vigente** del hecho, **siempre que esa versión tenga ≥ 28 días** (o se mida la edad por versión) | Mide la retención y la recuperación del Core, **no** que la persona retome el tema en una conversación real (2.5:109). **Oráculo no independiente:** se compara con el mismo almacén que responde, así que un error de captura o una supersesión errónea cuentan como acierto. Sin la condición de edad por versión, un valor cambiado el día 27 contaría como «recuperado a 28 días» |
| **Hecho retirado** | Refutado, superseded (`valid_until`), retirado o con lápida | **A decidir:** excluirlo del denominador (riesgo: una retirada **no pedida por el usuario** saca un fallo del denominador e infla la tasa) o contarlo como no recuperado (castiga al usuario por ejercer su soberanía). Una variante: excluir solo las retiradas que inicia el usuario |
| **Fabricado** | La respuesta afirma un valor que **no** está en el historial vigente de ese hecho, o recupera un valor retirado como si fuera vigente | **Límite estructural:** si la respuesta sale del Core, se compara con el mismo almacén que la produjo (el oráculo comparte el modo de fallo) y daría 0 por construcción `[INFER]`. Si sale del LLM, hace falta un juez, y ADR-0014 se lo impide al LLM local `[INFER]`. Sobre texto libre hay que extraer el valor, y los hechos «recuerda que…» no tienen atributo tipado. **Con A, «cero fabricación» queda sin evidenciar** |
| **Re-explicación** | Un turno en el que el usuario vuelve a declarar un hecho **después de un fallo de recuperación observado en un turno real suyo**. Así lo pide 2.5:113: turnos que «**exigen** re-explicar» | Un fallo que solo detecta una sonda interna no le «exige» nada al usuario y no cuenta. La re-declaración voluntaria de un hecho que sí se recuperaba tampoco. No detecta re-explicaciones de temas no declarados. Hay que definir el denominador «turnos» |
| **Ventana** | Edad ≥ 28 días desde la fecha de origen, con sondas a 7 y 14 días como serie temprana | Las ausencias o caídas de hardware **pausan** la ventana de aceptación (2.2 §3.4); cómo se trasladan al reloj está por definir |
| **Tasa** | Recuperaciones correctas entre hechos en evaluación con edad ≥ 28 días, con los retirados tratados según lo que se decida | Con pocos hechos la cifra no es estable: hay que fijar un mínimo antes de mostrar un porcentaje |
| **Evaluación humana** | 7.2:38 la pide junto al LLM-as-judge: una muestra de turnos revisada por una persona, por ejemplo el CEO como en 2.5:153 | Es la vía compatible con ADR-0014 que identifica este DP (`[INFER]`; el juez externo se descarta por D24, también `[INFER]`) para evidenciar «cero fabricación» y re-explicación de temas no declarados. Tiene coste humano recurrente |
| **Identidad estable del hecho** | Un id **opaco** (no derivado del texto), asignado a la identidad del hecho (atributo o declaración) en su primera declaración y mantenido entre versiones | Si se derivara del contenido, sería un rastro de lo que el usuario olvidó (§4.1). Los hechos «recuerda que…» sin atributo tipado no tienen una identidad entre versiones resuelta en el código: **pendiente** |
| **Re-declaración** | Crea una versión nueva del mismo hecho (DR-2), **sin reiniciar la fecha de origen**. Solo cuenta como re-explicación si va precedida de un fallo de recuperación | Ver «Hecho en evaluación» y «Re-explicación» |
| **Retirada por el usuario frente a otras causas** | Distinguir `retirada_por` (`olvido`, `refutacion`, ya registrado en `core/ejecutor_modelo_usuario.py:171`) de una supersesión no pedida | Hoy solo se prueba `retirada_por="olvido"`; `refutacion` no tiene prueba. Una retirada accidental contada como exclusión inflaría la tasa |
| **Antigüedad** | La edad se mide desde la fecha de origen, no desde la última versión | `recall` no depende del tiempo (§5.3): la edad solo aproxima la interferencia de una memoria que crece |
| **Cambio de hardware** | **Sin propuesta.** Ningún documento dice si los datos medidos en HC-1 cuentan tras un cambio de equipo, que es la vía para CM1 (mapa §18-19) | **Pendiente del CEO** (§8). No hace falta para votar S3 |
| **Periodos de pausa** | **Sin propuesta.** 2.2 §3.4 dice que los eventos externos pausan la ventana de aceptación, pero no cómo se traslada eso a la edad de un hecho | **Pendiente** (§8) |

### 5.3 Qué demuestra la opción A frente a la aceptación de R1 (pregunta 3 del §7)

| Requisito de CM2 (2.5 §5.2) | Con la opción A |
|---|---|
| Ventana ≥ 4 semanas | **Cubriría**, para hechos declarados, una vez construido (proyección; hoy **no hay evidencia longitudinal**). Ojo: `recall` no depende del tiempo; lo que mide la edad es la persistencia más la interferencia de la memoria que crece |
| ≥ 90 % de **temas marcados como relevantes** | **Parcial:** equipara «declarado» con «marcado como relevante», y esa equivalencia no está en la Bible |
| > 10 % de re-explicación como fracaso | **Parcial:** solo la re-declaración de hechos declarados tras un fallo |
| Cero fabricación | **No evidenciado** sin evaluación humana (§5.2) |
| Sets derivados de los escenarios de 2.3 | **No demostrado:** los hechos declarados no se han mapeado a E-01 |

**Conclusión técnica (no es una decisión):** con la opción A, CM2 es un **indicador preliminar**. Que valga como **evidencia
suficiente** para aceptar R1 es una interpretación de 2.5 que solo puede fijar el CEO (2.5:153-154). Este DP no la da por
hecha ni rebaja el criterio.

**Sesgo de selección (no corregible solo con A):**
- El denominador solo incluye lo que el clasificador reconoce como `HECHO_DECLARADO` (`aura_skeleton/conectores/conversacion.py:209-228`). Un «recuerda que…» que no se capta es invisible.
- La consulta tipo por atributo, propuesta en la pregunta 5(c), restringe la muestra a los atributos tipados, que son los que mejor resuelve el Core.
- Las dos cosas inflan la tasa `[INFER]`.

**Límite de validez:** como `recall` es léxico, una prueba con reloj inyectado pasará aunque no se mida «memoria a semanas».
La variable que de verdad cambia con el tiempo es el tamaño y la composición de la memoria. Habría que registrarla como
covariable: número de entradas y presencia de términos ubicuos (D-M-1).

### 5.4 Pruebas que exigiría (al construir, no ahora)

- **TDD con reloj inyectado,** sin esperar semanas, más un **control de interferencia**: el mismo hecho, con memoria pequeña y
  con memoria grande.
- **Control obligatorio de retirados:** un hecho refutado, olvidado o con lápida **no** cuenta como recuperado. También con el
  eco episódico de una versión antigua, que hoy se filtra mal.
  - Hoy un eco marcado `retirada` **sigue saliendo en los `hits` de `recall`**, y ninguna prueba lo fija; solo se excluye del
    contexto del modelo (verificación del 2026-10-06).
  - `retirada_por="refutacion"` tampoco tiene prueba.
- **Control de consulta independiente:** una consulta construida con el texto almacenado se rechaza.
- **La sonda no escribe memoria:** el corpus es idéntico antes y después de cada sonda, y el evento de auditoría no contiene
  el texto del hecho.
- **Paradas armadas (a) y (b):** la sonda lee y emite el evento, sin ejecutar nada.
- **Reinicio:** el calendario se reconstruye desde el historial.
- **Conservación:** los eventos del reloj sobreviven a la rotación del audit log durante ≥ 28 días.
- **Mutación:**
  - de la **comparación** con los umbrales, que se leen de configuración porque son † propuestos;
  - del filtro de vigencia y de la fecha de origen;
  - del cableado en `composicion.py` («la composición no enciende el reloj»).

## 6. Qué NO cambia

- **CM1 sigue en P50 ≤ 800 ms**, criterio vigente comunicado por el CEO (CHECKPOINT 2026-09-28/29: «CM1 se mantiene
  (P50 ≤ 800 ms)… No autorizados: … cambio de CM1»). `milestones/m3-entry/ACTA-DECISION-CEO-CM1.md` lo repite, pero es un acta
  **preparada** (DECISION_REQUIRED), no firmada.
  - **Discrepancia documental registrada aparte, no se resuelve aquí:** Bible 2.5:102 (v1.1.0, cambio «HC-1» de auditoría
    aprobado el 2026-07-18) fija **R1 (nube) P50 ≤ 1200 ms** y **R2 (local) P50 ≤ 800 ms**.
  - La propia Bible se declara reconciliada (CEO, 2026-07-18). Es la decisión posterior del CEO, «CM1 se mantiene (P50 ≤ 800 ms)», que este DP lee
    como aplicable a R1 en local `[INFER]`, la que **no se ha trasladado** a 2.5. No hay ningún documento que articule las dos.
  - «HC-1» es ahí un hallazgo de auditoría, homónimo del equipo HC-1.
  - No afecta a S3; afecta a qué umbral aplica el gate de R1.
- R1-R4, D-3 y L4 siguen igual.
- La PARADA (a) del control-plane sigue armada; el kill switch (b) no se toca.
- La autoridad del LLM no cambia: no juzga relevancia ni fabricación.
- No se toca `main`.
- No se añade ningún permiso.
- **Con la opción A** no se añade ningún kind de memoria ni se guardan transcripciones nuevas. La opción B sí crearía
  retención nueva (§4).

## 7. Decisión requerida (CEO)

Cada pregunta separa los **hechos verificados** (alternativas, evidencia), las **inferencias** (línea propia o marca `[INFER]`),
las consecuencias y riesgos, y la **recomendación técnica del CTO**, que **no es una decisión**. La decisión pendiente es siempre
la pregunta. Ninguna alternativa se ha eliminado.

### Pregunta 1 · Set de evaluación de CM2

- **Pregunta:** ¿qué set mide CM2?
- **Alternativas:**
  - **A · hechos declarados;**
  - **B · marcado explícito por el usuario;**
  - **A ahora + B tras la decisión de retención** que corresponda (la decisión D u otra propia; lo indica el CEO);
  - **D · aplazar;**
  - **C · detección automática** sigue en la tabla del §4: el CTO **propone descartarla** por violar ADR-0014, pero el descarte
    lo decide el CEO.
- **Inferencias:** el sesgo de selección y la sobreestimación de A (§5.3) son `[INFER]`, sin medición.
- **Evidencia:** §3 y §4. Hoy se guardan los hechos declarados (`orchestrator.py:3134-3158`). No existe ningún set de «temas
  marcados como relevantes» (2.5:112).
- **Consecuencias:**
  - **A** permitiría empezar a medir sin retención nueva si la consulta independiente no exige paráfrasis guardadas (pregunta 5), pero solo da un **indicador limitado** sobre hechos declarados. **No es
    una evaluación integral de la memoria en la vida real** (§5.3).
  - **B** se ajusta al set que pide 2.5 (con el mismo límite de oráculo, §5.2), pero crea un archivo de temas y depende de una decisión de retención.
  - **D** no cuesta nada técnico; el tiempo de uso no cuenta para CM2.
- **Riesgos:**
  - A puede sobreestimar CM2 (sesgo de selección, §5.3) y **no puede construirse** sin resolver la consulta independiente
    (pregunta 5).
  - **Si el kill switch de AURA (b) se arma durante el uso real, A no registra hechos nuevos** (§3).
  - B crea retención nueva.
  - C viola la frontera cognitiva.
- **Recomendación técnica:** **A como indicador limitado**, con la condición de resolver antes la pregunta 5 (consulta
  independiente, tratamiento de los retirados y revisión humana). B solo después de la decisión de retención.

### Pregunta 2a · Medición bajo demanda (`--medir-cm2`)

- **Pregunta:** ¿se autoriza una medición explícita bajo demanda, fuera del ciclo autónomo y sin levantar la PARADA (a) del control-plane?
- **Alternativas:** son tres autorizaciones **independientes**:
  - **(i) diseño:** contrato, pruebas RED, eventos y sin código de producto;
  - **(ii) implementación**, con TDD, mutación y Quality Gate;
  - **(iii) inicio efectivo del reloj:** empieza a contar la ventana de cuatro semanas.
  - El CEO puede autorizar ninguna, (i), (i)+(ii) o las tres.
- **Evidencia:** el flag **no existe** (`grep -i cm2`: 0 resultados).
- **Inferencias:** que el kill switch (b) no impida leer ni emitir eventos de auditoría es una lectura de ADR-0024, sin prueba
  (§3).
- **Consecuencias:**
  - No cambia ninguna de las dos paradas.
  - **No autoriza ninguna clase nueva de registro de memoria:** el reloj no usa `memory.write`.
  - Los resultados irían como eventos de auditoría.
- **Riesgos:**
  - Construir (ii) sin la pregunta 5 resuelta produce una métrica sin definición.
  - Iniciar (iii) antes de tener pruebas haría inválidas las primeras semanas.
- **Recomendación técnica:** autorizar ahora solo **(i) diseño**. (ii) e (iii), cuando estén decididas las preguntas 1 y 5.

### Pregunta 2b · Medición automática al cierre de sesión

- **Pregunta:** ¿se autoriza además medir al cierre de sesión?
- **Alternativas:** sí / no / más adelante.
- **Evidencia:** `CentroNotificaciones.cerrar_sesion` (`aura_skeleton/core/notificaciones.py:92`) **no tiene llamadores en
  producción**: solo `demo_capacidad_m2.py:232` y `tests/unit/test_notificaciones.py:96-114`, verificado por grep el
  2026-10-06. `__main__.py` no tiene un evento de fin de sesión.
- **Inferencias:** ninguna relevante; los dos hechos están verificados por grep.
- **Consecuencias:** exige **crear un punto de integración nuevo**, con su propia justificación (regla de demostrar que no existe
  equivalente) y su propia autorización.
- **Riesgos:** un enganche automático añade una ejecución que nadie pide y que hay que probar con las paradas (a) y (b) armadas.
- **Recomendación técnica:** **no por ahora**. 2a basta para medir, y 2b se reevaluaría con datos de uso.

### Pregunta 3 · ¿Vale A como evidencia de CM2 para aceptar R1?

- **Pregunta:** ¿cuenta A como **evidencia** de CM2 para la aceptación de R1, o solo como **indicador preliminar**?
- **Alternativas:** evidencia suficiente / indicador preliminar / evidencia parcial que se complementa con la revisión humana
  de la pregunta 5.
- **Evidencia:** §5.3.
  - A **cubriría** la ventana sobre hechos declarados, una vez construido; hoy no hay datos longitudinales.
  - Cubre **parcialmente** «temas relevantes» y re-explicación.
  - **No evidencia** «cero fabricación».
  - No mapea sus sets a 2.3.
  - 2.5:153-154 reserva el veredicto y la zona intermedia al CEO.
- **Inferencias:** que A «cubriría» la ventana es una proyección sobre algo no construido.
- **Consecuencias:** si A contara como evidencia suficiente, el criterio de 2.5 se aplicaría de forma más estrecha que su texto.
- **Riesgos:** **rebajar CM2 sin un acta**. Por otro lado, R1 sigue bloqueado por CM1 (§1), así que esta pregunta no cambia
  nada inmediato.
- **Recomendación técnica:** **indicador preliminar**, no evidencia suficiente por sí sola. El criterio de aceptación no se
  toca.

### Pregunta 4 · D-AMP-3 (FORGET vs DELETE)

- **Pregunta:** ¿política **A** (coexistencia de `refutar`, `borrar` destructivo y `FORGET`, con borrado destructivo nunca
  automático) o política **B** (sustituir `borrar` por `FORGET`)? Fuente: `AMP-AURA-DECISIONES.md:83-113`; sin firmar.
- **Evidencia:** §4.1.
  - DR-2 = A ya decidió, sobre otra pregunta, que el olvido actúa por versión, conserva las versiones anteriores y conserva
    los ecos «para auditoría».
  - El código actual no tiene ningún borrado destructivo y conserva el texto olvidado en cuatro sitios, uno de ellos el audit
    log, en coherencia con G-6.
- **Inferencias:** que G-6 **exija** conservar el valor, y por tanto que cada política «choque» con G-6, es `[INFER]`
  (DP-D-M-8:193 dice «antes/después».)
- **Consecuencias, por comportamiento (§4.1.1) — las dos políticas cambian el estado actual:**
  - **Política A** (mantiene `borrar` destructivo y añade FORGET con «valor fuera»):
    - Exige **construir** la eliminación física (comportamiento 4) para `borrar`, que hoy no existe. Es lo que pide la Bible
      5.5 §3.
    - Esa eliminación choca con **G-7** («tras un olvido el fichero **no** pierde líneas», `DP-D-M-8:194`, aprobado), con
      **G-6** (`[INFER]`) y con ADR-0023, salvo excepción expresa.
    - Además, su FORGET también exige quitar el valor (comportamiento 3) de la lápida y, si G-6 lo permite, del audit log.
  - **Política B** (todo borrado es FORGET con «valor fuera»):
    - No construye eliminación física y es compatible con G-7 y ADR-0023.
    - Por sí sola **no cumple la Bible 5.5 §3**: la lápida deja rastro, y 5.5 pide eliminar «el dato y su rastro en índices y
      backups».
    - Pero **también cambia el comportamiento 3**: la lápida y la copia del audit log no deberían conservar el valor, y hoy lo
      conservan. Chocaría con G-6 en la misma medida que A `[INFER]`.
    - Hoy el código **no es B**: deja lápida, pero conserva el valor.
  - **Dimensiones de la fuente** (`AMP-AURA-DECISIONES.md:94-104`):
    - Con `borrar` destructivo, un borrado malicioso es **indetectable** y se pierde el qué en la auditoría.
    - Con FORGET, «AURA recuerda que había algo», el almacén crece de forma monótona y el cumplimiento exige justificar que la
      lápida no es dato personal (`[HIPO]`).
  - **Si no se firma:** se mantiene el estado de hecho, que no es ni A ni B (§4.1.1). No es una opción de la fuente; es lo que
    ocurre si la decisión se aplaza.
- **Riesgos:**
  - Decidir D-AMP-3 por conveniencia de la medición.
  - Que el usuario crea que «olvida X» elimina X cuando solo lo retira de la recuperación.
- **Recomendación técnica:** firmar D-AMP-3 **por separado de S3**, porque es una decisión global de soberanía y el reloj no la
  necesita para identificar los retirados. Al firmarla, decidir **expresamente** el comportamiento 3, conservar o no el valor,
  incluida su relación con G-6. Sobre ese punto, el CTO **no recomienda** ninguna opción: corresponde al CEO.

### Pregunta 5 · Definiciones operativas y protocolo de CM2

- **Pregunta:** ¿se aprueban las PROPUESTAS del §5.2, se modifican o se remiten a 7.2 antes de construir? Cubren hecho en
  evaluación, fecha de origen, identidad estable, recuperación correcta, fabricado, re-explicación, ventana, tasa, retiradas,
  antigüedad y consulta independiente.
- **Sub-decisiones:**
  - **(a) Retirados:** ¿se excluyen del denominador, se cuentan como no recuperados, o se excluyen solo los que retira el
    usuario?
  - **(b) Revisión humana** (7.2:38): ¿se incorpora una muestra revisada por una persona para fabricación y re-explicación?
  - **(c) Consulta independiente:** ¿pregunta tipo por atributo, o paráfrasis fijada al declarar? La paráfrasis es contenido
    nuevo.
- **Evidencia:** §2 (no hay definiciones oficiales) y §5.2.
- **Inferencias:** el oráculo circular de «fabricado» y los sesgos del §5.2 son análisis `[INFER]`, sin ejecutar.
- **Consecuencias:**
  - Sin definiciones, el reloj no puede medir.
  - Remitirlas a 7.2 retrasa A.
- **Riesgos:**
  - Los sesgos descritos en el §5.2 (supervivencia por re-declaración, retiradas accidentales, el oráculo de «fabricado» que
    comparte el modo de fallo).
  - Afirmar «cero fabricación» sin revisión humana.
- **Recomendación técnica:** aprobar las propuestas como **provisionales y revisables**, solo para construir el indicador de A:
  - (a) excluir únicamente las retiradas que inicia el usuario y contar las demás como no recuperadas;
  - (b) sí a la revisión humana por muestreo; sin ella, «fabricación» se presenta como **no evidenciada**;
  - (c) la pregunta tipo por atributo donde exista; sin paráfrasis almacenadas hasta una decisión de retención.
  - Nada de esto se convierte en política vigente sin la firma del CEO.

### Puntos separados (no son preguntas de S3)

- **Persistencia física del contenido olvidado.** Hoy el texto olvidado sigue en la memoria (línea original, lápida y ecos) y en
  el audit log inmutable, **incluidos los segmentos sellados con `sha256`**, que la rotación nunca borra (§3). No existe purga
  (§4.1.1, §4.1.3). Hay que distinguir tres cosas: retirar de la memoria activa (hecho), conservar metadatos del olvido
  (hecho) y conservar el texto literal (hecho, sin decisión expresa).
  - ¿Es aceptable?
  - ¿Debe ponderarse G-6 frente al «valor fuera»?
  - ¿Debe informarse al usuario de que «olvida» retira de la recuperación pero no borra del disco?
  - **Contradicción a resolver:** Bible 5.5 §3 (borrado que elimina el dato y su rastro, verificable) frente a G-6 / G-7 / ADR-0023 / ADR-0017
    (reconstrucción y append-only); el código cumple los segundos (§4.1.3).
  - Decisión de soberanía del CEO. Puede tratarse dentro de la pregunta 4 o por separado.
- **Umbral de latencia del gate de R1.** El criterio vigente es **P50 ≤ 800 ms**, decidido por el CEO (CHECKPOINT
  2026-09-28/29).
  - La Bible 2.5:102 (v1.1.0) se presenta como «reconciliado por HC-1, CEO 2026-07-18»: ≤ 1200 ms en nube para R1 y ≤ 800 ms
    en local para R2. Después, el CEO decidió «CM1 se mantiene (P50 ≤ 800 ms)» (2026-09-28/29), que este DP lee como aplicable a R1 en local
    `[INFER]`. **Ningún documento articula las dos
    decisiones.**
  - Medido el 2026-10-06 `[EJEC]`: P50 ≈ 7,9 s. Supera las dos cifras, 800 y 1200 ms. Si 1200 ms aplica o no a una medida
    local es parte de la discrepancia.
  - Resolución documental pendiente, separada de S3.

Hasta que se decida, **no se construye nada de S3**.

## 8. Información que falta (no la aporta ningún documento)

- **Protocolo de CM2 en 7.2:** no existe. 7.2:38 pide «LLM-as-judge + evaluación humana». ADR-0014 impide que el LLM local
  juzgue; un juez externo entraría en conflicto con D24 `[INFER]`.
- **Correspondencia de los hechos declarados con los escenarios de 2.3 (E-01):** sin hacer.
- **Mínimo de hechos** para que la tasa sea estable: sin fijar.
  - Con P50 ≈ 7,9 s por turno de voz, el uso diario puede producir pocos hechos declarados `[INFER]`.
- **Pausas de la ventana** (2.2 §3.4) trasladadas a un reloj automático: sin definir.
- **Validez de los datos de CM2 tras un cambio de hardware:** CM1 se resolvería con hardware objetivo (mapa §18-19), y la
  aceptación exige CM1–CM4 sostenidos en la misma ventana. Ningún documento dice si los datos medidos en HC-1 contarían
  después. Es una decisión futura del CEO; no hace falta para votar S3.
- **Contradicción Bible 5.5 §3 frente a G-6 / G-7 / ADR-0023 / ADR-0017** sobre el borrado (§4.1.3): no hay ningún documento que la
  reconcilie.
- **Id del hecho:** si se deriva del contenido, es un rastro de lo que el usuario olvidó. Hay que definir un id opaco.

## 9. Registro de revisión

| Fecha | Cambio | Motivo / evidencia |
|---|---|---|
| 2026-10-04 | Borrador inicial | — |
| 2026-10-06 | **Corrección documental autorizada por el CEO antes de la votación.** **Corregido:** «24/24»; decisión D; regla de almacenamiento; filtro de `recall`; inexistencia de `--medir-cm2` y del cierre de sesión; estado real de `borrar`/`olvidar` (lápida con el texto); D-AMP-3 descrita sobre la fuente (la A conserva `borrar` destructivo). **Añadido:** D-AMP-3 (§4.1, pregunta 4); definiciones operativas como PROPUESTA (§5.2, pregunta 5, con evaluación humana de 7.2:38); alcance de A frente a R1 (§5.3); límites de validez (oráculo de «fabricado», edad e interferencia); CM1 frente a S3 (§1, con mapa:175); discrepancia de latencia (§6); contrapeso de urgencia en D. **Reformulado:** C pasa de «descartada» a «el CTO propone descartarla; decide el CEO»; la pregunta 2 se separa en 2a/2b; se añaden las preguntas 4 y 5 | **Revisiones:** `auditor-consistencia`, `arquitecto-evaluador` y `explorador-repositorio` (AURA); `verificador-mutacion` en modo solo lectura (pytest 293 passed sobre 10 ficheros, sin ejecutar mutación); `architect` de ECC como revisor externo, porque Codex y OpenCode no están instalados; consulta del grafo de Graphify (artefacto en `6dad6af`; la CLI no está instalada). Citas verificadas por lectura directa. **Las opciones A/B/C/D no cambian de definición; no se decide ninguna pregunta** |
| 2026-10-06 (v3) | **Revisión final previa a la votación, ordenada por el CEO.** **Añadido:** los cuatro comportamientos del olvido (§4.1.1); el análisis de DR-2 y de «conservando historial» (= versiones anteriores, no el valor olvidado; §4.1.2); el texto olvidado en el audit log por G-6; la contradicción con Bible 5.5 §3 (§4.1.3); las variables de medición que faltaban en §5.2 (identidad, re-declaración, retiradas, antigüedad, hardware, pausas); el §7 por decisión, con recomendación técnica separada y 2a en tres niveles; el eco retirado en `hits` sin prueba (§5.4). **Corregido:** la rotación del audit log no pierde eventos (sella segmentos), así que el riesgo pasa a ser «leer segmentos + activo»; el texto de un hecho entra al audit log **desde la declaración** (`ejecutor_modelo_usuario.py:282-288`), no solo a través de los ecos; se distinguen las dos paradas, PARADA (a) del control-plane y kill switch (b) de AURA, y se señala la dependencia de A respecto de (b); las consecuencias de la pregunta 4 pasan a ser simétricas (las dos políticas cambian el comportamiento 3; G-7; dimensiones de la fuente; estado de hecho si no se firma); precedencia citada (1.1 §3; ADR-0017; actas D1 y estándar de producto); circularidad y edad por versión en «recuperación correcta»; re-explicación solo tras un fallo observado; sesgo de selección; la recomendación sale de la tabla del §4; 2.5:102 se declara reconciliada por la propia Bible | Lectura directa de `modules/memory.py`, `core/ejecutor_modelo_usuario.py`, `observability.py`, ADR-0023, DP-D-M-8, Bible 5.5 y `DECISIONES-REQUERIDAS-2026-09-15.md`. `verificador-mutacion` en solo lectura (pytest 47 passed sobre 6 ficheros). Revisión externa de ECC y auditorías de AURA (ver el informe de la misión). **No cambia ninguna opción ni decide ninguna pregunta** |
| 2026-10-06 (v4) | **Cierre de la revisión documental, ordenado por el CEO.** Se marcan como `[INFER]` las afirmaciones que eran lecturas o proyecciones: que G-6 «exija» el valor y los choques que se derivan de ello; que el kill switch (b) permita leer y emitir eventos; DR-2 = versiones; «R1 en local»; la retención de 28 días por diseño; «A cubriría»; la única vía compatible. Se cita el artefacto de la medición de latencia `[EJEC]`. Se hacen explícitos el texto olvidado en los **segmentos sellados** del audit log, la distinción entre retirar, metadatos y texto literal, y la **ausencia de evidencia longitudinal**. El §7 tiene una línea de «Inferencias» por pregunta. Se añaden G-7 y ADR-0017 en el conflicto de §7 y §8 | Revisión de ECC `architect` (hechos frente a inferencias) y lectura directa. **No cambia ninguna opción, recomendación ni pregunta** |
