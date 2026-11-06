---
documento: "Decision Package — Integridad, recuperación y consistencia del estado autónomo"
fecha: 2026-11-06
estado: "F1 APROBADA por el CEO (2026-11-06) e IMPLEMENTADA (ver §10). F2, F3, F4, F5 siguen PROPUESTAS, pendientes de aprobación. El Director no se aprueba a sí mismo las pendientes."
tipo: "DP técnico de integridad/recuperación. Diagnóstico de solo lectura; ninguna corrección implementada."
rama: "integracion/m3-entry · HEAD 2956c402bc347d2363e519ac9cd267e7e7750481"
evidencia: "Análisis del CÓDIGO y los documentos del repo (sin leer ~/.aura, §7.3). Clasificación D47."
alcance: "Control-plane: historial eventos.jsonl, proyección estado.json, recuperación tras caídas, observabilidad de estados."
no-cubre: "Leer ~/.aura · ejecutar recuperación real · reactivar autonomía · modificar runtime/estado.json/eventos.jsonl/cron/PARADA · merge a main · implementar correcciones"
---

# DP — Integridad, recuperación y consistencia del estado autónomo

> Herramientas: Graphify orientó los ficheros. ECC: agentes de proyecto disponibles; este análisis se hizo en
> solitario y de solo lectura tras la caída por límite de sesión de dos exploradores previos (documentado, no simulado).
> AgentShield, Codex y OpenCode: **NO DISPONIBLES** (no instalados). Sin fallback necesario.

## Entregable A · Contrato de integridad

**Fuente de verdad: `eventos.jsonl`, log encadenado por hash y append-only** (ADR-0023; `control_plane.py:1164-1165`).
No es solo «append-only»: cada evento lleva `seq` contiguo, `hash_anterior` y `hash = _hash_de(evento)`. El
verificador `_defecto_de_cadena` (`control_plane.py:2046-2058`) recorre la cadena y detecta tres roturas: salto de
`seq` (`seq != i+1`), enlace roto (`hash_anterior` ≠ hash del previo) y contenido alterado (`hash` ≠ recalculado). `[LECT]`

**Proyección: `estado.json`.** `proyectar(directorio)` (`control_plane.py:2356`) reconstruye el estado desde el log.
`estado.json` «pasa a ser proyección» (`control_plane.py:1164-1165`): reconstruible, no autoritativa. `[LECT]`

**Ancla de integridad fuera del directorio del log** (`control_plane.py:1873-1917`): guarda el último `seq` confirmado y
su `hash`, con protocolo atómico — `append + fsync` del evento → `tmp + fsync + rename + fsync del directorio` del
ancla. Ancla **génesis** (`seq` 0, hash nulo) escrita antes del primer evento. La verificación exige que el evento en el
`seq` del ancla tenga ese hash y que la cola sea una **extensión** de la cadena. `[LECT]`

**Semántica de secuencias:** `seq` estrictamente contiguo desde 1 (`eventos[i].seq == i+1`); el ancla fija el último
confirmado. Reescribir encima reutilizaría `seq` ya anclados y perdería evidencia: **no se escribe** (`:1917`). `[LECT]`

**Eventos incompletos:** una cola sin anclar tras una caída se tolera como extensión pendiente de confirmar, nunca como
cadena rota; `completitud ∈ {demostrada, no_demostrable, truncada_o_alterada}` (`control_plane.py:2062-2065`). `[LECT]`

**Invariantes que deben permanecer verdaderas:**
1. El historial es inmutable: no se reescribe ni se reutiliza un `seq` anclado.
2. `seq` único, contiguo y monótono; la cadena de hash enlaza cada evento con el anterior.
3. El estado es **siempre** reconstruible desde el historial sin modificarlo (`proyectar`).
4. Ningún evento se fabrica ni se duplica durante la recuperación.
5. Toda proyección obsoleta o corrupta es **detectable** (verificador de cadena + ancla).

**¿El diseño permite reconstruir el estado sin tocar el historial?** **Sí** `[LECT]`: `proyectar` lee el log y produce
el estado; la integridad se verifica contra el ancla sin escribir. Es exactamente el modelo ADR-0023.

## Entregable B · Recuperación tras caídas (ciclos 196 y 217)

**Qué es un ciclo abierto:** abrió con `motor_iniciado`/`ciclo_autonomo_iniciado` y no consta su cierre
(`ciclo_detenido`/`ciclo_autonomo_terminado`) — `observatorio.py:80-81,199-200`. Un ciclo abierto está corriendo o
murió; **no puede aparecer como ciclo limpio**. `[LECT]`

**Mecanismo de recuperación:** existe y está implementado — `DP-RECUPERACION-TRAS-CAIDAS` (commit `9f238d6`). Contrato
de estados de tarea (§2, §10.1), `recuperar()` **antes de planificar**, idempotente: confirma, restaura o bloquea, y
`constaba` evita duplicar `cambio_aplicado` (§10.2, tabla de órdenes). La comprobación-y-adición va bajo el cerrojo del
log (`registrar_evento_si`), así que el mismo `id` no se replanifica si sigue vivo. `[LECT]`

