"""La pieza 19: delegar una misión acotada a un subagente (CEO, 2026-09-21).

QUÉ SE EXIGE AQUÍ, Y POR QUÉ CADA GARANTÍA TIENE SU CONTROL. Una capacidad que crea ejecutores con
autoridad prestada solo vale si se puede demostrar que **falla cerrada**: que niega por defecto y
concede por excepción. Por eso casi cada prueba negativa viene acompañada de su control positivo —
una barrera que niega siempre es indistinguible de una parálisis, y este proyecto ya pagó el
descubrir la diferencia tarde.

EL ATAQUE ES EL MÉTODO. No basta con comprobar el camino feliz: aquí se intenta romper la capacidad
a propósito —salir del sandbox con `..`, con enlaces simbólicos, reutilizar una credencial gastada,
cambiar la misión después de autorizarla, encadenar subagentes, delegar materia reservada, ignorar
`PARADA`— porque el criterio del plano es que *«ningún control de seguridad se declara operativo sin
un intento real de violación que falle»*.

LO QUE ESTAS PRUEBAS NO HACEN: no retiran `PARADA` real, no escriben fuera de `tmp_path`, no tocan
`TODO_LO_DELEGABLE` ni `_MATERIA_RESERVADA`. Todo ocurre en directorios temporales.
"""

from __future__ import annotations

import pathlib
import time

import control_plane as cp
import delegacion as dl
import orquestador as orq
import pytest
import review as rv

ACTA = "DEC-ORCH-2 del CEO"


@pytest.fixture(autouse=True)
def _el_arnes_no_esta_corriendo(monkeypatch):
    """El verificador se niega a medir con el arnés en marcha, y con razón. Aquí lo neutralizamos
    para poder ejercitar el camino real sin depender de si hay una mutación corriendo fuera."""
    monkeypatch.setattr(orq, "mutacion_en_curso", lambda: False)


def _plano(tmp_path) -> pathlib.Path:
    d = tmp_path / "plano"
    d.mkdir(exist_ok=True)
    return d


def _caja(tmp_path, con_prueba: bool = True) -> pathlib.Path:
    caja = tmp_path / "caja"
    caja.mkdir(exist_ok=True)
    if con_prueba:
        (caja / "test_demo.py").write_text("def test_suma():\n    assert 1 + 1 == 2\n",
                                           encoding="utf-8")
    return caja


def _mision(caja, **kw) -> dl.Mision:
    base = {"capacidad": "ejecutar_pruebas", "sandbox": str(caja),
            "argumentos": ("test_demo.py",), "limite_s": 60.0}
    base.update(kw)
    return dl.Mision(**base)


# ============================================================ INTEGRACIÓN: EL CICLO REAL --


def test_una_mision_minima_se_delega_ejecuta_verifica_y_revoca(tmp_path):
    """El extremo a extremo, ejecutado de verdad: no se simula ni el subagente ni su resultado."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    resultado = dl.delegar_y_ejecutar(d, _mision(caja), autoridad="ceo", acta=ACTA)

    assert resultado.ok is True, f"la mision real no salio adelante: {resultado.motivo}"
    assert resultado.evidencia["ejecutadas"] == 1, (
        "la evidencia no refleja una ejecucion real: el subagente no midio nada")
    assert resultado.evidencia["fallidas"] == 0


def test_el_resultado_se_VERIFICA_contra_el_mundo_no_se_cree(tmp_path):
    """`agentes.py` lo fija para todo el plano: *«AURA no cree al agente; verifica el efecto»*.

    Con una prueba que falla de verdad, el resultado tiene que salir `ok=False` **por medición**,
    no porque alguien lo declare."""
    d = _plano(tmp_path)
    caja = _caja(tmp_path, con_prueba=False)
    (caja / "test_rota.py").write_text("def test_falla():\n    assert False\n", encoding="utf-8")

    resultado = dl.delegar_y_ejecutar(
        d, _mision(caja, argumentos=("test_rota.py",)), autoridad="ceo", acta=ACTA)

    assert resultado.ok is False, "una bateria en rojo se reporto como sana"
    assert resultado.evidencia["fallidas"] == 1, "no se conto el fallo real"


def test_la_segunda_capacidad_construida_tambien_ejecuta_de_verdad(tmp_path):
    """`verificar_calidad` no es una entrada decorativa del catalogo: corre `ruff` real."""
    d, caja = _plano(tmp_path), _caja(tmp_path, con_prueba=False)
    (caja / "limpio.py").write_text("VALOR = 1\n", encoding="utf-8")

    resultado = dl.delegar_y_ejecutar(
        d, _mision(caja, capacidad="verificar_calidad", argumentos=("limpio.py",)),
        autoridad="ceo", acta=ACTA)

    assert resultado.ok is True, f"ruff no dio limpio sobre un fichero limpio: {resultado.evidencia}"


# ============================================================ AUTORIDAD --


def test_una_capacidad_que_NO_consta_autorizada_no_se_delega(tmp_path):
    """El corazón del módulo: **una delegación no puede conceder lo que su origen no tenía.**"""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="ejecutor construido|no consta autorizada"):
        dl.delegar(d, _mision(caja, capacidad="desplegar_a_produccion"), "ceo", ACTA)


def test_sin_ACTA_no_hay_delegacion(tmp_path):
    """*«No hay permiso, hay intencion»*: la misma regla que el resto del plano."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="acta"):
        dl.delegar(d, _mision(caja), autoridad="ceo", acta="   ")


