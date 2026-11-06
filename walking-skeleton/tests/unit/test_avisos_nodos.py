"""Avisos de NODO-01 (acta 2026-10-18, opción R1): caída, recuperación y receptor caído.

Se prueba DIRECTAMENTE la función pura `evaluar_avisos_nodos`. Es deliberado: el Centro de Notificaciones
deduplica por huella (fuente|título) y enmascararía un fallo de la función («no actualizar previos»), de modo
que T1 y T2 exigen que una SEGUNDA llamada con los `previos` devueltos no produzca avisos.
"""

from __future__ import annotations

import json
import time

import pytest

from aura_skeleton.adapters.receptor_nodos import crear_vigia_nodos
from aura_skeleton.core.nodos import (
    RegistroNodos,
    construir_latido,
    evaluar_avisos_nodos,
    validar_latido,
)

ID_A = "a" * 32
ARR = "1" * 32
BASE = 1_000_000.0  # reloj de HC-1 en las pruebas
HORA = 3600.0


def _registro(recibido_en, secuencia=1, omitidas=(), nombre="NODO-01"):
    latido = validar_latido(
        construir_latido(ID_A, nombre, secuencia, ARR, 10.0, {"ram_mb": 986.0, "nucleos": 2.0}, omitidas, "1.0")
    )
    reg = RegistroNodos()
    reg.registrar(latido, recibido_en)
    return reg


def _hhmm_dd_mm(instante):
    return time.strftime("%H:%M %d-%m", time.localtime(instante))


def _hhmm(instante):
    return time.strftime("%H:%M", time.localtime(instante))


def _titulo_receptor(ahora):
    return f"No se sabe el estado de los nodos: el receptor de HC-1 no está escuchando (detectado a las {_hhmm(ahora)})"


def _titulos(avisos):
    return [a.titulo for a in avisos]


def test_t1_al_abrir_con_nodo_offline_avisa_una_vez_y_la_segunda_evaluacion_no():
    reg = _registro(BASE)
    ahora = BASE + 600.0  # muy por encima de 3 x 10 s

    avisos, previos = evaluar_avisos_nodos(reg, ahora, True, None)

    assert len(avisos) == 1
    assert avisos[0].titulo == f"Al abrir AURA: NODO-01 sin latido desde las {_hhmm_dd_mm(BASE)}"
    assert avisos[0].prioridad == "alta"
    assert avisos[0].estado == "OFFLINE"
    # La segunda evaluación, con los previos devueltos, NO repite (mata «no actualizar previos»).
    de_nuevo, previos2 = evaluar_avisos_nodos(reg, ahora + 10.0, True, previos)
    assert de_nuevo == ()
    assert previos2 == previos


def test_t2_online_a_offline_en_sesion_avisa_una_vez_y_el_siguiente_turno_no():
    reg = _registro(BASE)
    _, previos = evaluar_avisos_nodos(reg, BASE + 5.0, True, None)  # ONLINE al abrir: nada

    avisos, previos = evaluar_avisos_nodos(reg, BASE + 600.0, True, previos)

    assert len(avisos) == 1
    assert avisos[0].titulo == f"Detectado en esta sesión: NODO-01 sin latido desde las {_hhmm_dd_mm(BASE)}"
    assert avisos[0].prioridad == "alta"
    de_nuevo, _ = evaluar_avisos_nodos(reg, BASE + 700.0, True, previos)
    assert de_nuevo == ()


def test_t2b_online_al_abrir_no_avisa_nada():
    avisos, previos = evaluar_avisos_nodos(_registro(BASE), BASE + 5.0, True, None)
    assert avisos == ()
    assert previos  # se recuerda el estado aunque no se avise


def test_t3_offline_a_online_en_sesion_avisa_recuperacion_con_prioridad_normal():
    _, previos = evaluar_avisos_nodos(_registro(BASE), BASE + 600.0, True, None)  # OFFLINE al abrir
    vuelve = BASE + 2 * HORA
    reg = _registro(vuelve, secuencia=2)

    avisos, previos = evaluar_avisos_nodos(reg, vuelve + 2.0, True, previos)

    assert len(avisos) == 1
    assert avisos[0].titulo == f"Detectado en esta sesión: NODO-01 conectado de nuevo (latido a las {_hhmm(vuelve)})"
    assert avisos[0].prioridad == "normal"
    assert avisos[0].estado == "ONLINE"
    de_nuevo, _ = evaluar_avisos_nodos(reg, vuelve + 4.0, True, previos)
    assert de_nuevo == ()


