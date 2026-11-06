"""Un evento crudo no puede crear autoridad (CEO, 2026-09-20).

LA VULNERABILIDAD, REPRODUCIDA ANTES DE ESCRIBIR ESTO. `cp.registrar_evento()` rechaza los cuatro
eventos que conceden ESTADO de tarea, pero aceptaba en crudo los dos que conceden **AUTORIDAD**:

    cp.registrar_evento(d, "review_habilitado", {"por": "nadie-real", "acta": "", "alcance": [...]})
        -> `review.habilitado()` pasa a True y `_alcance()` devuelve lo que se le haya puesto.

    cp.registrar_evento(d, "propuesta_autorizada", {"id": X, "autorizada_por": "nadie-real"})
        -> `ac.esta_autorizada(X)` pasa de False a True.

Las puertas legítimas —`review.habilitar()` y `ac.autorizar()`— sí comprobaban autoridad humana y
acta, y rechazaban correctamente. El problema era que **no eran el único camino**: bastaba rodearlas
por la primitiva del log. Es el mismo defecto que `estado_de_tarea` ya tuvo dos veces, con otro
nombre: *«si se aceptase a pelo, el gobierno sería decorativo, porque bastaría rodearlo»*.

LA REGLA DE MONOTONICIDAD. Una habilitación posterior puede **mantener o estrechar** el alcance
vigente, nunca ampliarlo. Sin ella, `_alcance()` —que devuelve el del ÚLTIMO evento, sin acumular—
convierte cualquier acta nueva en un reemplazo silencioso: el 2026-09-16 DR-E sustituyó a DR-D y
`eliminar_codigo_muerto` desapareció del alcance sin que nadie lo declarara. Aquí se impide lo
contrario, que es lo peligroso: que aparezca un verbo que nadie autorizó.

LO QUE NO SE TOCA: `_INTOCABLES`, el alcance vigente, la autoridad del anillo, PARADA, ni la
semántica de `review.habilitar()`. La barrera **restringe**; no concede nada.
"""

from __future__ import annotations

import pathlib

import autoconstruccion as ac
import control_plane as cp
import pytest
import review

ACTA = "acta de prueba del CEO 2026-09-20"


# ============================================================ 1 · LA VIA CRUDA SE CIERRA --


def test_un_review_habilitado_CRUDO_no_enciende_REVIEW(tmp_path):
    """RED el 2026-09-20: `registrar_evento` lo aceptaba y `review.habilitado()` pasaba a True."""
    d = pathlib.Path(tmp_path)

    with pytest.raises(cp.EventoNoGobernado):
        cp.registrar_evento(d, "review_habilitado",
                            {"por": "nadie-real", "acta": "", "alcance": ["lo_que_sea"]})

    assert review.habilitado(d) is False, "un evento crudo encendio REVIEW"
    assert review._alcance(d) == (), "un evento crudo concedio alcance"


def test_una_propuesta_autorizada_CRUDA_no_autoriza_nada(tmp_path):
    """RED el 2026-09-20: `ac.esta_autorizada` pasaba de False a True con un evento a mano."""
    d = pathlib.Path(tmp_path)

    with pytest.raises(cp.EventoNoGobernado):
        cp.registrar_evento(d, "propuesta_autorizada",
                            {"id": "P-1", "autorizada_por": "nadie-real", "acta": ""})

    assert ac.esta_autorizada(d, "P-1") is False, "un evento crudo autorizo una propuesta"


def test_los_dos_eventos_de_autoridad_constan_como_gobernados():
    """La barrera se declara donde ya se declaran las demás: una sola lista, no una segunda verdad."""
    assert "review_habilitado" in cp.EVENTOS_GOBERNADOS
    assert "propuesta_autorizada" in cp.EVENTOS_GOBERNADOS


def test_cada_evento_de_autoridad_dice_cual_es_su_puerta():
    """Un «esto no» sin «esto sí» empuja a rodearlo, y así nacen las rutas alternativas."""
    for tipo in ("review_habilitado", "propuesta_autorizada"):
        assert cp._PUERTA_DE.get(tipo), f"{tipo} se rechaza sin ofrecer salida"


# ============================================================ 2 · LA PUERTA EXIGE AUTORIDAD --


@pytest.mark.parametrize("por", ["nadie-real", "aura", "orquestador", "", "   ", "CEO", "ceo "])
def test_la_puerta_de_review_rechaza_autoridad_NO_humana(tmp_path, por):
    """Incluye `"CEO"` y `"ceo "`: la comparación es exacta, y un acierto por mayúsculas o por un
    espacio de más sería una autoridad concedida por descuido de tecleo."""
    d = pathlib.Path(tmp_path)

    with pytest.raises(Exception) as exc:  # noqa: B017 — el tipo lo fija la implementacion
        cp.registrar_review_habilitado(d, por=por, acta=ACTA, alcance=("eliminar_codigo_muerto",))

    assert "human" in str(exc.value).lower(), f"se detuvo por otra razon: {exc.value}"
    assert review.habilitado(d) is False