def test_sin_AUTORIDAD_declarada_no_hay_delegacion(tmp_path):
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="autoridad"):
        dl.delegar(d, _mision(caja), autoridad="", acta=ACTA)


def test_una_credencial_CADUCADA_no_ejecuta(tmp_path, monkeypatch):
    """Lifecycle finito: una misión no se convierte en una autorización permanente."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    delegacion = dl.delegar(d, mision, "ceo", ACTA)

    monkeypatch.setattr(dl, "_ahora", lambda: time.time() + dl.VIGENCIA_S + 1)

    with pytest.raises(dl.DelegacionInvalida, match="caduc"):
        dl.ejecutar(d, delegacion, mision)


def test_una_credencial_YA_GASTADA_no_ejecuta_dos_veces(tmp_path):
    """De un solo uso. Sin esto, una autorización legítima serviría indefinidamente."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    delegacion = dl.delegar(d, mision, "ceo", ACTA)
    dl.ejecutar(d, delegacion, mision)

    with pytest.raises(dl.DelegacionInvalida, match="gasto|un solo uso"):
        dl.ejecutar(d, delegacion, mision)


def test_una_credencial_REVOCADA_no_ejecuta(tmp_path):
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    delegacion = dl.delegar(d, mision, "ceo", ACTA)
    dl.revocar(d, delegacion.id, por="ceo", motivo="me arrepiento")

    with pytest.raises(dl.DelegacionInvalida, match="revocada"):
        dl.ejecutar(d, delegacion, mision)


def test_CONTROL_una_credencial_recien_emitida_SI_ejecuta(tmp_path):
    """Sin este control, las cuatro pruebas de arriba se cumplirían con un `raise` incondicional."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)

    resultado = dl.ejecutar(d, dl.delegar(d, mision, "ceo", ACTA), mision)

    assert resultado.ok is True


# ============================================================ ESCALAMIENTO --


def test_la_mision_NO_puede_cambiar_despues_de_autorizarse(tmp_path):
    """El ataque más fino: obtener una credencial legítima para una misión inocua y usarla para
    otra. La huella ata la credencial al contenido exacto de lo que se autorizó."""
    d = _plano(tmp_path)
    caja, otra = _caja(tmp_path), tmp_path / "otra"
    otra.mkdir()
    (otra / "test_demo.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")

    autorizada = _mision(caja)
    delegacion = dl.delegar(d, autorizada, "ceo", ACTA)
    suplantada = _mision(otra)

    with pytest.raises(dl.DelegacionInvalida, match="no corresponde|cambio"):
        dl.ejecutar(d, delegacion, suplantada)


def test_un_subagente_no_puede_concederse_MAS_de_lo_que_recibio(tmp_path):
    """Fabricar a mano una credencial con otra capacidad no sirve: `ejecutar` compara contra la
    misión y la huella no cuadra."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    legitima = dl.delegar(d, mision, "ceo", ACTA)
    falsificada = dl.Delegacion(
        id=legitima.id, mision_id="otra-mision", capacidad="crear_autoridad",
        sandbox=legitima.sandbox, autoridad_origen="yo-mismo", acta="me lo concedo",
        expira_en=legitima.expira_en + 10_000, profundidad=0, huella="inventada")

    with pytest.raises(dl.DelegacionInvalida):
        dl.ejecutar(d, falsificada, mision)


# ============================================================ RECURSIÓN --


def test_un_subagente_NO_crea_otro_subagente(tmp_path):
    """La cadena tiene un eslabón. Sin esto, una misión podría abrir un árbol sin fondo."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="profundidad|subagente"):
        dl.delegar(d, _mision(caja, profundidad=dl.PROFUNDIDAD_MAXIMA), "ceo", ACTA)


def test_una_credencial_con_profundidad_excedida_no_ejecuta(tmp_path):
    """La profundidad se comprueba **también** al ejecutar: validarla solo al crear dejaría pasar
    una credencial fabricada con la profundidad ya gastada."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    legitima = dl.delegar(d, mision, "ceo", ACTA)
    profunda = dl.Delegacion(**{**dataclasses_asdict(legitima),
                                "profundidad": dl.PROFUNDIDAD_MAXIMA + 1})

    with pytest.raises(dl.DelegacionInvalida, match="profundidad"):
        dl.ejecutar(d, profunda, mision)


def dataclasses_asdict(objeto) -> dict:
    import dataclasses as _d
    return {campo.name: getattr(objeto, campo.name) for campo in _d.fields(objeto)}


def test_CONTROL_la_profundidad_inicial_SI_se_permite(tmp_path):
    d, caja = _plano(tmp_path), _caja(tmp_path)
    assert dl.delegar(d, _mision(caja, profundidad=0), "ceo", ACTA).profundidad == 1


