# Decision Package — Communication Plane de AURORA

**Estado:** PROPUESTO · **Fecha:** 2026-08-17 · **Decide:** CEO · **Propone:** APUS-5 (asistencia externa)
**Origen:** prioridad arquitectónica del CEO, 2026-08-17 — *«Communication Plane antes de Agent
Orchestrator»*, para eliminar la dependencia de la presencia del CEO como mensajero.
**Clasificación D47:** `[EJEC]` medido ejecutando · `[LECT]` leído · `[INFER]` deducido · `[HIPO]` no verificado.

> **NADA ESTÁ IMPLEMENTADO.** Entregado: este diseño y **35 pruebas RED que fallan a propósito**
> (`entorno/communication-plane/test_red_communication_plane.py`). No hay `communication_plane.py`.
> **GREEN no está autorizado**: el DP vigente (`DP-DEVELOPMENT-ORCHESTRATOR`) sigue en estado
> **PROPUESTO**, y la orden del CEO fue *«GREEN solo si la implementación está explícitamente
> autorizada por el DP vigente; si no, detenerse después del diseño»*. Me detengo aquí.

---

## 0 · El hallazgo que cambia la premisa — léase antes que nada

El encargo pide *«comunicación persistente GPT ↔ Claude Code»* sin que el CEO copie respuestas a mano.
Investigado contra documentación oficial, el resultado es incómodo y hay que decirlo sin rodeos:

> **ChatGPT —el producto de chat, web o app— NO puede participar en un canal de ficheros local.**
> Sin clave de API y sin un endpoint HTTPS público, **no lee ni escribe un solo byte del disco local**.

Verificado punto por punto:

| Vía | ¿Lee disco local? | ¿Escribe? | ¿Sin humano? | Bloqueo |
|---|---|---|---|---|
| Conector **GitHub** de ChatGPT | no (lee repos) | **NO escribe** — ni commits, ni PR, ni issues | no | — |
| **MCP** en ChatGPT | solo servidores **remotos HTTPS**; **no soporta stdio local** | — | no | exige exponer a Internet |
| **Custom GPT + Action** | vía endpoint propio | sí | **no** — requiere turno humano; excluido de tareas programadas | exige TLS 443 con certificado público |
| **Tareas programadas** | — | — | sí, pero **~1/hora y sin Custom GPTs** | no toca disco local |
| **App de escritorio ChatGPT para Linux** (preview, ago-2026) | **sí** | sí | **NO** — es una GUI conducida por una persona | no es headless |

**Conclusión:** un diseño que asumiera «ChatGPT lee el canal» estaría **fingiendo una capacidad no
construida** — INV-9 exactamente.

### Pero el objetivo SÍ es alcanzable, por otra vía

**Codex CLI** `[LECT, documentación oficial]`:

- Corre **local en Linux**; inspecciona ficheros, los edita y ejecuta herramientas de la máquina.
- **Se autentica con la suscripción ChatGPT, SIN clave de API** (`codex login`; `--device-auth` para
  máquinas sin navegador).
- **Modo no interactivo real**: `codex exec` con `--json` (eventos JSONL), `--output-schema` (respuesta
  conforme a JSON Schema) y `-o <ruta>` (escribe el resultado a fichero).
- Sandbox por defecto **solo lectura**; escritura con `--sandbox workspace-write`.
- **Sin Internet entrante, sin endpoint público, sin clave.**

Es el **análogo exacto de Claude Code al otro extremo del canal**. Y es la única vía que satisface a la
vez local-first, D24 y «sin claves de terceros».

**Tensión con la orden del CEO, declarada y no resuelta:** el encargo dice *«no integrar Codex
todavía»*. **No se integra.** Pero es un hecho verificado que **Codex CLI es hoy el único transporte
que cumple el objetivo sin abrir la decisión de claves de terceros**. Eso convierte «¿integrar Codex?»
en la decisión que gobierna todo el valor del canal → **§17.1**.

**Riesgo de términos de servicio, declarado por honestidad `[INCIERTO]`:** la documentación de Codex
recomienda **clave de API** o `CODEX_ACCESS_TOKEN` para *«workflows programáticos: scripts, CI/CD,
cuentas de servicio»*. No se encontró prohibición explícita de usar la autenticación de suscripción en
un bucle local propio, **pero tampoco permiso explícito**. Debe verificarse antes de comprometer el
diseño. No lo doy por bueno.

