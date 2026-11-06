---
documento: "Propuesta técnica mínima — diseño del reloj de CM2 (S3)"
tipo: "PROPUESTA DEL CTO/COO. NO AUTORIZADA. No es diseño aprobado ni código; no cambia el estado del DP."
fecha: 2026-10-06
depende_de: "DP-S3-RELOJ-CM2.md §7 — pregunta 1 (= A), pregunta 5 (definiciones) y pregunta 2a(i) (diseño), sin votar"
estado: "EN ESPERA DE AUTORIZACIÓN"
---

# Propuesta mínima: diseño del reloj de CM2

`[LECT]` leído · `[INFER]` deducido. **Nada de esto está construido ni autorizado.** Sirve para que, si el CEO vota Q1 = A, Q5 y
Q2a(i), el diseño arranque sin volver a investigar. **No implementa el reloj, no inicia la ventana, no fija política de
retirados (Q5a), no toca D-AMP-3 ni E-Q1 y no cambia CM1.**

## 1. Qué se reutiliza, y qué no

Las piezas se localizaron con el grafo de Graphify (`~/.graphify/aura/graphify-out/graph.json`, construido en `6dad6af` el
2026-09-21). Ese grafo está **desfasado** respecto al árbol actual: por ejemplo, sitúa `_da_por_cierto` en la L483, cuando hoy
está en la L516. Por eso cada línea se confirmó leyendo el código `[LECT]`.

| Necesidad del reloj | Pieza existente | Fuente |
|---|---|---|
| Leer el historial completo, sobrevivir al reinicio y a la rotación | `obs.leer_audit_desde(ruta, -1)` / `AuditLog.reconstruir()`: activo + segmentos, ordenados por `seq` | `aura_skeleton/observability.py:175-232` |
| Registrar el resultado de cada sonda | `obs.log(..., audit=True)` hacia `AuditLog` (append-only, sellado) | `observability.py:98-160` |
| Población de hechos declarados | La **procedencia de la entrada de memoria** ya guarda `clase` y `origen` («declarada» / «observada») y `ts` | `aura_skeleton/core/almacen_senales.py:50-58` |
| Fecha de origen | `valid_from`, derivado del `ts` de la señal (no del `ts` de auditoría: «dos relojes para el mismo hecho es un hecho con dos historias») | `core/ejecutor_modelo_usuario.py:272-281` |
| Retirada y su causa | Procedencia: `refutada`, `valid_until`, `retirada`, `retirada_por`; lápida `_olvidada` | `core/orchestrator.py:516-528`; `core/ejecutor_modelo_usuario.py:171`; `modules/memory.py:117` |
| Filtro de vigencia del Core | `_da_por_cierto` | `core/orchestrator.py:516-528` |

**`ConectorDeAuditoria` NO se reutiliza** (`aura_skeleton/conectores/auditoria.py:63-75`) `[LECT]`:
- Descarta todo lo que no sea de su módulo y no empiece por «EJECUTA ».
- Emite `Senal` que el orquestador guarda como memoria a través de `registrar_informacion_usuario` (`core/orchestrator.py:3108-3110`).
- Un «conector cm2» cableado así **escribiría memoria**, justo lo que la sonda no puede hacer.

Tampoco hace falta un **cursor**. Las sondas a 7/14/28 días necesitan eventos antiguos. El reloj releería el historial desde el
principio y deduciría las sondas ya hechas a partir de sus propios eventos `cm2`. Así es idempotente y regenerable
(ADR-0023:82), sin estado propio.

## 2. Identidad del hecho: problema abierto que el diseño tiene que resolver

El `seq` del evento de registro es estable (`observability.py:126, 209-232`), pero **no sirve como `hecho_id`** `[LECT]`:
- **No separa la población.** El mensaje de auditoría no lleva `clase` ni `origen`, y por el mismo registro entran señales
  observadas.
- **No hay enlace.** La entrada de memoria no guarda ese `seq`. El `trace_id` no es único: las señales de un turno comparten
  `tid`, y una corrección usa el literal `"correccion"` (`core/modelo_usuario.py:95`).
- **Leer el mensaje para unir obligaría a comparar texto** (E-Q1).

**Lo que tendría que incluir el diseño autorizado:** un **id opaco** asignado al registrar la entrada, guardado en su procedencia
y emitido como **campo estructurado** del evento de auditoría, sin texto. Para los atributos tipados, valorar la pareja
`(identidad, versión)`, que el ejecutor ya maneja (`ejecutor_modelo_usuario.py:237-238`). Es un cambio de código en un
componente de memoria: **no se hace aquí**.
- **Precedente que exige autorización expresa:** el propio ejecutor eligió `(identidad, versión)` «para no inventar un campo `id`
  fuera de la autorización» (`ejecutor_modelo_usuario.py:237-238`). Añadir un id opaco entra, por tanto, en la autorización del
  diseño (Q2a(i)), no en la de esta propuesta.

