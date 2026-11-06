# DECISIÓN REQUERIDA — Aviso al usuario cuando una dependencia del hogar deja de funcionar

**Estado: PROPUESTA (no autorizada, nada construido).** Redactada 2026-10-18 tras dos bloqueos reales observados
el mismo día. No modifica DP, ADR, actas ni el Plan de Formación (que se actualiza en el Consejo, con evidencia
del Centro de Gobierno).

## 1. Evidencia del uso real `[EJEC]` (CHECKPOINT 2026-10-18 (f)-(g))

| # | Qué pasó | Cuánto tiempo sin que nadie lo supiera | Cómo se detectó |
|---|---|---|---|
| 1 | NODO-01 sin conexión NATS (reloj desfasado; 1 949 handshakes TLS fallidos) | **~6 días** (10-12 → 10-18) | Diagnóstico manual de rendimiento de HC-1 |
| 2 | Home Assistant con el hilo principal al 100 % y `:8123` sin responder, aunque systemd lo diera por `active` | ≥ 1 h (desde ~09:59) | Diagnóstico manual |

En ambos casos el sistema **sabía** el estado o podía saberlo, pero **no lo comunicó**.

## 2. Qué existe ya (no se duplica)

- `core/nodos.py:30,316` calcula `OFFLINE` desde la edad del último latido; `informe_nodos` lo muestra bajo
  demanda (`--nodos`) y `test_informe_nodos.py::test_nodo_viejo_es_offline` lo prueba.
- `core/notificaciones.py` (`Notificacion`, `notificacion_de_accion`) es el canal de avisos al usuario, gobernado
  por el Motor Único. **No tiene ninguna referencia a nodos ni a la salud de HA** `[EJEC grep]`.
- Para HA no existe sonda de salud funcional (solo el estado de systemd).

## 3. Propuesta mínima (si se autoriza)

Emitir **una** notificación por transición (no por latido) cuando:
(a) un nodo pasa a `OFFLINE` y sigue así más de un umbral, y cuando vuelve a `ONLINE`;
(b) HA deja de responder a una sonda HTTP local (`/manifest.json`) durante un umbral, y cuando se recupera.
Reutiliza `core/nodos.py` (estado), `Notificacion` (canal) y el receptor existente; solo **avisa**: no reinicia
servicios ni toca el nodo (eso seguiría exigiendo autorización humana, lista roja en caso de duda — ADR-0003).

## 4. Decisión que se pide al CEO

- **(A)** Autorizar un DP de construcción para (a)+(b).
- **(B)** Solo (a), nodos (el estado ya existe; el incremento es el más pequeño).
- **(C)** No construir; registrar ambos casos como observación para el próximo Consejo de Formación.

**Riesgos:** ruido de avisos si el umbral es corto (mitigado: aviso por transición con histéresis); que (b)
amplíe el alcance del MVP (D23) — por eso (B) existe. **Reversibilidad:** alta (solo añade avisos).
**Incertidumbre:** dos observaciones en un día no son aún «evidencia repetida» en sentido estricto; la opción (C)
respeta esa regla al pie de la letra.

---

## 5. Plan de ejecución de la opción B (preparado 2026-10-18; **no ejecutado**, sin autorización)

### 5.1 Hechos de arquitectura que condicionan el diseño `[EJEC]`

- `core/nodos.py:306` `estado_nodo(registro, ahora, receptor_vivo)` es **pura** y se evalúa bajo demanda. Un OFFLINE
  es **ausencia** de latidos: ningún evento lo dispara; hace falta una **evaluación**.
- El **receptor** es un proceso aparte (`aura-receptor-nodos.service`, `__main__.py:539`), con bucle de vida cada 10 s
  (`adapters/receptor_nodos.py:133-156`), y persiste `<ruta>/nodos/registro.json` (`:4-5`, `leer_registro` :53).
- `CentroNotificaciones` (`core/notificaciones.py:68`) vive **en memoria del proceso principal** de AURA
  (`composicion.py:544`), deduplica por `huella = sha256(fuente|titulo)` mientras no esté purgada (`:60-62,78-84`) y
  solo admite `FUENTES_MVP = ("computador", "home_assistant", "aura")` (`:28`). Hoy solo lo alimenta el orquestador
  tras acciones/reglas (`orchestrator.py:2300,3158`).
- **El proceso principal de AURA no corre continuamente**: los servicios persistentes son HA, NATS y el receptor.
  ⇒ Con el mecanismo existente, el aviso llega **cuando el usuario abre/usa AURA**, no en el instante de la caída.

### 5.2 Alcance mínimo (sin canal nuevo, sin proceso nuevo, sin fuente nueva)

1. **Función pura nueva** en `core/nodos.py` (junto a `estado_nodo`): `transiciones_de_nodos(registro, ahora,
   receptor_vivo, conocidos) -> (avisos, conocidos_nuevos)`, que compara el estado actual de cada nodo con el
   último **notificado** y devuelve solo **cambios** ONLINE→OFFLINE y OFFLINE→ONLINE (UNKNOWN por receptor
   caído = un aviso distinto, «HC-1 no escucha»).
2. **Punto de evaluación único** en el proceso principal: al **arrancar la sesión** y en cada turno (coste: leer un
   JSON pequeño), lee `registro.json` con `leer_registro` y entrega cada aviso a `CentroNotificaciones.recibir` con
   `Notificacion("aura", "NODO-01 sin conexión desde <hora>", prioridad="alta")` / `("aura", "NODO-01 conectado
   de nuevo", "normal")`.
3. **Deduplicación entre sesiones:** el «último estado notificado» se guarda en un fichero propio pequeño junto al
   registro (`<ruta>/nodos/avisados.json`, escritura atómica, 0600) — sin él, cada sesión repetiría el aviso.
   La huella del centro ya evita duplicados **dentro** de la sesión.