---

## 1 · El problema

**Hoy el canal entre el ejecutor y el revisor es una persona.** El CEO lee una respuesta, la copia a
otra ventana, copia la contestación de vuelta. Si cierra el portátil, el hilo se detiene.

Y el sustrato para arreglarlo **no existe**: el Control Plane no tiene lock ni historial de mensajes
—defectos P2/P3/P4, demostrados por ejecución en el DP del Orchestrator—. Sin un canal transaccional,
cualquier intento de coordinación automática produce estado corrupto en silencio.

**Por eso el Communication Plane va ANTES que el Orchestrator, y el CEO tiene razón en el orden:** el
orquestador es un segundo escritor, y hoy no hay dónde escribir con seguridad.

---

## 2 · Qué se decide

Construir —cuando se autorice— un **canal de mensajes transaccional, local-first y verificable** entre
agentes de desarrollo, con historial append-only encadenado por hashes, locks reales, idempotencia y
handoff derivado del propio log.

**El canal transporta. No autoriza.** Es la línea que no se cruza.

---

## 3 · Arquitectura

```
   ┌────────────────────────────────────────────────────────────┐
   │  CONTROL PLANE — autoridad operacional (estado, política)   │
   │  Un mensaje NUNCA concede lo que aquí no está concedido     │
   └───────────────────────────┬────────────────────────────────┘
                               │ consulta (nunca al revés)
   ┌───────────────────────────▼────────────────────────────────┐
   │  COMMUNICATION PLANE                                        │
   │                                                             │
   │   canal.jsonl      log append-only, seq + cadena de hashes  │
   │   procesados.jsonl acuses por agente (idempotencia)         │
   │   canal.lock       flock — exclusión real entre procesos    │
   │   adjuntos/        cuerpos > 4 KB, por referencia           │
   └───┬────────────────────────┬───────────────────┬───────────┘
       │ TransporteAdapter      │                   │
   ┌───▼────────┐      ┌────────▼────────┐   ┌──────▼──────────┐
   │ Claude Code│      │  Codex CLI      │   │ worker local    │
   │ (verificado│      │  (NO integrado, │   │ AURORA          │
   │  2.1.233)  │      │   §17.1)        │   │ (futuro)        │
   └────────────┘      └─────────────────┘   └─────────────────┘
```

**Tres invariantes de la arquitectura:**

1. **El canal es un tubo, no un juez.** No interpreta la autoridad de un mensaje; la consulta al
   Control Plane.
2. **El log es la fuente de verdad; todo lo demás es proyección** reconstruible (ADR-0023).
3. **Los participantes son identificadores, no tipos cableados.** Añadir un agente no cambia el canal.

---

## 4 · Protocolo de mensajes

### 4.1 · Los ocho tipos, y ni uno más

| Tipo | Quién lo emite | Significado | Efecto en el canal |
|---|---|---|---|
| `TASK` | quien encarga | trabajo a ejecutar | crea pendiente |
| `ACK` | quien recibe | «lo he recibido y lo tomo» | marca en curso |
| `RESULT` | ejecutor | terminado, con evidencia | cierra el hilo si el criterio se cumple |
| `BLOCKED` | ejecutor | no puede seguir por una dependencia | pendiente, no fallo |
| `DECISION_REQUIRED` | cualquiera | hace falta autoridad humana | **BLOQUEA hasta aprobación válida** |
| `WAITING_FOR_ENVIRONMENT` | ejecutor | recurso insuficiente (RAM, disco) | pendiente reintentable |
| `WAITING_FOR_QUOTA` | ejecutor | límite observado **con evidencia** | pendiente reintentable |
| `FAILED` | ejecutor | falló, con causa | cerrado sin éxito, reejecutable |

**Un tipo desconocido se rechaza al escribir**, no al leer: la validación va en la entrada, porque un
mensaje inválido ya escrito contamina el historial permanente.

### 4.2 · Esquema del mensaje

