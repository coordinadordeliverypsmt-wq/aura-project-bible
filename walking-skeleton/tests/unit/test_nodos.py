"""Pruebas de `core/nodos.py` (DP-NODO-01 §4.2, §4.3, §4.4): latido, registro, estado y capacidades."""

from __future__ import annotations

import json
import math

import pytest

from aura_skeleton.core import nodos
from aura_skeleton.core.capacidades import Estado
from aura_skeleton.core.nodos import (
    DEGRADED,
    OFFLINE,
    ONLINE,
    UNKNOWN,
    Latido,
    LatidoInvalido,
    RegistroNodos,
    capacidades_de,
    construir_latido,
    estado_nodo,
    nodo_id_de_subject,
    subject_de,
    validar_latido,
)

NODO = "a" * 32
NODO_B = "b" * 32
ARR1 = "1" * 32
ARR2 = "2" * 32


def _datos(**cambios: object) -> dict[str, object]:
    base: dict[str, object] = {
        "esquema": "nodo.latido/1",
        "nodo_id": NODO,
        "nombre": "portatil",
        "secuencia": 0,
        "arranque": ARR1,
        "intervalo_s": 10.0,
        "recursos": {"ram_mb": 986.0, "nucleos": 2.0},
        "omitidas": [],
        "agente": "0.1",
    }
    base.update(cambios)
    return base


def _latido(
    nodo_id: str = NODO,
    secuencia: int = 0,
    arranque: str = ARR1,
    intervalo_s: float = 10.0,
    recursos: dict[str, float] | None = None,
    omitidas: tuple[str, ...] = (),
) -> Latido:
    return validar_latido(
        construir_latido(
            nodo_id,
            "n",
            secuencia,
            arranque,
            intervalo_s,
            {"ram_mb": 986.0, "nucleos": 2.0} if recursos is None else recursos,
            omitidas,
            "0.1",
        )
    )


# --- constantes -------------------------------------------------------------------------------------------


def test_constantes_del_contrato() -> None:
    assert (ONLINE, DEGRADED, OFFLINE, UNKNOWN) == ("ONLINE", "DEGRADED", "OFFLINE", "UNKNOWN")
    assert nodos.ESQUEMA_LATIDO == "nodo.latido/1"
    assert nodos.TOLERANCIA_INTERVALOS == 3
    assert nodos.METRICAS_MINIMAS == ("ram_mb", "nucleos")
    assert nodos.PREFIJO_SUBJECT == "nodo.latido"


# --- validación -------------------------------------------------------------------------------------------


def test_latido_valido_round_trip() -> None:
    latido = validar_latido(_datos(omitidas=["gpu_render"], secuencia=7))
    assert latido == Latido(
        esquema="nodo.latido/1",
        nodo_id=NODO,
        nombre="portatil",
        secuencia=7,
        arranque=ARR1,
        intervalo_s=10.0,
        recursos={"ram_mb": 986.0, "nucleos": 2.0},
        omitidas=("gpu_render",),
        agente="0.1",
    )
    assert isinstance(latido.omitidas, tuple)


def test_construir_latido_es_json_y_vuelve_a_validarse() -> None:
    dato = construir_latido(NODO, "x", 3, ARR1, 5, {"ram_mb": 1.0}, ("a_b",), "v1")
    assert isinstance(dato["omitidas"], list)
    assert dato["esquema"] == "nodo.latido/1"
    ida_y_vuelta = validar_latido(json.loads(json.dumps(dato)))
    assert ida_y_vuelta.secuencia == 3
    assert ida_y_vuelta.omitidas == ("a_b",)


def test_construir_latido_invalido_lanza() -> None:
    with pytest.raises(LatidoInvalido):
        construir_latido("no-es-id", "x", 0, ARR1, 10.0, {}, (), "v")


@pytest.mark.parametrize("campo", list(_datos()))
def test_campo_faltante_se_rechaza(campo: str) -> None:
    datos = _datos()
    del datos[campo]
    with pytest.raises(LatidoInvalido):
        validar_latido(datos)


def test_campo_sobrante_se_rechaza() -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido({**_datos(), "extra": 1})


@pytest.mark.parametrize("basura", [None, [], "texto", 5, ()])
def test_no_dict_se_rechaza(basura: object) -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(basura)


def test_esquema_distinto_se_rechaza() -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(esquema="nodo.latido/2"))


@pytest.mark.parametrize(
    "valor",
    ["A" * 32, "a" * 31, "a" * 33, "g" * 32, "a" * 31 + "\n", "", 5, None, " " + "a" * 31],
)
def test_nodo_id_y_arranque_siguen_la_regex(valor: object) -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(nodo_id=valor))
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(arranque=valor))


@pytest.mark.parametrize("nombre", ["", "x" * 65, "a\nb", "a\x00b", 5, None])
def test_nombre_invalido(nombre: object) -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(nombre=nombre))


