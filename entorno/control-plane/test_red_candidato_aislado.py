"""Candidato aislado en la autoconstruccion — alternativa A del DP-CANDIDATO-AISLADO-AUTOCONSTRUCCION.

Defecto demostrado (`milestones/m3-entry/evidencia-candidato-aislado-2026-10-22/`): `ejecutar` escribia
el candidato SOBRE el arbol vivo y verificaba alli (R1: cualquier lector concurrente ve codigo sin
verificar) y un SIGKILL durante la verificacion dejaba el candidato sin respaldo ni rastro (R2).

Garantias que fijan estas pruebas (cada una con su caso de control):

1. el arbol vivo NO contiene el candidato mientras se verifica; la verificacion corre sobre una copia;
2. rechazo / excepcion / «no se midio» / SIGKILL => el vivo es byte a byte el original;
3. la promocion es atomica, con diario de intencion en disco y precondicion de hashes;
4. si la promocion falla se restaura y se verifica el sha; si la restauracion falla, NO hay exito:
   respaldo conservado, bloqueo y excepcion explicita;
5. `recuperar` es idempotente y resuelve un diario huerfano;
6. sin autorizacion / intocable / PARADA => nada se escribe (ni copia ni diario).

Todas usan `AURA_AUTOCONSTRUCCION_ESTADO` apuntando a `tmp_path`: jamas el estado real.
"""

import fcntl
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

import aislamiento as ais
import autoconstruccion as ac
import control_plane as cp
import pytest

PLANO = pathlib.Path(__file__).parent
# FASE B (estricto): la verificacion por contrato exige Landlock ABI>=6 + seccomp; sin ello se rechaza.
LANDLOCK = ais.estricto_disponible()
necesita_landlock = pytest.mark.skipif(not LANDLOCK, reason="este kernel no ofrece el confinamiento estricto")
ORIGINAL = "VALOR = 1\n"
CANDIDATO = "VALOR = 2\n"


def _sha(ruta) -> str:
    return hashlib.sha256(pathlib.Path(ruta).read_bytes()).hexdigest()


def _tipos(d) -> list[str]:
    return [e["tipo"] for e in cp.leer_eventos(d)]


@pytest.fixture
def montaje(tmp_path, monkeypatch):
    """Directorio de trabajo + estado aislado en tmp. Devuelve (d, propuesta, objetivo, estado)."""
    estado = tmp_path / "estado"
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(estado))
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / "s.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "incremento"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-10-22")
    return d, p, objetivo, estado


def _operaciones(estado) -> list[pathlib.Path]:
    """Directorios de operacion pendientes (con diario) bajo el estado aislado."""
    if not estado.exists():
        return []
    return sorted(p.parent for p in estado.rglob("diario.json"))


def _bloqueos(estado) -> list[pathlib.Path]:
    return sorted(estado.rglob("BLOQUEADO")) if estado.exists() else []


class _FalloDeReplace:
    """Envuelve `os.replace`. `modo`: 'antes' (falla sin hacer nada), 'despues' (hace el reemplazo
    real y luego falla: la muerte justo tras el replace). `veces`: cuantas llamadas hacia `destino`
    fallan (None = todas)."""

    def __init__(self, monkeypatch, destino, excepcion, modo="antes", veces=None):
        self.real = os.replace
        self.destino, self.excepcion, self.modo, self.veces = (
            pathlib.Path(destino), excepcion, modo, veces)
        self.activo = True
        self.llamadas = 0
        monkeypatch.setattr(os, "replace", self)

    def __call__(self, src, dst, *a, **k):
        if self.activo and pathlib.Path(dst) == self.destino and (
                self.veces is None or self.llamadas < self.veces):
            self.llamadas += 1
            if self.modo == "despues":
                self.real(src, dst, *a, **k)
            raise self.excepcion
        return self.real(src, dst, *a, **k)


def _sin_mkdtemp(monkeypatch):
    def prohibido(*a, **k):
        raise AssertionError("se creo una copia temporal antes de pasar las puertas")
    monkeypatch.setattr(tempfile, "mkdtemp", prohibido)


# ======================================= T1 · EL VIVO NO CONTIENE EL CANDIDATO AL VERIFICAR --


def test_T1_durante_la_verificacion_el_vivo_es_el_original_y_la_copia_lleva_el_candidato(montaje):
    d, p, objetivo, estado = montaje
    sha_original = _sha(objetivo)
    visto = {}

    def espia(raiz):
        visto["sha_vivo"] = _sha(objetivo)
        visto["raiz"] = pathlib.Path(raiz).resolve()
        visto["copia"] = (pathlib.Path(raiz) / "s.py").read_text(encoding="utf-8")
        return True

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=espia)
    assert visto["sha_vivo"] == sha_original, "el vivo ya contenia el candidato durante la verificacion"
    assert visto["copia"] == CANDIDATO, "la verificacion no vio el candidato en la copia"
    assert d.resolve() not in (visto["raiz"], *visto["raiz"].parents), "la copia esta dentro del vivo"
    assert r["revertido"] is False and r["promovido"] is True, r
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO
    assert _sha(objetivo) == hashlib.sha256(CANDIDATO.encode()).hexdigest()
    assert not visto["raiz"].exists(), "la copia temporal no se limpio"
    assert _operaciones(estado) == [], "el diario no se cerro tras promover"
    assert "cambio_aplicado" in _tipos(d)


def test_T1_CONTROL_la_verificacion_heredada_sin_raiz_se_rechaza_explicitamente(montaje, monkeypatch,
                                                                                tmp_path):
    """FASE A (PROMPT 03): la via heredada (`verificacion=lambda: True`, que mide el vivo) ya NO
    funciona: es un error explicito `VerificadorSinRaiz`, antes de crear la copia, sin llamar al
    verificador y con el vivo intacto. Con raiz (`lambda raiz: True`) el mismo montaje promueve."""
    d, p, objetivo, estado = montaje
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmpdir))
    sha_antes, llamadas = _sha(objetivo), []

    def heredada():
        llamadas.append(1)
        return True

    with pytest.raises(ac.VerificadorSinRaiz, match="raiz"):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=heredada)
    assert llamadas == [], "se EJECUTO un verificador que no recibe la raiz"
    assert _sha(objetivo) == sha_antes and list(tmpdir.iterdir()) == [], "se creo copia o se toco el vivo"
    assert _operaciones(estado) == [], "se escribio un diario"
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)          # CONTROL
    assert r["revertido"] is False and objetivo.read_text(encoding="utf-8") == CANDIDATO


# ============================================== T2 · VERIFICACION EN ROJO: EL VIVO NUNCA CAMBIA --


def test_T2_verificacion_en_rojo_el_vivo_nunca_contuvo_el_candidato(montaje):
    d, p, objetivo, estado = montaje
    sha_original = _sha(objetivo)
    lecturas = []

    def espia(raiz):
        lecturas.append(objetivo.read_text(encoding="utf-8"))
        return False

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=espia)
    assert lecturas == [ORIGINAL], lecturas
    assert r["revertido"] is True and r["promovido"] is False, r
    assert _sha(objetivo) == sha_original
    assert _operaciones(estado) == [], "se escribio un diario para un candidato rechazado"
    assert "cambio_aplicado" in _tipos(d), "se perdio el evento de compatibilidad"


def test_T2_el_vivo_no_se_toca_ni_se_reescribe_al_rechazar(montaje):
    """Ni siquiera un write/restore: la fecha de modificacion del vivo no cambia."""
    d, p, objetivo, _ = montaje
    antes = objetivo.stat().st_mtime_ns
    ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: False)
    assert objetivo.stat().st_mtime_ns == antes, "el vivo se reescribio aunque se rechazo"


def test_T2_sin_verificador_no_se_midio_y_se_rechaza(montaje):
    d, p, objetivo, _ = montaje
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=None)
    assert r["revertido"] is True and r["verificacion_sana"] is not True
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


# =========================================================== T3 · EXCEPCION / PLAZO / «NO SE MIDIO» --


@pytest.mark.parametrize("excepcion", [RuntimeError("cuota agotada"), KeyboardInterrupt()])
def test_T3_una_excepcion_en_la_verificacion_deja_el_vivo_intacto_y_deja_evento(montaje, excepcion):
    d, p, objetivo, estado = montaje
    sha_original = _sha(objetivo)

    def revienta(raiz):
        assert (pathlib.Path(raiz) / "s.py").read_text(encoding="utf-8") == CANDIDATO
        raise excepcion

    with pytest.raises(type(excepcion)):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=revienta)
    assert _sha(objetivo) == sha_original
    assert "cambio_revertido_por_error" in _tipos(d)
    assert _operaciones(estado) == []


def test_T3_una_medicion_vacia_None_se_rechaza_como_no_medido(montaje):
    d, p, objetivo, _ = montaje
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: None)  # «no se midio»
    assert r["revertido"] is True and r["promovido"] is False
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


# ================================================================ T4 · SIGKILL EN LA VERIFICACION --

_GUION_SIGKILL = r"""
import os, signal, sys, pathlib
sys.path.insert(0, sys.argv[1])
import autoconstruccion as ac
d = pathlib.Path(sys.argv[2])
p = ac.proponer(d, {"fichero": str(d / "s.py"), "operacion": "sustituir_texto",
                    "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "incremento"})
ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-10-22")
def mata(raiz):
    pathlib.Path(sys.argv[3]).write_text(str(raiz))
    os.kill(os.getpid(), signal.SIGKILL)
ac.ejecutar(d, p, autoridad="ceo", verificacion=mata)
"""


def test_T4_un_SIGKILL_durante_la_verificacion_deja_el_vivo_como_el_original(tmp_path, monkeypatch):
    estado = tmp_path / "estado"
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(estado))
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / "s.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    sha_original = _sha(objetivo)
    marca = tmp_path / "raiz_copia.txt"
    r = subprocess.run([sys.executable, "-c", _GUION_SIGKILL, str(PLANO), str(d), str(marca)],
                       env=os.environ.copy(), timeout=60)
    assert r.returncode == -9, f"el subproceso no murio por SIGKILL: {r.returncode}"
    copia = pathlib.Path(marca.read_text())
    try:
        assert _sha(objetivo) == sha_original, "tras SIGKILL el vivo quedo con el candidato (R2)"
        assert copia.resolve() != d.resolve() and d.resolve() not in copia.resolve().parents
        assert (copia / "s.py").read_text(encoding="utf-8") == CANDIDATO, "la copia no era la verificada"
        assert _operaciones(estado) == [], "no habia nada que recuperar: el vivo nunca se toco"
    finally:
        import shutil
        shutil.rmtree(copia, ignore_errors=True)


# ============================================= T4b · MUERTE ENTRE EL DIARIO Y EL REPLACE; RECUPERAR --


