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
import uuid

from .. import observability as obs
from . import resultado_accion
from .identidad_memoria import identidad_de
from .modelo_usuario import _TIPOS
from .senales import ClaseSenal

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


#: Valor de `ambito` con el que `olvidar_informacion_usuario` apunta a los REGISTROS DE ACCIONES (T19) en lugar de al
#: modelo del usuario. Es una ampliacion de la operacion que ya existe, no una operacion nueva: mismo catalogo,
#: mismo sujeto, mismos controles del motor.
AMBITO_ACCIONES = "acciones"


def _predicado_acciones(user_id: str):
    """Los `resultado_accion` de ESE usuario. Aislamiento por usuario (P-ARQ-5), como `_predicado`."""

    def objetivo(i: dict) -> bool:
        return i["user_id"] == user_id and i["kind"] == resultado_accion.KIND

    return objetivo


def _predicado_entrada(user_id: str, entrada: dict, solo_vivas: bool = False):
    """UNA entrada concreta, localizada por su contenido Y su sello `ts` — DR-2 (CEO, 2026-09-15).

    `_predicado` localiza por TEXTO (`contiene in content`), y eso destruia lo que nadie habia pedido:
    medido, con «mi ciudad favorita es Valencia» declarada como v1 y otra vez como v3, «olvida eso» se
    llevaba las DOS, historial incluido. El `ts` lo pone el registro de cada entrada y no se repite, asi
    que (contenido, ts) señala una sola: la que el Core presento y el usuario eligio.

    **No toca el `_predicado` de texto**: sigue siendo el camino de `borrar(user_id)` para olvidarlo TODO,
    que no nombra ninguna entrada.
    """
    contenido = entrada.get("contenido")
    ts = entrada.get("ts")

    def objetivo(i: dict) -> bool:
        prov = i.get("provenance", {})
        return (
            i["user_id"] == user_id
            and i["kind"] in _TIPOS
            and i["content"] == contenido
            and prov.get("ts") == ts
            and not (solo_vivas and prov.get("refutada"))
        )

    return objetivo


