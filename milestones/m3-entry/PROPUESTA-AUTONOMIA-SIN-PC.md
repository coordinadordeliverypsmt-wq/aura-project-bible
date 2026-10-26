# PROPUESTA (para decisión del CEO) — Que AURA siga funcionando con el PC de desarrollo apagado

**Fecha:** 2026-10-22 · **Tipo:** propuesta técnica. NO migra nada ni cambia infraestructura.
Evidencia: `[EJEC]` medido hoy · `[LECT]` leído en el repo · `[HIPO]` sin verificar en esta casa.

## 1. Estado actual

- `[EJEC]` En HC-1 (el PC: x86_64, 2 núcleos, 3,7 GB de RAM, disco al 89 %) corren como servicios de usuario:
  - `aura-hogar-ha` (Home Assistant 2026.2.3; solo escucha en 127.0.0.1);
  - `aura-nats` (bus);
  - `aura-receptor-nodos` (latidos de NODO-01);
  - además, `ollama serve` (modelo local).
- `[EJEC]` La memoria residente medida (7-18 MB por proceso) **no sirve para dimensionar**: el equipo usa swap y esa
  cifra infravalora el consumo real.
- `[LECT]` NODO-01 (`DP-VOZ-ACCION.md` §1): Atom N450, 1 núcleo, 986 MB de RAM, **32 bits**. Amplía presencia y
  periféricos; no alcanza para Home Assistant ni para el modelo.
- **Consecuencia:** con HC-1 apagado no hay hogar (HA), ni bus, ni receptor, ni conversación. Hoy no existe ninguna
  independencia del PC, y no se declara.

## 2. Qué tiene que quedar encendido para cada función

| Función | Componentes | Nube | Sin Internet |
|---|---|---|---|
| Hablar con AURA desde un teléfono (texto o notificación) | HA + su app oficial en el teléfono, o un canal propio de AURA | no (HA local) | sí, dentro de la LAN |
| Estado e inventario de dispositivos | AURA (núcleo) + HA + descubrimiento | no | sí |
| Órdenes con efecto verificado (TV) | AURA + Motor Único + HA | no | sí |
| Voz local (STT/TTS) | Whisper + Piper (pesados: STT ≈ 5,5 s por turno en HC-1) | no | sí |
| Modelo conversacional | Ollama | no | sí |
| Avisos de nodos | NATS + receptor | no | sí |
| Juego en curso de la PS5, apps de relojes | PSN / nubes de fabricante | **sí** | no — excluidos por D24 |

## 3. Opciones (la elección es del propietario)

| Opción | Qué es | A favor | En contra |
|---|---|---|---|
| **1 · HC-1 siempre encendido** | Sin hardware nuevo: HC-1 pasa a ser el servidor de la casa | Coste cero; ya funciona y está medido | No resuelve «sin el PC»; consumo y ruido permanentes; el desarrollo y la casa comparten máquina |
| **2 · Un nodo de 64 bits siempre encendido** para HA + NATS + receptor + núcleo de AURA en modo texto | Un mini-PC o placa de 64 bits con ≥ 4 GB `[HIPO]` | Separa la casa del desarrollo; local; bajo consumo | Compra; migración de HA con backup y restauración; la voz pesada se queda en HC-1 hasta medirla en el nodo |
| **3 · Como 2, pero solo HA + NATS en el nodo** | AURA sigue en HC-1 | Migración mínima; HA y la casa no dependen del PC | La conversación sigue dependiendo del PC |

**Recomendación del ejecutor: la opción 2, por fases.** Primero HA + NATS + receptor; después el núcleo de AURA en modo
texto; la voz, solo tras medirla en el nodo. Cada fase se da por cumplida solo con una prueba real: apagar HC-1, actuar
sobre la TV desde el teléfono y comprobar el efecto.

## 4. Lo que NO se hace sin decisión

Comprar o elegir el hardware, migrar Home Assistant, abrir puertos, exponer servicios fuera de la LAN o usar servicios en
la nube.