def test_T4b_muerte_entre_el_diario_y_el_replace_recuperar_deja_el_original(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    sha_original = _sha(objetivo)
    fallo = _FalloDeReplace(monkeypatch, objetivo, SystemExit(9), modo="antes")
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    fallo.activo = False
    ops = _operaciones(estado)
    assert len(ops) == 1, "el diario de intencion no estaba en disco antes del replace"
    assert _sha(objetivo) == sha_original

    ac.recuperar(d)
    assert _sha(objetivo) == sha_original
    assert _operaciones(estado) == [], "el diario no se cerro"
    assert not list(d.glob(".*.aura-cand-*.tmp")), "quedo un temporal huerfano junto al destino"
    eventos = [e for e in cp.leer_eventos(d) if e["tipo"] == "recuperacion_al_arranque"]
    assert len(eventos) == 1 and eventos[0]["datos"]["resultado"] == "sin_cambios"

    n = len(cp.leer_eventos(d))
    ac.recuperar(d)                                                       # idempotente
    assert len(cp.leer_eventos(d)) == n and _sha(objetivo) == sha_original


def test_T4b_muerte_justo_despues_del_replace_recuperar_restaura_el_original(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    sha_original = _sha(objetivo)
    fallo = _FalloDeReplace(monkeypatch, objetivo, SystemExit(9), modo="despues", veces=1)
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    fallo.activo = False
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO, "el escenario no simulo la muerte tras el replace"

    ac.recuperar(d)
    assert _sha(objetivo) == sha_original, "un diario `preparado` con el candidato en el vivo debe revertir"
    assert _operaciones(estado) == []
    res = [e["datos"]["resultado"] for e in cp.leer_eventos(d) if e["tipo"] == "recuperacion_al_arranque"]
    assert res == ["restaurado"], res
    n = len(cp.leer_eventos(d))
    ac.recuperar(d)
    assert len(cp.leer_eventos(d)) == n and _sha(objetivo) == sha_original


def test_diario_ambiguo_bloquea_conserva_todo_y_la_siguiente_ejecucion_se_niega(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    fallo = _FalloDeReplace(monkeypatch, objetivo, SystemExit(9), modo="antes")
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    fallo.activo = False
    objetivo.write_text("VALOR = 99  # alguien lo toco\n", encoding="utf-8")   # ni original ni candidato
    tocado = _sha(objetivo)

    ac.recuperar(d)
    assert _sha(objetivo) == tocado, "no se debe pisar un fichero que no es ni el original ni el candidato"
    assert len(_operaciones(estado)) == 1, "se borro el diario de un caso ambiguo"
    assert len(_bloqueos(estado)) == 1
    assert "promociones_bloqueadas" in _tipos(d)
    n = len(cp.leer_eventos(d))
    ac.recuperar(d)                                                       # idempotente
    assert len(cp.leer_eventos(d)) == n
    with pytest.raises(ac.PromocionesBloqueadas):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert _sha(objetivo) == tocado


# ======================================================= T5 · LA BASE CAMBIA ANTES DE LA PROMOCION --


def test_T5_si_el_vivo_cambia_durante_la_verificacion_se_aborta_sin_escribir(montaje):
    d, p, objetivo, estado = montaje

    def otro_proceso_edita(raiz):
        objetivo.write_text("VALOR = 1\n# editado por otro\n", encoding="utf-8")
        return True

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=otro_proceso_edita)
    assert r["revertido"] is True and r["promovido"] is False, r
    assert objetivo.read_text(encoding="utf-8") == "VALOR = 1\n# editado por otro\n"
    assert "promocion_abortada_base_cambiada" in _tipos(d)
    assert _operaciones(estado) == []


def test_T5_tambien_si_cambia_otro_fichero_copiado(montaje):
    d, p, objetivo, _ = montaje
    vecino = d / "vecino.py"
    vecino.write_text("X = 1\n", encoding="utf-8")

    def toca_al_vecino(raiz):
        assert (pathlib.Path(raiz) / "vecino.py").exists()
        vecino.write_text("X = 2\n", encoding="utf-8")
        return True

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=toca_al_vecino)
    assert r["promovido"] is False and objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert vecino.read_text(encoding="utf-8") == "X = 2\n"
    assert "promocion_abortada_base_cambiada" in _tipos(d)


def test_T5_PARADA_armada_durante_la_verificacion_impide_promover(montaje):
    d, p, objetivo, estado = montaje

    def arma_parada(raiz):
        (d / "PARADA").write_text("", encoding="utf-8")
        return True

    with pytest.raises(ac.ParadaActiva):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=arma_parada)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert _operaciones(estado) == []


# ===================================================== T6 / T10 / PARADA · NADA SE ESCRIBE ANTES --


def test_T6_sin_autorizacion_no_hay_copia_ni_diario(tmp_path, monkeypatch):
    estado = tmp_path / "estado"
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(estado))
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / "s.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "x"})
    _sin_mkdtemp(monkeypatch)
    with pytest.raises(ac.SinAutorizacion):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert not estado.exists() or not any(estado.rglob("*"))


@pytest.mark.parametrize("nombre", ["orquestador.py", "review.py"])
def test_T10_un_candidato_sobre_un_intocable_se_rechaza_en_la_puerta_3_sin_copia(
        tmp_path, monkeypatch, nombre):
    estado = tmp_path / "estado"
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(estado))
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / nombre
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "x"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba")
    _sin_mkdtemp(monkeypatch)
    with pytest.raises(ac.FicheroIntocable):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert not estado.exists() or not any(estado.rglob("*"))


def test_T10_PARADA_como_destino_no_se_toca_y_no_hay_copia(tmp_path, monkeypatch):
    estado = tmp_path / "estado"
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(estado))
    d = tmp_path / "cp"
    d.mkdir()
    parada = d / "PARADA"
    parada.write_text("VALOR = 1\n", encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(parada), "operacion": "sustituir_texto",
                        "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "x"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba")
    _sin_mkdtemp(monkeypatch)
    with pytest.raises((ac.FicheroIntocable, ac.ZonaProhibida, ac.ParadaActiva)):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert parada.read_text(encoding="utf-8") == "VALOR = 1\n"
    assert not estado.exists() or not any(estado.rglob("*"))


def test_PARADA_armada_no_crea_copia_ni_diario(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    (d / "PARADA").write_text("", encoding="utf-8")
    _sin_mkdtemp(monkeypatch)
    with pytest.raises(ac.ParadaActiva):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert not estado.exists() or not any(estado.rglob("*"))


def test_PARADA_armada_recuperar_no_escribe_nada(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    fallo = _FalloDeReplace(monkeypatch, objetivo, SystemExit(9), modo="despues", veces=1)
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    fallo.activo = False
    (d / "PARADA").write_text("", encoding="utf-8")
    n = len(cp.leer_eventos(d))

    ac.recuperar(d)                                         # informa, no escribe
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO
    assert len(cp.leer_eventos(d)) == n and len(_operaciones(estado)) == 1

    (d / "PARADA").unlink()                                 # CONTROL: sin PARADA si restaura
    ac.recuperar(d)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


# ======================================================= T7 / T8 · FALLOS EN LA PROMOCION --


def test_T7_si_os_replace_falla_en_la_promocion_se_restaura_y_se_verifica_el_sha(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    sha_original = _sha(objetivo)
    _FalloDeReplace(monkeypatch, objetivo, OSError("disco lleno"), modo="despues", veces=1)
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["revertido"] is True and r["promovido"] is False, r
    assert _sha(objetivo) == sha_original, "el vivo no quedo como el original tras el fallo"
    assert "promocion_revertida" in _tipos(d)
    assert _operaciones(estado) == [], "el diario de una promocion revertida y verificada debe cerrarse"
    assert not list(d.glob(".*.aura-*.tmp")), "quedaron temporales junto al destino"


def test_T7_CONTROL_sin_fallo_no_hay_promocion_revertida(montaje):
    d, p, _, _ = montaje
    ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert "promocion_revertida" not in _tipos(d)


def test_T8_si_tambien_falla_la_restauracion_hay_excepcion_respaldo_y_bloqueo(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    sha_original = _sha(objetivo)
    fallo = _FalloDeReplace(monkeypatch, objetivo, OSError("disco lleno"), modo="despues", veces=1)
    # el primer replace (promocion) se hace y falla; los siguientes hacia el destino (restauracion) fallan
    real = fallo.real

    def siempre_falla_hacia_el_destino(src, dst, *a, **k):
        if pathlib.Path(dst) == objetivo:
            if fallo.llamadas == 0:
                fallo.llamadas += 1
                real(src, dst, *a, **k)
            raise OSError("disco lleno")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(os, "replace", siempre_falla_hacia_el_destino)
    with pytest.raises(ac.RestauracionFallida):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO, "el escenario debia dejar el candidato en el vivo"
    assert "restauracion_fallida" in _tipos(d)
    assert "promocion_revertida" not in _tipos(d)
    ops = _operaciones(estado)
    assert len(ops) == 1 and (ops[0] / "original").read_bytes() == ORIGINAL.encode()
    assert hashlib.sha256((ops[0] / "original").read_bytes()).hexdigest() == sha_original
    assert len(_bloqueos(estado)) == 1
    # respaldo y diario privados
    assert (ops[0].stat().st_mode & 0o777) == 0o700
    assert ((ops[0] / "original").stat().st_mode & 0o777) == 0o600
    assert ((ops[0] / "diario.json").stat().st_mode & 0o777) == 0o600

    monkeypatch.setattr(os, "replace", real)
    with pytest.raises(ac.PromocionesBloqueadas):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)


# ======================================================== T9 · LA COPIA NO LLEVA SECRETOS NI ENLACES --


def test_T9_la_copia_excluye_secretos_enlaces_y_estado(montaje):
    d, p, objetivo, _ = montaje
    (d / "util.py").write_text("U = 1\n", encoding="utf-8")
    (d / ".env").write_text("CLAVE=x\n", encoding="utf-8")
    (d / ".env.local").write_text("CLAVE=y\n", encoding="utf-8")
    (d / "mi_token.txt").write_text("t\n", encoding="utf-8")
    (d / "api_secret.json").write_text("{}\n", encoding="utf-8")
    (d / "clave.key").write_text("k\n", encoding="utf-8")
    (d / "cert.pem").write_text("p\n", encoding="utf-8")
    (d / "enlace.py").symlink_to(d / "util.py")
    (d / "__pycache__").mkdir()
    (d / "__pycache__" / "x.pyc").write_bytes(b"\0")
    (d / "estado.json").write_text("{}", encoding="utf-8")
    (d / ".control-plane.lock").write_text("", encoding="utf-8")
    visto = {}

    def inspecciona(raiz):
        raiz = pathlib.Path(raiz)
        visto["nombres"] = {q.relative_to(raiz).as_posix() for q in raiz.rglob("*")}
        return True

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=inspecciona)
    assert r["promovido"] is True, "unos vecinos intactos no deben bloquear la promocion"
    nombres = visto["nombres"]
    assert {"s.py", "util.py"} <= nombres, "la copia no incluye el codigo"       # CONTROL
    prohibidos = {".env", ".env.local", "mi_token.txt", "api_secret.json", "clave.key", "cert.pem",
                  "enlace.py", "__pycache__", "__pycache__/x.pyc", "PARADA", ".control-plane.lock"}
    assert not (nombres & prohibidos), f"la copia contiene {nombres & prohibidos}"
    assert "estado.json" in nombres, "el estado se copia (solo lectura) para la fidelidad de la verificacion"
    assert (d / "enlace.py").is_symlink() and (d / ".env").exists(), "se tocaron ficheros del vivo"


def test_T9_un_objetivo_con_nombre_sensible_no_se_puede_aislar_y_no_se_toca(tmp_path, monkeypatch):
    estado = tmp_path / "estado"
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(estado))
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / "token_util.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "x"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba")
    with pytest.raises(ac.CandidatoNoAislable):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


