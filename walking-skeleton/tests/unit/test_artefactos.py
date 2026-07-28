"""Unit: gestión de artefactos de IA (ADR-0022) — manifiesto declarativo + ModelResolver.

ADR-0022 define, y este módulo prueba, el ALCANCE MÍNIMO: un manifiesto declarativo (`manifiesto.json`
junto al artefacto en el entorno) y un `ModelResolver` de una sola responsabilidad que localiza el
artefacto, verifica su integridad (SHA-256) y su formato, y entrega la ruta válida. NADA más
(sin cachés, sin descarga, sin múltiples proveedores, sin descubrimiento — exclusiones de ADR-0022).

El manifiesto vive en el ENTORNO (no en el código): cambiar de modelo = apuntar a otro directorio con su
propio manifiesto, sin tocar código (criterio de éxito del CEO).
"""

import hashlib
import json

import pytest


def _artefacto(dir_, contenido_onnx=b"onnx-bytes", con_tokenizer=True, checksum=None, formato="onnx+tokenizer"):
    """Crea un directorio de artefacto de prueba con model.onnx (+ tokenizer.json) y su manifiesto.json."""
    (dir_ / "model.onnx").write_bytes(contenido_onnx)
    if con_tokenizer:
        (dir_ / "tokenizer.json").write_text("{}")
    real = hashlib.sha256(contenido_onnx).hexdigest()
    manifiesto = {
        "id": "embedder.prueba",
        "version": "1.0.0",
        "checksum": checksum if checksum is not None else real,
        "licencia": "Apache-2.0",
        "formato": formato,
        "dims": 384,
    }
    (dir_ / "manifiesto.json").write_text(json.dumps(manifiesto))
    return dir_


def test_cargar_manifiesto_lee_los_campos(tmp_path):
    from aura_skeleton.artefactos import cargar_manifiesto

    _artefacto(tmp_path)
    m = cargar_manifiesto(str(tmp_path))
    assert m.id == "embedder.prueba"
    assert m.version == "1.0.0"
    assert m.licencia == "Apache-2.0"
    assert m.formato == "onnx+tokenizer"
    assert m.dims == 384


def test_resolver_entrega_la_ruta_con_artefacto_valido(tmp_path):
    from aura_skeleton.artefactos import ModelResolver

    _artefacto(tmp_path)
    ruta = ModelResolver().resolver(str(tmp_path))
    assert ruta == str(tmp_path)


def test_resolver_rechaza_checksum_invalido(tmp_path):
    """Integridad: si el SHA-256 no coincide, NO entrega la ruta (el hueco que motivó ADR-0022)."""
    from aura_skeleton.artefactos import ArtefactoNoResuelto, ModelResolver

    _artefacto(tmp_path, checksum="0" * 64)
    with pytest.raises(ArtefactoNoResuelto):
        ModelResolver().resolver(str(tmp_path))


def test_resolver_rechaza_fichero_faltante(tmp_path):
    """Localización/formato: si falta un fichero que el formato exige (tokenizer.json), rechaza."""
    from aura_skeleton.artefactos import ArtefactoNoResuelto, ModelResolver

    _artefacto(tmp_path, con_tokenizer=False)
    with pytest.raises(ArtefactoNoResuelto):
        ModelResolver().resolver(str(tmp_path))


def test_resolver_rechaza_formato_desconocido(tmp_path):
    """Compatibilidad: un formato que el resolver no conoce se rechaza (no se adivina)."""
    from aura_skeleton.artefactos import ArtefactoNoResuelto, ModelResolver

    _artefacto(tmp_path, formato="formato-inexistente")
    with pytest.raises(ArtefactoNoResuelto):
        ModelResolver().resolver(str(tmp_path))


def test_resolver_rechaza_sin_manifiesto(tmp_path):
    """Sin manifiesto no hay artefacto gestionable: rechaza (no carga a ciegas)."""
    from aura_skeleton.artefactos import ArtefactoNoResuelto, ModelResolver

    (tmp_path / "model.onnx").write_bytes(b"x")
    (tmp_path / "tokenizer.json").write_text("{}")
    with pytest.raises(ArtefactoNoResuelto):
        ModelResolver().resolver(str(tmp_path))


def test_resolver_rechaza_directorio_inexistente(tmp_path):
    from aura_skeleton.artefactos import ArtefactoNoResuelto, ModelResolver

    with pytest.raises(ArtefactoNoResuelto):
        ModelResolver().resolver(str(tmp_path / "no_existe"))
