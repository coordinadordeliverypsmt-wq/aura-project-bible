"""Arnes de mutacion permanente de AURA.

Por que existe: un arnes ad-hoc anterior declaro "7 mutantes sobreviven" en produccion y la
afirmacion era falsa. Aquel arnes parseaba el TEXTO de salida de pytest para decidir si una
prueba paso o fallo, en vez de mirar el codigo de retorno del proceso. Un arnes que miente sobre
la cobertura de sus garantias es peor que no tener arnes: genera una falsa sensacion de seguridad.

Este modulo existe para que eso no vuelva a pasar. Reglas de diseno que no son negociables:

  1. La base debe estar en verde ANTES de mutar nada. Si no lo esta, no se informa de ningun
     mutante (informar "sobrevive"/"detectado" sobre una base rota es indistinguible de mentir).
  2. La decision de "paso" o "fallo" es SIEMPRE el returncode del subprocess de pytest. El texto
     de salida solo se usa para *informar* que pruebas fallaron, nunca para decidir el estado.
  3. El contenido original de cada fichero mutado se restaura siempre (try/finally), incluso si
     el subprocess lanza una excepcion, y se verifica byte a byte tras restaurar.
  4. Si el patron `buscar` no aparece en el fichero, el mutante no se pudo aplicar: NO_APLICADO.
     Nunca "detectado" (eso reportaria una garantia como probada cuando en realidad la garantia
     nunca se llego a mutar).

Formato de declaracion (mutaciones/*.toml), ver ejemplos en la carpeta `mutaciones/`:

    incremento = "descripcion del incremento"
    pruebas = ["tests/unit/test_x.py", "tests/integration/test_y.py"]

    [[mutante]]
    id = "M1"
    garantia = "frase humana: que garantia degrada este mutante"
    fichero = "aura_skeleton/core/reglas.py"
    buscar = \"\"\"texto exacto a sustituir\"\"\"
    sustituir = \"\"\"texto de reemplazo\"\"\"

`pruebas` es la lista global de pruebas para el incremento; un mutante puede llevar su propia
clave `pruebas` que la sobreescribe (por ejemplo, para acotar la verificacion a una prueba mas
especifica que la garantia de ese mutante concreto).
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Estados posibles de un mutante. Se dejan como constantes de texto (no Enum) porque el contrato
# del arnes los fija como literales exactos ("detectado" / "SOBREVIVE" / "NO_APLICADO") y las
# meta-pruebas comparan contra esas cadenas directamente.
_DETECTADO = "detectado"
_SOBREVIVE = "SOBREVIVE"
_NO_APLICADO = "NO_APLICADO"
# AMBIGUO: la declaracion del mutante no permite concluir nada (patron repetido, mutante que no
# degrada, o pytest que no llego a ejercitar las pruebas). NUNCA se cuenta como exito.
_AMBIGUO = "AMBIGUO"


@dataclass
class ResultadoMutante:
    """Resultado de evaluar un unico mutante."""

    id: str
    garantia: str
    estado: str  # "detectado" | "SOBREVIVE" | "NO_APLICADO" | "AMBIGUO"
    pruebas_que_fallaron: str  # solo informativo; la decision del estado ya se tomo por returncode


@dataclass
class ResultadoMutacion:
    """Resultado de ejecutar el arnes completo sobre un fichero de declaracion."""

    base_verde: bool
    resultados: list[ResultadoMutante]
    detectados: int
    supervivientes: int
    no_aplicados: int
    ambiguos: int

    @property
    def concluyente(self) -> bool:
        """Solo es concluyente si TODO mutante murio. Un ambiguo o un no aplicado invalidan el conjunto."""
        return self.base_verde and self.supervivientes == 0 and self.no_aplicados == 0 and self.ambiguos == 0


def _ejecutar_pytest(pruebas: list[str], raiz: str) -> tuple[int, str]:
    """Ejecuta pytest y devuelve su RETURNCODE crudo. Quien llama interpreta; aqui no se decide nada.

    Se devuelve el codigo entero y no un booleano porque pytest distingue casos que el arnes NO puede
    confundir (auditoria 2026-08-02):

      0 -> todo paso
      1 -> alguna PRUEBA fallo (una asercion se ejercito y no se cumplio)
      2 -> pytest se interrumpio: error de COLECCION (p. ej. el mutante rompio la sintaxis)
      5 -> no se recogio ninguna prueba

    Tratar el 2 como "detectado" seria mentir: significa que el fichero ni siquiera se pudo importar,
    no que una prueba protegiera la garantia. El texto se devuelve solo para informar.
    """
    proceso = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--color=no", *pruebas],
        cwd=raiz,
        capture_output=True,
        text=True,
    )
    return proceso.returncode, proceso.stdout + proceso.stderr


def _extraer_pruebas_que_fallaron(salida: str) -> str:
    """Extrae del texto de pytest que pruebas fallaron, solo para el informe humano.

    Esto NO participa en la decision de estado (esa ya se tomo por returncode en
    `_ejecutar_pytest`); es pura conveniencia para que el informe diga algo mas util que "fallo".
    """
    lineas_relevantes = [linea for linea in salida.splitlines() if linea.startswith(("FAILED ", "ERROR "))]
    if lineas_relevantes:
        return "\n".join(lineas_relevantes)
    return salida.strip()


def _evaluar_mutante(mutante: dict[str, Any], pruebas: list[str], raiz: str) -> ResultadoMutante:
    """Aplica un mutante, ejecuta sus pruebas y restaura el fichero pase lo que pase."""
    id_mutante = str(mutante["id"])
    garantia = str(mutante.get("garantia", ""))
    ruta_fichero = Path(raiz) / str(mutante["fichero"])
    buscar = str(mutante["buscar"])
    sustituir = str(mutante["sustituir"])

    original_bytes = ruta_fichero.read_bytes()
    contenido = original_bytes.decode("utf-8")

    apariciones = contenido.count(buscar)
    if apariciones == 0:
        # Patron ausente: el mutante nunca llego a aplicarse. Jamas "detectado" -- eso mentiria
        # sobre haber probado una garantia que en realidad no se toco.
        return ResultadoMutante(id=id_mutante, garantia=garantia, estado=_NO_APLICADO, pruebas_que_fallaron="")
    if apariciones > 1:
        # AMBIGUO (auditoria 2026-08-02): con el patron repetido se mutaria la PRIMERA aparicion, que
        # puede ser un comentario o codigo inocuo, dejando intacto lo que se queria degradar. El
        # resultado seria un "SOBREVIVE" falso: parece un hueco de cobertura y es una declaracion mal
        # escrita. Se rechaza en vez de adivinar cual de las N era la buena.
        return ResultadoMutante(
            id=id_mutante,
            garantia=garantia,
            estado=_AMBIGUO,
            pruebas_que_fallaron=f"el patron aparece {apariciones} veces en {mutante['fichero']}: amplialo hasta que sea unico",
        )
    if buscar == sustituir:
        # Mutante degenerado: no degrada nada, luego su "SOBREVIVE" no informaria de ningun hueco.
        return ResultadoMutante(
            id=id_mutante,
            garantia=garantia,
            estado=_AMBIGUO,
            pruebas_que_fallaron="'buscar' y 'sustituir' son identicos: el mutante no degrada nada",
        )

    contenido_mutado = contenido.replace(buscar, sustituir, 1)
    estado = _SOBREVIVE
    pruebas_que_fallaron = ""
    try:
        ruta_fichero.write_bytes(contenido_mutado.encode("utf-8"))
        codigo, salida = _ejecutar_pytest(pruebas, raiz)
        if codigo == 0:
            # Las pruebas siguen en verde a pesar de la mutacion: la garantia NO esta cubierta.
            estado = _SOBREVIVE
        elif codigo == 1:
            # Una PRUEBA fallo: la garantia SI esta cubierta. Unico caso que merece "detectado".
            estado = _DETECTADO
            pruebas_que_fallaron = _extraer_pruebas_que_fallaron(salida)
        else:
            # pytest no llego a ejercitar las pruebas (error de coleccion, sintaxis rota, nada que
            # recoger). Contarlo como "detectado" daria confianza falsa: no se probo la garantia.
            estado = _AMBIGUO
            pruebas_que_fallaron = f"pytest termino con codigo {codigo} sin ejercitar las pruebas:\n{_extraer_pruebas_que_fallaron(salida)}"
    finally:
        # Restauracion garantizada: corre incluso si _ejecutar_pytest lanza una excepcion o el
        # proceso se interrumpe. La excepcion (si la hubo) sigue propagandose despues de esto.
        ruta_fichero.write_bytes(original_bytes)
        if ruta_fichero.read_bytes() != original_bytes:
            # Verificacion byte a byte: si esto no se cumple, el arnes mismo esta roto y no debe
            # informar nada como si todo estuviera bien.
            raise RuntimeError(f"No se pudo restaurar {ruta_fichero} tras evaluar el mutante {id_mutante}")

    return ResultadoMutante(id=id_mutante, garantia=garantia, estado=estado, pruebas_que_fallaron=pruebas_que_fallaron)


def ejecutar(ruta_toml: str, raiz: str = ".") -> ResultadoMutacion:
    """Ejecuta el arnes de mutacion declarado en `ruta_toml`, con `raiz` como raiz del proyecto.

    Contrato (no cambiar sin cambiar tambien las meta-pruebas en tests/unit/test_arnes_mutacion.py):
      - Si la base (las pruebas declaradas) no esta en verde ANTES de mutar, se devuelve de
        inmediato con `base_verde=False` y `resultados=[]`, sin tocar ni un fichero.
      - Cada mutante se evalua con sus propias pruebas si las declara, o con las globales si no.
    """
    with open(ruta_toml, "rb") as f:
        declaracion: dict[str, Any] = tomllib.load(f)

    pruebas_globales: list[str] = list(declaracion.get("pruebas", []))
    mutantes: list[dict[str, Any]] = list(declaracion.get("mutante", []))

    # Base en verde: se verifica con la UNION de todas las pruebas que se van a usar (las
    # globales mas cualquier override por-mutante), para no dejar colarse una prueba ya rota que
    # luego se confundiria con un mutante "detectado" por razones ajenas a la mutacion.
    pruebas_a_verificar: list[str] = list(pruebas_globales)
    for mutante in mutantes:
        for prueba in mutante.get("pruebas", []):
            if prueba not in pruebas_a_verificar:
                pruebas_a_verificar.append(prueba)

    # `_ejecutar_pytest` devuelve el RETURNCODE, no un booleano: 0 es exito. Compararlo
    # explicitamente evita el error clasico de tratar el 0 como falso.
    codigo_base, _ = _ejecutar_pytest(pruebas_a_verificar, raiz)
    base_verde = codigo_base == 0
    if not base_verde:
        # Nunca informar de mutantes con la base en rojo: es la regla que el arnes historico violo.
        return ResultadoMutacion(
            base_verde=False, resultados=[], detectados=0, supervivientes=0, no_aplicados=0, ambiguos=0
        )

    resultados: list[ResultadoMutante] = []
    for mutante in mutantes:
        pruebas_del_mutante = list(mutante.get("pruebas", pruebas_globales))
        resultados.append(_evaluar_mutante(mutante, pruebas_del_mutante, raiz))

    detectados = sum(1 for r in resultados if r.estado == _DETECTADO)
    supervivientes = sum(1 for r in resultados if r.estado == _SOBREVIVE)
    no_aplicados = sum(1 for r in resultados if r.estado == _NO_APLICADO)
    ambiguos = sum(1 for r in resultados if r.estado == _AMBIGUO)

    return ResultadoMutacion(
        base_verde=True,
        resultados=resultados,
        detectados=detectados,
        supervivientes=supervivientes,
        no_aplicados=no_aplicados,
        ambiguos=ambiguos,
    )


def _formatear_informe(resultado: ResultadoMutacion, ruta_toml: str) -> str:
    """Informe legible en texto plano. No decide nada -- el returncode de main() ya se decidio."""
    lineas = [f"Arnes de mutacion: {ruta_toml}"]

    if not resultado.base_verde:
        lineas.append("BASE EN ROJO: las pruebas declaradas no pasan antes de mutar nada.")
        lineas.append("No se evaluo ningun mutante (una base en rojo invalida cualquier resultado).")
        return "\n".join(lineas)

    lineas.append(f"Base en verde. Mutantes evaluados: {len(resultado.resultados)}")
    # `.get` con marca por defecto en vez de indexacion directa: un estado sin marca declarada
    # reventaba el informe entero con KeyError y ocultaba TODOS los resultados —incluidos los
    # supervivientes—. Un informe que no se puede leer es peor que uno con una marca fea.
    marcas = {_DETECTADO: "OK", _SOBREVIVE: "!!", _NO_APLICADO: "??", _AMBIGUO: "~~"}
    for r in resultado.resultados:
        lineas.append(f"  [{marcas.get(r.estado, '??')}] {r.id} ({r.estado}): {r.garantia}")
        if r.estado == _SOBREVIVE:
            lineas.append("        garantia NO verificada por ninguna prueba declarada")
        elif r.estado == _NO_APLICADO:
            lineas.append("        el patron 'buscar' ya no existe en el fichero (declaracion obsoleta)")
        elif r.estado == _AMBIGUO:
            lineas.append("        declaracion ambigua: el patron no identifica un unico punto del codigo")
        elif r.pruebas_que_fallaron:
            for linea_falla in r.pruebas_que_fallaron.splitlines()[:3]:
                lineas.append(f"        {linea_falla}")

    lineas.append("")
    lineas.append(
        f"Total: {resultado.detectados} detectados, {resultado.supervivientes} sobreviven, "
        f"{resultado.no_aplicados} no aplicados, {resultado.ambiguos} ambiguos"
    )
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    """CLI: `python3 -m herramientas.mutar <fichero.toml>`.

    Codigos de salida:
      0 -> base en verde y todos los mutantes fueron detectados.
      1 -> la base no esta en verde (no se evaluo ningun mutante).
      2 -> hay supervivientes y/o mutantes no aplicados.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Uso: python3 -m herramientas.mutar <fichero.toml>", file=sys.stderr)
        return 1

    ruta_toml = args[0]
    # `--raiz` permite ejecutar el arnes sobre un proyecto distinto del directorio actual. Existe
    # sobre todo para que las meta-pruebas puedan ejercitar ESTA funcion contra un proyecto de
    # juguete: sin ella, el contrato de codigos de salida quedaria sin cobertura (auditoria 2026-08-02).
    raiz = args[args.index("--raiz") + 1] if "--raiz" in args and len(args) > args.index("--raiz") + 1 else "."
    resultado = ejecutar(ruta_toml, raiz=raiz)
    print(_formatear_informe(resultado, ruta_toml))

    if not resultado.base_verde:
        return 1
    # Un unico punto de decision: `concluyente` exige que TODO mutante haya muerto. Si se anadiera un
    # estado nuevo sin contarlo, el conjunto dejaria de ser concluyente en vez de pasar por exito.
    if not resultado.concluyente:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
