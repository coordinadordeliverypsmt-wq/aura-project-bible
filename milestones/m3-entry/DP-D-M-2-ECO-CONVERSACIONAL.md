# Decision Package — D-M-2: el eco del propio turno desactiva ADR-0014

**Estado (CEO, 2026-08-03):**

- ✅ **Diagnóstico de D-M-2 APROBADO**, y la investigación con él.
- ❌ **Implementación de Op-5 NO AUTORIZADA.**
- ➡️ **Queda supeditada a `D-M-7`.** El CEO dictaminó que D-M-2 y D-M-7 comparten el mismo núcleo
  arquitectónico, y que el DP de D-M-7 debe definir **primero el modelo general de clasificación de
  intención**. Una vez aprobado ese marco, se retoma este DP para decidir cuál es la solución correcta
  **dentro** de él.

**Razón de la reserva, en palabras del CEO:** la investigación demuestra que el autoeco existe, pero no
demuestra que la regla correcta sea «las preguntas no deben almacenarse». Antes hay que responder cómo
clasifica AURA la intención de una interacción y qué información debe convertirse en memoria
recuperable. **Comparto el razonamiento:** Op-5 es una heurística local para un problema de nivel
superior, y adoptarla ahora arriesgaba construir un segundo detector que después habría que unificar.

**No se ha modificado el repositorio ni implementado ninguna alternativa.** Todas las mediciones
proceden de prototipos ejecutados fuera del árbol de código.

**Recomendación original (en suspenso hasta el marco de D-M-7):** **Op-5 — no almacenar como recuerdo
recuperable las entradas interrogativas**, detectadas por signo de interrogación o palabra
interrogativa inicial.

**Clasificación de evidencia** (D47): `[EJEC]` salvo marca explícita.

---

## 1 · El defecto

`orchestrator.py:636` (`_finalizar_turno`) escribe `usuario dijo: {text}` en **las 7 rutas del turno**
—se invoca desde las líneas 341, 346, 352, 355, 361, **373** y 398—. La 373 es **la propia rama de
ADR-0014**, que responde «No tengo ningún recuerdo registrado sobre eso» sin llamar al LLM… y acto
seguido almacena la pregunta.

La pregunta queda indexada y **cubre su propia repetición con cobertura 1,00**, porque los verbos de
evocación (`acordamos`, `recuerdas`, `dijimos`…) están en `_VACIAS` y se descartan en ambos lados:

```
consulta  '¿Que acordamos sobre el presupuesto del trimestre?' → {presupuesto, trimestre}
eco       'usuario dijo: ¿Que acordamos sobre el presupuesto…'  → {dijo, presupuesto, trimestre, usuario}
cobertura 2/2 = 1,00  ≥ 0,60
```

**Reproducción, misma pregunta tres veces `[EJEC]`:**

| | turno 1 | turno 2 | turno 3 |
|---|---|---|---|
| **Hoy** | ADR-0014 activa | **DESACTIVADA** (1 hit) | **DESACTIVADA** (2 hits) |

El contexto que recibe el LLM en el turno 2 es literalmente
`[contexto memoria: usuario dijo: Que acordamos sobre el presupuesto del trimestre?]` — **la propia
pregunta del usuario, presentada como recuerdo**.

### Los dos efectos, con superficies muy distintas

1. **Apaga ADR-0014** cuando esta se activaría. Superficie **estrecha** — ver §2.
2. **Inyecta la pregunta del usuario en el contexto del LLM** en cualquier repetición, se active
   ADR-0014 o no. Superficie **amplia**: ocurre en todo el camino conversacional.

El segundo efecto es el que hace grave a D-M-2 con independencia de lo que se decida sobre ADR-0014.

---

## 2 · Hallazgo colateral — **D-M-7**, que no estaba buscando

Investigando este DP apareció un defecto **distinto y probablemente mayor**, que se registra aparte y
**no se resuelve aquí**:

> **`_es_consulta_de_memoria` no reconoce NINGUNA de las 77 consultas de la batería oficial `[EJEC]`.**
> Tampoco ninguna de las **24 negativas**, que son exactamente las que ADR-0014 existe para proteger.

