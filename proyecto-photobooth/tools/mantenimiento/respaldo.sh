#!/bin/bash
# Respaldo de la cabina: caja negra, punto de control, registro de sesiones y registros de systemd (y las tiras con --fotos).
#   ./tools/mantenimiento/respaldo.sh                 -> ~/fotobut-respaldo-FECHA.tar.gz
#   ./tools/mantenimiento/respaldo.sh --fotos         incluye tambien las tiras guardadas en la microSD
# Para traerlo a tu PC:   scp papu@IP:~/fotobut-respaldo-*.tar.gz .
# Para revivir la cabina en otra tarjeta: instala con scripts/instalar.sh y luego  ./tools/mantenimiento/restaurar.sh ARCHIVO.tar.gz
set -e
OUT="$HOME/fotobut-respaldo-$(date +%Y%m%d-%H%M).tar.gz"
T=$(mktemp -d); mkdir -p "$T/respaldo/caja_negra" "$T/respaldo/sesiones" "$T/respaldo/sistema"
CN=/var/lib/fotobut/caja_negra; [ -d "$CN" ] || CN="$HOME/fotobut_estado/caja_negra"
cp -r "$CN"/. "$T/respaldo/caja_negra/" 2>/dev/null || sudo cp -r "$CN"/. "$T/respaldo/caja_negra/" 2>/dev/null || echo "(sin caja negra todavia)"
for f in estado.json sesiones.log contador.txt; do cp "$HOME/fotobut_sesiones/$f" "$T/respaldo/sesiones/" 2>/dev/null || true; done
[ "${1:-}" = "--fotos" ] && cp "$HOME"/fotobut_sesiones/*.jpg "$T/respaldo/sesiones/" 2>/dev/null || true
journalctl -u fotobut-control -u fotobut-vision -u fotobut-qr -u fotobut-monitor --no-pager -o short-iso -n 5000 > "$T/respaldo/journal.txt" 2>/dev/null || true
{ echo "fecha: $(date)"; echo "equipo: $(hostname)"; uname -a; echo; cat /etc/os-release 2>/dev/null | head -3
  echo; (cd "$(dirname "$0")/../.." && git log --oneline -1 2>/dev/null); echo; systemctl --no-pager --lines=0 status 'fotobut-*' 2>/dev/null | grep -E "●|Active:"
  echo; nmcli -t -f NAME,TYPE,AUTOCONNECT connection show 2>/dev/null; } > "$T/respaldo/sistema/resumen.txt"
cp /boot/firmware/config.txt "$T/respaldo/sistema/" 2>/dev/null || true
tar -czf "$OUT" -C "$T" respaldo && rm -rf "$T"
chmod 600 "$OUT"
echo "Respaldo listo: $OUT ($(du -h "$OUT" | cut -f1))"