# ============================================================ SANDBOX --


def test_un_argumento_con_PUNTOS_no_escapa_del_sandbox(tmp_path):
    """`..` no es un atajo: se resuelve antes de juzgar."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="fuera del sandbox"):
        dl.delegar(d, _mision(caja, argumentos=("../../etc/passwd",)), "ceo", ACTA)


def test_un_SYMLINK_hacia_fuera_no_concede_el_destino(tmp_path):
    """Un nombre inocente no cambia a dónde apunta: la comparación es sobre la ruta resuelta."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    fuera = tmp_path / "secreto"
    fuera.mkdir()
    (fuera / "clave.txt").write_text("x", encoding="utf-8")
    try:
        (caja / "inocente").symlink_to(fuera)
    except (OSError, NotImplementedError):
        pytest.skip("el sistema de ficheros no permite enlaces simbolicos")

    with pytest.raises(dl.MisionRechazada, match="fuera del sandbox"):
        dl.delegar(d, _mision(caja, argumentos=("inocente/clave.txt",)), "ceo", ACTA)


def test_un_sandbox_que_NO_existe_no_se_acepta(tmp_path):
    d = _plano(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="no es un directorio"):
        dl.delegar(d, dl.Mision(capacidad="ejecutar_pruebas",
                                sandbox=str(tmp_path / "fantasma")), "ceo", ACTA)


def test_al_EJECUTAR_el_sandbox_vuelve_a_comprobarse(tmp_path):
    """Comprobarlo solo al delegar dejaría una ventana entre autorizar y ejecutar."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    legitima = dl.delegar(d, mision, "ceo", ACTA)
    estrecha = dl.Delegacion(**{**dataclasses_asdict(legitima),
                                "sandbox": str(caja / "subcarpeta-inexistente")})

    with pytest.raises((dl.PerimetroViolado, dl.DelegacionInvalida)):
        dl.ejecutar(d, estrecha, mision)


def test_CONTROL_un_argumento_DENTRO_del_sandbox_si_se_concede(tmp_path):
    """Sin este control, el perímetro se cumpliría negándolo todo — parálisis, no seguridad."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    (caja / "sub").mkdir()
    (caja / "sub" / "test_hondo.py").write_text("def test_ok():\n    assert True\n",
                                                encoding="utf-8")

    resultado = dl.delegar_y_ejecutar(
        d, _mision(caja, argumentos=("sub/test_hondo.py",)), "ceo", ACTA)

    assert resultado.ok is True


# ============================================================ GOBERNANZA --


def test_la_MATERIA_RESERVADA_no_se_delega_jamas(tmp_path):
    """`D22` manda sobre todo lo demás. Se prueban **todas** las materias, no una de muestra."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    for materia in rv._MATERIA_RESERVADA:
        with pytest.raises(dl.MisionRechazada):
            dl.delegar(d, _mision(caja, capacidad=materia), "ceo", ACTA)


def test_CREAR_AUTORIDAD_sigue_siendo_indelegable(tmp_path):
    """La frontera que este módulo no cruza, dicha con su nombre.

    Delegar es prestar un permiso que ya existe; crear autoridad es inventarlo. Lo primero es lo
    que hace este módulo; lo segundo sigue reservado al CEO por `D22` y ninguna delegación lo
    alcanza."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    assert "crear_autoridad" in rv._MATERIA_RESERVADA, "la premisa de esta prueba desaparecio"

    with pytest.raises(dl.MisionRechazada, match="materia reservada|ejecutor construido"):
        dl.delegar(d, _mision(caja, capacidad="crear_autoridad"), "ceo", ACTA)


def test_una_capacidad_de_ESCRITURA_no_se_delega(tmp_path, monkeypatch):
    """El catálogo `[auto]` es de efecto lectura a propósito. Si algún día entrara una de
    escritura, esta delegación tendría que seguir negándose hasta que un acta lo dijera."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    monkeypatch.setattr(dl, "MISIONES_CONSTRUIDAS", ("ejecutar_pruebas", "escribir_cosas"))
    monkeypatch.setattr(dl, "_capacidad_autorizada",
                        lambda c: {"tipo": "escritura"} if c == "escribir_cosas" else orq.ficha_de(c))

    with pytest.raises(dl.MisionRechazada, match="lectura|escritura"):
        dl.delegar(d, _mision(caja, capacidad="escribir_cosas"), "ceo", ACTA)


def test_una_capacidad_sin_EJECUTOR_construido_se_rechaza_por_INV9(tmp_path):
    """No se finge capacidad: se dice que no existe, en vez de devolver un resultado inventado."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="INV-9|ejecutor construido"):
        dl.delegar(d, _mision(caja, capacidad="diagnosticar_estado"), "ceo", ACTA)


# ============================================================ PARADA --


def test_con_PARADA_armada_no_se_delega_nada(tmp_path):
    d, caja = _plano(tmp_path), _caja(tmp_path)
    orq.ruta_parada(d).write_text("", encoding="utf-8")

    with pytest.raises(dl.MisionRechazada, match="kill switch"):
        dl.delegar(d, _mision(caja), "ceo", ACTA)