def _predicado_ecos(user_id: str, trace_ids: set[str]):
    """Los ecos episodicos («usuario dijo: ...») de los MISMOS turnos que las entradas afectadas — DR-2.

    El enlace es el `trace_id` del turno, que el eco y el hecho comparten desde que se escriben: no se
    busca por texto, porque dos declaraciones identicas en turnos distintos son dos ecos distintos, y
    retirar uno no puede arrastrar al otro. Ya retirados no cuentan: retirar dos veces no es retirar.
    """

    def objetivo(i: dict) -> bool:
        prov = i.get("provenance", {})
        return (
            i["user_id"] == user_id
            and i["kind"] == "episodica"
            and prov.get("trace_id") in trace_ids
            and not prov.get("retirada")
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

    def _seleccion(self, args: dict, solo_vivas: bool = False):
        """El predicado que decide QUE se toca. Con `entrada` localiza UNA; sin ella, por texto (el camino
        de «olvidarlo todo», `contiene=None`). DR-2: cuando existe una entrada concreta, nunca por texto."""
        user_id = args.get("user_id", "")
        if args.get("ambito") == AMBITO_ACCIONES:
            return _predicado_acciones(user_id)
        if args.get("entrada"):
            return _predicado_entrada(user_id, args["entrada"], solo_vivas)
        return _predicado(user_id, args.get("contiene"), solo_vivas)

    def _afectadas(self, args: dict, solo_vivas: bool = False) -> list[dict]:
        pred = self._seleccion(args, solo_vivas)
        return [i for i in self._memoria._items if pred(i)]

    def _ecos(self, args: dict, afectadas: list[dict]) -> list[dict]:
        """Ecos de los turnos de las entradas afectadas. Solo cuando se nombro una entrada concreta."""
        if not args.get("entrada"):
            return []
        trazas = {i.get("provenance", {}).get("trace_id") for i in afectadas} - {None}
        if not trazas:
            return []
        pred = _predicado_ecos(args.get("user_id", ""), trazas)
        return [i for i in self._memoria._items if pred(i)]

    def _retirar_ecos(self, args: dict, afectadas: list[dict], motivo: str, trace_id: str) -> int:
        """Retira los ecos de la RECUPERACION NORMAL marcandolos, sin borrarlos — DR-2.

        Marcar y no borrar tiene una razon escrita ya en `ModeloUsuario.borrar`: *«borrar lo que AURA cree
        saber sobre alguien no puede borrarle su propia conversacion»*. El eco es el registro de lo que el
        usuario DIJO, y eso sigue siendo cierto como registro: se conserva para auditoria. Lo que deja de
        hacer es entrar al contexto del modelo como si fuera memoria vigente (`_da_por_cierto`).
        """
        ecos = self._ecos(args, afectadas)
        if not ecos:
            return 0
        trazas = {i.get("provenance", {}).get("trace_id") for i in ecos}
        n = self._memoria.marcar(
            _predicado_ecos(args.get("user_id", ""), trazas),
            {"retirada": True, "retirada_ts": time.time(), "retirada_por": motivo},
        )
        obs.log(
            "MODELO",
            "ejecutor-modelo",
            f"retirados {n} eco(s) de recuperacion por {motivo}: {[i['content'] for i in ecos]!r}",
            trace_id,
            audit=True,
        )
        return n

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

    def _hecho_id(self, user_id: str, contenido: str, procedencia: dict) -> str | None:
        """Identidad OPACA del hecho para el reloj de CM2 (resolucion S3 §2.1), o None si no aplica.

        Solo los hechos declarados TIPADOS (clase HECHO_DECLARADO con atributo reconocido por
        `identidad_de`) entran en la poblacion. El id es `uuid4` —nunca derivado del contenido— y las
        versiones de una misma identidad del mismo usuario lo HEREDAN, incluidas las cerradas y las
        refutadas. Vive en la procedencia, aparte de los cuatro campos de vigencia (D-AMP-1 = B).
        """
        if procedencia.get("clase") != ClaseSenal.HECHO_DECLARADO.value:
            return None
        identidad = identidad_de(contenido)
        if identidad is None:
            return None
        previas = [i for i in self._memoria._items if _predicado_identidad(user_id, identidad, False)(i)]
        con_id = sorted(
            (i for i in previas if i.get("provenance", {}).get("hecho_id")),
            key=lambda i: int(i["provenance"].get("version", 1)),
        )
        return con_id[0]["provenance"]["hecho_id"] if con_id else uuid.uuid4().hex

    @staticmethod
    def _auditar_retirada(entradas: list[dict], causa: str, trace_id: str) -> None:
        """`cm2.hecho_retirado` por cada entrada con `hecho_id` retirada por el usuario. SIN texto."""
        for i in entradas:
            hecho_id = i.get("provenance", {}).get("hecho_id")
            if hecho_id:
                obs.log(
                    "CM2",
                    "reloj-cm2",
                    "hecho retirado",
                    trace_id,
                    audit=True,
                    evento="cm2.hecho_retirado",
                    hecho_id=hecho_id,
                    causa=causa,
                )

    def _olvidar_acciones(self, user_id: str, trace_id: str) -> dict:
        """T19: lapida de los `resultado_accion` del usuario. Se CUENTAN en el audit, no se nombran: el rastro del
        olvido no puede ser una copia de lo olvidado (la entidad y la hora son un patron de vida)."""
        n = self._memoria.olvidar(_predicado_acciones(user_id))
        obs.log(
            "MODELO",
            "ejecutor-modelo",
            f"olvidados {n} registro(s) de acciones sobre '{user_id}'",
            trace_id,
            audit=True,
            evento="resultado.olvidado",
            cantidad=n,
        )
        return {"n": n}

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
        efecto = f"{verbo} {len(afectadas)} entrada(s)"
        # El dry-run nombra TODO el efecto: si ademas se retiran ecos, quien aprueba tiene que verlo.
        ecos = self._ecos(args, afectadas)
        if ecos:
            efecto += f" y retiraria {len(ecos)} eco(s) de la recuperacion"
        return {"viable": True, "efecto": efecto}

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
            hecho_id = self._hecho_id(user_id, contenido, procedencia)
            procedencia.update(self._vigencia(user_id, contenido, ts, trace_id))
            if hecho_id:
                procedencia["hecho_id"] = hecho_id
            await self._memoria.write(user_id, args.get("tipo", "semantica"), contenido, procedencia)
            obs.log(
                "MODELO",
                "ejecutor-modelo",
                f"registrada sobre '{user_id}': {contenido!r} v{procedencia.get('version', '-')}",
                trace_id,
                audit=True,
            )
            if hecho_id:
                obs.log(
                    "CM2",
                    "reloj-cm2",
                    "hecho registrado",
                    trace_id,
                    audit=True,
                    evento="cm2.hecho_registrado",
                    hecho_id=hecho_id,
                    version=procedencia.get("version"),
                    valid_from=procedencia.get("valid_from"),
                )
            return {"n": 1}

        if accion == "olvidar_informacion_usuario" and args.get("ambito") == AMBITO_ACCIONES:
            return self._olvidar_acciones(user_id, trace_id)

        # §5.1 — se leen ANTES de tocar nada: despues de mutar, lo perdido ya no se puede nombrar.
        refutar = accion == "refutar_informacion_usuario"
        entradas = self._afectadas(args, solo_vivas=refutar)
        afectadas = [i["content"] for i in entradas]
        if accion == "olvidar_informacion_usuario":
            # Los ecos se retiran ANTES de olvidar: despues, las entradas ya no estan y su `trace_id`
            # —el unico enlace con el eco— se habria perdido con ellas.
            self._retirar_ecos(args, entradas, "olvido", trace_id)
            n = self._memoria.olvidar(self._seleccion(args))
            obs.log(
                "MODELO",
                "ejecutor-modelo",
                f"olvidadas {n} entrada(s) sobre '{user_id}': {afectadas!r}",
                trace_id,
                audit=True,
            )
            self._auditar_retirada(entradas, "olvido", trace_id)
            return {"n": n}

        n = self._memoria.marcar(
            self._seleccion(args, solo_vivas=True),
            {"refutada": True, "refutada_ts": time.time()},
        )
        if n:
            self._retirar_ecos(args, entradas, "refutacion", trace_id)
            self._auditar_retirada(entradas, "refutacion", trace_id)
        obs.log(
            "MODELO",
            "ejecutor-modelo",
            f"refutadas {n} entrada(s) sobre '{user_id}': {afectadas!r}",
            trace_id,
            audit=True,
        )
        return {"n": n}
