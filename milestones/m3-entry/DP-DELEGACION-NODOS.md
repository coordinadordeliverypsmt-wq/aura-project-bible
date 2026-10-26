---
documento: "Decision Package — Delegación de tareas a nodos secundarios (NODO-01)"
fecha: 2026-10-26
estado: "PROPUESTO, con texto de enmienda de DP-NODO-01 preparado (§6). NADA implementado. DP-NODO-01 sigue VIGENTE sin cambios: requiere decisión y acta del CEO (D23)"
evidencia: "[LECT] y [EJEC] de solo lectura (--nodos); ver CHECKPOINT (z) y (aa)"
---

# DP — Delegación de tareas a nodos

## 1. Estado real: qué existe y qué no

**Existe** `[LECT]` y `[EJEC]`, este último en solo lectura:

- **NODO-01** publica **latidos** firmados por NATS con TLS a HC-1. El agente es `walking-skeleton/aura_skeleton/nodo_agente.py`,
  que publica en `nodo.latido.<id>` (:311-314) y **no se suscribe a nada**.
- El **receptor** (`adapters/receptor_nodos.py`) solo se suscribe a `nodo.latido.*` (:152), valida, rechaza la
  suplantación (:106-109) y escribe `registro.json`.
- `core/nodos.py` define el esquema del latido, el estado (ONLINE, OFFLINE, UNKNOWN), los avisos y el sobre de
  capacidad (`capacidades_de`).
- **TLS:** cadena hasta una CA privada (`entorno/nodos/red_hc1.py`). El nodo usa `check_hostname=False` por diseño,
  porque la IP de HC-1 cambia por DHCP (DP §4.5).
- **Descubrimiento:** `tls://<hostname>.local:4222`, traducido por mDNS y con respaldo por IP. Hoy
  `<hostname>.local` **no se anuncia**: Avahi se renombró a `…-3.local` el 25-10. NODO-01 sigue **ONLINE** por el
  respaldo IP.

**No existe** `[LECT]`:

- ningún tema, cola ni contrato de **tarea remota**;
- ninguna respuesta del nodo;
- ninguna autoridad del nodo.

Un grep de `nodo.tarea`, `nodo.orden` o `delegar.*nodo` no da ningún resultado.

**Conflicto normativo.** `DP-NODO-01.md:13-21`: «**No** cubre: capacidades cognitivas remotas… autoridad del nodo».
`:112-113`: «el nodo solo puede **publicar** en `nodo.latido.<su_id>`, no puede suscribirse a nada y no tiene
respuestas». **Delegar exige revocar o ampliar esa decisión.** No se ha implementado ningún prototipo, porque
contradeciría una decisión vigente.

## 2. Contrato propuesto de tarea remota

| Elemento | Propuesta |
|---|---|
| **Tema** | HC-1 publica en `nodo.tarea.<id_nodo>`; el nodo responde en `nodo.resultado.<id_nodo>`. Permisos NATS por usuario: el nodo **solo** puede suscribirse a su tema de tarea y publicar en el suyo de resultado |
| **Contrato de la tarea** | `{id_tarea, id_ejecucion (uuid), capacidad (nombre registrado, nunca una orden del sistema operativo), argumentos validados, limite_s, limites_recursos, firma}`. Solo **capacidades registradas** (regla del CEO 2026-08-03), con nombre según el resultado que producen |
| **Identidad y correlación** | `id_ejecucion` único por intento; el resultado debe citar el `id_ejecucion` exacto. Se registra en el log de HC-1 como `tarea_delegada` y `resultado_remoto` |
| **Autenticación** | La TLS mutua existente (CA privada) y la credencial NATS por nodo. **Mejora necesaria:** fijar el certificado del servidor o verificar el SAN (M-1 de seguridad), porque hoy cualquier certificado de la CA serviría |
| **Autorización** | HC-1 decide; el nodo **no tiene autoridad**. La lista de capacidades delegables se declara por nodo, a partir de su sobre de capacidad, y la aprueba el CEO |
| **Verificación** | HC-1 **verifica el resultado** con su propio verificador. Nunca se cree el «ok» del nodo (INV-9). Un resultado no verificable se trata como fallo |
| **Reintentos y conectividad** | Tope de intentos por `id_tarea`, el mismo modelo que `TOPE_DE_REINTENTOS`. El tiempo de espera se deriva del `limite_s` declarado. Un nodo OFFLINE (estado del latido) deja la tarea `interrumpida_reintentable`, con el mismo contrato que DP-RECUPERACION-TRAS-CAIDAS |
| **Duplicados** | Idempotencia por `id_tarea` y `id_ejecucion`: HC-1 ignora resultados de ejecuciones que no estén en curso; el nodo ignora una tarea ya en curso |
| **Caídas** | HC-1 aplica el contrato de reanudación del DP de recuperación, con el ejecutor remoto identificado por `id_nodo` e `id_ejecucion` en lugar de pid. El nodo no guarda estado: si se reinicia, la tarea queda interrumpida y HC-1 decide |
| **Límites** | En el nodo, el mismo confinamiento estricto que la verificación local (Landlock + seccomp, sin red), rlimits, `limite_s`, y ninguna escritura fuera de su sandbox |

## 3. Pruebas de aceptación (cuando se autorice)

