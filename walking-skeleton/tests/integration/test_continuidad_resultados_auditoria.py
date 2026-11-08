"""Correcciones tras la auditoria independiente del punto D (arquitectura + seguridad, 2026-11-06).

Cada prueba lleva su caso de control. Numeracion = la del encargo del orquestador.
"""

from __future__ import annotations

import inspect
import json
import os
import stat
import uuid

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.core import orchestrator as orq_mod
from aura_skeleton.core import resultado_accion as ra
from aura_skeleton.core.orchestrator import Orchestrator, _redactar_resultado_de_orden, describir_desenlace
from aura_skeleton.modules.memory import PersistentMemory
from tests.integration.test_continuidad_resultados import (
    UID,
    _anexar_a_mano,
    _apagar_la_tele,
    _eventos,
    _reiniciar,
    _texto,
)
from tests.integration.test_voz_accion_opcion_c import _HA, SALA, _aura

AHORA = 1_762_424_137.0


def _valido(**campos) -> dict:
    registro, motivo = ra.construir(
        "apagar_dispositivo",
        {
            "estado": "ejecutada",
            "resultado": {"device": SALA, "estado_antes": "on", "estado_despues": "off", "verificado": True},
        },
        "T-A",
        AHORA,
    )
    assert registro is not None, motivo
    return {**registro, **campos}


# ----------------------------------------------------------------- 1 y 4: olvido honesto y PARADA --


@pytest.mark.asyncio
@pytest.mark.parametrize("frase", sorted(ra._FORMAS_OLVIDO_DE_ACCIONES))
async def test_con_PARADA_ninguna_forma_del_olvido_de_acciones_modifica_nada_y_AURA_lo_dice(tmp_path, frase):
    sis = _aura(tmp_path, _HA())[0]
    await _apagar_la_tele(sis)
    assert len(ra.leer(sis.memoria, UID)[0]) == 1, "control: hay un registro"
    open(os.path.join(str(tmp_path), "KILL"), "w").close()

    dicho = await _texto(sis, frase)

    assert "detenido" in dicho, dicho
    assert len(ra.leer(sis.memoria, UID)[0]) == 1, f"con PARADA «{frase}» modifico el registro"
    assert "No tenía ningún registro" not in dicho and not dicho.startswith("Hecho")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resultado", [{"estado": "error", "motivo": "fallo"}, {"estado": "detenida", "motivo": "permiso"}]
)
async def test_si_el_motor_no_ejecuta_el_olvido_AURA_no_dice_que_no_habia_nada(tmp_path, resultado):
    sis = _aura(tmp_path, _HA())[0]
    await _apagar_la_tele(sis)
    real = sis.motor.ejecutar

    async def falla(accion, *a, **k):
        if accion == "olvidar_informacion_usuario":
            return resultado
        return await real(accion, *a, **k)

    sis.motor.ejecutar = falla

    dicho = await _texto(sis, "borra el historial de acciones")

    assert "No tenía ningún registro" not in dicho and not dicho.startswith("Hecho"), dicho
    assert "no he podido" in dicho.lower() and "sigue" in dicho.lower()
    assert len(ra.leer(sis.memoria, UID)[0]) == 1

    # CONTROL: sin nada que olvidar y con el motor sano, SI es verdad que no habia nada.
    sana = _aura(tmp_path / "otro", _HA())[0]
    assert "No tenía ningún registro" in await _texto(sana, "borra el historial de acciones")


@pytest.mark.asyncio
async def test_el_olvido_no_promete_lo_que_no_hace_el_borrado_fisico_no_esta_implementado(tmp_path):
    sis = _aura(tmp_path, _HA())[0]
    await _apagar_la_tele(sis)

    dicho = await _texto(sis, "olvida lo que hiciste")

    assert "borrado físico" in dicho and "no está implementado" in dicho, dicho
    assert "ya no conservo registro" not in dicho.lower()
    assert "dejo de usar" in dicho.lower() and "mostrar" in dicho.lower()
    assert "SALA" not in dicho and ra.leer(sis.memoria, UID)[0] == []


# ------------------------------------------------------------------- 2: evidencia y modo registro --

