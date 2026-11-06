"""La composicion usa el detector REAL de hardware (ADR-0020/0021) en el camino de producto.

Antes, el unico detector era `_PerfilInyectado` con perfil VACIO: el Manager decidia la memoria con
`ram_mb = 0` en cualquier equipo (declarado != real). Aqui se prueba que un detector inyectado gobierna el
plan, y que `Configuracion.desde_entorno()` (camino de producto) lo cablea (patron ALERTA-005).
"""

from __future__ import annotations

from aura_skeleton import observability as obs
from aura_skeleton.adapters.detector_hardware import DetectorHardwareLocal
from aura_skeleton.composicion import Configuracion, componer
from aura_skeleton.core.capacidades import Estado, PerfilHardware


class _Falso:
    def __init__(self, ram_mb: float | None):
        self._p = PerfilHardware(recursos={} if ram_mb is None else {"ram_mb": ram_mb, "nucleos": 8.0})

    def detectar(self) -> PerfilHardware:
        return self._p


def _cfg(tmp_path, **kw):
    return Configuracion(datos=str(tmp_path), raices_permitidas=(str(tmp_path),), usar_stack_real=False, **kw)


def test_16gb_detectados_amplian_la_memoria_a_activa(tmp_path):
    s = componer(_cfg(tmp_path, detector=_Falso(16384.0)))
    assert s.plan.decision("memoria").estado is Estado.ACTIVA  # control: vacio da DEGRADADA (prueba 3)
    # Si el modelo de embeddings falta, N2 no se ensambla: debe declararlo degradado y con motivo.
    m = s.materializaciones[0]
    assert m.estado_plan is Estado.ACTIVA
    if m.degradada:
        assert m.motivo and m.estado_efectivo is Estado.DEGRADADA
    else:
        assert m.nivel.startswith("N2")


def test_3_6gb_detectados_dejan_la_memoria_degradada(tmp_path):
    s = componer(_cfg(tmp_path, detector=_Falso(3719.0)))
    assert s.plan.decision("memoria").estado is Estado.DEGRADADA


def test_sin_detector_se_comporta_como_antes(tmp_path):
    s = componer(_cfg(tmp_path))
    assert s.plan.decision("memoria").estado is Estado.DEGRADADA
    assert s.perfil_hardware.recursos == {}


def test_desde_entorno_cablea_el_detector_real(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_DATOS", str(tmp_path))
    cfg = Configuracion.desde_entorno()
    assert isinstance(cfg.detector, DetectorHardwareLocal)


def test_sistema_expone_el_perfil_detectado(tmp_path):
    s = componer(_cfg(tmp_path, detector=_Falso(16384.0)))
    assert s.perfil_hardware.recursos["ram_mb"] == 16384.0
    assert s.perfil_hardware.recursos["nucleos"] == 8.0


def test_boot_auditado_lista_las_metricas(tmp_path, monkeypatch):
    lineas: list[tuple] = []
    orig = obs.log

    def espia(*a, **kw):
        lineas.append((a, kw))
        return orig(*a, **kw)

    monkeypatch.setattr(obs, "log", espia)
    componer(_cfg(tmp_path, detector=_Falso(16384.0)))
    textos = [a[2] for a, kw in lineas if a[0] == "BOOT" and "perfil de hardware" in a[2]]
    assert len(textos) == 1 and "ram_mb=16384" in textos[0] and "nucleos=8" in textos[0]
    assert any(kw.get("audit") for a, kw in lineas if a[0] == "BOOT" and "perfil de hardware" in a[2])


def test_boot_declara_perfil_vacio(tmp_path, monkeypatch):
    lineas: list[str] = []
    orig = obs.log
    monkeypatch.setattr(obs, "log", lambda *a, **kw: (lineas.append(a[2]), orig(*a, **kw))[1])
    componer(_cfg(tmp_path))
    assert any("sin métricas (inyectado vacío)" in t or "sin metricas" in t for t in lineas)


class _Roto:
    def detectar(self):
        raise RuntimeError("boom")


class _Vacio:
    def detectar(self) -> PerfilHardware:
        return PerfilHardware()


def _boot_perfil(tmp_path, monkeypatch, detector):
    lineas: list[str] = []
    orig = obs.log
    monkeypatch.setattr(obs, "log", lambda *a, **kw: (lineas.append(a[2]), orig(*a, **kw))[1])
    componer(_cfg(tmp_path, detector=detector))
    return [t for t in lineas if "perfil de hardware" in t]


def test_boot_con_detector_que_lanza_no_culpa_a_la_inyeccion(tmp_path, monkeypatch):
    (texto,) = _boot_perfil(tmp_path, monkeypatch, _Roto())
    assert "el detector de hardware no entregó métricas (ver WARN)" in texto
    assert "inyectado" not in texto  # control: la causa falsa del defecto original


def test_boot_con_detector_que_devuelve_vacio_tampoco_dice_inyectado(tmp_path, monkeypatch):
    (texto,) = _boot_perfil(tmp_path, monkeypatch, _Vacio())
    assert "el detector de hardware no entregó métricas" in texto


def test_boot_sin_detector_sigue_diciendo_inyectado_vacio(tmp_path, monkeypatch):
    (texto,) = _boot_perfil(tmp_path, monkeypatch, None)
    assert "inyectado vacío" in texto