1. NATS **local** en un puerto aleatorio, con PKI de prueba, como ya hacen `test_nodo_e2e_nats.py` y
   `test_red_hc1_pki.py`.
2. Una capacidad inocua registrada, por ejemplo calcular el sha de un fichero del sandbox, delegada a un agente de
   nodo de prueba: la respuesta se verifica en HC-1.
3. Matar al nodo a mitad de la tarea: queda `interrumpida`, se reintenta dentro del tope y no hay duplicados.
4. Un resultado con `id_ejecucion` ajeno o un certificado no fijado se rechaza.
5. Una capacidad no registrada o con argumentos fuera de contrato se rechaza **antes** de enviarse.
6. **Nunca contra NODO-01 en producción** hasta superar todo lo anterior y con una ventana segura.

## 4. Reversión

Los temas nuevos son aditivos. Retirar los permisos NATS `nodo.tarea.*` y `nodo.resultado.*` y la capacidad delegable
devuelve el sistema al estado de solo latidos. No hay datos que migrar.

## 5. Decisión que se pide

1. **Ampliar el alcance de DP-NODO-01**, o crear un DP nuevo que lo sustituya en este punto, para permitir el contrato
   del §2.
2. Aprobar la **primera capacidad delegable** (inocua) y la mejora M-1 de TLS (fijar el certificado o el SAN).
3. Solo después: TDD, un prototipo aislado con NATS local, mutación, revisiones y el QG.

## 6. Propuesta normativa: enmienda de `DP-NODO-01` (preparada el 2026-10-26, **no aplicada**)

`DP-NODO-01` **no se ha modificado**. Esto es el texto que el CEO aprobaría o rechazaría; hasta entonces rige el
original, con solo latidos.

**Enmienda 1, a `DP-NODO-01` §1 («No cubre»).** Se mantienen **todas** las exclusiones, incluida «autoridad del nodo».
Se añade:

> El nodo puede **ejecutar capacidades registradas y delegables** que HC-1 le encargue, de una lista cerrada aprobada
> por el CEO para cada nodo. Ejecutar por encargo **no es autoridad**: el nodo no decide qué se hace, no verifica su
> propio resultado y no puede encargar nada a nadie. Las capacidades cognitivas remotas (LLM, Whisper, Piper,
> visión) **siguen excluidas**.

**Enmienda 2, a `DP-NODO-01` §4.5 (permisos NATS).** Donde dice «solo puede publicar en `nodo.latido.<su_id>`, no puede
suscribirse a nada y no tiene respuestas», diría:

> El nodo puede publicar en `nodo.latido.<su_id>` y en `nodo.resultado.<su_id>`, y **suscribirse solo** a
> `nodo.tarea.<su_id>`. HC-1 es el único que publica en `nodo.tarea.*`. Ninguna otra ruta.

**Enmienda 3, a la verificación TLS (mejora M-1).** El nodo, además de anclarse a la CA, **fija la identidad del
servidor**: el SAN del certificado de HC-1, o su huella. Así un certificado distinto de la misma CA no puede hacerse
pasar por HC-1. Es un requisito **previo** a cualquier tarea, no posterior.

### 6.1 Contrato completo de la tarea remota

| Aspecto | Contrato |
|---|---|
| **Identidad** | `id_tarea`, derivado como hoy (no correlativo); `id_ejecucion` (uuid por intento); `id_nodo`, que tiene que coincidir con el subject, igual que el latido |
| **Autorización** | HC-1 decide con el mismo circuito que una tarea local: descubrimiento, planificador, `review` y PARADA. La capacidad tiene que estar en la lista delegable **de ese** nodo. Si no lo está, se rechaza **antes** de publicar |
| **Autenticación** | TLS mutua con la CA privada, más el servidor fijado (enmienda 3) y la credencial NATS por nodo (0600). El resultado tiene que llegar por `nodo.resultado.<id_nodo>`, con el mismo `id_nodo` y el `id_ejecucion` en curso |
| **Verificación del resultado** | HC-1 lo verifica con su propio verificador, en una copia confinada. El «ok» del nodo **nunca** cuenta (INV-9). Un resultado inverificable es un fallo |
| **Reintentos** | `TOPE_DE_REINTENTOS` (el mismo de hoy) por `id_tarea`. Cada publicación es un intento y deja `tarea_planificada` **antes** de publicarse |
| **Duplicados** | Se usa `registrar_evento_si` (comprobar y añadir bajo cerrojo), igual que en local: dos supervisores no pueden encargar la misma tarea. HC-1 descarta cualquier resultado cuyo `id_ejecucion` no sea el del último intento; el nodo ignora una tarea que ya tiene en curso |
| **Recuperación** | Es el contrato de `DP-RECUPERACION-TRAS-CAIDAS`, cambiando el ejecutor `{pid, inicio, arranque}` por `{id_nodo, id_ejecucion}`. «Vivo» significa que el nodo está ONLINE (latido) **y** ha confirmado haber recibido ese `id_ejecucion`. Un nodo OFFLINE o reiniciado deja la tarea `interrumpida_reintentable`; agotada, deja el evento de agotamiento |
| **Límites de recursos** | En el nodo: `limite_s` declarado, rlimits de CPU, memoria y ficheros, confinamiento estricto (Landlock + seccomp), **sin red** salvo NATS, y escritura solo en su sandbox. `max_payload` sigue en 64 KiB |
| **Observabilidad** | Eventos `tarea_delegada`, `resultado_remoto` y `resultado_remoto_rechazado` (motivo), todos en el log de HC-1 con su cadena de hash |