def test_PARADA_armada_DESPUES_de_delegar_impide_ejecutar(tmp_path):
    """El caso que de verdad importa: un permiso concedido antes de que alguien pare el sistema no
    puede valer después. El subagente no participa en esta comprobación — no puede."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    delegacion = dl.delegar(d, mision, "ceo", ACTA)

    orq.ruta_parada(d).write_text("", encoding="utf-8")

    with pytest.raises(dl.DelegacionInvalida, match="kill switch"):
        dl.ejecutar(d, delegacion, mision)


def test_el_kill_switch_real_no_se_toca_desde_una_mision(tmp_path):
    """Una misión en sandbox no arma ni desarma el `PARADA` del plano real."""
    plano_real = pathlib.Path(__file__).resolve().parent
    antes = orq.ruta_parada(plano_real).exists()

    dl.delegar_y_ejecutar(_plano(tmp_path), _mision(_caja(tmp_path)), "ceo", ACTA)

    assert orq.ruta_parada(plano_real).exists() is antes, (
        "una mision delegada cambio el PARADA REAL")


# ============================================================ PRESUPUESTO Y PLAZO --


def test_una_mision_que_se_PASA_del_plazo_se_corta(tmp_path):
    """El plazo no es una sugerencia: el proceso se mata y el resultado sale `agotado`."""
    d = _plano(tmp_path)
    caja = _caja(tmp_path, con_prueba=False)
    (caja / "test_lento.py").write_text(
        "import time\n\n\ndef test_eterno():\n    time.sleep(30)\n", encoding="utf-8")

    resultado = dl.delegar_y_ejecutar(
        d, _mision(caja, argumentos=("test_lento.py",), limite_s=3.0), "ceo", ACTA)

    assert resultado.agotado is True, "la mision se paso del plazo y nadie la corto"
    assert resultado.ok is False, "una mision agotada no puede declararse correcta"


def test_tras_agotar_el_plazo_la_credencial_queda_gastada(tmp_path):
    """Agotar el plazo consume el uso. Si no lo consumiera, un timeout sería un reintento gratis."""
    d = _plano(tmp_path)
    caja = _caja(tmp_path, con_prueba=False)
    (caja / "test_lento.py").write_text(
        "import time\n\n\ndef test_eterno():\n    time.sleep(30)\n", encoding="utf-8")
    mision = _mision(caja, argumentos=("test_lento.py",), limite_s=3.0)
    delegacion = dl.delegar(d, mision, "ceo", ACTA)

    dl.ejecutar(d, delegacion, mision)

    assert dl.usos_de(d, delegacion.id) == 1
    with pytest.raises(dl.DelegacionInvalida, match="gasto|un solo uso"):
        dl.ejecutar(d, delegacion, mision)


# ============================================================ TRAZABILIDAD --


def test_el_ciclo_entero_deja_rastro_en_el_historial(tmp_path):
    """Un ciclo sin rastro no es auditable, y esta capacidad se audita o no existe.

    **Son cuatro eventos, no tres, y la diferencia es la corrección de una carrera** (2026-09-21).
    `mision_ejecutada` es la *reserva* del uso —se escribe ANTES de ejecutar, para que dos llamadas
    concurrentes no puedan gastar la misma credencial— y `mision_resuelta` es el resultado con su
    evidencia. Antes eran el mismo evento al final, y esa era exactamente la ventana por la que
    cinco ejecuciones simultáneas pasaban las cinco."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    resultado = dl.delegar_y_ejecutar(d, _mision(caja), "ceo", ACTA)

    tipos = [e["tipo"] for e in dl.historial_de(d, resultado.delegacion_id)]
    assert tipos == ["mision_delegada", "mision_ejecutada", "mision_resuelta",
                     "delegacion_revocada"], f"el rastro esta incompleto o desordenado: {tipos}"


def test_el_rastro_dice_QUIEN_autorizo_QUE_y_CON_QUE_ACTA(tmp_path):
    """«Se delegó algo» no es un informe: sin identidad ni acta, el evento no se puede auditar."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    delegacion = dl.delegar(d, _mision(caja), autoridad="ceo", acta=ACTA)

    datos = [e for e in cp.leer_eventos(d) if e["tipo"] == "mision_delegada"][-1]["datos"]
    assert datos["autoridad_origen"] == "ceo"
    assert datos["acta"] == ACTA
    assert datos["capacidad"] == "ejecutar_pruebas"
    assert datos["delegacion"] == delegacion.id


def test_una_mision_RECHAZADA_tambien_deja_rastro(tmp_path):
    """Lo negado se registra igual que lo concedido: un rechazo silencioso es indistinguible de
    que nadie lo intentara, y saber quién intentó qué es media auditoría."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada):
        dl.delegar(d, _mision(caja, capacidad="crear_autoridad"), "ceo", ACTA)

    rechazos = [e for e in cp.leer_eventos(d) if e["tipo"] == "mision_rechazada"]
    assert rechazos, "se nego una mision sin dejar constancia"
    assert rechazos[-1]["datos"]["capacidad"] == "crear_autoridad"