# ============================================================================ REVISIONES (v2) ==
# Dos revisiones independientes (seguridad y codigo) sobre la v1. Cada bloque cita su hallazgo.


def _escenario_muerte(montaje, monkeypatch, modo="antes", exc=None):
    """Deja un diario `preparado` en disco simulando la muerte alrededor del `os.replace`."""
    d, p, objetivo, estado = montaje
    fallo = _FalloDeReplace(monkeypatch, objetivo, exc or SystemExit(9), modo=modo, veces=1)
    with pytest.raises(BaseException):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    fallo.activo = False
    return _operaciones(estado)[0]


def _diario_de(op) -> dict:
    return json.loads((op / "diario.json").read_text(encoding="utf-8"))


def _guardar(op, diario) -> None:
    (op / "diario.json").write_text(json.dumps(diario), encoding="utf-8")


def _motivos_bloqueo(d) -> list[str]:
    return [e["datos"].get("motivo") for e in cp.leer_eventos(d) if e["tipo"] == "promociones_bloqueadas"]


# ------------------------------------------------------------- S-H1 · EL DIARIO NO SE CONFIA --


@pytest.mark.parametrize("forja", ["ruta_externa", "tmp_ajeno", "directorio_distinto", "id_distinto",
                                   "intocable", "tipo_invalido"])
def test_SH1_un_diario_forjado_no_toca_nada_y_bloquea(montaje, monkeypatch, tmp_path, forja):
    d, p, objetivo, estado = montaje
    op = _escenario_muerte(montaje, monkeypatch)
    victima = tmp_path / "victima.txt"
    victima.write_text("V\n", encoding="utf-8")
    intocable = d / "review.py"
    intocable.write_text("R = 1\n", encoding="utf-8")
    sha_v = hashlib.sha256(b"V\n").hexdigest()
    di = _diario_de(op)
    if forja == "ruta_externa":                       # restauraria `original` sobre un fichero ajeno
        di.update(ruta=str(victima), sha_candidato=sha_v, tmp=str(victima.with_name(
            f".{victima.name}.aura-cand-{di['id_op']}.tmp")))
        (op / "original").write_bytes(b"PWNED\n")
    elif forja == "tmp_ajeno":                        # borraria un fichero ajeno como «temporal»
        di.update(tmp=str(victima))
    elif forja == "directorio_distinto":
        di.update(directorio="/otro/directorio")
    elif forja == "id_distinto":
        di.update(id_op="otro")
    elif forja == "intocable":
        di.update(ruta=str(intocable), sha_candidato=_sha(intocable), tmp=str(intocable.with_name(
            f".review.py.aura-cand-{di['id_op']}.tmp")))
        (op / "original").write_bytes(b"PWNED\n")
    elif forja == "tipo_invalido":
        di.update(sha_original=123)
    _guardar(op, di)

    ac.recuperar(d)                                   # no debe lanzar
    assert victima.read_text(encoding="utf-8") == "V\n", "el diario forjado toco un fichero ajeno"
    assert intocable.read_text(encoding="utf-8") == "R = 1\n"
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert op.exists() and len(_bloqueos(estado)) == 1
    assert len(_motivos_bloqueo(d)) == 1 and _motivos_bloqueo(d)[0]


def test_SH1_CONTROL_un_diario_legitimo_se_sigue_recuperando(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    _escenario_muerte(montaje, monkeypatch)
    ac.recuperar(d)
    assert _operaciones(estado) == [] and not _bloqueos(estado)


# --------------------------------------------------- S-M3 / C-B5 · DIARIO CORRUPTO O PARCIAL --


@pytest.mark.parametrize("dano", ["json_invalido", "sin_original", "sin_diario"])
def test_SM3_un_diario_corrupto_o_parcial_bloquea_sin_excepcion_cruda(montaje, monkeypatch, dano):
    d, p, objetivo, estado = montaje
    op = _escenario_muerte(montaje, monkeypatch)
    if dano == "json_invalido":
        (op / "diario.json").write_text("{no es json", encoding="utf-8")
    elif dano == "sin_original":
        (op / "original").unlink()
    else:
        (op / "diario.json").unlink()
    ac.recuperar(d)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert op.exists() and len(_bloqueos(estado)) == 1
    assert _motivos_bloqueo(d), "no quedo evento del bloqueo"


# --------------------------------------------------------- S-H2 · ACTUALIZACION PERDIDA --


def test_SH2_si_el_vivo_cambia_entre_leer_el_original_y_copiar_se_aborta(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    real = ac.shutil.copy2
    cambiado = "VALOR = 1\n# editado a mitad\n"

    def copia_con_carrera(origen, destino, *a, **k):
        if pathlib.Path(origen) == objetivo:
            objetivo.write_text(cambiado, encoding="utf-8")
        return real(origen, destino, *a, **k)

    monkeypatch.setattr(ac.shutil, "copy2", copia_con_carrera)
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["revertido"] is True and r["promovido"] is False and r["motivo"] == "base_cambiada", r
    assert objetivo.read_text(encoding="utf-8") == cambiado, "se perdio la edicion concurrente"
    assert "promocion_abortada_base_cambiada" in _tipos(d)
    assert _operaciones(estado) == []


def test_SH2_el_original_del_diario_es_exactamente_lo_verificado(montaje, monkeypatch):
    """Si el vivo cambia justo antes de `_promover`, no se guarda en el diario algo distinto."""
    d, p, objetivo, estado = montaje
    real = ac._base_intacta
    cambiado = "VALOR = 1\n# otro\n"

    def intacta_y_luego_cambia(*a, **k):
        res = real(*a, **k)
        objetivo.write_text(cambiado, encoding="utf-8")       # carrera tras la precondicion
        return res

    monkeypatch.setattr(ac, "_base_intacta", intacta_y_luego_cambia)
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["promovido"] is False and objetivo.read_text(encoding="utf-8") == cambiado
    assert "promocion_abortada_base_cambiada" in _tipos(d)


def test_SH2_los_finales_de_linea_CRLF_se_conservan_byte_a_byte(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(tmp_path / "estado"))
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / "s.py"
    objetivo.write_bytes(b"A = 0\r\nVALOR = 1\r\nB = 3\r\n")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "x"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba")
    ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert objetivo.read_bytes() == b"A = 0\r\nVALOR = 2\r\nB = 3\r\n"


# ----------------------------------------- C-A1 · LA VERIFICACION AISLADA SE DECLARA, NO SE SUPONE --


def test_CA1_un_verificador_sin_parametros_que_lee_el_vivo_se_RECHAZA_no_se_declara_aislado(montaje):
    """Antes (defecto documentado) el resultado era `verificacion_aislada=False` tras medir el vivo;
    ahora esa medicion ni siquiera se hace: `VerificadorSinRaiz`, vivo intacto, sin evento de cambio."""
    d, p, objetivo, _ = montaje
    lecturas = []
    with pytest.raises(ac.VerificadorSinRaiz):
        ac.ejecutar(d, p, autoridad="ceo",
                    verificacion=lambda: lecturas.append(1) or ORIGINAL in objetivo.read_text())
    assert lecturas == [], "el verificador sin raiz llego a leer el vivo"
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert "cambio_aplicado" not in _tipos(d)


def test_CA1_CONTROL_un_verificador_que_recibe_la_raiz_si_es_aislada(montaje):
    d, p, _, _ = montaje
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["verificacion_aislada"] is True
    evento = [e for e in cp.leer_eventos(d) if e["tipo"] == "cambio_aplicado"][-1]
    assert evento["datos"]["verificacion_aislada"] is True


def test_CA1_sin_verificador_tampoco_es_aislada(montaje):
    d, p, _, _ = montaje
    assert ac.ejecutar(d, p, autoridad="ceo", verificacion=None)["verificacion_aislada"] is False


_TOML = """
id = "capacidad-aislada"
nombre = "x"
version = "1"
estado = "AUTORIZADA"
intencion = "x"
regla_de_transformacion = {{ operacion = "sustituir_texto", buscar = "VALOR = 1", sustituir = "VALOR = 2" }}

[[entradas]]
nombre = "fichero"
fuente = "{o}"
formato = "py"

[[salidas]]
resultado = "x"
destino = "{o}"

[fuentes_de_verdad]
autoridad = ["{o}"]
referencia = []

[perimetro]
modificables = ["{o}"]
fuera_de_alcance = []

[autoridad]
nivel = "REVIEW"
acta = "DR-E"
parte_de_aura = "aplicar"
parte_del_ceo = "autorizar"

[ejecutor]
verbo = "implementar_incremento_especificado"

[efectos]
permitidos = ["sustituir una cadena"]
prohibidos = []
reversible = true

[verificacion]
invariantes = ["INV-9"]
pruebas_minimas = ["{o}"]
criterio_de_aceptacion = "x"
evidencia = "cambio_aplicado"

[trazabilidad]
especificacion = "fixture"
autorizacion = "DR-E"
"""


@necesita_landlock
def test_CA1_la_ruta_de_review_construye_el_verificador_sobre_la_raiz_de_la_copia(
        tmp_path, monkeypatch):
    import contrato as ct
    import orquestador as orq
    import review
    import verificador as vf

    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(tmp_path / "estado"))
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)
    objetivo = tmp_path / "observable.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    caps = tmp_path / "capacidades"
    caps.mkdir()
    (caps / "capacidad-aislada.toml").write_text(_TOML.format(o=objetivo), encoding="utf-8")
    monkeypatch.setattr(ct, "CONTRATOS", caps)
    review.habilitar(tmp_path, alcance=("implementar_incremento_especificado",), por="ceo",
                     acta="DR-E del CEO")
    visto = {}

    def arbol_sano_espia(pruebas, raiz, limite_s=0, confinar=None):
        visto["raiz"] = pathlib.Path(raiz).resolve()
        visto["vivo"] = objetivo.read_text(encoding="utf-8")
        visto["copia"] = (pathlib.Path(raiz) / "observable.py").read_text(encoding="utf-8")
        return vf.Informe(1, 0, 0, 0, False, 0, "")

    monkeypatch.setattr(vf, "ejecutar_pruebas", arbol_sano_espia)
    tarea = {"id": "T-A1", "accion": "implementar_incremento_especificado", "simbolo": "",
             "forma": "funcion", "fichero": str(objetivo), "operacion": "sustituir_texto",
             "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "contrato": "capacidad-aislada"}
    r = review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura", autoridad="orquestador",
                                    verificacion=None)
    assert r["ejecutado"] is True, r
    assert visto["raiz"] != tmp_path.resolve(), "el verificador de review midio el arbol vivo"
    assert visto["vivo"] == ORIGINAL and visto["copia"] == CANDIDATO
    evento = [e for e in cp.leer_eventos(tmp_path) if e["tipo"] == "cambio_aplicado"][-1]
    assert evento["datos"]["verificacion_aislada"] is True


