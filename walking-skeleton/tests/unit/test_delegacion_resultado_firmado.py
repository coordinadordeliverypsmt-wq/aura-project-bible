"""A2 — resultado y acuse firmados por el nodo, vinculación y estados (§11 A2, §12.4, §12.6 N6/N7, HAL-041-2)."""

from __future__ import annotations

import base64
from typing import Any

import pytest

from aura_skeleton.adapters.almacen_consumidas import AlmacenConsumidas
from aura_skeleton.adapters.firma_delegacion import Firmante
from aura_skeleton.core.delegacion import (
    DOMINIO_ACUSE,
    DOMINIO_RESULTADO,
    SALIDA_MAX_BYTES,
    Motivo,
    RechazoOrden,
    bytes_canonicos,
)
from aura_skeleton.core.delegacion_hc1 import Estado, SeguimientoHC1
from aura_skeleton.core.delegacion_nodo import NodoDelegado
from tests.delegacion_apoyo import NODO, OTRO_NODO, Mundo, RegistroSintetico, campos_validos, firmante_orden, mundo


class Escena:
    def __init__(self, tmp_path: Any) -> None:
        self.m: Mundo = mundo()
        self.hc1 = SeguimientoHC1(self.m.verificador_nodos(), self.m.reloj)
        self.nodo = NodoDelegado(
            self.m.politica(), self.m.verificador_hc1(), AlmacenConsumidas(tmp_path / "nodo"), self.m.nodo.firmar
        )
        self.registro = RegistroSintetico()

    def emitir(self, **cambios: Any) -> tuple[bytes, dict[str, Any]]:
        campos = campos_validos(**cambios)
        sobre = firmante_orden(self.m.hc1, campos)
        self.hc1.registrar_emision(sobre, techo_total_s=60)
        return sobre, campos

    def ciclo_hasta_resultado(self, **cambios: Any) -> tuple[str, bytes, bytes]:
        sobre, c = self.emitir(**cambios)
        ac = self.nodo.aceptar(sobre)
        res = self.nodo.ejecutar(ac.orden)
        return c["id_ejecucion"], ac.acuse, res


@pytest.fixture
def esc(tmp_path: Any) -> Escena:
    return Escena(tmp_path)


def _rechazo(fn, *a) -> Motivo:  # type: ignore[no-untyped-def]
    with pytest.raises(RechazoOrden) as e:
        fn(*a)
    return e.value.motivo


def _resultado_a_medida(firmante: Firmante, **campos: Any) -> bytes:
    return firmante.firmar(DOMINIO_RESULTADO, bytes_canonicos(campos))


def _base_resultado(esc: Escena, ident: str, **cambios: Any) -> dict[str, Any]:
    ej = esc.hc1.ejecucion(ident)
    assert ej is not None
    base = {
        "v": 1,
        "alg": "ed25519",
        "tarea": ej.tarea,
        "intento": ej.intento,
        "id_nodo": NODO,
        "id_ejecucion": ident,
        "hash_tarea": ej.hash_tarea,
        "salida": "0" * 64,
    }
    base.update(cambios)
    return base


def test_ciclo_completo_solo_el_ultimo_estado_cuenta_como_completada(esc: Escena) -> None:
    ident, acuse, res = esc.ciclo_hasta_resultado()
    ej = esc.hc1.ejecucion(ident)
    assert ej is not None and ej.estado is Estado.EMITIDA and not ej.completada
    esc.hc1.recibir_acuse(acuse, NODO)
    assert ej.estado is Estado.ACEPTADA and not ej.completada
    esc.hc1.recibir_resultado(res, NODO)
    assert ej.estado is Estado.RESULTADO_FIRMADO and not ej.completada
    assert esc.hc1.validar(ident) is True
    assert ej.estado is Estado.VALIDADO and not ej.completada
    esc.hc1.incorporar(ident, esc.registro)
    assert ej.estado is Estado.INCORPORADO and ej.completada
    assert len(esc.registro) == 1 and esc.registro[0]["verificado"] is True
    assert esc.registro[0]["hash_tarea"] == ej.hash_tarea
    assert base64.b64decode(esc.registro[0]["orden_firmada"]) == ej.sobre_orden


def test_el_resultado_se_valida_sin_acuse_previo_pero_el_acuse_perdido_no_completa_nada(esc: Escena) -> None:
    ident, _, res = esc.ciclo_hasta_resultado()
    esc.hc1.recibir_resultado(res, NODO)
    assert esc.hc1.ejecucion(ident).estado is Estado.RESULTADO_FIRMADO  # type: ignore[union-attr]


