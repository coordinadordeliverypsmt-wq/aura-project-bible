"""RED del Communication Plane -- DP-COMMUNICATION-PLANE-AURORA.

===============================================================================
ESTAS PRUEBAS DEBEN FALLAR. NO SON UN DEFECTO.
===============================================================================

Son la fase RED del protocolo del proyecto: la prueba se escribe ANTES que el codigo y falla
porque `communication_plane.py` **no existe**. Ese fallo es el entregable: fija el contrato del
canal de forma ejecutable, para que GREEN no pueda inventarse la interfaz sobre la marcha.

**NO SE HA IMPLEMENTADO NADA.** El DP vigente (DP-DEVELOPMENT-ORCHESTRATOR) esta en estado
PROPUESTO, no aprobado, y la orden del CEO es explicita: GREEN solo si la implementacion esta
autorizada por el DP vigente. No lo esta. Por eso el modulo bajo prueba no existe y este fichero
se queda en rojo hasta que el CEO autorice.

**No rompen el Quality Gate:** el gate ejecuta `pytest` desde `walking-skeleton/` y no recoge
`entorno/`. Verificado leyendo `walking-skeleton/quality-gate.sh:16-19`.

**Como leer un fallo aqui:** si el error es `ModuleNotFoundError: communication_plane`, el RED
esta funcionando. Si algun dia el error es otro, es que hay implementacion parcial y hay que
mirarla.

QUE DEMUESTRA CADA BLOQUE
-------------------------
Cada prueba corresponde a un requisito numerado del encargo del CEO (2026-08-17), citado en el
docstring. Un requisito sin prueba que pueda fallar no es un requisito: es una intencion.
"""

from __future__ import annotations

import importlib
import pathlib

import pytest

def _canal():
    """Importa el modulo bajo prueba. Falla en RED, y ese es el punto.

    Se importa dentro de cada prueba (no arriba) para que el fallo sea POR PRUEBA y el informe
    muestre exactamente que requisitos quedan sin cubrir, en vez de un unico error de coleccion
    que oculta el mapa completo.
    """
    return importlib.import_module("communication_plane")


# ===========================================================================
# Req. 2 -- Tipos de mensaje del protocolo
# ===========================================================================

def test_el_protocolo_define_exactamente_los_ocho_tipos_de_mensaje():
    """Req. 2. Ni uno mas ni uno menos: un tipo extra es superficie no gobernada."""
    canal = _canal()
    assert set(canal.TIPOS_MENSAJE) == {
        "TASK", "ACK", "RESULT", "BLOCKED", "DECISION_REQUIRED",
        "WAITING_FOR_ENVIRONMENT", "WAITING_FOR_QUOTA", "FAILED",
    }


def test_un_tipo_de_mensaje_desconocido_se_rechaza_al_escribir():
    """Req. 2. El canal valida en la entrada, no en la lectura."""
    canal = _canal()
    with pytest.raises(canal.MensajeInvalido):
        canal.validar({"tipo": "APROBADO_POR_LA_IA", "de": "x", "para": "y", "cuerpo": {}})


# ===========================================================================
# Req. 3 y 6 -- Identificador unico y determinista
# ===========================================================================

def test_el_identificador_de_mensaje_es_determinista_sobre_su_contenido():
    """Req. 3 + 6. Mismo contenido -> mismo id. Es la base de la idempotencia."""
    canal = _canal()
    m = {"tipo": "TASK", "de": "gpt", "para": "claude", "cuerpo": {"objetivo": "x"}}
    assert canal.id_de_mensaje(m) == canal.id_de_mensaje(dict(m))


def test_un_contenido_distinto_produce_un_identificador_distinto():
    """Req. 3. Si dos mensajes distintos colisionaran, el canal perderia uno."""
    canal = _canal()
    a = {"tipo": "TASK", "de": "gpt", "para": "claude", "cuerpo": {"objetivo": "x"}}
    b = {"tipo": "TASK", "de": "gpt", "para": "claude", "cuerpo": {"objetivo": "y"}}
    assert canal.id_de_mensaje(a) != canal.id_de_mensaje(b)