# ------------------------------------------------------ C-A2 · MUTANTES DEL DP SIN PRUEBA --


def test_CA2_una_restauracion_que_escribe_otra_cosa_no_se_da_por_buena(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    real = os.replace
    n = {"destino": 0}

    def replace(src, dst, *a, **k):
        if pathlib.Path(dst) == objetivo:
            n["destino"] += 1
            if n["destino"] == 1:                       # la promocion: se hace y «falla»
                real(src, dst, *a, **k)
                raise OSError("disco lleno")
            pathlib.Path(src).write_bytes(b"BASURA\n")  # la restauracion «tiene exito» con otro contenido
        return real(src, dst, *a, **k)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(ac.RestauracionFallida):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert "restauracion_fallida" in _tipos(d) and "promocion_revertida" not in _tipos(d)
    assert len(_bloqueos(estado)) == 1 and len(_operaciones(estado)) == 1


def test_CA2_un_replace_que_tiene_exito_pero_deja_otro_contenido_se_revierte(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    real = os.replace
    n = {"destino": 0}

    def replace(src, dst, *a, **k):
        if pathlib.Path(dst) == objetivo:
            n["destino"] += 1
            if n["destino"] == 1:
                pathlib.Path(src).write_bytes(b"VALOR = 3\n")   # otro contenido, sin error
        return real(src, dst, *a, **k)

    monkeypatch.setattr(os, "replace", replace)
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["revertido"] is True and r["promovido"] is False and r["motivo"] == "promocion_revertida"
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert "promocion_revertida" in _tipos(d) and _operaciones(estado) == []


# --------------------------------------------------------------- S-M1 · EXCLUSION MUTUA --


def test_SM1_con_el_cerrojo_tomado_recuperar_no_toca_diarios_ajenos(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    op = _escenario_muerte(montaje, monkeypatch, modo="despues")      # vivo == candidato
    cerrojos = list(estado.rglob(".cerrojo"))
    assert len(cerrojos) == 1, "no hay cerrojo en el directorio de estado"
    fd = os.open(cerrojos[0], os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)                               # «otro proceso» en plena promocion
        n = len(cp.leer_eventos(d))
        informe = ac.recuperar(d)
        assert informe.get("ocupado") is True
        assert objetivo.read_text(encoding="utf-8") == CANDIDATO and op.exists()
        assert len(cp.leer_eventos(d)) == n
    finally:
        os.close(fd)
    ac.recuperar(d)                                                  # CONTROL: libre, recupera
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


# ------------------------------------------------- S-M2 · DIRECTORIO DE ESTADO Y TEMPORALES --


def test_SM2_un_estado_en_un_directorio_ajeno_preexistente_no_cambia_sus_permisos(tmp_path, monkeypatch):
    ajeno = tmp_path / "ajeno"
    ajeno.mkdir()
    os.chmod(ajeno, 0o755)
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(ajeno))
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / "s.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "x"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba")
    fallo = _FalloDeReplace(monkeypatch, objetivo, SystemExit(9), modo="antes", veces=1)
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    fallo.activo = False
    assert (ajeno.stat().st_mode & 0o777) == 0o755, "se hizo chmod de un directorio ajeno"
    propio = ajeno / "aura-autoconstruccion"
    assert propio.is_dir() and (propio.stat().st_mode & 0o777) == 0o700
    assert [q.name for q in ajeno.iterdir()] == ["aura-autoconstruccion"]


def test_SM2_un_symlink_plantado_como_temporal_no_se_sigue(montaje, monkeypatch, tmp_path):
    d, p, objetivo, estado = montaje
    victima = tmp_path / "victima.txt"
    victima.write_text("V\n", encoding="utf-8")
    monkeypatch.setattr(ac.secrets, "token_hex", lambda n=32: "a" * (2 * n))
    plantado = d / f".s.py.aura-cand-{'a' * 16}.tmp"
    plantado.symlink_to(victima)
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert victima.read_text(encoding="utf-8") == "V\n", "se escribio a traves del symlink plantado"
    assert r["promovido"] is False and objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert plantado.is_symlink(), "se borro algo que no creo esta operacion"


# --------------------------------------------------------------------- S-M4 · CONFINAMIENTO --


def test_SM4_el_resultado_declara_que_la_verificacion_no_esta_confinada(montaje):
    d, p, _, _ = montaje
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["ejecucion_confinada"] is False
    evento = [e for e in cp.leer_eventos(d) if e["tipo"] == "cambio_aplicado"][-1]
    assert evento["datos"]["ejecucion_confinada"] is False


# --------------------------------------------------------------------- S-M5 · EXCLUSIONES --


def test_SM5_la_copia_excluye_credenciales_claves_y_directorios_pesados(montaje):
    d, p, objetivo, _ = montaje
    for nombre in ("credentials.json", ".netrc", "id_rsa", "id_rsa.pub", "a.p12", "b.pfx"):
        (d / nombre).write_text("x", encoding="utf-8")
    for dirname in ("secrets", ".ssh", ".venv", "node_modules", ".git"):
        (d / dirname).mkdir()
        (d / dirname / "f.py").write_text("x", encoding="utf-8")
    visto = {}

    def inspecciona(raiz):
        visto["n"] = {q.relative_to(raiz).as_posix() for q in pathlib.Path(raiz).rglob("*")}
        return True

    ac.ejecutar(d, p, autoridad="ceo", verificacion=inspecciona)
    prohibidos = {"credentials.json", ".netrc", "id_rsa", "id_rsa.pub", "a.p12", "b.pfx", "secrets",
                  "secrets/f.py", ".ssh", ".ssh/f.py", ".venv", ".venv/f.py", "node_modules",
                  "node_modules/f.py", ".git", ".git/f.py"}
    assert "s.py" in visto["n"] and not (visto["n"] & prohibidos), visto["n"] & prohibidos


# ------------------------------------------------------- C-M1 · RAMA `promovido` DE recuperar --


def test_CM1_muerte_tras_promovido_y_antes_del_evento_recuperar_registra_y_cierra(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    real = cp.registrar_evento

    def evento_con_muerte(directorio, tipo, datos=None):
        if tipo == "cambio_aplicado":
            raise SystemExit(9)
        return real(directorio, tipo, datos)

    monkeypatch.setattr(cp, "registrar_evento", evento_con_muerte)
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    monkeypatch.setattr(cp, "registrar_evento", real)
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO
    assert _diario_de(_operaciones(estado)[0])["estado"] == "promovido"

    ac.recuperar(d)
    aplicados = [e for e in cp.leer_eventos(d) if e["tipo"] == "cambio_aplicado"]
    assert len(aplicados) == 1 and aplicados[0]["datos"]["promovido"] is True
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO and _operaciones(estado) == []
    n = len(cp.leer_eventos(d))
    ac.recuperar(d)
    assert len(cp.leer_eventos(d)) == n


def test_CM1_si_el_evento_ya_constaba_no_se_duplica(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    real = ac.shutil.rmtree

    def rmtree_con_muerte(ruta, *a, **k):
        if pathlib.Path(ruta).parent.parent == estado / "aura-autoconstruccion" or \
                pathlib.Path(ruta).parent.name and pathlib.Path(ruta).parent.parent.name == "aura-autoconstruccion":
            raise SystemExit(9)
        return real(ruta, *a, **k)

    monkeypatch.setattr(ac.shutil, "rmtree", rmtree_con_muerte)
    with pytest.raises(SystemExit):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    monkeypatch.setattr(ac.shutil, "rmtree", real)
    assert len(_operaciones(estado)) == 1
    ac.recuperar(d)
    aplicados = [e for e in cp.leer_eventos(d) if e["tipo"] == "cambio_aplicado"]
    assert len(aplicados) == 1, "se duplico el cambio_aplicado"
    assert _operaciones(estado) == [] and objetivo.read_text(encoding="utf-8") == CANDIDATO


def test_SL2_si_falla_guardar_el_diario_promovido_recuperar_restaura(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    real = os.replace
    n = {"diario": 0}

    def replace(src, dst, *a, **k):
        if pathlib.Path(dst).name == "diario.json":
            n["diario"] += 1
            if n["diario"] == 2:                       # el segundo: marcar `promovido`
                raise OSError("disco lleno")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(OSError):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    monkeypatch.setattr(os, "replace", real)
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO
    assert _diario_de(_operaciones(estado)[0])["estado"] == "preparado"
    ac.recuperar(d)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL and _operaciones(estado) == []


# --------------------------------------------------------------------------- C-M2 · MOTIVO --


def test_CM2_el_motivo_del_rechazo_va_al_resultado_y_al_evento(montaje):
    d, p, _, _ = montaje
    cases = [(lambda raiz: False, "verificacion"), (None, "no_medido")]
    for verificacion, esperado in cases:
        r = ac.ejecutar(d, p, autoridad="ceo", verificacion=verificacion)
        assert r["revertido"] is True and r["motivo"] == esperado, r
        assert [e for e in cp.leer_eventos(d)
                if e["tipo"] == "cambio_aplicado"][-1]["datos"]["motivo"] == esperado


def test_CM2_CONTROL_un_cambio_promovido_no_lleva_motivo_de_rechazo(montaje):
    d, p, _, _ = montaje
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["revertido"] is False and not r.get("motivo")


# --------------------------------------------------------------- C-M3 · COPIAS HUERFANAS --


def _marcar(copia, pid, hace_s) -> None:
    (copia / ".aura-candidato-marca").write_text(
        json.dumps({"marca": "m", "pid": pid, "t": time.time() - hace_s}), encoding="utf-8")


def test_CM3_recuperar_barre_solo_copias_propias_muertas_y_antiguas(montaje, monkeypatch, tmp_path):
    d, p, _, _ = montaje
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmpdir))
    muerto = subprocess.Popen([sys.executable, "-c", "pass"])
    muerto.wait()
    casos = {}
    for nombre, pid, edad in (("aura-candidato-vieja", muerto.pid, 7200),
                              ("aura-candidato-reciente", muerto.pid, 60),
                              ("aura-candidato-viva", os.getpid(), 7200)):
        casos[nombre] = tmpdir / nombre
        casos[nombre].mkdir()
        _marcar(casos[nombre], pid, edad)
    sin_marca = tmpdir / "aura-candidato-sinmarca"
    sin_marca.mkdir()
    ajena = tmpdir / "otra-cosa"
    ajena.mkdir()
    _marcar(ajena, muerto.pid, 7200)

    ac.recuperar(d)
    assert not casos["aura-candidato-vieja"].exists(), "no se barrio la copia huerfana"
    assert casos["aura-candidato-reciente"].exists() and casos["aura-candidato-viva"].exists()
    assert sin_marca.exists() and ajena.exists(), "se borro algo que no era una copia propia"


def test_CM3_un_fallo_a_mitad_del_volcado_no_deja_copia(montaje, monkeypatch, tmp_path):
    d, p, objetivo, _ = montaje
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmpdir))
    (d / "otro.py").write_text("X = 1\n", encoding="utf-8")

    def falla(*a, **k):
        raise OSError("disco lleno")

    monkeypatch.setattr(ac.shutil, "copy2", falla)
    with pytest.raises(OSError):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert list(tmpdir.iterdir()) == [], "quedo una copia huerfana"
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