def test_nombre_limites_validos() -> None:
    assert validar_latido(_datos(nombre="x")).nombre == "x"
    assert validar_latido(_datos(nombre="ñ" * 64)).nombre == "ñ" * 64


def test_agente_limite_32() -> None:
    assert validar_latido(_datos(agente="v" * 32)).agente == "v" * 32
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(agente="v" * 33))
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(agente=3))


@pytest.mark.parametrize("valor", [-1, 1.0, "1", None, True, False])
def test_secuencia_estricta(valor: object) -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(secuencia=valor))


def test_secuencia_cero_valida() -> None:
    assert validar_latido(_datos(secuencia=0)).secuencia == 0


@pytest.mark.parametrize("valor", [1, 1.0, 3600, 3600.0])
def test_intervalo_limites_validos(valor: float) -> None:
    assert validar_latido(_datos(intervalo_s=valor)).intervalo_s == valor


@pytest.mark.parametrize("valor", [0.99, 3600.1, 0, -5, True, "10", None, math.nan, math.inf])
def test_intervalo_fuera_de_rango_o_tipo(valor: object) -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(intervalo_s=valor))


def test_recursos_limite_64_claves() -> None:
    ok = {f"m{i}": 1.0 for i in range(64)}
    assert len(validar_latido(_datos(recursos=ok)).recursos) == 64
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(recursos={f"m{i}": 1.0 for i in range(65)}))


@pytest.mark.parametrize("clave", ["Ram", "a-b", "", "x" * 41, "a b", 5])
def test_recursos_clave_invalida(clave: object) -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(recursos={clave: 1.0}))


def test_recursos_clave_de_40_valida() -> None:
    assert "x" * 40 in validar_latido(_datos(recursos={"x" * 40: 1})).recursos


@pytest.mark.parametrize("valor", [math.nan, math.inf, -math.inf, True, False, "1", None, [1]])
def test_recursos_valor_invalido(valor: object) -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(recursos={"ram_mb": valor}))


def test_recursos_no_dict() -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(recursos=[("ram_mb", 1.0)]))


@pytest.mark.parametrize("omitidas", ["gpu", ("gpu",), None, [5], ["GPU"], ["a-b"], [""], ["x" * 41]])
def test_omitidas_invalidas(omitidas: object) -> None:
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(omitidas=omitidas))


def test_omitidas_limite_64() -> None:
    assert len(validar_latido(_datos(omitidas=[f"m{i}" for i in range(64)])).omitidas) == 64
    with pytest.raises(LatidoInvalido):
        validar_latido(_datos(omitidas=[f"m{i}" for i in range(65)]))


def test_mensajes_de_error_no_filtran_el_valor_recibido() -> None:
    secreto = "SECRETO-<script>-123"
    casos = [
        _datos(nombre=secreto + "\n"),
        _datos(nodo_id=secreto),
        _datos(agente=secreto * 5),
        _datos(recursos={secreto: 1.0}),
        _datos(omitidas=[secreto]),
        _datos(esquema=secreto),
        {**_datos(), secreto: 1},
    ]
    for caso in casos:
        with pytest.raises(LatidoInvalido) as exc:
            validar_latido(caso)
        assert "SECRETO" not in str(exc.value)
        assert "script" not in str(exc.value)
    with pytest.raises(LatidoInvalido, match="intervalo_s"):
        validar_latido(_datos(intervalo_s=9999))


# --- subject ----------------------------------------------------------------------------------------------


def test_subject_ida_y_vuelta() -> None:
    assert subject_de(NODO) == f"nodo.latido.{NODO}"
    assert nodo_id_de_subject(subject_de(NODO)) == NODO


@pytest.mark.parametrize(
    "subject",
    [
        "",
        "nodo.latido",
        "nodo.latido.",
        f"nodo.latido.{'A' * 32}",
        f"otro.{NODO}",
        f"nodo.latido.{NODO}.x",
        f"nodo.latido.{NODO}\n",
    ],
)
def test_nodo_id_de_subject_invalido_devuelve_none(subject: str) -> None:
    assert nodo_id_de_subject(subject) is None


# --- registro ---------------------------------------------------------------------------------------------


def test_registro_transiciones() -> None:
    reg = RegistroNodos()
    assert reg.registrar(_latido(secuencia=0), 100.0) == "nuevo"
    assert reg.registrar(_latido(secuencia=1), 110.0) == "latido"
    assert reg.registrar(_latido(secuencia=2, arranque=ARR2), 120.0) == "reinicio"
    assert reg.registrar(_latido(secuencia=3, arranque=ARR2), 130.0) == "latido"
    r = reg.obtener(NODO)
    assert r is not None
    assert (r.reinicios, r.primer_contacto, r.recibido_en) == (1, 100.0, 130.0)