### 6.2 Qué **no** se hace hasta que haya acta

No se cambian permisos NATS ni se crean temas. No se envían tareas a NODO-01, no se reinicia el receptor y no se toca
`DP-NODO-01`. La capacidad de delegación se considerará implementada solo después de tres cosas: el acta, un
prototipo aislado con NATS local y PKI de prueba que supere las pruebas del §3, y la mutación y la revisión
independiente.


## 7. Cinco hechos distintos que no deben confundirse (2026-10-26)

Cada fila es una afirmación más fuerte que la anterior, y **ninguna implica la siguiente**. Confundirlas es el patrón
«declarado ≠ real» aplicado a la distribución.

| # | Hecho | Qué lo prueba | ¿Existe hoy? `[LECT]` |
|---|---|---|---|
| 1 | **Nodo visible por latido** | Un latido válido en `nodo.latido.<id>`, dentro de la ventana del estado ONLINE (`core/nodos.estado_nodo`) | **Sí** |
| 2 | **Nodo autenticado** | TLS mutua con la CA privada, credencial NATS del nodo y `nodo_id` igual al subject (el receptor rechaza la suplantación, `receptor_nodos.py:106-109`). **Falta:** fijar la identidad del servidor (M-1) | **Sí, a medias.** La autenticación de cliente existe; la del servidor solo se ancla a la CA |
| 3 | **Tarea remota aceptada** | El nodo publica en `nodo.resultado.<id>` un acuse que cita el `id_ejecucion` exacto, y HC-1 registra `tarea_aceptada` | **No.** No existen temas ni permisos |
| 4 | **Tarea realmente ejecutada** | El nodo declara un resultado, con `id_ejecucion`, en su sandbox confinado. **Es una declaración del nodo, no un hecho para HC-1** | **No** |
| 5 | **Resultado devuelto y verificado** | HC-1 lo verifica **con su propio verificador**, en una copia confinada, y registra `resultado_remoto` con `verificado: true`. Es el **único** que cuenta como trabajo hecho (INV-9) | **No** |

**Consecuencias para el contrato:**

- Un nodo ONLINE (1) **no** está disponible para recibir tareas mientras no se cumpla también (2) con el servidor fijado.
- Un acuse (3) **no** consume ni concede nada: solo hace que el ejecutor remoto cuente como «vivo» para el contrato de
  recuperación.
- (4) **nunca** se registra como completado. Solo (5) produce `completada`.

## 8. Justificación técnica para ampliar `DP-NODO-01`

- **Por qué es seguro hacerlo ahora:**
  1. La identidad del ejecutor y la recuperación ya existen y están probadas localmente (`DP-RECUPERACION-TRAS-CAIDAS`):
     interrumpida, agotada con evento y sin duplicados bajo cerrojo.
  2. El supervisor único por log impide atribuciones cruzadas.
  3. El receptor ya rechaza la suplantación por subject.

  La delegación reutiliza esas piezas, sustituyendo `{pid, inicio, arranque}` por `{id_nodo, id_ejecucion}`, en lugar
  de inventar otras.
- **Lo que falta y bloquea la delegación:**
  - la fijación del servidor TLS (M-1);
  - la **correlación estable tarea→resultado** (`DP-AUTOCONSTRUCCION-CORRELACION-Y-RECUPERACION`, pieza 1). Sin ella, un
    resultado remoto que llegase tarde se atribuiría por orden, y con varios nodos eso es **seguro** que falla.

  **Por eso aquel DP es un prerrequisito de este.**

## 9. Criterios de aceptación de la ampliación (todos `[EJEC]`, en aislamiento)

1. Se cumplen los prerrequisitos: M-1 y la correlación estable, aprobados e integrados.
2. Las pruebas del §3, con NATS local, PKI de prueba y un agente de nodo de prueba. **Nunca NODO-01.**
3. Cada uno de los hechos 1-5 del §7 tiene **su propia prueba**, con un control que demuestre que el hecho anterior no
   basta:
   - online sin autenticar → no recibe;
   - acuse sin resultado → `en_curso`;
   - resultado no verificable → fallo.
4. **Caídas:**
   - nodo apagado tras el acuse → `interrumpida_reintentable`;
   - dos veces → `agotada`, con evento;
   - resultado tardío de un intento anterior → descartado.
5. **Seguridad:**
   - una capacidad no registrada o con argumentos fuera de contrato se rechaza **antes** de publicar;
   - un certificado de la misma CA pero distinto del de HC-1 → rechazado;
   - límites de recursos y sin red en el sandbox del nodo.
6. Mutación de cada garantía, auditor de garantías, revisión independiente (código y seguridad) y QG.
7. **Acta del CEO** que apruebe el texto del §6 y la primera capacidad delegable (inocua).

**Hasta que se cumpla todo esto, `DP-NODO-01` sigue vigente sin cambios**: solo latidos.

## 10. Completar la propuesta (decisión del CEO, 2026-10-26: solo documental)

