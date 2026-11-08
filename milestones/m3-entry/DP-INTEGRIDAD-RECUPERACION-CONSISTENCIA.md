---
documento: "Decision Package — Integridad, recuperación y consistencia del estado autónomo"
fecha: 2026-11-06
estado: "F1, F2, F3 y F4 APROBADAS por el CEO e IMPLEMENTADAS (§10-§13). F5 (D-INT-1, D-ORCH-6) AUTORIZADA (2026-11-08), en ejecución. El Director no se aprueba a sí mismo lo no autorizado."
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

## §11 · Cierre de F2 (implementada, 2026-11-06)

**Autorizada e implementada**: `regenerar_proyeccion(directorio)` en `entorno/control-plane/control_plane.py`, regeneración
EXPLÍCITA y CONTROLADA del `estado.json` desde el log. Solo regenera si F1 lo detecta OBSOLETA o AUSENTE **y** el log es
verificable (íntegro + completitud demostrada); ante NO_VERIFICABLE no escribe; ACTUAL es no-op. Los campos derivados del
log vienen de `proyectar()`; el gobierno por tarea (`previo`, `creada_sin_origen`) se **deriva del propio log** —de
`datos["previo"]` del último evento de estado, o de `ESTADO_SIN_REGISTRAR` para una tarea registrada-sin-transicionar—,
**nunca se fabrica**. Los campos de entorno (git, cuota, trabajo_completado, …) se preservan del `estado.json` existente.
Valida con `validar`+`validar_tareas` y escribe con el escritor único `guardar` (atómico): nunca deja un estado parcial.
Si una tarea no es reconstruible sin fabricar gobierno (COMPLETED cuya autoridad en el log no es humana), **rechaza la
regeneración entera y lo reporta** (DECISION_REQUIRED, no se fabrica). Es explícita: no la llama ninguna ruta de lectura
(no hay auto-reparación; eso sería F3). No modifica F1, `proyectar`, `guardar`, `cargar`, `_leer_ancla` ni
`verificar_integridad_log`.

Evidencia `[EJEC]`: `test_red_regeneracion_proyeccion.py` **19 pruebas** (RED→GREEN, incluidos los casos
registrada-sin-transicionar, mixto, COMPLETED-sin-autoridad rechazado, fallo de escritura sin estado parcial, no toca
eventos/ancla, idempotencia); suite del control-plane 155 passed sin regresión; mutación
`mutaciones/regeneracion-proyeccion.toml` **7/7** (RP5 retirado y documentado como equivalente: `guardar` ya revalida);
Quality Gate del repo **PASS** (4562). Diff aditivo (+140/−0); no se tocaron las funciones protegidas.

Un defecto propio de F2 (falso rechazo de una tarea registrada-sin-transicionar) lo detectó la **auditoría en línea del
Director** y se corrigió antes de publicar. Limitación declarada: las dos auditorías independientes de F2 (arquitectura y
seguridad) cayeron por límite de sesión; la verificación de F2 fue del orquestador en línea (implementador ≠ auditor:
el ingeniero es Sonnet, el auditor el Director/Opus), más la mutación 7/7 y el QG. Conviene una auditoría independiente
de F2 cuando el presupuesto de sesión lo permita.