```json
{
  "seq": 42,
  "id": "uuid5 determinista sobre (tipo, de, para, cuerpo, in_reply_to)",
  "tipo": "TASK",
  "de": "gpt", "para": "claude-code",
  "in_reply_to": "uuid del mensaje al que responde, o null",
  "instante": "2026-08-17T16:04:11",
  "cuerpo": { "...": "payload del tipo; > 4 KB va por referencia a adjuntos/" },
  "hash_anterior": "sha256 del mensaje seq-1",
  "hash": "sha256 de este mensaje + hash_anterior"
}
```

**Campos que NO existen, deliberadamente:** `autoriza`, `aprueba`, `permiso`, `permite`,
`autorizacion`, `override`. **La garantía no es que nadie los use: es que no están en el esquema.**

### 4.3 · Identificador e `in_reply_to`

- **`id` determinista** (`uuid5` sobre el contenido): el mismo mensaje publicado dos veces produce el
  mismo `id` → la duplicación es **detectable**, no una cuestión de disciplina.
- **`in_reply_to` debe apuntar a un mensaje existente**; si no, se rechaza. Una referencia rota
  impide reconstruir el hilo, y un hilo irreconstruible no es auditable.

---

## 5 · Almacenamiento

| Fichero | Qué | Por qué así |
|---|---|---|
| `canal.jsonl` | log append-only, una línea por mensaje | ADR-0023: historial → proyección |
| `procesados.jsonl` | acuses `(mensaje, agente)` | sobrevive al reinicio; sin esto se reejecuta todo |
| `canal.lock` | fichero de bloqueo `flock` | exclusión real entre procesos |
| `adjuntos/<sha256>` | cuerpos grandes | ver §5.1 |

**Nada se sobrescribe jamás.** Retractar un mensaje es **anexar una lápida**, nunca borrar la línea.

### 5.1 · El límite de 4 KB, medido `[EJEC]`

Medición propia en esta máquina: **4 procesos escribiendo 800 líneas concurrentes → 0 corruptas**. El
`append` es atómico para líneas de ~130 bytes. Y `PC_PIPE_BUF` sobre el sistema de ficheros = **4096**.

**Consecuencia de diseño, honesta:** el log tolera varios escritores sin partir líneas **siempre que
cada mensaje quepa bajo 4 KB**. Por encima de ese umbral la atomicidad **no está garantizada**, así que
**todo cuerpo > 4 KB viaja por referencia** a `adjuntos/<sha256>`, y en el log queda solo el puntero.

**Esto NO significa que el lock sobre.** Ver §6.

---

## 6 · Locking

**El lock no existe para evitar líneas partidas** —eso ya lo da el `append`—. **Existe porque el `seq`
monotónico y la cadena de hashes requieren leer el estado anterior antes de escribir**, y esa secuencia
leer-calcular-escribir no es atómica.

**Se elige `flock`, y por una razón medida `[EJEC]`:**

```
ANTES DE MATAR: bloqueado correctamente (el hijo lo tiene)
TRAS SIGKILL:   lock LIBERADO -> flock es seguro ante muerte subita
```

Un **fichero centinela** —el patrón del kill switch— sería aquí un **defecto grave**: sobrevive a la
muerte del proceso y **congelaría el canal para siempre**. En el kill switch esa persistencia es la
virtud; aquí sería el fallo. **La misma técnica, invertida de valor según el propósito.**

---

## 7 · Idempotencia y detección de ya procesados

Cuatro capas:

1. **`id` determinista** — publicar dos veces el mismo mensaje devuelve el mismo `id` y **no duplica**.
2. **`procesados.jsonl`** — un mensaje acusado no vuelve a entregarse, **ni tras reiniciar**.
3. **Acuse idempotente** — marcar procesado dos veces es inocuo.
4. **`seq` + lectura incremental** — un agente que se reincorpora lee **solo lo nuevo** (`leer_desde`),
   no todo el historial.

Sin la capa 2, cada arranque reejecuta el pasado entero. Es el modo de fallo más caro de un canal.

---

## 8 · Recuperación tras caída

| Fallo | Detección | Respuesta |
|---|---|---|
| Corte a mitad de escritura | última línea no parsea | **se descarta, se registra el descarte** y el canal abre |
| Manipulación del log | la cadena de hashes no cuadra | `integro: false` + **número de la primera línea corrupta** |
| Proceso muerto con el lock | `flock` lo libera solo `[EJEC]` | el canal sigue disponible |
| Agente caído a mitad de tarea | `TASK` con `ACK` y sin `RESULT` | queda **pendiente**, nunca completada |
| Proyección perdida | — | se **reconstruye** del log |

