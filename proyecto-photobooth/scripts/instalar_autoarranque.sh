#!/bin/bash
# Chromium a pantalla completa al iniciar la sesion grafica (los 3 procesos ya los arranca systemd: instalar_servicios.sh).
# Uso: ./scripts/instalar_autoarranque.sh      Quitar: rm ~/.config/autostart/fotobut.desktop ; borrar la linea kiosk.sh de ~/.config/labwc/autostart
D="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p ~/.config/autostart ~/.config/labwc
cat > ~/.config/autostart/fotobut.desktop <<EOT
[Desktop Entry]
Type=Application
Name=El Fotobut
Exec=$D/kiosk.sh
EOT
grep -qs "kiosk.sh" ~/.config/labwc/autostart 2>/dev/null || echo "$D/kiosk.sh &" >> ~/.config/labwc/autostart
echo "Autoarranque de la pantalla instalado. Reinicia para probar:  sudo reboot"
