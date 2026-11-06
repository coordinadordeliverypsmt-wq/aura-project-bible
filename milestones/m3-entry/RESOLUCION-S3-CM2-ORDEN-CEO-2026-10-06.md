---
documento: "Resolución técnica de S3 (reloj de CM2) y de la puerta ADR-0014 bajo orden ejecutiva del CEO"
tipo: "RESOLUCIÓN DEL DIRECTOR TÉCNICO por delegación expresa del CEO. NO es un voto del CEO registrado en `decisiones/`."
fecha: 2026-10-06
fuente_de_autoridad: "Orden del CEO (Mauricio) en sesión, 2026-10-06: «AURA — ORDEN DE CONTINUACIÓN EJECUTIVA» (transcrita en §0)"
relacion_con_el_DP: "DP-S3-RELOJ-CM2.md v4 (sha256 55d48642…) sigue siendo BORRADOR y DECISION_REQUIRED. Este documento no lo edita ni lo aprueba"
estado: "VIGENTE para el alcance técnico de §2. Los puntos de §3 siguen reservados al CEO"
---

# Resolución técnica de S3 bajo orden ejecutiva del CEO

## 0. Fuente de autoridad (transcripción literal de la orden, 2026-10-06)

> «Tu misión es tomar decisiones de ingeniería, implementar las soluciones autorizadas, probarlas, verificar su
> funcionamiento y avanzar con el Mapa Maestro.» · «Utiliza las recomendaciones preliminares del Director: Q1 A+B si son
> compatibles; Q2a diseño e implementación sin iniciar anticipadamente el reloj; Q5 como base de definiciones tras
> comprobar su consistencia; Q4 y E-Q1 para resolver la semántica de olvido y auditoría.» · «No des por resueltas Q2b, Q3
> o E-Q2 sin analizarlas.» · «Si falta una autorización formal para iniciar la medición, deja el mecanismo técnicamente
> preparado.» · «Si la solución exige resolver formalmente un conflicto entre la Bible y un ADR, no lo ocultes con un
> cambio de código: prepara la resolución conforme al gobierno canónico.» · «No registres votos inexistentes.»

La orden **delega las decisiones de ingeniería**; no sustituye las decisiones de soberanía ni de criterio de aceptación
que la Bible reserva al CEO (2.5:153-154; 1.1). Por eso este documento separa lo que resuelve (§2) de lo que deja
preparado para el CEO (§3).

## 1. Hallazgo previo que cambia el análisis `[EJEC]` 2026-10-06

Un eco marcado `retirada` (olvido o refutación) **sigue en los `hits` de `recall`**, también tras reiniciar
(`es_recuperable` solo mira `kind`). El orquestador lo filtra para el contexto del LLM (`_da_por_cierto`,
`orchestrator.py:2066`), pero **la puerta de ADR-0014 (`orchestrator.py:2026`) decide con los `hits` crudos**: si todo lo
recuperado está retirado, refutado o superseded, la puerta no dispara la ausencia determinista y el turno llega al LLM con
«(sin recuerdos relevantes)». El propio código lo declaraba «elevado como decisión».

## 2. Resoluciones técnicas (dentro de la delegación)