# ===========================================================================
# Req. 4 -- in_reply_to y trazabilidad de la conversacion
# ===========================================================================

def test_una_respuesta_referencia_el_mensaje_al_que_responde(tmp_path):
    """Req. 4. Sin `in_reply_to` no hay hilo, solo mensajes sueltos."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    tarea = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})
    ack = c.publicar(tipo="ACK", de="claude", para="gpt", cuerpo={}, in_reply_to=tarea)

    assert c.leer(ack)["in_reply_to"] == tarea


def test_in_reply_to_debe_apuntar_a_un_mensaje_existente(tmp_path):
    """Req. 4. Una referencia a un mensaje inexistente rompe la reconstruccion del hilo."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    with pytest.raises(canal.MensajeInvalido):
        c.publicar(tipo="ACK", de="claude", para="gpt", cuerpo={},
                   in_reply_to="00000000-0000-0000-0000-000000000000")


def test_el_hilo_completo_se_reconstruye_desde_el_log(tmp_path):
    """Req. 4 + 5. TASK -> ACK -> RESULT debe poder leerse como una conversacion."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    t = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})
    a = c.publicar(tipo="ACK", de="claude", para="gpt", cuerpo={}, in_reply_to=t)
    r = c.publicar(tipo="RESULT", de="claude", para="gpt", cuerpo={"ok": True}, in_reply_to=t)

    # ANADIDO 2026-08-24 por un mutante SUPERVIVIENTE: si todos los mensajes publicados pertenecen
    # al hilo, devolver el log ENTERO da el mismo resultado y la prueba no discrimina. Hace falta
    # un mensaje ajeno que NO debe aparecer.
    ajeno = c.publicar(tipo="TASK", de="otro", para="nadie", cuerpo={"objetivo": "z"})

    assert [m["id"] for m in c.hilo(t)] == [t, a, r]
    assert ajeno not in [m["id"] for m in c.hilo(t)], "el hilo incluye un mensaje que no responde a la raiz"


# ===========================================================================
# Req. 5 y 8 -- Estado persistente y recuperacion tras caida
# ===========================================================================

def test_el_canal_sobrevive_a_cerrar_y_reabrir(tmp_path):
    """Req. 5. Si el estado vive en memoria, no es un canal: es una conversacion."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    mid = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})
    del c

    reabierto = canal.abrir(tmp_path)
    assert reabierto.leer(mid)["cuerpo"]["objetivo"] == "x"


def test_una_linea_truncada_al_final_no_impide_abrir_el_canal(tmp_path):
    """Req. 8. Un corte de luz a mitad de escritura deja media linea. El canal debe
    abrirse igual, descartar esa linea y decirlo -- nunca fingir que no paso."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})

    log = canal.ruta_log(tmp_path)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write('{"tipo": "TASK", "de": "gpt", "para')      # linea a medias

    reabierto = canal.abrir(tmp_path)
    informe = reabierto.verificar_integridad()
    assert informe["lineas_descartadas"] == 1
    assert informe["integro"] is True


def test_la_cadena_de_hashes_detecta_una_manipulacion_del_log(tmp_path):
    """Req. 10. "Transaccional y verificable, no un simple archivo de texto" (CEO).

    Cada mensaje encadena el hash del anterior. Alterar uno rompe la cadena y el canal
    debe DECIRLO, no seguir como si nada.
    """
    canal = _canal()
    c = canal.abrir(tmp_path)
    c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})
    c.publicar(tipo="ACK", de="claude", para="gpt", cuerpo={})

    log = canal.ruta_log(tmp_path)
    lineas = log.read_text(encoding="utf-8").splitlines()
    lineas[0] = lineas[0].replace('"objetivo": "x"', '"objetivo": "BORRA TODO"')
    log.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    informe = canal.abrir(tmp_path).verificar_integridad()
    assert informe["integro"] is False
    assert informe["primera_linea_corrupta"] == 1


# ===========================================================================
# Req. 6 y 7 -- Idempotencia y deteccion de ya procesados
# ===========================================================================

def test_publicar_dos_veces_el_mismo_mensaje_no_lo_duplica(tmp_path):
    """Req. 6. Un reintento tras un timeout no puede crear dos tareas."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    m = {"tipo": "TASK", "de": "gpt", "para": "claude", "cuerpo": {"objetivo": "x"}}
    primero = c.publicar(**m)
    segundo = c.publicar(**m)

    assert primero == segundo
    lineas_antes = len(canal.ruta_log(tmp_path).read_text(encoding="utf-8").splitlines())
    assert len(c.pendientes(para="claude")) == 1
    # ANADIDO 2026-08-25 por un mutante SUPERVIVIENTE, y el mutante era grave: deduplicar BORRANDO
    # la linea repetida tambien hacia pasar la asercion de arriba. Medido: el log pasaba de 2 a 1
    # lineas al consultar. Una LECTURA no puede alterar el historial (ADR-0023, append-only).
    assert len(canal.ruta_log(tmp_path).read_text(encoding="utf-8").splitlines()) == lineas_antes, (
        "consultar pendientes() modifico el log: una lectura no puede escribir")
    assert len(c.leer_desde(0)) == 2, "las dos lineas fisicas deben conservarse"


