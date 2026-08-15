"""Ejecutor Auditor: revision independiente, determinista y sin LLM.

POR QUE EXISTE. El protocolo del proyecto exige que quien implementa no audite su propio trabajo, y
hoy ese papel lo ocupa la asistencia externa. Esta sesion demostro que es fragil: la auditoria
independiente cayo por limite de cuenta y el implementador reviso lo suyo, incumpliendo el estandar.
Este ejecutor no sustituye a un auditor con criterio —no razona—, pero cubre la parte MECANICA de la
revision, que es justo la que se degrada cuando falta capacidad externa.

EL VACIO REAL QUE CIERRA: **los mutantes que dejan de aplicarse**. En esta sesion, CUATRO veces un
reformateo automatico invalido el patron `buscar` de un mutante. El arnes lo reporta `NO_APLICADO` y
NO lo cuenta como superviviente, asi que un informe puede decir "todos detectados" mientras una
garantia se quedo sin red. Es una forma silenciosa del patron declarado != real: la proteccion figura
declarada en el TOML y no protege nada.

Reutiliza el patron del Ejecutor QA sin cambios: mismo contrato `Adapter`, misma gobernanza por el
Motor Unico, capacidades nombradas por el RESULTADO que ofrecen. Y es de LECTURA: no modifica nada.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from .. import observability as obs


class EjecutorAuditor:
    """Adaptador de dominio con capacidades de revision independiente."""

    name = "auditor"
    capabilities = ["auditar_garantias"]

    def __init__(self, raiz: str) -> None:
        self._raiz = Path(raiz)

    async def execute(self, command: str, args: dict, trace_id: str, event_id: str) -> dict:
        if command != "auditar_garantias":
            raise ValueError(f"capacidad no ofrecida por el ejecutor Auditor: {command!r}")
        return auditar_garantias(str(self._raiz), trace_id)


def auditar_garantias(raiz: str, trace_id: str = "-") -> dict:
    """Comprueba que cada mutante declarado SIGUE aplicandose a su fichero.

    Tres formas de que una garantia declarada no proteja nada, todas detectables sin ejecutar nada:

      AUSENTE   el patron ya no aparece: el codigo cambio y el mutante quedo huerfano.
      AMBIGUO   aparece mas de una vez: el arnes mutaria la primera aparicion, que puede ser un
                comentario, dejando intacto lo que se queria degradar.
      DEGENERADO  `buscar` == `sustituir`: no degrada nada, luego su "detectado" no informa.
    """
    base = Path(raiz)
    rotos: list[dict] = []
    total = 0

    for toml in sorted((base / "mutaciones").glob("*.toml")):
        datos = tomllib.loads(toml.read_text(encoding="utf-8"))
        for m in datos.get("mutante", []):
            total += 1
            fichero = base / str(m.get("fichero", ""))
            buscar, sustituir = str(m.get("buscar", "")), str(m.get("sustituir", ""))
            ident = f"{toml.name}:{m.get('id')}"

            # CONTEXTO ACCIONABLE (acta del CEO, 2026-08-15). Estos tres datos ya estaban aqui, en
            # `m`, y se descartaban: solo salia el identificador y un detalle en prosa. Publicarlos
            # es lo que permite que la correccion derivada llegue al ejecutor con algo que usar en
            # vez de morir en el dry-run por `args={}`. No se infiere nada: es lo que el TOML declara.
            # EL ARTEFACTO A CORREGIR ES EL TOML, no el fichero objetivo (defecto detectado en
            # auditoria, 2026-08-15). Cuando una garantia deja de aplicar, el codigo objetivo suele
            # estar BIEN: lo que quedo obsoleto es el patron DECLARADO en `mutaciones/*.toml`.
            # Publicar el objetivo enviaba al ejecutor a tocar el fichero equivocado.
            #
            # `sustituir` del mutante NO se publica como correccion: es el texto de la mutacion, no
            # el patron nuevo que hay que escribir en el TOML. Ese hay que DECIDIRLO -- y decidirlo
            # es razonar, no transportar. Se deja ausente a proposito (INV-9).
            accionable = {
                "fichero": str(toml.relative_to(base)),
                "buscar": buscar,
                "objetivo": str(m.get("fichero", "")),
            }

            # SE DECIDE QUE PASA, Y LUEGO SE PUBLICA UNA SOLA VEZ. Las cuatro ramas anexaban su
            # propio diccionario con `**accionable` repetido, y solo una tenia prueba: la quinta
            # auditoria encontro las otras tres como mutantes vivos -- quitar el contexto de la rama
            # AMBIGUO, o de DEGENERADO, o de la de fichero ausente, no rompia nada. Es la misma
            # familia que ya costo tres rechazos: una regla escrita N veces diverge en N-1 sitios.
            problema, detalle = "", ""
            if not fichero.is_file():
                problema, detalle = "AUSENTE", f"no existe {m.get('fichero')}"
            else:
                apariciones = fichero.read_text(encoding="utf-8").count(buscar)
                if apariciones == 0:
                    problema, detalle = "AUSENTE", "el patron ya no aparece"
                elif apariciones > 1:
                    problema, detalle = "AMBIGUO", f"aparece {apariciones} veces"
                elif buscar == sustituir:
                    problema, detalle = "DEGENERADO", "no degrada nada"
            if problema:
                rotos.append({"mutante": ident, "problema": problema, "detalle": detalle, **accionable})

    ok = not rotos
    obs.log("AUDIT", "ejecutor-auditor", f"garantias: {total - len(rotos)}/{total} vigentes", trace_id, audit=True)
    return {
        "capacidad": "auditar_garantias",
        "ok": ok,
        "declaradas": total,
        "vigentes": total - len(rotos),
        "rotas": rotos,
        "resumen": "todas las garantias siguen aplicando"
        if ok
        else f"{len(rotos)} garantia(s) declaradas que NO protegen nada: "
        + ", ".join(f"{r['mutante']} ({r['problema']})" for r in rotos[:4]),
    }
