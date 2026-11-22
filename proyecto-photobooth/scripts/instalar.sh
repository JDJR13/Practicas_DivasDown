#!/bin/bash
# Instalacion completa de El Fotobut en una Raspberry Pi OS de 64 bits recien grabada (con escritorio).
#   git clone https://github.com/JDJR13/Practicas_DivasDown.git && cd Practicas_DivasDown/proyecto-photobooth
#   sudo ./scripts/instalar.sh          (necesita internet; al terminar:  sudo reboot)
# Hace, en orden: paquetes, buses y UART en config.txt, permisos, los 4 servicios, pantalla en modo kiosco y endurecimiento.
set -u
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo:  sudo $0"; exit 1; }
DIR="$(cd "$(dirname "$0")/.." && pwd)"; USR="${SUDO_USER:-papu}"
echo "== 1/6 Paquetes =="
apt-get update -q
apt-get install -y python3-lgpio python3-spidev python3-serial python3-pil python3-numpy python3-picamera2 \
  chromium i2c-tools nftables curl stm32flash dnsmasq-base || { echo "Fallo la instalacion de paquetes (¿hay internet?)"; exit 1; }

echo "== 2/6 Buses y UART (/boot/firmware/config.txt) =="
CFG=/boot/firmware/config.txt; [ -f "$CFG" ] || CFG=/boot/config.txt
cp -n "$CFG" "$CFG.antes-fotobut"
for l in "dtparam=i2c_arm=on" "dtparam=spi=on" "enable_uart=1" "dtoverlay=disable-bt" "dtoverlay=pwm,pin=18,func=2" "dtparam=watchdog=on"; do
  grep -qxF "$l" "$CFG" || { echo "$l" >> "$CFG"; echo "  agregado: $l"; }
done
if command -v raspi-config >/dev/null; then
  raspi-config nonint do_serial_cons 1 || true      # sin consola en el UART: lo usa el STM32
  raspi-config nonint do_serial_hw 0 || true
fi

echo "== 3/6 Servicios (control, vision, qr, monitor) =="
"$DIR/scripts/instalar_servicios.sh" || exit 1

echo "== 4/6 Pantalla en modo kiosco al encender =="
sudo -u "$USR" "$DIR/scripts/instalar_autoarranque.sh"
systemctl enable lightdm 2>/dev/null || true
command -v raspi-config >/dev/null && { raspi-config nonint do_boot_behaviour B4 || true; }

echo "== 5/6 Endurecimiento (cortafuegos, SSH, watchdog, registros) =="
"$DIR/scripts/blindar.sh"

echo "== 6/6 Red Wi-Fi propia de la cabina =="
"$DIR/scripts/setup_ap.sh" || echo "  (no se pudo crear el perfil del punto de acceso; se puede repetir despues)"

echo
echo "Instalacion terminada. Falta:"
echo "  1) sudo reboot                               la cabina debe aparecer sola en el monitor"
echo "  2) ./scripts/ap_on.sh --arranque --force     enciende la red 'Fotobut' en cada arranque (la Pi se queda sin internet)"
echo "  3) ./tools/pruebas/auditar_seguridad.sh              comprueba el endurecimiento"
echo "  4) firmware del STM32: ver la seccion 4 del README"