| Punto | Resolución | Justificación | Reversibilidad |
|---|---|---|---|
| **Puerta ADR-0014** | La puerta decide con las entradas **vigentes** (`_da_por_cierto`), no con los `hits` crudos. `recall`, `es_recuperable`, `_es_consulta_de_memoria` y el olvido **no cambian** | ADR-0014: la ausencia de memoria vigente es un hecho del Core y no se le da al LLM ocasión de completarla. Alinea la puerta con el filtro que ya aplica el contexto (una sola definición de «vigente» para decidir y para contextualizar). No borra nada: no toca E-Q1 ni D-AMP-3. El límite de `DP-COGNICION-LOCAL-Y-RENDIMIENTO.md` §9-10 era el perímetro de aquella inversión, no una regla permanente | Una línea; mutante declarado |
| **Q1** | **«A ahora + B tras la decisión de retención»** (alternativa literal del DP). Se construye **A**. B no se construye: crea un archivo de temas (retención nueva) que depende de una decisión de soberanía (§3) | A y B son compatibles como secuencia, no como construcción simultánea: B exige retención nueva | B se añade sin rehacer A |
| **Q2a** | **(i) diseño + (ii) implementación**, con TDD, mutación y Quality Gate. **(iii) inicio: NO**. El mecanismo queda listo y cerrado: la medición oficial exige un marcador de inicio que solo crea una orden explícita (`--iniciar-cm2`), que esta resolución no ejecuta | Orden literal del CEO: «sin iniciar anticipadamente el reloj» | El marcador no existe hasta que se cree |
| **Q2b** | **No por ahora** | Exige crear un enganche de fin de sesión que no existe (`cerrar_sesion` sin llamadores de producción); 2a basta para medir; añade una ejecución que nadie pide | Se reevalúa con datos de uso |
| **Q3** | **Indicador preliminar**. El criterio de aceptación de 2.5 **no se toca** | Contarlo como evidencia suficiente estrecharía 2.5 sin acta: eso no es ingeniería, es criterio de aceptación (2.5:153-154). «Indicador preliminar» es la única opción que no cambia ningún criterio | Si el CEO decide otra cosa, solo cambia la lectura del informe |
| **Q5 (base provisional y revisable)** | §5.2 del DP como base, con: **población** = hechos declarados **tipados** (`HECHO_DECLARADO` con atributo reconocido por `identidad_memoria`); los ecos episódicos quedan **fuera** (no tienen id, ni evento auditado, ni pregunta tipo, e incluirlos exigiría guardar contenido nuevo). **(a)** se excluyen del denominador **solo** las retiradas iniciadas por el usuario (olvido, refutación); cualquier otra desaparición cuenta como **no recuperada**. **(b)** revisión humana por muestreo: sin ella, «fabricación» se informa **no evidenciada**. **(c)** consulta = **pregunta tipo por atributo**, respondida por el Core sin LLM (`_responder_hecho`); sin paráfrasis almacenadas | Consistencia comprobada contra §5.2 y la propuesta (§7.1: la población A real son las declaraciones tipadas). Ninguna opción añade retención | Las reglas son parámetros (política de la tasa, mínimo), no constantes enterradas |
| **E-Q2** | **CM1 se mantiene en P50 ≤ 800 ms** (decisión del CEO 2026-09-28/29, sin cambio). La discrepancia con Bible 2.5:102 se **prepara** como resolución documental (§3), no se reescribe la Bible | Sustituir un criterio del CEO no es ingeniería | — |

### 2.1 Contrato del reloj de CM2 (lo que se implementa)

- **Identidad opaca del hecho (`hecho_id`):** `uuid4().hex` asignado en la **primera** declaración de una identidad
  (`identidad_de`) y **heredado** por sus versiones. Se guarda en la procedencia de la entrada, **aparte** de los cuatro
  campos de vigencia de D-AMP-1 = B, que no cambian. No se deriva del contenido.
- **Eventos de auditoría del módulo `cm2`, sin texto** (`obs.log(..., audit=True)` con campos estructurados):
  - `cm2.hecho_registrado`: `hecho_id`, `version`, `valid_from`;
  - `cm2.hecho_retirado`: `hecho_id`, `causa` ∈ {`olvido`, `refutacion`} (retirada iniciada por el usuario);
  - `cm2.sonda`: `hecho_id`, `dia` ∈ {7, 14, 28}, `edad_dias`, `version_edad_dias`, `estado_retirada` (en bruto),
    `resultado` ∈ {`vigente`, `valor_retirado`, `nada`, `sin_consulta`}, `n_entradas_memoria` (covariable de
    interferencia).
