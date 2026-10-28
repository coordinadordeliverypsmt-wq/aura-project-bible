# Especificación contractual del Communication Plane

> **ACTUALIZACIÓN 2026-09-02 — `cerrar_tarea` RETIRADA DEL CONTRATO por decisión del CEO (opción 3
> del `DECISION_REQUIRED` de `G2`).** El Communication Plane **comunica; no certifica el cierre y no
> produce `COMPLETED`.** No reúne ninguna de las garantías de `DP-ORCH §14.bis`: no fija el criterio
> antes de invocar (regla 1), no puede ejecutarlo contra el árbol resultante (regla 3) y **no sabe
> quién le habla** —`limites_de_identidad()["autentica"] is False`—, así que no puede distinguir al
> Orchestrator del Worker que se autocertifica. **El cierre vive exclusivamente en el motor único:**
> `control_plane.transicion()` exige autoridad humana para `COMPLETED` y `agentes.cerrar_tarea()`
> exige efecto verificado (`A12`). La autoridad **no se importa** hacia este plano:
> `permisos_sobre_el_control_plane() == 'SOLO_LECTURA'` y `fuentes_de_autoridad() == ('control_plane',)`.
> La ausencia está protegida por cuatro pruebas de frontera y por los mutantes `G2-M14..M17`, que
> intentan reabrir la ruta —incluso **con otro nombre**— y mueren. **Símbolos: 48 → 47.**

> **ACTUALIZACIÓN 2026-08-25 — `D-CP-7` CERRADA:** `F-DCP7 = GREEN respecto al WORKER ADMINISTRADO`. `bwrap` + user namespace es enforcement real para el Worker dentro de la jaula. **Constraint arquitectónico permanente, no deuda:** no protege frente a otro proceso del **mismo UID**; sin privilegios esa frontera no se considera cerrable. **Siguen ABIERTOS** —y no se presentan como cerrados— el lanzador omitible, el TOCTOU, credencial+red, el audit log `rw` y la cobertura incompleta del hook. **Sigue abierta `D-CP-3`.**


> **ACTUALIZACIÓN 2026-08-23 — `D-CP-5` YA ESTÁ DECIDIDA E IMPLEMENTADA:** esquema CERRADO por tipo, con RED, GREEN, mutación 6/6 sin supervivientes y auditoría independiente. **Decisión del CEO del 2026-08-23** (mensaje de encargo: *«La decisión vigente es ESQUEMA CERRADO POR TIPO»*), registrada tardíamente el mismo día tras una auditoría independiente que señaló su ausencia como artefacto. Lo detectó esa misma auditoría: cinco documentos seguían declarándola abierta mientras el código ya la implementaba — «declarado ≠ real», esta vez del lado de la gobernanza. **Siguen abiertas `D-CP-7` y `D-CP-3`.**


Derivada **mecánicamente** de las 79 pruebas RED (`entorno/communication-plane/test_red_*.py`) por
extracción AST. **No es un informe:** es lo que debe existir el día que se autorice GREEN.

**Verificación cruzada, ejecutada:** 47 símbolos · **0 con dos naturalezas** (módulo vs método) ·
**0 con aridad incompatible** · 0 dependencias circulares (el grafo es un árbol: `abrir` → canal →
resto de métodos; las funciones de módulo no se llaman entre sí en las pruebas).

