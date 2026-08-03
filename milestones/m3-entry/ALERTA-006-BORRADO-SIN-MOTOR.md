# ALERTA-006 — Rutas que mutan estado del usuario fuera del Motor Único

**Detectada:** 2026-08-03. **Ampliada el mismo día** tras el barrido exhaustivo ordenado por el CEO.
**Estado:** abierta, **prioridad máxima**. No se ha modificado código.
**Viola:** ALERTA-005 (*«toda ejecución pasa por el motor único; ninguna ruta alternativa»*), ADR-0003
(lista roja ⇒ confirmación humana **siempre**), **Bible 5.3 §5 / RN-3** (kill switch) e **INV-9** (no
fingir capacidad).

> **Lo más grave, en una línea:** con la **parada de emergencia armada**, AURA sigue **destruyendo
> datos del usuario** `[EJEC]`.

---

## 1 · Las 7 ramas del turno: solo una pasa por el motor `[EJEC]`

| # | Rama | Qué muta | ¿Motor? | ¿Permisos? | ¿Kill switch? |
|---|---|---|---|---|---|
| 1 | Soberanía del modelo | **borra / refuta** el modelo persistido | **No** | **No** | **No** |
| 2 | Notificaciones | solo lee | – | – | – |
| 3 | Ver automatizaciones | solo lee | – | – | – |
| 4 | Crear automatización | escribe `reglas.jsonl` | **No** | **No** | **No** |
| 5 | Cancelar automatización | escribe `reglas.jsonl` | **No** | **No** | **No** |
| 6 | ADR-0014 | solo lee | – | – | – |
| 7 | LLM → acción | vía adaptador | **Sí** | Sí | Sí |

Además, `_finalizar_turno` muta estado persistente en **las 7 ramas** (memoria episódica, señales,
cursores, TTS).

---

## 2 · Hallazgos por gravedad

### G-1 · Irreversible, sin confirmación, sin motor

**M-01 · Borrado del modelo del usuario.** `orchestrator.py:417-422` → `modelo_usuario.borrar` →
`PersistentMemory.olvidar` → **`_persist()` reescribe el JSONL completo** (`memory.py:196, 244-251`).
**No es append-only y no hay lápida:** la línea desaparece del disco. `backup()` existe
(`memory.py:271`) pero **nadie lo llama** en producción. El registro forense que queda no incluye
`user_id` ni contenido, así que **no permite reconstruir lo borrado** `[EJEC]`.

**M-01b · Falso positivo destructivo — no hace falta ni pedir olvidar.** El disparador es la subcadena
`"olvida"` **sin guarda de dominio** (`_PAT_MODELO_OLVIDA`, `orchestrator.py:104`). Reproducido:

```
frase   : «Se me olvida siempre tomar la pastilla.»   ← no pide olvidar nada
antes   : ['tiene alergia a la penicilina', 'suele pagar las facturas por la app']
después : ['suele pagar las facturas por la app']
fichero : 0 líneas → la entrada DESAPARECIÓ del disco
```

**Una frase mundana sobre medicación destruyó un dato clínico declarado.** Asimetría reveladora:
`_es_cancelacion_de_regla` exige **dos** señales (marcador **y** dominio) precisamente para evitar esta
clase de fallo; `_PAT_MODELO_OLVIDA` no tiene esa guarda.

**M-02 · `refutar`: mismo defecto, y peor.** Responde la pregunta que quedó `[HIPO]` en la versión
anterior de este documento: **sí, usa el mismo `_foco` y falla igual** `[EJEC]`. Correcciones a lo que
yo mismo escribí antes:

- Lo clasifiqué como **«reversible (append-only)»**. **Las dos cosas son falsas:** `marcar` también
  llama a `_persist()` (reescribe el fichero), y **no existe `desrefutar`** — una entrada refutada sale
  de `vivas` y `_foco` no puede volver a seleccionarla. **Es irreversible desde la conversación.**
- **Narra éxito sin efecto** (INV-9): `orchestrator.py:427` **descarta el retorno** de `refutar`. Con
  `n=0`, AURA responde igualmente *«Entendido, lo corrijo»* `[EJEC]`. `borrar` sí comprueba `n`: la
  asimetría está en el código.
- Secuencia de vaciado silencioso verificada: el usuario intenta **corregir** el error y AURA refuta
  otra entrada, hasta *«Todavía no sé nada sobre ti»*.

**M-03 · El kill switch es inerte para estas rutas — hallazgo nuevo.** `kill_switch.py` declara *«cuando
está activado, NINGUNA acción se ejecuta»*, pero **`permissions.py:107` es el único punto que lo
comprueba**. Como las ramas 1/4/5 no llaman a `authorize`, no lo consultan. Reproducido con el switch
**armado**:

```
kill switch activo: True
«olvida…»    → borradas=1   modelo después: []      ← DESTRUYÓ el dato
crear regla  → escribe reglas.jsonl
desactivar   → escribe reglas.jsonl
acción (LLM) → detenida: «kill switch activo»       ← solo aquí funciona
```

**La parada de emergencia no para la destrucción de datos del usuario.**

