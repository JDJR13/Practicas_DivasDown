#!/bin/bash
# Apaga la red de la cabina y deja que wlan0 vuelva a conectarse a tu Wi-Fi normal.
sudo nmcli connection down FotobutAP
sudo nmcli device connect wlan0 2>/dev/null || true
