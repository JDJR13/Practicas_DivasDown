#!/bin/bash
# Quita los servicios de El Fotobut (no borra fotos ni registros).
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo"; exit 1; }
systemctl disable --now fotobut-control fotobut-vision fotobut-qr fotobut-monitor fotobut-firewall 2>/dev/null || true
rm -rf /etc/systemd/system/fotobut-{control,vision,qr,monitor,firewall}.service /etc/systemd/system/fotobut-{control,vision,qr}.service.d
nft delete table inet fotobut 2>/dev/null || true
systemctl daemon-reload; echo "Servicios eliminados"
