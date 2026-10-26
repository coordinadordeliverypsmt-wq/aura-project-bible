"""Blindaje del anillo — tres barreras que decían proteger y no protegían (CEO, 2026-09-16).

Las tres se descubrieron auditando el mecanismo ANTES de concederle más capacidad. Ninguna ha
concedido nunca un permiso indebido —el anillo lleva parado desde el 2026-09-08— pero las tres
fallarían en el momento en que se autorizara un segundo contrato.

1. **`_acta_consta` compara por SUBSTRING.** Citar `acta = "D"` en un contrato bastaba para que la
   comprobación diera por buena la autorización: la letra aparece en algún dato de algún evento. La
   cita de un acta tiene que ser la identidad del acta, no un fragmento que se encuentre dentro.

2. **Sin verificador, el ejecutor declaraba el árbol SANO.** `sano = bool(verificacion() if
   verificacion else True)` convierte «no se midió» en «salió bien», y el punto de entrada empaquetado
   (`aura.py`) pasa `verificacion=None`. Un `cambio_aplicado` con `verificacion_sana: true` que nadie
   verificó es exactamente el patrón «declarado != real».

3. **PARADA no se consultaba en la puerta de escritura.** Se consulta al despertar
   (`motor_autonomia`, `despertador`, `observatorio`) pero no en `autoconstruccion.ejecutar`, que es
   por donde pasa todo el mundo. ALERTA-005: la puerta va donde pasa todo el mundo, no antes.

Estas pruebas usan la API real del plano de control y directorios temporales. Ninguna ejecuta el
ciclo ni escribe en el historial real.
"""

import pathlib

import autoconstruccion as ac
import contrato as ct
import orquestador as orq
import pytest

PLANO = pathlib.Path(__file__).parent


# ============================================== 1 · UN ACTA SE CITA ENTERA, NO POR TROZOS --


def test_un_fragmento_de_acta_no_acredita_autorizacion():
    """`"D"` y `"DR-"` no son actas: son trozos que aparecen dentro de cualquier dato del historial."""
    for fragmento in ("D", "DR-", "a", "acta"):
        assert not ct._acta_consta(fragmento, PLANO), (
            f"un fragmento {fragmento!r} acredito un acta que nadie registro"
        )


def test_CONTROL_un_acta_real_sigue_acreditandose():
    """La corrección no puede romper lo que sí está registrado: DEC-ORCH-2 y DR-D constan."""
    assert ct._acta_consta("DEC-ORCH-2", PLANO), "el acta real dejo de reconocerse"


def test_un_acta_inventada_no_se_acredita():
    assert not ct._acta_consta("DEC-ORCH-999", PLANO)
    assert not ct._acta_consta("ACTA-QUE-NADIE-FIRMO", PLANO)


# ====================================== 2 · SIN VERIFICADOR NO SE DECLARA SANO --


def _propuesta_lista(d: pathlib.Path):
    """Una propuesta autorizada sobre un fichero del sandbox. Usa la API real."""
    objetivo = d / "s.py"
    objetivo.write_text("VALOR = 1\n", encoding="utf-8")
    p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                        "buscar": "VALOR = 1", "sustituir": "VALOR = 2", "motivo": "incremento"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-09-16")
    return p, objetivo


def test_sin_verificador_el_arbol_NO_puede_declararse_sano(tmp_path):
    """«No se midió» no es «salió bien». El ejecutor no puede firmar una verificación que no hizo.

    Y no basta con no declararlo sano: hay que DESHACER. Un cambio cuya sanidad nadie comprobó tiene
    que salir del árbol, que es la misma regla que ya aplica el `except` para una verificación que
    revienta («eso no es no sano: es no se sabe») y la de ADR-0003, ante la duda, roja. Afirmar solo
    `is not True` dejaba vivo un mutante que se quedaba el cambio sin revertir (BA-M5, 2026-09-16).
    """
    d = pathlib.Path(tmp_path)
    p, objetivo = _propuesta_lista(d)
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=None)
    assert r["verificacion_sana"] is not True, (
        "se declaro el arbol sano sin ejecutar ninguna verificacion"
    )
    assert r["revertido"] is True, "un cambio sin verificar se quedo aplicado"
    assert objetivo.read_text(encoding="utf-8") == "VALOR = 1\n", "el fichero quedo tocado sin verificar"


def test_CONTROL_con_verificador_en_verde_si_se_declara_sano(tmp_path):
    d = pathlib.Path(tmp_path)
    p, objetivo = _propuesta_lista(d)
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["verificacion_sana"] is True and r["revertido"] is False, r
    assert "VALOR = 2" in objetivo.read_text(encoding="utf-8")


def test_CONTROL_con_verificador_en_rojo_se_revierte(tmp_path):
    d = pathlib.Path(tmp_path)
    p, objetivo = _propuesta_lista(d)
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: False)
    assert r["revertido"] is True, r
    assert objetivo.read_text(encoding="utf-8") == "VALOR = 1\n", "no se revirtio el fichero"


# ============================================= 3 · PARADA BLOQUEA LA ESCRITURA --