`orchestrator.py:75-78` decide por **subcadena** sobre 15 literales (`acordamos`, `recuerdas`,
`te conté`…). Consecuencia medida:

| Entrada | ¿Activa ADR-0014? |
|---|---|
| «¿Cuál es el nombre de mi abuela?» | **No** |
| «¿Cuál es la combinación de mi caja fuerte?» | **No** |
| «Mi preferencia es la luz tenue por la noche» *(afirmación)* | **Sí** — falso positivo |
| «Te conté que trabajo en logística» *(afirmación)* | **Sí** — falso positivo |

Es decir: **la garantía de no-fabricación cubre una fracción estrechísima del espacio real de
preguntas**, y se dispara sobre afirmaciones que no lo son. 4 de 8 afirmaciones probadas dieron falso
positivo `[EJEC]`.

**Clasificación: defecto real, deuda crítica, independiente de D-M-2.** Se registra en
`DEUDA-N1-RECUPERADOR.md`. **Decisión del CEO pendiente** sobre si se aborda a continuación; mi lectura
es que sí, y probablemente antes que D-M-1.

---

## 3 · Hechos que condicionan el diseño

| Hecho | Evidencia |
|---|---|
| **El eco es el único consumidor real de `recall` en producción** | `orchestrator.py:363` es el único llamador `[EJEC]` |
| **`recall` NO lee `kind` en ningún punto** — ni N1 ni N2 | `[EJEC]` verificado en las tres implementaciones |
| `kind == "episodica"` es **hoy exclusivo del eco** | `[EJEC]` único emisor en producción: `orchestrator.py:636` |
| `provenance["fuente"] == "conversacion"` **NO discrimina el eco**: lo comparte con las señales capturadas | `[EJEC]` `almacen_senales.py:42` |
| `ModeloUsuario` ya filtra por `kind` (`_TIPOS`), así que **no ve el eco** | `modelo_usuario.py:119` `[EJEC]` |
| **La respuesta de AURA no se almacena**; solo vive en un buffer RAM de 6 turnos | `orchestrator.py:638-640` `[EJEC]` |
| Existe precedente de filtrado por `kind` en lectura y primitivas `olvidar`/`marcar` con predicado | `modelo_usuario.py:92-113` `[EJEC]` |
| **Quitar el eco rompe exactamente 1 prueba** de 478 | `[EJEC]` `test_capacidad_m1.py::test_capacidad_conversacional_completa` |
| **Excluirlo de `recall` rompe la misma y única prueba** | `[EJEC]` |

**La capacidad en juego** es «AURA recuerda lo que le dijiste, entre sesiones»: el eco es hoy la
**única** vía por la que el contenido del usuario llega al almacén persistente en el camino
conversacional general. Las señales capturadas exigen que el enunciado dispare un marcador. Cualquier
alternativa que elimine el eco sin más **destruye la capacidad 1 del MVP**.

---

## 4 · Alternativas

### Op-1 — No escribir el eco solo en la rama de ADR-0014

**Algoritmo.** Suprimir la escritura en la línea 373.

**Dónde gana.** Cambio de una línea. Riesgo nulo.

**Dónde falla.** **Incompleta.** Solo cubre 1 de las 7 rutas. Si el usuario pregunta algo que
`_es_consulta_de_memoria` no reconoce —que por D-M-7 es **el 100 % de la batería**— el turno va por la
ruta del LLM (línea 398), el eco **sí** se escribe, y repetir la pregunta lo recupera igual. Corrige el
síntoma en la ruta donde D-M-7 hace que casi nunca se entre.

**Veredicto: descartada por insuficiente.**

---

### Op-2 — Excluir `kind == "episodica"` de `recall`

**Algoritmo.** Filtrar por tipo en la recuperación.

**Dónde gana.** Elimina el auto-eco de raíz y es fácil de razonar. Reutiliza el precedente de `_TIPOS`.

**Dónde falla.** **Destruye la capacidad de memoria entre sesiones** `[EJEC]`: rompe
`test_capacidad_conversacional_completa`, y con razón — sin el episódico, lo único recuperable son las
señales clasificadas. Cambiaría un defecto por la pérdida de una capacidad cerrada del MVP.