_DET_HOGAR = {"device": SALA, "estado_antes": "on", "estado_despues": "off", "verificado": False, "ya_en_estado": False}
#  (id, capacidad, detalle, evidencia esperada, marca en vivo, marca en registro)
_ESCENARIOS = [
    (
        "verificada",
        "apagar_dispositivo",
        {**_DET_HOGAR, "status": "ok", "verificado": True, "evidencia": "estado_ha_tras_orden"},
        "verificada",
        "Listo",
        "Constaba que Home Assistant veía",
    ),
    (
        "asumida",
        "apagar_dispositivo",
        {**_DET_HOGAR, "status": "sin_efecto", "evidencia": "estado_asumido_por_ha"},
        "asumida",
        "estado asumido",
        "estado asumido",
    ),
    (
        "ya_en_estado",
        "apagar_dispositivo",
        {
            **_DET_HOGAR,
            "status": "sin_efecto",
            "ya_en_estado": True,
            "estado_antes": "off",
            "evidencia": "estado_ha_tras_orden",
        },
        "ya_en_estado",
        "ya veía",
        "ya veía",
    ),
    (
        "simulada",
        "apagar_dispositivo",
        {"device": SALA, "verificado": False},
        "simulada",
        "modo simulado",
        "modo simulado",
    ),
    (
        "no_verificada",
        "apagar_dispositivo",
        {**_DET_HOGAR, "status": "sin_efecto", "estado_despues": "on", "evidencia": "estado_ha_tras_orden"},
        "ninguna",
        "No lo doy por hecho",
        "No lo doy por hecho",
    ),
    (
        "no_leida",
        "apagar_dispositivo",
        {**_DET_HOGAR, "status": "sin_efecto", "estado_despues": "?", "evidencia": "ninguna"},
        "no_leida",
        "no pude leer",
        "no pude leer",
    ),
    (
        "vol_verificada",
        "subir_volumen",
        {
            "device": SALA,
            "status": "ok",
            "verificado": True,
            "ya_en_estado": False,
            "atributo": "volume_level",
            "valor_antes": 0.25,
            "valor_despues": 0.4,
            "evidencia": "estado_ha_tras_orden",
        },
        "verificada",
        "lo he comprobado",
        "constaba comprobado",
    ),
    (
        "vol_asumida",
        "subir_volumen",
        {
            "device": SALA,
            "status": "sin_efecto",
            "verificado": False,
            "ya_en_estado": False,
            "atributo": "volume_level",
            "valor_antes": 0.25,
            "valor_despues": 0.4,
            "evidencia": "estado_asumido_por_ha",
        },
        "asumida",
        "estado asumido",
        "estado asumido",
    ),
    (
        "silencio_ya",
        "silenciar",
        {
            "device": SALA,
            "status": "sin_efecto",
            "verificado": False,
            "ya_en_estado": True,
            "atributo": "is_volume_muted",
            "valor_antes": True,
            "valor_despues": True,
            "evidencia": "estado_ha_tras_orden",
        },
        "ya_en_estado",
        "ya veía",
        "ya veía",
    ),
    (
        "vol_simulada",
        "subir_volumen",
        {"device": SALA, "verificado": False, "atributo": "volume_level"},
        "simulada",
        "modo simulado",
        "modo simulado",
    ),
]
_PRESENTE = ("lo he comprobado", "Home Assistant ve ", "sigue viendo", "ahora la ve", "ahora lo ve", "Listo:")


@pytest.mark.parametrize(
    "nombre,capacidad,detalle,evidencia,marca_vivo,marca_registro", _ESCENARIOS, ids=[e[0] for e in _ESCENARIOS]
)
def test_la_redaccion_recuperada_de_hogar_va_a_la_MISMA_rama_que_la_en_vivo(
    nombre, capacidad, detalle, evidencia, marca_vivo, marca_registro
):
    res = {"estado": "ejecutada", "resultado": detalle}
    en_vivo = _redactar_resultado_de_orden(capacidad, res)
    registro, motivo = ra.construir(capacidad, res, "T-EQ", AHORA)
    assert registro is not None, motivo
    recuperado = describir_desenlace(
        capacidad, registro["desenlace"], detalle_hogar=ra.detalle_reconstruido(registro), modo="registro"
    )

    assert registro["evidencia"] == evidencia
    assert marca_vivo in en_vivo, f"control: la marca de la rama en vivo no esta: {en_vivo!r}"
    assert marca_registro in recuperado, f"{nombre}: otra rama. vivo={en_vivo!r} registro={recuperado!r}"
    for frase in _PRESENTE:
        assert frase not in recuperado, f"el modo registro usa una frase de verificacion en presente: {frase!r}"


