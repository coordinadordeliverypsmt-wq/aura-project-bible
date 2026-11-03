"""RED · la **consola de observabilidad**: mirar a AURA sin tocarla.

El motor ya trabaja solo. Lo que falta no es capacidad: es que un humano pueda preguntar «¿qué estás
haciendo?» y obtener una respuesta que sea **verdad**. Y la forma en que una consola miente no es
inventándose una frase — es mucho más sutil:

| La mentira | Cómo aparece |
|---|---|
| **contar despertares como trabajo** | el cron despertó 61 veces ⇒ «61 trabajos» |
| **contar un `0` que nadie midió** | el campo no existía y se rellenó con cero |
| **dar por ejecutado lo autorizado** | hubo veredicto favorable, luego se hizo |
| **dar por ejecutado lo intentado** | hay `cambio_aplicado`, luego hubo efecto |
| **resolver en silencio** | `estado.json` dice A, el log dice B, se enseña A |
| **enseñar un ciclo viejo** | el último cerrado no es el último que hubo |

Todas comparten la misma raíz: **rellenar un hueco en vez de declararlo**. Por eso la regla central de
este fichero es una sola, y se prueba muchas veces:

> Si el dato no está en la fuente, la respuesta es `NO DISPONIBLE`. Nunca `0`, nunca «ninguno», nunca
> una estimación razonable.

Y una regla negativa, que se comprueba en el **código** y no en el comportamiento: la consola no puede
escribir. Ni el log, ni el estado, ni el árbol. Ni siquiera indirectamente — `descubrimiento.descubrir`
registra un evento, así que una consola que descubriera para «enseñar la cola» estaría escribiendo en
el historial cada vez que alguien la mira.
"""

from __future__ import annotations

import ast
import json
import pathlib

import datetime as dt

import control_plane as cp
import observatorio as obs
import orquestador as orq

ND = "NO DISPONIBLE"


# ============================================================ ayudas --

def _despertar(d, **datos):
    cp.registrar_evento(d, "aura_despertada", {"tope": 3, "resultado": "cola agotada",
                                               "ejecutadas": 0, "actos_humanos": 0, **datos})


def _ciclo(d, *, encontradas=0, por_clase=None, ejecutadas=0, bloqueadas=0, elevadas=0,
           motivo="cola agotada", cerrar=True):
    """Un ciclo del motor tal y como lo escribe `motor_autonomia`: abre, descubre y cierra."""
    cp.registrar_evento(d, "motor_iniciado", {"raiz": str(d), "review": True, "tope": 3})
    cp.registrar_evento(d, "descubrimiento_realizado", {
        "encontradas": encontradas, "fuentes": ["codigo_muerto"], "fuentes_con_error": [],
        "por_clase": por_clase or {"OPORTUNIDAD_REAL": 0, "BLOQUEADA": bloqueadas,
                                   "DECISION_REQUIRED": elevadas, "FALSO_HUECO": 0},
        "raiz": str(d)})
    if cerrar:
        cp.registrar_evento(d, "ciclo_detenido", {"ejecutadas": ejecutadas, "bloqueadas": bloqueadas,
                                                  "elevadas": elevadas, "motivo": motivo,
                                                  "detenida_en": None})


def _ciclo_con_trabajo(d, ident, fichero, simbolo, **kwargs):
    """Un trabajo **dentro de su ciclo**, que es la unica forma en que ocurre de verdad.

    Un `cambio_aplicado` suelto, sin `motor_iniciado` que lo enmarque, no pertenece a ningun ciclo —y
    el observatorio no debe adoptarlo: sería inventarle una procedencia."""
    cp.registrar_evento(d, "motor_iniciado", {"raiz": str(d), "review": True, "tope": 3})
    _trabajo_real(d, ident, fichero, simbolo, **kwargs)
    cp.registrar_evento(d, "ciclo_detenido", {"ejecutadas": 1, "bloqueadas": 0, "elevadas": 0,
                                              "motivo": "cola agotada", "detenida_en": None})


def _trabajo_real(d, ident, fichero, simbolo, *, efecto=True, sana=True, revertido=False):
    """El circuito completo de un trabajo: se propone, se autoriza y se aplica con efecto."""
    cp.registrar_evento(d, "propuesta_registrada", {
        "id": ident, "fichero": fichero, "simbolo": simbolo, "forma": "funcion",
        "estado": "PROPUESTA", "autorizada": False, "linea": None, "motivo": "bajo REVIEW"})
    cp.registrar_evento(d, "propuesta_autorizada", {
        "id": ident, "autorizada_por": "REVIEW:auditor", "acta": "acta del CEO"})
    cp.registrar_evento(d, "cambio_aplicado", {
        "id": ident, "fichero": fichero, "simbolo": simbolo, "autoridad": "orquestador",
        "efecto_verificado": efecto, "verificacion_sana": sana, "revertido": revertido})


# ============================================================ NO ESCRIBE — garantía negativa --