# --------------------------------------------------------------------------- BAJOS (eventos) --


def test_SL1_un_destino_no_aislable_deja_evento(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(tmp_path / "estado"))
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / "token_util.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "x"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba")
    with pytest.raises(ac.CandidatoNoAislable):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert "candidato_no_aislable" in _tipos(d)


def test_SL1_la_PARADA_en_la_recomprobacion_deja_evento(montaje):
    d, p, _, _ = montaje

    def arma(raiz):
        (d / "PARADA").write_text("", encoding="utf-8")
        return True

    with pytest.raises(ac.ParadaActiva):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=arma)
    assert "promocion_abortada_parada" in _tipos(d)


def test_SL1_un_bloqueo_deja_evento_al_negarse_a_ejecutar(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    _escenario_muerte(montaje, monkeypatch)
    objetivo.write_text("VALOR = 99\n", encoding="utf-8")
    ac.recuperar(d)
    with pytest.raises(ac.PromocionesBloqueadas):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert "promocion_rechazada_por_bloqueo" in _tipos(d)


def test_CB3_el_modo_del_fichero_se_conserva_al_promover(montaje):
    d, p, objetivo, _ = montaje
    os.chmod(objetivo, 0o755)
    ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert (objetivo.stat().st_mode & 0o777) == 0o755


# ============================================================ RE-REVISION DE SEGURIDAD (v3) ==


@pytest.mark.parametrize("fuera_de_zona", ["adr/0003-politica.md", "docs/1.1-constitucion.md"])
def test_R1_un_diario_forjado_sobre_un_fichero_fuera_de_zona_no_se_escribe(
        montaje, monkeypatch, fuera_de_zona):
    d, p, objetivo, estado = montaje
    op = _escenario_muerte(montaje, monkeypatch)
    victima = d / fuera_de_zona
    victima.parent.mkdir(parents=True, exist_ok=True)
    victima.write_text("GOBERNANZA\n", encoding="utf-8")
    assert ac.zona_permitida(victima, raiz=d) is False         # el escenario es el que dice ser
    di = _diario_de(op)
    di.update(ruta=str(victima.resolve()), sha_candidato=_sha(victima),
              tmp=str(victima.resolve().with_name(f".{victima.name}.aura-cand-{di['id_op']}.tmp")))
    (op / "original").write_bytes(b"PWNED\n")
    di["sha_original"] = hashlib.sha256(b"PWNED\n").hexdigest()
    _guardar(op, di)
    ac.recuperar(d)
    assert victima.read_text(encoding="utf-8") == "GOBERNANZA\n", "se reescribio un fichero fuera de zona"
    assert op.exists() and len(_bloqueos(estado)) == 1 and _motivos_bloqueo(d)


def test_R2_un_bloqueo_aparecido_durante_la_verificacion_impide_promover(montaje):
    d, p, objetivo, estado = montaje

    def planta_bloqueo(raiz):
        ac._asegurar_estado(ac._dir_estado(d))
        (ac._dir_estado(d) / "BLOQUEADO").write_text("{}", encoding="utf-8")
        return True

    with pytest.raises(ac.PromocionesBloqueadas):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=planta_bloqueo)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert "promocion_rechazada_por_bloqueo" in _tipos(d)


def test_R2_un_diario_pendiente_ajeno_aparecido_durante_la_verificacion_impide_promover(montaje):
    d, p, objetivo, estado = montaje

    def planta_pendiente(raiz):
        ajeno = ac._dir_estado(d) / ("b" * 16)
        ac._asegurar_estado(ac._dir_estado(d))
        ajeno.mkdir()                                           # un proceso muerto dejo una operacion
        return True

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=planta_pendiente)
    assert r["promovido"] is False and r["revertido"] is True and r["motivo"] == "diario_pendiente_ajeno"
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL
    assert "promocion_abortada_diario_pendiente" in _tipos(d)


@necesita_landlock
def test_RA_review_propaga_las_claves_de_la_verificacion_aislada(tmp_path, monkeypatch):
    import contrato as ct
    import orquestador as orq
    import review
    import verificador as vf

    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(tmp_path / "estado"))
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)
    monkeypatch.setattr(vf, "ejecutar_pruebas",
                        lambda pruebas, raiz, limite_s=0, confinar=None: vf.Informe(1, 0, 0, 0, False, 0, ""))
    objetivo = tmp_path / "observable.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    caps = tmp_path / "capacidades"
    caps.mkdir()
    (caps / "capacidad-aislada.toml").write_text(_TOML.format(o=objetivo), encoding="utf-8")
    monkeypatch.setattr(ct, "CONTRATOS", caps)
    review.habilitar(tmp_path, alcance=("implementar_incremento_especificado",), por="ceo",
                     acta="DR-E del CEO")
    tarea = {"id": "T-RA", "accion": "implementar_incremento_especificado", "simbolo": "",
             "forma": "funcion", "fichero": str(objetivo), "operacion": "sustituir_texto",
             "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "contrato": "capacidad-aislada"}
    r = review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura", autoridad="orquestador")
    assert r["verificacion_aislada"] is True and r["ejecucion_confinada"] is LANDLOCK
    assert r["promovido"] is True
    for clave in ("ejecutado", "revisor", "objeciones", "efecto_verificado", "revertido", "propuesta"):
        assert clave in r, f"se quito la clave {clave}"


def test_RB_un_parametro_con_valor_por_defecto_no_es_la_raiz(montaje):
    def con_plazo(timeout=5):
        return True

    def con_raiz(raiz):
        return True

    def con_raiz_opcional(raiz=None):
        return True

    assert ac._acepta_raiz(con_plazo) is False
    assert ac._acepta_raiz(lambda: True) is False
    assert ac._acepta_raiz(con_raiz) is True and ac._acepta_raiz(con_raiz_opcional) is True
    d, p, objetivo, _ = montaje
    with pytest.raises(ac.VerificadorSinRaiz):                    # un `timeout=5` no recibe la raiz
        ac.ejecutar(d, p, autoridad="ceo", verificacion=con_plazo)
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


@pytest.mark.parametrize("t", [float("nan"), float("inf"), float("-inf")])
def test_RM_una_marca_con_hora_no_finita_no_se_barre(montaje, monkeypatch, tmp_path, t):
    d, p, _, _ = montaje
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmpdir))
    muerto = subprocess.Popen([sys.executable, "-c", "pass"])
    muerto.wait()
    copia = tmpdir / "aura-candidato-rara"
    copia.mkdir()
    (copia / ".aura-candidato-marca").write_text(
        json.dumps({"marca": "m", "pid": muerto.pid, "t": t}), encoding="utf-8")
    ac.recuperar(d)
    assert copia.exists(), "se borro una copia con marca invalida"


# ============================================ LIMPIEZA DEL ESTADO VACIO + CERROJO POR INODO ==


def _subdirs_de_estado(estado) -> list[pathlib.Path]:
    base = estado / "aura-autoconstruccion"
    return sorted(base.iterdir()) if base.exists() else []


def test_LI_tras_promover_no_queda_el_subdirectorio_de_estado(montaje):
    d, p, objetivo, estado = montaje
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["promovido"] is True
    assert _subdirs_de_estado(estado) == [], "quedo estado vacio tras una promocion cerrada"
    assert (estado / "aura-autoconstruccion").is_dir(), "no se debe borrar el directorio base (compartido)"


def test_LI_tras_un_aborto_dentro_del_cerrojo_tampoco_queda(montaje):
    d, p, objetivo, estado = montaje

    def otro_edita(raiz):
        objetivo.write_text("VALOR = 1\n# otro\n", encoding="utf-8")
        return True

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=otro_edita)
    assert r["motivo"] == "base_cambiada"
    assert _subdirs_de_estado(estado) == []


def test_LI_un_rechazo_no_crea_estado(montaje):
    d, p, _, estado = montaje
    ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: False)
    assert _subdirs_de_estado(estado) == []


def test_LI_recuperar_sin_nada_pendiente_retira_un_estado_con_solo_cerrojo(montaje):
    d, p, _, estado = montaje
    residuo = ac._dir_estado(d)
    ac._asegurar_estado(residuo)
    (residuo / ".cerrojo").write_text("", encoding="utf-8")
    ac.recuperar(d)
    assert _subdirs_de_estado(estado) == []


def test_LI_recuperar_sin_estado_no_lo_crea(montaje):
    d, p, _, estado = montaje
    ac.recuperar(d)
    assert not estado.exists()


