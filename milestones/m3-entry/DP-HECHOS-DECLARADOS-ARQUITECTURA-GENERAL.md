---
documento: "Decision Package — arquitectura general de hechos declarados"
tipo: "Decision Package (NADA implementado)"
fecha: 2026-09-10
estado: "PENDIENTE DE DECISIÓN DEL CEO"
decide: "CEO (Mauricio) — elección de arquitectura"
mantenido-por: "APUS-5 (CTO)"
---

# Responder hechos declarados sin una tabla cerrada de preguntas

**Evidencia** (D47): `[EJEC]` medido · `[LECT]` leído en el código · `[INFER]` deducido · `[HIPO]` no verificado.

## 1 · Problema demostrado `[EJEC]`

Con la tabla actual, **cada atributo nuevo cuesta dos ediciones de producto y su batería de pruebas**.
Antes de la última: «Mi color favorito es el azul» + «¿Cuál es mi color favorito?» → **129,02 s, 1 llamada
al LLM y la respuesta «amarillo»**. El Core tenía el dato correcto; el modelo lo deformó al redactarlo.
Se corrigió añadiendo una fila, y el siguiente atributo costará exactamente lo mismo.

## 2 · Estado actual `[LECT]`

| Pieza | Dónde | Qué hace |
|---|---|---|
| Detección de declaración | `conectores/conversacion.py` · `_HECHO` (**7 patrones cerrados**) + `_clasificar` | «me llamo», «mi nombre es», «trabajo en/de», «proyecto llamado», «mi proyecto se llama», «mi color favorito/preferido es». La **preferencia gana** si hay marcador de gusto |
| Filtro de terceros | `_TERCERO` + `_habla_de_tercero` → `SenalDeTercero` | descarta «mi hermana/jefe/vecino/madre/padre/hijo/esposo/pareja/amigo…» |
| Clases | `core/senales.py` · `ClaseSenal` | 7: `PREFERENCIA_DECLARADA`, `CORRECCION`, `FEEDBACK_DIRECTO`, **`HECHO_DECLARADO`**, `PATRON_DE_USO`, `TEMA_RECURRENTE`, `RESPUESTA_A_SUGERENCIA` |
| Almacenamiento | `core/almacen_senales.py` → motor → `ejecutor_modelo_usuario` → `MemoryStore.write` | `kind` ∈ {`semantica`,`procedimental`}; **el contenido es la frase literal** |
| Metadata | `provenance` = `{trace_id, fuente, clase, origen, ts}` | **no existe par (atributo, valor)** |
| Recuperación | `ModeloUsuario.ver()` → `_entradas()` | filtra `kind in _TIPOS`; expone `contenido, tipo, origen, fuente, clase, refutada, ts` |
| Correspondencia pregunta↔hecho | `orchestrator.py` · `_CONSULTAS_DE_HECHO` (**4 filas**: nombre, trabajo, proyecto, color favorito) + `_responder_hecho` + `_valor_declarado` | tabla cerrada `(preguntas, regex, plantilla, ausencia)`; solo entradas **vivas** de clase `HECHO_DECLARADO`; gana la **última** declaración |
| Autoridad del Core | `orchestrator.on_turn` paso 1, **antes del recall** | si responde, `provider=core` y **0 llamadas al LLM** |
| Recall | `SimpleMemory`/`PersistentMemory.recall` | **solapamiento de palabras**; `SemanticMemory` (N2, coseno de embeddings ONNX) existe y se cablea si el plan promueve memoria y hay modelo |

**Quién depende de la tabla:** solo `orchestrator.py` (la constante, `_responder_hecho`, `_valor_declarado`).
Ningún otro módulo la importa `[EJEC]`.

**La barrera real no es la tabla de preguntas, es `_HECHO`.** Medido: «mi abuela es enfermera», «mi primo
es piloto», «mi coche es rojo» → `clase=None`: **no se guardan**, porque no están entre los 7 patrones.
Y «mi hermana es médico» → `tercero=True`, descartada. Cualquier arquitectura general **abre esa puerta**,
y ahí está el riesgo principal: `_TERCERO` **no** cubre abuela, primo ni tío `[EJEC]`.

## 3 · Requisito arquitectónico

> Si el Core posee un hecho personal declarado y la pregunta se refiere a ese hecho, **el Core es la
> autoridad del valor**; el LLM no puede modificarlo; la redacción es determinista; la inferencia no
> está permitida; y si la correspondencia no se establece con seguridad, **no se inventa ni se llama al
> LLM para fabricar el hecho**: se responde ausencia o se sigue la ruta segura actual.

## 4 · Alternativas reales

Todas derivadas del código existente. **E se lista solo para descartarla con evidencia.**