**Siguen pendientes de tu decisión:** F3 (indicador agregado), F4 (lectura agregada de `~/.aura`, decisión #3), F5
(D-INT-1, D-ORCH-6).

## §12 · Cierre de F3 (implementada, 2026-11-06)

**Autorizada e implementada**: `integridad_del_control_plane(directorio)` en `entorno/control-plane/control_plane.py`,
INDICADOR AGREGADO de integridad de SOLO LECTURA que consolida F1 (`estado_de_la_proyeccion`) en un veredicto
`{integridad: "ok"|"degradada"|"no_verificable", verificable, proyeccion, regeneracion_pendiente, seq_confirmado,
seq_proyeccion?, motivo, integridad_log?}`. Mapeo con fallo seguro (nunca "ok" ni verificable si el log no es
verificable); `regeneracion_pendiente` = verificable ∧ proyección ∈ {OBSOLETA, AUSENTE, INVALIDA} (exactamente el
conjunto donde F2 actuaría). **Separa integridad de autorización (PARADA) y de disponibilidad (cola/cuota):** no las
consulta ni las mezcla. Es puro (no escribe, no llama a `regenerar_proyeccion`, no reclasifica: deriva de F1 una sola
llamada), no crea una segunda fuente de verdad. El subinforme de `verificar_integridad_log` se expone bajo la clave
propia `integridad_log` (no pisa el veredicto string). No se invoca desde ninguna lectura (no hay consumidor todavía).
No modifica F1, F2, `proyectar`, `guardar`, `cargar`, `_leer_ancla` ni `verificar_integridad_log`.

Evidencia `[EJEC]`: `test_red_integridad_agregada.py` **17 pruebas** (RED→GREEN; incluye el test de no-colisión de
claves); suite del control-plane sin regresión; mutación `mutaciones/integridad-agregada.toml` **9/9** (IA1-IA9, IA9
blinda la no-colisión); Quality Gate del repo **PASS** (4562; un primer intento dio un FAIL espurio por un test de
tiempo intermitente de `test_nodo_agente`, ajeno a F3 —pasa 3/3 bajo carga normal—, confirmado y relanzado a PASS
limpio). Auditorías independientes: corrección **CABE CON CONDICIONES** (condición 2 atendida con el test + IA9;
condición 1 = el docstring de F2 omite INVALIDA, riesgo residual documental, F2 no se reabre); seguridad **APROBADO**,
sin hallazgos. Diff aditivo (+75/−0 + el test/IA9); funciones protegidas intactas.

**Riesgo residual declarado:** el docstring de F2 (§11) dice "OBSOLETA o AUSENTE" y omite INVALIDA, aunque el código de
F2 sí la procesa; F3 está alineada con el COMPORTAMIENTO de F2, no con su docstring. Es deuda documental preexistente de
F2; no se corrige aquí para no reabrir F2.

**Siguen pendientes de tu decisión:** F4 (lectura agregada de `~/.aura`, decisión #3 — única vía para confirmar los
ciclos 196/217 y la causa de BLOQUEADA) y F5 (D-INT-1, D-ORCH-6). Con F1+F2+F3, el Entregable C/D del DP queda cubierto
salvo F4/F5.

## §13 · Cierre de F4 (lectura agregada de residencia, implementada 2026-11-08)

**Autorizada por el CEO (2026-11-08)** la lectura agregada de `~/.aura` (decisión #3 del DP-RESIDENCIA). Dos entregas:

**A. Función reutilizable** `lectura_agregada(directorio, ruta_audit=None)` en `entorno/control-plane/control_plane.py`:
informe AGREGADO y SIN CONTENIDO (solo números, enums, ids de seq y nombres de tipo de un VOCABULARIO CERRADO; cualquier
tipo libre → `"otros"`). Bloque control-plane (seq dup/huecos, ciclos cerrados/abiertos, recuento por tipo conocido,
status/recuento de tareas por enum) y bloque audit (parser PROPIO, NUNCA `AuditLog` —su `__init__` reconcilia = escribe—:
seq dup/huecos, segmentos, huérfanos). PURA de solo lectura. No modifica F1/F2/F3 ni las funciones protegidas.

**B. Lectura agregada ejecutada sobre los DATOS REALES** `[EJEC]`, write-free (confirmado por mtimes), respondiendo F4:
- **Decisión #3 — audit `~/.aura/audit.jsonl`:** 1345 líneas, seq 1..1331, **14 seq duplicados** (daño de concurrencia
  anterior a P1, antes del cerrojo), **0 huecos, 0 huérfanos**, sin rotación. Sin exponer contenido.
- **Ciclos 196/217:** el control-plane de producción (`m3-entry/entorno/control-plane/eventos.jsonl`, 4334 eventos, seq
  1..4334, 0 duplicados/huecos) tiene 366 ciclos cerrados y **2 ABIERTOS = exactamente 196 y 217**: NO fueron cerrados/
  recuperados. (El mecanismo de DP-RECUPERACION es idempotente, pero estos dos ciclos del pasado siguen abiertos.)
- **Causa de BLOQUEADA:** no es una caída. `estado.json` está OBSOLETO (status `WAITING_FOR_NEXT_TASK`, actualizado
  2026-09-01) frente al log vivo; `despertar_rechazado` domina (2655 de ~3000 despertares) = espera sin trabajo
  AUTO-ejecutable. Es la obsolescencia de proyección que F1/F2/F3 atacan (F2 la regeneraría; F3 la marca `degradada`).

Evidencia `[EJEC]`: `test_red_lectura_agregada.py` **23 pruebas** (RED→GREEN; privacidad con secretos plantados en msg/
evento/módulo/descripción/causa/tipo/id/provenance/rutas/bidi, DoS por anidamiento, pureza bytes+mtime, sin AuditLog);
suite control-plane sin regresión; mutación `lectura-agregada.toml` **10/10** (LA1 reanclado al vector real tras detectar
que era equivalente; LA9/LA10 de los dos defectos corregidos); Quality Gate **PASS** (4562). Auditorías independientes:
corrección **CABE**; privacidad/seguridad **RECHAZADO** en 1.ª ronda (fuga por `tipo` libre CRÍTICO + DoS ALTO) →
corregido (vocabulario cerrado + captura de RecursionError) → **APROBADO** en 2.ª ronda (41 checks de ataque, 0 fugas).
Diff aditivo; funciones protegidas intactas.

**Defectos hallados y corregidos durante la integración:** (1) CRÍTICO — `recuento_por_tipo` usaba el `tipo` libre como
clave y filtraba contenido; corregido con vocabulario cerrado + `"otros"`. (2) ALTO — DoS por `RecursionError` no
capturado en los parsers del audit; corregido. (3) LA1 era un mutante equivalente (defensa en profundidad del bloque
audit); reanclado al límite real. Las dos auditorías (corrección/privacidad) se repartieron el trabajo: la adversarial
cazó la fuga que la de corrección, al asumir `tipo` enum, no vio.

**Riesgos residuales:** el `seq` reportado de un ciclo abierto es FIFO-canónico, no causal, bajo solapamiento de la misma
familia (el recuento siempre es correcto); asimetría bool/int inocua con datos reales. Ninguno afecta las respuestas de F4.