def test_LI_con_un_diario_pendiente_no_se_borra_nada(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    op = _escenario_muerte(montaje, monkeypatch)
    antes = sorted(q.relative_to(estado).as_posix() for q in estado.rglob("*"))
    informe = ac.recuperar(d)                               # lo resuelve; antes de eso el diario existia
    assert antes and op.name in " ".join(antes)
    assert informe["resultados"] == ["sin_cambios"]


def test_LI_con_BLOQUEADO_no_se_borra_nada(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    _escenario_muerte(montaje, monkeypatch)
    objetivo.write_text("VALOR = 99\n", encoding="utf-8")
    ac.recuperar(d)                                          # ambiguo => bloqueo
    antes = sorted(q.relative_to(estado).as_posix() for q in estado.rglob("*"))
    ac.recuperar(d)
    with pytest.raises(ac.PromocionesBloqueadas):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert sorted(q.relative_to(estado).as_posix() for q in estado.rglob("*")) == antes
    assert any(n.endswith("BLOQUEADO") for n in antes)


def test_LI_con_un_diario_ajeno_pendiente_el_estado_se_conserva(montaje):
    d, p, objetivo, estado = montaje

    def planta(raiz):
        ac._asegurar_estado(ac._dir_estado(d))
        (ac._dir_estado(d) / ("b" * 16)).mkdir()
        return True

    ac.ejecutar(d, p, autoridad="ceo", verificacion=planta)
    assert (ac._dir_estado(d) / ("b" * 16)).is_dir() and (ac._dir_estado(d) / ".cerrojo").exists()


def test_LI_el_cerrojo_se_reintenta_si_otro_proceso_lo_borro_y_recreo(montaje, monkeypatch):
    d, p, _, estado = montaje
    dest = ac._dir_estado(d)
    ac._asegurar_estado(dest)
    real = ac.fcntl.flock
    n = {"veces": 0}

    def flock_con_carrera(fd, operacion):
        real(fd, operacion)
        n["veces"] += 1
        if n["veces"] == 1:                                  # «otro proceso» retira y recrea el cerrojo
            (dest / ".cerrojo").unlink()
            (dest / ".cerrojo").write_text("", encoding="utf-8")

    monkeypatch.setattr(ac.fcntl, "flock", flock_con_carrera)
    with ac._cerrojo(dest, bloqueante=True) as tomado:
        assert tomado is True
        assert n["veces"] == 2, "no se reintento tras detectar que el inodo cambio"


# ------------------------------------------------ MUTACION (2026-10-22) · huecos que dejo la v2 --
# Hallados por `mutaciones/candidato-aislado.toml`: las pruebas de diario forjado usaban un `sha_original`
# incoherente con el respaldo, asi que lo rechazaba la comprobacion del respaldo y no la de la ruta.
# Aqui el diario es COHERENTE (sha, id, temporal, directorio) y solo la RUTA es vedada.


def _diario_coherente_sobre(op, victima, original=b"PWNED\n"):
    (op / "original").write_bytes(original)
    di = _diario_de(op)
    di.update(ruta=str(victima.resolve()), sha_original=hashlib.sha256(original).hexdigest(),
              sha_candidato=_sha(victima),
              tmp=str(victima.resolve().with_name(f".{victima.name}.aura-cand-{di['id_op']}.tmp")))
    _guardar(op, di)


def test_SH1b_CONTROL_un_diario_coherente_sobre_una_ruta_normal_si_se_obedece(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    op = _escenario_muerte(montaje, monkeypatch)
    otro = d / "otro.py"
    otro.write_text("V = 1\n", encoding="utf-8")
    _diario_coherente_sobre(op, otro)
    ac.recuperar(d)
    assert otro.read_bytes() == b"PWNED\n", "el escenario forjado no es valido: la prueba no mide nada"
    assert not _bloqueos(estado)


@pytest.mark.parametrize("forja", ["intocable", "sensible", "dir_excluido", "fuera_del_directorio"])
def test_SH1b_un_diario_coherente_sobre_una_ruta_vedada_no_se_obedece(
        montaje, monkeypatch, tmp_path, forja):
    d, p, objetivo, estado = montaje
    op = _escenario_muerte(montaje, monkeypatch)
    if forja == "fuera_del_directorio":     # autorizado por acta en el repo, pero NO colgando de `d`
        monkeypatch.setattr(ac, "_RAIZ_REPO", tmp_path.resolve())
        monkeypatch.setattr(ac, "_FICHEROS_AUTORIZADOS", frozenset({"fuera/f.py"}))
        victima = tmp_path / "fuera" / "f.py"
    else:
        victima = d / {"intocable": "review.py", "sensible": "mi_token.py",
                       "dir_excluido": ".venv/x.py"}[forja]
    victima.parent.mkdir(parents=True, exist_ok=True)
    victima.write_text("V = 1\n", encoding="utf-8")
    _diario_coherente_sobre(op, victima)
    ac.recuperar(d)
    assert victima.read_text(encoding="utf-8") == "V = 1\n", f"un diario sobre {forja} se obedecio"
    assert op.exists() and len(_bloqueos(estado)) == 1 and _motivos_bloqueo(d)


def test_SM2_un_temporal_preexistente_no_se_reutiliza_ni_se_trunca(montaje, monkeypatch):
    d, p, objetivo, estado = montaje
    monkeypatch.setattr(ac.secrets, "token_hex", lambda n=32: "a" * (2 * n))
    plantado = d / f".s.py.aura-cand-{'a' * 16}.tmp"
    plantado.write_text("AJENO\n", encoding="utf-8")
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert plantado.read_text(encoding="utf-8") == "AJENO\n", "se reutilizo un temporal preexistente"
    assert r["promovido"] is False and objetivo.read_text(encoding="utf-8") == ORIGINAL


def test_T9_la_copia_no_arrastra_el_contenido_de_un_directorio_enlazado(montaje, tmp_path):
    d, p, objetivo, _ = montaje
    fuera = tmp_path / "fuera_del_arbol"
    fuera.mkdir()
    (fuera / "ajeno.py").write_text("AJENO = 1\n", encoding="utf-8")
    (d / "enlace_dir").symlink_to(fuera, target_is_directory=True)
    visto = {}

    def inspecciona(raiz):
        raiz = pathlib.Path(raiz)
        visto["nombres"] = {q.relative_to(raiz).as_posix() for q in raiz.rglob("*")}
        return True

    ac.ejecutar(d, p, autoridad="ceo", verificacion=inspecciona)
    assert "s.py" in visto["nombres"]                                                  # CONTROL
    assert not any("ajeno.py" in n or n.startswith("enlace_dir") for n in visto["nombres"]), \
        f"la copia arrastro contenido de fuera: {visto['nombres']}"



# ======================================== FASE A · VERIFICACION REAL EN LA COPIA, RESULTADO ESTRUCTURADO ==

import contrato as ct  # noqa: E402
import orquestador as orq  # noqa: E402
import review  # noqa: E402


def _montaje_review(tmp_path, monkeypatch, test_src, *, prueba_fuera=None):
    """Directorio de review con `mod.py` (VALOR = 1) y un contrato cuya `pruebas_minimas` es una RUTA
    ABSOLUTA, como los contratos reales. Devuelve (objetivo, tarea, fichero_marca)."""
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(tmp_path / "estado"))
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)
    d = tmp_path / "cp"
    d.mkdir()
    objetivo = d / "mod.py"
    objetivo.write_text(ORIGINAL, encoding="utf-8")
    marca = tmp_path / "marca.txt"
    prueba = d / "test_mod.py"
    decoy = tmp_path / "decoy.txt"
    decoy.write_text("INTACTO", encoding="utf-8")
    prueba.write_text(test_src.format(marca=str(marca), decoy=str(decoy), live=str(d.resolve()),
                                      ruta=str(tmp_path / "enruta" / "lee.txt")),
                      encoding="utf-8")
    declarada = prueba_fuera or prueba
    caps = tmp_path / "capacidades"
    caps.mkdir()
    texto = _TOML.format(o=objetivo).replace(f'pruebas_minimas = ["{objetivo}"]',
                                             f'pruebas_minimas = ["{declarada}"]')
    (caps / "capacidad-aislada.toml").write_text(texto, encoding="utf-8")
    monkeypatch.setattr(ct, "CONTRATOS", caps)
    review.habilitar(d, alcance=("implementar_incremento_especificado",), por="ceo", acta="DR-E del CEO")
    tarea = {"id": "T-FA", "accion": "implementar_incremento_especificado", "simbolo": "",
             "forma": "funcion", "fichero": str(objetivo), "operacion": "sustituir_texto",
             "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "contrato": "capacidad-aislada"}
    return d, objetivo, tarea, marca


# Las pruebas corren CONFINADAS (solo escriben en la copia): la comprobacion de DONDE se cargo el
# modulo va dentro de la prueba, no en un fichero externo.
_TEST_ESPERA_2 = ("import mod, os\n"
                  "def test_valor():\n"
                  "    assert os.path.dirname(os.path.realpath(mod.__file__)) != {live!r}\n"
                  "    assert mod.VALOR == 2\n")
_TEST_ESPERA_1 = ("import mod\n"
                  "def test_valor():\n    assert mod.VALOR == 1\n")


def _llama(d, tarea):
    return review.ejecutar_bajo_review(d, tarea, propuesto_por="aura", autoridad="orquestador")


def test_FA1_una_prueba_con_ruta_absoluta_verifica_el_CANDIDATO_y_se_promueve(tmp_path, monkeypatch):
    d, objetivo, tarea, marca = _montaje_review(tmp_path, monkeypatch, _TEST_ESPERA_2.replace("{marca!r}", "{marca!r}"))
    r = _llama(d, tarea)
    assert r["ejecutado"] is True, f"se midio el vivo (VALOR=1) en vez del candidato: {r}"
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO
    assert r["verificacion_aislada"] is True


def test_FA1_sin_fallback_al_arbol_vivo_el_modulo_se_carga_de_la_copia(tmp_path, monkeypatch):
    """La propia prueba asierta que `mod` NO viene del vivo; si cayera al vivo, fallaria y se rechazaria."""
    d, objetivo, tarea, marca = _montaje_review(tmp_path, monkeypatch, _TEST_ESPERA_2)
    r = _llama(d, tarea)
    assert r["ejecutado"] is True, r


def test_FA1_el_inverso_un_candidato_que_incumple_la_prueba_se_rechaza(tmp_path, monkeypatch):
    d, objetivo, tarea, marca = _montaje_review(tmp_path, monkeypatch, _TEST_ESPERA_1)
    r = _llama(d, tarea)
    assert r["ejecutado"] is False and r["motivo"] == "verificacion", r
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


# `mod` ya importado desde el VIVO por el proceso padre; la prueba comprueba, desde la copia, que su
# `mod` es el de la copia (la prueba y `mod.py` viajan juntos en la copia: mismo directorio).
_TEST_MODULO_YA_IMPORTADO = ("import mod, os\n"
                             "def test_valor():\n"
                             "    aqui = os.path.dirname(os.path.realpath(__file__))\n"
                             "    assert os.path.dirname(os.path.realpath(mod.__file__)) == aqui\n"
                             "    assert aqui != {live!r} and not aqui.startswith({live!r} + os.sep)\n"
                             "    assert mod.VALOR == 2\n")


def test_FA6_un_modulo_previamente_importado_del_vivo_no_contamina_la_verificacion(tmp_path, monkeypatch):
    """Sin fallback al vivo: el padre YA tiene `mod` (del vivo) en `sys.modules`; la verificacion corre
    en un subproceso sobre la copia y carga el `mod` de la copia. CONTROL: el padre si ve el del vivo."""
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _TEST_MODULO_YA_IMPORTADO)
    monkeypatch.syspath_prepend(str(d))
    monkeypatch.delitem(sys.modules, "mod", raising=False)
    import importlib
    previo = importlib.import_module("mod")
    try:
        assert pathlib.Path(previo.__file__).resolve() == objetivo.resolve(), "control: el padre no tiene el del vivo"
        assert previo.VALOR == 1
        r = _llama(d, tarea)
        assert r["ejecutado"] is True and r["verificacion_aislada"] is True, r
        assert objetivo.read_text(encoding="utf-8") == CANDIDATO
        assert sys.modules["mod"] is previo, "la verificacion toco el sys.modules del padre"
    finally:
        sys.modules.pop("mod", None)


_TEST_LEE_DATOS = ("import os\n"
                   "import mod\n"
                   "def test_datos():\n"
                   "    aqui = os.path.dirname(os.path.realpath(__file__))\n"
                   "    assert os.path.exists(os.path.join(aqui, 'estado.json'))\n"
                   "    with open(os.path.join(aqui, 'eventos.jsonl'), 'a') as fh:\n"
                   "        fh.write('ESCRITO_POR_LA_PRUEBA\\n')\n"
                   "    assert mod.VALOR == 2\n")


def test_FA6_estado_y_eventos_viajan_como_DATOS_en_la_copia_y_los_reales_no_se_alteran(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _TEST_LEE_DATOS)
    (d / "estado.json").write_text("{}", encoding="utf-8")
    (d / "eventos.jsonl").write_text("", encoding="utf-8") if not (d / "eventos.jsonl").exists() else None
    sha_estado = _sha(d / "estado.json")
    log_antes = (d / "eventos.jsonl").read_bytes()
    r = _llama(d, tarea)
    assert r["ejecutado"] is True, f"la prueba no hallo estado/eventos dentro de la copia: {r}"
    log_despues = (d / "eventos.jsonl").read_bytes()
    assert b"ESCRITO_POR_LA_PRUEBA" not in log_despues, "la prueba escribio en el log REAL"
    assert log_despues.startswith(log_antes), "el log real no solo crecio: se reescribio"
    assert _sha(d / "estado.json") == sha_estado, "el estado.json real cambio"


def test_FA2_una_prueba_fuera_de_la_copia_no_es_aislable_y_se_rechaza(tmp_path, monkeypatch):
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    ajena = fuera / "test_ajena.py"
    ajena.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _TEST_ESPERA_2, prueba_fuera=ajena)
    r = _llama(d, tarea)
    assert r["ejecutado"] is False and r["motivo"] == "pruebas_fuera_de_la_copia", r
    assert r["verificacion_aislada"] is False
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