def test_t3b_recuperacion_a_degraded_tambien_cuenta():
    _, previos = evaluar_avisos_nodos(_registro(BASE), BASE + 600.0, True, None)
    vuelve = BASE + HORA
    reg = _registro(vuelve, secuencia=2, omitidas=("gpu_render",))

    avisos, _ = evaluar_avisos_nodos(reg, vuelve + 2.0, True, previos)

    assert len(avisos) == 1 and "conectado de nuevo" in avisos[0].titulo


def test_t4_receptor_caido_avisa_del_receptor_y_nunca_sin_latido():
    reg = _registro(BASE)  # latido viejo: con receptor vivo sería OFFLINE

    avisos, previos = evaluar_avisos_nodos(reg, BASE + 600.0, False, None)

    assert _titulos(avisos) == [_titulo_receptor(BASE + 600.0)]
    assert avisos[0].prioridad == "alta"
    assert all("sin latido" not in a.titulo for a in avisos)
    # Y no se repite mientras siga caído.
    de_nuevo, _ = evaluar_avisos_nodos(reg, BASE + 700.0, False, previos)
    assert de_nuevo == ()


def test_t4b_receptor_caido_en_sesion_no_fabrica_recuperacion_ni_caida_del_nodo():
    reg = _registro(BASE)
    _, previos = evaluar_avisos_nodos(reg, BASE + 5.0, True, None)  # ONLINE
    avisos, previos = evaluar_avisos_nodos(reg, BASE + 600.0, False, previos)
    assert _titulos(avisos) == [_titulo_receptor(BASE + 600.0)]
    assert previos[ID_A] == "ONLINE"  # el estado del nodo no se pisa con UNKNOWN mientras el receptor está caído


def test_t5_nodo_nunca_registrado_no_avisa_ni_al_abrir_ni_en_turnos():
    vacio = RegistroNodos()
    avisos, previos = evaluar_avisos_nodos(vacio, BASE, True, None)
    assert avisos == ()
    de_nuevo, _ = evaluar_avisos_nodos(vacio, BASE + 60.0, True, previos)
    assert de_nuevo == ()


def test_t6_caida_recuperacion_y_nueva_caida_producen_dos_avisos_de_caida_distintos():
    reg1 = _registro(BASE)
    _, previos = evaluar_avisos_nodos(reg1, BASE + 5.0, True, None)
    caida1, previos = evaluar_avisos_nodos(reg1, BASE + 600.0, True, previos)
    vuelve = BASE + 2 * HORA
    reg2 = _registro(vuelve, secuencia=2)
    recup, previos = evaluar_avisos_nodos(reg2, vuelve + 2.0, True, previos)
    segunda = vuelve + 4 * HORA
    reg3 = _registro(segunda, secuencia=3)
    caida2, _ = evaluar_avisos_nodos(reg3, segunda + 600.0, True, previos)

    assert len(caida1) == 1 and len(recup) == 1 and len(caida2) == 1
    assert "sin latido" in caida1[0].titulo and "sin latido" in caida2[0].titulo
    assert caida1[0].titulo != caida2[0].titulo  # episodios distintos: huellas distintas en el Centro


def test_t7_reloj_de_hc1_que_retrocede_no_fabrica_una_caida():
    reg = _registro(BASE)
    avisos, previos = evaluar_avisos_nodos(reg, BASE - 500.0, True, None)
    assert avisos == ()
    avisos, _ = evaluar_avisos_nodos(reg, BASE - 400.0, True, previos)
    assert avisos == ()


# --- T8: el adaptador --------------------------------------------------------------------------------------


def _escribir(tmp_path, contenido):
    carpeta = tmp_path / "nodos"
    carpeta.mkdir(exist_ok=True)
    (carpeta / "registro.json").write_text(
        contenido if isinstance(contenido, str) else json.dumps(contenido), encoding="utf-8"
    )


def test_t8_registro_ausente_el_puerto_devuelve_none_sin_lanzar(tmp_path):
    assert crear_vigia_nodos(str(tmp_path))(BASE) is None


@pytest.mark.parametrize(
    "contenido", ["{ esto no es json", "[]", '{"nodos": 3}', '{"receptor": {"latido": 1}, "nodos": {"x": 1}}']
)
def test_t8_registro_corrupto_el_puerto_devuelve_none_sin_lanzar(tmp_path, contenido):
    _escribir(tmp_path, contenido)
    assert crear_vigia_nodos(str(tmp_path))(BASE) is None


