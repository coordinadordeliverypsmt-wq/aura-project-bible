---
documento: "Acta — cuatro decisiones del CEO: cierre de ALERTA-006, alcance de PARADA, siguiente inversión y escenario de despliegue"
tipo: "Acta de decisiones del CEO (1.1 §3.2.3)"
fecha: 2026-09-09
mantenido-por: "APUS-5 (CTO)"
decide: "CEO (Mauricio)"
checkpoint: "3708e11d38ab9a4bbcbfb814fbc1c1ccbb293b8b"
---

# Acta — cuatro decisiones del CEO (2026-09-09)

**Fuente:** decisión explícita del CEO en la sesión del 2026-09-09. **No existe acta anterior**: este
documento registra lo que se acaba de decidir, y esa es toda su autoridad. Ninguna de las cuatro se
infiere de una decisión previa.

**Un solo acta y no cuatro ficheros**, por lo que el propio CEO pidió: no crear documentación paralela.

---

## D-1 · `ALERTA-006` original — **RESUELTA TÉCNICAMENTE**

**Decidido.** El defecto tal como fue descrito el 2026-08-03 —cuatro rutas que mutaban estado del
usuario fuera del Motor Único— queda formalmente **resuelto técnicamente**.

**Evidencia obligatoria, verificada** `[EJEC]`/`[LECT]`:

| Ruta | Símbolo | Evidencia |
|---|---|---|
| M-01 borrado del modelo | `modelo_usuario.borrar` | `modelo_usuario.py:112` → `_por_el_motor` |
| M-02 refutación | `modelo_usuario.refutar` | `modelo_usuario.py:128` → `_por_el_motor` |
| Rama 4 crear automatización | `AlmacenReglas.crear` | `reglas.py:126-135` → `self._motor.ejecutar` |
| Rama 5 cancelar automatización | `AlmacenReglas.desactivar` | `reglas.py:154-162` → `self._motor.ejecutar` |

- **fail-closed** en las cuatro: sin motor inyectado no hay mutación (`return 0` / `return` / `return False`);
- **permisos** y **kill switch** actúan dentro de `motor.ejecutar`, por el que las cuatro pasan;
- **G-1 · R-A = 0** · **G-1 · R-B = 0**.

**Fijado por prueba:** `test_g1_ruta_unica.py::test_las_cuatro_rutas_de_alerta_006_ALCANZAN_el_motor`.

> **Lo que esta decisión NO declara.** No declara que «toda mutación de estado del usuario está
> gobernada». Es falso: `memory.write` sigue fuera del motor. Esa exposición residual se trata en `D-2`
> y **no se cierra con esta acta**.

**Trazabilidad documental.** `milestones/m3-entry/ALERTA-006-BORRADO-SIN-MOTOR.md` lleva un bloque de
cierre fechado con la evidencia, y un aviso al inicio de su §1 que advierte de que la tabla de rutas es
el diagnóstico del 2026-08-03. **Su contenido histórico no se ha borrado ni reescrito**: el fichero está
versionado en git desde `58ba28f`, de modo que cualquier redacción anterior es recuperable.

---

## D-2 · Alcance de `PARADA` — **OPCIÓN B ADOPTADA**

**Decidido.** `PARADA` bloquea las acciones ejecutables y destructivas gobernadas por el Motor Único, y
**no** convierte en acción ejecutable todo procesamiento conversacional.

```
PARADA  ≠  apagado completo de la conversación
```

**Registrado en `ADR-0024`**, que publica la definición mecánica de «escritura pasiva»: whitelist cerrada
y fail-closed en `contracts.KINDS_PASIVOS` = `{episodica, historico}`.

**Lo que esta decisión deja expresamente escrito, y no autoriza:**

- `memory.write` es una **mutación persistente**;
- hoy está **fuera del motor**, de los permisos y del kill switch;
- la Opción B **NO significa** «toda escritura conversacional está permitida»;
- su tratamiento queda **delimitado, no resuelto**;
- **no se crea autoridad nueva** para ella, **no se amplía `persistencia_autorizada`**, **no pasa a ser
  acción del motor** y **no se modifica ningún contrato**.