def test_FA3_error_de_infraestructura_en_el_verificador_de_review(tmp_path, monkeypatch):
    import verificador as vf
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _TEST_ESPERA_2)

    def revienta(*a, **k):
        raise RuntimeError("sin cuota")

    monkeypatch.setattr(vf, "ejecutar_pruebas", revienta)
    r = _llama(d, tarea)
    assert r["ejecutado"] is False and r["motivo"] == "error_infraestructura", r
    monkeypatch.setattr(vf, "ejecutar_pruebas", lambda *a, **k: vf.Informe(0, 0, 0, 0, True, None, "plazo"))
    r = _llama(d, tarea)
    assert r["motivo"] == "error_infraestructura", "un plazo agotado no es un fallo de la prueba"


@pytest.mark.parametrize("res,aislada,sana,motivo,confinada", [
    (("sano", True, False, ""), True, True, None, False),
    (("sano", False, False, ""), False, True, None, False),          # lo declarado manda, no la intencion
    (("sano", True, True, ""), True, True, None, True),
    (("fallo", True, False, "x"), True, False, "verificacion", False),
    (("error_infraestructura", False, False, "x"), False, None, "error_infraestructura", False),
    (("no_aislable", False, False, "x"), False, None, "pruebas_fuera_de_la_copia", False),
])
def test_FA3_ejecutar_deriva_los_campos_del_ResultadoVerificacion(
        montaje, res, aislada, sana, motivo, confinada):
    d, p, objetivo, _ = montaje
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: ac.ResultadoVerificacion(*res))
    assert r["verificacion_aislada"] is aislada and r["verificacion_sana"] is sana, r
    assert r.get("motivo") == motivo and r["ejecucion_confinada"] is confinada, r
    assert r["promovido"] is (res[0] == "sano")
    assert objetivo.read_text(encoding="utf-8") == (CANDIDATO if res[0] == "sano" else ORIGINAL)


def test_FA3_un_estado_desconocido_se_rechaza(montaje):
    d, p, objetivo, _ = montaje
    r = ac.ejecutar(d, p, autoridad="ceo",
                    verificacion=lambda raiz: ac.ResultadoVerificacion("quiza", True, False, ""))
    assert r["promovido"] is False and objetivo.read_text(encoding="utf-8") == ORIGINAL


def test_FA4_el_estado_y_el_log_se_copian_pero_el_real_no_cambia(montaje):
    d, p, objetivo, _ = montaje
    (d / "estado.json").write_text("{}", encoding="utf-8")
    log = d / "eventos.jsonl"
    assert log.exists()
    visto = {}

    def escribe_en_la_copia(raiz):
        raiz = pathlib.Path(raiz)
        visto["copiado"] = (raiz / "eventos.jsonl").exists() and (raiz / "estado.json").exists()
        visto["sha_antes"] = _sha(log)
        with open(raiz / "eventos.jsonl", "a", encoding="utf-8") as fh:
            fh.write("ESCRITO_EN_LA_COPIA\n")
        visto["sha_durante"] = _sha(log)
        return True

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=escribe_en_la_copia)
    assert visto["copiado"] is True
    assert visto["sha_durante"] == visto["sha_antes"], "escribir en la copia cambio el log real"
    assert "ESCRITO_EN_LA_COPIA" not in log.read_text(encoding="utf-8")
    assert r["promovido"] is True, "el log/estado copiados no deben contar en la precondicion de hashes"


def test_FA4_el_log_real_que_crece_durante_la_verificacion_no_aborta_la_promocion(montaje):
    d, p, _, _ = montaje

    def otro_proceso_registra(raiz):
        cp.registrar_evento(d, "otro_evento", {})
        return True

    assert ac.ejecutar(d, p, autoridad="ceo", verificacion=otro_proceso_registra)["promovido"] is True


# --------------------------------------------- E2E · LOS DOS CONTRATOS REALES (sin modificarlos) --

_CONTRATOS_REALES = [("sexta-fuente-estancamiento", "estancamiento.py"),
                     ("etiqueta-observatorio-efecto", "observatorio.py")]


@pytest.mark.parametrize("identificador,modulo", _CONTRATOS_REALES)
def test_FA5_E2E_los_contratos_reales_se_verifican_en_la_copia(identificador, modulo, tmp_path,
                                                               monkeypatch):
    """Las pruebas reales corren sobre una COPIA del plano: sano con la copia intacta y FALLO si el
    candidato (en la copia) rompe el modulo — lo que demuestra que no se mide el vivo. Marcada lenta."""
    contrato = ct.contrato_de(identificador)
    assert contrato, f"no se pudo leer el contrato {identificador}"
    declaradas = contrato["verificacion"]["pruebas_minimas"]
    if not all(pathlib.Path(x).resolve().is_relative_to(PLANO.resolve()) for x in declaradas):
        pytest.skip("el contrato declara rutas de otro checkout")
    monkeypatch.setenv("AURA_AUTOCONSTRUCCION_ESTADO", str(tmp_path / "estado"))
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)
    verifica = review._verificador_de_review(contrato, PLANO)
    copia, marca, manifiesto, _ = ac._crear_copia(PLANO.resolve(), pathlib.PurePath(modulo))
    try:
        sano = verifica(copia)
        assert sano.estado == "sano" and sano.aislada is True, sano
        assert sano.confinada is LANDLOCK, "el contrato real debe verificarse confinado"
        with open(copia / modulo, "a", encoding="utf-8") as fh:
            fh.write("\nraise RuntimeError('candidato roto en la copia')\n")
        roto = verifica(copia)
        assert roto.estado == "fallo" and roto.aislada is True, (
            f"el candidato roto de la copia no se noto: se midio el vivo ({roto})")
    finally:
        import shutil
        shutil.rmtree(copia, ignore_errors=True)



# ============================================== FASE B · VERIFICACION CONFINADA (Landlock) ==
# Politica: la verificacion por contrato es CONFINADA OBLIGATORIA. Sin Landlock efectivo no se ejecuta
# ninguna prueba y se rechaza (`confinamiento_no_disponible`): no se rebaja en silencio.

import verificador as vf  # noqa: E402

_T_CONFINADA_OK = "import mod\ndef test_v():\n    assert mod.VALOR == 2\n"
_T_ESCRIBE_SENUELO = ("import mod\ndef test_v():\n    open({decoy!r}, 'w').write('TOCADO')\n"
                      "    assert mod.VALOR == 2\n")
_T_NIETO = ("import mod, subprocess, sys\n"
            "def test_v():\n"
            "    nieto = \"open({decoy!r}, 'w').write('TOCADO')\"\n"
            "    hijo = 'import subprocess,sys; subprocess.run([sys.executable, \"-c\", ' + repr(nieto) + '], check=True)'\n"
            "    r = subprocess.run([sys.executable, '-c', hijo])\n"
            "    assert r.returncode == 0\n")
_T_LEE_SENUELO = ("import mod\ndef test_v():\n    assert open({decoy!r}).read() == 'INTACTO'\n")
_T_LEE_DENEGADO = ("import mod\ndef test_v():\n"
                   "    try:\n        open({decoy!r}).read()\n    except PermissionError:\n        return\n"
                   "    raise AssertionError('pudo leer fuera de la copia')\n")
_T_ESCRIBE_VIVO = ("import mod\ndef test_v():\n"
                   "    open({live!r} + '/mod.py', 'w').write('VALOR = 99\\n')\n"
                   "    open({live!r} + '/pwn.txt', 'w').write('x')\n")


def _sha_f(ruta) -> str:
    return hashlib.sha256(pathlib.Path(ruta).read_bytes()).hexdigest()


@necesita_landlock
def test_FB_a_una_prueba_que_pasa_confinada_se_promueve_y_se_declara_confinada(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_CONFINADA_OK)
    r = _llama(d, tarea)
    assert r["ejecutado"] is True and r["ejecucion_confinada"] is True, r
    assert objetivo.read_text(encoding="utf-8") == CANDIDATO


@necesita_landlock
@pytest.mark.parametrize("fuente", [_T_ESCRIBE_SENUELO, _T_NIETO], ids=["directa", "nieto"])
def test_FB_bc_una_escritura_externa_directa_o_de_un_nieto_se_bloquea_y_se_rechaza(
        tmp_path, monkeypatch, fuente):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, fuente)
    decoy = tmp_path / "decoy.txt"
    antes = _sha_f(decoy)
    r = _llama(d, tarea)
    assert _sha_f(decoy) == antes, "el verificador escribio fuera de la copia"
    assert r["ejecutado"] is False and r["motivo"] == "verificacion", r
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


