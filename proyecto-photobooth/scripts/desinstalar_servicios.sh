#!/bin/bash
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo"; exit 1; }
systemctl disable --now fotobut-control fotobut-vision fotobut-qr 2>/dev/null || true
rm -f /etc/systemd/system/fotobut-{control,vision,qr}.service; systemctl daemon-reload; echo "Servicios eliminados"
