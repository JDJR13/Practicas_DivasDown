#!/bin/bash
# Apaga la red de la cabina y quita su encendido automatico. NetworkManager se conecta solo a otra red Wi-Fi guardada
# (si hay alguna al alcance); si no, se elige una desde el icono de Wi-Fi del escritorio o con:
#   sudo nmcli device wifi connect "NOMBRE" password "CLAVE"
# (Si estas por SSH en 192.168.4.1 esta sesion se corta: vuelve a entrar por la IP de tu red normal.)
# No se usa "nmcli device connect wlan0": si la unica red guardada es la de la cabina, la volveria a encender.
sudo -v || exit 1
sudo nmcli connection modify FotobutAP connection.autoconnect no 2>/dev/null || true
sudo nohup nmcli connection down FotobutAP >/tmp/ap_off.log 2>&1 &
sleep 1; echo "Apagando la red de la cabina (log: /tmp/ap_off.log). Conecta la Pi a otra red desde el icono de Wi-Fi si no lo hace sola."
