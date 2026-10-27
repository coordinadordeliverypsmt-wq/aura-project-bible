---
acta: "Integración local de la delegación segura en integracion/m3-entry"
fecha: 2026-10-27
autoridad: CEO (orden directa en sesión, prompt «HERRAMIENTAS OPERATIVAS + INTEGRACIÓN CONTROLADA»)
---

# Acta · Integración local de `pista/delegacion-segura` (5d78887)

**Autorizado:** merge `--no-ff` local de `pista/delegacion-segura` (5d78887) en `integracion/m3-entry`, como biblioteca
**no cableada**.

**Condiciones del CEO:**

1. Se acepta A3 (`nodo_agente.py`) dentro de la integración, sujeto a comprobar su comportamiento: inerte sin
   `spki_fijada`.
2. DECISION_REQUIRED 1 (contrato de reintento) y 2 (G-1 / `unlink` del firmador) quedan **abiertas**.
3. `DP-DELEGACION-NODOS` sigue **PROPUESTO**. Esta acta no lo aprueba.
4. No se cablea la delegación a producción.
5. Sin cambios en `main` ni en `origin/main`; sin push ni PR.
6. `ciclo_autonomo.py`, `orquestador.py` y `politica-orquestador.toml` sin cambios.

**Validación exigida tras el merge, en serie:** arnés de delegación, integridad y autoconstrucción, reanudación y motor
de autonomía; QG sobre una exportación limpia; suite del control-plane y preflight; E2E sin omisiones.

**El cableado sigue RECHAZADO** (`delegacion-segura.md` §10.6): N2, R4-M1, R4-M2, R4-M3, N1 residual, D-LOG-1 fuera de
producción, `cryptography` sin declarar y acta del DP pendiente.