def test_evidencia_es_un_campo_cerrado_validado_al_escribir_y_al_leer():
    assert ra.validar(_valido(evidencia="verificada"))
    for malo in ("comprobada", "", None, 1, "verificada\n"):
        assert not ra.validar(_valido(evidencia=malo))
    assert set(ra.EVIDENCIAS) == {"verificada", "asumida", "ya_en_estado", "simulada", "no_leida", "ninguna"}
    assert (
        "evidencia" in ra.CAMPOS
        and ra.validar(ra._peor_caso())
        and len(ra.a_contenido(ra._peor_caso())) == ra.LONGITUD_MAXIMA
    )
    contenido = ra.a_contenido(_valido())
    assert ra.desde_contenido(contenido) is not None
    assert ra.desde_contenido(contenido.replace("evidencia=verificada", "evidencia=comprobada")) is None


# -------------------------------------------------------------------------------- 3: permisos 0600 --


def _modo(ruta) -> int:
    return stat.S_IMODE(os.stat(ruta).st_mode)


@pytest.mark.asyncio
async def test_memoria_json_se_crea_con_0600_aunque_el_umask_sea_0(tmp_path):
    anterior = os.umask(0)
    try:
        memoria = PersistentMemory(str(tmp_path / "m.json"))
        await memoria.write("u", "episodica", "usuario dijo: hola", {})
    finally:
        os.umask(anterior)
    assert _modo(tmp_path / "m.json") == 0o600


def test_un_memoria_json_preexistente_con_0644_pasa_a_0600_al_construir(tmp_path):
    ruta = tmp_path / "m.json"
    ruta.write_text("", encoding="utf-8")
    os.chmod(ruta, 0o644)
    assert _modo(ruta) == 0o644, "control: el fichero parte de 0644"

    PersistentMemory(str(ruta))

    assert _modo(ruta) == 0o600
    PersistentMemory(str(ruta))  # idempotente
    assert _modo(ruta) == 0o600


@pytest.mark.asyncio
async def test_backup_restore_y_persist_dejan_el_fichero_y_las_copias_en_0600(tmp_path):
    anterior = os.umask(0)
    try:
        memoria = PersistentMemory(str(tmp_path / "m.json"))
        await memoria.write("u", "episodica", "usuario dijo: hola", {})
        nombre = memoria.backup()
        assert memoria.restore(nombre)
    finally:
        os.umask(anterior)

    assert _modo(tmp_path / "m.json") == 0o600
    copias = [p for p in os.listdir(memoria._bdir)]
    assert copias, "control: hay copias"
    for c in copias:
        assert _modo(os.path.join(memoria._bdir, c)) == 0o600, c
    assert not os.path.exists(str(tmp_path / "m.json") + ".tmp")


# ------------------------------------------------- 5 y 6: rechazos auditados, catalogo, ts, conflicto --


@pytest.mark.asyncio
async def test_ver_y_exportar_auditan_los_registros_rechazados_como_la_recuperacion(tmp_path):
    ha = _HA()
    await _apagar_la_tele(_aura(tmp_path, ha)[0])
    _anexar_a_mano(tmp_path, "texto libre que no es un registro")
    nuevo = _reiniciar(tmp_path, ha)

    marca = len(obs.audit_records())
    await nuevo.modelo_usuario.ver_acciones(UID)
    assert len(_eventos(marca, "resultado.rechazado")) == 1
    marca = len(obs.audit_records())
    await nuevo.modelo_usuario.exportar(UID)
    assert len(_eventos(marca, "resultado.rechazado")) == 1
    # CONTROL: otra persona no tiene nada rechazado.
    marca = len(obs.audit_records())
    await nuevo.modelo_usuario.ver_acciones("otra")
    assert _eventos(marca, "resultado.rechazado") == []


