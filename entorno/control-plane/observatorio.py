"""El **observatorio** — mirar a AURA sin tocarla.

    python3 aura.py estado       # que esta haciendo ahora
    python3 aura.py historial    # que ha hecho, ciclo a ciclo
    python3 aura.py ultimo       # el ultimo ciclo, entero

AURA ya trabaja sola. Lo que faltaba no era capacidad: era que un humano pudiera preguntar «¿que
estas haciendo?» sin **entrar en el motor**, sin Claude Code y sin interferir en el ciclo. Este modulo
es exactamente eso y nada mas: **lee**.

## Por que es un modulo aparte y no unas lineas en `aura.py`

Porque «solo lectura» tiene que poder demostrarse, no prometerse. Al vivir aparte, la garantia se
comprueba sobre el arbol sintactico —igual que en `despertador.py`—: aqui no aparecen `registrar_evento`,
`transicion`, `guardar`, `write_text` ni `trabajar`. Una consola que *resulta* que hoy no escribe
volvera a escribir en cuanto alguien le anada una comodidad.

Y hay una trampa concreta que esa garantia cierra. `descubrimiento.descubrir()` **registra un evento**
(`descubrimiento.py:414`). Una consola que descubriera para «ensenar la cola actualizada» escribiria en
el historial **cada vez que alguien la mira**, y el log dejaria de ser el registro de lo que hizo AURA
para ser tambien el de quien la estuvo observando. Por eso el observatorio no descubre: informa de lo
que AURA registro. Quien quiera mirar el arbol en vivo tiene `aura.py diagnosticar`, que si trabaja.

## Las tres alturas, que no son la misma cosa

La forma en que una consola miente no es inventandose una frase: es **colapsar niveles**.

| | Que significa | Como consta |
|---|---|---|
| **despertar** | el `cron` llamo | `aura_despertada` · `despertar_rechazado` |
| **ciclo** | el motor arranco y termino | `motor_iniciado` → `ciclo_detenido` |
| **trabajo** | hubo un efecto real y verificado | `cambio_aplicado` con `efecto_verificado` |

El `cron` desperto a AURA 61 veces y AURA no toco un fichero en ninguna. Una consola que contara
despertares como trabajo informaria de 61 trabajos. Por eso las tres cifras se cuentan por separado y
se imprimen con su nombre.

## La regla que gobierna todo lo demas

> **Si el dato no esta en la fuente, la respuesta es `NO DISPONIBLE`.**

Nunca `0`, nunca «ninguno», nunca una estimacion razonable. Cero es una medicion; ausente es la falta
de una, y verlas iguales es como se fabrican los informes que tranquilizan. La contrapartida es igual
de importante: lo que **si** se puede derivar de una fuente, se deriva —los actos humanos de un ciclo
se cuentan de su rango de eventos aunque el cierre no los anotara—. La regla no es «ante la duda, NO
DISPONIBLE»: es «no rellenar huecos».

## Nivel y flujo no se suman igual

`ejecutadas` es un **flujo**: se acumula, y el total tiene sentido. `bloqueadas` es un **nivel**: son
las mismas seis oportunidades vistas noventa veces. Sumarlas daria «540 bloqueadas» y seria basura. Los
niveles se leen del ultimo descubrimiento; los flujos, de toda la historia. El render lo dice.

## Fuentes, y que pasa cuando no coinciden

El log encadenado manda —ADR-0023: la proyeccion debe poder borrarse y regenerarse desde el historial—.
Pero que mande no significa que la discrepancia se resuelva **en silencio**: si `estado.json` lleva dias
diciendo otra cosa, *eso* es la noticia. Las contradicciones se listan; no se arreglan.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess

import control_plane as cp
import orquestador as orq

#: La respuesta honesta a un hueco. Es una cadena y no `None` a proposito: `None` se imprime como
#: «None» o se confunde con un cero al pasar por un `or`, y el hueco se pierde justo al mostrarlo.
NO_DISPONIBLE = "NO DISPONIBLE"

ESTADOS = ("TRABAJANDO", "ESPERANDO", "BLOQUEADA", "DECISION_REQUIRED", "ERROR")

#: Un ciclo se abre con uno de estos y se cierra con el que le corresponde. Son dos vocabularios
#: distintos porque los escriben dos piezas distintas —el motor y el orquestador—, y unificarlos
#: seria reescribir historia ya registrada.
APERTURAS = {"motor_iniciado": "ciclo_detenido",
             "ciclo_autonomo_iniciado": "ciclo_autonomo_terminado"}
CIERRES = {cierre: apertura for apertura, cierre in APERTURAS.items()}

#: El motivo de parada se llama distinto segun quien cierre. Se traducen los dos; lo que **no** se
#: hace es inventar el campo que un cierre no trajo.
_CLAVES_DE_MOTIVO = ("motivo", "motivo_de_parada")

LIMITE_HISTORIAL = 20

#: Cota del barrido hacia delante al derivar el proximo despertar. `§14`: ningun recorrido sin cota.
_MINUTOS_MAXIMOS = 8 * 24 * 60


# --------------------------------------------------------------- huecos --

def _dato(datos: dict, *claves):
    """El valor de la primera clave que **conste**, o `NO_DISPONIBLE`.

    Nota deliberada: se comprueba `in`, no la verdad del valor. Un `0` o un `False` registrados son
    datos, y un `datos.get(clave) or NO_DISPONIBLE` los borraria — que es exactamente el error que
    este modulo existe para no cometer."""
    for clave in claves:
        if clave in (datos or {}):
            return datos[clave]
    return NO_DISPONIBLE


def _es_numero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


# --------------------------------------------------------------- ciclos --

def _actos_humanos_en(eventos: list) -> int:
    """Cuantos actos de autoridad humana caen dentro del ciclo.

    Misma regla que usa el motor (`_actos_humanos_desde`): se cuenta del historial, que es donde
    consta quien hizo que. Es la cifra que decide si un ciclo fue autonomo o asistido, asi que
    callarla haria indistinguibles las dos cosas."""
    return sum(1 for e in eventos
               if (e.get("datos") or {}).get("autoridad") in cp.AUTORIDADES_HUMANAS)


def _trabajos_en(eventos: list) -> list:
    """Los cambios aplicados **por AURA** dentro de un tramo.

    Un `cambio_aplicado` con autoridad humana es trabajo del humano. Atribuirselo a AURA convertiria
    el informe en una felicitacion."""
    salida = []
    for e in eventos:
        if e.get("tipo") != "cambio_aplicado":
            continue
        d = e.get("datos") or {}
        if d.get("autoridad") in cp.AUTORIDADES_HUMANAS:
            continue
        salida.append(e)
    return salida


def _efecto_real(evento: dict) -> bool:
    """Que el cambio dejara un efecto que siga en pie.

    Tres condiciones, y las tres han fallado alguna vez en este proyecto: que se verificara, que la
    verificacion **fuera capaz de fallar** (`verificacion_sana`), y que no se revirtiera despues. Un
    efecto «verificado» por una comprobacion que no verifica es el falso PASS de siempre."""
    d = evento.get("datos") or {}
    return bool(d.get("efecto_verificado")) and bool(d.get("verificacion_sana")) \
        and not d.get("revertido", False)


def _detalle_de_trabajo(evento: dict, eventos: list, integro: bool) -> dict:
    """Un trabajo con su cadena de cinco etapas y su procedencia."""
    d = evento.get("datos") or {}
    ident = _dato(d, "id")
    autorizacion = None
    criterio = None
    if ident != NO_DISPONIBLE:
        for otro in eventos:
            od = otro.get("datos") or {}
            if od.get("id") != ident:
                continue
            if otro.get("tipo") == "propuesta_autorizada":
                autorizacion = od
            elif otro.get("tipo") == "criterio_verificado":
                criterio = od
    descubierta = any(e.get("tipo") == "descubrimiento_realizado"
                      and _es_numero((e.get("datos") or {}).get("encontradas"))
                      and (e.get("datos") or {})["encontradas"] > 0
                      for e in eventos)
    return {
        "id": ident,
        "fichero": _dato(d, "fichero"),
        "simbolo": _dato(d, "simbolo"),
        "forma": _dato(d, "forma"),
        "momento": _dato(evento, "momento"),
        "autoridad": _dato(d, "autoridad"),
        "autorizada_por": _dato(autorizacion or {}, "autorizada_por"),
        "acta": _dato(autorizacion or {}, "acta"),
        # Registrado, no deducido: `propuesta_autorizada` y `cambio_aplicado` comparten el `id`. Se
        # dice explicitamente porque otros enlaces del circuito solo se pueden **derivar**, y vender
        # una deduccion como un hecho es como se construyen los informes falsos.
        "enlace": "REGISTRADO" if autorizacion else NO_DISPONIBLE,
        "efecto_verificado": _dato(d, "efecto_verificado"),
        "verificacion_sana": _dato(d, "verificacion_sana"),
        "revertido": _dato(d, "revertido"),
        "resultado": "efecto verificado" if _efecto_real(evento) else "sin efecto acreditado",
        "pruebas": criterio.get("criterio") if criterio else NO_DISPONIBLE,
        "etapas": {"descubierta": descubierta,
                   "autorizada": autorizacion is not None,
                   "ejecutada": True,
                   "efecto_verificado": _efecto_real(evento),
                   "registrada": bool(integro)},
    }


def ciclos(directorio, eventos=None, integro=None) -> list:
    """Los ciclos emparejados apertura/cierre, del mas antiguo al mas reciente.

    Un ciclo que abrio y no consta que cerrara queda **abierto**: puede estar corriendo o puede haber
    muerto, pero lo que no puede es aparecer como un ciclo limpio.

    `eventos` e `integro` se pueden pasar YA CALCULADOS. No es una optimizacion prematura: `estado()`
    leia el log cuatro veces y verificaba la cadena dos por cada llamada —940 hashes sobre 470
    eventos—, y el coste crece con un historial que no para de crecer (~200 eventos al dia). Medido
    en conversacion, un turno normal costaba 30 ms y preguntar «¿en que estas trabajando?» 239 ms.
    Compartir la lectura **dentro de una misma llamada** no cambia ni un resultado: sigue siendo la
    misma foto del log, leida una vez en vez de cuatro. Lo que NO se hace es cachear entre llamadas,
    que si cambiaria respuestas -el `cron` avanza el ciclo cada media hora-."""
    directorio = pathlib.Path(directorio)
    if eventos is None:
        eventos = cp.leer_eventos(directorio)
    if integro is None:
        integro = bool(cp.verificar_integridad_log(directorio).get("integro"))

    salida, abierto = [], None
    for evento in eventos:
        tipo = evento.get("tipo")
        if tipo in APERTURAS:
            if abierto is not None:
                salida.append(abierto)
            abierto = {"apertura": evento, "cierre": None, "eventos": [evento]}
            continue
        if abierto is None:
            continue
        abierto["eventos"].append(evento)
        if tipo in CIERRES and CIERRES[tipo] == abierto["apertura"]["tipo"]:
            abierto["cierre"] = evento
            salida.append(abierto)
            abierto = None
    if abierto is not None:
        salida.append(abierto)

    return [_resumir_ciclo(i + 1, c, integro) for i, c in enumerate(salida)]


def _resumir_ciclo(numero: int, crudo: dict, integro: bool) -> dict:
    cierre = crudo["cierre"]
    cerrado = cierre is not None
    dc = (cierre.get("datos") or {}) if cerrado else {}
    descubrimientos = [e for e in crudo["eventos"] if e.get("tipo") == "descubrimiento_realizado"]
    ultimo_descubrimiento = (descubrimientos[-1].get("datos") or {}) if descubrimientos else {}
    trabajos = _trabajos_en(crudo["eventos"])
    return {
        "numero": numero,
        "abierto": not cerrado,
        "inicio": _dato(crudo["apertura"], "momento"),
        "fin": _dato(cierre, "momento") if cerrado else NO_DISPONIBLE,
        "motivo_de_parada": _dato(dc, *_CLAVES_DE_MOTIVO) if cerrado else NO_DISPONIBLE,
        "descubiertas": _dato(ultimo_descubrimiento, "encontradas"),
        "por_clase": ultimo_descubrimiento.get("por_clase", NO_DISPONIBLE),
        "ejecutadas": _dato(dc, "ejecutadas") if cerrado else NO_DISPONIBLE,
        "bloqueadas": _dato(dc, "bloqueadas") if cerrado else NO_DISPONIBLE,
        "elevadas": _dato(dc, "elevadas") if cerrado else NO_DISPONIBLE,
        # Derivado del rango del propio ciclo: se puede medir aunque el cierre no lo anotara.
        "actos_humanos": _actos_humanos_en(crudo["eventos"]),
        "actos_humanos_registrados": _dato(dc, "actos_humanos_durante_el_ciclo", "actos_humanos"),
        "tareas_ejecutadas": [_detalle_de_trabajo(t, crudo["eventos"], integro) for t in trabajos],
        "efecto_real": sum(1 for t in trabajos if _efecto_real(t)),
    }


# --------------------------------------------------------------- proximo despertar --

def _lineas_de_cron() -> list:
    """Las lineas del `cron` que despiertan a AURA. Aislada para poder sustituirla en las pruebas y
    porque un `crontab` que no existe es un hueco, no un fallo."""
    try:
        salida = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    if salida.returncode != 0:
        return []
    lineas = [linea.strip() for linea in salida.stdout.splitlines()]
    return [linea for linea in lineas
            if linea and not linea.startswith("#") and "despertar-aura" in linea]


def _campo_de_cron(campo: str, tope: int):
    """Los valores que casan con un campo, o `None` si no se sabe derivarlo.

    Se soportan `*`, `*/N` y listas de enteros. Cualquier otra forma devuelve `None` y el proximo
    despertar sale `NO DISPONIBLE`: aproximar «mas o menos el lunes» seria justo el numero sin
    derivacion formal que el CEO prohibio publicar."""
    if campo == "*":
        return set(range(tope))
    if campo.startswith("*/"):
        try:
            paso = int(campo[2:])
        except ValueError:
            return None
        return set(range(0, tope, paso)) if paso > 0 else None
    valores = set()
    for trozo in campo.split(","):
        if not trozo.isdigit():
            return None
        valor = int(trozo)
        if not 0 <= valor < tope:
            return None
        valores.add(valor)
    return valores or None


def proximo_despertar(ahora: dt.datetime | None = None) -> str:
    """La proxima vez que el `cron` despertara a AURA, derivada de la linea real.

    Leer el `crontab` es consultar una fuente. Estimarlo de la cadencia observada en el historial
    seria adivinar, y adivinar bien la mayoria de las veces es la peor forma de fallar: nadie
    comprueba lo que suele acertar."""
    lineas = _lineas_de_cron()
    if not lineas:
        return NO_DISPONIBLE
    campos = lineas[0].split()
    if len(campos) < 5:
        return NO_DISPONIBLE
    minuto, hora, dia, mes, semana = campos[:5]
    if (dia, mes, semana) != ("*", "*", "*"):
        # Dias del mes o de la semana: no se sabe resolver, y se dice.
        return NO_DISPONIBLE
    minutos = _campo_de_cron(minuto, 60)
    horas = _campo_de_cron(hora, 24)
    if minutos is None or horas is None:
        return NO_DISPONIBLE

    momento = (ahora or dt.datetime.now()).replace(second=0, microsecond=0)
    for _ in range(_MINUTOS_MAXIMOS):
        momento += dt.timedelta(minutes=1)
        if momento.minute in minutos and momento.hour in horas:
            return momento.isoformat()
    return NO_DISPONIBLE


# --------------------------------------------------------------- contradicciones --

def _proyeccion(directorio: pathlib.Path):
    ruta = directorio / "estado.json"
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _contradicciones(directorio: pathlib.Path, eventos: list, lista_de_ciclos: list,
                     proyeccion=None) -> list:
    """Donde dos fuentes dicen cosas distintas. **No** se arregla ninguna: se listan.

    El log manda, pero que mande no autoriza a resolver la diferencia en silencio. Si la proyeccion
    lleva dias desfasada, eso *es* la noticia.

    ### Lo que aqui NO se compara, y por que

    La primera version comparaba `estado.json["status"]` con el estado del ciclo, filtrando por
    `declarado in ESTADOS`. Una auditoria independiente lo tumbo midiendo: ese campo usa el
    vocabulario de estados de **tarea** de `control_plane` —`WORKING`, `WAITING_FOR_NEXT_TASK`,
    `COMPLETED`…—, y este modulo usa el del **ciclo** —`TRABAJANDO`, `ESPERANDO`…—. Solo
    `DECISION_REQUIRED` aparece en los dos, por casualidad. Resultado: siete de los ocho valores
    reales no disparaban nunca, y el filtro que yo habia puesto «por prudencia» era justo lo que
    mataba la comprobacion en silencio.

    Son **dos ejes distintos**: el estado de la tarea en curso y el estado del ciclo autonomo. No se
    contradicen porque no hablan de lo mismo. Fingir que se comparan producia una comprobacion que
    solo podia dar la respuesta tranquilizadora, que es la peor clase de comprobacion que hay.

    Lo que si es comparable —y es la discrepancia que de verdad ocurre— es la **frescura**: la
    proyeccion tiene una fecha de actualizacion y el log tiene un ultimo evento. Cuando la primera
    va por detras del segundo, la proyeccion esta desfasada, y eso se puede medir sin interpretar
    nada. En el momento de escribir esto llevaba siete horas por detras."""
    avisos = []
    if proyeccion is None:
        proyeccion = _proyeccion(directorio)
    ultimo_momento = _dato(eventos[-1], "momento") if eventos else NO_DISPONIBLE
    if proyeccion is not None:
        actualizado = proyeccion.get("actualizado")
        if actualizado and ultimo_momento != NO_DISPONIBLE and str(actualizado) < str(ultimo_momento):
            avisos.append(f"estado.json se actualizo el {actualizado} y el historial llega hasta "
                          f"{ultimo_momento}: la proyeccion va por detras del log")
    abandonados = [c["numero"] for c in lista_de_ciclos[:-1] if c["abierto"]]
    if abandonados:
        # Certeza, no sospecha: otro ciclo arranco despues, asi que este no puede estar corriendo.
        avisos.append(f"ciclos que abrieron y nunca cerraron, y que otro ciclo posterior deja sin "
                      f"duda abandonados: {abandonados}")
    for ciclo in lista_de_ciclos:
        registrados = ciclo["actos_humanos_registrados"]
        if _es_numero(registrados) and registrados != ciclo["actos_humanos"]:
            avisos.append(f"ciclo {ciclo['numero']}: el cierre anoto {registrados} actos humanos y "
                          f"en su tramo constan {ciclo['actos_humanos']}")
        ejecutadas = ciclo["ejecutadas"]
        if _es_numero(ejecutadas) and ejecutadas != ciclo["efecto_real"]:
            avisos.append(f"ciclo {ciclo['numero']}: el cierre anoto {ejecutadas} ejecutadas y "
                          f"constan {ciclo['efecto_real']} efectos verificados")
    return avisos


def _antiguedad(desde: str, ahora: dt.datetime | None = None) -> str:
    """Cuanto lleva abierto, en texto. `NO DISPONIBLE` si no hay marca de tiempo que restar."""
    if desde == NO_DISPONIBLE:
        return NO_DISPONIBLE
    try:
        inicio = dt.datetime.fromisoformat(str(desde))
    except ValueError:
        return NO_DISPONIBLE
    segundos = int(((ahora or dt.datetime.now()) - inicio).total_seconds())
    if segundos < 0:
        return NO_DISPONIBLE
    horas, resto = divmod(segundos, 3600)
    return f"{horas}h {resto // 60:02d}m"


def _periodo_del_cron(ahora: dt.datetime | None = None) -> int | None:
    """Cada cuantos minutos despierta el `cron`, derivado de dos disparos consecutivos.

    Sirve para poder decir algo mas fuerte que «lleva un rato»: si un ciclo lleva abierto mas de lo
    que tarda el `cron` en volver, ya paso un despertar entero sin que cerrara. Es una comparacion
    contra una fuente real, no un umbral inventado — y si el `cron` no se sabe leer, no se dice
    nada, que es lo que corresponde cuando no hay referencia."""
    momento = (ahora or dt.datetime.now()).replace(second=0, microsecond=0)
    primero = proximo_despertar(momento)
    if primero == NO_DISPONIBLE:
        return None
    segundo = proximo_despertar(dt.datetime.fromisoformat(primero))
    if segundo == NO_DISPONIBLE:
        return None
    return int((dt.datetime.fromisoformat(segundo)
                - dt.datetime.fromisoformat(primero)).total_seconds() // 60)


def _sospecha_de_ciclo_muerto(ciclo: dict, ahora: dt.datetime | None = None) -> str:
    """El aviso que convierte un `TRABAJANDO` mudo en informacion.

    Un ciclo abierto puede estar corriendo o puede haber muerto, y el informe no puede decidirlo. Lo
    que si puede es **decir cuanto lleva** y contrastarlo con la unica referencia real que hay: cada
    cuanto vuelve el `cron`. Sin esto, un proceso muerto hace horas se lee igual que uno trabajando
    ahora mismo — que es exactamente el falso positivo que encontro la auditoria."""
    if not ciclo["abierto"]:
        return ""
    edad = _antiguedad(ciclo["inicio"], ahora)
    if edad == NO_DISPONIBLE:
        return "el ciclo abrio y no consta que terminara"
    periodo = _periodo_del_cron(ahora)
    aviso = f"el ciclo abrio hace {edad} y no consta que terminara"
    if periodo is not None:
        try:
            transcurridos = int(((ahora or dt.datetime.now())
                                 - dt.datetime.fromisoformat(str(ciclo["inicio"]))
                                 ).total_seconds() // 60)
        except ValueError:
            return aviso
        if transcurridos > periodo:
            aviso += (f"; el cron vuelve cada {periodo} min, asi que ya paso un despertar entero "
                      f"sin que cerrara")
    return aviso


# --------------------------------------------------------------- estado --

def _estado_actual(directorio: pathlib.Path, lista_de_ciclos: list, integro: bool) -> str:
    """En orden de fuerza del hecho, no de gravedad aparente."""
    if orq.parada_solicitada(directorio):
        # Alguien paro el sistema a mano: es el hecho mas fuerte que hay, y cualquier otra lectura
        # del historial es secundaria.
        return "BLOQUEADA"
    if not integro:
        # Con la cadena rota, la evidencia sobre la que se informaria esta en duda. Seguir como si
        # nada seria dar por buena justamente la prueba que falla.
        return "ERROR"
    if not lista_de_ciclos:
        return NO_DISPONIBLE
    ultimo_ciclo = lista_de_ciclos[-1]
    if ultimo_ciclo["abierto"]:
        return "TRABAJANDO"
    # Importado aqui y no arriba para no crear un ciclo de imports —`aura` importa este modulo— y,
    # sobre todo, para no **copiar** la tupla: dos listas de paradas normales que se separen es el
    # defecto que este proyecto ha pagado seis veces.
    import aura
    if ultimo_ciclo["motivo_de_parada"] not in aura.PARADAS_NORMALES:
        return "ERROR"
    por_clase = ultimo_ciclo["por_clase"]
    elevadas = _dato(por_clase, "DECISION_REQUIRED") if isinstance(por_clase, dict) else NO_DISPONIBLE
    if elevadas == NO_DISPONIBLE:
        # No consta el reparto por clase, asi que no se puede distinguir «no hay nada pendiente» de
        # «no se sabe». La primera version escribia `.get("DECISION_REQUIRED", 0)` y por tanto
        # afirmaba ESPERANDO —en la linea de cabecera— mientras el detalle admitia NO DISPONIBLE
        # tres lineas mas abajo. Lo encontro la auditoria independiente: era el unico sitio del
        # modulo que rellenaba un hueco con un cero, y estaba justo en el dato que mas se lee.
        return NO_DISPONIBLE
    if _es_numero(elevadas) and elevadas > 0:
        # Hay algo que una firma del CEO desbloquearia. Decir solo ESPERANDO lo esconderia.
        return "DECISION_REQUIRED"
    return "ESPERANDO"


def estado(directorio) -> dict:
    """Que esta haciendo AURA ahora, y que lleva hecho."""
    directorio = pathlib.Path(directorio)
    eventos = cp.leer_eventos(directorio)
    integridad = cp.verificar_integridad_log(directorio)
    integro = bool(integridad.get("integro"))
    lista = ciclos(directorio, eventos, integro)
    actual = _estado_actual(directorio, lista, integro)
    ultimo_ciclo = lista[-1] if lista else None
    trabajos = [t for t in _trabajos_en(eventos) if _efecto_real(t)]
    proyeccion = _proyeccion(directorio)

    ultima = NO_DISPONIBLE
    if trabajos:
        ultima = _detalle_de_trabajo(trabajos[-1], eventos, integro)

    por_clase = ultimo_ciclo["por_clase"] if ultimo_ciclo else NO_DISPONIBLE
    def _nivel(clase):
        return por_clase.get(clase, NO_DISPONIBLE) if isinstance(por_clase, dict) else NO_DISPONIBLE

    return {
        "estado": actual,
        "ultimo_ciclo": ultimo_ciclo["numero"] if ultimo_ciclo else NO_DISPONIBLE,
        "hora_ultimo_ciclo": ultimo_ciclo["inicio"] if ultimo_ciclo else NO_DISPONIBLE,
        "proximo_despertar": proximo_despertar(),
        "ciclos": len(lista),
        "despertares": sum(1 for e in eventos
                           if e.get("tipo") in ("aura_despertada", "despertar_rechazado")),
        # Niveles: se leen del ultimo descubrimiento. Acumularlos sumaria las mismas seis
        # oportunidades noventa veces.
        "trabajo_descubierto": ultimo_ciclo["descubiertas"] if ultimo_ciclo else NO_DISPONIBLE,
        "trabajo_bloqueado": _nivel("BLOQUEADA"),
        "trabajo_elevado": _nivel("DECISION_REQUIRED"),
        # Flujos: se acumulan sobre toda la historia.
        "trabajo_ejecutado": len(trabajos),
        "trabajo_autorizado": sum(1 for e in eventos if e.get("tipo") == "propuesta_autorizada"),
        "ultima_tarea": ultima,
        "actos_humanos": ultimo_ciclo["actos_humanos"] if ultimo_ciclo else NO_DISPONIBLE,
        "decisiones_pendientes": (proyeccion.get("decisiones_pendientes", NO_DISPONIBLE)
                                  if proyeccion is not None else NO_DISPONIBLE),
        # Las oportunidades bloqueadas UNA POR UNA, con su motivo y quien las desbloquea. Ya estaban
        # en la misma proyeccion que se acaba de leer para las decisiones; no exponerlas obligaba a
        # contestar «hay 6 bloqueadas» sin poder decir cuales ni por que, que es medio informe.
        "oportunidades_bloqueadas": (proyeccion.get("oportunidades_bloqueadas", NO_DISPONIBLE)
                                     if proyeccion is not None else NO_DISPONIBLE),
        # Los ultimos trabajos con efecto, acotados. Salen de la misma lista que ya se recorrio para
        # `ultima_tarea`: ni una lectura mas.
        "trabajos_recientes": [_detalle_de_trabajo(x, eventos, integro)
                               for x in trabajos[-LIMITE_HISTORIAL:]],
        "cola": por_clase,
        "antiguedad_del_ciclo_abierto": (_antiguedad(ultimo_ciclo["inicio"])
                                         if ultimo_ciclo and ultimo_ciclo["abierto"]
                                         else NO_DISPONIBLE),
        "sospecha": _sospecha_de_ciclo_muerto(ultimo_ciclo) if ultimo_ciclo else "",
        # Se ensena tal cual y **etiquetado como de otro eje**, en vez de compararlo: el `status` de
        # `estado.json` habla de la tarea en curso, no del ciclo autonomo.
        "estado_de_tarea_declarado": (proyeccion.get("status", NO_DISPONIBLE)
                                      if proyeccion is not None else NO_DISPONIBLE),
        "contradicciones": _contradicciones(directorio, eventos, lista, proyeccion),
        "integridad_del_log": integridad,
    }


# --------------------------------------------------------------- historial y ultimo --

def historial(directorio, limite: int = LIMITE_HISTORIAL) -> dict:
    """Los ciclos y los trabajos recientes, **separados**.

    Tres ciclos y un trabajo son tres ciclos y un trabajo. Mezclarlos haria creer que AURA hizo tres
    cosas cuando solo toco un fichero una vez."""
    directorio = pathlib.Path(directorio)
    eventos = cp.leer_eventos(directorio)
    integridad = cp.verificar_integridad_log(directorio)
    integro = bool(integridad.get("integro"))
    lista = ciclos(directorio, eventos, integro)
    trabajos = [_detalle_de_trabajo(t, eventos, integro) for t in _trabajos_en(eventos)]
    despertares = [e for e in eventos
                   if e.get("tipo") in ("aura_despertada", "despertar_rechazado")]
    return {
        "ciclos": list(reversed(lista))[:limite],
        "ciclos_totales": len(lista),
        "trabajos": list(reversed(trabajos))[:limite],
        "trabajos_totales": len(trabajos),
        "despertares_totales": len(despertares),
        "limite": limite,
        "recortado": len(lista) > limite or len(trabajos) > limite,
        "integridad_del_log": integridad,
    }


def ultimo(directorio) -> dict:
    """El ultimo ciclo autonomo real. El **ultimo**, no el ultimo interesante.

    La tentacion es enterrar un ciclo vacio y ensenar el anterior «porque tiene mas contenido». Eso
    convierte el informe en una seleccion editorial."""
    directorio = pathlib.Path(directorio)
    integridad = cp.verificar_integridad_log(directorio)
    lista = ciclos(directorio, integro=bool(integridad.get("integro")))
    if not lista:
        return {"estado": NO_DISPONIBLE, "inicio": NO_DISPONIBLE, "fin": NO_DISPONIBLE,
                "motivo_de_parada": NO_DISPONIBLE, "descubiertas": NO_DISPONIBLE,
                "ejecutadas": NO_DISPONIBLE, "bloqueadas": NO_DISPONIBLE,
                "elevadas": NO_DISPONIBLE, "actos_humanos": NO_DISPONIBLE,
                "tareas_ejecutadas": [], "efecto_real": NO_DISPONIBLE, "errores": []}
    ciclo = dict(lista[-1])
    errores = []
    if not integridad.get("integro"):
        errores.append(f"historial: {integridad.get('motivo')}")
    if ciclo["abierto"]:
        errores.append(_sospecha_de_ciclo_muerto(ciclo))
    ciclo["estado"] = _estado_actual(directorio, lista, bool(integridad.get("integro")))
    ciclo["errores"] = errores
    return ciclo


# --------------------------------------------------------------- render --

def _linea(etiqueta: str, valor, vacio: str = "ninguna") -> str:
    if isinstance(valor, dict):
        valor = ", ".join(f"{k}={v}" for k, v in sorted(valor.items())) or NO_DISPONIBLE
    if isinstance(valor, list):
        valor = ("\n" + " " * 37).join(str(v) for v in valor) if valor else vacio
    return f"  {etiqueta+':':<34} {valor}"


def _resumen_decisiones(decisiones) -> list:
    """Las decisiones pendientes, en una linea cada una.

    Volcar el registro entero seria tecnicamente veraz e inutil: un muro de texto en el que la
    informacion que importa —cuantas hay y sobre que— queda enterrada. Lo que el CEO necesita ver de
    un vistazo es que hay algo esperando su firma; el detalle esta en `estado.json`."""
    if not isinstance(decisiones, list):
        return decisiones if decisiones == NO_DISPONIBLE else []
    return [f"{d.get('id', NO_DISPONIBLE)} · {d.get('titulo', NO_DISPONIBLE)}"
            if isinstance(d, dict) else str(d) for d in decisiones]


def render_estado(informe: dict) -> str:
    lineas = ["", "AURA — ESTADO AUTÓNOMO", "=" * 62, "",
              _linea("Estado actual", informe["estado"]
                     + (f"  ({informe['antiguedad_del_ciclo_abierto']} abierto)"
                        if informe["antiguedad_del_ciclo_abierto"] != NO_DISPONIBLE else "")),
              _linea("Estado de la TAREA en estado.json", informe["estado_de_tarea_declarado"]),
              _linea("Último ciclo", informe["ultimo_ciclo"]),
              _linea("Hora del último ciclo", informe["hora_ultimo_ciclo"]),
              _linea("Próximo despertar", informe["proximo_despertar"]),
              "",
              _linea("Ciclos ejecutados (total)", informe["ciclos"]),
              _linea("Despertares del cron (total)", informe["despertares"]),
              "",
              _linea("Trabajo descubierto (ahora)", informe["trabajo_descubierto"]),
              _linea("Trabajo bloqueado (ahora)", informe["trabajo_bloqueado"]),
              _linea("Trabajo elevado (ahora)", informe["trabajo_elevado"]),
              _linea("Trabajo autorizado (total)", informe["trabajo_autorizado"]),
              _linea("Trabajo ejecutado (total)", informe["trabajo_ejecutado"]),
              "",
              _linea("Actos humanos en el último ciclo", informe["actos_humanos"]),
              _linea("Estado de la cola", informe["cola"]),
              _linea("Decisiones pendientes",
                     _resumen_decisiones(informe["decisiones_pendientes"]), "ninguna"),
              ""]
    ultima = informe["ultima_tarea"]
    if isinstance(ultima, dict):
        lineas += ["  Última tarea realmente ejecutada",
                   _linea("  identidad", ultima["id"]),
                   _linea("  fichero", ultima["fichero"]),
                   _linea("  objeto", ultima["simbolo"]),
                   _linea("  resultado", ultima["resultado"]),
                   _linea("  autorizada por", ultima["autorizada_por"]),
                   _linea("  enlace con la autorización", ultima["enlace"]),
                   _linea("  pruebas asociadas", ultima["pruebas"]), ""]
    else:
        lineas += [_linea("Última tarea realmente ejecutada", NO_DISPONIBLE), ""]
    if informe["sospecha"]:
        lineas += [_linea("Aviso", informe["sospecha"]), ""]
    integridad = informe["integridad_del_log"]
    lineas += [_linea("Integridad del historial",
                      "íntegro" if integridad.get("integro") else f"ROTO — {integridad.get('motivo')}"),
               _linea("Cola truncada", integridad.get("cola_truncada", NO_DISPONIBLE)),
               _linea("Contradicciones entre fuentes", informe["contradicciones"]), ""]
    return "\n".join(lineas)


def _render_ciclo(ciclo: dict) -> str:
    marca = "ABIERTO" if ciclo["abierto"] else ciclo["motivo_de_parada"]
    return (f"  #{ciclo['numero']:<4} {ciclo['inicio']}  ·  {marca}\n"
            f"         descubiertas={ciclo['descubiertas']} ejecutadas={ciclo['ejecutadas']} "
            f"bloqueadas={ciclo['bloqueadas']} elevadas={ciclo['elevadas']} "
            f"actos_humanos={ciclo['actos_humanos']} efecto_real={ciclo['efecto_real']}")


def _render_trabajo(trabajo: dict) -> str:
    etapas = " ".join(f"{'✓' if v else '·'}{k}" for k, v in trabajo["etapas"].items())
    return (f"  {trabajo['momento']}  {trabajo['id']}  {trabajo['simbolo']} "
            f"en {pathlib.Path(str(trabajo['fichero'])).name}\n"
            f"         {trabajo['resultado']} · autorizada por {trabajo['autorizada_por']}\n"
            f"         {etapas}")


def render_historial(informe: dict) -> str:
    lineas = ["", "AURA — HISTORIAL", "=" * 62, "",
              f"  CICLO AUTÓNOMO — {informe['ciclos_totales']} en total, "
              f"{informe['despertares_totales']} despertares del cron",
              "  (un despertar no es un ciclo; un ciclo no es trabajo)", ""]
    lineas += [_render_ciclo(c) for c in informe["ciclos"]] or ["  " + NO_DISPONIBLE]
    lineas += ["", f"  TRABAJO REAL EJECUTADO — {informe['trabajos_totales']} en total", ""]
    lineas += [_render_trabajo(t) for t in informe["trabajos"]] or ["  ninguno"]
    if informe["recortado"]:
        lineas += ["", f"  (recortado a los {informe['limite']} más recientes)"]
    lineas += [""]
    return "\n".join(lineas)


def render_ultimo(informe: dict) -> str:
    lineas = ["", "AURA — ÚLTIMO CICLO AUTÓNOMO", "=" * 62, "",
              _linea("Inicio", informe["inicio"]),
              _linea("Fin", informe["fin"]),
              _linea("Estado", informe["estado"]),
              _linea("Motivo de parada", informe["motivo_de_parada"]),
              "",
              _linea("Descubiertas", informe["descubiertas"]),
              _linea("Ejecutadas (según el cierre)", informe["ejecutadas"]),
              _linea("Bloqueadas", informe["bloqueadas"]),
              _linea("Elevadas", informe["elevadas"]),
              _linea("Actos humanos", informe["actos_humanos"]),
              _linea("Efecto real verificado", informe["efecto_real"]),
              ""]
    if informe["tareas_ejecutadas"]:
        lineas += ["  Tareas ejecutadas", ""]
        lineas += [_render_trabajo(t) for t in informe["tareas_ejecutadas"]]
    else:
        lineas += [_linea("Tareas ejecutadas", "ninguna")]
    lineas += ["", _linea("Errores", informe["errores"], "ninguno"), ""]
    return "\n".join(lineas)


__all__ = ["estado", "historial", "ultimo", "ciclos", "proximo_despertar", "_antiguedad",
           "render_estado", "render_historial", "render_ultimo",
           "NO_DISPONIBLE", "ESTADOS", "APERTURAS", "CIERRES", "LIMITE_HISTORIAL"]
