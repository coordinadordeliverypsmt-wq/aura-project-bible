---
id: IE-033
titulo: yujinrobot/korus — software ROS1 del manipulador móvil Korus de Yujin Robot
fuente: https://github.com/yujinrobot/korus
rama-revision: hydro-devel (por defecto) @ f0f82345b0299c7169adf8f8f17ae367d37864f5 (2014-05-18) · indigo-devel @ 1b8dac00252023c7d2a9a6e7aeb4a7b870d9bd7b (2015-05-14) · motion_retargeting @ 8aaacea (2014-05-19)
fecha-revision: 2026-10-26
licencia: SIN fichero LICENSE (API `license` → 404). Por paquete: `<license>Yujin</license>` sin texto (korus, korus_meta, korus_capabilities, korus_object_recognition, korus_smach, korus_stage), BSD (korus_moveit_config, korus_scripts), TODO (korus_rapi, korus_moveit_ikfast_plugin); ficheros ikfast BSD/Apache-2.0
area: robotica (fuera del cronograma)
estado: descartado
cobertura: Lectura remota con `gh api` de branches, commits, license, issues, README, package.xml, CMakeLists.txt, rosinstall, launch y yaml de korus_meta, korus_rapi y korus_smach. Sin clonar, instalar ni ejecutar. Contrastado por un auditor independiente
relacionadas: [IE-032, DP-NODO-01, DP-DELEGACION-NODOS]
---

Base de las citas: `B = https://github.com/yujinrobot/korus/blob/1b8dac00252023c7d2a9a6e7aeb4a7b870d9bd7b`.

Clasificación: **[CÓDIGO]** verificado y contrastado; **[CÓDIGO*]** leído por un solo agente; **[README]** declarado por
los autores; **[INFER]** inferencia.

## Qué se examinó (rutas y símbolos)

- **Actividad:** 211 commits, 205 de ellos en 2013. Último commit el 2015-05-14. 0 tags y 0 releases. No está archivado,
  pero está abandonado de hecho. Issue #2 abierta desde 2018 («couldn't find controller_msg»), sin respuesta
  **[CÓDIGO]**.
- **Plataforma:** ROS1 con catkin. Los `package.xml` son de formato 1 con `buildtool_depend catkin`, y ninguna ruta
  contiene `ament` **[CÓDIGO]**; no se leyeron los `package.xml` de 5 de los 10 paquetes. La distribución objetivo es
  **Hydro** (`korus_meta/resources/rosinstall/korus_hydro.rosinstall#L4`), con un port mínimo a Indigo (commit
  1b8dac0). Usa Python 2 **[CÓDIGO*]**.
- **Dependencias privadas o propietarias** **[CÓDIGO]**:
  - 8 repositorios YCS en `git@bitbucket.org:yujinrobot/...`;
  - `korus_rapi` habla por TCP con un «mainframe» propietario (192.168.2.1, puertos 5001, 5002 y 5015) sin
    autenticación visible;
  - drivers por puerto serie (`goo`, CruizCore, StarGazer, Hokuyo).
- **README** **[README]**: «Most of the software here won't run without Yujin Robot's control software. Few things
  however are useable as is, e.g. view the robot model and run the MoveIt! demo.»

## Patrones relevantes

- **No hay orquestación de nodos de cómputo.** No hay latidos propios ni `diagnostic_aggregator`. El proveedor
  `diagnostics` tiene el `launch_file` vacío, y lo más parecido son timeouts de dispositivo y transporte **[CÓDIGO*]**.
- **Delegación solo dentro de un robot:** ROS actionlib y SMACH (`korus_smach`). No hay verificación independiente de
  resultados entre máquinas **[CÓDIGO*]**.
- **Reutilizables aislados** (y con condiciones): la descripción URDF/xacro con sus mallas y la configuración MoveIt +
  ikfast (BSD/Apache). Solo son útiles para modelar **ese robot concreto** **[INFER]**.

## Límites, riesgos y dependencias

- **No compila desde fuentes públicas:** faltan los repositorios privados y `controller_msgs` (issue #2).
- **Fin de soporte:** Hydro (2015) e Indigo (2019); ROS1 Noetic llegó al final de su soporte en 2025. Python 2 está sin
  soporte desde 2020 **[INFER, por fechas públicas]**.
- **Riesgo legal:** el repositorio no tiene licencia y la mayoría de los paquetes declaran una licencia «Yujin» sin
  texto, así que no hay concesión de redistribución.
- **Seguridad:** un cliente TCP sin autenticación hacia una IP fija de la LAN. No aplica, porque no se ejecuta.

## Comparación con AURA

| AURA | Relación |
|---|---|
| `walking-skeleton/aura_skeleton/adapters/receptor_nodos.py` y `core/nodos.py` (latidos firmados, estado ONLINE/OFFLINE/UNKNOWN y rechazo de la suplantación) | **Sin equivalente en KORUS.** Un proyecto ROS para un robot físico no gestiona nodos de cómputo, y no debe forzarse la analogía |
| `DP-DELEGACION-NODOS.md` (firmas, fijación SPKI, STRIDE) | KORUS no aporta nada a esos bloqueos |
| Planificador, control-plane y verificación | actionlib/SMACH dentro de un robot, sin verificación independiente: no es comparable |
| Cronograma (`milestones/mapa-maestro/AURA_MASTER_DEVELOPMENT_MAP.md:163-178`: S1-S8, R1 → R2 → R3 → R4) | **No existe ninguna línea de robótica física.** Graphify y grep no encuentran ROS ni robótica en el mapa ni en `docs/` |

## Decisión

**`DESCARTAR POR AHORA`.**

| Modalidad | Veredicto (arquitecto-evaluador) | Por qué |
|---|---|---|
| Reutilización inmediata en la infraestructura actual | NO ENCAJA | No compila, no tiene licencia, usa Python 2 y ROS1 sin soporte, y depende de repositorios privados. Choca con D24/ADR-0001, D34, D23 y con «solo capacidades registradas» (`CLAUDE.md` §4) |
| Referencia documental para robótica futura | NO ENCAJA | No hay línea de robótica en el cronograma. Archivarlo como «referencia» insinuaría una línea no aprobada (D23, INV-9). Admisible solo como nota bibliográfica sin estatus de plan, y de bajo valor (ROS1 de 2014) |
| Descarte | **ENCAJA** | Sin deuda y reversible: el repositorio público sigue disponible si algún día el CEO abriera por acta una línea de robótica |

## Validación mínima

Ninguna: descartado. Si el CEO abriera una línea de robótica, el punto de partida debería ser ROS 2 con proyectos
mantenidos y con licencia, no KORUS.

## Licencia y precauciones

**Sin licencia de repositorio. No se debe copiar ni redistribuir nada salvo los ficheros con cabecera BSD o
Apache-2.0.** No se clonó, instaló ni ejecutó nada.
