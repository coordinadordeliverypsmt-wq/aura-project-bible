#!/usr/bin/env bash
# RED · el objetivo de `codex review` debe estar DEMOSTRADO, no supuesto.
# Usa exclusivamente repositorios sinteticos: AURA NUNCA es objetivo, ni siquiera como caso negativo.
# Estas pruebas NO invocan a Codex: verifican que el wrapper ABORTA antes de invocarlo.
S="${S:?falta S=ruta a delegar.sh}"; M=/tmp/codex-mvp; f=0
ok(){ printf "  %-46s %s\n" "$1" "$2"; }
mal(){ printf "  %-46s %s  <-- FALLO\n" "$1" "$2"; f=$((f+1)); }
# Se ejecuta desde un cwd NEUTRO (ni ancestro ni descendiente de los repos) para que solo actue
# la barrera bajo prueba y no las reglas de anidamiento del cwd.
probar(){ # $1=descripcion $2=worktree $3=esperado(OK|FAILURE)
  r=$(cd /var/tmp && "$S" --worktree "$2" --review --solo-verificar 2>&1 | head -1)
  case "$r" in FAILURE*) got=FAILURE ;; *) got=OK ;; esac
  [ "$got" = "$3" ] && ok "$1" "$got" || mal "$1" "$got · $r"
}
probar "A · repo autorizado"              "$M/authorized"      OK
probar "C · repo anidado en otro repo"    "$M/parent/nested"   OK
# El caso «repo no autorizado» se RETIRA del criterio (CEO 2026-08-27): el wrapper garantiza
# COHERENCIA DEL OBJETIVO, no pertenencia a una allowlist. Un repo sintetico distinto de AURA es
# aceptable si se declara explicitamente como worktree autorizado. La expectativa era mia y era
# incorrecta; no se convierte en garantia nueva.
probar "D · repo padre, declarado explicito"  "$M/parent"          OK
probar "E · objetivo ambiguo (sin git)"   "$M/ambiguous"       FAILURE
probar "F · ruta inexistente"             "$M/no_existe"       FAILURE
[ $f -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL · $f"; exit 1; }