Rutas confirmadas con Graphify:

- `walking-skeleton/aura_skeleton/nodo_agente.py`: el agente del nodo, que hoy solo publica latidos;
- `walking-skeleton/aura_skeleton/core/nodos.py`: el esquema y el estado del nodo;
- `walking-skeleton/aura_skeleton/adapters/receptor_nodos.py`: el receptor, que rechaza la suplantación;
- `entorno/nodos/red_hc1.py`: la PKI;
- `milestones/m3-entry/DP-NODO-01.md`: §1 y §4.5.

### 10.1 Prerrequisitos (bloqueantes, en este orden)

1. **Identidad TLS del servidor fijada (M-1).** Hoy el nodo valida que el certificado procede de la CA privada
   (`CERT_REQUIRED`), pero no **de cuál** servidor se trata (`check_hostname=False`, DP-NODO-01 §4.5). Propuesta:
   fijar la **huella SHA-256 del certificado de HC-1**, o el **SAN** de un nombre lógico estable (no la IP, que cambia
   por DHCP). Al rotar el certificado, lo publica HC-1 por un canal ya autenticado y se actualiza la huella. **Prueba:**
   un certificado válido de la misma CA con otra huella se rechaza.
2. **Correlación inequívoca.** Es la del `DP-AUTOCONSTRUCCION-CORRELACION-Y-RECUPERACION` (I1), extendida con
   `{tarea, intento, id_nodo, id_ejecucion}`. `intento` es el `seq` de `tarea_planificada` en HC-1, y `id_ejecucion` es
   un uuid por publicación. Un resultado sin los cuatro campos, o con cualquiera distinto del del intento en curso, se
   **descarta y se registra** (`resultado_remoto_rechazado`).
3. **Estados distintos** (§7): `aceptada` (acuse del nodo), `declarada_ejecutada` (el nodo lo dice) y `verificada`
   (HC-1 lo comprueba). Solo `verificada` concede `completada`.

### 10.2 Contrato operativo

| Aspecto | Regla |
|---|---|
| **Idempotencia** | `(tarea, intento)` se planifica con `registrar_evento_si`, bajo cerrojo y una sola vez. El nodo **ignora** un `id_ejecucion` que ya tiene en curso o terminado (memoria acotada a la ventana de caducidad), y HC-1 ignora resultados de intentos que ya no están en curso |
| **Caducidad** | Cada tarea lleva `caduca_en`, derivado de su `limite_s` declarado y no de un número fijo (regla del CEO 2026-08-04). El nodo **no empieza** una tarea caducada y responde `rechazada_caducada` |
| **Timeouts** | Espera de acuse: cuenta desde la publicación y, si se agota, deja la tarea `interrumpida_reintentable`. Espera de resultado: `limite_s` más un margen declarado en el contrato de la capacidad. Agotada sin resultado → `interrumpida_reintentable` |
| **Reintentos** | `TOPE_DE_REINTENTOS` (el mismo que en local). Cada publicación consume un intento. Agotado → `agotada` y el evento `presupuesto_de_tarea_agotado` |
| **Recuperación** | HC-1 cae: al volver, `estado_de` con el ejecutor remoto. «Vivo» significa nodo ONLINE **y** acuse de ese `id_ejecucion` dentro de su caducidad; si no, `interrumpida_reintentable`. Cae el nodo: no guarda estado y decide HC-1. Supervisor único por log en HC-1 |
| **Trazabilidad** | `tarea_delegada{tarea, intento, id_nodo, id_ejecucion, capacidad, caduca_en}`, `tarea_aceptada`, `resultado_remoto{…, verificado}` y `resultado_remoto_rechazado{motivo}`, todos en la cadena de hash de HC-1 |

### 10.3 Pruebas aisladas (cuando se autorice; nunca contra NODO-01)

- **Entorno:** NATS local en puerto aleatorio, PKI de prueba (como `test_red_hc1_pki.py` y `test_nodo_e2e_nats.py`) y
  un agente de nodo de prueba en un proceso propio.
- **Casos, cada uno con su control:**
  - certificado de la misma CA con otra huella → rechazado;
  - acuse sin resultado → `en_curso`, y al caducar → `interrumpida_reintentable`;
  - resultado de un `id_ejecucion` antiguo → `resultado_remoto_rechazado`;
  - resultado inverificable → fallo;
  - dos supervisores → uno solo publica;
  - nodo apagado dos veces → `agotada` con evento;
  - tarea caducada → no se empieza.
- **Además:** mutación de cada garantía, auditor de garantías, revisión de código y de seguridad, y QG.

### 10.4 Reversión segura

Retirar los permisos NATS de `nodo.tarea.*` y `nodo.resultado.*` y la lista de capacidades delegables: el nodo vuelve
a solo latidos, como hoy. Los eventos de delegación se quedan en el log, que es append-only, y el código anterior no
los interpreta. No hay que migrar nada. **El receptor no se reinicia** como parte de la reversión salvo que haya una
ventana segura aprobada.

**Estado: PROPUESTA DOCUMENTAL. `DP-NODO-01` sigue vigente sin cambios. Ninguna tarea remota ejecutada ni ningún nodo
modificado.**

## 11. Revisión de seguridad (`security-reviewer`, 2026-10-26): APTA CON CONDICIONES. Requisitos incorporados