def test_solo_incorporado_es_completada() -> None:
    from aura_skeleton.core.delegacion_hc1 import Ejecucion

    for est in Estado:
        ej = Ejecucion("i", "t", 1, NODO, "c", {}, "h", b"", 0.0, estado=est)
        assert ej.completada is (est is Estado.INCORPORADO)


def test_resultado_alterado_se_rechaza(esc: Escena) -> None:
    ident, _, res = esc.ciclo_hasta_resultado()
    import json

    o = json.loads(res)
    p = base64.b64decode(o["p"])
    o["p"] = base64.b64encode(p.replace(b'"salida":"', b'"salida":"0')).decode()
    assert _rechazo(esc.hc1.recibir_resultado, json.dumps(o).encode(), NODO) is Motivo.FIRMA_INVALIDA
    esc.hc1.recibir_resultado(res, NODO)  # control: el original se acepta


def test_resultado_de_otro_nodo_en_el_subject_ajeno_se_rechaza(esc: Escena) -> None:
    ident, _, _ = esc.ciclo_hasta_resultado()
    de_otro = _resultado_a_medida(esc.m.otro_nodo, **_base_resultado(esc, ident, id_nodo=OTRO_NODO))
    # llega por el subject de OTRO_NODO: firma e id_nodo cuadran, pero NO es el destinatario de la orden
    assert _rechazo(esc.hc1.recibir_resultado, de_otro, OTRO_NODO) is Motivo.NODO_AJENO
    # llega por el subject del destinatario con kid ajeno
    assert _rechazo(esc.hc1.recibir_resultado, de_otro, NODO) is Motivo.KID_DESCONOCIDO


def test_id_nodo_distinto_del_subject_o_firma_con_clave_ajena_se_rechaza(esc: Escena) -> None:
    ident, _, _ = esc.ciclo_hasta_resultado()
    mintiendo = _resultado_a_medida(esc.m.otro_nodo, **_base_resultado(esc, ident, id_nodo=NODO))
    assert _rechazo(esc.hc1.recibir_resultado, mintiendo, OTRO_NODO) is Motivo.NODO_AJENO
    # sobre con kid=NODO pero firmado con la clave de otro nodo
    from aura_skeleton.core.delegacion import empaquetar_sobre, mensaje_con_dominio

    payload = bytes_canonicos(_base_resultado(esc, ident))
    firma = esc.m.otro_nodo._Firmante__clave.sign(mensaje_con_dominio(DOMINIO_RESULTADO, payload))  # type: ignore[attr-defined]
    assert _rechazo(esc.hc1.recibir_resultado, empaquetar_sobre(NODO, payload, firma), NODO) is Motivo.FIRMA_INVALIDA


def test_hash_tarea_que_no_corresponde_se_rechaza(esc: Escena) -> None:
    ident, _, _ = esc.ciclo_hasta_resultado()
    res = _resultado_a_medida(esc.m.nodo, **_base_resultado(esc, ident, hash_tarea="f" * 64))
    assert _rechazo(esc.hc1.recibir_resultado, res, NODO) is Motivo.HASH_NO_CORRESPONDE
    ok = _resultado_a_medida(esc.m.nodo, **_base_resultado(esc, ident))  # control
    esc.hc1.recibir_resultado(ok, NODO)


def test_resultado_sin_hash_tarea_es_campo_faltante(esc: Escena) -> None:
    ident, _, _ = esc.ciclo_hasta_resultado()
    base = _base_resultado(esc, ident)
    del base["hash_tarea"]
    res = _resultado_a_medida(esc.m.nodo, **base)
    assert _rechazo(esc.hc1.recibir_resultado, res, NODO) is Motivo.CAMPOS_FALTANTES


def test_vinculo_roto_tarea_o_intento_distintos(esc: Escena) -> None:
    ident, _, _ = esc.ciclo_hasta_resultado()
    for cambio in ({"tarea": "otra"}, {"intento": 2}):
        res = _resultado_a_medida(esc.m.nodo, **_base_resultado(esc, ident, **cambio))
        assert _rechazo(esc.hc1.recibir_resultado, res, NODO) is Motivo.VINCULO_ROTO


def test_ejecucion_desconocida_se_rechaza(esc: Escena) -> None:
    ident, _, _ = esc.ciclo_hasta_resultado()
    import uuid

    res = _resultado_a_medida(esc.m.nodo, **_base_resultado(esc, ident, id_ejecucion=str(uuid.uuid4())))
    assert _rechazo(esc.hc1.recibir_resultado, res, NODO) is Motivo.EJECUCION_DESCONOCIDA


