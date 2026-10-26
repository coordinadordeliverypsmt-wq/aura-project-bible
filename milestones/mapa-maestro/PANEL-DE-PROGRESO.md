---
documento: "AURA Progress Dashboard — arquitectura, métricas y uso"
fecha: 2026-10-22
mantenido-por: "APUS-5 (CTO)"
codigo: "walking-skeleton/herramientas/panel_progreso.py · censura_panel.py · registro_gate.py"
salida: "publicado/panel-progreso/index.html (generada, desechable)"
---

# AURA Progress Dashboard

Vista única del avance del **proyecto** AURA, construida solo con fuentes reales. **No es una capacidad del producto**
(no lo importa AURA, no está en el runtime, no entra en `centro_gobierno.panel()` ni en `capacidades.json`; D23). Es una
herramienta de proceso, como `indice_madurez.py`.

## 1. Arquitectura

```
capacidades.json ─┐
mapa maestro ─────┤
MAPA-ECOSISTEMA ──┤                       ┌─ --json  (modelo, stdout)
DECISION-REQ-* ───┼─► construir_modelo() ─┤
CHECKPOINT ───────┤   (valida · censura)  └─ render_html() ─► publicado/panel-progreso/index.html (atómico)
registro del QG ──┘
        ▲
quality-gate.sh ──► registro_gate.py ──► ~/.local/state/aura/quality-gate-ultimo.json
```

- **Proyección desechable (ADR-0023).** El HTML no tiene estado propio; borrarlo y regenerarlo da lo mismo. Nunca
  escribe en las fuentes.
- **HTML estático, sin JavaScript ni servidor (ADR-0002).** Leer el panel no ejecuta ninguna acción.
- **El índice no se calcula aquí:** se importa `herramientas/indice_madurez.py` por ruta. Una sola fórmula.
- **Registro del Quality Gate.** `quality-gate.sh` llama a `registro_gate` al final con `|| true`: es una proyección del
  resultado; el código de salida del gate no cambia (verificado por la revisión de seguridad). Vive fuera del repo para no
  ensuciar el worktree ni el `pre-push` de `main`.

## 2. Fuentes y procedencia

| Sección | Fuente | Fecha mostrada (origen) |
|---|---|---|
| Resumen, Dimensiones, Capacidades | `milestones/mapa-maestro/capacidades.json` (+ escala del mapa maestro) | campo `actualizado` del JSON (`contenido`) |
| Calidad | `~/.local/state/aura/quality-gate-ultimo.json` + `walking-skeleton/mutaciones/*.toml` | fecha del registro |
| Ecosistema | primera tabla `## 7.` de `MAPA-ECOSISTEMA-FISICO.md` (censurada) | último commit (`git`) |
| Bloqueos y decisiones | `bloqueo` de cada capacidad + `milestones/*/DECISION-REQUERIDA-*.md` | último commit (`git`) |
| Procedencia | fecha del título de la última entrada del CHECKPOINT | `contenido` |

Cada bloque muestra `origen`, `fecha`, `fecha_origen` y su estado de antigüedad.

## 3. Definición de las métricas

- **Índice de madurez** = `indice_madurez.calcular(capacidades, ámbito)`. **Lanzamiento** = ámbito `MVP` (Bible 2.2);
  **horizonte** = todas. `Core = min(n,3)/3`, `Ready = max(n−3,0)/3`; media por dimensión y luego entre dimensiones (todas
  pesan igual). Se publica redondeado a 1 decimal, igual que la cifra oficial; un valor < 100 nunca se muestra como 100,0
  (tope 99,9).
- **Estado de cada capacidad** = el nombre oficial de su nivel en la escala 0–6 del mapa maestro (inexistente, concepto,
  prototipo, implementada, integrada, demostrada E2E, operativa), con el recuento por nivel. El panel **no** inventa una
  agrupación «completada/parcial/pendiente»: la escala ya lo expresa. **Bloqueada** = tiene `bloqueo` no vacío. Las
  etiquetas del tipo de bloqueo (decisión / técnico / externo) son **derivadas** por heurística y van marcadas como tales.
- **Calidad** = conteos de pytest y resultado de los 5 pasos del último gate registrado, su sha frente a `HEAD`
  (coincide / distinto / no comprobado) y los cambios sin commit cuando se ejecutó; número de garantías de mutación
  declaradas.
- **Ecosistema** = columnas Equipo / Estado / Bloqueo de la primera tabla `## 7.` del MAPA físico, tal cual (el grado
  descubierto/identificado/accesible/integrado/verificado es el que declare esa columna Estado; el panel no lo recalcula),
  con MAC, IP, serie, uuid y secretos censurados. Hoy el MAPA no tiene commit, así que se muestra «sin fecha».

### 3.bis Procedencia de la evidencia (derivada; `herramientas/procedencia_panel.py`)

`capacidades.json` no tiene un campo de procedencia: `evidencia` es texto libre. El único marcador estructurado es `[EJEC]`
(D47). El panel lo clasifica sin inventar, y marca la clasificación como derivada:

| Procedencia | Regla | Qué significa |
|---|---|---|
| ejecución real declarada | contiene `[EJEC]` | alguien la ejecutó en real y lo dejó escrito; **no implica verificación física** salvo que la evidencia lo diga |
| solo pruebas automatizadas | cita `tests/` o `mutaciones/` sin `[EJEC]` | pruebas con dobles o simulaciones; **nunca** se presenta como integración real |
| desconocida | cualquier otra cosa (código, actas, docs, notas) | no se infiere que sea real |
| sin evidencia | vacía | — |

