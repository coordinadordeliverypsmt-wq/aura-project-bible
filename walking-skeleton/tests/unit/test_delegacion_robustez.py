"""Revisión de seguridad independiente: M-1 (profundidad), B-1 (fullmatch), A1 (alg, revocación, canonicalización).

Cada garantía tiene su CONTROL positivo: la misma entrada sin el defecto se acepta.
"""

from __future__ import annotations

import json
import os
import stat
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from aura_skeleton.adapters.almacen_consumidas import AlmacenConsumidas
from aura_skeleton.adapters.fijacion_spki import ErrorFijacion, normalizar_pines
from aura_skeleton.adapters.firma_delegacion import (
    ErrorClave,
    cargar_revocados,
    revocar,
    verificador_de,
)
from aura_skeleton.core.delegacion import (
    DOMINIO_ORDEN,
    DOMINIO_RESULTADO,
    PROFUNDIDAD_MAX,
    Motivo,
    RechazoOrden,
    abrir_sobre,
    bytes_canonicos,
    empaquetar_sobre,
    leer_json_estricto,
    payload_acuse,
    payload_orden,
    payload_resultado,
    validar_campos_acuse,
    validar_campos_orden,
    validar_campos_resultado,
    validar_orden,
    verificar_y_leer,
)
from aura_skeleton.core.delegacion_hc1 import SeguimientoHC1
from tests.delegacion_apoyo import (
    NODO,
    OTRO_NODO,
    campos_validos,
    firmante_orden,
    firmar_campos,
    mundo,
)


def _motivo(fn, *a, **kw) -> Motivo:  # type: ignore[no-untyped-def]
    with pytest.raises(RechazoOrden) as e:
        fn(*a, **kw)
    return e.value.motivo


def _validar(m, sobre, almacen, **kw):  # type: ignore[no-untyped-def]
    return validar_orden(sobre, politica=m.politica(**kw), verificar=m.verificador_hc1(), almacen=almacen)


# --- M-1: profundidad -------------------------------------------------------------------------------------


def test_m1_control_profundidad_maxima_se_acepta_y_una_mas_se_rechaza() -> None:
    assert leer_json_estricto(b"[" * PROFUNDIDAD_MAX + b"]" * PROFUNDIDAD_MAX) is not None
    with pytest.raises(ValueError):
        leer_json_estricto(b"[" * (PROFUNDIDAD_MAX + 1) + b"]" * (PROFUNDIDAD_MAX + 1))
    with pytest.raises(ValueError):
        leer_json_estricto(b'{"a":' * (PROFUNDIDAD_MAX + 1) + b"1" + b"}" * (PROFUNDIDAD_MAX + 1))


def test_m1_los_corchetes_dentro_de_cadenas_no_cuentan_como_anidamiento() -> None:
    texto = '"' + "[" * 500 + '\\"' + "{" * 500 + '"'
    assert leer_json_estricto(f'{{"a":{texto}}}'.encode()) == {"a": "[" * 500 + '"' + "{" * 500}


def test_m1_sobre_con_90000_niveles_se_rechaza_con_motivo_cerrado_antes_de_verificar_firma(tmp_path: Path) -> None:
    m = mundo()
    sobre = b'{"p":' + b"[" * 90_000 + b"]" * 90_000 + b"}"
    assert len(sobre) < 192 * 1024  # cabe en el límite de tamaño: es el ataque real
    llamadas: list[int] = []

    def verificador(*_: Any) -> bool:
        llamadas.append(1)
        return True

    assert _motivo(abrir_sobre, sobre) is Motivo.SOBRE_MALFORMADO  # antes: RecursionError sin capturar
    motivo = _motivo(
        validar_orden, sobre, politica=m.politica(), verificar=verificador, almacen=AlmacenConsumidas(tmp_path / "n")
    )
    assert motivo is Motivo.SOBRE_MALFORMADO and llamadas == []