def test_id_ejecucion_que_no_es_el_intento_en_curso_se_rechaza(esc: Escena) -> None:
    ident1, _, res1 = esc.ciclo_hasta_resultado(intento=1)
    esc.hc1.marcar_desconexion(NODO)  # intento 1 interrumpido
    ident2, _, res2 = esc.ciclo_hasta_resultado(intento=2)
    assert _rechazo(esc.hc1.recibir_resultado, res1, NODO) is Motivo.EJECUCION_NO_EN_CURSO
    esc.hc1.recibir_resultado(res2, NODO)  # control: el intento en curso sí
    assert ident1 != ident2


def test_resultado_duplicado_se_rechaza(esc: Escena) -> None:
    _, _, res = esc.ciclo_hasta_resultado()
    esc.hc1.recibir_resultado(res, NODO)
    assert _rechazo(esc.hc1.recibir_resultado, res, NODO) is Motivo.RESULTADO_DUPLICADO


def test_salida_en_el_limite_se_acepta_y_por_encima_se_rechaza(esc: Escena) -> None:
    ident, _, _ = esc.ciclo_hasta_resultado()
    grande = _resultado_a_medida(esc.m.nodo, **_base_resultado(esc, ident, salida="x" * (SALIDA_MAX_BYTES + 1)))
    assert _rechazo(esc.hc1.recibir_resultado, grande, NODO) is Motivo.SALIDA_EXCESIVA
    limite = _resultado_a_medida(esc.m.nodo, **_base_resultado(esc, ident, salida="x" * SALIDA_MAX_BYTES))
    esc.hc1.recibir_resultado(limite, NODO)


def test_el_nodo_no_puede_emitir_una_salida_excesiva() -> None:
    from aura_skeleton.core.delegacion import OrdenValida, payload_resultado

    ov = OrdenValida({"tarea": "t", "intento": 1, "id_ejecucion": "i"}, b"", "h")
    with pytest.raises(RechazoOrden):
        payload_resultado(ov, NODO, "x" * (SALIDA_MAX_BYTES + 1))
    assert payload_resultado(ov, NODO, "x" * SALIDA_MAX_BYTES)


def test_el_nodo_miente_hc1_lo_detecta_con_su_verificador_y_nunca_incorpora(esc: Escena) -> None:
    ident, _, _ = esc.ciclo_hasta_resultado()
    mentira = _resultado_a_medida(
        esc.m.nodo, **_base_resultado(esc, ident, salida="0" * 64)
    )  # firma válida, dato falso
    esc.hc1.recibir_resultado(mentira, NODO)
    assert esc.hc1.validar(ident) is False
    ej = esc.hc1.ejecucion(ident)
    assert ej is not None and ej.estado is Estado.VERIFICACION_FALLIDA and not ej.completada
    assert _rechazo(esc.hc1.incorporar, ident, esc.registro) is Motivo.EJECUCION_NO_EN_CURSO
    assert esc.registro == []


def test_no_se_incorpora_lo_no_validado(esc: Escena) -> None:
    ident, _, res = esc.ciclo_hasta_resultado()
    esc.hc1.recibir_resultado(res, NODO)
    assert _rechazo(esc.hc1.incorporar, ident, esc.registro) is Motivo.EJECUCION_NO_EN_CURSO
    assert esc.registro == []


def test_si_el_registro_falla_la_ejecucion_sigue_validada_y_se_repite_n6(esc: Escena) -> None:
    ident, _, res = esc.ciclo_hasta_resultado()
    esc.hc1.recibir_resultado(res, NODO)
    esc.hc1.validar(ident)

    class Cae(RegistroSintetico):
        def __call__(self, hecho: dict[str, Any]) -> None:
            raise OSError("disco lleno")

    cae = Cae()

    with pytest.raises(OSError):
        esc.hc1.incorporar(ident, cae)
    ej = esc.hc1.ejecucion(ident)
    assert ej is not None and ej.estado is Estado.INCORPORANDO and not ej.completada  # C1: explícito, no «validado»
    esc.hc1.incorporar(ident, esc.registro)  # reintento tras la recuperación
    assert ej.completada