4. **Solo informa.** No reinicia el agente, no toca el nodo, no ejecuta acciones (no pasa por el Motor Único porque
   no es una acción; actuar desde la notificación seguiría el camino normal, `notificaciones.py:10-12`).
5. Superficie **determinista**: sin LLM (ADR-0014); el texto sale del estado calculado.

### 5.3 Archivos afectados (previstos)

`core/nodos.py` (función pura) · `adapters/receptor_nodos.py` (solo lectura reutilizada; quizá un helper de ruta de
`avisados.json`) · `composicion.py` u `orchestrator.py` (un único punto de evaluación, a decidir por el auditor de
cableado) · pruebas nuevas `tests/unit/test_avisos_nodos.py` + caso en `tests/integration/test_notificaciones_flujo.py`
· `mutaciones/avisos-nodos.toml`.

### 5.4 Pruebas (RED antes de GREEN)

1. ONLINE→OFFLINE produce **un** aviso; repetir la evaluación **no** produce otro (mismo ciclo y tras «reinicio»
   simulado, gracias a `avisados.json`).
2. OFFLINE→ONLINE produce **un** aviso de recuperación.
3. Nodo que nunca latió (UNKNOWN) y receptor caído: aviso distinto y único; **no** se confunde con OFFLINE.
4. Reloj de HC-1 que retrocede: no genera falsas caídas (reutiliza `max(0, edad)` de `estado_nodo`).
5. `registro.json` ausente o corrupto: sin excepción, sin aviso falso (`leer_registro` ya lo tolera).
6. **Cableado real** (lección ALERTA-005/§2 CLAUDE.md): prueba que la composición de verdad evalúa y entrega al
   centro, no solo la función pura.
Mutantes: quitar la comparación con el último notificado (avisos repetidos) · invertir la transición · no persistir
`avisados.json` · desconectar el punto de evaluación en la composición.

### 5.5 Riesgos

- **Latencia del aviso** = hasta la siguiente sesión de AURA. Un aviso **inmediato** (escritorio/móvil) requiere un
  canal nuevo o que el receptor notifique: **fuera de B**, decisión aparte (Bible 6.4, D23).
- Umbral: se reutiliza el de `estado_nodo` (`TOLERANCIA_INTERVALOS × intervalo`); sin histéresis extra, un nodo
  que parpadea generaría pares caída/recuperación → mitigable con un tiempo mínimo en OFFLINE (parámetro a fijar).
- Alcance: DP-NODO-01 v1 incluye «estado» y «supervisión por runit», **no** avisos al usuario → B es capacidad nueva
  y necesita acta (CLAUDE.md §2: nada sin DP aprobado).

### 5.6 Qué se pide

Acta del CEO que apruebe B con: (i) evaluación al arrancar sesión + por turno (o solo al arrancar); (ii) fichero
`avisados.json` para no repetir; (iii) tiempo mínimo en OFFLINE antes de avisar (propuesta: el propio umbral de
`estado_nodo`, sin extra). Con el acta, la ejecución es RED→GREEN→mutación→QG→ECC en una sesión.

### 5.7 Revisión arquitectónica independiente (`arquitecto-evaluador`, 2026-10-18) — **CABE CON CAMBIOS, solo con acta**

Citas verificadas `[EJEC]`: `CHECKLIST-CONTINUIDAD.md:82` («la fase de **integración NO está abierta** … decisión
**explícita** del CEO») y `DP-D-M-8 §2.1` («toda modificación de estado persistente se expresa como una Mutación»).

**Fricciones:** (1) **mayor** — cablear NODO-01 (hoy solo consultado en `__main__.py:476-488`) con el Centro
(`composicion.py:544`) es **integración entre capacidades**, fase no abierta; (2) DP-NODO-01 §1 no incluye avisos
(cabe en RF-9 / fuente `"aura"`, pero es capacidad nueva); (3) `avisados.json` es estado persistente del proceso
principal → tensión con D-M-8 §2.1 (precedente: `registro.json` del receptor fuera del motor) → exige **exención
escrita** o alternativa sin estado; (4) INV-9 — el texto no puede sugerir vigilancia continua: «al abrir AURA:
NODO-01 sin latido desde <hora>», nunca «acaba de caerse»; UNKNOWN por receptor caído = «no se sabe», no «sin
conexión». ADR-0014 cumple; ALERTA-002 no aplica (`contiene_terceros=False`).

**Cambios al plan:** Core sin E/S — la transición pura en `core/nodos.py`; la lectura de `registro.json` /
`avisados.json` en `adapters/receptor_nodos.py`. Punto único: solo-al-arrancar → `composicion.py`; por turno → puerto
inyectado en `core/orchestrator.py` (como `notificaciones`), nunca `leer_registro` dentro del orquestador.
`avisados.json`: atómico 0600 reutilizando el patrón `receptor_nodos.py:97-100` + mutante que lo saque de esa ruta.
Histéresis: usar el umbral existente y **documentar** el parpadeo como límite; no inventar valor numérico (regla CEO
2026-08-04). Alternativa sin almacén nuevo: avisar en cada sesión mientras no esté ONLINE (dedupe por huella en la
sesión), a costa de perder el aviso de recuperación.

**Decisiones del CEO (para el acta):** (1) B como **ampliación de DP-NODO-01 dentro de RF-9** o como **apertura
parcial de la fase de integración**; (2) evaluar solo al arrancar o también por turno; (3) `avisados.json` exento de
D-M-8 §2.1, o alternativa sin estado (sin aviso de recuperación); (4) aceptar que el aviso llega en la siguiente
sesión, no en tiempo real.