def test_nuevo_empieza_sin_reinicios_y_primer_contacto_es_ahora() -> None:
    reg = RegistroNodos()
    reg.registrar(_latido(), 50.0)
    r = reg.obtener(NODO)
    assert r is not None
    assert (r.reinicios, r.primer_contacto, r.recibido_en) == (0, 50.0, 50.0)


def test_reinicio_con_secuencia_menor_no_es_descartado() -> None:
    reg = RegistroNodos()
    reg.registrar(_latido(secuencia=50), 100.0)
    assert reg.registrar(_latido(secuencia=0, arranque=ARR2), 110.0) == "reinicio"
    r = reg.obtener(NODO)
    assert r is not None
    assert r.latido.secuencia == 0
    assert r.recibido_en == 110.0


@pytest.mark.parametrize("secuencia", [5, 4, 0])
def test_descartado_no_refresca_recibido_en(secuencia: int) -> None:
    reg = RegistroNodos()
    reg.registrar(_latido(secuencia=5), 100.0)
    assert reg.registrar(_latido(secuencia=secuencia), 999.0) == "descartado"
    r = reg.obtener(NODO)
    assert r is not None
    assert r.recibido_en == 100.0
    assert r.latido.secuencia == 5
    # y por tanto un latido retrasado no resucita al nodo
    assert estado_nodo(r, 999.0, True)[0] == OFFLINE


def test_secuencia_siguiente_si_se_acepta() -> None:
    reg = RegistroNodos()
    reg.registrar(_latido(secuencia=5), 100.0)
    assert reg.registrar(_latido(secuencia=6), 105.0) == "latido"


def test_nodos_independientes_y_ordenados() -> None:
    reg = RegistroNodos()
    reg.registrar(_latido(nodo_id=NODO_B), 1.0)
    reg.registrar(_latido(nodo_id=NODO), 2.0)
    assert [r.latido.nodo_id for r in reg.nodos()] == [NODO, NODO_B]
    assert reg.obtener("c" * 32) is None
    assert isinstance(reg.nodos(), tuple)


def test_persistencia_round_trip_exacto() -> None:
    reg = RegistroNodos()
    reg.registrar(_latido(secuencia=0, omitidas=("gpu",)), 100.0)
    reg.registrar(_latido(secuencia=1, arranque=ARR2), 110.5)
    reg.registrar(_latido(nodo_id=NODO_B), 120.0)
    volcado = json.loads(json.dumps(reg.a_dict()))
    reg2 = RegistroNodos.desde_dict(volcado)
    assert reg2.nodos() == reg.nodos()
    assert reg2.a_dict() == reg.a_dict()
    # el registro restaurado sigue aplicando las reglas de transición
    assert reg2.registrar(_latido(secuencia=1, arranque=ARR2), 200.0) == "descartado"


def test_registro_vacio_round_trip() -> None:
    assert RegistroNodos.desde_dict(RegistroNodos().a_dict()).nodos() == ()


def test_desde_dict_con_latido_corrupto_lanza() -> None:
    reg = RegistroNodos()
    reg.registrar(_latido(), 100.0)
    volcado = json.loads(json.dumps(reg.a_dict()))
    entrada = next(iter(volcado["nodos"].values()))
    entrada["latido"]["intervalo_s"] = 0
    with pytest.raises(LatidoInvalido):
        RegistroNodos.desde_dict(volcado)


@pytest.mark.parametrize("basura", [None, [], {}, {"nodos": []}, {"nodos": {NODO: 5}}, {"nodos": {NODO: {}}}])
def test_desde_dict_con_estructura_corrupta_lanza(basura: object) -> None:
    with pytest.raises(LatidoInvalido):
        RegistroNodos.desde_dict(basura)  # type: ignore[arg-type]


def test_desde_dict_con_clave_distinta_del_nodo_id_lanza() -> None:
    reg = RegistroNodos()
    reg.registrar(_latido(), 100.0)
    volcado = json.loads(json.dumps(reg.a_dict()))
    volcado["nodos"] = {NODO_B: volcado["nodos"][NODO]}
    with pytest.raises(LatidoInvalido):
        RegistroNodos.desde_dict(volcado)


# --- estado -----------------------------------------------------------------------------------------------


def _registro(recibido_en: float = 100.0, **kw: object) -> nodos.RegistroNodo:
    reg = RegistroNodos()
    reg.registrar(_latido(**kw), recibido_en)  # type: ignore[arg-type]
    r = reg.obtener(NODO)
    assert r is not None
    return r


def test_receptor_muerto_es_unknown_aunque_el_latido_sea_fresco() -> None:
    estado, motivo = estado_nodo(_registro(100.0), 100.0, receptor_vivo=False)
    assert estado == UNKNOWN
    assert motivo == "HC-1 no está escuchando"