def test_acuse_valido_acepta_pero_no_prorroga_el_techo_ni_completa(esc: Escena) -> None:
    ident, acuse, _ = esc.ciclo_hasta_resultado()
    ej = esc.hc1.ejecucion(ident)
    assert ej is not None
    techo = ej.vence_en
    esc.m.reloj.t += 30
    esc.hc1.recibir_acuse(acuse, NODO)
    assert ej.estado is Estado.ACEPTADA and ej.vence_en == techo and not ej.completada


def test_acuse_duplicado_alterado_o_con_firma_de_resultado_se_rechaza(esc: Escena) -> None:
    ident, acuse, res = esc.ciclo_hasta_resultado()
    esc.hc1.recibir_acuse(acuse, NODO)
    assert _rechazo(esc.hc1.recibir_acuse, acuse, NODO) is Motivo.ACUSE_DUPLICADO
    # un sobre de RESULTADO no sirve como acuse (separación de dominio)
    assert _rechazo(esc.hc1.recibir_acuse, res, NODO) is Motivo.FIRMA_INVALIDA


def test_acuse_con_hash_equivocado_o_nodo_ajeno_se_rechaza(esc: Escena) -> None:
    ident, _, _ = esc.ciclo_hasta_resultado()
    ej = esc.hc1.ejecucion(ident)
    assert ej is not None
    base = {
        "v": 1,
        "alg": "ed25519",
        "tarea": ej.tarea,
        "intento": 1,
        "id_nodo": NODO,
        "id_ejecucion": ident,
        "hash_tarea": "e" * 64,
        "recibida_en": 1.0,
    }
    malo = esc.m.nodo.firmar(DOMINIO_ACUSE, bytes_canonicos(base))
    assert _rechazo(esc.hc1.recibir_acuse, malo, NODO) is Motivo.HASH_NO_CORRESPONDE
    de_otro = esc.m.otro_nodo.firmar(DOMINIO_ACUSE, bytes_canonicos({**base, "id_nodo": OTRO_NODO}))
    assert _rechazo(esc.hc1.recibir_acuse, de_otro, OTRO_NODO) is Motivo.NODO_AJENO


def test_desconexion_sin_acuse_es_interrumpida_reintentable_y_con_acuse_es_ambigua(esc: Escena) -> None:
    ident, acuse, res = esc.ciclo_hasta_resultado(tarea="t-a")
    esc.hc1.marcar_desconexion(NODO)
    assert esc.hc1.ejecucion(ident).estado is Estado.INTERRUMPIDA  # type: ignore[union-attr]

    ident2, acuse2, res2 = esc.ciclo_hasta_resultado(tarea="t-b")
    esc.hc1.recibir_acuse(acuse2, NODO)
    esc.hc1.marcar_desconexion(NODO)
    assert esc.hc1.ejecucion(ident2).estado is Estado.AMBIGUO  # type: ignore[union-attr]
    # un resultado tardío de una ejecución ambigua NO se incorpora
    assert _rechazo(esc.hc1.recibir_resultado, res2, NODO) is Motivo.EJECUCION_NO_EN_CURSO


def test_el_techo_de_duracion_interrumpe_lo_que_sigue_en_curso(esc: Escena) -> None:
    ident, acuse, _ = esc.ciclo_hasta_resultado()
    esc.hc1.recibir_acuse(acuse, NODO)
    assert esc.hc1.vencer() == []  # control: aún dentro del techo
    esc.m.reloj.t += 61
    assert [e.id_ejecucion for e in esc.hc1.vencer()] == [ident]
    assert esc.hc1.ejecucion(ident).estado is Estado.AMBIGUO  # type: ignore[union-attr]


def test_un_segundo_intento_exige_que_el_anterior_no_este_en_curso_y_que_el_numero_crezca(esc: Escena) -> None:
    esc.emitir(intento=1)
    assert _rechazo(esc.emitir) is Motivo.EJECUCION_NO_EN_CURSO  # intento 1 repetido con el anterior vivo
    esc.hc1.marcar_desconexion(NODO)
    assert _rechazo(lambda: esc.emitir(intento=1)) is Motivo.EJECUCION_NO_EN_CURSO  # no creciente
    esc.emitir(intento=2)


def test_cada_motivo_de_rechazo_de_resultados_queda_contado(esc: Escena) -> None:
    _, _, res = esc.ciclo_hasta_resultado()
    esc.hc1.recibir_resultado(res, NODO)
    with pytest.raises(RechazoOrden):
        esc.hc1.recibir_resultado(res, NODO)
    assert esc.hc1.rechazos == [Motivo.RESULTADO_DUPLICADO]
