"""Punto de entrada unico de produccion (MA.1).

**Este es el unico lugar del proyecto donde se cablea AURA.**

Antes de MA.1 habia siete scripts construyendo el `Orchestrator` cada uno por su cuenta, y la
auditoria del 2026-07-21 midio la consecuencia: **ninguno activaba la captura de senales de M3.0**,
y solo uno registraba el adaptador del computador. Cada punto de entrada era una oportunidad de
encender el sistema a medias sin que nadie lo notara — el mismo patron que produjo ALERTA-004
(grounding declarado y ausente) y ALERTA-005 (adaptadores construidos e inalcanzables).

La regla que este modulo hace cumplir:

> **Si una capacidad esta construida, el arranque la enciende. Si no debe encenderse, no deberia
> estar construida.**

Los scripts de demo y validacion deben **consumir** esta composicion, no replicarla. Un cableado
propio en otro fichero reabre exactamente el agujero que MA.1 cierra.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import observability as obs
from .adapters.hitl_consola import confirmar_por_consola
from .adapters.home_assistant import HomeAssistantMock
from .adapters.voice import VoiceAdapterMock
from .artefactos import ModelResolver
from .bus import InProcessEventBus
from .conectores.computador import ConectorComputador
from .conectores.conversacion import ConectorConversacion
from .conectores.hogar import ConectorHogar
from .contracts import Adapter, MemoryStore, ModelProvider, VoiceAdapter
from .core.activation_context_builder import ActivationContextBuilder
from .core.automatizacion import MotorAutomatizacion
from .core.capability_manager import CapabilityManager
from .core.capability_registry import CapabilityRegistry
from .core.capacidades import Estado, PerfilHardware, PlanActivacion
from .core.catalogo_capacidades import catalogo
from .core.conectores_externos import habilitar
from .core.contexto import RegistroContexto
from .core.director import DirectorGeneral, RegistroEjecutores
from .core.estado_operativo import AlmacenEstadoOperativo
from .core.kill_switch import KillSwitch
from .core.modelo_usuario import ModeloUsuario
from .core.motor_ciclo import MotorDelCiclo
from .core.notificaciones import CentroNotificaciones
from .core.orchestrator import Orchestrator
from .core.permissions import PermissionManager
from .core.registro import RegistroAdaptadores
from .core.reglas import AlmacenReglas
from .modules.memory import PersistentMemory
from .modules.memory_semantic import SemanticMemory
from .modules.router import ModelRouter


class _PerfilInyectado:
    """DetectorHardware del arranque: devuelve el perfil que trae `Configuracion`.

    Cableado, no arquitectura: implementa el contrato ya aprobado (`DetectorHardware`) para que el
    Builder tenga de donde tomar las metricas. El detector REAL —el que mide capacidad efectiva con
    pruebas (D44)— es **latente-prevista**: requiere hardware para construirse y validarse.
    """

    def __init__(self, perfil: PerfilHardware) -> None:
        self._perfil = perfil

    def detectar(self) -> PerfilHardware:
        return self._perfil


# Directorio por defecto del artefacto de embeddings de N2: una ubicacion estandar de AURA que contiene
# el modelo + su `manifiesto.json` (ADR-0022). Hoy normalmente ausente -> N2 se materializa como N1.
# Configurable por AURA_EMBED_MODEL_DIR sin editar codigo (D24); cambiar de modelo = apuntar a otro
# directorio con su propio manifiesto (sin tocar codigo).
_MODELO_EMBED_DEFECTO = "~/.aura/models/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True)
class Materializacion:
    """Que se consiguio ENSAMBLAR realmente para una capacidad, frente a lo que el plan permitia.

    Existe porque son dos hechos distintos y hasta ahora solo se registraba el primero:

    - `estado_plan`   — lo que el **hardware permite** (lo decide el `CapabilityManager`, y sigue siendo
      cierto aunque falte un artefacto: la RAM no desaparece porque se borre un fichero);
    - `estado_efectivo` — lo que **de verdad quedo corriendo** tras intentar ensamblarlo.

    Cuando difieren —artefacto ausente, dependencia caida, integridad rota— **AURA declara el segundo**
    (CEO, 2026-08-02: *"nunca debe declarar una capacidad activa si en realidad esta ejecutando otra"*;
    INV-9: no se finge capacidad). El plan NO se toca ni se reinterpreta: INV-7 lo prohibe, y ademas seria
    falsearlo en sentido contrario. Se anade un hecho nuevo, no se corrige uno viejo.
    """

    capacidad: str
    estado_plan: Estado
    estado_efectivo: Estado
    nivel: str  # que corre realmente, en lenguaje del dominio ("N1 (almacen minimo)")
    degradada: bool  # el plan permitia mas de lo que se logro ensamblar
    motivo: str  # por que, si `degradada`; vacio si no hay discrepancia


def _efectivas(plan: PlanActivacion, materializaciones: tuple[Materializacion, ...], estado: Estado) -> tuple[str, ...]:
    """Capacidades en `estado` segun lo que REALMENTE corre: el plan, corregido por lo que se ensamblo.

    Unica traduccion de "lo que el hardware permite" a "lo que AURA puede declarar". No modifica el plan
    (INV-7 lo prohibe): lo lee y aplica encima el hecho de la materializacion.
    """
    efectivo = {m.capacidad: m.estado_efectivo for m in materializaciones}
    return tuple(d.nombre for d in plan.decisiones if efectivo.get(d.nombre, d.estado) == estado)


def _memoria_por_nivel(estado: Estado, ruta: str) -> tuple[MemoryStore, str, str]:
    """Selecciona la implementacion de memoria segun el nivel que decide el plan (C2.3, ADR-0020).

    - **ACTIVA** + modelo de embeddings presente -> **N2** (`SemanticMemory`, indice semantico).
    - En cualquier otro caso -> **N1** (`PersistentMemory`, almacen minimo lexico), sin perdida.

    Esta funcion es el UNICO punto donde el estado del plan se traduce en una materializacion distinta
    (D40/INV-7: la composicion ENSAMBLA, no decide; el estado ya lo decidio el Manager). La disponibilidad
    del modelo es **cableado**, no decision: si el artefacto no esta o no puede cargarse, se materializa N1
    y el arranque no se interrumpe (degradacion transparente, ADR-0020). N3 sigue **latente-prevista**.

    El artefacto se resuelve por **manifiesto** (ADR-0022): el `ModelResolver` localiza el modelo, verifica
    su integridad (SHA-256) y su formato antes de entregar la ruta. La ruta se resuelve en el ARRANQUE, no
    al importar: asi es configuracion, no un valor congelado.
    """
    modelo_dir = os.path.expanduser(os.environ.get("AURA_EMBED_MODEL_DIR", _MODELO_EMBED_DEFECTO))
    motivo = ""
    if estado is Estado.ACTIVA:
        try:
            ruta_validada = ModelResolver().resolver(modelo_dir)  # ADR-0022: localiza + integridad + formato
            return SemanticMemory(ruta, ruta_validada), "N2 (indice semantico)", ""
        except Exception as e:  # artefacto ausente/invalido o carga fallida: se materializa N1, sin romper
            # El motivo VIAJA con la materializacion en lugar de perderse en una linea de consola. Antes
            # este log no llevaba `audit=True`: la degradacion no dejaba rastro forense y el sistema seguia
            # anunciando la capacidad como activa. Ese era el defecto.
            motivo = str(e)
    return PersistentMemory(ruta), "N1 (almacen minimo)", motivo


@dataclass
class Configuracion:
    """Configuracion del arranque. Se lee del entorno; **no se edita codigo para cambiarla**.

    `datos` es el directorio donde vive el estado permanente: memoria, audit log y kill switch. En
    produccion NO debe ser un directorio temporal — la auditoria encontro que todo el historial del
    proyecto (12 entradas) se habia perdido por escribir en `/tmp`.
    """

    datos: str = field(default_factory=lambda: os.environ.get("AURA_DATOS", os.path.expanduser("~/.aura")))
    raices_permitidas: tuple[str, ...] | None = None
    usar_stack_real: bool = field(default_factory=lambda: os.environ.get("AURA_STACK_REAL") == "1")
    modelo: str = field(default_factory=lambda: os.environ.get("AURA_LLM_MODEL", "qwen2.5:3b"))
    presupuesto_latencia_ms: int = 1200
    # Conectores externos habilitados por el usuario (MA.4, ADR-0019). Opt-in explicito: por defecto
    # NINGUNO. Es configuracion del usuario, no una lista blanca en el Core (ADR-0015).
    conectores_externos_habilitados: frozenset[str] = field(default_factory=frozenset)
    # Perfil de capacidad efectiva (D44) que el Capability Manager evalua. Por defecto CONSERVADOR
    # (recursos vacios) -> las capacidades operan en su nivel minimo. La deteccion real de hardware es
    # una capacidad latente-prevista (DetectorPerfil): C1/C2 no la implementan; el perfil se inyecta.
    perfil: PerfilHardware = field(default_factory=PerfilHardware)

    @classmethod
    def desde_entorno(cls) -> Configuracion:
        return cls()


@dataclass
class Sistema:
    """AURA armada. Se expone cada pieza para que el arranque sea inspeccionable y verificable."""

    orquestador: Orchestrator
    motor: MotorAutomatizacion
    permisos: PermissionManager
    kill_switch: KillSwitch
    registro_adaptadores: RegistroAdaptadores
    registro_contexto: RegistroContexto
    memoria: MemoryStore  # N1 (PersistentMemory) o N2 (SemanticMemory) segun el plan
    notificaciones: CentroNotificaciones
    modelo_usuario: ModeloUsuario
    automatizaciones: AlmacenReglas
    estado_operativo: AlmacenEstadoOperativo
    director: DirectorGeneral
    motor_ciclo: MotorDelCiclo
    plan: PlanActivacion  # lo que el hardware PERMITE (decision del Manager; nunca se reinterpreta, INV-7)
    materializaciones: tuple[Materializacion, ...]  # lo que se consiguio ENSAMBLAR
    ruta_memoria: str
    ruta_audit: str

    @property
    def capacidades_activas_efectivas(self) -> tuple[str, ...]:
        """Lo que AURA puede declarar activo. **Usa esto, no `plan.activas`, para informar a nadie.**

        `plan.activas` responde "¿lo permite el hardware?"; esta propiedad responde "¿esta corriendo?".
        Solo la segunda puede comunicarse al usuario o al operador sin arriesgarse a afirmar algo falso.
        """
        return _efectivas(self.plan, self.materializaciones, Estado.ACTIVA)

    @property
    def capacidades_degradadas_efectivas(self) -> tuple[str, ...]:
        return _efectivas(self.plan, self.materializaciones, Estado.DEGRADADA)


# Responsable -> accion del catalogo que lo atiende. Es el equivalente, para los agentes del SO
# Interno, de lo que `RegistroAdaptadores` hace con las capacidades: un responsable, un dueno. Hoy solo
# se declara el que existe de verdad; declarar agentes no construidos seria fingir capacidad (INV-9).
_EJECUTORES = {"programador": "copiar_archivo", "qa": "verificar_calidad"}


def componer(config: Configuracion | None = None, confirmador=None) -> Sistema:
    """Arma AURA completa. Unico cableado del proyecto.

    Anadir una capacidad al sistema significa anadirla AQUI, y la prueba de composicion falla si una
    capacidad declarada no queda encendida.
    """
    config = config or Configuracion.desde_entorno()
    os.makedirs(config.datos, exist_ok=True)

    ruta_memoria = os.path.join(config.datos, "memoria.json")
    ruta_audit = os.path.join(config.datos, "audit.jsonl")
    ruta_kill = os.path.join(config.datos, "KILL")

    # Registro forense persistente (H2). Se configura ANTES que nada: si algo falla durante el
    # arranque, ese fallo tambien queda registrado.
    obs.configure_audit(ruta_audit)

    kill_switch = KillSwitch(ruta_kill)
    permisos = PermissionManager(confirmador or confirmar_por_consola, kill_switch=kill_switch)

    # --- Adaptadores: todo lo que AURA puede hacer -------------------------
    from .adapters.computador import AdaptadorComputador
    from .adapters.qa import EjecutorQA

    raices = config.raices_permitidas
    adaptadores: list[Adapter] = [
        AdaptadorComputador(raices=raices) if raices else AdaptadorComputador(),
        HomeAssistantMock(),
        # Ejecutor QA del SO Interno: AURORA puede verificarse a si misma. Su raiz es la del propio
        # arbol de trabajo y se fija AQUI, no llega por argumentos de ninguna llamada.
        EjecutorQA(raiz=str(Path(__file__).resolve().parents[1])),
    ]
    registro_adaptadores = RegistroAdaptadores(adaptadores)

    # Ejecutor unico (M2.5): conversacion, reglas y notificaciones convergen aqui.
    motor = MotorAutomatizacion(registro_adaptadores, permisos)

    # --- Conectores de contexto: todo lo que AURA observa (ADR-0015) -------
    # Gate de habilitacion (MA.4, ADR-0019): un conector externo requiere opt-in explicito del usuario
    # y declaracion de transparencia. Hoy TODOS los conectores son locales -> el gate es un no-op.
    habilitacion = habilitar(
        [ConectorConversacion(), ConectorComputador(ruta_audit), ConectorHogar(ruta_audit)],
        config.conectores_externos_habilitados,
    )
    registro_contexto = RegistroContexto(habilitacion.activos)
    if habilitacion.informe:
        obs.log("BOOT", "composicion", f"conectores externos habilitados:\n{habilitacion.informe}", "-", audit=True)

    # --- Modelo y voz ------------------------------------------------------
    if config.usar_stack_real:
        from .adapters.voice_real import WhisperPiperVoice
        from .modules.providers_real import OllamaProvider

        proveedores: list[ModelProvider] = [OllamaProvider("ollama", config.modelo)]
        voz: VoiceAdapter = WhisperPiperVoice(piper_voice=os.environ.get("AURA_PIPER_VOICE", ""))
    else:
        from .modules.router import MockProvider

        proveedores = [MockProvider("mock", 100, healthy=True)]
        voz = VoiceAdapterMock()

    # --- Capacidades por perfil (C2, ADR-0021/D45/D46) ---------------------
    # El Capability Manager decide el estado de cada capacidad SOLO desde el PerfilHardware. La
    # composicion consume el plan (ensambla, no decide, D40) y selecciona la implementacion de memoria
    # segun el nivel que el plan permite. El Manager es el UNICO que decide estados (regla permanente).
    # Flujo definitivo: Detectores -> Builder -> ActivationContext -> Manager -> Plan.
    # La composicion ENSAMBLA (D40): inyecta los detectores, pide el contexto al Builder y consume el plan.
    # Hoy no hay detectores de entorno (ninguna capacidad declarada los necesita), asi que el conjunto de
    # capacidades soportadas sale vacio, igual que en el ensamblaje provisional.
    contexto = ActivationContextBuilder(_PerfilInyectado(config.perfil), ()).construir()
    plan = CapabilityManager(CapabilityRegistry(catalogo())).planificar(contexto)
    dec_memoria = plan.decision("memoria")
    estado_memoria = dec_memoria.estado if dec_memoria is not None else Estado.DEGRADADA
    memoria, nivel_memoria, motivo_memoria = _memoria_por_nivel(estado_memoria, ruta_memoria)

    # Estado EFECTIVO: si el plan permitia mas de lo que se logro ensamblar, manda lo ensamblado.
    degradada_memoria = bool(motivo_memoria)
    materializaciones = (
        Materializacion(
            capacidad="memoria",
            estado_plan=estado_memoria,
            estado_efectivo=Estado.DEGRADADA if degradada_memoria else estado_memoria,
            nivel=nivel_memoria,
            degradada=degradada_memoria,
            motivo=motivo_memoria,
        ),
    )
    for m in materializaciones:
        if m.degradada:
            # AUDITADO (audit=True): una capacidad que corre por debajo de lo planificado es un hecho
            # forense, no una curiosidad de consola. Sin esta entrada, la degradacion es indetectable
            # despues del arranque — que es justamente como paso inadvertida hasta la revision del 2026-08-02.
            obs.log(
                "MATZ",
                "composicion",
                f"materializacion degradada: '{m.capacidad}' planificada {m.estado_plan.name} pero corre "
                f"{m.nivel} ({m.motivo}); AURA la declara {m.estado_efectivo.name}",
                "-",
                audit=True,
            )
    obs.log(
        "BOOT",
        "composicion",
        f"capacidades (estado EFECTIVO): activas={list(_efectivas(plan, materializaciones, Estado.ACTIVA))} "
        f"degradadas={list(_efectivas(plan, materializaciones, Estado.DEGRADADA))} "
        f"latentes={list(plan.latentes)}; memoria -> {nivel_memoria}",
        "-",
        audit=True,
    )

    # Centro de Notificaciones (MVP): AURA registra en lenguaje natural lo que hace, para poder contarselo
    # al usuario ("¿que ha pasado mientras no estaba?"). Reutiliza el motor para el dry-run de `actuar`.
    centro_notificaciones = CentroNotificaciones(permisos=permisos, motor=motor)
    # Soberania del modelo del usuario (MVP): inspeccionar/entender/corregir/olvidar lo que AURA sabe de ti,
    # sobre la MISMA memoria del sistema (el olvido persiste; ADR-0017).
    modelo_usuario = ModeloUsuario(memoria)
    # Automatizaciones definidas por el usuario (MVP capacidad 5, Bible 6.4). Sus reglas son DATO DEL
    # USUARIO y viven junto al resto de su estado permanente: por eso persisten al reiniciar AURA, que es
    # exactamente lo que distingue una automatizacion de una instruccion dada en una conversacion.
    automatizaciones = AlmacenReglas(os.path.join(config.datos, "reglas.jsonl"))

    # SISTEMA OPERATIVO INTERNO. El estado del trabajo de AURORA vive en disco junto al resto de su
    # estado permanente: eso es lo que le permite reanudar tras apagarse sin depender de una
    # conversacion. El Director es el UNICO coordinador y no ejecuta nada por su cuenta: despacha por
    # el `motor`, de modo que hereda permisos, dry-run y kill switch (ALERTA-005, RN-5).
    estado_operativo = AlmacenEstadoOperativo(os.path.join(config.datos, "estado_operativo.jsonl"))
    director = DirectorGeneral(estado_operativo, motor, RegistroEjecutores(_EJECUTORES))
    # EL LATIDO. Sin esto el Director solo existe cuando alguien pide una vuelta, y AURORA depende de
    # un modelo externo para funcionar. El kill switch se comprueba ANTES de cada latido (RN-3).
    motor_ciclo = MotorDelCiclo(director, kill_switch=kill_switch)

    orquestador = Orchestrator(
        InProcessEventBus(),
        memoria,
        ModelRouter(proveedores, config.presupuesto_latencia_ms),
        permisos,
        voz,
        registro_adaptadores,
        motor=motor,
        contexto=registro_contexto,  # captura de senales ENCENDIDA (M3.0)
        notificaciones=centro_notificaciones,
        modelo_usuario=modelo_usuario,
        automatizaciones=automatizaciones,
    )

    obs.log(
        "BOOT",
        "composicion",
        f"AURA lista: {len(registro_adaptadores.capacidades())} capacidades, "
        f"{len(registro_contexto.fuentes)} fuentes de contexto, "
        f"stack={'real' if config.usar_stack_real else 'mock'}",
        "-",
        audit=True,
    )

    return Sistema(
        orquestador=orquestador,
        motor=motor,
        permisos=permisos,
        kill_switch=kill_switch,
        registro_adaptadores=registro_adaptadores,
        registro_contexto=registro_contexto,
        memoria=memoria,
        notificaciones=centro_notificaciones,
        modelo_usuario=modelo_usuario,
        automatizaciones=automatizaciones,
        estado_operativo=estado_operativo,
        director=director,
        motor_ciclo=motor_ciclo,
        plan=plan,
        materializaciones=materializaciones,
        ruta_memoria=ruta_memoria,
        ruta_audit=ruta_audit,
    )