def test_el_historial_de_delegacion_no_ROMPE_la_cadena_del_log(tmp_path):
    """Esta capacidad escribe en el log encadenado: si lo corrompiera, ADR-0023 quedaría tocado."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    dl.delegar_y_ejecutar(d, _mision(caja), "ceo", ACTA)

    assert cp.verificar_integridad_log(d)["integro"] is True, (
        "las escrituras de la delegacion rompieron la cadena del historial")


# ============================================================ NO CONCEDE NADA --


def test_los_eventos_de_delegacion_NO_son_eventos_gobernados(tmp_path):
    """Son trazabilidad, no autoridad. Gobernarlos sería confundir informar con permitir."""
    for evento in (dl._EVENTO_DELEGADA, dl._EVENTO_EJECUTADA, dl._EVENTO_RESULTADO,
                   dl._EVENTO_RECHAZADA, dl._EVENTO_REVOCADA):
        assert evento not in cp.EVENTOS_GOBERNADOS


def test_la_capacidad_no_amplia_TODO_LO_DELEGABLE_ni_la_materia_reservada(tmp_path):
    """El control de que este módulo no movió ninguna frontera al construirse."""
    assert rv.TODO_LO_DELEGABLE == ("eliminar_codigo_muerto", "implementar_incremento_especificado")
    assert "crear_autoridad" in rv._MATERIA_RESERVADA
    assert len(orq._INTOCABLES) == 8


# ============================================================ CADA GUARDIA, AISLADO --
#
# Los mutantes `DL-M3` y `DL-M4` SOBREVIVIERON la primera vez, y no porque el código estuviera mal:
# porque las pruebas no llegaban hasta ellos. `crear_autoridad` y `desplegar_a_produccion` tampoco
# constan en `MISIONES_CONSTRUIDAS`, así que la puerta de `INV-9` las rechazaba antes y la puerta
# que se quería medir nunca se ejercía. **Dos guardias cubriéndose el uno al otro dan un falso
# verde**: si uno cae, el otro tapa el hueco y nadie se entera hasta que caen los dos.
#
# Se aíslan montando el escenario exacto en que solo queda en pie el guardia bajo prueba.


def test_AISLADO_la_materia_reservada_manda_aunque_la_capacidad_este_construida(tmp_path,
                                                                                monkeypatch):
    """`D22` se comprueba ANTES que nada y no depende de que otra puerta cubra el caso.

    Se fabrica el peor escenario posible: una capacidad **construida** y **autorizada en la
    política** que además es materia reservada. Si `D22` no mandara, pasaría."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    reservada = rv._MATERIA_RESERVADA[0]
    monkeypatch.setattr(dl, "MISIONES_CONSTRUIDAS", (*dl.MISIONES_CONSTRUIDAS, reservada))
    monkeypatch.setattr(dl, "_capacidad_autorizada", lambda c: {"tipo": "lectura"})

    with pytest.raises(dl.MisionRechazada, match="materia reservada"):
        dl.delegar(d, _mision(caja, capacidad=reservada), "ceo", ACTA)


def test_AISLADO_una_capacidad_CONSTRUIDA_pero_sin_autorizar_no_se_delega(tmp_path, monkeypatch):
    """Tener ejecutor no es tener permiso.

    Aquí la capacidad está construida y no es materia reservada: el único guardia que queda en pie
    es el que comprueba que el CEO la autorizó en la política. Si cayera, la capacidad prestaría
    algo que su origen nunca tuvo — que es exactamente lo que este módulo promete no hacer."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    monkeypatch.setattr(dl, "MISIONES_CONSTRUIDAS", (*dl.MISIONES_CONSTRUIDAS, "capacidad_fantasma"))
    monkeypatch.setattr(dl, "_capacidad_autorizada", lambda c: {})

    with pytest.raises(dl.MisionRechazada, match="no consta autorizada"):
        dl.delegar(d, _mision(caja, capacidad="capacidad_fantasma"), "ceo", ACTA)


def test_CONTROL_con_los_dos_guardias_satisfechos_la_delegacion_SI_se_concede(tmp_path):
    """El control de las dos de arriba: si negaran siempre, serían parálisis y no barreras."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    delegacion = dl.delegar(d, _mision(caja), "ceo", ACTA)

    assert delegacion.capacidad == "ejecutar_pruebas"
    assert delegacion.acta == ACTA


# ============================================================ INYECCIÓN DE OPCIONES --
#
# ESTO NACIÓ DE UN ATAQUE QUE FUNCIONÓ (2026-09-21). Los argumentos de la misión se pasaban tal cual
# a la línea de órdenes de la herramienta, y `ruff` —como casi todas— interpreta como **opción** lo
# que empieza por `-`. Una misión con el argumento `--exit-zero` devolvía `ok=True, codigo=0` sobre
# un árbol sucio: la capacidad declaraba «calidad verificada» sin haber verificado nada.
#
# El perímetro no lo veía, y el porqué es lo instructivo: `caja / "--exit-zero"` es nominalmente una
# ruta **dentro** del sandbox. Comprobar la contención no basta si lo que pasa por ahí nunca fue una
# ruta.


