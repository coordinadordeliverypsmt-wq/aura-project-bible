# PROPUESTA DE ACTA — Avisos de NODO-01: caída y recuperación (opción B, revisión 2)

**Estado: BORRADOR para firma del CEO. No es un acta: no autoriza nada hasta que el CEO la apruebe.**
Revisión 2 (2026-10-18, orden ejecutiva 5.7.1): añade la **recuperación** sin almacén nuevo. Sustituye a la revisión 1.
Fuentes: `DECISION-REQUERIDA-SUPERVISION-DEPENDENCIAS-HOGAR.md` §5-5.7 · ficha `.claude/ficha-evidencia.md`.

## Hechos verificados `[EJEC]`

- `estado_nodo` (`core/nodos.py:306`) es pura; OFFLINE = edad del último latido > límite; UNKNOWN = receptor no vivo
  o nodo nunca registrado.
- El receptor (proceso aparte) es el **único escritor** de `~/.aura-red/nodos/registro.json` (1 151 B; lectura 0,088 ms).
- `RegistroNodos.desde_dict` exige **exactamente** 4 campos por nodo (`core/nodos.py:282-288`); un registro con un campo
  más se aparta como `.corrupto` y el receptor empieza vacío (`adapters/receptor_nodos.py:84-88`) → **ampliar el
  esquema sin compatibilidad perdería `primer_contacto` y `reinicios`**.
- `CentroNotificaciones` en memoria del proceso principal; dedupe `sha256(fuente|titulo)`; fuente `"aura"` admitida.
- Graphify: **sin camino** `ReceptorNodos → CentroNotificaciones` → cableado nuevo = integración (no abierta,
  `CHECKLIST-CONTINUIDAD.md:82`).
- El audit log **no** puede usarse como memoria de avisos: punto K de `DECISION-REQUERIDA-CONTINUIDAD-DE-RESULTADOS.md`
  y `tests/integration/test_frontera_continuidad.py:164` (`test_ninguna_superficie_de_conversacion_LEE_el_audit_log…`).
- No existe ningún dato persistido del inicio de la sesión anterior fuera del audit log (grep sin resultados).

## Opciones de recuperación evaluadas (`arquitecto-evaluador` + `auditor-consistencia`)

| Opción | Encaje | Motivo |
|---|---|---|
| **R1 — memoria de sesión** (estado anterior en RAM) | **Cabe** (solo D1) | Sin persistencia: D-M-8 no aplica; Core sin E/S vía puerto inyectado |
| R2 — campo `ultima_reconexion` en `registro.json` | Cabe con cambios + **enmienda a DP-NODO-01** | Riesgo de pérdida de datos por esquema estricto; umbral duplicado; tensión D-M-8 no resuelta |
| R3 — audit log como memoria | **Bloqueada** | Choca con el punto K y su prueba |

**Decisión técnica (dentro de la autoridad del ejecutor): primera versión = R1.** R2 queda como decisión aparte (D5).

## Decisiones que se proponen al CEO

**D1 — Alcance.** Apertura **parcial y nominal** de la fase de integración **solo** para: leer el estado de los nodos
ya calculado y entregarlo como aviso al Centro existente. Sin fuentes nuevas (`"aura"` ya admitida), sin canales nuevos
(escritorio/móvil fuera), sin capacidad de actuar sobre el nodo.

**D2 — Frecuencia.** Evaluar **al abrir AURA y en cada turno** (coste medido despreciable). El adaptador
(`adapters/receptor_nodos.py`) lee el registro; `composicion.py` inyecta un puerto en el orquestador (patrón de
`notificaciones`); el Core nunca abre ficheros.

**D3 — Persistencia: sin almacén nuevo y sin estado persistente nuevo.** El «último estado visto» de cada nodo vive en
**memoria de la sesión**. No se crea `avisados.json`, no se modifica `registro.json`, no se pide excepción a D-M-8.

**D4 — Momento.** Avisos al abrir AURA o en un turno posterior; **no** en tiempo real con AURA cerrado. Los textos lo
declaran.

**D5 (opcional, separada) — Recuperación ocurrida con AURA cerrado.** Solo si el CEO la quiere: enmienda a DP-NODO-01
(campo `ultima_reconexion`, `desde_dict` compatible con el esquema antiguo y el nuevo, umbral compartido con
`estado_nodo`), mostrada como **estado** («conectado desde …; antes sin latido desde …»), no como alerta. Fuera de esta
primera versión.

## Comportamiento (función pura en `core/nodos.py`: transiciones entre el estado anterior en memoria y el actual)

| Situación | Aviso (fuente `"aura"`) | Prioridad |
|---|---|---|
| Al abrir, nodo OFFLINE | «Al abrir AURA: NODO-01 sin latido desde <HH:MM DD-MM>» | alta |
| Durante la sesión, ONLINE/DEGRADED → OFFLINE | «Detectado en esta sesión: NODO-01 sin latido desde <HH:MM DD-MM>» | alta |
| Durante la sesión, OFFLINE → ONLINE/DEGRADED | «Detectado en esta sesión: NODO-01 conectado de nuevo (latido a las <HH:MM>)» | normal |
| Receptor de HC-1 caído (UNKNOWN) | «No se sabe el estado de los nodos: el receptor de HC-1 no está escuchando» | alta |
| Nodo nunca registrado (UNKNOWN) | ninguno | — |
| Al abrir, nodo ONLINE | ninguno (sin conocimiento previo no se afirma una recuperación) | — |

