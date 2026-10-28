"""Unit: modelo y almacén de reglas de automatización (MVP capacidad 5, Bible 6.4).

Una automatización definida por el usuario es una regla `evento → condición → acción` (6.4:38), con el
modelo DEFINITIVO fijado por el CEO (2026-07-28):
  - `rule_id`     identificador estable;
  - `evento`      tipo de evento del bus que la dispara;
  - `condicion`   DECLARATIVA (campo/operador/valor), sin lógica arbitraria;
  - `accion` + `args`  la acción a ejecutar; los args son REFERENCIAS al evento ($evento.ruta), no valores fijos;
  - `estado`      activa / inactiva;
  - `metadatos`   descripción legible, creada, etc.

La regla es **dato del usuario** y debe PERSISTIR: sobrevive al reinicio (criterio de aceptación del CEO).
"""

import os

import pytest

from aura_skeleton.core.automatizacion import MotorAutomatizacion
from aura_skeleton.core.ejecutor_reglas import EjecutorReglas
from aura_skeleton.core.permissions import PermissionManager
from aura_skeleton.core.registro import RegistroAdaptadores
from aura_skeleton.core.reglas import AlmacenReglas, ReglaUsuario, evaluar_condicion, resolver_args


async def _confirmar(accion, args, trace_id):
    return True

def _almacen(ruta):
    """`AlmacenReglas` CABLEADO al motor unico (F4 tramo 2, 2026-08-25).

    `crear` y `desactivar` dejaron de escribir el JSONL directamente: pasan por catalogo, permisos y
    kill switch. **Sin motor no mutan**, asi que un fixture que construya `_almacen(ruta)` a
    secas haria pasar estas pruebas EN VACIO. Ningun veredicto cambia.
    """
    registro = RegistroAdaptadores()
    motor = MotorAutomatizacion(registro, PermissionManager(_confirmar))
    almacen = AlmacenReglas(ruta, motor=motor)
    registro.registrar(EjecutorReglas(almacen))
    return almacen

def _regla():
    return ReglaUsuario(
        rule_id="r-copia-antes-de-borrar",
        user_id="mauricio",
        evento="action.command",
        condicion={"campo": "action", "op": "==", "valor": "borrar_archivo"},
        accion="copiar_archivo",
        args={"ruta": "$evento.ruta"},  # referencia al evento, no valor fijo
        estado="activa",
        metadatos={"descripcion": "guardar una copia antes de borrar"},
    )

def test_regla_tiene_los_cinco_campos_del_modelo():
    r = _regla()
    assert r.rule_id and r.evento == "action.command"
    assert r.condicion["op"] == "==" and r.accion == "copiar_archivo"
    assert r.args["ruta"] == "$evento.ruta"  # referencia, no valor
    assert r.estado == "activa" and "descripcion" in r.metadatos

@pytest.mark.asyncio
async def test_el_almacen_persiste_la_regla_tras_reiniciar(tmp_path):
    """CRITERIO DEL CEO: la automatización sobrevive al reinicio (nuevo almacén desde disco)."""
    ruta = os.path.join(tmp_path, "reglas.jsonl")
    await _almacen(ruta).crear(_regla())
    reglas = AlmacenReglas(ruta).listar("mauricio")  # reinicio: nueva instancia
    assert len(reglas) == 1
    assert reglas[0].rule_id == "r-copia-antes-de-borrar"
    assert reglas[0].args == {"ruta": "$evento.ruta"}

@pytest.mark.asyncio
async def test_el_almacen_aisla_por_usuario(tmp_path):
    alm = _almacen(os.path.join(tmp_path, "reglas.jsonl"))
    await alm.crear(_regla())
    otra = ReglaUsuario(
        "r2", "otro", "action.command", {"campo": "action", "op": "==", "valor": "x"}, "y", {}, "activa", {}
    )
    await alm.crear(otra)
    assert [r.rule_id for r in alm.listar("mauricio")] == ["r-copia-antes-de-borrar"]

def test_condicion_declarativa_igualdad():
    cond = {"campo": "action", "op": "==", "valor": "borrar_archivo"}
    assert evaluar_condicion(cond, {"action": "borrar_archivo", "args": {}})
    assert not evaluar_condicion(cond, {"action": "mover_archivo", "args": {}})