def test_receptor_muerto_y_sin_registro_es_unknown_por_receptor() -> None:
    assert estado_nodo(None, 0.0, False) == (UNKNOWN, "HC-1 no está escuchando")


def test_sin_registro_es_unknown() -> None:
    estado, motivo = estado_nodo(None, 0.0, True)
    assert estado == UNKNOWN
    assert "ningún latido" in motivo


def test_frontera_exactamente_tres_intervalos_sigue_online() -> None:
    assert estado_nodo(_registro(100.0), 130.0, True)[0] == ONLINE


def test_mas_de_tres_intervalos_es_offline() -> None:
    estado, motivo = estado_nodo(_registro(100.0), 130.0 + 1e-6, True)
    assert estado == OFFLINE
    assert "conexión antigua" in motivo


def test_offline_tiene_precedencia_sobre_degraded() -> None:
    r = _registro(100.0, omitidas=("gpu",))
    assert estado_nodo(r, 131.0, True)[0] == OFFLINE


def test_la_frontera_usa_el_intervalo_del_nodo() -> None:
    r = _registro(100.0, intervalo_s=2.0)
    assert estado_nodo(r, 106.0, True)[0] == ONLINE
    assert estado_nodo(r, 106.5, True)[0] == OFFLINE


def test_degraded_por_omitidas() -> None:
    estado, motivo = estado_nodo(_registro(omitidas=("gpu_render",)), 100.0, True)
    assert estado == DEGRADED
    assert "gpu_render" in motivo


def test_degraded_por_falta_de_ram() -> None:
    estado, motivo = estado_nodo(_registro(recursos={"nucleos": 2.0}), 100.0, True)
    assert estado == DEGRADED
    assert "ram_mb" in motivo


def test_degraded_por_falta_de_nucleos() -> None:
    estado, motivo = estado_nodo(_registro(recursos={"ram_mb": 1000.0}), 100.0, True)
    assert estado == DEGRADED
    assert "nucleos" in motivo


def test_online_con_todo_en_orden() -> None:
    assert estado_nodo(_registro(), 100.0, True)[0] == ONLINE


def test_edad_negativa_se_trata_como_cero() -> None:
    assert estado_nodo(_registro(500.0), 100.0, True)[0] == ONLINE
    assert estado_nodo(_registro(500.0, omitidas=("x",)), -1e9, True)[0] == DEGRADED


# --- capacidades ------------------------------------------------------------------------------------------


def test_capacidades_con_poca_ram_degrada_memoria() -> None:
    plan = capacidades_de({"ram_mb": 986.0, "nucleos": 2.0})
    decision = plan.decision("memoria")
    assert decision is not None
    assert decision.estado is Estado.DEGRADADA
    assert plan.degradadas == ("memoria",)
    assert plan.motivo("memoria") == "criterio de degradacion cumplido: opera en modo reducido"


def test_capacidades_con_mucha_ram_activa_memoria() -> None:
    plan = capacidades_de({"ram_mb": 16000.0, "nucleos": 8.0})
    assert plan.activas == ("memoria",)
    assert plan.motivo("memoria") == "criterio de promocion cumplido"


def test_capacidades_umbral_exacto_de_8000() -> None:
    assert capacidades_de({"ram_mb": 8000.0}).activas == ("memoria",)
    assert capacidades_de({"ram_mb": 7999.0}).degradadas == ("memoria",)


def test_capacidades_son_las_del_catalogo_y_no_hay_nada_nuevo() -> None:
    from aura_skeleton.core.catalogo_capacidades import catalogo

    plan = capacidades_de({"ram_mb": 986.0})
    assert tuple(d.nombre for d in plan.decisiones) == tuple(sorted(c.nombre for c in catalogo()))


def test_capacidades_no_muta_los_recursos() -> None:
    recursos = {"ram_mb": 1.0}
    capacidades_de(recursos)
    assert recursos == {"ram_mb": 1.0}


def test_intervalo_declarado_enorme_no_alarga_la_tolerancia() -> None:
    r = _registro(100.0, intervalo_s=3600.0)
    assert estado_nodo(r, 100.0 + 180.0, True)[0] == ONLINE  # 3 x 60 s: frontera
    estado, motivo = estado_nodo(r, 100.0 + 181.0, True)
    assert estado == OFFLINE
    assert "conexión antigua" in motivo


def test_intervalo_menor_al_maximo_se_respeta() -> None:
    r = _registro(100.0, intervalo_s=10.0)
    assert estado_nodo(r, 130.0, True)[0] == ONLINE
    assert estado_nodo(r, 131.0, True)[0] == OFFLINE


def test_constante_intervalo_max_evaluacion() -> None:
    assert nodos.INTERVALO_MAX_EVALUACION_S == 60.0
