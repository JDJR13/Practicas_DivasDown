#!/bin/bash
# Instala los 4 servicios de El Fotobut para que arranquen solos al encender la Pi (clase 8/11, rubrica "arranque").
# Uso:  sudo ./scripts/instalar_servicios.sh            (desde la carpeta del proyecto, con el usuario que opera la cabina)
set -e
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo:  sudo $0"; exit 1; }
DIR="$(cd "$(dirname "$0")/.." && pwd)"
USR="${SUDO_USER:-papu}"
echo "Proyecto: $DIR   Usuario: $USR"
usermod -a -G gpio,i2c,spi,dialout,video,render,systemd-journal "$USR" || true
HOME_U="$(getent passwd "$USR" | cut -d: -f6)"
mkdir -p "$HOME_U/fotobut_sesiones" && chown "$USR:$USR" "$HOME_U/fotobut_sesiones"
for s in control vision qr monitor; do
  sed -e "s|__DIR__|$DIR|g" -e "s|__USER__|$USR|g" "$DIR/systemd/fotobut-$s.service" > "/etc/systemd/system/fotobut-$s.service"
done
systemctl daemon-reload
systemctl enable fotobut-control fotobut-vision fotobut-qr fotobut-monitor
systemctl restart fotobut-control fotobut-vision fotobut-qr fotobut-monitor
# Chromium en pantalla completa: se lanza con la sesion grafica (autologin + labwc). Ver scripts/instalar_autoarranque.sh
if command -v raspi-config >/dev/null; then raspi-config nonint do_boot_behaviour B4 || true; fi   # B4 = escritorio con autologin
sleep 3
systemctl --no-pager --lines=0 status fotobut-control fotobut-vision fotobut-qr fotobut-monitor | grep -E "●|Active:" || true
echo
echo "Listo. Para probar el arranque automatico:  sudo reboot"
echo "Despues del reinicio:  ./tools/medicion/medir_arranque.sh   y   ./tools/medicion/mostrar_prioridades.sh"
