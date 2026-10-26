from aura_skeleton.core import reloj_cm2 as r
from aura_skeleton.core.identidad_memoria import identidad_de
C = ["mi color favorito es el azul", "Mi perro es Toby", "mi trabajo es de ingeniero", "Mi ciudad es Bogotá",
     "mi comida favorita es la pizza", "mi equipo es el Nacional", "mi esposa es Ana", "Mi edad es 40",
     "yo me llamo Juan Pablo", "me llamo Ana, y tú", "mi cumpleaños es el 10 de mayo", "mi coche es rojo y viejo",
     "Mi película favorita es El Padrino", "mi hermano es médico", "mi color favorito es el verde.", "MI CIUDAD ES CALI",
     "mi número es 3001234567", "mi deporte favorito son los bolos", "mi apellido es Muñoz", "Me llamo Mauricio",
     "mi correo es a@b.co", "mi segundo apellido es Pérez", "mi mamá es Luz", "mi café es sin azúcar",
     "mi pais es Colombia", "Mi país es Colombia", "mi niña es Sofía", "mi música favorita es el jazz",
     "creo que mi color favorito es el rojo", "hoy mi ánimo es bueno"]
for c in C:
    if identidad_de(c) is None:
        print("FUERA", repr(c)); continue
    e = [{"user_id": "u", "hecho_id": "h", "contenido": c, "clase": "hecho_declarado", "version": 1, "refutada": False, "valid_until": None}]
    ev = r.evaluar_sonda("h", e)
    print(ev["resultado"].ljust(13), repr(c), "->", r._pregunta_tipo(c))
