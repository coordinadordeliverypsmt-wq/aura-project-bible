"""Ejecutor interno del ESTADO PROPIO — F3 · `DP-D-M-8 §7`.

*«F3 · Ejecutor interno | Contrato `simular`/`aplicar` para estado propio + catálogo con `sujeto` |
El andamiaje del resto.»*

Es el adaptador que permite que las operaciones sobre la información de la persona atraviesen el
**motor único** igual que cualquier otra acción: dry-run, permisos, kill switch, auditoría. Antes no
existía, y por eso `ModeloUsuario` mutaba el almacén directamente — el agujero de `ALERTA-006`.

**La auditoría se emite aquí y no en el llamador** porque aquí es donde se sabe *qué* se pierde:
`§5.1` exige que del audit pueda responderse *«¿qué había antes y qué hay ahora?»*, y para eso hay
que leer las entradas **antes** de tocarlas.
"""

from __future__ import annotations

import time

from .. import observability as obs
from .identidad_memoria import identidad_de
from .modelo_usuario import _TIPOS

#: Operaciones que este ejecutor atiende. Son exactamente las tres que `§4.2` nombra: ni una más.
ACCIONES = (
    "registrar_informacion_usuario",
    "olvidar_informacion_usuario",
    "refutar_informacion_usuario",
)


def _predicado(user_id: str, contiene: str | None, solo_vivas: bool = False):
    """Aislamiento por usuario (P-ARQ-5) y acotado por contenido, igual que la ruta anterior.

    `solo_vivas` conserva un matiz de `refutar` que la migracion estuvo a punto de perder: refutar
    algo YA refutado no tiene efecto, y sin este filtro devolveria `n > 0` la segunda vez. El
    orquestador leeria ese numero como exito y responderia «Entendido, lo corrijo» **sin haber
    corregido nada** — que es exactamente INV-9 y el punto 4 de ALERTA-005.
    """

    def objetivo(i: dict) -> bool:
        return (
            i["user_id"] == user_id
            and i["kind"] in _TIPOS
            and (contiene is None or contiene in i["content"])
            and not (solo_vivas and i.get("provenance", {}).get("refutada"))
        )

    return objetivo


def _predicado_identidad(user_id: str, identidad: str, solo_vigentes: bool = True):
    """Las entradas del MISMO usuario que declaran el MISMO atributo — AMP-AURA etapas 1-2.

    Es la pregunta «¿de que ya sabia algo esto?». `solo_vigentes` separa los dos usos: para CERRAR la
    version anterior solo interesan las vivas y vigentes; para NUMERAR la nueva interesan todas,
    tambien las cerradas y las refutadas, porque si no el contador se reiniciaria al refutar y dos
    entradas distintas compartirian `version` — y entonces `supersedes` dejaria de identificar una.
    """

    def objetivo(i: dict) -> bool:
        if i["user_id"] != user_id or i["kind"] not in _TIPOS:
            return False
        if identidad_de(i["content"]) != identidad:
            return False
        if not solo_vigentes:
            return True
        prov = i.get("provenance", {})
        return prov.get("valid_until") is None and not prov.get("refutada")

    return objetivo