@pytest.mark.parametrize("veneno", ["--exit-zero", "--help", "--config=/etc/x", "-p", "--version"])
def test_un_argumento_que_parece_OPCION_no_se_acepta(tmp_path, veneno):
    """Una misión no compone la línea de órdenes de la herramienta. Nunca."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="OPCION|opcion"):
        dl.delegar(d, _mision(caja, capacidad="verificar_calidad", argumentos=(veneno,)),
                   "ceo", ACTA)


def test_el_ataque_EXACTO_que_funciono_ya_no_declara_limpio_lo_sucio(tmp_path):
    """La regresión del incidente, con su medición.

    Antes: `--exit-zero` sobre un árbol sucio devolvía `ok=True`. Ahora se rechaza al delegar, y la
    misma carpeta medida **de verdad** sale sucia. Las dos mitades importan: que el ataque no pase,
    y que la medición honesta siga detectando el problema real."""
    d, caja = _plano(tmp_path), _caja(tmp_path, con_prueba=False)
    (caja / "sucio.py").write_text("import os\n", encoding="utf-8")   # import sin usar

    with pytest.raises(dl.MisionRechazada):
        dl.delegar(d, _mision(caja, capacidad="verificar_calidad", argumentos=("--exit-zero",)),
                   "ceo", ACTA)

    honesta = dl.delegar_y_ejecutar(
        d, _mision(caja, capacidad="verificar_calidad", argumentos=("sucio.py",)), "ceo", ACTA)
    assert honesta.ok is False, (
        "la medicion honesta declaro limpio un fichero con un import sin usar: si esto pasara, "
        "bloquear el ataque no serviria de nada")


def test_un_argumento_que_NO_EXISTE_no_se_acepta(tmp_path):
    """Una ruta que no existe no es trabajo: o es un error, o es un intento de que la herramienta
    la interprete de otra manera."""
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="no existe"):
        dl.delegar(d, _mision(caja, argumentos=("fantasma.py",)), "ceo", ACTA)


def test_un_argumento_con_BYTE_NULO_no_se_acepta(tmp_path):
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="byte nulo|no es una ruta"):
        dl.delegar(d, _mision(caja, argumentos=("test_demo.py\x00.txt",)), "ceo", ACTA)


def test_un_argumento_VACIO_no_se_acepta(tmp_path):
    d, caja = _plano(tmp_path), _caja(tmp_path)

    with pytest.raises(dl.MisionRechazada, match="vacio|no es una ruta"):
        dl.delegar(d, _mision(caja, argumentos=("   ",)), "ceo", ACTA)


def test_una_ruta_ABSOLUTA_fuera_del_sandbox_no_se_acepta(tmp_path):
    """En Python `Path("/caja") / "/etc/passwd"` es `/etc/passwd`: la barra inicial descarta la
    base. La comprobación se hace sobre el resultado final, que es lo que salva el caso."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    fuera = tmp_path / "secreto"
    fuera.mkdir()
    (fuera / "test_robado.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")

    with pytest.raises(dl.MisionRechazada, match="fuera del sandbox"):
        dl.delegar(d, _mision(caja, argumentos=(str(fuera / "test_robado.py"),)), "ceo", ACTA)


# ============================================================ CADA CAPA DEL FILTRO, AISLADA --
#
# `DL-M17` y `DL-M19` SOBREVIVIERON la primera vez, y otra vez no por culpa del código: un fichero
# llamado `--exit-zero` no existe, así que la comprobación de existencia lo rechazaba antes y la
# comprobación que se quería medir nunca llegaba a ejercerse. **La defensa en profundidad tiene ese
# precio**: cada capa tapa a la siguiente, y hay que desnudarlas de una en una para saber si cada
# una sostiene su parte.


def test_AISLADO_un_argumento_que_parece_opcion_se_rechaza_AUNQUE_EXISTA(tmp_path):
    """El guardia de la opción, a solas.

    Se crea un fichero que **de verdad se llama** `--exit-zero`, así que la comprobación de
    existencia queda satisfecha y el único que puede negarlo es el que mira si parece una opción.
    """
    d, caja = _plano(tmp_path), _caja(tmp_path)
    trampa = caja / "--exit-zero"
    trampa.write_text("", encoding="utf-8")
    assert trampa.exists(), "el montaje exige que el fichero trampa exista de verdad"

    with pytest.raises(dl.MisionRechazada, match="OPCION|opcion"):
        dl.delegar(d, _mision(caja, capacidad="verificar_calidad",
                              argumentos=("--exit-zero",)), "ceo", ACTA)