La revisión fue **documental**: no se ejecutó nada. AgentShield, bandit y semgrep no están instalados. **Cambio de modelo
de amenaza que se declara:** con la enmienda, el nodo deja de ser un **emisor pasivo** (`:18`, «no se suscribe a nada»)
y pasa a ser un **ejecutor de entrada remota**. Cada requisito siguiente es **condición previa** de la implementación.

| # | Hallazgo | Requisito que se incorpora a la propuesta |
|---|---|---|
| A1 (ALTO) | Las órdenes no tienen autenticidad propia (solo TLS más la credencial NATS) | **Firma de tarea por HC-1.** La clave, Ed25519, es **distinta** de la del servidor TLS. Firma el JSON canónico y versionado `{v, tarea, intento, id_nodo, id_ejecucion, capacidad, argumentos, caduca_en}`. El nodo la **verifica antes de nada** y rechaza firmas inválidas o ausentes. Clave pública aprovisionada fuera de banda; rotación y revocación por el mismo procedimiento que A3 |
| A2 (ALTO) | Los resultados no van firmados y el subject no se liga en `nodo.resultado.*` | **Firma del resultado con la clave del nodo** sobre `{v, tarea, intento, id_nodo, id_ejecucion, hash_tarea, salida}`, donde `hash_tarea` es el hash de la orden firmada recibida. Consumidor único: un suscriptor de HC-1 con permiso **solo** de suscripción a `nodo.resultado.*`, que exige `id_nodo` igual al subject (la regla del receptor de latidos, extendida) |
| A3 (ALTO) | Fijación TLS ambigua; rotación circular; arranque en frío; downgrade | **Fijar la clave pública (SPKI)** del servidor de HC-1, no solo el SAN. **Aprovisionamiento inicial fuera de banda**, con TOFU prohibido. **Rotación con doble fijación** (actual y siguiente) durante una ventana; la siguiente va firmada por una clave raíz **fuera de línea**. **Fallo cerrado:** sin fijación válida no se reciben tareas y no se vuelve a «solo CA». TLS 1.3 como mínimo. El nodo informa en su latido de que tiene la fijación activa (huella de la SPKI que usa), y así HC-1 sabe si puede delegarle |
| M1 | Permisos NATS solo descritos en prosa; JetStream; compromiso de un nodo | Configuración **exacta por usuario**: suscripción solo a `nodo.tarea.<su_id>`; publicación solo en `nodo.latido.<su_id>` y `nodo.resultado.<su_id>`; sin comodines, sin `_INBOX.>`, `$SYS` ni `$JS`; `max_subscriptions=1`, `max_connections=1`, `max_payload` 64 KiB; una credencial por nodo, nunca compartida. **Sin JetStream:** NATS núcleo es at-most-once, y una tarea publicada con el nodo apagado se pierde, lo que se cubre con el timeout de acuse. Análisis STRIDE y plan de compromiso de un nodo (revocar credencial y clave, retirar permisos) **antes del acta** |
| M2 | Repetición tras un reinicio del nodo; nonce; reloj | `caduca_en` **absoluto y firmado**. El nodo exige un reloj sincronizado (NTP) dentro de una tolerancia declarada; fuera de ella, rechaza. `id_ejecucion` = uuid4 de CSPRNG. Tras reiniciar, el nodo rechaza todo lo emitido antes de su arranque, por lo que no hace falta memoria persistente |
| M3 | Qué verifica HC-1; acuses que alargan la tarea | **Toda capacidad delegable declara su verificador en HC-1. Si no tiene, no es delegable.** El verificador trata el resultado como entrada hostil: tamaño acotado, esquema estricto y sin deserialización insegura. **Techo de duración total** derivado de `limite_s`, que los acuses **no** prorrogan |
| M4 | Concurrencia; inundación del log; dos intentos a la vez en el nodo; cancelación | Límite de tareas en vuelo por nodo y global, con cola acotada. **Exclusión por `tarea` en el nodo:** no ejecuta un segundo intento si el anterior sigue vivo. Tope de eventos `resultado_remoto_rechazado` por nodo y ventana, después agregado y alerta, porque el log es append-only. Mensaje de **cancelación** firmado. Margen de timeout con cota máxima. La semántica del reintento remoto (la orden pudo tener efecto) se declara por capacidad: solo se delegan capacidades **idempotentes** |
| M5 | Validación solo en HC-1; ejecutor por nombre; sobre autodeclarado | El nodo **revalida** capacidad y argumentos contra su lista **local**. Ejecutor = **tabla de funciones fija**, nunca `exec`, `shell=True` ni interpolación. Esquema de argumentos con tipos y longitudes; sin rutas absolutas, `..`, symlinks ni comodines. La lista delegable sale de la **configuración de HC-1 aprobada por el CEO**, nunca del sobre que declara el nodo |
| M6 | El sandbox puede tocar NATS o credenciales; Landlock ausente | **Procesos separados:** el agente tiene NATS y las claves; el ejecutor no tiene red, ni acceso a credenciales ni a claves, y solo dispone de un canal de resultado heredado. **Fallo cerrado** si faltan Landlock, seccomp o la ABI mínima. Límites de `RLIMIT_NPROC`, tiempo de reloj y CPU, `RLIMIT_FSIZE`, salida ≤ 64 KiB y cuota de disco. **Sandbox limpio** entre tareas e intentos. Usuario dedicado sin sudo |
| M7 | Definición de «vivo» incoherente entre `:110`, `:138` y `:213` | Definición única: **vivo = nodo ONLINE + acuse firmado de ese `id_ejecucion` + dentro del techo de duración total**. Las tres menciones remiten a esta |
| B1-B6 | Reversión, observabilidad, pruebas negativas, primera capacidad, formato y superficie | La reversión revoca la clave de tareas y las fijaciones, cancela las tareas en vuelo y espera la limpieza del sandbox, y rota la credencial si hay sospecha. Un control **prueba** que el código anterior ignora tipos de evento desconocidos. Eventos de seguridad (firma inválida, fijación fallida, reloj fuera de tolerancia, sandbox ausente) con alerta al CEO tras N rechazos. Los casos negativos de B3 pasan a ser **pruebas obligatorias**, cada una con su control. La primera capacidad se fija por escrito con su verificador; un sha de un fichero del nodo **no** sirve, porque HC-1 no puede verificarlo sin recalcularlo. JSON canónico, versionado y con rechazo de campos desconocidos |