**Exclusión que hay que declarar (no decidida):** el eco episódico «usuario dijo: …» se escribe sin auditoría
(`orchestrator.py:3158` → `memory.py:162`). Si la población se toma de los hechos registrados, los ecos quedan fuera. Eso forma
parte de la definición de «hecho en evaluación» y la decide **Q5**.

## 3. Contrato propuesto (a validar en el diseño autorizado)

- **Evento de sonda** (`obs.log(..., audit=True)`, módulo `cm2`, **sin texto**):
  `{hecho_id, edad_dias, version_edad_dias, estado_retirada, resultado_recuperacion}`.
  - **`estado_retirada`** = la causa en bruto (`refutada`, `valid_until`, `retirada_por`, lápida, o ninguna), sin clasificarla.
  - **`resultado_recuperacion`** se registra **siempre** e independientemente: `vigente`, `valor_retirado`, `nada` o
    `sin_consulta`.
  - Así no se tapa el caso «recupera un valor retirado como si fuera vigente», que el DP §5.2 llama **fabricado**.
- **Tasa:** función pura sobre los eventos. **El mapeo de causas a numerador y denominador es un parámetro**, la regla que
  apruebe Q5a. Ningún código ni prueba fija esa política antes. Devuelve `"sin datos suficientes"` por debajo de 28 días o del
  mínimo que fije Q5 (INV-9).
- **Punto de entrada de la sonda (Q5c / DP §5.1): sin decidir.** Con la opción (i), `handle_utterance`, la respuesta puede venir
  del LLM y dejar de ser determinista (ADR-0014).

## 4. Pruebas RED que abriría el diseño autorizado (no escritas)

1. El evento de sonda no contiene el texto del hecho ni ningún derivado.
2. `hecho_id` es opaco, no se deriva del contenido y se mantiene estable tras reiniciar y rotar el audit log.
3. *(Condicionada a Q5)* Calendario con reloj inyectado: las sondas caen a 7/14/28 días de `valid_from` de la primera
   declaración. Una re-declaración no reinicia la fecha.
4. Un hecho retirado registra su causa en bruto **y** el resultado de la recuperación por separado. Control: si recupera un
   valor retirado, consta `valor_retirado`, no `vigente`.
5. La tasa devuelve `"sin datos suficientes"` por debajo del mínimo, y aplica la regla de denominador **recibida como parámetro**.
6. *(Condicionada al punto de entrada de Q5c)* Con la PARADA (a) y el kill switch (b) armados: la sonda lee y emite el evento,
   sin ejecutar nada ni escribir memoria (corpus idéntico antes y después).
7. Idempotencia: releer el historial dos veces no duplica sondas.
8. Mutantes candidatos: umbral de 28 días; comparación de la tasa; filtro de vigencia; `hecho_id` derivado del contenido;
   `resultado_recuperacion` anulado por `estado_retirada`; cableado en `composicion.py`.

**No se propone** ninguna prueba sobre si un eco retirado sale en los `hits` de `recall`: fijaría una política pendiente
(E-Q1 / D-AMP-3). La limitación queda documentada en el DP §5.4.

## 5. Riesgos que el diseño tendría que cerrar

- **Sin auditoría configurada no hay `seq`** (`observability.py:68`). El reloj exige `configure_audit` activo, que es el caso
  normal en `composicion.py`.
- **Contenido en el audit:** el evento «registrada sobre …» lleva el texto (E-Q1). El reloj no tiene que leer mensajes: el id
  opaco estructurado (§2) lo evita.
- **Kill switch (b) armado:** no hay declaraciones nuevas, así que no hay hechos que medir. El informe tiene que decirlo en vez
  de mostrar 0 %.

## 6. Qué desbloquea esta propuesta

Con **Q1 = A**, **Q5** (al menos a, b y c, más la decisión sobre los ecos) y **Q2a(i)** votadas, el siguiente paso son las
pruebas RED 1, 2, 4, 5 y 7, el id opaco y el contrato del evento. Sin implementar la sonda real ni iniciar la ventana, que
dependen de Q2a(ii) y (iii).

## 7. Evidencia nueva para decidir Q5 (2026-10-06, `[EJEC]` salvo indicación)

**7.1 Qué entra hoy en la población A.** Se ejecutaron el clasificador real (`conectores/conversacion.py::_clasificar`) y el
destino de memoria (`core/intencion.py::destino_de_memoria`) sobre frases de ejemplo:

| Frase | ¿`HECHO_DECLARADO`? | Destino en memoria |
|---|---|---|
| «me llamo Mauricio» | Sí | recuperable (eco) **y** hecho registrado |
| «mi color favorito es el azul» | Sí (apertura posesiva genérica «mi X es Y») | recuperable (eco) **y** hecho registrado |
| «trabajo en Lenovo» | Sí | recuperable (eco) **y** hecho registrado |
| «recuerda que mi coche es rojo» | Sí, por el «mi X es Y» interior | recuperable (eco) **y** hecho registrado |
| «recuerda que tengo cita el lunes» | **No** | **solo el eco** «usuario dijo: …» |
| «recuerda que soy alérgico a la penicilina» | **No** | **solo el eco** |
| «mi perro se llama Toby» | **No** | **solo el eco** |
| «¿cómo me llamo?» | No (es pregunta) | no se almacena |

