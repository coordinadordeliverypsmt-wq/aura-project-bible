---
adr: 22
titulo: "Gestión de artefactos de IA: entorno + manifiesto declarativo + ModelResolver"
estado: accepted
fecha: 2026-07-28
decide: "CEO"
propone: "CTO / Director"
supersede: null
relacionado: "ADR-0016 (neutralidad tecnológica), ADR-0010/0012/0013 (runtimes LLM/STT/TTS), ADR-0020 (memoria por niveles), Bible 3.4 (manifiesto de plugin), D24 (stack local-first, beneficio medible), INV-6 (invariantes del modelo de activación)"
---

# ADR-0022 — Gestión de artefactos de IA

## Decisión

Los **artefactos de modelos de IA** (embeddings, STT, TTS, LLM, y los que existan en el futuro) se
gestionan mediante **entorno + manifiesto declarativo**, no dentro del código ni del repositorio. Este
ADR define **exclusivamente** tres piezas mínimas, y **nada más**:

### 1. Manifiesto mínimo de artefacto

Cada artefacto que AURA use se describe con un manifiesto declarativo que contiene, como mínimo:

- **`id`** — identificador estable del artefacto (p. ej. `embedder.multilingual-minilm-l12-v2`).
- **`version`** — **SemVer** (política de deprecación de ADR-0004: máx. 2 versiones mayores vivas).
- **`checksum`** — **SHA-256** del/los fichero(s) del artefacto.
- **`licencia`** — identificador de licencia (p. ej. `Apache-2.0`, `MIT`).
- **`source`** — **procedencia** del artefacto: de dónde se obtuvo y desde dónde puede reponerse
  (*enmienda del CEO, 2026-08-02*).
- **`contrato_tecnico`** — lo que el consumidor necesita para funcionar: p. ej. dimensiones de salida,
  formato (`onnx` + `tokenizer.json`), interfaz esperada. Es el **contrato**, no el binario.

> **Por qué `source` es obligatorio y no opcional** (enmienda 2026-08-02). **Integridad y recuperación son
> garantías distintas.** El `checksum` responde *"¿este binario es el que declaro?"*; `source` responde
> *"y si desaparece, ¿de dónde vuelve?"*. La revisión estratégica del 2026-08-02 encontró el caso real: el
> manifiesto del embedder multilingüe permitía **verificar** el artefacto pero no **reponerlo**, porque no
> registraba su origen. Un campo opcional que casi nadie rellena no da trazabilidad, solo la aparenta: por
> eso `cargar_manifiesto` rechaza un manifiesto sin `source`, con prueba que lo fija.
>
> Sigue siendo **dato declarativo**: el `ModelResolver` **no descarga nada** — la descarga automática
> permanece fuera de alcance por decisión normativa de este ADR.

El manifiesto es **datos declarativos** (serializable), coherente con el principio de independencia del
catálogo. Vive en la **infraestructura**, nunca dentro de una `Capacidad`.

### 2. Un único `ModelResolver`

Un componente único con **una sola responsabilidad**: dado el manifiesto de un artefacto,

- **localizar** el artefacto en el entorno;
- **verificar integridad** (SHA-256 contra el manifiesto);
- **comprobar compatibilidad** (que el artefacto satisface el `contrato_tecnico`);
- **entregar la ruta válida** al consumidor.

El `ModelResolver` no descarga de forma "inteligente", no cachea en varios niveles, no gestiona
múltiples proveedores ni resuelve dependencias complejas. Localiza, valida y entrega. Nada más.

### 3. Bootstrap

El **bootstrap** de AURA **materializa el entorno a partir del manifiesto**: coloca cada artéfacto
declarado en su ubicación y deja el sistema en un estado en el que el `ModelResolver` puede resolverlos.
Extiende el patrón que los instaladores actuales ya usan (`entorno/scripts/install-linux.sh` hace
`ollama pull`), **añadiéndole la verificación de integridad que hoy no existe**.

## Principio protegido (permanente)

> **Las capacidades nunca conocen modelos concretos. Una capacidad declara únicamente el _contrato
> funcional_ que necesita. La infraestructura decide qué artefacto satisface ese contrato.**

Este principio es **normativo** y queda protegido por este ADR porque **preserva ADR-0016** (neutralidad
tecnológica: el Core es independiente del modelo) e **INV-6** (la relación de una capacidad con sus
realizaciones tecnológicas pertenece a la infraestructura, fuera del modelo de capacidades). El
`ModelResolver` y el manifiesto son **infraestructura**; el Capability Registry permanece limpio de
nombres de modelos.

## Contexto (evidencia del repositorio, no supuestos)

Auditoría del 2026-07-28 (método D47: Operario + Ingeniero + Director):

- **[EJECUCIÓN]** Cero modelos versionados en git ni git-LFS; ~6.8 GB de artefactos viven en el entorno
  (USB + `~/.ruvector` + `~/.local` + caché de HuggingFace). El almacén de Ollama (~6.5 GB) lo gestiona
  el propio Ollama.
- **[LECTURA]** Cuatro convenciones **distintas** de localización, una por consumidor, sin unificar:
  `AURA_EMBED_MODEL_DIR` (directorio + `model.onnx`/`tokenizer.json`), `AURA_LLM_MODEL` (etiqueta a un
  servicio), `AURA_PIPER_VOICE` (ruta a un `.onnx`), `AURA_STACK_REAL` (interruptor de modo). No existe un
  componente común de resolución.