def test_el_observatorio_NO_PUEDE_escribir():
    """Comprobado en el código, no en el comportamiento: una consola que solo *resulta* que hoy no
    escribe volverá a escribir en cuanto alguien le añada una comodidad."""
    arbol = ast.parse(pathlib.Path(obs.__file__).read_text(encoding="utf-8"))
    llamadas = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    llamadas |= {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    for prohibido in ("registrar_evento", "transicion", "guardar", "actualizar_estado",
                      "completar_tarea", "fijar_estado_tarea", "write_text", "write_bytes",
                      "unlink", "mkdir", "rename", "trabajar", "despertar", "ejecutar"):
        assert prohibido not in llamadas, f"la consola observa: no {prohibido}"


def test_el_observatorio_NO_DESCUBRE_para_ensenar_la_cola():
    """`descubrimiento.descubrir` **registra un evento**. Una consola que descubriera para mostrar la
    cola escribiría en el historial cada vez que un humano la mira — y el historial dejaría de ser el
    registro de lo que hizo AURA para ser también el de quién la estuvo observando."""
    arbol = ast.parse(pathlib.Path(obs.__file__).read_text(encoding="utf-8"))
    importados = {a.name.split(".")[0] for n in ast.walk(arbol)
                  if isinstance(n, ast.Import) for a in n.names}
    importados |= {n.module.split(".")[0] for n in ast.walk(arbol)
                   if isinstance(n, ast.ImportFrom) and n.module}
    for prohibido in ("descubrimiento", "planificador", "motor_autonomia", "despertador",
                      "autoconstruccion", "agentes"):
        assert prohibido not in importados, (
            f"observar no es trabajar: importar {prohibido} pone a la consola a hacer el trabajo "
            f"que estaba mirando")


def test_mirar_NO_DEJA_RASTRO(tmp_path):
    """La comprobación de comportamiento que acompaña a la del código: mirar tres veces no añade ni
    una línea al log ni toca el estado."""
    _ciclo(tmp_path, encontradas=3, bloqueadas=3)
    antes = cp.ruta_eventos(tmp_path).read_bytes()
    obs.estado(tmp_path)
    obs.historial(tmp_path)
    obs.ultimo(tmp_path)
    assert cp.ruta_eventos(tmp_path).read_bytes() == antes, "observar no escribe"


# ============================================================ CICLO ≠ TRABAJO --

def test_un_DESPERTAR_no_es_un_CICLO_y_un_CICLO_no_es_TRABAJO(tmp_path):
    """La confusión más cara de todas. El cron despertó a AURA 61 veces y AURA no hizo nada en
    ninguna: si la consola contara despertares como trabajo, el informe diría que AURA trabajó 61
    veces sin haber tocado un solo fichero."""
    for _ in range(3):
        _ciclo(tmp_path)
        _despertar(tmp_path)
    informe = obs.estado(tmp_path)
    assert informe["despertares"] == 3
    assert informe["ciclos"] == 3
    assert informe["trabajo_ejecutado"] == 0, "ningún ciclo produjo efecto: no hubo trabajo"


def test_un_despertar_RECHAZADO_no_es_un_ciclo(tmp_path):
    """El kill switch o el arnés impidieron arrancar. Hubo un despertar, y no hubo ciclo."""
    cp.registrar_evento(tmp_path, "despertar_rechazado", {"motivo": "kill switch activado", "tope": 3})
    informe = obs.estado(tmp_path)
    assert informe["despertares"] == 1 and informe["ciclos"] == 0


# ============================================================ EJECUTADO EXIGE EVIDENCIA --

def test_AUTORIZADO_no_es_EJECUTADO(tmp_path):
    """Un veredicto favorable dice que se *podía* hacer, no que se hiciera. El circuito puede pararse
    justo después: kill switch, cuota, o el ejecutor falla."""
    cp.registrar_evento(tmp_path, "propuesta_registrada", {
        "id": "P-1", "fichero": "x.py", "simbolo": "_m", "forma": "funcion",
        "estado": "PROPUESTA", "autorizada": False, "linea": None, "motivo": "bajo REVIEW"})
    cp.registrar_evento(tmp_path, "propuesta_autorizada", {
        "id": "P-1", "autorizada_por": "REVIEW:auditor", "acta": "acta"})
    informe = obs.estado(tmp_path)
    assert informe["trabajo_autorizado"] == 1
    assert informe["trabajo_ejecutado"] == 0, "autorizar no es ejecutar"


def test_APLICADO_SIN_EFECTO_VERIFICADO_no_es_EJECUTADO(tmp_path):
    """Y ésta es la trampa fina: existe el `cambio_aplicado`, luego «se hizo». Pero el propio evento
    lleva el veredicto del efecto, y si dice que no se verificó, lo que consta es un intento."""
    _trabajo_real(tmp_path, "P-1", "x.py", "_m", efecto=False)
    assert obs.estado(tmp_path)["trabajo_ejecutado"] == 0


def test_una_VERIFICACION_INSANA_no_acredita_efecto(tmp_path):
    """`verificacion_sana=False` significa que la comprobación no era capaz de fallar. Un efecto
    «verificado» por una verificación que no verifica no está verificado — es el falso PASS que este
    proyecto ya pagó cuatro veces."""
    _trabajo_real(tmp_path, "P-1", "x.py", "_m", efecto=True, sana=False)
    assert obs.estado(tmp_path)["trabajo_ejecutado"] == 0


def test_lo_REVERTIDO_no_cuenta_como_trabajo(tmp_path):
    """Se aplicó y se deshizo. El árbol quedó como estaba: contarlo sería contar un efecto que ya no
    existe."""
    _trabajo_real(tmp_path, "P-1", "x.py", "_m", revertido=True)
    assert obs.estado(tmp_path)["trabajo_ejecutado"] == 0


def test_lo_BLOQUEADO_y_lo_ELEVADO_no_cuentan_como_ejecutado(tmp_path):
    """Seis bloqueadas y dos elevadas es exactamente el estado real de AURA hoy. Ninguna es trabajo
    hecho: son trabajo que no se pudo hacer y trabajo que espera una firma."""
    _ciclo(tmp_path, encontradas=8, bloqueadas=6, elevadas=2)
    informe = obs.estado(tmp_path)
    assert informe["trabajo_bloqueado"] == 6
    assert informe["trabajo_elevado"] == 2
    assert informe["trabajo_ejecutado"] == 0


# ============================================================ NO FABRICAR --

def test_sin_HISTORIAL_no_se_inventa_un_estado(tmp_path):
    """Un log vacío no es «AURA está esperando»: es «no consta nada». Decir ESPERANDO sería afirmar
    algo sobre un sistema del que no se sabe nada."""
    informe = obs.estado(tmp_path)
    assert informe["estado"] == ND
    for campo in ("ultimo_ciclo", "hora_ultimo_ciclo", "ultima_tarea"):
        assert informe[campo] == ND, f"{campo} sin fuente tiene que decirlo"


def test_un_CAMPO_AUSENTE_no_se_rellena_con_cero(tmp_path):
    """La mentira silenciosa: el ciclo no registró `ejecutadas`, y el informe dice 0. Cero es una
    medición; ausente es la falta de una. No son lo mismo y no pueden verse igual."""
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "tope": 3})
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"motivo": "cola agotada"})
    ultimo = obs.ultimo(tmp_path)
    assert ultimo["ejecutadas"] == ND, "un hueco se declara, no se rellena"
    assert ultimo["bloqueadas"] == ND
    # Y el contraste que impide que la regla degenere en «ante la duda, NO DISPONIBLE»: los actos
    # humanos **si** se pueden medir aunque el cierre no los anotara, porque se cuentan del rango de
    # eventos del propio ciclo. Un hueco se declara; un dato derivable se deriva.
    assert ultimo["actos_humanos"] == 0


