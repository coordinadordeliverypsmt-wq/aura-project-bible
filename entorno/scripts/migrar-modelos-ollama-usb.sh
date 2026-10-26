#!/usr/bin/env bash
# Traslada los modelos de Ollama al USB AURORA_EXT para que el preflight de AURA quede APTO (2026-10-07, v2 tras revisión
# de seguridad ECC). Medido: OLLAMA_MODELS=/home/majo1230/.ollama/models (disco interno) por el override de systemd; el
# preflight exige la ruta en el USB y ningún blob >100 MB en /home, /usr ni /opt.
#
# Uso:
#   migrar-modelos-ollama-usb.sh --solo-comprobar   solo lectura (no copia, no sudo)
#   migrar-modelos-ollama-usb.sh --migrar           procedimiento completo; pide la contraseña de sudo en los pasos 4-5
#
# Garantías:
#  - el original NO se borra hasta que hay DOS copias verificadas leyendo del MEDIO (no de la caché): USB y AURORA_BAK;
#  - no se reescribe el override existente: se añade un drop-in propio (zz-usb.conf); revertir = borrarlo;
#  - si algo falla a partir del paso 4, el script imprime cómo revertir.
# Comportamiento resultante (por diseño): sin el USB montado, Ollama NO arranca (RequiresMountsFor); tras enchufarlo,
# `sudo systemctl start ollama`. Desmontar el USB detiene Ollama.
set -euo pipefail

ORIGEN="/home/majo1230/.ollama/models"
USB="/media/majo1230/AURORA_EXT"
UUID_USB="c8847222-a540-4060-8908-b3de02ebdb6e"
DESTINO="$USB/ollama_models"
BAK="/media/majo1230/AURORA_BAK"
LABEL_BAK="AURORA_BAK"
RESPALDO="$BAK/ollama_models.respaldo-20261007"
DROPIN="/etc/systemd/system/ollama.service.d/zz-usb.conf"
MODELO="qwen2.5:0.5b"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
API="http://127.0.0.1:11434"

paso() { echo; echo "== $*"; }
falla() { echo "FALLA: $*" >&2; exit 1; }
revertir_msg() {
  cat >&2 <<EOF

FALLA en la línea $1. Cómo volver al estado anterior:
  sudo rm -f $DROPIN && sudo systemctl daemon-reload && sudo systemctl restart ollama
  (los modelos originales siguen en $ORIGEN salvo que el paso 7 ya hubiera terminado;
   en ese caso: mkdir -p $ORIGEN && cp -a $RESPALDO/. $ORIGEN/)
EOF
}
usb_ok() { [[ "$(findmnt -no UUID "$USB" 2>/dev/null)" == "$UUID_USB" ]] || falla "AURORA_EXT ($UUID_USB) no está montado en $USB"; }
bak_ok() {
  [[ "$(findmnt -no LABEL "$BAK" 2>/dev/null)" == "$LABEL_BAK" ]] || falla "AURORA_BAK no está montado en $BAK"
  [[ "$(stat -c %d "$BAK")" != "$(stat -c %d /)" ]] || falla "$BAK está en el disco interno"
}
servicio_pid() { systemctl show -p MainPID --value ollama; }
blobs_integros() {  # $1 = directorio; lee del MEDIO (O_DIRECT) para no validar contra la caché de páginas
  local d="$1" n=0 b h
  for b in "$d"/blobs/sha256-*; do
    h="$(dd if="$b" iflag=direct bs=1M status=none | sha256sum | cut -c1-64)"
    [[ "sha256-$h" == "$(basename "$b")" ]] || falla "blob dañado o ilegible: $b"
    n=$((n + 1))
  done
  [[ $n -gt 0 ]] || falla "no hay blobs en $d"
  echo "   $n blobs íntegros (leídos del medio) en $d"
}