**Consecuencias `[INFER]`:**
- **La población A son solo las declaraciones tipadas:** `_HECHO` en `conversacion.py:74-99`, es decir «me llamo», «mi nombre
  es», «trabajo en/de», «proyecto llamado», «mi proyecto se llama» y «mi X es Y» con X de uno o dos términos.
- **«recuerda que…» no hace que algo sea un hecho declarado.** El ejemplo del DP §4, fila A, es **inexacto**. Esta misión no
  modifica el DP; la corrección queda propuesta.
- **Las declaraciones no tipadas viven solo como eco episódico,** sin auditoría y sin `seq`. Por eso la decisión sobre los ecos
  de Q5 es, en la práctica, la decisión entre medir **solo atributos tipados** o también la memoria libre:
  - **Excluir los ecos:** población limpia y medible con preguntas tipo deterministas, pero estrecha. El sesgo de selección del
    DP §5.3 queda confirmado.
  - **Incluir los ecos:** la población representa la memoria real, pero sin pregunta tipo. Hay que resolver la consulta
    independiente (Q5c) y la identidad del eco, que hoy no tiene id ni evento auditado.

**7.2 ¿Es determinista la pregunta tipo?**
- Las 58 pruebas de `tests/unit/test_hecho_declarado_sin_llm.py` y `tests/integration/test_hechos_declarados.py` pasan
  (`58 passed`). Entre ellas, la respuesta del Core «sin llamar al modelo», con un proveedor que falla si se le invoca.
- `_responder_hecho` (`core/orchestrator.py:2381-2425`) responde las consultas de la tabla `_CONSULTAS_DE_HECHO` (`:277-300`) y
  las de forma «¿cuál es mi X?» solo con hechos **vigentes** de clase `HECHO_DECLARADO`.
- Si no hay correspondencia, no responde y deja decidir a la puerta de ADR-0014.
- Para la población A tipada, el punto de entrada (i) por turno **sería determinista** cuando el hecho existe `[INFER]`. Cuando
  no existe, el turno sigue la ruta de ausencia de ADR-0014.

## 8. Clasificación de las actividades y qué decisión desbloquea cada una

| Actividad | Categoría | Estado | La desbloquea |
|---|---|---|---|
| Mapa de reutilización y dependencias (§1), evidencia de la población y del determinismo (§7) | Documental / análisis | **Hecho** | — |
| Alternativas de identidad del hecho (§2) y de contrato (§3), descritas sin elegir | Diseño reversible | **Hecho, como alternativas** | — |
| Elegir la población: solo tipados, o tipados + ecos | Decisión de métrica | Pendiente | **Q5** (hecho en evaluación y ecos) |
| Elegir la consulta: pregunta tipo, o paráfrasis guardada (contenido nuevo) | Decisión de métrica y privacidad | Pendiente | **Q5c** (y E-Q1 si se guarda contenido) |
| Regla de numerador y denominador para los retirados | Decisión de métrica | Pendiente | **Q5a** |
| Revisión humana para fabricación | Decisión de protocolo | Pendiente | **Q5b** |
| Id opaco del hecho en la procedencia y en el evento (cambio de código en memoria) | Código | No iniciado | **Q2a(i)**, más la población decidida en Q5 |
| Pruebas RED 1, 2, 4, 5 y 7 | Pruebas | No escritas | **Q2a(i)** y **Q1 = A** |
| Sonda real y `--medir-cm2` | Código | No iniciado | **Q2a(ii)** |
| Inicio de la ventana de 4 semanas | Activación | No iniciado | **Q2a(iii)** |
| Corrección del ejemplo «recuerda que…» del DP §4 | Documental en el DP | Propuesta, no aplicada | Autorización para editar el DP |

**Conclusión `[INFER]`:** no queda trabajo técnico que pueda avanzar sin fijar alguna de estas decisiones. **El primer
desbloqueo útil es Q1 + Q5 (la población, sobre todo los ecos) + Q2a(i).** Con eso se pueden escribir las pruebas RED sin
decidir nada más.

## 7. Registro

| Fecha | Cambio |
|---|---|
| 2026-10-06 (2) | Añadidos §7, evidencia ejecutada sobre la población A y el determinismo de la pregunta tipo, y §8, la clasificación de actividades frente a decisiones. Ningún código cambiado |
| 2026-10-06 | Primera versión. Una revisión acotada de ECC (`architect`) corrigió la reutilización de `ConectorDeAuditoria` (filtra «EJECUTA » y escribiría memoria), el cursor (contradice un calendario regenerable), el `seq` como `hecho_id` (no separa la población ni tiene enlace), la exclusión implícita de los ecos, y las pruebas 4 y 6, que imponían políticas pendientes. Verificado leyendo el código |
