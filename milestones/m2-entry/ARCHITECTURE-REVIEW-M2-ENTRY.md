---
documento: "Architecture Review — M2 Entry"
version: 1.0.0
autor: "CTO"
fecha: "2026-07-20"
estado: "Pendiente de aprobación del CEO. NO se ha iniciado implementación de M2."
---

# Architecture Review — M2 Entry (Manos Digitales)

## 0. Hallazgos previos que condicionan el arranque

La revisión de entrada detectó **tres defectos preexistentes** que M2 amplificaría si no se corrigen
antes de escribir adaptadores nuevos.

**H1 — El contrato `Adapter` declara una firma que no es la real.**

```python
# contracts.py declara:
async def execute(self, command: str, args: dict) -> dict: ...
# pero el orquestador llama con CUATRO argumentos:
await self.ha.execute(action, args, tid, cmd_ev.event_id)
```

`runtime_checkable` verifica que el método **exista**, no su firma: `test_adaptador_cumple_contrato`
pasa mientras el contrato es incorrecto. **Cualquiera que escriba un adaptador nuevo siguiendo el
contrato declarado escribirá un adaptador roto.** M2 consiste precisamente en escribir adaptadores
nuevos. Es la misma familia de defecto que ALERTA-004: una declaración que nadie verifica.

**H2 — El audit log no persiste.** `observability._records` es una lista en memoria: se pierde en cada
reinicio. La Bible (2.2 §3.2) exige para el cierre de M2 *"toda acción registrada en el audit log"*.
Un registro de auditoría volátil no cumple esa función cuando lo que se audita son **acciones reales
sobre archivos del usuario**.

**H3 — Las listas de permisos son abstractas.** `GREEN` contiene `organizacion` y `monitoreo`;
`RED` no contempla ninguna acción específica de sistema de archivos, procesos o red. M2 requiere un
**catálogo concreto** (6.4 §1), no categorías genéricas.

Los tres se corrigen en **M2.0**, antes de cualquier capacidad.

## 1. Objetivos de M2

Entregar las **manos digitales** del MVP: capacidades 4, 5 y 9 del acta D2.

| # | Capacidad | Alcance en M2 |
|---|---|---|
| 4 | Agente local del computador principal | Acciones de lista verde: buscar/abrir archivos, organizar, consultar estado |
| 5 | Motor de automatización | Reglas `trigger → condición → acción`, **definidas por el usuario** (las sugeridas son M3) |
| 9 | Centro único de notificaciones | Consolida computador + Home Assistant + AURA |

**Objetivo transversal:** que toda acción con efecto real quede sujeta a Permisos/HITL y registrada en
un audit log **persistente**.

**Fuera de alcance explícito:** NAS, Docker, redes y Android (hasta R2, 2.2 §4.4); automatizaciones
sugeridas (M3); captura de micrófono, VAD y barge-in (hito independiente ya diferido por el CEO).

## 2. Riesgos nuevos

**RN-1 — El error deja de ser simulado (riesgo dominante).** En M1 una acción mal autorizada encendía
una luz falsa. En M2 borra, mueve o sobrescribe **archivos reales del usuario**. La tolerancia a falsos
negativos en la lista roja pasa de "importante" a "existencial": un solo fallo puede destruir datos
irrecuperables.
*Mitigación:* catálogo de acciones cerrado y clasificado **antes** de implementar el adaptador;
**dry-run obligatorio** (6.4 §2); prohibición de comodines en rutas hasta que exista confirmación
explícita por acción.

**RN-2 — Ejecución de comandos arbitrarios.** Un "agente del computador" tiende a derivar en
"ejecuta este comando". Eso convertiría la lista roja en irrelevante: cualquier acción destructiva
podría envolverse en un comando.
*Mitigación:* **no se implementa ejecución de comandos arbitrarios en M2.** El adaptador expone un
catálogo finito de operaciones tipadas. Si en el futuro se requiere, será por su propio ADR y alerta.

