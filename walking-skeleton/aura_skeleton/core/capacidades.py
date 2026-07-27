"""Tipos del Registro de Capacidades (C1, ADR-0021 / D45 / Bible 3.1 P-ARQ-9).

Datos PUROS, sin comportamiento. Una `Capacidad` es una **declaracion pasiva**: describe una
capacidad-subsistema (los diez campos de ADR-0021) y NO contiene logica, no decide, no conoce el hardware
y no ejecuta codigo. Por eso los criterios de promocion/degradacion **no** son funciones embebidas, sino
**reglas declarativas** (`Regla`/`Condicion`): asi una capacidad puede **serializarse, persistirse,
exportarse, inspeccionarse, versionarse y compararse** sin depender de objetos Python ni de funciones en
memoria — el catalogo completo podria vivir como JSON/YAML sin cambiar la arquitectura.

**Independencia del catalogo (principio permanente, CEO 2026-07-26).** `Capacidad` es el **modelo canonico
del dominio**. JSON, YAML, base de datos o repositorios remotos son solo mecanismos de
**persistencia/transporte**; los **Loaders** (p. ej. `JsonCapabilityLoader`, `YamlCapabilityLoader`,
`DatabaseCapabilityLoader`, `RemoteCapabilityLoader`) seran los UNICOS responsables de transformar un
formato externo en una coleccion de `Capacidad`. Ni el `CapabilityRegistry` ni el `CapabilityManager`
conocen formatos: podra anadirse cualquier Loader nuevo sin tocar una sola linea de ellos. Patron
permanente para todo catalogo futuro de AURA.

La INTELIGENCIA (interpretar las reglas contra un `PerfilHardware` y decidir el estado) pertenece
EXCLUSIVAMENTE al `CapabilityManager` (regla permanente del CEO), no a esta declaracion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Protocol


class GradoLatencia(Enum):
    """Grado de latencia de una capacidad (ADR-0021 §3, campo 7)."""

    ACTIVABLE = "activable"  # implementacion existe tras el contrato; se enciende sola por perfil
    PREVISTA = "prevista"  # arquitectura reserva contrato y lugar; aun sin implementar (D34/D38)


class NivelAutonomia(IntEnum):
    """Nivel de autonomia (ADR-0021 campo 10). Ordenado: a mayor valor, mas autonomia.

    SIEMPRE subordinado al gate HITL (P-ARQ-1/ADR-0003/5.3): una accion de lista roja exige confirmacion
    humana sea cual sea el nivel. El Manager nunca eleva el nivel por capacidad efectiva (D33).
    """

    OBSERVACION = 0
    RECOMENDACION = 1
    HITL = 2
    AUTOMATICA_CONTROLADA = 3
    AUTONOMA_LIMITADA = 4
    AUTONOMA_COMPLETA = 5


class Fuente(Enum):
    """De donde procede el dato de una condicion, dentro del `ActivationContext`.

    RECURSO/PRUEBA -> metricas verificadas del `PerfilHardware` (magnitudes, D44).
    SOPORTE        -> hecho de dominio: la capacidad esta soportada por el entorno.
    """

    RECURSO = "recurso"
    PRUEBA = "prueba"
    SOPORTE = "soporte"


class Operador(Enum):
    """Comparadores admitidos en una condicion declarativa. El Manager los interpreta.

    Los cinco primeros son numericos (metricas); PRESENTE/AUSENTE son de pertenencia (soporte).
    """

    GE = ">="
    LE = "<="
    GT = ">"
    LT = "<"
    EQ = "=="
    PRESENTE = "presente"
    AUSENTE = "ausente"


@dataclass(frozen=True)
class PerfilHardware:
    """Capacidad EFECTIVA del entorno (D44): specs + resultados de pruebas reales.

    Es lo UNICO que el Manager recibe. Deliberadamente NO contiene marcas, modelos ni OS: solo metricas
    (p. ej. `ram_mb` en `recursos`; `embed_ms` en `pruebas`). Es un input; no necesita ser hashable.
    """

    recursos: dict[str, float] = field(default_factory=dict)
    pruebas: dict[str, float] = field(default_factory=dict)

    def valor(self, fuente: Fuente, metrica: str, defecto: float = 0.0) -> float:
        tabla = self.recursos if fuente is Fuente.RECURSO else self.pruebas
        return tabla.get(metrica, defecto)


@dataclass(frozen=True)
class ActivationContext:
    """**Unico contrato de entrada** del CapabilityManager (I-A4 / INV-4). Objeto de DOMINIO.

    Contiene exactamente dos cosas, ambas en lenguaje del dominio:
      - `hardware`: **metricas verificadas** (D44) — gobierna lo que ESCALA (promueve/degrada por umbral).
      - `capacidades_soportadas`: **nombres de capacidades que el entorno soporta** — gobierna lo que
        ABRE/CIERRA (gate). "Soportada" NO es "activa": es una ENTRADA; la decision de estado es
        exclusiva del Manager (I-A1).

    **NO contiene** tecnologia (MQTT, Ollama, Whisper, credenciales, dispositivos por producto, marcas,
    modelos, SO), ni decisiones (`Estado`/`Decision`/`PlanActivacion`), ni reglas del Registry, ni
    referencias a detectores o fuentes concretas.

    **Quien lo construye:** unicamente el ActivationContextBuilder (I-A3), a partir del detector de
    hardware (metricas) y de los detectores especializados (hechos de soporte).
    **Quien puede modificarlo:** NADIE tras su construccion (`frozen`). El Manager solo lo LEE.

    Invariantes permanentes del contrato (CEO, 2026-07-27):
      - **I-AC1** — los elementos de `capacidades_soportadas` solo pueden ser **nombres de capacidades
        declaradas en el Registry**. Queda prohibido usarlo para tokens tecnicos, nombres de productos,
        servicios, protocolos o cualquier identificador ajeno al dominio.
      - **I-AC2** — si el soporte necesitara informacion adicional (grado, version, confianza...), **no**
        se anadira automaticamente un tipo nuevo: primero debe demostrarse que ha aparecido un **concepto
        del dominio**, no una mera necesidad de implementacion. Solo entonces se reconsidera la representacion.
    """

    hardware: PerfilHardware
    capacidades_soportadas: frozenset[str] = frozenset()

    def soporta(self, capacidad: str) -> bool:
        """Lectura del hecho de dominio: ¿el entorno soporta esta capacidad?"""
        return capacidad in self.capacidades_soportadas


@dataclass(frozen=True)
class Condicion:
    """Condicion declarativa sobre el contexto de activacion. Datos puros: serializable y comparable.

    `metrica` nombra la magnitud (fuentes RECURSO/PRUEBA) o la **capacidad** cuyo soporte se consulta
    (fuente SOPORTE). `valor` se ignora en las condiciones de soporte (PRESENTE/AUSENTE).
    """

    fuente: Fuente
    metrica: str
    operador: Operador
    valor: float = 0.0  # irrelevante (y omitible) en condiciones de soporte: PRESENTE/AUSENTE


@dataclass(frozen=True)
class Regla:
    """Conjunto de condiciones en conjuncion (AND). Declarativa; el Manager la interpreta.

    Una regla **sin condiciones NO se cumple** (criterio ausente). Ampliable a disyuncion en el futuro de
    forma aditiva (p. ej. una lista de reglas alternativas), sin romper compatibilidad (ADR-0004 regla 11).
    """

    condiciones: tuple[Condicion, ...] = ()


@dataclass(frozen=True)
class Capacidad:
    """Declaracion PASIVA de una capacidad-subsistema: los diez campos de ADR-0021. Datos puros.

    Totalmente serializable/comparable/hashable: no contiene funciones. ADR-0021 es la fuente normativa;
    el Registro es la fuente unica de la clasificacion (D41).
    """

    nombre: str  # identidad unica en el registro
    # --- OPERATIVOS: gobiernan una decision o una materializacion ---
    contrato: str  # (1) id/version del Protocol que expone; consumidor previsto: la composicion
    promocion: Regla | None = None  # (5) criterio de promocion -> ACTIVA. Consumidor: Manager
    # (6) Criterio de VIABILIDAD REDUCIDA: **PISO, no techo**. Si se cumple (5) -> ACTIVA; si no y se
    # cumple (6) -> DEGRADADA; si ninguno -> LATENTE. El identificador conserva el nombre historico
    # `degradacion`; la lectura "condicion para bajar de nivel" quedo DEROGADA en ADR-0021 v1.1.0.
    degradacion: Regla | None = None
    latencia: GradoLatencia = GradoLatencia.PREVISTA  # (7) activable / prevista. Consumidor: Manager
    dependencias: tuple[str, ...] = ()  # (8) otras CAPACIDADES requeridas; nunca servicios (INV-6)
    # --- DOCUMENTALES: auditables por humanos; ningun componente deriva comportamiento de ellos ---
    comportamiento_degradado: str = ""  # (4) descripcion del modo reducido; no gobierna materializacion
    garantias_seguridad: tuple[str, ...] = ()  # (9) que debe preservarse; lo hace cumplir el gate de permisos
    # --- PROVISIONAL: sin consumidor. No gobierna nada (ADR-0021 v1.1.0 §1) ---
    # Se conserva unicamente por el coste asimetrico de reintroducirlo (obligaria a redeclarar todas las
    # capacidades), a la espera de evidencia arquitectonica. No se le atribuye funcion actual ni futura.
    autonomia_maxima: NivelAutonomia = NivelAutonomia.OBSERVACION  # (10)


class Estado(Enum):
    """Estado de una capacidad en el plan."""

    ACTIVA = "activa"
    DEGRADADA = "degradada"
    LATENTE = "latente"


@dataclass(frozen=True)
class Decision:
    """Estado de UNA capacidad en el plan, con su motivo (criterio de exito del CEO)."""

    nombre: str
    estado: Estado
    autonomia_efectiva: NivelAutonomia
    motivo: str


@dataclass(frozen=True)
class PlanActivacion:
    """Resultado determinista del Manager: el estado y el motivo de cada capacidad."""

    decisiones: tuple[Decision, ...]

    def _nombres(self, estado: Estado) -> tuple[str, ...]:
        return tuple(d.nombre for d in self.decisiones if d.estado == estado)

    @property
    def activas(self) -> tuple[str, ...]:
        return self._nombres(Estado.ACTIVA)

    @property
    def degradadas(self) -> tuple[str, ...]:
        return self._nombres(Estado.DEGRADADA)

    @property
    def latentes(self) -> tuple[str, ...]:
        return self._nombres(Estado.LATENTE)

    def decision(self, nombre: str) -> Decision | None:
        return next((d for d in self.decisiones if d.nombre == nombre), None)

    def motivo(self, nombre: str) -> str:
        d = self.decision(nombre)
        return d.motivo if d is not None else ""


class DetectorPerfil(Protocol):
    """Produce el `PerfilHardware` (specs + pruebas reales, D44).

    Aisla TODA la inteligencia de deteccion. Su implementacion real es **latente-prevista** (requiere
    hardware): C1 no la construye. El Manager solo consume su resultado.
    """

    def detectar(self) -> PerfilHardware: ...