class EjecutorModeloUsuario:
    """Atiende las operaciones sobre información de la persona. Expone `simular` y `execute`."""

    #: Identidad ante el registro de adaptadores (`RegistroAdaptadores.registrar`).
    name = "modelo_usuario"
    capabilities = ACCIONES

    def __init__(self, memoria) -> None:
        self._memoria = memoria

    # El motor resuelve el adaptador por aquí; devolver None para lo ajeno evita que este ejecutor
    # se convierta en un comodín que atienda acciones que no son suyas.
    def para(self, accion: str):
        return self if accion in ACCIONES else None

    def _afectadas(self, args: dict, solo_vivas: bool = False) -> list[dict]:
        pred = _predicado(args.get("user_id", ""), args.get("contiene"), solo_vivas)
        return [i for i in self._memoria._items if pred(i)]

    def _plan_de_vigencia(self, user_id: str, contenido: str) -> tuple[str | None, int, int]:
        """Lectura PURA del historial: (identidad, ultima version escrita, cuantas vigentes hay).

        **No muta.** La usan las dos caras de la misma operacion: el dry-run, para poder decir la
        verdad completa sobre lo que va a pasar, y la ejecucion, para hacerlo. Si cada una lo calculase
        por su cuenta, el plan aprobado y el efecto real podrian separarse sin que nadie lo notase.
        """
        identidad = identidad_de(contenido)
        if identidad is None:
            return None, 0, 0
        # TODAS, para numerar. El maximo se toma sobre lo ya escrito; una entrada heredada que no
        # tiene `version` cuenta como la 1: existia y era vigente, aunque nadie la numerase.
        previas = [i for i in self._memoria._items if _predicado_identidad(user_id, identidad, False)(i)]
        ultima = max((int(i.get("provenance", {}).get("version", 1)) for i in previas), default=0)
        vigentes = sum(1 for i in previas if _predicado_identidad(user_id, identidad)(i))
        return identidad, ultima, vigentes

    def _vigencia(self, user_id: str, contenido: str, ts: float, trace_id: str) -> dict:
        """Los cuatro campos autorizados para la entrada que se va a escribir, cerrando la anterior.

        *Etapas 1-2 de AMP-AURA · `D-AMP-1 = B` (CEO, 2026-09-10).* Autorizados **exactamente**
        `version`, `supersedes`, `valid_from` y `valid_until`: ni uno mas. «Superseded» NO es un
        quinto campo, es una **lectura derivada** de `valid_until is not None` — un booleano aparte
        podria contradecir a la fecha, y entonces habria que decidir cual manda.

        Esta aqui, y no en `AlmacenSenales`, por dos razones que no son de estilo. La primera es que
        versionar exige **leer** el historial para saber que version toca y cual cerrar, y el almacen
        de senales tiene prohibido leer («no lee, no infiere, no decide»). La segunda es G-1: el
        cierre de la version anterior MUTA el almacen, y toda mutacion pasa por el motor unico. Aqui
        ya estamos dentro de el, con dry-run, permisos, parada y auditoria.

        **El LLM no participa.** La identidad sale de la gramatica de la propia frase del usuario
        (`identidad_memoria`), de forma deterministica y sin una sola llamada al modelo: ADR-0014.
        """
        identidad, ultima, vigentes = self._plan_de_vigencia(user_id, contenido)
        if identidad is None:
            # No toda entrada declara un atributo —«me gusta el jazz», un patron observado—. Esas no
            # se versionan: inventarles una version seria declarar un historial que nadie pidio.
            return {}

        # Se cierra ANTES de escribir: asi el predicado no puede alcanzar a la entrada nueva, que
        # todavia no existe. Cerrar despues exigiria excluirla, y ese filtro es el tipo de detalle
        # que se rompe en silencio.
        if vigentes:
            cerradas = self._memoria.marcar(_predicado_identidad(user_id, identidad), {"valid_until": ts})
            obs.log(
                "MODELO",
                "ejecutor-modelo",
                f"'{identidad}' v{ultima}: {cerradas} entrada(s) superseded, vigencia cerrada en {ts}",
                trace_id,
                audit=True,
            )

        return {
            "version": ultima + 1,
            # La version anterior, no un identificador nuevo: (identidad, version) ya señala una
            # entrada sola, y asi no hay que inventar un campo `id` fuera de la autorizacion.
            "supersedes": ultima or None,
            "valid_from": ts,
            "valid_until": None,  # explicito: «vigente» se afirma, no se deduce de una ausencia.
        }

    async def simular(self, accion: str, args: dict, trace_id: str) -> dict:
        """Dry-run: qué pasaría. **No muta.** Un plan no viable detiene la ejecución antes de empezar."""
        if accion == "registrar_informacion_usuario":
            contenido = args.get("contenido")
            if not contenido:
                return {"viable": False, "efecto": "sin contenido"}
            # El dry-run tiene que nombrar TODO lo que va a pasar. Decir solo «registraria una entrada»
            # cuando la ejecucion ademas cierra la vigencia de la version anterior es el patron
            # «declarado != real» que este proyecto ya ha pagado ocho veces — en pequeño, pero es el
            # mismo: quien aprueba el plan no veria la mitad del efecto.
            identidad, ultima, vigentes = self._plan_de_vigencia(args.get("user_id", ""), contenido)
            if identidad is None:
                return {"viable": True, "efecto": "registraria una entrada"}
            efecto = f"registraria '{identidad}' como v{ultima + 1}"
            if vigentes:
                efecto += f", cerrando la vigencia de {vigentes} anterior(es)"
            return {"viable": True, "efecto": efecto}
        afectadas = self._afectadas(args, solo_vivas=(accion == "refutar_informacion_usuario"))
        verbo = "olvidaria" if accion == "olvidar_informacion_usuario" else "marcaria como refutadas"
        return {"viable": True, "efecto": f"{verbo} {len(afectadas)} entrada(s)"}

    async def execute(self, accion: str, args: dict, trace_id: str, event_id: str) -> dict:
        user_id = args.get("user_id", "")
        if accion == "registrar_informacion_usuario":
            # `tipo` lo aporta la captura de señales (semantica | procedimental, 4.1 §1). Sin el,
            # una señal procedimental se guardaria como semantica y la taxonomia se perderia.
            contenido = args["contenido"]
            procedencia = dict(args.get("procedencia", {}))
            # El `ts` de la senal, no `time.time()`: `valid_from` debe coincidir con el momento que la
            # procedencia ya declara. Dos relojes para el mismo hecho es un hecho con dos historias.
            ts = procedencia.get("ts") or time.time()
            procedencia.update(self._vigencia(user_id, contenido, ts, trace_id))
            await self._memoria.write(user_id, args.get("tipo", "semantica"), contenido, procedencia)
            obs.log(
                "MODELO",
                "ejecutor-modelo",
                f"registrada sobre '{user_id}': {contenido!r} v{procedencia.get('version', '-')}",
                trace_id,
                audit=True,
            )
            return {"n": 1}

        # §5.1 — se leen ANTES de tocar nada: despues de mutar, lo perdido ya no se puede nombrar.
        afectadas = [i["content"] for i in self._afectadas(
            args, solo_vivas=(accion == "refutar_informacion_usuario"))]
        if accion == "olvidar_informacion_usuario":
            n = self._memoria.olvidar(_predicado(user_id, args.get("contiene")))
            obs.log("MODELO", "ejecutor-modelo",
                    f"olvidadas {n} entrada(s) sobre '{user_id}': {afectadas!r}", trace_id, audit=True)
            return {"n": n}

        n = self._memoria.marcar(
            _predicado(user_id, args.get("contiene"), solo_vivas=True),
            {"refutada": True, "refutada_ts": time.time()},
        )
        obs.log("MODELO", "ejecutor-modelo",
                f"refutadas {n} entrada(s) sobre '{user_id}': {afectadas!r}", trace_id, audit=True)
        return {"n": n}