### A · Seguir ampliando la tabla (statu quo)
**Mecanismo:** una fila por atributo en `_CONSULTAS_DE_HECHO` + un patrón en `_HECHO`.
**Ficheros:** `orchestrator.py`, `conversacion.py`. **Contratos:** ninguno.
**Ventaja:** máxima seguridad; cada atributo se piensa uno a uno. **Riesgo:** no escala.
**Ausencia/múltiples/contradicción/preferencias:** ya resueltos y probados.
**Falsos positivos:** mínimos (tabla cerrada). **LLM:** nunca. **Latencia:** 0,00 s `[EJEC]`.
**24/24:** intacto `[EJEC]`. **Pruebas/mutación:** el patrón ya existe (7 mutantes). **Migración:** n/a.

### B · Par (atributo, valor) en `provenance` al declarar
**Mecanismo:** extraer determinísticamente el par al capturar la señal y guardarlo en `provenance`; la
consulta deriva el atributo y resuelve por **igualdad**.
**Ficheros:** `conversacion.py` (extracción), `almacen_senales.py` (propagar), `modelo_usuario.py`
(exponer las claves nuevas en `ver()`), `orchestrator.py` (resolver).
**Contratos:** **ninguno** — `MemoryStore.write(provenance: dict)` es libre y el ejecutor pasa
`args.get("procedencia", {})` **sin filtrar claves** `[EJEC]`.
**Ventaja:** el dato queda estructurado en origen; la correspondencia es igualdad exacta, no parecido.
**Riesgo:** **requiere migración** —lo ya almacenado no tiene el par— y toca 4 ficheros, uno de ellos la
puerta de entrada de señales. **Ausencia:** igual que hoy. **Múltiples:** gana la última (ya existe).
**Contradicción:** la refutación ya marca `refutada`. **Preferencias:** intactas si se conserva la
precedencia de `_clasificar`. **Falsos positivos:** los de la extracción, no los de la consulta.
**LLM:** nunca. **Latencia:** 0,00 s `[INFER]`. **24/24:** intacto si la resolución sigue **antes** del
recall y exige declaración `[INFER]`. **Mutación:** sí (extracción, propagación, igualdad, ausencia).
**Migración incremental:** sí, con respaldo en C para lo antiguo.

### C · Emparejamiento gramatical simétrico en la consulta
**Mecanismo:** la declaración «mi X es V» y la pregunta «¿cuál es mi X?» comparten el sujeto posesivo.
Se deriva X de ambas, **en el momento de responder**, sobre las entradas ya almacenadas.
**Ficheros:** **solo `orchestrator.py`**. **Contratos:** ninguno. **Migración: ninguna** — funciona con
lo ya guardado, porque el contenido es la frase literal.
**Medido en prototipo desechable** `[EJEC]`: extrae el par en **6/6** declaraciones (incluidos cumpleaños
y teléfono, que la tabla no cubre), deriva el atributo en 4/5 preguntas, y **0 de las 24 protegidas**
generan atributo → no entran por esta ruta.
**Riesgo:** cubre la **familia posesiva**; «¿Cómo me llamo?» o «¿A qué hora ceno?» **no** casan y
seguirían necesitando tabla. Y si se abre `_HECHO` para alimentarla, hereda el riesgo de terceros de §2.
**Ausencia/múltiples/contradicción/preferencias:** reutiliza la mecánica actual.
**LLM:** nunca. **Latencia:** 0,00 s `[INFER]`. **24/24:** intacto `[EJEC]` (0/24 casan).
**Mutación:** sí. **Complejidad:** la menor de las tres.

### D · Recall semántico N2 para emparejar
**Mecanismo:** `SemanticMemory` (ya cableada) empareja pregunta↔hecho por **coseno de embeddings**.
**Ficheros:** `orchestrator.py` + activación de N2. **Contratos:** `MemoryStore` ya lo admite.
**Ventaja:** cubre paráfrasis sin términos comunes. **Riesgos:** exige **umbral** —un número que
gobierna si un hecho personal se da por correspondido—; el propio módulo declara que **el embedder tiene
calidad limitada en español** `[LECT]`; un falso positivo devuelve **el hecho equivocado** con autoridad
de Core; y la latencia del embedding **no está medida en HC-1** `[HIPO]`.
**24/24:** en riesgo si el umbral empareja una de las 24 con cualquier entrada `[HIPO]`.
**Mutación:** posible, pero un umbral no se mata con un mutante: se mide con un corpus.

### E · Delegar la correspondencia o la redacción al LLM — **DESCARTADA**
Prohibida por `ADR-0014` §2, y ya **medida**: con el hecho correcto en el prompt, el modelo respondió
«amarillo» donde el usuario dijo «azul» `[EJEC]`.