def test_AISLADO_el_separador_protege_aunque_el_primer_filtro_caiga(tmp_path, monkeypatch):
    """La segunda capa, ejercida con la primera desactivada a propósito.

    Es la única forma honesta de comprobar una defensa en profundidad: si la primera capa siempre
    actúa, la segunda nunca se ejerce y su garantía es una suposición. Aquí se neutraliza el filtro
    de argumentos y se comprueba que `--` sigue impidiendo que `--exit-zero` se interprete como
    opción — con un fichero sucio al lado cuyo error **tiene** que seguir apareciendo.
    """
    d, caja = _plano(tmp_path), _caja(tmp_path, con_prueba=False)
    (caja / "--exit-zero").write_text("", encoding="utf-8")
    (caja / "sucio.py").write_text("import os\n", encoding="utf-8")
    monkeypatch.setattr(dl, "_exigir_ruta_de_verdad", lambda *a, **k: None)

    resultado = dl.delegar_y_ejecutar(
        d, _mision(caja, capacidad="verificar_calidad",
                   argumentos=("--exit-zero", "sucio.py")), "ceo", ACTA)

    assert resultado.ok is False, (
        "`--exit-zero` se coló como OPCION pese al separador `--`: ruff salio limpio sobre un "
        "fichero con un import sin usar")


# ============================================================ LAS TRES QUE UNA AUDITORÍA ROMPIÓ --
#
# Una auditoría adversarial independiente (2026-09-21) atacó esta capacidad y **tres ataques
# funcionaron**. Estas pruebas son esos mismos ataques, ahora fijados. Se conservan con su nombre
# porque una regresión aquí no sería un fallo cualquiera: sería reabrir una vía de escalada que ya
# se demostró explotable.


def test_ATAQUE_una_credencial_FABRICADA_a_mano_no_ejecuta(tmp_path):
    """`Delegacion` es un `dataclass` sin firma: cualquiera puede construir uno bien formado.

    El ataque original construía una credencial a mano, con `huella` calculada de campos públicos,
    y `ejecutar` la aceptaba porque solo comprobaba su consistencia **interna**. Una credencial que
    se valida a sí misma no valida nada.

    La defensa no es criptográfica: es `ADR-0023`. El historial es la única fuente de verdad, y una
    credencial que no consta emitida en él no existe."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    fabricada = dl.Delegacion(
        id="credencial-inventada-a-mano", mision_id=mision.id, capacidad="ejecutar_pruebas",
        sandbox=str(caja.resolve()), autoridad_origen="nadie-en-particular",
        acta="ninguna-acta-real", expira_en=time.time() + 999_999, profundidad=1,
        huella=mision.id)
    assert dl.historial_de(d, fabricada.id) == [], "el montaje exige que NO conste emitida"

    with pytest.raises(dl.DelegacionInvalida, match="no consta emitida"):
        dl.ejecutar(d, fabricada, mision)


def test_ATAQUE_una_credencial_caducada_no_se_RESUCITA_cambiandole_la_fecha(tmp_path):
    """`dataclasses.replace(caducada, expira_en=...)` la revivía. Ahora la caducidad que manda es
    la que quedó **escrita al emitirla**, no la que traiga el objeto."""
    import dataclasses
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    legitima = dl.delegar(d, mision, "ceo", ACTA)
    resucitada = dataclasses.replace(legitima, expira_en=time.time() + 999_999)

    with pytest.raises(dl.DelegacionInvalida, match="caducidad|no coincide"):
        dl.ejecutar(d, resucitada, mision)


def test_ATAQUE_no_se_puede_subir_la_PROFUNDIDAD_de_una_credencial_legitima(tmp_path):
    """Mismo vector por otro campo: lo que decide es el hecho registrado."""
    import dataclasses
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    legitima = dl.delegar(d, mision, "ceo", ACTA)
    manipulada = dataclasses.replace(legitima, profundidad=0)

    with pytest.raises(dl.DelegacionInvalida, match="profundidad|no coincide"):
        dl.ejecutar(d, manipulada, mision)


def test_ATAQUE_un_proceso_YA_DELEGADO_no_puede_pedir_otra_mision(tmp_path, monkeypatch):
    """La recursión real, que la cota no veía.

    `Mision.profundidad` la declara quien construye la misión, así que el código que corría dentro
    de una misión hacía `import delegacion` y pedía otra con `profundidad=0`. La comprobación
    funcionaba y no servía de nada: el dato en el que confiaba se lo daba el atacante.

    Ahora la profundidad viaja **en el entorno del proceso** y se hereda. Aquí se simula estar
    dentro de una misión poniendo la marca, que es exactamente lo que el subproceso recibe."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    monkeypatch.setenv(dl._VAR_PROFUNDIDAD, str(dl.PROFUNDIDAD_MAXIMA))
    monkeypatch.setenv(dl._VAR_EN_CURSO, "la-mision-del-padre")

    with pytest.raises(dl.MisionRechazada, match="profundidad|subagente"):
        dl.delegar(d, _mision(caja, profundidad=0), "subagente-nieto", "acta-fabricada-por-el-hijo")


def test_una_marca_de_profundidad_CORRUPTA_no_concede(tmp_path, monkeypatch):
    """Ante la duda, roja: un valor ilegible se trata como «ya estamos dentro», no como cero."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    monkeypatch.setenv(dl._VAR_PROFUNDIDAD, "no-es-un-numero")

    with pytest.raises(dl.MisionRechazada, match="profundidad|subagente"):
        dl.delegar(d, _mision(caja), "ceo", ACTA)


def test_CONTROL_sin_marca_de_profundidad_la_delegacion_SI_se_concede(tmp_path, monkeypatch):
    """Sin este control, las dos de arriba se cumplirían negando siempre."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    monkeypatch.delenv(dl._VAR_PROFUNDIDAD, raising=False)

    assert dl.delegar(d, _mision(caja), "ceo", ACTA).profundidad == 1


