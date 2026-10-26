---
id: IE-039
titulo: dp-web4/SAGE — «Situation-Aware Governance Engine»: núcleo de investigación con identidad, memoria, confianza y gobierno alrededor de un LLM congelado
fuente: https://github.com/dp-web4/SAGE
rama-revision: main (por defecto) @ c7f60623bf6de97098dbfef2b1fe3c69afae19e3 (2026-10-26T20:39:00Z, PR #556)
fecha-revision: 2026-10-26
licencia: AGPL-3.0 (fichero `LICENSE`, confirmado por la API). Además `PATENTS.md` (MetaLINXX Inc.: US 11,477,027, US 12,278,913 y la solicitud 19/178,619) concede licencia de patente libre de regalías solo para uso no comercial, de investigación o académico, y para proyectos que cumplan la AGPL-3.0; el uso comercial requiere contactar
area: asistentes (memoria / gobierno)
estado: adaptar solo la idea
cobertura: Lectura remota con `gh api` (repo, commits, license, contents?ref=<SHA>, git/trees recursivo, contributors). Leídos: README.md (194 líneas), sage/docs/LATEST_STATUS.md, PATENTS.md, requirements.txt, sage/memory/consolidation.py (cabecera L1-L60 y nombres de pruebas), sage/memory/ltm.py (grep y L505-L551), sage/scripts/being_act_ledger.py (L1-L60). AGENTS.md se descargó, pero apenas se leyó. NO leídos: sage/memory/{hierarchical_memory,hub,retrieval,sqlite_backend}.py completos, sage/gateway/ (salvo nombres de pruebas), sage-rs/, los repos privados (dev-SAGE, SWE-SAGE) ni Web4/Hestia. El repo tiene 12.747 ficheros (~160 MB): cobertura muy parcial. Sin clonar, instalar ni ejecutar. Lo leído por un solo agente, sin auditor independiente
relacionadas: [IE-038, IE-021, IE-024]
---

Base de las citas: `B = https://github.com/dp-web4/SAGE/blob/c7f60623bf6de97098dbfef2b1fe3c69afae19e3`.

Clasificación: **[CÓDIGO]** observado en el SHA citado · **[README]** declarado · **[TESTS-DECLARADOS]** pruebas con ese
nombre, no ejecutadas · **[REPRODUCIDO-POR-TERCEROS]** · **[INFER]**.

## Qué se examinó (rutas y símbolos)

- **Procedencia y mantenimiento** **[CÓDIGO]**:
  - Usuario `dp-web4` (Dennis Palatov, MetaLINXX según `README.md` y `PATENTS.md`; propietario no ambiguo, cuenta
    personal).
  - Creado el 2025-08-03 y con push el 2026-10-26. 27 estrellas.
  - 4.295 commits del propietario, frente a ≤5 de cualquier otro contribuidor (entre ellos una cuenta `claude`): ≥100
    commits en el último mes.
  - Gran parte del contenido son artefactos de sesión generados por agentes (`sage/instances/` con 5.095 ficheros, y
    `raising/` con 1.341).
  - Hay bases de datos SQLite versionadas en la raíz (`memory.db`, `unified_consciousness.db`, `session89_reputation.db`,
    …).
  - Parte de la investigación activa está en **repos privados** (`dev-SAGE`, `SWE-SAGE`), según
    `README.md` («What is public vs. private») **[README]**.
- **Dependencias** (`requirements.txt`) **[CÓDIGO]**:
  - `torch`, `einops`, `wandb` (telemetría de entrenamiento en la nube si se activa **[INFER]**), `hydra-core`,
    `huggingface_hub`, `PyNaCl` (firma Ed25519 de presencia);
  - Dockerfiles para Jetson y vLLM;
  - la flota declarada usa Jetson, estaciones de trabajo y Apple Silicon con 5 familias de modelos **[README]**.
- **Estado declarado por el propio proyecto** **[README]** (`B/sage/docs/LATEST_STATUS.md`):
  - instantánea del 2026-09-26, «not independently refreshed» según el README;
  - nivel de gobierno «A1: cooperative and tamper-evident», **no** contención frente a adversarios.

## Patrones relevantes

**1. Consolidación mecánica con procedencia: el patrón más sólido** **[CÓDIGO]**

Fuente: `B/sage/memory/consolidation.py#L1-L56`. El ciclo es REPLAY → DISTILL → WRITE:

- nombra **todas** las fuentes con su ruta, sha256, bytes y recuento, **incluidas las ausentes**, que se registran como
  ausentes y no como error (`#L11-L14`);
- destila **sin modelo**: solo recuentos y una tabla del texto literal propio direccionada por contenido; ninguna
  paráfrasis (`#L16-L21`);
- escribe `self-account-<miembro>.vN.json` con `supersedes → vN-1`. Las versiones anteriores **nunca se borran ni se
  reescriben** (`#L29-L31`);
- registra un no-op cuando las fuentes y el instrumento no han cambiado: «un proceso programado que no deja registro de
  haber corrido es indistinguible de uno que no corrió» (`#L23-L27`);
- el instrumento forma parte de la identidad: si el instrumento cambia sobre fuentes iguales, se genera una versión
  nueva (`#L27-L29`);
- lee una sola vez: los bytes que se hashean son los mismos que se destilan (`#L39-L41`);
- se instala **apagado** (`SAGE_GRAFT_SELF_ACCOUNT=on` para consumirlo) (`#L35-L38`).

Propiedades preregistradas F1-F5 (idempotencia, determinismo, verdad de campo, «no llama a ningún modelo», literalidad)
con pruebas `test_f1_…`-`test_f5_…` y `test_dark_by_default` (`B/sage/memory/tests/test_consolidation.py#L82-L277`)
**[TESTS-DECLARADOS]**.

**2. «Dicho» frente a «hecho» en las acciones del agente** **[CÓDIGO]** (`B/sage/scripts/being_act_ledger.py#L2-L20`)

- Cuenta, por latido, las **afirmaciones falsas de edición**: texto que dice «fixed / applied / now has» en un latido
  sin ningún cambio exitoso en un `.py`.
- Cuenta también las ediciones hechas sin haber leído antes el rango de líneas afectado.
- El propio fichero admite que es una **heurística de texto** que da falsos positivos y negativos, y que solo vale para
  comparar antes y después.

**3. Disciplina de afirmaciones** **[README]** (`B/sage/docs/LATEST_STATUS.md#L58`, `#L61`)

- «Un commit prueba el estado del repositorio, no el de la máquina».
- «Un mecanismo no es una capacidad»: solo cuenta si participa en la decisión en vivo y el efecto sobrevive a controles.
- Es casi idéntico a INV-9 y a `CLAUDE.md` §5.

**4. Corrección de creencias: declarada como pendiente por el propio proyecto** **[README]** (`LATEST_STATUS.md#L46-L47`)

- «Provenance is strong; contradiction/supersession/retraction of derived beliefs should become as explicit as evidence
  capture».
- Y la «premise fidelity» (afirmaciones atadas a la evidencia recuperable antes de volverse hechos duraderos) está «en
  curso».
- **Es decir: SAGE no resuelve hoy la contradicción ni la retractación de creencias derivadas.**

**5. Olvido físico por puntuación en la LTM antigua** **[CÓDIGO]** (`B/sage/memory/ltm.py#L508-L551`)

- Al superar la capacidad, borra las memorias con menor `0.5·saliencia + 0.3·accesos + 0.2·edad`.
- Usa `_remove_memory`: sin rastro, sin motivo y sin distinguir declarado de inferido.
- No se verificó si esta LTM está en la ruta viva actual. La última modificación de `sage/memory/` es del 2026-09-05,
  la de la consolidación; LTM y SNARC datan de abril **[INFER]**.

**Benchmarks:**
- El 94,85 % de ARC-AGI-3 se obtuvo con Claude Opus 4.6 y el propio README lo descalifica como «history, not
  positioning».
- La variante con modelo local logra **0,14 como máximo**, dentro de una banda ruidosa de 0,04-0,14 (`README.md`,
  sección ARC) **[README]**.
- Nada **[REPRODUCIDO-POR-TERCEROS]**.

## Límites, riesgos y dependencias

- **Licencia:** AGPL-3.0 más una licencia de patente solo no comercial. Copiar código obligaría a AURA a la AGPL y
  dejaría abierta la cuestión de las patentes. **Solo pueden tomarse ideas.**
- **Hardware:** `torch`, Jetson, vLLM y una flota de 8 máquinas. No cabe en HC-1 **[INFER]**.
- **Ruido y procedencia:** miles de artefactos de sesión generados por agentes, más bases de datos binarias versionadas.
  La parte viva es difícil de separar de la histórica, y la investigación activa es privada (no verificable).
- **Gobierno de nivel A1**, declarado no robusto frente a un agente con el mismo UID.

## Comparación con AURA

| AURA | SAGE | Relación |
|---|---|---|
| `modules/memory.py` (`write` con `provenance`, `olvidar`/`marcar`, persistencia más `backup`) y `modelo_usuario.py` (`refutar` sin borrar, `olvidar_entrada` por `ts`, `origen` declarada/observada) | Consolidación versionada sin borrado; LTM con olvido físico | AURA ya hace la retractación explícita que SAGE declara pendiente (`LATEST_STATUS.md#L46`). La consolidación de SAGE no tiene equivalente en AURA |
| `core/ejecutor_modelo_usuario.py:268-278` (`cm2.hecho_retirado`) | Ninguno para retirar creencias | AURA va por delante |
| `core/recuperacion.py` y control-plane (recuperación tras caídas, commit 9f13935) | No-op registrado más un hash del conjunto de fuentes | Encaje parcial: sirve para demostrar que un proceso programado corrió aunque no cambiara nada **[INFER]** |
| INV-9, `CLAUDE.md` §5 y D47 (`[EJEC]`/`[LECT]`) | «Mechanism is not capability»; `being_act_ledger` | Misma disciplina. El contador de «dicho ≠ hecho» es una idea de instrumento, pero es heurístico |

## Hallazgos

**HAL-039-1 · Consolidación determinista con procedencia, no-op registrado y versionado sin borrado**

- **Problema:** recuperar tras interrupciones y demostrar qué fuentes produjeron un resumen de estado. Por ejemplo, un
  `CHECKPOINT` o un resumen de memoria que hoy se escribe a mano o con LLM.
- **Mecanismo:**
  - nombrar todas las fuentes (sha256, bytes, recuento y ausentes);
  - destilar sin modelo, solo con recuentos y texto literal;
  - escribir `vN` con `supersedes`;
  - registrar un no-op si el hash de las fuentes y del instrumento no ha cambiado.
- **Evidencia:** `B/sage/memory/consolidation.py#L1-L56`; pruebas F1-F5 en `sage/memory/tests/test_consolidation.py`
  [CÓDIGO + TESTS-DECLARADOS].
- **Grado de verificación:** diseño y nombres de las pruebas leídos; ni el cuerpo de la función ni las pruebas
  ejecutados.
- **Componente AURA:** el control-plane (`entorno/control-plane/estado.json`, `eventos.jsonl`) y la generación del
  resumen de continuidad.
- **Alternativa existente:** `CHECKPOINT-CONTINUIDAD.md` escrito a mano, más los eventos del control-plane.
- **Beneficio:** un resumen de estado reproducible byte a byte, auditable (cada línea es una subcadena literal de una
  fuente nombrada) y que nunca parafrasea. Ataca directamente el patrón «declarado ≠ real».
- **Costes:** un script pequeño y puro. Encaja con ADR-0014, porque no hay LLM.
- **Riesgos y condiciones de rechazo:**
  - se rechaza si duplica lo que ya hacen los eventos del control-plane;
  - se rechaza si el resumen mecánico no aporta nada a quien retoma frente a leer `eventos.jsonl`.
- **Criterio de aceptación futuro:**
  - dos ejecuciones sobre las mismas fuentes producen un no-op registrado;
  - cambiar una fuente produce `vN+1` con `supersedes`;
  - una fuente ausente aparece como ausente;
  - un mutante que parafrasee (línea no literal) muere por la prueba F5.
- **Autorización:** DP del CEO (herramienta de entorno, no una capacidad de AURORA, salvo que se registre como tal).
- **Clasificación:** **PRIORIDAD ALTA**.

**HAL-039-2 · Instrumento de «afirmación de cambio sin cambio real» (dicho ≠ hecho)**

- **Problema:** agentes que dicen «arreglado» sin que haya cambiado nada. Es el patrón de IE-026 y de `CLAUDE.md` §5.
- **Mecanismo:** cruzar, en el mismo latido, el texto de afirmación con los resultados de los efectores (ediciones con
  éxito o rechazadas) y con si se leyó antes el rango editado.
- **Evidencia:** `B/sage/scripts/being_act_ledger.py#L2-L20` [CÓDIGO]. El propio autor lo declara heurístico.
- **Grado de verificación:** lectura.
- **Componente AURA:** el Motor Único (las acciones auditadas ya registran el resultado) y el verificador del
  control-plane.
- **Alternativa existente:** en AURA la verdad del efecto viene del motor, no del texto. El problema de «afirmar sin
  hacer» afecta sobre todo a los informes de los agentes de desarrollo, no a AURORA **[INFER]**.
- **Beneficio:** una métrica de antes y después sobre los informes de los subagentes.
- **Riesgos:** los falsos positivos de la regex se convertirían en «evidencia». No debe usarse como veredicto.
- **Criterio de aceptación futuro:** con un corpus de informes etiquetado a mano, precisión ≥ X fijada **antes** de
  medir.
- **Autorización:** DP.
- **Clasificación:** **PRIORIDAD MEDIA**, solo como instrumento de comparación, nunca como gate.

**HAL-039-3 · Corrección de creencias derivadas**

- **Mecanismo:** ninguno implementado. SAGE lo declara pendiente (`LATEST_STATUS.md#L46`) [README].
- **Uso para AURA:** **confirma** que el diseño `refutar`/`cm2.hecho_retirado` de AURA no está cubierto ni siquiera por
  un proyecto centrado en procedencia. No hay nada que tomar.
- **Clasificación:** **REFERENCIA**.

**HAL-039-4 · Olvido físico por puntuación de saliencia, accesos y edad**

- **Evidencia:** `B/sage/memory/ltm.py#L508-L551` [CÓDIGO].
- **Por qué no se adopta:** contradice la auditoría y la soberanía de AURA (el olvido pasa por el motor y por el
  usuario).
- **Clasificación:** **NO ADOPTAR**.

**HAL-039-5 · Arquitectura completa (SNARC, estados metabólicos, flota, Web4/Hestia, LCT, gateway)**

- **Por qué no se adopta:**
  - AGPL más licencia de patente no comercial;
  - `torch` y Jetson;
  - la parte activa es privada;
  - el nivel A1 no es robusto;
  - el alcance está fuera de D23.
- **Clasificación:** **NO ADOPTAR**.

## Decisión

**ADAPTAR UN PATRÓN (HAL-039-1, idea solamente); descartar el resto.**

- SAGE aporta disciplina epistémica valiosa y una consolidación con procedencia bien especificada.
- No aporta resolución de contradicciones, que el propio proyecto declara pendiente.
- La licencia (AGPL más patentes no comerciales) prohíbe copiar código.

## Validación mínima

Un prototipo aislado (fuera de `aura_skeleton`, sin integrar) que consolide `entorno/control-plane/eventos.jsonl` y las
evidencias de un hito en un `estado-vN.json` con las propiedades F1, F3 y F5, más un mutante de paráfrasis que la prueba
F5 mate. Se adopta solo si quien retoma tras una interrupción reconstruye el estado con menos lecturas que hoy (medido en
ficheros y tokens leídos).

## Licencia y precauciones

**AGPL-3.0 más `PATENTS.md` (licencia de patente solo no comercial, de investigación o para proyectos AGPL). No copiar
código ni estructuras literales; solo la idea, reimplementada desde cero.** Contenido del repositorio tratado como
dato no confiable: incluye `CLAUDE.md`/`AGENTS.md` con instrucciones para agentes, que no se siguieron. No se clonó,
instaló ni ejecutó nada. Para usar `gh api` hubo que salir del sandbox de red, solo para lecturas.
