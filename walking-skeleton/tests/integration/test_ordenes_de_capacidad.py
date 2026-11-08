"""El usuario pide una capacidad y AURA la EJECUTA (CEO, 2026-09-21).

EL HUECO, MEDIDO ANTES DE CERRARLO `[EJEC]`. AURA arrancaba declarando 21 operaciones con sus
adaptadores montados, sus permisos clasificados y el Motor Único funcionando. Y a *«ejecuta las
pruebas»* respondía:

    AURA> Esto lo genera mi modelo local y no está verificado: Entendido.

Capacidad registrada, ejecutor construido, permiso concedido, y **ninguna ruta desde la conversación
hasta ellos**. El patrón «declarado ≠ real» aplicado a lo que el usuario puede pedir: el catálogo
prometía algo que el runtime no sabía hacer.

QUÉ FIJA ESTE FICHERO. Que la ruta existe, que **pasa por el Motor Único** y no por un atajo, que
**no le quita ninguna frase** a las superficies que ya existían, y que lo que AURA cuenta del
resultado es lo que de verdad pasó — incluido cuando el resultado es malo, que es donde una
superficie complaciente haría más daño.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aura_skeleton import observability as obs
from aura_skeleton.core import ordenes

# ============================================================ EL RECONOCEDOR, A SOLAS --


SERVIDAS = (
    "ejecutar_pruebas",
    "verificar_calidad",
    "auditar_garantias",
    "diagnosticar_estado",
    "consultar_estado_sistema",
)


@pytest.mark.parametrize(
    "frase, esperada",
    [
        ("ejecuta las pruebas", "ejecutar_pruebas"),
        ("corre los tests", "ejecutar_pruebas"),
        ("verifica la calidad del codigo", "verificar_calidad"),
        ("audita las garantias", "auditar_garantias"),
        ("diagnostica tu estado", "diagnosticar_estado"),
        ("como esta el sistema", "consultar_estado_sistema"),
    ],
)
def test_reconoce_las_ordenes_escritas(frase, esperada):
    assert ordenes.reconocer(frase, SERVIDAS) == esperada


@pytest.mark.parametrize(
    "frase",
    [
        "no ejecutes las pruebas",  # negación: parecida, pero no es la variante
        # **Contiene la variante LITERAL.** Es el caso que distingue comparar por segmento completo de
        # comparar por subcadena: con `in`, esta frase ejecutaría. Lo destapó el mutante `OC-M1`.
        "por favor ejecuta las pruebas ahora",
        "no quiero que ejecuta las pruebas",
        "antes de ejecutar las pruebas dime algo",
        "hola",
        "que puedes hacer",
        "",
        "ejecuta",
    ],
)
def test_NO_reconoce_lo_que_no_es_una_orden_limpia(frase):
    """Por segmento COMPLETO, nunca por subcadena.

    Reconocer *«no ejecutes las pruebas»* sería ejecutar exactamente lo contrario de lo que pide el
    usuario — y por una barrera de implementación, no de intención."""
    assert ordenes.reconocer(frase, SERVIDAS) is None


def test_una_capacidad_que_el_registro_NO_sirve_no_se_reconoce():
    """`INV-9`: no se finge lo que no está montado.

    Si se reconociera, el turno acabaría en «ninguna capacidad atiende», que el usuario leería como
    una avería en vez de como lo que es: algo que no existe."""
    assert ordenes.reconocer("ejecuta las pruebas", ()) is None
    assert ordenes.reconocer("ejecuta las pruebas", ("auditar_garantias",)) is None


def test_solo_se_reconocen_capacidades_VERDES_y_de_LECTURA():
    """Esta superficie ejecuta **sin pedir confirmación**, así que no puede alcanzar nada que
    modifique el mundo: `ADR-0003` exige confirmación humana para la lista roja.

    Y el filtro se calcula del catálogo, no se escribe a mano — si alguien reclasificara una de
    estas como roja, dejaría de reconocerse sin tocar `ordenes.py`."""
    from aura_skeleton.core.permissions import CATALOGO

    for nombre in ordenes.capacidades_reconocibles():
        ficha = CATALOGO[nombre]
        assert ficha["lista"] == "verde", f"{nombre} no es de lista verde"
        assert ficha["efecto"] == "lectura", f"{nombre} no es de efecto lectura"


def test_una_orden_no_lleva_argumentos_del_usuario():
    """La capacidad se ejecuta con su configuración propia. Si el usuario pudiera parametrizarla,
    la superficie ejecutable dejaría de ser cerrada — que es justo lo que `EjecutorQA` protege
    construyendo su comando desde una constante suya."""
    for nombre in ordenes.capacidades_reconocibles():
        assert ordenes.argumentos_de(nombre) == {}


# ============================================================ EL REDACTOR: DICE LA VERDAD --


def _redactar(res):
    from aura_skeleton.core.orchestrator import _redactar_resultado_de_orden

    return _redactar_resultado_de_orden("auditar_garantias", res)


def test_un_resultado_MALO_no_se_cuenta_como_bueno():
    """RED el 2026-09-21, y era un bug real de la primera versión.

    El redactor usaba claves que el motor no devuelve, así que caía al caso final y contestaba
    *«terminó correctamente»* mientras el adaptador devolvía `ok=False` y «5 garantías que NO
    protegen nada». Es «declarado ≠ real» en la superficie que el usuario lee y se cree."""
    salida = _redactar(
        {
            "accion": "auditar_garantias",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"ok": False, "resumen": "5 garantia(s) no protegen nada"},
        }
    )

    assert "correctamente" not in salida.lower(), "un resultado malo se conto como bueno"
    assert "5 garantia(s) no protegen nada" in salida, "no se cuenta QUE salio mal"
    # No basta con no mentir: hay que AVISAR. Sin esto, el mutante que deja de mirar `ok` sobrevivía
    # porque el resumen se seguía mostrando y la frase quedaba neutra.
    assert "No está limpio" in salida, "se conto el resultado sin señalar que la capacidad NO quedo limpia"


def test_una_capacidad_DETENIDA_por_el_gobierno_no_se_cuenta_como_fallo():
    """El motor distingue «detenida» de «error», y el usuario necesita esa distinción: lo primero
    es el gobierno funcionando; lo segundo, una avería."""
    salida = _redactar(
        {
            "accion": "auditar_garantias",
            "estado": "detenida",
            "motivo": "permisos: exige confirmacion",
            "origen": "conversacion",
        }
    )

    assert "No he ejecutado" in salida
    assert "permisos: exige confirmacion" in salida
    assert "no pude" not in salida, "una denegacion de permisos se conto como avería"


def test_un_ERROR_se_cuenta_como_error():
    salida = _redactar(
        {
            "accion": "auditar_garantias",
            "estado": "error",
            "motivo": "ninguna capacidad atiende",
            "origen": "conversacion",
        }
    )

    assert "no pude" in salida and "ninguna capacidad atiende" in salida


def test_CONTROL_un_resultado_BUENO_si_se_cuenta_como_bueno():
    """Sin este control, el redactor cumpliría todo lo anterior diciendo siempre que algo va mal."""
    salida = _redactar(
        {
            "accion": "auditar_garantias",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"ok": True, "resumen": "1140 garantias vigentes"},
        }
    )

    assert "No está limpio" not in salida
    assert "1140 garantias vigentes" in salida


def test_una_salida_ENORME_no_revienta_el_turno():
    salida = _redactar(
        {
            "accion": "auditar_garantias",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"ok": True, "resumen": "x" * 5000},
        }
    )

    assert len(salida) < 1200, "una salida enorme paso entera al turno"
    assert "[…]" in salida, "se recorto sin avisar de que se recorto"


# ============================================================ ALERTA-005: EL MOTOR ÚNICO --


class _MotorEspia:
    """Un motor que solo apunta lo que le piden. No ejecuta nada."""

    def __init__(self, respuesta=None):
        self.llamadas = []
        self._respuesta = respuesta or {
            "accion": "auditar_garantias",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"ok": True, "resumen": "todo vigente"},
        }

    async def ejecutar(self, accion, args, trace_id, event_id, origen):
        self.llamadas.append({"accion": accion, "args": args, "origen": origen})
        return self._respuesta


class _RegistroFalso:
    def __init__(self, caps):
        self._caps = tuple(caps)

    def capacidades(self):
        return self._caps

    def para(self, _cap):
        return None


async def _atender(texto, caps=SERVIDAS, motor=None):
    """Invoca la superficie nueva con lo mínimo montado, sin levantar AURA entera."""
    from aura_skeleton.core.orchestrator import Orchestrator

    orq = Orchestrator.__new__(Orchestrator)  # sin __init__: esta prueba mide UNA superficie
    orq.perm = SimpleNamespace(_kill=None)  # PARADA no armada, explicito: `_despachar_orden` la consulta (punto D)
    orq.motor = motor if motor is not None else _MotorEspia()
    orq.registro = _RegistroFalso(caps)
    return await orq._atender_orden_de_capacidad("u1", texto, "t1")


@pytest.mark.asyncio
async def test_la_orden_se_ejecuta_POR_EL_MOTOR_UNICO_y_no_por_un_atajo():
    """`ALERTA-005`: *«toda ejecución pasa por el motor único; ninguna ruta alternativa»*.

    Esta superficie es nueva y toca ejecución: si llamara a un adaptador por su cuenta sería
    exactamente la segunda ruta que ese incidente costó dos veces. Se comprueba con un motor espía:
    si la orden no pasa por él, no se ejecutó por donde debía."""
    motor = _MotorEspia()

    salida = await _atender("audita las garantias", motor=motor)

    assert len(motor.llamadas) == 1, "la orden NO paso por el motor unico"
    assert motor.llamadas[0]["accion"] == "auditar_garantias"
    assert motor.llamadas[0]["origen"] == "conversacion"
    assert motor.llamadas[0]["args"] == {}, "se colaron argumentos del usuario"
    assert "todo vigente" in salida


@pytest.mark.asyncio
async def test_el_KILL_SWITCH_detiene_la_orden_porque_pasa_por_el_motor():
    """Medido también contra AURA real `[EJEC]`: con `~/.aura/KILL` armado, la respuesta fue
    *«No he ejecutado «auditar_garantias»: permisos: kill switch activo (5.3 §5)»*.

    Aquí se fija la garantía sin tocar el centinela real: el motor devuelve «detenida» y la
    superficie lo cuenta como lo que es — gobierno, no avería."""
    motor = _MotorEspia(
        {
            "accion": "auditar_garantias",
            "estado": "detenida",
            "motivo": "permisos: kill switch activo (5.3 §5)",
            "origen": "conversacion",
        }
    )

    salida = await _atender("audita las garantias", motor=motor)

    assert "No he ejecutado" in salida and "kill switch" in salida


@pytest.mark.asyncio
async def test_un_turno_con_VARIAS_frases_no_se_ejecuta():
    """Ante la duda, no se ejecuta (`ADR-0003`). Un turno compuesto no es una orden limpia, y
    adivinar cuál de las frases manda sería decidir por el usuario."""
    motor = _MotorEspia()

    salida = await _atender("hola, audita las garantias", motor=motor)

    assert salida is None
    assert motor.llamadas == [], "se ejecuto algo en un turno que no era una orden limpia"

    # **Y con la orden PRIMERA**, que es el caso que de verdad discrimina: mirar solo `partes[0]`
    # dejaría pasar este turno. Lo destapó el mutante `OC-M6`.
    salida = await _atender("audita las garantias, gracias", motor=motor)

    assert salida is None, "un turno compuesto se ejecuto porque la orden iba primero"
    assert motor.llamadas == []


@pytest.mark.asyncio
async def test_sin_motor_no_hay_superficie():
    """Si el motor no está montado, esta superficie no existe: no se inventa un camino de
    ejecución cuando falta la puerta por la que tendría que pasar."""
    from aura_skeleton.core.orchestrator import Orchestrator

    orq = Orchestrator.__new__(Orchestrator)
    orq.motor = None
    orq.registro = _RegistroFalso(SERVIDAS)

    assert await orq._atender_orden_de_capacidad("u1", "audita las garantias", "t1") is None


def test_AISLADO_una_capacidad_RECLASIFICADA_deja_de_reconocerse(monkeypatch):
    """El filtro se calcula del catálogo, y eso tiene que poder comprobarse.

    `OC-M3` sobrevivía porque hoy **todas** las variantes escritas son ya verde+lectura, así que
    quitar el filtro no cambiaba nada: la prueba era tautológica. Aquí se reclasifica una a roja y
    se exige que desaparezca — que es lo que impide que esta superficie ejecute sin confirmación
    algo que `ADR-0003` reserva."""
    from aura_skeleton.core import permissions as pm

    catalogo = dict(pm.CATALOGO)
    catalogo["auditar_garantias"] = {**catalogo["auditar_garantias"], "lista": "roja"}
    monkeypatch.setattr(ordenes, "CATALOGO", catalogo)

    reconocibles = ordenes.capacidades_reconocibles()

    assert "auditar_garantias" not in reconocibles, (
        "una capacidad reclasificada como ROJA se sigue ejecutando sin confirmacion"
    )
    assert "ejecutar_pruebas" in reconocibles, "el filtro se llevo por delante a las demas"


# ============================================================ ÓRDENES CON RUTA --
#
# El salto respecto de las anteriores: *«lista el directorio»* no significa nada sin decir cuál.
# Negarle el argumento no la haría más segura; la haría inservible. Quien valida la ruta sigue
# siendo `operaciones.validar()`, la puerta única del sistema de ficheros — aquí solo se extrae.

CON_RUTA = ("listar_directorio", "leer_archivo", "buscar_archivo")


@pytest.mark.parametrize(
    "frase, capacidad, ruta",
    [
        ("lista el directorio Documentos", "listar_directorio", "Documentos"),
        ("lista la carpeta ~/Música", "listar_directorio", "~/Música"),
        ("lee el fichero ~/Música/notas.TXT", "leer_archivo", "~/Música/notas.TXT"),
        ("muestrame el archivo /home/x/A.md", "leer_archivo", "/home/x/A.md"),
    ],
)
def test_reconoce_la_orden_y_CONSERVA_la_ruta_literal(frase, capacidad, ruta):
    """**La ruta se toma del texto ORIGINAL.**

    Medido antes de escribirlo `[EJEC]`: la normalización del orquestador pasa a minúsculas y parte
    por el punto, así que `Documentos` se volvía `documentos` y `~/Música/notas.TXT` se partía en
    dos. Usarla para la ruta habría producido un «no existe» sobre ficheros que sí están."""
    assert ordenes.reconocer_con_ruta(frase, CON_RUTA) == (capacidad, ruta)


@pytest.mark.parametrize(
    "frase",
    [
        "lista el directorio",  # sin ruta: no dice cuál, y adivinarlo sería decidir por él
        "lista la carpeta   ",
        "hola",
        "",
        "lee",
    ],
)
def test_sin_ruta_no_hay_orden(frase):
    assert ordenes.reconocer_con_ruta(frase, CON_RUTA) is None


def test_una_capacidad_con_ruta_que_el_registro_NO_sirve_no_se_reconoce():
    assert ordenes.reconocer_con_ruta("lista el directorio Documentos", ()) is None


def test_el_nombre_del_argumento_se_lee_del_NUCLEO_no_se_cablea():
    """`buscar_archivo` lo llama `patron` y las otras `ruta`. Mantener una copia de ese detalle en
    la superficie sería una lista paralela que se desincroniza en silencio."""
    from aura_skeleton.core.operaciones import ESPECIFICACIONES
    from aura_skeleton.core.orchestrator import _ARG_RUTA

    for capacidad, arg in _ARG_RUTA.items():
        assert arg == ESPECIFICACIONES[capacidad]["args"][0], (
            f"{capacidad}: la superficie usa {arg!r} y el nucleo espera {ESPECIFICACIONES[capacidad]['args'][0]!r}"
        )


@pytest.mark.asyncio
async def test_la_orden_con_ruta_tambien_pasa_por_el_MOTOR_UNICO():
    """Las dos formas de orden —con ruta y sin ella— comparten el mismo despacho.

    Tenerlo duplicado habría sido el cableado que se olvida en una rama: la lección de `ALERTA-005`
    y la del mutante `AI-M2`, que sobrevivió porque cada camino conectaba su propia protección."""
    motor = _MotorEspia(
        {
            "accion": "listar_directorio",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"status": "ok", "entradas": ["a.txt", "b.txt"]},
        }
    )

    salida = await _atender("lista el directorio ~/Documentos", caps=CON_RUTA, motor=motor)

    assert len(motor.llamadas) == 1, "la orden con ruta NO paso por el motor unico"
    assert motor.llamadas[0]["accion"] == "listar_directorio"
    assert motor.llamadas[0]["args"] == {"ruta": "~/Documentos"}, "la ruta no llego intacta"
    assert "a.txt" in salida and "b.txt" in salida, "no se enseño el resultado real"


# ============================================================ LOS OTROS CONTRATOS DE SALIDA --


def _redactar_cap(capacidad, res):
    from aura_skeleton.core.orchestrator import _redactar_resultado_de_orden

    return _redactar_resultado_de_orden(capacidad, res)


def test_un_LISTADO_se_enseña_en_vez_de_decir_solo_que_termino():
    """Los adaptadores no comparten contrato: `computador` devuelve `{status, entradas}` y no
    `{ok, resumen}`. Leer solo el primero hacía que un listado real se contara como «terminó
    correctamente» **sin enseñar nada** — cierto, e inútil."""
    salida = _redactar_cap(
        "listar_directorio",
        {
            "accion": "listar_directorio",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"status": "ok", "entradas": ["uno", "dos"]},
        },
    )

    assert "uno" in salida and "dos" in salida
    assert "2 entrada(s)" in salida


def test_un_directorio_VACIO_se_dice_que_esta_vacio():
    salida = _redactar_cap(
        "listar_directorio",
        {
            "accion": "listar_directorio",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"status": "ok", "entradas": []},
        },
    )

    assert "vacío" in salida
    assert "0 entrada" not in salida, "un vacio se conto como un listado de cero"


def test_un_resultado_DUPLICATE_no_se_cuenta_como_ejecucion_fresca():
    """Idempotencia del adaptador: **no se volvió a ejecutar**. Contarlo como trabajo hecho sería
    afirmar algo que no ocurrió — el mismo patrón que este proyecto lleva nueve veces pagando."""
    salida = _redactar_cap(
        "leer_archivo",
        {
            "accion": "leer_archivo",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"status": "duplicate"},
        },
    )

    assert "no lo repetí" in salida
    assert "correctamente" not in salida.lower(), "una no-ejecucion se conto como ejecucion correcta"


def test_el_CONTENIDO_de_un_fichero_se_enseña():
    salida = _redactar_cap(
        "leer_archivo",
        {
            "accion": "leer_archivo",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"status": "ok", "contenido": "hola mundo"},
        },
    )

    assert "hola mundo" in salida


def test_buscar_archivo_NO_se_reconoce_porque_pide_DOS_argumentos():
    """No es un olvido: de *«busca el fichero informe.pdf»* sale el patrón, no la raíz.

    Pasar medio contrato daría un error del núcleo que el usuario leería como avería de AURA, y
    adivinar la raíz sería decidir por él dónde buscar. La exclusión es **por construcción**:
    `_nombre_del_argumento` solo acepta capacidades de un único argumento, así que volver a ponerla
    en la tabla no bastaría para colarla."""
    from aura_skeleton.core.operaciones import ESPECIFICACIONES

    assert len(ESPECIFICACIONES["buscar_archivo"]["args"]) == 2, "la premisa cambio"
    assert ordenes.reconocer_con_ruta("busca el fichero informe.pdf", ("buscar_archivo",)) is None


def test_AISLADO_anadir_buscar_archivo_a_la_tabla_NO_basta_para_colarla(monkeypatch):
    """La segunda capa, ejercida con la primera desactivada.

    `OC-M12` sobrevivía porque `buscar_archivo` ya no está en la tabla de prefijos: la comprobación
    de «un solo argumento» nunca llegaba a actuar. Pero el módulo **promete** que volver a ponerla
    ahí no bastaría, y una promesa que nadie comprueba es la clase de garantía que este proyecto
    llama declarada y no real. Aquí se pone en la tabla a propósito y se exige que siga sin
    reconocerse."""
    tabla = dict(ordenes._PREFIJOS_CON_RUTA)
    tabla["buscar_archivo"] = ("busca el fichero",)
    monkeypatch.setattr(ordenes, "_PREFIJOS_CON_RUTA", tabla)

    assert ordenes.reconocer_con_ruta("busca el fichero informe.pdf", ("buscar_archivo",)) is None, (
        "se colo una capacidad de DOS argumentos solo con anadirla a la tabla"
    )

    # Y el control: las de un solo argumento siguen reconociéndose con la tabla parcheada.
    assert ordenes.reconocer_con_ruta("lista el directorio Documentos", ("listar_directorio",)) == (
        "listar_directorio",
        "Documentos",
    )


# ============================================================ LO QUE LA AUDITORÍA DESTAPÓ --
#
# Encontrado probando casos límite `[EJEC]`, no leyendo: la ruta se tragaba lo que viniera detrás.


@pytest.mark.parametrize(
    "frase",
    [
        "lista el directorio ~/Documentos y luego dime la hora",
        "lista el directorio ~/Documentos, gracias",
        "lee el archivo ~/x.txt y borra el otro",
        "lista el directorio ~/Documentos porfa",
        "lista el directorio ~/a ~/b",  # dos rutas: cuál, no se adivina
    ],
)
def test_la_ruta_no_se_traga_el_RESTO_de_la_frase(frase):
    """La ruta era todo lo que venía detrás del prefijo.

    El núcleo lo habría rechazado —esas rutas no existen—, pero el usuario habría leído *«no existe
    '~/Documentos, gracias'»* para algo que nunca pidió: un mensaje que culpa al sistema de ficheros
    de un fallo de comprensión. **Ante la duda, no se ejecuta** (`ADR-0003`)."""
    assert ordenes.reconocer_con_ruta(frase, CON_RUTA) is None


def test_CONTROL_una_ruta_con_ESPACIOS_sigue_siendo_valida():
    """Sin este control, la corrección anterior se cumpliría rechazando toda ruta con espacio — y
    `~/Mis Documentos` es una ruta perfectamente legítima. Lo que se busca no es el espacio, sino
    la marca de que hay otra oración detrás."""
    assert ordenes.reconocer_con_ruta("lista el directorio ~/Mis Documentos", CON_RUTA) == (
        "listar_directorio",
        "~/Mis Documentos",
    )


def test_un_fichero_BINARIO_no_se_vuelca_a_la_conversacion():
    """Encontrado auditando `[EJEC]`: un contenido en bytes salía como `b'\\x00\\x01…'` — ilegible y
    con caracteres de control que pueden desordenar la terminal de quien lo lee."""
    salida = _redactar_cap(
        "leer_archivo",
        {
            "accion": "leer_archivo",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"status": "ok", "contenido": b"\x00\x01binario"},
        },
    )

    assert "no parece texto legible" in salida
    assert "\x00" not in salida, "se colaron bytes de control en la respuesta"


def test_un_texto_con_caracteres_de_CONTROL_tampoco_se_vuelca():
    salida = _redactar_cap(
        "leer_archivo",
        {
            "accion": "leer_archivo",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"status": "ok", "contenido": "ab\x07cd"},
        },
    )

    assert "no parece texto legible" in salida


def test_CONTROL_un_texto_NORMAL_si_se_enseña():
    """Los saltos de línea y tabuladores son texto normal, no control que haya que esconder."""
    salida = _redactar_cap(
        "leer_archivo",
        {
            "accion": "leer_archivo",
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"status": "ok", "contenido": "hola\n\tmundo"},
        },
    )

    assert "hola" in salida and "mundo" in salida


# ============================================================ COMPOSICIÓN: LA REVISIÓN --
#
# *«Haz una revisión»* no pide una cosa: pide que AURA mire lo que sabe mirar y cuente qué encontró.
# No es arquitectura nueva — es el patrón que `_atender_conversacion_general` ya aplica a las
# intenciones, llevado a las capacidades.

REVISABLES = ("diagnosticar_estado", "auditar_garantias", "consultar_estado_sistema")


def _rev(*resultados):
    """Redacta una revisión a partir de los resultados que devolvería el motor."""
    from aura_skeleton.core.orchestrator import _redactar_revision

    return _redactar_revision(list(resultados))


def _ok(cap, resumen=""):
    return (
        cap,
        {"accion": cap, "estado": "ejecutada", "origen": "conversacion", "resultado": {"ok": True, "resumen": resumen}},
    )


def _mal(cap, resumen):
    return (
        cap,
        {
            "accion": cap,
            "estado": "ejecutada",
            "origen": "conversacion",
            "resultado": {"ok": False, "resumen": resumen},
        },
    )


def _bloqueada(cap, motivo="permisos: kill switch activo (5.3 §5)"):
    return (cap, {"accion": cap, "estado": "detenida", "motivo": motivo, "origen": "conversacion"})


def test_reconoce_una_peticion_COMPUESTA():
    assert ordenes.reconocer_compuesta("haz una revision", REVISABLES) == REVISABLES


def test_solo_se_componen_capacidades_que_el_registro_SIRVE():
    """`INV-9`: un informe sobre capacidades que no están montadas sería inventado."""
    assert ordenes.reconocer_compuesta("haz una revision", ("auditar_garantias",)) == ("auditar_garantias",)
    assert ordenes.reconocer_compuesta("haz una revision", ()) is None


def test_una_INCIDENCIA_impide_decir_que_todo_esta_limpio():
    """La regla dura de la misión: *«AURA no puede decir "todo está bien" si el diagnóstico devuelve
    una incidencia»*. El veredicto sale de contar, no de interpretar, así que la síntesis no puede
    ser más optimista que sus partes."""
    salida = _rev(_ok("consultar_estado_sistema"), _mal("auditar_garantias", "5 garantias no protegen nada"))

    assert "todo limpio" not in salida.lower(), "se declaro limpio con una incidencia delante"
    assert "1 con incidencia" in salida
    assert "5 garantias no protegen nada" in salida


def test_una_capacidad_BLOQUEADA_no_se_compensa_con_las_demas():
    """**Componer no concede autoridad.** Si una parte no llegó a mirarse, el informe lo dice:
    presentar una revisión completa cuando una capacidad quedó bloqueada sería «declarado ≠ real»
    con la firma de AURA debajo.

    Medido también contra AURA real `[EJEC]`: con `~/.aura/KILL` armado, la respuesta fue *«No
    encontré incidencias, pero **no pude mirarlo todo**»* con el motivo de cada bloqueo."""
    salida = _rev(_ok("consultar_estado_sistema"), _bloqueada("auditar_garantias"))

    assert "todo limpio" not in salida.lower(), "un bloqueo se conto como revision limpia"
    assert "no pude mirarlo todo" in salida
    assert "no lo revisé" in salida and "kill switch" in salida


def test_un_bloqueo_NO_se_cuenta_como_incidencia():
    """Son cosas distintas y el usuario necesita distinguirlas: una incidencia es un problema
    encontrado; un bloqueo es una barrera que funcionó y **algo que no se miró**."""
    salida = _rev(_bloqueada("auditar_garantias"))

    assert "con incidencia" not in salida, "una barrera se conto como un problema del sistema"
    assert "no pude mirarlo todo" in salida


def test_un_ERROR_de_una_capacidad_no_hunde_la_revision_entera():
    """Lo que falló se dice; lo que se pudo mirar, también. Perder los aciertos porque una parte
    reventó dejaría al usuario sin la información que sí se obtuvo."""
    salida = _rev(
        _ok("consultar_estado_sistema", "sin novedad"),
        (
            "auditar_garantias",
            {
                "accion": "auditar_garantias",
                "estado": "error",
                "motivo": "ninguna capacidad atiende",
                "origen": "conversacion",
            },
        ),
    )

    assert "falló al revisarlo" in salida and "ninguna capacidad atiende" in salida
    assert "consultar_estado_sistema" in salida


def test_un_DUPLICATE_se_cuenta_como_sin_datos_no_como_limpio():
    """Idempotencia: **no se volvió a ejecutar**. Contarlo como revisado sería afirmar una
    comprobación que no ocurrió."""
    salida = _rev(
        (
            "auditar_garantias",
            {
                "accion": "auditar_garantias",
                "estado": "ejecutada",
                "origen": "conversacion",
                "resultado": {"status": "duplicate"},
            },
        )
    )

    assert "sin datos" in salida
    assert "todo limpio" not in salida.lower()


def test_CONTROL_si_TODO_esta_limpio_se_dice_que_esta_limpio():
    """Sin este control, todas las de arriba se cumplirían no diciendo nunca que algo va bien — y
    una revisión que jamás da buenas noticias es tan inútil como una que siempre las da."""
    salida = _rev(_ok("diagnosticar_estado"), _ok("consultar_estado_sistema"))

    assert "está todo limpio" in salida
    assert "incidencia" not in salida


def test_una_revision_SIN_capacidades_lo_dice_en_vez_de_inventar():
    assert "ninguna capacidad" in _rev().lower()


@pytest.mark.asyncio
async def test_cada_capacidad_de_la_revision_pasa_POR_SU_PROPIA_puerta():
    """`ALERTA-005` y la regla de que componer no concede autoridad: no hay un despacho «de
    revisión» en bloque, sino el mismo camino repetido. Se comprueba contando las llamadas al
    motor: una por capacidad, ni una menos."""
    motor = _MotorEspia(
        {"accion": "x", "estado": "ejecutada", "origen": "conversacion", "resultado": {"ok": True, "resumen": ""}}
    )

    salida = await _atender("haz una revision", caps=REVISABLES, motor=motor)

    assert len(motor.llamadas) == 3, (
        f"la revision hizo {len(motor.llamadas)} llamada(s) al motor y componia 3 capacidades"
    )
    assert [ll["accion"] for ll in motor.llamadas] == list(REVISABLES)
    assert all(ll["origen"] == "conversacion" for ll in motor.llamadas)
    assert "está todo limpio" in salida


def test_ninguna_variante_COMPUESTA_choca_con_las_superficies_ANTERIORES():
    """Una variante que otra superficie intercepta antes **nunca se alcanza**: es código muerto
    disfrazado de capacidad, con el catálogo prometiendo algo que el runtime no hace.

    Medido `[EJEC]`: *«como va todo»* la atendía el tablero de estado autónomo, que va antes. Se
    retiró. Esta prueba impide que vuelva a colarse: las superficies anteriores mandan, y esta va
    detrás de todas."""
    from aura_skeleton.core.orchestrator import _TABLA_INTENCIONES

    previas = {v for _clase, _nombre, variantes in _TABLA_INTENCIONES for v in variantes}
    mias = {v for variantes in ordenes._VARIANTES_COMPUESTAS.values() for v in variantes}
    mias |= {v for variantes in ordenes._VARIANTES.values() for v in variantes}

    choques = previas & mias
    assert not choques, f"estas variantes ya las atiende una superficie anterior y nunca se alcanzarian: {choques}"


# ====================================== EL REGISTRO FORENSE NO PUEDE MENTIR (M7) --
#
# Encontrado midiendo el audit log REAL `[EJEC]` el 2026-09-21. Traza completa de un turno:
#
#   seq 1047  ERROR ejecutor  [conversacion] ERROR leer_archivo: ruta fuera del ambito permitido
#   seq 1048  CORE  orden     capacidad leer_archivo ejecutada por orden del usuario
#
# La línea del ejecutor dice la verdad; la de la superficie de órdenes afirma «ejecutada» sobre algo
# que NO se ejecutó. El usuario sí recibía la respuesta correcta —`_redactar_resultado_de_orden`
# distingue bien los tres estados—, así que el defecto vive SOLO en la prueba forense: justo donde
# nadie lo ve hasta que hace falta reconstruir qué pasó.
#
# Es «declarado ≠ real» escrito por AURA sobre sí misma, y contradice el punto 4 de `ALERTA-005`
# («nunca informa éxito sin haber obtenido un resultado real») e `INV-9`.


def _marca_de_agua() -> int:
    """`observability` no expone `reset()` y no se le añade uno solo para probar: se mide el tramo
    NUEVO del registro. Un `reset` en la API de produccion seria una puerta para borrar auditoria."""
    return len(obs.audit_records())


def _mensajes_de_orden(desde: int) -> list[str]:
    return [r["msg"] for r in obs.audit_records()[desde:] if r.get("module") == "orden"]


@pytest.mark.asyncio
async def test_el_audit_log_NO_dice_ejecutada_cuando_el_motor_la_detuvo():
    motor = _MotorEspia(
        {
            "accion": "auditar_garantias",
            "estado": "detenida",
            "motivo": "permisos: kill switch activo (5.3 §5)",
            "origen": "conversacion",
        }
    )
    marca = _marca_de_agua()

    await _atender("audita las garantias", motor=motor)

    msgs = _mensajes_de_orden(marca)
    assert msgs, "la superficie de ordenes no dejo rastro forense"
    assert not any("ejecutada" in m for m in msgs), f"el audit log afirma «ejecutada» sobre una orden DETENIDA: {msgs}"
    assert any("detenida" in m for m in msgs), f"el audit log no dice que se detuvo: {msgs}"


@pytest.mark.asyncio
async def test_el_audit_log_NO_dice_ejecutada_cuando_el_motor_fallo():
    motor = _MotorEspia(
        {
            "accion": "leer_archivo",
            "estado": "error",
            "motivo": "ruta fuera del ambito permitido",
            "origen": "conversacion",
        }
    )
    marca = _marca_de_agua()

    await _atender("audita las garantias", motor=motor)

    msgs = _mensajes_de_orden(marca)
    assert not any("ejecutada" in m for m in msgs), f"el audit log afirma «ejecutada» sobre una orden con ERROR: {msgs}"
    assert any("error" in m for m in msgs), f"el audit log no dice que fallo: {msgs}"


@pytest.mark.asyncio
async def test_el_audit_log_SI_dice_ejecutada_cuando_de_verdad_se_ejecuto():
    """Caso de control. Sin él, borrar la palabra «ejecutada» del código pasaría los dos de arriba."""
    motor = _MotorEspia()
    marca = _marca_de_agua()

    await _atender("audita las garantias", motor=motor)

    msgs = _mensajes_de_orden(marca)
    assert any("ejecutada" in m for m in msgs), f"una orden que SI se ejecuto no consta: {msgs}"


@pytest.mark.asyncio
async def test_la_revision_registra_cuantas_capacidades_llegaron_a_ejecutarse():
    """La revisión compone tres capacidades. Si una se bloquea, el registro no puede sugerir que
    las tres corrieron: `Componer no concede autoridad` vale también para la prueba forense."""
    motor = _MotorEspia({"accion": "x", "estado": "detenida", "motivo": "kill switch", "origen": "conversacion"})
    marca = _marca_de_agua()

    await _atender("haz una revision", motor=motor)

    msgs = _mensajes_de_orden(marca)
    assert msgs, "la revision no dejo rastro forense"
    assert not any("ejecutada" in m for m in msgs), (
        f"la revision afirma ejecucion con TODAS las capacidades detenidas: {msgs}"
    )
