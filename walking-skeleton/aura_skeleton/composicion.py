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

from . import observability as obs
from .adapters.hitl_consola import confirmar_por_consola
from .adapters.home_assistant import HomeAssistantMock
from .adapters.voice import VoiceAdapterMock
from .bus import InProcessEventBus
from .conectores.computador import ConectorComputador
from .conectores.conversacion import ConectorConversacion
from .conectores.hogar import ConectorHogar
from .contracts import Adapter, ModelProvider, VoiceAdapter
from .core.automatizacion import MotorAutomatizacion
from .core.conectores_externos import habilitar
from .core.contexto import RegistroContexto
from .core.kill_switch import KillSwitch
from .core.orchestrator import Orchestrator
from .core.permissions import PermissionManager
from .core.registro import RegistroAdaptadores
from .modules.memory import PersistentMemory
from .modules.router import ModelRouter


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
    memoria: PersistentMemory
    ruta_memoria: str
    ruta_audit: str


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

    raices = config.raices_permitidas
    adaptadores: list[Adapter] = [
        AdaptadorComputador(raices=raices) if raices else AdaptadorComputador(),
        HomeAssistantMock(),
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

    memoria = PersistentMemory(ruta_memoria)
    orquestador = Orchestrator(
        InProcessEventBus(),
        memoria,
        ModelRouter(proveedores, config.presupuesto_latencia_ms),
        permisos,
        voz,
        registro_adaptadores,
        motor=motor,
        contexto=registro_contexto,  # captura de senales ENCENDIDA (M3.0)
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
        ruta_memoria=ruta_memoria,
        ruta_audit=ruta_audit,
    )
