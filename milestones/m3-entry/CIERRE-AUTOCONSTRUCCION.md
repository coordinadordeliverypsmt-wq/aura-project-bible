# Cierre · Autoconstrucción gobernada + `D-ORCH-2` (parte determinada)

**2026-08-26** · `worktree-m3-entry` · **0 commits · 0 push**

## Los ocho pasos y dónde está la frontera

`OBSERVAR → DIAGNOSTICAR → PROPONER` — AURA sola.
**`AUTORIZAR`** — exige acto humano **con acta**. `1.1:93`: la autoridad de aprobación *«no es
delegable a ningún agente»*. `1.1:85`: el silencio no aprueba.
`EJECUTAR → VERIFICAR → REGISTRAR → CONTINUAR` — solo después.

Esa es la diferencia entre automatización y autonomía gobernada: no pedir permiso para lo que ya cae
dentro de una autorización, y no concederlo nunca para lo que no.

## E2E real — AURA corrigió su propio código

```
1-2 OBSERVAR/DIAGNOSTICAR -> 1 hallazgo   _sin_usar  linea 97  codigo muerto
      fichero intacto tras observar: True
3 PROPONER -> P-001  autorizada=False
4 AUTORIZAR · sin acta -> RECHAZADO
      autorizada por acta del CEO: True
      verificacion: pytest exit=0 -> SANO
5-6 EJECUTAR/VERIFICAR -> efecto=True sano=True revertido=False
7 REGISTRAR · '_sin_usar' sigue presente: False   log integro: True
8 CONTINUAR -> hallazgos restantes: 0
```

**Reversible por construcción:** si la verificación falla, el fichero vuelve a como estaba. Dejar el
árbol roto es peor que no haber hecho nada.

**El efecto se comprueba releyendo el fichero.** Que la sustitución «se haya hecho» no es evidencia.

## `D-ORCH-2` — lo decidido se implementa, lo demás se registra

**Implementado (C5):** `Veredicto` **sin campo de autorización** —si lo tuviera, un modelo podría
rellenarlo—, `autoriza()` constante a `False` para dejar la regla escrita donde alguien la buscaría,
no es requisito para operar, y usa los revisores **que ya existen**. No se creó ningún revisor nuevo
ni se contrató proveedor.

**`DECISION_REQUIRED`:** si un veredicto puede ser *condición previa* para ejecutar una tarea
`REVIEW`. El nivel no existe en ADR-0003 y crearlo eleva la autonomía: solo el CEO.

## Dos defectos propios encontrados y corregidos

- **Zona por descarte.** `zona_permitida` aceptaba «cualquier `.py`», con lo que el producto entero
  entraba. Convertida en lista blanca.
- **Comparación por substring.** Buscar `"bible"` en la ruta completa rechazaba
  `entorno/control-plane/orquestador.py`, porque el repositorio se llama `aura-project-bible`. El
  E2E lo destapó. Ahora se compara por **segmento de ruta**. Es el mismo error de substring que este
  proyecto ya pagó con las zonas de discovery.

## Verificación

| | |
|---|---|
| Control Plane | **331 passed** (23 nuevas) |
| Communication Plane · agente-externo | **180/5** · **20** — sin cambios |
| **Mutación** | **87 mutantes** (35+18+19+15) · **0 supervivientes · 0 NO_APLICADO** |
| `ruff` · Quality Gate | PASS · **FAIL 5/1139/3** (baseline) |
| `estado.json` real | **INTACTO** tras mutación, baterías y gate |
| OpenCode · Codex · residuos · procesos · credenciales | **ausentes · 0 · 0 · 0** |
| D24 · Bible · ADR · roadmap | **0 cambios** |
