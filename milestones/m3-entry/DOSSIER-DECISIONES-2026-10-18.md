# Dossier de decisiones — 2026-10-18

**Naturaleza:** informe de trabajo para el CEO técnico-estratégico. **No es normativo**: no aprueba, no
modifica ni sustituye ningún DP, ADR, acta o pendiente. Clasificación D47: `[EJEC]` medido · `[LECT]` leído ·
`[INFER]` deducido · `[HIPO]` no verificado.

## 0. Resultado de la búsqueda de trabajo ejecutable

**Ausencia demostrada de obra autorizada y ejecutable.** Barrido (agente `explorador-repositorio`) de
roadmap 2.2, `milestones/*`, actas, `CHECKLIST`, `PLAN-DE-FORMACION`, CHECKPOINT y worktree `l4-clean`:
12 candidatos con autorización explícita → todos **YA-HECHOS**, **BLOQUEADOS** por una decisión concreta o
**sin evidencia de uso** suficiente. Los cierres de hito M1/M2/M3 son gates del CEO (2.2 §3.2). `[LECT]`

## 1. Decisiones, por capacidad de desbloqueo (no por preferencia)

### P1 · Preservación del trabajo verificado (sin ID; nuevo hallazgo) — **riesgo de pérdida de información**
- **Hechos `[EJEC]`:** último commit `6dad6af` del **2026-09-13**. Desde entonces: 130 ficheros versionados
  modificados (+11 991 / −1 152) y ~360 ficheros nuevos sin seguimiento fuera de `graphify-out/cache`
  (148 en `milestones/m3-entry`, 70 pruebas, 40 mutaciones, 31 control plane, 24 producto). Incluye D-AMP-2,
  M3.2a, D-M-1 A′, todos VERIFICADOS (QG PASS 3260, 2026-10-12). La regla vigente prohíbe commit sin
  autorización.
- **Repercusión doméstica:** un borrado del worktree, un `git checkout`/`clean` accidental o un fallo de
  disco pierde ~5 semanas de capacidades verificadas de memoria.
- **Alternativas:** (a) autorizar **commit local** en `worktree-m3-entry` (sin push ni merge; reversible con
  `git reset --soft`); (b) commit + push de la rama (copia remota; no toca `main`); (c) mantener sin commit.
- **Riesgos:** (a/b) hay que decidir si `graphify-out/cache` (808 ficheros) entra o se ignora; (b) publica en
  remoto. **Reversibilidad:** alta en (a).
- **Evidencia faltante:** ninguna para decidir; para ejecutar, revisar `git status` por tipos (secretos: el
  hook de QG corre en push, no en commit).
- **Independiente de:** todo lo demás.

### P2 · D-INT-1 — integración de la rama en `main`
- **Hechos `[EJEC]`:** la rama va **29 commits por delante** de `main` (`d933a08`), `main` 0 por delante.
  `l4-clean` (`l4-multimodal`, `f81361a`) = 1 commit sobre `6dad6af`, limpio, multimodal YA-HECHO (mutación
  8/8, E2E físico) y solo integrable vía esta decisión `[LECT]`.
- **Alternativas** (de `estado.json` D-INT-1): (a) `merge --no-ff` completo; (b) dejar `main` intacto;
  (c) revisar antes los commits previos y decidir después.
- **Dependencia:** P1 (sin commit, la integración no incluiría el trabajo del 13-sep en adelante).
- **Repercusión:** `main` hoy no contiene memoria verificada ni el bloque multimodal.

### P3 · Percepción visual e identidad (A/B) — `DECISION-REQUERIDA-PERCEPCION-VISUAL-E-IDENTIDAD.md`
- **Hechos:** acta 2026-09-27 autoriza la cadena cámara→contexto; lo ambiental (sin persona) está
  construido (`DP-FRAME-A`, `test_observacion_visual.py`) `[EJEC]`; la grada persona/identidad choca con
  ALERTA-002 y `2.4:116` (no perfilar a terceros) `[LECT]`.
- **Decisión:** (A) presencia visual **sin** identidad en el MVP; (B) reconocer miembros de la familia con
  enrolamiento explícito.
- **Repercusión doméstica:** alta (saludo/contexto por persona). **Riesgo:** privacidad de terceros.
- **Evidencia faltante:** ninguna técnica (cámara 640×480 operativa, 85 ms/fotograma `[EJEC]` histórico).

### P4 · Continuidad de resultados — punto D (privacidad) — `DECISION-REQUERIDA-CONTINUIDAD-DE-RESULTADOS.md`
- **Hechos `[EJEC]` (histórico):** contenido de ficheros leídos (IBAN, clave del router) reentra en prompts
  posteriores; hoy acotado porque el proveedor es local (D24). No existe clasificación de sensibilidad.
- **Decisión:** qué contenido se prohíbe retener (+ 11 preguntas ya redactadas A–L; L resuelto).
- **Repercusión:** se vuelve crítica el día que haya proveedor remoto. **Reversible.**

### P5 · Calidad del recuperador de memoria — D-M-3, D-M-4, D-M-6 (sin DP)
- **Hechos:** abiertos en código (`memory.py:222-225` desempate; cobertura normalizada por la consulta) `[LECT]`;
  D-M-1 A′ excluye tocarlos (acta :31). D-M-4 probablemente ligado a D-M-7 `[INFER]`.
- **Incertidumbre:** **ningún defecto observado en uso real** (tampoco D-M-1) → la regla «capacidades nacen
  de bloqueos observados» pide evidencia antes de construir.
- **Comprobación mínima:** telemetría/registro de recuerdos fallidos en uso doméstico real.

### P6 · Política post-rollback — `DP-POLITICA-POST-ROLLBACK.md` (ADR-0025, solo el CEO lo acepta)
- (a) continuar con tareas restantes / seguir deteniendo el ciclo; (b) asignar ID; (c) ADR obligatorio.
  Afecta al motor de desarrollo, no al AURA doméstico. Con `PARADA` armada, **impacto hoy nulo** `[INFER]`.

### P7 · Proyector automático de `estado.json` + D-REL-1/2/3 (`DP-MENSAJERO-RELEVO.md`)
- **Hecho `[EJEC]`:** `estado.json` desfasado desde 2026-09-01 → el `handoff` existente entrega datos viejos.
  El relevo entre sesiones depende de esto o de derivar la carga del CHECKPOINT (D-REL-1). Herramienta de
  desarrollo, no producto.

### P8 · Delegación a subagentes (6 preguntas) y D-ORCH-6 — sin evidencia de uso real; impacto hoy nulo.

## 2. Saneamiento documental (no es obra; requiere permiso para editar estados)
`[LECT]` `DP-VOZ-ACCION.md:6` dice «EN EJECUCIÓN» (ejecutado, CHECKPOINT:7650/7679) · `CHECKLIST:291` da
DP-D-M-8 como pendiente (cerrado, CHECKPOINT:3288) · faltan líneas de cierre formal de D-M-7, DP-017 y DP-A ·
`DEUDA-N1-RECUPERADOR.md:197-214` describe D-M-5 abierto (resuelto). Cambiar campos de estado de DP es
tocar documentos normativos → no se hizo.

## 3. Qué podría continuar sin decisión
Nada de construcción. Tras P1, el commit es la única operación que no amplía alcance.
