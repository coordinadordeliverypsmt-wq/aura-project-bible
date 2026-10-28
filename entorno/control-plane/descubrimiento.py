"""Descubrimiento de trabajo — **de dónde salen las tareas cuando no hay nadie que las entregue**.

`ciclo_autonomo(directorio, ficheros, ...)` sabe encadenar tareas, pero recibe la lista de ficheros
desde fuera. Ese parametro **es** el traspaso manual: alguien decide donde mirar. Este modulo es el
tramo que faltaba encima.

## La regla que hace esto seguro

**Descubrir trabajo no es concederse autoridad.** Son dos decisiones distintas y se toman por
separado: el descubridor mira **todas** las fuentes y clasifica lo que encuentra; quien decide si algo
se ejecuta sigue siendo la politica y el acta del CEO, con el mecanismo que ya existia.

Por eso hay cuatro clases y no dos:

| Clase | Que es | Que se hace |
|---|---|---|
| `OPORTUNIDAD_REAL` | dentro del perimetro autorizado | se convierte en tarea |
| `BLOQUEADA` | real, pero exige acta | se registra y **no se ejecuta** |
| `DECISION_REQUIRED` | ninguna fuente aprobada la determina | se eleva |
| `FALSO_HUECO` | parece un hueco y no lo es | se descarta **con su motivo** |

Un descubridor que solo supiera decir «hay trabajo / no hay trabajo» acabaria empujando hacia la
primera respuesta, porque es la util. Separar «lo hay pero no puedo» de «no lo hay» es lo que hace
que una cola vacia sea una afirmacion con evidencia y no una rendicion.

## El meta-control

Un descubridor que puede inventar trabajo es **peor** que no tener ninguno: produce actividad que
parece progreso. Por eso toda oportunidad trae ocho piezas y la `fuente` tiene que apuntar a algo que
se pueda ir a mirar — un `fichero:linea` o un mecanismo nombrado. Una oportunidad sin procedencia se
rechaza por la misma razon que un porcentaje de cuota sin procedencia: son indistinguibles de las
inventadas.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import pathlib

import autoconstruccion as ac
import control_plane as cp
import entorno_disponible as ent
import estancamiento as est

OPORTUNIDAD_REAL = "OPORTUNIDAD_REAL"
BLOQUEADA = "BLOQUEADA"
DECISION_REQUIRED = "DECISION_REQUIRED"
FALSO_HUECO = "FALSO_HUECO"

CLASES = (OPORTUNIDAD_REAL, BLOQUEADA, DECISION_REQUIRED, FALSO_HUECO)

#: Las ocho piezas. Sin una sola, la oportunidad no es accionable ni auditable: quien la lea manana
#: no sabria de donde salio, que la autoriza ni cuando estaria terminada.
PIEZAS_OBLIGATORIAS = ("fuente", "justificacion", "alcance", "accion", "autoridad",
                       "criterio_de_finalizacion", "evidencia_requerida", "riesgo", "estado")


#: Mecanismos que una fuente puede nombrar en vez de un fichero. **Declarados**, no deducidos: una
#: fuente que valga «porque suena a mecanismo» no comprueba nada.
MECANISMOS_DECLARADOS = ("estado.json:", "eventos.jsonl:seq=", "control_plane.")


def fuente_verificable(fuente: str) -> bool:
    """Si la fuente **lleva de verdad a algun sitio**.

    El constructor solo miraba que la cadena no estuviera en blanco, asi que `fuente="de la nada"`
    producia una oportunidad ejecutable — lo encontro una auditoria independiente, y el docstring
    afirmaba justo lo contrario. La barrera real estaba en la disciplina de las cinco fuentes
    incluidas, y una barrera que depende de que nadie escriba una sexta con un fallo no es una
    barrera.

    Valen dos formas, y solo dos: un `fichero[:linea]` **que exista**, o el nombre de un mecanismo
    **declarado** en `MECANISMOS_DECLARADOS`. Nombrar un mecanismo que no existe tampoco cuela: se
    comprueba que el atributo este de verdad en el modulo."""
    fuente = (fuente or "").strip()
    if not fuente:
        return False
    for prefijo in MECANISMOS_DECLARADOS:
        if not fuente.startswith(prefijo):
            continue
        if prefijo == "control_plane.":
            atributo = fuente[len(prefijo):].split("(")[0].split(" ")[0]
            return hasattr(cp, atributo)
        return True
    candidato = fuente.rsplit(":", 1)[0] if ":" in fuente else fuente
    # `is_file()` y no `exists()`: `fuente="."` existe —es un directorio— y colaba. Una fuente apunta
    # a un sitio concreto que se puede abrir y leer, no a «por ahi».
    return pathlib.Path(candidato).is_file()


class OportunidadSinProcedencia(ValueError):
    """Se intento crear una oportunidad sin fuente verificable.

    Es la unica barrera real contra inventar trabajo, y por eso vive en el constructor y no en una
    comprobacion posterior: lo que no se puede construir no hace falta acordarse de filtrarlo."""


@dataclasses.dataclass(frozen=True)
class Oportunidad:
    """Trabajo **encontrado**, con todo lo necesario para decidir sobre el sin volver a mirar."""
    id: str
    fuente: str
    justificacion: str
    alcance: str
    accion: str
    autoridad: str
    criterio_de_finalizacion: dict
    evidencia_requerida: dict
    riesgo: str
    estado: str
    #: Lo que la fuente sepa y el planificador necesite —el simbolo a eliminar, por ejemplo—. No
    #: entra en las piezas obligatorias porque depende de la fuente: exigirlo a todas obligaria a
    #: rellenarlo con algo, y un campo rellenado por obligacion no informa de nada.
    detalle: dict = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not fuente_verificable(self.fuente):
            raise OportunidadSinProcedencia(
                f"{self.id!r} declara la fuente {self.fuente!r}, que no lleva a ninguna parte. No "
                f"basta con que el campo este relleno: una procedencia que no se puede ir a mirar es "
                f"indistinguible de una inventada, y un descubridor que puede inventar trabajo "
                f"produce actividad que parece progreso")
        if self.estado not in CLASES:
            raise ValueError(f"clase desconocida: {self.estado!r}; validas: {CLASES}")
        for pieza in PIEZAS_OBLIGATORIAS:
            if not getattr(self, pieza):
                raise OportunidadSinProcedencia(f"{self.id!r} no trae {pieza}")

    def como_dict(self) -> dict:
        return dataclasses.asdict(self)


def _id_de(fuente: str, alcance: str, accion: str, distintivo: str = "") -> str:
    """Derivado, no correlativo. Dos descubrimientos de lo mismo dan el mismo id, asi que el
    duplicado se reconoce solo — la misma razon que el `--session-id` del `§13`.

    **`distintivo` es lo que identifica la oportunidad de verdad**, y su ausencia costo un defecto
    real: el id se derivaba de `fichero:linea`, asi que al borrar un simbolo el siguiente **ocupaba la
    linea liberada**, heredaba su id y el antiduplicados lo suprimia. AURA perdia trabajo en silencio
    y el ciclo informaba «cola agotada» habiendo dejado algo sin hacer.

    La identidad de una oportunidad de codigo muerto es **(fichero, simbolo, forma)**. La linea es
    donde estaba, no que es — y ademas se mueve con cualquier edicion de mas arriba, lo que habria
    hecho que la misma oportunidad se viera como nueva en cada vuelta."""
    semilla = f"{fuente}|{alcance}|{accion}|{distintivo}"
    return "OP-" + hashlib.sha256(semilla.encode("utf-8")).hexdigest()[:12]


def _clasificar(directorio, accion: str, alcance) -> tuple[str, str]:
    """Autoridad y clase, **con el mecanismo que ya existe**. Aqui no se decide nada nuevo: se
    pregunta a `ciclo_autonomo.clasificar`, que a su vez consulta zona, materia reservada y acta."""
    import ciclo_autonomo as ca
    nivel = ca.clasificar({"accion": accion, "fichero": str(alcance)}, pathlib.Path(directorio))
    if nivel == "REVIEW":
        return nivel, OPORTUNIDAD_REAL
    return nivel, BLOQUEADA


# ============================================================ LAS FUENTES --

#: **Decision declarada.** Los ficheros huerfanos NO se proponen como codigo muerto. En el plano real
#: hay exactamente uno —`medicion-a11.py`— y no es codigo muerto: es el artefacto que mide el criterio
#: `A11` contra el binario real, y **por eso** nadie lo importa. Un detector cuya unica instancia real
#: seria un error convierte una capacidad en un riesgo. Se declara para que quien lo eche en falta
#: sepa que se miro y se descarto, no que se olvido.
FICHEROS_NO_SE_PROPONEN_COMO_MUERTOS = True

#: Las formas que toma el codigo muerto. El acta autoriza `eliminar_codigo_muerto`; AURA solo sabia
#: ver una de ellas, asi que estaba autorizada a algo que hacia en un tercio. Completar la capacidad
#: **no amplia el perimetro**: misma accion, misma zona.
FORMAS = ("import", "constante", "clase", "funcion", "metodo")


def _usados_en(arbol) -> set:
    """Los nombres que el fichero usa — **incluidos los que exporta**.

    Un nombre listado en `__all__` esta exportado: `from modulo import *` lo entrega. Pero en el arbol
    es una **cadena dentro de una lista**, no un `Name`, asi que un detector que busque usos lo ve
    muerto. Y borrarlo dejaria `__all__` nombrando algo que ya no existe: `import *` fallaria con
    `AttributeError`, y ninguna prueba lo veria porque nadie hace `import *`. Un fallo latente que la
    verificacion de efecto daria por bueno."""
    usados = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
    usados |= {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
    return usados


def _muertos_en(ruta: pathlib.Path) -> list[tuple[str, int, str]]:
    """`(simbolo, linea, forma)` de lo que nadie usa **dentro de su propio fichero**.

    Solo se mira lo **privado** y los imports. Lo publico puede usarse desde fuera del arbol, y
    borrarlo seria romper una interfaz sin saberlo: el acta habla de codigo muerto, no de codigo que
    hoy no veo llamar."""
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):                     # pragma: no cover - fichero no legible
        return []
    usados = _usados_en(arbol)
    fuente = ruta.read_text(encoding="utf-8")
    muertos = []

    for n in arbol.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                nombre = a.asname or a.name.split(".")[0]
                if nombre != "*" and nombre not in usados:
                    muertos.append((nombre, n.lineno, "import"))
        elif isinstance(n, ast.FunctionDef) and n.name.startswith("_") \
                and not n.name.startswith("__") and n.name not in usados:
            muertos.append((n.name, n.lineno, "funcion"))
        elif isinstance(n, ast.ClassDef) and n.name.startswith("_") and n.name not in usados:
            muertos.append((n.name, n.lineno, "clase"))
        elif isinstance(n, ast.Assign):
            for objetivo in n.targets:
                if not isinstance(objetivo, ast.Name) or not objetivo.id.startswith("_"):
                    continue
                apariciones = sum(1 for x in ast.walk(arbol)
                                  if isinstance(x, ast.Name) and x.id == objetivo.id)
                if apariciones <= 1:
                    muertos.append((objetivo.id, n.lineno, "constante"))

    for c in [n for n in arbol.body if isinstance(n, ast.ClassDef)]:
        cuerpo = ast.unparse(c)
        for m in [x for x in c.body if isinstance(x, ast.FunctionDef)
                  and x.name.startswith("_") and not x.name.startswith("__")]:
            if cuerpo.count(m.name) <= 1 and f"{c.name}.{m.name}" not in fuente:
                muertos.append((f"{c.name}.{m.name}", m.lineno, "metodo"))

    # **La segunda barrera, en su primer punto de aplicacion.** El detector responde a «parece que
    # nadie lo usa»; `es_eliminable` responde a «¿es esto eliminable, mire quien lo mire?». Aplicarla
    # aqui evita que un falso positivo llegue siquiera a proponerse, y no consuma revisor, acta ni una
    # vuelta del ciclo. La regla vive en un solo sitio: aqui se **consulta**, no se reimplementa.
    return [(s, ln, forma) for s, ln, forma in muertos
            if ac.es_eliminable(fuente, s, forma)[0]]


def codigo_muerto(raiz: pathlib.Path, directorio) -> list[Oportunidad]:
    """Funciones privadas que nadie llama. La fuente cita `fichero:linea`.

    **El falso hueco importa tanto como el hueco**: una privada usada desde otro modulo parece muerta
    en su fichero y no lo esta. Borrarla romperia una interfaz sin saberlo, asi que se comprueba
    contra el arbol entero y, si se usa fuera, se descarta **diciendo por que**."""
    ficheros = sorted(p for p in raiz.rglob("*.py")
                      if not p.name.startswith(("test_", "conftest")))
    # **El perimetro que el acta anade no cuelga de `raiz`.** Ampliar la zona sin ampliar el barrido
    # habria dejado la autorizacion sin efecto: `zona_permitida` dice que se puede tocar, `raiz` dice
    # donde se mira, y son dos cosas distintas. La lista de ficheros exactos vive en
    # `autoconstruccion`, que es la unica fuente de verdad sobre el perimetro: aqui se consulta.
    ficheros = sorted(set(ficheros) | set(ac.ficheros_autorizados()))
    fuera = {}
    for otro in ficheros:
        try:
            texto = otro.read_text(encoding="utf-8")
        except OSError:                                # pragma: no cover
            continue
        fuera[otro] = texto

    halladas = []
    for fichero in ficheros:
        for simbolo, linea, forma in _muertos_en(fichero):
            # Un `import` solo vive en su fichero: que su nombre aparezca en otro modulo no significa
            # nada —cada uno tiene los suyos—. Para lo demas, aparecer fuera si es senal de uso.
            buscado = simbolo.split(".")[-1]
            usada_fuera = (forma != "import" and
                           any(buscado in texto for otro, texto in fuera.items() if otro != fichero))
            fuente = f"{fichero}:{linea}"
            identidad = f"{simbolo}:{forma}"     # lo que la oportunidad ES, no donde esta hoy
            if usada_fuera:
                halladas.append(Oportunidad(
                    id=_id_de(str(fichero), str(fichero), "eliminar_codigo_muerto", identidad),
                    fuente=fuente,
                    justificacion=(f"{simbolo} ({forma}) parece muerta en su fichero pero se usa "
                                   f"desde otro modulo: borrarla romperia una interfaz sin saberlo"),
                    alcance=str(fichero), accion="eliminar_codigo_muerto", autoridad="NINGUNA",
                    criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
                    evidencia_requerida={"tipo": "fichero_existe", "ruta": str(fichero)},
                    riesgo="ninguno", estado=FALSO_HUECO,
                    detalle={"simbolo": simbolo, "forma": forma, "usada_fuera": True}))
                continue
            autoridad, clase = _clasificar(directorio, "eliminar_codigo_muerto", fichero)
            halladas.append(Oportunidad(
                id=_id_de(str(fichero), str(fichero), "eliminar_codigo_muerto", identidad),
                fuente=fuente,
                justificacion=(f"{simbolo} es {forma} muerto: nadie lo usa, ni en su fichero ni en "
                               f"el resto del arbol"),
                alcance=str(fichero), accion="eliminar_codigo_muerto", autoridad=autoridad,
                criterio_de_finalizacion={"capacidad": "ejecutar_pruebas"},
                evidencia_requerida={"tipo": "fichero_existe", "ruta": str(fichero)},
                riesgo="bajo: reversible y verificable releyendo el fichero",
                estado=clase, detalle={"simbolo": simbolo, "forma": forma, "linea": linea}))
    return halladas


def invocables_sin_clasificar(_raiz, directorio) -> list[Oportunidad]:
    """Un invocable que nombra el estado final y no esta declarado. Lo detecta el meta-control que
    ya existe; aqui solo se convierte en oportunidad, y sale **bloqueada**: clasificar un invocable
    es tocar la lista de lo gobernado, y eso no esta en el alcance de ningun acta."""
    return [Oportunidad(
        id=_id_de("control_plane.invocables_sin_clasificar", nombre, "clasificar_invocable"),
        fuente=f"control_plane.invocables_sin_clasificar() -> {nombre}",
        justificacion=(f"{nombre} nombra el estado final y no esta en ninguna de las tres listas: "
                       f"«no esta clasificado» ha significado «nadie lo ha mirado» cuatro veces"),
        alcance=nombre, accion="clasificar_invocable", autoridad="CEO",
        criterio_de_finalizacion={"capacidad": "auditar_garantias"},
        evidencia_requerida={"tipo": "salida_contiene", "patron": nombre},
        riesgo="alto: toca la lista de funciones gobernadas",
        estado=BLOQUEADA) for nombre in cp.invocables_sin_clasificar()]


def eventos_sin_puerta(_raiz, directorio) -> list[Oportunidad]:
    """Un evento que concede estado y no declara por que puerta se escribe. El mensaje de rechazo lo
    necesita: un «esto no» sin «esto si» empuja a rodearlo, y asi nacen las rutas alternativas."""
    return [Oportunidad(
        id=_id_de("control_plane.EVENTOS_GOBERNADOS", tipo, "declarar_puerta"),
        fuente=f"control_plane.EVENTOS_GOBERNADOS -> {tipo}",
        justificacion=f"{tipo} concede estado y no tiene puerta declarada en _PUERTA_DE",
        alcance=tipo, accion="declarar_puerta", autoridad="CEO",
        criterio_de_finalizacion={"capacidad": "auditar_garantias"},
        evidencia_requerida={"tipo": "salida_contiene", "patron": tipo},
        riesgo="alto: toca el gobierno de eventos",
        estado=BLOQUEADA)
        for tipo in sorted(cp.EVENTOS_GOBERNADOS) if tipo not in cp._PUERTA_DE]


def decisiones_pendientes(_raiz, directorio) -> list[Oportunidad]:
    """Preguntas abiertas registradas en el historial. **No son trabajo**: son decisiones, y
    convertirlas en tarea seria resolverlas por cuenta propia (`ADR-0003:33`)."""
    vistas = []
    for evento in cp.leer_eventos(pathlib.Path(directorio)):
        if evento["tipo"] != "decision_pendiente":
            continue
        datos = evento["datos"]
        ident = datos.get("id") or f"seq-{evento['seq']}"
        vistas.append(Oportunidad(
            id=_id_de(f"eventos.jsonl:seq={evento['seq']}", ident, "resolver_decision"),
            fuente=f"eventos.jsonl:seq={evento['seq']}",
            justificacion=(datos.get("pregunta") or datos.get("titulo")
                           or "decision registrada sin resolver"),
            alcance=ident, accion="resolver_decision", autoridad="CEO",
            criterio_de_finalizacion={"capacidad": "diagnosticar_estado"},
            evidencia_requerida={"tipo": "salida_contiene", "patron": ident},
            riesgo="ninguno: no se ejecuta",
            estado=DECISION_REQUIRED))

    # Y las del `estado.json`, que es donde viven las que el CEO tiene sobre la mesa. Mirar solo el
    # log dejaba fuera `D-ORCH-6` — lo destapo ejecutar el diagnostico contra el plano real, no
    # leerlo: el descubridor decia «0 decisiones» con una registrada desde hacia dias.
    ruta = pathlib.Path(directorio) / "estado.json"
    if ruta.exists():
        try:
            estado = cp.cargar(ruta)
        except Exception:                              # pragma: no cover - estado ilegible
            estado = {}
        for pendiente in estado.get("decisiones_pendientes", []) or []:
            ident = pendiente.get("id", "D-?")
            vistas.append(Oportunidad(
                id=_id_de(f"estado.json:decisiones_pendientes:{ident}", ident, "resolver_decision"),
                fuente=f"estado.json:decisiones_pendientes:{ident}",
                justificacion=(pendiente.get("titulo") or pendiente.get("pregunta")
                               or "decision registrada sin resolver"),
                alcance=ident, accion="resolver_decision",
                autoridad="CEO",
                criterio_de_finalizacion={"capacidad": "diagnosticar_estado"},
                evidencia_requerida={"tipo": "salida_contiene", "patron": ident},
                riesgo="ninguno: no se ejecuta",
                estado=DECISION_REQUIRED))
    return vistas


def bloqueos_registrados(_raiz, directorio) -> list[Oportunidad]:
    """Lo que el propio estado ya declara fuera de alcance. Se redescubre a proposito: que siga
    apareciendo en cada vuelta es lo que impide que un bloqueo se convierta en un olvido."""
    ruta = pathlib.Path(directorio) / "estado.json"
    if not ruta.exists():
        return []
    try:
        estado = cp.cargar(ruta)
    except Exception:                                  # pragma: no cover - estado ilegible
        return []
    vistas = []
    for bloqueada in estado.get("oportunidades_bloqueadas", []) or []:
        ident = bloqueada.get("id", "OB-?")
        quien = bloqueada.get("quien_desbloquea", "CEO")
        # **Lo ya decidido no vuelve a la bandeja de excepciones.** Una entrada cuyo propio registro
        # dice que **nadie** la desbloquea porque esta cerrada no es un bloqueo esperando decision:
        # es una cuestion resuelta, y contarla como pendiente convierte una decision tomada en una
        # por tomar. Su clase ya existe: `FALSO_HUECO` —«parece un hueco y no lo es»—.
        #
        # El criterio se **lee del dato**, no se deduce: solo cuando el desbloqueador declarado es
        # literalmente «nadie». Sin campo, o con un desbloqueador nombrado, sigue bloqueada
        # (fail-closed: la ausencia no es una declaracion de cierre).
        cerrada = str(quien).strip().lower().startswith("nadie")
        vistas.append(Oportunidad(
            id=_id_de(f"estado.json:oportunidades_bloqueadas:{ident}", ident, "desbloquear"),
            fuente=f"estado.json:oportunidades_bloqueadas:{ident}",
            justificacion=(f"cerrada, no pendiente: {bloqueada.get('por_que', '')}".strip(": ")
                           if cerrada else bloqueada.get("por_que", "registrada como bloqueada")),
            alcance=bloqueada.get("que", ident), accion="desbloquear",
            autoridad=quien,
            criterio_de_finalizacion={"capacidad": "diagnosticar_estado"},
            evidencia_requerida={"tipo": "salida_contiene", "patron": ident},
            riesgo="ninguno: ya decidida" if cerrada else "no evaluable sin acta",
            estado=FALSO_HUECO if cerrada else BLOQUEADA))
    return vistas


# **El import va aqui abajo, no arriba, y es deliberado.** `formacion` importa este modulo para
# construir `Oportunidad`, asi que importarlo en la cabecera cerraria el ciclo antes de que las
# constantes existan. Colocado despues de ellas, el ciclo se resuelve y no hace falta envoltorio.
import formacion as frm  # noqa: E402

#: Las fuentes que el contrato ya reconoce. Una sola fuente volveria a ser una lista escrita a mano,
#: solo que mas corta — el defecto que este proyecto lleva cuatro auditorias corrigiendo.
FUENTES = {
    "codigo_muerto": codigo_muerto,
    "invocables_sin_clasificar": invocables_sin_clasificar,
    "eventos_sin_puerta": eventos_sin_puerta,
    "decisiones_pendientes": decisiones_pendientes,
    "bloqueos_registrados": bloqueos_registrados,
    # Sexta fuente (DP-SELF-EVOLUTION-01 · Fase A): observa el historial y eleva estancamiento como
    # DECISION_REQUIRED. Solo lectura, inerte mientras el acta no fije K. No requiere tocar el motor:
    # `descubrir()` recorre este dict, asi que basta con estar aqui.
    "estancamiento": est.estancamiento,
    # Septima fuente (DR-A): observa el ENTORNO DE EJECUCION —procesos, puertos en escucha, modelos
    # locales— leyendo lo que el nucleo ya publica. Ni ejecuta, ni escribe, ni pregunta por red. Su
    # techo es DECISION_REQUIRED: eleva conocimiento, nunca permiso.
    "capacidades_del_entorno": ent.entorno,
    # Octava fuente: **el plan de formacion**. Es el unico documento de la evolucion de AURA que le
    # era invisible. Su techo es DECISION_REQUIRED por construccion —lo fija el propio plan: «ninguna
    # capacidad se desarrolla automaticamente»—, asi que ver lo que le falta no le concede permiso
    # para construirlo. Solo lectura. El import va aqui abajo para no cerrar un ciclo: `formacion`
    # importa este modulo.
    "capacidades_declaradas": frm.formacion,
}


def descubrir(raiz, directorio) -> list[Oportunidad]:
    """Recorre **todas** las fuentes y devuelve lo encontrado, clasificado.

    Una fuente que revienta no puede dejar ciego al descubridor entero: se anota y se sigue. Un
    descubrimiento parcial declarado es mejor que ninguno, y muy mejor que uno que se cree completo."""
    raiz = pathlib.Path(raiz)
    encontradas: list[Oportunidad] = []
    fallos = []
    for nombre, fuente in FUENTES.items():
        try:
            encontradas.extend(fuente(raiz, directorio))
        except Exception as exc:                       # pragma: no cover - fuente defectuosa
            fallos.append({"fuente": nombre, "error": f"{type(exc).__name__}: {exc}"[:200]})
    cp.registrar_evento(pathlib.Path(directorio), "descubrimiento_realizado", {
        "raiz": str(raiz), "encontradas": len(encontradas), "fuentes": sorted(FUENTES),
        "por_clase": {c: sum(1 for o in encontradas if o.estado == c) for c in CLASES},
        "fuentes_con_error": fallos})
    return encontradas


def resumen(encontradas) -> dict:
    """Lo que hay que poder decir sin volver a mirar: cuanto de cada clase."""
    return {clase: [o.id for o in encontradas if o.estado == clase] for clase in CLASES}


def hay_trabajo_autorizado(encontradas) -> bool:
    """Una cola vacia deja de significar «no puedo hacer nada» y pasa a significar «no hay trabajo
    autorizado ahora mismo», que es una afirmacion con evidencia detras."""
    return any(o.estado == OPORTUNIDAD_REAL for o in encontradas)


__all__ = ["Oportunidad", "OportunidadSinProcedencia", "descubrir", "resumen",
           "hay_trabajo_autorizado", "FUENTES", "CLASES", "PIEZAS_OBLIGATORIAS",
           "OPORTUNIDAD_REAL", "BLOQUEADA", "DECISION_REQUIRED", "FALSO_HUECO",
]