def test_un_mensaje_marcado_como_procesado_no_vuelve_a_entregarse(tmp_path):
    """Req. 7. Sin esto, un worker reejecuta la misma tarea en cada arranque."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    mid = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})

    assert mid in [m["id"] for m in c.pendientes(para="claude")]
    c.marcar_procesado(mid, por="claude")
    assert mid not in [m["id"] for m in c.pendientes(para="claude")]


def test_marcar_procesado_dos_veces_es_inocuo(tmp_path):
    """Req. 6. La idempotencia tambien aplica al acuse, no solo al mensaje."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    mid = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})
    c.marcar_procesado(mid, por="claude")
    lineas_tras_la_primera = len(canal.ruta_log(tmp_path).read_text(encoding="utf-8").splitlines())
    c.marcar_procesado(mid, por="claude")

    assert c.pendientes(para="claude") == []
    # ANADIDO 2026-08-24 por un mutante SUPERVIVIENTE. Mirar solo `pendientes` NO distingue la
    # idempotencia: sigue vacio aunque se anexe un evento por cada llamada. La garantia es que la
    # SEGUNDA marca no escriba nada, y eso solo se ve en el log.
    assert len(canal.ruta_log(tmp_path).read_text(encoding="utf-8").splitlines()) == lineas_tras_la_primera, (
        "marcar dos veces anexo un segundo evento: no es idempotente")


def test_el_estado_de_procesado_sobrevive_al_reinicio(tmp_path):
    """Req. 7 + 8. Lo contrario reejecuta todo el historial tras cada caida."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    mid = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})
    c.marcar_procesado(mid, por="claude")
    del c

    assert canal.abrir(tmp_path).pendientes(para="claude") == []


# ===========================================================================
# Req. 9 -- Locks: dos workers no modifican el mismo estado a la vez
# ===========================================================================

def test_dos_escritores_concurrentes_no_pierden_ningun_mensaje(tmp_path):
    """Req. 9. Es el defecto P2 del Control Plane, que aqui NO debe repetirse.

    Se lanzan dos procesos reales que publican a la vez. **Los dos mensajes deben estar.**
    En el Control Plane actual, sin lock, uno se pierde en silencio.
    """
    canal = _canal()
    resultado = canal.prueba_de_concurrencia(tmp_path, escritores=2, mensajes_por_escritor=5)

    assert resultado["publicados"] == 10
    assert resultado["en_el_log"] == 10
    assert resultado["perdidos"] == 0
    # ANADIDO 2026-08-24 por un mutante SUPERVIVIENTE: con HILOS el recuento sale idéntico —el flock
    # del mismo proceso los serializa— y la prueba pasaría sin ejercer concurrencia entre procesos.
    # Que los escritores sean procesos DISTINTOS y distintos del test lo hace observable.
    assert len(resultado["pids"]) == 2, "los escritores deben ser dos procesos distintos"
    assert resultado["pid_del_test"] not in resultado["pids"], (
        "un escritor que corre en el proceso del test no ejerce concurrencia real")


def test_un_segundo_proceso_no_puede_tomar_el_lock_mientras_esta_tomado(tmp_path):
    """Req. 9. El lock debe ser real (flock), no una convencion."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    with c.lock():
        # CORREGIDO 2026-08-24: `is False or True` es una TAUTOLOGIA — siempre cierta, ninguna
        # degradacion la haria fallar. Era una asercion decorativa, justo lo que CLAUDE.md advierte.
        # MEDIDO: con el lock tomado, la consulta devuelve True aunque pregunte el mismo proceso,
        # porque flock es por descriptor abierto y este es otro.
        assert c.lock_tomado_por_otro_proceso() is True, "el lock esta tomado y la consulta lo niega"
        assert canal.intentar_lock_no_bloqueante(tmp_path) is False


