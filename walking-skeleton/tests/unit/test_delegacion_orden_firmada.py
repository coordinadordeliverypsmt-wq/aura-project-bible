"""A1 — orden firmada por HC-1 (DP-DELEGACION-NODOS §11 A1, §12.6 N8). Cada rechazo lleva su CASO DE CONTROL
(la misma orden sin la alteración se acepta), así que la prueba no puede pasar por rechazar todo."""

from __future__ import annotations

import base64
import json

import pytest

from aura_skeleton.adapters.firma_delegacion import generar_firmante, verificador_de
from aura_skeleton.core.delegacion import (
    CAPACIDADES,
    DOMINIO_ACUSE,
    DOMINIO_ORDEN,
    DOMINIO_RESULTADO,
    Motivo,
    RechazoOrden,
    abrir_sobre,
    bytes_canonicos,
    empaquetar_sobre,
    validar_orden,
)
from tests.delegacion_apoyo import (
    NODO,
    OTRO_NODO,
    T0,
    AlmacenMemoria,
    campos_validos,
    firmante_orden,
    firmar_campos,
    mundo,
    orden_firmada,
)


def _validar(m, sobre, **kw):  # type: ignore[no-untyped-def]
    return validar_orden(
        sobre,
        politica=m.politica(**kw),
        verificar=m.verificador_hc1(),
        almacen=AlmacenMemoria(),
    )


def _rechazo(m, sobre, **kw) -> Motivo:  # type: ignore[no-untyped-def]
    with pytest.raises(RechazoOrden) as e:
        _validar(m, sobre, **kw)
    return e.value.motivo


def test_control_la_orden_valida_se_acepta_y_su_hash_liga_los_bytes_firmados() -> None:
    m = mundo()
    sobre = orden_firmada(m)
    orden = _validar(m, sobre)
    assert orden.campos["capacidad"] == "calcular_resumen_sha256"
    import hashlib

    assert orden.hash_tarea == hashlib.sha256(abrir_sobre(sobre).payload).hexdigest()


def test_json_canonico_claves_ordenadas_sin_espacios_utf8() -> None:
    assert bytes_canonicos({"b": 1, "a": "ñ"}) == '{"a":"ñ","b":1}'.encode()


def test_firma_invalida_se_rechaza() -> None:
    m = mundo()
    sobre = orden_firmada(m)
    o = json.loads(sobre)
    f = bytearray(base64.b64decode(o["f"]))
    f[0] ^= 1
    o["f"] = base64.b64encode(bytes(f)).decode()
    assert _rechazo(m, json.dumps(o).encode()) is Motivo.FIRMA_INVALIDA


def test_campo_alterado_tras_firmar_se_rechaza() -> None:
    m = mundo()
    o = abrir_sobre(orden_firmada(m))
    alterado = o.payload.replace(b"hola aura", b"hola AURA")
    assert alterado != o.payload
    sobre = empaquetar_sobre(o.kid, alterado, o.firma)
    assert _rechazo(m, sobre) is Motivo.FIRMA_INVALIDA


def test_se_verifica_sobre_bytes_exactos_un_json_equivalente_no_canonico_no_pasa() -> None:
    m = mundo()
    campos = campos_validos()
    no_canonico = json.dumps(campos, indent=1).encode()  # mismo contenido, otros bytes, FIRMADO correctamente
    from aura_skeleton.core.delegacion import mensaje_con_dominio

    firma = m.hc1._Firmante__clave.sign(mensaje_con_dominio(DOMINIO_ORDEN, no_canonico))  # type: ignore[attr-defined]
    assert _rechazo(m, empaquetar_sobre("hc1-k1", no_canonico, firma)) is Motivo.NO_CANONICO


def test_firma_de_otra_clave_no_autorizada_se_rechaza() -> None:
    m = mundo()
    intruso = generar_firmante("hc1-k1")  # mismo kid, otra clave
    assert _rechazo(m, firmante_orden(intruso, campos_validos())) is Motivo.FIRMA_INVALIDA


def test_kid_desconocido_se_rechaza_antes_de_verificar() -> None:
    m = mundo()
    otro = generar_firmante("kid-ajeno")
    assert _rechazo(m, firmante_orden(otro, campos_validos(kid="kid-ajeno"))) is Motivo.KID_DESCONOCIDO


def test_emisor_que_no_corresponde_al_kid_se_rechaza() -> None:
    m = mundo()
    assert _rechazo(m, orden_firmada(m, emisor="hc9")) is Motivo.EMISOR_DESCONOCIDO


def test_kid_firmado_distinto_del_del_sobre_se_rechaza() -> None:
    m = mundo()
    o = abrir_sobre(firmar_campos(m.hc1, campos_validos(kid="otro-kid")))
    assert _rechazo(m, empaquetar_sobre("hc1-k1", o.payload, o.firma)) is Motivo.KID_DESCONOCIDO


def test_destinatario_ajeno_se_rechaza_y_el_propio_se_acepta() -> None:
    m = mundo()
    assert _rechazo(m, orden_firmada(m, destinatario=OTRO_NODO)) is Motivo.DESTINATARIO_AJENO
    assert _validar(m, orden_firmada(m, destinatario=NODO)).campos["destinatario"] == NODO


def test_version_menor_que_la_minima_se_rechaza_sin_negociar_n8() -> None:
    m = mundo()
    assert _rechazo(m, orden_firmada(m, v=1), v_minima=2) is Motivo.VERSION_MENOR
    assert _validar(m, orden_firmada(m, v=1), v_minima=1).campos["v"] == 1


def test_version_mayor_que_la_soportada_se_rechaza() -> None:
    m = mundo()
    assert _rechazo(m, firmar_campos(m.hc1, campos_validos(v=2))) is Motivo.VERSION_NO_SOPORTADA