**Veredicto: descartada.**

---

### Op-5 — No almacenar como recuperable lo que es una pregunta *(recomendada)*

**Algoritmo.** Antes de escribir el eco, decidir si la entrada es interrogativa. Si lo es, **no se
almacena como recuerdo recuperable**. Detección: signo `¿`/`?` **o** palabra interrogativa inicial
(`qué, cuál, cuándo, dónde, cómo, cuánto, quién, por qué, recuerdas, sabes, dime`).

**Fundamento.** Una pregunta **no es información sobre el usuario**: es una petición de información.
Almacenarla como recuerdo es una confusión de categorías, y el auto-eco es su consecuencia directa.

**Fiabilidad del detector `[EJEC]`** — comparado con el vigente:

| | Detector vigente | **Detector de interrogación** |
|---|---|---|
| Consultas de la batería reconocidas | **0 / 77** | **70 / 77 (90,9 %)** |
| Afirmaciones mal clasificadas | 4 / 8 | **0 / 8** |

Las 7 no reconocidas son consultas de **una sola palabra** (`Rocky`, `Adidas`, `Complutense`…), que no
son preguntas en sentido gramatical: sobre las que sí lo son, acierta en **70 de 70**.

**Verificación en los dos escenarios que deciden `[EJEC]`:**

| Escenario | Hoy | Con Op-5 |
|---|---|---|
| Misma pregunta ×3 (D-M-2) | activa · **DESACTIVADA** · **DESACTIVADA** | **activa · activa · activa** |
| Memoria entre sesiones | recupera «tenue» ✓ | **recupera «tenue» ✓** |

Resuelve el defecto **por completo** y **preserva la capacidad**: el turno «Enciende la luz de la sala
en modo tenue» no es pregunta, así que se sigue almacenando y sigue siendo recuperable.

**Criterios.** *Corrección:* resuelve los dos efectos de §1. *Rendimiento:* nulo — una comprobación
léxica por turno, sin tocar `recall`. *Determinismo:* la detección es una función pura del texto.
*Complejidad:* baja, comparable al detector que ya existe. *Impacto arquitectónico:* nulo, no cambia
contratos ni formato persistido. *ADR-0014:* lo **restaura**. *MA.2a:* intacta, no toca la
recuperación. *Riesgo de regresión:* 1 prueba a revisar `[EJEC]`, y verificado que **no** se rompe.

**Dónde falla — dicho sin adornos.** (1) Si el usuario da información **en forma de pregunta**
(«¿sabías que soy alérgico a los frutos secos?»), se perdería. `[HIPO]`: no he medido su frecuencia,
y no puedo — nadie ha usado AURA. (2) No arregla D-M-7: ADR-0014 seguirá activándose en una superficie
estrecha, solo que ya no se apagará sola dentro de ella. (3) El detector es léxico y heredará los
límites de cualquier heurística de ese tipo.

**Mitigación de (1) disponible sin coste:** en vez de no escribir, escribir con un `kind` propio
(p. ej. `"interrogativa"`) que `recall` no considere. La entrada **no se pierde** —queda en el
histórico, exportable e inspeccionable— pero deja de ser recuperable. Recomiendo esta variante:
conserva el dato y respeta el principio de no destruir información del usuario.

---

### Op-8′ — Exigir que el recuerdo aporte algo que la consulta no tenga

**Algoritmo.** Filtrar en `recall` los recuerdos que no aporten ningún término informativo ausente en
la consulta, tratando `usuario` y `dijo` como no informativos.

**Dónde gana.** Elegante y no depende de detectar preguntas: ataca la tautología directamente.
Verificado `[EJEC]` en los 4 casos de diseño, incluida una **pregunta reformulada** —que Op-5 también
resolvería, pero por otra vía—.

**Dónde falla.** **Cuesta recall**: 0,6226 frente a 0,6604 sobre la batería `[EJEC]`, es decir 2
aciertos legítimos perdidos de 53, sin mejorar los FP (0 puros y 2 críticos en ambos casos). Paga
calidad de recuperación por un problema que Op-5 resuelve **sin coste**.

