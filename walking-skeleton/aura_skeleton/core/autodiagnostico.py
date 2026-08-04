"""Autodiagnostico: AURORA lee su propio historial y dice como esta.

EL VACIO QUE CIERRA. AURORA genera evidencia —audit log, estado del ciclo, garantias— y NO LA CONSUME
para analizarse. Tenia tres capacidades de autodiagnostico (IMA, tablero de dependencia, auditoria de
garantias) y solo una cableada, cada una respondiendo a una pregunta distinta y ninguna a la unica que
importa para dirigir la propia evolucion: **¿como estoy y que deberia hacer al respecto?**

NO DEPENDE DE UN MODELO LOCAL. Agrupa y cuenta hechos registrados; no interpreta ni genera texto. Es
la clase de trabajo que la evidencia demostro que SI es determinista, frente al 98 % generativo del
desarrollo.

NO TOCA EL PRODUCTO. Solo lee. No participa en el camino conversacional, asi que no puede afectar a la
estabilidad de lo que el CEO va a usar a diario.

POR QUE AGRUPA EN VEZ DE LISTAR. Un informe que enumera 40 incidencias no ayuda a decidir; uno que dice
"3 clases de problema, esta se repite 28 veces" si. La agrupacion por TIPO es lo que convierte un
registro en una prioridad, y es exactamente lo que hara falta cuando existan datos de uso real.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Diagnostico:
    """Lo que AURORA sabe de si misma en un momento dado. Todo derivado, nada almacenado (ADR-0023)."""

    eventos: int = 0
    por_tipo: dict[str, int] = field(default_factory=dict)
    incidencias: dict[str, int] = field(default_factory=dict)
    sin_datos: bool = False
    motivo: str = ""

    @property
    def incidencia_dominante(self) -> tuple[str, int] | None:
        """La clase de problema mas repetida. Es la que deberia atenderse primero."""
        if not self.incidencias:
            return None
        return max(self.incidencias.items(), key=lambda kv: (kv[1], kv[0]))


# Tipos de registro que denotan un problema, no actividad normal. Se agrupan por CLASE para que el
# informe diga "que" falla y no solo "cuantas veces paso algo".
_INCIDENCIAS = {
    "ERROR": "errores de ejecucion",
    "WARN": "avisos del sistema",
    "HITL": "intervenciones humanas exigidas",
    "KILL": "paradas de emergencia",
}


def diagnosticar(ruta_audit: str) -> Diagnostico:
    """Lee el audit log y agrupa lo ocurrido. Sin datos, lo declara en vez de inventar un informe."""
    p = Path(ruta_audit)
    if not p.exists():
        return Diagnostico(sin_datos=True, motivo=f"no existe el registro: {ruta_audit}")

    tipos: Counter = Counter()
    incidencias: Counter = Counter()
    total = 0
    for linea in p.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            reg = json.loads(linea)
        except ValueError:
            continue  # una linea ilegible no puede impedir el diagnostico del resto
        total += 1
        tipo = str(reg.get("kind") or reg.get("tipo") or reg.get("level") or "?")
        tipos[tipo] += 1
        if tipo in _INCIDENCIAS:
            incidencias[_INCIDENCIAS[tipo]] += 1

    if total == 0:
        return Diagnostico(sin_datos=True, motivo="el registro esta vacio: no hay uso que analizar")
    return Diagnostico(eventos=total, por_tipo=dict(tipos.most_common()), incidencias=dict(incidencias.most_common()))


def informe_ejecutivo(diag: Diagnostico, ima=None, dependencia=None, garantias=None) -> str:
    """Responde "¿como estoy?" en una sola lectura, juntando lo que hoy vive disperso.

    Cada bloque es opcional: el informe se degrada declarando lo que falta en vez de omitirlo en
    silencio, porque un informe incompleto que no lo dice es peor que uno corto.
    """
    lineas = ["ESTADO DE AURORA", "=" * 60]

    if diag.sin_datos:
        lineas.append(f"USO: sin datos — {diag.motivo}")
        lineas.append("     Sin uso real, cualquier prioridad seria una hipotesis.")
    else:
        lineas.append(f"USO: {diag.eventos} evento(s) registrados")
        dom = diag.incidencia_dominante
        if dom:
            lineas.append(f"     incidencia dominante: {dom[0]} ({dom[1]}x)")
            for clase, n in diag.incidencias.items():
                if clase != dom[0]:
                    lineas.append(f"     · {clase}: {n}x")
        else:
            lineas.append("     sin incidencias registradas")

    if garantias is not None:
        estado = "todas vigentes" if garantias.get("ok") else f"{len(garantias.get('rotas', []))} ROTAS"
        lineas.append(f"GARANTIAS: {garantias.get('vigentes')}/{garantias.get('declaradas')} — {estado}")
    else:
        lineas.append("GARANTIAS: no evaluadas en este informe")

    if ima is not None:
        medibles = [d for d in ima if d.medible]
        log, tot = sum(d.logrado for d in medibles), sum(d.total for d in medibles)
        no_medibles = len(ima) - len(medibles)
        lineas.append(f"CAPACIDADES (IMA): {log}/{tot} en dimensiones medibles, {no_medibles} sin instrumentar")
    else:
        lineas.append("CAPACIDADES (IMA): no evaluadas en este informe")

    if dependencia is not None:
        for i in dependencia:
            if i.estado != "medible":
                lineas.append(f"AUTONOMIA · {i.nombre}: NO_MEDIBLE")
            elif i.denominador is None:
                lineas.append(f"AUTONOMIA · {i.nombre}: {i.numerador} punto(s)")
            else:
                lineas.append(f"AUTONOMIA · {i.nombre}: {i.numerador}/{i.denominador} = {i.porcentaje}%")
    else:
        lineas.append("AUTONOMIA: no evaluada en este informe")

    return "\n".join(lineas)