def test_args_se_resuelven_como_referencias_al_evento():
    """$evento.ruta se sustituye por el valor del evento; un valor fijo se deja tal cual."""
    evento = {"action": "borrar_archivo", "args": {"ruta": "/home/u/informe.pdf"}}
    resueltos = resolver_args({"ruta": "$evento.ruta", "modo": "seguro"}, evento)
    assert resueltos["ruta"] == "/home/u/informe.pdf"  # referencia resuelta
    assert resueltos["modo"] == "seguro"  # valor fijo intacto


# --- Silencio selectivo de fallos del respaldo (auditoría independiente 2026-08-02) ----------------

def test_solo_se_silencia_la_ausencia_del_origen_nunca_una_colision():
    """El nombre del archivo lo elige el USUARIO y viaja dentro del motivo de error.

    Con un fichero llamado `cuaderno existente.txt`, el motivo de una colisión real contiene la
    subcadena "no existe" a través de la frontera de palabras («cuader-NO EXISTE-nte»). Si el filtro
    comparase contra el motivo completo, silenciaría un respaldo que NO se hizo: el archivo se
    borraría y el usuario no se enteraría de que perdió la copia. Pérdida de datos en silencio.
    """
    from aura_skeleton.core.orchestrator import _nada_que_respaldar

    colision = {"motivo": "el destino ya existe: 'cuaderno existente.txt.copia'"}
    assert not _nada_que_respaldar(colision), "silenció una colisión real por el nombre del archivo"

    ausente = {"motivo": "fallo del sistema de archivos: No such file or directory"}
    assert _nada_que_respaldar(ausente), "debe seguir callando cuando no había nada que respaldar"

    protegido = {"motivo": "fallo del sistema de archivos: Permission denied"}
    assert not _nada_que_respaldar(protegido), "un fallo de permisos SIEMPRE debe comunicarse"


# --- Desactivar reglas (deuda D-A-9): el log se proyecta por (user_id, rule_id) -----------------------

@pytest.mark.asyncio
async def test_desactivar_hace_que_listar_y_aplicables_dejen_de_devolver_la_regla(tmp_path):
    ruta = os.path.join(tmp_path, "reglas.jsonl")
    alm = _almacen(ruta)
    await alm.crear(_regla())

    assert await alm.desactivar("mauricio", "r-copia-antes-de-borrar") is True
    assert alm.listar("mauricio") == []
    assert alm.aplicables("mauricio", "action.command") == []

@pytest.mark.asyncio
async def test_desactivar_conserva_el_historial_en_el_fichero(tmp_path):
    """El append-only es la garantia que el CEO aprobo: nunca se reescribe ni se trunca el fichero."""
    ruta = os.path.join(tmp_path, "reglas.jsonl")
    alm = _almacen(ruta)
    await alm.crear(_regla())
    with open(ruta, encoding="utf-8") as f:
        lineas_antes = f.readlines()
    assert len(lineas_antes) == 1

    await alm.desactivar("mauricio", "r-copia-antes-de-borrar")

    with open(ruta, encoding="utf-8") as f:
        lineas_despues = f.readlines()
    assert len(lineas_despues) == 2  # creacion + desactivacion: ninguna linea se pierde
    assert lineas_despues[0] == lineas_antes[0]  # la linea original de creacion sigue literal

@pytest.mark.asyncio
async def test_desactivar_sobrevive_al_reinicio(tmp_path):
    """CRITERIO DEL CEO: una instancia nueva, leyendo el mismo fichero, no debe devolver la regla desactivada."""
    ruta = os.path.join(tmp_path, "reglas.jsonl")
    await _almacen(ruta).crear(_regla())
    alm1 = _almacen(ruta)
    await alm1.desactivar("mauricio", "r-copia-antes-de-borrar")

    alm2 = _almacen(ruta)  # reinicio: nueva instancia, mismo fichero
    assert alm2.listar("mauricio") == []

