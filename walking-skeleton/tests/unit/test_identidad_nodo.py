"""Identidad persistente del nodo (DP-NODO-01 §4.1): se crea una vez, sobrevive al reinicio y nunca se regenera.

Cada prueba lleva su caso de control (qué tendría que romperse para que falle).
"""

from __future__ import annotations

import json
import os
import re
import stat
import uuid
from datetime import UTC, datetime

import pytest

from aura_skeleton.adapters.identidad_nodo import IdentidadCorrupta, cargar_o_crear

_HEX32 = re.compile(r"^[0-9a-f]{32}$")


def _fichero(datos):
    return datos / "nodo" / "identidad.json"


def _modo(ruta) -> int:
    return stat.S_IMODE(os.stat(ruta).st_mode)


def test_crea_identidad_con_formato_del_contrato(tmp_path):
    ahora = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    nodo_id = cargar_o_crear(str(tmp_path), reloj=lambda: ahora)
    cuerpo = json.loads(_fichero(tmp_path).read_text())
    assert _HEX32.match(nodo_id)
    assert set(cuerpo) == {"nodo_id", "creado"}  # esquema cerrado
    assert cuerpo["nodo_id"] == nodo_id
    assert datetime.fromisoformat(cuerpo["creado"]) == ahora  # ISO-8601 UTC, el del reloj inyectado
    assert cuerpo["creado"].endswith(("Z", "+00:00"))


def test_segunda_llamada_devuelve_el_mismo_id_aunque_el_generador_cambie(tmp_path):
    # Control: si recreara, el segundo generador (distinto) daría otro id: «otro nodo» tras reiniciar.
    primero = cargar_o_crear(str(tmp_path), generar=lambda: uuid.UUID(int=1))
    segundo = cargar_o_crear(str(tmp_path), generar=lambda: uuid.UUID(int=2))
    assert primero == segundo == uuid.UUID(int=1).hex


def test_el_id_sale_del_generador_inyectado_y_no_del_hostname_ni_la_ip(tmp_path, monkeypatch):
    import socket

    monkeypatch.setattr(socket, "gethostname", lambda: "otro-host")
    a = cargar_o_crear(str(tmp_path / "a"), generar=lambda: uuid.UUID(int=7))
    monkeypatch.setattr(socket, "gethostname", lambda: "host-distinto")
    b = cargar_o_crear(str(tmp_path / "b"), generar=lambda: uuid.UUID(int=7))
    assert a == b == uuid.UUID(int=7).hex  # mismo generador, distinto hostname: mismo id
    c = cargar_o_crear(str(tmp_path / "c"), generar=lambda: uuid.UUID(int=8))
    assert c != a  # y otro generador: otro id


def test_ids_por_defecto_son_distintos_entre_nodos(tmp_path):
    assert cargar_o_crear(str(tmp_path / "a")) != cargar_o_crear(str(tmp_path / "b"))


def test_permisos_0700_directorio_y_0600_fichero_aun_con_umask_laxa(tmp_path):
    anterior = os.umask(0)
    try:
        cargar_o_crear(str(tmp_path))
    finally:
        os.umask(anterior)
    assert _modo(tmp_path / "nodo") == 0o700
    assert _modo(_fichero(tmp_path)) == 0o600


def test_no_deja_ficheros_temporales(tmp_path):
    cargar_o_crear(str(tmp_path))
    assert [p.name for p in (tmp_path / "nodo").iterdir()] == ["identidad.json"]


def test_permisos_mas_abiertos_se_corrigen_a_0600_y_0700(tmp_path):
    nodo_id = cargar_o_crear(str(tmp_path))
    os.chmod(_fichero(tmp_path), 0o644)
    os.chmod(tmp_path / "nodo", 0o755)
    assert cargar_o_crear(str(tmp_path)) == nodo_id  # no regenera: solo corrige
    assert _modo(_fichero(tmp_path)) == 0o600
    assert _modo(tmp_path / "nodo") == 0o700


@pytest.mark.parametrize(
    "contenido",
    [
        b"",
        b"{no es json",
        b"\xff\xfe\x00",
        b"[]",
        b'{"creado": "2026-01-01T00:00:00+00:00"}',
        b'{"nodo_id": 5, "creado": "x"}',
        b'{"nodo_id": "ABCDEF0123456789ABCDEF0123456789", "creado": "x"}',  # mayúsculas
        b'{"nodo_id": "abc", "creado": "x"}',
        b'{"nodo_id": "' + b"a" * 33 + b'", "creado": "x"}',
        b'{"nodo_id": "' + b"a" * 32 + b'\\n", "creado": "x"}',  # $ casaría antes del salto
    ],
)
def test_identidad_corrupta_lanza_y_no_sobrescribe(tmp_path, contenido):
    # Control: regenerar «para arreglar» cambiaría los bytes (y crearía otro nodo, INV-9).
    (tmp_path / "nodo").mkdir(mode=0o700)
    _fichero(tmp_path).write_bytes(contenido)
    os.chmod(_fichero(tmp_path), 0o600)
    with pytest.raises(IdentidadCorrupta):
        cargar_o_crear(str(tmp_path))
    assert _fichero(tmp_path).read_bytes() == contenido


def test_fichero_ilegible_lanza_corrupta(tmp_path):
    (tmp_path / "nodo").mkdir(mode=0o700)
    # Un directorio donde debería haber fichero: la lectura falla con OSError, no se regenera.
    _fichero(tmp_path).mkdir()
    with pytest.raises(IdentidadCorrupta):
        cargar_o_crear(str(tmp_path))
    assert _fichero(tmp_path).is_dir()


def test_directorio_nodo_enlace_simbolico_se_rechaza(tmp_path):
    real = tmp_path / "otro"
    real.mkdir()
    datos = tmp_path / "datos"
    datos.mkdir()
    os.symlink(real, datos / "nodo")
    with pytest.raises(IdentidadCorrupta):
        cargar_o_crear(str(datos))
    assert list(real.iterdir()) == []  # no escribió a través del enlace


def test_fichero_identidad_enlace_simbolico_se_rechaza(tmp_path):
    # Control: seguir el enlace leería un id ajeno y lo daría por propio.
    ajeno = tmp_path / "ajeno.json"
    ajeno.write_text(json.dumps({"nodo_id": "a" * 32, "creado": "2026-01-01T00:00:00+00:00"}))
    (tmp_path / "datos" / "nodo").mkdir(parents=True, mode=0o700)
    os.symlink(ajeno, tmp_path / "datos" / "nodo" / "identidad.json")
    with pytest.raises(IdentidadCorrupta):
        cargar_o_crear(str(tmp_path / "datos"))


def test_enlace_simbolico_colgante_tambien_se_rechaza(tmp_path):
    (tmp_path / "datos" / "nodo").mkdir(parents=True, mode=0o700)
    destino = tmp_path / "no-existe.json"
    os.symlink(destino, tmp_path / "datos" / "nodo" / "identidad.json")
    with pytest.raises(IdentidadCorrupta):
        cargar_o_crear(str(tmp_path / "datos"))
    assert not destino.exists()  # no creó el fichero a través del enlace