**Invariante:** *el canal se abre siempre, o dice exactamente por qué no.* Un canal que se niega a
abrir sin explicar bloquea todo el trabajo; uno que abre fingiendo integridad es peor.

---

## 9 · Auditoría append-only y verificabilidad

El CEO pidió *«transaccional y verificable, no un simple archivo de texto»*. Lo que lo hace verificable:

1. **`seq` monotónico** — detecta huecos.
2. **Cadena de hashes** — cada mensaje incluye el hash del anterior. **Alterar un mensaje pasado rompe
   la cadena y el canal lo denuncia** señalando la línea. Es lo que separa esto de un fichero de texto.
3. **`fsync` por línea** — lo confirmado sobrevive a un corte.
4. **Append-only con lápidas** — el pasado no se reescribe.

**Límite declarado, sin adornos:** la cadena detecta **manipulación torpe o corrupción**, no a un
adversario con acceso de escritura al fichero, que puede recalcular toda la cadena. En un entorno
local-first monousuario, **quien controla la cuenta ya puede hacerlo** — igual que puede armar el kill
switch. **No empeora la postura; la iguala.** No se vende como criptografía.

---

## 10 · Límites de autoridad — la sección que no se negocia

> **«No permitir que un mensaje del canal otorgue autoridad que el Control Plane no posea»** (CEO).

Cómo se cumple, estructuralmente:

| Garantía | Mecanismo |
|---|---|
| Un mensaje no concede permisos | **Los campos de concesión no existen en el esquema** (§4.2). Publicar uno lanza `MensajeInvalido` |
| `DECISION_REQUIRED` bloquea | `bloqueado_por(id)` sigue `True` hasta una aprobación válida |
| Un `ACK` de otro agente **no** desbloquea una decisión humana | probado explícitamente en RED |
| Una aprobación sin prueba de autoridad se rechaza | `AutoridadInsuficiente`. *El silencio no aprueba* (`1.1:85`); una afirmación tampoco |
| Ningún agente aprueba su propia decisión | rechazado por identidad emisor≠aprobador |
| Ningún modelo aprueba nada | `1.1:93` — *«su autoridad de aprobación no es delegable a ningún agente»* |

**El canal pregunta al Control Plane; el Control Plane nunca pregunta al canal.** La dirección de la
dependencia es la garantía.

---

## 11 · Seguridad

| Amenaza | Control |
|---|---|
| Un mensaje intenta elevar permisos | esquema sin campos de concesión; validación en escritura |
| Un agente se hace pasar por otro | **límite declarado:** no hay firma criptográfica. En entorno monousuario local, `de` es *declarativo*. Si se quisiera fuerte, exige firmas y esa es otra decisión |
| Inyección por el cuerpo del mensaje | el cuerpo es **datos**, nunca instrucciones para el canal; quien lo consuma debe tratarlo como entrada no confiable |
| Fuga de contenido a un tercero | no aplica sin transporte externo. Con él exige **minimización**, que **no existe** en el repo `[EJEC]` |
| Secretos | **el canal no requiere ninguna credencial** — son ficheros locales. Ninguna clave inventada |
| Escritura fuera del canal | el canal solo escribe bajo su propio directorio |

---

## 12 · Cuota

**`usage_known = false` se mantiene.** El canal **no estima cuota** y una prueba lo protege.

- `WAITING_FOR_QUOTA` **exige evidencia observada**: mensaje literal, tarea, ventana
  ∈ `{SHORT_4H30, WEEKLY, UNKNOWN}`. Sin evidencia, **no se emite**.
- **Una ventana no arrastra a la otra.**
- Lo observable **por invocación** (coste, tokens) es **presupuesto operacional**, no conocimiento de
  cuota. Son cosas distintas y el canal no las confunde.

---

## 13 · Interacción GPT ↔ Claude, hoy

**Lo que funciona hoy sin ninguna decisión pendiente:**

