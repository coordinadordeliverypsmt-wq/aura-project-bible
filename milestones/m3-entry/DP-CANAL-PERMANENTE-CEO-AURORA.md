# Decision Package — Canal permanente CEO ↔ AURORA

**Estado:** propuesto · **Fecha:** 2026-08-04 · **Decide:** CEO · **Propone:** APUS-5 (asistencia externa)

---

## 1 · El problema, verificado

El CEO lo formuló así: *«si Claude Code deja de estar disponible, perdemos el canal de comunicación
con AURORA»*. La verificación por ejecución dice algo más incómodo:

> **AURORA nunca ha tenido proceso propio ni superficie propia.** No es que el canal se pierda si
> falta la asistencia externa: es que **el canal siempre ha sido la asistencia externa**.

Tres brechas medidas `[EJEC]`:

| # | Brecha | Evidencia |
|---|---|---|
| **B1** | **Nadie arranca el ciclo.** `MotorDelCiclo.servir()` es un `while True` funcional. Su único invocador en todo el repositorio es `tests/integration/test_motor_ciclo.py:122` | `motor_ciclo.py:72-83` · `composicion.py:363` lo ensambla y `__main__.py` no lo menciona |
| **B2** | **Nadie entrega el Centro de Gobierno.** Se autodescribe como «la interfaz oficial entre el CEO y AURORA»; su único importador es su propia prueba | `centro_gobierno.py:1` · `tests/integration/test_centro_gobierno.py:11` |
| **B3** | **Desatendida, AURORA se deniega a sí misma.** Sin terminal, `input()` lanza `EOFError` → deniega → tarea `bloqueada` definitiva, sin constancia de que esperaba una decisión | `hitl_consola.py:35-38` → `automatizacion.py:143` → `director.py:113-120` |

B3 tiene una consecuencia que decide la prioridad: **`proponer_cambio` es lista roja**
(`permissions.py:69`). Es decir, **AURORA no puede mejorarse a sí misma sin un humano delante, por
diseño**. La capacidad central de la etapa está bloqueada por la ausencia del canal.

Los mismos informes de IMA, tablero de dependencia y modelo de datos solo se invocan desde pruebas.
Y `EjecutorDiagnostico` produce un campo `informe` que el orquestador **nunca entrega**
(`adapters/diagnostico.py:57` vs `orchestrator.py:702-719`).

**Esto no es una capacidad nueva: es el cuello de botella que el CEO ya había identificado.**
`CHECKPOINT-CONTINUIDAD.md:30-34` — *«ambos componentes existen y funcionan pero **NADIE los usa en
producción. Ese es el cuello de botella real**»*.

---

## 2 · Qué se decide

Dotar a AURORA de **proceso propio, buzón de decisiones y superficie de gobierno persistente**,
usando el **sistema de ficheros como canal**, sin dependencias nuevas ni superficie de red.

---

## 3 · Por qué el canal es el sistema de ficheros

**Local-first no prohíbe un servidor local.** D37 lo precisa: *«lo prohibido es la **dependencia
funcional**, no la existencia de fuentes opcionales. Local-first no es local-only»*. El stack
aprobado ya corre Ollama en `127.0.0.1:11434`. Un HTTP en localhost sería **legal**.

Se descarta igualmente, y no por el principio sino por el coste:

| Alternativa | Por qué se rechaza |
|---|---|
| **Servidor HTTP local** | Dependencia nueva → D26 exige *beneficio medible* y no lo hay: no aporta nada que el fichero no dé. Añade superficie que ADR-0018 (*«in-process reduce la superficie, sin socket»*) y ADR-0002 (*«sin backend ni superficie de ataque nueva»*) valoran evitar. En un Celeron N4020 con 3,6 GB, un proceso servidor compite con el modelo |
| **Centro de Notificaciones persistente** | Es **retrospectivo por diseño**: detecta que algo se paró (`notificaciones.py:180-183`) y no ofrece vía de respuesta. Vive en memoria y muere con el proceso. Convertirlo en canal de decisión mezclaría dos responsabilidades |
| **Subir el nivel de autonomía por política** | ADR-0003 lo permite (*«solo por política y decisión del CEO»*), pero **elimina la garantía en vez de diferirla**. Es la respuesta contraria a la que el proyecto ha defendido ocho veces |

