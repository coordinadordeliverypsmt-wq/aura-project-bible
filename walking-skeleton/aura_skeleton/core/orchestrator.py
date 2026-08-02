"""Orquestador (nucleo, Bible 3.2/4.2/4.3). Coordina memoria, router y permisos.
Los eventos son SERIALIZABLES (contrato 3.3): el estado de temporizacion se guarda por trace_id,
no en el payload. Asi el MISMO orquestador corre sobre el bus in-process o sobre NATS real."""

from __future__ import annotations

import asyncio

from .. import observability as obs
from ..contracts import Event
from ..observability import Timer
from .almacen_senales import AlmacenSenales
from .automatizacion import MotorAutomatizacion
from .modelo_usuario import describir_conocimiento, explicar_entrada
from .notificaciones import notificacion_de_accion
from .registro import RegistroAdaptadores
from .reglas import ReglaUsuario, evaluar_condicion, resolver_args


def _parse_decision(out: str, tid: str) -> tuple[str, dict, str]:
    """Parsing defensivo de la salida del LLM (resiliencia; los modelos reales a veces devuelven
    JSON imperfecto o con texto alrededor). Nunca crashea: ante fallo, decision segura (consulta)."""
    import json as _j

    for candidate in (out, _extract_json(out)):
        if not candidate:
            continue
        try:
            d = _j.loads(candidate)
            action = str(d.get("action", "consulta")) or "consulta"
            args = d.get("args", {}) if isinstance(d.get("args", {}), dict) else {}
            say = str(d.get("say", "")) or "Entendido."
            return action, args, say
        except (ValueError, TypeError):
            continue
    obs.log("WARN", "orchestrator", "salida del LLM no parseable -> decision segura (consulta)", tid, audit=True)
    return "consulta", {}, "No entendi bien; puedes reformularlo?"


def _extract_json(s: str) -> str:
    a, b = s.find("{"), s.rfind("}")
    return s[a : b + 1] if 0 <= a < b else ""


# ADR-0014 — El Core es la unica fuente de verdad sobre los hechos del sistema.
# La deteccion de "el usuario pregunta por un recuerdo" es DETERMINISTA: no puede
# delegarse en el LLM, porque el objetivo es precisamente no consultarlo cuando no
# hay nada que recordar. Se normalizan acentos para que "habiamos"/"habíamos" coincidan.
_PATRONES_CONSULTA_MEMORIA = (
    "acordamos",
    "quedamos en",
    "recuerdas",
    "te acuerdas",
    "que dije",
    "que dijimos",
    "habiamos hablado",
    "hablamos de",
    "te conte",
    "te comente",
    "mencione",
    "que sabes de mi",
    "que recuerdas",
    "mi preferencia",
    "habiamos quedado",
)


