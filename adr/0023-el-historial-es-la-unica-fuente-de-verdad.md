---
adr: 23
titulo: "El historial de eventos es la única fuente de verdad; todo lo demás es proyección"
estado: accepted
fecha: 2026-08-03
decide: "CEO"
propone: "CTO"
supersede: null
relacionado: "ALERTA-005, ALERTA-006, D41 (fuente única de verdad), G-1 (ruta única de mutación)"
---

# ADR-0023 — El historial es la única fuente de verdad

> Esta ADR documenta un **descubrimiento**, no solo una decisión. El principio no se diseñó por
> adelantado: cuatro implementaciones independientes convergieron hacia él, y solo después se
> reconoció el patrón. Por eso incluye un apartado de **evidencia** que las ADR anteriores no tienen.

---

## 1 · Problema observado

El principio no nació de una idea, sino de **defectos concretos ya pagados**:

- **ALERTA-006 (2026-08-03).** `PersistentMemory.olvidar` **reescribe** el fichero de memoria desde
  `self._items`. Al hacerlo destruye historia: lo que la proyección ya no contiene deja de existir, sin
  copia previa ni forma de reconstruirlo. Se detectó auditando **seguridad**.
- **La misma pieza, por otra vía.** Semanas después, analizando el **modelo de datos**, apareció el
  mismo `_persist` como la única anomalía del sistema. Dos investigaciones independientes —una de
  seguridad, otra de arquitectura de datos— señalaron el mismo punto. Esa convergencia es lo que
  convirtió una corrección puntual en un principio.
- **ALERTA-005** había enseñado antes la lección equivalente para la *ejecución*: dos implementaciones
  del mismo control acaban divergiendo. Aquí ocurre con los *datos*: **un dato almacenado dos veces
  termina divergiendo**.

El síntoma común: cuando la proyección manda sobre el historial, **la verdad del sistema se puede
perder sin que nadie lo note**.

---

## 2 · Evidencia — cuatro convergencias independientes

Ninguno de estos componentes se diseñó siguiendo esta ADR. Todos llegaron al mismo patrón por su
cuenta, resolviendo problemas distintos:

| Componente | Cuándo y por qué | Patrón al que llegó |
|---|---|---|
| **Automatizaciones** (`AlmacenReglas`) | MVP capacidad 5. Necesitaba que una regla sobreviviera al reinicio | JSONL append-only + proyección por `(user_id, rule_id)`. **Desactivar anexa una línea**, no reescribe |
| **Estado Operativo** | SO Interno. Necesitaba que el ciclo de trabajo sobreviviera a la sesión | Copió el patrón anterior con clave `(objetivo_id, tarea_id)`. La proyección vive solo en memoria |
| **Auditoría** (`observability`) | ALERTA-004. Necesitaba evidencia forense no manipulable | append + `fsync`, con sellado por segmentos |
| **IMA** | Medición de madurez | **No persiste nada**: se recalcula por introspección en cada evaluación |
| **Aprendizaje** (`intentos`, trazas) | Protocolo de Transiciones | No tiene almacén propio: vive dentro del historial de la tarea |

**Cinco componentes, cinco problemas distintos, un solo patrón.** Y una única anomalía —Memoria—, que
además resultó ser un defecto ya identificado por otra vía.

---

## 3 · Decisión

> **La única información persistente con valor semántico es el historial de eventos.**
> Todo lo demás puede existir únicamente como **proyección reconstruible**.

Corolarios vinculantes:

1. **El historial es append-only.** Retirar información se expresa **anexando** —una lápida, una línea
   `inactiva`, una transición a estado final—, nunca reescribiendo.
2. **Ninguna estructura derivada puede ser fuente de verdad.** Si se pierde, debe regenerarse desde el
   historial sin que el comportamiento del sistema cambie.
3. **La dirección del flujo es historial → proyección.** Escribir el historial *desde* la proyección
   invierte la relación y es lo que ALERTA-006 costó.

---

## 4 · No objetivos

Esta ADR **no prohíbe** —y en algunos casos recomienda— **snapshots, cachés, índices, métricas ni
proyecciones**. Son legítimos y necesarios: `_indice` y `_cache_terminos` de la memoria son ejemplos
correctos, y un snapshot será **recomendable** cuando el coste de reconstrucción deje de ser aceptable.

**El criterio único que separa una optimización de una segunda fuente de verdad:**

> *Debe poder eliminarse por completo y regenerarse desde el historial sin alterar el comportamiento
> del sistema.*

Si cumple eso, es una optimización. Si no, es una fuente de verdad encubierta.

**Esta aclaración es deliberada:** sin ella, el principio se interpretaría dentro de unos meses como
«prohibido cachear», que es más rígido de lo que pretende y llevaría a romperlo a escondidas.

---

## 5 · Garantía — cómo se verifica

Esta ADR **no termina diciendo «debe cumplirse»**. Termina diciendo **cómo se comprueba**, y esa
comprobación ya existe y corre en el Quality Gate:

`aura_skeleton/core/modelo_datos.py` · `tests/integration/test_modelo_datos.py`

Protocolo **genérico** —describe un componente con cuatro funciones y vale para cualquiera, presente o
futuro—, con cinco comprobaciones: fuente de verdad persistente · proyección eliminable · reconstruible
desde la fuente · comportamiento indistinguible · nada vive solo en la proyección. Clasifica en
**cumple / cumple con excepciones justificadas / viola**, y nombra la comprobación que falló.

**Resultado hoy, verificado:** Estado Operativo **CUMPLE** · Automatizaciones **CUMPLE** · Memoria
**VIOLA** (detectada a propósito; su corrección es trabajo aparte).

**Si mañana alguien rompe el principio, el Quality Gate falla.** Eso convierte esta ADR en una decisión
viva y no en documentación histórica.

### Límite conocido del protocolo, declarado

La comprobación de append-only observa **un solo fichero**. Dos casos legítimos quedan hoy fuera de su
alcance y **no deben leerse como incumplimientos**:

- **Rotación del audit log** (`observability.py:129`): trunca el fichero activo tras sellar un segmento.
  El contenido **sobrevive íntegro** en el segmento; el historial real es la *concatenación* de
  segmentos más el activo. El protocolo, que mira un fichero, lo vería decrecer.
- **Cursores de conectores** (`auditoria.py:41-47`): guardan una posición de lectura por reescritura.
  **No es información semántica**, es un puntero: perderlo solo provoca reprocesar eventos, y la
  idempotencia por `event_id` ya cubre esa consecuencia.

Ampliar el protocolo a historiales multi-fichero es **deuda declarada**, no un defecto de la decisión.