def test_un_CERO_MEDIDO_se_distingue_de_un_hueco(tmp_path):
    """El control de la prueba anterior: si todo saliera `NO DISPONIBLE` la garantía sería trivial."""
    _ciclo(tmp_path, ejecutadas=0)
    assert obs.ultimo(tmp_path)["ejecutadas"] == 0


def test_sin_TAREAS_no_se_inventa_una_ultima_tarea(tmp_path):
    _ciclo(tmp_path)
    assert obs.estado(tmp_path)["ultima_tarea"] == ND


def test_las_PRUEBAS_ASOCIADAS_solo_aparecen_si_constan(tmp_path):
    """El CEO las pidió «cuando existan». Hoy no consta ningún `criterio_verificado` en el historial
    real, y la respuesta correcta a eso es decirlo — no enseñar la batería del proyecto como si fuera
    la prueba de esa tarea concreta."""
    _ciclo_con_trabajo(tmp_path, "P-1", "x.py", "_m")
    assert obs.ultimo(tmp_path)["tareas_ejecutadas"][0]["pruebas"] == ND


# ============================================================ EL ÚLTIMO ES EL ÚLTIMO --

def test_ULTIMO_es_el_ultimo_y_no_el_ultimo_INTERESANTE(tmp_path):
    """Tentación real: el último ciclo no hizo nada, y el anterior sí. Enseñar el anterior «porque
    tiene más contenido» convierte el informe en una selección editorial."""
    _ciclo(tmp_path, ejecutadas=1, motivo="cola agotada")
    _trabajo_real(tmp_path, "P-1", "x.py", "_m")
    _ciclo(tmp_path, ejecutadas=0, motivo="cola agotada")
    ultimo = obs.ultimo(tmp_path)
    assert ultimo["ejecutadas"] == 0
    assert ultimo["tareas_ejecutadas"] == [], "ese trabajo fue del ciclo anterior"


def test_el_trabajo_se_atribuye_AL_CICLO_EN_QUE_OCURRIO(tmp_path):
    """El control del anterior: dentro de su ciclo, el trabajo sí aparece."""
    _ciclo(tmp_path, ejecutadas=0)
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "tope": 3})
    _trabajo_real(tmp_path, "P-1", "x.py", "_m")
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 1, "bloqueadas": 0,
                                                     "elevadas": 0, "motivo": "cola agotada"})
    ultimo = obs.ultimo(tmp_path)
    assert [t["simbolo"] for t in ultimo["tareas_ejecutadas"]] == ["_m"]
    assert ultimo["tareas_ejecutadas"][0]["fichero"] == "x.py"