def test_la_puerta_de_review_rechaza_un_acta_vacia(tmp_path):
    d = pathlib.Path(tmp_path)

    with pytest.raises(Exception) as exc:  # noqa: B017
        cp.registrar_review_habilitado(d, por="ceo", acta="   ", alcance=("eliminar_codigo_muerto",))

    assert "acta" in str(exc.value).lower(), f"se detuvo por otra razon: {exc.value}"
    assert review.habilitado(d) is False


def test_un_alcance_VACIO_se_acepta_y_no_concede_nada(tmp_path):
    """Rechazarlo habría cambiado la semántica de `review.habilitar()`, que el acta manda conservar.

    Y no hace falta rechazarlo: un alcance vacío no autoriza ningún verbo. Es la forma de **retirar**
    autoridad sin borrar historial.
    """
    d = pathlib.Path(tmp_path)

    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=())

    assert review._alcance(d) == ()
    assert review.en_alcance(d, "eliminar_codigo_muerto") is False
    assert review.en_alcance(d, "implementar_incremento_especificado") is False


def test_un_alcance_vacio_CUENTA_para_la_monotonicidad(tmp_path):
    """El rodeo de dos pasos, cerrado: vaciar el alcance no reinicia la regla.

    Si «vacío» contara como «no hay habilitación anterior», bastaría habilitar a vacío para que el
    acto siguiente pudiera conceder lo que quisiera. La regla mira si **hubo evento**, no si el
    alcance quedó vacío.
    """
    d = pathlib.Path(tmp_path)
    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a",))
    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=())

    with pytest.raises(Exception) as exc:  # noqa: B017
        cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a",))

    assert "ampl" in str(exc.value).lower()
    assert review._alcance(d) == ()


@pytest.mark.parametrize("alcance", [None, "eliminar_codigo_muerto", ["", "  "], [None], [123]])
def test_la_puerta_de_review_rechaza_un_alcance_MALFORMADO(tmp_path, alcance):
    """Una cadena suelta no es una tupla de verbos: iterarla concedería el alcance «e», «l», «i»…"""
    d = pathlib.Path(tmp_path)

    with pytest.raises(Exception):  # noqa: B017
        cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=alcance)

    assert review.habilitado(d) is False


def test_la_puerta_de_propuesta_rechaza_autoridad_desconocida(tmp_path):
    d = pathlib.Path(tmp_path)

    with pytest.raises(Exception) as exc:  # noqa: B017
        cp.registrar_propuesta_autorizada(d, "P-1", autorizada_por="nadie-real", acta=ACTA)

    assert "autoridad" in str(exc.value).lower() or "human" in str(exc.value).lower()
    assert ac.esta_autorizada(d, "P-1") is False


def test_la_puerta_de_propuesta_rechaza_el_circuito_REVIEW_si_REVIEW_no_esta_habilitado(tmp_path):
    """La autoridad `REVIEW:<revisor>` vale **porque un humano encendió REVIEW**, no por su forma.

    Sin esta comprobación, escribir `autorizada_por="REVIEW:yo"` sería la nueva vía cruda: se
    habría cerrado la puerta y dejado la ventana abierta con otro nombre.
    """
    d = pathlib.Path(tmp_path)

    with pytest.raises(Exception) as exc:  # noqa: B017
        cp.registrar_propuesta_autorizada(d, "P-1", autorizada_por="REVIEW:inventado", acta=ACTA)

    assert "review" in str(exc.value).lower()
    assert ac.esta_autorizada(d, "P-1") is False


# ============================================================ 3 · MONOTONICIDAD --


def test_una_habilitacion_posterior_puede_MANTENER_el_alcance(tmp_path):
    d = pathlib.Path(tmp_path)
    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a", "b"))

    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a", "b"))

    assert set(review._alcance(d)) == {"a", "b"}


def test_una_habilitacion_posterior_puede_ESTRECHAR_el_alcance(tmp_path):
    d = pathlib.Path(tmp_path)
    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a", "b"))

    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a",))

    assert set(review._alcance(d)) == {"a"}


def test_una_habilitacion_posterior_NO_puede_AMPLIAR_el_alcance(tmp_path):
    """El caso que importa: un verbo que nadie autorizó no puede aparecer por la puerta de atrás."""
    d = pathlib.Path(tmp_path)
    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a",))

    with pytest.raises(Exception) as exc:  # noqa: B017
        cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a", "b"))

    assert "ampl" in str(exc.value).lower() or "estrech" in str(exc.value).lower()
    assert set(review._alcance(d)) == {"a"}, "el alcance vigente cambio pese al rechazo"