**Prerrequisito citado** (`:154`): `DP-AUTOCONSTRUCCION-CORRELACION-Y-RECUPERACION.md`. Su estado es **diseño completo, no
aprobado** (§11 de ese DP). La delegación no puede implementarse antes de que se apruebe e integre.

**Estado tras la revisión: PROPUESTA DOCUMENTAL, apta con condiciones.** Antes del acta del CEO faltan:

- elegir explícitamente la fijación por SPKI y el esquema de firmas;
- el análisis STRIDE;
- la primera capacidad, con su verificador.

`DP-NODO-01` sigue sin cambios.

## 12. Análisis formal de amenazas (STRIDE) de la delegación propuesta (2026-10-26, documental)

**Estado:** propuesta documental. **No se ha ejecutado ninguna tarea remota.** `DP-NODO-01` sigue vigente sin cambios
(solo latidos). Siguen **abiertos los tres ALTOS** del §11 (A1-A3), a los que la revisión del §12.6 añade **N1** (replay tras reinicio) y **N2** (custodia de la clave de HC-1):

- **A1:** las tareas de HC-1 firmadas.
- **A2:** los resultados del nodo firmados.
- **A3:** fijación de la identidad TLS del servidor por SPKI, aprovisionada fuera de banda, con fallo cerrado.

### 12.1 Activos

| Activo | Por qué importa |
|---|---|
| **Log de HC-1** (`eventos.jsonl`, cadena de hash) | Fuente de verdad (ADR-0023). Lo que entre en él cuenta como hecho |
| **Clave de firma de tareas de HC-1** (A1) | Quien la tenga puede ordenar ejecuciones a los nodos |
| **Clave de firma del nodo** (A2) y **credencial NATS por nodo** | Quien las tenga puede hacerse pasar por el nodo |
| **CA privada y SPKI fijada de HC-1** (A3) | Raíz de la autenticación del canal |
| **Sandbox y ejecutor del nodo** | Donde se ejecuta código por encargo |
| **PARADA, lista roja y autoridad humana** | Ninguna vía remota puede rodearlas |

### 12.2 Fronteras de confianza

1. **HC-1, entre el control-plane y el publicador NATS:** dentro del mismo proceso o usuario, que es de confianza.
2. **Red LAN, entre HC-1 y el nodo:** **no** es de confianza. En la LAN hay IoT, un DVR y una PS5.
3. **Nodo, entre el agente y el ejecutor:** el ejecutor **no** es de confianza para el agente (separación de procesos,
   M6).
4. **Entrada de resultados a HC-1:** **toda** salida del nodo es entrada hostil hasta que se verifica.

### 12.3 STRIDE

