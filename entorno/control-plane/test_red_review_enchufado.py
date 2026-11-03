"""RED · el `§8.3` no llegaba a la ruta real de `REVIEW`.

La tercera auditoría lo encontró: `revisores.pedir_revision` —el mecanismo de F4, que implementa
`§8.2` y `§8.3` **literalmente**, con degradación, `review_id` y escalada a `DECISION_REQUIRED`—
**no lo llama ningún módulo de producción**. `grep` fuera de los `test_*`: nada.

Lo que sí está cableado es `review.ejecutar_bajo_review`, que llama a `review.pedir_veredicto`. Y ese
**asume que el revisor contesta siempre**: construye un veredicto a partir de los criterios D22 sin
comprobar antes que exista un revisor capaz. Si mañana no lo hay, no espera — sigue.

Es el mismo patrón que la primera auditoría llamó *«el aparato existía y no estaba enchufado»*, y
además hay **dos contratos de `Veredicto`** para lo mismo: el de tres campos de `autoconstruccion` y
el de cinco de `revisores` (`§8.2`). `INV-7` dice que el plan se interpreta **en un solo punto**.

Lo que este fichero cierra es la mitad que importa para la seguridad: **la degradación del `§8.3`
llega a la ruta real**. La unificación de los dos contratos queda declarada como deuda, con su
condición de promoción escrita — no se hace aquí porque tocar el circuito que el CEO aprobó y vio
funcionar es un riesgo mayor que la duplicación que corrige.
"""

from __future__ import annotations

import autoconstruccion as ac
import control_plane as cp
import orquestador as orq
import pytest
import review
import revisores as rev


@pytest.fixture(autouse=True)
def _estas_pruebas_no_miden_el_arbol(monkeypatch):
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _preparado(tmp_path, monkeypatch):
    """Un REVIEW habilitado por acta, con una tarea real en zona."""
    modulo = tmp_path / "modulo.py"
    modulo.write_text("def _muerta():\n    return 1\n\n\ndef viva():\n    return 2\n",
                      encoding="utf-8")
    review.habilitar(tmp_path, alcance=("eliminar_codigo_muerto",), por="ceo",
                     acta="DEC-ORCH-2 del CEO")
    return {"id": "T-R", "accion": "eliminar_codigo_muerto", "simbolo": "_muerta",
            "fichero": str(modulo), "cambia_alcance": False, "respeta_decisiones": True,
            "d21_afirmativas": True, "reversible": True}


def test_sin_revisor_capaz_la_ruta_REAL_de_review_ESPERA(tmp_path, monkeypatch):
    """`§8.3`: *«si no hay revisor disponible, la tarea que exige revisión pasa a
    `WAITING_FOR_REVIEW` y **espera**. No se autoaprueba jamás»*.

    Antes, `ejecutar_bajo_review` no preguntaba si había revisor: fabricaba el veredicto y seguía."""
    tarea = _preparado(tmp_path, monkeypatch)
    monkeypatch.setattr(review, "revisores_capaces", lambda: ())
    resultado = review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura",
                                            autoridad="orquestador", verificacion=lambda: True)
    assert resultado["ejecutado"] is False
    assert resultado.get("estado") == cp.ESTADO_REVISION


def test_sin_revisor_capaz_el_fichero_NO_se_toca(tmp_path, monkeypatch):
    """La garantía por el efecto: esperar significa que no ha pasado nada, no que se registre que se
    esperaba mientras el cambio ya está hecho."""
    tarea = _preparado(tmp_path, monkeypatch)
    antes = (tmp_path / "modulo.py").read_text(encoding="utf-8")
    monkeypatch.setattr(review, "revisores_capaces", lambda: ())
    review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura", autoridad="orquestador",
                               verificacion=lambda: True)
    assert (tmp_path / "modulo.py").read_text(encoding="utf-8") == antes


def test_con_revisor_capaz_la_ruta_real_SIGUE_funcionando(tmp_path, monkeypatch):
    """Caso de control, y el más importante: la degradación no puede romper el circuito que el CEO
    aprobó y vio funcionar."""
    tarea = _preparado(tmp_path, monkeypatch)
    resultado = review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura",
                                            autoridad="orquestador", verificacion=lambda: True)
    assert resultado["ejecutado"] is True
    assert "_muerta" not in (tmp_path / "modulo.py").read_text(encoding="utf-8")
    assert "viva" in (tmp_path / "modulo.py").read_text(encoding="utf-8")


def test_los_revisores_capaces_salen_del_ESTADO_REAL_no_de_una_lista(tmp_path):
    """`§8.1`: *«qué se puede hacer HOY, sin inventar nada»*. La disponibilidad se mide, no se
    declara: un revisor se considera capaz si su ficha existe, igual que en F4."""
    capaces = review.revisores_capaces()
    assert set(capaces) <= set(ac.REVISORES)
    for nombre in capaces:
        assert (ac.RAIZ_AGENTES / f"{nombre}.md").exists(), f"{nombre} no tiene ficha: no es capaz"


def test_la_espera_NO_es_una_aprobacion(tmp_path, monkeypatch):
    """`1.1:85`. La forma de fallar de un circuito de revisión es aprobar por cansancio, y por eso
    se comprueba explícitamente que esperar no produce ni ejecución ni veredicto favorable."""
    tarea = _preparado(tmp_path, monkeypatch)
    monkeypatch.setattr(review, "revisores_capaces", lambda: ())
    resultado = review.ejecutar_bajo_review(tmp_path, tarea, propuesto_por="aura",
                                            autoridad="orquestador", verificacion=lambda: True)
    assert resultado["ejecutado"] is False
    assert not resultado.get("objeciones"), "no hay veredicto: no hay ni objeciones ni conformidad"
    assert rev.autoriza(None) is False


def test_la_deuda_de_los_DOS_contratos_de_veredicto_esta_declarada():
    """`INV-7`: *«el plan se interpreta en un solo punto y nunca se reinterpreta»*. Hay dos clases
    `Veredicto` para lo mismo —tres campos en `autoconstruccion`, cinco en `revisores` (`§8.2`)— y
    unificarlas toca el circuito que el CEO aprobó. Se declara con su condición de promoción en vez
    de arreglarse a medias, y esta prueba impide que la declaración se pierda."""
    assert len(ac.Veredicto.__dataclass_fields__) == 3
    assert len(rev.Veredicto.__dataclass_fields__) == 5
    fuente = review.__doc__ or ""
    assert "dos contratos" in fuente.lower() or "INV-7" in fuente, (
        "la duplicación tiene que estar declarada donde se lea, no solo en una prueba")
