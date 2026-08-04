"""Integracion: el Director General esta VIVO en el arranque real de AURORA.

Sin esta prueba, el Director seria una capacidad construida e inalcanzable — el patron exacto de
ALERTA-004 y ALERTA-005, que este proyecto ya ha pagado dos veces: codigo correcto que nadie invoca.
Aqui se verifica sobre `composicion.componer()`, el UNICO lugar que ensambla el sistema (D40/D41).
"""

import asyncio
import os

from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.estado_operativo import Tarea


def _sistema(tmp_path):
    return componer(Configuracion(datos=str(tmp_path)))


def test_el_arranque_real_construye_el_director(tmp_path):
    s = _sistema(tmp_path)
    assert s.director is not None, "el Director no se ensambla en el arranque de produccion"
    assert s.estado_operativo is not None, "el Estado Operativo no se ensambla"


def test_el_director_despacha_por_el_motor_del_sistema(tmp_path):
    """El coordinador NO puede tener su propia ruta de ejecucion (ALERTA-005, RN-5)."""
    s = _sistema(tmp_path)
    assert s.director.motor is s.motor, "el Director debe compartir el Motor Unico del sistema"


def test_el_estado_del_trabajo_vive_junto_al_estado_permanente(tmp_path):
    """Debe persistir en el directorio de datos, no en memoria ni en un temporal."""
    s = _sistema(tmp_path)
    s.estado_operativo.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta"))
    assert os.path.exists(os.path.join(str(tmp_path), "estado_operativo.jsonl")), (
        "el estado del trabajo no se esta persistiendo donde vive el resto del estado permanente"
    )


def test_aurora_recupera_su_backlog_al_volver_a_arrancar(tmp_path):
    """Dos arranques REALES de composicion: el segundo sabe que trabajo quedo pendiente."""
    s1 = _sistema(tmp_path)
    s1.estado_operativo.registrar(
        Tarea(
            objetivo_id="o",
            tarea_id="t-01",
            estado="abierta",
            responsable="programador",
            descripcion="tarea pendiente",
            args={"ruta": str(tmp_path / "x.txt")},
        )
    )

    s2 = _sistema(tmp_path)  # arranque nuevo: solo conoce el directorio de datos

    assert s2.estado_operativo.objetivos_activos() == ["o"], "el arranque nuevo no recupero el objetivo"
    pendiente = s2.estado_operativo.reanudar("o")
    assert pendiente is not None and pendiente.tarea_id == "t-01"


def test_el_director_ejecuta_una_vuelta_sobre_el_sistema_real(tmp_path):
    """El ciclo completo contra el motor REAL, con permisos y dry-run de verdad."""
    s = _sistema(tmp_path)
    destino = tmp_path / "informe.txt"
    destino.write_text("contenido", encoding="utf-8")
    s.estado_operativo.registrar(
        Tarea(
            objetivo_id="o",
            tarea_id="t-01",
            estado="abierta",
            responsable="programador",
            descripcion="copiar el informe",
            args={"ruta": str(destino)},
        )
    )

    hecha = asyncio.run(s.director.ciclo("o", trace_id="t"))

    assert hecha is not None, "el Director no tomo la tarea pendiente"
    # El resultado depende de permisos reales; lo que NO puede pasar es cerrarla sin efecto (INV-9).
    assert hecha.estado in ("terminada", "bloqueada")
    if hecha.estado == "terminada":
        assert hecha.evidencias, "una tarea terminada debe registrar evidencia del resultado real"
    else:
        assert hecha.bloqueos, "una tarea bloqueada debe conservar el motivo"


def test_control_un_responsable_no_declarado_no_se_finge(tmp_path):
    """INV-9: solo se declaran los ejecutores que existen. Un rol no construido bloquea, no simula."""
    s = _sistema(tmp_path)
    s.estado_operativo.registrar(Tarea(objetivo_id="o", tarea_id="t-01", estado="abierta", responsable="investigador"))

    hecha = asyncio.run(s.director.ciclo("o"))

    assert hecha.estado == "bloqueada", "un responsable sin ejecutor no puede darse por hecho"
    assert any("ningun ejecutor" in b for b in hecha.bloqueos)