def test_el_lock_se_libera_si_el_proceso_muere(tmp_path):
    """Req. 8 + 9. Un lock huerfano tras un SIGKILL congelaria el canal para siempre.

    `flock` lo libera al cerrarse el descriptor, incluso con SIGKILL -- por eso se elige
    flock y no un fichero centinela, que si se quedaria colgado.
    """
    canal = _canal()
    cerrojo = tmp_path / "canal.lock"
    assert not cerrojo.exists(), "el cerrojo no debe existir antes: se mide sobre un canal virgen"

    assert canal.lock_se_libera_al_morir_el_proceso(tmp_path) is True

    # Caso de control. Sin esto la prueba pasaria igual con un `return True` que no mide nada -- lo
    # destapo el mutante G2-M12, que sobrevivio. Medir de verdad EXIGE tomar el cerrojo, y tomarlo
    # crea el fichero: una afirmacion sin medicion no deja rastro en el disco.
    assert cerrojo.exists(), (
        "la funcion devolvio True sin haber tocado el cerrojo: eso es afirmar la garantia, "
        "no medirla (INV-9)")


# ===========================================================================
# Req. 10 -- Auditoria append-only
# ===========================================================================

def test_el_log_es_append_only_los_mensajes_no_se_modifican(tmp_path):
    """Req. 10. Retirar algo es anexar una lapida, nunca reescribir (ADR-0023)."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    mid = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})
    antes = canal.ruta_log(tmp_path).read_text(encoding="utf-8")

    c.retractar(mid, motivo="la tarea ya no aplica")
    despues = canal.ruta_log(tmp_path).read_text(encoding="utf-8")

    assert despues.startswith(antes), "el log anterior debe conservarse intacto"
    assert len(despues) > len(antes), "la retractacion se anexa"


def test_cada_mensaje_lleva_secuencia_monotona(tmp_path):
    """Req. 10. Sin `seq` no se puede leer incrementalmente ni detectar huecos."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    a = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "1"})
    b = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "2"})

    assert c.leer(b)["seq"] == c.leer(a)["seq"] + 1