def test_un_ciclo_ABIERTO_no_se_da_por_cerrado(tmp_path):
    """Arrancó y no consta que terminara. Puede estar corriendo o puede haber muerto; lo que **no**
    puede es aparecer como un ciclo limpio."""
    _ciclo(tmp_path, cerrar=False)
    informe = obs.estado(tmp_path)
    assert informe["estado"] == "TRABAJANDO"
    assert obs.ultimo(tmp_path)["motivo_de_parada"] == ND


# ============================================================ HUMANO ≠ AUTÓNOMO --

def test_un_acto_HUMANO_no_se_cuenta_como_trabajo_de_AURA(tmp_path):
    """La cifra que decide si esto es autonomía o teatro. Un cambio con autoridad humana es trabajo
    del humano, y contarlo como de AURA convertiría el informe en una felicitación."""
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "tope": 3})
    cp.registrar_evento(tmp_path, "cambio_aplicado", {
        "id": "P-9", "fichero": "x.py", "simbolo": "_m", "autoridad": "ceo",
        "efecto_verificado": True, "verificacion_sana": True, "revertido": False})
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 0, "bloqueadas": 0,
                                                     "elevadas": 0, "motivo": "cola agotada"})
    informe = obs.estado(tmp_path)
    assert informe["trabajo_ejecutado"] == 0, "lo hizo un humano, no AURA"
    assert obs.ultimo(tmp_path)["actos_humanos"] == 1, "y consta que un humano intervino"


def test_los_ACTOS_HUMANOS_del_ciclo_NO_se_ignoran(tmp_path):
    """Si el informe los callara, un ciclo asistido sería indistinguible de uno autónomo."""
    _ciclo(tmp_path, ejecutadas=0)
    assert obs.ultimo(tmp_path)["actos_humanos"] == 0
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "tope": 3})
    cp.registrar_evento(tmp_path, "propuesta_autorizada", {"id": "P-2", "autoridad": "ceo",
                                                           "autorizada_por": "ceo", "acta": "a"})
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 0, "bloqueadas": 0,
                                                     "elevadas": 0, "motivo": "cola agotada"})
    assert obs.ultimo(tmp_path)["actos_humanos"] == 1


# ============================================================ IDENTIDAD --

def test_la_IDENTIDAD_de_la_tarea_viaja_hasta_el_efecto(tmp_path):
    """Sin identidad no hay trazabilidad: «se ejecutó algo» no es un informe, es un rumor."""
    _ciclo_con_trabajo(tmp_path, "P-7", "x.py", "_m")
    ejecutada = obs.ultimo(tmp_path)["tareas_ejecutadas"][0]
    assert ejecutada["id"] == "P-7"
    assert ejecutada["autorizada_por"] == "REVIEW:auditor"


def test_un_cambio_SIN_IDENTIDAD_no_se_da_por_bueno(tmp_path):
    """Un efecto que no se puede atribuir a ninguna propuesta es exactamente lo que ALERTA-005
    describe: una ruta alternativa. La consola tiene que poder verlo, no absorberlo."""
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "tope": 3})
    cp.registrar_evento(tmp_path, "cambio_aplicado", {
        "fichero": "x.py", "simbolo": "_m", "autoridad": "orquestador",
        "efecto_verificado": True, "verificacion_sana": True, "revertido": False})
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 1, "bloqueadas": 0,
                                                     "elevadas": 0, "motivo": "cola agotada"})
    ejecutada = obs.ultimo(tmp_path)["tareas_ejecutadas"][0]
    assert ejecutada["id"] == ND
    assert ejecutada["autorizada_por"] == ND, "sin id no hay a quién atribuirle la autorización"
    assert ejecutada["enlace"] == ND, (
        "y el enlace no puede decir REGISTRADO: no hay nada registrado que enlazar")


def test_el_ENLACE_con_la_autorizacion_se_marca_como_lo_que_es(tmp_path):
    """`propuesta_autorizada` y `cambio_aplicado` comparten el `id`: el enlace está **registrado**.
    Distinguirlo importa porque hay otros enlaces del circuito que solo se pueden **derivar**, y una
    consola que los enseñara igual estaría vendiendo una deducción como un hecho."""
    _ciclo_con_trabajo(tmp_path, "P-7", "x.py", "_m")
    assert obs.ultimo(tmp_path)["tareas_ejecutadas"][0]["enlace"] == "REGISTRADO"


# ============================================================ LAS CINCO ETAPAS --

def test_las_CINCO_ETAPAS_se_distinguen(tmp_path):
    """Descubierta · autorizada · ejecutada · efecto verificado · registrada. Colapsarlas es lo que
    permite decir «lo hizo» cuando lo que hubo fue «lo pensó»."""
    _ciclo(tmp_path, encontradas=1, por_clase={"OPORTUNIDAD_REAL": 1, "BLOQUEADA": 0,
                                               "DECISION_REQUIRED": 0, "FALSO_HUECO": 0},
           ejecutadas=1, cerrar=False)
    _trabajo_real(tmp_path, "P-7", "x.py", "_m")
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 1, "bloqueadas": 0,
                                                     "elevadas": 0, "motivo": "cola agotada"})
    etapas = obs.ultimo(tmp_path)["tareas_ejecutadas"][0]["etapas"]
    assert etapas == {"descubierta": True, "autorizada": True, "ejecutada": True,
                      "efecto_verificado": True, "registrada": True}