| Categoría | Amenaza concreta | Control requerido | Estado |
|---|---|---|---|
| **S** · suplantación del **servidor** | Un dispositivo de la LAN con un certificado de la misma CA se hace pasar por HC-1 | A3: fijación SPKI, aprovisionamiento fuera de banda, TOFU prohibido, **fallo cerrado** y TLS 1.3 como mínimo | **ABIERTO** |
| **S** · suplantación del **nodo** | Credencial NATS filtrada o compartida, o un resultado publicado en el subject de otro nodo | Credencial **por nodo** y nunca compartida; `id_nodo` igual al subject también en `nodo.resultado.*`; firma del resultado con la clave del nodo (A2) | **ABIERTO** (A2) |
| **T** · manipulación de la **tarea** | Alterar capacidad, argumentos o `caduca_en` en tránsito, o inyectar una tarea | Firma Ed25519 de HC-1 sobre JSON canónico versionado (A1); el nodo verifica **antes de nada** y revalida contra su lista local (M5) | **ABIERTO** (A1) |
| **T** · manipulación del **resultado** | Resultado falsificado o alterado | Firma del nodo sobre `{…, hash_tarea, salida}` (A2) **y** verificación independiente en HC-1 (M3). La firma prueba **quién**, no **que sea correcto** | **ABIERTO** (A2) |
| **R** · repudio | El nodo niega haber recibido o ejecutado; HC-1 no puede probar qué ordenó | Eventos `tarea_delegada`, `tarea_aceptada` (acuse firmado), `resultado_remoto` y `resultado_remoto_rechazado` en la cadena de hash de HC-1, con la orden y el resultado firmados | REQUERIDO, no implementado (§10.2) |
| **R** · **replay** y caducidad | Reenviar una tarea o un resultado antiguo, incluso tras reiniciar el nodo | `caduca_en` absoluto y firmado; reloj NTP con tolerancia; uuid4 de CSPRNG; rechazar lo emitido antes del arranque del nodo; HC-1 descarta resultados que no sean del intento en curso | REQUERIDO, no implementado; **insuficiente hasta N1** |
| **I** · fuga de información | Argumentos o resultados con datos sensibles; credenciales accesibles al ejecutor | Ejecutor sin acceso a credenciales ni claves (Landlock); capacidades declaradas sin datos personales; salida ≤ 64 KiB | REQUERIDO, no implementado (M6) |
| **I** · reutilización de credenciales | Credencial NATS de un nodo usada para publicar en `nodo.tarea.*` | Permisos NATS exactos por usuario: deny de `nodo.tarea.*` para los nodos, sin comodines ni `$SYS`/`$JS` (M1) | REQUERIDO, no implementado (M1) |
| **D** · denegación de servicio | Inundación de resultados que llenan el log append-only; tareas en vuelo sin límite; acuses que alargan la vida de una tarea | Tope de rechazos por nodo y ventana; límite de tareas en vuelo; techo de duración que los acuses **no** prorrogan (M3, M4) | REQUERIDO, no implementado |
| **E** · elevación de privilegios | Una tarea que se convierte en orden del SO; un nodo que amplía su propio sobre de capacidades | Ejecutor = **tabla de funciones fija**, sin `exec` ni shell; lista delegable configurada en HC-1 y aprobada por el CEO, nunca autodeclarada (M5); usuario dedicado sin sudo | REQUERIDO, no implementado |
| **E** · rodear la autoridad de AURA | Una acción remota que evita PARADA, la lista roja o el motor único | Toda delegación pasa por el mismo circuito que lo local: planificador, `review`, PARADA y lista roja. El nodo **no tiene autoridad** | REQUERIDO, no implementado; **depende de N2** |

**Compromiso del nodo** (el escenario más grave aceptado):

- Un nodo comprometido puede devolver **resultados falsos pero bien firmados**. Lo único que lo detiene es la
  **verificación independiente en HC-1** (M3): **sin verificador, la capacidad no es delegable**.
- **Respuesta:** revocar la clave y la credencial del nodo, retirar sus permisos NATS, cancelar sus tareas en vuelo y
  marcar `resultado_ambiguo` en los intentos afectados. No hay rotación silenciosa.

**Interrupciones:** se aplica el contrato de `DP-RECUPERACION-TRAS-CAIDAS` con el ejecutor remoto
`{id_nodo, id_ejecucion}`:

- nodo OFFLINE o caducado → `interrumpida_reintentable`;
- intentos agotados → `agotada`, con su evento.

**Autorización, auditoría y revocación:**

- **Autorización:** el acta del CEO por nodo y por capacidad.
- **Auditoría:** la cadena de hash.
- **Revocación:** la clave de tareas, las fijaciones y las credenciales (B1).

**Fallo cerrado:** cualquier error de firma, de fijación, de reloj o de verificación → **no se ejecuta** en el nodo y
**no se incorpora** en HC-1. Se registra el evento de seguridad.

### 12.4 Cinco estados de un resultado remoto (ninguno implica el siguiente)

| # | Estado | Qué lo prueba | ¿Cuenta como trabajo hecho? |
|---|---|---|---|
| 1 | **Tarea aceptada** | Acuse **firmado** por el nodo, con el `id_ejecucion` exacto | No. Solo hace que el ejecutor cuente como «vivo» dentro del techo de duración |
| 2 | **Tarea ejecutada** | Declaración del nodo | **No**: es una afirmación del nodo |
| 3 | **Resultado firmado** | Firma válida del nodo sobre `{…, hash_tarea, salida}` | **No**: prueba **quién** lo envía, no que sea correcto |
| 4 | **Resultado validado por HC-1** | El verificador propio de HC-1, en una copia confinada, da `verificado: true` | **Todavía no.** `completada` exige el estado 5 (N6, §12.6): si HC-1 cae entre validar y registrar, la tarea queda en recuperación y se repite la validación |
| 5 | **Resultado incorporado a la evidencia** | `resultado_remoto{verificado: true}` en la cadena de hash de HC-1, con la orden y el resultado firmados | Es lo que queda como **hecho auditable** |

**Un latido no demuestra ejecución ni integridad:** solo dice que el nodo está ONLINE.

### 12.5 Brechas que quedan antes de cualquier acta

- Resolver A1, A2 y A3 por escrito, con la elección explícita de SPKI y del esquema de firmas.
- Elegir la primera capacidad delegable, con su **verificador** en HC-1.
- Fijar la tolerancia de reloj y la fuente NTP.
- Concretar la configuración NATS exacta.
- Escribir las pruebas negativas obligatorias (B3) con su control.
- **Revisión de seguridad independiente** de este STRIDE.