**Estado de implementación: ya ejecutada en la misión anterior. Aquí solo se verifica y se documenta.**
Verificación `[EJEC]`: `tests/unit/test_parada_escritura_pasiva.py` en verde por los dos lados —lo pasivo
sigue funcionando con la parada armada; lo no pasivo no ocurre— y
`mutaciones/parada-escritura-pasiva.toml` con **5 detectados · 0 supervivientes**. No se reimplementó ni
se duplicó nada.

---

## D-3 · Siguiente inversión del proyecto — **COGNICIÓN LOCAL + RENDIMIENTO DEL RAZONADOR**

**Decidido.** Queda desbloqueado el pendiente *«siguiente inversión del proyecto»* (`CHECKLIST` §3, desde
2026-08-02), que bloqueaba **todo trabajo de construcción nuevo**.

**Objetivo:** que AURA pueda sostener conversación, razonamiento general, conocimiento e hipótesis con el
razonador **local**, sin convertir al LLM en autoridad sobre memoria personal, permisos, acciones, reglas,
señales, hechos del usuario ni gobernanza.

**La separación no cambia:**

```
CORE   = autoridad sobre hechos y memoria personal   (ADR-0014)
LLM    = razonador y conversador, sin autoridad
MOTOR  = único ejecutor autorizado                    (ALERTA-005)
PARADA = mecanismo de seguridad                       (ADR-0024)
```

**Ataca primero el cuello de botella ya medido**, no uno supuesto: `qwen2.5:0.5b` local, hardware actual,
latencias del orden de cientos de segundos, y la **ingestión de prompt** como componente significativo
del tiempo.

**Límites de la inversión:** no cambiar de modelo sin decisión posterior específica · no aumentar su
tamaño por iniciativa propia · no introducir APIs externas ni credenciales · no abandonar local-first.

**Perímetro preparado en:** `milestones/m3-entry/DP-COGNICION-LOCAL-Y-RENDIMIENTO.md`.

---

## D-4 · `P1` · Escenario de despliegue — **LOCAL EN LA MÁQUINA PRINCIPAL DEL USUARIO**

**Decidido.** Queda desbloqueado `P1` (`CHECKLIST` §3, desde 2026-07-21), que bloqueaba **3 de las 5
fases de M3**.

La arquitectura continúa siendo **local-first, open source y sin dependencia de servicios externos**
(`D24` / `ADR-0001`).

**`HC-1` — hardware de referencia para optimización y medición:**

```
Lenovo 100e 2nd Gen · Celeron N4020 · ~3,6 GiB RAM
swapfile ~4 GB · zRAM · Ollama local · qwen2.5:0.5b
```

> **`HC-1` NO fija las especificaciones definitivas de AURA.** Significa una cosa concreta: **no se
> optimiza contra hardware imaginario**. Toda medición de la inversión `D-3` se hace aquí, y cualquier
> cifra que no se haya medido en `HC-1` no cuenta como evidencia de rendimiento.

**Límites:** no comprar ni introducir hardware · no asumir hardware futuro · no cambiar el modelo por
iniciativa propia.

---

## Trazabilidad

| Decisión | Documento | Implementación |
|---|---|---|
| D-1 | esta acta · `ALERTA-006-BORRADO-SIN-MOTOR.md` (cierre) · `D-A006-decision-package.md` | ya ejecutada (F4 + reconciliación de G-1) |
| D-2 | esta acta · **`ADR-0024`** · `D-A006-decision-package.md` §D-A006-2 | ya ejecutada; aquí verificada |
| D-3 | esta acta · `DP-COGNICION-LOCAL-Y-RENDIMIENTO.md` | **futura**, no iniciada en esta misión |
| D-4 | esta acta · `DP-COGNICION-LOCAL-Y-RENDIMIENTO.md` §HC-1 | referencia de medición, vigente |

## Lo que estas cuatro decisiones NO conceden

Ninguna amplía autoridad. `_INTOCABLES`, `_MATERIA_RESERVADA`, `TODO_LO_DELEGABLE`,
`REVIEW_HABILITADO = False`, los permisos, el motor y el kill switch quedan **sin cambios**. No se crea
ninguna capacidad nueva, no se cablea NATS, no entra ningún servicio externo y `PARADA` sigue **ARMADA**.