def test_una_etapa_que_NO_CONSTA_sale_como_no_cumplida(tmp_path):
    """El control: si todas salieran siempre en `True`, la tabla sería decorativa."""
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "tope": 3})
    cp.registrar_evento(tmp_path, "cambio_aplicado", {
        "id": "P-8", "fichero": "x.py", "simbolo": "_m", "autoridad": "orquestador",
        "efecto_verificado": True, "verificacion_sana": True, "revertido": False})
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 1, "bloqueadas": 0,
                                                     "elevadas": 0, "motivo": "cola agotada"})
    etapas = obs.ultimo(tmp_path)["tareas_ejecutadas"][0]["etapas"]
    assert etapas["autorizada"] is False, "no consta ninguna autorización para P-8"
    assert etapas["ejecutada"] is True


# ============================================================ FUENTES QUE SE CONTRADICEN --

def _proyeccion(d, **campos):
    """`estado.json` como lo escribe el sistema de verdad, con SU vocabulario de estados de tarea."""
    (d / "estado.json").write_text(json.dumps(
        {"version": 1, "status": "WAITING_FOR_NEXT_TASK", "tareas": [],
         "actualizado": "2026-09-01T00:00:00", **campos}), encoding="utf-8")


def test_una_PROYECCION_DESFASADA_se_denuncia(tmp_path):
    """La contradicción que de verdad ocurre. `estado.json` es una proyección y el log encadenado es
    la fuente; que el log mande está bien, lo que no puede es no notarse. En el árbol real la
    proyección llevaba **siete horas** por detrás y la primera versión de esta consola no lo dijo."""
    _ciclo(tmp_path, ejecutadas=0)
    _proyeccion(tmp_path, actualizado="2020-01-01T00:00:00")
    avisos = obs.estado(tmp_path)["contradicciones"]
    assert any("la proyeccion va por detras" in a for a in avisos), avisos


def test_sin_desfase_no_se_inventa_una_contradiccion(tmp_path):
    """El control. Con la proyección al día, no hay nada que denunciar."""
    _ciclo(tmp_path, ejecutadas=0)
    ultimo_momento = cp.leer_eventos(tmp_path)[-1]["momento"]
    _proyeccion(tmp_path, actualizado=ultimo_momento)
    assert obs.estado(tmp_path)["contradicciones"] == []


def test_el_STATUS_de_estado_json_NO_se_finge_comparable_con_el_del_ciclo(tmp_path):
    """El defecto que encontró la auditoría independiente, convertido en prueba.

    `estado.json["status"]` usa el vocabulario de estados de **tarea** de `control_plane`
    —`WORKING`, `WAITING_FOR_NEXT_TASK`, `COMPLETED`…— y esta consola usa el del **ciclo**
    —`TRABAJANDO`, `ESPERANDO`…—. Son dos ejes distintos: no se contradicen porque no hablan de lo
    mismo. La primera versión los comparaba filtrando por `declarado in ESTADOS`, y ese filtro
    —puesto «por prudencia»— mataba la comprobación para siete de los ocho valores reales. Una
    comprobación que solo puede dar la respuesta tranquilizadora es peor que ninguna.

    Ahora el valor se **enseña** etiquetado como de otro eje, en vez de compararse."""
    _ciclo(tmp_path, ejecutadas=0)
    ultimo_momento = cp.leer_eventos(tmp_path)[-1]["momento"]
    for declarado in cp.ESTADOS:
        _proyeccion(tmp_path, status=declarado, actualizado=ultimo_momento)
        informe = obs.estado(tmp_path)
        assert informe["estado_de_tarea_declarado"] == declarado, "se enseña, no se esconde"
        assert informe["contradicciones"] == [], (
            f"{declarado!r} es un estado de TAREA: contradecir con él sería comparar dos ejes")


def test_un_ciclo_ABANDONADO_por_otro_posterior_se_denuncia(tmp_path):
    """Certeza, no sospecha: si otro ciclo arrancó después, el anterior no puede estar corriendo.
    Sin esta cuenta, un ciclo que murió a medias desaparece del informe sin dejar rastro."""
    _ciclo(tmp_path, cerrar=False)
    _ciclo(tmp_path, ejecutadas=0)
    avisos = obs.estado(tmp_path)["contradicciones"]
    assert any("abandonados: [1]" in a for a in avisos), avisos


def test_sin_ciclos_abandonados_no_se_inventa_ninguno(tmp_path):
    _ciclo(tmp_path, ejecutadas=0)
    _ciclo(tmp_path, ejecutadas=0)
    assert not [a for a in obs.estado(tmp_path)["contradicciones"] if "abandonados" in a]