**RN-3 — Automatización = acciones sin humano delante.** Una regla `trigger → acción` ejecuta cuando el
usuario no está mirando. Es el primer punto del proyecto donde AURA actúa sin presencia humana.
*Mitigación:* toda automatización que toque lista roja **exige confirmación en el momento**, nunca
preautorizada; dry-run antes del primer disparo real; kill switch debe detener el motor de reglas, no
solo el turno conversacional.

**RN-4 — Ampliación de la superficie de auditoría.** Con acciones reales, el audit log deja de ser
observabilidad y pasa a ser **prueba forense**. Requiere persistencia, integridad y no-repudio básico.
*Mitigación:* H2 se corrige en M2.0 con escritura atómica y verificación de integridad, reutilizando el
mecanismo ya probado en `PersistentMemory`.

**RN-5 — Notificaciones como vector de ruido y de fuga.** Consolidar notificaciones implica leer
contenido potencialmente sensible de varias fuentes.
*Mitigación:* aplicar el alcance de sesión de ALERTA-002; no persistir contenido de terceros más allá
de lo necesario.

**RN-6 — Hardware.** Cada validación con LLM real cuesta 2-5 minutos. M2 tiene más casos que M1.
*Mitigación:* usar `qwen2.5:0.5b` para validación funcional (equivalencia de comportamiento seguro ya
demostrada al 100%), reservando `3b` para calidad.

## 3. Capacidades a incorporar

| Fase | Contenido |
|---|---|
| **M2.0** | Corrección de H1, H2, H3 — **bloqueante** |
| **M2.1** | Catálogo de acciones del computador + clasificación verde/roja + pruebas, **antes** del adaptador |
| **M2.2** | Adaptador del computador principal (lectura y organización de archivos) |
| **M2.3** | Motor de automatización con dry-run |
| **M2.4** | Centro de notificaciones |
| **M2-Exit** | Architecture Review + Executive Summary (D25) |

## 4. Componentes del Core que se modificarán

| Componente | Cambio | Naturaleza |
|---|---|---|
| `contracts.py` | Corregir firma de `Adapter`; añadir prueba de **firma**, no solo de existencia | Corrección (H1) |
| `observability.py` | Audit log persistente con integridad | Ampliación (H2) |
| `permissions.py` | Catálogo concreto de acciones de sistema | Ampliación (H3) |
| `orchestrator.py` | Punto de enganche del motor de automatización | Ampliación |
| `kill_switch.py` | Debe detener también automatizaciones en curso | Ampliación |

**Ningún componente se reescribe.** Todos los cambios son correcciones o extensiones aditivas.

## 5. Contratos que deben permanecer invariantes

| Contrato | Compromiso |
|---|---|
| `ModelProvider` | **Invariante.** M2 no toca el router ni los proveedores |
| `MemoryStore` | **Invariante.** |
| `EventBus` | **Invariante.** Las automatizaciones se suscriben; no alteran el contrato |
| `VoiceAdapter` | **Invariante.** Recién formalizado en T2.b |
| `Adapter` | **Se corrige la declaración para que refleje el uso real** (H1). No es un cambio de comportamiento: es alinear el contrato con lo que el sistema ya hace |
| **ADR-0014** | **Invariante y reforzado.** Ninguna decisión sobre permisos, rutas o efectos puede depender del LLM. La clasificación verde/roja se resuelve en el Core |
| ADR-0001, ADR-0003, D24 | **Invariantes.** |

## 6. Nuevas evaluaciones y pruebas

| Eval / prueba | Qué demuestra | Diseño anti-falso-PASS |
|---|---|---|
| `accion_destructiva_siempre_confirmada` | 100% de acciones de archivo destructivas pasan por HITL | Parametrizada sobre **todo** el catálogo, no una muestra |
| `sin_ejecucion_de_comandos_arbitrarios` | El adaptador rechaza cualquier operación fuera del catálogo | Intento explícito de inyección de comando |
| `dry_run_no_produce_efectos` | El dry-run no toca el sistema de archivos | Espía de sistema de archivos + **caso de control** que sí escribe |
| `automatizacion_respeta_lista_roja` | Una regla que dispara acción roja se detiene | Regla real disparada por evento real |
| `kill_switch_detiene_automatizaciones` | El kill switch alcanza al motor de reglas | Control: sin kill switch la regla **sí** ejecuta |
| `audit_log_sobrevive_reinicio` | Persistencia del registro forense | Nueva instancia lee del disco |
| `contrato_adapter_firma` | La firma declarada coincide con la real | `inspect.signature`, no `isinstance` |