def test_la_PRIMERA_habilitacion_no_esta_limitada_por_una_anterior_inexistente(tmp_path):
    """Sin esto, la monotonicidad impediría el primer acto del CEO: subconjunto de nada es nada."""
    d = pathlib.Path(tmp_path)

    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a", "b"))

    assert set(review._alcance(d)) == {"a", "b"}


def test_un_alcance_rechazado_no_deja_rastro_en_el_log(tmp_path):
    """Fallo cerrado de verdad: si el evento se escribiera y luego se rechazara, el log mentiría."""
    d = pathlib.Path(tmp_path)
    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a",))
    antes = len(cp.leer_eventos(d))

    with pytest.raises(Exception):  # noqa: B017
        cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a", "b"))

    assert len(cp.leer_eventos(d)) == antes, "el intento rechazado dejo un evento escrito"


# ============================================================ 4 · RECONSTRUIBLE DESDE EL LOG --


def test_el_alcance_efectivo_se_reconstruye_LEYENDO_EL_HISTORIAL(tmp_path):
    """ADR-0023: el historial es la única fuente de verdad. Nada de estado.json ni de memoria."""
    d = pathlib.Path(tmp_path)
    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a", "b"))
    cp.registrar_review_habilitado(d, por="humano", acta=ACTA, alcance=("a",))

    # Se calcula **solo** con los eventos leídos del fichero, sin tocar ningún estado en memoria.
    eventos = cp.leer_eventos(d)
    ultimo = [e for e in eventos if e["tipo"] == "review_habilitado"][-1]

    assert tuple(ultimo["datos"]["alcance"]) == ("a",)
    assert review._alcance(d) == ("a",), "la lectura del modulo y la del log no coinciden"


def test_un_evento_de_autoridad_MALFORMADO_en_el_log_no_concede_alcance(tmp_path):
    """Un log manipulado a mano no puede convertirse en autoridad al leerlo.

    La barrera de escritura cierra la vía por la API; esta prueba cubre la otra mitad: que la
    LECTURA tampoco se crea cualquier cosa.
    """
    d = pathlib.Path(tmp_path)
    cp.registrar_review_habilitado(d, por="ceo", acta=ACTA, alcance=("a",))
    # Se escribe directamente en el fichero, saltandose la API entera.
    (d / "eventos.jsonl").open("a", encoding="utf-8").write(
        '{"seq": 999, "tipo": "review_habilitado", "datos": {"alcance": "todo"}, '
        '"momento": "2026-09-20T00:00:00", "hash": "x", "hash_anterior": "y"}\n')

    alcance = review._alcance(d)

    assert alcance != tuple("todo"), "una cadena suelta se interpreto letra a letra como alcance"
    assert all(isinstance(v, str) and v.strip() for v in alcance)


# ============================================================ 5 · LA VIA LEGITIMA SIGUE VIVA --


def test_CONTROL_review_habilitar_sigue_funcionando(tmp_path):
    """La semántica de `review.habilitar()` se conserva: es un requisito explícito del acta."""
    d = pathlib.Path(tmp_path)

    r = review.habilitar(d, por="ceo", acta=ACTA, alcance=("eliminar_codigo_muerto",))

    assert r["alcance"] == ("eliminar_codigo_muerto",)
    assert review.habilitado(d) is True
    assert review.en_alcance(d, "eliminar_codigo_muerto") is True


def test_CONTROL_review_habilitar_sigue_rechazando_lo_que_ya_rechazaba(tmp_path):
    d = pathlib.Path(tmp_path)

    with pytest.raises(review.ReviewNoHabilitado):
        review.habilitar(d, por="aura", acta=ACTA, alcance=("eliminar_codigo_muerto",))
    with pytest.raises(review.ReviewNoHabilitado):
        review.habilitar(d, por="ceo", acta="", alcance=("eliminar_codigo_muerto",))


def test_CONTROL_ac_autorizar_sigue_funcionando(tmp_path):
    """La otra puerta humana: autorizar una propuesta concreta."""
    d = pathlib.Path(tmp_path)
    objetivo = d / "m.py"
    objetivo.write_text("X = 1\n", encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "X = 1", "sustituir": "X = 2", "motivo": "trabajo"})

    ac.autorizar(d, p["id"], por="ceo", acta=ACTA)

    assert ac.esta_autorizada(d, p["id"]) is True


def test_CONTROL_ac_autorizar_sigue_rechazando_autoridad_falsa(tmp_path):
    d = pathlib.Path(tmp_path)

    with pytest.raises(ac.SinAutorizacion):
        ac.autorizar(d, "P-X", por="nadie-real", acta=ACTA)
