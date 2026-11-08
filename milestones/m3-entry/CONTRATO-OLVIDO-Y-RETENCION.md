---
documento: "Contrato técnico de olvido y retención — modelo de amenazas y garantías verificables"
tipo: "CONTRATO TÉCNICO del Director Técnico por delegación (orden ejecutiva del CEO, 2026-10-06, «post-S3»). No es un voto del CEO ni modifica la Bible, los ADR ni el DP-S3"
version: 2
fecha: 2026-10-07
relacionado: "Bible 5.5 §3 y §5 · 1.1 §3 (jerarquía) · ADR-0023 · ADR-0017 §4 · ADR-0001 · DP-D-M-8 (G-1, G-6, G-7, §5.2) · DP-S3-RELOJ-CM2 (§4.1, Q4/D-AMP-3, E-Q1) · AMP-AURA-DECISIONES (D-AMP-3) · DEUDA-N2 (D-N2-2, D-N2-5) · RESOLUCION-S3-CM2-ORDEN-CEO-2026-10-06"
estado: "§1-§4 VIGENTES salvo las filas marcadas BLOQUEADO · §5 BLOQUEADO por decisión formal"
revision: "v2: correcciones de la evaluación de arquitectura (arquitecto-evaluador, Opus, 2026-10-07) · v3 (2026-11-05): fila T9 ratificada por el CEO Operativo de AURA (DP-DURABILIDAD-MEMORIA, P2-B) · v4 (2026-11-06): fila T19 (acta continuidad de resultados)"
---

# Contrato de olvido y retención

## 1. Estados de una entrada de memoria (no se confunden)

| Estado | Cómo se produce | Marca | ¿En `hits` crudos de `recall`? | ¿Afirmable como vigente (`_da_por_cierto`)? |
|---|---|---|---|---|
| **Vigente** | Declaración, **y también los ecos episódicos sin marca** | sin `valid_until`/`refutada`/`retirada`/lápida | Sí | Sí |
| **Superseded** | Redeclaración del mismo atributo | `valid_until` | **Sí** (también en `ver()`/`exportar()`, con su marca) | No |
| **Refutada** | «eso ya no es cierto» | `refutada` | **Sí** (también en `ver()`/`exportar()`) | No |
| **Eco retirado** | Olvido o refutación **por entrada concreta (DR-2)**. `borrar(contiene)`/`refutar(contiene)`/`corregir` no retiran ecos (`ejecutor_modelo_usuario.py:151-152`; sin llamadores en producción hoy) | `retirada`, `retirada_por` | Sí | **No** |
| **Olvidada** | «olvida X» | lápida `_olvidada`, que **copia el valor** (`memory.py:233`) | No | No |
| **Histórico no recuperable** | Órdenes puras (`destino_de_memoria`), y desde 2026-10-07 **el eco de todo turno de soberanía** (T11) | `kind="historico"` | No (`es_recuperable`) | No |

**Granularidad de «Olvidada»:** en RAM se olvida una entrada concreta; en disco la proyección agrupa por
`_clave = (user_id, kind, content)` (`memory.py:120-135`), así que tras reiniciar una lápida oculta todas las entradas
de texto idéntico (DP-S3 §4.1.1).

## 2. Modelo de amenazas: rutas por las que un contenido olvidado podría reaparecer