def test_m1_payload_firmado_pero_profundo_se_rechaza_tras_la_firma() -> None:
    m = mundo()
    profundo = b'{"a":' + b"[" * 5000 + b"]" * 5000 + b"}"
    sobre = m.hc1.firmar(DOMINIO_ORDEN, profundo)
    assert _motivo(verificar_y_leer, sobre, DOMINIO_ORDEN, m.verificador_hc1()) is Motivo.SOBRE_MALFORMADO
    ok = m.hc1.firmar(DOMINIO_ORDEN, b'{"a":[1]}')  # control: mismo camino, sin profundidad
    assert verificar_y_leer(ok, DOMINIO_ORDEN, m.verificador_hc1())[1] == {"a": [1]}


def test_m1_registrar_emision_acuses_y_resultados_profundos_son_rechazos_no_excepciones() -> None:
    m = mundo()
    hc1 = SeguimientoHC1(m.verificador_nodos(), m.reloj)
    hostil = b'{"p":' + b"[" * 90_000 + b"]" * 90_000 + b"}"
    assert _motivo(hc1.registrar_emision, hostil, 60) is Motivo.SOBRE_MALFORMADO
    assert _motivo(hc1.recibir_acuse, hostil, NODO) is Motivo.SOBRE_MALFORMADO
    assert _motivo(hc1.recibir_resultado, hostil, NODO) is Motivo.SOBRE_MALFORMADO
    # emisión con payload (firmado por nosotros) que no es un objeto: rechazo, no AttributeError/TypeError
    no_objeto = empaquetar_sobre("hc1-k1", b"[1,2]", b"x")
    assert _motivo(hc1.registrar_emision, no_objeto, 60) is Motivo.SOBRE_MALFORMADO
    hc1.registrar_emision(firmante_orden(m.hc1, campos_validos()), 60)  # control


# --- B-1: fullmatch ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("campo", ["tarea", "emisor", "capacidad", "kid", "destinatario"])
def test_b1_un_salto_de_linea_final_en_un_campo_de_la_orden_se_rechaza(campo: str) -> None:
    base = campos_validos()
    validar_campos_orden(base)  # control
    with pytest.raises(RechazoOrden) as e:
        validar_campos_orden({**base, campo: base[campo] + "\n"})
    assert e.value.motivo is Motivo.CAMPO_INVALIDO


@pytest.mark.parametrize("campo", ["tarea", "id_nodo", "hash_tarea"])
def test_b1_un_salto_de_linea_final_en_resultado_y_acuse_se_rechaza(campo: str) -> None:
    m = mundo()
    orden_bytes = firmante_orden(m.hc1, campos_validos())
    from aura_skeleton.core.delegacion import OrdenValida, hash_de

    payload = abrir_sobre(orden_bytes).payload
    ov = OrdenValida(json.loads(payload), payload, hash_de(payload))
    for payload_fn, validar in (
        (lambda: payload_resultado(ov, NODO, "x"), validar_campos_resultado),
        (lambda: payload_acuse(ov, NODO, 1.0), validar_campos_acuse),
    ):
        c = json.loads(payload_fn())
        validar(c)  # control
        if campo in c:
            with pytest.raises(RechazoOrden) as e:
                validar({**c, campo: c[campo] + "\n"})
            assert e.value.motivo is Motivo.CAMPO_INVALIDO


def test_b1_kid_del_sobre_y_pin_con_salto_de_linea_se_rechazan() -> None:
    assert abrir_sobre(empaquetar_sobre("abc", b"{}", b"f")).kid == "abc"  # control
    assert _motivo(abrir_sobre, empaquetar_sobre("abc\n", b"{}", b"f")) is Motivo.SOBRE_MALFORMADO
    assert normalizar_pines(["a" * 64]) == {"a" * 64}  # control
    with pytest.raises(ErrorFijacion):
        normalizar_pines(["a" * 64 + "\n"])


# --- A1: algoritmo -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("alg", ["ed448", "none", "Ed25519", "ES256", "", None, 25519, ["ed25519"]])
def test_a1_alg_distinto_de_ed25519_se_rechaza_aunque_este_firmado(tmp_path: Path, alg: object) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "n")
    sobre = firmar_campos(m.hc1, campos_validos(alg=alg))
    assert _motivo(_validar, m, sobre, alm) is Motivo.ALG_NO_SOPORTADO
    assert _validar(m, firmante_orden(m.hc1, campos_validos()), alm)  # control: ed25519 y sin quemar nada