**A favor del fichero, y es un precedente propio, no una analogía:** el **kill switch ya es
exactamente esto** — un fichero en `~/.aura/` consultado con `os.path.exists` en cada comprobación
(`kill_switch.py:29-31`), que permite **armarlo desde otro proceso sin reiniciar nada**. Bible 5.3:77
lo llama *«mecanismo fuera de banda»*. El canal CEO→AURORA replica un patrón **ya aprobado y en
producción**: cero dependencias, cero puertos, sobrevive a reinicios y apagones.

---

## 4 · Diseño

Tres piezas. **Ninguna crea un componente nuevo donde exista uno extensible.**

### Pieza 1 — `--servir`: AURORA obtiene proceso propio

`__main__.py` gana un flag que arranca `sistema.motor_ciclo.servir()`.

- **Cumple D40** (`acta:420`): *«`python -m aura_skeleton` es la única forma oficial de iniciar AURA»*.
  No se crea ejecutable nuevo; se amplía el único entrypoint declarado en
  `architecture_manifest.toml:24-28`. No hay que tocar el manifiesto.
- **Cumple D40 punto 3**: la composición sigue ensamblando, no decide.
- **Defecto a corregir en la misma pieza:** `correr` y `servir` **no capturan excepciones** de
  `director.ciclo` (`motor_ciclo.py:61-70`, `:78-83`). Hoy da igual porque nadie los invoca; con
  proceso propio, una excepción mata el latido **en silencio**. Un demonio que muere sin dejar rastro
  es peor que no tenerlo.

### Pieza 2 — Buzón de decisiones: aprobación diferida gobernada

Confirmador nuevo `adapters/hitl_diferido.py`, **misma firma** que el de consola. Está previsto por
el propio código: `hitl_consola.py:7-9` — *«Otras interfaces (voz, móvil, web) serán otros módulos con
la misma firma; ninguna debería vivir en la composición»*.

En vez de denegar por ausencia de humano:

1. **Anexa una solicitud al historial** con acción, args, **la previsualización del dry-run** y una
   **huella SHA-256 de (acción + args + previsualización)**.
2. **Devuelve `False`** — el motor devuelve `detenida`, la tarea queda `bloqueada`. *El comportamiento
   seguro de hoy no cambia.*
3. La solicitud se registra en **`Tarea.decisiones_pendientes`** — campo que **ya existe**
   (`estado_operativo.py:76`) y que **nadie escribe ni lee**. El almacén no hay que inventarlo: hay
   que encenderlo.

El CEO responde escribiendo un fichero en `~/.aura/decisiones/`. En el siguiente latido AURORA:

4. **Re-ejecuta el dry-run** y **recalcula la huella**. Si coincide, reabre la tarea
   (`bloqueada → abierta`, transición ya permitida) con autoridad `ceo`. **Si no coincide, la
   aprobación caduca** y se anexa el motivo.

**Por qué esto es más fuerte que el HITL actual, no más débil:**

| ADR-0003 exige | Cómo se cumple |
|---|---|
| Confirmación humana **siempre** | Nadie aprueba salvo el CEO. La omisión sigue siendo denegación: sin respuesta, la tarea sigue bloqueada indefinidamente |
| **Con la previsualización delante** — *«confirmar a ciegas no satisface el consentimiento informado»* | La previsualización viaja **dentro** de la solicitud. El CEO decide leyéndola |
| Tolerancia cero a falsos negativos | Intacta: el camino por defecto sigue siendo denegar |
| dry-run **antes** de confirmar | Se ejecuta antes de emitir la solicitud **y otra vez antes de ejecutar** |

Hoy confirmas y se ejecuta lo que el adaptador haga. Aquí **se verifica que el efecto previsto no
cambió entre la aprobación y la ejecución**. Es una garantía que el HITL síncrono no da.

**No existe decisión previa sobre aprobación diferida** — ni a favor ni en contra. Verificado en
`adr/`, `docs/`, `decisiones/`, `milestones/`, `revisiones/`. Es terreno que el CEO debe fijar.

### Pieza 3 — Centro de Gobierno como proyección en disco

En cada latido con cambios, AURORA escribe `~/.aura/CENTRO-DE-GOBIERNO.md` con
`render(panel(...))` — funciones que **ya existen y ya devuelven texto** (`centro_gobierno.py:136`).

- **Cumple ADR-0023 por su propio criterio** (`:74-88`): *«debe poder eliminarse por completo y
  regenerarse desde el historial sin alterar el comportamiento»*. Bórralo y el siguiente latido lo
  reconstruye. Es una proyección desechable, no una segunda fuente de verdad.
