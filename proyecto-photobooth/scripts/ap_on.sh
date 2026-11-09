#!/bin/bash
# Enciende la red Wi-Fi de la cabina. OJO: usa la tarjeta wlan0; si estas conectado a la Pi por SSH
# a traves de Wi-Fi, ESTA CONEXION SE CORTA. Conectate por cable (Ethernet) o usa --force.
# Despues conecta tu PC/celular a "Fotobut" y entra por SSH a  papu@192.168.4.1
FORCE=0; [ "$1" = "--force" ] && FORCE=1
if [ $FORCE = 0 ]; then
  VIA=$(ip -4 route get "${SSH_CLIENT%% *}" 2>/dev/null | grep -o 'dev [a-z0-9]*' | head -1 | cut -d' ' -f2)
  if [ -n "$SSH_CLIENT" ] && [ "$VIA" = "wlan0" ]; then
    echo "Estas conectado por SSH a traves de Wi-Fi (wlan0): al encender el AP se cortaria tu sesion."
    echo "Usa Ethernet, o repite con --force sabiendo que tendras que unirte a la red 'Fotobut' y entrar a 192.168.4.1."
    exit 1
  fi
fi
nmcli connection show FotobutAP >/dev/null 2>&1 || { echo "Primero:  sudo ./scripts/setup_ap.sh"; exit 1; }
sudo nohup nmcli connection up FotobutAP >/tmp/ap_on.log 2>&1 &
sleep 6; cat /tmp/ap_on.log; ip -4 addr show wlan0 | grep inet || echo "(sin IP en wlan0: revisa /tmp/ap_on.log)"