def test_a1_alg_es_obligatorio_y_va_firmado_en_orden_resultado_y_acuse() -> None:
    sin_alg = {k: v for k, v in campos_validos().items() if k != "alg"}
    assert _motivo(validar_campos_orden, sin_alg) is Motivo.CAMPOS_FALTANTES
    m = mundo()
    payload = abrir_sobre(firmante_orden(m.hc1, campos_validos())).payload
    from aura_skeleton.core.delegacion import OrdenValida, hash_de

    ov = OrdenValida(json.loads(payload), payload, hash_de(payload))
    for datos, validar in ((payload_resultado(ov, NODO, "x"), validar_campos_resultado),
                           (payload_acuse(ov, NODO, 1.0), validar_campos_acuse)):  # fmt: skip
        c = json.loads(datos)
        assert c["alg"] == "ed25519"
        validar(c)
        assert _motivo(validar, {**c, "alg": "ed448"}) is Motivo.ALG_NO_SOPORTADO


# --- A1: revocación ----------------------------------------------------------------------------------------


def test_a1_orden_firmada_con_un_kid_revocado_se_rechaza_y_con_uno_vigente_se_acepta(tmp_path: Path) -> None:
    m = mundo()
    alm = AlmacenConsumidas(tmp_path / "n")
    sobre = firmante_orden(m.hc1, campos_validos())
    assert _motivo(_validar, m, sobre, alm, revocados=frozenset({"hc1-k1"})) is Motivo.KID_REVOCADO
    assert _validar(m, sobre, alm, revocados=frozenset({"otro-kid"}))  # control: otro kid revocado no afecta


def test_a1_la_lista_de_revocados_persiste_y_falla_cerrada(tmp_path: Path) -> None:
    ruta = tmp_path / "revocados.jsonl"
    assert cargar_revocados(ruta) == frozenset()  # aún no se revocó nada
    revocar(ruta, "hc1-k1")
    revocar(ruta, "hc1-k0")
    revocar(ruta, "hc1-k1")  # idempotente
    assert cargar_revocados(ruta) == {"hc1-k1", "hc1-k0"}  # "reinicio": lectura nueva
    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o600
    m = mundo()
    sobre = firmante_orden(m.hc1, campos_validos())
    alm = AlmacenConsumidas(tmp_path / "n")
    assert _motivo(_validar, m, sobre, alm, revocados=cargar_revocados(ruta)) is Motivo.KID_REVOCADO
    sana = ruta.read_bytes()
    for roto in (
        b"{no es json\n",
        b'{"kid":"bien"}\n{"kid":"mal\\n"}\n',
        b'{"kid":"x","otro":1}\n',
        b"[]\n",
        sana + b'{"kid":"tru',
    ):
        ruta.write_bytes(roto)
        with pytest.raises(ErrorClave):
            cargar_revocados(ruta)  # ilegible, mal formada o TRUNCADA: nunca se ignora
    ruta.write_bytes(sana)
    os.chmod(ruta, 0o666)
    with pytest.raises(ErrorClave):
        cargar_revocados(ruta)
    os.chmod(ruta, 0o600)
    assert cargar_revocados(ruta) == {"hc1-k1", "hc1-k0"}  # control
    with pytest.raises(ErrorClave):
        revocar(ruta, "mal\n")


def test_a1_hc1_no_acepta_firmas_de_una_clave_de_nodo_revocada() -> None:
    m = mundo()
    claves = {NODO: m.nodo.publica(), OTRO_NODO: m.otro_nodo.publica()}
    sobre = m.nodo.firmar(DOMINIO_RESULTADO, b"{}")
    ab = abrir_sobre(sobre)
    msg = DOMINIO_RESULTADO + ab.payload
    assert verificador_de(claves)(NODO, msg, ab.firma) is True  # control
    assert verificador_de(claves, revocados={NODO})(NODO, msg, ab.firma) is False
    assert verificador_de(claves, revocados={NODO})(OTRO_NODO, msg, ab.firma) is False  # (firma ajena: no es suya)


