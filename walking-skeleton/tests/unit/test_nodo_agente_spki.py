"""A3 integrada en el agente: la opción `spki_fijada` de nodo.conf. Sin ella el comportamiento NO cambia (NODO-01)."""

from __future__ import annotations

import asyncio
import json
import ssl
from pathlib import Path
from typing import Any

import pytest

from aura_skeleton import nodo_agente
from aura_skeleton.bus_nats import NatsEventBus
from aura_skeleton.nodo_agente import ConfigAgente, ErrorConfiguracion, cargar_config
from tests.tls_apoyo import AcPrueba

PIN = "ab" * 32
PIN2 = "cd" * 32
NODO_ID = "ab" * 16


def _datos(tmp_path: Path, **conf: Any) -> Path:
    cuerpo = {"servidores": ["tls://127.0.0.1:4222"], "usuario": "u", "nombre": "n1", "intervalo_s": 2}
    cuerpo.update(conf)
    (tmp_path / "nodo.conf").write_text(json.dumps(cuerpo))
    cred = tmp_path / "credencial"
    cred.write_text("clave\n")
    cred.chmod(0o600)
    (tmp_path / "ca.crt").write_text("CA")
    return tmp_path


def test_sin_spki_fijada_la_config_es_la_historica(tmp_path: Path) -> None:
    cfg, _ = cargar_config(str(_datos(tmp_path)))
    assert cfg.spki_fijada == ()


def test_con_spki_fijada_se_lee_ordenada(tmp_path: Path) -> None:
    cfg, _ = cargar_config(str(_datos(tmp_path, spki_fijada=[PIN2, PIN])))
    assert cfg.spki_fijada == (PIN, PIN2)


@pytest.mark.parametrize("valor", [[], "ab" * 32, ["xyz"], [PIN, PIN], [PIN, PIN2, "ef" * 32], None, {"a": 1}])
def test_spki_fijada_presente_pero_invalida_falla_cerrado_no_degrada_a_solo_ca(tmp_path: Path, valor: Any) -> None:
    with pytest.raises(ErrorConfiguracion, match="spki_fijada"):
        cargar_config(str(_datos(tmp_path, spki_fijada=valor)))


def _capturar_ctx(datos: Path, monkeypatch: pytest.MonkeyPatch, **cambios: Any) -> ssl.SSLContext:
    datos.mkdir(parents=True, exist_ok=True)
    AcPrueba(datos)  # deja un ca.crt válido en `datos`
    cap: dict[str, Any] = {}

    async def falso(url: Any, **opciones: Any) -> str:
        cap.update(opciones)
        return "bus"

    monkeypatch.setattr(NatsEventBus, "connect", falso)
    cfg = ConfigAgente(str(datos), NODO_ID, ["tls://hc-1.local:4222"], "u", "n", 10.0, **cambios)
    asyncio.run(nodo_agente._fabrica_nats(cfg, "x", resolutor=lambda _: None)())
    return cap["tls"]  # type: ignore[no-any-return]


def test_la_fabrica_aplica_la_fijacion_solo_si_esta_configurada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sin = _capturar_ctx(tmp_path / "a", monkeypatch)
    assert sin.sslobject_class is ssl.SSLObject and sin.minimum_version != ssl.TLSVersion.TLSv1_3
    con = _capturar_ctx(tmp_path / "b", monkeypatch, spki_fijada=(PIN,))
    assert con.sslobject_class is not ssl.SSLObject and con.minimum_version == ssl.TLSVersion.TLSv1_3
    assert con.verify_mode == ssl.CERT_REQUIRED and con.verify_flags & ssl.VERIFY_X509_STRICT
