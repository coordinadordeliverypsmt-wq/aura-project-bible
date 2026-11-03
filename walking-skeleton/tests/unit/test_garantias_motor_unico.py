"""F0 · RED de D-M-8 — las garantías G-2…G-7 del Motor Único, escritas contra el código ACTUAL.

`DP-D-M-8 §7`, fase **F0**: *«Escribir G-1…G-7 en rojo, contra el código actual. Sin red, la
migración no tiene cómo demostrarse. Documenta el estado real.»* Eso es lo que hace este fichero:
**no arregla nada**, deja constancia ejecutable de qué está roto hoy y de qué ya está a salvo.

**G-1 NO está aquí, y su ausencia es deliberada.** El CEO autorizó el 2026-08-17 únicamente el RED
de G-2…G-7 «que sea independiente de G-1». `D-G1-1` sigue `DECISION_REQUIRED`: el mecanismo de la
garantía madre está especificado en `ESPEC-G-1-RUTA-UNICA-DE-MUTACION.md`, **pendiente de
aprobación**. Aquí no se implementa, ni se sustituye, ni se reinterpreta. Ver
`test_este_fichero_no_depende_del_mecanismo_de_G_1`, que lo comprueba por ejecución.

**Cómo leer los verdes y los rojos de este fichero:**

- Un **rojo** es el estado real de ALERTA-006 y debe seguir rojo hasta que su fase lo cierre.
- Un **verde** aquí NO significa que la clase de fallo esté cerrada: significa que ese caso concreto
  quedó cubierto por la contención F1. La ruta sigue **fuera del Motor Único** (eso es G-1).

Cada garantía lleva su **caso de control**: sin él, un rojo no distingue «la garantía falla» de «la
prueba está mal escrita», y este proyecto ya se comió cuatro falsos PASS por ahorrárselo.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_modelo_usuario import EjecutorModeloUsuario
from aura_skeleton.core.kill_switch import KillSwitch
from aura_skeleton.core.modelo_usuario import ModeloUsuario
from aura_skeleton.core.permissions import ALTERA_ESTADO, CATALOGO, PermissionManager
from aura_skeleton.core.reglas import AlmacenReglas, ReglaUsuario
from aura_skeleton.modules.memory import PersistentMemory

# Operaciones que el DP §4.2 declara que FALTAN en el catálogo. Se citan literalmente; no se
# inventan otras ni se amplía la lista.
OPERACIONES_QUE_FALTAN = (
    "registrar_informacion_usuario",
    "olvidar_informacion_usuario",
    "refutar_informacion_usuario",
)


async def _confirmar(accion, args, trace_id):  # HITL que siempre autoriza: aísla el efecto medido
    return True


def _almacen_reglas(ruta, kill=None):
    """`AlmacenReglas` cableado al motor (F4 tramo 2). Sin motor no muta: pasaria en vacio."""
    from aura_skeleton.core.ejecutor_reglas import EjecutorReglas
    from aura_skeleton.core.registro import RegistroAdaptadores

    registro = RegistroAdaptadores()
    almacen = AlmacenReglas(str(ruta), motor=MotorAutomatizacion(
        registro, PermissionManager(_confirmar, kill_switch=kill)))
    registro.registrar(EjecutorReglas(almacen))
    return almacen


def _modelo(mem, kill=None):
    """`ModeloUsuario` CABLEADO al motor unico — F4, 2026-08-25.

    Antes bastaba `ModeloUsuario(mem)` porque mutaba el almacen directamente; esa era justamente la
    ruta huerfana que estos rojos denunciaban. Migrada, el modelo enruta por el motor y **sin motor
    no muta**: dejar el fixture como estaba habria hecho que estas pruebas pasaran EN VACIO — verdes
    porque nada ocurre, que es el falso PASS que este proyecto ya ha pagado varias veces.
    """
    return ModeloUsuario(mem, motor=MotorAutomatizacion(
        EjecutorModeloUsuario(mem), PermissionManager(_confirmar, kill_switch=kill)))


def _memoria_con_dos_hechos(tmp_path) -> tuple[PersistentMemory, pathlib.Path]:
    ruta = tmp_path / "memoria.json"
    mem = PersistentMemory(str(ruta))
    # `kind` DEBE pertenecer a `modelo_usuario._TIPOS` ("semantica", "procedimental"). Con
    # cualquier otro valor el predicado de `borrar` no casa con nada, el borrado no ocurre y los
    # rojos de este fichero pasarian EN VACIO. Ocurrio al escribirlo y por eso queda anotado.
    mem._items = [
        {"user_id": "mauricio", "kind": "semantica",
         "content": "tiene alergia a la penicilina", "provenance": {}},
        {"user_id": "mauricio", "kind": "semantica",
         "content": "suele pagar las facturas por la app", "provenance": {}},
    ]
    mem._persist()
    return mem, ruta


async def test_la_siembra_es_realmente_borrable(tmp_path):
    """META-CONTROL del fichero. Si la siembra no fuera alcanzable por `borrar`, TODOS los rojos de
    G-2, G-3 y G-7 pasarian en vacio y este fichero mentiria diciendo que el sistema esta sano."""
    mem, _ = _memoria_con_dos_hechos(tmp_path)
    n = await _modelo(mem, locals().get("kill")).borrar("mauricio", "penicilina")
    assert n == 1, "la siembra debe ser alcanzable por el borrado, o los rojos no prueban nada"


# ======================================================================== G-2 --
# «El kill switch armado detiene TODA mutación» — verificada sobre TODAS las operaciones, no solo
# las que pasan por `authorize`. Hoy el kill switch vive DENTRO de PermissionManager
# (`permissions.py:118`), así que solo alcanza a quien llama a `authorize`. F2 lo eleva a paso 0.


@pytest.mark.parametrize("accion", sorted(ALTERA_ESTADO))
async def test_g2_control_el_kill_switch_detiene_las_acciones_del_catalogo(accion):
    """CASO DE CONTROL — debe estar en VERDE hoy.

    Si esto fallara, el rojo de las pruebas siguientes no probaría nada: significaría que el kill
    switch no funciona en ningún sitio, no que hay rutas que lo esquivan."""
    kill = KillSwitch(trigger_file="/tmp/aura-inexistente-g2")
    kill.engage("prueba G-2")
    permisos = PermissionManager(_confirmar, kill_switch=kill)
    ok, motivo = await permisos.authorize(accion, {}, "t-g2")
    assert ok is False, f"{accion} debería quedar bloqueada por el kill switch"
    assert "kill switch" in motivo


async def test_g2_el_kill_switch_armado_no_detiene_el_olvido_del_modelo(tmp_path):
    """RED · ALERTA-006. Con la parada de emergencia ARMADA, el dato se destruye igual.

    La rama de soberanía no consulta al kill switch porque no pasa por `authorize`: no hay nada que
    consultarle. Es literalmente el titular de la alerta — *«con la parada de emergencia armada,
    AURA sigue destruyendo datos del usuario»*."""
    mem, _ = _memoria_con_dos_hechos(tmp_path)
    kill = KillSwitch(trigger_file="/tmp/aura-inexistente-g2")
    kill.engage("prueba G-2")
    assert kill.is_engaged() is True

    await _modelo(mem, locals().get("kill")).borrar("mauricio", "penicilina")

    contenidos = [i["content"] for i in mem._items]
    assert "tiene alergia a la penicilina" in contenidos, (
        "G-2: el kill switch armado NO detuvo el borrado del modelo del usuario")


async def test_g2_el_kill_switch_armado_no_detiene_la_refutacion(tmp_path):
    """RED · misma ruta, mismo agujero. `refutar` tampoco pregunta al kill switch."""
    mem, _ = _memoria_con_dos_hechos(tmp_path)
    kill = KillSwitch(trigger_file="/tmp/aura-inexistente-g2")
    kill.engage("prueba G-2")

    n = await _modelo(mem, locals().get("kill")).refutar("mauricio", "penicilina")

    assert n == 0, "G-2: el kill switch armado NO detuvo la refutación"


async def test_g2_el_kill_switch_armado_no_detiene_la_creacion_de_reglas(tmp_path):
    """RED · rama 4 de las 7 del turno: escribe `reglas.jsonl` sin motor, permisos ni kill switch."""
    kill = KillSwitch(trigger_file="/tmp/aura-inexistente-g2")
    kill.engage("prueba G-2")
    almacen = _almacen_reglas(tmp_path / "reglas.jsonl", kill)

    await almacen.crear(ReglaUsuario(rule_id="r1", user_id="mauricio", evento="archivo_creado",
                               condicion={}, accion="copiar_archivo", args={}))

    assert almacen.listar("mauricio") == [], (
        "G-2: el kill switch armado NO impidió crear una regla persistente")


# ======================================================================== G-3 --
# «Ninguna operación no catalogada se ejecuta» (RN-2).


async def test_g3_control_una_operacion_inventada_se_deniega():
    """CASO DE CONTROL — debe estar en VERDE. El catálogo deniega por defecto lo no clasificado."""
    permisos = PermissionManager(_confirmar)
    ok, motivo = await permisos.authorize("operacion_que_nadie_declaro", {}, "t-g3")
    assert ok is False, f"lo no catalogado debe denegarse (RN-2); motivo devuelto: {motivo!r}"


@pytest.mark.parametrize("operacion", OPERACIONES_QUE_FALTAN)
def test_g3_las_mutaciones_del_estado_propio_no_estan_catalogadas(operacion):
    """RED · `DP-D-M-8 §4.2`: el catálogo clasifica por verbo y **no existe entrada para crear
    información sobre la persona**, ni se distingue el sujeto. Estas tres son el mínimo que el DP
    declara necesario; no se añaden otras."""
    assert operacion in CATALOGO, (
        f"G-3: '{operacion}' muta estado persistente del usuario y no está en el catálogo")


async def test_g3_el_olvido_SOLO_se_ejecuta_estando_catalogado(tmp_path):
    """**PREMISA SUPERADA, garantía sustituida** — 2026-08-25, F3 + D-M8-2 = B.

    La versión anterior afirmaba `"olvidar_informacion_usuario" not in CATALOGO` y demostraba el
    agujero por su efecto: la operación mutaba el disco **sin que nadie la mirase**. Esa premisa dejó
    de ser cierta cuando el CEO aprobó las tres entradas que `§4.2` nombra, así que mantenerla sería
    comprobar un hecho histórico en vez de una garantía.

    Lo que se protege ahora es lo que de verdad importa y no caduca: **la operación se ejecuta
    porque está catalogada y correctamente clasificada, no porque nadie la controle.**
    """
    assert "olvidar_informacion_usuario" in CATALOGO
    assert CATALOGO["olvidar_informacion_usuario"]["lista"] == "soberania"
    assert CATALOGO["olvidar_informacion_usuario"].get("sujeto") == "usuario"

    mem, _ = _memoria_con_dos_hechos(tmp_path)
    borradas = await _modelo(mem).borrar("mauricio", "penicilina")
    assert borradas == 1, "catalogada y sin kill switch, la operación debe poder ejecutarse"

    # y el control que impide el falso PASS: lo NO catalogado sigue sin ejecutarse
    permisos = PermissionManager(_confirmar)
    ok, motivo = await permisos.authorize("olvidar_lo_que_sea", {"user_id": "mauricio"}, "t-g3")
    assert ok is False and "no clasificada" in motivo


# ======================================================================== G-4 --
# «No se narra éxito sin efecto» (INV-9 / ALERTA-005 §4).
#
# NOTA HONESTA: el caso que el DP cita en §2.3 —«refutar narra éxito con n=0 porque el orquestador
# descarta el retorno»— YA fue corregido por la contención F1 (`orchestrator.py:1021-1024`). Este
# bloque lo fija para que no se pierda, y **no lo presenta como rojo**.


async def test_g4_refutar_sin_efecto_devuelve_cero(tmp_path):
    """VERDE hoy, por F1. Se fija para que una migración futura no lo rompa en silencio."""
    mem, _ = _memoria_con_dos_hechos(tmp_path)
    n = await _modelo(mem, locals().get("kill")).refutar("mauricio", "algo que nadie ha declarado jamas")
    assert n == 0


async def test_g4_borrar_sin_efecto_devuelve_cero(tmp_path):
    """VERDE hoy. El contador es la única fuente de verdad sobre si hubo efecto."""
    mem, _ = _memoria_con_dos_hechos(tmp_path)
    n = await _modelo(mem, locals().get("kill")).borrar("mauricio", "algo que nadie ha declarado jamas")
    assert n == 0


# ======================================================================== G-5 --
# «Referente ambiguo no destruye». Cubierta por la contención F1 (`_foco`). Se fija aquí porque G-5
# es una garantía del DP y F1 puede deshacerse durante F4 sin que nadie lo note.


async def test_g5_un_predicado_que_no_casa_con_nada_no_destruye_nada(tmp_path):
    """VERDE hoy. El nivel de `_foco` está cubierto en `test_contencion_alerta006.py`; aquí se fija
    el nivel inferior: un objetivo que no casa **no puede** llevarse por delante otra entrada."""
    mem, _ = _memoria_con_dos_hechos(tmp_path)
    antes = len(mem._items)
    await _modelo(mem, locals().get("kill")).borrar("mauricio", "termino que no aparece en ninguna entrada")
    assert len(mem._items) == antes


# ======================================================================== G-6 --
# «Toda mutación es reconstruible desde el audit log» — criterio de aceptación del DP §5.1: *a
# partir del audit log debe poder responderse «¿qué había antes y qué hay ahora?»*.


async def test_g6_el_borrado_no_deja_rastro_reconstruible(tmp_path, monkeypatch):
    """RED · `memory.py:196` registra *«olvidadas N entrada(s)»* con `trace_id="-"`, **sin user_id y
    sin contenido**. El registro existe, pero no permite reconstruir lo perdido: la auditoría no
    cumple su función."""
    from aura_skeleton import observability as obs

    registros: list[dict] = []
    monkeypatch.setattr(obs, "log",
                        lambda *a, **k: registros.append({"args": a, "kv": k}))

    mem, _ = _memoria_con_dos_hechos(tmp_path)
    await _modelo(mem, locals().get("kill")).borrar("mauricio", "penicilina")

    texto = json.dumps(registros, ensure_ascii=False)
    assert "tiene alergia a la penicilina" in texto, (
        "G-6: el audit no registra QUÉ se borró; lo perdido no es reconstruible")
    assert "mauricio" in texto, "G-6: el audit no registra SOBRE QUIÉN recayó la mutación"


# ======================================================================== G-7 --
# «Append-only en los almacenes que lo declaran».


async def test_g7_control_desactivar_una_regla_anexa_en_vez_de_reescribir(tmp_path):
    """CASO DE CONTROL — VERDE. `AlmacenReglas.desactivar` es el modelo a imitar según el DP §5.2:
    anexa una línea `inactiva` en vez de reescribir el fichero."""
    ruta = tmp_path / "reglas.jsonl"
    almacen = _almacen_reglas(ruta)
    await almacen.crear(ReglaUsuario(rule_id="r1", user_id="mauricio", evento="archivo_creado",
                               condicion={}, accion="copiar_archivo", args={}))
    lineas_antes = len(ruta.read_text(encoding="utf-8").splitlines())

    await almacen.desactivar("mauricio", "r1")

    lineas_despues = len(ruta.read_text(encoding="utf-8").splitlines())
    assert lineas_despues > lineas_antes, "el almacén de reglas debería anexar, no reescribir"


async def test_g7_el_olvido_destruye_lineas_del_almacen(tmp_path):
    """RED · `olvidar` llama a `_persist()`, que **reescribe el JSONL entero**. La línea desaparece
    del disco: sin lápida, sin backup —`backup()` existe pero nadie lo llama en producción— y sin
    posibilidad de reconstrucción. El DP §5.2 exige adoptar el patrón que las reglas ya usan."""
    mem, ruta = _memoria_con_dos_hechos(tmp_path)
    lineas_antes = len(ruta.read_text(encoding="utf-8").splitlines())

    await _modelo(mem, locals().get("kill")).borrar("mauricio", "penicilina")

    lineas_despues = len(ruta.read_text(encoding="utf-8").splitlines())
    assert lineas_despues >= lineas_antes, (
        f"G-7: el almacén perdió líneas ({lineas_antes} -> {lineas_despues}): no es append-only")


# ============================================== INDEPENDENCIA RESPECTO DE G-1 --


def _fuente_sin_las_lineas_declarativas() -> str:
    """El fichero, sin las líneas que solo NOMBRAN lo prohibido.

    Sin este filtro la prueba se encontraría a sí misma y fallaría por hablar de lo que vigila —el
    mismo autoengaño que ya costó cuatro pruebas mal escritas en este proyecto."""
    lineas = pathlib.Path(__file__).read_text(encoding="utf-8").splitlines()
    return "\n".join(ln for ln in lineas if '" + "' not in ln)


def test_este_fichero_no_depende_del_mecanismo_de_G_1():
    """Comprobación EXIGIDA POR EL CEO: G-2…G-7 deben ser independientes de G-1.

    G-1 se verifica por **análisis AST** sobre una **lista blanca** derivada del manifiesto de
    arquitectura (`ESPEC-G-1 §1`). Este fichero no usa ninguna de esas dos cosas: todas sus pruebas
    son **de comportamiento** —ejecutan una mutación y observan su efecto—, y ninguna necesita saber
    *quién* llama a *quién*."""
    fuente = _fuente_sin_las_lineas_declarativas()
    for prohibido in ("import " + "ast", "architecture_" + "manifest",
                      "test_manifiesto_" + "arquitectura", "lista_" + "blanca"):
        assert prohibido not in fuente, (
            f"esta prueba usa {prohibido!r}: sería el mecanismo de G-1, que NO está autorizado")


def test_las_garantias_escritas_son_exactamente_las_autorizadas():
    """Ni una garantía de menos —sería alcance incompleto— ni una de más —sería alcance ampliado."""
    fuente = _fuente_sin_las_lineas_declarativas()
    for g in ("G-2", "G-3", "G-4", "G-5", "G-6", "G-7"):
        assert f"test_{g.lower().replace('-', '')}_" in fuente, f"falta el RED de {g}"
    assert "def test_g" + "1_" not in fuente, (
        "G-1 NO está autorizada: D-G1-1 sigue DECISION_REQUIRED")
