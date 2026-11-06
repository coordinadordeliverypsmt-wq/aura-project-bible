---
tipo: "Registro de decisión del CEO"
id: "D-CM2-1"
fecha: "2026-10-18"
decide: "CEO del proyecto AURA"
sobre: "Población de evaluación de CM2 (S3)"
---

# Acta — D-CM2-1 · Política de población de CM2: solo hechos espontáneos del uso real (2026-10-18)

**Fuente:** orden ejecutiva del CEO «AURA — S3 / CM2: formalizar la política de población y continuar la recogida real»,
recibida en sesión el 2026-10-18. Este documento **transcribe** la orden; no añade alcance. ID `D-CM2-1` elegido por la
convención `D-<línea>-<n>` (D-M-1, D-AMP-2); verificado sin colisión (grep vacío en `.md`/`.py`).

## Decisión (literal)

«CM2 utilizará exclusivamente hechos declarados de forma espontánea durante el uso real y autorizado de AURA. No se
autoriza sembrar hechos para la evaluación, ni siquiera si se etiquetan como sintéticos.»

Consecuencias (literales): no crear hechos de prueba en producción · no importar los 11 hechos históricos anteriores al
mecanismo CM2 · no reconstruir hechos a partir de conversaciones o documentos · no alterar `memoria.json` ni generar
eventos artificiales · aplicar las reglas existentes del DP-S3 e INV-9 para hechos corregidos, olvidados, invalidados o
no elegibles · mantener abierto el gate de CM2 hasta disponer de al menos 20 sondas válidas del día 28 y satisfacer
todos los criterios vigentes · mantener la automatización existente dentro del alcance autorizado · sin commit, push,
merge ni despliegue.

## Justificación metodológica

Evitar el **sesgo de selección** y una tasa artificialmente inflada. `milestones/m3-entry/DP-S3-RELOJ-CM2.md` §5.3
(~380-405) ya reconoce que el denominador solo incluye lo que el clasificador reconoce como `HECHO_DECLARADO` y que eso
puede inflar la tasa; el propio DP (~114) midió 19/24 con corpus sembrado frente a 24/24 con memoria vacía. Una
población sembrada mediría la facilidad de lo sembrado, no la memoria en la vida real.

## Relación con las normas vigentes (sin reescribirlas)

- **DP-S3 / Resolución S3** (`RESOLUCION-S3-CM2-ORDEN-CEO-2026-10-06.md` Q5: población = hechos declarados tipados;
  §2.1: la sonda no escribe memoria; el tiempo anterior al inicio no cuenta): coherente.
- **INV-9** (CLAUDE.md §4 «no se finge capacidad no construida»; ADR-0021): sembrar o importar fabricaría evidencia;
  la política lo refuerza. «Sin datos» sigue siendo «sin datos», no un resultado.
- **Bible 2.5 §5.2** (~107-114: recuperar temas de ≥4 semanas sin re-explicación; >10 % de re-explicación = fracaso;
  cero fabricación de recuerdos) y ~150-154 (evidencia por registro automático; veredicto del CEO): coherente.
- **Privacidad** (Bible 5.5 §3, ALERTA-002, D24): sin conflicto; no tocar `memoria.json` evita agravar el conflicto
  append-only reservado al CEO (Resolución §3, Q4/E-Q1). Eventos `cm2.*` sin texto (minimización).

## Aclaraciones de interpretación (no son reglas nuevas)

1. La política rige la **medición oficial en producción**. Las pruebas unitarias con datos ficticios en directorios
   temporales previstas por el DP-S3 (~86, §5.4) no son población de CM2 y no se ven afectadas.
2. Los 11 hechos históricos ya quedan fuera por mecanismo (no tienen `hecho_id` ni evento `cm2.hecho_registrado`); un
   hecho espontáneo posterior al mecanismo sigue la regla existente de recorte del origen al `cm2.inicio`.

## Efecto sobre CM2

La recogida continúa con el cron diario ya autorizado (`decisiones/2026-10-18-acta-ratificacion-inicio-cm2.md`). El
gate de CM2 permanece **abierto** mientras falte evidencia suficiente.

## No autorizado (literal)

Cambios adicionales en privacidad, retención, arquitectura, código de CM2 ni gobernanza de PARADA.