### G-2 · Fuera del motor, pero reversible o append-only

`M-04` crear regla y `M-05` desactivar regla (append-only, auditable; el catálogo las respalda como
**verdes**, pero aun así no pasan por el gate y el kill switch no las frena) · `M-06` escritura
episódica en las 7 ramas · **`M-07` la captura de señales escribe en el modelo del usuario sin gate
alguno**, y el catálogo **no tiene entrada** para *crear* información sobre la persona (sí para
destruirla) · `M-08` cursores · `M-09` audit log (correcto: es el registro forense) · `M-10` TTS con
efecto audible `[INFER]` · `M-11` egress del prompt al LLM local `[INFER]`.

### G-3 · Capacidad construida y no cableada (patrón ALERTA-004/005)

**M-15 · `ModeloUsuario.corregir` no lo llama nadie** en producción `[EJEC]`: solo un test. Los
docstrings anuncian «corregir» como capacidad viva; lo que la rama hace es **refutar**, que es otra
cosa. `M-13` `cerrar_sesion` (de la que depende ALERTA-002) tampoco tiene llamador.

---

## 3 · Por qué la suite en verde no lo detectó

- **No existe ninguna prueba de «toda mutación pasa por el motor».** La prueba de ALERTA-005
  (`test_alcanzabilidad_capacidades.py`) cubre la dirección **contraria** —que toda capacidad declarada
  sea alcanzable— y ni siquiera inyecta `modelo_usuario`, así que las ramas 1/4/5 no se ejercitan.
- **La prueba e2e oficial de soberanía fija el bypass como comportamiento esperado:**
  `test_modelo_usuario_flujo.py` monta el sistema con `PermissionManager(_deny)` —el humano deniega
  todo— y **afirma que el olvido persiste tras el reinicio**. Es decir: el salto del gate está
  **codificado como criterio de aceptación**.

Esta es la novena repetición del patrón «declarado ≠ real», y la primera en que **una prueba consagra
la violación**.

---

## 4 · Propuesta de corrección (para decisión del CEO; nada implementado)

### Contención inmediata — coste bajo, sin rediseño

1. **Guarda de dominio en `_PAT_MODELO_OLVIDA`**: exigir dos señales, como ya hace
   `_es_cancelacion_de_regla`. Elimina M-01b.
2. **`_foco` ante duda NO actúa**: si no hay coincidencia, pedir desambiguación en vez de devolver
   `vivas[0]`. Convierte una destrucción silenciosa en una pregunta. Aplica a `borrar` **y** a
   `refutar`.
3. **`refutar` comprueba `n`** antes de narrar éxito. Cierra la violación de INV-9.

### Corrección estructural — requiere decisión

4. **El kill switch se comprueba en toda mutación persistente**, no solo en `authorize`. Es la
   violación más clara de una garantía declarada.
5. **Borrado reversible**: marca de baja en vez de reescritura, preservando append-only. Hoy `olvidar`
   destruye historia sin backup.
6. **Enrutar las mutaciones sobre datos del usuario por el motor único**, o **declarar explícitamente
   una lista blanca de exenciones** revisada por el CEO. Hoy la exención es implícita y accidental.
7. **Prueba de ruta única** en el Quality Gate: toda mutación persistente pasa por el gate o figura en
   esa lista blanca. Sin ella, esto vuelve a ocurrir.
8. **Revisar `test_modelo_usuario_flujo.py`**, que hoy consagra el bypass.

**Recomiendo 1-3 como contención inmediata** (baratas, sin rediseño, eliminan la destrucción
silenciosa) y **4 y 7 como las estructurales prioritarias**: sin 7, la clase entera de fallo puede
reaparecer.

### Tensión de producto que el CEO debe resolver

¿Debe la **soberanía del usuario** estar exenta del gate? Un «olvida esto» que pidiera confirmación
puede resultar hostil, y ADR-0017 defiende que el usuario mande sobre sus datos. **Pero hoy la exención
no es una decisión: es un accidente del orden de evaluación**, y arrastra consigo el kill switch y la
resolución errónea del referente. La pregunta legítima es *«¿qué controles se relajan para la
soberanía?»*, no *«se relajan todos sin querer?»*.

---

## 5 · No determinado

- `M-10` (TTS) y `M-11` (egress a Ollama) leídos en código, **no ejecutados** — requieren el stack real.
- **Concurrencia**: `olvidar` reescribe desde `self._items` sin locks. Con `asyncio` monohilo el riesgo
  es bajo, pero una escritura concurrente no reflejada en RAM se perdería. `[HIPO]`
- Si la exención de la soberanía **debe** existir: decisión de producto, no técnica.
- El barrido reportó dos fallos intermitentes en `tests/unit/test_arnes_mutacion.py`. **No los
  reproduzco** `[EJEC]`: 3 corridas aisladas en verde y **Quality Gate completo PASS**. Lo más probable
  es que el arnés dejara un fichero mutado residual en el entorno del barrido (documentado en
  `CLAUDE.md`: si el proceso muere por SIGKILL con un fichero mutado, queda mutado). **No se propaga
  como hecho**; queda anotado por si reaparece.