| Símbolo | Naturaleza | Firma observada | Retorno | Invariante / excepción | RED |
|---|---|---|---|---|---|
| `AutoridadInsuficiente` | constante/clase | — | `excepcion` | aprobar sin prueba de autoridad, o aprobarse a si mismo | 2 |
| `CAMPOS_DE_IDENTIDAD` | constante/clase | — | `tuple[str,...]` | contiene de, sesion_id y estado_leido (N-2) | 1 |
| `CAMPOS_MENSAJE` | constante/clase | — | `tuple[str,...]` | NINGUNO se llama autoriza/aprueba/permiso/permite/autorizacion/override | 1 |
| `MensajeInvalido` | constante/clase | — | `excepcion` | se lanza al PUBLICAR, nunca al leer: un mensaje invalido ya escrito contamina el historial | 6 |
| `TIPOS_MENSAJE` | constante/clase | — | `tuple[str,...]` | exactamente los 8 tipos del DP §4.1, ni uno mas | 2 |
| `TransporteAdapter` | constante/clase | — | `clase` | expone exactamente entregar() y recoger() | 2 |
| `abrir` | módulo | (1 pos) · (1 pos, sincronizacion_github) | `Canal` | unica forma de abrir; publicar/leer/lock son METODOS del canal | 28 |
| `aplicable` | módulo | (0 pos, estado_actual, mensaje) | `bool` | False si el estado cambio: concurrencia optimista | 1 |
| `aprobar` | método del canal | (1 pos, autoridad, causa, prueba) | `None` | exige prueba de autoridad; emisor != aprobador | 3 |
| `bloqueado_por` | método del canal | (1 pos) | `bool` | DECISION_REQUIRED sigue True hasta aprobacion valida | 4 |
| `clase_de` | módulo | (1 pos) | `str` | PROPUESTA/INFORMACION/SOLICITUD; ningun tipo es AUTORIZACION | 1 |
| `ejecucion_correcta` | módulo | (1 pos) | `bool` | MEDIDO: se decide por is_error, NUNCA por subtype | 2 |
| `entregar_a_receptor` | módulo | (1 pos) | `dict` | confianza=NO_CONFIABLE, ejecutable=False | 1 |
| `es_automatizable` | módulo | (1 pos) | `bool` | False sin orden verificable | 1 |
| `esquema_de_cuerpo` | módulo | (1 pos) | `dict` | modo=CERRADO  [DEPENDE DE D-CP-5] | 1 |
| `fuentes_de_autoridad` | módulo | (0 pos) | `tuple` | == ('control_plane',) y nada mas | 1 |
| `handoff` | método del canal | (0 pos) | `str` | autosuficiente: quien lo lee continua sin la conversacion | 3 |
| `hilo` | método del canal | (1 pos) | `list[dict]` | reconstruye por in_reply_to | 1 |
| `huecos_de_secuencia` | módulo | (1 pos) | `list[int]` |  | 1 |
| `id_de_mensaje` | módulo | (1 pos) | `str` | determinista sobre (tipo,de,para,in_reply_to,cuerpo) | 2 |
| `identidad_de_agente` | módulo | (1 pos) | `str` | 'UNKNOWN' para codex: no se inventa | 1 |
| `intentar_lock_no_bloqueante` | módulo | (1 pos) | `bool` |  | 1 |
| `leer` | método del canal | (1 pos) | `list[dict]` |  | 4 |
| `leer_desde` | método del canal | (0 pos, seq) | `list[dict]` | desde seq | 1 |
| `limites_de_identidad` | módulo | (0 pos) | `dict` | autentica=False; N-2 es trazabilidad | 1 |
| `limites_frente_a_inyeccion` | módulo | (0 pos) | `dict` | no impide la persuasion; impide su efecto | 1 |
| `lock` | método del canal | (0 pos) | `contexto` | flock; se libera si el proceso muere | 1 |
| `lock_se_libera_al_morir_el_proceso` | módulo | (1 pos) | `bool` | MEDIDO: True | 1 |
| `lock_tomado_por_otro_proceso` | método del canal | (0 pos) | `bool` |  | 1 |
| `marcar_procesado` | método del canal | (1 pos, por) | `None` | idempotencia: procesar dos veces no duplica efecto | 3 |
| `nuevo_mensaje` | módulo | (0 pos, cuerpo, de, para, tipo) | `dict` | incluye estado_leido | 1 |
| `pendientes` | método del canal | (0 pos, para) | `list[dict]` | filtra por destinatario | 3 |
| `permisos_sobre_el_control_plane` | módulo | (0 pos) | `str` | 'SOLO_LECTURA' | 1 |
| `permitido` | módulo | (1 pos, estado) · (1 pos, estado, mensaje) | `bool` | INVARIANTE CENTRAL: una frase en cuerpo NO altera el veredicto | 1 |
| `prueba_de_autoridad_local` | módulo | (0 pos) | `dict` |  | 2 |
| `prueba_de_concurrencia` | módulo | (1 pos, escritores, mensajes_por_escritor) | `dict` | 4x800 lineas -> 0 corruptas | 1 |
| `publicar` | método del canal | (0 pos) · (0 pos, cuerpo, de, in_reply_to, para, tipo) · (0 pos, cuerpo, de, para, tipo) | `id:str` | determinista sobre el contenido: publicar dos veces da el mismo id | 26 |
| `registrar_coste` | módulo | (1 pos) | `dict` | coste por invocacion; cuota_restante='UNKNOWN' | 1 |
| `requiere_credenciales` | módulo | (0 pos) | `bool` | False: local-first, D24 | 1 |
| `retractar` | método del canal | (1 pos, motivo) | `None` | append-only: retractar ANEXA, no borra | 1 |
| `ruta_log` | módulo | (1 pos) | `Path` |  | 3 |
| `rutas_de_ejecucion_desde_el_cuerpo` | módulo | (0 pos) | `tuple` | == () vacia | 1 |
| `sincronizar` | método del canal | (0 pos, simular_fallo_de_red) | `dict` | GitHub es ESPEJO opcional; su fallo no rompe el canal | 1 |
| `transportes_autorizados` | módulo | (0 pos) | `dict[str,bool]` | AUTORIZACION, no disponibilidad: modelo externo False | 1 |
| `transportes_disponibles` | módulo | (0 pos) | `dict[str,str]` | tri-estado MEDIDO: fichero DISPONIBLE, codex UNKNOWN | 1 |
| `validar` | módulo | (1 pos) | `dict` | rechaza tipo desconocido y campos prohibidos | 1 |
| `validar_respuesta` | módulo | (1 pos, ids_conocidos) | `None` | lanza si in_reply_to no existe | 1 |

