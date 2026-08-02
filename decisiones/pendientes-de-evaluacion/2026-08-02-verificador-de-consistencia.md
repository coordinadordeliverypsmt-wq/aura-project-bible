---
documento: "Verificador de consistencia del proyecto"
tipo: "Oportunidad de mejora — PENDIENTE DE EVALUACIÓN"
fecha: 2026-08-02
autor: "CTO"
estado: "NO AUTORIZADO como incremento. Propuesta registrada; se reevaluará después de la revisión estratégica."
base: "main @ e6490f1"
---

# Oportunidad de mejora — Verificador de consistencia

> **Estado: NO es un incremento autorizado.** El CEO decidió el 2026-08-02 no invertir en herramientas de
> desarrollo antes de cerrar la revisión estratégica del roadmap, y exigió comprobar primero que existe un
> vacío que el Checklist de Continuidad, el preflight y el Quality Gate no cubran ya.
>
> Este documento existe **para no perder el análisis**, no para justificar su construcción.

## Problema que pretendía resolver

`[EJEC 2026-08-02]` La revisión estratégica necesitó **~25 comandos de investigación** para establecer qué
existe y qué no, y **tres de sus conclusiones fueron erróneas** —`detectores.py` contado como código
muerto, la captura de señales dada por rota, y Ollama declarado sin modelos—. Reconstruir el estado a mano
es caro **y falible**.

El proyecto tiene dos verificadores y carece del tercero:

| Pregunta | Herramienta | Estado |
|---|---|---|
| ¿El entorno es apto? | `entorno/scripts/preflight-check.sh` | ✅ existe |
| ¿El código está sano? | `walking-skeleton/quality-gate.sh` | ✅ existe |
| ¿Lo que el proyecto **declara** es cierto? | — | ❌ no existe |

## Evidencia de que el vacío es real

`[EJEC 2026-08-02]` `ROADMAP-CAPACIDADES-FUNCIONALES.md` **se contradice consigo mismo**, y está publicado
en `main`:

| Fuente | Centro de Notificaciones | Modelo de Usuario |
|---|---|---|
| Tabla «Estado del MVP» | ✅ | ✅ |
| Tabla «incrementos», mismo documento | ⏭ «Siguiente (pendiente de Decision Package)» | «Construido y probado; **no cableado**» |
| **Realidad medida** | cableado: `True` | cableado: `True` |

Ninguna de las dos tablas coincide con el sistema. **Ni el checklist, ni el preflight, ni el Quality Gate
detectan esto**: el primero no verifica el roadmap, y los otros dos miran entorno y código, no artefactos.

**Nota:** esta contradicción concreta es corregible a mano en minutos. Lo que el verificador aportaría no
es corregirla, sino **impedir que se repita sin que nadie lo note**.

## Diseño propuesto (para no rehacerlo si se reevalúa)

**Naturaleza:** infraestructura de ingeniería; no capacidad del MVP; no toca la D2.
**Ubicación:** `herramientas/verificar-consistencia.py`. **Tamaño estimado:** ~180 LOC + pruebas.

### Fuente única por dato — la herramienta no posee ninguno

| Dato | Fuente única |
|---|---|
| Acciones declaradas | `core/permissions.CATALOGO` |
| Capacidades con adaptador | `RegistroAdaptadores.capacidades()` |
| Capacidades materializadas | `Sistema.capacidades_activas_efectivas` |
| Estado declarado del MVP | tabla «Estado del MVP» del roadmap |
| Deudas registradas | ficheros `milestones/*/DEUDA-*.md` |
| Deudas citadas | tabla de deuda del checklist |
| Sincronía y limpieza | `git` |
| Salud del código / entorno | invoca `quality-gate.sh` y `preflight-check.sh` — no los reimplementa |

### Siete contrastes

| | Verificación | Detecta |
|---|---|---|
| V1 | Capacidad con adaptador ⊆ catálogo de permisos | Operación ejecutable sin clasificar |
| V2 | Lo declarado activo = lo materializado | Regresión de la corrección D |
| V3 | Todo `DEUDA-*.md` está citado en el checklist | Deuda huérfana |
| V4 | Toda deuda citada existe | Referencia rota |
| V5 | El roadmap no se contradice ni consigo ni con la realidad | El caso de arriba |
| V6 | Los comandos del §1 del checklist existen | Checklist que manda ejecutar lo inexistente |
| V7 | `main` vs `origin/main`, árbol limpio | Trabajo sin publicar |

Código de salida ≠ 0 si algún contraste falla: verificador, no informe.

### Tres reglas anti-duplicación

1. **No persiste nada** — sin fichero de datos, sin caché, sin documento generado; salida a `stdout`. No
   puede convertirse en fuente de verdad porque no guarda nada. Con prueba que falla si escribe en disco.
2. **Un dato, una fuente** — si falta, responde `NO VERIFICABLE`; nunca lo deduce.
3. **No reimplementa lo existente** — invoca las dos herramientas ya construidas.

### Qué NO haría

Nada que requiera juicio (Product Readiness, valor, prioridades) · no sugiere qué hacer · no evalúa prosa ·
no modifica ningún artefacto.

## Criterio de reevaluación (condición del CEO)

Reevaluar **solo si** se demuestra que el vacío no lo cubren los artefactos existentes. Señales que lo
demostrarían:

- Vuelve a aparecer una contradicción entre artefactos que nadie detecta hasta que causa una decisión mala.
- El coste de reconstruir el estado sigue siendo alto **después** de que el Checklist de Continuidad lleve
  varios incrementos en uso — hoy solo lleva uno, así que **aún no hay evidencia suficiente para juzgarlo**.

Esa última es la razón honesta por la que la decisión del CEO de esperar es correcta: el checklist es
demasiado reciente para saber cuánto cubre.