- **Calendario regenerable:** se reconstruye leyendo el audit log completo (segmentos + activo, ordenados por `seq`). Sin
  cursor ni estado propio. Idempotente: un `(hecho_id, dia)` ya sondeado no se repite; eventos duplicados no duplican.
- **Fecha de origen:** `max(valid_from de la primera versión, ts del evento cm2.inicio)`; una redeclaración no la
  reinicia y **el tiempo anterior al inicio no cuenta** (orden ejecutiva post-S3, 2026-10-07: «evite contar tiempo
  anterior a ese evento»). Sin `cm2.inicio` no hay calendario. Lo mismo para la edad de la versión.
- **Procedimiento de inicio:** `PROCEDIMIENTO-INICIO-CM2.md` (preparado; no autoriza el inicio).
- **Sonda:** lee la memoria y el modelo de usuario, construye la pregunta tipo del atributo y la responde con
  `_responder_hecho`. **No escribe memoria** (corpus idéntico antes y después) y **no llama al LLM**.
- **Tasa:** función pura sobre las sondas de día 28. La política de retirados es un parámetro. Devuelve
  **«sin datos suficientes»** por debajo del mínimo provisional o sin sondas a 28 días (INV-9). Nunca afirma «cero
  fabricación».
- **Inicio:** es un **evento de auditoría `cm2.inicio`** (append-only, regenerable), emitido solo por
  `--iniciar-cm2 --confirmo-inicio`. Sin ese evento en el historial, `--medir-cm2` informa «NO iniciado» y no emite sondas.
  Un segundo inicio es idempotente. *(Primera versión: un fichero marcador `CM2_INICIO`; se descartó porque abría una
  ruta de escritura directa que G-1 R-B acusa y que exigiría una declaración aprobada en `architecture_manifest.toml`.)*
- **Paradas:** la sonda solo lee y audita; no ejecuta ninguna acción del Motor Único. Con el kill switch (b) armado
  produce las mismas sondas que sin él (prueba con control). La PARADA (a) del control-plane **no aplica**: `--medir-cm2`
  no forma parte del ciclo autónomo del control-plane ni lo invoca.

### 2.2 Las cinco fases, separadas

1. **Mecanismo implementado** — objetivo de esta resolución.
2. **Integración y validación** — pruebas, mutación, Quality Gate, ECC.
3. **Inicio oficial** — `--iniciar-cm2`: **NO autorizado** por esta resolución.
4. **Cuatro semanas naturales transcurridas** — no se simulan: solo el calendario real las produce.
5. **Evaluación final** — CEO (2.5:153-154).

## 3. Reservado al CEO (no se implementa; resolución preparada)

| Punto | Por qué no es ingeniería | Qué se necesita |
|---|---|---|
| **Q4 (D-AMP-3)** y **E-Q1** — persistencia física del texto olvidado | Contradicción entre Bible 5.5 §3 (borrado verificable del dato y su rastro) y G-6 / G-7 / ADR-0023 / ADR-0017 (append-only). Resolverla con código ocultaría el conflicto | Decisión de soberanía del CEO o Alerta de Arquitectura (2.5:32). La corrección de la puerta (§2) **no depende** de esto |
| **B de Q1** (marcado explícito) | Crea retención nueva (archivo de temas) | Decisión de retención |
| **Inicio oficial (Q2a(iii))** | El CEO lo excluyó expresamente | Orden explícita; entonces `--iniciar-cm2` |
| **E-Q2 documental** | Alinear la Bible 2.5:102 con «CM1 = 800 ms» toca la Bible | Resolución documental del CEO |
| **Error del DP v4 (:48-49)** | Editar el DP | Autorización para corregirlo: dice «propuesto» de un umbral que 2.5:32 declara ratificado |

## 4. Registro

| Fecha | Cambio |
|---|---|
| 2026-10-06 | Primera versión, por orden ejecutiva del CEO en sesión |
| 2026-10-07 | Fecha de origen recortada al inicio del reloj; procedimiento de inicio preparado |
