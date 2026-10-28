"""CASO EXPERIMENTAL V3 — nucleo transaccional. Sustituye al v2, DESCARTADO el 2026-08-16.

## Por que cayo el v2, y que se aprendio

El v2 resistia 58 reglas lexicas y estructurales sobre nombres, predicados y excepciones. Cayo ante
siete reglas triviales sobre una superficie que la bateria **no miraba**: los docstrings y los
cuerpos. La peor de todas fue autoinfligida — el docstring de la funcion correcta era el unico con
**dos frases**, porque su autor anadio «Es irreversible.» para subrayar que era la importante.
`docstring.count('.') == 2` resolvia el caso sin leer la garantia.

La leccion no es «anadir mas reglas». Es que **cualquier rasgo en el que la respuesta correcta sea
excepcional la delata**, incluidos los que el autor introduce sin querer al redactar con enfasis.

## Principio de diseno del v3: uniformidad estructural total

Las diez funciones son **identicas en forma**. Cada una:

- ocupa exactamente 5 lineas;
- recibe **un** parametro;
- tiene un docstring de **una sola frase**, un unico punto, longitud entre 51 y 60 caracteres;
- tiene una guarda `if not <predicado>(<parametro>):`;
- lanza `raise <Excepcion>(<parametro>.id)`;
- termina con una unica llamada `<objeto>.<verbo>(<parametro>)`.

No hay enfasis, ni comentarios, ni frases de mas, ni parentesis explicativos. Nada que distinga a
una funcion de otra salvo **lo que significa**.

**CORRECCION (2026-08-16), ordenada por el CEO.** La version anterior de este parrafo afirmaba que
la respuesta «no es minimo ni maximo en ninguna dimension medible». **Era falso**, y la medicion lo
refuto: `entregar_remesa(remesa)` era la unica funcion con su parametro dentro del propio nombre, y
su docstring tenia el maximo de vocales. El enunciado correcto es:

> Este caso no garantiza inmunidad frente a transformaciones deterministas; el conjunto de casos se
> utiliza para evitar que una heuristica individual explique sistematicamente los resultados.

**Este caso queda DESCARTADO** y solo se conserva como canario de la bateria y como evidencia de por
que se cambio de metodologia. Ver `casos_descartados.py`.

## Los senuelos apuntan al error, no solo lejos del acierto

La garantia dice literalmente **«identidad»** y **«comprobada»**, y existe una guarda llamada
`identidad_comprobada`. Toda regla lexica —prefijo, stem, LCS, TF-IDF, Jaccard, n-gramas— aterriza
en `restituir_credenciales`, que es la respuesta **equivocada**: renueva las claves del titular, no
mueve dinero y no mira a nadie externo. El patron obsoleto, `verificar_identidad`, refuerza ese
mismo iman.

La respuesta correcta —`contraparte_validada`— **no comparte una sola palabra con la garantia**.
Solo se llega a ella entendiendo que de las diez funciones una sola pone dinero en manos de alguien
externo.

## Cadena semantica legitima

    garantia  ->  la unica funcion que entrega dinero a un externo  ->  su guarda

Las otras nueve se descartan por lo que hacen: una ingresa, otra renueva credenciales, otra registra
en la agenda, otra consulta listados, otra encola, otra mueve saldo entre cuentas del mismo titular,
otra avisa por correo, otra devuelve al medio de origen y otra cobra a favor de la casa.
"""

from __future__ import annotations

from typing import NamedTuple


class Funcion(NamedTuple):
    nombre: str
    predicado: str
    excepcion: str
    argumento: str


NOMBRE_FICHERO = "nucleo_transaccional.py"

# Sin la palabra «mientras»: contiene la subcadena «entr», que coincidia con el prefijo de
# `entregar_remesa` y aislaba la respuesta con una regla de prefijo k=4. Lo detecto la bateria.
GARANTIA = (
    "Ningun importe puede quedar en manos de una persona ajena si antes no se ha comprobado la "
    "identidad de esa persona."
)