- Se añade una sección **«decisiones que te esperan»** con la previsualización y la instrucción exacta
  para aprobar. Respeta el principio de trazabilidad de origen: su contenido lo produce AURORA.
- El CEO lo abre con cualquier editor, sin sesión de asistencia externa, en cualquier momento.

**Claude Code pasa a mentor bajo petición:** el Centro declara qué necesita formulación —las
capacidades 🔴 del Plan de Formación—. El CEO convoca cuando quiere, ya sabiendo para qué.

---

## 5 · Ataque a la propuesta

| Ataque | Respuesta |
|---|---|
| **Un fichero de aprobación es falsificable**: cualquier proceso con tu cuenta puede escribir `SI` | Cierto, y **se declara como límite**. Pero el kill switch —la defensa última, ya aprobada— es exactamente igual de falsificable. En un modelo local-first monousuario, quien controla la cuenta ya puede escribir `SI` en el REPL. **No empeora la postura; la iguala** |
| **Disco al 99 %**: 892 MB libres (`ESTADO-ENTORNO-VERIFICADO.md`). Un demonio escribiendo cada 30 s puede llenarlo | **Riesgo real, no teórico.** Mitigación exigible: el latido **no escribe si no hay cambio**, y existe rotación en `observability.py:129`. **Debe medirse el crecimiento en 24 h antes de dejarlo permanente** |
| **La huella cubre la previsualización, no el mundo**: el fichero a borrar puede cambiar de contenido sin cambiar de ruta | Por eso el dry-run se **re-ejecuta** al reabrir en vez de confiar en la huella almacenada. Cierra el hueco para todo efecto que el dry-run sepa ver; **lo que el dry-run no modela, sigue sin modelarse** — y eso es deuda previa, no introducida aquí |
| **Un demonio en un Celeron de 2 núcleos** | `servir()` duerme 30 s entre sondeos sin trabajo (`motor_ciclo.py:24`). El coste en reposo es despreciable frente al modelo, que es lo que satura la máquina |
| **¿No es esto ampliar el alcance del MVP (D23)?** | No añade funcionalidad de producto: **conecta componentes ya construidos y ya aprobados**. Y responde al encargo estratégico del CEO de 2026-08-03, que reorientó el objetivo a que AURORA se administre a sí misma. Aun así, **la decisión es del CEO**: D22 le reserva toda modificación de rango 1 |

---

## 6 · Riesgo colateral encontrado, ajeno a este DP

`revisiones/2026-08-02:157-162`: **el artefacto que sostiene la memoria N2 (470 MB) son enlaces
simbólicos al directorio temporal de un job de Claude Code.** Si se borra el job, la composición
**degrada a N1 en silencio**.

Es exactamente la dependencia que este DP quiere eliminar, y hoy está activa. *«Mitigación de un
minuto, pendiente de autorización»*. **Se recomienda autorizarla con independencia de este DP.**

---

## 7 · Retorno sobre Tokens

- **Hoy cada verificación de estado consume una sesión de asistencia externa.** Con el Centro de
  Gobierno en disco, el CEO lee el estado con **cero tokens**.
- **Hoy AURORA solo trabaja cuando yo lanzo su proceso.** Con `--servir`, trabaja sin que nadie gaste
  contexto.
- **Hoy `proponer_cambio` es inalcanzable sin humano presente.** Con el buzón, la vía de autoevolución
  queda abierta sin renunciar a ninguna garantía.
- **IMA:** convierte en medible la dimensión de operación autónoma, hoy no instrumentada.

---

## 8 · Qué se pide aprobar

1. **Pieza 1** — `--servir` en el entrypoint existente + captura de excepciones en el latido.
2. **Pieza 2** — buzón de decisiones con aprobación diferida verificada por re-ejecución del dry-run.
   **Requiere decisión expresa del CEO: no hay precedente ni a favor ni en contra.**
3. **Pieza 3** — Centro de Gobierno como proyección en `~/.aura/CENTRO-DE-GOBIERNO.md`.
4. **Medición obligatoria** del crecimiento en disco durante 24 h antes de declarar el demonio
   permanente.

**Orden sugerido:** 3 → 1 → 2. La Pieza 3 entrega valor sin cambiar comportamiento alguno; la 2 es la
que introduce una garantía nueva y debe llegar con el terreno ya asentado.

**No se implementa nada hasta que el CEO apruebe.**