| Modo | Cómo | ¿Sin humano? |
|---|---|---|
| **Claude Code ↔ Claude Code** (subagentes) | ambos extremos leen y escriben el canal | **sí** |
| **CEO ↔ agentes** | el CEO lee el handoff y responde por el canal | por definición, no |
| **GPT vía humano-transporte** | el CEO pega un bloque del canal y devuelve la respuesta | **no**, pero el humano deja de *interpretar*: solo transporta un bloque ya formado |

**Lo que NO funciona hoy y no se finge:** ChatGPT como participante autónomo. **Requiere `D-CP-1`.**

**Mejora real aunque nunca se apruebe nada más:** hoy el CEO lee, interpreta, resume y reescribe. Con
el canal, **copia un bloque estructurado y pega la respuesta**. El trabajo cognitivo de mensajería
desaparece aunque el transporte siga siendo manual. **Eso ya es valor entregado.**

---

## 14 · Futuro: Codex

**No se integra ahora** (orden del CEO). Lo que este diseño hace es **no cerrarle la puerta**:

- `TransporteAdapter` con `entregar()`; Codex sería **una implementación más**.
- Los participantes son identificadores: `codex` no requiere cambios en el canal.
- `codex exec --json --output-schema` produce salida estructurada **parseable**, igual que
  `claude -p --output-format json --json-schema`. **Los dos extremos hablan el mismo idioma.**

**Y se declara lo que hoy es cierto:** `transportes_disponibles()` devuelve
`{"ficheros_locales": true, "modelo_externo_via_api": false}`. **Declarar disponible un transporte que
exige una decisión no tomada sería fingir capacidad — INV-9.**

---

## 15 · Futuro: Orchestrator

Este canal es **prerequisito**, y encaja así:

| Necesidad del Orchestrator | Se la da el canal |
|---|---|
| Entregar tareas y recibir resultados | `TASK` / `RESULT` |
| No perder estado con dos escritores | lock `flock` |
| No repetir trabajo | idempotencia + procesados |
| Reconstruir qué pasó | log encadenado |
| Parar ante decisiones humanas | `DECISION_REQUIRED` bloqueante |
| Handoff sin redactarlo a mano | derivado del log |

**Lo que el canal NO le da, y debe seguir en el Orchestrator:** la política de autoridad, el criterio
mecánico de finalización (§14.bis del DP del Orchestrator) y el presupuesto por tarea. **El canal no
decide qué se ejecuta ni cuándo se considera hecho.**

---

## 16 · GitHub como espejo

| | GitHub | Local |
|---|---|---|
| Fuente operacional | **nunca** | **canal.jsonl** |
| Espejo, backup, handoff entre máquinas | sí | — |
| Si no está disponible | **no pasa nada**: se anota y se sigue | — |

Probado en RED: `sincronizar(simular_fallo_de_red=True)` → `sincronizado: false`,
**`canal_operativo: true`**. Es D37 aplicado: *lo prohibido es la dependencia funcional*.

---

## 17 · Decisiones que requieren al CEO — `DECISION_REQUIRED`

### 17.1 · `D-CP-1` — El transporte hacia el segundo agente

**El hecho, verificado:** ChatGPT-el-chat no puede participar. Las opciones reales son tres:

| Opción | Clave de terceros | Local-first | Autónomo | Choca con |
|---|---|---|---|---|
| **A · Codex CLI local** (login de suscripción) | **NO** | **sí** | **sí** | *«no integrar Codex todavía»* + ToS `[INCIERTO]` |
| **B · API de OpenAI** | **SÍ** | no | sí | **D24 + `CHECKLIST:237`** → es `D-ORCH-1` |
| **C · Humano-transporte** | no | sí | **no** | no cumple el objetivo del encargo |

**Hoy rige C por defecto.** A es el único que cumple el objetivo sin abrir la decisión de claves, y
está bloqueado por una orden del propio encargo. **Es una decisión estratégica, y no la tomo.**

### 17.2 · `D-CP-2` — ¿Se autoriza GREEN del canal?

El diseño está completo y las pruebas RED escritas. **La implementación no está autorizada** porque el
DP del Orchestrator sigue en `PROPUESTO`. **¿Se autoriza construir el Communication Plane como
incremento propio**, con su ciclo RED→GREEN→mutación→Quality Gate→auditoría?