def _normalizar(texto: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _es_consulta_de_memoria(texto: str) -> bool:
    """True si el usuario pregunta por algo supuestamente recordado."""
    t = _normalizar(texto)
    return any(p in t for p in _PATRONES_CONSULTA_MEMORIA)


# El usuario pregunta por lo que AURA hizo: "¿que ha pasado?", "¿tengo algun aviso?", "novedades".
_PATRONES_CONSULTA_NOTIF = (
    "que ha pasado",
    "que paso",
    "mientras no estaba",
    "algun aviso",
    "algun aviso?",
    "tengo avisos",
    "notificacion",
    "novedad",
)


def _es_consulta_de_notificaciones(texto: str) -> bool:
    """True si el usuario pregunta por lo que AURA ha hecho/avisado."""
    t = _normalizar(texto)
    return any(p in t for p in _PATRONES_CONSULTA_NOTIF)


# Soberania del modelo del usuario: inspeccionar, entender, corregir y olvidar lo que AURA sabe de el.
_PAT_MODELO_VER = ("que sabes de mi", "que sabes sobre mi", "que sabes acerca de mi", "que informacion tienes de mi")
_PAT_MODELO_PORQUE = ("por que dices", "por que sabes", "como lo sabes", "como sabes eso", "por que piensas")
_PAT_MODELO_REFUTA = ("ya no es cierto", "no es cierto", "eso esta mal", "eso es falso", "ya no es verdad")
_PAT_MODELO_OLVIDA = ("olvida", "olvidate")


def _cae_en(t: str, pats: tuple) -> bool:
    return any(p in t for p in pats)


# Automatizaciones definidas por el usuario (MVP capacidad 5, Bible 6.4). La deteccion es DETERMINISTA en el
# nucleo (ADR-0014), igual que el resto de superficies: crear una regla o consultarla es un HECHO, no una
# inferencia, y no se delega en el LLM. El MVP reconoce en lenguaje natural UNA automatizacion —"guarda una
# copia antes de borrar"—; la generalidad (cualquier disparador/accion) vive en el MODELO de regla y en el
# MOTOR, no en el reconocedor, que se ampliara sin rediseno (deuda registrada, no rearquitectura).
_PAT_REGLAS_VER = ("que automatizaciones", "que automatizacion", "mis automatizaciones", "que reglas", "mis reglas")
_PAT_REGLA_DISPARADOR = ("siempre que", "cada vez que", "cuando ")

# Identificador ESTABLE de la unica automatizacion que el MVP sabe reconocer en lenguaje natural. Al ser
# estable, repetir la frase no duplica la regla ni al reiniciar (el almacen es append-only).
_ID_COPIA_ANTES_DE_BORRAR = "copia-antes-de-borrar"

# Accion del usuario -> clausula en pasado y primera persona (habla AURA), para narrar "... y luego <esto>".
_CLAUSULA_USUARIO = {
    "borrar_archivo": "lo borré",
    "mover_archivo": "lo moví",
    "renombrar_archivo": "lo renombré",
    "escribir_archivo": "lo escribí",
}


def _es_consulta_de_reglas(texto: str) -> bool:
    """True si el usuario quiere inspeccionar sus automatizaciones ("¿que automatizaciones tengo?")."""
    return any(p in _normalizar(texto) for p in _PAT_REGLAS_VER)


def _es_creacion_de_regla(texto: str) -> bool:
    """True si el usuario define la automatizacion "copia antes de borrar" en lenguaje natural.

    Reconoce el patron disparador ("siempre que / cada vez que / cuando") + accion disparadora (borrar) +
    intencion de respaldo (copia). Es el unico patron del MVP; ampliarlo es deuda, no rediseno.
    """
    t = _normalizar(texto)
    return any(p in t for p in _PAT_REGLA_DISPARADOR) and ("borr" in t or "elimin" in t) and "copia" in t


class Orchestrator:
    """Coordina el turno conversacional. NO ejecuta acciones por su cuenta (M2.5, ALERTA-005).

    El sexto parametro admite un adaptador suelto (uso historico de M1) o un `RegistroAdaptadores`
    con varios. En ambos casos la ejecucion se delega en el `MotorAutomatizacion`, que es el unico
    camino de ejecucion del sistema: el orquestador no tiene acceso directo a ningun adaptador.
    """

    def __init__(
        self,
        bus,
        memory,
        router,
        permissions,
        voice,
        adaptadores,
        motor=None,
        contexto=None,
        notificaciones=None,
        modelo_usuario=None,
        automatizaciones=None,
    ):
        self.bus, self.memory, self.router = bus, memory, router
        self.perm, self.voice = permissions, voice
        self.notificaciones = notificaciones  # Centro de Notificaciones (MVP): registra lo que AURA hace
        self.modelo_usuario = modelo_usuario  # Soberania (MVP): ver/entender/corregir/olvidar lo que sabe de ti
        self.automatizaciones = automatizaciones  # AlmacenReglas (MVP cap. 5): reglas del usuario, persistentes
        self._foco_modelo: dict[str, dict] = {}  # a que afirmacion se refiere "eso" por usuario
        # M3.0 — captura de senales. OPCIONAL y PASIVA: si no hay registro de contexto, el sistema
        # se comporta exactamente igual que en M2. La captura observa el turno; no participa en
        # ninguna decision (restriccion 2 del gate del CEO).
        self.contexto = contexto
        self.almacen = AlmacenSenales(memory) if contexto is not None else None
        # Un adaptador suelto se envuelve; el resto del codigo trabaja siempre contra un registro.
        if hasattr(adaptadores, "para"):
            self.registro = adaptadores
        else:
            self.registro = RegistroAdaptadores([adaptadores])
        # Sin motor inyectado se construye uno sobre el mismo registro y los mismos permisos: el
        # flujo es identico venga de donde venga la peticion.
        self.motor = motor if motor is not None else MotorAutomatizacion(self.registro, permissions)
        self._timers: dict[str, Timer] = {}
        self._done: dict[str, asyncio.Event] = {}
        self._results: dict[str, dict] = {}
        self._dialogue: dict[str, list[tuple[str, str]]] = {}  # memoria de trabajo por usuario
        self._DIALOG_N = 6
        bus.subscribe("perception.turn_end", self.on_turn)

    async def handle_utterance(self, user_id, audio_text, trace_id):
        t = Timer()
        self._timers[trace_id] = t
        self._done[trace_id] = asyncio.Event()
        text = await self.voice.stt(audio_text, trace_id)
        t.mark("stt")
        await self.bus.publish(Event("perception.turn_end", trace_id, user_id, {"text": text}))

    async def wait(self, trace_id, timeout=10):
        await asyncio.wait_for(self._done[trace_id].wait(), timeout)
        return self._results.get(trace_id)

    async def on_turn(self, ev: Event):
        tid = ev.trace_id
        uid = ev.user_id
        text = ev.payload["text"]
        t = self._timers.get(tid) or Timer()
        # Soberania del modelo del usuario: inspeccionar/entender/corregir/olvidar lo que AURA sabe de ti.
        if self.modelo_usuario is not None:
            resp = await self._atender_modelo_usuario(uid, text)
            if resp is not None:
                await self._finalizar_turno(uid, tid, text, resp, "core", t)
                return
        # Superficie del Centro de Notificaciones: "¿que ha pasado mientras no estaba?" se responde con
        # lo que AURA hizo, sin consultar memoria ni LLM (es un hecho del sistema, no una inferencia).
        if self.notificaciones is not None and _es_consulta_de_notificaciones(text):
            await self._finalizar_turno(uid, tid, text, self._resumen_notificaciones(), "core", t)
            return
        # Automatizaciones del usuario (MVP capacidad 5): inspeccionar y crear reglas. Deterministas como el
        # resto de superficies; el LLM no interviene (definir o listar una regla es un hecho, no una inferencia).
        if self.automatizaciones is not None:
            if _es_consulta_de_reglas(text):
                await self._finalizar_turno(uid, tid, text, self._describir_reglas(uid), "core", t)
                return
            if _es_creacion_de_regla(text):
                await self._finalizar_turno(uid, tid, text, self._crear_regla(uid, text), "core", t)
                return
        hits = await self.memory.recall(uid, text)
        t.mark("memory")
        # ADR-0014: la ausencia de memoria es un HECHO, no una inferencia. Si el usuario
        # pregunta por un recuerdo y no existe registro, responde el nucleo y NO se consulta
        # al LLM: no se le da ocasion de inferir, completar ni reformular lo inexistente.
        if not hits and _es_consulta_de_memoria(text):
            say = "No tengo ningun recuerdo registrado sobre eso."
            obs.log(
                "CORE", "grounding", "memoria vacia -> respuesta determinista (sin llamada al LLM)", tid, audit=True
            )
            await self._finalizar_turno(uid, tid, text, say, "core", t)
            return

        ctx = " | ".join(h["content"] for h in hits) if hits else "(sin recuerdos relevantes)"
        buffer = self._dialogue.get(uid, [])
        recent = "\n".join(f"(previo) tu: {u} | AURA: {a}" for u, a in buffer) or "(inicio de la conversacion)"
        prompt = f"[contexto memoria: {ctx}]\n[conversacion reciente:\n{recent}]\nUsuario: {text}"
        prov, out = await self.router.route(prompt, tid)
        t.mark("llm")
        action, args, say = _parse_decision(out, tid)
        if action != "consulta":
            evento = {"action": action, "args": args}
            # Las automatizaciones del usuario reaccionan al evento ANTES de ejecutar la accion que lo
            # origino: "guarda ANTES una copia" exige que la copia ocurra antes del borrado. Cada regla
            # disparada recorre el motor (mismo camino, mismos permisos); copiar es verde -> sin confirmacion.
            disparos = await self._disparar_reglas(uid, evento, tid)
            # M2.5 (ALERTA-005): la ejecucion se delega en el motor, unico camino del sistema. El
            # orquestador no llama a ningun adaptador: aqui no hay ruta alternativa que mantener.
            cmd_ev = Event("action.command", tid, uid, evento, causation_id=ev.event_id)
            res = await self.motor.ejecutar(action, args, tid, cmd_ev.event_id, origen="conversacion")
            say = self._redactar_con_reglas(action, args, say, res, disparos)
            # Productor del Centro (MVP): AURA registra, en lenguaje natural, lo que acaba de hacer, para
            # poder contarselo despues al usuario ("¿que ha pasado mientras no estaba?").
            if self.notificaciones is not None:
                self.notificaciones.recibir(notificacion_de_accion(action, args, res))
        await self._finalizar_turno(uid, tid, text, say, prov, t)

    async def _atender_modelo_usuario(self, uid: str, text: str) -> str | None:
        """Atiende las cuatro conversaciones de soberania. Devuelve la respuesta, o None si no aplica.

        Fiel al modelo interno (declarado/observado); no infiere ni inventa certezas. "eso" se resuelve
        con el foco: la ultima afirmacion en discusion, o la que el texto mencione explicitamente.
        """
        t = _normalizar(text)
        entradas = await self.modelo_usuario.ver(uid)
        vivas = [e for e in entradas if not e.get("refutada")]

        if _cae_en(t, _PAT_MODELO_VER):
            # Foco por defecto para el "eso" siguiente: la primera observada (la cuestionable); si no,
            # la primera declarada. La declarada no suele necesitar explicacion ("me lo dijiste").
            if vivas:
                self._foco_modelo[uid] = next((e for e in vivas if e.get("origen") != "declarada"), vivas[0])
            return describir_conocimiento(entradas)

        if _cae_en(t, _PAT_MODELO_OLVIDA):  # antes que refutar/porque: "olvida" es inequivoco
            foco = self._foco(uid, t, vivas)
            n = await self.modelo_usuario.borrar(uid, foco["contenido"]) if foco else 0
            return (
                "Hecho. Ya no lo consideraré parte de lo que sé de ti." if n else "No he encontrado eso para olvidarlo."
            )

        if _cae_en(t, _PAT_MODELO_REFUTA):
            foco = self._foco(uid, t, vivas)
            if foco:
                await self.modelo_usuario.refutar(uid, foco["contenido"])
                return "Entendido, lo corrijo. Dejo de darlo por cierto."
            return "¿A qué te refieres? Puedes decirme «¿qué sabes de mí?» y lo revisamos."

        if _cae_en(t, _PAT_MODELO_PORQUE):
            foco = self._foco(uid, t, vivas)
            return explicar_entrada(foco) if foco else "Ahora mismo no estoy afirmando nada sobre ti."

        return None

    def _foco(self, uid: str, t: str, vivas: list[dict]) -> dict | None:
        """Resuelve "eso": la entrada que el texto menciona, o la ultima en discusion, o la primera viva."""
        for e in vivas:
            palabras = [w for w in _normalizar(e["contenido"]).split() if len(w) > 4]
            if any(w in t for w in palabras):
                self._foco_modelo[uid] = e
                return e
        return self._foco_modelo.get(uid) or (vivas[0] if vivas else None)

    def _resumen_notificaciones(self) -> str:
        """Lo que AURA hizo desde la ultima vez, en lenguaje natural (comunicable, no un log).

        Orden CRONOLOGICO: "¿que ha pasado?" se narra en el orden en que ocurrio, no por criticidad
        (la priorizacion de `listar()` es para una bandeja, no para contar una secuencia de hechos).
        """
        items = sorted(self.notificaciones.listar(), key=lambda n: n.ts)
        if not items:
            return "No ha pasado nada relevante mientras no estabas."
        lineas = "\n".join(f"• {n.titulo}" for n in items)
        return f"Desde la última vez:\n{lineas}"

    # ----------------------------------------- automatizaciones del usuario --

    def _describir_reglas(self, uid: str) -> str:
        """Responde "¿que automatizaciones tengo?" con lo que hay REALMENTE en el almacen.

        Fiel al estado interno: si no hay ninguna, se dice; no se describe una intencion ni un plan.
        """
        reglas = self.automatizaciones.listar(uid)
        if not reglas:
            return "No tienes ninguna automatización activa."
        cabecera = "1 automatización activa" if len(reglas) == 1 else f"{len(reglas)} automatizaciones activas"
        lineas = "\n".join(f"• {r.metadatos.get('descripcion') or f'{r.accion} cuando {r.evento}'}" for r in reglas)
        return f"Tienes {cabecera}:\n{lineas}"

    def _crear_regla(self, uid: str, text: str) -> str:
        """Persiste la automatizacion que el usuario acaba de definir y lo confirma.

        El MVP reconoce un unico patron ("copia antes de borrar"), pero lo que se guarda es el MODELO
        GENERAL de regla —evento, condicion declarativa, accion y args por referencia al evento—, de modo
        que ampliar el reconocedor no obligue a migrar los datos ya escritos. `rule_id` es estable: repetir
        la frase no crea una regla duplicada, y AURA lo dice en lugar de fingir que aprendio algo nuevo.
        """
        if any(r.rule_id == _ID_COPIA_ANTES_DE_BORRAR for r in self.automatizaciones.listar(uid)):
            return "Ya lo hago: guardo una copia antes de borrar."
        regla = ReglaUsuario(
            rule_id=_ID_COPIA_ANTES_DE_BORRAR,
            user_id=uid,
            evento="action.command",
            condicion={"campo": "action", "op": "==", "valor": "borrar_archivo"},
            accion="copiar_archivo",
            args={"ruta": "$evento.ruta"},  # referencia al evento: opera sobre el archivo real de cada vez
            metadatos={"descripcion": "Guardar una copia antes de borrar un archivo", "frase": text},
        )
        self.automatizaciones.crear(regla)
        obs.log("REGLA", "automatizacion", f"automatizacion creada: {regla.rule_id}", "-", audit=True)
        return "Entendido. Lo haré a partir de ahora."

    async def _disparar_reglas(self, uid: str, evento: dict, tid: str) -> list[dict]:
        """Ejecuta las automatizaciones del usuario que aplican a este evento. Devuelve lo ocurrido.

        Cada disparo recorre el MISMO camino que cualquier otra accion —el motor— con sus permisos y su
        dry-run: una regla no es un atajo para saltarse el gate (RN-5). El `event_id` distingue el disparo
        del evento del usuario para que la idempotencia del adaptador no confunda ambos.

        DEUDA (fuera del alcance fijado): si un disparo previo falla, la accion del usuario se ejecuta
        igualmente; el MVP no tiene semantica transaccional. El fallo no se silencia: se comunica en la
        respuesta y en el Centro de Notificaciones.
        """
        if self.automatizaciones is None:
            return []
        disparos: list[dict] = []
        for regla in self.automatizaciones.aplicables(uid, "action.command"):
            if not evaluar_condicion(regla.condicion, evento):
                continue
            args = resolver_args(regla.args, evento)
            res = await self.motor.ejecutar(
                regla.accion, args, tid, f"{tid}:regla:{regla.rule_id}", origen=f"regla:{regla.rule_id}"
            )
            obs.log(
                "REGLA",
                "automatizacion",
                f"regla {regla.rule_id} -> {regla.accion} {res.get('estado')}",
                tid,
                audit=True,
            )
            n = notificacion_de_accion(regla.accion, args, res)
            if self.notificaciones is not None:
                self.notificaciones.recibir(n)
            disparos.append({"regla": regla, "args": args, "resultado": res, "mensaje": n.titulo})
        return disparos

    def _redactar_con_reglas(self, action: str, args: dict, say_llm: str, res: dict, disparos: list[dict]) -> str:
        """Narra el turno completo: lo que hizo la automatizacion Y lo que pidio el usuario.

        Sin esto, AURA ejecutaria la regla en silencio y el usuario no sabria que ocurrio. Se reutiliza el
        mismo texto comunicable que va al Centro de Notificaciones, para que AURA cuente lo mismo en el
        momento y despues. Lo que no se ejecuto nunca se narra como hecho (ALERTA-005).
        """
        base = self._redactar(action, say_llm, res)
        if not disparos:
            return base
        hechos = [d for d in disparos if d["resultado"].get("estado") == "ejecutada"]
        avisos = [d["mensaje"] for d in disparos if d["resultado"].get("estado") != "ejecutada"]
        clausula = _CLAUSULA_USUARIO.get(action)
        if hechos and clausula and res.get("estado") == "ejecutada":
            previo = ", ".join(d["mensaje"].rstrip(".") for d in hechos)
            return " ".join([*avisos, f"{previo} y luego {clausula}. [accion {action} ejecutada]"])
        return " ".join([*avisos, *[d["mensaje"] for d in hechos], base])

    def _redactar(self, action: str, say_llm: str, res: dict) -> str:
        """Construye la respuesta sobre el RESULTADO REAL, no sobre lo que el modelo dijo.

        ALERTA-005 punto 4: queda prohibido responder con exito cuando no hay evidencia de
        ejecucion. Antes de M2.5, una accion autorizada que ningun adaptador podia atender devolvia
        la frase del LLM —"Listo el directorio"— y AURA afirmaba haber hecho algo que no hizo.

        La frase del modelo solo sobrevive cuando el adaptador devolvio un resultado. En cualquier
        otro caso se DESCARTA: el modelo no es autoridad sobre los hechos del sistema (ADR-0014), y
        una frase de exito redactada antes de intentar la accion no es informacion, es ruido con
        apariencia de confirmacion.
        """
        estado = res.get("estado")
        if estado == "ejecutada":
            return f"{say_llm} [accion {action} ejecutada]"
        if estado == "detenida":
            return f"No ejecute la accion. [accion {action} detenida: {res.get('motivo')}]"
        return f"No pude ejecutar la accion. [error en {action}: {res.get('motivo')}]"

    async def _capturar_senales(self, uid, tid, text):
        """Captura pasiva de senales de aprendizaje (M3.0).

        Se ejecuta al CIERRE del turno, despues de que la respuesta ya este decidida: asi es
        estructuralmente imposible que la captura influya en lo que AURA contesta (restriccion 2).

        Un fallo aqui no puede costarle el turno al usuario. La captura es infraestructura para el
        futuro; la conversacion es el producto de hoy.
        """
        if self.contexto is None or self.almacen is None:
            return
        try:
            self.contexto.observar(text)
            senales = await self.contexto.recoger_todas(tid)
            if senales:
                n = await self.almacen.guardar(uid, senales)
                obs.log("CTX", "senales", f"capturadas {n} senal(es) de aprendizaje", tid)
        except Exception as e:
            obs.log("WARN", "senales", f"captura fallida (turno no afectado): {e}", tid)

    async def _finalizar_turno(self, uid, tid, text, say, prov, t):
        """Cierre comun del turno: persistencia, memoria de trabajo, voz, metricas y resultado."""
        await self.memory.write(uid, "episodica", f"usuario dijo: {text}", {"trace_id": tid, "fuente": "conversacion"})
        await self._capturar_senales(uid, tid, text)
        buffer = self._dialogue.setdefault(uid, [])
        buffer.append((text, say))
        del buffer[: max(0, len(buffer) - self._DIALOG_N)]  # conserva las ultimas N (memoria de trabajo)
        await self.voice.tts(say, tid)
        t.mark("tts")
        total = t.total_ms()
        obs.log("LAT", "orchestrator", f"latencia total {total:.1f} ms (proveedor={prov})", tid, audit=True)
        self._results[tid] = {"say": say, "provider": prov, "latency_ms": total, "marks": dict(t.marks)}
        if tid in self._done:
            self._done[tid].set()