@pytest.mark.asyncio
async def test_desactivar_aisla_por_usuario_no_afecta_al_mismo_rule_id_de_otro_usuario(tmp_path):
    """Prueba de seguridad (P-ARQ-5): la clave de proyeccion es (user_id, rule_id), nunca solo rule_id.

    Si dos usuarios tienen una regla con el mismo rule_id, que uno desactive la suya NO debe apagar
    la del otro: eso romperia el aislamiento por usuario.
    """
    ruta = os.path.join(tmp_path, "reglas.jsonl")
    alm = _almacen(ruta)
    await alm.crear(_regla())  # rule_id="r-copia-antes-de-borrar", user_id="mauricio"
    regla_de_otro = ReglaUsuario(
        rule_id="r-copia-antes-de-borrar",  # mismo rule_id, otro usuario
        user_id="otro",
        evento="action.command",
        condicion={"campo": "action", "op": "==", "valor": "borrar_archivo"},
        accion="copiar_archivo",
        args={"ruta": "$evento.ruta"},
        estado="activa",
        metadatos={},
    )
    await alm.crear(regla_de_otro)

    assert await alm.desactivar("mauricio", "r-copia-antes-de-borrar") is True

    assert [r.rule_id for r in alm.listar("otro")] == ["r-copia-antes-de-borrar"]
    assert alm.listar("mauricio") == []

    # tambien tras reinicio, para probar que la proyeccion desde disco respeta el mismo aislamiento
    alm2 = _almacen(ruta)
    assert [r.rule_id for r in alm2.listar("otro")] == ["r-copia-antes-de-borrar"]
    assert alm2.listar("mauricio") == []

@pytest.mark.asyncio
async def test_desactivar_devuelve_false_si_no_existe_o_ya_esta_inactiva_y_no_escribe_nada(tmp_path):
    ruta = os.path.join(tmp_path, "reglas.jsonl")
    alm = _almacen(ruta)
    await alm.crear(_regla())

    assert await alm.desactivar("mauricio", "regla-inexistente") is False
    with open(ruta, encoding="utf-8") as f:
        lineas = f.readlines()
    assert len(lineas) == 1  # no escribio nada por una regla que no existe

    assert await alm.desactivar("mauricio", "r-copia-antes-de-borrar") is True  # ahora si la desactiva
    with open(ruta, encoding="utf-8") as f:
        lineas_tras_primera_desactivacion = f.readlines()
    assert len(lineas_tras_primera_desactivacion) == 2

    assert await alm.desactivar("mauricio", "r-copia-antes-de-borrar") is False  # ya estaba inactiva
    with open(ruta, encoding="utf-8") as f:
        lineas_finales = f.readlines()
    assert lineas_finales == lineas_tras_primera_desactivacion  # no escribio nada de mas

@pytest.mark.asyncio
async def test_crear_no_duplica_la_proyeccion_tras_desactivar_y_volver_a_crear(tmp_path):
    """Hallazgo de auditoria independiente (2026-08-02): crear() hacia self._reglas.append(regla)
    SIN proyectar, mientras que desactivar() si actualizaba la proyeccion en memoria. Tras
    crear -> desactivar -> crear la MISMA regla en la MISMA sesion, self._reglas quedaba con DOS
    entradas para la misma clave (user_id, rule_id): primero la inactiva, luego la activa.
    `desactivar` busca con next(...), que devuelve la PRIMERA coincidencia: siempre encontraba la
    inactiva y devolvia False para siempre (hasta reiniciar el proceso), dejando la automatizacion
    disparando sin que el usuario pudiera apagarla. La proyeccion por (user_id, rule_id) debe ser
    la UNICA responsable del estado vigente: nunca debe haber dos entradas con la misma clave.
    """
    ruta = os.path.join(tmp_path, "reglas.jsonl")
    alm = _almacen(ruta)
    await alm.crear(_regla())
    assert await alm.desactivar("mauricio", "r-copia-antes-de-borrar") is True

    await alm.crear(_regla())  # el usuario vuelve a crear la MISMA regla, en la MISMA instancia
    assert alm.listar("mauricio") != [], "deberia estar activa de nuevo tras recrearla"

    assert await alm.desactivar("mauricio", "r-copia-antes-de-borrar") is True, (
        "la proyeccion en memoria tenia una entrada duplicada: desactivar encontro la vieja inactiva"
    )
    assert alm.listar("mauricio") == []
    assert alm.aplicables("mauricio", "action.command") == []