**Veredicto: descartada como solución principal.** Es una **red complementaria** válida si en el futuro
se quisiera cubrir ecos que Op-5 deje pasar; hoy no compensa.

---

## 5 · Matriz comparativa

| Criterio | **Op-5** *(recomendada)* | Op-1 | Op-2 | Op-8′ |
|---|---|---|---|---|
| **Resuelve D-M-2** | **Sí, completo** (3/3 turnos) | Solo 1 de 7 rutas | Sí | Sí |
| **Preserva memoria entre sesiones** | **Sí** | Sí | **No** — rompe la capacidad | Sí |
| **Coste en recall** | **Ninguno** | Ninguno | Alto | −0,038 (2 aciertos) |
| **Rendimiento** | Nulo | Nulo | Nulo | Filtro extra por consulta |
| **Determinismo** | Función pura del texto | Sí | Sí | Sí |
| **Complejidad** | Baja | Mínima | Baja | Media |
| **Impacto arquitectónico** | Nulo | Nulo | Nulo | Toca `recall` |
| **ADR-0014** | **Lo restaura** | Lo restaura en 1 ruta | Lo restaura | Lo restaura |
| **MA.2a** | Intacta | Intacta | Intacta | Intacta |
| **Riesgo de regresión** | 1 prueba, verificada OK | Nulo | **1 prueba rota** | Recall a la baja |
| **Veredicto** | **RECOMENDADA** | Insuficiente | Descartada | Red complementaria |

---

## 6 · Qué tendría que demostrarse para cambiar esta decisión

1. **Que los usuarios dan información en forma de pregunta con frecuencia apreciable.** Haría de Op-5
   una pérdida de información. Mitigado por la variante `kind="interrogativa"`, que no destruye nada.
   Umbral sugerido: **>5 % de turnos interrogativos con contenido almacenable**. Hoy `[HIPO]`.
2. **Un contraejemplo del detector de interrogación**: una pregunta real que no detecte y cuyo eco
   vuelva a desactivar ADR-0014. Las 7 no detectadas de la batería son de una sola palabra.
3. **Que D-M-7 se resuelva ampliando `_es_consulta_de_memoria`.** Si esa ampliación incorporase
   detección de interrogación —que es lo natural—, ambos detectores deberían **unificarse** en vez de
   convivir. Esto es lo más probable, y es un argumento para decidir D-M-7 **antes** de implementar
   este DP.
4. **Que el episódico deje de ser la única vía de persistencia conversacional.** Si la captura de
   señales se ampliara para cubrir el habla general, Op-2 dejaría de destruir la capacidad y sería más
   simple.

---

## 7 · Lo que este DP NO incluye

- **No resuelve D-M-7** (ADR-0014 apenas se activa). Es un defecto distinto, registrado aparte y
  pendiente de decisión del CEO.
- **No resuelve D-M-3…D-M-6 ni D-M-1.**
- **No toca** `recall`, la cobertura, la tokenización ni el formato persistido.
- **No implementa nada.** Requiere aprobación explícita.

---

## 8 · Advertencia sobre el orden, para que la decisión sea informada

El CEO fijó `D-M-2` antes que `D-M-1`, y la evidencia lo respalda. Pero esta investigación destapó
`D-M-7`, y aparece un solapamiento real: **D-M-7 obligará a revisar la detección de intención del
usuario, que es exactamente lo que Op-5 introduce.** Implementar Op-5 primero y luego D-M-7 podría
significar escribir dos detectores para unificarlos después.

**Mi recomendación —no una decisión— es decidir D-M-7 antes de implementar este DP**, o al menos
decidir si se aborda, para poder diseñar un único detector de intención en lugar de dos.

> **Resuelto (CEO, 2026-08-03).** Esa es exactamente la decisión tomada: D-M-7 se abre como Decision
> Package independiente y debe definir el modelo general de clasificación de intención **antes** de
> que este DP se retome. Ver `DP-D-M-7-CLASIFICACION-DE-INTENCION.md`.
