#!/usr/bin/env bash
# Mueve el swap en disco de AURA del disco interno (/swapfile) al USB AURORA_EXT, 2026-10-07 (v2 tras revisión de
# seguridad ECC). Sustituye al «swapoff + rm + swapon» directo que proponía el preflight, que activaba un fichero 755 de
# majo1230 (memoria volcada legible), no tocaba /etc/fstab (no sobrevivía al reinicio y dejaba una entrada a un fichero
# borrado) y borraba /swapfile sin margen de reversión.
#
# Uso:
#   migrar-swap-usb.sh --solo-comprobar         solo lectura
#   migrar-swap-usb.sh --migrar                 mueve el fichero a $USB/.swap (root, 700), permisos 600, lo activa, retira el
#                                                swap interno y deja /etc/fstab persistente. NO borra /swapfile. Pide sudo.
#   migrar-swap-usb.sh --retirar-swap-interno   borra /swapfile. Solo funciona DESPUÉS de un reinicio en el que el swap del
#                                                USB volvió solo desde /etc/fstab.
#   migrar-swap-usb.sh --revertir               deshace sus propias líneas de /etc/fstab y vuelve al swap interno.
#
# Riesgos residuales declarados: (1) la raíz del USB es de majo1230 (el preflight lo exige), así que ese usuario podría
# renombrar .swap y plantar otro fichero; el directorio root 700 impide leer o sustituir el contenido, no el renombrado.
# (2) El swap no va cifrado. (3) `rm` no borra de forma segura las páginas viejas del eMMC.
set -euo pipefail

USB="/media/majo1230/AURORA_EXT"
UUID_USB="c8847222-a540-4060-8908-b3de02ebdb6e"
SWAP_ORIG="$USB/swapfile_aurora"
DIR_SWAP="$USB/.swap"
SWAP_USB="$DIR_SWAP/swapfile_aurora"
SWAP_INT="/swapfile"
FSTAB="/etc/fstab"
FSTAB_BAK="/etc/fstab.antes-swap-usb-20261007"
MARCA="# retirado 2026-10-07 swap en el USB por migrar-swap-usb"   # sin metacaracteres: se usa dentro de una ERE al revertir
TAM_ESPERADO=4294967296
PRIO=10   # por encima del interno (-2) y por debajo de zram (100)
LINEA_USB="$SWAP_USB none swap sw,nofail,pri=$PRIO 0 0"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
TOCANDO_FSTAB=0

paso() { echo; echo "== $*"; }
falla() {
  echo "FALLA: $*" >&2
  [[ $TOCANDO_FSTAB -eq 1 ]] && echo "Para volver atrás: $0 --revertir" >&2
  exit 1
}
activo() { local l; l="$(swapon --show=NAME --noheadings)"; grep -qxF "$1" <<<"$l"; }
fstab_activa() { grep -qE "^[[:space:]]*$1[[:space:]]" "$FSTAB"; }
firma() {  # $1 = fichero; lee la firma de mkswap (con sudo si ya es de root)
  if [[ -r "$1" ]]; then dd if="$1" bs=1 skip=4086 count=10 status=none
  else sudo dd if="$1" bs=1 skip=4086 count=10 status=none; fi
}