def test_t8_registro_sin_receptor_no_aporta_conocimiento(tmp_path):
    _escribir(tmp_path, {"nodos": _registro(BASE).a_dict()["nodos"]})
    assert crear_vigia_nodos(str(tmp_path))(BASE + 600.0) is None


def test_t8_registro_valido_devuelve_registro_y_receptor_vivo(tmp_path):
    _escribir(tmp_path, {"receptor": {"latido": BASE, "pid": 1}, "nodos": _registro(BASE).a_dict()["nodos"]})
    vigia = crear_vigia_nodos(str(tmp_path))

    vivo = vigia(BASE + 5.0)
    muerto = vigia(BASE + 300.0)

    assert vivo is not None and vivo[1] is True and vivo[0].obtener(ID_A) is not None
    assert muerto is not None and muerto[1] is False


def test_t8_aura_red_declarado_vacio_no_crea_vigia(monkeypatch):
    monkeypatch.setenv("AURA_RED", "")
    assert crear_vigia_nodos() is None


def test_t8_aura_red_declarado_apunta_a_esa_ruta(monkeypatch, tmp_path):
    _escribir(tmp_path, {"receptor": {"latido": BASE, "pid": 1}, "nodos": {}})
    monkeypatch.setenv("AURA_RED", str(tmp_path))
    vigia = crear_vigia_nodos()
    assert vigia is not None and vigia(BASE + 1.0) is not None


# --- límites defensivos del puerto del vigía ----------------------------------------------------------------


def test_t8_fichero_mayor_que_el_tope_se_rechaza_sin_leerlo_ni_lanzar(tmp_path):
    from aura_skeleton.adapters.receptor_nodos import MAX_BYTES_REGISTRO

    # Registro VÁLIDO rellenado con espacios (JSON admite espacio final): sin el tope se leería y se aceptaría.
    # Con basura en vez de JSON la prueba sería decorativa: se rechazaría por corrupto, haya tope o no (M11).
    valido = json.dumps({"receptor": {"latido": BASE, "pid": 1}, "nodos": _registro(BASE).a_dict()["nodos"]})
    _escribir(tmp_path, valido + " " * (MAX_BYTES_REGISTRO + 1 - len(valido)))
    assert crear_vigia_nodos(str(tmp_path))(BASE) is None


def test_t8_mas_nodos_que_el_tope_se_rechaza_sin_lanzar(tmp_path):
    from aura_skeleton.adapters.receptor_nodos import MAX_NODOS_REGISTRO

    # Nodos VÁLIDOS y distintos (cada clave con su propio latido): sin el tope, `desde_dict` los aceptaría.
    # Reutilizar un mismo latido bajo claves distintas lo haría inválido y la prueba sería decorativa (M12).
    reg = RegistroNodos()
    for i in range(MAX_NODOS_REGISTRO + 1):
        reg.registrar(
            validar_latido(
                construir_latido(f"{i:032x}", f"N{i}", 1, ARR, 10.0, {"ram_mb": 1.0, "nucleos": 1.0}, (), "1.0")
            ),
            BASE,
        )
    nodos = reg.a_dict()["nodos"]
    _escribir(tmp_path, {"receptor": {"latido": BASE, "pid": 1}, "nodos": nodos})
    assert crear_vigia_nodos(str(tmp_path))(BASE) is None


def test_t8_exactamente_el_tope_de_nodos_no_se_rechaza_por_tamano(tmp_path, monkeypatch):
    from aura_skeleton.adapters import receptor_nodos as rn

    monkeypatch.setattr(rn, "MAX_NODOS_REGISTRO", 1)
    _escribir(tmp_path, {"receptor": {"latido": BASE, "pid": 1}, "nodos": _registro(BASE).a_dict()["nodos"]})
    assert crear_vigia_nodos(str(tmp_path))(BASE) is not None


def test_t8_errores_de_tipo_o_clave_en_el_desde_dict_no_escapan(tmp_path, monkeypatch):
    from aura_skeleton.adapters import receptor_nodos as rn

    _escribir(tmp_path, {"receptor": {"latido": BASE, "pid": 1}, "nodos": {}})
    for exc in (KeyError("x"), TypeError("y")):

        def falla(_datos, exc=exc):
            raise exc

        monkeypatch.setattr(rn.RegistroNodos, "desde_dict", staticmethod(falla))
        assert crear_vigia_nodos(str(tmp_path))(BASE) is None