Nota: sigue vigente `CHECKLIST:235` — *no iniciar incrementos nuevos sin decisión posterior a la
revisión estratégica*. **Hace falta levantarlo explícitamente** (es `D-ORCH-5`).

### 17.3 · `D-CP-3` — Identidad de los participantes

El campo `de` es **declarativo**: no hay firma. En un entorno local monousuario es coherente con la
postura del kill switch, pero **si algún día el canal cruzara máquinas, sería insuficiente**. ¿Se
acepta el modelo declarativo, o se exige firma desde el principio?

---

## 18 · Ataque a la propuesta

| Ataque | Respuesta honesta |
|---|---|
| **«Esto es una cola de mensajes reinventada; usa Redis/SQLite»** | Ataque serio. **SQLite sería técnicamente superior** para transacciones. Se elige ficheros porque: el proyecto ya decidió el fichero como canal en `DP-CANAL-PERMANENTE` con razones propias; D26 exige beneficio medible para toda dependencia nueva; y el log JSONL es **legible por un humano sin herramientas**, cosa que importa cuando el auditor es el CEO. **Si el CEO prefiere SQLite, el diseño se adapta sin cambiar el protocolo** — y eso es señal de que el protocolo está bien separado del almacén |
| **«La cadena de hashes no protege de nadie con acceso de escritura»** | **Cierto, y se declara en §9.** Detecta corrupción y manipulación torpe. No se vende como más de lo que es |
| **«El objetivo declarado (GPT↔Claude sin humano) no se cumple»** | **Cierto hoy, y es el hallazgo de §0.** No se disimula: se eleva como `D-CP-1`. El canal entrega valor igualmente (§13), pero el objetivo completo depende de una decisión del CEO |
| **«Construir un canal para un solo desarrollador es sobre-ingeniería»** | Mismo ataque que R7 del DP anterior, y sigue siendo parcialmente válido. Mitigación: el canal cierra defectos **medidos** (P2/P3/P4) que existen con o sin GPT al otro lado |
| **«35 pruebas rojas en el árbol confunden al siguiente agente»** | Riesgo real. Mitigado: nombre `test_red_…`, docstring de cabecera explícito, fuera del Quality Gate `[EJEC]`, y declarado en el checkpoint y en `estado.json` |
| **«Un canal facilita que dos IA se auto-certifiquen»** | El canal **no puede** conceder autoridad (§10) — pero el ataque acierta en algo: **el riesgo no está en el canal, está en la política del Orchestrator**. Por eso §14.bis del DP anterior exige criterio mecánico. **El canal no lo resuelve y no pretende hacerlo** |

---

## 19 · Riesgos

| # | Riesgo | Gravedad | Mitigación |
|---|---|---|---|
| **R1** | Se construye el canal y el transporte nunca se autoriza → tubo sin consumidor | **Alta** | §13: entrega valor con humano-transporte. Aun así, **el CEO debería resolver `D-CP-1` ANTES de autorizar GREEN** |
| **R2** | Mensajes > 4 KB parten líneas | Media | Umbral medido `[EJEC]`; cuerpos grandes por referencia |
| **R3** | El log crece sin límite | Media | Rotación sellada, patrón ya probado en `observability.py` |
| **R4** | Suplantación de `de` | Media | Declarada en §11 y elevada como `D-CP-3` |
| **R5** | Usar auth de suscripción en bucle automático incumple ToS | **Alta** `[INCIERTO]` | **Verificar antes de implementar el adaptador Codex.** No asumido |
| **R6** | Las pruebas RED se toman por defectos | Baja | Nombre, docstring, ubicación y registro en el estado |
| **R7** | El canal se usa para saltarse el Control Plane | **Alta** | §10: estructural, no confianza |

---

## 20 · Criterios de aceptación

**Comportamiento demostrado, no «las pruebas pasan».**