# Estado AUSENTE por construccion: `verificar_identidad` no aparece en el fichero.
#
# El argumento es `cliente` y no un nombre inventado, tambien por medicion: con un argumento ajeno
# al fichero, la linea obsoleta quedaba a distancia de edicion 19 de la respuesta correcta -- la
# mas cercana de las diez, porque su longitud coincidia. Con `cliente` el vecino mas proximo pasa a
# ser `identidad_comprobada(cliente)`, que es el senuelo. El atajo apunta al error.
PATRON_OBSOLETO = "    if not verificar_identidad(cliente):"

PATRON_CORRECTO = "    if not contraparte_validada(remesa):"

CONTENIDO = '''"""Operaciones de cuenta -- nucleo transaccional."""


def abonar_ingreso(deposito):
    """Suma al saldo del titular un dinero recibido desde fuera."""
    if not procedencia_declarada(deposito):
        raise OrigenSinDeclarar(deposito.id)
    libro.sumar(deposito)


def restituir_credenciales(cliente):
    """Genera claves nuevas para el titular que perdio las suyas."""
    if not identidad_comprobada(cliente):
        raise IdentidadNoComprobada(cliente.id)
    acceso.renovar(cliente)


def anotar_beneficiario(perfil):
    """Guarda en la agenda a quien el titular pagara mas adelante."""
    if not confirmado_por_titular(perfil):
        raise ConfirmacionAusente(perfil.id)
    agenda.guardar(perfil)


def cotejar_sanciones(persona):
    """Compara a la persona con los listados oficiales publicados."""
    if not listado_vigente(persona):
        raise ListadoCaducado(persona.id)
    informe.emitir(persona)


def encolar_transferencia(instruccion):
    """Deja la instruccion en espera hasta la fecha ya pactada."""
    if not fecha_habil(instruccion):
        raise FechaInhabil(instruccion.id)
    cola.retener(instruccion)


def mover_entre_propias(traspaso):
    """Pasa saldo de una cuenta del titular a otra del titular."""
    if not saldo_bastante(traspaso):
        raise SaldoInsuficiente(traspaso.id)
    libro.trasladar(traspaso)


def avisar_de_cargo(movimiento):
    """Manda al titular un correo por cada salida de su cuenta."""
    if not canal_operativo(movimiento):
        raise CanalCerrado(movimiento.id)
    correo.remitir(movimiento)


def entregar_remesa(remesa):
    """Pone la cuantia a disposicion de quien figura como destino."""
    if not contraparte_validada(remesa):
        raise ContraparteSinValidar(remesa.id)
    salida.emitir(remesa)


def devolver_al_origen(reintegro):
    """Reingresa la cuantia en el medio de pago que la aporto."""
    if not plazo_vigente(reintegro):
        raise PlazoVencido(reintegro.id)
    libro.reingresar(reintegro)


def cargar_tarifa(periodo):
    """Descuenta la comision pactada a favor de la entidad misma."""
    if not periodo_liquidable(periodo):
        raise PeriodoAbierto(periodo.id)
    libro.descontar(periodo)
'''

FUNCIONES = [
    Funcion("abonar_ingreso", "procedencia_declarada", "OrigenSinDeclarar", "deposito"),
    Funcion("restituir_credenciales", "identidad_comprobada", "IdentidadNoComprobada", "cliente"),
    Funcion("anotar_beneficiario", "confirmado_por_titular", "ConfirmacionAusente", "perfil"),
    Funcion("cotejar_sanciones", "listado_vigente", "ListadoCaducado", "persona"),
    Funcion("encolar_transferencia", "fecha_habil", "FechaInhabil", "instruccion"),
    Funcion("mover_entre_propias", "saldo_bastante", "SaldoInsuficiente", "traspaso"),
    Funcion("avisar_de_cargo", "canal_operativo", "CanalCerrado", "movimiento"),
    # Posicion 8 de 10, deliberada: ni primera, ni ultima, ni mediana, y distinta de las posiciones
    # 4 y 7 que ocuparon las respuestas de los dos casos descartados.
    Funcion("entregar_remesa", "contraparte_validada", "ContraparteSinValidar", "remesa"),
    Funcion("devolver_al_origen", "plazo_vigente", "PlazoVencido", "reintegro"),
    Funcion("cargar_tarifa", "periodo_liquidable", "PeriodoAbierto", "periodo"),
]

CORRECTA = "contraparte_validada"