**Criterio heredado de T1, obligatorio para toda prueba nueva:** *¿qué tendría que romperse en el
sistema para que esta prueba falle?* Si la respuesta es "nada" o "el doble", la prueba no vale. Todas
las evals con espía llevan **caso de control**.

## 7. Criterios de terminación (Definition of Done)

M2 se considera terminado cuando **todos** se cumplen:

1. H1, H2 y H3 corregidos y verificados.
2. Catálogo de acciones del computador **cerrado, clasificado y probado** por acción.
3. Las 7 evaluaciones de §6 en **PASS**, las críticas sin excepción.
4. **Cero** acciones con efecto que alcancen un adaptador sin pasar por Permisos (eval con control).
5. Audit log **persistente**, íntegro y verificado tras reinicio.
6. Kill switch detiene conversación **y** automatizaciones.
7. Dry-run demostrado sin efectos colaterales.
8. Quality Gate PASS; sin regresión en las garantías de M1.
9. Demo de capacidad M2 con stack real y **0 errores no recuperados**.
10. Architecture Review M2-Exit + Executive Summary (D25).
11. **Sin alertas de arquitectura abiertas.**

## 8. Product Readiness

Métrica separada del avance técnico. Responde a: *¿qué tan cerca está AURA de ser un compañero usable
por una persona durante una jornada completa?*

| Dimensión | Peso | Estado | Puntuación |
|---|---|---|---|
| Entiende y responde con sentido | 15% | Funciona con LLM local | **12%** |
| **Responde a tiempo** | **25%** | **160.267 ms por turno** frente a 1.200 ms objetivo | **0%** |
| Entrada y salida por voz | 15% | TTS y STT validados; **sin captura de micrófono** | **5%** |
| Conversación natural (interrumpible) | 10% | No existe barge-in | **0%** |
| Recuerda entre sesiones | 10% | Verificado con dato discriminante | **9%** |
| **Hace cosas útiles (acciones reales)** | **15%** | Solo dispositivos simulados | **1%** |
| Disponible sin fricción | 5% | Requiere lanzar procesos a mano | **0%** |
| Seguro y gobernable | 5% | HITL, kill switch, grounding, todo en verde | **5%** |
| | | **PRODUCT READINESS** | **≈ 32/100 → 32%** |

Corrección: la suma ponderada real es **12+0+5+0+9+1+0+5 = 32** sobre 100 posibles.

### Lectura honesta de la cifra

**Avance técnico ~28% · Product Readiness 32%.** Las dos cifras miden cosas distintas y ninguna debe
consolar.

El dato que domina todo lo demás: **a 160 segundos por turno, veinte interacciones son 53 minutos de
espera pura.** Ninguna funcionalidad compensa eso. Mientras la latencia no baje, AURA **no es usable
durante una jornada** aunque se completen M2 y M3 al 100%.

De ahí una conclusión incómoda pero necesaria: **M2 aumentará el avance técnico sin mover apenas el
Product Readiness.** Añadir manos digitales a un sistema que tarda tres minutos en responder produce
un sistema que tarda tres minutos en actuar. La palanca real de producto es el hardware objetivo
(HC-1), no las capacidades siguientes.

Esto **no es un argumento para detener M2** —las capacidades hay que construirlas y el orden del
roadmap es correcto— sino para no confundir progreso de ingeniería con progreso de producto. La
métrica que pediste sirve exactamente para eso.

### Objetivo de Product Readiness al cierre de M2

**≈ 45%**, asumiendo que la latencia siga sin resolverse: sube "hace cosas útiles" de 1% a ~12% y
"disponible sin fricción" de 0% a ~3%. **El salto grande (a ~70%) requiere hardware objetivo**, no más
código.

---

**No se ha iniciado implementación de M2.**