def test_se_puede_leer_desde_una_secuencia_dada(tmp_path):
    """Req. 8. Un worker que se reincorpora lee solo lo nuevo, no todo el historial."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "1"})
    b = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "2"})

    assert [m["id"] for m in c.leer_desde(seq=2)] == [b]


# ===========================================================================
# LIMITES DE AUTORIDAD -- el requisito que no se negocia
# ===========================================================================

def test_un_mensaje_del_canal_no_puede_otorgar_autoridad(tmp_path):
    """CEO: "No permitir que un mensaje del canal otorgue autoridad que el Control Plane no
    posea". La garantia es estructural: el canal transporta, no autoriza.
    """
    canal = _canal()
    c = canal.abrir(tmp_path)
    with pytest.raises(canal.MensajeInvalido):
        c.publicar(tipo="TASK", de="gpt", para="claude",
                   cuerpo={"objetivo": "x", "autoriza": True, "nivel": "HUMAN"})


def test_ningun_campo_del_mensaje_se_llama_como_una_concesion_de_permiso():
    """Misma garantia, por construccion del esquema: los campos prohibidos no existen."""
    canal = _canal()
    prohibidos = {"autoriza", "aprueba", "permiso", "permite", "autorizacion", "override"}
    assert not set(canal.CAMPOS_MENSAJE) & prohibidos


def test_decision_required_bloquea_y_no_se_desbloquea_sola(tmp_path):
    """CEO: "DECISION_REQUIRED debe permanecer bloqueante hasta una aprobacion valida"."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    d = c.publicar(tipo="DECISION_REQUIRED", de="claude", para="ceo",
                   cuerpo={"pregunta": "reduzco n?"})

    assert c.bloqueado_por(d) is True
    c.publicar(tipo="ACK", de="gpt", para="claude", cuerpo={}, in_reply_to=d)
    assert c.bloqueado_por(d) is True, "un ACK de otro agente NO desbloquea una decision humana"
    # ANADIDO 2026-08-25 por un mutante SUPERVIVIENTE: nada probaba que el bloqueo sea ESPECIFICO de
    # DECISION_REQUIRED. Bloquear cualquier tipo pasaria inadvertido y congelaria el canal entero.
    # Derivado del contrato: `clase_de` declara que solo DECISION_REQUIRED es una SOLICITUD.
    t = c.publicar(tipo="TASK", de="gpt", para="claude",
                   cuerpo={"objetivo": "x", "a": 1, "b": 2, "instruccion": "haz x"})
    assert c.bloqueado_por(t) is False, "un TASK no es una decision humana y no puede bloquear"


def test_solo_una_aprobacion_humana_valida_desbloquea(tmp_path):
    """La aprobacion se verifica; no basta con que un mensaje diga que aprueba."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    d = c.publicar(tipo="DECISION_REQUIRED", de="claude", para="ceo",
                   cuerpo={"pregunta": "reduzco n?"})

    c.aprobar(d, autoridad="ceo", causa="acta 2026-08-17", prueba=canal.prueba_de_autoridad_local())
    assert c.bloqueado_por(d) is False


def test_una_aprobacion_sin_prueba_de_autoridad_se_rechaza(tmp_path):
    """El silencio no aprueba, y una afirmacion tampoco (1.1:85, 1.1:93)."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    d = c.publicar(tipo="DECISION_REQUIRED", de="claude", para="ceo",
                   cuerpo={"pregunta": "reduzco n?"})

    with pytest.raises(canal.AutoridadInsuficiente):
        c.aprobar(d, autoridad="gpt", causa="me parece bien", prueba=None)
    assert c.bloqueado_por(d) is True
    # ANADIDOS 2026-08-25 por DOS mutantes SUPERVIVIENTES. Probar solo `None` dejaba sin red la parte
    # que de verdad importa: que la prueba se VERIFIQUE contra el Control Plane en vez de creerse lo
    # que dice. Sin estos casos, aceptar cualquier dict —o un sello inventado— pasaba inadvertido.
    with pytest.raises(canal.AutoridadInsuficiente):
        c.aprobar(d, autoridad="gpt", causa="x", prueba={"lo": "que sea"})
    with pytest.raises(canal.AutoridadInsuficiente):
        c.aprobar(d, autoridad="gpt", causa="x",
                  prueba={"fuente": "control_plane", "sello": "0" * 64})
    assert c.bloqueado_por(d) is True, "una prueba falsificada desbloqueo la decision"


def test_un_agente_no_puede_aprobar_su_propia_decision(tmp_path):
    """El que implementa nunca audita su propio trabajo, llevado al canal."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    d = c.publicar(tipo="DECISION_REQUIRED", de="claude", para="ceo", cuerpo={"pregunta": "x"})

    with pytest.raises(canal.AutoridadInsuficiente):
        c.aprobar(d, autoridad="claude", causa="yo mismo",
                  prueba=canal.prueba_de_autoridad_local())


# ===========================================================================
# Req. 11 -- Handoff automatico
# ===========================================================================

def test_el_handoff_se_genera_desde_el_canal_sin_intervencion(tmp_path):
    """Req. 11. El handoff deja de redactarse a mano: se deriva del log."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})

    h = c.handoff()
    assert "pendientes" in h and "ultimo_seq" in h and "bloqueos" in h


