"""`_informe` (--verificar) imprime el perfil de hardware MEDIDO, o declara que no hay metricas.

Control: sustituir la linea por `pass` deja el informe sin `perfil de hardware`, y esta prueba falla.
"""

from __future__ import annotations

import types

from aura_skeleton.__main__ import _informe
from aura_skeleton.composicion import Configuracion
from aura_skeleton.core.capacidades import PerfilHardware


def _sistema(perfil: PerfilHardware, tmp_path):
    return types.SimpleNamespace(
        registro_adaptadores=types.SimpleNamespace(capacidades=lambda: {"a"}),
        registro_contexto=types.SimpleNamespace(fuentes={"conversacion"}),
        ruta_memoria=str(tmp_path / "m.json"),
        ruta_audit=str(tmp_path / "a.jsonl"),
        kill_switch=types.SimpleNamespace(is_engaged=lambda: False),
        capacidades_activas_efectivas=(),
        materializaciones=(),
        perfil_hardware=perfil,
        config=Configuracion(datos=str(tmp_path)),
        orquestador=types.SimpleNamespace(router=types.SimpleNamespace(providers=[], estado_circuitos=lambda: {})),
    )


def test_informe_muestra_las_metricas_ordenadas(tmp_path):
    texto = _informe(_sistema(PerfilHardware(recursos={"ram_mb": 3719.0, "isa_avx2": 0.0, "nucleos": 2.0}), tmp_path))
    assert "  perfil de hardware  : isa_avx2=0, nucleos=2, ram_mb=3719" in texto


def test_informe_declara_sin_metricas(tmp_path):
    texto = _informe(_sistema(PerfilHardware(), tmp_path))
    assert "  perfil de hardware  : (sin métricas)" in texto
