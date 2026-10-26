"""Ejecutable oficial de AURA (MA.1).

    python -m aura_skeleton --verificar     comprueba el arranque y sale
    python -m aura_skeleton --servir        AURORA con PROCESO PROPIO: sirve hasta Ctrl-C
    python -m aura_skeleton                 conversacion interactiva

Es el **unico** mecanismo previsto para ejecutar AURA. Los scripts de demo y validacion existen
para reproducir escenarios concretos; este es el programa.

`--verificar` esta pensado para el arranque en un equipo nuevo: enumera lo que quedo encendido, de
modo que un cableado incompleto se vea en pantalla en vez de descubrirse semanas despues con el
historial vacio.

`--servir` es lo que le falta a AURORA para tener PROCESO PROPIO (PIEZA 1): hasta este incremento
`MotorDelCiclo.servir()` era un bucle funcional que nadie invocaba fuera de las pruebas, asi que
AURORA solo avanzaba cuando un modelo externo pedia cada vuelta. Con este flag, el CEO arranca AURA
en una terminal, cierra Claude Code, y AURORA sigue trabajando por si misma.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import signal
import stat
import sys
import time
import uuid

from . import observability as obs
from .adapters.hitl_diferido import crear_confirmador_diferido
from .composicion import Configuracion, componer
from .core.centro_gobierno import panel, publicar
from .core.decisiones import AlmacenDecisiones
from .core.motor_ciclo import FallosConsecutivosExcedidos

#: Timeout total de un turno de conversacion (existente; no se cambia, D-FC-7). Vive aqui como
#: constante en vez de un `900` suelto porque `_informe` necesita el MISMO numero para poder avisar
#: si el timeout del proveedor lo supera -- dos literales identicos habrian podido divergir sin que
#: nadie lo notara (el mismo patron "declarado != real").
_TIMEOUT_TURNO_S = 900

#: D-FC-6: tramo corto antes del primer acuse de espera. Reutiliza `orquestador.wait` en dos tramos;
#: no crea colas ni hilos nuevos. 3s es deliberadamente corto: una respuesta mock o de cognicion local
#: rapida no llega a mostrar el acuse, solo lo ve quien de verdad esta esperando al modelo.
_ACUSE_TRAMO_S = 3


def _informe(sistema) -> str:
    caps = sorted(sistema.registro_adaptadores.capacidades())
    fuentes = sorted(sistema.registro_contexto.fuentes)
    lineas = [
        "=" * 62,
        "AURA — arranque verificado",
        "=" * 62,
        f"  operaciones disponibles ({len(caps)}): {', '.join(caps)}",
        f"  fuentes de contexto ({len(fuentes)}): {', '.join(fuentes)}",
        f"  memoria persistente : {sistema.ruta_memoria}",
        f"  registro forense    : {sistema.ruta_audit}",
        f"  kill switch         : {'ARMADO' if sistema.kill_switch.is_engaged() else 'en reposo'}",
    ]
    # Estado EFECTIVO, no planificado (CEO, 2026-08-02): lo que el operador lee al arrancar debe ser lo
    # que de verdad esta corriendo. Una capacidad que el hardware permite pero que no se pudo ensamblar
    # se anuncia DEGRADADA y con su motivo — nunca como activa.
    activas = sistema.capacidades_activas_efectivas
    lineas.append(f"  capacidades activas : {', '.join(activas) if activas else '(ninguna)'}")
    recursos = sistema.perfil_hardware.recursos
    medido = ", ".join(f"{k}={v:g}" for k, v in sorted(recursos.items()))
    lineas.append(f"  perfil de hardware  : {medido if medido else '(sin métricas)'}")
    # Aclaracion anadida tras auditar `[EJEC]`: la linea de arriba lee el MODELO DE ACTIVACION
    # (ADR-0021, por perfil de hardware), no el catalogo de las 21 operaciones ejecutables. Que una
    # diga "(ninguna)" junto a "operaciones disponibles (21)" parece una contradiccion y no lo es:
    # son dos registros distintos. Confundirlos ya produjo una lectura erronea en una auditoria de
    # este mismo proyecto -- se aclara aqui para que no vuelva a ocurrir.
    lineas.append(
        "  (nota: capacidades activas = modelo de activacion por hardware, ADR-0021; "
        "no es el catalogo de operaciones ejecutables de arriba)"
    )
    for m in sistema.materializaciones:
        if m.degradada:
            lineas.append(f"  [!] '{m.capacidad}': el equipo permitía {m.estado_plan.name}, corre {m.nivel}")
            lineas.append(f"      motivo: {m.motivo}")
    lineas.extend(_informe_proveedor(sistema))
    lineas.append("=" * 62)
    return "\n".join(lineas)


def _informe_proveedor(sistema) -> list[str]:
    """D-FC-7 (entregable 3): hace visible lo que hasta ahora solo se podia medir -- el timeout
    efectivo del proveedor, su origen, la politica del circuito y su estado. Sin esto, un timeout de
    900s heredado de `~/.profile` era indistinguible del defecto de 180s del codigo con solo mirar
    `--verificar`."""
    config = sistema.config
    router = sistema.orquestador.router
    stack = "real" if config.usar_stack_real else "mock"
    if config.usar_stack_real:
        proveedor = router.providers[0] if router.providers else None
        nombre_proveedor = getattr(proveedor, "name", "?")
        modelo = getattr(proveedor, "model", config.modelo)
        circuitos = str(router.estado_circuitos())
    else:
        nombre_proveedor = "mock"
        modelo = "mock (no aplica)"
        # El circuit breaker SI corre sobre el mock (es el mismo ModelRouter); se etiqueta el stack
        # para que no se lea como si fuera el estado de un proveedor real.
        circuitos = f"{router.estado_circuitos()} (stack mock)"
    lineas = [
        f"  proveedor LLM       : {nombre_proveedor} (stack={stack})",
        f"  modelo              : {modelo}",
        f"  timeout proveedor   : {config.timeout_proveedor_s}s (fuente: {config.fuente_timeout_proveedor})",
        f"  enfriamiento circuito: {config.enfriamiento_circuito_s}s (fuente: {config.fuente_enfriamiento_circuito})",
        f"  estado circuitos    : {circuitos}",
        f"  timeout conversacion (wait): {_TIMEOUT_TURNO_S}s",
    ]
    if config.timeout_proveedor_s > _TIMEOUT_TURNO_S:
        lineas.append(
            f"  [!] el timeout del proveedor ({config.timeout_proveedor_s}s) SUPERA el timeout de la "
            f"conversacion ({_TIMEOUT_TURNO_S}s): un turno lento puede cortarse antes de que el "
            "proveedor termine de responder."
        )
    return lineas


def _gobierno(sistema) -> str:
    """Construye el Centro de Gobierno con el estado operativo REAL del sistema compuesto, lo
    publica en disco y devuelve el texto (PIEZA 3). Superficie determinista: no consulta al LLM
    (ADR-0014), solo lee lo que `componer()` ya ensamblo.

    CUBRE TODOS los objetivos activos (D-3, auditoria independiente 2026-08-04): mostrar solo uno y
    callar el resto firmaria como [AURORA] una afirmacion falsa — "sin riesgos activos" cuando OTRO
    objetivo si tenia tareas bloqueadas fue exactamente el defecto que reprodujo la auditoria. Elegir
    "el mas urgente" seria igual de arbitrario: esta capa no tiene autoridad para descartar trabajo
    real sin avisar. Se listan todos y `panel()` identifica cada bloque con su objetivo cuando hay
    mas de uno.
    """
    activos = sistema.estado_operativo.objetivos_activos()
    # El buzon viaja con el panel: es la interfaz oficial donde el CEO ve lo que AURORA espera de el.
    # Sin esto, la aprobacion diferida existe pero llega por un canal que el CEO no mira.
    buzon = AlmacenDecisiones(os.path.join(Configuracion.desde_entorno().datos, "decisiones"))
    secciones = panel(estado=sistema.estado_operativo, objetivo=activos or None, decisiones=buzon)
    # <datos>/CENTRO-DE-GOBIERNO.md: junto al resto del estado permanente (memoria, audit log). No se
    # anade un campo nuevo a `Sistema` para la ruta de datos: `ruta_memoria` ya vive en ese directorio
    # y derivar de ahi evita crear una segunda fuente de configuracion (reutilizar, no crear).
    ruta = os.path.join(os.path.dirname(sistema.ruta_memoria), "CENTRO-DE-GOBIERNO.md")
    return publicar(secciones, ruta)


async def _servir(sistema) -> int:
    """PIEZA 1: arranca el latido permanente de AURORA sobre el sistema compuesto (D40: un solo
    `componer()`, sin ejecutable nuevo). Superficie determinista: no consulta al LLM (ADR-0014).

    El objetivo a servir se LEE del propio estado operativo, igual que `_gobierno` (INV-7: no se
    reinterpreta el trabajo, se reporta). Si no hay ningun objetivo con tareas vivas no hay nada que
    servir: se declara y se sale, en vez de arrancar un bucle que gira para siempre sobre un objetivo
    inexistente a la espera de un trabajo que nadie va a crear en esa direccion.
    """
    activos = sistema.estado_operativo.objetivos_activos()
    if not activos:
        # flush=True: un servicio permanente casi nunca corre en una TTY interactiva (systemd, nohup,
        # `> log` redirigido) -- alli stdout viene TOTALMENTE bufferizado, no por linea. Sin flush, un
        # SIGTERM/SIGKILL puede matar el proceso con el mensaje todavia en el buffer y nunca llega al log.
        print("AURA: no hay ningun objetivo activo en el estado operativo. Nada que servir.", flush=True)
        return 0
    objetivo = activos[0]
    trace_id = uuid.uuid4().hex[:12]
    print(f"AURA sirviendo el objetivo '{objetivo}' (trace={trace_id[:8]}). Ctrl-C para detener.", flush=True)
    await sistema.motor_ciclo.servir(objetivo, trace_id)
    return 0


class _ParadaPorSigterm(KeyboardInterrupt):
    """SIGTERM dentro de una espera síncrona: se trata como Ctrl-C, el camino de salida que ya existe."""


_ESPERAS_SINCRONAS = [0]  # >0 mientras el hilo principal está en `input()`, grabando o reproduciendo
_ULTIMO_TURNO: list[str | None] = [None]  # tid del último turno de voz de ESTE proceso (restos tras una parada)


def _descartar_restos_del_turno(microfono) -> None:
    """Tras `asyncio.run` —con el ejecutor ya cerrado, nadie puede escribir después— borra el audio del último
    turno por su nombre exacto. Idempotente: si el turno terminó bien, sus ficheros ya no están."""
    tid = _ULTIMO_TURNO[0]
    descartar = getattr(microfono, "descartar_restos", None)
    if tid and callable(descartar):
        descartar(tid)


@contextlib.contextmanager
def _espera_sincrona():
    """Marca un tramo en que el hilo principal bloquea sin ceder al bucle (`input()`, `parecord`, `paplay`).

    Solo ahí SIGTERM lanza una excepción: es la única forma de interrumpirlo. Fuera, la parada CANCELA en el
    siguiente `await` y no corta código síncrono a medias —escribir el audit forense, un `finally`—."""
    _ESPERAS_SINCRONAS[0] += 1
    try:
        yield
    finally:
        _ESPERAS_SINCRONAS[0] -= 1


def _ejecutar_conversacion(sistema, microfono, telemetria: bool = False) -> int:
    """Pulsar-para-hablar y modo texto, con parada limpia por SIGTERM (la escucha continua usa `_hasta_sigterm`).

    Defecto `[EJEC]` (2026-10-06): un SIGTERM mataba el proceso sin ejecutar los `finally` de `_turno_de_voz` y
    la grabación del usuario quedaba en `/tmp/aura`. Aquí la espera es un `input()` SÍNCRONO, que un manejador
    de asyncio no interrumpe; por eso el manejador es híbrido: lanza dentro de `_espera_sincrona` y cancela la
    tarea principal fuera de ella (como `asyncio.Runner` con Ctrl-C). Tras la primera señal se ignoran las
    siguientes: la limpieza no puede cortarse a medias."""
    estado: dict = {}

    def _manejador(*_a) -> None:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        tarea, bucle = estado.get("tarea"), estado.get("bucle")
        if _ESPERAS_SINCRONAS[0] > 0 or tarea is None or bucle is None:
            raise _ParadaPorSigterm
        bucle.call_soon_threadsafe(tarea.cancel)

    async def _principal() -> int:
        estado["tarea"], estado["bucle"] = asyncio.current_task(), asyncio.get_running_loop()
        try:
            return await _conversar(sistema, telemetria=telemetria, microfono=microfono)
        finally:
            estado.clear()  # un SIGTERM tras cerrar el bucle no puede intentar usarlo

    anterior = signal.signal(signal.SIGTERM, _manejador)
    try:
        return asyncio.run(_principal())
    except (_ParadaPorSigterm, asyncio.CancelledError):
        print("\nAURA: detenida (SIGTERM); el turno en curso se descartó.", flush=True)
        return 0
    finally:
        _descartar_restos_del_turno(microfono)
        signal.signal(signal.SIGTERM, anterior if anterior is not None else signal.SIG_DFL)


async def _conversar(sistema, telemetria: bool = False, microfono=None) -> int:
    """Conversacion humana. La telemetria NO se apaga: se saca de la pantalla.

    `[VOICE]`, `[MEM]`, `[EVENT]`, `[LAT]`… seguian saliendo por `stderr` mientras la respuesta salia
    por `stdout` — dos flujos distintos, si, pero en una terminal caen en el mismo sitio, asi que la
    separacion no separaba nada y la conversacion aparecia sepultada bajo su propia instrumentacion.

    Lo que cambia es DONDE se imprime, no si se registra: `observability.log` guarda el registro y
    persiste la auditoria **antes** de decidir si lo pinta. El audit log sigue en
    `sistema.ruta_audit`, `obs.audit_records()` sigue devolviendo lo mismo, y `--telemetria` la
    devuelve a la pantalla para quien la quiera delante."""
    if not telemetria:
        obs.configurar_salida(None)
    print(_informe(sistema))
    if microfono is None:
        print("Escribe para hablar con AURA. Ctrl-D para salir.\n")
    else:
        print("Pulsa Enter y habla (o escribe). Ctrl-D para salir.\n")
    while True:
        try:
            with _espera_sincrona():
                texto = input("tu> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nhasta luego.")
            return 0
        tid = uuid.uuid4().hex[:12]
        if not texto:
            if microfono is None:
                continue
            # PULSAR PARA HABLAR: solo se graba porque el usuario lo ha pedido, y con tope.
            await _turno_de_voz(sistema, microfono, tid)
        else:
            await _turno_de_voz(sistema, microfono, tid, texto)


async def _turno_de_voz(sistema, microfono, tid: str, texto: str | None = None, activado: bool = False) -> None:
    """EL ciclo de voz, en un solo sitio: grabar (si no hay texto) -> turno -> reproducir -> descartar.

    Lo comparten pulsar-para-hablar y la escucha continua. Tenerlo dos veces es como acaban divergiendo
    dos implementaciones del mismo control (la leccion de ALERTA-005): por ejemplo, que un modo borre
    el audio del usuario y el otro no."""
    from .adapters.microfono import descartar_audio

    _ULTIMO_TURNO[0] = tid
    grabacion = None
    respuesta_audio = None
    if texto is None:
        # Fin de habla SOLO en escucha continua (tras la palabra de activación); pulsar-para-hablar sigue
        # con duración fija. Sin el método (dobles, micrófonos antiguos) se cae a la captura fija.
        con_fin_de_habla = getattr(microfono, "escuchar_hasta_silencio", None) if activado else None
        capturar = con_fin_de_habla if callable(con_fin_de_habla) else microfono.escuchar
        t0 = time.monotonic()
        try:
            print("   (escuchando...)", flush=True)
            with _espera_sincrona():
                grabacion = capturar(tid)
        except Exception as e:
            print(f"AURA> No pude oírte: {e}\n")
            return
        corte = getattr(microfono, "ultimo_corte", None) if capturar is con_fin_de_habla else "fija"
        obs.log("LAT", "voz", f"captura ms={_ms(t0)} corte={corte}", tid)
        texto = grabacion
    t_turno = time.monotonic()
    try:
        res = await _turno(sistema.orquestador, texto, tid, activado=activado)
        obs.log("LAT", "voz", f"turno ms={_ms(t_turno)}", tid)
        print(f"AURA> {res['say']}\n")
        # La respuesta sintetizada existe TAMBIÉN en modo texto: hay que borrarla igual.
        respuesta_audio = res.get("audio")
        if microfono is not None:
            t_respuesta = time.monotonic()
            with _espera_sincrona():
                microfono.reproducir(respuesta_audio)
            obs.log("LAT", "voz", f"respuesta ms={_ms(t_respuesta)}", tid)
    except Exception as e:
        # Un turno fallido no puede tumbar la sesion: AURA sigue disponible.
        print(f"AURA> No pude completar el turno ({type(e).__name__}: {e})\n")
    finally:
        # Lo oído no se archiva: la grabación se borra en cuanto el turno la ha consumido. Y tampoco
        # lo que AURA recitó: el WAV de la respuesta puede contener datos personales («tu color
        # favorito es…») y se acumulaba en disco (hallazgo ALTO de la auditoría, 2026-09-27).
        if grabacion is not None:
            microfono.descartar(grabacion)
        if respuesta_audio is not None:
            descartar = microfono.descartar if microfono is not None else descartar_audio
            descartar(respuesta_audio)


async def _escuchar_continuo(sistema, microfono, oido, telemetria: bool = False) -> int:
    """AURA atenta: espera a que la llamen por su nombre, contesta «¿Sí?» y escucha la orden.

    Bible 6.2 §46: escucha continua en LOCAL; lo que no es la palabra de activación no se transmite.
    Aqui ademas no se escribe a disco (`adapters/escucha.py`)."""
    if not telemetria:
        obs.configurar_salida(None)
    print(_informe(sistema))
    await _preparar_voz(sistema, microfono)
    print("AURA está atenta: di «Aurora» para hablarle. Ctrl-C para salir.\n")
    while True:
        try:
            llamada = await asyncio.to_thread(oido.esperar_llamada)
        except KeyboardInterrupt:
            print("\nhasta luego.")
            return 0
        if not llamada:
            print("AURA: el micrófono dejó de entregar audio; dejo de escuchar.")
            return 1
        tid = uuid.uuid4().hex[:12]
        await _acusar_llamada(sistema, microfono, tid)
        # C1 (DP-VOZ-ACCION §8): ESTE turno sigue a la palabra de activación; es el único hecho que lo prueba.
        await _turno_de_voz(sistema, microfono, tid, activado=True)


_ACUSE_TEXTO = "¿Sí?"


def _ms(desde: float) -> int:
    return round((time.monotonic() - desde) * 1000)


async def _preparar_voz(sistema, microfono) -> None:
    """Antes de declararse atenta: precarga los modelos de voz y pre-sintetiza el acuse (perfil 2026-10-04:
    Whisper ~10 s en el primer turno, Piper ~2 s en cada «¿Sí?»). Es periférico: un fallo no impide escuchar."""
    voz = sistema.orquestador.voice
    precargar = getattr(voz, "precargar", None)
    if callable(precargar):
        try:
            await asyncio.to_thread(precargar)
        except Exception as e:  # noqa: BLE001 - el primer turno repetirá el intento y lo dirá
            obs.log("WARN", "escucha", f"la precarga de voz falló: {e}", "-", audit=True)
    await _audio_del_acuse(voz, "precarga")  # solo calienta Piper y deja el WAV cacheado


async def _audio_del_acuse(voz, tid: str) -> tuple[str | None, bool]:
    """(ruta, cacheado). WAV de «¿Sí?», sintetizado UNA vez por proceso. Es una frase CONSTANTE de AURA, no audio del usuario:
    por eso se conserva con nombre fijo y NO se descarta. Si el fichero desaparece, se regenera."""
    ruta = getattr(voz, "_acuse_si", None)
    if ruta and os.path.isfile(ruta):
        return ruta, True
    try:
        sintetizado = await voz.tts(_ACUSE_TEXTO, f"{tid}-acuse")
    except Exception as e:  # la voz es periferica: el turno sigue aunque el acuse no suene
        obs.log("WARN", "escucha", f"el acuse no sono: {e}", tid, audit=True)
        return None, False
    # Se conserva el WAV que ya escribió el TTS, sin renombrarlo: renombrar era una escritura directa a disco
    # fuera del Motor (G-1 R-B la acusó) y no aportaba nada. La purga de arranque lo borra al empezar otro
    # proceso, que lo vuelve a sintetizar una vez.
    try:
        voz._acuse_si = sintetizado
        return sintetizado, True
    except AttributeError:
        return sintetizado, False  # voz sin atributos: efímero, se descarta


async def _acusar_llamada(sistema, microfono, tid: str) -> None:
    """«¿Sí?» por el altavoz, para que la persona sepa que AURA la oyó y puede hablar."""
    print("AURA> ¿Sí?", flush=True)
    t0 = time.monotonic()
    audio, cacheado = None, False
    try:
        audio, cacheado = await _audio_del_acuse(sistema.orquestador.voice, tid)
        if audio:
            microfono.reproducir(audio)
    except Exception as e:  # noqa: BLE001
        obs.log("WARN", "escucha", f"el acuse no sono: {e}", tid, audit=True)
    finally:
        if audio and not cacheado:
            microfono.descartar(audio)  # el WAV cacheado NO se descarta: es una frase constante de AURA
    obs.log("LAT", "voz", f"acuse ms={_ms(t0)}", tid)


async def _turno(orquestador, texto: str, tid: str, activado: bool = False) -> dict:
    """Lanza el turno como TAREA del MISMO bucle de eventos (D-FC-6, medido con Ollama y el bus real
    -- arquitecto, 2026-09-13): `InProcessEventBus.publish` hace `await h(event)`, asi que
    `handle_utterance` NO vuelve hasta que el turno ENTERO termina (251-263s medidos con Ollama). Con
    `await handle_utterance(...)` en linea, el turno ya estaba resuelto cuando `_esperar_con_acuse` lo
    consultaba: el acuse nunca se imprimia en produccion, solo en pruebas con un doble cuyo `wait()`
    expiraba por su cuenta. Lanzandolo como tarea, el bucle queda libre para que `_esperar_con_acuse`
    consulte el progreso REAL mientras la llamada al modelo corre en `run_in_executor` (sin hilos ni
    colas nuevas: es la misma infraestructura de `asyncio` que ya usaba el proyecto).

    Al final se hace `await tarea`: si el turno fallo con una excepcion (en vez de resolverse con una
    respuesta, aunque sea de abstencion), se propaga aqui, igual que con el `await` directo de antes."""
    tarea = asyncio.create_task(orquestador.handle_utterance("usuario", texto, tid, activado=activado))
    try:
        return await _esperar_con_acuse(orquestador, tid)
    finally:
        await tarea


async def _esperar_con_acuse(orquestador, tid: str) -> dict:
    """D-FC-6: acuse de espera sobre la infraestructura EXISTENTE -- reutiliza `orquestador.wait` en
    dos tramos, sin colas ni hilos nuevos. Una inferencia real medida en 123-248s no imprimia nada
    hasta terminar y parecia un cuelgue; esto no acorta la espera, solo la hace visible.

    `turno_en_modelo` es OPCIONAL (lo implementa el integrador del orquestador): con `getattr` y
    respaldo, esta funcion se comporta igual si el metodo todavia no existe."""
    try:
        return await _wait_robusto(orquestador, tid, _ACUSE_TRAMO_S)
    except TimeoutError:
        pass
    turno_en_modelo = getattr(orquestador, "turno_en_modelo", None)
    if callable(turno_en_modelo) and turno_en_modelo(tid):
        print("AURA> (consultando mi modelo local; puede tardar varios minutos…)")
    else:
        print("AURA> (sigo trabajando en tu petición…)")
    return await orquestador.wait(tid, timeout=_TIMEOUT_TURNO_S - _ACUSE_TRAMO_S)


async def _wait_robusto(orquestador, tid: str, timeout: float, reintentos_registro: int = 200) -> dict:
    """`orquestador.wait` puede lanzar `KeyError` si se le pregunta por un turno que
    `handle_utterance` todavia no registro: el `Orchestrator` real crea `_done[trace_id]` en sus DOS
    PRIMERAS lineas -antes de su primer `await`- pero `_turno` lo lanza como tarea para no bloquear
    el acuse (ver `_turno`), y eso abre una ventana de carrera muy breve entre crear la tarea y que
    el turno quede registrado.

    Se cierra cediendo el control con duracion CERO (`asyncio.sleep(0)`) las veces que haga falta --
    nunca con un sleep de duracion arbitraria-- y solo mientras el fallo sea EXACTAMENTE ese
    `KeyError`; cualquier otro resultado (exito o `TimeoutError` genuino porque el turno sigue en
    curso) se propaga tal cual, sin reintentar. `reintentos_registro` es una red de seguridad, no un
    plazo: en la practica se resuelve en la primera o segunda vuelta."""
    for _ in range(reintentos_registro):
        try:
            return await orquestador.wait(tid, timeout=timeout)
        except KeyError:
            await asyncio.sleep(0)
    return await orquestador.wait(tid, timeout=timeout)  # se agotaron los reintentos: que se vea el KeyError real


_RED_POR_DEFECTO = "~/.aura-red"
_URL_RED_POR_DEFECTO = "tls://127.0.0.1:4222"
_USUARIO_RECEPTOR = "receptor"


def _ruta_red() -> str | None:
    """La red de nodos del CLI. `AURA_RED` declarado y vacio = «sin red», como `crear_vigia_nodos` y
    `estado_autonomo_cp`; ausente = `~/.aura-red`."""
    declarado = os.environ.get("AURA_RED")
    if declarado is not None and not declarado.strip():
        return None
    return os.path.expanduser(declarado or _RED_POR_DEFECTO)


def _nodos() -> int:
    """`--nodos`: estado de los nodos y sobres de capacidad. Solo lee el registro y mide HC-1: sin red."""
    from .adapters.detector_hardware import DetectorHardwareLocal
    from .adapters.receptor_nodos import informe_nodos, leer_registro
    from .core.nodos import LatidoInvalido

    ruta = _ruta_red()
    if ruta is None:
        print("AURA: red de nodos desactivada (AURA_RED declarado vacio)")
        return 0
    try:
        registro = leer_registro(ruta)
        recursos = DetectorHardwareLocal(ruta).detectar().recursos
        print(informe_nodos(registro, recursos, time.time()))
    except (ValueError, LatidoInvalido) as e:
        print(f"AURA: no puedo leer el registro de nodos en {ruta}: {e}", file=sys.stderr)
        return 1
    return 0


def _leer_credencial(ruta: str) -> str:
    """Lee la contraseña del receptor; rechaza el fichero si lo puede leer el grupo u otros."""
    if not os.path.isfile(ruta):
        raise ValueError(f"falta la credencial del receptor: {ruta}")
    if os.stat(ruta).st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError(f"permisos inseguros en {ruta}: debe ser 0600 (legible solo por su dueño)")
    with open(ruta, encoding="utf-8") as f:
        credencial = f.read().strip()
    if not credencial:
        raise ValueError(f"la credencial del receptor está vacía: {ruta}")
    return credencial


async def _hasta_sigterm(corrutina, al_detener=None) -> int:
    """Ejecuta `corrutina` hasta que termina o hasta SIGTERM, que la CANCELA en vez de matar el proceso.

    Defecto `[EJEC]` (2026-10-06): un SIGTERM —el de runit o el del arnés— a mitad de un turno dejaba la
    grabación del usuario en `/tmp/aura`, porque el proceso moría sin ejecutar los `finally` de
    `_turno_de_voz`. Cancelando, esos `finally` corren y el audio se descarta (no se almacena audio).
    `al_detener` libera lo que bloquee el cierre desde otro hilo (el flujo de Vosk). Mismo patrón que
    `_receptor_nodos`."""
    tarea = asyncio.ensure_future(corrutina)

    def _parar() -> None:
        if al_detener is not None:
            al_detener()
        tarea.cancel()

    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, _parar)
    try:
        return await tarea
    except asyncio.CancelledError:
        print("AURA: detenida (SIGTERM); el turno en curso se descartó.", flush=True)
        return 0


def _ejecutar_escucha_continua(sistema, microfono, oido, telemetria: bool = False) -> int:
    """La escucha continua es el modo desatendido (runit, `aura-voz.sh`): se detiene limpia con SIGTERM."""
    corrutina = _escuchar_continuo(sistema, microfono, oido, telemetria=telemetria)
    try:
        return asyncio.run(_hasta_sigterm(corrutina, al_detener=getattr(oido, "detener", None)))
    finally:
        _descartar_restos_del_turno(microfono)


def _receptor_nodos() -> int:
    """`--receptor-nodos`: escucha latidos de nodos en HC-1 hasta SIGTERM/Ctrl-C."""
    from .adapters.receptor_nodos import ReceptorNodos

    ruta = _ruta_red()
    if ruta is None:
        print("AURA: no se puede arrancar el receptor de nodos: AURA_RED declarado vacio (sin red)", file=sys.stderr)
        return 2
    ca = os.path.join(ruta, "pki", "ca.crt")
    try:
        password = _leer_credencial(os.path.join(ruta, "receptor.credencial"))
        if not os.path.isfile(ca):
            raise ValueError(f"falta la CA privada (ca.crt): {ca}")
    except ValueError as e:
        print(f"AURA: no se puede arrancar el receptor de nodos: {e}", file=sys.stderr)
        return 2
    servidores = [u.strip() for u in os.environ.get("AURA_RED_URL", _URL_RED_POR_DEFECTO).split(",") if u.strip()]

    async def _correr() -> None:
        tarea = asyncio.ensure_future(ReceptorNodos(ruta).ejecutar(servidores, _USUARIO_RECEPTOR, password, ca))
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, tarea.cancel)
        try:
            await tarea
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(_correr())
    except KeyboardInterrupt:
        pass
    except Exception as e:  # conexión, TLS, etc.: mensaje claro, sin traza
        print(f"AURA: el receptor de nodos se detuvo: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print("AURA: receptor de nodos detenido.", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aura", description="Sistema Operativo de Inteligencia Personal")
    ap.add_argument("--verificar", action="store_true", help="verifica el arranque y sale")
    ap.add_argument(
        "--gobierno", action="store_true", help="publica el Centro de Gobierno con el estado operativo real y sale"
    )
    ap.add_argument(
        "--servir", action="store_true", help="AURORA con proceso propio: sirve el objetivo activo hasta Ctrl-C"
    )
    ap.add_argument(
        "--telemetria",
        action="store_true",
        help="muestra la telemetria interna en pantalla durante la conversacion (por defecto solo se registra)",
    )
    ap.add_argument(
        "--continuo",
        action="store_true",
        help="con --escuchar: AURA escucha siempre y acude al oir «Aurora» (Bible 6.2, todo en local)",
    )
    ap.add_argument(
        "--escuchar",
        action="store_true",
        help="conversacion por voz: Enter para hablar por el microfono; la respuesta suena por el altavoz",
    )
    ap.add_argument("--nodos", action="store_true", help="muestra los nodos registrados y sus sobres de capacidad")
    ap.add_argument(
        "--receptor-nodos",
        action="store_true",
        help="HC-1 escucha latidos de nodos por NATS (config: AURA_RED, AURA_RED_URL)",
    )
    ap.add_argument(
        "--medir-cm2",
        action="store_true",
        help="reloj de CM2: ejecuta las sondas vencidas (solo lectura) e informa; sin el evento de inicio, solo informa",
    )
    ap.add_argument(
        "--iniciar-cm2",
        action="store_true",
        help="reloj de CM2: emite el evento de inicio de la medicion oficial (exige --confirmo-inicio)",
    )
    ap.add_argument(
        "--confirmo-inicio",
        action="store_true",
        help="confirmacion explicita para --iniciar-cm2 (decision del CEO: arranca la ventana oficial)",
    )
    args = ap.parse_args(argv)

    # El reloj de CM2 tampoco compone AURA: lee `AURA_DATOS` como la composicion, abre la memoria SOLO para
    # leer y no construye proveedores ni motor.
    if args.iniciar_cm2 and args.medir_cm2:
        ap.error("--iniciar-cm2 y --medir-cm2 son mutuamente excluyentes")
    if args.iniciar_cm2 or args.medir_cm2:
        from .core import reloj_cm2

        datos = Configuracion().datos
        try:
            if args.iniciar_cm2:
                print(reloj_cm2.iniciar(datos, confirmo=args.confirmo_inicio))
            else:
                print(reloj_cm2.medir(datos))
        except (reloj_cm2.MemoriaNoLegible, reloj_cm2.DatosNoValidos) as e:
            print(e)
            return 1
        return 0

    # Estos dos modos NO componen AURA: no tocan memoria, ni estado operativo ni proveedores.
    if args.nodos:
        return _nodos()
    if args.receptor_nodos:
        return _receptor_nodos()

    config = Configuracion.desde_entorno()
    # QUIEN PREGUNTA DEPENDE DEL MODO (Pieza 2). En sesion interactiva el CEO esta delante y la
    # consola es mejor: responde al instante. En `--servir` no hay nadie, y preguntar por `input()`
    # solo producia `EOFError` -> denegada, con la peticion perdida: AURORA no podia completar NINGUN
    # trabajo de lista roja sin el CEO presente en ese instante. El buzon deja la peticion escrita.
    confirmador = crear_confirmador_diferido(os.path.join(config.datos, "decisiones")) if args.servir else None
    sistema = componer(config, confirmador=confirmador)

    if args.verificar:
        print(_informe(sistema))
        return 0
    if args.gobierno:
        print(_gobierno(sistema))
        return 0
    if args.servir:
        try:
            return asyncio.run(_servir(sistema))
        except KeyboardInterrupt:
            # Salida limpia (CEO): Ctrl-C detiene el servicio sin volcar un traceback feo. El
            # KeyboardInterrupt se captura AQUI, fuera de la corrutina: durante `asyncio.sleep` la
            # interrupcion llega al `asyncio.run` que la envuelve, no al `await` suspendido dentro.
            print("\nAURA: servicio detenido por el usuario (Ctrl-C).", flush=True)
            return 0
        except FallosConsecutivosExcedidos as e:
            print(f"\nAURA: servicio detenido -- {e}", flush=True)
            return 1
    microfono = None
    if args.escuchar:
        from .adapters.microfono import DispositivoNoDisponible, Microfono

        if not config.usar_stack_real:
            # Sin el stack real la voz es un doble que no transcribe: grabar seria fingir que se escucha.
            print("AURA: --escuchar exige AURA_STACK_REAL=1 (transcripcion real); sigo por texto.")
        else:
            microfono = Microfono()
            try:
                print(f"AURA: microfono {microfono.comprobar()}")
            except DispositivoNoDisponible as e:
                print(f"AURA: sin microfono ({e}); sigo por texto.")
                microfono = None
    if microfono is not None and args.continuo:
        from .adapters.escucha import OidoContinuo

        oido = OidoContinuo(modelo=os.environ.get("AURA_VOSK_MODEL", ""))
        try:
            print(f"AURA: {oido.comprobar()}")
            oido.preparar()  # el modelo se carga ANTES de decir que AURA está atenta
            return _ejecutar_escucha_continua(sistema, microfono, oido, telemetria=args.telemetria)
        except DispositivoNoDisponible as e:
            print(f"AURA: sin escucha continua ({e}); sigo con pulsar para hablar.")
    return _ejecutar_conversacion(sistema, microfono, telemetria=args.telemetria)


if __name__ == "__main__":
    sys.exit(main())