---

## ⚠ Verificación cruzada contra las fuentes de verdad — **dos requisitos anticipan decisiones no tomadas**

La coherencia **interna** es completa. Contra las fuentes de verdad aparecen **dos** requisitos que
**dan por resuelta una decisión que el CEO no ha tomado**. No los corrijo ni los retiro: los señalo.

| Requisito del contrato | Decisión que anticipa | Dónde |
|---|---|---|
| `esquema_de_cuerpo(tipo)["modo"] == "CERRADO"` | **`D-CP-5`** — lista negra → esquema cerrado, **sin decidir** | `test_v4_el_cuerpo_se_valida_contra_un_esquema_CERRADO_por_tipo` |
| Publicar un `cuerpo` con `criterio` lanza `MensajeInvalido` | **`D-CP-4`** — opción **(b)**, criterio fuera de `cuerpo`, **sin decidir** | `test_v1_el_criterio_de_finalizacion_no_puede_venir_del_cuerpo` |

El segundo ya se escribió declarando su propia condición —*«fija UNA de las tres opciones que el CEO
no ha elegido»*—; el primero **no lo declaraba**, y aquí queda dicho.

**Consecuencia práctica y concreta:** el resto del contrato —46 de 48 símbolos— **no depende de
ninguna decisión pendiente**. Solo estos dos quedan condicionados.

## Grafo de dependencias

```
abrir(ruta) ─▶ Canal
                ├─ publicar · leer · leer_desde · hilo · pendientes
                ├─ marcar_procesado · retractar · handoff
                ├─ aprobar · bloqueado_por
                └─ lock · lock_tomado_por_otro_proceso · sincronizar

funciones de módulo: independientes entre sí — ninguna llama a otra.
```

**Sin ciclos.** El único punto de entrada es `abrir()`; todo lo demás cuelga de él o es una función
pura de módulo.

## Reparto de responsabilidades — una sola autoridad de cierre

```
COMUNICACIÓN (este plano)   →  transporte · lectura · respuesta
MOTOR ÚNICO (Control Plane) →  criterio · autorización · ejecución · verificación · cierre
```

**No hay atajo entre los dos.** El canal no importa el motor, y el motor no delega el cierre.

## Siguiente paso mínimo para B1

**B1 = transporte de fichero, un solo extremo.** El subconjunto mínimo que lo hace real son
**11 símbolos**, todos libres de decisiones pendientes:

`abrir` · `publicar` · `leer` · `leer_desde` · `ruta_log` · `validar` · `id_de_mensaje` ·
`CAMPOS_MENSAJE` · `TIPOS_MENSAJE` · `MensajeInvalido` · `lock`

Con ellos, el CEO deja de copiar y pegar mensajes. **No requieren Codex, ni cuota, ni tocar
producción, ni `D-CP-4`, ni `D-CP-5`.** Requieren **`D-CP-2`**: autorizar GREEN.