def test_un_LOG_ROTO_se_denuncia_y_no_se_lee_como_bueno(tmp_path):
    """Un historial cuya cadena no cierra puede haber sido alterado. Seguir informando desde él como
    si nada sería dar por buena justamente la evidencia que está en duda."""
    _ciclo(tmp_path, ejecutadas=0)
    ruta = cp.ruta_eventos(tmp_path)
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    alterada = json.loads(lineas[1])
    alterada["datos"]["encontradas"] = 999
    lineas[1] = json.dumps(alterada, ensure_ascii=False, sort_keys=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    informe = obs.estado(tmp_path)
    assert informe["integridad_del_log"]["integro"] is False
    assert informe["estado"] == "ERROR", "con el historial en duda, el informe no puede ser normal"


def test_una_COLA_TRUNCADA_consta(tmp_path):
    """Media línea al final es una caída, no una alteración: el resto del historial sigue siendo
    bueno. Pero el lector tiene que saber que el último evento puede faltar."""
    _ciclo(tmp_path, ejecutadas=0)
    with open(cp.ruta_eventos(tmp_path), "a", encoding="utf-8") as f:
        f.write('{"seq": 99, "tipo": "a-medi')
    assert obs.estado(tmp_path)["integridad_del_log"]["cola_truncada"] is True


# ============================================================ EL ESTADO ACTUAL --

def test_el_KILL_SWITCH_manda_sobre_cualquier_otra_lectura(tmp_path):
    """Es el hecho más fuerte que hay: alguien paró el sistema a mano. Cualquier otra interpretación
    del historial es secundaria."""
    _ciclo(tmp_path, ejecutadas=0)
    orq.ruta_parada(tmp_path).write_text("parada", encoding="utf-8")
    assert obs.estado(tmp_path)["estado"] == "BLOQUEADA"


def test_TRABAJO_ELEVADO_pendiente_se_ve_como_DECISION_REQUIRED(tmp_path):
    """Es el estado real de AURA hoy: la cola se agotó, pero quedan dos cosas esperando una firma.
    Decir sólo ESPERANDO escondería que hay algo que el CEO puede desbloquear."""
    _ciclo(tmp_path, encontradas=8, bloqueadas=6, elevadas=2)
    assert obs.estado(tmp_path)["estado"] == "DECISION_REQUIRED"


def test_sin_nada_pendiente_el_estado_es_ESPERANDO(tmp_path):
    _ciclo(tmp_path, encontradas=0)
    assert obs.estado(tmp_path)["estado"] == "ESPERANDO"


def test_una_PARADA_ANOMALA_es_ERROR_y_no_ESPERANDO(tmp_path):
    """«Zona prohibida» o «verificación fallida» no son terminaciones normales: son paradas que
    alguien tiene que mirar. Igualarlas a «cola agotada» las enterraría."""
    _ciclo(tmp_path, motivo="verificacion fallida")
    assert obs.estado(tmp_path)["estado"] == "ERROR"


def test_el_estado_SIEMPRE_es_uno_de_los_declarados(tmp_path):
    _ciclo(tmp_path, encontradas=8, bloqueadas=6, elevadas=2)
    assert obs.estado(tmp_path)["estado"] in obs.ESTADOS + (ND,)


# ============================================================ PRÓXIMO DESPERTAR --

def test_el_PROXIMO_DESPERTAR_sale_del_cron_real_o_no_sale(tmp_path, monkeypatch):
    """Derivarlo de la línea del `cron` es leer una fuente. Estimarlo de la cadencia observada sería
    adivinar — y adivinar bien la mayoría de las veces es la peor forma de fallar."""
    monkeypatch.setattr(obs, "_lineas_de_cron", lambda: [])
    assert obs.proximo_despertar() == ND


def test_una_cadencia_que_NO_se_sabe_derivar_no_se_aproxima(monkeypatch):
    """Días del mes o de la semana: la consola no los sabe resolver, y lo dice. Aproximar «más o
    menos el lunes» sería exactamente el dato que el CEO prohibió publicar."""
    monkeypatch.setattr(obs, "_lineas_de_cron",
                        lambda: ["0 3 * * 1 /ruta/despertar-aura.sh --max-tareas 3"])
    assert obs.proximo_despertar() == ND


def test_una_cadencia_SIMPLE_si_se_deriva(monkeypatch):
    """El control: si todo saliera `NO DISPONIBLE`, la prueba anterior no probaría nada."""
    monkeypatch.setattr(obs, "_lineas_de_cron",
                        lambda: ["*/30 * * * * /ruta/despertar-aura.sh --max-tareas 3"])
    import datetime as dt
    proximo = obs.proximo_despertar(ahora=dt.datetime(2026, 9, 1, 10, 5))
    assert proximo == "2026-09-01T10:30:00"


# ============================================================ HISTORIAL --

def test_el_HISTORIAL_separa_ciclos_de_trabajos(tmp_path):
    """Tres ciclos, un trabajo. Un historial que los mezclara haría creer que AURA hizo tres cosas."""
    _ciclo(tmp_path)
    _despertar(tmp_path)
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "tope": 3})
    _trabajo_real(tmp_path, "P-1", "x.py", "_m")
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 1, "bloqueadas": 0,
                                                     "elevadas": 0, "motivo": "cola agotada"})
    _ciclo(tmp_path)
    _despertar(tmp_path)
    h = obs.historial(tmp_path)
    assert len(h["ciclos"]) == 3
    assert len(h["trabajos"]) == 1
    assert h["trabajos"][0]["simbolo"] == "_m"