Una capacidad de nivel ≥ 5 sin `[EJEC]` lleva el aviso «nivel alto sin ejecución real declarada». El aviso no cambia ni el
nivel ni el índice. Recuento real al 2026-10-22 (82): 28 ejecución real declarada · 14 solo pruebas · 35 desconocida ·
5 sin evidencia; 22 de nivel ≥ 5 con aviso.

Gate: si el sha del registro no es `HEAD`, el panel dice «PASS en otro commit (sha X); no corresponde al HEAD actual».
Si no puede comprobarlo, dice «no comprobado». Nunca lo presenta como vigente.

## 4. Estados del panel

| Estado | Cuándo | Qué se ve |
|---|---|---|
| Correcto | fuente válida y fechada dentro del umbral | cifra + fecha + origen |
| Desactualizado | fecha más antigua que el umbral (`--umbral-dias`, 7 por defecto; parámetro del panel, no propiedad del sistema) | aviso «desactualizado: fuente de AAAA-MM-DD» |
| Sin fecha | la fuente no trae fecha | «sin fecha para comparar» — nunca «al día» (no se usa el mtime) |
| Fecha futura | > 5 min por delante | aviso «fecha futura» |
| Vacío | ámbito sin capacidades / sin decisiones | «sin capacidades en este ámbito» / «sin decisiones registradas» — nunca 0,0 % |
| Error | fuente ausente, ilegible o con esquema inválido | bloque de error con el motivo; el resto del panel sigue |

No hay estado «cargando»: el HTML es estático y se genera completo o no se escribe (escritura atómica).

## 5. Privacidad

Todo texto que entra desde una fuente se censura **una vez, al construir el modelo** (`censura_panel.censurar`): MAC
(`:`, `-`, Cisco), uuid (con o sin `urn:uuid`), números de serie, IPv4 (solo queda `.N`), credenciales en URL, `Bearer`,
y el valor de `contraseña|password|pass|pwd|clave|psk|token|secret|api_key` hasta fin de línea o de celda. Todo se escapa
en HTML. No se muestran imágenes ni contenido de cámaras. La censura es conservadora: puede tapar prosa inocua («token de
sesión»), nunca al revés.

## 5.bis Consulta privada (sin exponer nada)

El panel es un fichero estático sin JavaScript. No hay ningún servidor del proyecto que lo sirva (verificado con
`ss -ltnp` el 2026-10-22).

1. **Por defecto, en el propio HC-1:** abrir `publicado/panel-progreso/index.html` en el navegador (`file://`). Sin red y
   sin puertos.
2. **Si hace falta HTTP en HC-1**, solo en loopback y mientras se consulta:
   `python3 -m http.server 8765 --bind 127.0.0.1 --directory publicado/panel-progreso`. Se cierra con Ctrl-C.
   Verificado el 2026-10-22: responde 200 solo en `127.0.0.1:8765`; tras cerrarlo el puerto queda libre.
3. **Desde otro dispositivo**, nada se activa sin autorización expresa del CEO:
   - (a) túnel SSH desde ese dispositivo (`ssh -L 8765:127.0.0.1:8765 hc-1`). Requiere sshd en HC-1 y la clave del
     dispositivo. Es la opción que menos expone.
   - (b) copiar el HTML (USB o carpeta sincronizada local). No requiere red.
   - (c) servir en la IP de la LAN. Expone el panel a toda la red; no se recomienda.
   - (d) página privada en claude.ai (Artifact). Queda alojada en Internet, aunque sea privada, y choca con «no exponer a
     Internet».

   Lo que **no** se hace sin acta: abrir puertos en el router ni cambiar el firewall.

## 6. Actualización

```bash
cd walking-skeleton
./quality-gate.sh                                   # deja el registro estructurado del gate
python3 -m herramientas.panel_progreso              # → publicado/panel-progreso/index.html
python3 -m herramientas.panel_progreso --json       # modelo por stdout, no escribe
python3 -m herramientas.panel_progreso --umbral-dias 3 --salida /ruta/panel.html
```

El panel **no** ejecuta la suite: lee el último registro del gate. Para refrescar la calidad hay que correr el gate.

## 7. Pruebas y verificación

- `tests/unit/test_panel_progreso.py` y `tests/unit/test_registro_gate.py` (125 pruebas al 2026-10-22, incluida la privacidad de extremo a extremo con secretos en TODAS las fuentes): cálculo y paridad con el
  índice oficial, agregación por dimensión y ámbito, datos ausentes/desactualizados/sin fecha/futuros, esquemas
  inválidos, registro del gate con y sin conteos, sha vs HEAD, censura con cadenas inventadas, escape HTML.
- Mutación: `walking-skeleton/mutaciones/panel-progreso.toml`, 60 mutantes, 60 detectados (incluye procedencia y vigencia del gate).

## 8. Limitaciones conocidas

- Los nombres de las dimensiones A–Q **no existen en el repositorio**: el panel muestra letras. Hay una correspondencia
  fundamentada pendiente de aprobación: `PROPUESTA-NOMBRES-DIMENSIONES.md`.
- Ecosistema y decisiones usan la fecha del último commit: en un worktree con cambios sin commit puede ser anterior a lo
  editado.
- El registro del gate es único por usuario (no por worktree); por eso se muestra su sha frente a `HEAD`.
- `decisiones/pendientes.md` no se lee: es prosa sin estructura estable. Las decisiones vienen de los ficheros
  `DECISION-REQUERIDA-*`.
