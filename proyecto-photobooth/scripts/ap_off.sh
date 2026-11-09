#!/bin/bash
# Apaga la red de la cabina, quita su encendido automatico y deja que wlan0 vuelva a tu Wi-Fi normal.
# (Si estas por SSH en 192.168.4.1 esta sesion se corta: vuelve a entrar por la IP de tu red normal.)
sudo -v || exit 1
sudo nmcli connection modify FotobutAP connection.autoconnect no 2>/dev/null || true
sudo nohup sh -c 'nmcli connection down FotobutAP; sleep 2; nmcli device connect wlan0' >/tmp/ap_off.log 2>&1 &
sleep 1; echo "Apagando la red de la cabina; wlan0 vuelve a tu Wi-Fi normal en unos segundos (log: /tmp/ap_off.log)."