## 5 · Comparación

| | A tabla | B metadata | C simetría | D semántico |
|---|---|---|---|---|
| Escala a atributos nuevos | **no** | sí | parcial (posesivos) | sí |
| Ficheros a tocar | 2 | 4 | **1** | 2 + N2 |
| Contratos | ninguno | ninguno | **ninguno** | ninguno |
| Migración | n/a | **sí** | **no** | no |
| Determinista | sí | sí | sí | **no (umbral)** |
| Riesgo de devolver un hecho ajeno | bajo | medio | medio | **alto** |
| 24/24 | intacto `[EJEC]` | intacto `[INFER]` | intacto `[EJEC]` | **en riesgo** `[HIPO]` |
| Latencia | 0,00 s | 0,00 s | 0,00 s | embedding, sin medir |
| Reversible | sí | sí | **sí** | sí |

## 6 · Recomendación técnica

**C como base, con A para lo que C no cubre, y B solo si el uso lo exige.** Razones, en orden:

1. **C es la única que no exige migración ni cambia la puerta de entrada**: un fichero, ningún contrato,
   y funciona con los hechos ya almacenados.
2. **C ya está medida** en prototipo: 6/6 declaraciones, 0/24 protegidas afectadas.
3. **B resuelve lo mismo pero más tarde y más caro**: el par estructurado es mejor ingeniería a largo
   plazo, pero hoy exigiría migrar y tocar la captura de señales, y el beneficio sobre C es invisible
   para el usuario.
4. **D no cumple el requisito de §3**: un umbral no es «correspondencia establecida con seguridad», y el
   embedder disponible es de calidad limitada en español por declaración propia.

**Y una advertencia que condiciona cualquier opción:** el cuello no es la tabla de preguntas sino
`_HECHO`. Abrirla a «mi X es V» genérico haría que «mi abuela es enfermera» se guardara como hecho del
usuario. Si se amplía, **hay que ampliar `_TERCERO` en el mismo incremento** (no cubre abuela, primo ni
tío) `[EJEC]`.

## 7 · Impacto

- **Usuario:** los hechos que hoy se deforman o caen al modelo se responderían al instante y exactos.
- **Latencia:** de ~130 s a **0,00 s** por consulta cubierta `[EJEC]`.
- **Autoridad:** sin cambios — el Core sigue siendo la única fuente; el LLM no interviene.
- **`ADR-0014`:** se refuerza (menos ocasiones de que el modelo toque un hecho personal).
- **Riesgo nuevo:** responder con autoridad de Core un hecho mal emparejado. Es el riesgo a acotar.

## 8 · Plan de implementación posterior (si se aprueba)

1. **RED** con el corpus de la decisión: declaraciones cubiertas, preguntas cubiertas, las 24 protegidas,
   terceros y preferencias.
2. **Ampliar `_TERCERO`** antes de abrir `_HECHO` — en el mismo incremento, nunca después.
3. **GREEN** mínimo en la alternativa elegida.
4. **Mutación** sobre: derivación del atributo, igualdad, filtro de clase, ausencia, última declaración,
   terceros.
5. **Verificación**: 24/24, frontera, memoria, modelo de usuario, integración, control-plane, ruff,
   Quality Gate, y **E2E con 0 llamadas al LLM**.
6. **Sin commit** hasta nueva autorización.

## 9 · Pruebas y garantías que deben quedar fijadas

- El valor devuelto **coincide exactamente** con el declarado.
- **0 llamadas al LLM**, verificado con un proveedor que falle si se le invoca (patrón ya usado).
- **Ausencia** → texto de ausencia, nunca invención.
- **Última declaración gana**; una **refutada** no alimenta la ruta.
- Solo **`HECHO_DECLARADO` vivo** (el mutante `HD-M6` demostró que esta regla necesita prueba propia).
- **Preferencias** siguen siendo preferencias.
- **Terceros** no se responden como hechos del usuario.
- **24/24 intacto**, re-medido antes y después.

## 10 · Decisión exacta que debe tomar el CEO

**¿Qué arquitectura se implementa para responder hechos declarados de forma general?**

- **(A)** seguir ampliando la tabla atributo por atributo;
- **(B)** par (atributo, valor) en `provenance`, con migración;
- **(C)** emparejamiento gramatical simétrico — **recomendada**, un fichero, sin migración;
- **(D)** recall semántico N2 con umbral.

**Y, unida a ella:** ¿se autoriza **abrir `_HECHO`** a la construcción posesiva genérica —con la
ampliación obligatoria de `_TERCERO` en el mismo incremento— o la entrada sigue siendo una lista cerrada
de construcciones aprobadas una a una?