def test_la_PARADA_bloquea_la_puerta_de_escritura_no_solo_el_despertar(tmp_path):
    """ALERTA-005: la puerta va donde pasa todo el mundo. `ejecutar` es esa puerta."""
    d = pathlib.Path(tmp_path)
    p, objetivo = _propuesta_lista(d)
    (d / "PARADA").write_text("", encoding="utf-8")
    assert orq.parada_solicitada(d) is True, "la prueba no armo la parada"
    with pytest.raises(Exception) as exc:  # noqa: B017 — el tipo concreto lo fija la implementacion
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert "parada" in str(exc.value).lower(), f"se detuvo por otra razon: {exc.value}"
    assert objetivo.read_text(encoding="utf-8") == "VALOR = 1\n", "escribio con la PARADA armada"


def test_CONTROL_sin_PARADA_la_ejecucion_sigue_su_curso(tmp_path):
    d = pathlib.Path(tmp_path)
    p, objetivo = _propuesta_lista(d)
    assert orq.parada_solicitada(d) is False
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["efecto_verificado"] is True and r["revertido"] is False, r
    assert "VALOR = 2" in objetivo.read_text(encoding="utf-8")


# ============================ 4 · LA LISTA DE INTOCABLES SE RESPETA EN LA ESCRITURA --


def test_la_puerta_de_escritura_respeta_los_INTOCABLES(tmp_path):
    """`_INTOCABLES` no protegía nada en la ruta de escritura (auditoría, 2026-09-16).

    Se demostró ejecutando: `ac.ejecutar` reescribió un fichero llamado `orquestador.py` —que SÍ está
    en la tupla— porque `ejecutar` nunca la consultaba. La lista solo se miraba en la clasificación de
    `contrato.evaluar` y en `Orquestador.puede_tocar`, **que no tiene ningún llamante de producción**.

    `orquestador.py:56-58` ya declara por qué existe la tupla: *«un ejecutor que puede reescribir
    cualquiera de los tres puede concederse lo que quiera en la iteracion siguiente»*. Esta prueba
    hace verdadera esa frase en la única puerta de escritura del plano (ALERTA-005).

    NO se amplía la tupla aquí: se respeta la que ya existe. Ampliarla cambia un invariante publicado
    y es decisión del CEO.
    """
    d = pathlib.Path(tmp_path)
    for nombre in orq._INTOCABLES:
        if not nombre.endswith(".py"):
            continue
        objetivo = d / nombre
        objetivo.write_text("TUPLA = ('a',)\n", encoding="utf-8")
        p = ac.proponer(d, {"fichero": str(objetivo), "operacion": "sustituir_texto",
                            "buscar": "TUPLA = ('a',)", "sustituir": "TUPLA = ('a', 'crear_autoridad')",
                            "motivo": "intento de ampliarse la autoridad"})
        ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-09-16")
        with pytest.raises(Exception) as exc:  # noqa: B017 — el tipo lo fija la implementacion
            ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
        assert "intocable" in str(exc.value).lower(), f"{nombre}: se detuvo por otra razon: {exc.value}"
        assert objetivo.read_text(encoding="utf-8") == "TUPLA = ('a',)\n", (
            f"{nombre} es intocable y el ejecutor lo reescribio"
        )


def test_CONTROL_un_fichero_ordinario_del_plano_si_se_puede_tocar(tmp_path):
    """La barrera es por identidad, no por zona: un fichero normal del plano sigue siendo trabajable."""
    d = pathlib.Path(tmp_path)
    p, objetivo = _propuesta_lista(d)   # s.py, un nombre ordinario
    r = ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert r["revertido"] is False and "VALOR = 2" in objetivo.read_text(encoding="utf-8"), r


def test_un_symlink_con_nombre_inocente_no_burla_la_barrera(tmp_path):
    """La barrera juzga el fichero REAL, no el nombre escrito.

    `zona_permitida` ya resuelve enlaces desde su segunda auditoría por esta misma razón. Sin
    resolver, bastaría con apuntar `inocente.py -> orquestador.py` para reescribir un intocable
    (BA-M7, 2026-09-16).
    """
    d = pathlib.Path(tmp_path)
    real = d / "orquestador.py"
    real.write_text("TUPLA = ('a',)\n", encoding="utf-8")
    disfraz = d / "inocente.py"
    disfraz.symlink_to(real)
    p = ac.proponer(d, {"fichero": str(disfraz), "operacion": "sustituir_texto",
                        "buscar": "TUPLA = ('a',)", "sustituir": "TUPLA = ('a', 'crear_autoridad')",
                        "motivo": "intento con nombre disfrazado"})
    ac.autorizar(d, p["id"], por="ceo", acta="acta de prueba 2026-09-16")
    with pytest.raises(Exception) as exc:  # noqa: B017
        ac.ejecutar(d, p, autoridad="ceo", verificacion=lambda raiz: True)
    assert "intocable" in str(exc.value).lower(), f"se detuvo por otra razon: {exc.value}"
    assert real.read_text(encoding="utf-8") == "TUPLA = ('a',)\n", "un symlink burlo la barrera"