### 12.6 Revisión independiente del STRIDE (`security-reviewer`): COMPLETO CON CONDICIONES. Correcciones incorporadas

**Convención** (N13): en la columna de estado del §12.3, «REQUERIDO, no implementado» sustituye a «Diseñado». **Nada
de la delegación está implementado ni probado.** El vocabulario de estado es {ABIERTO, REQUERIDO, PROBADO}.

| # | Hallazgo | Corrección del diseño |
|---|---|---|
| **N1 · ALTO** | Replay tras reiniciar el nodo: la orden firmada no lleva cuándo se emitió | La orden firmada (A1) añade **`emitida_en`** (hora de HC-1) y **`epoch_hc1`** (contador monótono de sesión de HC-1, persistido en su log). El nodo rechaza: (a) toda orden con `emitida_en` anterior a su propio arranque; (b) toda orden de un `epoch_hc1` menor que el último visto. Hasta sincronizar el reloj (N5), lo rechaza **todo** |
| **N2 · ALTO** | Custodia de la clave de firma de tareas de HC-1 | **Firmador único:** un proceso o servicio aparte, con un usuario propio, que es el **único** que lee la clave y que solo firma peticiones de la vía planificador → `review` → PARADA → lista roja. Cada firma queda registrada en la cadena de hash (`tarea_firmada{hash, quién}`). Otros procesos del usuario de HC-1 **no** pueden firmar. **Compromiso de HC-1 o de la clave:** revocar la clave (nueva clave fuera de banda), avisar a los nodos para que rechacen la anterior por `epoch` o por huella, cuarentena de lo firmado desde la sospecha (N10). Fila STRIDE: **E · robo de la clave de firma → ABIERTO** |
| N3 | Broker NATS sin modelar | **Activo y frontera:** el broker **no es de confianza** para integridad ni autenticidad (las firmas de extremo a extremo de A1 y A2 lo hacen irrelevante). Su compromiso solo degrada la **disponibilidad** (puede descartar, retrasar o reordenar). Quien administra su configuración controla los permisos de M1: configuración bajo acta y auditada |
| N4 | Compromiso de la CA | **Fila S · CA comprometida → ABIERTO.** La fijación SPKI de A3 protege al servidor. Para los clientes: sustituir la CA, reemitir los certificados de nodo y revocar los anteriores (lista de huellas permitidas de nodo en HC-1). La autenticidad de las tareas y resultados no depende de la CA, sino de A1 y A2 |
| N5 | Reloj y NTP manipulables desde la LAN | **Fila T · reloj → ABIERTO.** Fuente de tiempo **autenticada**: NTS, o la hora de HC-1 dentro de un mensaje firmado. Un nodo recién arrancado o sin RTC **rechaza todo** hasta sincronizar dentro de la tolerancia |
| N6 | Vocabulario de estados disperso entre §7, §10.1 y §12.4; `completada` prematura | **Vocabulario único**, el del §12.4. Equivalencias: §7 «aceptada» y §10.1 «aceptada» = estado 1; §7 y §10.1 «declarada/ejecutada» = estado 2; §7 «verificada» = estados 4 y 5. **`completada` exige el estado 5** (registrado en la cadena), no solo el 4. Si HC-1 cae entre validar y registrar, la tarea queda en recuperación y se repite la validación |
| N7 | El acuse no tiene formato firmado | El acuse firmado es `{v, tarea, intento, id_nodo, id_ejecucion, hash_tarea, recibida_en}`, firmado con la clave del nodo (A2). «Vivo» se define **solo** en M7 (§11); las menciones de `:110`, `:138` y `:213` remiten a ella |
| N8 | Downgrade del esquema | El nodo fija una **`v` mínima** sin negociación: rechaza cualquier `v` menor, igual que los campos desconocidos (B6) |
| N9 | Verificador de HC-1 envenenado por una entrada hostil | **Fila D/E · verificador → REQUERIDO:** proceso confinado (el mismo aislamiento estricto que la verificación local), límites de CPU, memoria y tiempo, tamaño acotado y prueba negativa con control |
| N10 | Resultados ya incorporados de un nodo comprometido después | **Cuarentena retroactiva:** desde la ventana de sospecha, los resultados de ese nodo pasan a `resultado_ambiguo` (evento `resultado_remoto_en_cuarentena`, que se añade al catálogo del §10.2). No se borra nada: es append-only |
| N11 | Canales laterales en el sandbox | **Mitigado y aceptado:** sandbox nuevo por tarea, `/tmp` privado, uid dedicado y una sola tarea a la vez por nodo. El canal lateral de temporización se **acepta** como residual |
| N12 | Aprovisionamiento fuera de banda y clave del nodo | **Activo:** la huella inicial se verifica por un canal físico (presencia en el equipo). La clave del nodo solo la lee el agente, y su compromiso es el escenario «nodo comprometido» |
| N14 | Verificar recomputando anula el valor de delegar | **Una capacidad solo es delegable si se puede verificar más barato que ejecutarla**, o de forma independiente. Si no, no se delega |

**Estado tras la revisión:**

- **ALTOS abiertos:** A1, A2, A3, N1 y N2.
- **Resto:** requisitos documentados, sin implementar.
- **Nada autoriza ejecución remota ni cambia `DP-NODO-01`.**

