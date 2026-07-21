"""Conectores de contexto del computador y del hogar (M3.0).

Los registros de estas pruebas usan el formato REAL que escribe `observability.AuditLog`
(`level`/`module`/`msg`/`ts`). Con nombres inventados, los conectores pasarian las pruebas y
fallarian con datos reales: la prueba verificaria el doble, no el sistema (criterio T1).

Segunda y tercera fuente que M3 instrumenta. Ambas producen senales IMPLICITAS: nadie las declara,
se observan del uso. Su materia prima es el audit log que M2 ya escribe — no hay instrumentacion
nueva del sistema de archivos ni del hogar, solo lectura de lo que ya se registraba.
"""

import json

import pytest

from aura_skeleton.conectores.computador import ConectorComputador
from aura_skeleton.conectores.hogar import ConectorHogar
from aura_skeleton.core.senales import ClaseSenal


def _audit(tmp_path, registros):
    p = tmp_path / "audit.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(r) + "\n")
    return str(p)


@pytest.mark.asyncio
async def test_computador_deriva_patron_de_uso_del_audit_log(tmp_path):
    ruta = _audit(
        tmp_path,
        [
            {"level": "ACT", "module": "computador", "msg": "EJECUTA listar_directorio", "ts": 1.0},
            {"level": "ACT", "module": "computador", "msg": "EJECUTA borrar_archivo", "ts": 2.0},
        ],
    )
    senales = await ConectorComputador(ruta).recoger("t-1")

    assert len(senales) == 2
    assert all(s.clase is ClaseSenal.PATRON_DE_USO for s in senales)
    assert all(s.fuente == "computador" for s in senales)
    assert "listar_directorio" in senales[0].contenido


@pytest.mark.asyncio
async def test_no_se_reprocesan_registros_ya_leidos(tmp_path):
    """CASO DE CONTROL: sin esto, cada recogida duplicaria todo el historial."""
    ruta = _audit(tmp_path, [{"level": "ACT", "module": "computador", "msg": "EJECUTA leer_archivo", "ts": 1.0}])
    conector = ConectorComputador(ruta)

    primera = await conector.recoger("t-1")
    segunda = await conector.recoger("t-2")

    assert len(primera) == 1
    assert segunda == [], "un registro ya leido no puede volver a generar senal"


@pytest.mark.asyncio
async def test_solo_acciones_ejecutadas_generan_senal(tmp_path):
    """Una accion DETENIDA no es un patron de uso: es una que el usuario no llego a hacer."""
    ruta = _audit(
        tmp_path,
        [
            {"level": "ACT", "module": "computador", "msg": "EJECUTA borrar_archivo", "ts": 1.0},
            {"level": "AUTO", "module": "ejecutor", "msg": "[conversacion] DETENIDA borrar_archivo: x", "ts": 2.0},
            {"level": "HITL", "module": "permissions", "msg": "accion de LISTA ROJA requiere...", "ts": 3.0},
        ],
    )
    senales = await ConectorComputador(ruta).recoger("t-1")
    assert len(senales) == 1


@pytest.mark.asyncio
async def test_audit_inexistente_no_rompe_la_captura(tmp_path):
    """El log puede no existir todavia. Degradar, no caer."""
    senales = await ConectorComputador(str(tmp_path / "no-existe.jsonl")).recoger("t-1")
    assert senales == []


@pytest.mark.asyncio
async def test_hogar_deriva_patron_de_uso_de_dispositivos(tmp_path):
    ruta = _audit(
        tmp_path,
        [
            {"level": "ACT", "module": "ha-adapter", "msg": "EJECUTA encender_dispositivo sobre 'luz sala'", "ts": 1.0},
        ],
    )
    senales = await ConectorHogar(ruta).recoger("t-1")

    assert len(senales) == 1
    assert senales[0].fuente == "home_assistant"
    assert senales[0].clase is ClaseSenal.PATRON_DE_USO
    assert "luz sala" in senales[0].contenido


@pytest.mark.asyncio
async def test_cada_conector_solo_ve_su_dominio(tmp_path):
    """El conector del hogar no debe capturar acciones del computador ni al reves."""
    ruta = _audit(
        tmp_path,
        [
            {"level": "ACT", "module": "computador", "msg": "EJECUTA borrar_archivo", "ts": 1.0},
            {"level": "ACT", "module": "ha-adapter", "msg": "EJECUTA encender_dispositivo sobre 'luz'", "ts": 2.0},
        ],
    )
    del_pc = await ConectorComputador(ruta).recoger("t")
    del_hogar = await ConectorHogar(ruta).recoger("t")

    assert len(del_pc) == 1 and "borrar_archivo" in del_pc[0].contenido
    assert len(del_hogar) == 1 and "luz" in del_hogar[0].contenido
