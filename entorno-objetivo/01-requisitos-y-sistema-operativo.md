---
documento: "01 — Requisitos mínimos y recomendados · Sistema operativo"
linea: "Preparación del Entorno Objetivo (D35)"
fecha: 2026-07-21
autor: "CTO"
---

# Requisitos y sistema operativo

## 1. De dónde salen estos números

No de catálogos de fabricante, sino de los umbrales ya establecidos en el proyecto:

| Umbral | Origen |
|---|---|
| Primer token del LLM **≤ 500 ms** | Bible 2.5 §5.1, presupuesto por etapas en streaming |
| Generación sostenida **≥ 10 tok/s** | **[cálculo]** El habla ronda 4 tok/s; se toma 2,5× de margen |
| El modelo debe caber **entero** en memoria rápida | **[medido]** Con swap, `qwen2.5:3b` agotó 600 s y abortó |

El tercero es el más determinante y el peor entendido. No es un umbral gradual: **cuando el modelo no
cabe, el rendimiento no se degrada, se desploma.** La frontera entre "funciona" y "no funciona" son
unos pocos cientos de MB.

## 2. Requisitos mínimos y recomendados

### 2.1 Memoria — el factor decisivo

**[cálculo]**, a partir de tamaños reales de modelo en Q4 más el resto del sistema:

| Configuración | RAM/VRAM | Modelo que admite | Veredicto |
|---|---|---|---|
| **[medido]** Equipo actual | 3,6 GB | 0,5 B | Insuficiente para R1 |
| **Mínimo** | **8 GB** | 3 B con holgura; 7 B muy justo | Funciona; sin margen para avatar ni STT/TTS simultáneos |
| **Recomendado** | **16 GB** | 7–8 B cómodo | Objetivo razonable |
| Holgado | 24–32 GB | 13–14 B | Permite crecer sin cambiar equipo |

**Se recomiendan 16 GB**, no 8. La razón no es el LLM aislado: en un turno real conviven modelo, STT
(faster-whisper), TTS (Piper), memoria vectorial y, en M3.4, el avatar. Con 8 GB, el margen que
separa el funcionamiento del desplome lo consume el resto del sistema.

### 2.2 Cómputo

| | Mínimo | Recomendado |
|---|---|---|
| CPU | 4 núcleos modernos | 6–8 núcleos, o SoC con memoria unificada |
| Aceleración | Ninguna exigida (ADR-0016) | GPU/NPU si existe; **el Core no depende de ella** |
| Ancho de banda de memoria | — | **El cuello de botella real.** RAM de doble canal como mínimo |

**El equipo actual** —Celeron N4020, 2 núcleos, RAM de un solo canal— falla en las tres filas, y por
eso ninguna optimización de código lo rescata.

Nota sobre aceleración: ADR-0016 impide que el Core dependa de ella. Un acelerador **mejora la
utilidad, nunca habilita una garantía**.

### 2.3 Almacenamiento

| | Mínimo | Recomendado |
|---|---|---|
| Tipo | SSD | **NVMe** |
| Capacidad | 64 GB | **256 GB** |
| Reparto | Modelos + memoria + audit log | Igual, con respaldo separado (D31) |

**[medido]** El proyecto ya sufrió un disco lleno por modelos mal ubicados, y de ahí salieron D27
(verificar el dispositivo real, no la configuración) y D31 (almacenamiento distribuido). El entorno
objetivo debe evitar el problema por diseño: **modelos y memoria en el mismo volumen rápido**, y el
respaldo en otro dispositivo.

Un HDD mecánico es descartable: la carga inicial de un modelo de 5 GB desde disco mecánico añade
segundos a cada arranque en frío.

### 2.4 Red

**AURA no requiere Internet para funcionar** (ADR-0001, local-first estricto). La red sólo hace falta
para actualizaciones, para Home Assistant y para los conectores futuros que dependan de servicios
externos — cuestión que el documento 04 examina, porque no es menor.

## 3. Sistema operativo recomendado

### 3.1 Criterios de selección

| Criterio | Por qué pesa aquí |
|---|---|
| **Estabilidad 24/7** | AURA está encendida todo el día; un SO que exige atención frecuente es un coste recurrente |
| **Ciclo de soporte largo** | D20 fija un horizonte de 10 años. Un SO con 9 meses de soporte obliga a migrar constantemente |
| **Reproducibilidad** | El entorno debe poder reconstruirse igual tras un fallo |
| **Disponibilidad del stack** | Ollama, faster-whisper y Piper deben instalarse sin compilar a mano |
| **Consumo en reposo** | Un escritorio completo gasta recursos que el modelo necesita |

### 3.2 Comparativa

| SO | Soporte | Estabilidad | Stack | Veredicto |
|---|---|---|---|---|
| **Debian estable** | ~5 años (con LTS) | **Muy alta** | Completo | **Recomendado** para x86 |
| Ubuntu Server LTS | 5 años (+5 con ESM) | Alta | Completo, más actualizado | **Alternativa válida** |
| macOS | Ligado al hardware | Alta | Completo; MLX sólo aquí | **Obligado** si Apple Silicon |
| Fedora / rolling | Corto | Media | Muy actualizado | **Descartado** — ciclo incompatible con D20 |
| Windows | Largo | Media | Funciona, peor integrado | **Descartado** — sobrecarga innecesaria en un servicio permanente |

### 3.3 Recomendación

**Debian estable sin entorno gráfico**, si la plataforma es x86. **macOS**, si la plataforma acaba
siendo Apple Silicon — no por preferencia, sino porque es el único SO de ese hardware.

Tres precisiones:

1. **Sin escritorio.** AURA es un servicio, no una aplicación de escritorio. Un entorno gráfico
   consume memoria que el modelo necesita. Cuando llegue el avatar (M3.4) habrá que revisarlo, y esa
   revisión debe ser explícita, no un efecto lateral de haber instalado un escritorio "por si acaso".

2. **Debian sobre Ubuntu por sobriedad**, no por rendimiento: menos componentes que mantener en un
   equipo que debe funcionar años sin atención. Ubuntu LTS es defendible si se valora un stack más
   actualizado.

3. **La elección de SO no la fuerza AURA, la fuerza el hardware.** ADR-0016 garantiza que el Core
   corre igual en los tres. Es una decisión de operación, no de arquitectura.

## 4. Resumen ejecutable

| Componente | Mínimo | Recomendado |
|---|---|---|
| RAM | 8 GB | **16 GB** |
| CPU | 4 núcleos | 6–8 núcleos o SoC unificado |
| Almacenamiento | SSD 64 GB | **NVMe 256 GB** |
| Aceleración | No exigida | Deseable, nunca requerida |
| SO | Linux estable sin GUI | **Debian estable** / macOS si Apple Silicon |
| Respaldo | — | Dispositivo separado (D31) |

**Ninguna de estas cifras oficializa una plataforma** (D33). Definen el listón que cualquier
candidata debe superar.