def test_el_HISTORIAL_esta_acotado_y_lo_dice(tmp_path):
    """§14: ningún recorrido sin cota. Y si se recortó, que conste — un historial truncado en
    silencio es un historial que miente por omisión."""
    for _ in range(8):
        _ciclo(tmp_path)
    h = obs.historial(tmp_path, limite=3)
    assert len(h["ciclos"]) == 3
    assert h["ciclos_totales"] == 8
    assert h["recortado"] is True


def test_el_historial_va_del_mas_reciente_al_mas_antiguo(tmp_path):
    _ciclo(tmp_path, motivo="primero")
    _ciclo(tmp_path, motivo="segundo")
    assert obs.historial(tmp_path)["ciclos"][0]["motivo_de_parada"] == "segundo"


# ============================================================ RENDER --

def test_lo_que_se_IMPRIME_dice_lo_mismo_que_se_calcula(tmp_path):
    """Una consola puede ser honesta por dentro y mentir al imprimir. El render se prueba aparte."""
    _ciclo(tmp_path, encontradas=8, bloqueadas=6, elevadas=2)
    texto = obs.render_estado(obs.estado(tmp_path))
    assert "DECISION_REQUIRED" in texto
    assert "AURA" in texto
    for etiqueta in ("Trabajo bloqueado", "Trabajo elevado", "Trabajo ejecutado"):
        assert etiqueta in texto


def test_el_render_ESCRIBE_NO_DISPONIBLE_cuando_falta_el_dato(tmp_path):
    texto = obs.render_estado(obs.estado(tmp_path))
    assert ND in texto


def test_los_tres_comandos_estan_en_el_punto_de_entrada():
    """El CEO los ejecuta como `python3 aura.py estado`. Que la función exista no basta si el punto
    de entrada no la ofrece."""
    import aura
    for orden in ("estado", "historial", "ultimo"):
        assert aura.principal([orden]) == 0, f"`aura.py {orden}` tiene que funcionar"


def test_un_cambio_FUERA_DE_TODO_CICLO_no_se_adopta(tmp_path):
    """El control de la ayuda anterior. Un `cambio_aplicado` sin `motor_iniciado` que lo enmarque no
    pertenece a ningún ciclo, y colgarlo del último que hubiera sería inventarle una procedencia —
    justo lo que la barrera de oportunidades sin fuente cerró en el bloque anterior."""
    _ciclo(tmp_path, ejecutadas=0)
    _trabajo_real(tmp_path, "P-9", "x.py", "_m")
    assert obs.ultimo(tmp_path)["tareas_ejecutadas"] == []
    # Pero el trabajo **existió**, y el total no lo esconde: no pertenecer a un ciclo no es no haber
    # ocurrido. Que las dos cifras discrepen es información, no un fallo del informe.
    assert obs.estado(tmp_path)["trabajo_ejecutado"] == 1


def test_las_DECISIONES_PENDIENTES_se_resumen_sin_perderse(tmp_path):
    """Volcar el registro entero es técnicamente veraz e inútil: la información que importa —que hay
    algo esperando una firma— queda enterrada bajo el detalle."""
    _ciclo(tmp_path, ejecutadas=0)
    (tmp_path / "estado.json").write_text(json.dumps({
        "version": 1, "status": "ESPERANDO", "tareas": [], "actualizado": "2026-09-01T00:00:00",
        "decisiones_pendientes": [{"id": "D-X", "titulo": "algo que decidir",
                                   "por_que_no_la_resuelvo": "x" * 500}]}), encoding="utf-8")
    texto = obs.render_estado(obs.estado(tmp_path))
    assert "D-X · algo que decidir" in texto
    assert "x" * 100 not in texto, "el detalle vive en estado.json, no en la consola"


def test_sin_decisiones_pendientes_se_dice_ninguna(tmp_path):
    _ciclo(tmp_path, ejecutadas=0)
    (tmp_path / "estado.json").write_text(json.dumps({
        "version": 1, "status": "ESPERANDO", "tareas": [], "actualizado": "2026-09-01T00:00:00",
        "decisiones_pendientes": []}), encoding="utf-8")
    linea = [texto for texto in obs.render_estado(obs.estado(tmp_path)).splitlines()
             if "Decisiones pendientes" in texto][0]
    assert linea.strip().endswith("ninguna"), linea


# ============================================================ UN CICLO ABIERTO NO ES UNA ACTIVIDAD --

def test_un_ciclo_abierto_dice_CUANTO_lleva_abierto(tmp_path):
    """El segundo hallazgo de la auditoría. Un ciclo que abrió porque el proceso murió hace horas se
    mostraba como `TRABAJANDO`, exactamente igual que uno corriendo ahora mismo. El estado no puede
    decidir cuál de los dos es —no hay dato que lo diga—, pero sí puede decir **cuánto lleva**, y
    eso convierte un `TRABAJANDO` mudo en información."""
    _ciclo(tmp_path, cerrar=False)
    informe = obs.estado(tmp_path)
    assert informe["estado"] == "TRABAJANDO"
    assert informe["antiguedad_del_ciclo_abierto"] != ND
    assert "abrio hace" in informe["sospecha"]


