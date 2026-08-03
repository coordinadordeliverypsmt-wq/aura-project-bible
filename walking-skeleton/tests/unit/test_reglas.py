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

from aura_skeleton.core.reglas import AlmacenReglas, ReglaUsuario, evaluar_condicion, resolver_args


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


def test_el_almacen_persiste_la_regla_tras_reiniciar(tmp_path):
    """CRITERIO DEL CEO: la automatización sobrevive al reinicio (nuevo almacén desde disco)."""
    ruta = os.path.join(tmp_path, "reglas.jsonl")
    AlmacenReglas(ruta).crear(_regla())
    reglas = AlmacenReglas(ruta).listar("mauricio")  # reinicio: nueva instancia
    assert len(reglas) == 1
    assert reglas[0].rule_id == "r-copia-antes-de-borrar"
    assert reglas[0].args == {"ruta": "$evento.ruta"}


def test_el_almacen_aisla_por_usuario(tmp_path):
    alm = AlmacenReglas(os.path.join(tmp_path, "reglas.jsonl"))
    alm.crear(_regla())
    otra = ReglaUsuario(
        "r2", "otro", "action.command", {"campo": "action", "op": "==", "valor": "x"}, "y", {}, "activa", {}
    )
    alm.crear(otra)
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
