"""RED del conflicto `D-CP-4` / `ADR-0003` — solo lo VERDE puede ser criterio AUTO.

Decisión del CEO, 2026-08-23, opción (1). Cierra una contradicción **viva y medida**: antes de esta
RED, `es_automatizable({"criterio": "pago"})` devolvía `True`, y `pago` es lista **roja**.

`ADR-0003` no admite matices: *«lista roja (confirmación humana SIEMPRE)… con tolerancia cero a
falsos negativos»*. `DP-ORCH §14.bis` regla 4 dice lo mismo por el otro lado: lo que no es AUTO sube
a REVIEW o HUMAN. Un criterio AUTO sobre una capacidad roja convertiría una decisión humana
obligatoria en una automática.

**La clasificación se deriva del registro real** (`permissions.py`), no de una lista copiada aquí:
duplicarla sería crear una segunda fuente de verdad que el día que producción reclasifique una
capacidad seguiría contestando lo de ayer.

**Fuera de alcance:** `D-CP-5` · `D-CP-7` · el orquestador · el alcance de `D-CP-6`, que no se amplía.
"""

from __future__ import annotations

import importlib

import pytest

# Verdes en `permissions.py`, y las cuatro que `D-CP-4` admite como criterio.
VERDES = ("ejecutar_pruebas", "verificar_calidad", "auditar_garantias", "diagnosticar_estado")

# Rojas en `permissions.py`. Todas exigen confirmación humana por `ADR-0003`.
ROJAS = ("pago", "transferencia", "accion_financiera", "eliminar_informacion",
         "terminar_proceso", "mover_archivo")

INEXISTENTE = "capacidad_que_no_existe_en_el_catalogo"


def _canal():
    return importlib.import_module("communication_plane")


@pytest.mark.parametrize("capacidad", VERDES)
def test_una_capacidad_verde_si_puede_ser_criterio_AUTO(capacidad):
    """El caso de control. Sin él, rechazarlo todo pasaría las pruebas de abajo y rompería `D-CP-4`."""
    assert _canal().es_automatizable({"criterio": capacidad}) is True


@pytest.mark.parametrize("capacidad", ROJAS)
def test_una_capacidad_roja_NUNCA_es_criterio_AUTO(capacidad):
    """**El conflicto que esta RED cierra.** Medido antes de existir: `pago` devolvía `True`."""
    assert _canal().es_automatizable({"criterio": capacidad}) is False, (
        f"{capacidad} es lista ROJA y se acepto como criterio automatico (ADR-0003)")


def test_una_capacidad_inexistente_se_rechaza():
    assert _canal().es_automatizable({"criterio": INEXISTENTE}) is False


@pytest.mark.parametrize("capacidad", VERDES + ROJAS)
def test_la_clasificacion_se_lee_del_registro_real(capacidad):
    """`clasificacion_de_capacidad` debe reflejar `permissions.py`, no una copia del canal."""
    esperada = "verde" if capacidad in VERDES else "roja"
    assert _canal().clasificacion_de_capacidad(capacidad) == esperada


def test_una_capacidad_sin_clasificacion_conocida_no_es_verde():
    """Ante la duda, roja: lo que no consta clasificado no se trata como automatizable."""
    assert _canal().clasificacion_de_capacidad(INEXISTENTE) != "verde"


def test_fail_safe_si_el_registro_no_es_legible_nada_es_verde(tmp_path):
    """**Tolerancia cero a falsos negativos** (`ADR-0003`): un fallo de lectura no puede degradar en
    permiso. Se carga una copia del módulo sin producción encima, de modo que la lectura falla."""
    import importlib.util
    from pathlib import Path

    original = importlib.import_module("communication_plane")
    copia = tmp_path / "canal_sin_registro.py"
    copia.write_text(Path(original.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("canal_sin_registro", copia)
    aislado = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aislado)

    assert aislado.clasificacion_de_capacidad("ejecutar_pruebas") != "verde"
    assert aislado.es_automatizable({"criterio": "ejecutar_pruebas"}) is False


def test_fail_safe_un_registro_con_codificacion_invalida_tampoco_concede(tmp_path):
    """**El caso que faltaba, encontrado por auditoría independiente.**

    `UnicodeDecodeError` hereda de `ValueError`, no de `OSError`: un `permissions.py` con bytes
    inválidos **lanzaba** en lugar de degradar a rechazo. No era una fuga de permiso —nada devolvía
    `True` de más— pero incumplía lo que el módulo promete, y una excepción no es «roja»: es
    comportamiento indefinido que depende de quién llame.

    Se replica la jerarquía real (`parents[2]`) porque el módulo localiza producción por ruta.
    """
    import importlib.util
    from pathlib import Path

    canal_dir = tmp_path / "entorno" / "communication-plane"
    core = tmp_path / "walking-skeleton" / "aura_skeleton" / "core"
    canal_dir.mkdir(parents=True)
    core.mkdir(parents=True)

    original = importlib.import_module("communication_plane")
    copia = canal_dir / "canal_registro_ilegible.py"
    copia.write_text(Path(original.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (core / "permissions.py").write_bytes(b"\xff\xfe\x00\x01CATALOGO = {}")
    (core / "operaciones.py").write_bytes(b"\xff\xfe\x00\x01ESPECIFICACIONES = {}")

    spec = importlib.util.spec_from_file_location("canal_registro_ilegible", copia)
    aislado = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aislado)

    assert aislado.clasificacion_de_capacidad("ejecutar_pruebas") == "desconocida"
    assert aislado.es_automatizable({"criterio": "ejecutar_pruebas"}) is False
    assert aislado.es_automatizable({"criterio": "pago"}) is False
    assert aislado.esquema_de_argumentos("leer_archivo")["acepta_argumentos"] is False
