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
import os
import sys
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
    # Aclaracion anadida tras auditar `[EJEC]`: la linea de arriba lee el MODELO DE ACTIVACION
    # (ADR-0021, por perfil de hardware), no el catalogo de las 21 operaciones ejecutables. Que una
    # diga "(ninguna)" junto a "operaciones disponibles (21)" parece una contradiccion y no lo es:
    # son dos registros distintos. Confundirlos ya produjo una lectura erronea en una auditoria de
    # este mismo proyecto -- se aclara aqui para que no vuelva a ocurrir.
    lineas.append("  (nota: capacidades activas = modelo de activacion por hardware, ADR-0021; "
                 "no es el catalogo de operaciones ejecutables de arriba)")
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


async def _turno_de_voz(sistema, microfono, tid: str, texto: str | None = None) -> None:
    from .adapters.microfono import descartar_audio

    """EL ciclo de voz, en un solo sitio: grabar (si no hay texto) -> turno -> reproducir -> descartar.

    Lo comparten pulsar-para-hablar y la escucha continua. Tenerlo dos veces es como acaban divergiendo
    dos implementaciones del mismo control (la leccion de ALERTA-005): por ejemplo, que un modo borre
    el audio del usuario y el otro no."""
    grabacion = None
    respuesta_audio = None
    if texto is None:
        try:
            print("   (escuchando...)", flush=True)
            grabacion = microfono.escuchar(tid)
        except Exception as e:
            print(f"AURA> No pude oírte: {e}\n")
            return
        texto = grabacion
    try:
        res = await _turno(sistema.orquestador, texto, tid)
        print(f"AURA> {res['say']}\n")
        # La respuesta sintetizada existe TAMBIÉN en modo texto: hay que borrarla igual.
        respuesta_audio = res.get("audio")
        if microfono is not None:
            microfono.reproducir(respuesta_audio)
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
        # Vía rápida OPCIONAL (B2, CM1): la orden se transcribe con Vosk y su fin de habla propio en vez
        # de grabar un tiempo fijo y pasar por Whisper. El camino Whisper sigue siendo el DEFECTO: es más
        # exacto y solo se cambia con `AURA_ORDEN_VOSK=1`.
        if os.environ.get("AURA_ORDEN_VOSK") == "1" and hasattr(oido, "escuchar_orden"):
            texto = await asyncio.to_thread(oido.escuchar_orden)
            if not texto:
                print("AURA> No te oí.\n", flush=True)
                continue
            print(f"tú (oído)> {texto}", flush=True)
            await _turno_de_voz(sistema, microfono, tid, texto)
        else:
            await _turno_de_voz(sistema, microfono, tid)


def _gramatica_de_orden(env):
    """Gramática cerrada de órdenes conocidas, solo con la vía rápida `AURA_ORDEN_VOSK=1` (B2)."""
    if env.get("AURA_ORDEN_VOSK") != "1":
        return None
    from .core.ordenes_deterministas import ORDENES_DE_VOZ

    return ORDENES_DE_VOZ


async def _acusar_llamada(sistema, microfono, tid: str) -> None:
    """«¿Sí?» por el altavoz, para que la persona sepa que AURA la oyó y puede hablar."""
    print("AURA> ¿Sí?", flush=True)
    audio = None
    try:
        audio = await sistema.orquestador.voice.tts("¿Sí?", f"{tid}-acuse")
        microfono.reproducir(audio)
    except Exception as e:  # la voz es periferica: el turno sigue aunque el acuse no suene
        obs.log("WARN", "escucha", f"el acuse no sono: {e}", tid, audit=True)
    finally:
        microfono.descartar(audio)


async def _turno(orquestador, texto: str, tid: str) -> dict:
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
    tarea = asyncio.create_task(orquestador.handle_utterance("usuario", texto, tid))
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
    args = ap.parse_args(argv)

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

        oido = OidoContinuo(modelo=os.environ.get("AURA_VOSK_MODEL", ""),
                            gramatica_orden=_gramatica_de_orden(os.environ))
        try:
            print(f"AURA: {oido.comprobar()}")
            oido.preparar()  # el modelo se carga ANTES de decir que AURA está atenta
            return asyncio.run(_escuchar_continuo(sistema, microfono, oido, telemetria=args.telemetria))
        except DispositivoNoDisponible as e:
            print(f"AURA: sin escucha continua ({e}); sigo con pulsar para hablar.")
    return asyncio.run(_conversar(sistema, telemetria=args.telemetria, microfono=microfono))


if __name__ == "__main__":
    sys.exit(main())
