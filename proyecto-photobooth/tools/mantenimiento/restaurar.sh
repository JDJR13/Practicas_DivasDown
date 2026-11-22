#!/bin/bash
# Restaura un respaldo hecho con tools/mantenimiento/respaldo.sh (o descargado del panel) en una cabina recien instalada:
# recupera el contador de sesiones, el registro de sesiones, la caja negra y las tiras (si el respaldo las trae).
#   ./tools/mantenimiento/restaurar.sh fotobut-respaldo-FECHA.tar.gz
set -e
[ -f "${1:-}" ] || { echo "Uso: $0 ARCHIVO.tar.gz"; exit 1; }
T=$(mktemp -d); tar -xzf "$1" -C "$T" --no-same-owner
[ -d "$T/respaldo" ] || { echo "Ese archivo no es un respaldo de El Fotobut"; exit 1; }
sudo systemctl stop fotobut-vision fotobut-monitor 2>/dev/null || true
mkdir -p "$HOME/fotobut_sesiones"
if [ -d "$T/respaldo/sesiones" ]; then cp -n "$T"/respaldo/sesiones/* "$HOME/fotobut_sesiones/" 2>/dev/null || true; fi
if [ -f "$T/respaldo/sesiones/estado.json" ]; then cp "$T/respaldo/sesiones/estado.json" "$HOME/fotobut_sesiones/estado.json"; fi
if [ -d /var/lib/fotobut ]; then
  sudo mkdir -p /var/lib/fotobut/caja_negra && sudo cp -n "$T"/respaldo/caja_negra/*.jsonl /var/lib/fotobut/caja_negra/ 2>/dev/null || true
  sudo chown -R "$USER:$USER" /var/lib/fotobut
fi
rm -rf "$T"
sudo systemctl start fotobut-vision fotobut-monitor 2>/dev/null || true
echo "Restaurado. Contador de sesiones: $(python3 -c "import json;print(json.load(open('$HOME/fotobut_sesiones/estado.json')).get('contador','?'))" 2>/dev/null || cat "$HOME/fotobut_sesiones/contador.txt" 2>/dev/null || echo '?')"