ya_migrado() { [[ -d "$DIR_SWAP" ]] && grep -qxF "$LINEA_USB" "$FSTAB"; }
unidad_usb() { systemd-escape -p --suffix=swap "$SWAP_USB"; }
estado_migrado() {  # verificable SIN root: el fichero vive en .swap (root 700) y no se puede leer como usuario
  paso "Estado tras la migración (solo lectura)"
  [[ "$(findmnt -no UUID "$USB" 2>/dev/null)" == "$UUID_USB" ]] || falla "AURORA_EXT ($UUID_USB) no está montado en $USB"
  local tam prio
  tam="$(swapon --show=NAME,SIZE --bytes --noheadings | awk -v f="$SWAP_USB" '$1==f{print $2}')"
  prio="$(swapon --show=NAME,PRIO --noheadings | awk -v f="$SWAP_USB" '$1==f{print $2}')"
  [[ -n "$tam" ]] || falla "$SWAP_USB NO está activo"
  echo "   $SWAP_USB activo: $tam bytes, prioridad $prio"
  # Estado COMPLETO o nada (revisión ECC): un estado a medias no se da por «hecho».
  local incompleto=""
  [[ "$tam" -ge $((TAM_ESPERADO - 65536)) ]] || incompleto+=" tamaño activo $tam;"
  systemctl is-active --quiet "$(unidad_usb)" || incompleto+=" unidad $(unidad_usb) no activa;"
  [[ "$(systemctl show -p FragmentPath --value "$(unidad_usb)")" == /run/systemd/generator/* ]] || incompleto+=" la unidad no viene de $FSTAB;"
  ! fstab_activa "$SWAP_INT" || incompleto+=" $FSTAB aún activa $SWAP_INT;"
  ! activo "$SWAP_INT" || incompleto+=" $SWAP_INT sigue activo;"
  [[ -z "$incompleto" ]] || falla "migración INCOMPLETA:$incompleto usar $0 --revertir (o terminarla a mano)"
  echo "   $FSTAB: $(grep -c -xF "$LINEA_USB" "$FSTAB") línea del USB; $SWAP_INT $(fstab_activa "$SWAP_INT" && echo ACTIVO || echo comentado)"
  activo "$SWAP_INT" && echo "   AVISO: $SWAP_INT sigue activo" || echo "   $SWAP_INT no está activo$([[ -f "$SWAP_INT" ]] && echo ' (el fichero sigue en disco)')"
  local frag; frag="$(systemctl show -p FragmentPath --value "$(unidad_usb)")"
  echo "   unidad $(unidad_usb): $(systemctl show -p ActiveState --value "$(unidad_usb)") · generada desde $FSTAB: $([[ "$frag" == /run/systemd/generator/* ]] && echo sí || echo NO)"
  if [[ -e "$FSTAB_BAK" ]] && [[ $(date -d "$(uptime -s)" +%s) -gt $(stat -c %Z "$FSTAB_BAK") ]]; then
    echo "   hubo reinicio después de la migración ($(uptime -s)): el swap del USB volvió solo"
  else
    echo "   todavía NO ha habido reinicio después de la migración"
  fi
}

comprobar() {  # $1 = fichero de swap del USB a validar (ANTES de migrar: legible como usuario)
  paso "Precondiciones (solo lectura)"
  [[ "$USER" == majo1230 ]] || falla "ejecutar como majo1230 (no con sudo delante)"
  [[ "$(findmnt -no UUID "$USB" 2>/dev/null)" == "$UUID_USB" ]] || falla "AURORA_EXT ($UUID_USB) no está montado en $USB"
  echo "   USB AURORA_EXT montado en $USB ($(findmnt -no SOURCE "$USB"))"
  local f="$1"
  sudo -n test -f "$f" 2>/dev/null || [[ -f "$f" ]] || falla "no existe $f"
  local tam bloques
  tam="$(sudo -n stat -c %s "$f" 2>/dev/null || stat -c %s "$f")"
  bloques="$(sudo -n stat -c %b "$f" 2>/dev/null || stat -c %b "$f")"
  [[ "$tam" == "$TAM_ESPERADO" ]] || falla "$f no mide $TAM_ESPERADO bytes"
  [[ $((bloques * 512)) -ge $TAM_ESPERADO ]] || falla "$f tiene huecos (no válido como swap)"
  [[ "$(firma "$f")" == "SWAPSPACE2" ]] || falla "$f no tiene firma de swap (mkswap)"
  echo "   $f: 4 GiB, sin huecos, firma SWAPSPACE2"
  echo "   swaps activos: $(swapon --show=NAME,SIZE,USED,PRIO --noheadings | tr -s ' ' | paste -sd';')"
  echo "   memoria disponible: $(free -m | awk '/^Mem/{print $7}') MB"
}

case "${1:-}" in
  --solo-comprobar)
    if ya_migrado; then estado_migrado; echo; echo "La migración YA está hecha. No repetir --migrar."; exit 0; fi
    if [[ -e "$SWAP_ORIG" ]]; then comprobar "$SWAP_ORIG"; echo "   permisos actuales: $(stat -c '%U:%G %a' "$SWAP_ORIG") (se corregirán)"
    else comprobar "$SWAP_USB"; fi
    activo "$SWAP_INT" && echo "   $SWAP_INT activo (uso: $(swapon --show=NAME,USED --noheadings | awk -v f="$SWAP_INT" '$1==f{print $2}'))"
    fstab_activa "$SWAP_INT" && echo "   $FSTAB activa $SWAP_INT en el arranque"
    echo; echo "Precondiciones OK. Para migrar: $0 --migrar"
    ;;

  --migrar)
    if ya_migrado; then estado_migrado; echo; echo "La migración YA está hecha: no se hace nada."; exit 0; fi
    comprobar "$SWAP_ORIG"
    [[ ! -e "$DIR_SWAP" ]] || falla "ya existe $DIR_SWAP sin migración completa: devolver a mano el fichero (sudo mv $SWAP_USB $SWAP_ORIG && sudo rmdir $DIR_SWAP) o usar --revertir"
    [[ ! -e "$FSTAB_BAK" ]] || falla "ya existe $FSTAB_BAK: revisar antes de repetir"
    activo "$SWAP_ORIG" && falla "$SWAP_ORIG ya está activo: revisar antes de repetir"

    paso "1 · Directorio solo de root y permisos 600 (sudo)"
    sudo install -d -m 700 -o root -g root "$DIR_SWAP"
    sudo mv -- "$SWAP_ORIG" "$SWAP_USB"
    sudo chown root:root "$SWAP_USB"
    sudo chmod 600 "$SWAP_USB"
    [[ "$(sudo stat -c '%U:%G %a' "$SWAP_USB")" == "root:root 600" ]] || falla "permisos no aplicados"
    echo "   $SWAP_USB: root:root 600 en $DIR_SWAP (root 700)"

    paso "2 · Activar el swap del USB ANTES de retirar el interno"
    sudo swapon -p "$PRIO" "$SWAP_USB"
    activo "$SWAP_USB" || falla "$SWAP_USB no quedó activo"
    echo "   activo con prioridad $PRIO"

    paso "3 · Retirar el swap interno (el fichero NO se borra)"
    if activo "$SWAP_INT"; then sudo swapoff "$SWAP_INT"; fi
    ! activo "$SWAP_INT" || falla "$SWAP_INT sigue activo"
    echo "   $SWAP_INT desactivado"

    paso "4 · /etc/fstab persistente (copia en $FSTAB_BAK)"
    TOCANDO_FSTAB=1
    sudo cp -p "$FSTAB" "$FSTAB_BAK"
    sudo sed -i -E "s|^([[:space:]]*$SWAP_INT[[:space:]].*)$|# \\1   $MARCA|" "$FSTAB"
    if ! grep -qxF "$LINEA_USB" "$FSTAB"; then
      [[ -z "$(tail -c1 "$FSTAB")" ]] || echo | sudo tee -a "$FSTAB" >/dev/null   # el fichero acaba en salto de línea
      printf '%s\n' "$LINEA_USB" | sudo tee -a "$FSTAB" >/dev/null
    fi
    sudo findmnt --verify --tab-file "$FSTAB" >/dev/null || falla "findmnt --verify rechaza $FSTAB"
    sudo systemctl daemon-reload
    ! fstab_activa "$SWAP_INT" || falla "$FSTAB sigue activando $SWAP_INT"
    grep -qxF "$LINEA_USB" "$FSTAB" || falla "falta la línea del USB en $FSTAB"
    echo "   $SWAP_INT comentado; añadido: $LINEA_USB"
    TOCANDO_FSTAB=0

    paso "5 · Verificación"
    swapon --show
    bash "$RAIZ/entorno/scripts/preflight-check.sh" | sed -n '/-- Swap/,/-- Hooks/p;/ESTADO/p'
    echo
    echo "Siguiente: reiniciar HC-1 cuando convenga; después, entorno/nodos/verificar-tras-reinicio-hc1.sh \"<arranque previo>\""
    echo "y solo entonces: $0 --retirar-swap-interno"
    ;;

  --retirar-swap-interno)
    ya_migrado || falla "la migración no está hecha (falta $DIR_SWAP o la línea en $FSTAB)"
    estado_migrado
    [[ -e "$FSTAB_BAK" ]] || falla "no hay $FSTAB_BAK: --migrar no se ejecutó"
    grep -qxF "$LINEA_USB" "$FSTAB" || falla "$FSTAB no contiene la línea del USB"
    ! fstab_activa "$SWAP_INT" || falla "$FSTAB aún activa $SWAP_INT"
    # Tiene que haber habido un reinicio DESPUÉS de --migrar (ctime: cp -p conserva el mtime original).
    [[ $(date -d "$(uptime -s)" +%s) -gt $(stat -c %Z "$FSTAB_BAK") ]] || falla "no ha habido reinicio desde --migrar"
    activo "$SWAP_USB" || falla "$SWAP_USB no está activo tras el reinicio"
    # Lo activó systemd EN EL ARRANQUE (no un swapon manual posterior): ≤120 s desde el arranque (reloj monotónico).
    [[ $(systemctl show -p ActiveEnterTimestampMonotonic --value "$(unidad_usb)") -le 120000000 ]] \
      || falla "el swap del USB no se activó en el arranque (¿swapon manual?): no se borra $SWAP_INT"
    [[ "$(systemctl show -p FragmentPath --value "$(unidad_usb)")" == /run/systemd/generator/* ]] \
      || falla "el swap del USB no lo activó systemd desde $FSTAB"
    ! activo "$SWAP_INT" || falla "$SWAP_INT sigue activo"
    echo "   Reinicio comprobado y swap del USB activado desde $FSTAB. Se borra $SWAP_INT."
    sudo rm -- "$SWAP_INT"
    echo "   borrado (revertir exige ya recrearlo: fallocate -l 4G + chmod 600 + mkswap)"
    ;;

  --revertir)
    [[ -f "$SWAP_INT" ]] || falla "$SWAP_INT ya no existe: revertir exige recrearlo (fallocate + chmod 600 + mkswap)"
    activo "$SWAP_INT" || sudo swapon "$SWAP_INT"
    if activo "$SWAP_USB"; then sudo swapoff "$SWAP_USB"; fi
    sudo sed -i -E "\\|^$SWAP_USB[[:space:]]|d; s|^# ($SWAP_INT[[:space:]].*)   $MARCA$|\\1|" "$FSTAB"
    sudo findmnt --verify --tab-file "$FSTAB" >/dev/null || falla "findmnt --verify rechaza $FSTAB"
    sudo systemctl daemon-reload
    fstab_activa "$SWAP_INT" || falla "$FSTAB no reactiva $SWAP_INT: revisar a mano con $FSTAB_BAK"
    ! grep -qF "$SWAP_USB" "$FSTAB" || falla "$FSTAB aún menciona $SWAP_USB"
    [[ -e "$FSTAB_BAK" ]] && sudo mv -- "$FSTAB_BAK" "$FSTAB_BAK.revertido"
    swapon --show
    echo "revertido: swap interno activo y $FSTAB sin las líneas de esta migración (el fichero del USB queda en $DIR_SWAP)"
    ;;

  *) echo "uso: $0 --solo-comprobar | --migrar | --retirar-swap-interno | --revertir" >&2; exit 2 ;;
esac
