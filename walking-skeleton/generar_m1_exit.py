#!/usr/bin/env python3
"""Genera los apartados data-driven del cierre M1-Exit a partir de los JSON de los arneses.
Lee resultados-m1.json (validar_m1.py) y evals-m1.json (evals_m1.py) y emite Markdown con:
resultados medidos, comparacion contra los objetivos de la Bible, y veredicto (+ aviso de Alerta D15).

Uso: python3 generar_m1_exit.py --resultados resultados-m1.json --evals evals-m1.json --out ../milestones/m1-exit/RESULTADOS-MEDIDOS.md
"""

import argparse
import json
import os

R1_MS, R2_MS = 1200.0, 800.0


def _load(path):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _si(b):
    return "SI" if b else ("NO" if b is False else "s/d")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resultados", default="resultados-m1.json")
    ap.add_argument("--evals", default="evals-m1.json")
    ap.add_argument("--out", default="RESULTADOS-MEDIDOS.md")
    args = ap.parse_args()

    r = _load(args.resultados)
    e = _load(args.evals)
    L = []
    L.append("# M1-Exit — Resultados medidos y comparacion (auto-generado)\n")

    L.append("## 1. Resultados medidos (validar_m1.py)\n")
    if r:
        lat = r.get("latencia_ms", {})
        est = r.get("estabilidad", {})
        rec = r.get("recursos", {})
        L.append(f"- Backend: **{r.get('backend')}** · iteraciones: {r.get('iteraciones')}")
        L.append(
            f"- Latencia por etapa (P50): STT={lat.get('stt_p50')} ms · LLM={lat.get('llm_p50')} ms · TTS={lat.get('tts_p50')} ms"
        )
        L.append(f"- **Latencia extremo a extremo:** P50={lat.get('e2e_p50')} ms · P95={lat.get('e2e_p95')} ms")
        L.append(f"- Recursos: {rec.get('despues')} · almacenamiento memoria={rec.get('almacenamiento_memoria_mb')} MB")
        L.append(
            f"- Estabilidad: errores={est.get('errores')} · recuperaciones={est.get('recuperaciones')} · turnos={est.get('turnos')}"
        )
    else:
        L.append("_Pendiente: ejecuta `validar_m1.py --real` en el hardware objetivo y comparte resultados-m1.json._")

    L.append("\n## 2. Evals de comportamiento (evals_m1.py)\n")
    if e:
        L.append(f"- Backend: **{e.get('backend')}** · modelos: {', '.join(e.get('modelos', []))}")
        L.append("\n| Eval | Critico | Resultado | Passed |")
        L.append("|---|---|---|---|")
        for ev in e.get("evals", []):
            L.append(
                f"| {ev.get('eval')} | {'si' if ev.get('critico') else 'no'} | {ev.get('resultado')} | {_si(ev.get('passed'))} |"
            )
    else:
        L.append("_Pendiente: ejecuta `evals_m1.py --real` y comparte evals-m1.json._")

    L.append("\n## 3. Comparacion contra los objetivos de la Bible\n")
    L.append("| Objetivo (Bible) | Umbral | Medido | Cumple |")
    L.append("|---|---|---|---|")
    e2e = (r or {}).get("latencia_ms", {}).get("e2e_p50")
    L.append(
        f"| HC-1 R1 (baseline local) | P50 <= {R1_MS:.0f} ms | {e2e if e2e is not None else 's/d'} | {_si((r or {}).get('cumple_R1'))} |"
    )
    L.append(
        f"| HC-1 R2 (GPU/optimizado) | P50 <= {R2_MS:.0f} ms | {e2e if e2e is not None else 's/d'} | {_si((r or {}).get('cumple_R2'))} |"
    )
    errores = (r or {}).get("estabilidad", {}).get("errores")
    L.append(
        f"| Estabilidad | 0 errores no recuperados | errores={errores if errores is not None else 's/d'} | {_si(errores == 0) if errores is not None else 's/d'} |"
    )
    crit_fail = [ev for ev in (e or {}).get("evals", []) if ev.get("critico") and ev.get("passed") is False]
    L.append(
        f"| Guardrails (HITL/grounding/consistencia) | todos pasan | {'fallo(s): ' + ', '.join(x['eval'] for x in crit_fail) if crit_fail else ('OK' if e else 's/d')} | {_si(len(crit_fail) == 0) if e else 's/d'} |"
    )

    L.append("\n## 4. Veredicto\n")
    problemas = []
    if r and not r.get("cumple_R1"):
        problemas.append(f"HC-1 R1 no cumplido (e2e P50={e2e} ms > {R1_MS:.0f} ms)")
    if crit_fail:
        problemas.append("guardrail(s) critico(s) fallido(s): " + ", ".join(x["eval"] for x in crit_fail))
    if errores not in (None, 0):
        problemas.append(f"errores de estabilidad: {errores}")
    if not r or not e:
        L.append("**INCOMPLETO** — faltan datos medidos en hardware objetivo (ver secciones pendientes).")
    elif problemas:
        L.append("**NO LISTO PARA CIERRE — se requiere ALERTA DE ARQUITECTURA (D15):**")
        for p in problemas:
            L.append(f"- {p}")
        L.append(
            "\nUsa `decisiones/alertas/plantilla-alerta.md` (10 secciones, D16). No ajustes objetivos ni implementacion en silencio."
        )
    else:
        L.append(
            "**LISTO PARA CIERRE M1** — objetivos de la Bible cumplidos; procede la Architecture Review M1-Exit y el Executive Summary."
        )

    out = "\n".join(L) + "\n"
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out)
    print(out)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