def test_un_ciclo_CERRADO_no_arrastra_antiguedad_ni_aviso(tmp_path):
    """El control: si el aviso saliera siempre, no diría nada."""
    _ciclo(tmp_path, ejecutadas=0)
    informe = obs.estado(tmp_path)
    assert informe["antiguedad_del_ciclo_abierto"] == ND
    assert informe["sospecha"] == ""


def test_pasado_un_PERIODO_DEL_CRON_entero_el_aviso_lo_dice(monkeypatch):
    """Y aquí se dice algo más fuerte que «lleva un rato», sin inventar ningún umbral: si el ciclo
    lleva abierto más de lo que tarda el `cron` en volver, ya pasó un despertar entero sin que
    cerrara. La referencia sale de la línea real del `cron`; si no se sabe leer, no se dice nada."""
    monkeypatch.setattr(obs, "_lineas_de_cron",
                        lambda: ["*/30 * * * * /ruta/despertar-aura.sh --max-tareas 3"])
    ciclo = {"abierto": True, "inicio": "2026-09-01T10:00:00"}
    aviso = obs._sospecha_de_ciclo_muerto(ciclo, ahora=dt.datetime(2026, 9, 1, 11, 5))
    assert "1h 05m" in aviso
    assert "cada 30 min" in aviso and "despertar entero" in aviso


def test_sin_CRON_legible_el_aviso_no_se_inventa_una_referencia(monkeypatch):
    """El control del anterior: sin fuente de la que derivar el periodo, se dice la antigüedad y se
    calla lo demás. Aproximar «debería haber cerrado ya» sin referencia sería opinar."""
    monkeypatch.setattr(obs, "_lineas_de_cron", lambda: [])
    ciclo = {"abierto": True, "inicio": "2026-09-01T10:00:00"}
    aviso = obs._sospecha_de_ciclo_muerto(ciclo, ahora=dt.datetime(2026, 9, 1, 11, 5))
    assert "1h 05m" in aviso
    assert "despertar entero" not in aviso


def test_el_render_ENSENA_la_antiguedad_y_el_aviso(tmp_path):
    _ciclo(tmp_path, cerrar=False)
    texto = obs.render_estado(obs.estado(tmp_path))
    assert "abierto)" in texto
    assert "Aviso" in texto


def test_sin_REPARTO_POR_CLASE_la_cabecera_no_afirma_ESPERANDO(tmp_path):
    """El hallazgo MENOR de la auditoría independiente, convertido en prueba.

    Si no consta el reparto por clase del descubrimiento, no se puede distinguir «no hay nada
    pendiente» de «no se sabe». La primera versión usaba `.get("DECISION_REQUIRED", 0)` y afirmaba
    ESPERANDO en la línea de cabecera mientras el detalle, tres líneas más abajo, admitía
    `NO DISPONIBLE`. Era el único sitio del módulo que rellenaba un hueco con un cero — y estaba
    justo en el dato que más se lee."""
    cp.registrar_evento(tmp_path, "motor_iniciado", {"raiz": str(tmp_path), "tope": 3})
    cp.registrar_evento(tmp_path, "ciclo_detenido", {"ejecutadas": 0, "motivo": "cola agotada"})
    informe = obs.estado(tmp_path)
    assert informe["estado"] == ND
    assert informe["trabajo_elevado"] == ND, "y la cabecera y el detalle dicen lo mismo"


def test_las_OPORTUNIDADES_BLOQUEADAS_se_exponen_una_por_una(tmp_path):
    """Contestar «hay 6 bloqueadas» sin poder decir cuáles ni por qué es medio informe. El detalle ya
    estaba en la misma proyección que se lee para las decisiones: no exponerlo era el hueco."""
    _ciclo(tmp_path, ejecutadas=0)
    (tmp_path / "estado.json").write_text(json.dumps({
        "version": 1, "status": "WAITING_FOR_NEXT_TASK", "tareas": [],
        "actualizado": cp.leer_eventos(tmp_path)[-1]["momento"],
        "oportunidades_bloqueadas": [{"id": "OB-1", "que": "algo", "por_que": "un motivo",
                                      "quien_desbloquea": "CEO"}]}), encoding="utf-8")
    informe = obs.estado(tmp_path)
    assert informe["oportunidades_bloqueadas"][0]["id"] == "OB-1"
    assert informe["oportunidades_bloqueadas"][0]["por_que"] == "un motivo"


def test_sin_oportunidades_bloqueadas_registradas_se_declara_el_hueco(tmp_path):
    """El control: no se devuelve una lista vacía como si constara que no hay ninguna."""
    _ciclo(tmp_path, ejecutadas=0)
    assert obs.estado(tmp_path)["oportunidades_bloqueadas"] == ND


def test_los_TRABAJOS_RECIENTES_se_exponen_acotados(tmp_path):
    """«¿Qué hiciste hoy?» necesita más de una tarea. Salen de la misma lista que ya se recorrió para
    `ultima_tarea`: ni una lectura más."""
    _ciclo_con_trabajo(tmp_path, "P-1", "x.py", "_a")
    _ciclo_con_trabajo(tmp_path, "P-2", "y.py", "_b")
    recientes = obs.estado(tmp_path)["trabajos_recientes"]
    assert [t["simbolo"] for t in recientes] == ["_a", "_b"]
    assert len(recientes) <= obs.LIMITE_HISTORIAL