| # | Criterio | Demostración |
|---|---|---|
| **A1** | Dos procesos concurrentes publican y **no se pierde ningún mensaje** | 2 procesos reales × 5 mensajes → 10 en el log |
| **A2** | El canal se reconstruye entero tras borrar toda proyección | borrar, reproyectar, comparar |
| **A3** | Una línea truncada no impide abrir, y **el descarte se declara** | truncar a mano y abrir |
| **A4** | Manipular un mensaje pasado **se detecta** | editar una línea → `integro: false` + línea señalada |
| **A5** | Un mensaje repetido no duplica trabajo | publicar dos veces → un pendiente |
| **A6** | Un mensaje procesado no se reentrega **tras reiniciar** | marcar, reabrir, comprobar |
| **A7** | `DECISION_REQUIRED` **no se desbloquea** sin aprobación válida | intentarlo con `ACK` y con aprobación sin prueba |
| **A8** | Ningún agente aprueba su propia decisión | intentarlo |
| **A9** | El canal opera **al 100 % sin red** | desconectar |
| **A10** | El fallo de GitHub no detiene el canal | simular fallo |
| **A11** | El canal **no pide ninguna credencial** | `requiere_credenciales() is False` |
| **A12** | El lock se libera si el proceso muere | `SIGKILL` — **ya medido `[EJEC]`** |
| **A13** | `transportes_disponibles()` declara `false` lo no autorizado | INV-9 |

---

## 21 · Qué queda FUERA de alcance

1. **El Orchestrator completo** — es el DP anterior.
2. **Autonomía de AURORA** — **0/7 sin cambios**. Esto es infraestructura de desarrollo.
3. **Integración de Codex** — diseñada como adaptador, **no construida** (orden del CEO).
4. **Cualquier llamada a API de terceros** — bloqueada por `D-ORCH-1`.
5. **Firma criptográfica de participantes** — `D-CP-3`.
6. **Política de autoridad** — vive en el Control Plane, no aquí.
7. **Criterio mecánico de finalización** — es del Orchestrator.
8. **Modificar `n=3`, el benchmark, Bible, ADR o políticas** — intactos `[EJEC]`.
9. **Daemon o watcher permanente** — el canal se consulta, no reside.
10. **GREEN** — no autorizado.

---

## 22 · Retorno sobre Tokens

- **Hoy cada relevo consume una intervención humana y contexto nuevo.** El handoff derivado del log se
  lee con `grep`: **cero tokens**.
- **Hoy el CEO interpreta y reescribe mensajes.** Con el canal, transporta un bloque ya formado: el
  trabajo cognitivo de mensajería desaparece **aunque el transporte siga siendo manual**.
- **Hoy una tarea repetida por error se paga entera.** La idempotencia la hace detectable.
- **Hoy reconstruir «qué pasó» exige releer conversaciones.** El log lo responde por lectura directa.
- **Riesgo honesto en sentido contrario:** un canal puede aumentar el consumo si multiplica mensajes de
  bajo valor. Mitigación: los ocho tipos son cerrados y `RESULT` exige evidencia.

---

## 23 · Qué se pide aprobar

1. **El hallazgo de §0** — ChatGPT-el-chat no puede participar; **Codex CLI es la única vía sin clave**.
   *(¿Se acepta el hecho?)*
2. **La arquitectura de §3** — canal transaccional local-first; el Control Plane conserva la autoridad.
   *(¿Se acepta?)*
3. **El protocolo de §4** — ocho tipos, `id` determinista, `in_reply_to`, sin campos de concesión.
   *(¿Se acepta?)*
4. **`D-CP-1`** — qué transporte se autoriza: **A (Codex local)**, **B (API, exige enmienda de D24)** o
   **C (humano, no cumple el objetivo)**. *(Elegir una.)*
5. **`D-CP-2`** — ¿se autoriza GREEN del canal como incremento propio? Requiere levantar
   `CHECKLIST:235`. *(Sí/no.)*
6. **`D-CP-3`** — identidad declarativa o firmada. *(Elegir.)*

**Recomendación:** resolver **`D-CP-1` antes** de autorizar GREEN. Construir el canal sin decidir el
transporte es aceptar el riesgo R1 —un tubo sin consumidor—, que es exactamente el diagnóstico que el
DP del Orchestrator hizo del incremento anterior. **No repetir ese patrón es más valioso que empezar
antes.**

**Qué tendría que demostrarse para cambiar esta decisión:** que existe una vía verificada por la que
ChatGPT-el-chat lea y escriba un canal local sin clave ni endpoint público (invalidaría §0); o que el
Control Plane ya soporta dos escritores (invalidaría la urgencia).

**No se implementa nada hasta que el CEO apruebe.** Autonomía de AURORA: **0/7**.