| # | Ruta | Garantía | Estado 2026-10-07 |
|---|---|---|---|
| T1 | `recall` N1 en la misma sesión | La entrada olvidada no está en `_items` ni en el índice | Prueba adversarial |
| T2 | Reinicio (releer el fichero) | `_proyectar` aplica la lápida | Prueba adversarial |
| T3 | N2 (`SemanticMemory`) | Mismas garantías que N1 | **BLOQUEADO**: N2 no implementa `_items`/`olvidar`/`marcar` (D-N2-2, D-N2-5). La corrección exige declaración G-1 aprobada y gate del CEO (DEUDA-N2). N2 no se materializa en HC-1. Parche propuesto: `propuestas/D-N2-5-y-restore.patch`. Prueba `xfail(strict)` |
| T4 | Puerta ADR-0014 y contexto del modelo | Deciden con lo vigente | Prueba adversarial (incluye 4+ versiones) |
| T5 | Respuesta de hechos del Core | Solo hechos vigentes | Prueba adversarial |
| T6 | Historial («¿cuál era mi X?») | Lo olvidado no aparece como versión anterior | Prueba adversarial. **Límite:** con versiones de texto idéntico, en sesión puede devolverse el mismo texto (T14) |
| T7 | `ver`, `describir_conocimiento` | Lo olvidado no aparece | Prueba adversarial |
| T8 | `restore(backup)` de una copia anterior al olvido | — | **BLOQUEADO**: `restore` reescribe el historial con `_persist()` (viola G-7 y ADR-0023, corolarios 1 y 3) y no tiene llamadores en producción. Garantía vigente: **no se conecta** sin operación de catálogo y DP (D23). Prueba `xfail(strict)` que documenta la resurrección |
| T9 | Línea final truncada | Falla en alto si es ambigua, corrupta o puede ser lápida o marca; solo se tolera un corte demostrable, con constancia (texto ratificado en §2.1) | Prueba (T9 ×3 + `test_durabilidad_memoria_p2.py`) |
| T10 | Reloj de CM2 | Misma proyección y misma lectura de líneas que la memoria (`_lineas_legibles`); eventos `cm2.*` sin texto | Prueba |
| T19 | Registro de resultados de acción (`resultado_accion`, punto D) | «olvida lo que hiciste» / «borra el historial de acciones» anexa lápidas sobre los registros del usuario: no se recuperan, ni tras reinicio, ni en ver/exportar; nunca entran en `recall` ni en el prompt (acta 2026-11-06) | Prueba adversarial |
| **T11b** | **Captura de señales de la orden** («olvídalo, mi cumpleaños es el 3 de junio» se capturaba como declaración vigente) | Un turno de soberanía no captura señales | **Defecto activo (ECC ALTO A1), corregido 2026-10-07** |
| **T11** | **Eco de la propia orden de olvido** («usuario dijo: olvida que mi ciudad favorita es Valencia», escrito después de la lápida como `episodica` vigente) | El eco de un turno de soberanía es `historico` | **Defecto activo, corregido 2026-10-07** (TDD de extremo a extremo) |
| T12 | Olvido/refutación por texto o total no retira ecos | — | Latente (sin llamadores); documentado |
| T13 | Ventana de diálogo en RAM (6-9 turnos) | — | **BLOQUEADO (decisión)** `[EJEC]` ECC 2026-10-07: tras «olvida…», el prompt de un turno posterior lleva la declaración original **y** la orden. Solo en la sesión (no persiste). La ventana es **DR-4, aprobada por el CEO el 2026-09-15** por latencia/caché; su privacidad consta como **no decidida** (`decisiones/pendientes.md:24`). Purgarla al olvidar cambia un mecanismo aprobado: decisión del CEO |
| T14 | Versiones de texto idéntico en el historial de sesión | — | Límite documentado (véase T6) |
| T15 | Entradas `historico` con texto | No recuperables por diseño | Persisten en claro: entra en §5 |
| T16 | `backup()`: copias anteriores al olvido conservan el texto; además reescribe el fichero y **destruye lápidas** | — | Sin llamadores en producción. **Declarado ≠ real:** el manifiesto clasifica `backup` como neutro (`architecture_manifest.toml:87`). Corregirlo exige editar el manifiesto (aprobación) |
| T17 | N2 `_items` | — | Parte de T3 |
| T18 | Telemetría en RAM (`obs._records`) y stderr con `--telemetria` | — | Contiene texto; entra en §5 (5.5 §5) |

### 2.1 T9 — texto ratificado (decisión del CEO Operativo de AURA, 2026-11-05)

> Una línea final truncada debe fallar en alto cuando sea ambigua, corrupta o pueda corresponder a una lápida o
> marca. Se permite tolerar únicamente un corte demostrable: prefijo JSON válido cuyo único defecto sea el fin
> abrupto del contenido, que no pueda corresponder al inicio de una línea con la clave de un recuerdo existente y
> siempre que no se superen tres líneas toleradas por fichero. Cada tolerancia deberá quedar registrada mediante
> constancia de auditoría, sin exponer el contenido del recuerdo.

Sustituye al texto anterior («comportamiento existente: falla en alto, no resucita en silencio»), que exigía fallar
ante cualquier línea final truncada. La garantía de olvido no se debilita: toda línea que pueda ser una lápida
(`olvidar`) o una marca (`marcar`) —ambas copian la clave `(user_id, kind, content)`— sigue fallando en alto, y no
puede tolerarse una corrupción.

Implementación y evidencia: `DP-DURABILIDAD-MEMORIA.md` §8; código `7b7d45c` (`_lineas_legibles`,
`_forma_de_corte`, `_fragmento_ambiguo`, `_MAX_FRAGMENTOS_TOLERADOS = 3`, constancia
`memoria.linea_truncada_tolerada` con posición y bytes); pruebas y mutación `ac0ffc8`.

*Nota de alcance (descriptiva, no normativa):* la siguiente escritura cierra un corte tolerado con `\n` sin borrar
bytes, de modo que esa línea deja de ser la final; en relecturas posteriores sigue tolerándose con las mismas
condiciones de esta sección (y cuenta para el tope de tres por fichero).

## 3. Metadatos que pueden conservarse

Que hubo un olvido, cuándo y de qué identidad opaca (`hecho_id`, `cm2.hecho_retirado`); la lápida; los registros que
reconstruyen **que** ocurrió una mutación. **Salvedad:** que conservar el metadato del olvido sea legítimo depende de
D-AMP-3 (`AMP-AURA-DECISIONES.md:96-106`: «AURA recuerda que había algo» puede ser exactamente lo que el usuario no
quería). No está resuelto.