- **Idempotente:** sí (§10.2 punto 1: «la siguiente vuelta lo repite sin efecto doble»). `[LECT]`
- **Segunda caída durante la recuperación:** cubierta por el orden de operaciones y el ancla atómica (§10.2; bordes en §6). `[LECT]`
- **Cómo se evita duplicar eventos:** `registrar_evento_si` bajo cerrojo + `constaba`; `seq` contiguo impide reinsertar. `[LECT]`
- **Evidencia de diseño:** 21 pruebas en `test_red_reanudacion_tras_caida.py`; mutación `reanudacion-tras-caida.toml` **RC1-RC16 16/16**, EXIT 0 (§7). Condiciones cerradas por el CEO el 2026-10-26 (§10.3). `[LECT]`

**Ciclos 196 y 217 — NO VERIFICADO.** El mecanismo para cerrarlos existe y es idempotente, pero **confirmar que
quedaron cerrados exige leer `eventos.jsonl`**, prohibido por §7.3. No se declara que fueron recuperados. La única
evidencia concluyente sería la lectura agregada del historial real (decisión #3 del DP-RESIDENCIA, pendiente).

## Entregable C · Proyecciones (divergencia estado.json ↔ eventos.jsonl)

Una proyección con fecha vieja frente a un historial al día **no es corrupción**: es el modelo ADR-0023 (la proyección
se regenera del historial). El riesgo es de **presentación**: un panel que lea la proyección muestra algo viejo mientras
otro que derive del historial muestra lo actual (lo observado: «último ciclo 2026-09-08» vs historial a 2026-11-06).

Opciones (sin editar proyección ni historial):
1. **Reconstrucción completa** bajo demanda con `proyectar()` — ya existe; coste O(historial).
2. **Refresco incremental** de la proyección al cerrar cada ciclo con efecto — reduce la ventana de obsolescencia.
3. **Validación de consistencia** proyección↔ancla↔historial antes de publicar la proyección.
4. **Detección de proyección obsoleta:** comparar el `seq`/fecha de la proyección con el último `seq` del ancla; si
   difieren, marcar la vista como «proyección obsoleta: regenerar», en vez de mostrar datos viejos como actuales.
5. **Recuperación ante corrupción:** si el verificador marca `truncada_o_alterada`, regenerar desde el último `seq`
   íntegro del ancla; nunca «reparar» el historial.

## Entregable D · Diagnóstico operativo (estados)

| Estado | Qué es | Evidencia | ¿Bloquea? |
|---|---|---|---|
| `WAITING_FOR_NEXT_TASK` | estado inicial/octavo de una **tarea**; «a la espera de la siguiente» | `control_plane.py:57-61,1211,1188` | No en sí |
| Espera por ausencia de trabajo AUTO | descubrió solo trabajo bloqueado/elevado; nada AUTO-ejecutable | observatorio: 20 descubierto / 5 bloqueado / 11 elevado | Pausa legítima |
| PARADA | kill switch armado; ninguna acción se ejecuta | ADR-0003; `kill_switch.py` | Sí, por diseño |
| Recuperación pendiente | ciclo abierto sin cerrar tras caída | observatorio ciclos abiertos | Hasta recuperar |
| Error operativo | fallo real del motor | eventos de error | Sí |
| BLOQUEADA (reportado) | **causa exacta NO VERIFICADA** sin leer `~/.aura` | — | — |

**Modelo de observabilidad propuesto (sin inspeccionar contenido privado):** un indicador agregado que distinga, usando
solo metadatos derivables del historial y del ancla (no el contenido), cuál de las causas anteriores aplica —
`esperando_tarea` · `sin_trabajo_auto` · `parada_armada` · `recuperacion_pendiente` · `error` — y lo publique con su
`seq`/fecha de respaldo, para que ninguna vista muestre una proyección obsoleta como estado actual.

## Entregable E · Matriz de riesgos

| # | Hallazgo | Clase | Impacto | Prob. | Riesgo persistencia | Riesgo autonomía | Acción |
|---|---|---|---|---|---|---|---|
| R1 | Proyección `estado.json` obsoleta frente al historial | HECHO (diseño) | Panel engañoso | Alta | Bajo (historial intacto) | Medio (decisión sobre datos viejos) | Opción C-4: detectar y marcar obsoleta |
| R2 | Ciclos 196/217 abiertos; cierre no confirmado | NO VERIFICADO | Trazabilidad | Media | Bajo | Medio | Confirmar vía §7.3 (decisión #3) |
| R3 | 11 vs 12 (efecto real vs aplicado; P-017 revertido) | HECHO (conocido) | Métrica mal leída | Cierta | Nulo | Bajo | P-019 ya propuesto; etiquetas |
| R4 | Causa de BLOQUEADA no verificable sin `~/.aura` | NO VERIFICADO | Diagnóstico incompleto | — | — | Medio | Indicador agregado (Entregable D) |
| R5 | fsync parcial del FS ante caída en el borde | HIPÓTESIS | Cola sin anclar | Baja | Bajo (ancla lo detecta) | Bajo | Ya cubierto por el ancla |
| R6 | Despertares≫ciclos leído como anomalía | INDICIO (es diseño) | Falsa alarma | Media | Nulo | Bajo | Documentar en el panel |

## Entregable F · Decision Package (alternativas)

**Correcciones necesarias (requieren tu aprobación):**
- **F1 · Detección de proyección obsoleta** (R1): comparar `seq`/fecha de `estado.json` con el ancla; marcar la vista
  como obsoleta en vez de mostrarla como actual. *Ventaja:* elimina el «declarado ≠ real» del panel. *Riesgo:* bajo,
  solo lectura y presentación. *Aceptación:* con un historial más nuevo que la proyección, la vista dice «regenerar»;
  tras `proyectar()`, coinciden.

**Mejoras opcionales:**
- **F2 · Refresco incremental** de la proyección al cerrar ciclo con efecto (R1). *Aceptación:* la proyección nunca
  queda más de un ciclo por detrás.
- **F3 · Indicador agregado de estado** (R4, Entregable D). *Aceptación:* distingue las seis causas sin leer contenido.

**Decisiones que requieren tu aprobación:**
- **F4 · Lectura agregada de `~/.aura`** (decisión #3 del DP-RESIDENCIA) para confirmar R2 (ciclos 196/217) y la causa
  de BLOQUEADA. *Sin ella, R2 y R4 permanecen NO VERIFICADOS.*
- **F5 · D-INT-1** (merge a `main`) y **D-ORCH-6** (delegación): pendientes, no son defectos.

**Acciones bloqueadas por seguridad (no ejecutadas):** leer `~/.aura`/`eventos.jsonl`/`estado.json`, ejecutar la
recuperación real, confirmar 196/217, desarmar PARADA, reactivar autonomía.

## Pruebas de aceptación (cuando se autorice una corrección)
RED/GREEN sobre copia aislada con `AURA_DATOS` en tmp; mutación del catálogo afectado; Quality Gate; auditoría
independiente. Ninguna prueba escribe en producción. Nada se ejecuta en paralelo con `herramientas.mutar`.

## Cierre
Este DP es **diagnóstico y PROPUESTO**. No implementa correcciones, no reactiva autonomía, no toca producción ni
runtime, y **no se aprueba a sí mismo**: espera tu revisión y aprobación formal antes de cualquier implementación.

## §10 · Cierre de F1 (implementada, 2026-11-06)

**Autorizada e implementada** en `entorno/control-plane/control_plane.py`: detección de solo lectura
`estado_de_la_proyeccion(directorio)` que clasifica la proyección `estado.json` en cinco estados —
`PROYECCION_ACTUAL`, `PROYECCION_OBSOLETA`, `PROYECCION_AUSENTE`, `PROYECCION_INVALIDA`,
`ESTADO_NO_VERIFICABLE` — reutilizando `verificar_integridad_log`/`cargar`/`proyectar`/`validar` sin
reimplementar la verificación ni crear una segunda fuente de verdad. Compara solo la parte derivada del log
(`status`, `tareas`, `eventos_aplicados`, `eventos_ignorados`), excluyendo campos de entorno
(`actualizado`, `cuota`, `git`, `previo`) para no dar falsos positivos. Guarda delgada `cargar_si_actual`
que devuelve la proyección solo si es ACTUAL. Falla cerrado: nunca declara ACTUAL lo que no puede demostrar.
No regenera (eso sería F2) ni añade un indicador agregado (F3).

Evidencia `[EJEC]`: `test_red_proyeccion_obsoleta.py` **20 pruebas** (RED→GREEN); suite del control-plane
145 passed sin regresión; mutación `mutaciones/proyeccion-obsoleta.toml` **5/5** (`--raiz ../entorno/control-plane`);
Quality Gate del repo **PASS** (4562 passed; el QG cubre walking-skeleton, no toca el control-plane, por lo que
F1 se valida con su suite propia y la mutación). Auditorías independientes: corrección **CABE**, seguridad
**APROBADO**, sin hallazgos CRITICAL/HIGH/MEDIUM. Cambio puramente aditivo (+ función nueva; 0 líneas
eliminadas); no se tocó `proyectar`/`guardar`/`cargar`/`_leer_ancla`/`verificar_integridad_log`/`estado.json`/
`eventos.jsonl`/el ancla.

**Siguen pendientes de tu decisión:** F2 (refresco incremental), F3 (indicador agregado), F4 (lectura agregada
de `~/.aura`, decisión #3 — única vía para confirmar los ciclos 196/217 y la causa de BLOQUEADA), F5 (D-INT-1,
D-ORCH-6). F1 **no las implementa ni las desbloquea**.
