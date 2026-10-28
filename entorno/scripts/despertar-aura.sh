#!/usr/bin/env bash
# Despierta el ciclo de AURA UNA VEZ y termina.
#
# Esto NO es un demonio: el §23 del DP aprobado los prohibe -«Ningun daemon ni watcher permanente.
# El Orchestrator se invoca y termina»-. Cada invocacion hace una vuelta acotada y sale.
#
# Y NO decide nada: no mira la cola, no crea tareas, no tiene autoridad sobre el repositorio.
# Quien decide que trabajo se puede hacer es AURA, con su acta y su politica. Esto solo la llama.
#
#   ./despertar-aura.sh                  # despierta con el tope por defecto
#   ./despertar-aura.sh --max-tareas 5   # despierta con otro tope (acotado a 10)
#   ./despertar-aura.sh --instrucciones  # imprime como programarlo, sin programar nada
#
# Codigos de salida (los de AURA, sin reinterpretar):
#   0  trabajo hecho, o cola agotada -- las dos son terminaciones correctas
#   2  se detuvo por algo que alguien tiene que mirar, o no se pudo despertar
#   3  el arranque estaba roto
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANO="$(cd "$AQUI/../control-plane" && pwd)"

if [[ "${1:-}" == "--instrucciones" ]]; then
  cat <<AYUDA
Para que AURA se despierte sola cada 30 minutos, anade esta linea a tu crontab
(\`crontab -e\`). La ejecutas tu: programar trabajo en tu maquina es una decision
de operacion, no de codigo, y dejarla instalada seria un residuo.

  */30 * * * * $AQUI/despertar-aura.sh --max-tareas 3 >> /tmp/aura-despertar.log 2>&1

Para quitarla, borra la linea. Para parar a AURA sin tocar el cron, crea el
fichero de parada -es un mecanismo fuera de banda, no hace falta que AURA colabore-:

  touch $PLANO/PARADA      # AURA no volvera a trabajar aunque la despierten
  rm    $PLANO/PARADA      # y vuelve

Comprobar que ve sin tocar nada:

  cd $PLANO && python3 aura.py diagnosticar
AYUDA
  exit 0
fi

cd "$PLANO"
exec python3 despertador.py "$@"