## 4. Verificación

Cada ruta con estado «prueba» tiene caso de **control** (antes del olvido sí aparece) y **adversarial** (después no).
`tests/integration/test_olvido_adversarial.py`. Las filas BLOQUEADO tienen `xfail(strict=True, raises=…)`: si empezaran a pasar,
la suite lo señalaría. **Límite (ECC C1):** en N2 los controles fallan antes de su primera aserción (no hay `_items`),
así que no se sabe si miden algo hasta promover D-N2-5; al promoverlo hay que revisar uno a uno los XPASS de `[n2]`.

## 5. BLOQUEADO — borrado físico del texto

**Contradicción:**
- **Bible 5.5 §3** (rango 4, aprobado por delegación D22): el borrado elimina «el dato y su rastro en índices y backups»
  y es **verificable**. 5.5 §5: los logs son dato del usuario, **cifrados** y con redacción (tampoco cumplido hoy).
- **ADR-0023** (rango 3, accepted): el historial es la única fuente de verdad y nunca se reescribe (corolarios 1 y 3).
- **DP-D-M-8 G-7**: tras un olvido el fichero no pierde líneas. **G-6**: toda mutación es reconstruible; la prueba
  `test_g7_el_audit_sigue_identificando_QUE_y_SOBRE_QUIEN` fija hoy que el audit conserve el texto. Los segmentos del
  audit están **sellados con sha256** (integridad forense, ALERTA-004).
- **En sentido contrario a 5.5 no hay solo ADR:** ADR-0017 §4 («borrarse total o selectivamente», rango 3), el acta D1 y
  el acta del estándar (rango 1) apuntan a favor del borrado. Por jerarquía (1.1 §3) el ADR prevalece en lo que decide;
  la colisión es entre fuentes de rango 1 y 3, y no la resuelve ingeniería.
- **DP-D-M-8 §5.2 ya previó** una «purga física diferida explícita (lista roja)», sin decidirla. Una purga separada no
  viola G-7 por definición; los obstáculos reales son ADR-0023 c.1, el sellado sha256 y la interpretación de G-6.

**Dónde sigue hoy el texto olvidado:**
- la línea original del JSONL de memoria y la lápida, que copia el valor;
- los ecos, incluidos los de órdenes;
- las entradas `historico`;
- los mensajes de auditoría y sus segmentos sellados;
- las copias de `backup()`;
- la ventana de diálogo y la telemetría en RAM;
- cualquier fichero ya exportado.

**Para el contenido ya escrito no hay solución sin enmienda o excepción formal:** quitarlo exige reescribir ficheros
append-only y segmentos sellados.

**Alternativa técnica recomendada para el contenido futuro: borrado criptográfico.**
- **Cómo funciona:** el contenido se escribe cifrado con una clave por entrada o por turno. «Olvidar» destruye la clave;
  el historial no pierde líneas y la mutación sigue siendo reconstruible como metadato.
- **Decisiones que necesita, ninguna dentro de la delegación técnica:**
  - D-AMP-3, Q4 y E-Q1, de las que es una implementación;
  - una enmienda o excepción a ADR-0023, porque el almacén de claves es estado mutable con valor semántico que no se
    regenera desde el historial;
  - un ADR de tecnología reservado al CEO (D3/D22) y la dependencia de cifrado (D26; ADR-0001 ya lo anticipa), local y
    sin KMS de terceros (D24), con decisión sobre la protección de la clave maestra;
  - la política de respaldos 3-2-1 y 7.4: una copia del almacén de claves resucita claves destruidas, y perderlo
    pierde la memoria;
  - una declaración G-1 R-B para el almacén de claves;
  - la interpretación de G-6: reconstruir la mutación, no el valor;
  - un cambio de formato: `_clave` y la lápida sin texto, lo que cambia las pruebas G-7;
  - cobertura de ecos, `historico` y entradas sin `hecho_id`;
  - aviso al usuario de que la exportación total sale descifrada y no se destruye con la clave.

**Registro formal pendiente.** 1.1 §3.2, regla 3, exige registrar este conflicto en `decisiones/pendientes.md`. Hacerlo
requiere la autorización del CEO para editar ese fichero, que sigue pendiente desde el 2026-10-06.

## 6. Registro

| Fecha | Cambio |
|---|---|
| 2026-10-06 | v1: estados, amenazas T1-T10, metadatos, pruebas, bloqueo y alternativa |
| 2026-10-07 | v2 tras la evaluación de arquitectura. Se añaden el estado `historico`, las precisiones de eco retirado, granularidad y vigencia de los ecos, y T11-T18 (T11 activo, corregido). T3 y T8 pasan a BLOQUEADO (G-1/gate del CEO; `_persist` viola G-7 y ADR-0023). Se añaden jerarquía, la purga diferida de DP-D-M-8 §5.2, el sellado sha256, la prueba G-7 sobre el audit, las ubicaciones del texto y las decisiones que faltaban para el borrado criptográfico |