**Deduplicación por sesión, dos capas:** (1) la función solo emite en **transiciones** (al abrir: solo estados
anómalos), así que repetir la evaluación no produce avisos; (2) el título incluye la hora del latido que lo evidencia,
de modo que el mismo episodio tiene la misma huella y un episodio nuevo tiene otra. Umbral: el de `estado_nodo` (sin
histéresis añadida; el parpadeo se documenta como límite, sin inventar un valor). Solo informa; actuar desde un aviso
sigue el camino normal (`notificaciones.py:10-12`). Determinista, sin LLM (ADR-0014). Al cerrar la sesión la memoria se
pierde por diseño.

## Pruebas de aceptación (RED antes de GREEN)

| # | Prueba | Nivel |
|---|---|---|
| T1 | Al abrir con el nodo OFFLINE → la función devuelve 1 aviso; una segunda evaluación sin cambios devuelve **0** (se verifica en la función, no solo en el Centro) | unit |
| T2 | ONLINE → OFFLINE durante la sesión → 1 aviso «Detectado en esta sesión»; el siguiente turno, 0 | unit |
| T3 | OFFLINE → ONLINE durante la sesión → 1 aviso de recuperación, prioridad normal | unit |
| T4 | Receptor caído → aviso «No se sabe…»; **nunca** «sin latido» | unit |
| T5 | Nodo nunca registrado → 0 avisos al abrir y en turnos | unit |
| T6 | Caída, recuperación y nueva caída → dos avisos de caída con huellas **distintas** (no se fusionan episodios) | unit |
| T7 | Reloj de HC-1 que retrocede → sin falsa caída | unit |
| T8 | `registro.json` ausente o corrupto → el adaptador no lanza y no hay aviso falso | unit (adaptador) |
| T9 | Cableado real: la composición inyecta el puerto y el aviso llega al Centro; `core/` no importa el adaptador ni abre ficheros (frontera AST) | integración |

## Mutantes y cobertura efectiva (comprobada sobre el papel; se ejecutará con `herramientas.mutar`)

| Mutante | Degradación | Lo detecta |
|---|---|---|
| M1 | Avisar también del nodo nunca registrado | T5 |
| M2 | Tratar el receptor caído como OFFLINE (texto «sin latido») | T4 |
| M3 | No actualizar el estado anterior tras evaluar (repite cada turno) | T1, T2 — **solo porque comprueban la función**: la huella del Centro enmascararía M3 si se probara solo a través del Centro |
| M4 | Ignorar la transición OFFLINE → ONLINE | T3 |
| M5 | Desconectar el puerto en `composicion.py` | T9 |

Mutante adicional recomendado: quitar la hora del título (fusiona episodios) → detecta T6.

## Riesgos y dependencias

- **Dependencia de gobierno:** D1 (apertura parcial de integración). Sin firma, no se construye.
- **Cobertura:** las recuperaciones ocurridas con AURA cerrado no se avisan en esta versión (D5). Con el nodo aún caído,
  cada sesión vuelve a avisar una vez, que es lo correcto.
- Sin incompatibilidades con D-M-8 (no hay persistencia), ADR-0014, ALERTA-005 (no es una acción), ALERTA-002 (sin
  terceros), punto K (no se lee el audit log) ni D23 (fuente ya admitida, RF-9).
- La mutación **no** puede ejecutarse en paralelo con nada (CLAUDE.md §2) y HC-1 es limitado: QG y mutación, en serie.

## Criterios de salida

9/9 pruebas en verde · 5/5 mutantes detectados (más el adicional) · QG PASS · ECC sin CRÍTICO/ALTO tras correcciones ·
demostración: con el nodo detenido (o un registro de prueba) AURA muestra el aviso al abrir y la recuperación en sesión ·
CHECKPOINT con evidencia.

## Firma

- [ ] Apruebo D1-D4 (primera versión R1).
- [ ] Apruebo además D5 (enmienda a DP-NODO-01 para recuperación con AURA cerrado).
- [ ] Apruebo con cambios: ______________________
- [ ] Rechazo.

## Nota técnica de ejecución (2026-10-18, tras la orden 5.7.2)

El texto del receptor caído se amplió a «No se sabe el estado de los nodos: el receptor de HC-1 no está escuchando
(detectado a las HH:MM)». Motivo (revisión ECC, `code-reviewer` + `arquitecto-evaluador`): con el título constante, la
2ª caída del receptor en la misma sesión tenía la misma huella y el Centro la suprimía sin que el usuario la viera.
La hora de detección distingue episodios igual que la hora del latido en los avisos de nodo. Mutante M10 + prueba con
el Centro real. Sin cambio de alcance ni de significado.