# --- A1: canonicalización ----------------------------------------------------------------------------------


def _sobre_con_payload(m, payload: bytes) -> bytes:  # type: ignore[no-untyped-def]
    return m.hc1.firmar(DOMINIO_ORDEN, payload)


def test_a1_solo_la_forma_canonica_exacta_pasa() -> None:
    m = mundo()
    c = campos_validos()
    canonico = bytes_canonicos(c)
    assert verificar_y_leer(_sobre_con_payload(m, canonico), DOMINIO_ORDEN, m.verificador_hc1())[1] == c  # control
    # espacios, orden de claves, escapes \u equivalentes: mismo objeto, otros bytes => NO_CANONICO
    con_espacios = json.dumps(c, sort_keys=True).encode()
    reordenado = json.dumps(c, sort_keys=False, separators=(",", ":")).encode()
    con_escape = canonico.replace(b'"t-001"', b'"t\\u002d001"')
    assert con_escape != canonico and json.loads(con_escape) == c
    for variante in (con_espacios, reordenado, con_escape):
        assert variante != canonico
        assert (
            _motivo(verificar_y_leer, _sobre_con_payload(m, variante), DOMINIO_ORDEN, m.verificador_hc1())
            is Motivo.NO_CANONICO
        )


def test_a1_uno_y_uno_punto_cero_son_distintos() -> None:
    m = mundo()
    c = campos_validos()
    canonico = bytes_canonicos(c)
    assert b'"intento":1,' in canonico
    como_float = canonico.replace(b'"intento":1,', b'"intento":1.0,')
    en_exponente = canonico.replace(b'"intento":1,', b'"intento":1e0,')
    # 1.0: es canónico como float pero NO es un entero => campo inválido; 1e0: ni siquiera es canónico
    sobre_f = _sobre_con_payload(m, como_float)
    _, campos = verificar_y_leer(sobre_f, DOMINIO_ORDEN, m.verificador_hc1())
    assert campos["intento"] == 1.0 and _motivo(validar_campos_orden, campos) is Motivo.CAMPO_INVALIDO
    assert (
        _motivo(verificar_y_leer, _sobre_con_payload(m, en_exponente), DOMINIO_ORDEN, m.verificador_hc1())
        is Motivo.NO_CANONICO
    )
    validar_campos_orden(json.loads(canonico))  # control: el entero 1 sí


def test_a1_nfc_y_nfd_no_se_normalizan_en_silencio_solo_nfc_pasa() -> None:
    m = mundo()
    nfc = unicodedata.normalize("NFC", "canción é")
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd and len(nfd) > len(nfc)
    ok = bytes_canonicos(campos_validos(argumentos={"texto": nfc}))
    assert verificar_y_leer(_sobre_con_payload(m, ok), DOMINIO_ORDEN, m.verificador_hc1())[1]["argumentos"] == {
        "texto": nfc
    }
    malo = bytes_canonicos(campos_validos(argumentos={"texto": nfd}))  # canónico en bytes, pero NO NFC
    assert (
        _motivo(verificar_y_leer, _sobre_con_payload(m, malo), DOMINIO_ORDEN, m.verificador_hc1()) is Motivo.NO_CANONICO
    )
    # también en claves anidadas
    malo_clave = bytes_canonicos({**campos_validos(), "x": {nfd: 1}})
    assert (
        _motivo(verificar_y_leer, _sobre_con_payload(m, malo_clave), DOMINIO_ORDEN, m.verificador_hc1())
        is Motivo.NO_CANONICO
    )


def test_a1_payload_orden_del_firmador_tambien_exige_nfc(tmp_path: Path) -> None:
    nfd = unicodedata.normalize("NFD", "é")
    assert payload_orden(campos_validos(argumentos={"texto": "é"}))  # control
    # el firmador no tiene por qué normalizar: lo que no sea NFC no llegaría a pasar la validación del nodo
    m = mundo()
    sobre = firmante_orden(m.hc1, campos_validos(argumentos={"texto": nfd}))
    assert _motivo(_validar, m, sobre, AlmacenConsumidas(tmp_path / "n")) is Motivo.NO_CANONICO