def test_ATAQUE_dos_ejecuciones_CONCURRENTES_no_gastan_la_misma_credencial(tmp_path):
    """La carrera medida: cinco hilos pasaban los cinco la comprobación de «no gastada».

    El `flock` de `registrar_evento` protege la escritura puntual, no el ciclo
    comprobar → ejecutar → consumir. Ahora la reserva se escribe **antes** de ejecutar y el
    desempate lo hace el `seq` del log, que es monotónico: gana uno y solo uno."""
    import concurrent.futures as futuros

    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    delegacion = dl.delegar(d, mision, "ceo", ACTA)

    def intentar():
        try:
            dl.ejecutar(d, delegacion, mision)
            return "ejecuto"
        except dl.DelegacionInvalida:
            return "rechazado"

    with futuros.ThreadPoolExecutor(max_workers=5) as piscina:
        salidas = list(piscina.map(lambda _: intentar(), range(5)))

    assert salidas.count("ejecuto") == 1, (
        f"una credencial de un solo uso se gasto {salidas.count('ejecuto')} veces: {salidas}")
    assert salidas.count("rechazado") == 4


# ============================================================ LAS CAPAS REDUNDANTES, AISLADAS --
#
# Tras cerrar la carrera quedaron DOS mecanismos para el uso único: la comprobación previa
# (`usos_de >= 1`, en `vigente`) y el desempate por `seq` (en `ejecutar`). Cada uno tapa al otro, y
# por eso sus mutantes sobrevivían: quitar cualquiera de los dos dejaba el otro haciendo el trabajo.
#
# La redundancia es deliberada, pero **cada capa tiene que sostener su parte o sobra**. Aisladas,
# resulta que protegen cosas distintas: el desempate impide la segunda ejecución; la comprobación
# previa impide **escribir una reserva inútil** en un log que es append-only y no se puede limpiar.


def test_AISLADO_una_credencial_gastada_no_ensucia_el_log_con_otra_reserva(tmp_path):
    """Lo que de verdad aporta la comprobación previa de `vigente`.

    Sin ella, el segundo intento igualmente no ejecuta —el desempate por `seq` lo para—, pero deja
    escrita una reserva que nadie va a usar. En un log **append-only** eso no se limpia: cada
    reintento perdido queda ahí para siempre, y el conteo de usos deja de leerse de un vistazo."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    delegacion = dl.delegar(d, mision, "ceo", ACTA)
    dl.ejecutar(d, delegacion, mision)
    reservas_tras_el_primero = dl.usos_de(d, delegacion.id)

    with pytest.raises(dl.DelegacionInvalida):
        dl.ejecutar(d, delegacion, mision)

    assert dl.usos_de(d, delegacion.id) == reservas_tras_el_primero, (
        "el intento rechazado dejo una reserva inutil en un log que no se puede limpiar")


def test_AISLADO_el_desempate_por_seq_decide_cuando_la_comprobacion_previa_no_ve_nada(tmp_path,
                                                                                      monkeypatch):
    """El desempate, con la capa de arriba desactivada a propósito.

    Es la única forma honesta de medirlo: mientras `usos_de` mire, el desempate nunca decide nada.
    Aquí se neutraliza el conteo previo y se comprueba que el `seq` sigue dejando pasar a uno solo."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    delegacion = dl.delegar(d, mision, "ceo", ACTA)
    dl.ejecutar(d, delegacion, mision)
    monkeypatch.setattr(dl, "usos_de", lambda *a, **k: 0)

    with pytest.raises(dl.DelegacionInvalida, match="reservo antes|un solo uso"):
        dl.ejecutar(d, delegacion, mision)


def test_AISLADO_una_credencial_con_profundidad_por_encima_del_maximo_no_ejecuta(tmp_path,
                                                                                 monkeypatch):
    """La rama defensiva de `vigente`, que por vía legítima es inalcanzable.

    `delegar` nunca emite una profundidad mayor que el máximo, así que esta comprobación solo actúa
    si alguien fabrica la credencial o si el máximo baja. Se ejerce bajando el máximo después de
    emitirla, que es el escenario realista: **la cota se endurece y las credenciales ya emitidas
    tienen que dejar de valer**, no seguir corriendo con la cota vieja."""
    d, caja = _plano(tmp_path), _caja(tmp_path)
    mision = _mision(caja)
    delegacion = dl.delegar(d, mision, "ceo", ACTA)
    monkeypatch.setattr(dl, "PROFUNDIDAD_MAXIMA", 0)

    ok, motivo = dl.vigente(d, delegacion)

    assert ok is False and "profundidad" in motivo, (
        f"una credencial por encima de la cota vigente se declaro utilizable: {motivo!r}")