- **[LECTURA]** **Ninguno** de los cuatro consumidores valida **checksum, versión o licencia** del
  artefacto antes de cargarlo. La maquinaria `sha256` del proyecto existe solo para audit log y backups de
  datos de usuario, **no para modelos**. `AURA_LLM_MODEL=qwen2.5:3b` es una **etiqueta mutable** (versión
  implícita).
- **[LECTURA]** `install-linux.sh`/`install-macos.sh` descargan modelos (`ollama pull`) **sin verificación
  de integridad**.
- **[EJECUCIÓN]** La Fase 0 de N2 demostró que un modelo distinto es **sustituible sin tocar código** vía
  `AURA_EMBED_MODEL_DIR` (el embedder multilingüe fue drop-in): evidencia de que lo que el código necesita
  es el **contrato**, no el binario.

El problema demostrado es concreto: **fragmentación de convenciones, ausencia de integridad, versiones
implícitas y etiquetas mutables.** Este ADR resuelve exactamente eso.

## Alternativas consideradas

| Alt. | Descripción | Veredicto |
|---|---|---|
| **A** | Modelos en el repositorio (git / git-LFS) | **Rechazada.** ~6.8 GB, licencias heterogéneas (redistribución), git-LFS exige servidor/ancho de banda → incoherente con D24 (local-first) y el tamaño real. |
| **B** | Solo entorno, ad-hoc (statu quo) | **Insuficiente.** Su núcleo es correcto (binarios fuera del código), pero no resuelve integridad, versión, licencia ni unificación. Es la deuda que este ADR cierra. |
| **C** | **Entorno + manifiesto declarativo + ModelResolver** | **ADOPTADA.** Conserva el núcleo correcto de B y añade lo que falta, realizando principios ya normados (ADR-0016, Bible 3.4). |

## Fuera de alcance (exclusiones explícitas)

Este ADR **NO** incluye, y su implementación futura **no** deberá introducir sin un ADR propio con
beneficio medible (D24):

- sistema general de plugins;
- marketplace de modelos;
- descubrimiento dinámico;
- registro distribuido;
- resolución automática de dependencias complejas;
- descarga "inteligente";
- cachés multinivel;
- gestión de múltiples proveedores;
- cualquier otra infraestructura cuyo beneficio no esté demostrado por evidencia.

El manifiesto de plugin completo de Bible 3.4 (sandbox, firma, SBOM, ciclo de vida, descubrimiento)
**no** se construye aquí: este ADR toma **solo** la parte de artefactos (id/versión/checksum/licencia/
contrato) y la resolución.

## Consecuencias

- Las cuatro convenciones ad-hoc convergen en **un** mecanismo (`ModelResolver` + manifiesto).
- Aparece, por primera vez, **verificación de integridad, versión y licencia** de los modelos antes de
  usarlos.
- La **sustitución por un artefacto compatible** deja de ser una convención frágil y pasa a estar
  respaldada por el `contrato_tecnico` del manifiesto.
- **Primer consumidor real:** el embedder multilingüe de la Fase 1 de N2. N2 permanece cerrada; su Fase 1
  se retomará **después** de aprobar este ADR y usará este mecanismo, pero **no condiciona** el diseño.
- Toda capacidad futura (LLM, STT, TTS, visión, OCR, embeddings y las que aún no existan) declara un
  contrato y delega el artefacto en la infraestructura: el patrón se reutiliza sin re-decidir.

## Impacto (acta D11 — obligatorio)

- **Seguridad:** **mejora.** La verificación SHA-256 impide cargar un artefacto corrupto o manipulado —
  hoy inexistente para modelos.
- **Privacidad:** neutra/positiva. Local-first (ADR-0001/D24); sin llamadas a terceros salvo la descarga
  inicial ya autorizada por el bootstrap.
- **Modularidad:** **mejora.** Formaliza el desacoplamiento capacidad↔modelo (ADR-0016, INV-6).
- **Costo:** mínimo. Reutiliza la maquinaria `sha256` existente; el manifiesto son datos; el resolver es
  una función de resolución sin estado.
- **UX:** transparente para el usuario final; el bootstrap deja el entorno listo.
- **Mantenimiento:** **mejora.** Una convención en lugar de cuatro; el punto de cambio de modelo es el
  manifiesto, no el código.

## Riesgos aceptados

- **Abstracción prematura.** Con cuatro consumidores, un mecanismo nuevo podría sobredimensionarse.
  **Mitigación:** el alcance está deliberadamente reducido al manifiesto mínimo y a un resolver de una
  sola responsabilidad; las exclusiones son normativas.
- **Punto único (`ModelResolver`).** **Mitigación:** es una función de resolución determinista, sin estado
  retenido; su fallo (artefacto ausente/corrupto) degrada de forma explícita, como ya hace hoy la
  composición de N2 al caer a N1.

## Estado

**ACEPTADA (CEO, 2026-07-28).** Este ADR define la decisión y su alcance; **no** autoriza la implementación
del `ModelResolver`. La implementación será un trabajo posterior con su propio gate, bajo la disciplina
estándar (TDD, Quality Gate) y respetando estrictamente las exclusiones de este documento. Su primer
consumidor será la Fase 1 de N2 (embedder multilingüe), que se retomará tras aprobar el plan de
implementación mínimo correspondiente.

**Nota de gobernanza (CEO, 2026-07-28):** ADR-0022 es el **último ADR** antes de volver al desarrollo
funcional. No se abren nuevos ADR durante la implementación salvo que aparezca evidencia que demuestre que
una decisión arquitectónica es imprescindible.
