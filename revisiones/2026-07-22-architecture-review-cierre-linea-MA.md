---
documento: "Architecture Review / Executive Summary — Cierre de la linea MA (Madurez de Arquitectura)"
fecha: 2026-07-22
autor: "CTO"
encargo: "CEO — sintetizar las decisiones permanentes, los cambios estructurales y el estado arquitectonico alcanzado; sera la nueva linea base"
base: "main @ 3b7bc6f (origin/main sincronizada)"
estado: "Linea base. Vigente hasta que una revision posterior lo supere."
---

# Cierre de la linea MA — Madurez de Arquitectura

La linea MA nacio de D39 (*desarrollo continuo con restricciones de hardware*): madurar la
arquitectura con el hardware actual para que, al llegar el equipo objetivo, solo haya que **habilitar**
capacidades, no construirlas. Se cierra completa: **MA.1 · MA.2 · MA.3 · MA.4 · MA.5-a · MA.5-b**, toda
integrada en `main` y publicada, con Quality Gate **PASS (303 passed / 3 skipped)** y sin regresiones.

## 1. Decisiones permanentes

| Decisión | Qué establece (permanente) |
|---|---|
| **D40** | **Arranque y composicion.** Punto de entrada unico de produccion (`python -m aura_skeleton`); la composicion **ensambla, no decide** (declarativa); **observabilidad de arranque** (AURA indica siempre que cree activo antes de operar). Todo ejecutable consume la composicion o es un arnes declarado. |
| **ADR-0018** | **Bus de eventos por escenario.** `InProcessEventBus` es el bus oficial de **E1** (personal, un proceso); `NatsEventBus` queda reservado a **E2** (multi-proceso/hogar). La **sustituibilidad** (P-ARQ-4) sigue siendo requisito, no obligacion de E1. Refina ADR-0006 sin revocarlo; consistente con Bible 3.3. |
| **D41** | **Fuente unica de verdad.** Ninguna lista de excepciones arquitectonicas se duplica entre docs, codigo y pruebas. Toda clasificacion estructural vive en un manifiesto versionado que las herramientas de validacion consumen (`architecture_manifest.toml`). |
| **ADR-0019** | **Habilitacion y transparencia de conectores externos.** Marco **generico** (sin conectores reales): auto-declaracion externo/local, opt-in explicito por config del usuario, `DeclaracionTransparencia` obligatoria y versionada, y ninguno como requisito (degradacion limpia). Extiende ADR-0015 de forma aditiva. |
| **D42** | **Pendiente de contrato ≠ codigo muerto.** Un elemento clasificado como implementacion pendiente de un contrato se identifica de forma explicita en la documentacion arquitectonica y **no vuelve a considerarse "codigo muerto" mientras el contrato siga vigente**. Solo se elimina con evidencia de absorcion/convergencia o de ausencia de contrato. |

## 2. Cambios estructurales por fase

- **MA.1 — Punto de entrada unico.** `composicion.py` (el unico cableado del sistema) + `__main__.py`
  (`python -m aura_skeleton`, con `--verificar`). Politica HITL extraida a `adapters/hitl_consola.py`
  (la composicion dejo de contener logica funcional, D40).
- **MA.2 — Memoria escalable.** `PersistentMemory` con persistencia **JSONL incremental** (append O(1))
  e **indice invertido** con salto de terminos ubicuos. Coste plano con el volumen. **ADR-0011 (Qdrant)
  no se reabrio**: la deuda era de indice/persistencia, no de busqueda semantica.
- **MA.3 — Rotacion por archivo del audit log.** El registro forense (D9, inmutable) acota su
  crecimiento **sin borrar evidencia**: `seq` monotonico + sellado en segmentos con `sha256` +
  manifiesto + reconstruccion completa. Los conectores de senales pasan a un **cursor `seq`
  persistente**, robusto a rotacion y reinicio.
- **MA.4 — Conectores externos (infraestructura).** `core/conectores_externos.py`: mecanismo generico
  de opt-in + transparencia + degradacion (ADR-0019, D37). Gate minimo en `composicion` (no-op sin
  conectores externos). **Ningun conector real construido.**
- **MA.5-a — Convergencia validacion↔produccion.** `architecture_manifest.toml` (fuente unica, D41) +
  prueba anti-regresion por AST; `run_demo.py` **eliminado por convergencia arquitectonica** (no por
  desuso). ADR-0018 nacio aqui.
- **MA.5-b — Clasificacion, no eliminacion.** El subsistema de metricas resulto ser la implementacion
  **sin cablear** del contrato P-ARQ-7 (Bible 7.4). Se **conservo y clasifico** (codigo + D42); **cero
  eliminaciones**.

## 3. Estado arquitectonico alcanzado

- **Un solo camino de arranque** (D40): produccion consume `composicion`; los arneses estan declarados
  en un manifiesto (D41) que una prueba anti-regresion hace cumplir. La divergencia validacion↔produccion
  que la auditoria del 2026-07-21 midio queda **cerrada y blindada**.
- **Memoria** que no degrada con anos de historial, sin anadir servicios externos (ADR-0011 intacto).
- **Audit log forense** con almacenamiento acotado por archivo, inmutabilidad preservada (D9) y una
  base de senales fiable para la futura anticipacion (M3.3).
- **Marco de conectores externos** listo (opt-in, transparencia, degradacion) sin haber construido
  ninguno: al aprobarse el primer conector, el consentimiento y la transparencia ya existen.
- **Gobierno reforzado:** D41 (una sola fuente de verdad para clasificaciones) y D42 (lo pendiente de
  contrato no se borra por parecer muerto) son ahora reglas permanentes.
- **Neutralidad tecnologica y de escenario** consolidada: bus por escenario (ADR-0018), memoria sin
  base vectorial hasta que haya evidencia, conectores externos opcionales y transparentes.

## 4. Lo que la linea MA NO cambio (frontera honesta)

- **Product Readiness: 41%** (cierre de M2). La linea MA fue madurez de **arquitectura**, no capacidad
  de cara al usuario; no mueve la cifra.
- **HC-1 (latencia e2e): ABIERTO.** No certificable en el hardware actual; pendiente del entorno objetivo.
- **Diferido a hardware/entorno fisico (D39):** M3.1 (Home Assistant real), M3.2b (inferencia), M3.3
  (anticipacion), M3.4 (avatar). La arquitectura queda **lista** para habilitarlos.
- **Contrato pendiente registrado:** metricas basicas (P-ARQ-7 / Bible 7.4) documentadas pero sin
  cablear (D42). Realizarlas es una iniciativa funcional independiente.

## 5. Nueva linea base

Estado publicado y verificado: **`main == origin/main` @ `3b7bc6f`**, arboles limpios, 0 commits sin
publicar, Quality Gate PASS. ADRs vigentes: 0001-0019 (`accepted`). Acta hasta **D42**.

Este documento es la referencia arquitectonica de partida para la siguiente etapa. La incorporacion de
cualquier conector concreto, la realizacion del contrato de metricas, o la validacion en hardware
(HC-1, M3.1/3.2b) seguiran requiriendo su propia decision y aprobacion.
