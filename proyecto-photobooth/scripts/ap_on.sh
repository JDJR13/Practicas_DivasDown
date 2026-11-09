#!/bin/bash
# Enciende la red Wi-Fi de la cabina ("Fotobut"). Con ella encendida, la pantalla de resultado muestra los DOS codigos QR:
# 1) unirse al Wi-Fi  2) descargar la tira (http://192.168.4.1:8080/s/<sesion>).
#   ./scripts/ap_on.sh              solo ahora (al reiniciar la Pi vuelve a su Wi-Fi normal)
#   ./scripts/ap_on.sh --arranque   ahora y en cada arranque (modo cabina). Se quita con ./scripts/ap_off.sh
#   --force                         no preguntar aunque estes por SSH a traves de Wi-Fi
# OJO: usa la tarjeta wlan0. Si estas conectado a la Pi por SSH a traves de Wi-Fi, ESA SESION SE CORTA: despues conecta tu
# PC a la red "Fotobut" y entra con  ssh papu@192.168.4.1   (por cable Ethernet no se corta nada).
FORCE=0; BOOT=0
for a in "$@"; do
  case "$a" in --force) FORCE=1;; --arranque) BOOT=1;; *) echo "Uso: $0 [--arranque] [--force]"; exit 1;; esac
done
nmcli connection show FotobutAP >/dev/null 2>&1 || { echo "Primero:  sudo ./scripts/setup_ap.sh"; exit 1; }
if [ $FORCE = 0 ]; then
  VIA=$(ip -4 route get "${SSH_CLIENT%% *}" 2>/dev/null | grep -o 'dev [a-z0-9]*' | head -1 | cut -d' ' -f2)
  if [ -n "$SSH_CLIENT" ] && [ "$VIA" = "wlan0" ]; then
    echo "Estas conectado por SSH a traves de Wi-Fi (wlan0): al encender la red de la cabina se cortara esta sesion."
    echo "Repite agregando --force. Luego conecta tu PC a la red 'Fotobut' (clave fotobut2026) y entra con:  ssh $USER@192.168.4.1"
    exit 1
  fi
fi
sudo -v || exit 1                                        # pide la clave de sudo ahora (despues corre en segundo plano)
if [ $BOOT = 1 ]; then
  sudo nmcli connection modify FotobutAP connection.autoconnect yes connection.autoconnect-priority 100 \
    && echo "La red de la cabina se encendera sola en cada arranque (se quita con ./scripts/ap_off.sh)."
fi
sudo nohup nmcli connection up FotobutAP >/tmp/ap_on.log 2>&1 &
sleep 8; cat /tmp/ap_on.log
if ip -4 addr show wlan0 | grep -q "192.168.4.1"; then
  echo "Red 'Fotobut' encendida. La cabina es 192.168.4.1; la descarga queda en http://192.168.4.1:8080/"
else
  echo "(wlan0 no tiene la IP 192.168.4.1: revisa /tmp/ap_on.log y  journalctl -u NetworkManager -n 30)"
fi