paso "1 · Precondiciones (solo lectura)"
[[ "$USER" == majo1230 ]] || falla "ejecutar como majo1230 (no con sudo delante)"
usb_ok; echo "   USB AURORA_EXT montado en $USB ($(findmnt -no SOURCE "$USB"))"
[[ -w "$USB" ]] || falla "$USB no es escribible por $USER"
bak_ok; echo "   AURORA_BAK montado en $BAK ($(findmnt -no SOURCE "$BAK"))"
[[ -d "$ORIGEN/blobs" ]] || falla "no existe $ORIGEN/blobs"
compgen -G "$ORIGEN/blobs/*-partial*" >/dev/null && falla "hay una descarga de Ollama a medias: no migrar ahora"
blobs_integros "$ORIGEN"
tam=$(du -sk "$ORIGEN" | cut -f1); libre_usb=$(df -k --output=avail "$USB" | tail -1); libre_bak=$(df -k --output=avail "$BAK" | tail -1)
echo "   modelos: $((tam / 1024)) MB · libre USB: $((libre_usb / 1024)) MB · libre AURORA_BAK: $((libre_bak / 1024)) MB"
[[ $libre_usb -gt $((tam * 2)) ]] || falla "espacio insuficiente en el USB"
[[ $libre_bak -gt $((tam * 2)) ]] || falla "espacio insuficiente en AURORA_BAK"
[[ ! -e "$DESTINO" ]] || falla "ya existe $DESTINO: revisarlo antes de migrar"
[[ ! -e "$RESPALDO" ]] || falla "ya existe $RESPALDO: revisarlo antes de migrar"
[[ ! -e "$DROPIN" ]] || falla "ya existe $DROPIN: revisarlo antes de migrar"
systemctl is-active --quiet ollama || falla "ollama.service no está activo"
echo "   OLLAMA_MODELS actual: $(tr '\0' '\n' < /proc/"$(servicio_pid)"/environ | sed -n 's/^OLLAMA_MODELS=//p')"
[[ "${1:-}" == "--migrar" ]] || { echo; echo "Precondiciones OK. Para migrar: $0 --migrar"; exit 0; }
echo "   (no ejecutes «ollama pull» mientras dure la migración)"

paso "2 · Copia al USB (el original no se toca)"
usb_ok
mkdir -p "$DESTINO"
cp -a "$ORIGEN/." "$DESTINO/"
sync -f "$DESTINO"
paso "3 · Integridad de la copia del USB"
blobs_integros "$DESTINO"
diff -r "$ORIGEN/manifests" "$DESTINO/manifests" >/dev/null || falla "los manifiestos difieren"
echo "   manifiestos idénticos"

trap 'revertir_msg $LINENO' ERR
paso "4 · Drop-in de systemd (sudo): el override actual no se toca"
sudo tee "$DROPIN" >/dev/null <<EOF
# AURA 2026-10-07: modelos de Ollama en el USB AURORA_EXT (preflight). Revertir: borrar este fichero + daemon-reload.
[Unit]
# Sin el USB montado Ollama NO arranca: mejor un fallo visible que una copia nueva y vacía en el disco interno.
RequiresMountsFor=$USB

[Service]
Environment="OLLAMA_MODELS=$DESTINO"
EOF
sudo systemctl daemon-reload
echo "   escrito $DROPIN"

paso "5 · Reinicio de Ollama (sudo)"
sudo systemctl restart ollama
systemctl is-active --quiet ollama || falla "ollama.service no quedó activo tras el reinicio"
listo=0
for _ in $(seq 1 30); do curl -fsS -m 5 "$API/api/tags" >/dev/null 2>&1 && { listo=1; break; }; sleep 1; done
[[ $listo -eq 1 ]] || falla "la API de Ollama no respondió en 30 s"

paso "6 · Ollama funciona con el USB"
pid="$(servicio_pid)"
[[ "$(tr '\0' '\n' < /proc/"$pid"/environ | sed -n 's/^OLLAMA_MODELS=//p')" == "$DESTINO" ]] || falla "Ollama no usa $DESTINO"
echo "   OLLAMA_MODELS=$DESTINO (pid $pid)"
tags="$(curl -fsS -m 10 "$API/api/tags")" || falla "no se pudo listar modelos"
[[ "$tags" == *"\"$MODELO\""* ]] || falla "Ollama no lista $MODELO"
echo "   $MODELO listado"
json="$(curl -fsS -m 180 "$API/api/generate" -d "{\"model\":\"$MODELO\",\"prompt\":\"Responde solo: ok\",\"stream\":false}")" \
  || falla "la generación de prueba falló o tardó más de 180 s"
resp="$(printf '%s' "$json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("response","").strip())')" \
  || falla "respuesta de generación ilegible"
[[ -n "$resp" ]] || falla "el modelo no generó respuesta"
echo "   generación de prueba: «$resp»"

paso "7 · Respaldo en AURORA_BAK y retirada de la copia interna"
bak_ok
mkdir -p "$RESPALDO"
cp -a "$ORIGEN/." "$RESPALDO/"
sync -f "$RESPALDO"
blobs_integros "$RESPALDO"
usb_ok; bak_ok
blobs_integros "$DESTINO"
rm -rf -- "$ORIGEN"
echo "   copia interna retirada; respaldo en $RESPALDO"
trap - ERR

paso "8 · Preflight"
bash "$RAIZ/entorno/scripts/preflight-check.sh" | tail -8
cat <<EOF

Reversión completa (si alguna vez hiciera falta):
  mkdir -p $ORIGEN && cp -a $RESPALDO/. $ORIGEN/
  sudo rm -f $DROPIN && sudo systemctl daemon-reload && sudo systemctl restart ollama
EOF