def test_el_handoff_declara_los_bloqueos_pendientes(tmp_path):
    """Req. 11. Un handoff que no dice que espera una decision es un handoff que miente."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    c.publicar(tipo="DECISION_REQUIRED", de="claude", para="ceo", cuerpo={"pregunta": "x"})

    assert c.handoff()["bloqueos"], "debe listar la decision pendiente"


# ===========================================================================
# Req. 12 y 13 -- GitHub opcional, local-first
# ===========================================================================

def test_el_canal_funciona_entero_sin_red(tmp_path):
    """Req. 13. Local-first: sin Internet el canal opera al 100 %."""
    canal = _canal()
    c = canal.abrir(tmp_path, sincronizacion_github=False)
    mid = c.publicar(tipo="TASK", de="gpt", para="claude", cuerpo={"objetivo": "x"})

    assert c.leer(mid) is not None
    assert c.handoff()["pendientes"]


def test_la_sincronizacion_con_github_es_opcional_y_su_fallo_no_rompe_el_canal(tmp_path):
    """Req. 12. GitHub es espejo, nunca fuente. Si falla, se anota y se sigue."""
    canal = _canal()
    c = canal.abrir(tmp_path, sincronizacion_github=True)
    resultado = c.sincronizar(simular_fallo_de_red=True)

    assert resultado["sincronizado"] is False
    assert resultado["canal_operativo"] is True


# ===========================================================================
# Req. 14 -- Sin secretos inventados
# ===========================================================================

def test_el_canal_no_requiere_ninguna_clave_para_operar(tmp_path):
    """Req. 14. El canal en si no autentica contra nadie: son ficheros locales."""
    canal = _canal()
    assert canal.requiere_credenciales() is False


def test_el_modulo_no_contiene_ninguna_credencial_ni_la_pide():
    """Req. 14. Ni claves inventadas, ni variables de entorno de proveedores."""
    canal = _canal()
    fuente = pathlib.Path(canal.__file__).read_text(encoding="utf-8")
    for prohibido in ("API_" + "KEY", "api_" + "key", "OPENAI_", "ANTHROPIC_" + "API"):
        assert prohibido not in fuente


# ===========================================================================
# Req. 15 -- Compatibilidad futura: Claude Code, Codex, workers locales
# ===========================================================================

def test_el_canal_es_agnostico_del_agente_que_hay_al_otro_lado(tmp_path):
    """Req. 15. Los participantes son identificadores, no tipos cableados."""
    canal = _canal()
    c = canal.abrir(tmp_path)
    for quien in ("claude-code", "gpt", "codex", "worker-local-aurora"):
        mid = c.publicar(tipo="TASK", de="orquestador", para=quien, cuerpo={"objetivo": "x"})
        assert c.leer(mid)["para"] == quien


def test_el_transporte_es_un_adaptador_sustituible():
    """Req. 15. Cambiar como llegan los mensajes no debe tocar el canal."""
    canal = _canal()
    assert hasattr(canal, "TransporteAdapter")
    assert "entregar" in dir(canal.TransporteAdapter)


def test_el_canal_declara_que_transportes_estan_disponibles_hoy():
    """INV-9: no se finge capacidad no construida.

    El transporte hacia un modelo externo NO esta disponible mientras no se resuelva la
    decision del CEO sobre claves de terceros. El canal debe declararlo, no simularlo.
    """
    canal = _canal()
    # DISPONIBILIDAD y AUTORIZACION son preguntas distintas, y fundirlas producia una
    # contradiccion entre ficheros de prueba: uno esperaba booleanos de autorizacion y otro
    # tri-estado de disponibilidad medida. Se separan.
    autorizados = canal.transportes_autorizados()
    assert autorizados["ficheros_locales"] is True
    assert autorizados["modelo_externo_via_api"] is False, (
        "declarar disponible un transporte que exige una clave no autorizada seria fingir "
        "una capacidad no construida")