def test_la_capacidad_se_valida_contra_el_catalogo_real_y_la_entidad_es_solo_de_hogar():
    assert ra.validar(_valido(capacidad="apagar_dispositivo"))
    assert ra.validar(
        _valido(capacidad="ejecutar_pruebas", entidad=None, antes=None, despues=None, evidencia="ninguna")
    )
    assert not ra.validar(_valido(capacidad="capacidad_inventada", entidad=None))
    assert not ra.validar(_valido(capacidad="auditar_garantias"))  # lleva entidad: no es de hogar
    registro, motivo = ra.construir("capacidad_inventada", {"estado": "ejecutada", "resultado": {}}, "T-X", AHORA)
    assert registro is None and motivo == ra.MOTIVO_INVALIDO


class _Memoria:
    def __init__(self, items):
        self._items = items


def _item(registro, uid="u"):
    return {"user_id": uid, "kind": ra.KIND, "content": ra.a_contenido(registro), "provenance": {}}


def test_un_registro_del_futuro_se_descarta_y_cuenta_como_rechazado():
    ahora = AHORA
    pasado = _valido(trace_id="PASADO", ts=int(ahora) // 60 * 60)
    limite = _valido(trace_id="LIMITE", ts=(int(ahora) // 60 + 1) * 60)  # dentro del margen del redondeo
    futuro = _valido(trace_id="FUTURO", ts=(int(ahora) // 60 + 3) * 60)

    registros, rechazados = ra.leer(_Memoria([_item(pasado), _item(limite), _item(futuro)]), "u", ahora=ahora)

    assert [r["trace_id"] for r in registros] == ["PASADO", "LIMITE"] and rechazados == 1


def test_dos_registros_con_el_mismo_trace_id_y_contenido_distinto_se_descartan_todos():
    a = _valido(trace_id="MISMO", ts=60)
    b = _valido(trace_id="MISMO", ts=120, despues="on")
    sano = _valido(trace_id="SANO", ts=180)

    registros, rechazados = ra.leer(_Memoria([_item(a), _item(b), _item(sano)]), "u", ahora=AHORA)

    assert [r["trace_id"] for r in registros] == ["SANO"] and rechazados == 2
    # CONTROL: el MISMO contenido repetido (doble escritura) no es conflicto: se conserva una vez.
    registros, rechazados = ra.leer(_Memoria([_item(a), _item(a)]), "u", ahora=AHORA)
    assert [r["trace_id"] for r in registros] == ["MISMO"] and rechazados == 0


# ------------------------------------------------------------------------ 7: una sola clasificacion --


def test_la_clasificacion_del_desenlace_es_una_sola_y_en_el_mismo_orden_que_la_redaccion_en_vivo():
    res = {"estado": "ejecutada", "resultado": {"ok": False, "resumen": "5 rotas", "status": "duplicate"}}
    assert ra.desenlace_de(res) == "no_limpia"
    assert "No está limpio" in _redactar_resultado_de_orden("auditar_garantias", res)
    assert ra.desenlace_de({"estado": "ejecutada", "resultado": {"status": "duplicate"}}) == "duplicada"
    assert ra.desenlace_de("no es un dict") == "desconocido"
    assert "no me devolvió un resultado que pueda leer" in _redactar_resultado_de_orden("x_cap", "no es un dict")
    assert "desenlace_de(" in inspect.getsource(orq_mod._redactar_resultado_de_orden)
    assert not hasattr(ra, "del_usuario"), "codigo muerto"


def test_las_frases_de_desenlace_no_se_redactan_fuera_de_la_funcion_unica():
    fuente = inspect.getsource(orq_mod)
    unica = inspect.getsource(describir_desenlace)
    resto = fuente.replace(unica, "")
    for frase in ("no sé interpretar", "leí un archivo", "no me devolvió un resultado que pueda leer"):
        assert frase in unica, f"control: {frase!r} deberia vivir en describir_desenlace"
        assert frase not in resto, f"{frase!r} se redacta fuera de la funcion unica"
    assert uuid and json and Orchestrator