@necesita_landlock
def test_FB_d_la_lectura_fuera_de_la_copia_esta_denegada(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_LEE_SENUELO)
    r = _llama(d, tarea)
    assert r["ejecutado"] is False, "la prueba pudo leer un fichero externo"       # asierta leer => falla
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


@necesita_landlock
def test_FB_d_CONTROL_la_PermissionError_es_lo_que_ocurre(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_LEE_DENEGADO)
    r = _llama(d, tarea)
    assert r["ejecutado"] is True and r["ejecucion_confinada"] is True, r


@necesita_landlock
def test_FB_e_una_prueba_no_puede_escribir_en_el_arbol_vivo(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_ESCRIBE_VIVO)
    antes = _sha_f(objetivo)
    r = _llama(d, tarea)
    assert _sha_f(objetivo) == antes, "la verificacion modifico el fichero vivo"
    assert not (d / "pwn.txt").exists()
    assert r["ejecutado"] is False


def test_FB_f_sin_Landlock_no_se_ejecuta_nada_y_se_rechaza(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_CONFINADA_OK)
    monkeypatch.setattr(ais, "abi_disponible", lambda: 0)
    llamadas = []
    monkeypatch.setattr(vf, "ejecutar_pruebas", lambda *a, **k: llamadas.append(a))
    r = _llama(d, tarea)
    assert llamadas == [], "se ejecuto una prueba sin confinamiento efectivo"
    assert r["ejecutado"] is False and r["motivo"] == "confinamiento_no_disponible", r
    assert r["ejecucion_confinada"] is False
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


def test_FB_f_un_confinador_que_declara_abi_0_tampoco_se_acepta(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_CONFINADA_OK)
    sin_reglas = lambda: None                                  # noqa: E731
    sin_reglas.abi = 0
    sin_reglas.completo = True
    sin_reglas.controles = {c: True for c in ais.CONTROLES_ESTRICTOS}
    monkeypatch.setattr(ais, "preparar_estricto", lambda *a, **k: sin_reglas)
    llamadas = []
    monkeypatch.setattr(vf, "ejecutar_pruebas", lambda *a, **k: llamadas.append(a))
    r = _llama(d, tarea)
    assert llamadas == [] and r["motivo"] == "confinamiento_no_disponible" and r["ejecutado"] is False


def test_FB_g_un_fallo_al_aplicar_las_reglas_es_error_de_infraestructura(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_CONFINADA_OK)

    def confinador():
        raise OSError("landlock_restrict_self fallo")

    confinador.abi = 6
    confinador.completo = True
    confinador.controles = {c: True for c in ais.CONTROLES_ESTRICTOS}
    confinador.con_escritura_en = lambda ruta: confinador
    monkeypatch.setattr(ais, "preparar_estricto", lambda *a, **k: confinador)
    r = _llama(d, tarea)
    assert r["ejecutado"] is False and r["motivo"] == "error_infraestructura", r
    assert r["ejecucion_confinada"] is False
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


def test_FB_2_un_bool_heredado_nunca_declara_confinamiento(montaje):
    d, p, _, _ = montaje
    assert ac.ejecutar(d, p, autoridad="ceo",
                       verificacion=lambda raiz: True)["ejecucion_confinada"] is False


# ---------------------------------- RESERVAS DE LA RE-REVISION DE FASE B (documentacion veraz) --

_T_LEE_SYSPATH = ("import mod\ndef test_v():\n"
                  "    for ruta in ({ruta!r}, '/etc/passwd'):\n"
                  "        try:\n            open(ruta).read()\n        except PermissionError:\n            continue\n"
                  "        raise AssertionError('pudo LEER fuera de la copia: ' + ruta)\n"
                  "    try:\n        open({ruta!r}, 'w')\n    except PermissionError:\n        return\n"
                  "    raise AssertionError('pudo ESCRIBIR fuera de la copia')\n")


@necesita_landlock
def test_FB_real_en_estricto_la_lectura_fuera_de_la_copia_SI_esta_aislada(tmp_path, monkeypatch):
    """FASE B: el estricto NO concede `sys.path` del padre ni `/etc`; antes (modo por defecto) si.
    La prueba asierta que leer un directorio de `sys.path` y `/etc/passwd` da PermissionError."""
    enruta = tmp_path / "enruta"
    enruta.mkdir()
    (enruta / "lee.txt").write_text("LEIBLE", encoding="utf-8")
    monkeypatch.syspath_prepend(str(enruta))
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_LEE_SYSPATH)
    r = _llama(d, tarea)
    assert r["ejecutado"] is True and r["ejecucion_confinada"] is True, r
    assert (enruta / "lee.txt").read_text(encoding="utf-8") == "LEIBLE"


def test_FB_real_la_documentacion_declara_el_aislamiento_estricto():
    texto = (pathlib.Path(ac.__file__).read_text(encoding="utf-8")
             + pathlib.Path(review.__file__).read_text(encoding="utf-8"))
    assert "NO es aislamiento de lectura" not in texto, "documentacion obsoleta: la lectura SI esta acotada"
    assert "ESTRICTO" in texto and "RED denegada" in texto


def test_BAJO2_un_estado_json_en_un_subdirectorio_si_cuenta_en_el_manifiesto(montaje):
    d, p, objetivo, _ = montaje
    (d / "sub").mkdir()
    anidado = d / "sub" / "estado.json"
    anidado.write_text("{}", encoding="utf-8")

    def cambia_el_anidado(raiz):
        anidado.write_text('{"cambiado": true}', encoding="utf-8")
        return True

    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=cambia_el_anidado)
    assert r["promovido"] is False and r["motivo"] == "base_cambiada", r
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


def test_BAJO2_CONTROL_el_estado_y_el_log_de_la_raiz_siguen_fuera_del_manifiesto(montaje):
    d, p, _, _ = montaje
    (d / "estado.json").write_text("{}", encoding="utf-8")

    def crece_el_log(raiz):
        cp.registrar_evento(d, "otro", {})
        (d / "estado.json").write_text('{"x": 1}', encoding="utf-8")
        return True

    assert ac.ejecutar(d, p, autoridad="ceo", verificacion=crece_el_log)["promovido"] is True


# ------------------------------ MUTACION fases A/B: ramas del verificador de review aisladas ------

class _InformeFalso:
    agotado = False
    sano = True
    salida = ""


def _confinador_falso(abi=6):
    def confinador():
        return None
    confinador.abi = abi
    confinador.completo = True
    confinador.controles = {c: True for c in ais.CONTROLES_ESTRICTOS}
    return confinador


def test_FB_h_un_directorio_con_enlace_reconoce_sus_pruebas_absolutas_reales(tmp_path, monkeypatch):
    real = tmp_path / "real"
    real.mkdir()
    (real / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    enlace = tmp_path / "enlace"
    enlace.symlink_to(real)
    copia = tmp_path / "copia"
    copia.mkdir()
    monkeypatch.setattr(ais, "abi_disponible", lambda: 6)
    monkeypatch.setattr(ais, "preparar_estricto", lambda *a, **k: _confinador_falso())
    vistas = []
    monkeypatch.setattr(vf, "ejecutar_pruebas",
                        lambda pruebas, raiz, **k: vistas.append(list(pruebas)) or _InformeFalso())
    contrato = {"verificacion": {"pruebas_minimas": [str(real / "test_x.py")]}}
    r = review._verificador_de_review(contrato, enlace)(copia)
    assert r.estado == "sano", r                      # CONTROL: la prueba cabe en el directorio
    assert vistas == [[str(copia / "test_x.py")]]


def test_FB_i_la_comprobacion_de_abi_del_kernel_es_independiente_de_la_del_confinador(tmp_path, monkeypatch):
    real = tmp_path / "real"
    real.mkdir()
    (real / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(ais, "abi_disponible", lambda: 0)
    monkeypatch.setattr(ais, "preparar_estricto", lambda *a, **k: _confinador_falso(6))   # miente: abi 6
    llamadas = []
    monkeypatch.setattr(vf, "ejecutar_pruebas", lambda *a, **k: llamadas.append(a) or _InformeFalso())
    contrato = {"verificacion": {"pruebas_minimas": [str(real / "test_x.py")]}}
    r = review._verificador_de_review(contrato, real)(tmp_path)
    assert llamadas == [] and r.estado == "sin_confinamiento" and r.confinada is False, r


# ------------------------------------------- PROMPT 04 · MEDIO-1: validar el verificador al ENTRAR --

def _huella_dir(*dirs):
    out = {}
    for d in dirs:
        for p in sorted(pathlib.Path(d).rglob("*")):
            if p.is_file():
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_M1_un_verificador_sin_raiz_se_rechaza_ANTES_de_registrar_nada(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_CONFINADA_OK)
    estado = tmp_path / "estado"
    antes = _huella_dir(d, estado)
    with pytest.raises(ac.VerificadorSinRaiz):
        review.ejecutar_bajo_review(d, tarea, propuesto_por="aura", autoridad="orquestador",
                                    verificacion=lambda: True)
    assert _huella_dir(d, estado) == antes, "se registro un evento/propuesta/transicion antes de rechazar"
    assert objetivo.read_text(encoding="utf-8") == ORIGINAL


def test_M1_CONTROL_un_verificador_valido_sigue_su_camino(tmp_path, monkeypatch):
    d, objetivo, tarea, _ = _montaje_review(tmp_path, monkeypatch, _T_CONFINADA_OK)
    r = review.ejecutar_bajo_review(d, tarea, propuesto_por="aura", autoridad="orquestador",
                                    verificacion=lambda raiz: True)
    assert r["ejecutado"] is True and r["ejecucion_confinada"] is False


def test_T1_ejecutar_rechaza_el_verificador_sin_raiz_ANTES_de_leer_o_crear_la_copia(montaje, monkeypatch):
    """La exigencia de raiz de `ejecutar` va antes de `_crear_copia` (no basta con la de `_verificar`)."""
    d, p, objetivo, estado = montaje
    copias = []
    original = ac._crear_copia
    monkeypatch.setattr(ac, "_crear_copia", lambda *a, **k: (copias.append(1), original(*a, **k))[1])
    with pytest.raises(ac.VerificadorSinRaiz):
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda: True)
    assert copias == [], "se creo la copia antes de rechazar el verificador sin raiz"


def test_T1_defensa_en_profundidad_verificar_rechaza_un_verificador_sin_raiz_sin_llamarlo(tmp_path):
    llamadas = []

    def heredada():
        llamadas.append(1)
        return True

    with pytest.raises(ac.VerificadorSinRaiz):
        ac._verificar(heredada, tmp_path)
    assert llamadas == [], "_verificar llamo al verificador heredado sin raiz"