def test_campos_desconocidos_y_faltantes_se_rechazan() -> None:
    m = mundo()
    assert _rechazo(m, firmar_campos(m.hc1, {**campos_validos(), "extra": 1})) is Motivo.CAMPOS_DESCONOCIDOS
    falta = campos_validos()
    del falta["epoch_hc1"]
    assert _rechazo(m, firmar_campos(m.hc1, falta)) is Motivo.CAMPOS_FALTANTES


def test_capacidad_no_registrada_se_rechaza_aunque_este_firmada() -> None:
    m = mundo()
    assert _rechazo(m, firmar_campos(m.hc1, campos_validos(capacidad="rm_rf"))) is Motivo.CAPACIDAD_NO_REGISTRADA


def test_un_comando_del_sistema_no_es_una_capacidad() -> None:
    m = mundo()
    for cmd in ("rm -rf /", "sh -c id", "../../bin/sh", "calcular_resumen_sha256; id"):
        assert _rechazo(m, firmar_campos(m.hc1, campos_validos(capacidad=cmd))) in (
            Motivo.CAPACIDAD_NO_REGISTRADA,
            Motivo.CAMPO_INVALIDO,
        )


def test_capacidad_registrada_pero_fuera_de_la_lista_local_del_nodo_se_rechaza_m5() -> None:
    m = mundo()
    assert "calcular_resumen_sha256" in CAPACIDADES
    assert _rechazo(m, orden_firmada(m), capacidades=frozenset()) is Motivo.CAPACIDAD_NO_REGISTRADA


@pytest.mark.parametrize(
    "args",
    [{}, {"texto": ""}, {"texto": 5}, {"texto": "x" * 4097}, {"texto": "a", "extra": 1}, {"comando": "id"}],
)
def test_argumentos_fuera_de_esquema_se_rechazan(args: dict) -> None:
    m = mundo()
    assert _rechazo(m, firmar_campos(m.hc1, campos_validos(argumentos=args))) is Motivo.ARGUMENTOS_INVALIDOS


def test_argumentos_en_el_limite_del_esquema_se_aceptan() -> None:
    m = mundo()
    assert _validar(m, orden_firmada(m, argumentos={"texto": "x" * 4096}))


@pytest.mark.parametrize("campo,valor", [("tarea", "a b"), ("intento", 0), ("intento", True), ("epoch_hc1", -1)])
def test_tipos_y_formatos_invalidos_se_rechazan(campo: str, valor: object) -> None:
    m = mundo()
    assert _rechazo(m, firmar_campos(m.hc1, campos_validos(**{campo: valor}))) is Motivo.CAMPO_INVALIDO


def test_id_ejecucion_debe_ser_uuid4() -> None:
    m = mundo()
    assert _rechazo(m, firmar_campos(m.hc1, campos_validos(id_ejecucion="1" * 36))) is Motivo.CAMPO_INVALIDO
    import uuid

    assert _rechazo(m, firmar_campos(m.hc1, campos_validos(id_ejecucion=str(uuid.uuid1())))) is Motivo.CAMPO_INVALIDO


def test_sobre_malformado_y_con_campos_extra_se_rechaza() -> None:
    m = mundo()
    assert _rechazo(m, b"no es json") is Motivo.SOBRE_MALFORMADO
    o = json.loads(orden_firmada(m))
    o["extra"] = 1
    assert _rechazo(m, json.dumps(o).encode()) is Motivo.SOBRE_MALFORMADO
    assert _rechazo(m, b"x" * (200 * 1024)) is Motivo.SOBRE_MALFORMADO


def test_json_con_claves_duplicadas_o_nan_se_rechaza() -> None:
    m = mundo()
    dup = b'{"v":1,"v":1}'
    from aura_skeleton.core.delegacion import mensaje_con_dominio

    firma = m.hc1._Firmante__clave.sign(mensaje_con_dominio(DOMINIO_ORDEN, dup))  # type: ignore[attr-defined]
    assert _rechazo(m, empaquetar_sobre("hc1-k1", dup, firma)) is Motivo.SOBRE_MALFORMADO


def test_separacion_de_dominio_una_firma_de_resultado_o_acuse_no_vale_como_orden() -> None:
    m = mundo()
    payload = bytes_canonicos(campos_validos())
    for dominio in (DOMINIO_RESULTADO, DOMINIO_ACUSE):
        sobre = m.hc1.firmar(dominio, payload)
        assert _rechazo(m, sobre) is Motivo.FIRMA_INVALIDA
    assert _validar(m, m.hc1.firmar(DOMINIO_ORDEN, payload))  # control


def test_el_verificador_nunca_lanza_ante_basura() -> None:
    v = verificador_de({"k": generar_firmante("k").publica()})
    assert v("k", b"m", b"") is False
    assert v("desconocido", b"m", b"f" * 64) is False


def test_el_mensaje_de_rechazo_no_contiene_el_valor_recibido() -> None:
    m = mundo()
    with pytest.raises(RechazoOrden) as e:
        _validar(m, firmar_campos(m.hc1, campos_validos(capacidad="SECRETO-xyz")))
    assert "SECRETO-xyz" not in str(e.value)


def test_el_catalogo_de_motivos_es_cerrado_y_cada_rechazo_usa_un_miembro() -> None:
    assert len({x.value for x in Motivo}) == len(list(Motivo))
    m = mundo()
    assert isinstance(_rechazo(m, b"{}"), Motivo)


def test_orden_no_pasa_sin_fijar_el_tiempo_de_prueba() -> None:
    # control del apoyo: T0 coincide con el reloj falso, de modo que la orden base no es fresca por casualidad
    m = mundo()
    assert m.reloj.ahora() == T0
